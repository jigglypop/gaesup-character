"""UV expression textures and GLB derivatives bound to an exact saved body."""
import base64
from copy import deepcopy
import hashlib
import io
import json
import re

from PIL import Image
from src.services.asset_editor import _write_json
from src.services.avatar_factory import _LOCK, digest
from src.services.avatar_native_parts import AvatarNativeParts
from src.services.character_pipeline import PipelineError, read_json, now
from src.services.glb import parse_glb, build_glb


class AvatarExpressions:
    def __init__(self, factory, owner, job, version):
        self.factory, self.owner, self.job, self.version = factory, owner, job, version
        self.body = AvatarNativeParts(factory).artifact(owner, job, version, 'body.glb')
        self.root = self.body.parent/'expressions'

    def listing(self):
        return {'items': [self.get(path.parent.name) for path in self.root.glob('*/record.json')]}

    def get(self, expression_id):
        if not re.fullmatch('[a-f0-9]{24}', expression_id):
            raise PipelineError('not_found', '표정을 찾을 수 없습니다.', 404)
        record = read_json(self.root/expression_id/'record.json')
        if not record:
            raise PipelineError('not_found', '표정을 찾을 수 없습니다.', 404)
        prefix = f'/api/studio/bodies/{self.job}/{self.version}/expressions/{expression_id}'
        return {k: v for k, v in record.items() if k != 'files'} | {
            'artifacts': [{'name': name, 'sha256': sha, 'url': f'{prefix}/{name}'} for name, sha in record['files'].items()]}

    def save(self, payload):
        body_sha = digest(self.body)
        if payload['body_sha256'] != body_sha:
            raise PipelineError('body_changed', '표정을 적용한 기본 몸 버전이 다릅니다.', 409)
        maps = payload['maps']
        if not maps or len({m['material'] for m in maps}) != len(maps):
            raise PipelineError('invalid_maps', '중복되지 않은 얼굴 텍스쳐가 필요합니다.', 422)
        doc, binary = parse_glb(self.body.read_bytes(), strict=True)
        images = []
        for item in maps:
            index = item['material']
            if index < 0 or index >= len(doc.get('materials', [])):
                raise PipelineError('invalid_material', '기본 몸에 없는 재질입니다.', 422)
            try:
                raw = base64.b64decode(item['png'], validate=True)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format != 'PNG' or max(image.size) > 1024 or min(image.size) < 1:
                        raise ValueError('Image bounds')
                    image.verify()
            except Exception:
                raise PipelineError('invalid_texture', '표정 텍스쳐는 1024px 이하 PNG여야 합니다.', 422) from None
            images.append((index, raw))
        identity = {k: v for k, v in payload.items() if k != 'maps'} | {
            'maps': [(index, hashlib.sha256(raw).hexdigest()) for index, raw in images], 'recipe': 'uv-expression-v1'}
        expression_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
        directory = self.root/expression_id
        with _LOCK:
            if (directory/'record.json').is_file():
                return self.get(expression_id)
            directory.mkdir(parents=True, exist_ok=True)
            files, materials = {}, []
            binary = bytearray(binary)
            for index, raw in images:
                name = f'material-{index}.png'
                (directory/name).write_bytes(raw)
                files[name] = hashlib.sha256(raw).hexdigest()
                material = doc['materials'][index]
                pbr = material.setdefault('pbrMetallicRoughness', {})
                previous = pbr.get('baseColorTexture')
                if previous is None:
                    raise PipelineError('missing_uv_texture', '기본 색상 텍스쳐가 있는 얼굴 재질이 필요합니다.', 422)
                previous_texture = doc['textures'][previous['index']]
                binary.extend(b'\0'*(-len(binary) % 4))
                view = len(doc['bufferViews'])
                doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(raw)})
                binary.extend(raw)
                source = len(doc['images'])
                doc['images'].append({'name': name, 'mimeType': 'image/png', 'bufferView': view})
                texture = len(doc['textures'])
                doc['textures'].append({'source': source, **({'sampler': previous_texture['sampler']} if 'sampler' in previous_texture else {})})
                pbr['baseColorTexture'] = {**deepcopy(previous), 'index': texture}
                materials.append({'material': index, 'file': name})
            doc['buffers'][0]['byteLength'] = len(binary)
            doc.setdefault('extras', {})['expression'] = {**identity, 'id': expression_id}
            model = build_glb(doc, bytes(binary))
            (directory/'body.glb').write_bytes(model)
            files['body.glb'] = hashlib.sha256(model).hexdigest()
            manifest = {**identity, 'id': expression_id, 'materials': materials, 'created_at': now(),
                        'gpu': {'texture_edge_max': 1024, 'mipmaps': True, 'extra_draw_calls': 0}}
            _write_json(directory/'manifest.json', manifest)
            files['manifest.json'] = digest(directory/'manifest.json')
            _write_json(directory/'record.json', {**manifest, 'files': files})
        return self.get(expression_id)

    def artifact(self, expression_id, name):
        self.get(expression_id)
        record = read_json(self.root/expression_id/'record.json')
        expected = record['files'].get(name)
        path = self.root/expression_id/name
        if not expected or '/' in name or '\\' in name or digest(path) != expected:
            raise PipelineError('not_found', '표정 파일을 찾을 수 없습니다.', 404)
        return path
