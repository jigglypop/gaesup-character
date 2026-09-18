"""Owner-scoped S3 library metadata and reproducible tile maps."""
import hashlib
import io
import json
import math
import os
import random

from PIL import Image
from src.services.asset_editor import _write_json
from src.services.avatar_factory import _LOCK
from src.services.character_pipeline import PipelineError, read_json, now

SURFACES = {'snow': (224, 234, 244), 'sand': (202, 174, 119),
            'grass': (79, 112, 54), 'soil': (104, 76, 52), 'stone': (123, 128, 133)}


class StudioLibrary:
    def __init__(self, factory, owner):
        self.factory, self.owner = factory, owner
        self.root = factory.root/str(int(owner))/'library'

    def require_storage(self):
        if not os.getenv('ASSET_S3_BUCKET'):
            raise PipelineError('storage_required', 'S3 저장소 설정이 필요합니다.', 503)

    def metadata(self):
        return read_json(self.root/'catalog.json', {'revision': '0', 'items': {}})

    def save(self, job_id, name, archived, revision):
        self.require_storage()
        self.factory.get(self.owner, job_id)
        with _LOCK:
            catalog = self.metadata()
            if catalog['revision'] != revision:
                raise PipelineError('revision_conflict', '관리 목록이 변경되었습니다. 다시 불러오세요.', 409)
            catalog['items'][job_id] = {'name': name.strip(), 'archived': archived, 'updated_at': now()}
            catalog['revision'] = hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest()
            self.root.mkdir(parents=True, exist_ok=True)
            _write_json(self.root/'catalog.json', catalog)
            return catalog

    def textures(self):
        return {'items': [self.texture(path.parent.name) for path in (self.root/'textures').glob('*/record.json')]}

    def texture(self, texture_id):
        import re
        if not re.fullmatch(r'[a-f0-9]{24}', texture_id):
            raise PipelineError('not_found', '텍스쳐를 찾을 수 없습니다.', 404)
        record = read_json(self.root/'textures'/texture_id/'record.json')
        if not record:
            raise PipelineError('not_found', '텍스쳐를 찾을 수 없습니다.', 404)
        return {**record, 'artifacts': [{'name': name, 'sha256': sha,
                'url': f'/api/studio/textures/{texture_id}/{name}'} for name, sha in record['files'].items()]}

    def generate_texture(self, payload):
        self.require_storage()
        identity = {**payload, 'algorithm': 'periodic-fourier-pbr-v1'}
        texture_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
        directory = self.root/'textures'/texture_id
        with _LOCK:
            if (directory/'record.json').is_file():
                return self.texture(texture_id)
            n, seed, surface = payload['size'], payload['seed'], payload['surface']
            rng = random.Random(seed)
            # Integer frequencies produce a continuous periodic surface, including
            # normal derivatives. Each tile samples [0, 1), so texels aren't duplicated.
            waves = [(rng.randint(1, 24), rng.randint(-24, 24), rng.random()*math.tau,
                      .6**octave) for octave in range(7)]
            xs = [[math.sin(math.tau*fx*x/n+phase) for x in range(n)] for fx, _, phase, _ in waves]
            xc = [[math.cos(math.tau*fx*x/n+phase) for x in range(n)] for fx, _, phase, _ in waves]
            ys = [[math.sin(math.tau*fy*y/n) for y in range(n)] for _, fy, _, _ in waves]
            yc = [[math.cos(math.tau*fy*y/n) for y in range(n)] for _, fy, _, _ in waves]
            weight = sum(w[3] for w in waves)
            heights = [sum(a*(xs[i][x]*yc[i][y]+xc[i][x]*ys[i][y]) for i, (_, _, _, a) in enumerate(waves))/weight
                       for y in range(n) for x in range(n)]
            base = SURFACES[surface]; albedo, normals, orm = bytearray(), bytearray(), bytearray()
            clamp = lambda v: max(0, min(255, round(v)))
            for y in range(n):
                for x in range(n):
                    h = heights[y*n+x]
                    albedo.extend(clamp(c+(10 if surface == 'snow' else 24)*h) for c in base)
                    dx = (heights[y*n+(x+1)%n]-heights[y*n+(x-1)%n])*n*.025
                    dy = (heights[((y+1)%n)*n+x]-heights[((y-1)%n)*n+x])*n*.025
                    length = math.sqrt(dx*dx+dy*dy+1)
                    normals.extend((clamp(127.5-dx/length*127.5), clamp(127.5+dy/length*127.5), clamp(127.5+127.5/length)))
                    orm.extend((255, clamp(220+15*h), 0))
            directory.mkdir(parents=True, exist_ok=True)
            files = {}
            for name, raw in (('albedo', albedo), ('normal', normals), ('orm', orm)):
                output = io.BytesIO()
                Image.frombytes('RGB', (n, n), bytes(raw)).save(output, format='WEBP', lossless=True, method=4)
                data = output.getvalue(); filename = name+'.webp'
                (directory/filename).write_bytes(data)
                files[filename] = hashlib.sha256(data).hexdigest()
            record = {'id': texture_id, **identity, 'created_at': now(), 'files': files,
                'material': {'baseColor': 'albedo.webp', 'normal': 'normal.webp', 'orm': 'orm.webp',
                             'baseColorSpace': 'srgb', 'dataColorSpace': 'linear', 'wrap': 'repeat',
                             'mipmaps': True, 'metalness': 0, 'normalConvention': 'OpenGL'},
                'gpu': {'compression': 'rgba8-uncompressed', 'estimated_bytes_with_mips': n*n*4*3*4//3,
                        'texture_count': 3, 'sampler': 'repeat-trilinear', 'anisotropy': 4}}
            _write_json(directory/'record.json', record)
            return self.texture(texture_id)

    def artifact(self, texture_id, name):
        record = self.texture(texture_id)
        if name not in record['files']:
            raise PipelineError('not_found', '텍스쳐 파일을 찾을 수 없습니다.', 404)
        path = self.root/'textures'/texture_id/name
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['files'][name]:
            raise PipelineError('artifact_changed', '저장된 텍스쳐가 변경되었습니다.', 409)
        return path
