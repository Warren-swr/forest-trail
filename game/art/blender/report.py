"""Write art/asset-report.json from the exported GLBs (pure-Python GLB parser, no bpy needed).

For every GLB: triangle count, bounding box in glTF (Y-up) coordinates from accessor min/max
(with node transforms applied), node names, material names, and whether COLOR_0 / NORMAL exist.
COLOR_0 data is also read back from the binary chunk to confirm it is not constant.
"""
import json, math, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)
MODELS = os.path.join(os.path.dirname(ART), 'public', 'assets', 'models')
COMP = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def read_glb(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    magic, version, length = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67, 'not a GLB'
    off, js, binc = 12, None, b''
    while off < length:
        clen, ctype = struct.unpack_from('<II', data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode('utf-8'))
        elif ctype == 0x004E4942:
            binc = chunk
        off += 8 + clen
    return js, binc


def accessor_values(gl, binc, idx):
    acc = gl['accessors'][idx]
    bv = gl['bufferViews'][acc['bufferView']]
    fmt, size = COMP[acc['componentType']]
    nc = NCOMP[acc['type']]
    stride = bv.get('byteStride', size * nc)
    base = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
    out = []
    for i in range(acc['count']):
        vals = struct.unpack_from('<' + fmt * nc, binc, base + i * stride)
        if acc.get('normalized'):
            m = {'B': 255.0, 'H': 65535.0, 'b': 127.0, 'h': 32767.0}[fmt]
            vals = tuple(v / m for v in vals)
        out.append(vals)
    return out


def quat_rot(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))


def node_xform(node, p):
    s = node.get('scale', [1, 1, 1])
    p = (p[0] * s[0], p[1] * s[1], p[2] * s[2])
    if 'rotation' in node:
        p = quat_rot(node['rotation'], p)
    t = node.get('translation', [0, 0, 0])
    return (p[0] + t[0], p[1] + t[1], p[2] + t[2])


def analyse(path):
    gl, binc = read_glb(path)
    mats = [m.get('name', '') for m in gl.get('materials', [])]
    info = {'file': os.path.basename(path), 'bytes': os.path.getsize(path), 'tris': 0, 'nodes': [],
            'materials': mats, 'double_sided': {m.get('name', ''): bool(m.get('doubleSided')) for m in gl.get('materials', [])},
            'has_COLOR_0': False, 'has_NORMAL': True, 'per_node_tris': {}}
    mn, mx = [1e18] * 3, [-1e18] * 3
    color_stats = []
    for node in gl.get('nodes', []):
        info['nodes'].append(node.get('name', ''))
        if 'mesh' not in node:
            continue
        ntris = 0
        for prim in gl['meshes'][node['mesh']]['primitives']:
            attrs = prim['attributes']
            cnt = gl['accessors'][prim['indices']]['count'] if 'indices' in prim else gl['accessors'][attrs['POSITION']]['count']
            ntris += cnt // 3 if prim.get('mode', 4) == 4 else 0
            info['has_NORMAL'] &= 'NORMAL' in attrs
            if 'COLOR_0' in attrs:
                info['has_COLOR_0'] = True
                vals = accessor_values(gl, binc, attrs['COLOR_0'])
                color_stats.extend(vals)
            acc = gl['accessors'][attrs['POSITION']]
            a, b = acc['min'], acc['max']
            for c in [(x, y, z) for x in (a[0], b[0]) for y in (a[1], b[1]) for z in (a[2], b[2])]:
                w = node_xform(node, c)
                mn = [min(mn[i], w[i]) for i in range(3)]
                mx = [max(mx[i], w[i]) for i in range(3)]
        info['per_node_tris'][node.get('name', '')] = ntris
        info['tris'] += ntris
    r = lambda v: [round(x, 3) for x in v]
    info['bbox_yup'] = {'min': r(mn), 'max': r(mx), 'size': r([mx[i] - mn[i] for i in range(3)])}
    if color_stats:
        n = len(color_stats)
        lo = [min(c[i] for c in color_stats) for i in range(3)]
        hi = [max(c[i] for c in color_stats) for i in range(3)]
        info['COLOR_0_check'] = {'count': n, 'min_rgb_linear': r(lo), 'max_rgb_linear': r(hi),
                                 'varies': any(hi[i] - lo[i] > 1e-3 for i in range(3))}
    if len(info['per_node_tris']) <= 1:
        info.pop('per_node_tris')
    return info


def main(extra=None):
    files = sorted(f for f in os.listdir(MODELS) if f.endswith('.glb'))
    assets = [analyse(os.path.join(MODELS, f)) for f in files]
    by = {a['file'][:-4]: a for a in assets}
    for name, a in by.items():
        if name + '_lod1' in by:
            a['lod1_ratio'] = round(by[name + '_lod1']['tris'] / max(1, a['tris']), 3)
    rep = {'generated_by': 'art/blender/build_all.py', 'coordinate_note':
           'bbox is in glTF space: +Y up, Blender +Y (vehicle front) becomes glTF -Z, Blender +X stays +X',
           'assets': assets}
    if extra:
        rep.update(extra)
    out = os.path.join(ART, 'asset-report.json')
    with open(out, 'w') as fh:
        json.dump(rep, fh, indent=2)
    for a in assets:
        print('%-22s tris %6d  size %-24s COLOR_0 %-5s mats %s' % (a['file'], a['tris'], a['bbox_yup']['size'],
              a['has_COLOR_0'], ','.join(a['materials'])))
    return out


if __name__ == '__main__':
    main()
