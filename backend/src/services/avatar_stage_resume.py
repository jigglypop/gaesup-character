"""Resume a selected factory stage from its saved inputs, with durable admission."""
import hashlib
import re
from threading import Lock

from src.services.asset_editor import _write_json
from src.services.avatar_factory import _LOCK, digest
from src.services.character_pipeline import PipelineError, now, read_json
from src.services.object_storage import copy_file
from src.services.process_identity import identity, state as process_state
from src.services.avatar_equipment import is_native_part_set
from src.services.meshy_status import BLOCKED, saved_problem

STAGES = ('images', 'models', 'rig', 'assemble', 'expressions')
_WORKERS = {}


def current_run(directory):
    pointer = read_json(directory/'stage-runs/current.json')
    return read_json(directory/'stage-runs'/f'{pointer["id"]}.json') if pointer else {}


def active_run(record):
    return record.get('status') in ('accepted', 'running') and process_state(record.get('process')) != 'exited'


def ensure_stage_idle(factory, owner, job_id):
    factory.get(owner, job_id)
    if active_run(current_run(factory.directory(owner, job_id))):
        raise PipelineError('stage_running', '선택한 단계가 실행 중입니다. 저장된 실행 결과를 기다려 주세요.', 409)


def image_inputs(part, pipeline):
    if pipeline.get('uploaded_glb'):
        return []
    if pipeline.get('production_spec'):
        return [part.get('views', {}).get(view, {}) for view in pipeline['production_spec']['generated_views']]
    return [part.get('image', {})]


def saved_image(directory, image):
    name = image.get('file')
    return bool(name and '/' not in name and '\\' not in name and image.get('sha256')
                and (directory/'output'/name).is_file())


def model_problem(directory, part, pipeline, *, verify=False):
    run = directory/'parts'/part['slot']
    generated = read_json(run/'generation-artifacts.json').get('generated')
    if generated:
        if not (run/'generated.glb').is_file():
            return '저장된 3D 파일을 찾을 수 없습니다.'
        if verify and digest(run/'generated.glb') != generated.get('sha256'):
            return '저장된 3D 파일이 변경되었습니다.'
        return None
    task = read_json(run/'character.json')
    if task:
        if not task.get('task_id') or task.get('status') in BLOCKED:
            return '기존 3D 요청의 응답 확인이 필요합니다.'
        return None  # Poll the known task; image generation is not a prerequisite.
    for image in image_inputs(part, pipeline):
        if image.get('status') != 'succeeded' or not saved_image(directory, image):
            return '저장된 파츠 이미지가 필요합니다.'
        if verify and digest(directory/'output'/image['file']) != image['sha256']:
            return '저장된 파츠 이미지가 변경되었습니다.'
    return None


def validate_model_inputs(directory, pipeline):
    for part in pipeline.get('parts', []):
        problem = model_problem(directory, part, pipeline, verify=True)
        if problem:
            raise PipelineError('stage_inputs_missing', f'{part["slot"]}: {problem}', 409)


def publish_saved_models(directory, pipeline):
    """Recover output publication after a download, without any provider call."""
    job = read_json(directory/'job.json')
    for part in pipeline['parts']:
        name = f'generated-{part["slot"]}.glb'
        output = directory/'output'/name
        expected = job.get('files', {}).get(name)
        if expected and output.is_file() and digest(output) == expected:
            continue
        run = directory/'parts'/part['slot']
        receipt = read_json(run/'generation-artifacts.json').get('generated', {})
        if not receipt.get('sha256') or digest(run/'generated.glb') != receipt['sha256']:
            raise PipelineError('model_changed', '저장된 3D 파츠가 없거나 변경되었습니다.', 409)
        copy_file(run/'generated.glb', output)
        job.setdefault('files', {})[name] = receipt['sha256']
    job.update(status='review_required', auto_assemble=True, error=None, updated_at=now())
    _write_json(directory/'job.json', job)


