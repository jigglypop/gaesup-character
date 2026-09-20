"""A bounded body-referenced image edit followed by measured canvas alignment."""
import hashlib
import json
import math
import os
import re

import httpx
from PIL import Image, ImageOps
import io

from src.services.asset_editor import _write_json
from src.services.avatar_openai_images import DEFAULT_MODEL, DEFAULT_BASE, generate_standard_part_image
from src.services.avatar_standard import LOCK, sha
from src.services.avatar_standard_provider import run_lock, provider_lease
from contextlib import ExitStack
from src.services.character_pipeline import PipelineError, now, read_json
from src.services.process_identity import identity


def create(service, owner, key, payload, *, provider_config=None):
    if not re.fullmatch('[a-zA-Z0-9_-]{8,100}', key):
        raise PipelineError('invalid_key', '요청 식별자가 필요합니다.', 422)
    item = hashlib.sha256(f'{owner}:design:{key}'.encode()).hexdigest()[:24]
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    directory = service.directory(owner, item)
    with LOCK:
        if (directory/'record.json').exists():
            if service.raw(owner, item)['fingerprint'] != fingerprint:
                raise PipelineError('idempotency_conflict', '같은 요청의 시안 입력이 변경되었습니다.', 409)
            return service.public(owner, item), False
        base = service.base(owner, payload['base_id'], payload['base_sha256'])
        if not os.getenv('OPENAI_API_KEY'):
            raise PipelineError('image_provider_unavailable', 'OpenAI 이미지 생성 키가 필요합니다.', 422)
        references = [service.artifact(owner, base['id'], payload['view']+'.png')]
        if payload.get('reference_asset'):
            references.append(service.asset(owner, payload['reference_asset'], 'png'))
        if payload.get('identity_image_id'):
            prior = service.raw(owner, payload['identity_image_id'])
            if prior['kind'] != 'image' or any(prior['contract'].get(k) != payload[k] for k in ('base_id', 'base_sha256', 'object_key')):
                raise PipelineError('identity_mismatch', '같은 물체·기준 몸의 다른 시점 시안만 참조할 수 있습니다.', 422)
            references.append(service.artifact(owner, prior['id'], 'canvas.png'))
        directory.mkdir(parents=True, exist_ok=True)
        receipts = []
        for i, path in enumerate(references):
            name = f'reference-{i}.png'; (directory/name).write_bytes(path.read_bytes())
            receipts.append({'file': name, 'sha256': sha(directory/name)})
        prompt = (
            f'Create ONE isolated modular character part, {payload["view"]} orthographic view. '
            'The FIRST reference is the frozen bald base avatar, a measurement template, not a redesign target. '
            'Keep precisely the same 2048x2048 canvas, projection, pose and relative placement as this base view. '
            f'The body is {base["contract"]["height_m"]} metres tall, scalp at y=300, bare sole y=1800, centerline x=1024. '
            'Render ONLY the requested part where it would be worn on this body. Remove the reference body from the output. '
            'Use a transparent background; do not center, crop, enlarge or independently scale the part to fill the canvas. '
            'Complete the hidden attachment surfaces, inside sleeve/neck/waist/foot openings as appropriate. '
            'Additional references define style or the same object from another angle; maintain its identity and colors. '
            'No text, labels, checkerboard, cast shadows, extra parts or full character. '
            'Art direction: '+payload['description'])
        config = provider_config or {'model': DEFAULT_MODEL, 'base_url': os.getenv('OPENAI_API_BASE', DEFAULT_BASE)}
        settings = {'model': config['model'], 'base_url': config['base_url'],
                    'references': receipts, 'prompt': prompt, 'attempt': 'not_started'}
        _write_json(directory/'design.json', settings)
        _write_json(directory/'record.json', {'id': item, 'kind': 'design', 'name': payload['name'], 'contract': payload,
            'fingerprint': fingerprint, 'created_at': now(), 'status': 'accepted', 'files': {}, 'process': identity(),
            'provider': {'name': 'openai', 'model': config['model'], 'max_new_images': 1}, 'error': None})
        return service.public(owner, item), True


