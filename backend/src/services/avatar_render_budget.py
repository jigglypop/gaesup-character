"""Local runtime derivatives; provider source GLBs remain untouched."""
import bpy
import bmesh

PART_TRIANGLES = {'body': 8000, 'hair': 3500, 'hat': 1600, 'top': 2000, 'bottom': 1600, 'shoes': 1600,
                  'weapon': 1200, 'tool': 1000, 'glasses': 500}
TEXTURE_EDGE = 1024


def optimize_part(meshes, slot):
    def triangles(obj):
        return sum(max(0, len(p.vertices)-2) for p in obj.data.polygons)
    before = sum(triangles(obj) for obj in meshes)
    target = PART_TRIANGLES.get(slot, 2000)
    texture_count = 0
    resized = {}
    # Each object receives its share of the slot budget. Simplify BEFORE skin
    # transfer, so new vertices receive weights on the exact final geometry.
    for obj in meshes:
        count = triangles(obj)
        if before > target and count > 12 and not obj.data.shape_keys:
            # GLB often duplicates vertices at UV/normal seams. Collapsing these
            # disconnected triangles independently tears the surface. Weld only
            # coincident positions; UV coordinates remain per-corner loop data.
            mesh = bmesh.new()
            mesh.from_mesh(obj.data)
            extent = max(obj.dimensions)
            bmesh.ops.remove_doubles(mesh, verts=list(mesh.verts), dist=max(extent*1e-6, 1e-8))
            mesh.to_mesh(obj.data); mesh.free(); obj.data.update()
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True); bpy.context.view_layer.objects.active = obj
            modifier = obj.modifiers.new('RuntimeTriangleBudget', 'DECIMATE')
            modifier.ratio = target/before
            modifier.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
        for material in obj.data.materials:
            if not material or not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if node.type != 'TEX_IMAGE' or node.image is None:
                    continue
                image = node.image
                width, height = image.size
                if max(width, height) > TEXTURE_EDGE:
                    derivative = resized.get(image.as_pointer())
                    if derivative is None:
                        derivative = image.copy()
                        scale = TEXTURE_EDGE/max(width, height)
                        derivative.scale(max(1, round(width*scale)), max(1, round(height*scale)))
                        derivative.pack()
                        resized[image.as_pointer()] = derivative
                        texture_count += 1
                    node.image = derivative
    after = sum(triangles(obj) for obj in meshes)
    return {'source_triangles': before, 'runtime_triangles': after, 'target_triangles': target,
            'texture_max_edge': TEXTURE_EDGE, 'resized_textures': texture_count,
            'budget_met': after <= target, 'source_files_preserved': True}
