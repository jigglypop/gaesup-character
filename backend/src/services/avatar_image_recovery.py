"""Explicit per-view replacement attempts; never replay an uncertain POST."""
from copy import deepcopy
import hashlib
import json

from src.services.asset_editor import _write_json
from src.services.character_pipeline import PipelineError, now, read_json
from src.services.process_identity import identity
from src.services.avatar_openai_images import image_error_message, _error_category

RETRYABLE = {'submission_uncertain', 'rejected', 'failed', 'qc_failed'}


def image_failure(image):
    if image.get('failure'):
        return deepcopy(image['failure'])
    if image.get('status') == 'qc_failed':
        # Earlier servers saved QC without a failure ID. Derive a stable retry token.
        evidence = json.dumps({'sha256': image.get('sha256'), 'qc': image.get('qc')}, sort_keys=True)
        return {'id': hashlib.sha256(evidence.encode()).hexdigest()[:12], 'category': 'local_processing',
                'message': '저장 이미지 처리 대기'}
    return None


def receipt_path(directory, slot, view, image):
    return directory/'output'/image.get('receipt', f'{slot}-{view}-provider')


def has_dependents(state, part, view):
    if not part.get('views'):
        return True
    model = part.get('model', {})
    if model.get('task_id') or model.get('status', 'pending') != 'pending':
        return True
    if view == 'front' and part['views'].get('side', {}).get('status', 'pending') != 'pending':
        return True
    # All parts reference the common body. Other parts do not reference each other.
    return part['slot'] == 'body' and any(
        image['status'] != 'pending' for other in state['parts'] if other['slot'] != 'body'
        for image in other.get('views', {}).values())


def decorate_job(directory, public):
    """Expose actionable failures, including receipts written by earlier servers."""
    paused = public['status'] in ('pipeline_paused', 'failed', 'recovery_required')
    state = read_json(directory/'pipeline.json') if paused else {}
    failure_message = None
    failure_count = 0
    for part in public.get('parts', []):
        for view, image in part.get('views', {}).items():
            failure = image_failure(image)
            if not failure or image['status'] not in RETRYABLE:
                continue
            image['failure'] = failure
            if image['status'] == 'qc_failed':
                failure.update(category='local_processing', message='저장 이미지 처리 대기')
            saved = next((p for p in state.get('parts', []) if p['slot'] == part['slot']), {})
            receipt = receipt_path(directory, part['slot'], view, saved.get('views', {}).get(view, {}))
            transport = read_json(receipt.with_suffix('.request.json'))
            if image['status'] == 'rejected':
                rejection = read_json(receipt.with_suffix('.error.json'))
                http_status = rejection.get('http_status') or transport.get('http_status')
                provider_error = rejection.get('provider_error', transport.get('provider_error', {}))
                category = _error_category(http_status, provider_error) if isinstance(http_status, int) else failure.get('category', 'unknown')
                failure.update(category=category, message=image_error_message(category, http_status),
                               http_status=http_status, provider_code=provider_error.get('code'))
            failure.setdefault('elapsed_seconds', transport.get('elapsed_seconds'))
            failure.setdefault('phase', transport.get('phase'))
            if failure.get('type') in ('ReadError', 'ReadTimeout', 'RemoteProtocolError'):
                failure.setdefault('message', '생성 서버 연결 끊김 · 수신된 응답 없음')
            part['image_status'] = image['status']
            part['image_failure'] = deepcopy(failure)
            label = {'body': '몸', 'hair': '머리카락', 'head': '기존 머리 파츠', 'hairBack': '뒷머리', 'hairFront': '앞머리', 'hat': '모자', 'top': '상의', 'bottom': '하의', 'shoes': '신발'}.get(part['slot'], part['slot'])
            if failure.get('message'):
                failure_message = f'{label} {"정면" if view == "front" else "측면"}: {failure["message"]}'
                failure_count += 1
            if paused and failure.get('id') and (image['status'] == 'qc_failed' or not receipt.with_suffix('.response.json').is_file()):
                from src.services.avatar_production_spec import can_reuse_image
                if image['status'] == 'qc_failed' and can_reuse_image(image):
                    continue
                blocked = has_dependents(state, saved, view)
                public['next_actions'].append({'id': 'retry_image', 'enabled': not blocked,
                    'reason': '이 이미지를 사용하는 후속 작업이 있습니다.' if blocked else None,
                    'slot': part['slot'], 'view': view, 'failure_id': failure['id'], 'additional_image_tasks': 1})
    retryable = [{k: action[k] for k in ('slot', 'view', 'failure_id')}
                 for action in public['next_actions'] if action['id'] == 'retry_image' and action['enabled']]
    if len(retryable) > 1:
        public['next_actions'].append({'id': 'retry_images', 'enabled': True,
            'images': retryable, 'additional_image_tasks': len(retryable)})
    if failure_message and paused:
        if failure_count > 1:
            failure_message = f'미완료 이미지 {failure_count}장 · {failure_message}'
        public['error'] = failure_message
        public['progress']['message'] = failure_message
        if public.get('character_flow'):
            public['character_flow']['message'] = failure_message


