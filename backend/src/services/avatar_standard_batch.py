"""One immutable wardrobe order, independent durable jobs, one shared body.

No per-item rig is requested. Measured image alignment and garment fitting stay
visible review stages; a prompt is never treated as proof of geometric fit.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
import time

from src.services import avatar_standard_design as design, avatar_standard_provider as shape
from src.services.asset_editor import _write_json
from src.services.avatar_openai_images import DEFAULT_BASE, DEFAULT_MODEL
from src.services.avatar_standard import LOCK, sha
from src.services.character_pipeline import PipelineError, now, read_json
from src.services.process_identity import identity, state as process_state


class WardrobeBatch:
    def __init__(self, service):
        self.service = service
        self.root = service.root

    def directory(self, owner, item):
        if not re.fullmatch('[a-f0-9]{24}', item):
            raise PipelineError('not_found', '의상 배치를 찾을 수 없습니다.', 404)
        return self.root/str(int(owner))/'batches'/item

    def raw(self, owner, item):
        value = read_json(self.directory(owner, item)/'batch.json')
        if not value:
            raise PipelineError('not_found', '의상 배치를 찾을 수 없습니다.', 404)
        return value

    def public(self, owner, item):
        value = self.raw(owner, item)
        directory = self.directory(owner, item)
        execution = read_json(directory/'execution.json')
        busy = execution.get('status') == 'running' and process_state(execution.get('process')) != 'exited'
        records = self.service.listing(owner)
        by_id = {r['id']: r for r in records}
        rows = []
        for spec in value['contract']['rows']:
            receipt = read_json(directory/'rows'/(spec['key']+'.json'))
            children = {kind: by_id.get(receipt.get(kind+'_id')) for kind in ('design', 'shape', 'part')}
            designed = children['design']
            aligned = next((r for r in records if receipt.get('design_id') and r['kind'] == 'image' and
                            r.get('lineage', {}).get('design_id') == receipt.get('design_id')), None)
            generated = children['shape']
            fitted = children['part'] or next((r for r in records if r['kind'] == 'part' and generated and
                r['contract'].get('shape_id') == generated['id'] and r['contract'].get('slot') == spec['slot'] and
                r['contract'].get('garment_type') == spec['garment_type']), None)
            children['part'] = fitted
            stage = ('part_review' if fitted and fitted['status'] == 'review_required' else
                     'fitting' if fitted and fitted['status'] in ('accepted', 'running') else
                     'fit_required' if generated and generated['status'] == 'model_ready' else
                     'shape' if generated else 'image_ready' if aligned else
                     'image_review' if designed and designed['status'] == 'design_review_required' else 'design')
            child_error = next((c.get('error') for c in reversed(list(children.values())) if c and c.get('error')), None)
            rows.append({**spec, 'stage': stage, 'image_id': aligned['id'] if aligned else None,
                         **children, 'error': receipt.get('error') or child_error})
        ready = sum(r['stage'] == 'part_review' for r in rows)
        reference_url = f'/api/avatar-standard/batches/{item}/reference' if value['contract'].get('reference_asset') else None
        return {'id': item, 'name': value['contract']['name'], 'created_at': value['created_at'],
                'contract': value['contract'], 'spec': value['spec'], 'limits': value['limits'],
                'status': 'running' if busy else 'parts_review_required' if ready == len(rows) else 'attention_required',
                'busy': busy, 'can_resume': not busy, 'ready_count': ready, 'rows': rows,
                'reference_image_url': reference_url, 'error': execution.get('error')}

    def listing(self, owner):
        return [self.public(owner, p.parent.name) for p in sorted((self.root/str(int(owner))/'batches').glob('*/batch.json'), reverse=True)]

    def _verify_reference(self, owner, value, directory):
        asset_id = value['contract'].get('reference_asset')
        if not asset_id:
            return
        receipt = value.get('reference', {})
        source = self.service.asset(owner, asset_id, 'png')
        frozen = directory/'reference.png'
        if (receipt.get('asset_id') != asset_id or receipt.get('file') != 'reference.png' or
                receipt.get('sha256') != asset_id or not frozen.is_file() or
                sha(source) != asset_id or sha(frozen) != asset_id):
            raise PipelineError('reference_changed', '배치에 고정한 원본 참고 이미지가 변경되었습니다.', 409)

    def reference(self, owner, item):
        value = self.raw(owner, item)
        asset_id = value['contract'].get('reference_asset')
        receipt = value.get('reference', {})
        path = self.directory(owner, item)/'reference.png'
        if not asset_id:
            raise PipelineError('not_found', '배치 참고 이미지를 찾을 수 없습니다.', 404)
        if (receipt.get('asset_id') != asset_id or receipt.get('file') != 'reference.png' or
                receipt.get('sha256') != asset_id or not path.is_file() or sha(path) != asset_id):
            raise PipelineError('reference_changed', '배치에 고정한 원본 참고 이미지가 변경되었습니다.', 409)
        return path

    def create(self, owner, key, payload):
        if not re.fullmatch('[a-zA-Z0-9_-]{8,100}', key):
            raise PipelineError('invalid_key', '요청 식별자가 필요합니다.', 422)
        item = hashlib.sha256(f'{owner}:wardrobe-batch:{key}'.encode()).hexdigest()[:24]
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        directory = self.directory(owner, item)
        with LOCK:
            if (directory/'batch.json').exists():
                if self.raw(owner, item)['fingerprint'] != fingerprint:
                    raise PipelineError('idempotency_conflict', '수락한 배치 구성은 변경할 수 없습니다.', 409)
                return self.public(owner, item), False
            base = self.service.base(owner, payload['base_id'], payload['base_sha256'])
            if not os.getenv('OPENAI_API_KEY') or not os.getenv('MESHY_API_KEY'):
                raise PipelineError('provider_not_configured', 'OpenAI와 Meshy 설정이 필요합니다.', 422)
            self.service.artifact(owner, base['id'], 'front.png')
            reference_asset = payload.get('reference_asset')
            reference = self.service.asset(owner, reference_asset, 'png') if reference_asset else None
            config = {'image': {'model': DEFAULT_MODEL, 'base_url': os.getenv('OPENAI_API_BASE', DEFAULT_BASE)},
                      'shape': {'model': 'meshy-7', 'base_url': os.getenv('MESHY_API_BASE', 'https://api.meshy.ai')}}
            value = {'id': item, 'fingerprint': fingerprint, 'created_at': now(), 'contract': payload,
                'providers': config, 'spec': {'base_sha256': base['model_sha256'], 'height_m': base['contract']['height_m'],
                    'bones': base['result']['bones'], 'image': base['result'].get('image_spec'), 'rigging': 'reuse_base_weights'},
                'limits': {'images': len(payload['rows']), 'meshy_generation': len(payload['rows']), 'meshy_rigging': 0,
                           'image_model': DEFAULT_MODEL, 'shape_model': 'meshy-7', 'max_attempts_per_stage': 1}}
            directory.mkdir(parents=True, exist_ok=True)
            (directory/'rows').mkdir(exist_ok=True)
            if reference:
                frozen = directory/'reference.png'
                frozen.write_bytes(reference.read_bytes())
                value['reference'] = {'asset_id': reference_asset, 'file': frozen.name, 'sha256': sha(frozen)}
            _write_json(directory/'batch.json', value)
        return self.public(owner, item), True

    def _row(self, owner, item, spec):
        value = self.raw(owner, item); directory = self.directory(owner, item)
        receipt_path = directory/'rows'/(spec['key']+'.json')
        receipt_path.parent.mkdir(exist_ok=True)
        receipt = read_json(receipt_path)
        prefix = item+'-'+spec['key']
        body = {k: value['contract'][k] for k in ('base_id', 'base_sha256')}
        try:
            designed, _ = design.create(self.service, owner, prefix+'-design', {**body, 'name': spec['name'],
                'object_key': spec['key'], 'view': 'front', 'description': spec['description']+
                f' Single {spec["garment_type"]}, wardrobe slot {spec["slot"]}.',
                'reference_asset': value['contract'].get('reference_asset'),
                'identity_image_id': None, 'max_new_images': 1}, provider_config=value['providers']['image'])
            receipt.update(design_id=designed['id'], error=None); _write_json(receipt_path, receipt)
            if designed['status'] != 'design_review_required':
                design.execute(self.service, owner, designed['id'])
            state = next(r for r in self.public(owner, item)['rows'] if r['key'] == spec['key'])
            if not state['image_id']:
                return
            # Freeze the first accepted alignment; later image reviews cannot mutate
            # or duplicate an already submitted shape task.
            image_id = receipt.get('image_id', state['image_id'])
            generated, _ = shape.create(self.service, owner, prefix+'-shape', {**body,
                'name': spec['name'], 'image_ids': [image_id], 'max_new_tasks': 1}, provider_config=value['providers']['shape'])
            receipt.update(image_id=image_id, shape_id=generated['id']); _write_json(receipt_path, receipt)
            if generated['status'] == 'accepted':
                generated = shape.execute(self.service, owner, generated['id'])
            deadline = time.monotonic()+1200
            while generated['status'] not in ('model_ready', 'failed') and time.monotonic() < deadline:
                task = read_json(self.service.directory(owner, generated['id'])/'meshy/character.json')
                if not task.get('task_id'):
                    return
                generated = shape.execute(self.service, owner, generated['id'], poll=True)
                if generated['status'] not in ('provider_running',):
                    return
                time.sleep(10)
        except Exception as exc:
            # Individual jobs retain detailed diagnostics. A single failed row must
            # not cancel independent items or create replacement provider attempts.
            receipt['error'] = exc.message if isinstance(exc, PipelineError) else '이 항목의 기존 작업 기록을 확인해 주세요. 새 요청은 자동 재제출하지 않습니다.'
            _write_json(receipt_path, receipt)

    def execute(self, owner, item):
        directory = self.directory(owner, item)
        lock = shape.run_lock(('batch', owner, item))
        if not lock.acquire(blocking=False):
            return
        try:
            with shape.provider_lease(directory/'worker'):
                value = self.raw(owner, item)
                self.service.base(owner, value['contract']['base_id'], value['contract']['base_sha256'])
                self._verify_reference(owner, value, directory)
                _write_json(directory/'execution.json', {'status': 'running', 'process': identity(), 'started_at': now()})
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(self._row, owner, item, row) for row in value['contract']['rows']]
                    for future in futures:
                        future.result()
                _write_json(directory/'execution.json', {'status': 'idle', 'finished_at': now()})
        except Exception as exc:
            if isinstance(exc, PipelineError) and exc.code == 'worker_active':
                return
            _write_json(directory/'execution.json', {'status': 'paused', 'error': '기준 몸 또는 배치 실행 기록을 확인해 주세요.'})
        finally:
            lock.release()
