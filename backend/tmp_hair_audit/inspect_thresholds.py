
import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.services.avatar_standard_blender import load,skeleton,body_meshes
bpy.ops.wm.read_factory_settings(use_empty=True)
objs=load(str(Path(__file__).with_name('body.glb'))); rig=skeleton(objs)
for o in body_meshes(objs,rig):
 g=o.vertex_groups.get('Head')
 for t in (.05,.1,.25,.5,.75,.9):
  pts=[]
  for v in o.data.vertices:
   w=next((x.weight for x in v.groups if x.group==g.index),0)
   if w>=t:pts.append(o.matrix_world@v.co)
  lo=[min(x[i] for x in pts) for i in range(3)];hi=[max(x[i] for x in pts) for i in range(3)]
  print(t,len(pts),'x',lo[0],hi[0],'y',lo[1],hi[1],'z',lo[2],hi[2])
