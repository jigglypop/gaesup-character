"""Isolated Blender worker; reuse an imported skeleton without a 23-bone assumption."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.services.glb import parse_glb, build_glb


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return list(set(bpy.context.scene.objects)-before)


def bounds(meshes):
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    return Vector([min(p[i] for p in points) for i in range(3)]), Vector([max(p[i] for p in points) for i in range(3)])


def skeleton(objects):
    rigs = [o for o in objects if o.type == 'ARMATURE']
    if len(rigs) != 1:
        raise ValueError('Exactly one canonical armature is required')
    rig = rigs[0]
    if not rig.data.bones:
        raise ValueError('Missing bones')
    return rig


def body_meshes(objects, rig):
    # Blender's importer creates Icosphere custom bone widgets in the scene.
    # These are display aids, not glTF geometry or weight-transfer surfaces.
    widgets = {b.custom_shape for b in rig.pose.bones if b.custom_shape}
    meshes = [o for o in objects if o.type == 'MESH' and o not in widgets]
    if not meshes:
        raise ValueError('Body has no surface')
    return meshes


def mesh_signature(mesh):
    return {'vertices': len(mesh.data.vertices), 'polygons': len(mesh.data.polygons),
            'uv_layers': len(mesh.data.uv_layers), 'shape_keys': len(mesh.data.shape_keys.key_blocks) if mesh.data.shape_keys else 0}


def gltf_to_blender(p):
    return Vector((p[0], -p[2], p[1]))


def blender_to_gltf(p):
    return [p.x, p.z, -p.y]


def apply_textures(path, textures, target):
    if not textures:
        return path
    doc, binary = parse_glb(Path(path).read_bytes(), strict=True)
    for texture in textures:
        if sha(texture['path']) != texture['image_asset']:
            raise ValueError('Texture changed')
        png = Path(texture['path']).read_bytes(); binary += b'\0'*(-len(binary)%4)
        view = len(doc.setdefault('bufferViews', []))
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(png)})
        binary += png
        image = len(doc.setdefault('images', [])); doc['images'].append({'bufferView': view, 'mimeType': 'image/png'})
        material = doc['materials'][texture['material_index']].setdefault('pbrMetallicRoughness', {})
        previous = material.get('baseColorTexture', {})
        old_texture = doc.get('textures', [])[previous['index']] if 'index' in previous else {}
        tex = len(doc.setdefault('textures', [])); entry = {'source': image}
        if 'sampler' in old_texture:
            entry['sampler'] = old_texture['sampler']
        doc['textures'].append(entry)
        material['baseColorTexture'] = {**previous, 'index': tex}
        material['baseColorFactor'] = [1, 1, 1, 1]
    doc['buffers'][0]['byteLength'] = len(binary)
    target.write_bytes(build_glb(doc, binary))
    return target


def material_metadata(doc):
    return [{'index': i, 'name': m.get('name', f'material-{i}'),
        'has_uv': any(p.get('material') == i and 'TEXCOORD_0' in p['attributes'] for mesh in doc.get('meshes', []) for p in mesh['primitives'])}
        for i, m in enumerate(doc.get('materials', []))]


def uv_templates(path, output, prefix):
    from src.services.avatar_factory_geometry import accessor
    doc, binary = parse_glb(Path(path).read_bytes(), strict=True); files = []
    for material in material_metadata(doc):
        if not material['has_uv']:
            continue
        lines = []
        for mesh in doc['meshes']:
            for primitive in mesh['primitives']:
                if primitive.get('material') != material['index'] or 'TEXCOORD_0' not in primitive['attributes'] or primitive.get('mode', 4) != 4:
                    continue
                uv = accessor(doc, binary, primitive['attributes']['TEXCOORD_0'])
                indices = accessor(doc, binary, primitive['indices']).reshape(-1) if 'indices' in primitive else np.arange(len(uv))
                if not np.isfinite(uv).all():
                    raise ValueError('Nonfinite texture coordinates')
                for triangle in indices.reshape(-1,3):
                    points = ' '.join(f'{float(uv[i][0])*2048:.2f},{float(uv[i][1])*2048:.2f}' for i in triangle)
                    lines.append(f'<polygon points="{points}"/>')
        filename = f'{prefix}-uv-{material["index"]}.svg'
        (output/filename).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="2048" height="2048" viewBox="0 0 2048 2048"><g fill="none" stroke="#606060" stroke-width="1">'+''.join(lines)+'</g></svg>', encoding='utf-8')
        files.append(filename)
    return files


def fit_matrix(anchors, tolerance):
    source = np.array([gltf_to_blender(a['source']) for a in anchors], dtype=float)
    target = np.array([gltf_to_blender(a['target']) for a in anchors], dtype=float)
    a, b = source-source.mean(axis=0), target-target.mean(axis=0)
    if np.linalg.matrix_rank(a, tol=1e-7) < 2 or np.linalg.matrix_rank(b, tol=1e-7) < 2:
        raise ValueError('At least three non-collinear fitting anchors are required')
    u, singular, vt = np.linalg.svd(a.T @ b)
    correction = np.eye(3); correction[-1, -1] = np.linalg.det(vt.T @ u.T)
    rotation = vt.T @ correction @ u.T
    scale = float(np.sum(singular*np.diag(correction))/np.sum(a*a))
    if not .001 <= scale <= 1000:
        raise ValueError('Invalid uniform scale')
    translation = target.mean(axis=0)-scale*rotation@source.mean(axis=0)
    fitted = (scale*rotation@source.T).T+translation
    errors = np.linalg.norm(fitted-target, axis=1)
    if tolerance is not None and max(errors) > tolerance:
        raise ValueError('Wearing anchors disagree; redesign required instead of stretching silhouette')
    result = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            result[i][j] = float(scale*rotation[i, j])
        result[i][3] = float(translation[i])
    return result, {'uniform_scale': scale, 'anchor_errors_m': errors.tolist()}


def weight_surface(meshes, rig):
    points, triangles, weights = [], [], []
    for obj in meshes:
        offset = len(points)
        points += [obj.matrix_world @ v.co for v in obj.data.vertices]
        names = {g.index: g.name for g in obj.vertex_groups if g.name in rig.data.bones}
        for v in obj.data.vertices:
            row = {names[g.group]: g.weight for g in v.groups if g.group in names and g.weight > 0}
            if not row or abs(sum(row.values())-1) > .02:
                raise ValueError(f'Canonical body has missing or non-normalized weights: {obj.name} vertex {v.index}: {row}')
            weights.append(row)
        obj.data.calc_loop_triangles()
        triangles += [tuple(offset+i for i in t.vertices) for t in obj.data.loop_triangles]
    return BVHTree.FromPolygons(points, triangles, all_triangles=True), points, triangles, weights


def bind(meshes, body, rig, contract, *, transform=None):
    if transform is None:
        transform, report = fit_matrix(contract['anchors'], contract['max_anchor_error_m'])
        fitting = 'uniform_anchor_alignment'
    else:
        # Factory fitting already resolved width, depth, height and position.
        # Solving uniform anchors again would discard the depth correction.
        report = {'transform_blender': [list(row) for row in transform]}
        fitting = 'shared_frame_axis_alignment'
    tree, points, triangles, weights = weight_surface(body, rig)
    distances, inside = [], 0
    for obj in meshes:
        # Unrigged source only: do not silently discard an independently authored skin.
        if any(mod.type == 'ARMATURE' for mod in obj.modifiers):
            raise ValueError('Part is already rigged; supply the unrigged generated shape')
        world = transform @ obj.matrix_world
        obj.parent = None; obj.matrix_world = Matrix.Identity(4)
        obj.data.transform(world, shape_keys=True)
        obj.vertex_groups.clear()
        groups = {b.name: obj.vertex_groups.new(name=b.name) for b in rig.data.bones}
        for vertex in obj.data.vertices:
            hit, normal, index, distance = tree.find_nearest(vertex.co)
            if hit is None:
                raise ValueError('No body surface for weight transfer')
            distances.append(distance)
            inside += int((vertex.co-hit).dot(normal) < -.002)
            if contract['binding'] == 'rigid':
                row = {contract['bone']: 1.}
            else:
                maximum_distance = contract.get('max_transfer_distance_m')
                if maximum_distance is not None and distance > maximum_distance:
                    raise ValueError('Part is too far from the body for a reliable weight transfer')
                ids = triangles[index]
                bary = barycentric_transform(hit, *(points[i] for i in ids), Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
                row = {}
                for i, factor in zip(ids, bary):
                    for name, weight in weights[i].items():
                        row[name] = row.get(name, 0)+max(0, factor)*weight
                row = dict(sorted(row.items(), key=lambda pair: pair[1], reverse=True)[:4])
                total = sum(row.values())
                if total <= 1e-8:
                    raise ValueError('Zero transferred skin weight')
                row = {k: v/total for k, v in row.items()}
            for name, weight in row.items():
                if weight > 1e-8:
                    groups[name].add([vertex.index], weight, 'REPLACE')
        modifier = obj.modifiers.new('CanonicalBodySkin', 'ARMATURE'); modifier.object = rig
        obj['standard_slot'] = contract['slot']
    report.update(binding=contract['binding'], max_surface_distance_m=max(distances),
                  possible_inside_vertices=inside, visual_review='required',
                  fitting=fitting, weights='body_surface_barycentric' if contract['binding'] == 'transfer' else 'single_canonical_bone')
    return report


def export(path, objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = next(o for o in objects if o.type == 'ARMATURE')
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True,
                              export_animations=True, export_animation_mode='NLA_TRACKS',
                              export_extras=True, export_all_influences=False)


def camera_setup(height):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'; scene.cycles.samples = 8
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'; scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    camera = bpy.data.objects.new('StandardCamera', bpy.data.cameras.new('StandardCamera'))
    scene.collection.objects.link(camera); scene.camera = camera
    camera.data.type = 'ORTHO'; camera.data.ortho_scale = 2048*height/1500
    center = Vector((0, 0, height*(.5+26/1500)))
    for i, pos in enumerate(((2, -3, 4), (-3, -1, 2), (0, 3, 3))):
        light = bpy.data.objects.new(f'StandardLight{i}', bpy.data.lights.new(f'StandardLight{i}', 'AREA'))
        scene.collection.objects.link(light); light.location = pos; light.data.energy = 180; light.data.size = 4
        light.rotation_euler = (center-light.location).to_track_quat('-Z', 'Y').to_euler()
    return camera, center


def render(path, camera, center, direction, size):
    camera.location = center+Vector(direction)*4
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene = bpy.context.scene; scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.filepath = str(path); bpy.ops.render.render(write_still=True)


def motion_evidence(rig, output, camera, center):
    animation = rig.animation_data
    if not animation:
        raise ValueError('Imported rig has no animation data')
    candidates = []
    if animation.action:
        candidates.append((animation.action, animation.action_slot))
    for track in animation.nla_tracks:
        track.mute = True
        for strip in track.strips:
            if strip.action and all(a != strip.action for a, _ in candidates):
                candidates.append((strip.action, strip.action_slot))
    if not candidates:
        raise ValueError('No playable rig animation')
    scene = bpy.context.scene; samples = []
    rig.data.pose_position = 'POSE'
    for action, slot in candidates:
        animation.action = action
        if slot:
            animation.action_slot = slot
        lo, hi = action.frame_range
        frames = []
        for factor in (0., .25, .5, .75):
            scene.frame_set(int(lo+(hi-lo)*factor)); bpy.context.view_layer.update()
            matrix = np.array([list(row) for bone in rig.pose.bones for row in bone.matrix], dtype=float)
            if not np.isfinite(matrix).all():
                raise ValueError('Nonfinite animated joint transform')
            frames.append(matrix)
        samples.append({'clip': action.name, 'frames': [float(lo+(hi-lo)*f) for f in (0., .25, .5, .75)],
                        'max_joint_matrix_delta': max(float(np.max(np.abs(m-frames[0]))) for m in frames[1:])})
    selected = next(((a, s) for a, s in candidates if 'walk' in a.name.lower()), candidates[0])
    animation.action = selected[0]
    if selected[1]:
        animation.action_slot = selected[1]
    lo, hi = selected[0].frame_range
    scene.frame_set(int(lo+(hi-lo)*.25))
    render(output/'motion.png', camera, center, (0, -1, 0), 640)
    scene.frame_set(int(lo))
    return samples


def run(payload):
    output = Path(payload['output']); contract = payload['contract']; kind = payload['kind']
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if kind == 'base':
        if sha(payload['source']) != payload['source_sha256']:
            raise ValueError('Source changed')
        objects = load(payload['source']); rig = skeleton(objects)
        rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
        body = body_meshes(objects, rig)
        lo, hi = bounds(body); height = contract['height_m']
        scale = height/(hi.z-lo.z)
        # Wrap the complete scene: original accessors, skin, inverse binds, UVs,
        # morphs and animation channels remain byte-for-byte in the original BIN.
        doc, binary = parse_glb(Path(payload['source']).read_bytes(), strict=True)
        scene = doc['scenes'][doc.get('scene', 0)]
        translation = [-((lo.x+hi.x)/2)*scale, -lo.z*scale, ((lo.y+hi.y)/2)*scale]
        wrapper = {'name': 'StandardBodyMetres', 'children': scene['nodes'], 'scale': [scale]*3, 'translation': translation}
        scene['nodes'] = [len(doc['nodes'])]; doc['nodes'].append(wrapper)
        (output/'model.glb').write_bytes(build_glb(doc, binary))
        bpy.ops.wm.read_factory_settings(use_empty=True)
        objects = load(output/'model.glb'); rig = skeleton(objects)
        body = body_meshes(objects, rig)
        fit = {'normalization_scale': scale, 'normalization_translation_gltf': translation, 'source_buffers_preserved': True,
               'body_completeness': 'requires_human_review', 'provenance': payload['provenance']}
        source_doc = doc
    else:
        if sha(payload['base']) != contract['base_sha256']:
            raise ValueError('Canonical body changed')
        base_path = Path(payload['base'])
        base_path = apply_textures(base_path, [t for t in payload.get('textures', []) if not t.get('part_id')], output/'appearance.glb')
        objects = load(base_path); rig = skeleton(objects)
        body = body_meshes(objects, rig)
        source_doc, _ = parse_glb(Path(payload['base']).read_bytes(), strict=True)
        height = payload['base_metadata']['height_m']
        if kind == 'part':
            if sha(payload['source']) != payload['source_sha256']:
                raise ValueError('Part source changed')
            additions = load(payload['source'])
            if any(o.type == 'ARMATURE' for o in additions):
                raise ValueError('Independent part rig is not supported')
            parts = [o for o in additions if o.type == 'MESH']
            if not parts:
                raise ValueError('Missing part geometry')
            rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
            fit = bind(parts, body, rig, contract)
            fit['provider_task_id'] = payload.get('provider_task_id')
            export(output/'part.glb', [rig, *parts])
        else:
            parts = []; fit = {'parts': payload['parts']}
            for part in payload['parts']:
                if sha(part['path']) != part['sha256']:
                    raise ValueError('Part changed')
                part_path = apply_textures(Path(part['path']), [t for t in payload.get('textures', []) if t.get('part_id') == part['id']], output/f'appearance-{part["id"]}.glb')
                additions = load(part_path); duplicate = skeleton(additions)
                if set(duplicate.data.bones.keys()) != set(rig.data.bones.keys()):
                    raise ValueError('Incompatible joint names')
                for bone in rig.data.bones:
                    a = rig.matrix_world @ bone.matrix_local
                    b = duplicate.matrix_world @ duplicate.data.bones[bone.name].matrix_local
                    if max(abs(a[i][j]-b[i][j]) for i in range(4) for j in range(4)) > 1e-4:
                        raise ValueError('Incompatible joint rest transforms')
                for obj in body_meshes(additions, duplicate):
                    world = obj.matrix_world.copy(); obj.parent = None; obj.matrix_world = world
                    for mod in obj.modifiers:
                        if mod.type == 'ARMATURE':
                            mod.object = rig
                    parts.append(obj)
                bpy.data.objects.remove(duplicate, do_unlink=True)
        rig.data.pose_position = 'POSE'
        export(output/'model.glb', [rig, *body, *parts])
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
    weight_surface(body, rig)
    actions = [a.get('name', f'clip-{i}') for i, a in enumerate(source_doc.get('animations', []))]
    if not actions:
        raise ValueError('A canonical body must contain at least one reviewable animation')
    # Persist render scale and landmarks, without inventing A-pose or complete-body approval.
    # Blender Python intentionally has no application dependencies.
    camera, center = camera_setup(height)
    for view, direction in [('front', (0, -1, 0)), ('side', (1, 0, 0)), ('back', (0, 1, 0))]:
        render(output/f'{view}.png', camera, center, direction, 2048 if kind == 'base' else 640)
    motion_samples = motion_evidence(rig, output, camera, center)
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'master.blend'))
    result = {'technical_passed': True, 'height_m': height, 'bones': list(rig.data.bones.keys()),
              'bone_heads_gltf': {b.name: blender_to_gltf(rig.matrix_world @ b.head_local) for b in rig.data.bones},
              'animations': actions, 'motion_samples': motion_samples, 'base_meshes': {o.name: mesh_signature(o) for o in body},
              'materials': material_metadata(source_doc),
              'fit': fit, 'image_spec': {'width': 2048, 'height': 2048, 'body_top_px': 300, 'sole_px': 1800,
                  'center_x_px': 1024, 'body_height_m': height, 'pixels_per_meter': 1500/height,
                  'orthographic_scale_m': 2048*height/1500, 'pose': 'source_rest_pose'},
              'limitations': ['Human review required for complete scalp/body and neutral A-pose.',
                  'Anchor alignment preserves silhouette; it does not repair a badly designed garment.',
                  'Nearest-surface weights and a motion render do not prove collision-free animation.',
                  'Source UVs and morph targets are retained; front face art is not a UV texture.']}
    # Paths stay in the private worker input, never the public record.
    if kind == 'assembly':
        result['fit']['parts'] = [{k: p[k] for k in ('id', 'slot', 'sha256')} for p in payload['parts']]
    files = ['model.glb', 'master.blend', 'front.png', 'side.png', 'back.png', 'motion.png']
    if kind == 'part':
        files.append('part.glb')
        part_doc, _ = parse_glb((output/'part.glb').read_bytes(), strict=True)
        result['part_materials'] = material_metadata(part_doc)
        files.extend(uv_templates(output/'part.glb', output, 'part'))
    elif kind == 'base':
        files.extend(uv_templates(output/'model.glb', output, 'body'))
    (output/'complete.json').write_text(json.dumps({'input_sha256': sha(output/'input.json'),
        'files': {name: sha(output/name) for name in files}, 'result': result}), encoding='utf-8')


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8')))
