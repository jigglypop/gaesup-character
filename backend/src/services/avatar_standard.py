"""Local canonical-body workflow. No provider calls and no schema migrations."""
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import subprocess
from threading import RLock, Semaphore

from PIL import Image

from src.services.asset_delivery import inspect_glb
from src.services.asset_editor import _write_json
from src.services.character_parts import blender_executable
from src.services.character_pipeline import CharacterPipeline, PipelineError, now, read_json
from src.services.glb import parse_glb
from src.services.process_identity import identity, state as process_state
from src.services.avatar_standard_models import image_spec

LOCK = RLock()
QUEUE = Semaphore(1)
LOG = logging.getLogger(__name__)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AvatarStandard:
    def __init__(self, root):
        self.root = Path(root).resolve()/'avatar-standard'
        self.characters = CharacterPipeline(root)

    def directory(self, owner, item):
        if not re.fullmatch('[a-f0-9]{24}', item):
            raise PipelineError('not_found', '규격 버전을 찾을 수 없습니다.', 404)
        return self.root/str(int(owner))/item

    def raw(self, owner, item):
        value = read_json(self.directory(owner, item)/'record.json')
        if not value:
            raise PipelineError('not_found', '규격 버전을 찾을 수 없습니다.', 404)
        return value

    def public(self, owner, item):
        value = self.raw(owner, item)
        result = {k: v for k, v in value.items() if k not in ('fingerprint', 'process')}
        result['artifacts'] = [{'name': name, 'url': f'/api/avatar-standard/items/{item}/artifacts/{name}', 'sha256': digest}
                               for name, digest in value.get('files', {}).items()]
        result['next_actions'] = []
        if value['kind'] == 'design':
            settings = read_json(self.directory(owner, item)/'design.json')
            if value['status'] != 'design_review_required' and (settings.get('attempt') in ('not_started', 'received') or
                    (settings.get('attempt') == 'submitting' and ((self.directory(owner, item)/'image.response.json').is_file() or process_state(settings.get('executor')) == 'exited'))):
                result['next_actions'].append('resume_design')
            return result
        if value['kind'] == 'shape':
            task = read_json(self.directory(owner, item)/'meshy/character.json')
            if task and value['status'] != 'model_ready':
                result['provider'] = {**value['provider'], **{k: task.get(k) for k in ('task_id', 'status', 'progress')}}
                if task.get('status') == 'submission_rejected':
                    result['status'] = 'failed'
                elif value['status'] != 'failed':
                    result['next_actions'].append('poll' if task.get('task_id') else 'recover_task')
            elif value['status'] == 'accepted':
                result['next_actions'].append('resume_submission')
            return result
        if value['kind'] == 'base' and value['status'] == 'review_required':
            result['next_actions'].append('review')
        if value['status'] in ('accepted', 'running') and process_state(value.get('process', {})) != 'running':
            result['next_actions'].append('recover')
        return result

    def listing(self, owner):
        directory = self.root/str(int(owner))
        return [self.public(owner, p.parent.name) for p in sorted(directory.glob('*/record.json'), reverse=True)]

    def asset(self, owner, asset_id, suffix):
        if not re.fullmatch('[a-f0-9]{64}', asset_id):
            raise PipelineError('invalid_asset', '업로드한 파일 ID가 필요합니다.', 422)
        path = self.root/str(int(owner))/'uploads'/f'{asset_id}.{suffix}'
        if not path.is_file() or sha(path) != asset_id:
            raise PipelineError('asset_changed', '업로드 파일이 없거나 변경되었습니다.', 409)
        return path

    def upload(self, owner, content, kind):
        if not content or len(content) > 25*1024*1024:
            raise PipelineError('invalid_upload', '파일은 25MB 이하로 준비해 주세요.', 413)
        try:
            if kind == 'glb':
                doc, _ = parse_glb(content, strict=True)
                if any('uri' in image and not image['uri'].startswith('data:') for image in doc.get('images', [])) or any('uri' in b for b in doc.get('buffers', [])):
                    raise ValueError('External resources')
                result = inspect_glb(content)
                if result['errors']:
                    raise ValueError('Invalid geometry')
            else:
                with Image.open(io.BytesIO(content)) as image:
                    if image.format != 'PNG' or max(image.size) > 4096:
                        raise ValueError('Expected PNG at most 4096px')
                    image.verify()
        except Exception as exc:
            raise PipelineError('invalid_asset', '자체 포함 GLB 또는 4096px 이하 PNG를 확인해 주세요.', 422) from exc
        asset_id = hashlib.sha256(content).hexdigest()
        path = self.root/str(int(owner))/'uploads'/f'{asset_id}.{kind}'
        with LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(content)
        return {'id': asset_id, 'kind': kind}

    def artifact(self, owner, item, name):
        value = self.raw(owner, item)
        if Path(name).name != name or name not in value.get('files', {}):
            raise PipelineError('not_found', '산출물을 찾을 수 없습니다.', 404)
        path = self.directory(owner, item)/name
        if not path.is_file() or sha(path) != value['files'][name]:
            raise PipelineError('artifact_changed', '산출물 해시가 변경되었습니다.', 409)
        return path

    def base(self, owner, item, expected):
        base = self.raw(owner, item)
        if base['kind'] != 'base' or base['status'] != 'approved' or base.get('model_sha256') != expected:
            raise PipelineError('base_not_approved', '검수 승인한 동일 버전의 기준 몸이 필요합니다.', 409)
        self.artifact(owner, item, 'model.glb')
        return base

    def create(self, owner, kind, key, payload):
        if not re.fullmatch('[a-zA-Z0-9_-]{8,100}', key):
            raise PipelineError('invalid_key', '요청 식별자가 필요합니다.', 422)
        item = hashlib.sha256(f'{owner}:{kind}:{key}'.encode()).hexdigest()[:24]
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        directory = self.directory(owner, item)
        with LOCK:
            if (directory/'record.json').exists():
                if self.raw(owner, item)['fingerprint'] != fingerprint:
                    raise PipelineError('idempotency_conflict', '같은 요청의 입력이 변경되었습니다.', 409)
                return self.public(owner, item), False
            inputs = {'kind': kind, 'output': str(directory), 'contract': payload}
            if kind == 'base':
                if payload.get('factory_job_id'):
                    from src.services.avatar_factory import AvatarFactory
                    from src.services.avatar_meshy import AvatarMeshy
                    meshy = AvatarMeshy(AvatarFactory(self.root.parent))
                    source = meshy.artifact(owner, payload['factory_job_id'], payload['factory_version'], 'model.glb')
                    inputs['provenance'] = {'factory_job_id': payload['factory_job_id'], 'factory_version': payload['factory_version'], 'rig_origin': 'meshy'}
                else:
                    character = self.characters.detail(payload['character_id'], owner)
                    if not character['model_id'] or character['model_sha256'] != payload['source_sha256']:
                        raise PipelineError('source_changed', '선택한 몸의 원본 버전을 다시 확인해 주세요.', 409)
                    source = self.characters.artifact(character['id'], owner, character['model_id'])
                    inputs['provenance'] = {'character_id': character['id'], 'model_id': character['model_id'],
                                            'rig_origin': character['rig_origin'], 'provider': character['provider']}
                if sha(source) != payload['source_sha256']:
                    raise PipelineError('source_changed', '원본 해시가 변경되었습니다.', 409)
                content = source.read_bytes()
                # Apply the same self-contained resource gate as part uploads.
                self.upload(owner, content, 'glb')
                inputs['source_sha256'] = payload['source_sha256']
            else:
                base = self.base(owner, payload['base_id'], payload['base_sha256'])
                inputs['base'] = str(self.artifact(owner, base['id'], 'model.glb'))
                inputs['base_metadata'] = base['result']
                if kind == 'part':
                    source = self.asset(owner, payload['model_asset'], 'glb')
                    content = source.read_bytes()
                    inputs['source_sha256'] = payload['model_asset']
                    if payload.get('shape_id'):
                        shape = self.raw(owner, payload['shape_id'])
                        if (shape['kind'] != 'shape' or shape['status'] != 'model_ready' or shape['result']['model_asset'] != payload['model_asset'] or
                                shape['contract']['base_id'] != base['id'] or shape['contract']['base_sha256'] != payload['base_sha256']):
                            raise PipelineError('shape_mismatch', '같은 기준 몸으로 생성한 Meshy 파츠가 필요합니다.', 422)
                        inputs['provider_task_id'] = shape['provider']['task_id']
                    if payload['binding'] == 'rigid' and payload['bone'] not in base['result']['bones']:
                        raise PipelineError('invalid_bone', '기준 몸에 없는 연결 본입니다.', 422)
                    views, objects = [], set()
                    for image_id in payload['image_ids']:
                        image = self.raw(owner, image_id)
                        if image['kind'] != 'image' or image['contract']['base_id'] != base['id'] or image['contract']['base_sha256'] != payload['base_sha256']:
                            raise PipelineError('image_mismatch', '같은 기준 몸의 파츠 시안이 필요합니다.', 422)
                        views.append(image['contract']['view']); objects.add(image['contract']['object_key'])
                        self.artifact(owner, image_id, 'canvas.png')
                    if views and (views[0] != 'front' or len(views) != len(set(views)) or len(objects) != 1):
                        raise PipelineError('image_mismatch', '정면 우선, 동일 물체의 서로 다른 시점만 묶을 수 있습니다.', 422)
                elif kind == 'assembly':
                    slots = set(); inputs['parts'] = []
                    inputs['textures'] = []
                    material_indices = set()
                    for swap in payload.get('textures', []):
                        index = swap['material_index']
                        part_id = swap.get('part_id')
                        if part_id and part_id not in payload['part_ids']:
                            raise PipelineError('invalid_texture_part', '조합에 선택한 파츠만 색상·무늬를 바꿀 수 있습니다.', 422)
                        model = self.artifact(owner, part_id, 'part.glb') if part_id else Path(inputs['base'])
                        material_doc, _ = parse_glb(model.read_bytes(), strict=True)
                        primitives = [p for m in material_doc['meshes'] for p in m['primitives'] if p.get('material') == index]
                        address = (part_id, index)
                        if (address in material_indices or index >= len(material_doc.get('materials', [])) or not primitives or
                                any('TEXCOORD_0' not in p['attributes'] for p in primitives)):
                            raise PipelineError('invalid_uv_material', '중복되지 않은 UV가 있는 기준 몸 재질을 선택하세요.', 422)
                        material_indices.add(address)
                        path = self.asset(owner, swap['image_asset'], 'png')
                        inputs['textures'].append({**swap, 'path': str(path)})
                    for part_id in payload['part_ids']:
                        part = self.raw(owner, part_id)
                        if (part['kind'] != 'part' or part['status'] != 'review_required' or
                                part['contract']['base_sha256'] != payload['base_sha256'] or part['contract']['base_id'] != base['id']):
                            raise PipelineError('incompatible_part', '같은 기준 몸으로 제작한 파츠가 필요합니다.', 422)
                        slot = part['contract']['slot']
                        if slot in slots:
                            raise PipelineError('slot_conflict', '한 슬롯에 파츠 하나만 선택할 수 있습니다.', 422)
                        slots.add(slot)
                        path = self.artifact(owner, part_id, 'part.glb')
                        inputs['parts'].append({'id': part_id, 'slot': slot, 'path': str(path), 'sha256': sha(path)})
                else:
                    raise PipelineError('invalid_kind', '지원하지 않는 작업입니다.', 422)
            if not blender_executable():
                raise PipelineError('blender_unavailable', '로컬 Blender 설치를 확인해 주세요.', 422)
            directory.mkdir(parents=True, exist_ok=True)
            if kind in ('base', 'part'):
                (directory/'source.glb').write_bytes(content)
                inputs['source'] = str(directory/'source.glb')
            _write_json(directory/'input.json', inputs)
            record = {'id': item, 'kind': kind, 'name': payload['name'], 'contract': payload,
                      'fingerprint': fingerprint, 'created_at': now(), 'status': 'accepted', 'files': {},
                      'process': identity(), 'review': {'decision': 'pending'}, 'error': None}
            _write_json(directory/'record.json', record)
            return self.public(owner, item), True

    def finalize(self, owner, item):
        directory = self.directory(owner, item)
        record = self.raw(owner, item)
        seal = read_json(directory/'complete.json')
        if seal.get('input_sha256') != sha(directory/'input.json'):
            raise ValueError('Worker input receipt mismatch')
        required = {'model.glb', 'master.blend', 'front.png', 'side.png', 'back.png', 'motion.png'}
        if record['kind'] == 'part':
            required.add('part.glb')
        if not required.issubset(seal.get('files', {})):
            raise ValueError('Worker evidence missing')
        for name, expected in seal['files'].items():
            if Path(name).name != name or sha(directory/name) != expected:
                raise ValueError('Worker artifact receipt mismatch')
        inputs = read_json(directory/'input.json')
        if inputs.get('source') and sha(Path(inputs['source'])) != inputs['source_sha256']:
            raise ValueError('Original source changed')
        if inputs.get('base') and sha(Path(inputs['base'])) != record['contract']['base_sha256']:
            raise ValueError('Canonical base changed')
        for part in inputs.get('parts', []):
            if sha(Path(part['path'])) != part['sha256']:
                raise ValueError('Assembly part changed')
        result = seal['result']
        if not result['technical_passed']:
            raise ValueError('Technical checks failed')
        inspection = inspect_glb((directory/'model.glb').read_bytes())
        if inspection['errors'] or not inspection['metrics']['skins']:
            raise ValueError('Invalid compiled model')
        for view in ('front', 'side', 'back', 'motion'):
            with Image.open(directory/f'{view}.png') as image:
                size = 2048 if record['kind'] == 'base' and view != 'motion' else 640
                if image.size != (size, size) or image.mode != 'RGBA' or image.getchannel('A').getbbox() is None:
                    raise ValueError('Missing or invalid review render')
        record.update(status='review_required', files=seal['files'], result=result,
                      model_sha256=seal['files']['model.glb'], error=None)
        _write_json(directory/'record.json', record)

    def execute(self, owner, item):
        directory = self.directory(owner, item)
        with QUEUE:
            with LOCK:
                record = self.raw(owner, item)
                if record['status'] != 'accepted':
                    return
                record.update(status='running', process=identity())
                _write_json(directory/'record.json', record)
            try:
                command = [blender_executable(), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
                           '--python', str(Path(__file__).with_name('avatar_standard_blender.py')), '--', str(directory/'input.json')]
                with (directory/'worker.log').open('wb') as log:
                    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    _write_json(directory/'runner.json', {'process': identity(process.pid)})
                    try:
                        code = process.wait(timeout=600)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
                        raise ValueError('Worker timeout')
                if code:
                    raise ValueError('Worker failed')
                self.finalize(owner, item)
            except Exception:
                LOG.exception('Canonical workflow failed: %s', item)
                record.update(status='failed', error='몸·착용 기준점·가중치 또는 Blender 출력을 확인해 주세요. 원본은 보존했습니다.')
                _write_json(directory/'record.json', record)

    def recover(self, owner, item):
        with LOCK:
            record = self.raw(owner, item); directory = self.directory(owner, item)
            if record['status'] not in ('running', 'accepted'):
                return self.public(owner, item)
            runner = read_json(directory/'runner.json')
            if process_state(record.get('process', {})) != 'exited' or (runner and process_state(runner.get('process', {})) != 'exited'):
                raise PipelineError('worker_active', '실행 프로세스가 종료되었는지 확인할 수 없습니다.', 409)
            try:
                self.finalize(owner, item)
            except Exception:
                record.update(status='failed', error='중단된 작업의 완료 증거가 없습니다. 자동 재실행하지 않았습니다.')
                _write_json(directory/'record.json', record)
            return self.public(owner, item)

    def review(self, owner, item, payload):
        with LOCK:
            record = self.raw(owner, item)
            if record['kind'] != 'base' or record['status'] not in ('review_required', 'approved') or payload['model_sha256'] != record.get('model_sha256'):
                raise PipelineError('review_conflict', '검토한 기준 몸 버전을 다시 확인해 주세요.', 409)
            self.artifact(owner, item, 'model.glb')
            for filename in record['files']:
                self.artifact(owner, item, filename)
            if payload['decision'] == 'approved' and not all(payload[k] for k in ('bald_complete_body', 'neutral_apose', 'motion_checked')):
                raise PipelineError('review_incomplete', '완전한 몸·중립 A-pose·동작 검수가 모두 필요합니다.', 422)
            record['review'] = {**payload, 'reviewed_at': now(), 'evidence': dict(record['files'])}
            record['status'] = 'approved' if payload['decision'] == 'approved' else 'review_required'
            _write_json(self.directory(owner, item)/'record.json', record)
            return self.public(owner, item)

    def image(self, owner, payload):
        with LOCK:
            base = self.base(owner, payload['base_id'], payload['base_sha256'])
            source = self.asset(owner, payload['image_asset'], 'png')
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            item = fingerprint[:24]; directory = self.directory(owner, item)
            if (directory/'record.json').exists():
                return self.public(owner, item)
            with Image.open(source) as image:
                if image.size != (2048, 2048):
                    raise PipelineError('canvas_mismatch', '시안은 기준 몸과 동일한 2048 × 2048px 캔버스여야 합니다.', 422)
                x, y, w, h = payload['crop']; size = payload['export_size']
                scale = size/max(w, h)
                crop = image.convert('RGBA').crop((x, y, x+w, y+h))
                crop = crop.resize((max(1, round(w*scale)), max(1, round(h*scale))), Image.Resampling.LANCZOS)
                export = Image.new('RGBA', (size, size), (255, 255, 255, 0))
                offset = ((size-crop.width)//2, (size-crop.height)//2)
                export.paste(crop, offset)
                directory.mkdir(parents=True, exist_ok=False)
                (directory/'canvas.png').write_bytes(source.read_bytes()); export.save(directory/'provider.png')
            record = {'id': item, 'kind': 'image', 'name': payload['object_key']+' '+payload['view'],
                      'contract': payload, 'status': 'prepared', 'created_at': now(),
                      'result': {'image_spec': image_spec(base['contract']['height_m']),
                                 'crop_scale': scale, 'export_offset_px': offset,
                                 'scaled_crop_size_px': [crop.width, crop.height],
                                 'target_crop_size_m': [w*base['contract']['height_m']/1500, h*base['contract']['height_m']/1500],
                                 'landmark_review': 'required', 'same_object_review': 'required'},
                      'files': {name: sha(directory/name) for name in ('canvas.png', 'provider.png')}}
            _write_json(directory/'record.json', record)
            return self.public(owner, item)