class AvatarStageResume:
    def __init__(self, factory):
        self.factory = factory

    def get(self, owner, job_id):
        job = self.factory.get(owner, job_id)
        if job.get('production_mode') != 'character_parts':
            raise PipelineError('parts_required', '캐릭터 파츠 작업이 필요합니다.', 422)
        directory = self.factory.directory(owner, job_id)
        pipeline = read_json(directory/'pipeline.json')
        parts = pipeline.get('parts', [])
        valid = is_native_part_set(p['slot'] for p in parts)
        operation = current_run(directory)
        busy = active_run(operation) or job.get('character_flow', {}).get('busy', False)
        native_pointer = read_json(directory/'native-parts/current.json')
        native = read_json(directory/'native-parts'/native_pointer['version']/'record.json') if native_pointer else {}
        rig_worker = read_json(directory/'meshy/worker.json')
        busy |= active_run(native) or active_run(rig_worker)
        images = [i for p in parts for i in image_inputs(p, pipeline)]
        image_count = sum(saved_image(directory, i) for i in images)
        models = []
        for part in parts:
            slot = part['slot']; run = directory/'parts'/slot
            stored = read_json(run/'generation-artifacts.json').get('generated')
            exported = job.get('artifacts', [])
            models.append(bool(stored and (run/'generated.glb').is_file()) or
                          (any(a['name'] == f'generated-{slot}.glb' for a in exported)
                           and (directory/'output'/f'generated-{slot}.glb').is_file()))
        models_ready = valid and all(models)
        delivery = read_json(directory/'meshy/delivery.json')
        rig_ready = bool(delivery.get('version') and delivery.get('files', {}).get('model.glb')
                         and (directory/'meshy/versions'/delivery['version']/'model.glb').is_file())
        rig_problem = saved_problem(directory/'meshy')
        expressions = job.get('default_expressions')
        from src.services.avatar_expression_reuse import expression_reuse_state
        reused_expressions = expression_reuse_state(directory)
        if reused_expressions:
            expressions = {**reused_expressions, 'items': []}
        image_resume = False
        if valid and not pipeline.get('uploaded_glb'):
            if pipeline.get('production_spec'):
                from src.services.avatar_multiview_images import can_resume
                image_resume = can_resume(directory, pipeline)
            else:
                image_resume = all(p['image']['status'] in ('pending', 'received', 'succeeded') or
                    (directory/'output'/f'{p["slot"]}-provider.response.json').is_file() for p in parts)
        model_error = next((problem for p in parts if (problem := model_problem(directory, p, pipeline))), None)
        reasons = {
            'images': None if image_resume else '기존 이미지 응답 확인 또는 실패 이미지 재요청이 필요합니다.',
            'models': model_error,
            'rig': '저장된 3D 파츠가 필요합니다.' if not models_ready else
                   rig_problem['message'] if rig_problem else None,
            'assemble': '저장된 3D 파츠가 필요합니다.' if not models_ready else
                        '저장된 리깅 결과가 필요합니다.' if not rig_ready else None,
            'expressions': '이 작업에는 기본 표정 생성이 접수되지 않았습니다.' if not expressions else
                           '저장된 조립 몸이 필요합니다.' if native.get('status') != 'review_required' else
                           '기본 표정이 모두 저장됐습니다.' if expressions['status'] == 'complete' else None,
        }
        if pipeline.get('uploaded_glb'):
            reasons['images'] = reasons['models'] = '등록한 GLB를 사용합니다.'
            if (pipeline.get('base_body_setup') or {}).get('import_mode') == 'register':
                reasons['rig'] = '바로 등록한 원본입니다. 새 리깅은 GLB 등록에서 선택하세요.'
                if not pipeline['uploaded_glb'].get('rigged'):
                    reasons['assemble'] = '리깅 없는 원본이 등록됐습니다. 파츠 조립에는 리깅이 필요합니다.'
        # Earlier stages already have their files; replaying them only hits the same rejected rig.
        if models_ready and rig_problem:
            reasons['models'] = '3D 파츠가 모두 저장됐습니다. 리깅 오류를 확인해 주세요.'
            if image_count == len(images):
                reasons['images'] = '이미지가 모두 저장됐습니다. 리깅 오류를 확인해 주세요.'
        stages_paid = {
            'assemble': bool(not reused_expressions and expressions and expressions['status'] != 'complete'),
            'expressions': bool(expressions and any(item['status'] != 'complete' for item in expressions['items'])),
            'rig': not (rig_ready and rig_worker.get('status') == 'complete') and not bool((pipeline.get('base_body_setup') or {}).get('rig_source')),
            'models': not models_ready or not (rig_ready and rig_worker.get('status') == 'complete'),
            'images': any(i.get('status') != 'succeeded' for i in images) or not models_ready
                      or not (rig_ready and rig_worker.get('status') == 'complete'),
        }
        actions = [{'stage': stage, 'enabled': valid and not busy and not reasons[stage],
                    'reason': '진행 중인 작업이 있습니다.' if busy else reasons[stage] if valid else '저장된 파츠 작업이 필요합니다.',
                    'paid': stages_paid[stage]}
                   for stage in STAGES if stage != 'expressions' or expressions]
        recommended = next((a['stage'] for a in reversed(actions) if a['enabled']), None)
        public_operation = {k: operation.get(k) for k in ('id', 'stage', 'status', 'error', 'created_at', 'updated_at')} if operation else None
        if public_operation and operation['status'] in ('accepted', 'running') and not active_run(operation):
            public_operation.update(status='paused', error='서버가 중단되었습니다. 저장된 단계에서 다시 실행할 수 있습니다.')
        elif public_operation and operation['status'] == 'paused' and rig_problem and models_ready:
            public_operation['error'] = rig_problem['message']
        elif public_operation and operation['status'] == 'paused' and rig_ready and rig_worker.get('origin') == 'rig_transfer':
            public_operation = None  # The preserved old rejection is superseded by a local recovery.
        return {'actions': actions, 'busy': bool(busy), 'recommended_stage': recommended,
                'saved': {'images': image_count, 'images_total': len(images), 'models': sum(models),
                          'models_total': len(parts), 'rig': rig_ready}, 'operation': public_operation}

    def start(self, owner, job_id, stage, key):
        if stage not in STAGES or not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}', key):
            raise PipelineError('invalid_request', '시작 단계와 요청 식별자가 필요합니다.', 422)
        directory = self.factory.directory(owner, job_id)
        request_id = hashlib.sha256(key.encode()).hexdigest()
        path = directory/'stage-runs'/f'{request_id}.json'
        with _LOCK:
            state = self.get(owner, job_id)  # Also enforces ownership.
            previous = read_json(path)
            if previous:
                if previous['stage'] != stage:
                    raise PipelineError('idempotency_conflict', '같은 요청의 시작 단계가 다릅니다.', 409)
                # Replays recover the receipt, never restart a paid stage.
                return state, None
            action = next(a for a in state['actions'] if a['stage'] == stage)
            if not action['enabled']:
                raise PipelineError('stage_unavailable', action['reason'] or '현재 실행할 수 없는 단계입니다.', 409)
            record = {'id': request_id, 'stage': stage, 'status': 'accepted', 'process': identity(),
                      'created_at': now(), 'updated_at': now(), 'error': None}
            _write_json(path, record)
            _write_json(directory/'stage-runs/current.json', {'id': request_id})
        return self.get(owner, job_id), request_id

    def execute(self, owner, job_id, request_id):
        directory = self.factory.directory(owner, job_id)
        path = directory/'stage-runs'/f'{request_id}.json'
        with _LOCK:
            lock = _WORKERS.setdefault(str(directory), Lock())
        if not lock.acquire(blocking=False):
            return
        try:
            record = read_json(path)
            if record.get('status') != 'accepted':
                return
            record.update(status='running', process=identity(), updated_at=now())
            _write_json(path, record)
            try:
                stage = record['stage']
                pipeline = read_json(directory/'pipeline.json')
                if stage in ('images', 'models'):
                    from src.services.avatar_image_pipeline import AvatarImagePipeline
                    service = AvatarImagePipeline(self.factory)
                    service.resume(owner, job_id, stage=stage)
                    service.execute(owner, job_id)
                elif stage == 'expressions':
                    from src.services.avatar_expression_pipeline import execute as expressions_execute, summary
                    pointer = read_json(directory/'native-parts/current.json')
                    if pipeline.get('expression_reuse'):
                        from src.services.avatar_expression_reuse import reuse_saved_expressions
                        result = reuse_saved_expressions(self.factory, owner, job_id, pointer['version'])
                    else:
                        expressions_execute(self.factory, owner, job_id, pointer['version'])
                        result = summary(directory, pointer['version'])
                    job_record = read_json(directory/'job.json')
                    job_record['error'] = (result.get('error') or '기본 표정 텍스처 처리 대기') if result and result['status'] != 'complete' else None
                    _write_json(directory/'job.json', job_record)
                else:
                    publish_saved_models(directory, pipeline)
                    if stage == 'rig':
                        from src.services.avatar_character_flow import continue_character
                        continue_character(self.factory, owner, job_id)
                    else:
                        from src.services.avatar_character_flow import assemble_character
                        assemble_character(self.factory, owner, job_id)
                pointer = read_json(directory/'native-parts/current.json')
                native = read_json(directory/'native-parts'/pointer['version']/'record.json') if pointer else {}
                job = read_json(directory/'job.json')
                rig_worker = read_json(directory/'meshy/worker.json')
                problem = saved_problem(directory/'meshy') if stage != 'assemble' else None
                error = job.get('error') or native.get('error') or (problem['message'] if problem else
                        rig_worker.get('error') if stage != 'assemble' else None)
                complete = native.get('status') == 'review_required' and not error
                record.update(status='complete' if complete else 'paused',
                              error=None if complete else error or '저장된 작업 상태를 확인해 이어서 실행해 주세요.')
            except Exception as exc:
                record.update(status='paused', error=exc.message if isinstance(exc, PipelineError)
                              else '단계 실행이 중단되었습니다. 저장된 결과는 보존했습니다.')
            record['updated_at'] = now()
            _write_json(path, record)
        finally:
            lock.release()
