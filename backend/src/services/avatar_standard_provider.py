"""Bounded prepared-view Meshy tasks using the existing durable job adapter."""
import hashlib
import json
import os
from threading import Lock
from contextlib import contextmanager, ExitStack

import httpx

from src.services import character_jobs
from src.services.asset_editor import _write_json
from src.services.avatar_standard import LOCK, sha
from src.services.character_pipeline import PipelineError, now, read_json
from src.services.process_identity import lease_guard, state as process_state
from src.services.wardrobe import run_lock as persisted_run_lock

_RUNS = {}


def run_lock(item):
    with LOCK:
        return _RUNS.setdefault(item, Lock())


@contextmanager
def provider_lease(run):
    """Use the same disk lease as CLI; only reclaim a proven exited owner."""
    run = run.resolve(); lock = run.with_name(run.name+'.lock')
    with lease_guard(run):
        if lock.exists():
            value = read_json(lock)
            if (value.get('version') != 1 or not value.get('token') or value.get('directory') != str(run) or
                    process_state(value.get('owner')) != 'exited'):
                raise PipelineError('worker_active', '기존 작업 잠금의 종료를 확인할 수 없습니다.', 409)
            lock.unlink()
    with ExitStack() as stack:
        try:
            stack.enter_context(persisted_run_lock(run, 0, blender=False))
        except ValueError:
            raise PipelineError('worker_active', 'CLI 또는 다른 실행이 같은 작업을 사용 중입니다.', 409) from None
        yield


def create(service, owner, key, payload, *, provider_config=None):
    import re
    if not re.fullmatch('[a-zA-Z0-9_-]{8,100}', key):
        raise PipelineError('invalid_key', '요청 식별자가 필요합니다.', 422)
    item = hashlib.sha256(f'{owner}:shape:{key}'.encode()).hexdigest()[:24]
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    directory = service.directory(owner, item)
    with LOCK:
        if (directory/'record.json').exists():
            if service.raw(owner, item)['fingerprint'] != fingerprint:
                raise PipelineError('idempotency_conflict', '같은 요청의 입력이 변경되었습니다.', 409)
            return service.public(owner, item), False
        service.base(owner, payload['base_id'], payload['base_sha256'])
        if not os.getenv('MESHY_API_KEY'):
            raise PipelineError('provider_not_configured', 'Meshy 키 설정이 필요합니다.', 422)
        views, objects, images = [], set(), []
        for image_id in payload['image_ids']:
            image = service.raw(owner, image_id)
            if (image['kind'] != 'image' or image['contract']['base_id'] != payload['base_id'] or
                    image['contract']['base_sha256'] != payload['base_sha256']):
                raise PipelineError('image_mismatch', '같은 기준 몸의 파츠 시안이 필요합니다.', 422)
            views.append(image['contract']['view']); objects.add(image['contract']['object_key'])
            images.append(service.artifact(owner, image_id, 'provider.png'))
        if not views or views[0] != 'front' or len(views) != len(set(views)) or len(objects) != 1:
            raise PipelineError('image_mismatch', '정면 우선, 동일 물체의 서로 다른 시점만 묶을 수 있습니다.', 422)
        directory.mkdir(parents=True, exist_ok=True)
        for i, path in enumerate(images):
            (directory/f'view-{i}.png').write_bytes(path.read_bytes())
        config = provider_config or {'base_url': os.getenv('MESHY_API_BASE', 'https://api.meshy.ai'), 'model': 'meshy-7'}
        _write_json(directory/'provider.json', {**config,
            'images': [{'file': f'view-{i}.png', 'sha256': sha(path)} for i, path in enumerate(images)]})
        _write_json(directory/'record.json', {'id': item, 'kind': 'shape', 'name': payload['name'], 'status': 'accepted',
            'fingerprint': fingerprint, 'contract': payload, 'created_at': now(), 'files': {},
            'provider': {'model': 'meshy-7', 'max_new_tasks': 1, 'status': 'not_submitted'}, 'error': None})
        return service.public(owner, item), True


def execute(service, owner, item, *, poll=False, task_id=None):
    directory = service.directory(owner, item); lock = run_lock((owner, item))
    if not lock.acquire(blocking=False):
        raise PipelineError('worker_active', '이 작업의 제출·조회가 진행 중입니다.', 409)
    stack = ExitStack()
    try:
        record = service.raw(owner, item)
        if record['kind'] != 'shape':
            raise PipelineError('invalid_kind', 'Meshy 파츠 작업이 아닙니다.', 422)
        if record['status'] == 'model_ready':
            return service.public(owner, item)
        stack.enter_context(provider_lease(directory/'meshy'))
        settings = read_json(directory/'provider.json'); run = directory/'meshy'
        task = read_json(run/'character.json')
        try:
            with httpx.Client(base_url=settings['base_url'], headers={'Authorization': 'Bearer '+os.environ['MESHY_API_KEY']}, timeout=120) as client:
                if not poll:
                    if task or record['status'] != 'accepted':
                        return service.public(owner, item)
                    paths = [directory/i['file'] for i in settings['images']]
                    if any(sha(path) != receipt['sha256'] for path, receipt in zip(paths, settings['images'])):
                        raise PipelineError('image_changed', '수락한 시안 파일이 변경되었습니다.', 409)
                    # Submission intent is persisted by the shared adapter before POST.
                    task = character_jobs.generate_multiview_part(run, paths, client)
                else:
                    if not task:
                        raise PipelineError('task_missing', '제출 기록이 없습니다. 새 유료 요청은 보내지 않았습니다.', 409)
                    existing = task.get('task_id')
                    if task_id and existing and task_id != existing:
                        raise PipelineError('task_conflict', '이미 저장된 task ID를 바꿀 수 없습니다.', 409)
                    if not existing and not task_id:
                        raise PipelineError('task_recovery_required', '응답이 유실된 Meshy 작업 ID가 필요합니다.', 409)
                    task = character_jobs.refresh(run, client, task_id)
            record['provider'] = {**record['provider'], **{k: task.get(k) for k in ('task_id', 'status', 'progress')}}
            record['status'] = 'provider_running'
            if task['status'] == 'SUCCEEDED':
                receipt = read_json(run/'generation-artifacts.json')
                if not receipt:
                    receipt = character_jobs.download(run, 'generation')
                path = run/'generated.glb'
                if sha(path) != receipt['generated']['sha256']:
                    raise PipelineError('model_changed', '생성된 GLB의 해시가 변경되었습니다.', 409)
                asset = service.upload(owner, path.read_bytes(), 'glb')
                (directory/'generated.glb').write_bytes(path.read_bytes())
                record.update(status='model_ready', result={'model_asset': asset['id']}, files={'generated.glb': asset['id']})
            elif task['status'] in ('FAILED', 'CANCELED'):
                record.update(status='failed', error='Meshy에서 작업이 종료되었습니다. 자동 재제출하지 않았습니다.')
            record['error'] = None if record['status'] != 'failed' else record['error']
        except PipelineError:
            raise
        except Exception:
            task = read_json(run/'character.json')
            record['provider'] = {**record['provider'], **{k: task.get(k) for k in ('task_id', 'status', 'progress')}}
            record.update(status='provider_paused', error='Meshy 연결 또는 결과 처리 중 중단되었습니다. 기존 작업 조회·ID 복구만 가능하며 자동 재제출하지 않습니다.')
        _write_json(directory/'record.json', record)
        return service.public(owner, item)
    finally:
        try:
            stack.close()
        finally:
            lock.release()
