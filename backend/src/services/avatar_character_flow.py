"""Continue one photo-to-character job through its final local assembly."""
from src.services.asset_editor import _write_json
from src.services.character_pipeline import read_json
from src.services.process_identity import state as process_state


def character_flow(directory, job):
    """Summarize saved receipts only; GET must never poll a paid provider."""
    progress = job['progress']
    busy = job['status'] in ('pipeline_queued', 'pipeline_running', 'accepted', 'running')
    status = 'running' if busy else 'paused'
    stage, message = progress['stage'], job.get('error') or progress['message']
    if job['status'] == 'review_required':
        pointer = read_json(directory/'native-parts/current.json')
        native = read_json(directory/'native-parts'/pointer['version']/'record.json') if pointer else {}
        worker = read_json(directory/'meshy/worker.json')
        task = read_json(directory/'meshy/character.json')
        working = lambda record: record.get('status') in ('running', 'accepted') and process_state(record.get('process')) != 'exited'
        busy = working(native) or working(worker)
        blocked = task.get('status') in ('submission_uncertain', 'submission_rejected', 'FAILED', 'CANCELED')
        for path in (directory/'meshy/actions').glob('*/motion-pack.json'):
            blocked |= any(t.get('status') in ('submission_uncertain', 'submission_rejected', 'FAILED', 'CANCELED')
                           for t in read_json(path).get('tasks', {}).values())
        if native.get('status') == 'review_required' and not busy:
            status, stage, message = 'review_required', 'complete', '조립 완료'
            job['next_actions'] = []
            job['error'] = None
        else:
            stage = 'assemble' if working(native) or worker.get('status') == 'complete' else 'rig'
            status = 'running' if busy else 'blocked' if blocked or native.get('status') in ('failed', 'qc_failed') else 'paused'
            message = ('파츠 조립 중' if stage == 'assemble' else '몸 리깅·동작 수신 중') if busy else (
                ('조립 재개 필요' if native.get('status') == 'qc_failed' else native.get('error')) or worker.get('error') or job.get('error') or
                ('기존 제공자 응답 확인 필요' if blocked else '저장된 작업에서 이어가기 대기'))
            job['next_actions'] = [{'id': 'resume', 'enabled': not busy and not blocked,
                'reason': message if busy or blocked else None}]
            if native.get('status') == 'qc_failed':
                job['error'] = message
    elif not busy:
        status = 'paused' if any(a['id'] == 'resume' and a['enabled'] for a in job['next_actions']) else 'blocked'
    from src.services.avatar_stage_resume import active_run, current_run
    operation = current_run(directory)
    if active_run(operation):
        busy, status = True, 'running'
        if operation['status'] == 'accepted' or stage in ('complete', 'queued'):
            stage = operation['stage']
            message = {'images': '이미지부터 이어서 실행', 'models': '3D 파츠부터 이어서 실행',
                       'rig': '리깅·동작부터 이어서 실행', 'assemble': '피팅·조립부터 실행'}[stage]
        job['next_actions'] = []
    elif operation.get('status') == 'paused' and operation.get('error') and not busy:
        status, stage, message = 'paused', operation['stage'], operation['error']
    return {'status': status, 'stage': stage, 'message': message, 'busy': busy}


def assemble_character(factory, owner, job_id):
    from src.services.avatar_native_parts import AvatarNativeParts
    directory = factory.directory(owner, job_id)
    _write_json(directory / 'output/progress.json', {'stage': 'assemble', 'message': '파츠 조립 중'})
    service = AvatarNativeParts(factory)
    try:
        _, created = service.start(owner, job_id)
        if created:
            service.execute(owner, job_id)
        state = service.get(owner, job_id)
        if state['status'] == 'review_required':
            _write_json(directory / 'output/progress.json', {'stage': 'complete', 'message': '조립 완료'})
            error = None
        else:
            error = state.get('error') or '조립 작업을 이어서 확인해야 합니다.'
    except Exception:
        error = '파츠 조립이 중단되었습니다. 생성된 파츠와 몸·동작은 보존했으며 계속 만들기로 이어갈 수 있습니다.'
    record = read_json(directory / 'job.json')
    record['error'] = error
    _write_json(directory / 'job.json', record)


def continue_character(factory, owner, job_id):
    from src.services.avatar_meshy import AvatarMeshy
    job = factory.get(owner, job_id)
    if job.get('production_mode') != 'character_parts' or job['status'] != 'review_required':
        return
    directory = factory.directory(owner, job_id)
    record = read_json(directory / 'job.json')
    record['auto_assemble'] = True
    _write_json(directory / 'job.json', record)
    if read_json(directory / 'meshy/worker.json').get('status') == 'complete':
        assemble_character(factory, owner, job_id)
    else:
        provider = AvatarMeshy(factory)
        provider.start(owner, job_id)
        provider.execute(owner, job_id)
