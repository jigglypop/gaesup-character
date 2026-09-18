"""Durable image -> individual Meshy parts -> one local canonical skeleton.

One persisted attempt per paid stage. Resume only polls known task IDs or starts
stages never attempted within the original request's fixed limits.
"""
import base64
import hashlib
import io
import json
import logging
import os
import re
from src.services.object_storage import copy_file, copy_tree
import uuid
from src.services.object_storage import StoredPath as Path
from threading import Lock
import time

import httpx
from PIL import Image

from src.paths import BACKEND_ROOT
from src.services import character_jobs
from src.services.asset_editor import _write_json
from src.services.avatar_blueprints import AvatarBlueprints, SLOTS
from src.services.avatar_equipment import EQUIPMENT
from src.services.avatar_openai_images import (DEFAULT_MODEL, DEFAULT_BASE, OpenAIImageHTTPError,
                                                generate_part_image as generate_openai_part_image)
from src.services.avatar_factory import IMAGE_PROFILE as PROFILE, _LOCK, digest
from src.services.character_parts import blender_executable
from src.services.character_pipeline import PipelineError, now, read_json
from src.services.process_identity import identity, state as process_state
from src.services.avatar_production_spec import production_spec, public_spec, IMAGE_INTAKE_POLICY
from src.services.avatar_image_prompts import PART_FIT, hair_length_prompt, AXIS_LOCK

PARTS = SLOTS[1:] + ['body', 'hair']
CHARACTER_PART_SLOTS = ['body', 'hair', 'hat', 'top', 'bottom', 'shoes']
LOGGER = logging.getLogger(__name__)
WHOLE_BODY_PROMPT = (
    'Create ONE complete full-body Maple-inspired chibi character from the reference. '
    'Include the entire head with face and hair, neck, torso, both arms and hands, both legs and feet. '
    'Dress the character in an opaque short-sleeved T-shirt, shorts and simple shoes. '
    'Preserve the reference identity, face, colors, oversized head and tiny limbs. '
    'One intact character from the top of the head to the soles, front orthographic straight horizontal T-pose, '
    'both hands visible, feet parallel and separated. '
    'Keep the entire silhouette inside the frame with margin on a plain white background. '
    'No cropped head, isolated face, floating parts, disassembly, extra characters, text or cast shadows.'
)
WARDROBE_BODY_PROMPT = (
    'Create ONE complete Maple-inspired chibi wardrobe BASE BODY from the reference identity. '
    'Include the entire bald head, original face, ears, neck, torso, both arms, hands, legs and bare feet. '
    'Preserve the face, eyes, skin color and cute oversized-head proportions. '
    'The scalp and all limb contours must be complete and clearly visible. '
    'Dress the figure in one thin fully opaque matte WHITE fitted underlayer from neck to wrists and ankles; never blue, teal or cyan. '
    'For a 1.2m figure use a slender torso 0.22m wide and 0.13m deep, arms 0.036m diameter and legs 0.044m diameter. '
    'Keep shoulder, wrist, hip and ankle positions and limb lengths fixed; reduce only the thickness of the clothed core. '
    'No sweater, baggy trousers, padding, inflated shoulders, folds, cuffs or thick waistband. '
    'Use plain matte fabric and clean unadorned shapes, with the original large head, hands and bare feet unchanged. '
    'Show a full bald head without hair, hats, bunny ears or ornaments. '
    'Front orthographic horizontal T-pose, arms exactly 90 degrees away from the torso, hands open and separate, '
    'feet parallel and shoulder-width apart. Both shoulders, elbows, wrists, hips, knees and ankles must be unambiguous. '
    'One intact fully visible, fully clothed figure on a plain white background with margin; no text, shadows or extra parts. '
    'This is the reusable neutral clothed base for separately generated interchangeable garments.'
)
WHOLE_BODY_PROMPT += AXIS_LOCK
WARDROBE_BODY_PROMPT += AXIS_LOCK
_RUN_LOCKS = {}
DESCRIPTIONS = {
    'hair': 'one complete voluminous hairstyle including bangs, both sides, full crown, rear hair and nape; reconstruct hair hidden under the hat; hair only, no hat, headwear, face, scalp skin or body',
    'body': 'one complete clothed character, including head and all limbs',
    'face': 'ONE closed bald oversized chibi head with the original low-set large eyes and small mouth; the mesh ends at the chin; absolutely no neck, shoulders, bust, pedestal, hair, hat or clothing',
    'hairBack': 'back hair shell with completed hidden crown and nape; no face, head, bangs or clothing',
    'hairFront': 'front hair and bangs as a shell with an open face area; no face, head, hat or clothing',
    'hat': 'hat alone with complete hidden rim and underside; no head or hair',
    'top': 'top alone with complete collar, sleeves, cuffs and waistband; no hands, head, legs or skirt',
    'bottom': 'bottom alone with complete hidden waistband and opaque inner lining; no torso, legs or shoes',
    'shoes': 'matching pair of shoes with complete openings and hidden ankle overlap; no legs or body',
}
DESCRIPTIONS.update({slot: item['description'] for slot, item in EQUIPMENT.items()})


def capabilities():
    image = bool(os.getenv('OPENAI_API_KEY', '').strip())
    meshy = bool(os.getenv('MESHY_API_KEY'))
    blender = bool(blender_executable())
    return {'character_pipeline': 'parts_to_character_v2', 'image_configured': image, 'meshy_configured': meshy, 'blender_available': blender,
            'image_intake_policy': IMAGE_INTAKE_POLICY,
            'image_provider': 'openai', 'image_model': os.getenv('AVATAR_IMAGE_MODEL', DEFAULT_MODEL),
            'meshy_model': 'meshy-7', 'slots': PARTS, 'ready': image and meshy and blender,
            'next_actions': [{'id': 'produce_images', 'enabled': image and meshy and blender,
                              'reason': None if image and meshy and blender else '서버의 OpenAI·Meshy 키와 Blender 설치를 확인해 주세요.'},
                             {'id': 'produce_prepared', 'enabled': meshy and blender,
                              'reason': None if meshy and blender else '서버의 Meshy 키와 Blender 설치를 확인해 주세요.'}]}


