"""Quadruped-only rest skeleton; generated weights require visual inspection."""
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(payload):
    profiles={
        'dog': {'half_width': .31, 'body': .57, 'head': .72, 'knee': .31, 'ankle': .10,
                'neck': .68, 'head_end': .91, 'tail_rise': .025},
        'cat': {'half_width': .27, 'body': .54, 'head': .69, 'knee': .34, 'ankle': .115,
                'neck': .66, 'head_end': .89, 'tail_rise': .055},
        'dragon': {'half_width': .34, 'body': .56, 'head': .73, 'knee': .31, 'ankle': .10,
                   'neck': .66, 'head_end': .91, 'tail_rise': .04},
    }
    species=payload.get('species')
    if species not in profiles or payload.get('rig_profile') != 'local-quadruped-v2':
        raise ValueError('Unsupported quadruped rig profile')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=payload['source'])
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    if not meshes or not any(len(o.data.vertices) for o in meshes):
        raise ValueError('Animal mesh is empty')
    # Keep mesh world transforms and materials; replace old armatures explicitly.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.data=obj.data.copy()
        world=obj.matrix_world.copy(); obj.parent=None; obj.matrix_world=world
        for modifier in list(obj.modifiers):
            if modifier.type=='ARMATURE': obj.modifiers.remove(modifier)
        obj.vertex_groups.clear()
        bpy.context.view_layer.objects.active=obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        obj.select_set(False)
    for obj in list(bpy.context.scene.objects):
        if obj.type=='ARMATURE': bpy.data.objects.remove(obj,do_unlink=True)
    points=[v.co.copy() for o in meshes for v in o.data.vertices]
    lo=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    span=hi-lo
    if min(span)<1e-5: raise ValueError('Degenerate animal')
    # glTF forward +Z maps to Blender -Y. Fractions are species-specific and
    # measured in source bounds; this never reuses a humanoid armature.
    profile=profiles[species]
    half_width,body_height,head_height=(profile['half_width'],profile['body'],profile['head'])
    def p(x,forward,z): return Vector((lo.x+span.x*x,hi.y-span.y*forward,lo.z+span.z*z))
    data=bpy.data.armatures.new('QuadrupedSkeleton')
    rig=bpy.data.objects.new('Quadruped_'+species,data); bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    def bone(name,head,tail,parent=None):
        b=data.edit_bones.new(name);b.head=head;b.tail=tail
        if parent:b.parent=data.edit_bones[parent]
    bone('root',p(.5,.35,.05),p(.5,.35,.2)); data.edit_bones['root'].use_deform=False
    bone('pelvis',p(.5,.28,body_height),p(.5,.42,body_height),'root')
    bone('spine',p(.5,.42,body_height),p(.5,.64,body_height),'pelvis')
    bone('neck',p(.5,.64,body_height),p(.5,profile['neck'],head_height),'spine')
    bone('head',p(.5,profile['neck'],head_height),p(.5,profile['head_end'],head_height),'neck')
    for side,x in (('L',.5+half_width),('R',.5-half_width)):
        for limb,forward,parent in (('fore',.64,'spine'),('hind',.28,'pelvis')):
            joint=p(x,forward,profile['knee'])
            bone(limb+'_upper_'+side,p(x,forward,body_height),joint,parent)
            ankle=p(x,forward+(.04 if limb=='hind' else -.02),profile['ankle'])
            bone(limb+'_lower_'+side,joint,ankle,limb+'_upper_'+side)
            bone(limb+'_paw_'+side,ankle,p(x,forward+.12,.035),limb+'_lower_'+side)
    previous='pelvis'
    for i in range(3):
        name='tail_'+str(i+1)
        bone(name,p(.5,.28-.09*i,body_height),p(.5,.19-.09*i,body_height+profile['tail_rise']*(i+1)),previous);previous=name
    if species=='dragon':
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
            point=vertex.co
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
        'source_sha256':sha(payload['source']), 'rig_profile':payload['rig_profile'],
        'species':species, 'files':{n:sha(output/n) for n in ('rigged.glb','master.blend')},
        'bones':len(bones)+1}),encoding='utf8')


if __name__=='__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8')))
