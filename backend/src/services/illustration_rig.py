"""Whole-illustration 2D rig: proposed joints, rigid part regions with blended joints, and a grid mesh.

No part is cut out of the drawing. Each pixel belongs to one bone by the joint lines (head above the
neck, legs below the hips, arms against the torso by capsule distance); weights are those regions
blurred across their borders, so parts stay rigid and joints bend smoothly.
"""
import io
import math

import numpy as np
from PIL import Image

from src.services.character_pipeline import PipelineError

RIG_REVISION = 'illustration-rig-v1'
SKELETON = 'emoticon-2d-v1'
JOINTS = ('head_top', 'neck', 'pelvis', 'shoulder_r', 'elbow_r', 'wrist_r', 'shoulder_l', 'elbow_l', 'wrist_l',
          'hip_r', 'knee_r', 'ankle_r', 'hip_l', 'knee_l', 'ankle_l')
# name, parent, pivot joint, tail joint, draw layer (higher is in front). `_r` is the character's right,
# which is the image's left in a front view.
BONES = (('body', 'root', 'pelvis', 'neck', 1), ('head', 'body', 'neck', 'head_top', 2),
         ('arm_upper_r', 'body', 'shoulder_r', 'elbow_r', 3), ('arm_lower_r', 'arm_upper_r', 'elbow_r', 'wrist_r', 4),
         ('arm_upper_l', 'body', 'shoulder_l', 'elbow_l', 3), ('arm_lower_l', 'arm_upper_l', 'elbow_l', 'wrist_l', 4),
         ('leg_upper_r', 'root', 'hip_r', 'knee_r', 0), ('leg_lower_r', 'leg_upper_r', 'knee_r', 'ankle_r', 0),
         ('leg_upper_l', 'root', 'hip_l', 'knee_l', 0), ('leg_lower_l', 'leg_upper_l', 'knee_l', 'ankle_l', 0))
BONE_NAMES = tuple(bone[0] for bone in BONES)
_BLEND = 12        # px across which neighbouring parts share weight
_REGION_STEP = 4   # px per cell of the region grid


def load_alpha(png):
    image = Image.open(io.BytesIO(png)).convert('RGBA')
    rgba = np.array(image)
    mask = rgba[..., 3] >= 128
    if not mask.any():
        raise PipelineError('empty_illustration', '원화에 보이는 영역이 없습니다.', 422)
    if mask.mean() > .9:
        raise PipelineError('opaque_background', '배경이 투명한 원화만 리깅할 수 있습니다.', 422)
    return rgba, mask


def _run(row, x):
    """(start, end) of the opaque run at or nearest to column x, or None for an empty row."""
    columns = np.flatnonzero(row)
    if not len(columns):
        return None
    if not row[x]:
        x = int(columns[np.argmin(np.abs(columns - x))])
    breaks = np.flatnonzero(np.diff(columns) > 1)
    starts, ends = np.r_[columns[0], columns[breaks + 1]], np.r_[columns[breaks], columns[-1]]
    index = int(np.searchsorted(ends, x))
    return int(starts[index]), int(ends[index])