def generate_part_image(source, prompt, model, base):
    """Exactly one POST; deliberately no model fallback or automatic retry."""
    with Image.open(io.BytesIO(source.read_bytes())) as image:
        mime = Image.MIME.get(image.format, 'image/png')
    payload = {'contents': [{'parts': [{'text': prompt}, {'inlineData': {
        'mimeType': mime, 'data': base64.b64encode(source.read_bytes()).decode('ascii')}}]}],
        'generationConfig': {'responseModalities': ['IMAGE'], 'imageConfig': {'aspectRatio': '1:1'}}}
    with httpx.Client(timeout=180) as client:
        response = client.post(f'{base}/models/{model}:generateContent',
                               headers={'x-goog-api-key': os.environ['GEMINI_API_KEY']}, json=payload)
        response.raise_for_status()
        result = response.json()
    for candidate in result.get('candidates', []):
        for part in candidate.get('content', {}).get('parts', []):
            if part.get('thought'):
                continue
            inline = part.get('inlineData') or part.get('inline_data') or {}
            if inline.get('data'):
                raw = base64.b64decode(inline['data'], validate=True)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.width * image.height > 32_000_000:
                        raise ValueError('Image size limit')
                    output = io.BytesIO(); image.convert('RGBA').save(output, format='PNG')
                    return output.getvalue()
    raise PipelineError('image_missing', '이미지 제공자가 파츠 이미지를 반환하지 않았습니다. 자동 재요청하지 않습니다.', 422)


