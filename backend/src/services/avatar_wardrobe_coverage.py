"""Which triangles of a wardrobe body one garment covers, so the viewer can hide skin under it.

Parts of one wardrobe body share its skeleton and export frame, so a garment GLB and the
body GLB are compared directly in rest-pose glTF space. A body vertex is covered when the
garment surface lies just outside it along its normal; a triangle is hidden only when all
three vertices are covered, so openings (cuffs, hems, collars) never show a gap.
"""
import base64

import numpy as np

from src.services.glb import parse_glb

GARMENT_SLOTS = ('top', 'bottom', 'shoes')
OUTSIDE_M = (-.005, .06)   # garment distance along the skin normal that counts as covering
SIDEWAYS_M = .02           # a garment point farther sideways belongs to a neighbouring area
DRESS_LEG_SHARE = .35      # a top covering this share of the thighs takes the bottom's place
_COMPONENTS = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def _accessor(doc, binary, index):
    item = doc['accessors'][index]
    view = doc['bufferViews'][item['bufferView']]
    dtype = np.dtype(_COMPONENTS[item['componentType']])
    width = _WIDTH[item['type']]
    start = view.get('byteOffset', 0) + item.get('byteOffset', 0)
    stride = view.get('byteStride') or dtype.itemsize*width
    raw = np.frombuffer(binary, dtype=np.uint8, count=stride*(item['count']-1) + dtype.itemsize*width, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, shape=(item['count'], dtype.itemsize*width), strides=(stride, 1))
    values = np.ascontiguousarray(rows).view(dtype).reshape(item['count'], width).astype(np.float64)
    if item.get('normalized'):
        values /= np.iinfo(dtype).max
    return values


def _local(node):
    if 'matrix' in node:
        return np.array(node['matrix'], dtype=float).reshape(4, 4).T
    x, y, z, w = node.get('rotation', [0, 0, 0, 1])
    matrix = np.eye(4)
    matrix[:3, :3] = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                               [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                               [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])*np.array(node.get('scale', [1, 1, 1]), dtype=float)
    matrix[:3, 3] = node.get('translation', [0, 0, 0])
    return matrix


def skinned_primitives(content):
    """Rest-pose positions (glTF world), triangles and dominant joint names per skinned primitive."""
    doc, binary = parse_glb(content)
    nodes = doc.get('nodes', [])
    parent = {child: index for index, node in enumerate(nodes) for child in node.get('children', [])}
    world = {}

    def world_of(index):
        if index not in world:
            world[index] = (world_of(parent[index]) if index in parent else np.eye(4)) @ _local(nodes[index])
        return world[index]
    result = []
    for index, node in enumerate(nodes):
        if 'mesh' not in node or 'skin' not in node:
            continue
        skin = doc['skins'][node['skin']]
        names = np.array([nodes[j].get('name', '') for j in skin['joints']])
        inverse = _accessor(doc, binary, skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
        matrices = np.stack([world_of(j) for j in skin['joints']]) @ inverse
        for number, primitive in enumerate(doc['meshes'][node['mesh']]['primitives']):
            attributes = primitive.get('attributes', {})
            if not {'POSITION', 'JOINTS_0', 'WEIGHTS_0'} <= set(attributes):
                continue
            positions = _accessor(doc, binary, attributes['POSITION'])
            joints = _accessor(doc, binary, attributes['JOINTS_0']).astype(np.int64)
            weights = _accessor(doc, binary, attributes['WEIGHTS_0'])
            weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)
            homogeneous = np.c_[positions, np.ones(len(positions))]
            rest = np.zeros((len(positions), 3))
            for k in range(joints.shape[1]):
                rest += weights[:, k:k+1]*np.einsum('nij,nj->ni', matrices[joints[:, k]], homogeneous)[:, :3]
            indices = (_accessor(doc, binary, primitive['indices']).astype(np.int64).reshape(-1)
                       if 'indices' in primitive else np.arange(len(positions)))
            result.append({'key': f"{node['mesh']}:{number}", 'positions': rest.astype(np.float32),
                           'triangles': indices.reshape(-1, 3),
                           'joints': names[joints[np.arange(len(joints)), weights.argmax(axis=1)]]})
    return result


def _normals(positions, triangles):
    normals = np.zeros_like(positions, dtype=np.float64)
    a, b, c = (positions[triangles[:, i]].astype(np.float64) for i in range(3))
    face = np.cross(b - a, c - a)
    for i in range(3):
        np.add.at(normals, triangles[:, i], face)
    return (normals/np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)).astype(np.float32)


def _covered(positions, normals, garment, chunk=256):
    """Body vertices with garment surface just outside them. Chunks follow height (glTF Y),
    and each chunk only meets the garment points inside its own padded box."""
    covered = np.zeros(len(positions), dtype=bool)
    reach = max(-OUTSIDE_M[0], OUTSIDE_M[1]) + SIDEWAYS_M
    order = np.argsort(positions[:, 1], kind='stable')
    for start in range(0, len(order), chunk):
        index = order[start:start+chunk]
        points, directions = positions[index], normals[index]
        low, high = points.min(axis=0) - reach, points.max(axis=0) + reach
        near = garment[np.all((garment >= low) & (garment <= high), axis=1)]
        if not len(near):
            continue
        offset = near[None, :, :] - points[:, None, :]
        along = np.einsum('cgk,ck->cg', offset, directions)
        sideways = np.linalg.norm(offset - along[:, :, None]*directions[:, None, :], axis=2)
        covered[index] = ((along > OUTSIDE_M[0]) & (along < OUTSIDE_M[1]) & (sideways < SIDEWAYS_M)).any(axis=1)
    return covered


def coverage(body, part_content, slot):
    """{hidden: {primitive key: base64 bitset of triangles}, triangles: {key: count}, covers_bottom}.

    body: skinned_primitives() of the wardrobe body GLB (parse once, reuse for every part).
    """
    garment = np.concatenate([p['positions'] for p in skinned_primitives(part_content)] or [np.zeros((0, 3), np.float32)])
    if len(garment) > 20000:
        garment = garment[np.random.default_rng(0).choice(len(garment), 20000, replace=False)]
    hidden, counts, thigh = {}, {}, [0, 0]
    for primitive in body:
        positions, triangles = primitive['positions'], primitive['triangles']
        covered = _covered(positions, _normals(positions, triangles), garment) if len(garment) else np.zeros(len(positions), bool)
        faces = covered[triangles].all(axis=1)
        counts[primitive['key']] = int(len(triangles))
        hidden[primitive['key']] = base64.b64encode(np.packbits(faces, bitorder='little').tobytes()).decode()
        legs = np.isin(np.char.lower(primitive['joints'].astype(str)), ('leftupleg', 'rightupleg'))
        thigh[0] += int((covered & legs).sum()); thigh[1] += int(legs.sum())
    share = thigh[0]/thigh[1] if thigh[1] else 0.
    return {'slot': slot, 'hidden': hidden, 'triangles': counts,
            'covers_bottom': bool(slot == 'top' and share >= DRESS_LEG_SHARE), 'thigh_share': round(share, 3)}
