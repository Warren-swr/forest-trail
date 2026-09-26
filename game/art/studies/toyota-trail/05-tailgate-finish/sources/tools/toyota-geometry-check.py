"""Read final GLB geometry: flat glazing, fixed rim size and matching tyre LODs.

Usage: python tools/toyota-geometry-check.py NEW_OUTPUT.json
"""
import json, math, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
info = json.loads((ROOT / 'public/assets/models/vehicle_toyota_trail.json').read_text())
STUDY = ROOT / 'art/studies/toyota-trail' / info['revision']
before_info = json.loads((STUDY / 'before.json').read_text())


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(v):
    return math.sqrt(sum(x * x for x in v))


def key(v):
    return tuple(round(x, 6) for x in v)


def glb(path):
    data = path.read_bytes()
    size = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + size])
    start = 28 + size

    def read(index):
        a = doc['accessors'][index]
        view = doc['bufferViews'][a['bufferView']]
        width = {'SCALAR': 1, 'VEC3': 3}[a['type']]
        kind = {5126: 'f', 5125: 'I', 5123: 'H', 5121: 'B'}[a['componentType']]
        fmt = '<' + kind * width
        stride = view.get('byteStride', struct.calcsize(fmt))
        offset = start + view.get('byteOffset', 0) + a.get('byteOffset', 0)
        return [struct.unpack_from(fmt, data, offset + i * stride) for i in range(a['count'])]

    def primitives(node, material):
        mesh = next(n['mesh'] for n in doc['nodes'] if n['name'] == node)
        result = []
        for p in doc['meshes'][mesh]['primitives']:
            if doc['materials'][p['material']]['name'] == material:
                indices = [i[0] for i in read(p['indices'])]
                result.append((read(p['attributes']['POSITION']), [indices[i:i + 3] for i in range(0, len(indices), 3)]))
        return result
    return primitives


current = glb(ROOT / 'public/assets/models/vehicle_toyota_trail.glb')
before = glb(STUDY / 'before.glb')


def radius(asset, node, mat):
    return max(math.hypot(v[1], v[2]) for p, _ in asset(node, mat) for v in p)


def positions(asset, node, mat):
    return {key(v) for p, _ in asset(node, mat) for v in p}


assert positions(current, 'Body', 'Glass') == positions(before, 'Body', 'Glass'), 'Previously accepted glass changed'
panes = []
for verts, faces in current('Body', 'Glass'):
    # Weld render-normal splits before finding connected glass regions.
    keys = [key(v) for v in verts]
    links = {}
    for face in faces:
        for i in face:
            links.setdefault(keys[i], set()).update(keys[j] for j in face)
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
        area = sum(norm(cross(sub(t[1], t[0]), sub(t[2], t[0]))) / 2 for t in triangles)
        if area < .05:  # two small mirrors
            continue
        points = {v for t in triangles for v in t}
        t = max(triangles, key=lambda t: norm(cross(sub(t[1], t[0]), sub(t[2], t[0]))))
        n = cross(sub(t[1], t[0]), sub(t[2], t[0]))
        normal = tuple(x / norm(n) for x in n)
        deviation = max(abs(sum(x * y for x, y in zip(sub(p, t[0]), normal))) for p in points)
        assert deviation < 1e-6, f'Warped glass: {deviation}'
        panes.append(dict(areaM2=area, vertices=len(points), maxPlaneDeviationM=deviation))
assert len(panes) == 8
tyres = dict(before=radius(before, 'Wheel', 'Tire'), after=radius(current, 'Wheel', 'Tire'),
             far=radius(current, 'Wheel_LOD1', 'Tire'))
rims = dict(before=radius(before, 'Wheel', 'Rim'), after=radius(current, 'Wheel', 'Rim'))
assert abs(rims['after'] - rims['before']) < .0001, 'Steel wheel diameter changed'
assert abs(tyres['after'] - info['wheelRadius']) < .004
assert abs(tyres['far'] - tyres['after']) < .004
assert abs((tyres['after'] - tyres['before']) - (info['wheelRadius'] - before_info['wheelRadius'])) < .004
shock = info['shock']
def length(travel):
    b, t = shock['bottom'], shock['top']
    return math.sqrt((t[0] - b[0]) ** 2 + (t[1] - b[1] - travel) ** 2 + (t[2] - b[2]) ** 2)
closed, extended = length(.25), length(-.19)
assert closed > shock['barrelLength'] + .04
assert extended - closed < shock['barrelLength'] - .035
result = dict(passed=True, paneCount=len(panes), panes=panes, glassUnchanged=True,
              tyreRadiusM=tyres, steelRimRadiusM=rims,
              shock=dict(compressedLength=closed, extendedLength=extended,
                         stroke=extended - closed, barrelLength=shock['barrelLength']))
with open(sys.argv[1], 'x') as f:
    json.dump(result, f, indent=2)
print('PASS: eight unchanged planar panes; tyre and rim dimensions verified; LOD and shock lengths agree')
