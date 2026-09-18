"""One image-layout contract shared by prompts, visual guides, and fitting."""
import json

from src.services.avatar_production_spec import bounds_pixels, envelope_pixels, project

PROMPT_REVISION = 'measured-views-v14-t-pose-slender-joints'
PART_CONTENT = {
    'hair': 'ONE complete voluminous hairstyle: front bangs, both side locks, full crown, rear hair and nape form one continuous hair-only component. Reconstruct the complete hair hidden under the original hat. Exclude ALL headwear, hats, caps, brims, rabbit ears, ear flaps, hoods, headbands and hat-colored patches. Exclude face, scalp skin, anatomical ears, neck, body and clothes. Leave the face opening and a generous hollow cavity for the shared head.',
    'hairBack': 'One separate sculpted rear-hair component for a stylized game figurine, covering the crown, back and nape. Output hair strands and their hair-colored scalp backing only. Remove ALL headwear from the reference: no hat, cap, brim, rabbit ears, ear flaps, hood, headband or hat-colored patches. Reconstruct the hair that was hidden beneath the hat. Exclude the figurine, bangs and clothing.',
    'hairFront': 'One separate sculpted front-hair and bangs component for the same game figurine. Preserve the face opening; output hair only, without the figurine, rear hair, hat, cap, rabbit ears, ear flaps or headband.',
    'hat': 'ONE separate removable hat with only its original attached ornaments; complete its rim, underside and hollow head opening. Exclude ALL hair, bangs, side locks, rear hair, scalp, face and body. The hairstyle is a different independently generated part, never part of this object.',
    'top': 'Only the original upper garment, collar, sleeves, cuffs and hem; complete its neck, wrist and waist openings. Exclude hands and body.',
    'bottom': 'Only the original lower garment, waistband and lining; complete its body and leg openings. Exclude legs, torso and shoes.',
    'shoes': 'Only the original matching pair of shoes at the two feet positions, including ankle openings; exclude feet and legs. In profile the far shoe may be occluded; do not spread shoes for display.',
}

PART_FIT = {
    'hair': (
        'Build the hairstyle as one continuous volume around the entire head, not separate front and back panels. '
        'Keep generous volume at the temples, sides, crown and rear, with detailed overlapping locks in every view. '
        'Preserve the ORIGINAL hair-to-face width and hair-tip-to-body-height ratio, including the complete long lower locks. '
        'For long hair reaching the boot tops in the original, carry the rear and side hair down beside the torso to the boot tops; never shorten it to shoulder length. '
        'The overall hairstyle should be substantially wider than the bare head, around 1.5 times its width, with a generous hollow head cavity. '
        'Keep the crown centered on the body centerline and the root mass balanced on both sides. Preserve intentional asymmetric locks only. '
        'Preserve the original overall hairstyle proportions; do not stretch its depth or squash its height to fill a rectangle. '
        'Allow 25mm clearance from the bald head; do not compress the hair onto the scalp. '
        'The entire crown must be finished hair even though the art reference hides it under a hat. '
        'The hair must remain complete when worn without a hat; never cut its crown at a hat brim. '
        'The hat is a separate removable part and MUST NOT appear in this hair image. '
        'No cap, rabbit ears, bare scalp patch, flat smooth rear plate, detached hair panel or visible front/back seam.'),
    'hairBack': (
        'Own the rear scalp, rear crown and nape only. Leave the forehead, face and bangs region empty. '
        'Follow the skull surface with a hollow inner cavity; never fill that cavity with a solid head. '
        'Long hair follows the original outline and stays outside the neck, shoulders and upper garment. '
        'Do not add a second fringe, duplicate side locks or an oversized rear volume.'),
    'hairFront': (
        'Own the fringe and original front locks only; the rear scalp and rear crown belong to hairBack. '
        'Keep the original face opening, eye visibility and hairline. Roots follow the outside of the scalp. '
        'Do not include a second rear hair shell, solid skull, face mask or strands running through the face.'),
    'hat': (
        'Fit the hollow inner opening around the original worn hair volume, not through the hair or bald head. '
        'Keep its original brim width, crown height, tilt and ornament proportions in the common coordinate frame. '
        'Do not enlarge the hat to fill its maximum envelope or move it above the scalp as a floating prop.'),
    'top': (
        'Place collar at the neck, shoulders at shoulder anchors, cuffs at wrist anchors and hem at the original waist level. '
        'Sleeves follow the frozen T-pose: upper arms, elbows, cuffs and wrists are on one horizontal line at shoulder height. Keep neck, sleeve and hem cavities open. '
        'Use the specified garment size with modest ease around the torso, sleeves and cuffs. '
        'Do not enlarge the garment to cover protruding base clothing; that base layer is cropped during assembly. '
        'Preserve the original design and folds without embedding hands, torso or neck geometry.'),
    'bottom': (
        'Place the waistband at the frozen waist and each leg opening around its corresponding leg. '
        'Use the specified garment size with modest ease around the hips, thighs and leg openings. '
        'Preserve the original design and crotch; keep the pelvis cavity and leg openings hollow. '
        'Where the top covers the waistband, use separate nested surfaces with clearance, never crossing surfaces. '
        'Keep the specified width and depth ease; do not tighten the garment against the legs. '
        'Do not fuse the legs, extend the garment into the shoes or duplicate the torso.'),
    'shoes': (
        'Create exactly one left and one right shoe at the ankle anchors; no extra shoes or detached soles. '
        'Keep ankle cavities hollow, original toe direction and original sole thickness. '
        'The inner shoe contains its foot with clearance; the ankle rim does not cut through the foot or lower garment. '
        'Both soles share the floor. Never separate, rotate outward, stack or vertically offset the pair for presentation.'),
}


