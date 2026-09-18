"""Bounded per-view generation with durable images and shared placement."""
import hashlib
import uuid
import httpx
import time
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from src.services.asset_editor import _write_json
from src.services.avatar_openai_images import generate_standard_part_image, OpenAIImageHTTPError, image_error_message
from src.services.avatar_production_spec import guide, prepare_image, paired_bounds, can_reuse_image
from src.services.avatar_image_recovery import receipt_path
from src.services.avatar_image_prompts import PROMPT_REVISION, build_prompt, layout_contract, reference_roles
from src.services.character_pipeline import PipelineError, now, read_json


def can_resume(directory, state):
    def next_view(part):
        for view in state['production_spec']['generated_views']:
            image = part['views'][view]
            status = image['status']
            if status == 'succeeded':
                continue
            if status in ('pending', 'not_sent', 'received'):
                return True
            if status == 'qc_failed' and can_reuse_image(image):
                return True
            if status in ('submitting', 'submission_uncertain', 'failed') and receipt_path(directory, part['slot'], view, image).with_suffix('.response.json').is_file():
                return True
            return False
        return None
    body = next(p for p in state['parts'] if p['slot'] == 'body')
    body_next = next_view(body)
    if body_next is not None:
        return body_next
    remaining = [next_view(p) for p in state['parts'] if p['slot'] != 'body']
    return any(item is True for item in remaining) or all(item is None for item in remaining)


def execute(service, owner, job_id, state):
    directory = service.factory.directory(owner, job_id); output = directory/'output'
    spec = state['production_spec']; views = spec['generated_views']
    for view in views:
        path = output/f'guide-{view}.png'
        expected = guide(view, spec)
        if path.is_file() and path.read_bytes() != expected:
            raise PipelineError('guide_changed', '생산 기준 이미지가 변경되었습니다.', 409)
        path.write_bytes(expected)
    body = next(p for p in state['parts'] if p['slot'] == 'body')
    # Workers own their mutable part; publish only full snapshots under this lock.
    publish_lock = Lock()

    def persist(part):
        index = next(n for n, p in enumerate(state['parts']) if p['slot'] == part['slot'])
        state['parts'][index] = deepcopy(part)
        service.publish(owner, job_id, state)
        images = [i for p in state['parts'] for i in p['views'].values()]
        received = sum(i['status'] in ('received', 'succeeded', 'qc_failed') for i in images)
        active = sum(i['status'] == 'submitting' and not i.get('failure') for i in images)
        _write_json(output/'progress.json', {'stage': 'images',
            'message': f'이미지 수신 {received}/{len(images)} · 동시 생성 {active}',
            'images_received': received, 'images_total': len(images), 'active_images': active})

    def publish(part):
        with publish_lock:
            persist(part)

    def reserve(part, view):
        with publish_lock:
            image = part['views'][view]
            attempts = sum(int('attempted_at' in i) + len(i.get('previous_attempts', []))
                           for p in state['parts'] for i in p['views'].values())
            if image['status'] == 'pending' and attempts >= read_json(directory/'job.json')['limits']['image_tasks']:
                raise PipelineError('image_budget_exhausted', '수락한 이미지 생성 한도 도달', 409)
            image.pop('failure', None)
            image.update(status='submitting', attempted_at=image.get('attempted_at', now()))
            persist(part)

    body = deepcopy(body)
    _generate_part(service, owner, job_id, state, body, body, publish, reserve)
    parts = [deepcopy(p) for p in state['parts'] if p['slot'] != 'body']
    errors = []
    if parts:
        # The hat fits the saved complete hairstyle. Garments remain parallel;
        # a failed hair request must not send a hat request against a bare head.
        with ThreadPoolExecutor(max_workers=min(6, len(parts)), thread_name_prefix='avatar-image') as pool:
            hair = next((part for part in parts if part['slot'] == 'hair'), None)
            hair_future = pool.submit(_generate_part, service, owner, job_id, state, hair, body, publish, reserve) if hair else None
            def generate(part):
                underlying = None
                if part['slot'] == 'hat' and hair_future is not None:
                    hair_future.result()
                    underlying = hair
                _generate_part(service, owner, job_id, state, part, body, publish, reserve, hair=underlying)
            futures = ([hair_future] if hair_future else []) + [pool.submit(generate, part) for part in parts if part is not hair]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    errors.append(exc)
    if errors:
        first = errors[0]
        message = first.message if isinstance(first, PipelineError) else '이미지 처리 실패'
        if len(errors) > 1:
            message += f' · 중단된 파츠 {len(errors)}개'
        raise PipelineError('image_parts_incomplete', message, 409) from None


