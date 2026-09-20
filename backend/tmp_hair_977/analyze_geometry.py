
import bpy,sys,json,numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.services.avatar_standard_blender import load,skeleton,body_meshes
from src.services.avatar_fit_geometry import head_weighted_vertices
root=Path(__file__).parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bo=load(str(root/'body.glb')); brig=skeleton(bo); brig.data.pose_position='REST'; bpy.context.view_layer.update(); body=body_meshes(bo,brig)
weighted=head_weighted_vertices(body,brig)
verts=[]; tris=[]
for o,ids in weighted.items():
 idx={i:len(verts)+j for j,i in enumerate(sorted(ids))}
 verts += [o.matrix_world@o.data.vertices[i].co for i in sorted(ids)]
 for f in o.data.polygons:
  if len(f.vertices)==3 and all(i in idx for i in f.vertices): tris.append(tuple(idx[i] for i in f.vertices))
tree=BVHTree.FromPolygons(verts,tris,all_triangles=True)
a=np.array(verts); lo=a.min(0); hi=a.max(0); cen=(lo+hi)/2
print('HEAD',len(verts),len(tris),'xyz_lo',lo.tolist(),'xyz_hi',hi.tolist(),'width_depth_height',(hi-lo).tolist(),'center',cen.tolist())
ho=load(str(root/'hair.glb')); hrig=skeleton(ho); hrig.data.pose_position='REST'; bpy.context.view_layer.update()
meshes=[o for o in ho if o.type=='MESH']
for o in meshes:
 pts=np.array([list(o.matrix_world@v.co) for v in o.data.vertices])
 signed=[]; dist=[]
 for p in pts:
  hit,n,_,d=tree.find_nearest(Vector(p))
  signed.append(float((Vector(p)-hit).dot(n))); dist.append(float(d))
 signed=np.array(signed); dist=np.array(dist)
 rear=pts[:,1]>cen[1]
 central=rear & (np.abs(pts[:,0]-cen[0]) < (hi[0]-lo[0])*.30) & (pts[:,2] > lo[2]+(hi[2]-lo[2])*.12)
 near=dist<.08
 cr=central & near
 print('OBJECT',o.name,'verts',len(pts),'polys',len(o.data.polygons),'bounds',pts.min(0).tolist(),pts.max(0).tolist())
 print(' distribution rear',int(rear.sum()),'central_rear',int(central.sum()),'central_rear_near_head',int(cr.sum()))
 print(' signed_all q',np.quantile(signed,[0,.01,.1,.5,.9,.99,1]).tolist(),'inside',int((signed<0).sum()),'inside_gt25mm',int((signed<-.025).sum()))
 if central.any(): print(' central_signed q',np.quantile(signed[central],[0,.1,.5,.9,1]).tolist(),'central_inside',int((signed[central]<0).sum()))
