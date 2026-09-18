"""Frozen coordinates and image preparation without quality gates."""
from copy import deepcopy
import hashlib
import io
import json

from PIL import Image, ImageDraw, ImageOps

from src.paths import BACKEND_ROOT
from src.services.character_pipeline import PipelineError

IMAGE_INTAKE_POLICY = 'prepare-without-quality-gates-v2'


def can_reuse_image(image):
    return bool(image.get('file') and image.get('sha256'))


def production_spec(hair_length='source'):
    raw = (BACKEND_ROOT/'assets/avatars/production-v1.json').read_bytes()
    spec = json.loads(raw)
    profiles = spec['fitting']['hair_length_profiles']
    if hair_length not in profiles:
        raise PipelineError('invalid_hair_length', '머리카락 길이를 다시 선택하세요.', 422)
    spec['fitting']['hair_length'] = hair_length
    ratio = profiles[hair_length]
    spec['fitting']['hair_length_head_ratio'] = ratio
    if ratio is not None:
        head_height = spec['anchors']['crown'][1]-spec['anchors']['neck'][1]
        spec['fitting']['bounds']['hair'][0][1] = max(.035, spec['fitting']['bounds']['hair'][1][1]-head_height*ratio)
        spec['envelopes']['hair'][0][1] = min(spec['envelopes']['hair'][0][1], spec['fitting']['bounds']['hair'][0][1])
    canonical = json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()
    return {**spec, 'sha256': hashlib.sha256(canonical).hexdigest()}


def project(point, view, spec):
    c = spec['canvas']; horizontal = spec['views'][view]['horizontal']
    return (c['center_x'] + sum(a*b for a, b in zip(point, horizontal))*c['pixels_per_metre'],
            c['sole_y'] - point[1]*c['pixels_per_metre'])


def envelope_pixels(slot, view, spec):
    return bounds_pixels(spec['envelopes'][slot], view, spec)


def bounds_pixels(box, view, spec):
    lo, hi = box
    corners = [project((x, y, z), view, spec) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    return [min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)]


def guide(view, spec, slot=None):
    """Authored measurement template, never presented as a generated asset."""
    c = spec['canvas']; im = Image.new('RGBA', (c['width'], c['height']), 'white'); draw = ImageDraw.Draw(im)
    def oval(lo, hi, color):
        a, b = project(lo, view, spec), project(hi, view, spec)
        draw.ellipse((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])), fill=color)
    oval((-.39, .46, -.27), (.39, 1.2, .29), '#b5b7c3')
    core = spec.get('base_body')
    core_color = '#e4e4e1' if core and core.get('color_rgba') else '#aaaebb'
    torso_x = core['torso_width_m']/2 if core else .155
    torso_z = core['torso_depth_m']/2 if core else .1025
    oval((-torso_x, .17, .0075-torso_z), (torso_x, .47, .0075+torso_z), core_color)
    anchors = spec['anchors']
    for side in ('left', 'right'):
        shoulder, wrist, ankle = (anchors[f'{part}_{side}'] for part in ('shoulder', 'wrist', 'ankle'))
        arm_width = round(core['arm_diameter_m']*c['pixels_per_metre']) if core else 80
        leg_width = round(core['leg_diameter_m']*c['pixels_per_metre']) if core else 94
        if core:
            draw.line([project((0, shoulder[1], 0), view, spec), project(shoulder, view, spec)], fill=core_color, width=arm_width)
        for start, end, width, tip in ((shoulder, wrist, arm_width, core.get('wrist_diameter_m', .028) if core else .064),
                                      ((ankle[0], .22, 0), ankle, leg_width, core.get('ankle_diameter_m', .032) if core else .075)):
            for step in range(8):
                a, b = step/8, (step+1)/8
                begin = tuple(x+(y-x)*a for x, y in zip(start, end))
                finish = tuple(x+(y-x)*b for x, y in zip(start, end))
                tapered = round(width+(tip*c['pixels_per_metre']-width)*b*b)
                draw.line([project(begin, view, spec), project(finish, view, spec)], fill=core_color, width=max(1, tapered))
        oval((ankle[0]-.047, 0, -.055), (ankle[0]+.047, .09, .115), '#aaaebb')
    if slot is not None:
        draw.rectangle(envelope_pixels(slot, view, spec), outline='#429c95', width=3)
        if spec.get('fitting'):
            draw.rectangle(bounds_pixels(spec['fitting']['bounds'][slot], view, spec), outline='#294fb0', width=5)
        for name in ('crown', 'neck', 'waist'):
            x, y = project(anchors[name], view, spec)
            draw.line([(80, y), (c['width']-80, y)], fill='#cc6680', width=2)
            draw.text((85, y+5), f'{name}: y={y:g}px', fill='#7c344c')
        draw.line([(80, c['sole_y']), (c['width']-80, c['sole_y'])], fill='#cc6680', width=3)
        draw.line([(c['center_x'], 40), (c['center_x'], c['height']-40)], fill='#677eaa', width=2)
        for name, point in anchors.items():
            x, y = project(point, view, spec)
            draw.ellipse((x-5, y-5, x+5, y+5), fill='#576697')
    out = io.BytesIO(); im.save(out, format='PNG'); return out.getvalue()


