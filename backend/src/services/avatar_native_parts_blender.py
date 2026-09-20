"""Local fitting candidates on the original Meshy skeleton; never a visual approval."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.services.avatar_standard_blender import (
    load, skeleton, body_meshes, bounds, bind, export, sha,
    camera_setup, render,
)
from src.services.glb import parse_glb
from src.services.avatar_fit_geometry import measured_fit, normalize_body, body_targets, hair_target, headwear_target, clearance, place, slim_base_body, bind_body_head, fit_equipment
from src.services.avatar_shoe_geometry import fit_shoes_rigid, bind_shoes_rigid, finish_shoes_after_pose
from src.services.avatar_equipment import NATIVE_EQUIPMENT as EQUIPMENT
from src.services.avatar_body_layers import (
    mark_body_coverage, hide_covered_materials, restore_covered_materials, strip_covered_primitives,
)
from src.services.avatar_head_geometry import headwear_palette, prepare_rear_hair, fit_hat, hat_target_over_hair, fit_hair, fit_hair_length, fit_hair_scalp, head_preview_body, whiten_base_body, seat_legacy_hair_roots
from src.services.avatar_arm_geometry import fit_sleeves, bind_top_regions, t_rest_pose
from src.services.avatar_render_budget import optimize_part
from src.services.avatar_expression_uv_blender import prepare_expression_uv
from src.services.avatar_garment_geometry import (
    bind_garment_regions, fit_profiled_garment, measure_body_profile,
)


def rig_signature(rig):
    """glTF-stable rest skeleton identity; Blender-inferred tails/roll are excluded."""
    return {bone.name: {
        'parent': bone.parent.name if bone.parent else None,
        'world_rest': tuple(float(value) for row in (rig.matrix_world @ bone.matrix_local) for value in row),
    } for bone in rig.data.bones}


def compatible_rig(source, target, tolerance=1e-4):
    source_bones, target_bones = rig_signature(source), rig_signature(target)
    if source_bones.keys() != target_bones.keys():
        return False
    for name, source_bone in source_bones.items():
        target_bone = target_bones[name]
        if source_bone['parent'] != target_bone['parent']:
            return False
        if any(abs(a-b) > tolerance for a, b in zip(source_bone['world_rest'], target_bone['world_rest'])):
            return False
    return True


def load_prefit_part(part, rig):
    """Attach an already fitted slot to the identical canonical rig without touching its mesh."""
    if sha(part['path']) != part['sha256']:
        raise ValueError('Prefit part changed')
    additions = load(part['path'])
    imported_rigs = [obj for obj in additions if obj.type == 'ARMATURE']
    if len(imported_rigs) != 1:
        raise ValueError('Expected one sealed rigged prefit part')
    imported_rig = imported_rigs[0]
    meshes = body_meshes(additions, imported_rig)
    if not compatible_rig(imported_rig, rig):
        raise ValueError('Prefit part skeleton changed')
    for index, obj in enumerate(meshes):
        modifiers = [modifier for modifier in obj.modifiers if modifier.type == 'ARMATURE']
        if not modifiers or any(modifier.object != imported_rig for modifier in modifiers):
            raise ValueError('Prefit part skin binding changed')
        world = obj.matrix_world.copy()
        for modifier in modifiers:
            modifier.object = rig
        obj.parent = rig
        obj.matrix_world = world
        obj.name = f'{part["slot"]}_{index}'
        obj['part_role'] = part['slot']
    for obj in additions:
        if obj not in meshes:
            bpy.data.objects.remove(obj, do_unlink=True)
    report = deepcopy(part.get('report') or {})
    if not isinstance(report.get('runtime_budget'), dict):
        raise ValueError('Prefit part receipt missing runtime budget')
    report.update(slot=part['slot'], source_sha256=part['sha256'],
                  objects=[obj.name for obj in meshes], origin='reused_fitted_native')
    report.pop('nodes', None)
    return meshes, report


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
    frozen = spec.get('frozen_body', False)
    source_preserved_body = spec.get('base_body', {}).get('source_preserved') is True
    normalization = {'preserved': True} if frozen else normalize_body(objects, body, fitting['bounds']['body'])
    head_binding = ({'preserved': True, 'reason': 'source_body'} if source_preserved_body
                    else {'preserved': True} if frozen else bind_body_head(body, rig, spec))
    body_profile = payload.get('body_profile') or spec.get('body_profile')
    if not body_profile:
        body_profile = measure_body_profile(body, rig, payload['source_sha256'])
    targets, shoe_targets = (deepcopy(fitting['bounds']), deepcopy(fitting['shoe_bounds'])) if frozen else body_targets(body, rig, spec)
    # Frozen bodies still need their current measured head. Persisted envelopes
    # can belong to an older body and must not enlarge a short hairstyle.
    for slot in ('hair', 'hairFront', 'hairBack'):
        if slot in targets:
            targets[slot] = hair_target(body, rig, spec, slot)
    if frozen and 'hat' in targets:
        targets['hat'] = headwear_target(body, rig, spec)
    # Include the metric parent in every export so separately loaded parts and
    # the body retain the same scaled skeleton and animation coordinate frame.
    metric_frame = bpy.data.objects['FactoryMetricFrame']
    reports, fitted = [], []
    body_names = []
    for i, obj in enumerate(body):
        obj.name = f'body_{i}'; obj['part_role'] = 'body'; body_names.append(obj.name)
    imported, imported_additions, prefit_paths = {}, {}, {}
    for part in payload.get('prefit_parts', []):
        meshes, report = load_prefit_part(part, rig)
        imported[part['slot']] = meshes
        prefit_paths[part['slot']] = part['path']
        reports.append(report)
        fitted += meshes
    for part in payload['parts']:
        if sha(part['path']) != part['sha256']:
            raise ValueError('Part source changed')
        additions = load(part['path'])
        meshes = [o for o in additions if o.type == 'MESH']
        if not meshes or any(o.type == 'ARMATURE' for o in additions):
            raise ValueError('Expected an unrigged generated part')
        imported[part['slot']] = meshes
        imported_additions[part['slot']] = additions
    hat_palette = headwear_palette(imported.get('hat', []))
    # Headwear uses the already fitted hairstyle even if the request listed the hat first.
    for part in sorted(payload['parts'], key=lambda part: part['slot'] == 'hat'):
        slot = part['slot']; meshes = imported[slot]
        profiled = part.get('fit_profile') is not None
        garment_report, garment_masks = None, None
        if profiled:
            runtime_budget = {'preserved': True, 'source_mesh_detail': True,
                              'source_uv': True, 'optimization': 'skipped_for_profiled_garment'}
            supplied_source = part['fit_profile'].get('source_sha256')
            if supplied_source and supplied_source != part['sha256']:
                garment_report = {'fit_profile': part['fit_profile'], 'fit_status': 'failed',
                                  'errors': [{'code': 'source_sha256_mismatch',
                                              'message': 'Fit profile belongs to a different source mesh'}],
                                  'source_landmarks': {}, 'target_landmarks': {}, 'coverage': None}
                garment_masks = {obj: {} for obj in meshes}
            else:
                garment_report, garment_masks = fit_profiled_garment(
                    meshes, body, rig, slot, part['fit_profile'], body_profile=body_profile,
                    image_paths=part.get('image_paths'), canvas=spec.get('canvas'))
            if garment_report['fit_status'] != 'fitted' and part.get('fallback_path'):
                for obj in imported_additions.get(slot, []):
                    if obj.name in bpy.data.objects:
                        bpy.data.objects.remove(obj, do_unlink=True)
                fallback_path = part['fallback_path']
                fallback = {'slot': slot, 'path': fallback_path,
                            'sha256': part.get('fallback_sha256') or sha(fallback_path),
                            'report': part.get('fallback_report') or {}}
                meshes, fallback_report = load_prefit_part(fallback, rig)
                fallback_report['fit_status'] = 'fallback_preserved'
                fallback_report['attempted_fit'] = garment_report
                fallback_report['available'] = True
                imported[slot] = meshes
                prefit_paths[slot] = fallback_path
                reports.append(fallback_report); fitted += meshes
                continue
            if garment_report['fit_status'] != 'fitted':
                # Preserve the generated source artifact outside this worker, but
                # never bind or export an ambiguously placed raw mesh as wearable.
                for obj in imported_additions.get(slot, []):
                    if obj.name in bpy.data.objects:
                        bpy.data.objects.remove(obj, do_unlink=True)
                imported[slot] = []
                reports.append({'slot': slot, 'source_sha256': part['sha256'],
                    'objects': [], 'anchors': [], 'available': False,
                    'unavailable_reason': 'garment_fit_incomplete',
                    'measurement': garment_report, 'runtime_budget': runtime_budget,
                    'clearance': {'method': 'not_applied'}, **garment_report})
                continue
            transform, anchors, measurement = Matrix.Identity(4), [], garment_report
        else:
            runtime_budget = ({'preserved': True, 'source_mesh_detail': True, 'source_uv': True,
                               'optimization': 'skipped_for_accepted_meshy_options'}
                              if part.get('preserve_generated_detail') else optimize_part(meshes, slot))
        if not profiled and slot in EQUIPMENT:
            transform, anchors, measurement = fit_equipment(meshes, spec['equipment'][slot])
        elif not profiled and slot == 'shoes':
            measurement, shoe_regions = fit_shoes_rigid(meshes, shoe_targets)
            transform, anchors = Matrix.Identity(4), []
        elif not profiled and slot == 'hat':
            headwear_seat = None
            if imported.get('hair'):
                targets[slot], headwear_seat = hat_target_over_hair(targets[slot], imported['hair'], spec)
            transform, anchors, measurement = fit_hat(meshes, targets[slot], fitting.get('hat_width_scale', 1))
            if headwear_seat:
                measurement['seat'] = headwear_seat
        elif not profiled and slot in ('hair', 'hairFront', 'hairBack'):
            transform, anchors, measurement = fit_hair(meshes, targets[slot], spec)
        elif not profiled:
            transform, anchors, measurement = measured_fit(meshes, targets[slot])
        skirt = slot == 'bottom' and (part.get('fit_profile') or {}).get('kind', part.get('garment_kind')) == 'skirt'
        rigid = (skirt and not profiled) or slot in ('hair', 'head', 'hairBack', 'hairFront', 'hat', *EQUIPMENT)
        bone = EQUIPMENT.get(slot, 'Head')
        if skirt:
            pelvis = next((b.name for b in rig.data.bones if b.name.lower().split(':')[-1] in ('hips', 'pelvis')), None)
            if not pelvis:
                raise ValueError('Missing pelvis for skirt attachment')
            bone = pelvis
        contract = {'anchors': anchors, 'max_anchor_error_m': .0001,
                    'binding': 'rigid' if rigid else 'transfer', 'bone': bone,
                    'slot': slot, 'max_transfer_distance_m': None}
        if not profiled:
            place(meshes, transform)
        if slot in ('hair', 'hairFront', 'hairBack'):
            measurement['length_fitting'] = fit_hair_length(meshes, targets[slot], spec)
        if slot == 'top' and not profiled:
            measurement['sleeves'], sleeve_masks = fit_sleeves(meshes, rig, spec)
        # Rear topology comes from the generated multiview asset. Never clone
        # front bangs or scalp triangles to fabricate a missing back view.
        head_preparation = (prepare_rear_hair(meshes, body, hat_palette, spec)
                            if slot == 'hairBack' else None)
        if slot == 'shoes':
            adjustment = {'method': 'rigid_foot_fit_no_surface_projection',
                          'adjusted_vertices': 0, 'maximum_adjustment_m': 0.0}
        elif slot in EQUIPMENT:
            adjustment = {'method': 'rigid_socket', 'adjusted_vertices': 0, 'maximum_adjustment_m': 0.0}
        elif profiled:
            adjustment = {'method': 'profiled_regional_fit_no_surface_projection',
                          'adjusted_vertices': sum(len(row) for row in garment_masks.values()),
                          'maximum_adjustment_m': None}
        elif slot in fitting.get('garment_margin_m', {}):
            # Keep the generated garment's volume and folds. Vertex projection
            # onto the body turns loose sleeves and hems into a skin-tight shell.
            adjustment = {'method': 'loose_fit_no_surface_projection',
                          'body_margin_xz_m': fitting['garment_margin_m'][slot],
                          'adjusted_vertices': 0, 'maximum_adjustment_m': 0.0}
        elif slot in ('hair', 'hairFront', 'hairBack') and fitting.get('hair_surface_fit') == 'measured-skull-v1':
            adjustment = fit_hair_scalp(meshes, body, rig, spec)
        elif slot in ('hair', 'head', 'hairFront', 'hairBack'):
            maximum = max(fitting.get('hair_clearance_m', .025),
                          spec['tolerances'].get('max_surface_adjustment_m', .015))
            adjustments = [clearance([obj], body, fitting.get('scalp_clearance_m', .003) if obj.get('scalp_backing')
                                    else fitting.get('hair_clearance_m', .025), maximum) for obj in meshes]
            adjustment = {'adjusted_vertices': sum(a['adjusted_vertices'] for a in adjustments),
                          'maximum_adjustment_m': max(a['maximum_adjustment_m'] for a in adjustments),
                          'maximum_allowed_m': maximum,
                          'bounded': True}
        else:
            adjustment = clearance(meshes, body, spec['tolerances']['clearance_m'],
                spec['tolerances']['max_surface_adjustment_m'] if slot == 'hat' else None)
        if slot in ('hairBack', 'hairFront') and 'hat' in imported:
            seat_legacy_hair_roots(meshes, body, spec)
        # Transfer weights only after the final garment size has been applied.
        report = (bind_shoes_rigid(meshes, rig, shoe_regions) if slot == 'shoes'
                  else bind(meshes, body, rig, contract, transform=Matrix.Identity(4)))
        if profiled:
            report['regional_binding'] = bind_garment_regions(meshes, rig, slot, garment_masks)
            report['weights'] = 'profiled_anatomical_regions'
        elif slot == 'top':
            bind_top_regions(meshes, rig, sleeve_masks)
            report['weights'] = 'anatomical_sleeves_and_torso'
        report['measurement'] = measurement
        if profiled:
            report.update(garment_report)
        if slot == 'bottom':
            report['garment_kind'] = garment_report.get('resolved_kind', part['fit_profile'].get('kind')) if profiled else part.get('garment_kind', 'source')
        report['runtime_budget'] = runtime_budget
        report['clearance'] = adjustment
        if head_preparation is not None:
            report['head_preparation'] = head_preparation
        a, b = bounds(meshes)
        report['fitted_bounds_gltf'] = [[a.x, a.z, -b.y], [b.x, b.z, -a.y]]
        names = []
        for i, obj in enumerate(meshes):
            obj.name = f'{slot}_{i}'; obj['part_role'] = slot; names.append(obj.name)
        reports.append({'slot': slot, 'source_sha256': part['sha256'], 'objects': names,
                        'anchors': anchors, 'available': True, **report})
        fitted += meshes
    # Hair and hat retain independent meshes, files and equip slots. A complete
    # hairstyle comes from its own generation job, never from joining headwear.
    # Keep the original skin as the weight-transfer source, then slim the core
    # for display. This leaves all skeleton transforms and transferred weights intact.
    base_shape = ({'preserved': True, 'reason': 'source_body'} if source_preserved_body
                  else {'preserved': True} if frozen else slim_base_body(body, rig, spec))
    base_shape['head_binding'] = head_binding
    base_shape['appearance'] = ({'preserved': True, 'reason': 'source_body'} if source_preserved_body
                                else {'preserved': True} if frozen else whiten_base_body(body, spec))
    body_budget = ({'preserved': True, 'source_mesh_detail': True} if source_preserved_body
                   else {'preserved': True} if frozen and not payload.get('canonical_pose')
                   else optimize_part(body, 'body'))
    rest_pose = ({'preserved': True} if frozen and not payload.get('canonical_pose')
                 else t_rest_pose(rig, [*body, *fitted]))
    if frozen and payload.get('canonical_pose'):
        rest_pose['derived_from_sha256'] = payload['source_sha256']
    # Persist measurements from the exported body state. Fitting may consume a
    # previously sealed profile above, but registration must describe the final
    # uniform-normalized, canonical-rest derivative.
    body_profile = measure_body_profile(body, rig, payload['source_sha256'])
    expression_uv = ({'available': False, 'preserved': True, 'reason': 'uploaded_face_texture'}
                     if spec.get('base_body', {}).get('preserve_face_texture') else prepare_expression_uv(body))
    selected_slots = {part['slot'] for part in payload['parts']}
    shoes = [obj for obj in fitted if obj['part_role'] == 'shoes'] if 'shoes' in selected_slots else []
    if shoes:
        shoe_report = next(report for report in reports if report['slot'] == 'shoes')
        shoe_report['final_pose_fitting'] = finish_shoes_after_pose(shoes, rig)
        a, b = bounds(shoes)
        shoe_report['fitted_bounds_gltf'] = [[a.x, a.z, -b.y], [b.x, b.z, -a.y]]
    garment_meshes = {part['slot']: [obj for obj in fitted if obj['part_role'] == part['slot']]
                     for part in reports if part.get('fit_status') not in ('needs_anchors', 'failed')}
    coverage_profiles = {report['slot']: report.get('coverage') for report in reports
                         if report.get('coverage')}
    covered_materials, coverage, crop_lines = mark_body_coverage(
        body, garment_meshes, rig, spec, coverage_profiles)
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
    for obj in fitted:
        obj.hide_render = obj['part_role'] not in ('top', 'bottom', 'shoes', *EQUIPMENT)
    for view, direction in directions:
        name = f'wardrobe-{view}.png'
        render(output/name, camera, view_center, direction, 600)
        detail_files.append(name)
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
    export_roles = [('body', body), *[(p['slot'], [o for o in fitted if o['part_role'] == p['slot']])
                                      for p in reports if p.get('available', True)]]
    for role, meshes in export_roles:
        export(output/f'{role}.glb', [metric_frame, rig, *meshes])
        if role in prefit_paths:
            # Preserve the sealed fitted slot byte-for-byte. The composed model
            # above uses the same geometry/UV/weights attached to the same rig.
            shutil.copyfile(prefit_paths[role], output/f'{role}.glb')
    animation = rig.animation_data
    motion = None
    for track in animation.nla_tracks if animation else []:
        track.mute = True
        for strip in track.strips:
            if strip.action and (motion is None or 'walk' in strip.action.name.lower()):
                motion = (strip.action, strip.action_slot)
    if motion:
        animation.action, animation.action_slot = motion
        start, end = motion[0].frame_range
        bpy.context.scene.frame_set(round(start+(end-start)*.25))
    else:
        bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()
    hide_covered_materials(covered_materials)
    render(output/'motion.png', camera, view_center, (0, -1, 0), 800)
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'master.blend'))
    doc, _ = parse_glb((output/'model.glb').read_bytes(), strict=True)
    parts = [{'slot': 'body', 'objects': body_names, 'runtime_budget': body_budget}, *reports]
    for part in parts:
        if not part.get('available', True):
            part['nodes'] = []
            continue
        exported, _ = parse_glb((output/f'{part["slot"]}.glb').read_bytes(), strict=True)
        primitives = [primitive for node in exported.get('nodes', []) if 'mesh' in node
                      for primitive in exported['meshes'][node['mesh']]['primitives']]
        # Coverage cuts can add vertices after simplification. Report the actual
        # exported geometry rather than presenting the requested cap as achieved.
        triangles = sum(exported['accessors'][p.get('indices', p['attributes']['POSITION'])]['count']//3
                        for p in primitives if p.get('mode', 4) == 4)
        budget = part['runtime_budget']
        budget.update(runtime_triangles=triangles, runtime_draws=len(primitives),
                      runtime_materials=len({p.get('material') for p in primitives}))
        if 'target_triangles' in budget:
            budget['budget_met'] = triangles <= budget['target_triangles']
        part['nodes'] = [i for i, n in enumerate(doc['nodes']) if n.get('name') in part['objects'] and 'mesh' in n]
        if not part['nodes'] or any('skin' not in doc['nodes'][i] for i in part['nodes']):
            raise ValueError('Missing skinned part')
    incomplete_parts = []
    for part in reports:
        attempted = part.get('attempted_fit') or part
        if attempted.get('fit_status') in ('needs_anchors', 'failed'):
            incomplete_parts.append({'slot': part['slot'], 'status': attempted['fit_status'],
                'errors': attempted.get('errors', []),
                'fallback_preserved': part.get('fit_status') == 'fallback_preserved',
                'available': part.get('available', True)})
    result = {'parts': parts, 'bone_count': len(rig.data.bones),
              'production_spec_sha256': spec['sha256'], 'normalization': normalization,
              'fitting_revision': fitting['revision'], 'fitting_targets': targets,
              'body_coverage_faces': coverage,
              'body_crop_lines': crop_lines,
              'body_profile': body_profile,
              'fit_status': 'incomplete' if incomplete_parts else 'complete',
              'incomplete_parts': incomplete_parts,
              'base_body_shape': base_shape,
              'rest_pose': rest_pose,
              'expression_uv': expression_uv,
              'source_sha256': payload['source_sha256'],
              'visual_review': 'required', 'origin': 'generated_parts_fitted_to_meshy_body',
              'limitations': ['Measured fitting and surface weight transfer require visual review.',
                              'Independently generated parts are not a segmentation of the original image or mesh.']}
    files = ['model.glb', 'master.blend', 'front.png', 'side.png', 'back.png', 'opposite.png', 'motion.png'] + [f'{p["slot"]}.glb' for p in parts if p.get('available', True)] + detail_files
    (output/'complete.json').write_text(json.dumps({'input_sha256': sha(output/'input.json'),
        'files': {name: sha(output/name) for name in files}, 'result': result}), encoding='utf8')


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf8')))
