"""Find exposed coplanar overlaps between materials in exported vehicle meshes.

Run with Blender's Python for BVH ray visibility checks:
blender -b --python tools/toyota-surface-check.py -- MODEL.glb NEW_REPORT.json
Axis-aligned faces cover body panels, lamp lenses, hinges and applied trim. Curved
intersections still require the assembled mesh and moving-camera inspection.
"""
import json, math, sys
from collections import defaultdict
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'art/blender'))
from report import read_glb, accessor_values


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def minus(a, b):
    return (a[0] - b[0], a[1] - b[1])


def intersection(subject, boundary):
    if cross(minus(boundary[1], boundary[0]), minus(boundary[2], boundary[0])) < 0:
        boundary = boundary[::-1]
    for a, b in zip(boundary, boundary[1:] + boundary[:1]):
        output = []
        edge = minus(b, a)
        for p, q in zip(subject, subject[1:] + subject[:1]):
            dp, dq = cross(edge, minus(p, a)), cross(edge, minus(q, a))
            if dp >= -1e-10:
                output.append(p)
            if (dp > 0) != (dq > 0) and abs(dp - dq) > 1e-12:
                t = dp / (dp - dq)
                output.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        subject = output
        if len(subject) < 3:
            return []
    return subject


def analyse(file, node_name):
    doc, binary = read_glb(file)
    mesh = next(n['mesh'] for n in doc['nodes'] if n.get('name') == node_name)
    vertices, triangles, materials = [], [], []
    for p in doc['meshes'][mesh]['primitives']:
        start = len(vertices)
        vertices.extend(Vector(v) for v in accessor_values(doc, binary, p['attributes']['POSITION']))
        indices = [x[0] + start for x in accessor_values(doc, binary, p['indices'])]
        tris = [indices[i:i + 3] for i in range(0, len(indices), 3)]
        triangles.extend(tris)
        materials.extend([doc['materials'][p['material']]['name']] * len(tris))
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    groups = defaultdict(list)
    for i, tri in enumerate(triangles):
        v = [vertices[k] for k in tri]
        normal = (v[1] - v[0]).cross(v[2] - v[0])
        if normal.length < 1e-10:
            continue
        normal.normalize()
        axis = max(range(3), key=lambda k: abs(normal[k]))
        if abs(normal[axis]) < .999999:
            continue
        uv = [k for k in range(3) if k != axis]
        points = [(p[uv[0]], p[uv[1]]) for p in v]
        plane = sum(p[axis] for p in v) / 3
        groups[(axis, 1 if normal[axis] > 0 else -1, round(plane, 5))].append((i, points, plane))
    hits = []
    for (axis, sign, _), faces in groups.items():
        uv = [k for k in range(3) if k != axis]
        grid, done = defaultdict(list), set()
        for i, points, plane in faces:
            xs = range(math.floor(min(p[0] for p in points) / .08), math.floor(max(p[0] for p in points) / .08) + 1)
            ys = range(math.floor(min(p[1] for p in points) / .08), math.floor(max(p[1] for p in points) / .08) + 1)
            for x in xs:
                for y in ys:
                    for j, other, d in grid[(x, y)]:
                        pair = (j, i)
                        if pair in done or materials[i] == materials[j]:
                            continue
                        done.add(pair)
                        if abs(plane - d) > .00001:
                            continue
                        poly = intersection(points, other)
                        area = abs(sum(cross(a, b) for a, b in zip(poly, poly[1:] + poly[:1]))) / 2 if poly else 0
                        if area < 1e-7:
                            continue
                        p, n = Vector(), Vector()
                        p[axis], n[axis] = plane, sign
                        for k in range(2):
                            p[uv[k]] = sum(v[k] for v in poly) / len(poly)
                        # Exclude buried joins: an outward ray must reach open air.
                        if tree.ray_cast(p + n * .0002, n, 10)[0] is not None:
                            continue
                        hits.append(dict(materials=sorted([materials[i], materials[j]]),
                                         position=list(p), axis=axis, areaM2=area))
                    grid[(x, y)].append((i, points, plane))
    lamps = []
    if node_name.startswith('Body'):
        info = json.loads(file.with_suffix('.json').read_text())
        for kind, expected in (('tail', 'LampRear'), ('reverse', 'LampReverse')):
            for side, location in enumerate(info['lamps'][kind]):
                samples = []
                chase_samples = []
                half_x, half_y = info.get('lampSample', {}).get(kind, [.035, .030])
                for dx in (-half_x, 0, half_x):
                    for dy in (-half_y, 0, half_y):
                        origin = Vector((location[0] + dx, location[1] + dy, 3.5))
                        hit = tree.ray_cast(origin, Vector((0, 0, -1)), 5)
                        samples.append(materials[hit[2]] if hit[2] is not None else None)
                        eye = Vector((0, 1.1, 6.5))
                        target = Vector((location[0] + dx, location[1] + dy, location[2]))
                        hit = tree.ray_cast(eye, (target - eye).normalized(), 8)
                        chase_samples.append(materials[hit[2]] if hit[2] is not None else None)
                lamps.append(dict(kind=kind, side=side, expected=expected, hitMaterials=samples,
                                  chaseHitMaterials=chase_samples, visible=all(m == expected for m in samples + chase_samples)))
    return dict(node=node_name, exposedOverlaps=len(hits), totalAreaM2=sum(h['areaM2'] for h in hits), overlaps=hits,
                rearLampVisibility=lamps)


args = sys.argv[sys.argv.index('--') + 1:]
model, output = Path(args[0]), Path(args[1])
result = dict(model=str(model), method='Cross-material, same-facing axis-aligned triangles, <=10 micrometre plane gap, >0.1 mm2 overlapping area, outward BVH visibility ray.',
              meshes=[analyse(model, name) for name in ('Body', 'Body_LOD1', 'Wheel')])
result['passed'] = all(m['exposedOverlaps'] == 0 and all(l['visible'] for l in m['rearLampVisibility']) for m in result['meshes'])
with output.open('x') as f:
    json.dump(result, f, indent=2)
print('SURFACE AUDIT', json.dumps([{k: m[k] for k in ('node', 'exposedOverlaps', 'totalAreaM2')} for m in result['meshes']]))
if '--require-clean' in args:
    assert result['passed'], 'Exposed coplanar overlaps or obscured rear lamps remain; inspect the saved report'