def propose_joints(mask):
    """Joints for a front-view figure standing on its feet, from the silhouette alone."""
    ys, xs = np.nonzero(mask)
    top, bottom, left, right = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    height, width = bottom - top + 1, right - left + 1
    cx = int(np.median(xs))
    band = range(top + int(.22 * height), top + int(.62 * height) + 1)
    runs = [_run(mask[y], cx) for y in band]
    widths = np.array([run[1] - run[0] + 1 if run else width for run in runs], float)
    if len(widths) > 9:
        # Smoothed central-run width; the narrowest row between head and torso is the neck.
        widths = np.convolve(widths, np.ones(9) / 9, mode='same')
        neck_y = band.start + 4 + int(np.argmin(widths[4:-4]))
    else:
        neck_y = band.start + int(np.argmin(widths))
    run = _run(mask[neck_y], cx)
    neck_x = (run[0] + run[1]) / 2 if run else cx
    feet = np.flatnonzero(mask[max(top, bottom - int(.1 * height)):bottom + 1].any(0))
    legs_x = int(np.median(feet)) if len(feet) else cx
    lower = range(neck_y + int(.3 * (bottom - neck_y)), bottom + 1)
    gap = [y for y in lower if not mask[y, legs_x]]
    # The gap between the legs marks the crotch; legs drawn together keep it within SD proportions.
    crotch_y = (min(gap) - 1) if gap else neck_y + .55 * (bottom - neck_y)
    crotch_y = min(max(crotch_y, neck_y + .4 * (bottom - neck_y)), neck_y + .65 * (bottom - neck_y))
    pelvis_y = neck_y + .72 * (crotch_y - neck_y)
    run = _run(mask[int(pelvis_y)], legs_x)
    pelvis_x = (run[0] + run[1]) / 2 if run else legs_x
    half = min(((run[1] - run[0]) / 2) if run else .2 * width, .35 * width)
    hip_y = (pelvis_y + crotch_y) / 2
    ankle_y = bottom - .08 * (bottom - crotch_y)
    joints = {'head_top': (neck_x, top + .03 * height), 'neck': (neck_x, neck_y), 'pelvis': (pelvis_x, pelvis_y)}
    torso = neck_y, crotch_y + .15 * (bottom - crotch_y)
    for side, sign in (('r', -1), ('l', 1)):
        row = mask[int(ankle_y)]
        columns = np.flatnonzero(row[:legs_x] if sign < 0 else row[legs_x:])
        ankle_x = float(columns.mean()) + (0 if sign < 0 else legs_x) if len(columns) else pelvis_x + sign * .5 * half
        hip = (pelvis_x + sign * .5 * half, hip_y)
        joints[f'hip_{side}'], joints[f'ankle_{side}'] = hip, (ankle_x, ankle_y)
        joints[f'knee_{side}'] = ((hip[0] + ankle_x) / 2, (hip_y + ankle_y) / 2)
        shoulder = (neck_x + sign * .8 * half, neck_y + .18 * (crotch_y - neck_y))
        rows = slice(int(torso[0]), int(torso[1]) + 1)
        region = mask[rows]
        columns = np.flatnonzero(region.any(0))
        reach = columns.min() if sign < 0 else columns.max()
        if abs(reach - shoulder[0]) < .5 * half:
            wrist = (shoulder[0] + sign * .1 * half, shoulder[1] + .55 * (crotch_y - neck_y))
        else:
            ys_at = np.flatnonzero(region[:, reach]) + rows.start
            tip = (float(reach), float(ys_at.mean()))
            wrist = (tip[0] + .12 * (shoulder[0] - tip[0]), tip[1] + .12 * (shoulder[1] - tip[1]))
        joints[f'shoulder_{side}'], joints[f'wrist_{side}'] = shoulder, wrist
        joints[f'elbow_{side}'] = ((shoulder[0] + wrist[0]) / 2, (shoulder[1] + wrist[1]) / 2)
    return {name: [round(float(joints[name][0]), 1), round(float(joints[name][1]), 1)] for name in JOINTS}


def check_joints(joints, width, height):
    if not isinstance(joints, dict) or set(joints) != set(JOINTS):
        raise PipelineError('invalid_joints', '관절 목록이 맞지 않습니다.', 422)
    clean = {}
    for name in JOINTS:
        x, y = joints[name]
        if not (math.isfinite(x) and math.isfinite(y) and -width * .25 <= x <= width * 1.25 and -height * .25 <= y <= height * 1.25):
            raise PipelineError('invalid_joints', '관절이 원화 범위를 벗어났습니다.', 422)
        clean[name] = [round(float(x), 1), round(float(y), 1)]
    return clean


def _segment_distance(px, py, a, b):
    ax, ay = a; bx, by = b
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy or 1e-9
    u = np.clip(((px - ax) * dx + (py - ay) * dy) / length, 0, 1)
    return np.hypot(px - (ax + u * dx), py - (ay + u * dy)), u


