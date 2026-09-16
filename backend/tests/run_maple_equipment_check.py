"""Real Blender equipment compilation with disposable, explicitly authored fixtures."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile

from src.paths import BACKEND_ROOT
from src.services.asset_editor import _write_json
from src.services.avatar_equipment import EQUIPMENT
from src.services.avatar_factory import AvatarFactory, IMAGE_PROFILE
from src.services.character_pipeline import now
from src.services.glb import build_glb, parse_glb
from src.services.process_identity import identity


def boxes(parts):
    points, triangles = [], []
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
             (3, 7, 6), (3, 6, 2), (0, 4, 7), (0, 7, 3), (1, 2, 6), (1, 6, 5)]
    for x, y, z, w, h, d in parts:
        offset = len(points)
        points += [(x+sx*w/2, y+sy*h/2, z+sz*d/2) for sx, sy, sz in
                   [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
        triangles += [tuple(offset+i for i in face) for face in faces]
    vertices = struct.pack('<'+'f'*len(points)*3, *(v for p in points for v in p))
    indices = struct.pack('<'+'H'*len(triangles)*3, *(v for p in triangles for v in p))
    doc = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
           'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1}]}],
           'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(vertices)},
                           {'buffer': 0, 'byteOffset': len(vertices), 'byteLength': len(indices)}],
           'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': len(points), 'type': 'VEC3',
                          'min': [min(p[i] for p in points) for i in range(3)], 'max': [max(p[i] for p in points) for i in range(3)]},
                         {'bufferView': 1, 'componentType': 5123, 'count': len(triangles)*3, 'type': 'SCALAR'}],
           'buffers': [{'byteLength': len(vertices)+len(indices)}]}
    return build_glb(doc, vertices+indices)


def values(doc, binary, index):
    accessor = doc['accessors'][index]; view = doc['bufferViews'][accessor['bufferView']]
    code = {5126: 'f', 5123: 'H', 5121: 'B'}[accessor['componentType']]
    count = {'VEC3': 3, 'VEC4': 4}[accessor['type']]
    offset = view.get('byteOffset', 0)+accessor.get('byteOffset', 0)
    stride = view.get('byteStride', struct.calcsize('<'+code)*count)
    return [struct.unpack_from('<'+code*count, binary, offset+i*stride) for i in range(accessor['count'])]


def create_fixture(root):
    factory = AvatarFactory(root); job_id = 'e'*24; directory = factory.directory(1, job_id)
    output = directory/'output'; output.mkdir(parents=True)
    source = directory/'source.png'; source.write_bytes(b'disposable reference receipt, no image generation')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    models = []
    for slot in EQUIPMENT:
        geometry = [(0,.5,0,.12,.75,.06),(0,.2,0,.35,.06,.09),(0,.08,0,.08,.2,.08)] if slot == 'weapon' else [(0,.5,0,.5,.7,.09)]
        path = directory/f'fixture-{slot}.glb'; path.write_bytes(boxes(geometry))
        models.append({'slot': slot, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'task_id': None})
    _write_json(output/'input.json', {'source': str(source), 'source_sha256': source_hash, 'output': str(output),
        'part_models': models, 'rig': str(BACKEND_ROOT/'assets/avatars/rig-maple-v1.json'),
        'motions': str(BACKEND_ROOT/'assets/avatars/manual-v1/body-sd-neutral-v1.glb')})
    _write_json(directory/'job.json', {'id': job_id, 'executor': factory.instance, 'executor_process': identity(),
        'fingerprint': 'fixture', 'character_id': 'maple-equipment-fixture', 'character_name': 'Maple Equipment Fixture',
        'input_kind': 'image', 'source_sha256': source_hash, 'profile': IMAGE_PROFILE,
        'status': 'accepted', 'created_at': now(), 'updated_at': now(), 'error': None})
    factory.execute(1, job_id)
    result = factory.get(1, job_id)
    assert result['status'] == 'review_required', result
    assert set(result['outfit']['equipment']) == {e['slot'] for e in EQUIPMENT.values()}
    for slot, item in EQUIPMENT.items():
        doc, binary = parse_glb((output/f'{item["slot"]}.glb').read_bytes(), strict=True)
        joints = doc['skins'][0]['joints']
        expected = next(i for i, node in enumerate(joints) if doc['nodes'][node]['name'] == item['bone'])
        for mesh in doc['meshes']:
            for primitive in mesh['primitives']:
                attributes = primitive['attributes']
                assert all(row[0] == expected for row in values(doc, binary, attributes['JOINTS_0']))
                assert all(row == (1.,0.,0.,0.) for row in values(doc, binary, attributes['WEIGHTS_0']))
        assert result['evidence']['part_sources'][list(EQUIPMENT).index(slot)]['provider_task_id'] is None
    assert all(hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() == item['sha256'] for item in models)
    assert (output/'master.blend').is_file() and (output/'pose.png').is_file()
    return result


if __name__ == '__main__':
    root = Path(tempfile.mkdtemp(prefix='maple-equipment-check-'))
    result = create_fixture(root)
    print(json.dumps({'status': 'passed', 'root': str(root), 'job': result['id'], 'technical': result['technical'],
                      'verification': 'authored fixtures; real Blender; no provider or visual approval'}))