def execute(service, owner, item):
    lock = run_lock((owner, item))
    if not lock.acquire(blocking=False):
        raise PipelineError('worker_active', '시안 생성·복구 중입니다.', 409)
    stack = ExitStack()
    try:
        directory = service.directory(owner, item); record = service.raw(owner, item)
        if record['kind'] != 'design':
            raise PipelineError('invalid_kind', '시안 생성 작업이 아닙니다.', 422)
        stack.enter_context(provider_lease(directory/'image'))
        settings = read_json(directory/'design.json')
        if record['status'] == 'design_review_required':
            return service.public(owner, item)
        try:
            cached_response = (directory/'image.response.json').is_file()
            if settings['attempt'] == 'not_started' or (settings['attempt'] == 'submitting' and cached_response):
                references = [directory/r['file'] for r in settings['references']]
                if any(sha(path) != receipt['sha256'] for path, receipt in zip(references, settings['references'])):
                    raise ValueError('Reference changed')
                settings['attempt'] = 'submitting'; settings['executor'] = identity()
                _write_json(directory/'design.json', settings)
                record['status'] = 'image_running'; _write_json(directory/'record.json', record)
                raw = generate_standard_part_image(references, settings['prompt'], settings['model'], settings['base_url'], receipt=directory/'image')
                (directory/'provider-original.png').write_bytes(raw)
                with Image.open(io.BytesIO(raw)) as image:
                    source_size = list(image.size)
                    fitted = ImageOps.contain(image.convert('RGBA'), (2048, 2048), Image.Resampling.LANCZOS)
                    offset = [(2048-fitted.width)//2, (2048-fitted.height)//2]
                    canvas = Image.new('RGBA', (2048, 2048)); canvas.paste(fitted, offset)
                    canvas.save(directory/'generated.png')
                settings.update(attempt='received', image_sha256=sha(directory/'generated.png'),
                    original_sha256=sha(directory/'provider-original.png'),
                    normalization={'source_size': source_size, 'scaled_size': list(fitted.size), 'offset_px': offset})
                _write_json(directory/'design.json', settings)
            if settings['attempt'] != 'received':
                raise PipelineError('image_uncertain', '이미지 응답을 확인할 수 없어 자동 재제출하지 않습니다.', 409)
            if (sha(directory/'generated.png') != settings['image_sha256']
                    or sha(directory/'provider-original.png') != settings['original_sha256']):
                raise ValueError('Image receipt mismatch')
            asset = service.upload(owner, (directory/'generated.png').read_bytes(), 'png')
            record.update(status='design_review_required', files={'generated.png': asset['id'], 'provider-original.png': settings['original_sha256']},
                result={'image_asset': asset['id'], 'canvas_size': [2048, 2048], 'normalization': settings['normalization'], 'landmark_review': 'required'}, error=None)
        except Exception as exc:
            # Preserve receipt and stage. A new execution can only finalize received
            # bytes; no timeout, HTTP rejection or lost response re-enters POST.
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (400, 401, 403, 404, 422, 429):
                settings['attempt'] = 'rejected'; _write_json(directory/'design.json', settings)
            record.update(status='image_paused', error='시안 응답·규격을 확인해야 합니다. 기존 시도는 보존했고 자동 재요청하지 않습니다.')
        _write_json(directory/'record.json', record)
        return service.public(owner, item)
    finally:
        try:
            stack.close()
        finally:
            lock.release()


def similarity(anchors, max_error):
    source = [a['source'] for a in anchors]; target = [a['target'] for a in anchors]
    if len({a['name'] for a in anchors}) != len(anchors):
        raise PipelineError('duplicate_anchor', '기준점 이름은 중복할 수 없습니다.', 422)
    cx, cy = [sum(p[i] for p in source)/len(source) for i in range(2)]
    tx, ty = [sum(p[i] for p in target)/len(target) for i in range(2)]
    denom = sum((x-cx)**2+(y-cy)**2 for x, y in source)
    if denom < 1:
        raise PipelineError('invalid_anchors', '서로 떨어진 착용 기준점이 필요합니다.', 422)
    a = sum((x-cx)*(u-tx)+(y-cy)*(v-ty) for (x,y),(u,v) in zip(source,target))/denom
    b = sum((x-cx)*(v-ty)-(y-cy)*(u-tx) for (x,y),(u,v) in zip(source,target))/denom
    scale = math.hypot(a,b)
    if not .25 <= scale <= 4:
        raise PipelineError('invalid_scale', '시안의 배율 차이가 너무 큽니다. 디자인을 수정해 주세요.', 422)
    dx, dy = tx-a*cx+b*cy, ty-b*cx-a*cy
    errors = [math.hypot(a*x-b*y+dx-u, b*x+a*y+dy-v) for (x,y),(u,v) in zip(source,target)]
    if max(errors) > max_error:
        raise PipelineError('design_mismatch', '착용 기준점의 비율이 맞지 않습니다. 배율 정렬 대신 디자인 수정이 필요합니다.', 422)
    det = a*a+b*b
    inverse = (a/det, b/det, (-a*dx-b*dy)/det, -b/det, a/det, (b*dx-a*dy)/det)
    return inverse, {'scale': scale, 'rotation_radians': math.atan2(b,a), 'translation_px': [dx,dy], 'errors_px': errors}


def align(service, owner, item, payload):
    with LOCK:
        record = service.raw(owner, item)
        if record['kind'] != 'design' or record['status'] != 'design_review_required' or record['files'].get('generated.png') != payload['source_sha256']:
            raise PipelineError('design_changed', '검수한 시안 버전을 다시 확인해 주세요.', 409)
        source = service.artifact(owner, item, 'generated.png')
        inverse, report = similarity(payload['anchors'], payload['max_error_px'])
        with Image.open(source) as image:
            aligned = image.convert('RGBA').transform((2048, 2048), Image.Transform.AFFINE, inverse, Image.Resampling.BICUBIC)
            if aligned.getchannel('A').getbbox() is None:
                raise PipelineError('empty_design', '정렬한 시안이 비어 있습니다.', 422)
            raw = io.BytesIO(); aligned.save(raw, format='PNG')
        asset = service.upload(owner, raw.getvalue(), 'png')
        value = service.image(owner, {'base_id': record['contract']['base_id'], 'base_sha256': record['contract']['base_sha256'],
            'image_asset': asset['id'], 'object_key': record['contract']['object_key'], 'view': record['contract']['view'],
            'crop': [0,0,2048,2048], 'export_size': 1024})
        target = service.raw(owner, value['id'])
        target['lineage'] = {'design_id': item, 'source_sha256': payload['source_sha256'], 'provider': record['provider'],
                             'reviewed_at': now(), 'alignment': report, 'review': payload}
        _write_json(service.directory(owner, value['id'])/'record.json', target)
        return service.public(owner, value['id'])
