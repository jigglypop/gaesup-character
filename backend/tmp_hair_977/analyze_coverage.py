
import bpy,sys,numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.services.avatar_standard_blender import load,skeleton,body_meshes
from src.services.avatar_fit_geometry import head_weighted_vertices
root=Path(__file__).parent;bpy.ops.wm.read_factory_settings(use_empty=True)
bo=load(str(root/'body.glb'));r=skeleton(bo);r.data.pose_position='REST';bpy.context.view_layer.update();w=head_weighted_vertices(body_meshes(bo,r),r)
h=np.array([list(o.matrix_world@o.data.vertices[i].co) for o,ids in w.items() for i in ids]);lo=h.min(0);hi=h.max(0);c=(lo+hi)/2
ho=load(str(root/'hair.glb'));hr=skeleton(ho);hr.data.pose_position='REST';bpy.context.view_layer.update();o=next(x for x in ho if x.type=='MESH' and x.name=='hair_0')
p=np.array([list(o.matrix_world@v.co) for v in o.data.vertices]);rear=(p[:,1]>c[1]);central=rear&(abs(p[:,0]-c[0])<(hi[0]-lo[0])*.3)&(p[:,2]>lo[2]+(hi[2]-lo[2])*.12)
q=p[central];print('CENTRAL_VERT xyz bounds',q.min(0).tolist(),q.max(0).tolist(),'z_quantiles',np.quantile(q[:,2],[0,.1,.25,.5,.75,.9,1]).tolist(),'y_quantiles',np.quantile(q[:,1],[0,.1,.5,.9,1]).tolist())
cent=np.array([list(o.matrix_world@f.center) for f in o.data.polygons]);fc=(cent[:,1]>c[1])&(abs(cent[:,0]-c[0])<(hi[0]-lo[0])*.3)&(cent[:,2]>lo[2]+(hi[2]-lo[2])*.12)
f=cent[fc];print('CENTRAL_FACES',len(f),'bounds',f.min(0).tolist() if len(f) else None,f.max(0).tolist() if len(f) else None,'z_quantiles',np.quantile(f[:,2],[0,.1,.5,.9,1]).tolist() if len(f) else None)
# x-z occupancy within central rear, 12 x 12 over upper skull
mask=rear&(p[:,0]>=lo[0])&(p[:,0]<=hi[0])&(p[:,2]>=lo[2])&(p[:,2]<=hi[2]); z=p[mask]
ix=np.clip(((z[:,0]-lo[0])/(hi[0]-lo[0])*12).astype(int),0,11);iz=np.clip(((z[:,2]-lo[2])/(hi[2]-lo[2])*12).astype(int),0,11)
occ=set(zip(ix,iz));print('REAR_HEAD_PROJECTED_GRID occupied',len(occ),'of',144,'percent',len(occ)/144)
for row in range(11,-1,-1): print(''.join('#' if (col,row) in occ else '.' for col in range(12)))
