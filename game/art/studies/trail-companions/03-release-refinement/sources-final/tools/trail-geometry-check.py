"""Check exported companion meshes, including both LODs and spring deformation.

Run: python tools/trail-geometry-check.py NEW_OUTPUT.json
No Blender or browser is required.
"""
import json, math, sys
from hashlib import sha256
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'art/blender'))
from report import read_glb, accessor_values


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(p):
    return math.sqrt(sum(x * x for x in p))


def parts(doc, binary, node, material):
    mesh = next(n['mesh'] for n in doc['nodes'] if n.get('name') == node)
    for p in doc['meshes'][mesh]['primitives']:
        if doc['materials'][p['material']]['name'] != material:
            continue
        vertices = accessor_values(doc, binary, p['attributes']['POSITION'])
        indices = [i[0] for i in accessor_values(doc, binary, p['indices'])]
        yield vertices, [indices[i:i + 3] for i in range(0, len(indices), 3)], p


def panes(doc, binary, node):
    result = []
    for verts, faces, _ in parts(doc, binary, node, 'Glass'):
        keys = [tuple(round(c, 6) for c in v) for v in verts]
        links = defaultdict(set)
        for face in faces:
            for i in face:
                links[keys[i]].update(keys[j] for j in face)
        seen = set()
        for vertex in links:
            if vertex in seen:
                continue
            region, todo = set(), [vertex]
            while todo:
                k = todo.pop()
                if k in region:
                    continue
                region.add(k)
                todo.extend(links[k] - region)
            seen.update(region)
            triangles = [[verts[i] for i in f] for f in faces if keys[f[0]] in region]
            tri = max(triangles, key=lambda t: norm(cross(sub(t[1], t[0]), sub(t[2], t[0]))))
            normal = cross(sub(tri[1], tri[0]), sub(tri[2], tri[0]))
            length = norm(normal)
            assert length > 0
            normal = tuple(c / length for c in normal)
            points = {v for t in triangles for v in t}
            deviation = max(abs(sum(x * y for x, y in zip(sub(p, tri[0]), normal))) for p in points)
            assert deviation < 2e-6, 'Warped ' + node + ' glass: ' + str(deviation)
            result.append(dict(vertices=len(points), maxPlaneDeviationM=deviation))
    return result


def radius(doc, binary, node, material):
    return max(math.hypot(v[1], v[2]) for vertices, _, _ in parts(doc, binary, node, material) for v in vertices)


def assembled(tris, far=False):
    total = tris.get('Body_LOD1', tris['Body']) if far else tris['Body']
    total += 4 * (tris.get('Wheel_LOD1', tris['Wheel']) if far else tris['Wheel'])
    total += sum(tris.get(n, 0) for n in ('Glazing', 'SteeringWheel', 'AxleFront', 'AxleRear'))
    total += 4 * sum(tris.get(n, 0) for n in ('Spring', 'ShockBody', 'ShockRod'))
    total += 2 * sum(tris.get(n, 0) for n in ('Driveshaft', 'BrakeFront', 'BrakeRear'))
    return total


def mesh_triangles(doc):
    return {n['name']: sum(doc['accessors'][p['indices']]['count'] // 3
                          for p in doc['meshes'][n['mesh']]['primitives'])
            for n in doc['nodes'] if 'mesh' in n}


study = ROOT / 'art/studies/trail-companions/02-release-baseline'
baseline = json.loads((study / 'baseline.json').read_text())
assert baseline['kind'] == 'published-release'
result = dict(method='Final exported GLB positions and morph targets; both active LODs are checked. Counts compare the published release to the current complete assembly; the release has no distance LOD. Tyre radii include tread blocks. Coil wire cross sections must retain their diameter throughout the deformation.',
              releaseCommit=baseline['releaseCommit'], vehicles=[])
for vid in ('scout', 'ranger'):
    file = ROOT / 'public/assets/models' / ('vehicle_' + vid + '.glb')
    info = json.loads(file.with_suffix('.json').read_text())
    before = json.loads((study / vid / 'before.json').read_text())
    released = study / vid / 'before.glb'
    receipt = next(a for a in baseline['publishedAssets'] if a['id'] == vid and a['path'].endswith('.glb'))
    assert sha256(released.read_bytes()).hexdigest() == receipt['sha256']
    doc, binary = read_glb(file)
    released_doc, _ = read_glb(released)
    assert mesh_triangles(released_doc) == before['tris'], 'Published sidecar differs from exported geometry'
    assert mesh_triangles(doc) == info['tris'], 'Current sidecar differs from exported geometry'
    windows = {node: panes(doc, binary, node) for node in ('Body', 'Body_LOD1')}
    assert all(len(p) == (8 if vid == 'scout' else 4) for p in windows.values())
    tyres = {node: radius(doc, binary, node, 'Tire') for node in ('Wheel', 'Wheel_LOD1')}
    assert max(abs(r - info['wheelRadius']) for r in tyres.values()) < .002
    assert abs(tyres['Wheel'] - tyres['Wheel_LOD1']) < .002
    rims = {node: radius(doc, binary, node, 'Rim') for node in ('Wheel', 'Wheel_LOD1')}
    assert abs(rims['Wheel'] - rims['Wheel_LOD1']) < .001
    assert info['wheelRadius'] - rims['Wheel'] > .17, 'Sidewall was lost by scaling the entire wheel'
    counts = {kind: dict(near=assembled(data['tris']), far=assembled(data['tris'], True))
              for kind, data in (('before', before), ('after', info))}
    # The previous release used a much simpler mesh. Report its actual increase;
    # the earlier reduction claim was relative to an unpublished intermediate.
    assert counts['after']['far'] < counts['after']['near'] * .45
    shock = info['shock']
    rig = json.loads((ROOT / info['rigFile']).read_text())
    lengths = []
    for travel in (rig['bump'], -rig['droop']):
        bottom = shock['bottom'].copy()
        bottom[1] += travel
        length = norm(sub(shock['top'], bottom))
        exposed = length - shock['barrelLength']
        assert .025 < exposed < shock['barrelLength'] - .01, 'Damper runs out of telescoping overlap'
        lengths.append(dict(axleHeight=travel, eyeDistance=length, exposedRod=exposed))
    wire = None
    if vid == 'scout':
        vertices, _, primitive = next(parts(doc, binary, 'Spring', 'Chassis'))
        bump = accessor_values(doc, binary, primitive['targets'][0]['POSITION'])
        droop = accessor_values(doc, binary, primitive['targets'][1]['POSITION'])
        rings = defaultdict(list)
        for i, delta in enumerate(bump):
            rings[round(delta[1], 6)].append(i)
        assert len(rings) == 257, 'Coil wire was scaled instead of translating its cross sections'
        diameters = []
        for indices in rings.values():
            for target in (None, bump, droop):
                positions = {tuple(vertices[i][c] + (target[i][c] if target else 0) for c in range(3)) for i in indices}
                diameter = max(norm(sub(a, b)) for a in positions for b in positions)
                assert abs(diameter - .018) < .00001, 'Coil wire gauge changed'
                diameters.append(diameter)
        wire = dict(rings=len(rings), diameterMin=min(diameters), diameterMax=max(diameters))
    result['vehicles'].append(dict(id=vid, windows=windows, tyreRadius=tyres, rimRadius=rims,
                                   assembledTriangles=counts, damperLimits=lengths, coilWire=wire,
                                   bytes=file.stat().st_size, releasedBytes=released.stat().st_size))
result['passed'] = True
with Path(sys.argv[1]).open('x') as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
