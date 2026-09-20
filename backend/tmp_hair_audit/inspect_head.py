
import bpy, sys
from pathlib import Path
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services.avatar_standard_blender import load,skeleton,body_meshes,blender_to_gltf
bpy.ops.wm.read_factory_settings(use_empty=True)
objs=load(str(Path(__file__).with_name('body.glb'))); rig=skeleton(objs); meshes=body_meshes(objs,rig)
print('RIG',rig.name,[(b.name,list(blender_to_gltf(rig.matrix_world@b.head_local))) for b in rig.data.bones])
for o in meshes:
 print('MESH',o.name,len(o.data.vertices),'groups',[(g.index,g.name) for g in o.vertex_groups])
 for g in o.vertex_groups:
  if any(k in g.name.lower() for k in ('head','neck')):
   pts=[]; ws=[]
   for v in o.data.vertices:
    w=next((x.weight for x in v.groups if x.group==g.index),0)
    if w>.05: pts.append(o.matrix_world@v.co); ws.append(w)
   if pts:
    lo=Vector([min(p[i] for p in pts) for i in range(3)]); hi=Vector([max(p[i] for p in pts) for i in range(3)])
    print('GROUP',g.name,len(pts),min(ws),max(ws),'GLTF',list(blender_to_gltf(lo)),list(blender_to_gltf(hi)))
