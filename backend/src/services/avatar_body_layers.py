"""Crop the base layer at garment openings; retain every face for unequipping."""
import bmesh
import bpy
from mathutils import Vector

from src.services.avatar_fit_geometry import bounds
from src.services.avatar_standard_blender import blender_to_gltf
from src.services.glb import parse_glb, build_glb


def crop_regions(garments, rig, spec):
    settings = spec['fitting'].get('body_crop', {})
    inset = settings.get('opening_inset_m', .008)
    wrist_inset = settings.get('wrist_inset_m', .006)
    regions, lines = {}, []

    def joint(name):
        bone = rig.data.bones.get(name)
        return rig.matrix_world @ bone.head_local if bone else None

    def horizontal(name, height):
        lines.append((name, Vector((0, 0, height)), Vector((0, 0, 1))))

    for slot in ('hair', 'head'):
        if garments.get(slot):
            regions[slot] = {'scalp': spec['body_height_m']*.90}
            horizontal('scalp_under_'+slot, regions[slot]['scalp'])
    if garments.get('top'):
        lo, hi = bounds(garments['top'])
        neck = joint('neck') or joint('Neck')
        shoulders = [p for p in (joint('LeftArm'), joint('RightArm')) if p is not None]
        collar = neck.z if neck is not None else spec['anchors']['neck'][1]
        if shoulders:
            collar = max(collar, sum(p.z for p in shoulders)/len(shoulders)
                         + (spec['anchors']['neck'][1]-spec['anchors']['shoulder_left'][1])*.5)
        regions['top'] = {'hem': lo.z+inset, 'collar': min(hi.z-inset, collar), 'wrists': {}}
        regions['top']['fabric_collar'] = hi.z-inset
        horizontal('top_hem', regions['top']['hem'])
        horizontal('collar', regions['top']['collar'])
        horizontal('base_fabric_collar', regions['top']['fabric_collar'])
        for side in ('Left', 'Right'):
            wrist, elbow = joint(side+'Hand'), joint(side+'ForeArm')
            if wrist is not None and elbow is not None and (elbow-wrist).length > 1e-6:
                inward = (elbow-wrist).normalized()
                cut = wrist+inward*wrist_inset
                regions['top']['wrists'][side] = (cut, inward, elbow.x)
                lines.append((side.lower()+'_cuff', cut, inward))
    if garments.get('bottom'):
        lo, hi = bounds(garments['bottom'])
        regions['bottom'] = {'waist': hi.z-inset, 'hem': lo.z+inset, 'ankles': {}}
        horizontal('waist', regions['bottom']['waist'])
        horizontal('bottom_hem', regions['bottom']['hem'])
        for side in ('Left', 'Right'):
            ankle = joint(side+'Foot')
            if ankle is not None:
                # Crop the blue trousers through the shin to the shoe opening.
                # The exposed foot remains in body.glb when shoes are removed.
                regions['bottom']['ankles'][side] = ankle.z+inset
                horizontal(side.lower()+'_ankle', ankle.z+inset)
    if garments.get('shoes'):
        _, hi = bounds(garments['shoes'])
        regions['shoes'] = {'rim': hi.z-inset}
        horizontal('shoe_rim', regions['shoes']['rim'])
    return regions, lines


def split_crop_lines(obj, lines):
    """Insert real cut edges with interpolated UVs and deform weights, no deletion."""
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    inverse = obj.matrix_world.inverted()
    normal_transform = obj.matrix_world.to_3x3().transposed()
    mesh = bmesh.new()
    try:
        mesh.from_mesh(obj.data)
        for _, point, normal in lines:
            bmesh.ops.bisect_plane(mesh, geom=[*mesh.verts, *mesh.edges, *mesh.faces],
                dist=1e-6, plane_co=inverse @ point,
                plane_no=(normal_transform @ normal).normalized(),
                clear_inner=False, clear_outer=False)
        mesh.to_mesh(obj.data)
    finally:
        mesh.free()
    obj.data.update()


def cropped_slots(point, bone, regions, *, is_fabric=False):
    # These are anatomical cut regions, independent of the garment's ray hits
    # or width. A protruding blue shoulder must be cropped as well.
    slots = set()
    for slot in ('hair', 'head'):
        region = regions.get(slot)
        if region and point.z >= region['scalp']:
            slots.add(slot)
    if not is_fabric and any(name in bone for name in ('head', 'neck')):
        return slots
    hand = any(name in bone for name in ('hand', 'finger', 'thumb', 'index', 'middle', 'ring', 'pinky'))
    foot = any(name in bone for name in ('foot', 'toe'))
    arm = any(name in bone for name in ('arm', 'shoulder'))
    if hand and not is_fabric:
        return slots
    top = regions.get('top')
    if top and not foot and top['hem'] <= point.z <= top['fabric_collar' if is_fabric else 'collar']:
        inside_cuff = True
        for side, (cut, inward, elbow_x) in top['wrists'].items():
            lateral = point.x > elbow_x if side == 'Left' else point.x < elbow_x
            if lateral and (point-cut).dot(inward) < 0:
                inside_cuff = False
        if inside_cuff:
            slots.add('top')
    bottom = regions.get('bottom')
    if bottom and (not foot or is_fabric) and not arm and not hand and point.z <= bottom['waist']:
        side = 'Left' if point.x >= 0 else 'Right'
        if point.z >= max(bottom['hem'], bottom['ankles'].get(side, 0)):
            slots.add('bottom')
    shoes = regions.get('shoes')
    if shoes and point.z <= shoes['rim'] and (foot or (not arm and not hand)):
        slots.add('shoes')
    return slots


