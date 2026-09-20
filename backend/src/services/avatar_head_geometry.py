"""Head-part preparation: preserve hat proportions and separate duplicated headwear."""
import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from src.services.avatar_fit_geometry import bounds, head_region, place, surface, target_box


def face_samples(meshes):
    samples = []
    pixels = {}
    for obj in meshes:
        uv = obj.data.uv_layers.active
        if uv is None:
            continue
        for face in obj.data.polygons:
            material = obj.data.materials[face.material_index]
            if not material or not material.use_nodes:
                continue
            shader = next((n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            links = shader.inputs['Base Color'].links if shader else []
            node = links[0].from_node if links else None
            if node is None or node.type != 'TEX_IMAGE' or node.image is None:
                continue
            image = node.image
            if image not in pixels:
                values = np.empty(len(image.pixels), dtype=np.float32)
                image.pixels.foreach_get(values)
                pixels[image] = values.reshape(image.size[1], image.size[0], image.channels)
            coord = sum((uv.data[i].uv for i in face.loop_indices), Vector((0, 0)))/len(face.loop_indices)
            x = max(0, min(image.size[0]-1, int(coord.x*image.size[0])))
            y = max(0, min(image.size[1]-1, int(coord.y*image.size[1])))
            color = pixels[image][y, x, :3].astype(float)
            if color.sum() > .05:
                samples.append((obj, face.index, obj.matrix_world @ face.center,
                                color/color.sum(), material, coord.copy()))
    return samples


def headwear_palette(meshes):
    rows = face_samples(meshes)
    return np.median([row[3] for row in rows], axis=0) if rows else None


def underlayer_faces(meshes):
    """Identify fabric, including saved teal sources, without selecting the face."""
    result = {}
    lo, hi = bounds(meshes)
    neck_limit = lo.z+(hi.z-lo.z)*.48
    for obj in meshes:
        for face in obj.data.polygons:
            material = obj.data.materials[face.material_index] if obj.data.materials else None
            if material and material.get('base_underlayer'):
                result.setdefault(obj, set()).add(face.index)
    for obj, index, point, color, _, _ in face_samples(meshes):
        teal = color[1] > color[0]*1.15 and color[2] > color[0]*1.05
        white = max(color)-min(color) < .025
        if point.z < neck_limit and (teal or white):
            result.setdefault(obj, set()).add(index)
    return result


def whiten_base_body(body, spec):
    fabric = underlayer_faces(body)
    material = bpy.data.materials.new('WhiteBaseUnderlayer')
    material.use_nodes = True; material['base_underlayer'] = True
    shader = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = spec['base_body'].get('color_rgba', (.86, .86, .84, 1))
    shader.inputs['Roughness'].default_value = .9
    faces = 0
    for obj, indices in fabric.items():
        obj.data.materials.append(material); index = len(obj.data.materials)-1
        for face_index in indices:
            obj.data.polygons[face_index].material_index = index
            faces += 1
    return {'material': material.name, 'faces': faces, 'color': 'matte_white'}


def prepare_rear_hair(meshes, body, hat_palette, spec):
    """Remove a distinct headwear-colored crown, retaining the saved source GLB."""
    rows = face_samples(meshes)
    report = {'removed_headwear_faces': 0, 'scalp_shell': False}
    if not rows or hat_palette is None:
        return report
    lo, hi = bounds(meshes)
    span = max(hi.z-lo.z, .001)
    hair = [row for row in rows if row[2].z < lo.z+span*.35]
    crown = [row for row in rows if row[2].z > lo.z+span*.85]
    if not hair or not crown:
        return report
    hair_color = np.median([row[3] for row in hair], axis=0)
    crown_color = np.median([row[3] for row in crown], axis=0)
    difference = crown_color-hair_color
    separation = float(np.linalg.norm(difference))
    # A single-color hairstyle has no separable headwear region. Do not cut it.
    if separation < .012 or np.linalg.norm(crown_color-hat_palette) >= np.linalg.norm(hair_color-hat_palette):
        return report
    removed = {}
    for obj, index, point, color, _, _ in rows:
        score = float(np.dot(color-hair_color, difference)/np.dot(difference, difference))
        if point.z > lo.z+span*.36 and score > .48:
            removed.setdefault(obj, set()).add(index)
    for obj, indices in removed.items():
        mesh = bmesh.new()
        try:
            mesh.from_mesh(obj.data); mesh.faces.ensure_lookup_table()
            bmesh.ops.delete(mesh, geom=[mesh.faces[i] for i in indices], context='FACES')
            mesh.to_mesh(obj.data)
        finally:
            mesh.free()
        obj.data.update()
        report['removed_headwear_faces'] += len(indices)
    if not report['removed_headwear_faces']:
        return report
    # The mixed cap/hair crown is not usable hair geometry. Keep the detailed
    # lower locks and extend their roots to the hat seat instead of displaying
    # fragmented cap remnants or a large smooth replacement plate.
    root_line = lo.z+span*.60
    destination = spec['fitting'].get('hat_hairline_m', spec['body_height_m']*.95)
    for obj in meshes:
        mesh = bmesh.new()
        try:
            mesh.from_mesh(obj.data)
            bmesh.ops.bisect_plane(mesh, geom=[*mesh.verts, *mesh.edges, *mesh.faces],
                dist=1e-6, plane_co=Vector((0, 0, root_line)), plane_no=Vector((0, 0, 1)),
                clear_inner=False, clear_outer=True)
            for vertex in mesh.verts:
                vertex.co.z = lo.z+(vertex.co.z-lo.z)*(destination-lo.z)/(root_line-lo.z)
            mesh.to_mesh(obj.data)
        finally:
            mesh.free()
        obj.data.update()
    report['rear_locks_extended_to_m'] = destination
    return report


def fit_hat(meshes, target, width_scale=1.0):
    """Uniformly fit headwear to the measured body head and crown seat."""
    lo, hi = bounds(meshes); a, b = target_box(target)
    scale = (b.x-a.x)/(hi.x-lo.x)*width_scale
    source = Vector(((lo.x+hi.x)/2, (lo.y+hi.y)/2, hi.z))
    destination = Vector(((a.x+b.x)/2, (a.y+b.y)/2, b.z))
    transform = Matrix.Translation(destination) @ Matrix.Scale(scale, 4) @ Matrix.Translation(-source)
    return transform, [], {'method': 'uniform_hat_scale_on_measured_body_head', 'scale': scale,
                           'target_head_width_m': b.x-a.x,
                           'fitted_width_m': (hi.x-lo.x)*scale,
                           'crown_height_m': b.z, 'source_proportions_preserved': True}


def hat_target_over_hair(target, hair, spec):
    """Seat headwear around the upper hairstyle without sizing to hanging locks."""
    a, b = target_box(target)
    hair_lo, hair_hi = bounds(hair)
    seat_height = a.z
    crown = [obj.matrix_world @ vertex.co for obj in hair for vertex in obj.data.vertices
             if (obj.matrix_world @ vertex.co).z >= seat_height]
    if not crown:
        return target, {'method': 'measured_head_fallback', 'seat_height_m': seat_height,
                        'reason': 'no_hair_vertices_above_seat'}
    crown_lo = Vector([min(point[i] for point in crown) for i in range(3)])
    crown_hi = Vector([max(point[i] for point in crown) for i in range(3)])
    authored = spec['fitting']['bounds']
    base_width = max(b.x-a.x, crown_hi.x-crown_lo.x)
    # Both inputs are already measured in the canonical head frame. Applying
    # the legacy hat/hair envelope ratio again shrinks the cap below head width.
    width = base_width
    center_x = (crown_lo.x+crown_hi.x)/2
    crown_rise = max(0., authored['hat'][1][1]-authored['hair'][1][1])
    depth_center = (crown_lo.y+crown_hi.y)/2
    depth = max(b.y-a.y, crown_hi.y-crown_lo.y)
    fitted = [[center_x-width/2, seat_height, -depth_center-depth/2],
              [center_x+width/2, hair_hi.z+crown_rise, -depth_center+depth/2]]
    return fitted, {'method': 'measured_upper_hair_seat',
                    'seat_height_m': seat_height,
                    'hair_crown_bounds_gltf': [[crown_lo.x, crown_lo.z, -crown_hi.y],
                                                [crown_hi.x, crown_hi.z, -crown_lo.y]],
                    'measured_head_width_m': b.x-a.x,
                    'measured_crown_width_m': crown_hi.x-crown_lo.x,
                    'authored_crown_rise_m': crown_rise,
                    'target_width_before_clearance_m': width}


def fit_hair(meshes, target, spec):
    """Uniformly contain the measured head; strand length never sets the scale."""
    lo, hi = bounds(meshes); a, b = target_box(target)
    source_width, source_depth = hi.x-lo.x, hi.y-lo.y
    target_width, target_depth = b.x-a.x, b.y-a.y
    if min(source_width, source_depth, target_width, target_depth) <= 1e-8:
        raise ValueError('Hair has no measurable scalp footprint')
    width_scale = target_width/source_width
    depth_scale = target_depth/source_depth
    # One uniform scale preserves the authored silhouette. The larger required
    # axis keeps the shell outside both measured head axes; bounded clearance
    # handles only local intersections instead of reshaping the whole asset.
    scale = max(width_scale, depth_scale)
    source = Vector(((lo.x+hi.x)/2, (lo.y+hi.y)/2, hi.z))
    destination = Vector(((a.x+b.x)/2, (a.y+b.y)/2, b.z))
    transform = Matrix.Translation(destination) @ Matrix.Scale(scale, 4) @ Matrix.Translation(-source)
    return transform, [], {'method': 'uniform_hair_scale_on_measured_head', 'scale': scale,
                           'width_scale_required': width_scale,
                           'depth_scale_required': depth_scale,
                           'target_head_width_m': target_width,
                           'target_head_depth_m': target_depth,
                           'crown_height_m': b.z, 'source_proportions_preserved': True,
                           'hair_length': spec['fitting'].get('hair_length', 'source')}


def fit_hair_length(meshes, target, spec):
    """Adjust hanging strands below the crown, retaining scalp width and depth."""
    ratio = spec['fitting'].get('hair_length_head_ratio')
    if ratio is None:
        return {'method': 'preserve_source_length'}
    lo, hi = bounds(meshes); a, b = target_box(target)
    source_length, target_length = hi.z-lo.z, b.z-a.z
    if min(source_length, target_length) <= 1e-8:
        raise ValueError('Hair has no measurable length')
    # Keep the crown dome unchanged. Only the lower strands are extended or
    # shortened, with a continuous mapping at the protected scalp boundary.
    protected = min(source_length, target_length)*.35
    shoulder = hi.z-protected
    strand_scale = (target_length-protected)/(source_length-protected)
    for obj in meshes:
        inverse = obj.matrix_world.inverted()
        for vertex in obj.data.vertices:
            point = obj.matrix_world @ vertex.co
            if point.z < shoulder:
                point.z = shoulder-(shoulder-point.z)*strand_scale
                vertex.co = inverse @ point
        obj.data.update()
    return {'method': 'strands_below_fixed_crown', 'head_height_ratio': ratio,
            'source_length_m': source_length, 'target_length_m': target_length,
            'protected_crown_m': protected, 'strand_scale': strand_scale,
            'width_and_depth_preserved': True}


def fit_hair_scalp(meshes, body, rig, spec):
    """Seat existing hair surfaces outside the actual skull without adding faces.

    Outer hair bounds include hanging locks and do not describe its head cavity.
    A small generic clearance cap leaves deeply intersecting scalp vertices inside
    the head. Resolve the full displacement in the skull region; keep the bounded
    correction below the head so long strands retain their authored silhouette.
    """
    head_lo, _, _ = head_region(body, rig, spec)
    tree, _, _ = surface(body)
    minimum = spec['fitting'].get('hair_clearance_m', .025)
    lower_limit = max(minimum, spec['tolerances'].get('max_surface_adjustment_m', .015))
    adjusted = scalp_adjusted = 0
    maximum_applied = 0.
    for obj in meshes:
        inverse = obj.matrix_world.inverted()
        for vertex in obj.data.vertices:
            point = obj.matrix_world @ vertex.co
            hit, normal, _, _ = tree.find_nearest(point)
            if hit is None:
                raise ValueError('Missing head surface')
            signed = (point-hit).dot(normal)
            if signed >= minimum:
                continue
            amount = minimum-signed
            scalp = point.z >= head_lo.z and hit.z >= head_lo.z
            if not scalp:
                amount = min(amount, lower_limit)
            destination = point+normal*amount
            vertex.co = inverse @ destination
            adjusted += 1
            scalp_adjusted += int(scalp)
            maximum_applied = max(maximum_applied, (destination-point).length)
        obj.data.update()
    return {'method': 'measured_skull_surface_fit_v1', 'adjusted_vertices': adjusted,
            'scalp_adjusted_vertices': scalp_adjusted, 'head_floor_m': head_lo.z,
            'maximum_adjustment_m': maximum_applied, 'lower_strand_limit_m': lower_limit,
            'topology_preserved': True, 'uv_preserved': True, 'added_faces': 0}


def seat_legacy_hair_roots(meshes, body, spec):
    """Keep enlarged legacy locks, easing their roots inside the separate hat."""
    lo, hi = bounds(body)
    center = (lo+hi)/2
    rx = (hi.x-lo.x)/2; ry = (hi.y-lo.y)/2
    head_base = spec['anchors']['neck'][1]
    head_center = (hi.z+head_base)/2
    head_radius = (hi.z-head_base)/2
    rim = spec['fitting'].get('hat_hairline_m', 1.14)
    for obj in meshes:
        if obj.get('scalp_backing'):
            continue
        for vertex in obj.data.vertices:
            t = max(0, min(1, (vertex.co.z-(rim-.24))/.24))
            t = t*t*(3-2*t)
            x, y = vertex.co.x-center.x, vertex.co.y-center.y
            crown_fraction = max(0, min(.995, (vertex.co.z-head_center)/max(head_radius, .001)))
            section = (1-crown_fraction*crown_fraction)**.5
            radius = ((x/(rx*section+.035))**2+(y/(ry*section+.035))**2)**.5
            factor = 1-t*(1-min(1, 1/max(radius, 1e-8)))
            vertex.co.x = center.x+x*factor
            vertex.co.y = center.y+y*factor
        obj.data.update()


def expand_hair(meshes, spec):
    x_scale, depth_scale = spec['fitting'].get('hair_volume_scale_xz', (1, 1))
    for obj in meshes:
        if obj.get('scalp_backing'):
            continue
        for vertex in obj.data.vertices:
            vertex.co.x *= x_scale
            vertex.co.y = -.01+(vertex.co.y+.01)*depth_scale
        obj.data.update()


def head_preview_body(body, collar_height):
    copies = []
    for original in body:
        obj = bpy.data.objects.new('HeadViewBase', original.data.copy())
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = original.matrix_world.copy()
        place([obj], Matrix.Identity(4))
        mesh = bmesh.new()
        try:
            mesh.from_mesh(obj.data)
            bmesh.ops.bisect_plane(mesh, geom=[*mesh.verts, *mesh.edges, *mesh.faces],
                dist=1e-6, plane_co=Vector((0, 0, collar_height)), plane_no=Vector((0, 0, 1)),
                clear_inner=True, clear_outer=False)
            mesh.to_mesh(obj.data)
        finally:
            mesh.free()
        obj.data.update(); copies.append(obj)
    return copies