def _half_thickness(mask, a, b):
    """Median half-width of the silhouette across a bone, sampled at five points along it."""
    height, width = mask.shape
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    samples = []
    for t in (.2, .35, .5, .65, .8):
        cx, cy = a[0] + t * dx, a[1] + t * dy
        reach = []
        for sign in (1, -1):
            step = 0
            while step < max(width, height):
                x, y = int(round(cx + sign * step * nx)), int(round(cy + sign * step * ny))
                if not (0 <= x < width and 0 <= y < height) or not mask[y, x]:
                    break
                step += 1
            reach.append(step)
        samples.append(sum(reach) / 2)
    return float(np.median(samples))


def regions(mask, joints):
    """Bone index per region cell (-1 outside the drawing) on a grid of _REGION_STEP pixels."""
    height, width = mask.shape
    step = _REGION_STEP
    rows, cols = -(-height // step), -(-width // step)
    padded = np.zeros((rows * step, cols * step), bool)
    padded[:height, :width] = mask
    cells = padded.reshape(rows, step, cols, step).any((1, 3))
    py, px = (np.mgrid[0:rows, 0:cols] + .5) * step
    j = {name: tuple(value) for name, value in joints.items()}
    index = {name: i for i, name in enumerate(BONE_NAMES)}
    label = np.full((rows, cols), index['body'], np.int16)
    # Distance to each bone as a capsule: its half-thickness counts only beside the bone, never past its ends.
    reach = {}
    for name, _, head, tail, _ in BONES:
        if name == 'head':
            continue
        distance, u = _segment_distance(px, py, j[head], j[tail])
        radius = _half_thickness(mask, j[head], j[tail]) * (.95 if name == 'body' else 1)
        inside = (u > 0) & (u < 1)
        reach[name] = np.where(inside, np.maximum(distance - radius, 0), distance)
    names = [name for name in BONE_NAMES if name != 'head']
    label[:] = np.array([index[name] for name in names])[np.argmin(np.array([reach[name] for name in names]), axis=0)]
    # Above the neck line (perpendicular to the body at the neck) is head, apart from raised hands.
    axis = np.subtract(j['neck'], j['pelvis'])
    axis = axis / (np.hypot(*axis) or 1)
    above = (px - j['neck'][0]) * axis[0] + (py - j['neck'][1]) * axis[1] > 0
    hands = np.isin(label, [index['arm_lower_r'], index['arm_lower_l']]) \
        & (np.minimum(reach['arm_lower_r'], reach['arm_lower_l']) < 1.5 * step)
    label[above & ~hands] = index['head']
    label[~cells] = -1
    return label


def _box(channel, radius, axis):
    pad = [(0, 0), (0, 0)]
    pad[axis] = (radius, radius)
    total = np.cumsum(np.pad(channel, pad, mode='edge'), axis=axis, dtype=np.float64)
    total = np.concatenate([np.zeros_like(np.take(total, [0], axis=axis)), total], axis=axis)
    span, size = 2 * radius + 1, channel.shape[axis]
    return (np.take(total, np.arange(span, span + size), axis=axis) - np.take(total, np.arange(size), axis=axis)) / span


def weights_grid(label):
    """Per-cell weights (rows, cols, bones): one-hot regions blurred by _BLEND pixels, renormalised.

    Cells too far from every part to receive any weight are left all zero.
    """
    radius = max(1, int(round(_BLEND / _REGION_STEP / 2)))
    weights = np.zeros(label.shape + (len(BONE_NAMES),), np.float32)
    for bone in range(len(BONE_NAMES)):
        channel = (label == bone).astype(np.float64)
        for axis in (0, 1, 0, 1):
            channel = _box(channel, radius, axis)
        weights[..., bone] = channel
    total = weights.sum(-1, keepdims=True)
    return np.where(total > 1e-6, weights / np.maximum(total, 1e-6), 0).astype(np.float32)


def mesh(mask, cell):
    """Grid vertices (x, y) and triangles covering every cell that holds an opaque pixel."""
    height, width = mask.shape
    rows, cols = -(-height // cell), -(-width // cell)
    padded = np.zeros((rows * cell, cols * cell), bool)
    padded[:height, :width] = mask
    kept = padded.reshape(rows, cell, cols, cell).any((1, 3))
    corner = np.zeros((rows + 1, cols + 1), bool)
    for dr in (0, 1):
        for dc in (0, 1):
            corner[dr:rows + dr, dc:cols + dc] |= kept
    ids = np.full(corner.shape, -1, np.int64)
    ids[corner] = np.arange(corner.sum())
    vr, vc = np.nonzero(corner)
    vertices = np.stack([vc * cell, vr * cell], 1).astype(np.float64)
    r, c = np.nonzero(kept)
    a, b, d, e = ids[r, c], ids[r, c + 1], ids[r + 1, c], ids[r + 1, c + 1]
    triangles = np.concatenate([np.stack([a, b, e], 1), np.stack([a, e, d], 1)])
    return vertices, triangles


def skin(png, joints):
    """Mesh, per-vertex weights and per-triangle layers for a drawing and its joints."""
    rgba, mask = load_alpha(png)
    height, width = mask.shape
    label = regions(mask, joints)
    grid = weights_grid(label)
    cell = max(6, int(round(max(height, width) / 128)))
    vertices, triangles = mesh(mask, cell)
    r = np.clip((vertices[:, 1] / _REGION_STEP).astype(int), 0, grid.shape[0] - 1)
    c = np.clip((vertices[:, 0] / _REGION_STEP).astype(int), 0, grid.shape[1] - 1)
    weights = grid[r, c]
    empty = np.flatnonzero(weights.sum(1) < 1e-6)
    if len(empty):
        # A vertex beyond the blurred regions follows the nearest labelled cell.
        inside = np.argwhere(label >= 0)
        for vertex in empty:
            nearest = inside[np.argmin(np.abs(inside - (r[vertex], c[vertex])).sum(1))]
            weights[vertex, label[tuple(nearest)]] = 1
    layers = np.array([bone[4] for bone in BONES])[np.argmax(weights[triangles].sum(1), axis=1)]
    return {'rgba': rgba, 'mask': mask, 'label': label, 'vertices': vertices, 'triangles': triangles,
            'weights': weights, 'layers': layers}


def region_preview(rgba, label, size=512):
    """The drawing tinted by the bone each part follows, for checking joints."""
    palette = np.array([[182, 165, 237], [247, 196, 120], [120, 200, 170], [90, 170, 150], [120, 170, 235],
                        [90, 140, 220], [235, 140, 150], [210, 110, 125], [240, 170, 200], [215, 140, 175]], np.float32)
    height, width = rgba.shape[:2]
    rows = np.clip(np.arange(height) // _REGION_STEP, 0, label.shape[0] - 1)
    cols = np.clip(np.arange(width) // _REGION_STEP, 0, label.shape[1] - 1)
    full = label[rows][:, cols]
    tint = palette[np.clip(full, 0, len(palette) - 1)]
    base = rgba[..., :3].astype(np.float32)
    mixed = np.where((full >= 0)[..., None], base * .45 + tint * .55, base)
    out = np.dstack([np.clip(mixed, 0, 255).astype(np.uint8), rgba[..., 3]])
    image = Image.fromarray(out, 'RGBA')
    image.thumbnail((size, size), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, 'PNG', optimize=True)
    return buffer.getvalue()


def build_rig(png, joints=None):
    """Rig record and region preview for a drawing: proposed joints when none are given."""
    rgba, mask = load_alpha(png)
    height, width = mask.shape
    proposed = propose_joints(mask)
    chosen = proposed if joints is None else check_joints(joints, width, height)
    skinned = skin(png, chosen)
    ys, xs = np.nonzero(mask)
    rig = {'revision': RIG_REVISION, 'skeleton': SKELETON, 'width': width, 'height': height,
           'bounds': [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
           'joints': chosen, 'proposed': proposed, 'adjusted': chosen != proposed,
           'bones': [{'name': name, 'parent': parent, 'pivot': pivot, 'tail': tail, 'layer': layer}
                     for name, parent, pivot, tail, layer in BONES],
           'vertices': int(len(skinned['vertices'])), 'triangles': int(len(skinned['triangles']))}
    return rig, region_preview(rgba, skinned['label'])
