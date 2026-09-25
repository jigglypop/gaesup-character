"""Separate, owner-scoped quadruped rig jobs with immutable uploaded sources."""
import hashlib
import os
import re
import subprocess

from src.services.asset_delivery import inspect_glb
from src.services.asset_editor import _write_json
from src.services.avatar_factory import _LOCK, _QUEUE, digest
from src.services.character_parts import blender_executable
from src.services.character_pipeline import PipelineError, read_json, now
from src.services.object_storage import StoredPath as Path, local_workspace, publish_checkpoint
from src.services.process_identity import identity, state as process_state


SPECIES = {'dog', 'cat', 'dragon'}
RIG_PROFILE = 'local-quadruped-v2'


class AnimalRig:
    def __init__(self, factory, owner):
        self.factory = factory
        self.root = factory.root/str(int(owner))/'library/animals'

    def directory(self, animal_id):
        if not re.fullmatch(r'[a-f0-9]{24}', animal_id):
            raise PipelineError('not_found', '동물을 찾을 수 없습니다.', 404)
        return self.root/animal_id

    def listing(self):
        return {'items': [self.get(p.parent.name) for p in sorted(
            self.root.glob('*/record.json'), reverse=True)]}

    def get(self, animal_id):
        directory = self.directory(animal_id)
        record = read_json(directory/'record.json')
        if not record:
            raise PipelineError('not_found', '동물을 찾을 수 없습니다.', 404)
        if record['status'] in ('accepted', 'running'):
            worker = read_json(directory/'output/runner.json')
            worker_state = process_state(worker.get('process')) if worker else 'unknown'
            executor_restarted = record.get('executor') != self.factory.instance
            if worker_state == 'exited' or (worker_state != 'running' and executor_restarted):
                record = {**record, 'status': 'paused', 'error': '리깅 재개 필요'}
        return {k:v for k,v in record.items() if k not in ('process', 'files')} | {
            'artifacts': [{'name': name, 'url': f'/api/studio/animals/{animal_id}/{name}'}
                          for name in ['source.glb', *record.get('files', {})]]}

    def upload(self, content, species, name):
        if not os.getenv('ASSET_S3_BUCKET', '').strip():
            raise PipelineError('storage_required', 'S3 저장소 설정이 필요합니다.', 503)
        if species not in SPECIES:
            raise PipelineError('invalid_species', '지원하지 않는 동물 종류입니다.', 422)
        name = name.strip()
        if not name or len(name) > 80:
            raise PipelineError('invalid_name', '이름은 1~80자로 입력하세요.', 422)
        inspection = inspect_glb(content, budget_warnings=True)
        if inspection['errors'] or not inspection.get('metrics', {}).get('meshes'):
            raise PipelineError('invalid_model', '유효한 GLB 동물 모델을 선택하세요.', 422) from None
        animal_id = hashlib.sha256(species.encode()+content).hexdigest()[:24]
        directory = self.directory(animal_id)
        with _LOCK:
            if not (directory/'record.json').is_file():
                directory.mkdir(parents=True, exist_ok=True)
                (directory/'source.glb').write_bytes(content)
                _write_json(directory/'record.json', {'id':animal_id,'name':name,'species':species,
                    'source_sha256': hashlib.sha256(content).hexdigest(), 'status':'uploaded',
                    'created_at':now(),'updated_at':now(),'files':{},'rig_origin':RIG_PROFILE,
                    'source_metrics': inspection['metrics'], 'source_warnings': inspection.get('warnings', [])})
        return self.get(animal_id)

    def start(self, animal_id):
        directory = self.directory(animal_id)
        with _LOCK:
            record = self.get(animal_id)
            if record['status'] in ('accepted', 'running', 'complete'):
                return record, False
            runner = read_json(directory/'output/runner.json')
            if runner and process_state(runner.get('process')) != 'exited':
                raise PipelineError('worker_running', '기존 리깅 프로세스가 실행 중입니다.', 409)
            if not blender_executable():
                raise PipelineError('blender_unavailable', 'Blender 연결이 필요합니다.', 503)
            record = read_json(directory/'record.json')
            record.update(status='accepted', executor=self.factory.instance, process=identity(),
                          updated_at=now(), error=None)
            _write_json(directory/'record.json', record)
            output = directory/'output'
            output.mkdir(exist_ok=True)
            _write_json(output/'runner.json', {'process': identity(), 'phase': 'queued'})
        return self.get(animal_id), True

    def execute(self, animal_id):
        directory = self.directory(animal_id); output = directory/'output'
        output.mkdir(exist_ok=True)
        record = None
        try:
            # Same order as part assembly (storage workspace, then the Blender queue) so they cannot deadlock.
            with local_workspace(output, inputs=[directory/'source.glb']), _QUEUE:
                record = read_json(directory/'record.json')
                if record.get('status') != 'accepted' or record.get('executor') != self.factory.instance:
                    record = None
                    return
                self._run(directory, output, record)
        except Exception:
            # The workspace could not publish its files: this attempt failed and keeps its source.
            if record is not None:
                record.update(status='failed', updated_at=now(), error='사족 리깅 중단 · 원본 보존')
        # Publish the outcome only after the workspace has uploaded its artifacts.
        if record is not None:
            _write_json(directory/'record.json', record)

    def _run(self, directory, output, record):
        try:
            if digest(directory/'source.glb') != record['source_sha256']:
                raise ValueError('Source changed')
            _write_json(output/'input.json', {'source':str(directory/'source.glb'), 'output':str(output),
                'species':record['species'], 'rig_profile':RIG_PROFILE,
                'source_sha256':record['source_sha256']})
            record.update(status='running', executor=self.factory.instance, process=identity(), updated_at=now())
            _write_json(directory/'record.json', record)
            with (output/'blender.log').open('wb') as log:
                process = subprocess.Popen([blender_executable(), '--background', '--factory-startup',
                    '--disable-autoexec', '--python-exit-code', '1', '--threads', '2', '--python',
                    str(Path(__file__).with_name('animal_rig_blender.py')), '--', str(output/'input.json')],
                    stdout=log, stderr=subprocess.STDOUT, env={**os.environ,'ASSET_STORAGE_WORKER_LOCAL':'1'},
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                _write_json(output/'runner.json', {'process':identity(process.pid), 'phase':'blender'})
                publish_checkpoint(output/'runner.json')
                try: code=process.wait(timeout=600)
                except subprocess.TimeoutExpired:
                    process.terminate(); process.wait(timeout=10); raise
                if code: raise ValueError('Blender rig failed')
            seal=read_json(output/'complete.json')
            if (seal.get('input_sha256') != digest(output/'input.json') or
                    seal.get('source_sha256') != record['source_sha256'] or
                    seal.get('rig_profile') != RIG_PROFILE):
                raise ValueError('Input changed')
            files = seal.get('files')
            if set(files or {}) != {'rigged.glb', 'master.blend'}:
                raise ValueError('Incomplete rig artifacts')
            for name, expected in files.items():
                if Path(name).name != name or digest(output/name) != expected:
                    raise ValueError('Artifact changed')
            if type(seal.get('bones')) is not int or seal['bones'] < 10:
                raise ValueError('Invalid skeleton')
            record.update(status='complete', files=files, bones=seal['bones'],
                          rig_profile=RIG_PROFILE, visual_review='required', updated_at=now(), error=None)
        except Exception:
            record.update(status='failed', updated_at=now(), error='사족 리깅 중단 · 원본 보존')

    def artifact(self, animal_id, name):
        directory=self.directory(animal_id); self.get(animal_id)
        record=read_json(directory/'record.json')
        expected=record['source_sha256'] if name=='source.glb' else record.get('files',{}).get(name)
        path=directory/'source.glb' if name=='source.glb' else directory/'output'/name
        if not expected or Path(name).name != name or digest(path)!=expected:
            raise PipelineError('not_found','동물 파일을 찾을 수 없습니다.',404)
        return path
