
import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.services.avatar_standard_blender import load,skeleton,camera_setup,render
from src.services.avatar_head_geometry import complete_unified_hair_shell
bpy.ops.wm.read_factory_settings(use_empty=True)
root=Path(__file__).parent
objs=load(str(root/'model.glb')); rig=skeleton(objs)
rig.data.pose_position='REST'
bpy.context.scene.frame_set(0); bpy.context.view_layer.update()
body=[o for o in objs if o.type=='MESH' and o.get('part_role')=='body']
hair=[o for o in objs if o.type=='MESH' and o.get('part_role')=='hair']
spec=json.loads((root/'input.json').read_text(encoding='utf8'))['production_spec']
report=complete_unified_hair_shell(hair,body,rig,spec)
for o in hair:
 o['part_role']='hair'
print('SHELL_REPORT',json.dumps(report))
camera,center=camera_setup(spec['body_height_m'])
render(root/'back-shell-preview.png',camera,center,(0,1,0),800)
render(root/'front-shell-preview.png',camera,center,(0,-1,0),800)