def can_register_body(box, slot, spec):
    c = spec['canvas']
    if slot != 'body' or not box:
        return False
    if box[0] <= 0 or box[1] <= 0 or box[2] >= c['width'] or box[3] >= c['height'] or box[3] <= box[1]:
        return False
    scale = (c['sole_y']-c['scalp_y'])/(box[3]-box[1])
    return 0.5 <= scale <= 2.0


def prepare_image(raw, slot, spec):
    c = spec['canvas']; changed = False
    with Image.open(io.BytesIO(raw)) as original:
        if max(original.size) > 4096 or original.width * original.height > 16_777_216:
            raise PipelineError('canvas_mismatch', '응답 이미지가 허용한 크기를 초과했습니다.', 422)
        size = list(original.size)
        image = original.convert('RGBA')
        changed = original.format != 'PNG'
        if image.size != (c['width'], c['height']):
            contained = ImageOps.contain(image, (c['width'], c['height']), Image.Resampling.LANCZOS)
            image = Image.new('RGBA', (c['width'], c['height']), (0, 0, 0, 0))
            image.alpha_composite(contained, ((c['width']-contained.width)//2, (c['height']-contained.height)//2))
            changed = True
    mask = image.getchannel('A').point(lambda value: 255 if value >= 128 else 0)
    box = mask.getbbox()
    original_box = list(box) if box else None
    registration = None
    if (box and slot == 'body' and can_register_body(box, slot, spec) and
            (abs(box[1]-c['scalp_y']) > 1 or abs(box[3]-c['sole_y']) > 1)):
        # Fix framing only. One uniform scale preserves anatomy, thickness and aspect ratio.
        # X scales around the shared origin; profile depth is never inferred by centering its bbox.
        scale = (c['sole_y']-c['scalp_y'])/(box[3]-box[1])
        inverse = 1/scale
        image = image.transform(image.size, Image.Transform.AFFINE,
            (inverse, 0, c['center_x']*(1-inverse), 0, inverse, box[1]-c['scalp_y']*inverse),
            resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0))
        registration = {'method': 'uniform_body_canvas_v1', 'scale': scale, 'source_bounds_px': original_box,
                        'source_sha256': hashlib.sha256(raw).hexdigest(), 'horizontal_origin_preserved': True}
        changed = True
        mask = image.getchannel('A').point(lambda value: 255 if value >= 128 else 0)
        box = mask.getbbox()
    content = raw
    if changed:
        out = io.BytesIO(); image.save(out, format='PNG', compress_level=2)
        content = out.getvalue()
    return content, {'policy': IMAGE_INTAKE_POLICY, 'bounds_px': list(box) if box else None,
                     'registration': registration, 'source_size': size,
                     'canvas_size': [c['width'], c['height']], 'spec_sha256': spec['sha256']}


def paired_bounds(front, side, spec, slot):
    """Retain shared canvas placement; never infer a fitted size from tight crops."""
    f, s = front.get('bounds_px'), side.get('bounds_px')
    if not f or not s:
        return deepcopy(spec['envelopes'][slot])
    c = spec['canvas']; ppm = c['pixels_per_metre']; cx = c['center_x']; floor = c['sole_y']
    return [[(f[0]-cx)/ppm, (floor-max(f[3], s[3]))/ppm, (cx-s[2])/ppm],
            [(f[2]-cx)/ppm, (floor-min(f[1], s[1]))/ppm, (cx-s[0])/ppm]]


def public_spec(spec):
    result = {key: spec[key] for key in ('id', 'revision', 'sha256', 'body_height_m', 'axes', 'canvas', 'generated_views', 'release_requires')}
    if spec.get('fitting'):
        result['fitting'] = spec['fitting']
    return deepcopy(result)