def layout_contract(spec, slot, view):
    c = spec['canvas']
    layout = {
        'units': spec['units'],
        'world_axes': spec['axes'],
        'world_origin': spec['origin'],
        'body_height_m': spec['body_height_m'],
        'rest_pose': spec.get('rest_pose', 'T'),
        'allowed_part_bounds_m': spec['envelopes'][slot],
        'body_landmarks_m': spec['anchors'],
        'hair_length_mode': spec['fitting'].get('hair_length', 'source'),
        'hair_length_in_head_heights': spec['fitting'].get('hair_length_head_ratio'),
        'base_body_cross_sections_m': spec.get('base_body', {}),
        'canvas_px': [c['width'], c['height']],
        'pixel_coordinates': 'origin top-left, x right, y down; bounds [left, top, right, bottom]',
        'camera': spec['views'][view]['camera'],
        'pixels_per_metre': c['pixels_per_metre'],
        'centerline_x': c['center_x'],
        'scalp_top_y': c['scalp_y'],
        'sole_bottom_y': c['sole_y'],
        'body_height_px': c['sole_y']-c['scalp_y'],
        'head_height_px': round((spec['anchors']['crown'][1]-spec['anchors']['neck'][1])*c['pixels_per_metre']),
        'allowed_part_bounds_px': [round(n, 2) for n in envelope_pixels(slot, view, spec)],
        'body_landmarks_px': {name: [round(n, 2) for n in project(point, view, spec)] for name, point in spec['anchors'].items()},
        'pixel_tolerance': spec['tolerances']['canvas_px'],
        'paired_view_height_tolerance_px': spec['tolerances']['view_height_px'],
    }
    if spec.get('fitting'):
        target = spec['fitting']['bounds'][slot]
        layout.update(fitting_revision=spec['fitting']['revision'], target_part_bounds_m=target,
                      target_part_size_m=[round(b-a, 6) for a, b in zip(*target)],
                      target_part_bounds_px=[round(n, 2) for n in bounds_pixels(target, view, spec)])
        if slot == 'shoes':
            layout['shoe_bounds_m'] = spec['fitting']['shoe_bounds']
        if slot in spec['fitting'].get('garment_margin_m', {}):
            layout['garment_ease_each_side_xz_m'] = spec['fitting']['garment_margin_m'][slot]
    return layout


def reference_roles(slot, view, *, hair_reference=False):
    roles = ['GEOMETRY TEMPLATE: exact canvas, silhouette proportions, pose and pixel placement. Colored lines are measurement marks only.']
    if slot != 'body':
        roles.append('FROZEN BODY IN THIS VIEW: exact garment/hair/hat fit, scale and worn position. Do not render the body in the output.')
    if hair_reference:
        roles.append('FROZEN COMPLETE HAIR IN THIS VIEW: exact outer hair volume, crown, centerline and headwear seat. Fit the separate removable hat OVER this hair with clearance. Do NOT render any of this hair in the hat output.')
    roles.append('ORIGINAL ART: identity, face, colors and requested part design only. Its framing, pose and body proportions are not the layout template.')
    if view == 'side':
        roles.append('ACCEPTED FRONT VIEW OF THE SAME OBJECT: preserve its identity, shape, top and bottom pixel rows. Rotate it; do not redesign it.')
    return roles


