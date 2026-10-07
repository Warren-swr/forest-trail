"""Check the actual exported bonnet surfaces and glazing, independent of Blender.

Usage: python3 tools/vehicle-surface-check.py NEW_OUTPUT.json [BASELINE_MODELS]
Samples vertical intersections with the final GLB triangles, not generator values.
"""
import json, math, sys
from collections import defaultdict
from pathlib import Path
from hashlib import sha256

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'art/blender'))
from report import read_glb, accessor_values


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(sum(x * x for x in a))


def triangles(doc, binary, node, material):
    mesh = next(n['mesh'] for n in doc['nodes'] if n.get('name') == node)
    result = []
    for p in doc['meshes'][mesh]['primitives']:
        if doc['materials'][p['material']]['name'] != material:
            continue
        vs = accessor_values(doc, binary, p['attributes']['POSITION'])
        ids = [i[0] for i in accessor_values(doc, binary, p['indices'])]
        result.extend([[vs[k] for k in ids[i:i + 3]] for i in range(0, len(ids), 3)])
    return result


def bonnet(doc, binary, cowl, front):
    tris = [t for t in triangles(doc, binary, 'Body', 'Paint')
            if min(v[2] for v in t) < -cowl and max(v[2] for v in t) > -front
            and min(v[1] for v in t) < 1 and max(v[1] for v in t) > .70]
    samples = []
    for i in range(9):
        z = -(cowl + (front - cowl) * (.16 + .68 * i / 8))
        for j in range(7):
            x = -.36 + .12 * j
            heights = []
            for a, b, c in tris:
                d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
                if abs(d) < 1e-12:
                    continue
                u = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / d
                v = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / d
                if u >= -1e-6 and v >= -1e-6 and u + v <= 1.000001:
                    heights.append(u * a[1] + v * b[1] + (1 - u - v) * c[1])
            assert heights, f'Open bonnet at {x}, {z}'
            samples.append((x, z, max(heights)))
    zm = sum(p[1] for p in samples) / len(samples)
    hm = sum(p[2] for p in samples) / len(samples)
    slope = sum((p[1] - zm) * (p[2] - hm) for p in samples) / sum((p[1] - zm) ** 2 for p in samples)
    errors = [p[2] - hm - slope * (p[1] - zm) for p in samples]
    return dict(samples=len(samples), maxPlaneErrorM=max(abs(e) for e in errors),
                rmsPlaneErrorM=math.sqrt(sum(e * e for e in errors) / len(errors)),
                forwardSlope=-slope, sampleHeights=samples)


def glazing(doc, binary, node):
    tris = triangles(doc, binary, node, 'Glass')
    links, regions, visited = defaultdict(set), [], set()
    key = lambda p: tuple(round(c, 6) for c in p)
    for tri in tris:
        for v in tri:
            links[key(v)].update(key(p) for p in tri)
    for vertex in links:
        if vertex in visited:
            continue
        region, todo = set(), [vertex]
        while todo:
            v = todo.pop()
            if v in region:
                continue
            region.add(v); todo.extend(links[v] - region)
        visited.update(region)
        faces = [t for t in tris if key(t[0]) in region]
        areas = [length(cross(sub(t[1], t[0]), sub(t[2], t[0]))) / 2 for t in faces]
        if sum(areas) < .04:  # mirror glass is not a cabin pane
            continue
        tri = faces[areas.index(max(areas))]
        normal = cross(sub(tri[1], tri[0]), sub(tri[2], tri[0]))
        norm = length(normal)
        deviation = max(abs(sum(a * b for a, b in zip(sub(p, tri[0]), normal))) / norm
                        for t in faces for p in t)
        assert deviation < 2e-6, f'{node} pane is warped by {deviation} m'
        regions.append(dict(vertices=len(region), areaM2=sum(areas), maxPlaneErrorM=deviation))
    return regions


def main():
    assert len(sys.argv) >= 2, __doc__
    out = Path(sys.argv[1])
    assert not out.exists(), 'Use a new output path to preserve earlier checks'
    baseline = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    result = dict(method=__doc__, vehicles=[])
    for name, cowl, front, count in [('toyota_trail', .754, 1.98, 8), ('scout', .657, 1.773, 8),
                                     ('ranger', 1.007, 2.019, 4)]:
        file = ROOT / 'public/assets/models' / ('vehicle_' + name + '.glb')
        doc, binary = read_glb(file)
        row = dict(id=name, sha256=sha256(file.read_bytes()).hexdigest(), bonnet=bonnet(doc, binary, cowl, front))
        row['glazing'] = {lod: glazing(doc, binary, lod) for lod in ('Body', 'Body_LOD1')}
        assert all(len(p) == count for p in row['glazing'].values()), f'{name} cabin pane count changed'
        # No middle bulge in the broad primary pressing. Edge rolls and paired
        # swages sit outside this central 72 cm wide inspection patch.
        assert row['bonnet']['maxPlaneErrorM'] < .002, f'{name} bonnet has regained a dome'
        assert row['bonnet']['forwardSlope'] <= .001, f'{name} bonnet rises towards the grille'
        assert all(p['vertices'] >= 24 for p in row['glazing']['Body']), 'Lost the radiused aperture corners'
        if baseline:
            old_doc, old_binary = read_glb(baseline / file.name)
            row['beforeBonnet'] = bonnet(old_doc, old_binary, cowl, front)
        result['vehicles'].append(row)
        print(name, 'flat main pressing; planar radiused glazing in both LODs')
    result['passed'] = True
    out.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
