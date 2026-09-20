import bpy, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services.avatar_standard_blender import load, skeleton, camera_setup, render
from src.services.avatar_head_geometry import complete_unified_hair_shell
root = Path(__file__).parent
bpy.ops.wm.read_factory_settings(use_empty=True)
objects = load(str(root/'model.glb'))
rig = skeleton(objects)
rig.data.pose_position = 'REST'
bpy.context.scene.frame_set(0)
bpy.context.view_layer.update()
body = [o for o in objects if o.type == 'MESH' and o.get('part_role') == 'body']
hair = [o for o in objects if o.type == 'MESH' and o.get('part_role') == 'hair' and o.name != 'hair_1']
for obj in objects:
    if obj.name == 'hair_1':
        obj.hide_render = True
spec = json.loads((root/'input.json').read_text(encoding='utf8'))['production_spec']
spec['fitting']['rear_hair_strands'] = json.loads((root.parent/'assets/avatars/production-v1.json').read_text(encoding='utf8'))['fitting']['rear_hair_strands']
print('REAR_REPAIR', json.dumps(complete_unified_hair_shell(hair, body, rig, spec)))
camera, center = camera_setup(spec['body_height_m'])
render(root/'rear-repaired-back.png', camera, center, (0, 1, 0), 800)
render(root/'rear-repaired-front.png', camera, center, (0, -1, 0), 800)
