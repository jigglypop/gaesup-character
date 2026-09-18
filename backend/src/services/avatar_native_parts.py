"""Versioned local wardrobe candidates; no paid submissions or approval changes."""
import hashlib
import json
import os
from src.services.object_storage import StoredPath as Path
import re
import subprocess

from src.services.asset_editor import _write_json
from src.services.avatar_factory import _LOCK, _QUEUE, digest
from src.services.avatar_meshy import AvatarMeshy
from src.services.character_parts import blender_executable
from src.services.character_pipeline import PipelineError, read_json
from src.services.process_identity import identity, state as process_state
from src.services.object_storage import local_workspace, publish_checkpoint
from src.services.avatar_production_spec import production_spec
from src.services.avatar_equipment import NATIVE_EQUIPMENT as EQUIPMENT

SLOTS = ('hair', 'hat', 'top', 'bottom', 'shoes')
LEGACY_SLOTS = ('hairBack', 'hairFront', 'hat', 'top', 'bottom', 'shoes')
RECIPE = 'native-parts-v9-separate-hair-hat'


class AvatarNativeParts:
    def __init__(self, factory):
        self.factory = factory

    def root(self, owner, job):
        self.factory.get(owner, job)
        return self.factory.directory(owner, job)/'native-parts'

    def get(self, owner, job):
        root = self.root(owner, job)
        pointer = read_json(root/'current.json')
        if not pointer:
            return {'status': 'not_started', 'parts': [], 'artifacts': []}
        version = pointer['version']; directory = root/version
        record = read_json(directory/'record.json')
        status = record['status']
        if status in ('accepted', 'running') and process_state(record.get('process')) == 'exited':
            status = 'recovery_required'
        error = '조립 재개 필요' if status == 'qc_failed' else record.get('error')
        return {'version': version, 'status': status, 'error': error,
                **record.get('result', {}),
                'fit_update_available': record.get('result', {}).get('fitting_revision') != production_spec()['fitting']['revision'],
                'parts': record.get('result', {}).get('parts', []),
                'artifacts': [{'name': name, 'sha256': value,
                    'url': f'/api/avatar-factory/jobs/{job}/native-parts/{version}/{name}'}
                    for name, value in record.get('files', {}).items()]}

    def start(self, owner, job, *, canonical_pose=False):
        job_state = self.factory.get(owner, job)
        if job_state.get('production_mode') != 'character_parts':
            raise PipelineError('parts_required', '몸과 의상을 개별 생성한 파츠 작업이 필요합니다.', 422)
        provider = AvatarMeshy(self.factory); state = provider.get(owner, job)
        if not state.get('version'):
            raise PipelineError('rig_required', '먼저 몸의 Meshy 리깅과 동작을 가져오세요.', 422)
        body = provider.artifact(owner, job, state['version'], 'model.glb')
        pipeline = read_json(self.factory.directory(owner, job)/'pipeline.json')
        source_slots = tuple(part['slot'] for part in pipeline.get('parts', []) if part['slot'] != 'body')
        clothing_slots = set(source_slots)-set(EQUIPMENT)
        if clothing_slots not in (set(SLOTS), set(LEGACY_SLOTS), {'head', 'top', 'bottom', 'shoes'}):
            raise PipelineError('parts_required', '저장된 캐릭터 파츠 구성을 확인하세요.', 422)
        parts = []
        for slot in source_slots:
            path = self.factory.artifact(owner, job, f'generated-{slot}.glb')
            parts.append({'slot': slot, 'path': str(path), 'sha256': digest(path)})
        contract = {'recipe': RECIPE, 'worker_sha256': digest(Path(__file__).with_name('avatar_native_parts_blender.py')),
                    'canonical_pose': canonical_pose,
                    'binding_worker_sha256': digest(Path(__file__).with_name('avatar_standard_blender.py')),
                    'body_layers_sha256': digest(Path(__file__).with_name('avatar_body_layers.py')),
                    'head_geometry_sha256': digest(Path(__file__).with_name('avatar_head_geometry.py')),
                    'arm_geometry_sha256': digest(Path(__file__).with_name('avatar_arm_geometry.py')),
                    'render_budget_sha256': digest(Path(__file__).with_name('avatar_render_budget.py')),
                    'equipment_sha256': digest(Path(__file__).with_name('avatar_equipment.py')),
                    'body': digest(body), 'parts': [(p['slot'], p['sha256']) for p in parts]}
        pipeline = read_json(self.factory.directory(owner, job)/'pipeline.json')
        # Image receipts remain frozen. Local reassembly uses the current sizing
        # contract even for old single-view jobs and oversized image measurements.
        fit_spec = (pipeline['production_spec'] if pipeline.get('base_body')
                    else production_spec(pipeline.get('hair_length', 'source')))
        measurements = {p['slot']: p.get('target_bounds_m') for p in pipeline.get('parts', [])}
        contract.update(production_spec_sha256=fit_spec['sha256'],
                        source_spec_sha256=(pipeline.get('production_spec') or {}).get('sha256'),
                        fit_worker_sha256=digest(Path(__file__).with_name('avatar_fit_geometry.py')))
        version = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()[:24]
        root = self.root(owner, job); directory = root/version
        if not blender_executable():
            raise PipelineError('blender_unavailable', '로컬 Blender 설치가 필요합니다.', 422)
        with _LOCK:
            previous = read_json(root/'current.json')
            if previous:
                current = read_json(root/previous['version']/'record.json')
                if current.get('status') in ('accepted', 'running') and process_state(current.get('process')) != 'exited':
                    return self.get(owner, job), False
            record = read_json(directory/'record.json')
            if record.get('status') == 'review_required':
                _write_json(root/'current.json', {'version': version})
                return self.get(owner, job), False
            runner = read_json(directory/'runner.json')
            if runner and process_state(runner.get('process')) != 'exited':
                raise PipelineError('worker_running', '기존 Blender 작업이 아직 실행 중입니다.', 409)
            directory.mkdir(parents=True, exist_ok=True)
            _write_json(directory/'input.json', {'source': str(body), 'source_sha256': digest(body),
                        'parts': parts, 'output': str(directory), 'contract': contract,
                        'production_spec': fit_spec, 'source_measurements': measurements,
                        'canonical_pose': canonical_pose})
            _write_json(directory/'record.json', {'status': 'accepted', 'process': identity(), 'files': {}})
            _write_json(root/'current.json', {'version': version})
        return self.get(owner, job), True

    def execute(self, owner, job):
        root = self.root(owner, job)
        version = read_json(root/'current.json')['version']
        directory = root/version
        payload = read_json(directory/'input.json')
        # Reassembly needs the saved input GLBs and this output version, not every
        # prior render, provider response, and .blend in the job's history.
        inputs = [payload['source'], *(part['path'] for part in payload['parts'])]
        with local_workspace(directory, inputs=inputs):
            return self._execute_local(owner, job)

    def _execute_local(self, owner, job):
        root = self.root(owner, job); version = read_json(root/'current.json')['version']
        directory = root/version
        with _QUEUE:
            record = read_json(directory/'record.json')
            if record['status'] != 'accepted':
                return
            record.update(status='running', process=identity())
            _write_json(directory/'record.json', record)
            publish_checkpoint(directory/'record.json')
            try:
                command = [blender_executable(), '--background', '--factory-startup', '--disable-autoexec',
                           '--python-exit-code', '1', '--python', str(Path(__file__).with_name('avatar_native_parts_blender.py')),
                           '--', str(directory/'input.json')]
                with (directory/'blender.log').open('wb') as log:
                    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                        env={**os.environ, 'ASSET_STORAGE_WORKER_LOCAL': '1'},
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    _write_json(directory/'runner.json', {'process': identity(process.pid)})
                    publish_checkpoint(directory/'runner.json')
                    try:
                        code = process.wait(timeout=1800)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        process.wait(timeout=10)
                        raise
                if code:
                    raise ValueError('Blender fitting failed')
                seal = read_json(directory/'complete.json')
                if seal.get('input_sha256') != digest(directory/'input.json'):
                    raise ValueError('Unsealed output')
                payload = read_json(directory/'input.json')
                required = {'model.glb', 'master.blend', 'front.png', 'side.png', 'back.png', 'motion.png',
                            'body.glb', *(f'{p["slot"]}.glb' for p in payload['parts'])}
                production = payload.get('production_spec')
                if production:
                    required.add('opposite.png')
                if not required <= seal.get('files', {}).keys():
                    raise ValueError('Incomplete parts')
                for name, expected in seal['files'].items():
                    if Path(name).name != name or digest(directory/name) != expected:
                        raise ValueError('Output changed')
                record.update(status='review_required', files=seal['files'], result=seal['result'], error=None)
            except Exception as exc:
                record.update(status='failed', error='파츠 조립 중단', error_type=type(exc).__name__,
                    files={name: digest(directory/name) for name in ('front.png', 'side.png', 'back.png', 'opposite.png') if (directory/name).is_file()},
                    result={})
            _write_json(directory/'record.json', record)

    def artifact(self, owner, job, version, name):
        root = self.root(owner, job)
        if not re.fullmatch('[a-f0-9]{24}', version) or Path(name).name != name:
            raise PipelineError('not_found', '산출물을 찾을 수 없습니다.', 404)
        record = read_json(root/version/'record.json')
        expected = record.get('files', {}).get(name)
        path = root/version/name
        if not expected or not path.is_file() or digest(path) != expected:
            raise PipelineError('artifact_changed', '검증된 산출물을 찾을 수 없습니다.', 404)
        return path
