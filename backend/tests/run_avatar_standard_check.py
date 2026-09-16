"""Disposable real-Blender proof: freeze body, fit/skin two parts, two outfits."""
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import os
import io

from src.paths import BACKEND_ROOT
from src.services.avatar_standard import AvatarStandard
from src.services.avatar_standard_models import BaseInput, PartInput, AssemblyInput, ReviewInput
from src.services.character_pipeline import CharacterPipeline
from src.services.glb import parse_glb, build_glb
from src.services.character_parts import blender_executable
from run_maple_equipment_check import boxes


def add_design_fixture(root, base_id):
    from unittest.mock import patch
    from PIL import Image, ImageDraw
    from src.services import avatar_standard_design as design
    from src.services.avatar_standard_models import DesignInput
    service = AvatarStandard(root); base = service.raw(1, base_id)
    canvas = Image.new('RGBA', (2048,2048))
    ImageDraw.Draw(canvas).polygon([(824,1250),(1224,1250),(1400,1400),(1320,1480),(1200,1380),(1200,1630),(848,1630),(848,1380),(728,1480),(648,1400)], fill='#ebd8ad')
    output = io.BytesIO(); canvas.save(output, format='PNG')
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture-never-sent'}), patch.object(design, 'generate_standard_part_image', return_value=output.getvalue()):
        item, _ = design.create(service, 1, 'fixture-standard-design', DesignInput(name='Fixture generated shirt', base_id=base_id,
            base_sha256=base['model_sha256'], object_key='fixture-shirt', view='front', description='Authored disposable test image. No real provider generation.').model_dump())
        design.execute(service, 1, item['id'])
    assert service.raw(1,item['id'])['status'] == 'design_review_required'
    return item['id']


