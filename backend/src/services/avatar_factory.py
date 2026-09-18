"""Owner-scoped, resumable local avatar production. No provider submissions."""
from copy import deepcopy
import hashlib
import io
import json
import logging
import os
from src.services.object_storage import StoredPath as Path
import re
import subprocess
from threading import RLock, Semaphore
import uuid

from PIL import Image

from src.paths import BACKEND_ROOT
from src.services.asset_delivery import inspect_glb
from src.services.asset_editor import _write_json
from src.services.character_parts import blender_executable
from src.services.character_pipeline import CharacterPipeline, PipelineError, read_json, now
from src.services.character_segmentation import PART_ROLES, triangle_indices
from src.services.glb import parse_glb
from src.services.process_identity import identity, state as process_state
from src.services.object_storage import local_workspace, sha256

LOGGER = logging.getLogger(__name__)
_QUEUE = Semaphore(1)
_LOCK = RLock()
PROFILE = {'id': 'maple-sd-v2', 'name': '메이플풍 SD 공통 몸 · 기본복', 'rig': 'gaesup-humanoid-v1',
           'bones': 23, 'height': 1.81, 'head_height': .74, 'head_ratio': 2.45,
           'body_origin': 'authored_clothed_template', 'base_outfit': 'bald_face_tshirt_shorts',
           'pose': 'A-pose', 'visual_approval': 'pending'}
IMAGE_PROFILE = {**PROFILE, 'id': 'maple-chibi-v3', 'name': '대두 SD · 짧은 팔다리 · 기본복',
                 'rig': 'gaesup-maple-v1', 'body_archetype': 'MAPLE_CHIBI_V1',
                 'height': 1.81, 'head_height': 1.14, 'head_ratio': 1.59}


def digest(path):
    return sha256(path)


