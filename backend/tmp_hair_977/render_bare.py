
import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.services.avatar_standard_blender import load,skeleton,camera_setup,render
root=Path(__file__).parent;bpy.ops.wm.read_factory_settings(use_empty=True)
o=load(str(root/'model.glb'));r=skeleton(o);r.data.pose_position='REST';bpy.context.scene.frame_set(0);bpy.context.view_layer.update()
for x in o:
 if x.name=='hair_1': x.hide_render=True
spec=json.loads((root/'input.json').read_text(encoding='utf8'))['production_spec'];cam,cen=camera_setup(spec['body_height_m'])
render(root/'back-barehair.png',cam,cen,(0,1,0),800)
for x in o:
 if x.type=='MESH' and x.get('part_role')=='hat': x.hide_render=True
render(root/'back-barehair-nohat.png',cam,cen,(0,1,0),800)