def create_fixture(root):
    service = AvatarStandard(root); characters = CharacterPipeline(root)
    source = root/'fixture-body.glb'
    subprocess.run([blender_executable(), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
        '--python', str(Path(__file__).with_name('avatar_standard_fixture_blender.py')), '--', str(source)],
        check=True, stdout=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    original = source.read_bytes()
    char = characters.create('Canonical workflow fixture', 1.2, 1)
    char = characters.upload(char['id'], 1, original, 'model', char['revision'])
    value, _ = service.create(1, 'base', 'fixture-standard-base', BaseInput(character_id=char['id'], source_sha256=char['model_sha256'], name='Fixture body').model_dump())
    service.execute(1, value['id']); base = service.public(1, value['id'])
    assert base['status'] == 'review_required', (base, service.directory(1, value['id']))
    old, oldbin = parse_glb(original, strict=True)
    new, newbin = parse_glb(service.artifact(1, base['id'], 'model.glb').read_bytes(), strict=True)
    assert oldbin == newbin and old['skins'] == new['skins'] and old['animations'] == new['animations']
    from PIL import Image
    for view in ('front', 'side', 'back'):
        with Image.open(service.artifact(1, base['id'], f'{view}.png')) as image:
            assert image.size == (2048, 2048)
            box = image.getchannel('A').getbbox()
            assert box and abs(box[1]-300) <= 3 and abs(box[3]-1800) <= 3, (view, box)
    # Explicit test-only reviewer action, never an approval of a real asset.
    base = service.review(1, base['id'], ReviewInput(model_sha256=base['model_sha256'], decision='approved',
        bald_complete_body=True, neutral_apose=True, motion_checked=True, notes='Automated disposable fixture approval; not a production or visual approval.').model_dump())
    # Reuse authored template surface as a test garment. Strip its skin, preserve
    # geometry/materials, and let the new binder transfer weights from the body.
    normalized = service.artifact(1, base['id'], 'model.glb').read_bytes()
    doc, binary = parse_glb(normalized, strict=True)
    for node in doc['nodes']:
        node.pop('skin', None)
        if 'mesh' in node and node.get('name') not in ('torsoUpper', 'torsoLower', 'armUpperL.sleeve', 'armUpperR.sleeve'):
            node.pop('mesh')
    doc.pop('skins', None); doc.pop('animations', None)
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            primitive['attributes'].pop('JOINTS_0', None); primitive['attributes'].pop('WEIGHTS_0', None)
    model = service.upload(1, build_glb(doc, binary), 'glb')
    anchors = [{'name': name, 'source': p, 'target': p} for name, p in [('neck', [0, .8, 0]), ('left', [.2, .6, 0]), ('right', [-.2, .6, 0])]]
    parts = []
    for index, binding in enumerate(('transfer', 'rigid')):
        part_asset = model if index == 0 else service.upload(1, boxes([(0, 1.08, 0, .55, .16, .45)]), 'glb')
        part, _ = service.create(1, 'part', f'fixture-standard-part-{index}', PartInput(name=f'Fixture variant {index}',
            base_id=base['id'], base_sha256=base['model_sha256'], model_asset=part_asset['id'], slot='top' if index == 0 else 'hat',
            garment_type='top' if index == 0 else 'hat', binding=binding, bone='head' if index else None,
            anchors=anchors).model_dump())
        service.execute(1, part['id']); part = service.public(1, part['id'])
        assert part['status'] == 'review_required', (part, service.directory(1, part['id']))
        parts.append(part)
    outfits = []
    stream = io.BytesIO(); Image.new('RGBA', (32, 32), '#7799aa').save(stream, format='PNG')
    texture = service.upload(1, stream.getvalue(), 'png')
    for index, selected in enumerate(([parts[0]['id']], [parts[1]['id']])):
        outfit, _ = service.create(1, 'assembly', f'fixture-standard-outfit-{index}', AssemblyInput(base_id=base['id'],
            base_sha256=base['model_sha256'], name=f'Fixture outfit {index}', part_ids=selected,
            textures=[{'material_index': 0, 'image_asset': texture['id'], 'uv_layout_confirmed': True},
                {'part_id': parts[0]['id'], 'material_index': 0, 'image_asset': texture['id'], 'uv_layout_confirmed': True}] if index == 0 else []).model_dump())
        service.execute(1, outfit['id']); outfit = service.public(1, outfit['id'])
        assert outfit['status'] == 'review_required', (outfit, service.directory(1, outfit['id']))
        assert outfit['result']['bones'] == base['result']['bones']
        assert len(outfit['result']['bones']) == 24
        assert any(s['max_joint_matrix_delta'] > .01 for s in outfit['result']['motion_samples'])
        result_doc, _ = parse_glb(service.artifact(1, outfit['id'], 'model.glb').read_bytes(), strict=True)
        assert len(result_doc['animations']) == len(old['animations']), [a.get('name') for a in result_doc['animations']]
        if index == 0:
            assert any(a['name'].startswith('part-uv-') for a in parts[0]['artifacts'])
            directory = service.directory(1, outfit['id'])
            for original_path, changed_path in (
                (service.artifact(1, base['id'], 'model.glb'), directory/'appearance.glb'),
                (service.artifact(1, parts[0]['id'], 'part.glb'), directory/f'appearance-{parts[0]["id"]}.glb'),
            ):
                before, before_bin = parse_glb(original_path.read_bytes(), strict=True)
                after, after_bin = parse_glb(changed_path.read_bytes(), strict=True)
                assert all(before.get(key) == after.get(key) for key in ('meshes', 'nodes', 'skins', 'animations', 'accessors'))
                assert after_bin[:len(before_bin)] == before_bin
                assert len(after['images']) == len(before.get('images', []))+1
        outfits.append(outfit['id'])
    assert source.read_bytes() == original
    result = {'status': 'passed', 'root': str(root), 'base': base['id'], 'parts': [p['id'] for p in parts], 'outfits': outfits,
              'evidence': 'authored disposable fixture, no paid provider call, no production visual approval'}
    result['design'] = add_design_fixture(root, base['id'])
    (root/'fixture.json').write_text(json.dumps(result), encoding='utf-8')
    return result


if __name__ == '__main__':
    root = Path(tempfile.mkdtemp(prefix='avatar-standard-check-'))
    print(json.dumps(create_fixture(root)))