def _generate_part(service, owner, job_id, state, part, body, publish, reserve, *, hair=None):
    directory = service.factory.directory(owner, job_id); output = directory/'output'
    spec = state['production_spec']; views = spec['generated_views']
    slot = part['slot']
    for view in views:
        image = part['views'][view]; name = f'{slot}-{view}.png'; path = output/name
        receipt = receipt_path(directory, slot, view, image)
        if image['status'] == 'succeeded':
            if hashlib.sha256(path.read_bytes()).hexdigest() != image['sha256']:
                raise PipelineError('image_changed', '저장된 파츠 이미지가 변경되었습니다.', 409)
            continue
        cached = receipt.with_suffix('.response.json').is_file()
        if image['status'] == 'qc_failed' and can_reuse_image(image):
            image['status'] = 'received'
        if image['status'] not in ('pending', 'not_sent', 'received') and not (image['status'] in ('submitting', 'submission_uncertain', 'failed') and cached):
            raise PipelineError('view_recovery_required', f'{slot} {view}: 기존 응답 확인 필요', 409)
        if image['status'] != 'received':
            prompt_receipt = receipt.with_suffix('.prompt.json')
            recorded = read_json(prompt_receipt)
            # A previously submitted attempt keeps its exact prompt and inputs.
            revision = recorded.get('revision', PROMPT_REVISION)
            template = output/f'guide-{slot}-{view}-{revision}.png'
            template_bytes = guide(view, spec, slot)
            if template.is_file() and template.read_bytes() != template_bytes:
                raise PipelineError('guide_changed', '생산 기준 이미지가 변경되었습니다.', 409)
            template.write_bytes(template_bytes)
            refs = [template, directory/'source.png']
            if slot != 'body':
                refs.insert(1, output/body['views'][view]['file'])
            hair_reference = slot == 'hat' and hair is not None
            if hair_reference and recorded:
                # Response recovery preserves the exact inputs already sent.
                hair_reference = any(ref['name'] == hair['views'][view]['file'] for ref in recorded.get('references', []))
            if hair_reference:
                refs.insert(2, output/hair['views'][view]['file'])
            if view != 'front':
                refs.append(output/part['views']['front']['file'])
            previous = image.get('previous_attempts', [])
            prompt = build_prompt(spec, slot, view,
                previous_qc=previous[-1].get('qc') if previous else None,
                accepted_front_qc=(part['views']['front'].get('measurement') or part['views']['front'].get('qc')) if view == 'side' else None,
                notes=part.get('description', ''), hair_reference=hair_reference)
            if not cached:
                # Store the exact text and ordered input identities before the paid POST.
                if prompt_receipt.is_file():
                    identities = [{'name': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in refs]
                    if [{k: item[k] for k in ('name', 'sha256')} for item in recorded['references']] != identities:
                        raise PipelineError('reference_changed', '기록된 참조 이미지가 변경되었습니다.', 409)
                    prompt = recorded['prompt']
                else:
                    _write_json(prompt_receipt, {'revision': PROMPT_REVISION, 'spec_sha256': spec['sha256'],
                        'layout': layout_contract(spec, slot, view), 'prompt': prompt,
                        'references': [{'name': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'role': role}
                            for p, role in zip(refs, reference_roles(slot, view, hair_reference=hair_reference))]})
                image['prompt_revision'] = read_json(prompt_receipt)['revision']
            reserve(part, view)
            try:
                raw = generate_standard_part_image(refs, prompt, state['image_model'], state['image_base'], receipt=receipt,
                    canvas_size=(spec['canvas']['width'], spec['canvas']['height']))
                path.write_bytes(raw)
                image.update(status='received', file=name, sha256=hashlib.sha256(raw).hexdigest())
                publish(part)
            except Exception as exc:
                transport = read_json(receipt.with_suffix('.request.json'))
                saved = receipt.with_suffix('.response.json').is_file()
                if saved:
                    status, category, message = 'submitting', 'local_processing', '수신 이미지 처리 중단'
                elif isinstance(exc, OpenAIImageHTTPError):
                    status, category = 'rejected', exc.category
                    message = image_error_message(category, exc.response.status_code)
                elif transport.get('submission') == 'not_sent':
                    status, category, message = 'not_sent', 'provider_connection', '생성 서버 연결 실패 · 재개 가능'
                elif isinstance(exc, httpx.RequestError):
                    status, category, message = 'submission_uncertain', 'provider_connection', '생성 서버 연결 끊김 · 수신된 응답 없음'
                else:
                    status, category, message = 'failed', 'local_processing', '이미지 처리 실패'
                image.update(status=status, failure={
                    'id': getattr(exc, 'diagnostic_id', uuid.uuid4().hex[:12]), 'type': type(exc).__name__,
                    'category': category, 'message': message, 'phase': transport.get('phase'),
                    'elapsed_seconds': transport.get('elapsed_seconds'), 'at': now()})
                if isinstance(exc, OpenAIImageHTTPError):
                    image['failure'].update(http_status=exc.response.status_code,
                                            provider_code=exc.provider_error.get('code'))
                publish(part)
                label = {'body': '몸', 'hair': '머리카락', 'head': '기존 머리 파츠', 'hairBack': '뒷머리', 'hairFront': '앞머리', 'hat': '모자', 'top': '상의', 'bottom': '하의', 'shoes': '신발'}[slot]
                raise PipelineError('view_response_missing', f'{label} {"정면" if view == "front" else "측면"}: {message}', 409) from None
        image.pop('failure', None)
        saving_started = time.monotonic()
        received = path.read_bytes()
        if hashlib.sha256(received).hexdigest() != image['sha256']:
            raise PipelineError('image_changed', '수신 이미지 해시 불일치', 409)
        normalized, measurement = prepare_image(received, slot, spec)
        if normalized != received:
            path.write_bytes(normalized)
        image.update(measurement=measurement, sha256=hashlib.sha256(normalized).hexdigest())
        asset = service.blueprints.upload(owner, normalized)
        image.update(asset=asset['id'], status='succeeded')
        image['saving_seconds'] = round(time.monotonic()-saving_started, 3)
        publish(part)
    measurements = [part['views'][v].get('measurement') or part['views'][v].get('qc') or {} for v in views]
    part['target_bounds_m'] = paired_bounds(*measurements, spec, slot)
    part['image'] = {**part['views']['front'], 'status': 'succeeded'}
    publish(part)
