"""Fixed headless worker: compile, save editable master, render rest/diagnostic poses."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.services.avatar_factory_geometry import compile_source, compile_part_models, MASKS


def run(payload):
    output = Path(payload['output'])
    if hashlib.sha256(Path(payload['source']).read_bytes()).hexdigest() != payload['source_sha256']:
        raise ValueError('Source hash changed')
    def progress(stage, message):
        path = output/'progress.json'; temp = output/'progress.tmp'
        temp.write_text(json.dumps({'stage': stage, 'message': message}), encoding='utf-8'); temp.replace(path)
    progress('body', '공통 메이플풍 SD 기본 몸을 설계하는 중')
    result = compile_part_models(payload, progress) if payload.get('part_models') else compile_source(payload, progress)
    progress('verify', 'Blender에서 공통 리그와 동작을 검사하는 중')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(output/'workspace.glb'))
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE']
    if len(rigs) != 1 or len(rigs[0].data.bones) != 23:
        raise ValueError('Canonical armature must contain exactly 23 bones')
    hidden = {region for item in result['assets'] for region in MASKS.get(item['key'], [])}
    for obj in bpy.context.scene.objects:
        if obj.name.removeprefix('body_').split('.')[0] in hidden:
            obj.hide_render = True; obj.hide_set(True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'; scene.cycles.samples = 12
    scene.render.resolution_x = scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'; scene.render.film_transparent = True
    camera = bpy.data.objects.new('FactoryReviewCamera', bpy.data.cameras.new('FactoryReviewCamera'))
    scene.collection.objects.link(camera); scene.camera = camera
    visible_meshes = [obj for obj in scene.objects if obj.type == 'MESH' and not obj.hide_render]
    points = [obj.matrix_world @ Vector(corner) for obj in visible_meshes for corner in obj.bound_box]
    lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center = (lo+hi)/2
    camera.location = center + Vector((0, -4.5, .1))
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'; camera.data.ortho_scale = max(hi-lo)*1.2
    for index, offset in enumerate(((2, -3, 4), (-3, -2, 2))):
        obj = bpy.data.objects.new(f'FactoryLight{index}', bpy.data.lights.new(f'FactoryLight{index}', 'AREA'))
        scene.collection.objects.link(obj); obj.location = offset
        obj.rotation_euler = (center-obj.location).to_track_quat('-Z', 'Y').to_euler()
        obj.data.energy = 450; obj.data.shape = 'DISK'; obj.data.size = 4
    rig = rigs[0]
    # Save all body regions; garment masks are reversible visibility flags in the work file.
    rig.data.pose_position = 'REST'
    visibility = [(obj, obj.hide_render, obj.hide_get()) for obj in scene.objects if obj.type == 'MESH']
    for obj, _, _ in visibility:
        obj.hide_render = not obj.name.startswith('body_'); obj.hide_set(obj.hide_render)
    base_points = [obj.matrix_world @ Vector(corner) for obj, _, _ in visibility if not obj.hide_render for corner in obj.bound_box]
    base_lo = Vector(tuple(min(p[i] for p in base_points) for i in range(3)))
    base_hi = Vector(tuple(max(p[i] for p in base_points) for i in range(3)))
    base_center = (base_lo+base_hi)/2
    camera_location, camera_rotation, camera_scale = camera.location.copy(), camera.rotation_euler.copy(), camera.data.ortho_scale
    camera.location = base_center+Vector((0, -4.5, .1))
    camera.rotation_euler = (base_center-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = max(base_hi-base_lo)*1.2
    scene.render.filepath = str(output/'body.png'); bpy.ops.render.render(write_still=True)
    for obj, render_hidden, viewport_hidden in visibility:
        obj.hide_render = render_hidden; obj.hide_set(viewport_hidden)
    camera.location = camera_location; camera.rotation_euler = camera_rotation; camera.data.ortho_scale = camera_scale
    scene.render.filepath = str(output/'rest.png'); bpy.ops.render.render(write_still=True)
    camera.location = (3.5, -2.5, 1.3)
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(output/'side.png'); bpy.ops.render.render(write_still=True)
    rig.data.pose_position = 'POSE'
    rig.animation_data_clear()
    for name, angle in [('upperArmL', -.55), ('upperArmR', .55), ('lowerLegL', .4), ('upperLegR', -.25)]:
        bone = rig.pose.bones.get(name)
        if bone:
            bone.rotation_mode = 'XYZ'; bone.rotation_euler.z = angle
    scene.render.filepath = str(output/'pose.png'); bpy.ops.render.render(write_still=True)
    for bone in rig.pose.bones:
        bone.rotation_euler = (0, 0, 0)
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'master.blend'))
    (output/'compilation.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    files = ['body.glb', 'character.glb', 'workspace.glb', 'master.blend', 'body.png', 'rest.png', 'side.png', 'pose.png', 'compilation.json']
    files += [item['file'] for item in result['assets'] if item['key'] != 'body']
    seal = {'source_sha256': payload['source_sha256'], 'input_sha256': hashlib.sha256((output/'input.json').read_bytes()).hexdigest(),
            'files': {name: hashlib.sha256((output/name).read_bytes()).hexdigest() for name in files}}
    (output/'worker-complete.json').write_text(json.dumps(seal), encoding='utf-8')


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8')))
