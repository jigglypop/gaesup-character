"""New part versions on an immutable, already assembled body. No paid body/rig job."""
from copy import deepcopy
import hashlib
import json
import os
import re
import subprocess

from src.services.asset_editor import _write_json
from src.services.avatar_factory import _LOCK, digest
from src.services.avatar_image_pipeline import AvatarImagePipeline, capabilities
from src.services.avatar_native_parts import AvatarNativeParts
from src.services.avatar_production_spec import production_spec
from src.services.avatar_equipment import NATIVE_EQUIPMENT as EQUIPMENT, equipment_spec
from src.services.glb import parse_glb
from src.services.character_parts import blender_executable
from src.services.character_pipeline import PipelineError, now, read_json
from src.services.object_storage import StoredPath as Path, copy_file, copy_tree, local_workspace, publish_checkpoint
from src.services.process_identity import identity, state as process_state

VARIANT_SLOTS = ('hair', 'hat', 'top', 'bottom', 'shoes', *EQUIPMENT)


class AvatarVariants:
    def __init__(self, factory):
        self.factory = factory

    def create(self, owner, key, payload):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}', key):
            raise PipelineError('invalid_key', '요청 식별자가 필요합니다.', 422)
        if not os.getenv('ASSET_S3_BUCKET'):
            raise PipelineError('storage_required', 'S3 저장소 설정이 필요합니다.', 503)
        slots = payload['slots']
        if not slots or len(set(slots)) != len(slots) or not set(slots) <= set(VARIANT_SLOTS):
            raise PipelineError('invalid_slots', '생성할 파츠를 선택하세요.', 422)
        if payload['hair_length'] not in ('source', 'short', 'long'):
            raise PipelineError('invalid_hair_length', '머리 길이를 선택하세요.', 422)
        if not set(payload.get('descriptions', {})) <= set(slots):
            raise PipelineError('invalid_description', '선택한 파츠의 설명만 입력하세요.', 422)
        if any(not payload.get('descriptions', {}).get(slot, '').strip() for slot in slots if slot in EQUIPMENT):
            raise PipelineError('equipment_description_required', '무기·도구·안경의 디자인을 입력하세요.', 422)
        job_id = hashlib.sha256(f'{owner}:variant:{key}'.encode()).hexdigest()[:24]
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        target = self.factory.directory(owner, job_id)
        with _LOCK:
            prior = read_json(target/'job.json')
            if prior:
                if prior['fingerprint'] != fingerprint:
                    raise PipelineError('idempotency_conflict', '같은 요청의 입력이 변경되었습니다.', 409)
                return self.factory.get(owner, job_id), False
            if not capabilities()['ready']:
                raise PipelineError('provider_unavailable', '생성 서비스 연결을 확인하세요.', 503)
            base_id = payload['base_job_id']
            base = self.factory.get(owner, base_id)
            native = AvatarNativeParts(self.factory).get(owner, base_id)
            if native.get('status') != 'review_required' or native.get('version') != payload['base_version']:
                raise PipelineError('base_changed', '저장된 기본 몸 버전을 다시 선택하세요.', 409)
            source = self.factory.directory(owner, base_id)
            body_file = source/'native-parts'/native['version']/'body.glb'
            body_hash = next((a['sha256'] for a in native['artifacts'] if a['name'] == 'body.glb'), None)
            if not body_hash or digest(body_file) != body_hash:
                raise PipelineError('body_changed', '기본 몸 파일을 확인할 수 없습니다.', 409)
            original = read_json(source/'pipeline.json')
            if not original.get('production_spec') or any(p['model']['status'] != 'ready' for p in original['parts']):
                raise PipelineError('base_incomplete', '정면·측면과 파츠가 저장된 기본 몸을 선택하세요.', 422)
            # Acceptance is the final write. Interrupted staging can be repeated using
            # the same key; no provider call occurs until a complete job is accepted.
            (target/'output').mkdir(parents=True, exist_ok=True)
            copy_file(source/'source.png', target/'source.png')
            state = deepcopy(original)
            state.update(base_body={'job_id': base_id, 'version': native['version'], 'sha256': body_hash},
                         hair_length=payload['hair_length'], production_spec=production_spec(payload['hair_length']),
                         motion_actions={}, rig_with_meshy=True)
            state['production_spec']['frozen_body'] = True
            state['production_spec']['fitting']['bounds'].update(deepcopy(native['fitting_targets']))
            equipment_spec(state['production_spec'])
            state['parts'] = [p for p in state['parts'] if p['slot'] in ('body', *VARIANT_SLOTS)]
            for slot in slots:
                if not any(p['slot'] == slot for p in state['parts']):
                    state['parts'].append({'slot': slot})
            reused = []
            for part in state['parts']:
                slot = part['slot']
                if slot in slots:
                    part.update(description=payload.get('descriptions', {}).get(slot) or part.get('description', ''),
                                views={v: {'status': 'pending'} for v in ('front', 'side')},
                                image={'status': 'pending'}, model={'status': 'pending'},
                                provenance={'origin': 'generated_for_frozen_body', 'source_job_id': base_id})
                    part.pop('target_bounds_m', None)
                    continue
                reused.append(slot)
                part['provenance'] = {'origin': 'reused', 'source_job_id': base_id}
                for view in part['views'].values():
                    name = view['file']
                    if Path(name).name != name or digest(source/'output'/name) != view['sha256']:
                        raise PipelineError('image_changed', '기본 파츠 이미지가 변경되었습니다.', 409)
                    copy_file(source/'output'/name, target/'output'/name)
                    # Reused views are not charged against this request's limit.
                    for field in ('attempted_at', 'previous_attempts'):
                        view.pop(field, None)
                copy_tree(source/'parts'/slot, target/'parts'/slot)
                part['image'] = deepcopy(part['views']['front'])
                receipt = read_json(target/'parts'/slot/'generation-artifacts.json')['generated']
                if digest(target/'parts'/slot/'generated.glb') != receipt['sha256']:
                    raise PipelineError('model_changed', '저장된 파츠 모델이 변경되었습니다.', 409)
            state['reuse'] = {'source_job_id': base_id, 'slots': reused}
            # A minimal sealed rig delivery contains the actual chosen body and its
            # clips. It never copies another job's active provider worker or intent.
            version = body_hash[:24]
            rigdir = target/'meshy/versions'/version
            rigdir.mkdir(parents=True, exist_ok=True)
            copy_file(body_file, rigdir/'model.glb')
            doc, _ = parse_glb(body_file.read_bytes(), strict=True)
            receipt = {'version': version, 'files': {'model.glb': body_hash},
                       'bone_count': native['bone_count'],
                       'clips': [{'slot': a.get('name', f'clip_{i}'), 'source': 'frozen_body', 'action_id': None}
                                 for i, a in enumerate(doc.get('animations', []))],
                       'origin': 'frozen_body'}
            _write_json(rigdir/'receipt.json', receipt)
            _write_json(target/'meshy/delivery.json', receipt)
            _write_json(target/'meshy/worker.json', {'status': 'complete', 'origin': 'frozen_body'})
            _write_json(target/'pipeline.json', state)
            _write_json(target/'job.json', {'id': job_id, 'fingerprint': fingerprint,
                'executor': self.factory.instance, 'executor_process': identity(),
                'character_id': base['character_id'], 'character_name': base['character_name'],
                'source_sha256': base['source_sha256'], 'input_kind': 'image',
                'production_mode': 'character_parts', 'auto_assemble': True, 'profile': base['profile'],
                'status': 'pipeline_queued', 'created_at': now(), 'updated_at': now(), 'error': None,
                'base_job_id': base_id, 'base_version': native['version'], 'requested_slots': slots,
                'limits': {'image_tasks': 2*len(slots), 'meshy_tasks': len(slots),
                           'meshy_rig_tasks': 0, 'meshy_animation_tasks': 0},
                'review': {'decision': 'pending'}, 'files': {}})
            AvatarImagePipeline(self.factory).publish(owner, job_id, state)
            return self.factory.get(owner, job_id), True


