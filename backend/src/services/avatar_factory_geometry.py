"""Canonical compiler, executed by the isolated Blender Python worker (numpy bundled).

Source UVs/materials and triangle lineage survive; the output rig is newly authored.
Spatial segmentation and fitted weights are review candidates, never semantic approval.
"""
from copy import deepcopy
import json
import math
from pathlib import Path

import numpy as np

from src.services.glb import parse_glb, build_glb

ROLE_SLOT = {'head': 'face', 'eyes': 'face', 'hair': 'hair', 'hat': 'hat', 'top': 'top',
             'pants': 'bottom', 'skirt': 'bottom', 'dress': 'onepiece', 'outfit_base': 'onepiece',
             'shoes': 'shoes', 'accessory': 'back'}
MASKS = {'face': ['head'], 'top': ['torsoUpper', 'torsoLower', 'armUpperL', 'armUpperR'],
         'bottom': ['torsoLower', 'legUpperL', 'legUpperR'], 'onepiece': ['torsoUpper', 'torsoLower', 'legUpperL', 'legUpperR'],
         'shoes': ['footL', 'footR']}
ALIASES = {'pelvis': 'hips', 'spine1': 'chest', 'spine2': 'upperChest', 'leftarm': 'upperArmL',
           'rightarm': 'upperArmR', 'leftforearm': 'lowerArmL', 'rightforearm': 'lowerArmR',
           'lefthand': 'handL', 'righthand': 'handR', 'leftupleg': 'upperLegL', 'rightupleg': 'upperLegR',
           'leftleg': 'lowerLegL', 'rightleg': 'lowerLegR', 'leftfoot': 'footL', 'rightfoot': 'footR',
           'leftshoulder': 'shoulderL', 'rightshoulder': 'shoulderR'}
for side in ('L', 'R'):
    for source, target in [('upper_arm', 'upperArm'), ('forearm', 'lowerArm'), ('hand', 'hand'),
                           ('thigh', 'upperLeg'), ('shin', 'lowerLeg'), ('foot', 'foot')]:
        ALIASES[(source + '.' + side).lower()] = target + side


