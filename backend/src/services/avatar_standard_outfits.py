"""Owner-scoped, instant wardrobe selections for canonical avatars."""

import hashlib
import json
import re

from src.services.asset_editor import _write_json
from src.services.avatar_standard import LOCK
from src.services.character_pipeline import PipelineError, now, read_json


class AvatarStandardOutfits:
    def __init__(self, standard):
        self.standard = standard

    def _path(self, owner, base_id):
        if not re.fullmatch(r'[a-f0-9]{24}', base_id):
            raise PipelineError('not_found', '기준 몸을 찾을 수 없습니다.', 404)
        return self.standard.root / str(int(owner)) / 'wardrobes' / base_id / 'selection.json'

    @staticmethod
    def _fingerprint(payload):
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    @staticmethod
    def _key_id(key):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}', key):
            raise PipelineError('invalid_key', '요청 식별자가 필요합니다.', 422)
        return hashlib.sha256(key.encode()).hexdigest()

    def get(self, owner, base_id):
        with LOCK:
            base = self.standard.raw(owner, base_id)
            base_sha256 = base.get('model_sha256')
            if not isinstance(base_sha256, str) or not re.fullmatch(r'[a-f0-9]{64}', base_sha256):
                raise PipelineError('base_not_approved', '검수 승인한 동일 버전의 기준 몸이 필요합니다.', 409)
            self.standard.base(owner, base_id, base_sha256)
            state = read_json(self._path(owner, base_id))
            if not state:
                return {'base_id': base_id, 'base_sha256': base_sha256, 'revision': '0', 'part_ids': []}
            current = state.get('current')
            if not isinstance(current, dict) or current.get('base_id') != base_id or current.get('base_sha256') != base_sha256:
                raise PipelineError('wardrobe_conflict', '저장한 옷장의 기준 몸 버전을 다시 확인해 주세요.', 409)
            return dict(current)

    def put(self, owner, base_id, payload, expected_revision, key):
        key_id = self._key_id(key)
        fingerprint = self._fingerprint(payload)
        path = self._path(owner, base_id)
        with LOCK:
            state = read_json(path) or {'version': 1, 'receipts': {}}
            receipts = state.setdefault('receipts', {})
            receipt = receipts.get(key_id)
            if receipt:
                if receipt.get('fingerprint') != fingerprint:
                    raise PipelineError('idempotency_conflict', '같은 요청의 입력이 변경되었습니다.', 409)
                return dict(receipt['result'])

            base = self.standard.base(owner, base_id, payload['base_sha256'])
            current = state.get('current') or {
                'base_id': base_id,
                'base_sha256': base['model_sha256'],
                'revision': '0',
                'part_ids': [],
            }
            if current.get('base_id') != base_id or current.get('base_sha256') != base['model_sha256']:
                raise PipelineError('wardrobe_conflict', '저장한 옷장의 기준 몸 버전을 다시 확인해 주세요.', 409)
            if expected_revision != current.get('revision'):
                raise PipelineError('revision_conflict', '옷장이 변경되었습니다. 최신 선택을 다시 불러와 주세요.', 409)

            slots = set()
            part_ids = payload['part_ids']
            if len(set(part_ids)) != len(part_ids):
                raise PipelineError('duplicate_part', '같은 파츠를 중복 선택할 수 없습니다.', 422)
            for part_id in part_ids:
                part = self.standard.raw(owner, part_id)
                contract = part.get('contract', {})
                if (part.get('kind') != 'part' or part.get('status') != 'review_required' or
                        contract.get('base_id') != base_id or contract.get('base_sha256') != base['model_sha256']):
                    raise PipelineError('incompatible_part', '같은 기준 몸으로 제작해 검수가 필요한 파츠만 선택할 수 있습니다.', 422)
                slot = contract.get('slot')
                if not slot or slot in slots:
                    raise PipelineError('slot_conflict', '한 슬롯에 파츠 하나만 선택할 수 있습니다.', 422)
                slots.add(slot)
                self.standard.artifact(owner, part_id, 'part.glb')

            saved_at = now()
            revision = hashlib.sha256(
                f"{current['revision']}:{fingerprint}:{key_id}:{saved_at}".encode()
            ).hexdigest()
            result = {
                'base_id': base_id,
                'base_sha256': base['model_sha256'],
                'revision': revision,
                'part_ids': list(part_ids),
                'saved_at': saved_at,
            }
            receipts[key_id] = {'fingerprint': fingerprint, 'result': result}
            state['current'] = result
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_json(path, state)
            return dict(result)
