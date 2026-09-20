"""Public Meshy failures derived from saved receipts, without provider requests."""
from src.services.character_pipeline import read_json

BLOCKED = ('submission_uncertain', 'submission_rejected', 'FAILED', 'CANCELED')


def task_problem(task, stage):
    status = task.get('status')
    if status not in BLOCKED:
        return None
    label = {'rigging': '리깅', 'animation': '동작', 'generation': '3D 생성'}.get(stage, '작업')
    code = status
    http_status = task.get('http_status')
    if status == 'submission_rejected':
        suffix = f' (HTTP {http_status})' if http_status else ''
        if http_status == 422 and stage == 'rigging':
            # https://docs.meshy.ai/en/api/rigging: 422 means pose estimation failed.
            code = 'rig_pose_rejected'
            message = 'Meshy가 몸의 자세를 인식하지 못해 리깅을 거절했습니다 (HTTP 422). 몸 모델의 자세·팔다리 형태를 확인해 주세요.'
        elif http_status == 402:
            code = 'insufficient_credits'
            message = f'Meshy 크레딧 부족으로 {label} 요청이 거절됐습니다 (HTTP 402).'
        elif http_status in (401, 403):
            code = 'provider_authentication'
            message = f'Meshy 인증·권한 문제로 {label} 요청이 거절됐습니다{suffix}.'
        elif http_status == 429:
            code = 'provider_rate_limit'
            message = f'Meshy 요청 한도 초과로 {label} 요청이 거절됐습니다 (HTTP 429).'
        else:
            message = f'Meshy가 {label} 요청을 거절했습니다{suffix}. 요청 입력을 확인해 주세요.'
        message += ' 저장된 이미지와 3D 파일은 유지됩니다.'
    elif status == 'submission_uncertain':
        message = f'Meshy {label} 요청의 접수 여부를 확인하지 못했습니다. 기존 요청의 작업 ID를 확인해야 합니다.'
    elif status == 'FAILED':
        message = f'Meshy {label} 작업이 실패했습니다. 저장된 이미지와 3D 파일은 유지됩니다.'
    else:
        message = f'Meshy {label} 작업이 취소됐습니다. 저장된 이미지와 3D 파일은 유지됩니다.'
    return {'code': code, 'stage': stage, 'status': status, 'http_status': http_status,
            'task_id': task.get('task_id'), 'message': message}


def saved_problem(run):
    # Keep the rejected provider receipt intact after an explicit local recovery.
    if read_json(run/'delivery.json').get('origin') == 'transferred_meshy_rig':
        return None
    task = read_json(run/'character.json')
    problem = task_problem(task, task.get('stage', 'rigging'))
    if problem:
        return problem
    for path in sorted((run/'actions').glob('*/motion-pack.json')):
        pack = read_json(path)
        for task in pack.get('tasks', {}).values():
            problem = task_problem(task, 'animation')
            if problem:
                return {**problem, 'action_id': pack.get('action_id')}
    return None
