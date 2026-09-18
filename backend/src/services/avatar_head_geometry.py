"""Head-part preparation: preserve hat proportions and separate duplicated headwear."""
import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from src.services.avatar_fit_geometry import bounds, place, target_box


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
    # The original headwear concealed part of the rear scalp. Rebuild that
    # backing from the common head surface, beneath the retained sculpted locks.
    sample = min(hair, key=lambda row: float(np.linalg.norm(row[3]-hair_color)))
    material, uv_point = sample[4], sample[5]
    for original in body:
        cap = bpy.data.objects.new('RearScalpBacking', original.data.copy())
        bpy.context.scene.collection.objects.link(cap)
        cap.matrix_world = original.matrix_world.copy()
        place([cap], Matrix.Identity(4))
        mesh = bmesh.new()
        try:
            mesh.from_mesh(cap.data)
            for point, normal in ((Vector((0, -.015, 0)), Vector((0, 1, 0))),
                                  (Vector((0, 0, spec['body_height_m']*.5)), Vector((0, 0, 1)))):
                bmesh.ops.bisect_plane(mesh, geom=[*mesh.verts, *mesh.edges, *mesh.faces],
                    dist=1e-6, plane_co=point, plane_no=normal, clear_inner=True, clear_outer=False)
            mesh.normal_update()
            for vertex in mesh.verts:
                vertex.co += vertex.normal*spec['fitting'].get('scalp_clearance_m', .003)
            mesh.to_mesh(cap.data)
        finally:
            mesh.free()
        if not cap.data.polygons:
            bpy.data.objects.remove(cap, do_unlink=True)
            continue
        cap.data.materials.clear(); cap.data.materials.append(material)
        for face in cap.data.polygons:
            face.material_index = 0; face.use_smooth = True
        uv = cap.data.uv_layers.active or cap.data.uv_layers.new()
        for value in uv.data:
            value.uv = uv_point
        cap['scalp_backing'] = True
        cap.data.update(); meshes.append(cap)
        report['scalp_shell'] = True
    return report


def fit_hat(meshes, target, width_scale=1.0):
    """Keep the crown and hanging ears in the source's proportions."""
    lo, hi = bounds(meshes); a, b = target_box(target)
    scale = (b.x-a.x)/(hi.x-lo.x)*width_scale
    source = Vector(((lo.x+hi.x)/2, (lo.y+hi.y)/2, hi.z))
    destination = Vector(((a.x+b.x)/2, (a.y+b.y)/2, b.z))
    transform = Matrix.Translation(destination) @ Matrix.Scale(scale, 4) @ Matrix.Translation(-source)
    return transform, [], {'method': 'uniform_hat_scale', 'scale': scale,
                           'crown_height_m': b.z, 'source_proportions_preserved': True}


def fit_hair(meshes, target, spec):
    """Seat the full hairstyle on the measured head without anisotropic stretch."""
    lo, hi = bounds(meshes); a, b = target_box(target)
    scale = (b.x-a.x)/(hi.x-lo.x)
    if spec['fitting'].get('hair_length_head_ratio') is not None:
        scale = max(scale, (b.z-a.z)/(hi.z-lo.z))
    source = Vector(((lo.x+hi.x)/2, (lo.y+hi.y)/2, hi.z))
    destination = Vector(((a.x+b.x)/2, (a.y+b.y)/2, b.z))
    transform = Matrix.Translation(destination) @ Matrix.Scale(scale, 4) @ Matrix.Translation(-source)
    return transform, [], {'method': 'uniform_hair_scale_on_measured_head', 'scale': scale,
                           'crown_height_m': b.z, 'source_proportions_preserved': True,
                           'hair_length': spec['fitting'].get('hair_length', 'source')}


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
