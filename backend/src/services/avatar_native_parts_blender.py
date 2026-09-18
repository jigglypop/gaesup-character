"""Local fitting candidates on the original Meshy skeleton; never a visual approval."""
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.services.avatar_standard_blender import (
    load, skeleton, body_meshes, bounds, bind, export, sha,
    camera_setup, render,
)
from src.services.glb import parse_glb
from src.services.avatar_fit_geometry import measured_fit, normalize_body, body_targets, fit_shoes, clearance, place, slim_base_body, bind_body_head
from src.services.avatar_body_layers import (
    mark_body_coverage, hide_covered_materials, restore_covered_materials, strip_covered_primitives,
)
from src.services.avatar_head_geometry import headwear_palette, prepare_rear_hair, fit_hat, fit_hair, expand_hair, head_preview_body, whiten_base_body, seat_legacy_hair_roots
from src.services.avatar_arm_geometry import fit_sleeves, t_rest_pose


def run(payload):
    output = Path(payload['output'])
    if sha(payload['source']) != payload['source_sha256']:
        raise ValueError('Body source changed')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objects = load(payload['source']); rig = skeleton(objects)
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
    body = body_meshes(objects, rig)
    spec = payload['production_spec']
    fitting = spec['fitting']
    normalization = normalize_body(objects, body, fitting['bounds']['body'])
    head_binding = bind_body_head(body, rig, spec)
    targets, shoe_targets = body_targets(body, rig, spec)
    # Include the metric parent in every export so separately loaded parts and
    # the body retain the same scaled skeleton and animation coordinate frame.
    metric_frame = bpy.data.objects['FactoryMetricFrame']
    reports, fitted = [], []
    body_names = []
    for i, obj in enumerate(body):
        obj.name = f'body_{i}'; obj['part_role'] = 'body'; body_names.append(obj.name)
    imported = {}
    for part in payload['parts']:
        if sha(part['path']) != part['sha256']:
            raise ValueError('Part source changed')
        additions = load(part['path'])
        meshes = [o for o in additions if o.type == 'MESH']
        if not meshes or any(o.type == 'ARMATURE' for o in additions):
            raise ValueError('Expected an unrigged generated part')
        imported[part['slot']] = meshes
    hat_palette = headwear_palette(imported.get('hat', []))
    for part in payload['parts']:
        slot = part['slot']; meshes = imported[slot]
        if slot == 'shoes':
            measurement = fit_shoes(meshes, shoe_targets)
            transform, anchors = Matrix.Identity(4), []
        elif slot == 'hat':
            transform, anchors, measurement = fit_hat(meshes, targets[slot], fitting.get('hat_width_scale', 1))
        elif slot == 'hair':
            transform, anchors, measurement = fit_hair(meshes, targets[slot], spec)
        else:
            transform, anchors, measurement = measured_fit(meshes, targets[slot])
        rigid = slot in ('hair', 'head', 'hairBack', 'hairFront', 'hat')
        contract = {'anchors': anchors, 'max_anchor_error_m': .0001,
                    'binding': 'rigid' if rigid else 'transfer', 'bone': 'Head',
                    'slot': slot, 'max_transfer_distance_m': None}
        place(meshes, transform)
        if slot == 'top':
            measurement['sleeves'] = fit_sleeves(meshes, rig, spec)
        head_preparation = prepare_rear_hair(meshes, body, hat_palette, spec) if slot == 'hairBack' else None
        if slot in ('hairBack', 'hairFront'):
            expand_hair(meshes, spec)
        if slot in fitting.get('garment_margin_m', {}):
            # Keep the generated garment's volume and folds. Vertex projection
            # onto the body turns loose sleeves and hems into a skin-tight shell.
            adjustment = {'method': 'loose_fit_no_surface_projection',
                          'body_margin_xz_m': fitting['garment_margin_m'][slot],
                          'adjusted_vertices': 0, 'maximum_adjustment_m': 0.0}
        elif slot in ('hair', 'head', 'hairFront', 'hairBack'):
            adjustments = [clearance([obj], body, fitting.get('scalp_clearance_m', .003) if obj.get('scalp_backing')
                                    else fitting.get('hair_clearance_m', .025)) for obj in meshes]
            adjustment = {'adjusted_vertices': sum(a['adjusted_vertices'] for a in adjustments),
                          'maximum_adjustment_m': max(a['maximum_adjustment_m'] for a in adjustments)}
        else:
            adjustment = clearance(meshes, body, spec['tolerances']['clearance_m'],
                spec['tolerances']['max_surface_adjustment_m'] if slot == 'hat' else None)
        if slot in ('hairBack', 'hairFront') and 'hat' in imported:
            seat_legacy_hair_roots(meshes, body, spec)
        # Transfer weights only after the final garment size has been applied.
        report = bind(meshes, body, rig, contract, transform=Matrix.Identity(4))
        report['measurement'] = measurement
        report['clearance'] = adjustment
        if head_preparation is not None:
            report['head_preparation'] = head_preparation
        a, b = bounds(meshes)
        report['fitted_bounds_gltf'] = [[a.x, a.z, -b.y], [b.x, b.z, -a.y]]
        names = []
        for i, obj in enumerate(meshes):
            obj.name = f'{slot}_{i}'; obj['part_role'] = slot; names.append(obj.name)
        reports.append({'slot': slot, 'source_sha256': part['sha256'], 'objects': names,
                        'anchors': anchors, **report})
        fitted += meshes
    # Hair and hat retain independent meshes, files and equip slots. A complete
    # hairstyle comes from its own generation job, never from joining headwear.
    # Keep the original skin as the weight-transfer source, then slim the core
    # for display. This leaves all skeleton transforms and transferred weights intact.
    base_shape = slim_base_body(body, rig, spec)
    base_shape['head_binding'] = head_binding
    base_shape['appearance'] = whiten_base_body(body, spec)
    rest_pose = t_rest_pose(rig, [*body, *fitted])
    garment_meshes = {part['slot']: [obj for obj in fitted if obj['part_role'] == part['slot']]
                     for part in reports}
    covered_materials, coverage, crop_lines = mark_body_coverage(body, garment_meshes, rig, spec)
    hidden = hide_covered_materials(covered_materials)
    camera, view_center = camera_setup(spec['body_height_m'])
    directions = [('front', (0, -1, 0)), ('side', (1, 0, 0)), ('back', (0, 1, 0)), ('opposite', (-1, 0, 0))]
    for view, direction in directions:
        render(output/f'{view}.png', camera, view_center, direction, 800)
    # Persist the actual geometry from all four sides, including isolated head
    # parts. These are inspection views, never an automatic quality verdict.
    detail_files = []
    original_scale = camera.data.ortho_scale
    detail_center = Vector((0, 0, spec['body_height_m']*.74))
    camera.data.ortho_scale = spec['body_height_m']*1.05
    collar_height = next((line['point_m'][1] for line in crop_lines if line['name'] == 'collar'), spec['anchors']['neck'][1])
    preview_body = head_preview_body(body, collar_height)
    for obj in body:
        obj.hide_render = True
    visibility = {obj: obj.hide_render for obj in fitted}
    for group, slots in (('head', ('hair', 'head', 'hairFront', 'hairBack', 'hat')),
                         ('hair', ('hair', 'hairFront', 'hairBack')), ('hat', ('hat',))):
        if not any(obj['part_role'] in slots for obj in fitted):
            continue
        for obj in fitted:
            obj.hide_render = obj['part_role'] not in slots
        for view, direction in directions:
            name = f'{group}-{view}.png'
            render(output/name, camera, detail_center, direction, 600)
            detail_files.append(name)
    for obj, hidden_before in visibility.items():
        obj.hide_render = hidden_before
    for obj in preview_body:
        bpy.data.objects.remove(obj, do_unlink=True)
    for obj in body:
        obj.hide_render = False
    camera.data.ortho_scale = original_scale
    restore_covered_materials(hidden)
    for obj in fitted:
        obj.hide_render = True
    for view, direction in directions:
        name = f'body-{view}.png'
        render(output/name, camera, view_center, direction, 600)
        detail_files.append(name)
    for obj, hidden_before in visibility.items():
        obj.hide_render = hidden_before
    rig.data.pose_position = 'POSE'
    export(output/'model.glb', [metric_frame, rig, *body, *fitted])
    strip_covered_primitives(output/'model.glb')
    for role, meshes in [('body', body), *[(p['slot'], [o for o in fitted if o['part_role'] == p['slot']]) for p in reports]]:
        export(output/f'{role}.glb', [metric_frame, rig, *meshes])
    bpy.context.scene.frame_set(0); bpy.context.view_layer.update()
    hide_covered_materials(covered_materials)
    render(output/'motion.png', camera, view_center, (0, -1, 0), 800)
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'master.blend'))
    doc, _ = parse_glb((output/'model.glb').read_bytes(), strict=True)
    parts = [{'slot': 'body', 'objects': body_names}, *reports]
    for part in parts:
        part['nodes'] = [i for i, n in enumerate(doc['nodes']) if n.get('name') in part['objects'] and 'mesh' in n]
        if not part['nodes'] or any('skin' not in doc['nodes'][i] for i in part['nodes']):
            raise ValueError('Missing skinned part')
    result = {'parts': parts, 'bone_count': len(rig.data.bones),
              'production_spec_sha256': spec['sha256'], 'normalization': normalization,
              'fitting_revision': fitting['revision'], 'fitting_targets': targets,
              'body_coverage_faces': coverage,
              'body_crop_lines': crop_lines,
              'base_body_shape': base_shape,
              'rest_pose': rest_pose,
              'source_sha256': payload['source_sha256'],
              'visual_review': 'required', 'origin': 'generated_parts_fitted_to_meshy_body',
              'limitations': ['Measured fitting and surface weight transfer require visual review.',
                              'Independently generated parts are not a segmentation of the original image or mesh.']}
    files = ['model.glb', 'master.blend', 'front.png', 'side.png', 'back.png', 'opposite.png', 'motion.png'] + [f'{p["slot"]}.glb' for p in parts] + detail_files
    (output/'complete.json').write_text(json.dumps({'input_sha256': sha(output/'input.json'),
        'files': {name: sha(output/name) for name in files}, 'result': result}), encoding='utf8')


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8')))