def prepare_body(service, owner, job_id, state):
    """Render exact frozen-body references before any new image request."""
    if not state.get('base_body') or state['base_body'].get('prepared'):
        return
    directory = service.factory.directory(owner, job_id)
    body_hash = state['base_body']['sha256']
    body = directory/'meshy/versions'/body_hash[:24]/'model.glb'
    output = directory/'body-reference'
    output.mkdir(exist_ok=True)
    runner = read_json(output/'runner.json')
    if runner and process_state(runner.get('process')) != 'exited':
        raise PipelineError('body_render_running', '기존 기본 몸 렌더가 실행 중입니다.', 409)
    _write_json(output/'input.json', {'source': str(body), 'sha256': body_hash,
                                     'output': str(output), 'spec': state['production_spec']})
    with local_workspace(output, inputs=[body]):
        with (output/'blender.log').open('wb') as log:
            process = subprocess.Popen([blender_executable(), '--background', '--disable-autoexec', '--python-exit-code', '1', '--threads', '2', '--python',
                str(Path(__file__).with_name('avatar_body_reference_blender.py')), '--', str(output/'input.json')],
                stdout=log, stderr=subprocess.STDOUT, env={**os.environ, 'ASSET_STORAGE_WORKER_LOCAL': '1'},
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            _write_json(output/'runner.json', {'process': identity(process.pid)})
            publish_checkpoint(output/'runner.json')
            try:
                code = process.wait(timeout=240)
            except subprocess.TimeoutExpired:
                process.terminate(); process.wait(timeout=10)
                raise PipelineError('body_render_timeout', '기본 몸 참조 렌더 시간 초과', 409) from None
            if code:
                raise PipelineError('body_render_failed', '기본 몸 참조 렌더 실패', 409)
    state['production_spec'] = read_json(output/'spec.json')
    part = next(p for p in state['parts'] if p['slot'] == 'body')
    for view in ('front', 'side'):
        name = f'body-{view}.png'
        copy_file(output/name, directory/'output'/name)
        part['views'][view] = {'status': 'succeeded', 'file': name,
                              'sha256': digest(directory/'output'/name), 'origin': 'frozen_body_render'}
    part['image'] = deepcopy(part['views']['front'])
    state['base_body']['prepared'] = True
    service.publish(owner, job_id, state)
