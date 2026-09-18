"""Metric orthographic views of the exact saved base; never generates anatomy."""
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.services.avatar_standard_blender import load, skeleton, body_meshes, bounds, camera_setup, render, sha
from src.services.avatar_equipment import equipment_spec


def run(payload):
    if sha(payload['source']) != payload['sha256']:
        raise ValueError('Frozen body changed')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objects = load(payload['source']); rig = skeleton(objects)
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
    body = body_meshes(objects, rig); lo, hi = bounds(body)
    spec = payload['spec']; anchors = spec['anchors']
    def position(names):
        bone = next((b for b in rig.data.bones if any(b.name.lower().endswith(n.lower()) for n in names)), None)
        if bone is None:
            raise ValueError('Missing base joint')
        p = rig.matrix_world @ bone.head_local
        return [p.x, p.z, -p.y]
    for side, prefix in (('left', 'Left'), ('right', 'Right')):
        old_ankle = anchors[f'ankle_{side}'][:]
        for anchor, names in (('shoulder', [prefix+'Arm']), ('wrist', [prefix+'Hand']), ('ankle', [prefix+'Foot'])):
            anchors[f'{anchor}_{side}'] = position(names)
        foot = spec['fitting']['shoe_bounds'][side]
        for corner in foot:
            corner[0] += anchors[f'ankle_{side}'][0]-old_ankle[0]
            corner[2] += anchors[f'ankle_{side}'][2]-old_ankle[2]
    anchors['neck'] = position(['Neck']); anchors['waist'] = position(['Hips'])
    anchors['crown'] = [(lo.x+hi.x)/2, hi.z, -(lo.y+hi.y)/2]
    spec['body_height_m'] = hi.z-lo.z
    spec['fitting']['bounds']['body'] = [[lo.x, lo.z, -hi.y], [hi.x, hi.z, -lo.y]]
    head_points = [obj.matrix_world @ v.co for obj in body for v in obj.data.vertices
                   if (obj.matrix_world @ v.co).z > max(anchors['shoulder_left'][1], anchors['shoulder_right'][1])+.025]
    head_lo = [min(p[i] for p in head_points) for i in range(3)]
    head_hi = [max(p[i] for p in head_points) for i in range(3)]
    spec['measured_head_bounds_m'] = [[head_lo[0], head_lo[2], -head_hi[1]], [head_hi[0], head_hi[2], -head_lo[1]]]
    equipment_spec(spec)
    ratio = spec['fitting'].get('hair_length_head_ratio')
    if ratio is not None:
        hair = spec['fitting']['bounds']['hair']
        hair[0][1] = max(.035, hair[1][1]-(hi.z-anchors['neck'][1])*ratio)
    c = spec['canvas']; c['pixels_per_metre'] = (c['sole_y']-c['scalp_y'])/spec['body_height_m']
    camera, _ = camera_setup(spec['body_height_m'])
    camera.data.ortho_scale = c['height']/c['pixels_per_metre']
    center = Vector((0, 0, lo.z+(c['sole_y']-c['height']/2)/c['pixels_per_metre']))
    scene = bpy.context.scene
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'; scene.render.image_settings.color_mode = 'RGBA'
    output = Path(payload['output'])
    for view, direction in (('front', (0, -1, 0)), ('side', (1, 0, 0))):
        render(output/f'body-{view}.png', camera, center, direction, c['width'])
    spec.pop('sha256', None)
    spec['sha256'] = hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    (output/'spec.json').write_text(json.dumps(spec), encoding='utf8')


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8')))
