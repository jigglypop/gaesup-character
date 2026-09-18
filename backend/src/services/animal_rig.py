"""Separate, owner-scoped quadruped rig jobs with immutable uploaded sources."""
import hashlib
import os
import re
import subprocess

from src.services.asset_editor import _write_json
from src.services.avatar_factory import _LOCK, _QUEUE, digest
from src.services.character_parts import blender_executable
from src.services.character_pipeline import PipelineError, read_json, now
from src.services.glb import parse_glb
from src.services.object_storage import StoredPath as Path, local_workspace, publish_checkpoint
from src.services.process_identity import identity, state as process_state


class AnimalRig:
    def __init__(self, factory, owner):
        self.root = factory.root/str(int(owner))/'library/animals'

    def directory(self, animal_id):
        if not re.fullmatch(r'[a-f0-9]{24}', animal_id):
            raise PipelineError('not_found', '동물을 찾을 수 없습니다.', 404)
        return self.root/animal_id

    def listing(self):
        return {'items': [self.get(p.parent.name) for p in self.root.glob('*/record.json')]}

    def get(self, animal_id):
        directory = self.directory(animal_id)
        record = read_json(directory/'record.json')
        if not record:
            raise PipelineError('not_found', '동물을 찾을 수 없습니다.', 404)
        if record['status'] in ('accepted', 'running'):
            worker = read_json(directory/'output/runner.json')
            live = worker.get('process') or record.get('process')
            if process_state(live) == 'exited':
                record = {**record, 'status': 'paused', 'error': '리깅 재개 필요'}
        return {k:v for k,v in record.items() if k not in ('process', 'files')} | {
            'artifacts': [{'name': name, 'url': f'/api/studio/animals/{animal_id}/{name}'}
                          for name in ['source.glb', *record.get('files', {})]]}

    def upload(self, content, species, name):
        if not os.getenv('ASSET_S3_BUCKET'):
            raise PipelineError('storage_required', 'S3 저장소 설정이 필요합니다.', 503)
        try:
            document, _ = parse_glb(content, strict=True)
            if not document.get('meshes'):
                raise ValueError('No mesh')
            if any('uri' in buffer for buffer in document.get('buffers', [])) or any('uri' in image for image in document.get('images', [])):
                raise ValueError('External files')
        except (ValueError, KeyError, TypeError):
            raise PipelineError('invalid_model', '텍스쳐가 포함된 GLB 파일을 선택하세요.', 422) from None
        animal_id = hashlib.sha256(species.encode()+content).hexdigest()[:24]
        directory = self.directory(animal_id)
        with _LOCK:
            if not (directory/'record.json').is_file():
                directory.mkdir(parents=True, exist_ok=True)
                (directory/'source.glb').write_bytes(content)
                _write_json(directory/'record.json', {'id':animal_id,'name':name,'species':species,
                    'source_sha256': hashlib.sha256(content).hexdigest(), 'status':'uploaded',
                    'created_at':now(),'files':{},'rig_origin':'local_quadruped'})
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
            record.update(status='accepted', process=identity(), error=None)
            _write_json(directory/'record.json', record)
        return self.get(animal_id), True

    def execute(self, animal_id):
        directory = self.directory(animal_id); output = directory/'output'
        with _QUEUE:
            record = read_json(directory/'record.json')
            try:
                if digest(directory/'source.glb') != record['source_sha256']:
                    raise ValueError('Source changed')
                output.mkdir(exist_ok=True)
                _write_json(output/'input.json', {'source':str(directory/'source.glb'), 'output':str(output), 'species':record['species']})
                record.update(status='running', process=identity())
                _write_json(directory/'record.json', record)
                with local_workspace(output, inputs=[directory/'source.glb']):
                    with (output/'blender.log').open('wb') as log:
                        process = subprocess.Popen([blender_executable(), '--background', '--disable-autoexec', '--python-exit-code', '1', '--threads', '2', '--python',
                            str(Path(__file__).with_name('animal_rig_blender.py')), '--', str(output/'input.json')],
                            stdout=log, stderr=subprocess.STDOUT, env={**os.environ,'ASSET_STORAGE_WORKER_LOCAL':'1'},
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                        _write_json(output/'runner.json', {'process':identity(process.pid)})
                        publish_checkpoint(output/'runner.json')
                        try: code=process.wait(timeout=600)
                        except subprocess.TimeoutExpired:
                            process.terminate(); process.wait(timeout=10); raise
                        if code: raise ValueError('Blender rig failed')
                    seal=read_json(output/'complete.json')
                    if seal.get('input_sha256') != digest(output/'input.json'):
                        raise ValueError('Input changed')
                    for name, expected in seal['files'].items():
                        if Path(name).name != name or digest(output/name) != expected:
                            raise ValueError('Artifact changed')
                    record.update(status='complete', files=seal['files'], bones=seal['bones'],
                                  visual_review='required', error=None)
            except Exception:
                record.update(status='failed',error='사족 리깅 중단 · 원본 보존')
            _write_json(directory/'record.json',record)

    def artifact(self, animal_id, name):
        directory=self.directory(animal_id); self.get(animal_id)
        record=read_json(directory/'record.json')
        expected=record['source_sha256'] if name=='source.glb' else record.get('files',{}).get(name)
        path=directory/'source.glb' if name=='source.glb' else directory/'output'/name
        if not expected or Path(name).name != name or digest(path)!=expected:
            raise PipelineError('not_found','동물 파일을 찾을 수 없습니다.',404)
        return path