def mark_body_coverage(body, garments, rig, spec):
    from src.services.avatar_head_geometry import underlayer_faces
    regions, lines = crop_regions(garments, rig, spec)
    materials, face_counts = [], {}
    for obj in body:
        split_crop_lines(obj, lines)
        fabric = underlayer_faces([obj]).get(obj, set())
        if not obj.data.materials:
            material = bpy.data.materials.new('BodyBase')
            material.use_nodes = True
            obj.data.materials.append(material)
        names = {g.index: g.name.lower() for g in obj.vertex_groups}
        variants = {}
        for polygon in obj.data.polygons:
            weights = {}
            for index in polygon.vertices:
                for group in obj.data.vertices[index].groups:
                    weights[group.group] = weights.get(group.group, 0)+group.weight
            bone = names.get(max(weights, key=weights.get), '') if weights else ''
            slots = tuple(sorted(cropped_slots(obj.matrix_world @ polygon.center, bone, regions,
                                              is_fabric=polygon.index in fabric)))
            if not slots:
                continue
            key = polygon.material_index, slots
            if key not in variants:
                original = obj.data.materials[polygon.material_index]
                if original is None:
                    original = bpy.data.materials.new('BodyBase')
                    original.use_nodes = True
                    obj.data.materials[polygon.material_index] = original
                material = original.copy()
                material.name = f'{original.name}_under_{"_".join(slots)}'
                material['hidden_by_slots'] = '+'.join(slots)
                obj.data.materials.append(material)
                variants[key] = len(obj.data.materials)-1
                materials.append(material)
            polygon.material_index = variants[key]
            face_counts['+'.join(slots)] = face_counts.get('+'.join(slots), 0)+1
    return materials, face_counts, [
        {'name': name, 'point_m': blender_to_gltf(point), 'normal': blender_to_gltf(normal)}
        for name, point, normal in lines]


def hide_covered_materials(materials):
    """Render the all-equipped outfit; body.glb keeps opaque reversible patches."""
    changes = []
    for material in materials:
        if not material.use_nodes:
            continue
        nodes, links = material.node_tree.nodes, material.node_tree.links
        output = next((node for node in nodes if node.type == 'OUTPUT_MATERIAL' and node.is_active_output), None)
        if output is None:
            continue
        socket = output.inputs['Surface']
        previous = [link.from_socket for link in socket.links]
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        for link in list(socket.links):
            links.remove(link)
        links.new(transparent.outputs[0], socket)
        changes.append((material, transparent, socket, previous))
    return changes


def restore_covered_materials(changes):
    for material, transparent, socket, previous in changes:
        material.node_tree.nodes.remove(transparent)
        for source in previous:
            material.node_tree.links.new(source, socket)


def strip_covered_primitives(path):
    """The full-outfit export omits covered base faces without changing skins."""
    doc, binary = parse_glb(path.read_bytes(), strict=True)
    hidden = {i for i, m in enumerate(doc.get('materials', [])) if m.get('extras', {}).get('hidden_by_slots')}
    emptied = set()
    for index, mesh in enumerate(doc.get('meshes', [])):
        mesh['primitives'] = [p for p in mesh['primitives'] if p.get('material') not in hidden]
        if not mesh['primitives']:
            emptied.add(index)
    # glTF forbids empty primitive arrays, even for unreferenced meshes.
    mapping = {}; meshes = []
    for index, mesh in enumerate(doc.get('meshes', [])):
        if index not in emptied:
            mapping[index] = len(meshes); meshes.append(mesh)
    doc['meshes'] = meshes
    empty_nodes = set()
    for index, node in enumerate(doc.get('nodes', [])):
        if node.get('mesh') in emptied:
            node.pop('mesh'); node.pop('skin', None)
            node.pop('weights', None); empty_nodes.add(index)
        elif 'mesh' in node:
            node['mesh'] = mapping[node['mesh']]
    for animation in doc.get('animations', []):
        animation['channels'] = [channel for channel in animation['channels']
                                 if not (channel['target'].get('node') in empty_nodes
                                         and channel['target']['path'] == 'weights')]
    if 'animations' in doc:
        doc['animations'] = [animation for animation in doc['animations'] if animation['channels']]
    path.write_bytes(build_glb(doc, binary))