def hair_length_prompt(spec):
    mode = spec['fitting'].get('hair_length', 'source')
    ratio = spec['fitting'].get('hair_length_head_ratio')
    if mode == 'source':
        return (' ORIGINAL LENGTH MODE: the target lower bound is available space, NOT a required tip height or a short-hair maximum. '
                'Read the hair tips relative to the face, shoulders, waist and boots in the original art. '
                'Preserve short hair as short and long hair as long; do not lengthen or shorten it to fill the template.')
    return (f' SELECTED LENGTH MODE: {mode}. Crown-to-tip length is {ratio:g} times the bald crown-to-neck head height. '
            'Use the specified target lower bound for the tips. This explicit length selection overrides only the original length; retain its color and hairstyle details.')


def build_prompt(spec, slot, view, *, previous_qc=None, accepted_front_qc=None, notes='', hair_reference=False):
    layout = layout_contract(spec, slot, view)
    c = spec['canvas']
    roles = '\n'.join(f'Input image {i}: {role}' for i, role in enumerate(reference_roles(slot, view, hair_reference=hair_reference), 1))
    camera = {
        'front': 'FRONT ONLY. Camera on character +Z, optical axis toward -Z, up +Y. Face and torso face the camera in the symmetric template pose. Preserve asymmetrical design details on their original anatomical side; do not mirror them. No three-quarter turn.',
        'side': 'SIDE PROFILE ONLY. Camera on character +X, optical axis toward -X. Nose and toes point IMAGE-LEFT. Preserve the horizontal T-pose in 3D; arms point along the camera axis and overlap at shoulder height. Do not lower or bend them to reveal the hands. Do not rotate the face toward the camera or spread the legs.',
    }[view]
    if slot == 'body':
        content = (
            'Edit the geometry template IN PLACE into one complete bald chibi base body. '
            'Preserve its crown, chin/neck, shoulders, wrists, waist, ankles and sole positions. '
            'Transfer ONLY the original face identity, eyes and skin appearance from the art reference. '
            'Include bald head, face, ears, neck, torso, both arms, hands, legs and bare feet as one intact figure. '
            'The base figure is fully clothed in ONE thin opaque matte WHITE fitted underlayer from neck to wrists and ankles. '
            'Use a quiet neutral white fabric, never blue, teal, cyan, a saturated color or skin-colored fabric. '
            'This is a slender internal wardrobe mannequin, NOT a sweatshirt and trousers. '
            'Use the specified narrow torso width/depth and thin arm/leg diameters around the unchanged joint positions. '
            'Use a straight horizontal T-pose: both shoulders, elbows and wrists share the same height, palms face down. '
            'Keep wrists and ankles tapered to the specified thin joint diameters, continuous with the hands and feet. '
            'No padded torso, baggy sleeves, puffed shoulders, cuffs, waistband, folds, inflated thighs or extra clothing thickness. '
            'The underlayer is completely opaque; face and hands retain the original skin appearance. '
            'Keep the original large head, face, hands, feet, joint positions and limb lengths; reduce only the clothed torso and limb thickness. '
            'Include the base clothing; exclude hair, hat, accessories, outer costume layers and shoes. '
            f'The bald crown touches y={c["scalp_y"]}; the soles touch y={c["sole_y"]}. '
            f'Full body height is {layout["body_height_px"]}px; head crown-to-neck height is {layout["head_height_px"]}px. '
            f'Keep the {c["scalp_y"]}px upper margin and {c["height"]-c["sole_y"]}px lower margin EMPTY. '
            'The head is much larger than the tiny torso and short legs; follow the template landmarks instead of conventional child proportions.'
            ' Keep the head-to-body junction, limb lengths, foot spacing and torso depth identical across both views. '
            'Hands remain separate from the torso; fingers stay together in a neutral riggable pose. '
            'No elongated legs, narrow adult head, enlarged chest, extra joints, missing limbs or hair painted onto the scalp.'
        )
    else:
        content = (
            PART_CONTENT[slot] + ' Reproduce the visible design in the original art. '
            'Fit the object onto the frozen body at its current WORN POSITION, then hide the body without moving the object. '
            'Keep its full-character canvas position even when most of the output canvas is empty. ' +
            ('Use target_part_bounds_m for hair width and crown position. Preserve the original rounded silhouette and proportional depth. '
             if slot == 'hair' else 'When target_part_bounds_m is specified, use that exact overall width, height, depth and worn position. ') +
            'The blue template outline marks this fitting target; it is not the larger allowed envelope. '
            'The part bounds are a maximum envelope, not a box to stretch the object to fill. '
            f'Keep at least {spec["tolerances"]["clearance_m"]*1000:g}mm physical clearance from the underlying body or worn layer; preserve all inner attachment openings. '
            'Keep local scale and thickness consistent with the frozen body. Do not enlarge an isolated garment or move it to the canvas center.'
            '\nPART ATTACHMENT CONTRACT: '+PART_FIT[slot]
        )
        if slot == 'hair':
            content += hair_length_prompt(spec)
    prompt = '\n\n'.join([
        f'FACTORY IMAGE CONTRACT {PROMPT_REVISION}. Produce a measured modular 3D source image, not an illustration or product presentation. '
        f'Output exactly one {c["width"]}x{c["height"]} RGBA PNG of {slot}, {view} view. One view only; no montage, turnaround sheet or inset.',
        roles,
        'SUBJECT: a stylized modular game figurine and its manufactured costume components. '
        'Character references show a fully clothed figurine and provide shape and color context. '
        'For a hair, hat, garment or shoe request, create the independent sculpted component, with the figure absent from the output. '
        'Keep every body reference fully clothed; do not reinterpret component isolation as undressing a person. '
        'Use smooth stylized toy surfaces, not realistic human anatomy or detached anatomical material.',
        'NON-NEGOTIABLE PRIORITY: frozen metric coordinates and template landmarks first; same-object front/profile geometry second; original-art identity, materials and details third. '
        'Never solve a conflict by changing body proportions, object scale, camera, pose, crop or attachment position. '
        'The allowed bounds are maximum limits, not a target size. Keep intentional empty canvas space. '
        'Every generation in this factory shares the same body, origin, units, camera magnification and attachment anchors.',
        camera,
        'EXACT PIXEL LAYOUT (same values used by the assembly fitter):\n'+json.dumps(layout, ensure_ascii=True, indent=2),
        content,
        'ASSEMBLY RULES: skin/body is the innermost layer; clothes and hair are outside it; the hat is outside the worn hair. '
        'Separate surfaces may cover one another in a 2D projection, but must not cross or occupy the same volume in 3D. '
        'Preserve the same front/back depth, left/right placement, material boundaries and openings when rotating to profile. '
        'No fused body/garment surfaces, duplicated overlap shells, solid plugs in attachment holes or hidden spare body parts. '
        'Do not add geometry to make an isolated part look complete as a standalone character.',
        'No crop, auto-framing, camera zoom, perspective, tilt or extra objects. Preserve the entire square canvas. '
        'No text, rulers, grid, colored guide lines, floor, backdrop, checkerboard, cast shadow, glow, halo, bloom or vignette. '
        'Background pixels must have alpha 0. Object interiors are opaque; alpha transitions are limited to the antialiased contour. Use neutral flat illumination, no rim light.',
        'BEFORE RETURNING THE IMAGE: align crown, neck, waist, wrists, ankles and soles with the supplied landmarks; '
        'retain the original part silhouette within its metric envelope; preserve all empty attachment openings; '
        'keep only the requested part; remove every measurement mark and background pixel. '
        'Return the image only, without captions or claims about validation.',
    ])
    if accepted_front_qc and accepted_front_qc.get('bounds_px'):
        box = accepted_front_qc['bounds_px']
        prompt += (f'\n\nSAME-OBJECT PAIR: accepted front top={box[1]}px and bottom={box[3]}px. '
                   f'The profile must use those same rows within {layout["paired_view_height_tolerance_px"]}px; depth changes, height does not. '
                   'Keep the SAME object fixed in world coordinates; move only the orthographic camera 90 degrees from +Z to +X around world +Y. '
                   'No object translation, rotation, pose change or scale change. '
                   'Preserve hem, cuff, collar, brim, hair tip and sole heights. Do not reveal hidden limbs by moving them.')
    if previous_qc:
        prompt += ('\n\nCORRECTION OF THE PREVIOUS REJECTED ATTEMPT: '+json.dumps({
            'issues': previous_qc.get('issues'), 'layout_warnings': previous_qc.get('warnings'),
            'actual_bounds_px': previous_qc.get('bounds_px'),
            'required_envelope_px': layout['allowed_part_bounds_px'],
            'required_body_top_bottom_px': [c['scalp_y'], c['sole_y']] if slot == 'body' else None,
        }, ensure_ascii=True)+'. Re-render using the specified template placement and empty margins. Do not repeat the rejected framing.')
    if notes:
        prompt += '\n\nOptional appearance detail only (never changes view, scale, pose or canvas): '+notes
    return prompt