class AvatarImagePipeline:
    def __init__(self, factory):
        self.factory = factory
        self.blueprints = AvatarBlueprints(factory.data)

    def _reuse_character_parts(self, owner, target, parts, reuse_job_id, character_id, source_sha256):
        if not reuse_job_id:
            return []
        source_public = self.factory.get(owner, reuse_job_id)
        source = self.factory.directory(owner, reuse_job_id)
        if (source_public.get('character_id') != character_id
                or source_public.get('source_sha256') != source_sha256
                or not (source/'source.png').is_file() or digest(source/'source.png') != source_sha256):
            raise PipelineError('reuse_source_mismatch', '같은 캐릭터 원본에서 만든 파츠만 재사용할 수 있습니다.', 422)
        source_state = read_json(source/'pipeline.json')
        reused = []
        for part in parts:
            if part['slot'] == 'body':
                continue
            prior = next((item for item in source_state.get('parts', []) if item.get('slot') == part['slot']), None)
            if not prior or prior.get('image', {}).get('status') != 'succeeded' or prior.get('model', {}).get('status') != 'ready':
                continue
            image = prior['image']; prior_image_name = image.get('file')
            if not isinstance(prior_image_name, str) or Path(prior_image_name).name != prior_image_name:
                raise PipelineError('reuse_artifact_changed', f'{part["slot"]}: 재사용할 이미지 경로가 올바르지 않습니다.', 422)
            image_source = source/'output'/prior_image_name
            receipt = read_json(source/'parts'/part['slot']/'generation-artifacts.json').get('generated', {})
            model_source = source/'parts'/part['slot']/'generated.glb'
            if (not image_source.is_file() or digest(image_source) != image.get('sha256')
                    or not model_source.is_file() or digest(model_source) != receipt.get('sha256')):
                raise PipelineError('reuse_artifact_changed', f'{part["slot"]}: 재사용할 파츠 증거가 변경되었습니다.', 422)
            image_name = f'{part["slot"]}-image.png'
            copy_file(image_source, target/'output'/image_name)
            model_target = target/'parts'/part['slot']/'generated.glb'
            model_target.parent.mkdir(parents=True, exist_ok=True)
            copy_file(model_source, model_target)
            _write_json(model_target.parent/'generation-artifacts.json', {'generated': {
                'path': str(model_target), 'sha256': digest(model_target),
                'reused_from': {'job_id': reuse_job_id, 'slot': part['slot']}}})
            part['image'] = {'status': 'succeeded', 'file': image_name,
                'sha256': digest(target/'output'/image_name), 'asset': image.get('asset'), 'origin': 'reused'}
            part['model'] = {'status': 'ready', 'task_id': prior['model'].get('task_id'), 'origin': 'reused'}
            part['provenance'].update(origin='reused_generated_candidate', source_job_id=reuse_job_id)
            reused.append(part['slot'])
        return reused

    def create(self, owner, key, payload):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}', key):
            raise PipelineError('invalid_key', '생산 요청 식별자가 필요합니다.', 422)
        payload = dict(payload)
        if payload.get('hair_length') is None:
            payload.pop('hair_length', None)  # Preserve old idempotency fingerprints.
        hair_length = payload.get('hair_length', 'source')
        if hair_length not in ('source', 'short', 'long'):
            raise PipelineError('invalid_hair_length', '머리카락 길이를 다시 선택하세요.', 422)
        production_mode = payload.get('production_mode', 'legacy')
        multiview = payload.get('view_mode', 'single') == 'front_side'
        if multiview and (production_mode != 'character_parts' or payload.get('reuse_job_id')):
            raise PipelineError('invalid_view_mode', '공통 규격 생산은 새 캐릭터 파츠 세트로 시작하세요.', 422)
        if production_mode not in ('legacy', 'character_parts'):
            raise PipelineError('invalid_production_mode', '지원하는 이미지 생산 모드를 선택하세요.', 422)
        if production_mode == 'character_parts':
            if payload.get('image_mode') != 'generate':
                raise PipelineError('invalid_image_mode', '캐릭터 파츠 세트는 원본 이미지 생성 모드를 사용하세요.', 422)
            payload['slots'] = payload.get('slots') or list(CHARACTER_PART_SLOTS)
            payload['body_purpose'] = 'wardrobe_base'
            payload['rig_with_meshy'] = True
            if payload.get('reuse_job_id') and not re.fullmatch(r'[a-f0-9]{24}', payload['reuse_job_id']):
                raise PipelineError('invalid_reuse', '올바른 재사용 작업 ID가 필요합니다.', 422)
        job_id = hashlib.sha256(f'{owner}:image:{key}'.encode()).hexdigest()[:24]
        directory = self.factory.directory(owner, job_id)
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with _LOCK:
            existing = read_json(directory/'job.json')
            if existing:
                if existing['fingerprint'] != fingerprint:
                    raise PipelineError('idempotency_conflict', '같은 요청에 다른 생산 설정이 있습니다.')
                return self.factory.get(owner, job_id), False
            action = capabilities()['next_actions'][0 if payload['image_mode'] == 'generate' else 1]
            if not action['enabled']:
                raise PipelineError('provider_unavailable', action['reason'], 422)
            slots = payload['slots']
            if not slots or len(slots) != len(set(slots)) or any(s not in PARTS for s in slots):
                raise PipelineError('invalid_slots', '중복되지 않은 이미지 파츠를 선택하세요.', 422)
            if production_mode == 'character_parts' and slots != CHARACTER_PART_SLOTS:
                raise PipelineError('invalid_slots', '몸·머리카락·모자·상의·하의·신발 한 세트를 선택하세요.', 422)
            if production_mode != 'character_parts' and 'hair' in slots:
                raise PipelineError('invalid_slots', '일체형 머리카락은 캐릭터 파츠 모드에서 생성하세요.', 422)
            if production_mode != 'character_parts' and 'body' in slots and slots != ['body']:
                raise PipelineError('invalid_slots', '통짜 전신은 얼굴·의상을 포함합니다. 전신 하나만 선택하세요.', 422)
            mesh_rig = payload.get('rig_with_meshy', False)
            body_purpose = payload.get('body_purpose', 'whole_character')
            if body_purpose not in ('whole_character', 'wardrobe_base') or (body_purpose == 'wardrobe_base' and
                    ((production_mode != 'character_parts' and slots != ['body']) or not mesh_rig)):
                raise PipelineError('invalid_body_purpose', '의상용 기준 몸은 Meshy 전신 리깅 경로를 사용하세요.', 422)
            motions = payload.get('motion_actions', {})
            if (mesh_rig and slots != ['body'] and production_mode != 'character_parts') or (motions and not mesh_rig):
                raise PipelineError('invalid_rig', 'Meshy 리깅과 동작은 통짜 전신에서 선택하세요.', 422)
            if mesh_rig:
                from src.services.avatar_meshy import AvatarMeshy, SLOTS as MOTION_SLOTS
                available = {i['action_id'] for i in AvatarMeshy(self.factory).library(owner)} if motions else set()
                if not set(motions) <= set(MOTION_SLOTS) or any(type(v) is not int or v not in available for v in motions.values()):
                    raise PipelineError('invalid_action', '기본 동작을 현재 Meshy 목록에서 다시 선택하세요.', 422)
            character = self.factory.pipeline.detail(payload['character_id'], owner)
            source = self.factory.pipeline.artifact(character['id'], owner, 'reference')
            content = source.read_bytes()
            source_hash = hashlib.sha256(content).hexdigest()
            if source_hash != payload['source_sha256']:
                raise PipelineError('source_changed', '원본 이미지가 바뀌었습니다. 다시 불러오세요.')
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            blueprint = self.blueprints.read(owner, character['id'])
            if blueprint['revision'] != payload['blueprint_revision']:
                raise PipelineError('revision_conflict', '설계가 바뀌었습니다. 다시 불러오세요.')
            parts = []; prepared = {}
            for slot in slots:
                layer = {'description': DESCRIPTIONS['hair']} if slot == 'hair' else next(l for l in blueprint['layers'] if l['slot'] == slot)
                part = {'slot': slot, 'description': layer.get('description', ''),
                        'image': {'status': 'pending'}, 'model': {'status': 'pending'},
                        'provenance': {'origin': 'generated_part_candidate', 'review': 'pending'}}
                if multiview:
                    part['views'] = {view: {'status': 'pending'} for view in ('front', 'side')}
                if payload['image_mode'] == 'prepared':
                    layer = next(l for l in blueprint['layers'] if l['slot'] == slot)
                    # Prepared PNGs are exported as complete, isolated bitmaps by the image editor.
                    if not layer['asset'] or layer['asset'] == 'sample-A-atlas' or list(layer['crop']) != [0, 0, 1, 1]:
                        raise PipelineError('part_image_missing', f'{slot}: 완성한 개별 PNG를 먼저 저장해 주세요.', 422)
                    path = self.blueprints.asset(owner, layer['asset'])
                    name = f'{slot}-image.png'; prepared[name] = path.read_bytes()
                    part['image'] = {'status': 'succeeded', 'sha256': digest(path), 'asset': layer['asset'], 'file': name, 'origin': 'prepared'}
                parts.append(part)
            directory.mkdir(parents=True, exist_ok=True)
            (directory/'source.png').write_bytes(content)
            (directory/'output').mkdir(exist_ok=True)
            for name, raw in prepared.items():
                (directory/'output'/name).write_bytes(raw)
            reused = self._reuse_character_parts(owner, directory, parts, payload.get('reuse_job_id'),
                                                   character['id'], source_hash) if production_mode == 'character_parts' else []
            if payload.get('reuse_job_id') and production_mode != 'character_parts':
                raise PipelineError('invalid_reuse', '파츠 재사용은 캐릭터 파츠 모드에서만 사용할 수 있습니다.', 422)
            _write_json(directory/'pipeline.json', {'parts': parts, 'blueprint': blueprint,
                'production_spec': production_spec(hair_length) if multiview else None,
                'hair_length': hair_length,
                'production_mode': production_mode, 'reuse': {'source_job_id': payload.get('reuse_job_id'), 'slots': reused},
                'rig_with_meshy': mesh_rig, 'motion_actions': motions,
                'body_purpose': body_purpose, 'body_prompt': WARDROBE_BODY_PROMPT if body_purpose == 'wardrobe_base' else WHOLE_BODY_PROMPT,
                'body_height_m': 1.2 if body_purpose == 'wardrobe_base' else PROFILE['height'],
                'image_provider': 'openai', 'image_model': capabilities()['image_model'],
                'image_base': os.getenv('OPENAI_API_BASE', DEFAULT_BASE).rstrip('/'),
                'meshy_base': os.getenv('MESHY_API_BASE_URL', 'https://api.meshy.ai').rstrip('/')})
            _write_json(directory/'job.json', {'id': job_id, 'fingerprint': fingerprint, 'executor': self.factory.instance,
                'executor_process': identity(), 'character_id': character['id'], 'character_name': character['name'],
                'input_kind': 'image', 'production_mode': production_mode, 'auto_assemble': production_mode == 'character_parts', 'source_sha256': source_hash, 'profile': ({**PROFILE,
                    'name': '의상용 기준 몸 · 머리 포함' if body_purpose == 'wardrobe_base' else '통짜 전신 · 반팔·반바지',
                    'body_purpose': body_purpose, 'body_origin': 'generated_whole_character'} if body_purpose == 'wardrobe_base' or slots == ['body'] else PROFILE),
                'image_provider': 'openai', 'image_model': capabilities()['image_model'],
                'status': 'pipeline_queued', 'created_at': now(), 'updated_at': now(), 'error': None,
                'limits': {'image_tasks': sum(p['image']['status'] == 'pending' for p in parts) * (2 if multiview else 1) if payload['image_mode'] == 'generate' else 0,
                           'meshy_tasks': sum(p['model']['status'] == 'pending' for p in parts)},
                'review': {'decision': 'pending'}, 'files': {p['image']['file']: p['image']['sha256'] for p in parts if p['image']['status'] == 'succeeded'}})
            self.publish(owner, job_id, read_json(directory/'pipeline.json'))
            if mesh_rig:
                accepted = read_json(directory/'job.json')
                accepted['limits'].update(meshy_rig_tasks=1, meshy_animation_tasks=len(set(motions.values())))
                accepted['profile'].update(rig='meshy-native', bones=None, head_height=None, head_ratio=None,
                                           height=1.2 if body_purpose == 'wardrobe_base' else PROFILE['height'])
                if body_purpose == 'wardrobe_base':
                    accepted['profile']['base_outfit'] = 'opaque_training_bodysuit'
                _write_json(directory/'job.json', accepted)
            return self.factory.get(owner, job_id), True

    def publish(self, owner, job_id, state):
        directory = self.factory.directory(owner, job_id)
        _write_json(directory/'pipeline.json', state)
        job = read_json(directory/'job.json')
        job['parts'] = [{'slot': p['slot'], 'image_status': p['image']['status'], 'image_asset': p['image'].get('asset'),
                         'model_status': p['model']['status'], 'task_id': p['model'].get('task_id'),
                         'progress': p['model'].get('progress', 0), 'provenance': p.get('provenance'),
                         'image_failure': p['image'].get('failure'),
                         'view_alignment': p.get('view_alignment'),
                         'views': {view: {k: value.get(k) for k in ('status', 'file', 'sha256', 'qc', 'failure', 'saving_seconds')}
                                   for view, value in p.get('views', {}).items()}} for p in state['parts']]
        if state.get('production_spec'):
            job['production_spec'] = public_spec(state['production_spec'])
            reused = state.get('reuse', {}).get('slots', [])
            views = [image for p in state['parts'] if p['slot'] not in reused for image in p['views'].values()]
            # Accepted replacements survive a restart between pipeline and job writes.
            job['limits']['image_tasks'] = max(job['limits']['image_tasks'], len(views) + sum(len(image.get('previous_attempts', [])) for image in views))
        job['image_failures'] = [{'slot': p['slot'], **p['image']['failure']}
                                 for p in state['parts'] if p['image'].get('failure')]
        for p in state['parts']:
            for view in p.get('views', {}).values():
                if view.get('file'):
                    job.setdefault('files', {})[view['file']] = view['sha256']
            if p['image'].get('file'):
                job.setdefault('files', {})[p['image']['file']] = p['image']['sha256']
        job['updated_at'] = now(); _write_json(directory/'job.json', job)

    def _part_prompt(self, state, part):
        if part['slot'] == 'body':
            return state.get('body_prompt', WHOLE_BODY_PROMPT)
        prompt = ('Extract and complete ONE modular 3D modeling reference from the supplied character: '
                  + DESCRIPTIONS[part['slot']] + '. ')
        if part['slot'] == 'hair':
            prompt += hair_length_prompt(state.get('production_spec') or production_spec(state.get('hair_length', 'source')))
        if state.get('production_mode') == 'character_parts':
            return (prompt +
                PART_FIT.get(part['slot'], '') + ' ' +
                'Use the exact design, colors, materials, silhouette and details visibly belonging to this same character. '
                'Do not invent, replace, restyle or add an accessory or garment. '
                'Reconstruct only hidden connection surfaces needed to make this same part complete, with overlap for assembly. '
                'Center only this isolated part, fully visible, in a front orthographic view on a plain white background. '
                'No cast shadows, checkerboard, text, other body parts or full character. '
                + ('Additional identification notes: '+part['description'] if part.get('description') else ''))
        return (prompt +
            'Preserve its colors, identity, original silhouette and very large head with tiny limbs. Never normalize to adult or 2.5-head proportions. Front orthographic view. '
            'Complete hidden connection areas with generous overlap. Center only this isolated part, fully visible, on a plain white background. '
            'No cast shadows, checkerboard, text, other body parts or full character. This is a new completed design, not a crop. '
            'When the reference does not include this equipment, design a matching Maple-inspired fantasy accessory. '
            + ('Additional art direction: '+part['description'] if part.get('description') else ''))

    def _record_image_failure(self, owner, job_id, state, part, exc, receipt):
        failure_id = getattr(exc, 'diagnostic_id', uuid.uuid4().hex[:12])
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            part['image']['status'] = 'rejected' if status in (400, 401, 403, 404, 422, 429) else 'failed'
            category = getattr(exc, 'category', 'provider_http')
        elif isinstance(exc, httpx.RequestError):
            part['image']['status'] = 'submission_uncertain'
            category = 'provider_connection'
        else:
            if part['image'].get('status') not in ('received',):
                part['image']['status'] = ('submitting' if receipt.with_suffix('.response.json').is_file() else 'failed')
            category = 'local_processing'
        part['image']['failure'] = {'id': failure_id, 'category': category, 'type': type(exc).__name__, 'at': now()}
        self.publish(owner, job_id, state)

    def resume(self, owner, job_id, *, stage='images'):
        if stage not in ('images', 'models'):
            raise PipelineError('invalid_stage', '이미지 또는 3D 단계를 선택해 주세요.', 422)
        self.factory.get(owner, job_id)
        directory = self.factory.directory(owner, job_id)
        with _LOCK:
            job = read_json(directory/'job.json')
            if job.get('input_kind') != 'image' or job['status'] not in ('pipeline_paused', 'failed', 'recovery_required', 'review_required'):
                raise PipelineError('invalid_state', '현재 재개할 수 없는 작업입니다.')
            runner = read_json(directory/'output/runner.json')
            if job['status'] in ('failed', 'recovery_required') and runner and process_state(runner.get('process')) != 'exited':
                raise PipelineError('worker_running', '이전 Blender 프로세스가 종료되었는지 확인이 필요합니다.')
            state = read_json(directory/'pipeline.json')
            if stage == 'models':
                from src.services.avatar_stage_resume import validate_model_inputs
                validate_model_inputs(directory, state)
            if stage == 'images' and state.get('production_spec'):
                from src.services.avatar_multiview_images import can_resume
                if not can_resume(directory, state):
                    raise PipelineError('view_recovery_required', '기존 이미지 응답 확인 또는 실패 이미지 재요청이 필요합니다.', 409)
            for part in state['parts']:
                cached_response = (directory/'output'/f'{part["slot"]}-provider.response.json').is_file()
                if stage == 'images' and not state.get('production_spec') and part['image']['status'] in ('submitting', 'submission_uncertain', 'rejected', 'failed') and not cached_response:
                    raise PipelineError('image_attempt_recorded', '이미 시도한 이미지 요청입니다. 새 생산 버전에서만 다시 요청할 수 있습니다.')
                if read_json(directory/'parts'/part['slot']/'generation-artifacts.json').get('generated'):
                    continue
                task = read_json(directory/'parts'/part['slot']/'character.json')
                if task and not task.get('task_id'):
                    raise PipelineError('task_recovery_required', 'Meshy 작업 ID 확인이 필요합니다. 불확실한 요청은 재제출하지 않습니다.')
                if task.get('status') in ('FAILED', 'CANCELED'):
                    raise PipelineError('provider_failed', '실패한 Meshy 작업은 새 생산 버전에서만 다시 요청할 수 있습니다.')
            if job['status'] in ('failed', 'recovery_required') and (directory/'output/input.json').is_file():
                # Keep failed work files and their exact input/seal before rebuilding locally.
                attempt = uuid.uuid4().hex
                archive = directory/'attempts'/attempt
                copy_tree(directory/'output', archive/'output')
                _write_json(archive/'job.json', job)
                job.setdefault('previous_attempts', []).append({'id': attempt, 'status': job['status'], 'archived_at': now()})
            job.update(status='pipeline_queued', executor=self.factory.instance, executor_process=identity(),
                       resume_stage=stage, error=None)
            _write_json(directory/'job.json', job)
        return self.factory.get(owner, job_id)

    def rebuild(self, owner, job_id):
        """Create a new local assembly version from completed provider outputs."""
        self.factory.get(owner, job_id)
        with _LOCK:
            source = self.factory.directory(owner, job_id)
            original = read_json(source/'job.json'); state = read_json(source/'pipeline.json')
            if state.get('rig_with_meshy'):
                raise PipelineError('native_rig_preserved', 'Meshy 원본 골격은 재조립하지 않습니다. 전신 결과에서 기존 동작을 선택하세요.')
            if original.get('input_kind') != 'image' or original['status'] not in ('review_required', 'failed', 'recovery_required'):
                raise PipelineError('invalid_state', '생성이 끝난 이미지 작업만 기존 파츠로 재조립할 수 있습니다.')
            if not state.get('parts') or any(p['model']['status'] != 'ready' or p['image']['status'] != 'succeeded' for p in state['parts']):
                raise PipelineError('parts_not_ready', '모든 파츠 생성이 끝나야 유료 요청 없이 재조립할 수 있습니다.')
            runner = read_json(source/'output/runner.json')
            if runner and process_state(runner.get('process')) != 'exited':
                raise PipelineError('worker_running', '이전 Blender 프로세스가 아직 종료되지 않았습니다.')
            for part in state['parts']:
                name = part['image']['file']
                if Path(name).name != name or digest(source/'output'/name) != part['image']['sha256']:
                    raise PipelineError('source_changed', '기존 파츠 이미지 영수증이 일치하지 않습니다.')
                run = source/'parts'/part['slot']
                receipt = read_json(run/'generation-artifacts.json').get('generated', {})
                task = read_json(run/'character.json')
                if (not receipt.get('sha256') or not (run/'generated.glb').is_file()
                        or digest(run/'generated.glb') != receipt['sha256']
                        or not task.get('task_id') or task['task_id'] != part['model'].get('task_id')):
                    raise PipelineError('model_changed', '보존된 Meshy 파츠와 작업 영수증을 확인한 뒤 재조립해 주세요.')
            new_id = uuid.uuid4().hex[:24]; target = self.factory.directory(owner, new_id)
            (target/'output').mkdir(parents=True)
            copy_file(source/'source.png', target/'source.png')
            copy_tree(source/'parts', target/'parts')
            files = {}
            for part in state['parts']:
                name = part['image']['file']
                copy_file(source/'output'/name, target/'output'/name); files[name] = part['image']['sha256']
            _write_json(target/'pipeline.json', state)
            job = {k: original[k] for k in ('character_id', 'character_name', 'input_kind', 'source_sha256')}
            job.update(id=new_id, fingerprint=f'local-rebuild:{job_id}:{new_id}', source_job_id=job_id,
                executor=self.factory.instance, executor_process=identity(), profile=original.get('profile', PROFILE),
                status='pipeline_queued', created_at=now(), updated_at=now(), error=None,
                limits={'image_tasks': 0, 'meshy_tasks': 0}, review={'decision': 'pending'}, files=files)
            _write_json(target/'job.json', job)
            self.publish(owner, new_id, state)
        return self.factory.get(owner, new_id)

    def recover_task(self, owner, job_id, slot, task_id):
        self.factory.get(owner, job_id)
        directory = self.factory.directory(owner, job_id)
        with _LOCK:
            job = read_json(directory/'job.json'); state = read_json(directory/'pipeline.json')
            if job.get('input_kind') != 'image' or job['status'] != 'pipeline_paused' or slot not in [p['slot'] for p in state['parts']]:
                raise PipelineError('invalid_state', '복구할 파츠 작업을 찾을 수 없습니다.')
            run = directory/'parts'/slot; task = read_json(run/'character.json')
            if not task or task.get('task_id') or task.get('status') != 'submission_uncertain':
                raise PipelineError('invalid_state', '응답이 불확실한 기존 제출만 작업 ID로 복구할 수 있습니다.')
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', task_id):
                raise PipelineError('invalid_task', '올바른 Meshy 작업 ID를 입력하세요.', 422)
            try:
                with httpx.Client(base_url=state['meshy_base'], headers={'Authorization': 'Bearer '+os.environ['MESHY_API_KEY']}, timeout=30) as client:
                    task = character_jobs.refresh(run, client, task_id)
            except (httpx.HTTPError, KeyError, ValueError):
                raise PipelineError('task_lookup_failed', 'Meshy에서 해당 작업을 확인하지 못했습니다. 작업 ID와 연결 설정을 확인하세요.', 422) from None
            task['recovered_at'] = now(); task['recovered_by'] = owner; _write_json(run/'character.json', task)
            for p in state['parts']:
                if p['slot'] == slot:
                    p['model'] = {k: task.get(k) for k in ('status', 'task_id', 'progress')}
            self.publish(owner, job_id, state)
        return self.factory.get(owner, job_id)

    def _prepare_images(self, owner, job_id, state, job):
        directory = self.factory.directory(owner, job_id); output = directory/'output'
        from src.services.avatar_variants import prepare_body
        prepare_body(self, owner, job_id, state)
        if digest(directory/'source.png') != job['source_sha256']:
            raise PipelineError('source_changed', '보존한 원본 이미지가 변경되었습니다.')
        if state.get('production_spec'):
            from src.services.avatar_multiview_images import execute as generate_views
            generate_views(self, owner, job_id, state)
        for part in state['parts']:
            receipt = output/f'{part["slot"]}-provider'
            if part['image']['status'] == 'submitting' and receipt.with_suffix('.response.json').is_file():
                try:
                    raw = generate_openai_part_image(directory/'source.png', part['image']['prompt'],
                                                     state['image_model'], state['image_base'], receipt=receipt)
                    name = f'{part["slot"]}-image.png'; (output/name).write_bytes(raw)
                    part['image'].update(status='received', file=name, sha256=digest(output/name))
                    self.publish(owner, job_id, state)
                except Exception as exc:
                    if state.get('production_mode') != 'character_parts':
                        raise
                    self._record_image_failure(owner, job_id, state, part, exc, receipt)
                    continue
            if part['image']['status'] == 'received':
                image = part['image']; path = output/image['file']
                if digest(path) != image['sha256']:
                    raise PipelineError('image_changed', '보존한 이미지 응답이 변경되었습니다.')
                try:
                    asset = self.blueprints.upload(owner, path.read_bytes())
                    image.update(status='succeeded', asset=asset['id'])
                    image.pop('failure', None)
                    self.publish(owner, job_id, state)
                except Exception as exc:
                    if state.get('production_mode') != 'character_parts':
                        raise
                    self._record_image_failure(owner, job_id, state, part, exc, receipt)
                    continue
            if part['image']['status'] == 'succeeded':
                if digest(output/part['image']['file']) != part['image']['sha256']:
                    raise PipelineError('image_changed', '보존한 파츠 이미지가 변경되었습니다.')
                continue
            if part['image']['status'] != 'pending':
                if state.get('production_mode') == 'character_parts':
                    continue
                raise PipelineError('image_attempt_recorded', '이미지 요청의 응답을 확인할 수 없습니다. 자동 재제출하지 않습니다.')
            if sum('attempted_at' in p['image'] for p in state['parts']) >= job['limits']['image_tasks']:
                raise PipelineError('image_budget_exhausted', '허용된 이미지 생성 횟수를 모두 사용했습니다.')
            prompt = self._part_prompt(state, part)
            if part['slot'] == 'body' and state.get('body_purpose') != 'wardrobe_base' and part.get('description'):
                prompt += ' Additional art direction: '+part['description']
            provider = state.get('image_provider', 'gemini')
            if provider not in ('openai', 'gemini'):
                raise PipelineError('image_provider_unknown', '저장된 이미지 제공자를 확인할 수 없습니다. 자동 대체하지 않습니다.')
            part['image'] = {'status': 'submitting', 'prompt': prompt, 'provider': provider,
                             'model': state['image_model'], 'attempted_at': now()}
            self.publish(owner, job_id, state)
            _write_json(output/'progress.json', {'stage': 'images', 'message': f'{part["slot"]} 이미지 분리·숨겨진 형태 보완 중'})
            try:
                if provider == 'openai':
                    raw = generate_openai_part_image(directory/'source.png', prompt, state['image_model'], state['image_base'],
                                                     receipt=output/f'{part["slot"]}-provider')
                else:
                    raw = generate_part_image(directory/'source.png', prompt, state['image_model'], state['image_base'])
            except httpx.HTTPStatusError as exc:
                if state.get('production_mode') == 'character_parts':
                    self._record_image_failure(owner, job_id, state, part, exc, receipt)
                    continue
                if exc.response.status_code in (400, 401, 403, 404, 422, 429):
                    part['image']['status'] = 'rejected'; self.publish(owner, job_id, state)
                if isinstance(exc, OpenAIImageHTTPError):
                    reason = {
                        'invalid_request': '요청 형식이 이미지 제공자에서 거부되었습니다.',
                        'reference_url': '참조 이미지 URL을 이미지 제공자가 불러오지 못했습니다.',
                        'model': '설정된 이미지 모델을 제공자가 받아들이지 않았습니다.',
                        'size': '요청한 이미지 크기를 제공자가 받아들이지 않았습니다.',
                        'auth': '이미지 제공자 인증 또는 권한이 거부되었습니다.',
                        'policy': '이미지 요청이 제공자 정책 검사에서 거부되었습니다.',
                    }.get(exc.category, '이미지 제공자가 요청을 거부했습니다.')
                    raise PipelineError('image_provider_error',
                        f'이미지 생성 {part["slot"]}: {reason} 진단 {exc.diagnostic_id}. 자동 재요청하지 않습니다.') from None
                raise PipelineError('image_provider_error', f'이미지 생성 {part["slot"]}: HTTP {exc.response.status_code}. 모델·키·할당량을 확인해 주세요. 자동 재요청하지 않습니다.') from None
            except (httpx.RequestError, PipelineError, OSError, ValueError) as exc:
                if state.get('production_mode') != 'character_parts':
                    raise
                self._record_image_failure(owner, job_id, state, part, exc, receipt)
                continue
            name = f'{part["slot"]}-image.png'; (output/name).write_bytes(raw)
            # Keep the completed provider output before local indexing can fail.
            part['image'].update(status='received', file=name, sha256=digest(output/name))
            self.publish(owner, job_id, state)
            try:
                asset = self.blueprints.upload(owner, raw)
                part['image'].update(status='succeeded', file=name, sha256=digest(output/name), asset=asset['id'])
                part['image'].pop('failure', None)
                self.publish(owner, job_id, state)
            except Exception as exc:
                if state.get('production_mode') != 'character_parts':
                    raise
                self._record_image_failure(owner, job_id, state, part, exc, receipt)
        incomplete_images = [p['slot'] for p in state['parts'] if p['image']['status'] != 'succeeded']
        if incomplete_images:
            raise PipelineError('part_images_incomplete',
                f'파츠 이미지 {len(incomplete_images)}개가 완료되지 않았습니다. 실패 기록을 보존했고 Meshy 단계는 시작하지 않았습니다.')

    def execute(self, owner, job_id, *, poll_seconds=8, deadline_seconds=3600):
        directory = self.factory.directory(owner, job_id); output = directory/'output'
        with _LOCK:
            lock = _RUN_LOCKS.setdefault(str(directory), Lock())
        if not lock.acquire(blocking=False):
            return
        try:
            job = read_json(directory/'job.json')
            if job.get('status') != 'pipeline_queued' or job.get('executor') != self.factory.instance:
                return
            job.update(status='pipeline_running'); _write_json(directory/'job.json', job)
            state = read_json(directory/'pipeline.json')
            if job.get('resume_stage', 'images') == 'images':
                self._prepare_images(owner, job_id, state, job)
            else:
                from src.services.avatar_stage_resume import validate_model_inputs
                validate_model_inputs(directory, state)
            cached = all(read_json(directory/'parts'/p['slot']/'generation-artifacts.json').get('generated') for p in state['parts'])
            if cached:
                # Rebuilding completed files never needs credentials or a network client.
                for part in state['parts']:
                    run = directory/'parts'/part['slot']
                    receipt = read_json(run/'generation-artifacts.json')['generated']
                    if digest(run/'generated.glb') != receipt['sha256']:
                        raise PipelineError('model_changed', 'Generated part receipt mismatch')
                    part['model']['status'] = 'ready'
                self.publish(owner, job_id, state)
            else:
                with httpx.Client(base_url=state['meshy_base'], headers={'Authorization': 'Bearer '+os.environ['MESHY_API_KEY']}, timeout=120) as client:
                    for part in state['parts']:
                        run = directory/'parts'/part['slot']
                        artifacts = read_json(run/'generation-artifacts.json')
                        if artifacts.get('generated'):
                            if digest(run/'generated.glb') != artifacts['generated']['sha256']:
                                raise PipelineError('model_changed', '생성된 파츠 파일이 변경되었습니다.')
                            part['model']['status'] = 'ready'
                            continue
                        task = read_json(run/'character.json')
                        if not task:
                            attempts = sum((directory/'parts'/p['slot']/'character.json').is_file()
                                           for p in state['parts'] if p['slot'] not in state.get('reuse', {}).get('slots', []))
                            if attempts >= job['limits']['meshy_tasks']:
                                raise PipelineError('meshy_budget_exhausted', '허용된 Meshy 생성 횟수를 모두 사용했습니다.')
                            _write_json(output/'progress.json', {'stage': 'models', 'message': f'{part["slot"]} 개별 3D 생성 제출 중'})
                            # character_jobs persists the submission intent BEFORE the POST.
                            if state.get('production_spec'):
                                images = [output/part['views'][view]['file'] for view in state['production_spec']['generated_views']]
                                task = character_jobs.generate_multiview_part(run, images, client,
                                    isolated_part=part['slot'] != 'body', height=state['body_height_m'])
                            else:
                                task = character_jobs.generate(run, output/part['image']['file'], state.get('body_height_m', PROFILE['height']), client, isolated_part=part['slot'] != 'body')
                        if not task.get('task_id'):
                            raise PipelineError('task_recovery_required', f'{part["slot"]}: 기존 Meshy 작업 ID 확인이 필요합니다. 재제출하지 않습니다.')
                        part['model'] = {k: task.get(k) for k in ('status', 'task_id', 'progress')}
                        self.publish(owner, job_id, state)
                    deadline = time.monotonic()+deadline_seconds
                    while True:
                        complete = True
                        for part in state['parts']:
                            run = directory/'parts'/part['slot']
                            artifacts = read_json(run/'generation-artifacts.json')
                            if artifacts.get('generated'):
                                if digest(run/'generated.glb') != artifacts['generated']['sha256']:
                                    raise PipelineError('model_changed', '생성된 파츠 파일이 변경되었습니다.')
                                part['model']['status'] = 'ready'; continue
                            task = character_jobs.refresh(run, client)
                            part['model'] = {k: task.get(k) for k in ('status', 'task_id', 'progress')}
                            self.publish(owner, job_id, state)
                            if task['status'] in ('FAILED', 'CANCELED'):
                                raise PipelineError('provider_failed', f'{part["slot"]}: Meshy {task["status"]}. 성공한 다른 파츠는 보존했습니다.')
                            if task['status'] == 'SUCCEEDED':
                                character_jobs.download(run, 'generation'); part['model']['status'] = 'ready'
                            else:
                                complete = False
                        self.publish(owner, job_id, state)
                        _write_json(output/'progress.json', {'stage': 'models', 'message': f'개별 3D 완료 {sum(p["model"]["status"] == "ready" for p in state["parts"])}/{len(state["parts"])}'})
                        if complete: break
                        if time.monotonic() >= deadline:
                            raise PipelineError('poll_paused', '긴 작업의 조회를 일시 중단했습니다. 기존 작업 이어가기로 상태 조회를 재개하세요.')
                        time.sleep(poll_seconds)
            models = []
            for part in state['parts']:
                path = directory/'parts'/part['slot']/'generated.glb'
                models.append({'slot': part['slot'], 'path': str(path), 'sha256': digest(path), 'task_id': part['model']['task_id']})
                if state.get('production_mode') == 'character_parts' or part['slot'] == 'body':
                    name = f'generated-{part["slot"]}.glb'
                    copy_file(path, output/name)
                    job = read_json(directory/'job.json')
                    job.setdefault('files', {})[name] = digest(path)
                    _write_json(directory/'job.json', job)
            if state.get('rig_with_meshy'):
                # Preserve Meshy's native skin and clips. Never rebind this path to a local 23-bone rig.
                job = read_json(directory/'job.json')
                job.update(status='review_required', updated_at=now())
                _write_json(directory/'job.json', job)
                _write_json(output/'progress.json', {'stage': 'rig', 'message': '전신 생성 완료 · Meshy 리깅·동작 가져오는 중'})
                if state.get('production_mode') == 'character_parts':
                    from src.services.avatar_character_flow import continue_character
                    continue_character(self.factory, owner, job_id)
                else:
                    from src.services.avatar_meshy import AvatarMeshy
                    provider = AvatarMeshy(self.factory)
                    provider.start(owner, job_id); provider.execute(owner, job_id)
                return
            _write_json(output/'input.json', {'source': str(directory/'source.png'), 'source_sha256': job['source_sha256'],
                'output': str(output), 'part_models': models, 'rig': str(BACKEND_ROOT/'assets/avatars/rig-maple-v1.json'),
                'motions': str(BACKEND_ROOT/'assets/avatars/manual-v1/body-sd-neutral-v1.glb')})
            job = read_json(directory/'job.json'); job.update(status='accepted'); _write_json(directory/'job.json', job)
            self.factory.execute(owner, job_id)
        except Exception as exc:
            failure_id = uuid.uuid4().hex[:12]
            # No credentials, raw response or internal exception text in public errors.
            LOGGER.error('Avatar production %s failed: job=%s type=%s', failure_id, job_id, type(exc).__name__)
            import traceback
            frames = [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name}
                      for f in traceback.extract_tb(exc.__traceback__)]
            _write_json(directory/'failure.json', {'id': failure_id, 'type': type(exc).__name__, 'frames': frames, 'at': now()})
            # A POST may have persisted its intent before the caller received its result.
            state = read_json(directory/'pipeline.json')
            for p in state.get('parts', []):
                task = read_json(directory/'parts'/p['slot']/'character.json')
                if task:
                    p['model'] = {k: task.get(k) for k in ('status', 'task_id', 'progress')}
            self.publish(owner, job_id, state)
            job = read_json(directory/'job.json')
            message = exc.message if isinstance(exc, PipelineError) else (
                f'Meshy 요청 오류 (HTTP {exc.response.status_code}). 기존 작업을 보존했습니다.' if isinstance(exc, httpx.HTTPStatusError) else
                f'제공자 응답 연결이 끊겼습니다 ({type(exc).__name__}, 진단 {failure_id}). 성공 여부를 확인할 수 없어 자동 재제출하지 않습니다.' if isinstance(exc, httpx.RequestError) else
                f'생산 중단: {type(exc).__name__} · 진단 {failure_id}. 받은 이미지와 기존 작업은 보존했습니다. 새 유료 요청은 자동으로 보내지 않습니다.')
            job.update(status='pipeline_paused', error=message, updated_at=now()); _write_json(directory/'job.json', job)
        finally:
            lock.release()
