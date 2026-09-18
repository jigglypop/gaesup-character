"""Align saved sleeves and publish a shared T rest pose with rebased clips."""
import bpy
from mathutils import Matrix, Vector

from src.services.avatar_standard_blender import bounds, blender_to_gltf


def fit_sleeves(meshes, rig, spec):
    """Seat sleeve openings on the actual wrists before transferring weights."""
    lo, hi = bounds(meshes)
    torso = spec['base_body']['torso_width_m']/2
    reports = {}
    for side, sign in (('Left', 1), ('Right', -1)):
        shoulder = rig.matrix_world @ rig.data.bones[side+'Arm'].head_local
        wrist = rig.matrix_world @ rig.data.bones[side+'Hand'].head_local
        points = [obj.matrix_world @ v.co for obj in meshes for v in obj.data.vertices]
        extent = max(sign*p.x for p in points)
        cuff = [p for p in points if sign*p.x >= extent-.035]
        center = sum(cuff, Vector())/len(cuff)
        source_axis, target_axis = center-shoulder, wrist-shoulder
        rotation = source_axis.normalized().rotation_difference(target_axis.normalized()).to_matrix()
        direction = source_axis.normalized()
        longitudinal = target_axis.length/source_axis.length
        for obj in meshes:
            inverse = obj.matrix_world.inverted()
            for vertex in obj.data.vertices:
                point = obj.matrix_world @ vertex.co
                t = max(0, min(1, (sign*point.x-torso)/(extent*.72-torso)))
                if not t:
                    continue
                t = t*t*(3-2*t)
                offset = point-shoulder
                offset += direction*offset.dot(direction)*(longitudinal-1)
                destination = shoulder+rotation @ offset
                delta = inverse.to_3x3() @ ((destination-point)*t)
                original = vertex.co.copy()
                if obj.data.shape_keys:
                    for key in obj.data.shape_keys.key_blocks:
                        key.data[vertex.index].co += delta
                vertex.co = original+delta
            obj.data.update()
        reports[side.lower()] = {'source_cuff_m': blender_to_gltf(center),
                                'wrist_m': blender_to_gltf(wrist)}
    return {'method': 'sleeve_axis_to_actual_wrist', 'sides': reports}


def t_rest_pose(rig, meshes):
    """Rotate arm rest chains and skin together; compensate animation bases."""
    bones = list(rig.data.bones)
    old = {bone.name: bone.matrix_local.copy() for bone in bones}
    world = rig.matrix_world.copy()
    inverse = world.inverted()
    new = {name: matrix.copy() for name, matrix in old.items()}
    shoulder_height = sum((world @ old[side+'Arm']).translation.z for side in ('Left', 'Right'))/2
    for side, sign in (('Left', 1), ('Right', -1)):
        direction = Vector((sign, 0, 0))
        previous = None
        for suffix in ('Arm', 'ForeArm', 'Hand'):
            name = side+suffix
            source = world @ old[name]
            axis = source.to_3x3() @ Vector((0, 1, 0))
            rotation = axis.normalized().rotation_difference(direction).to_matrix().to_4x4()
            destination = rotation @ source
            if previous is None:
                destination.translation = Vector((source.translation.x, source.translation.y, shoulder_height))
            else:
                destination.translation = (world @ new[previous]) @ Vector((0, rig.data.bones[previous].length, 0))
            new[name] = inverse @ destination
            previous = name
        for bone in rig.data.bones[side+'Hand'].children_recursive:
            new[bone.name] = new[bone.parent.name] @ old[bone.parent.name].inverted() @ old[bone.name]

    # Capture channels in the imported rest frame before changing that frame.
    animation = rig.animation_data
    active = (animation.action, animation.action_slot) if animation and animation.action else None
    tracks = [(track, track.mute) for track in animation.nla_tracks] if animation else []
    sources = dict([(active[0], active[1])] if active else [])
    for track, _ in tracks:
        track.mute = True
        for strip in track.strips:
            if strip.action:
                sources[strip.action] = strip.action_slot
    samples = {}
    scene = bpy.context.scene
    frame = scene.frame_current
    rig.data.pose_position = 'POSE'
    for action, slot in sources.items():
        animation.action = action
        if slot:
            animation.action_slot = slot
        start, end = action.frame_range
        frames = sorted({float(start), float(end), *map(float, range(int(start), int(end)+1))})
        rows = []
        for value in frames:
            scene.frame_set(int(value), subframe=value-int(value))
            bpy.context.view_layer.update()
            rows.append((value, {p.name: p.matrix_basis.copy() for p in rig.pose.bones}))
        samples[action] = rows
    if animation:
        animation.action = None
    rig.data.pose_position = 'REST'

    transforms = {name: world @ new[name] @ old[name].inverted() @ inverse for name in old}
    for obj in meshes:
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        local = obj.matrix_world.inverted()
        groups = {g.index: g.name for g in obj.vertex_groups}
        for vertex in obj.data.vertices:
            weights = [(transforms[groups[g.group]], g.weight) for g in vertex.groups if groups.get(g.group) in transforms]
            total = sum(weight for _, weight in weights)
            if not total:
                continue
            def deform(co):
                point = obj.matrix_world @ co
                return local @ (sum(((transform @ point)*weight for transform, weight in weights), Vector())/total)
            destination = deform(vertex.co.copy())
            if obj.data.shape_keys:
                for key in obj.data.shape_keys.key_blocks:
                    key.data[vertex.index].co = deform(key.data[vertex.index].co.copy())
            vertex.co = destination
        obj.data.update()

    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in rig.data.edit_bones:
        bone.use_connect = False
        bone.matrix = new[bone.name]
    bpy.ops.object.mode_set(mode='OBJECT')
    new = {bone.name: bone.matrix_local.copy() for bone in rig.data.bones}
    correction = {}
    for bone in rig.data.bones:
        old_local = old[bone.parent.name].inverted() @ old[bone.name] if bone.parent else old[bone.name]
        new_local = new[bone.parent.name].inverted() @ new[bone.name] if bone.parent else new[bone.name]
        correction[bone.name] = new_local.inverted() @ old_local
    replacements = {}
    for source, rows in samples.items():
        action = bpy.data.actions.new(source.name+'_T_Rest')
        animation.action = action
        for value, matrices in rows:
            for pose in rig.pose.bones:
                pose.rotation_mode = 'QUATERNION'
                pose.matrix_basis = correction[pose.name] @ matrices[pose.name]
                for channel in ('location', 'rotation_quaternion', 'scale'):
                    pose.keyframe_insert(data_path=channel, frame=value, group=pose.name)
        replacements[source] = (action, animation.action_slot)
    if animation:
        animation.action = None
        for track, mute in tracks:
            for strip in track.strips:
                if strip.action in replacements:
                    action, slot = replacements[strip.action]
                    strip.action = action
                    strip.action_slot = slot
            track.mute = mute
        if active:
            animation.action, animation.action_slot = replacements[active[0]]
    scene.frame_set(frame)
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
    return {'rest_pose': 'T', 'animation_rest_bases_rebased': len(replacements),
            'wrists_m': {side.lower(): blender_to_gltf(world @ rig.data.bones[side+'Hand'].head_local)
                         for side in ('Left', 'Right')}}
