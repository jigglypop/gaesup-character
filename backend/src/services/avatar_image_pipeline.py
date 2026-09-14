"""Durable image -> individual Meshy parts -> one local canonical skeleton.

One persisted attempt per paid stage. Resume only polls known task IDs or starts
stages never attempted within the original request's fixed limits.
"""
import base64
import hashlib
import io
import json
import os
import re
import shutil
import uuid
from threading import Lock
import time

import httpx
from PIL import Image

from src.paths import BACKEND_ROOT
from src.services import character_jobs
from src.services.asset_editor import _write_json
from src.services.avatar_blueprints import AvatarBlueprints, SLOTS
from src.services.avatar_factory import IMAGE_PROFILE as PROFILE, _LOCK, digest
from src.services.character_parts import blender_executable
from src.services.character_pipeline import PipelineError, now, read_json
from src.services.process_identity import identity, state as process_state

PARTS = SLOTS[1:]
_RUN_LOCKS = {}
DESCRIPTIONS = {
    'face': 'ONE closed bald oversized chibi head with the original low-set large eyes and small mouth; the mesh ends at the chin; absolutely no neck, shoulders, bust, pedestal, hair, hat or clothing',
    'hairBack': 'back hair shell with completed hidden crown and nape; no face, head, bangs or clothing',
    'hairFront': 'front hair and bangs as a shell with an open face area; no face, head, hat or clothing',
    'hat': 'hat alone with complete hidden rim and underside; no head or hair',
    'top': 'top alone with complete collar, sleeves, cuffs and waistband; no hands, head, legs or skirt',
    'bottom': 'bottom alone with complete hidden waistband and opaque inner lining; no torso, legs or shoes',
    'shoes': 'matching pair of shoes with complete openings and hidden ankle overlap; no legs or body',
}


def capabilities():
    image = bool(os.getenv('GEMINI_API_KEY'))
    meshy = bool(os.getenv('MESHY_API_KEY'))
    blender = bool(blender_executable())
    return {'image_configured': image, 'meshy_configured': meshy, 'blender_available': blender,
            'image_model': os.getenv('GEMINI_IMAGE_MODEL', 'gemini-3.1-flash-image-preview'),
            'meshy_model': 'meshy-7', 'slots': PARTS, 'ready': image and meshy and blender,
            'next_actions': [{'id': 'produce_images', 'enabled': image and meshy and blender,
                              'reason': None if image and meshy and blender else '서버의 Gemini·Meshy 키와 Blender 설치를 확인해 주세요.'},
                             {'id': 'produce_prepared', 'enabled': meshy and blender,
                              'reason': None if meshy and blender else '서버의 Meshy 키와 Blender 설치를 확인해 주세요.'}]}


