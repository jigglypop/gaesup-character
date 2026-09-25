"""Measured wig seating and image-supported repair of missing rear surfaces.

Runs inside Blender. Fitted strands, UVs and materials remain intact; a derived
rear backing is a separate mesh with its own provenance in the fitting receipt.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from src.services.avatar_fit_geometry import bounds, head_region, place


class _Surface:
    """Keep large provider meshes in Blender instead of copying every triangle."""
    def __init__(self, meshes):
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        self.items = []
        for obj in meshes:
            matrix = obj.matrix_world.copy()
            inverse = matrix.inverted()
            tree = BVHTree.FromObject(obj, graph)
            self.items.append((tree, matrix, inverse, inverse.transposed().to_3x3()))

    def cast(self, origin, direction):
        nearest = None
        for tree, matrix, inverse, normals in self.items:
            local_direction = (inverse.to_3x3() @ direction).normalized()
            point, normal, _, _ = tree.ray_cast(inverse @ origin, local_direction)
            if point is None:
                continue
            world = matrix @ point
            distance = (world-origin).length
            if nearest is None or distance < nearest[2]:
                nearest = world, (normals @ normal).normalized(), distance
        return nearest


def fit_hair_cavity(meshes, body, rig, spec):
    """Seat the inner hair surface with one uniform correction, before clearance.

    Outer locks do not measure a head cavity. Use rays through the actual skull
    and the first hair surface, excluding lower front bangs and missing rays.
    A bounded correction preserves the design when the source is not a wig.
    """
    lo, hi, collar = head_region(body, rig, spec)
    center = (lo+hi)/2
    center.z = (max(lo.z, collar)+hi.z)/2
    skull, hair = _Surface(body), _Surface(meshes)
    clearance = spec['fitting'].get('scalp_clearance_m', .003)
    ratios = []
    sectors = set()
    for elevation in (.05, .3, .55, .8):
        horizontal = math.sqrt(1-elevation*elevation)
        for step in range(24):
            angle = step*math.tau/24
            ray = Vector((math.sin(angle)*horizontal, math.cos(angle)*horizontal, elevation))
            if ray.y < -.25 and elevation < .75:
                continue
            skin_hit, hair_hit = skull.cast(center, ray), hair.cast(center, ray)
            if skin_hit is None or hair_hit is None or hair_hit[2] <= 1e-8:
                continue
            ratio = (skin_hit[2]+clearance)/hair_hit[2]
            # Interior fragments are not the cavity. Keep their exclusion visible
            # in the receipt through the valid sample count, not a pass/fail gate.
            if .5 <= ratio <= 2:
                ratios.append(ratio)
                sectors.add(step//6)
    report = {'method': 'sampled_inner_hair_cavity_v3', 'samples': len(ratios),
              'sectors': len(sectors), 'scale': 1., 'center_blender': list(center),
              'source_proportions_preserved': True}
    if len(ratios) < 12 or len(sectors) < 3:
        return {**report, 'reason': 'insufficient_cavity_surface'}
    requested = max(1., float(np.percentile(ratios, 90)))
    limit = float(spec['fitting'].get('hair_cavity_scale_limit', 1.25))
    scale = min(requested, limit)
    report.update(requested_scale=requested, scale=scale, scale_limit=limit,
                  limited=requested > limit)
    if scale > 1.0001:
        place(meshes, Matrix.Translation(center) @ Matrix.Scale(scale, 4) @ Matrix.Translation(-center))
    return report


def _reference(path):
    image = bpy.data.images.load(path, check_existing=False)
    width, height = image.size
    values = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(values)
    rgba = values.reshape(height, width, image.channels)
    # Without a transparent reference, hair cannot be distinguished from a face
    # or background. Do not synthesize a cap from an opaque rectangle.
    if image.channels < 4 or not np.any(rgba[:, :, 3] < .1):
        bpy.data.images.remove(image)
        return None
    occupied = rgba[:, :, 3] >= .8
    ys, xs = np.where(occupied)
    if len(xs) < 16:
        bpy.data.images.remove(image)
        return None
    return image, occupied, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def repair_hair_backing(meshes, body, rig, spec, image_paths, *, shared_canvas=False):
    """Bridge a missing rear surface where the accepted rear image contains hair.

    A projected rear image supplies the strand color/texture. Geometry follows
    the measured rear head surface, with a small clearance and overlap beneath
    existing strands. V4 extends the backing to the reference silhouette below
    the skull; it does not claim to recover individual missing locks.
    """
    extended = spec['fitting'].get('hair_rear_surface') == 'reference-silhouette-v4'
    report = {'method': 'reference_rear_surface_v4' if extended else 'reference_backed_rear_roots_v3', 'added_faces': 0,
              'input_strands_preserved': True, 'body_geometry_preserved': True}
    path = (image_paths or {}).get('back')
    if not path:
        return {**report, 'reason': 'rear_reference_unavailable'}
    reference = _reference(path)
    if reference is None:
        return {**report, 'reason': 'rear_reference_alpha_unavailable'}
    image, mask, (px0, py0, px1, py1) = reference
    width, height = image.size
    lo, hi, collar = head_region(body, rig, spec)
    hair_lo, hair_hi = bounds(meshes)
    floor = hair_lo.z if extended else max(lo.z, collar, hair_lo.z)
    center = (lo+hi)/2
    skull, hair = _Surface(body), _Surface(meshes)
    clearance = max(.001, float(spec['fitting'].get('scalp_clearance_m', .003)))
    if hi.z <= floor or hair_hi.x-hair_lo.x <= 1e-8:
        bpy.data.images.remove(image)
        return {**report, 'reason': 'no_rear_head_region'}
    # Uploaded tiles share pixel scale but have no metre origin. Register the
    # rear image uniformly to the already seated hair, anchored at its crown.
    # Authored metric images retain their original shared canvas coordinates.
    pixel_scale = (px1-px0)/max(hair_hi.x-hair_lo.x, 1e-8)
    canvas = spec['canvas']
    use_canvas = bool(shared_canvas and width == canvas['width'] and height == canvas['height'])
    if extended:
        # Include the whole accepted silhouette even when the provider omitted
        # its lower rear. Register it at the same pixel scale, never stretch it.
        reference_floor = ((py0-(height-1-canvas['sole_y']))/canvas['pixels_per_metre']
                           if use_canvas else hair_hi.z-(py1-py0)/pixel_scale)
        floor = min(floor, reference_floor)

    def project(x, z):
        if use_canvas:
            return (canvas['center_x']-x*canvas['pixels_per_metre'],
                    height-1-canvas['sole_y']+z*canvas['pixels_per_metre'])
        return (px1-(x-hair_lo.x)*pixel_scale,
                py1-(hair_hi.z-z)*pixel_scale)

    columns, rows = spec['fitting'].get('hair_backing_grid', [81, 97])
    x_min, x_max = (hair_lo.x, hair_hi.x) if extended else (lo.x, hi.x)
    top = hair_hi.z if extended else hi.z
    radius_x = max((hi.x-lo.x)/2, (hair_hi.x-hair_lo.x)*.5, 1e-6)
    radius_y = max((hi.y-lo.y)/2, 1e-6)
    radius_z = max(top-center.z, 1e-6)
    points, uvs, missing = {}, {}, set()
    lower_samples = 0
    origin_y = max(hi.y, hair_hi.y)+(hi-lo).length
    for row, z in enumerate(np.linspace(floor, top, rows)):
        for col, x in enumerate(np.linspace(x_min, x_max, columns)):
            px, py = project(float(x), float(z))
            ix, iy = round(px), round(py)
            # One-pixel inset avoids projecting transparent border RGB.
            if (ix < 1 or iy < 1 or ix >= width-1 or iy >= height-1
                    or not mask[iy-1:iy+2, ix-1:ix+2].all()):
                continue
            origin = Vector((x, origin_y, z))
            hit = skull.cast(origin, Vector((0, -1, 0)))
            if (hit is not None and z >= max(lo.z, collar)
                    and hit[0].y >= center.y and hit[1].y > .1):
                point = hit[0]+hit[1]*clearance
            elif extended:
                # The old root-only patch stopped at the neck and never filled
                # the absent rear of a bob. Continue the measured rear curvature
                # down through the opaque reference silhouette, keeping every
                # transparent opening and all original strands. Never cross the
                # head centre toward the face. This is a derived curved surface,
                # not a claim to recover the provider's original strand geometry.
                horizontal = min(.98, ((x-center.x)/radius_x)**2)
                upper = (max(0., z-center.z)/radius_z)**2
                depth = radius_y*math.sqrt(max(.0025, 1-horizontal-upper))
                point = Vector((x, center.y+depth+clearance, z))
                lower_samples += int(z < max(lo.z, collar))
            else:
                continue
            hair_hit = hair.cast(origin, Vector((0, -1, 0)))
            index = (row, col)
            points[index] = point
            # Normal offset changes X/Z as well; project the final vertex.
            u, v = project(point.x, point.z)
            uvs[index] = ((u+.5)/width, (v+.5)/height)
            if hair_hit is None or hair_hit[0].y < point.y-clearance*.25:
                missing.add(index)
    # Extend two cells beneath surrounding source strands to avoid a hard gap.
    support = {index for row, col in missing for dy in range(-2, 3) for dx in range(-2, 3)
               if (index := (row+dy, col+dx)) in points}
    faces = []
    for row in range(rows-1):
        for col in range(columns-1):
            face = ((row, col), (row+1, col), (row+1, col+1), (row, col+1))
            if all(index in support for index in face):
                faces.append(face)
    if not faces:
        bpy.data.images.remove(image)
        return {**report, 'reason': 'no_supported_rear_gap', 'exposed_samples': len(missing)}
    used = sorted({index for face in faces for index in face})
    indices = {index: i for i, index in enumerate(used)}
    mesh = bpy.data.meshes.new('HairRearRootBacking')
    mesh.from_pydata([points[index] for index in used], [],
                     [tuple(indices[index] for index in face) for face in faces])
    mesh.update()
    uv = mesh.uv_layers.new(name='RearReferenceUV')
    for polygon in mesh.polygons:
        polygon.use_smooth = True
        for loop_index in polygon.loop_indices:
            uv.data[loop_index].uv = uvs[used[mesh.loops[loop_index].vertex_index]]
    material = bpy.data.materials.new('HairRearReference')
    material.use_nodes = True
    material.use_backface_culling = False
    shader = next(node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
    shader.inputs['Roughness'].default_value = .65
    texture = material.node_tree.nodes.new('ShaderNodeTexImage')
    texture.image = image
    texture.extension = 'EXTEND'
    texture_edge = int(spec.get('runtime', {}).get('texture_max_edge', max(width, height)))
    if max(width, height) > texture_edge:
        scale = texture_edge/max(width, height)
        image.scale(max(1, round(width*scale)), max(1, round(height*scale)))
    image.pack()
    material.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
    mesh.materials.append(material)
    obj = bpy.data.objects.new('HairRearRootBacking', mesh)
    obj['scalp_backing'] = True
    obj['derived_from'] = 'accepted_rear_reference_and_measured_head'
    bpy.context.scene.collection.objects.link(obj)
    meshes.append(obj)
    return {**report, 'added_faces': len(faces), 'added_vertices': len(used),
            'exposed_samples': len(missing), 'source_view': 'back',
            'lower_reference_samples': lower_samples,
            'projection': 'shared_canvas' if use_canvas else 'uniform_crown_registration',
            'source_texture_size_px': [width, height], 'texture_size_px': list(image.size),
            'clearance_m': clearance,
            'limitation': ('Missing rear surface follows the reference silhouette and measured head curvature; source strands are retained.'
                          if extended else 'Rear root backing is reconstructed; hanging strands remain the source mesh.')}