class AvatarFactory:
    def __init__(self, root):
        self.data = Path(root).resolve(); self.root = self.data/'avatar-factory'
        self.pipeline = CharacterPipeline(self.data)
        self.instance = uuid.uuid4().hex

    def directory(self, owner, job_id):
        if not re.fullmatch(r'[a-f0-9]{24}', job_id):
            raise PipelineError('not_found', '생산 작업을 찾을 수 없습니다.', 404)
        return self.root/str(int(owner))/job_id

    def create(self, owner, key, payload):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}', key):
            raise PipelineError('invalid_key', '생산 요청 식별자가 필요합니다.', 422)
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        job_id = hashlib.sha256(f'{owner}:{key}'.encode()).hexdigest()[:24]
        directory = self.directory(owner, job_id)
        with _LOCK:
            if (directory/'job.json').exists():
                job = read_json(directory/'job.json')
                if job['fingerprint'] != fingerprint:
                    raise PipelineError('idempotency_conflict', '같은 요청에 다른 원본 또는 설정이 있습니다.')
                return self.get(owner, job_id), False
            if not blender_executable():
                raise PipelineError('blender_unavailable', '로컬 Blender 설치를 확인해 주세요.', 422)
            source = self.pipeline.detail(payload['character_id'], owner)
            if not source['model_id'] or source['model_sha256'] != payload['source_sha256']:
                raise PipelineError('source_changed', '원본 GLB 버전이 달라졌습니다. 다시 불러와 주세요.')
            path = self.pipeline.artifact(source['id'], owner, source['model_id'])
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != payload['source_sha256']:
                raise PipelineError('source_changed', '원본이 변경되었습니다.')
            doc, binary = parse_glb(content, strict=True)
            selections = payload.get('selections', []); assigned = set()
            for item in selections:
                try:
                    node = doc['nodes'][item['node_index']]
                    primitive = doc['meshes'][node['mesh']]['primitives'][item['primitive_index']]
                    count = len(triangle_indices(doc, binary, primitive))
                    for face in item['faces']:
                        address = (item['node_index'], item['primitive_index'], face)
                        if face < 0 or face >= count or address in assigned:
                            raise ValueError('Invalid face')
                        assigned.add(address)
                except (IndexError, KeyError, ValueError) as exc:
                    raise PipelineError('invalid_selection', '원본에 없는 면 또는 겹치는 파츠 선택입니다.', 422) from exc
            directory.mkdir(parents=True, exist_ok=False)
            (directory/'source.glb').write_bytes(content)
            output = directory/'output'; output.mkdir()
            input_data = {'source': str(directory/'source.glb'), 'source_sha256': source['model_sha256'],
                          'parts': source['parts'], 'selections': selections, 'output': str(output),
                          'rig': str(BACKEND_ROOT/'assets/avatars/rig-v1.json'),
                          'motions': str(BACKEND_ROOT/'assets/avatars/manual-v1/body-sd-neutral-v1.glb')}
            _write_json(output/'input.json', input_data)
            job = {'id': job_id, 'fingerprint': fingerprint, 'executor': self.instance, 'executor_process': identity(),
                   'character_id': source['id'], 'character_name': source['name'], 'source_sha256': source['model_sha256'],
                   'source_model_id': source['model_id'], 'source_rig_origin': source['rig_origin'],
                   'profile': PROFILE, 'status': 'accepted', 'created_at': now(), 'updated_at': now(),
                   'error': None, 'review': {'decision': 'pending'}}
            _write_json(directory/'job.json', job)
            return self.get(owner, job_id), True

    def execute(self, owner, job_id):
        with local_workspace(self.directory(owner, job_id)):
            return self._execute_local(owner, job_id)

    def _execute_local(self, owner, job_id):
        directory = self.directory(owner, job_id); output = directory/'output'
        with _QUEUE:
            job = read_json(directory/'job.json')
            if job.get('status') != 'accepted' or job.get('executor') != self.instance:
                return
            try:
                job.update(status='running', updated_at=now()); _write_json(directory/'job.json', job)
                command = [blender_executable(), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
                           '--python', str(Path(__file__).with_name('avatar_factory_blender.py')), '--', str(output/'input.json')]
                with (output/'blender.log').open('wb') as log:
                    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                               env={**os.environ, 'ASSET_STORAGE_WORKER_LOCAL': '1'},
                                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    _write_json(output/'runner.json', {'process': identity(process.pid)})
                    try:
                        code = process.wait(timeout=600)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
                        raise ValueError('Factory worker timed out')
                if code:
                    raise ValueError('Blender factory worker failed')
                self.finalize(owner, job_id)
            except Exception as exc:
                LOGGER.exception('Avatar factory failed: %s', job_id)
                job.update(status='failed', error=exc.message if isinstance(exc, PipelineError) else 'Blender 조립·출력 중 오류가 발생했습니다. 원본과 생성한 파츠는 보존했습니다.', updated_at=now())
                _write_json(directory/'job.json', job)

    def finalize(self, owner, job_id):
        directory = self.directory(owner, job_id); output = directory/'output'
        job = read_json(directory/'job.json'); seal = read_json(output/'worker-complete.json')
        if (seal.get('source_sha256') != digest(directory/('source.png' if job.get('input_kind') == 'image' else 'source.glb'))
                or seal.get('input_sha256') != digest(output/'input.json')):
            raise ValueError('Factory source receipt mismatch')
        required = {'body.glb', 'character.glb', 'workspace.glb', 'master.blend', 'rest.png', 'side.png', 'pose.png', 'compilation.json'}
        if not required.issubset(seal.get('files', {})):
            raise ValueError('Factory evidence missing')
        for filename, expected in seal['files'].items():
            if Path(filename).name != filename or digest(output/filename) != expected:
                raise ValueError('Factory artifact changed')
        for filename in ('body.png', 'rest.png', 'side.png', 'pose.png'):
            if filename not in seal['files']:
                continue
            with Image.open(io.BytesIO((output/filename).read_bytes())) as render:
                if render.mode != 'RGBA' or render.getchannel('A').getbbox() is None:
                    raise PipelineError('empty_review_render', f'{filename} 검수 이미지가 비어 있습니다. 기존 파츠로 다시 조립해 주세요.')
        result = read_json(output/'compilation.json'); records = []; qualities = {}
        for filename in ('character.glb', 'workspace.glb'):
            quality = inspect_glb((output/filename).read_bytes(), budget_warnings=True)
            if quality['errors'] or set(quality['metrics']['joints']) != set(result['bones']) or len(quality['metrics']['animations']) != 7:
                reason = ', '.join(quality['errors']) or '공통 23본·7개 동작 계약 불일치'
                raise PipelineError('assembly_validation_failed', f'{filename} 품질 검사 실패: {reason}. 생성한 파츠는 보존했습니다.')
            qualities[filename] = quality
        for item in result['assets']:
            filename = item['file']
            if filename not in seal['files']:
                raise ValueError('Unsealed factory asset')
            quality = inspect_glb((output/filename).read_bytes(), budget_warnings=True)
            if quality['errors'] or set(quality['metrics']['joints']) != set(result['bones']):
                raise ValueError('Factory canonical GLB validation failed: ' + filename)
            qualities[item['key']] = quality
            asset_id = f'factory-{job_id}-{item["key"]}'
            uri = f'/api/avatars/assets/{asset_id}/model'
            manifest = {'schemaVersion': 1, 'assetId': asset_id, 'version': 1,
                        'kind': 'avatar-body' if item['key'] == 'body' else 'avatar-part', 'slot': item['key'],
                        'rig': job['profile']['rig'], 'bodyArchetypes': [job['profile'].get('body_archetype', 'SD_NEUTRAL_V1')], 'source': {'uri': uri},
                        'bones': result['bones'], 'meshes': item['meshes'], 'attachment': {'mode': 'skinned'}}
            for field in ('bodyRegions', 'hideBodyRegions'):
                if field in item:
                    manifest[field] = item[field]
            if item.get('wholeBody'):
                manifest.update(wholeBody=True, bodyArchetypes=['MAPLE_WHOLE_V1'])
            records.append({'id': asset_id, 'name': f'{job["character_name"]} · {item["key"]}', 'kind': 'characterPart',
                            'url': uri, 'format': 'glb', 'tags': ['avatar-factory', 'review-required'],
                            'metadata': {'avatar': manifest, 'factory': {'jobId': job_id, 'sourceSha256': job['source_sha256'],
                                                                       'bodyProfile': job['profile']['id'], 'visualApproval': 'pending'}}})
        _write_json(output/'quality.json', qualities)
        _write_json(output/'catalog.json', {'assets': records})
        equipment = {r['metadata']['avatar']['slot']: r['id'] for r in records if r['metadata']['avatar']['slot'] != 'body'}
        if 'onepiece' in equipment:
            equipment.pop('top', None); equipment.pop('bottom', None)
        job.update(status='review_required', updated_at=now(), model_sha256=seal['files']['character.glb'],
                   outfit={'body': records[0]['id'], 'equipment': equipment},
                   evidence={key: value for key, value in result.items() if key not in ('selections', 'assets', 'bones')},
                   technical={'passed': True, 'bone_count': 23, 'parts': len(records)-1, 'source_preserved': True,
                              'file_bytes': qualities['character.glb']['file_bytes'],
                              'texture_pixels': qualities['character.glb']['metrics']['texture_pixels'],
                              'resource_warnings': qualities['character.glb'].get('warnings', [])},
                   files={**job.get('files', {}), **seal['files'], 'quality.json': digest(output/'quality.json'), 'catalog.json': digest(output/'catalog.json')})
        _write_json(directory/'job.json', job)

    def get(self, owner, job_id):
        directory = self.directory(owner, job_id); job = read_json(directory/'job.json')
        if not job:
            raise PipelineError('not_found', '생산 작업을 찾을 수 없습니다.', 404)
        if job['status'] in ('pipeline_queued', 'pipeline_running') and job['executor'] != self.instance and process_state(job.get('executor_process')) == 'exited':
            job.update(status='pipeline_paused', error='서버가 재시작되었습니다. 기존 작업 이어가기로 저장한 단계부터 복구하세요.')
            _write_json(directory/'job.json', job)
        if job['status'] in ('accepted', 'running') and job['executor'] != self.instance:
            worker_state = process_state(read_json(directory/'output/runner.json').get('process'))
            if (directory/'output/worker-complete.json').exists() and worker_state == 'exited':
                self.finalize(owner, job_id); job = read_json(directory/'job.json')
            elif worker_state == 'exited' or (worker_state != 'running' and process_state(job.get('executor_process')) == 'exited'):
                job.update(status='recovery_required', error='서버가 중단된 생산 작업입니다. 원본과 중간 파일을 보존했습니다. 새 버전으로 다시 생산해 주세요.')
                _write_json(directory/'job.json', job)
        public = {k: deepcopy(v) for k, v in job.items() if k not in ('executor', 'executor_process', 'fingerprint', 'files')}
        public['progress'] = read_json(directory/'output/progress.json', {'stage': 'queued', 'message': '로컬 생산 대기 중'})
        public['artifacts'] = [{'name': name, 'url': f'/api/avatar-factory/jobs/{job_id}/artifacts/{name}'} for name in job.get('files', {})]
        public['next_actions'] = []
        if job.get('input_kind') == 'image' and job['status'] in ('pipeline_paused', 'failed', 'recovery_required'):
            state = read_json(directory/'pipeline.json')
            blocked = any(p['image']['status'] not in ('pending', 'received', 'succeeded') and
                          not (p['image']['status'] == 'submitting' and (directory/'output'/f'{p["slot"]}-provider.response.json').is_file())
                          for p in state.get('parts', []))
            if state.get('production_spec'):
                from src.services.avatar_multiview_images import can_resume
                blocked = not can_resume(directory, state)
            runner = read_json(directory/'output/runner.json')
            if job['status'] in ('failed', 'recovery_required') and runner and process_state(runner.get('process')) != 'exited':
                blocked = True
            for p in state.get('parts', []):
                task = read_json(directory/'parts'/p['slot']/'character.json')
                blocked = blocked or bool(task and (not task.get('task_id') or task.get('status') in ('FAILED', 'CANCELED')))
            public['next_actions'] = [{'id': 'resume', 'enabled': not blocked,
                                       'reason': '이미 시도한 요청의 결과 확인이 필요합니다. 자동 재제출하지 않습니다.' if blocked else None}]
        if job.get('production_mode') == 'character_parts':
            from src.services.avatar_character_flow import character_flow
            public['character_flow'] = character_flow(directory, public)
            public['progress'] = {key: public['character_flow'][key] for key in ('stage', 'message')}
            from src.services.avatar_image_recovery import decorate_job
            decorate_job(directory, public)
            from src.services.avatar_production_progress import production_progress
            public['production_progress'] = production_progress(directory, public)
        return public

    def listing(self, owner):
        return [self.get(owner, path.parent.name) for path in sorted((self.root/str(int(owner))).glob('*/job.json'), reverse=True)]

    def artifact(self, owner, job_id, filename):
        directory = self.directory(owner, job_id); job = read_json(directory/'job.json')
        if Path(filename).name != filename or filename not in job.get('files', {}):
            raise PipelineError('not_found', '생산 파일을 찾을 수 없습니다.', 404)
        path = directory/'output'/filename
        if not path.is_file() or digest(path) != job['files'][filename]:
            raise PipelineError('artifact_changed', '검증한 생산 파일과 현재 파일이 다릅니다.')
        return path


def factory_records(root, owner):
    if owner is None:
        return []
    records = []
    for path in (Path(root)/'avatar-factory'/str(int(owner))).glob('*/job.json'):
        job = read_json(path)
        if job.get('status') in ('review_required', 'approved'):
            # Native Meshy characters keep their arbitrary rig outside the 23-bone wardrobe catalog.
            if 'catalog.json' not in job.get('files', {}):
                continue
            catalog = path.parent/'output/catalog.json'
            if digest(catalog) != job.get('files', {}).get('catalog.json'):
                raise PipelineError('catalog_changed', '생산 카탈로그가 변경되었습니다.')
            records.extend(read_json(catalog).get('assets', []))
    return records