def generate_part_image(source, prompt, model, base):
    """Exactly one POST; deliberately no model fallback or automatic retry."""
    with Image.open(source) as image:
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

    def create(self, owner, key, payload):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}', key):
            raise PipelineError('invalid_key', '생산 요청 식별자가 필요합니다.', 422)
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
                part = {'slot': slot, 'image': {'status': 'pending'}, 'model': {'status': 'pending'}}
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
            _write_json(directory/'pipeline.json', {'parts': parts, 'blueprint': blueprint,
                'image_model': capabilities()['image_model'], 'image_base': os.getenv('GEMINI_API_BASE', 'https://generativelanguage.googleapis.com/v1beta').rstrip('/'),
                'meshy_base': os.getenv('MESHY_API_BASE_URL', 'https://api.meshy.ai').rstrip('/')})
            _write_json(directory/'job.json', {'id': job_id, 'fingerprint': fingerprint, 'executor': self.factory.instance,
                'executor_process': identity(), 'character_id': character['id'], 'character_name': character['name'],
                'input_kind': 'image', 'source_sha256': source_hash, 'profile': PROFILE,
                'status': 'pipeline_queued', 'created_at': now(), 'updated_at': now(), 'error': None,
                'limits': {'image_tasks': len(slots) if payload['image_mode'] == 'generate' else 0, 'meshy_tasks': len(slots)},
                'review': {'decision': 'pending'}, 'files': {p['image']['file']: p['image']['sha256'] for p in parts if p['image']['status'] == 'succeeded'}})
            self.publish(owner, job_id, read_json(directory/'pipeline.json'))
            return self.factory.get(owner, job_id), True

    def publish(self, owner, job_id, state):
        directory = self.factory.directory(owner, job_id)
        _write_json(directory/'pipeline.json', state)
        job = read_json(directory/'job.json')
        job['parts'] = [{'slot': p['slot'], 'image_status': p['image']['status'], 'image_asset': p['image'].get('asset'),
                         'model_status': p['model']['status'], 'task_id': p['model'].get('task_id'),
                         'progress': p['model'].get('progress', 0)} for p in state['parts']]
        for p in state['parts']:
            if p['image'].get('file'):
                job.setdefault('files', {})[p['image']['file']] = p['image']['sha256']
        job['updated_at'] = now(); _write_json(directory/'job.json', job)

    def resume(self, owner, job_id):
        self.factory.get(owner, job_id)
        directory = self.factory.directory(owner, job_id)
        with _LOCK:
            job = read_json(directory/'job.json')
            if job.get('input_kind') != 'image' or job['status'] not in ('pipeline_paused', 'failed', 'recovery_required'):
                raise PipelineError('invalid_state', '현재 재개할 수 없는 작업입니다.')
            runner = read_json(directory/'output/runner.json')
            if job['status'] in ('failed', 'recovery_required') and runner and process_state(runner.get('process')) != 'exited':
                raise PipelineError('worker_running', '이전 Blender 프로세스가 종료되었는지 확인이 필요합니다.')
            state = read_json(directory/'pipeline.json')
            for part in state['parts']:
                if part['image']['status'] in ('submitting', 'rejected', 'failed'):
                    raise PipelineError('image_attempt_recorded', '이미 시도한 이미지 요청입니다. 새 생산 버전에서만 다시 요청할 수 있습니다.')
                task = read_json(directory/'parts'/part['slot']/'character.json')
                if task and not task.get('task_id'):
                    raise PipelineError('task_recovery_required', 'Meshy 작업 ID 확인이 필요합니다. 불확실한 요청은 재제출하지 않습니다.')
                if task.get('status') in ('FAILED', 'CANCELED'):
                    raise PipelineError('provider_failed', '실패한 Meshy 작업은 새 생산 버전에서만 다시 요청할 수 있습니다.')
            if job['status'] in ('failed', 'recovery_required') and (directory/'output/input.json').is_file():
                # Keep failed work files and their exact input/seal before rebuilding locally.
                attempt = uuid.uuid4().hex
                archive = directory/'attempts'/attempt
                shutil.copytree(directory/'output', archive/'output')
                _write_json(archive/'job.json', job)
                job.setdefault('previous_attempts', []).append({'id': attempt, 'status': job['status'], 'archived_at': now()})
            job.update(status='pipeline_queued', executor=self.factory.instance, executor_process=identity(), error=None, profile=PROFILE)
            _write_json(directory/'job.json', job)
        return self.factory.get(owner, job_id)

    def rebuild(self, owner, job_id):
        """Create a new local assembly version from completed provider outputs."""
        self.factory.get(owner, job_id)
        with _LOCK:
            source = self.factory.directory(owner, job_id)
            original = read_json(source/'job.json'); state = read_json(source/'pipeline.json')
            if original.get('input_kind') != 'image' or original['status'] not in ('review_required', 'failed', 'recovery_required'):
                raise PipelineError('invalid_state', '생성이 끝난 이미지 작업만 기존 파츠로 재조립할 수 있습니다.')
            if not state.get('parts') or any(p['model']['status'] != 'ready' or p['image']['status'] != 'succeeded' for p in state['parts']):
                raise PipelineError('parts_not_ready', '모든 파츠 생성이 끝나야 유료 요청 없이 재조립할 수 있습니다.')
            runner = read_json(source/'output/runner.json')
            if runner and process_state(runner.get('process')) != 'exited':
                raise PipelineError('worker_running', '이전 Blender 프로세스가 아직 종료되지 않았습니다.')
            new_id = uuid.uuid4().hex[:24]; target = self.factory.directory(owner, new_id)
            (target/'output').mkdir(parents=True)
            shutil.copy2(source/'source.png', target/'source.png')
            shutil.copytree(source/'parts', target/'parts')
            files = {}
            for part in state['parts']:
                name = part['image']['file']
                if Path(name).name != name or digest(source/'output'/name) != part['image']['sha256']:
                    raise PipelineError('source_changed', '기존 파츠 이미지 영수증이 일치하지 않습니다.')
                shutil.copy2(source/'output'/name, target/'output'/name); files[name] = part['image']['sha256']
            _write_json(target/'pipeline.json', state)
            job = {k: original[k] for k in ('character_id', 'character_name', 'input_kind', 'source_sha256')}
            job.update(id=new_id, fingerprint=f'local-rebuild:{job_id}:{new_id}', source_job_id=job_id,
                executor=self.factory.instance, executor_process=identity(), profile=PROFILE,
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
            if digest(directory/'source.png') != job['source_sha256']:
                raise PipelineError('source_changed', '보존한 원본 이미지가 변경되었습니다.')
            for part in state['parts']:
                if part['image']['status'] == 'succeeded':
                    if digest(output/part['image']['file']) != part['image']['sha256']:
                        raise PipelineError('image_changed', '보존한 파츠 이미지가 변경되었습니다.')
                    continue
                if part['image']['status'] != 'pending':
                    raise PipelineError('image_attempt_recorded', '이미지 요청의 응답을 확인할 수 없습니다. 자동 재제출하지 않습니다.')
                prompt = ('Extract and complete ONE modular 3D modeling reference from the supplied character: '+DESCRIPTIONS[part['slot']]+'. '
                    'Preserve its colors, identity, original silhouette and very large head with tiny limbs. Never normalize to adult or 2.5-head proportions. Front orthographic view. '
                    'Complete hidden connection areas with generous overlap. Center only this isolated part, fully visible, on a plain white background. '
                    'No cast shadows, checkerboard, text, other body parts or full character. This is a new completed design, not a crop.')
                part['image'] = {'status': 'submitting', 'prompt': prompt, 'attempted_at': now()}
                self.publish(owner, job_id, state)
                _write_json(output/'progress.json', {'stage': 'images', 'message': f'{part["slot"]} 이미지 분리·숨겨진 형태 보완 중'})
                try:
                    raw = generate_part_image(directory/'source.png', prompt, state['image_model'], state['image_base'])
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (400, 401, 403, 404, 422, 429):
                        part['image']['status'] = 'rejected'; self.publish(owner, job_id, state)
                    raise PipelineError('image_provider_error', f'이미지 생성 {part["slot"]}: HTTP {exc.response.status_code}. 모델·키·할당량을 확인해 주세요. 자동 재요청하지 않습니다.') from None
                name = f'{part["slot"]}-image.png'; (output/name).write_bytes(raw)
                asset = self.blueprints.upload(owner, raw)
                part['image'].update(status='succeeded', file=name, sha256=digest(output/name), asset=asset['id'])
                self.publish(owner, job_id, state)
            with httpx.Client(base_url=state['meshy_base'], headers={'Authorization': 'Bearer '+os.environ['MESHY_API_KEY']}, timeout=120) as client:
                for part in state['parts']:
                    run = directory/'parts'/part['slot']
                    task = read_json(run/'character.json')
                    if not task:
                        _write_json(output/'progress.json', {'stage': 'models', 'message': f'{part["slot"]} 개별 3D 생성 제출 중'})
                        # character_jobs persists the submission intent BEFORE the POST.
                        task = character_jobs.generate(run, output/part['image']['file'], PROFILE['height'], client, isolated_part=True)
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
            _write_json(output/'input.json', {'source': str(directory/'source.png'), 'source_sha256': job['source_sha256'],
                'output': str(output), 'part_models': models, 'rig': str(BACKEND_ROOT/'assets/avatars/rig-maple-v1.json'),
                'motions': str(BACKEND_ROOT/'assets/avatars/manual-v1/body-sd-neutral-v1.glb')})
            job = read_json(directory/'job.json'); job.update(status='accepted'); _write_json(directory/'job.json', job)
            self.factory.execute(owner, job_id)
        except Exception as exc:
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
                '제공자 연결 또는 산출물 처리 중 중단되었습니다. 기존 작업은 보존되며 불확실한 요청은 다시 보내지 않습니다.')
            job.update(status='pipeline_paused', error=message, updated_at=now()); _write_json(directory/'job.json', job)
        finally:
            lock.release()