def retry_view(service, owner, job_id, slot, view, failure_id):
    return retry_views(service, owner, job_id, [{'slot': slot, 'view': view, 'failure_id': failure_id}])


def retry_views(service, owner, job_id, images):
    """Accept an explicit set atomically; a replay never creates more attempts."""
    from src.services.avatar_image_pipeline import _LOCK, _RUN_LOCKS
    service.factory.get(owner, job_id)
    directory = service.factory.directory(owner, job_id)
    with _LOCK:
        job = read_json(directory/'job.json')
        state = read_json(directory/'pipeline.json')
        if not images or len(images) != len({(i['slot'], i['view']) for i in images}):
            raise PipelineError('invalid_views', '중복되지 않은 이미지 요청을 선택하세요.', 422)
        selected = []
        reused = []
        for request in images:
            slot, view, failure_id = (request[k] for k in ('slot', 'view', 'failure_id'))
            part = next((p for p in state.get('parts', []) if p['slot'] == slot), None)
            image = part.get('views', {}).get(view) if part else None
            if not state.get('production_spec') or not image:
                raise PipelineError('view_not_found', '이미지 작업을 찾을 수 없습니다.', 404)
            reused.append(any(a.get('failure', {}).get('id') == failure_id for a in image.get('previous_attempts', [])))
            selected.append((part, view, image, failure_id))
        if all(reused):
            return service.factory.get(owner, job_id), False
        if any(reused):
            raise PipelineError('failure_changed', '이미 접수한 이미지가 포함되어 있습니다.', 409)
        lock = _RUN_LOCKS.get(str(directory))
        if job['status'] not in ('pipeline_paused', 'failed', 'recovery_required') or (lock and lock.locked()):
            raise PipelineError('worker_running', '진행 중인 작업입니다.', 409)
        for part, view, image, failure_id in selected:
            failure = image_failure(image)
            if image['status'] not in RETRYABLE or not failure or failure['id'] != failure_id:
                raise PipelineError('failure_changed', '이미지 상태가 변경되었습니다.', 409)
            if image['status'] != 'qc_failed' and receipt_path(directory, part['slot'], view, image).with_suffix('.response.json').is_file():
                raise PipelineError('response_saved', '저장된 응답에서 재개할 수 있습니다.', 409)
            if has_dependents(state, part, view):
                raise PipelineError('dependent_views_exist', '후속 이미지가 있는 작업은 새 버전이 필요합니다.', 409)
        for part, view, image, failure_id in selected:
            image['failure'] = image_failure(image)
            previous = image.get('previous_attempts', []) + [{k: deepcopy(v) for k, v in image.items() if k != 'previous_attempts'}]
            part['views'][view] = {'status': 'pending', 'receipt': f'{part["slot"]}-{view}-retry-{failure_id}-provider', 'previous_attempts': previous}
            part['image'] = {'status': 'pending'}
        service.publish(owner, job_id, state)
        job = read_json(directory/'job.json')
        job.update(status='pipeline_queued', resume_stage='images', error=None, executor=service.factory.instance, executor_process=identity(), updated_at=now())
        _write_json(directory/'job.json', job)
        _write_json(directory/'output/progress.json', {'stage': 'images', 'message': '이미지 다시 요청 중'})
    return service.factory.get(owner, job_id), True
