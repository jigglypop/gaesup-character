"""Quadruped-only rest skeleton; generated weights require visual inspection."""
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(payload):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=payload['source'])
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    # Keep mesh world transforms and materials; replace old armatures explicitly.
    for obj in meshes:
        world=obj.matrix_world.copy(); obj.parent=None; obj.matrix_world=world
        for modifier in list(obj.modifiers):
            if modifier.type=='ARMATURE': obj.modifiers.remove(modifier)
        obj.vertex_groups.clear()
    for obj in list(bpy.context.scene.objects):
        if obj.type=='ARMATURE': bpy.data.objects.remove(obj,do_unlink=True)
    points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    lo=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    span=hi-lo
    if min(span)<1e-5: raise ValueError('Degenerate animal')
    # GLTF forward +Z maps to Blender -Y. Fractions are species-specific,
    # measured in the source bounds; never use a humanoid armature or Meshy rig API.
    profiles={'dog':(.34,.64,.74),'cat':(.30,.57,.69),'dragon':(.31,.54,.73)}
    half_width,body_height,head_height=profiles[payload['species']]
    def p(x,forward,z): return Vector((lo.x+span.x*x,hi.y-span.y*forward,lo.z+span.z*z))
    data=bpy.data.armatures.new('QuadrupedSkeleton')
    rig=bpy.data.objects.new('Quadruped_'+payload['species'],data); bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    def bone(name,head,tail,parent=None):
        b=data.edit_bones.new(name);b.head=head;b.tail=tail
        if parent:b.parent=data.edit_bones[parent]
    bone('root',p(.5,.35,.05),p(.5,.35,.2))
    bone('pelvis',p(.5,.28,body_height),p(.5,.42,body_height),'root')
    bone('spine',p(.5,.42,body_height),p(.5,.64,body_height),'pelvis')
    bone('neck',p(.5,.64,body_height),p(.5,.75,head_height),'spine')
    bone('head',p(.5,.75,head_height),p(.5,.93,head_height),'neck')
    for side,x in (('L',.5+half_width),('R',.5-half_width)):
        for limb,forward,parent in (('fore',.64,'spine'),('hind',.28,'pelvis')):
            joint=p(x,forward,body_height*.57)
            bone(limb+'_upper_'+side,p(x,forward,body_height),joint,parent)
            ankle=p(x,forward+(.04 if limb=='hind' else -.02),.10)
            bone(limb+'_lower_'+side,joint,ankle,limb+'_upper_'+side)
            bone(limb+'_paw_'+side,ankle,p(x,forward+.12,.035),limb+'_lower_'+side)
    previous='pelvis'
    for i in range(3):
        name='tail_'+str(i+1)
        bone(name,p(.5,.28-.09*i,body_height),p(.5,.19-.09*i,body_height+.035*(i+1)),previous);previous=name
    if payload['species']=='dragon':
        for side,x in (('L',1.),('R',0.)):
            bone('wing_'+side,p(.5,.55,body_height),p(x,.48,.93),'spine')
    bpy.ops.object.mode_set(mode='OBJECT')
    bones=[b for b in data.bones if b.name!='root']
    def distance(point,b):
        v=b.tail_local-b.head_local
        t=max(0,min(1,(point-b.head_local).dot(v)/v.length_squared))
        return (point-(b.head_local+t*v)).length
    for obj in meshes:
        groups={b.name:obj.vertex_groups.new(name=b.name) for b in bones}
        for vertex in obj.data.vertices:
            point=obj.matrix_world@vertex.co
            nearest=sorted(((distance(point,b),b.name) for b in bones))[:4]
            weights=[1/max(d,span.length*.005)**4 for d,_ in nearest]; total=sum(weights)
            for (_,name),weight in zip(nearest,weights):groups[name].add([vertex.index],weight/total,'REPLACE')
        modifier=obj.modifiers.new('QuadrupedSkin','ARMATURE');modifier.object=rig
    output=Path(payload['output'])
    bpy.ops.object.select_all(action='DESELECT')
    for obj in [rig,*meshes]:obj.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(output/'rigged.glb'),export_format='GLB',use_selection=True,export_animations=False,export_all_influences=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'master.blend'))
    (output/'complete.json').write_text(json.dumps({'input_sha256':sha(output/'input.json'),
        'files':{n:sha(output/n) for n in ('rigged.glb','master.blend')},'bones':len(bones)+1}),encoding='utf8')


if __name__=='__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8')))