def accessor(doc, binary, index):
    a = doc['accessors'][index]
    if a.get('sparse') or 'bufferView' not in a:
        raise ValueError('Sparse geometry needs a decoded source')
    v = doc['bufferViews'][a['bufferView']]
    dtype = np.dtype({5120: 'i1', 5121: 'u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}[a['componentType']])
    n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
    result = np.ndarray((a['count'], n), dtype=dtype, buffer=binary,
                        offset=v.get('byteOffset', 0) + a.get('byteOffset', 0),
                        strides=(v.get('byteStride', dtype.itemsize * n), dtype.itemsize)).copy()
    if a.get('normalized') and dtype.kind in 'ui':
        result = np.maximum(result.astype(float) / np.iinfo(dtype).max, -1)
    return result


def world_matrices(doc):
    parents = {child: i for i, node in enumerate(doc['nodes']) for child in node.get('children', [])}
    cache = {}
    def world(i):
        if i in cache:
            return cache[i]
        node = doc['nodes'][i]
        if 'matrix' in node:
            matrix = np.array(node['matrix']).reshape(4, 4).T
        else:
            x, y, z, w = node.get('rotation', [0, 0, 0, 1])
            matrix = np.eye(4)
            matrix[:3, :3] = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                                      [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                                      [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]) @ np.diag(node.get('scale', [1, 1, 1]))
            matrix[:3, 3] = node.get('translation', [0, 0, 0])
        cache[i] = world(parents[i]) @ matrix if i in parents else matrix
        return cache[i]
    return [world(i) for i in range(len(doc['nodes']))]


class Package:
    def __init__(self, rig, source=None):
        self.rig = rig
        self.doc = {'asset': {'version': '2.0', 'generator': 'Gaesup Avatar Factory v1'}, 'scene': 0,
                    'scenes': [{'nodes': [0]}], 'nodes': [], 'meshes': [], 'accessors': [], 'bufferViews': []}
        self.binary = bytearray()
        self.positions = {}
        self.bones = {item[0]: i for i, item in enumerate(rig['bones'])}
        for name, parent, x, y, z in rig['bones']:
            node = {'name': name, 'translation': [x, y, z]}
            self.positions[name] = np.array([x, y, z]) + (self.positions[parent] if parent else 0)
            self.doc['nodes'].append(node)
            if parent:
                self.doc['nodes'][self.bones[parent]].setdefault('children', []).append(self.bones[name])
        inverses = []
        for position in self.positions.values():
            matrix = np.eye(4); matrix[:3, 3] = -position
            inverses.append(matrix.T.ravel())
        self.doc['skins'] = [{'name': rig['id'], 'skeleton': 0, 'joints': list(range(len(self.bones))),
                              'inverseBindMatrices': self.add(inverses, 'MAT4')}]
        if source:
            source_doc, source_bin = source
            # Images stay embedded, preserving their original bytes and UV appearance.
            self.doc['images'] = deepcopy(source_doc.get('images', []))
            for image in self.doc['images']:
                if 'uri' in image:
                    raise ValueError('Embed textures into the source GLB first')
                v = source_doc['bufferViews'][image['bufferView']]
                image['bufferView'] = self.blob(source_bin[v.get('byteOffset', 0):v.get('byteOffset', 0)+v['byteLength']])
            for key in ('materials', 'textures', 'samplers', 'extensionsUsed'):
                if key in source_doc:
                    self.doc[key] = deepcopy(source_doc[key])
        self.doc.setdefault('materials', []).append({'name': 'Maple SD neutral skin', 'pbrMetallicRoughness': {
            'baseColorFactor': [.91, .70, .59, 1], 'metallicFactor': 0, 'roughnessFactor': .8}})
        self.skin_material = len(self.doc['materials']) - 1
        self.body_materials = {'skin': self.skin_material}

    def body_material(self, name):
        region = name.split('.')[0]
        style = ('eye' if '.eye' in name or '.brow' in name else 'white' if '.shine' in name else
                 'mouth' if '.mouth' in name else 'shirt' if region == 'torsoUpper' or '.sleeve' in name else
                 'shorts' if region == 'torsoLower' or '.shorts' in name else 'white' if region.startswith('foot') else 'skin')
        if style not in self.body_materials:
            colors = {'shirt': [.86, .89, .91, 1], 'shorts': [.09, .17, .29, 1],
                      'white': [.96, .96, .94, 1], 'eye': [.07, .045, .065, 1], 'mouth': [.30, .13, .13, 1]}
            self.body_materials[style] = len(self.doc['materials'])
            self.doc['materials'].append({'name': 'Common body '+style,
                'pbrMetallicRoughness': {'baseColorFactor': colors[style], 'metallicFactor': 0, 'roughnessFactor': .8}})
        return self.body_materials[style]

    def blob(self, data):
        self.binary.extend(b'\0' * (-len(self.binary) % 4))
        self.doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(self.binary), 'byteLength': len(data)})
        self.binary.extend(data)
        return len(self.doc['bufferViews']) - 1

    def add(self, values, kind, component=5126, bounds=False):
        array = np.asarray(values, dtype={5126: '<f4', 5123: '<u2', 5125: '<u4'}[component])
        a = {'bufferView': self.blob(array.tobytes()), 'componentType': component, 'count': len(array), 'type': kind}
        if bounds:
            a.update(min=array.min(axis=0).tolist(), max=array.max(axis=0).tolist())
        self.doc['accessors'].append(a)
        return len(self.doc['accessors']) - 1

    def mesh(self, name, points, triangles, joints, weights, material, extras=None):
        normal = np.zeros_like(points)
        face_normal = np.cross(points[triangles[:, 1]]-points[triangles[:, 0]], points[triangles[:, 2]]-points[triangles[:, 0]])
        for axis in range(3):
            np.add.at(normal, triangles[:, axis], face_normal)
        normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-10)
        attrs = {'POSITION': self.add(points, 'VEC3', bounds=True), 'NORMAL': self.add(normal, 'VEC3'),
                 'JOINTS_0': self.add(joints, 'VEC4', 5123), 'WEIGHTS_0': self.add(weights, 'VEC4')}
        for key, values in (extras or {}).items():
            attrs[key] = self.add(values, {2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[values.shape[1]])
        primitive = {'attributes': attrs, 'indices': self.add(triangles.reshape(-1, 1), 'SCALAR', 5125), 'material': material}
        node = len(self.doc['nodes'])
        self.doc['nodes'].append({'name': name, 'mesh': len(self.doc['meshes']), 'skin': 0})
        self.doc['meshes'].append({'primitives': [primitive]})
        self.doc['scenes'][0]['nodes'].append(node)
        return {'node': node, 'primitive': 0}

    def motions(self, template):
        doc, binary = parse_glb(template.read_bytes(), strict=True)
        self.doc['animations'] = []
        for clip in doc.get('animations', []):
            target = deepcopy(clip)
            for sampler in target['samplers']:
                for key in ('input', 'output'):
                    index = sampler[key]
                    sampler[key] = self.add(accessor(doc, binary, index), doc['accessors'][index]['type'], bounds=key == 'input')
            for channel in target['channels']:
                source_node = doc['nodes'][channel['target']['node']]
                name = source_node['name']
                if channel['target']['path'] == 'translation' and self.rig['id'] != 'gaesup-humanoid-v1':
                    original = clip['samplers'][channel['sampler']]['output']
                    values = accessor(doc, binary, original)
                    rest = np.array(self.doc['nodes'][self.bones[name]]['translation'])
                    values = values-np.array(source_node.get('translation', [0, 0, 0]))+rest
                    target['samplers'][channel['sampler']]['output'] = self.add(values, 'VEC3')
                channel['target']['node'] = self.bones[name]
            self.doc['animations'].append(target)

    def write(self, path):
        # Imported sources can carry materials unused by their selected part.
        # Prune those records before validating/exporting the assembled asset.
        primitives = [p for mesh in self.doc['meshes'] for p in mesh['primitives']]
        used = sorted({p['material'] for p in primitives if 'material' in p})
        remap = {old: new for new, old in enumerate(used)}
        self.doc['materials'] = [self.doc['materials'][i] for i in used]
        for primitive in primitives:
            if 'material' in primitive:
                primitive['material'] = remap[primitive['material']]
        self.doc['buffers'] = [{'byteLength': len(self.binary)}]
        path.write_bytes(build_glb(self.doc, bytes(self.binary)))


def ellipsoid(center, radius, start=None, end=None):
    # Closed rings with explicit pole fans, no duplicate degenerate pole triangles.
    n, rows = 24, 12
    points = [[0, 1, 0]]
    for row in range(1, rows):
        phi = math.pi * row / rows
        points += [[math.sin(phi)*math.cos(2*math.pi*j/n), math.cos(phi), math.sin(phi)*math.sin(2*math.pi*j/n)] for j in range(n)]
    points.append([0, -1, 0]); faces = []
    for j in range(n):
        faces += [[0, 1+(j+1)%n, 1+j], [len(points)-1, 1+(rows-2)*n+j, 1+(rows-2)*n+(j+1)%n]]
    for row in range(rows-2):
        for j in range(n):
            a, b = 1+row*n+j, 1+row*n+(j+1)%n
            faces += [[a, b, b+n], [a, b+n, a+n]]
    points = np.array(points) * radius
    if start is not None:
        axis = end-start; axis /= np.linalg.norm(axis)
        u = np.cross(axis, [0, 0, 1]); u /= np.linalg.norm(u)
        points = points @ np.array([u, axis, np.cross(u, axis)])
    return points + center, np.array(faces)


def weights_for(points, package, candidates):
    positions = package.positions
    children = {parent: name for name, parent, *_ in package.rig['bones'] if parent}
    distances = []
    for name in candidates:
        head = positions[name]; tail = positions.get(children.get(name), head + [0, .08, 0])
        axis = tail-head
        t = np.clip((points-head) @ axis / max(float(axis @ axis), 1e-10), 0, 1)
        distances.append(np.linalg.norm(points-head-t[:, None]*axis, axis=1))
    distances = np.array(distances).T
    order = np.argsort(distances, axis=1)[:, :min(4, len(candidates))]
    values = 1 / np.maximum(np.take_along_axis(distances, order, axis=1), .035) ** 3
    values /= values.sum(axis=1, keepdims=True)
    joints = np.zeros((len(points), 4), dtype=int); weights = np.zeros((len(points), 4))
    joints[:, :order.shape[1]] = np.array([package.bones[name] for name in candidates])[order]
    weights[:, :order.shape[1]] = values
    return joints, weights


def body_geometry(package):
    if package.rig['id'] == 'gaesup-maple-v1':
        yield from maple_body_geometry(package)
        return
    p = package.positions
    regions = [('head', p['head'], [.35, .37, .30], ['head']),
               ('neck', p['neck'], [.085, .10, .085], ['neck']),
               ('torsoUpper', [0, .995, 0], [.215, .205, .145], ['spine', 'chest', 'upperChest']),
               ('torsoLower', [0, .76, 0], [.18, .15, .125], ['hips', 'spine'])]
    for side in ('L', 'R'):
        for region, bone, target, radius in [('armUpper', 'upperArm', 'lowerArm', .068), ('armLower', 'lowerArm', 'hand', .06),
                                            ('legUpper', 'upperLeg', 'lowerLeg', .087), ('legLower', 'lowerLeg', 'foot', .075)]:
            a, b = p[bone+side], p[target+side]
            points, triangles = ellipsoid((a+b)/2, [radius, np.linalg.norm(b-a)/2+.04, radius], a, b)
            yield region+side, points, triangles, [bone+side, target+side]
            if region in ('armUpper', 'legUpper'):
                # Opaque base clothes belong to body regions, so wardrobe masks hide
                # the sleeve/shorts together with the body underneath, then restore both.
                tip = a+(b-a)*(.48 if region == 'armUpper' else .62)
                width = .09 if region == 'armUpper' else .102
                points, triangles = ellipsoid((a+tip)/2, [width, np.linalg.norm(tip-a)/2+.025, width], a, tip)
                suffix = '.sleeve' if region == 'armUpper' else '.shorts'
                yield region+side+suffix, points, triangles, [bone+side]
        regions += [('hand'+side, p['hand'+side]+[0, -.025, .015], [.072, .09, .05], ['hand'+side]),
                    ('foot'+side, p['foot'+side]+[0, -.035, .065], [.079, .075, .135], ['foot'+side])]
    for name, center, radius, bones in regions:
        points, triangles = ellipsoid(center, radius)
        yield name, points, triangles, bones
    head = p['head']
    for side, x in [('L', .113), ('R', -.113)]:
        for feature, offset, radius in [('eye', [x, .008, .278], [.038, .061, .022]),
                                        ('shine', [x-.008, .033, .300], [.013, .017, .007]),
                                        ('brow', [x, .103, .269], [.035, .008, .008])]:
            points, triangles = ellipsoid(head+offset, radius)
            yield f'head.{feature}{side}', points, triangles, ['head']
    for i in range(5):
        x = -.035+i*.014; end_x = x+.014
        a = head+np.array([x, -.113+.022*(x/.035)**2, .289])
        b = head+np.array([end_x, -.113+.022*(end_x/.035)**2, .289])
        points, triangles = ellipsoid((a+b)/2, [.005, np.linalg.norm(b-a)/2+.002, .005], a, b)
        yield f'head.mouth{i}', points, triangles, ['head']


def maple_body_geometry(package):
    """Large head, almost concealed neck and short, separate limb chains."""
    p = package.positions
    regions = [('head', p['head'], [.61, .57, .46], ['head']),
               ('neck', p['neck'], [.07, .055, .07], ['neck']),
               ('torsoUpper', [0, .47, 0], [.20, .17, .14], ['spine', 'chest', 'upperChest']),
               ('torsoLower', [0, .29, 0], [.18, .09, .125], ['hips'])]
    for side in ('L', 'R'):
        for region, bone, target, radius in [('armUpper', 'upperArm', 'lowerArm', .07),
                ('armLower', 'lowerArm', 'hand', .065), ('legUpper', 'upperLeg', 'lowerLeg', .085),
                ('legLower', 'lowerLeg', 'foot', .075)]:
            a, b = p[bone+side], p[target+side]
            vertices, triangles = ellipsoid((a+b)/2, [radius, np.linalg.norm(b-a)/2+.028, radius], a, b)
            yield region+side, vertices, triangles, [bone+side, target+side]
            if region in ('armUpper', 'legUpper'):
                tip = a+(b-a)*.6
                vertices, triangles = ellipsoid((a+tip)/2, [radius+.018, np.linalg.norm(tip-a)/2+.025, radius+.018], a, tip)
                yield region+side+('.sleeve' if region=='armUpper' else '.shorts'), vertices, triangles, [bone+side]
        regions += [('hand'+side, p['hand'+side]+[0, -.012, .025], [.065, .07, .055], ['hand'+side]),
                    ('foot'+side, p['foot'+side]+[0, -.025, .05], [.09, .055, .12], ['foot'+side])]
    for name, center, radius, bones in regions:
        vertices, triangles = ellipsoid(center, radius)
        yield name, vertices, triangles, bones
    # Features sit low on the broad face, matching the chibi head rather than
    # a small adult face centered on a spherical skull.
    head = p['head']
    for side, x in [('L', .205), ('R', -.205)]:
        for feature, offset, radius in [('eye', [x, -.16, .42], [.07, .095, .027]),
                ('shine', [x-.015, -.12, .446], [.024, .029, .008]),
                ('brow', [x, -.015, .436], [.06, .01, .009])]:
            vertices, triangles = ellipsoid(head+offset, radius)
            yield f'head.{feature}{side}', vertices, triangles, ['head']
    for i in range(5):
        x = -.05+i*.02
        a = head+np.array([x, -.315+.024*(x/.05)**2, .385])
        b = head+np.array([x+.02, -.315+.024*((x+.02)/.05)**2, .385])
        vertices, triangles = ellipsoid((a+b)/2, [.006, np.linalg.norm(b-a)/2+.002, .006], a, b)
        yield f'head.mouth{i}', vertices, triangles, ['head']


def compile_source(payload, progress):
    output = Path(payload['output']); rig = json.loads(Path(payload['rig']).read_text())
    doc, binary = parse_glb(Path(payload['source']).read_bytes(), strict=True)
    world = world_matrices(doc); mesh_data = []; roles = {part['node_index']: part['role'] for part in payload.get('parts', [])}
    for i, node in enumerate(doc['nodes']):
        if 'mesh' not in node:
            continue
        for j, primitive in enumerate(doc['meshes'][node['mesh']]['primitives']):
            if primitive.get('mode', 4) != 4 or primitive.get('extensions', {}).get('KHR_draco_mesh_compression'):
                raise ValueError('Decode compressed geometry before factory import')
            local = accessor(doc, binary, primitive['attributes']['POSITION'])
            points = np.c_[local, np.ones(len(local))] @ world[i].T
            indices = accessor(doc, binary, primitive['indices']).reshape(-1, 3).astype(int) if 'indices' in primitive else np.arange(len(local)).reshape(-1, 3)
            mesh_data.append((i, j, primitive, points[:, :3], indices))
    if not mesh_data:
        raise ValueError('Source has no triangle meshes')
    points = np.concatenate([points[np.unique(tris)] for _, _, _, points, tris in mesh_data]); lo, hi = points.min(0), points.max(0)
    height = hi[1]-lo[1]
    if height < 1e-5:
        raise ValueError('Source must stand along glTF Y-up')
    base = Package(rig); target = base.positions
    aliases = {name.lower(): name for name in target} | ALIASES
    source_bones = {}
    for i, node in enumerate(doc['nodes']):
        name = node.get('name', '').lower().removeprefix('mixamorig:')
        if name in aliases:
            source_bones[aliases[name]] = world[i][:3, 3]
    scale = 1.81/height
    normalized = lambda p: (p - [float((lo[0]+hi[0])/2), lo[1], float((lo[2]+hi[2])/2)]) * scale
    source_bones = {name: normalized(p) for name, p in source_bones.items()}
    # Existing source roles are hash-bound. Without them, export spatial candidates for correction.
    progress('segment', '원본 면과 파츠 역할을 분리하는 중')
    groups = {}; lineage = []; quarantined = 0
    for i, j, primitive, source_points, triangles in mesh_data:
        norm = normalized(source_points); centers = norm[triangles].mean(axis=1)
        assigned = np.full(len(triangles), roles.get(i, ''), dtype=object)
        if i not in roles:
            assigned[:] = 'top'
            assigned[centers[:, 1] < .76] = 'pants'
            assigned[centers[:, 1] < .16] = 'shoes'
            neck_y = source_bones.get('neck', source_bones.get('head', np.array([0, 1.1, 0])))[1]
            assigned[centers[:, 1] > max(.8, neck_y)] = 'head'
        for selection in payload.get('selections', []):
            if selection['node_index'] == i and selection['primitive_index'] == j:
                assigned[selection['faces']] = selection['role']
        # A role label cannot make a distant hair strand into a shoe/skirt. Keep outliers
        # in the source-addressed report instead of stretching them across the new body.
        hips_y = source_bones.get('hips', np.array([0, .6, 0]))[1]
        stray = ((assigned == 'shoes') & (centers[:, 1] > hips_y*.82))
        stray |= ((assigned == 'skirt') & (centers[:, 1] < hips_y*.52))
        quarantined += int(stray.sum()); assigned[stray] = 'other'
        for role in sorted(set(assigned)):
            faces = np.where(assigned == role)[0]
            lineage.append({'node_index': i, 'primitive_index': j, 'role': role, 'faces': faces.tolist()})
            slot = ROLE_SLOT.get(role)
            if slot:
                groups.setdefault(slot, []).append((norm, triangles[faces], primitive, role))
    if not groups:
        raise ValueError('No wearable regions. Assign original faces to clothing/head roles first')
    head_points = [p[np.unique(t)] for p, t, _, role in groups.get('face', []) if role == 'head']
    if head_points:
        hp = np.concatenate(head_points); head_center = (hp.min(0)+hp.max(0))/2
        head_scale = min(.56/max(np.ptp(hp[:, 0]), .1), .60/max(np.ptp(hp[:, 1]), .1))
    else:
        head_center = np.array([0, 1.44, 0]); head_scale = 1.
    progress('fit', '공통 SD 몸 비율에 원본 파츠를 맞추는 중')
    def fit(p, slot):
        if slot in ('face', 'hair', 'hat'):
            return (p-head_center)*head_scale + target['head'] + [0, -.08, .05]
        if slot == 'shoes':
            fitted = p.copy()
            for side, sign in [('L', 1), ('R', -1)]:
                selected = p[:, 0]*sign >= 0
                if not selected.any():
                    continue
                vertices = p[selected]; lo, hi = vertices.min(0), vertices.max(0)
                fitted[selected] = (vertices-(lo+hi)/2)/np.maximum((hi-lo)/2, .01)*[.087, .115, .15] + target['foot'+side]+[0, .01, .065]
            return fitted
        if slot == 'bottom':
            fitted = p.copy()
            hips_y = max(source_bones.get('hips', np.array([0, .6, 0]))[1], .1)
            fitted[:, 1] *= .72/hips_y
            source_width = max(abs(source_bones.get('upperLegL', np.array([.105, 0, 0]))[0]), .05)
            fitted[:, [0, 2]] *= .105/source_width
            return fitted
        available = [name for name in source_bones if name in target and name not in ('root', 'head')]
        if len(available) < 5:
            return p.copy()
        # Landmark displacement with compact inverse-distance blending. Existing source armatures
        # supply the landmarks, but all exported weights and inverse binds are canonical.
        centers = np.array([source_bones[name] for name in available])
        distances = np.linalg.norm(p[:, None, :]-centers[None, :, :], axis=2)
        order = np.argsort(distances, axis=1)[:, :3]
        weights = 1 / np.maximum(np.take_along_axis(distances, order, 1), .03) ** 3
        weights /= weights.sum(axis=1, keepdims=True)
        delta = np.array([target[name]-source_bones[name] for name in available])
        return p + (delta[order]*weights[:, :, None]).sum(axis=1)
    combined = Package(rig, (doc, binary)); body = Package(rig)
    body_refs = {}; assets = []
    progress('rig', '공통 23-bone rig와 새 스킨 가중치를 적용하는 중')
    for region, vertices, triangles, bones in body_geometry(body):
        joints, weights = weights_for(vertices, body, bones)
        body_refs.setdefault(region.split('.')[0], []).append(body.mesh(region, vertices, triangles, joints, weights, body.body_material(region)))
        combined.mesh('body_'+region, vertices, triangles, joints, weights, combined.body_material(region))
    template = Path(payload['motions'])
    body.motions(template); body.write(output/'body.glb')
    assets.append({'key': 'body', 'file': 'body.glb', 'meshes': [ref for group in body_refs.values() for ref in group], 'bodyRegions': body_refs})
    counts = {}
    for slot, items in groups.items():
        part = Package(rig, (doc, binary)); refs = []
        candidates = ['head'] if slot in ('face', 'hair', 'hat') else (
            ['footL', 'footR'] if slot == 'shoes' else
            ['hips', 'upperLegL', 'upperLegR', 'lowerLegL', 'lowerLegR'] if slot == 'bottom' else
            [name for name in target if name not in ('root', 'head', 'toeL', 'toeR')])
        for index, (norm, triangles, primitive, role) in enumerate(items):
            used, inverse = np.unique(triangles, return_inverse=True); triangles = inverse.reshape(-1, 3)
            fitted = fit(norm[used], slot)
            joints, weights = weights_for(fitted, part, candidates)
            extras = {name: accessor(doc, binary, a)[used] for name, a in primitive['attributes'].items() if name.startswith('TEXCOORD_') or name.startswith('COLOR_')}
            material = primitive.get('material', part.skin_material)
            refs.append(part.mesh(f'{slot}_{index}', fitted, triangles, joints, weights, material, extras))
            combined.mesh(f'{slot}_{index}', fitted, triangles, joints, weights, primitive.get('material', combined.skin_material), extras)
            counts[slot] = counts.get(slot, 0) + len(triangles)
        part.write(output/f'{slot}.glb')
        assets.append({'key': slot, 'file': f'{slot}.glb', 'meshes': refs, 'hideBodyRegions': MASKS.get(slot, [])})
    # Combined preview masks covered regions too, matching the runtime outfit.
    combined.motions(template); combined.write(output/'workspace.glb')
    hidden = {region for slot in groups for region in MASKS.get(slot, [])}
    combined.doc['scenes'][0]['nodes'] = [i for i in combined.doc['scenes'][0]['nodes'] if combined.doc['nodes'][i]['name'].removeprefix('body_').split('.')[0] not in hidden]
    combined.write(output/'character.glb')
    return {'assets': assets, 'bones': body.bones, 'source_triangles': sum(len(t) for *_, t in mesh_data),
            'part_triangles': counts, 'selections': lineage, 'quarantined_faces': quarantined, 'source_bone_mapping': sorted(source_bones),
            'segmentation': 'source_bound_roles' if roles else 'spatial_candidates',
            'body_origin': 'authored_maple_sd_clothed_template_v2', 'rig_origin': 'canonical_rebind',
            'limitations': [f'해부학적 영역을 벗어난 {quarantined}개 면은 보류 영역으로 기록', '분리 경계와 의상 여유분은 검수 필요', '기본 몸은 새 공통 템플릿이며 원본의 가려진 몸 복원이 아님',
                            '공통 동작은 변형 검사 클립이며 원본 동작을 리타기팅한 결과가 아님']}


PART_BOXES = {
    'face': ([-.35, 1.07, -.28], [.35, 1.81, .30]),
    'hairBack': ([-.40, .90, -.34], [.40, 1.86, .08]),
    'hairFront': ([-.37, 1.28, .06], [.37, 1.85, .35]),
    'hat': ([-.43, 1.53, -.35], [.43, 2.04, .36]),
    'top': ([-.56, .67, -.16], [.56, 1.16, .18]),
    'bottom': ([-.25, .42, -.17], [.25, .79, .19]),
    'shoes': ([-.20, 0, -.095], [.20, .24, .225]),
}

MAPLE_BOXES = {
    'face': ([-.61, .65, -.46], [.61, 1.79, .46]),
    'hairBack': ([-.69, .17, -.49], [.69, 1.85, .12]),
    'hairFront': ([-.65, .84, .08], [.65, 1.84, .52]),
    'hat': ([-.80, 1.45, -.51], [.80, 2.05, .54]),
    'top': ([-.435, .29, -.16], [.435, .675, .18]),
    'bottom': ([-.245, .215, -.17], [.245, .355, .19]),
    'shoes': ([-.205, 0, -.08], [.205, .25, .22]),
}


def head_neck_cut(points):
    """Find a narrow neck below a broad head; never cut a plain round head.

    This is a geometric candidate with source face IDs in the output evidence,
    not a claim that the provider obeyed the head-only prompt.
    """
    lo, hi = points.min(0), points.max(0)
    height, width = hi[1]-lo[1], hi[0]-lo[0]
    samples = []
    for fraction in np.arange(.08, .36, .02):
        band = points[(points[:, 1] >= lo[1]+fraction*height) & (points[:, 1] < lo[1]+(fraction+.025)*height)]
        if len(band): samples.append((fraction, np.ptp(band[:, 0])/width))
    if not samples: return None
    fraction, ratio = min(samples, key=lambda value: value[1])
    below = [w for y, w in samples if y < fraction-.04]
    above = points[(points[:, 1] > lo[1]+.35*height) & (points[:, 1] < lo[1]+.7*height)]
    if .12 <= fraction <= .30 and ratio < .28 and below and max(below) > ratio*1.35 and len(above) and np.ptp(above[:, 0]) > width*.75:
        return float(lo[1]+(fraction+.025)*height)
    return None


def part_weights(points, package, slot):
    if slot in ('face', 'hair', 'hat'):
        return weights_for(points, package, ['head'])
    if slot == 'bottom':
        # A skirt must not be pulled apart by the left/right thigh chains.
        return weights_for(points, package, ['hips'])
    joints = np.zeros((len(points), 4), dtype=int); weights = np.zeros((len(points), 4))
    for side, sign in [('L', 1), ('R', -1)]:
        selected = points[:, 0]*sign >= 0 if side == 'L' else points[:, 0] < 0
        if slot == 'shoes':
            names = ['foot'+side, 'lowerLeg'+side]
        else:
            # Keep torso influences off the sleeve tips and left/right limbs
            # out of each other's influence set.
            torso = selected & (np.abs(points[:, 0]) < .19)
            joints[torso], weights[torso] = weights_for(points[torso], package, ['spine', 'chest', 'upperChest'])
            selected &= ~torso
            names = ['upperArm'+side, 'lowerArm'+side, 'hand'+side]
        if selected.any():
            joints[selected], weights[selected] = weights_for(points[selected], package, names)
    return joints, weights


def import_materials(package, source_doc, binary):
    """Append one source's embedded textures/materials without dropping earlier parts."""
    doc = package.doc
    offsets = {key: len(doc.setdefault(key, [])) for key in ('images', 'textures', 'samplers', 'materials')}
    for image in deepcopy(source_doc.get('images', [])):
        if 'uri' in image:
            raise ValueError('Part textures must be embedded in GLB')
        view = source_doc['bufferViews'][image['bufferView']]
        start = view.get('byteOffset', 0)
        image['bufferView'] = package.blob(binary[start:start+view['byteLength']])
        doc['images'].append(image)
    doc['samplers'].extend(deepcopy(source_doc.get('samplers', [])))
    for texture in deepcopy(source_doc.get('textures', [])):
        if 'source' in texture: texture['source'] += offsets['images']
        if 'sampler' in texture: texture['sampler'] += offsets['samplers']
        for extension in texture.get('extensions', {}).values():
            if 'source' in extension: extension['source'] += offsets['images']
        doc['textures'].append(texture)
    def fix(value, key=''):
        if isinstance(value, dict):
            if key.lower().endswith('texture') and 'index' in value:
                value['index'] += offsets['textures']
            for name, child in value.items(): fix(child, name)
        elif isinstance(value, list):
            for child in value: fix(child)
    materials = deepcopy(source_doc.get('materials', [])); fix(materials)
    doc['materials'].extend(materials)
    doc['extensionsUsed'] = sorted(set(doc.get('extensionsUsed', [])) | set(source_doc.get('extensionsUsed', [])))
    return offsets['materials']


def compile_part_models(payload, progress):
    """Image-first route: independently generated pieces fitted to one authored body/rig."""
    output = Path(payload['output']); rig = json.loads(Path(payload['rig']).read_text())
    body, combined = Package(rig), Package(rig)
    refs = {}; assets = []; counts = {}; packages = {}; provenance = []; segmentation = []
    maple = rig['id'] == 'gaesup-maple-v1'
    boxes = MAPLE_BOXES if maple else PART_BOXES
    for region, points, triangles, bones in body_geometry(body):
        joints, weights = weights_for(points, body, bones)
        refs.setdefault(region.split('.')[0], []).append(body.mesh(region, points, triangles, joints, weights, body.body_material(region)))
        combined.mesh('body_'+region, points, triangles, joints, weights, combined.body_material(region))
    body.motions(Path(payload['motions'])); body.write(output/'body.glb')
    assets.append({'key': 'body', 'file': 'body.glb', 'meshes': [ref for group in refs.values() for ref in group], 'bodyRegions': refs})
    progress('fit', '개별 생성한 파츠를 공통 몸 연결점에 맞추는 중')
    for item in payload['part_models']:
        source_path = Path(item['path'])
        import hashlib
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Generated part source changed')
        source, binary = parse_glb(source_path.read_bytes(), strict=True); worlds = world_matrices(source)
        primitives = []
        for i, node in enumerate(source['nodes']):
            if 'mesh' not in node: continue
            for primitive in source['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode', 4) != 4 or primitive.get('extensions', {}).get('KHR_draco_mesh_compression'):
                    raise ValueError('Expected decoded part triangle geometry')
                local = accessor(source, binary, primitive['attributes']['POSITION'])
                points = (np.c_[local, np.ones(len(local))] @ worlds[i].T)[:, :3]
                triangles = accessor(source, binary, primitive['indices']).reshape(-1, 3).astype(int) if 'indices' in primitive else np.arange(len(points)).reshape(-1, 3)
                primitives.append((primitive, points, triangles))
        if not primitives: raise ValueError('Generated part has no mesh')
        all_points = np.concatenate([p[np.unique(t)] for _, p, t in primitives]); lo, hi = all_points.min(0), all_points.max(0)
        cut = head_neck_cut(all_points) if item['slot'] == 'face' else None
        if cut is not None:
            trimmed = []
            for index, (primitive, points, triangles) in enumerate(primitives):
                keep = points[triangles, 1].mean(axis=1) >= cut
                segmentation.append({'slot': item['slot'], 'sha256': item['sha256'], 'primitive': index,
                    'removed_faces': np.flatnonzero(~keep).tolist(), 'reason': 'neck_and_bust_below_head', 'cut_y': cut})
                if keep.any(): trimmed.append((primitive, points, triangles[keep]))
            primitives = trimmed
            all_points = np.concatenate([p[np.unique(t)] for _, p, t in primitives]); lo, hi = all_points.min(0), all_points.max(0)
        target_lo, target_hi = (np.array(v) for v in boxes[item['slot']])
        slot = 'hair' if item['slot'] in ('hairBack', 'hairFront') else item['slot']
        if slot not in packages: packages[slot] = (Package(rig), [])
        package, part_refs = packages[slot]
        material_offset = import_materials(package, source, binary); combined_offset = import_materials(combined, source, binary)
        candidates = ['head'] if slot in ('face', 'hair', 'hat') else (
            ['footL', 'footR'] if slot == 'shoes' else ['hips', 'upperLegL', 'upperLegR'] if slot == 'bottom' else
            ['hips', 'spine', 'chest', 'upperChest', 'shoulderL', 'upperArmL', 'lowerArmL', 'shoulderR', 'upperArmR', 'lowerArmR'])
        for index, (primitive, points, triangles) in enumerate(primitives):
            used, inverse = np.unique(triangles, return_inverse=True); triangles = inverse.reshape(-1, 3)
            fitted = (points[used]-(lo+hi)/2)/np.maximum(hi-lo, .001)*(target_hi-target_lo)+(target_lo+target_hi)/2
            if maple and slot == 'face':
                # Preserve the head's frontal aspect ratio after removing the bust.
                scale = min((target_hi[0]-target_lo[0])/(hi[0]-lo[0]), (target_hi[1]-target_lo[1])/(hi[1]-lo[1]))
                fitted[:, 0] = (points[used, 0]-(lo[0]+hi[0])/2)*scale
                fitted[:, 1] = (points[used, 1]-lo[1])*scale+target_lo[1]
            joints, weights = part_weights(fitted, package, slot) if maple else weights_for(fitted, package, candidates)
            extras = {name: accessor(source, binary, a)[used] for name, a in primitive['attributes'].items() if name.startswith('TEXCOORD_') or name.startswith('COLOR_')}
            name = f'{item["slot"]}_{index}'
            part_refs.append(package.mesh(name, fitted, triangles, joints, weights, material_offset+primitive['material'] if 'material' in primitive else package.skin_material, extras))
            combined.mesh(name, fitted, triangles, joints, weights, combined_offset+primitive['material'] if 'material' in primitive else combined.skin_material, extras)
            counts[item['slot']] = counts.get(item['slot'], 0)+len(triangles)
        provenance.append({'slot': item['slot'], 'sha256': item['sha256'], 'provider_task_id': item.get('task_id')})
    progress('rig', '모든 파츠에 동일한 23개 뼈와 가중치를 연결하는 중')
    for slot, (package, part_refs) in packages.items():
        package.write(output/f'{slot}.glb')
        assets.append({'key': slot, 'file': f'{slot}.glb', 'meshes': part_refs, 'hideBodyRegions': MASKS.get(slot, [])})
    combined.motions(Path(payload['motions'])); combined.write(output/'workspace.glb')
    hidden = {region for slot in packages for region in MASKS.get(slot, [])}
    combined.doc['scenes'][0]['nodes'] = [i for i in combined.doc['scenes'][0]['nodes'] if combined.doc['nodes'][i]['name'].removeprefix('body_').split('.')[0] not in hidden]
    combined.write(output/'character.glb')
    return {'assets': assets, 'bones': body.bones, 'source_triangles': sum(counts.values()), 'part_triangles': counts,
            'part_sources': provenance, 'segmentation': 'image_first_individual_generation', 'source_bone_mapping': [],
            'geometry_corrections': segmentation,
            'body_origin': 'authored_maple_chibi_template_v3' if maple else 'authored_maple_sd_clothed_template_v2', 'rig_origin': 'canonical_rebind',
            'limitations': ['각 파츠의 뒷면·겹침 여유·가중치 변형은 검수 필요', '모든 파츠는 공통 몸에 맞춘 새 리그이며 개별 Meshy 자동 리그가 아님',
                            '공통 동작은 변형 검사 클립이며 외형 승인과 별도로 확인']}
