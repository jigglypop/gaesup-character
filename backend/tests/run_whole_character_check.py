"""Disposable Blender check: preserve a whole supplied mesh without a template body."""
import hashlib
import json
from pathlib import Path
import tempfile

from src.paths import BACKEND_ROOT
from src.services.asset_editor import _write_json
from src.services.avatar_factory import AvatarFactory, IMAGE_PROFILE
from src.services.character_pipeline import now
from src.services.glb import parse_glb
from src.services.process_identity import identity
from run_maple_equipment_check import boxes, values


def create_fixture(root):
    factory = AvatarFactory(root); job_id = 'd'*24
    directory = factory.directory(1, job_id); output = directory/'output'
    output.mkdir(parents=True)
    source = directory/'source.png'; source.write_bytes(b'authored fixture, no provider call')
    model = directory/'generated.glb'
    model.write_bytes(boxes([(0, 1.35, 0, .8, .8, .6), (0, .72, 0, .45, .45, .3),
                            (-.35, .72, 0, .3, .15, .15), (.35, .72, 0, .3, .15, .15),
                            (-.14, .25, 0, .18, .5, .2), (.14, .25, 0, .18, .5, .2)]))
    model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    _write_json(output/'input.json', {'source': str(source), 'source_sha256': source_hash,
        'output': str(output), 'part_models': [{'slot': 'body', 'path': str(model), 'sha256': model_hash}],
        'rig': str(BACKEND_ROOT/'assets/avatars/rig-maple-v1.json'),
        'motions': str(BACKEND_ROOT/'assets/avatars/manual-v1/body-sd-neutral-v1.glb')})
    _write_json(directory/'job.json', {'id': job_id, 'executor': factory.instance, 'executor_process': identity(),
        'fingerprint': 'whole-fixture', 'character_id': 'whole-fixture', 'character_name': 'Whole Fixture',
        'input_kind': 'image', 'source_sha256': source_hash, 'profile': IMAGE_PROFILE,
        'status': 'accepted', 'created_at': now(), 'updated_at': now(), 'error': None})
    factory.execute(1, job_id); result = factory.get(1, job_id)
    assert result['status'] == 'review_required', result
    assert result['outfit']['equipment'] == {}
    assert result['evidence']['body_origin'] == 'generated_whole_character'
    assert result['evidence']['source_triangles'] == 72
    assert result['evidence']['geometry_corrections'] == []
    doc, binary = parse_glb((output/'body.glb').read_bytes(), strict=True)
    assert len(doc['meshes']) == 1  # No appended template torso or head.
    primitive = doc['meshes'][0]['primitives'][0]
    points = values(doc, binary, primitive['attributes']['POSITION'])
    extent = [max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)]
    assert abs(extent[0]/extent[1]-1/1.75) < 1e-5
    assert hashlib.sha256(model.read_bytes()).hexdigest() == model_hash
    assert (output/'master.blend').is_file() and (output/'body.png').is_file()
    return {'status': 'passed', 'root': str(root), 'job': job_id, 'technical': result['technical']}


if __name__ == '__main__':
    print(json.dumps(create_fixture(Path(tempfile.mkdtemp(prefix='whole-character-check-')))))
