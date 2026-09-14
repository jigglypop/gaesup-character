"""Disposable, real Blender check of the separately-generated-part compiler."""
import hashlib
import json
from pathlib import Path
import tempfile

from src.paths import BACKEND_ROOT
from src.services.avatar_factory import AvatarFactory, PROFILE
from src.services.asset_editor import _write_json
from src.services.character_pipeline import now
from src.services.glb import parse_glb, build_glb
from src.services.process_identity import identity


if __name__ == '__main__':
    root = Path(tempfile.mkdtemp(prefix='avatar-factory-check-'))
    factory = AvatarFactory(root); job_id = 'f'*24; directory = factory.directory(1, job_id)
    output = directory/'output'; output.mkdir(parents=True)
    source = directory/'source.png'; source.write_bytes(b'disposable image-source receipt')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    package = BACKEND_ROOT/'assets/avatars/manual-v1'
    items = {'face': 'body-sd-neutral-v1', 'hairFront': 'hair-001', 'hairBack': 'hair-002', 'hat': 'hat-001',
             'top': 'top-001', 'bottom': 'bottom-001', 'shoes': 'shoes-001'}
    models = [{'slot': slot, 'path': str(package/f'{name}.glb'), 'sha256': hashlib.sha256((package/f'{name}.glb').read_bytes()).hexdigest(),
               'task_id': f'fixture-{slot}'} for slot, name in items.items()]
    # The face input contains only the authored head, not a mislabeled full body.
    catalog = json.loads((package/'catalog.json').read_text(encoding='utf-8'))
    head_nodes = {part['node'] for part in catalog[0]['metadata']['avatar']['bodyRegions']['head']}
    face_doc, face_binary = parse_glb((package/'body-sd-neutral-v1.glb').read_bytes(), strict=True)
    for i, node in enumerate(face_doc['nodes']):
        if i not in head_nodes:
            node.pop('mesh', None); node.pop('skin', None)
    face = directory/'fixture-face.glb'; face.write_bytes(build_glb(face_doc, face_binary))
    models[0].update(path=str(face), sha256=hashlib.sha256(face.read_bytes()).hexdigest())
    _write_json(output/'input.json', {'source': str(source), 'source_sha256': source_hash, 'output': str(output),
        'part_models': models, 'rig': str(BACKEND_ROOT/'assets/avatars/rig-v1.json'), 'motions': str(package/'body-sd-neutral-v1.glb')})
    _write_json(directory/'job.json', {'id': job_id, 'executor': factory.instance, 'executor_process': identity(),
        'fingerprint': 'fixture', 'character_id': 'fixture', 'character_name': 'Separate Part Fixture', 'input_kind': 'image',
        'source_sha256': source_hash, 'profile': PROFILE, 'status': 'accepted', 'created_at': now(), 'updated_at': now(), 'error': None})
    factory.execute(1, job_id)
    result = factory.get(1, job_id)
    assert result['status'] == 'review_required', (result, str(output/'blender.log'))
    doc, _ = parse_glb((output/'character.glb').read_bytes(), strict=True)
    assert len(doc['skins']) == 1 and len(doc['skins'][0]['joints']) == 23
    assert len(doc['animations']) == 7
    body, _ = parse_glb((output/'body.glb').read_bytes(), strict=True)
    names = {node.get('name') for node in body['nodes'] if 'mesh' in node}
    assert {'head.eyeL', 'head.eyeR', 'head.shineL', 'armUpperL.sleeve', 'legUpperL.shorts'} <= names
    assert {'Common body shirt', 'Common body shorts'} <= {material.get('name') for material in body['materials']}
    catalog = json.loads((output/'catalog.json').read_text(encoding='utf-8'))
    manifest = catalog['assets'][0]['metadata']['avatar']
    assert len(manifest['bodyRegions']['head']) == 12
    assert len(manifest['meshes']) == len(names)
    assert (output/'body.png').is_file()
    assert all(item['sha256'] == hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() for item in models)
    assert result['technical']['parts'] == 6  # Two image hair layers share the runtime hair slot.
    assert {a['name'] for a in result['artifacts']} >= {'master.blend', 'rest.png', 'side.png', 'pose.png', 'character.glb'}
    rig = json.loads((BACKEND_ROOT/'assets/avatars/rig-v1.json').read_text())
    frontend_rig = json.loads((BACKEND_ROOT.parent/'frontend/src/avatar/core/rig.json').read_text())
    assert rig == frontend_rig
    print(json.dumps({'status': 'passed', 'output': str(output), 'technical': result['technical'],
                      'verification': 'fixture parts compiled by real Blender; no provider or visual approval'}))
