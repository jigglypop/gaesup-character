"""Authored 24-bone fixture; never a production avatar."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services.avatar_factory_geometry import Package, body_geometry, weights_for

assets = Path(__file__).resolve().parents[1]/'assets/avatars'
rig = json.loads((assets/'rig-maple-v1.json').read_text())
rig['bones'].append(['fixtureExtra', 'head', 0, .02, 0])
package = Package(rig)
for region, points, triangles, bones in body_geometry(package):
    joints, weights = weights_for(points, package, bones)
    package.mesh(region, points, triangles, joints, weights, package.body_material(region))
package.motions(assets/'manual-v1/body-sd-neutral-v1.glb')
for mesh in package.doc['meshes']:
    for primitive in mesh['primitives']:
        count = package.doc['accessors'][primitive['attributes']['POSITION']]['count']
        primitive['attributes']['TEXCOORD_0'] = package.add([[i % 2, (i//2) % 2] for i in range(count)], 'VEC2')
package.write(Path(sys.argv[sys.argv.index('--')+1]))
