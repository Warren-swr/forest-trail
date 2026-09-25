"""Forest Trail nature pack 2: autumn trees, meadow grass and flowers, big boulders,
layered sandstone, deer and eagle.

Run: blender --background --python nature2.py
Conventions as vegetation.py / rocks.py: one mesh + one vertex-colour material "VC" per GLB
(sRGB vertex colours), origin at the ground centre, front +Y, soft custom normals on foliage,
*_lod1 for trees. Deer and eagle are multi-node (Body/Neck/Leg*, Body/Wing*): each object's
location is its animation pivot. Writes art/nature2-report.json.
"""
import bpy, bmesh, math, os, random, sys, json
from mathutils import Vector, Matrix, Euler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
from common import hexc, mix, ramp, smoothstep, bm_lathe, bm_cyl_between, bm_icosphere, bm_from, bm_hull, xform
import vegetation as V
import rocks as R

UP = Vector((0, 0, 1))


# ================================================================== deciduous crowns
def facet_blob(rng, r, center, subdiv, squash=0.85, amp=0.2, stretch=(1, 1)):
    bm = bm_icosphere(1.0, subdiv)
    for v in bm.verts:
        k = 1 + rng.uniform(-amp, amp)
        v.co = Vector((v.co.x * r * k * stretch[0], v.co.y * r * k * stretch[1], v.co.z * r * k * squash)) + Vector(center)
    bm.normal_update()
    return bm


def add_crown_clumps(mb, rng, clumps, ctr, span, cols, lod, squash=0.82, amp=0.22, face_w=0.45, hue=0.05):
    dark, mid_c, light = cols
    zlo, zhi = ctr.z - span[1], ctr.z + span[1]
    for c, r in clumps:
        bm = facet_blob(rng, r, c, 2 if lod == 0 else 1, squash, amp if lod == 0 else amp * 0.6)

        def cfn(l, f):
            p = l.vert.co
            out = (Vector((p.x, p.y, 0)) - Vector((ctr.x, ctr.y, 0))).length / span[0]
            v = 0.5 * min(1.0, out) ** 1.4 + 0.45 * (p.z - zlo) / (zhi - zlo)
            if f.normal.z < -0.3:
                v *= 0.45
            return ramp([(0.0, dark), (0.5, mid_c), (1.0, light)], v)

        def nfn(l, f):
            return V.center_normal(l.vert.co, ctr, f.normal, face_w, squash=0.8)

        mb.add(bm, color_fn=cfn, normal_fn=nfn, jitter=0.07, hue=hue)


def branch(mb, p0, p1, r0, r1, col, segs=5):
    mb.add(bm_cyl_between(p0, p1, r0, segs=segs, r2=r1, cap=False), color=col, shade='smooth', jitter=0.05)


MAPLES = {
    'maple_red': dict(seed=31, cols=(hexc('#5E1A17'), hexc('#B8352A'), hexc('#E0602E'))),
    'maple_orange': dict(seed=47, cols=(hexc('#7A3A16'), hexc('#D9722C'), hexc('#F2A640'))),
}


def build_maple(name, lod):
    cfg = MAPLES[name]
    rng = random.Random(cfg['seed'] * 10 + lod)
    mb = C.MeshBuilder(name + ('_lod1' if lod else ''), seed=cfg['seed'] + lod)
    H = 8.2
    bark = (hexc('#2E2622'), hexc('#43372F'), hexc('#5A4A3E'))
    V.add_trunk(mb, rng, 4.6, 0.24, 7 if lod == 0 else 4, 3 if lod == 0 else 1, top=1.0,
                lean=(0.25, 0.1), cols=bark, flare=1.45, bumpy=0.04 if lod == 0 else 0)
    ctr = Vector((0.2, 0.05, 5.5))
    # branches fanning out from the trunk top into the clumps
    fork = Vector((0.18, 0.05, 3.6))
    tips = []
    for k in range(3):
        a = k * 2.1 + rng.uniform(-0.3, 0.3)
        tips.append(Vector((math.cos(a) * 1.7, math.sin(a) * 1.5, 5.2 + rng.uniform(-0.3, 0.5))))
    if lod == 0:
        for t in tips:
            branch(mb, fork, t, 0.13, 0.05, bark[1])
    # clumps: an umbrella of faceted blobs, wider than tall
    clumps = [((ctr.x, ctr.y, 7.2), 1.55)]
    n_cl = 10 if lod == 0 else 4
    for i in range(n_cl - 1):
        a = i * 2.39996 + rng.uniform(-0.25, 0.25)
        t = (i + 0.5) / (n_cl - 1)
        rr = (2.2 if lod == 0 else 1.6) * (0.55 + 0.45 * math.sin(t * math.pi * 0.9 + 0.3))
        z = 6.9 - 2.2 * t + rng.uniform(-0.2, 0.2)
        clumps.append(((ctr.x + rr * math.cos(a), ctr.y + rr * math.sin(a), z),
                       rng.uniform(1.15, 1.5) * (1.25 if lod else 1.0)))
    add_crown_clumps(mb, rng, clumps, ctr, (3.3, 2.4), cfg['cols'], lod, squash=0.78, amp=0.26)
    return mb


def build_birch(lod):
    rng = random.Random(1201 + lod)
    mb = C.MeshBuilder('birch' + ('_lod1' if lod else ''), seed=12 + lod)
    H = 11.2
    # vertex colours reach the engine as linear values: ~0.47 is a real birch bark
    # albedo (a near-white value glowed under moonlight)
    white, mark = hexc('#7C776B'), hexc('#2F2B27')
    segs, rings = (6, 7) if lod == 0 else (4, 2)
    prof = [(0.19, 0.0), (0.14, 0.35)]
    for k in range(1, rings + 1):
        t = k / rings
        prof.append((0.12 * (1 - t) ** 0.85 + 0.02, 0.35 + (H * 0.88 - 0.35) * t))
    prof.append((0, H * 0.92))
    bm = bm_lathe(prof, segs, 'Z')
    for v in bm.verts:
        v.co.x += 0.3 * math.sin(v.co.z / H * 2.6) - 0.1
        v.co.y += 0.12 * math.sin(v.co.z / H * 4.1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    marks = {}

    def cfn(l, f):
        if f.index not in marks:
            z = f.calc_center_median().z
            marks[f.index] = rng.random() < (0.28 if z > 0.8 else 0.8)
        base = mix(white, mark, 0.88 if marks[f.index] else rng.uniform(0.0, 0.08))
        return base
    mb.add(bm, color_fn=cfn, shade='smooth', jitter=0.02)
    yellow = (hexc('#6E5A1C'), hexc('#D2A838'), hexc('#EFD263'))
    lime = (hexc('#4E5A22'), hexc('#A9B443'), hexc('#D8D86A'))
    ctr = Vector((0.0, 0.0, 7.6))
    n_cl = 12 if lod == 0 else 5
    for i in range(n_cl):
        t = i / max(1, n_cl - 1)
        z = 10.6 - 5.4 * t + rng.uniform(-0.25, 0.25)
        a = i * 2.39996 + rng.uniform(-0.3, 0.3)
        rr = (0.35 + 1.45 * math.sin(min(1.0, t * 1.15) * math.pi * 0.85)) * (0.8 if lod else 1.0)
        tx = 0.3 * math.sin(z / H * 2.6) - 0.1
        c = Vector((tx + rr * math.cos(a), rr * math.sin(a), z))
        r = rng.uniform(0.8, 1.08) * (1.35 if lod else 1.0)
        if lod == 0 and t > 0.25:            # thin twig into the lower clumps
            p0 = Vector((tx, 0.12 * math.sin(z / H * 4.1), z - 0.9))
            branch(mb, p0, c * 0.75 + p0 * 0.25, 0.04, 0.015, hexc('#6E685D'), 4)
        cols = lime if rng.random() < 0.22 else yellow
        add_crown_clumps(mb, rng, [(c, r)], ctr, (2.2, 3.2), cols, lod, squash=0.95, amp=0.28, face_w=0.5)
    return mb


LARCH = dict(H=14.0, z0=0.22, Rmax=2.7, N=8, n=11, N1=5, n1=7, r0=0.26, shape=0.95,
             stubs=4, seed=59, tj=0.16, off=0.14)


def build_larch(lod):
    cfg = LARCH
    rng = random.Random(cfg['seed'] * 10 + lod)
    mb = C.MeshBuilder('larch_gold' + ('_lod1' if lod else ''), seed=cfg['seed'] + lod)
    H = cfg['H']
    V.add_trunk(mb, rng, H, cfg['r0'], 7 if lod == 0 else 4, 4 if lod == 0 else 1, top=0.9,
                cols=(hexc('#3A2A20'), hexc('#5B402C'), hexc('#7A5436')))
    if lod == 0:
        for k in range(cfg['stubs']):
            z = cfg['z0'] * H * rng.uniform(0.4, 0.95)
            a = rng.uniform(0, 6.283)
            d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.4, -0.1)))
            V.add_stub(mb, (math.cos(a) * 0.12, math.sin(a) * 0.12, z), d, rng.uniform(0.5, 1.0), 0.05,
                       col=hexc('#4A3526'))
    tiers = V.pine_tiers(cfg, lod, rng)
    V.add_pine_crown(mb, rng, tiers, H, lod, (hexc('#6A3F1C'), hexc('#C06E2A'), hexc('#E2AE48')))
    return mb


# ================================================================== grass + flowers
GRASS_ROOT, GRASS_MID, GRASS_TIP = hexc('#4F5230'), hexc('#9A8A45'), hexc('#E0B85A')


def blade(mb, rng, root, a, h, w, lean, segs, cols, tint=None):
    """Bent blade: quad strip of segs-1 quads + tip triangle, double sided."""
    d = Vector((math.cos(a), math.sin(a), 0))
    side = Vector((-math.sin(a), math.cos(a), 0))
    pts = []
    for j in range(segs + 1):
        t = j / segs
        pts.append(root + d * lean * h * t ** 1.8 + UP * h * (t - 0.12 * lean * t ** 2))
    verts, faces = [], []
    for j in range(segs):
        t = j / segs
        ww = w * (1 - t * 0.75)
        verts += [pts[j] - side * ww, pts[j] + side * ww]
    verts.append(pts[-1])
    for j in range(segs - 1):
        b = 2 * j
        faces.append([b, b + 1, b + 3, b + 2])
    b = 2 * (segs - 1)
    faces.append([b, b + 1, len(verts) - 1])
    bm = bm_from(verts, faces)
    C.orient(bm, lambda f: d + UP * 0.3)
    root_c, mid_c, tip_c = cols
    if tint is not None:
        tip_c = tint

    def cfn(l, f):
        return ramp([(0, root_c), (0.45, mid_c), (1, tip_c)], l.vert.co.z / h)

    mb.add(bm, mat='VC_2S', color_fn=cfn, normal_fn=lambda l, f: (d * 0.5 + UP).normalized(), jitter=0.05)


def build_grass_tall(lod):
    rng = random.Random(1301 + lod)
    mb = C.MeshBuilder('grass_tall' + ('_lod1' if lod else ''), seed=13 + lod)
    n, segs = (24, 3) if lod == 0 else (12, 2)
    for k in range(n):
        a = k * 2.39996 + rng.uniform(-0.3, 0.3)
        h = rng.uniform(0.62, 0.98)
        root = Vector((math.cos(a), math.sin(a), 0)) * rng.uniform(0.0, 0.16)
        w = rng.uniform(0.022, 0.034) * (1.9 if lod else 1.0)
        tint = mix(GRASS_TIP, hexc('#C9A24C'), rng.uniform(0, 0.6))
        if rng.random() < 0.2:
            tint = mix(tint, hexc('#A9A457'), 0.5)
        blade(mb, rng, root, a + rng.uniform(-0.5, 0.5), h, w, rng.uniform(0.18, 0.55), segs,
              (GRASS_ROOT, GRASS_MID, GRASS_TIP), tint)
    return mb


def flower_head(mb, center, r, petals, col, eye=None, cup=0.0, rng=None):
    """Star disc facing up (cup lifts the petal tips)."""
    verts = [center + UP * 0.005]
    for i in range(petals * 2):
        a = i * math.pi / petals + (rng.uniform(-0.1, 0.1) if rng else 0)
        rr = r if i % 2 == 0 else r * 0.45
        verts.append(center + Vector((math.cos(a) * rr, math.sin(a) * rr, cup * (1 if i % 2 == 0 else 0.3))))
    faces = [[0, 1 + i, 1 + (i + 1) % (petals * 2)] for i in range(petals * 2)]
    bm = bm_from(verts, faces)
    C.orient(bm, lambda f: UP)
    ec = eye or col

    def cfn(l, f):
        return ec if l.vert.index == 0 else col

    mb.add(bm, mat='VC_2S', color_fn=cfn, normal_fn=lambda l, f: UP, jitter=0.04)


def stem(mb, p0, p1, w, col):
    d = (p1 - p0).normalized()
    side = d.cross(UP)
    side = side.normalized() * w if side.length > 1e-4 else Vector((w, 0, 0))
    bm = bm_from([p0 - side, p0 + side, p1 + side * 0.4, p1 - side * 0.4], [[0, 1, 2, 3]])
    mb.add(bm, mat='VC_2S', color=col, normal_fn=lambda l, f: (UP + d * 0.2).normalized())


def build_flowers_a():
    rng = random.Random(1401)
    mb = C.MeshBuilder('flowers_a', seed=14)
    leaf = (hexc('#3F4F2A'), hexc('#6E7F3E'), hexc('#95A052'))
    for k in range(9):
        a = k * 2.39996
        blade(mb, rng, Vector((math.cos(a), math.sin(a), 0)) * 0.05, a, rng.uniform(0.18, 0.3), 0.03, 0.6, 2, leaf)
    for k in range(7):                           # daisies
        a = k * 2.39996 + 0.4
        base = Vector((math.cos(a), math.sin(a), 0)) * rng.uniform(0.04, 0.2)
        h = rng.uniform(0.28, 0.46)
        top = base + Vector((math.cos(a) * 0.05, math.sin(a) * 0.05, h))
        stem(mb, base, top, 0.008, hexc('#5E7236'))
        flower_head(mb, top, rng.uniform(0.045, 0.06), 6, hexc('#F4F1E6'), hexc('#E8B52C'), 0.01, rng)
    for k in range(4):                           # poppies
        a = k * 1.9 + 1.1
        base = Vector((math.cos(a), math.sin(a), 0)) * rng.uniform(0.08, 0.2)
        h = rng.uniform(0.36, 0.55)
        top = base + Vector((math.cos(a) * 0.08, math.sin(a) * 0.08, h))
        stem(mb, base, top, 0.008, hexc('#5E7236'))
        flower_head(mb, top, rng.uniform(0.055, 0.07), 4, hexc('#D2361F'), hexc('#2A1E18'), 0.035, rng)
    return mb


def build_flowers_b():
    rng = random.Random(1501)
    mb = C.MeshBuilder('flowers_b', seed=15)
    leaf = (hexc('#3A4A2C'), hexc('#5F7340'), hexc('#8A9A55'))
    for k in range(7):
        a = k * 2.39996
        blade(mb, rng, Vector((math.cos(a), math.sin(a), 0)) * 0.06, a, rng.uniform(0.16, 0.24), 0.045, 0.9, 2, leaf)
    purple = [hexc('#4A2F6E'), hexc('#7B4FA8'), hexc('#B08AD6')]
    for k in range(5):
        a = k * 2.39996 + 0.7
        base = Vector((math.cos(a), math.sin(a), 0)) * rng.uniform(0.03, 0.14)
        h = rng.uniform(0.42, 0.62)
        spike0 = h * 0.45
        stem(mb, base, base + UP * spike0, 0.01, hexc('#4E6636'))
        # floret spike: jagged cone (alternating radii per ring)
        prof = []
        rings = 3
        for j in range(rings + 1):
            t = j / rings
            r = 0.05 * (1 - t) ** 0.8 * (1.0 if j % 2 == 0 else 1.25)
            prof.append((r, spike0 + (h - spike0) * t))
        prof[-1] = (0, h)
        bm = bm_lathe(prof, 5, 'Z', phase=rng.uniform(0, 1))
        bmesh.ops.translate(bm, vec=base, verts=bm.verts)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        tint = rng.choice([None, hexc('#D9CDE8'), None])

        def cfn(l, f, h=h, s0=spike0, tint=tint):
            t = (l.vert.co.z - s0) / (h - s0)
            c = ramp([(0, purple[0]), (0.5, purple[1]), (1, purple[2])], t)
            return mix(c, tint, 0.5) if tint else c

        mb.add(bm, mat='VC_2S', color_fn=cfn, normal_fn=lambda l, f, b=base: V.radial_normal(l.vert.co - b, up=0.6, rmin=0.05),
               jitter=0.06)
    return mb


# ================================================================== boulders (steam-14/06)
BLUE_D, BLUE, BLUE_L = hexc('#4E5963'), hexc('#6F7C86'), hexc('#A3AFB6')


def boulder_color_fn(rng, zmax):
    from mathutils import noise
    cache = {}
    off = Vector((rng.uniform(0, 40), rng.uniform(0, 40), 0))

    def fn(l, f):
        if f.index not in cache:
            c = f.calc_center_median()
            nz = f.normal.z
            h = max(0.0, c.z) / max(zmax, 1e-3)
            g = ramp([(0.0, BLUE_D), (0.5, BLUE), (1.0, BLUE_L)], 0.25 + 0.35 * h + 0.35 * max(0.0, nz) + rng.uniform(-0.08, 0.08))
            patch = smoothstep(0.1, 0.45, noise.noise(c * 0.6 + off))
            m = smoothstep(0.7, 0.95, nz) * patch * 0.45
            g = mix(g, R.MOSS, m)
            if c.z < 0.12:
                g = mix(g, R.DIRT, 0.35)
            cache[f.index] = g
        return cache[f.index]
    return fn


BOULDERS = {
    'boulder_a': dict(seed=2101, size=(3.0, 2.5, 3.1), n=44),
    'boulder_b': dict(seed=2202, size=(4.5, 3.0, 4.2), n=50),
    'boulder_c': dict(seed=2303, size=(2.2, 1.8, 2.3), n=38),
}


def build_big_boulder(name):
    cfg = BOULDERS[name]
    rng = random.Random(cfg['seed'])
    mb = C.MeshBuilder(name, seed=cfg['seed'])
    pts = R.rock_points(rng, cfg['n'], cfg['size'], bottom=-0.45, top=0.95, noise=0.1)
    bm = R.sink(R.hull_rock(rng, pts, 5.0, 0.05), 0.3)
    zmax = max(v.co.z for v in bm.verts)
    mb.add(bm, color_fn=boulder_color_fn(rng, zmax), shade='auto', angle=24, jitter=0.02)
    return mb


# ================================================================== sandstone (steam-05/11/13)
SAND_A, SAND_B, SAND_HI, SAND_DK = hexc('#C8683A'), hexc('#A9502F'), hexc('#E09A62'), hexc('#6E3322')


def strata_block(rng, cx, cy, z0, h, rx, ry, n=10, taper=0.0, overhang=0.06, jag=0.2, bands=1):
    """One stratum chunk: irregular blocky prism; each band ends in a shallow groove so the
    face reads as layered rock."""
    ph = rng.uniform(0, 6.283)
    base = []
    for i in range(n):
        a = ph + 2 * math.pi * i / n + rng.uniform(-0.2, 0.2)
        k = 1 + rng.uniform(-jag, jag)
        ca, sa = math.cos(a), math.sin(a)
        e = 0.3
        base.append((math.copysign(abs(ca) ** e, ca) * rx * k, math.copysign(abs(sa) ** e, sa) * ry * k))
    rings = [(0.0, 0.98)]
    for k in range(bands):
        s_k = 1.0 + rng.uniform(-0.03, overhang)
        top = (k + 1) / bands
        rings.append((top - 0.3 / bands, s_k))
        if k < bands - 1:
            rings.append((top - 0.06 / bands, s_k * 0.99))
            rings.append((top, s_k * 0.94))
    rings.append((1.0, 0.95 - taper))
    verts, faces = [], []
    for zf, sc in rings:
        for (x, y) in base:
            jj = 1 + rng.uniform(-0.04, 0.04)
            dz = rng.uniform(-0.02, 0.02) * h if 0 < zf < 1 else rng.uniform(-0.01, 0.01) * h
            verts.append((cx + x * sc * jj, cy + y * sc * jj, z0 + h * zf + dz))
    for r in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            faces.append([r * n + i, r * n + j, (r + 1) * n + j, (r + 1) * n + i])
    faces.append([(len(rings) - 1) * n + i for i in range(n)])
    faces.append(list(reversed(range(n))))
    bm = bm_from(verts, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    return bm


def sand_color(rng, band, zmax):
    base = [SAND_A, SAND_B, mix(SAND_A, SAND_HI, 0.35), mix(SAND_B, SAND_DK, 0.25)][band % 4]
    base = mix(base, SAND_HI, rng.uniform(0.0, 0.12))

    def fn(l, f):
        nz = f.normal.z
        c = f.calc_center_median()
        col = base
        if nz > 0.55:
            col = mix(base, SAND_HI, 0.55 + 0.2 * (c.z / zmax))
        elif nz < -0.3:
            col = mix(base, SAND_DK, 0.35)
        else:
            col = mix(col, SAND_DK, 0.12 * (1 - c.z / zmax))
        return col
    return fn


def add_stack(mb, rng, layers, cx=0.0, cy=0.0, band0=0, zmax=10.0, split=0.0):
    """layers: list of (h, rx, ry, dx, dy). split>0 breaks a layer into two chunks with a crack."""
    z = 0.0
    for i, (h, rx, ry, dx, dy) in enumerate(layers):
        chunks = [(cx + dx, cy + dy, rx, ry)]
        if split and rx > 2.2 and rng.random() < split:
            f = rng.uniform(0.35, 0.65)
            gap = -0.05
            w1, w2 = rx * f, rx * (1 - f)
            chunks = [(cx + dx - rx + w1, cy + dy + rng.uniform(-0.2, 0.2), w1 - gap, ry * rng.uniform(0.9, 1.05)),
                      (cx + dx + rx - w2, cy + dy + rng.uniform(-0.2, 0.2), w2 - gap, ry * rng.uniform(0.9, 1.05))]
        for (x, y, a, b) in chunks:
            hh = h * (rng.uniform(0.78, 1.0) if len(chunks) > 1 else rng.uniform(0.94, 1.0))
            bm = strata_block(rng, x, y, z, hh, a, b, n=11 if a > 2 else 8, taper=rng.uniform(0.0, 0.08),
                              overhang=rng.uniform(0.02, 0.07), bands=max(1, int(round(hh / 1.2))))
            mb.add(bm, color_fn=sand_color(rng, band0 + i, zmax), shade='flat', jitter=0.025)
        z += h * 0.985
    return z


def build_sandstone_a():
    rng = random.Random(3101)
    mb = C.MeshBuilder('sandstone_a', seed=31)
    layers = []
    hs = [3.0, 2.3, 2.7, 2.0]
    for i, h in enumerate(hs):
        t = i / len(hs)
        layers.append((h, 6.0 * (1 - 0.2 * t) + rng.uniform(-0.3, 0.3), 4.0 * (1 - 0.22 * t) + rng.uniform(-0.2, 0.2),
                       rng.uniform(-0.35, 0.35), rng.uniform(-0.3, 0.3)))
    add_stack(mb, rng, layers, zmax=10.0, split=0.6)
    return mb


def build_sandstone_b():
    rng = random.Random(3202)
    mb = C.MeshBuilder('sandstone_b', seed=32)
    layers = []
    hs = [3.0, 2.6, 2.8, 2.4, 2.2, 1.3]
    for i, h in enumerate(hs):
        t = i / len(hs)
        w = 2.5 * (1 - 0.22 * t) * (0.9 + 0.12 * math.sin(i * 1.7)) + (0.35 if i == len(hs) - 1 else 0)
        layers.append((h, w, w * rng.uniform(0.85, 1.0), rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25)))
    add_stack(mb, rng, layers, zmax=14.0, split=0.0)
    return mb


def build_sandstone_c():
    rng = random.Random(3303)
    mb = C.MeshBuilder('sandstone_c', seed=33)
    layers = [(2.3, 5.0, 3.0, 0, 0), (1.9, 4.0, 2.4, 0.5, -0.2)]
    add_stack(mb, rng, layers, zmax=4.0, split=0.8)
    return mb


def build_sandstone_arch():
    rng = random.Random(3404)
    mb = C.MeshBuilder('sandstone_arch', seed=34)
    zmax = 9.0
    for sx in (-1, 1):                          # two legs, opening x in [-3.2, 3.2]
        legs = []
        for i, h in enumerate([2.8, 2.6]):
            w = 2.1 - 0.1 * i + rng.uniform(-0.1, 0.1)
            legs.append((h, w, 2.0 + rng.uniform(-0.1, 0.1), sx * 0.1 * i, rng.uniform(-0.1, 0.1)))
        add_stack(mb, rng, legs, cx=sx * 5.3, zmax=zmax)
    # span: layers from z 5.2 upward, the lowest one bowed (arched underside)
    z = 5.2
    for i, (h, rx, ry) in enumerate([(1.9, 7.2, 2.0), (1.9, 6.4, 1.8)]):
        bm = strata_block(rng, rng.uniform(-0.3, 0.3), rng.uniform(-0.15, 0.15), z, h, rx, ry, n=12,
                          taper=0.06, overhang=0.04, jag=0.06, bands=2)
        if i == 0:
            for v in bm.verts:                  # lift the underside in the middle into an arch
                if v.co.z < z + h * 0.2 and abs(v.co.x) < 3.4:
                    v.co.z += 0.8 * math.cos(v.co.x / 3.4 * math.pi / 2) ** 1.5
        bm.normal_update()
        mb.add(bm, color_fn=sand_color(rng, 4 + i, zmax), shade='flat', jitter=0.025)
        z += h * 0.97
    return mb


# ================================================================== fauna
DEER_BACK, DEER, DEER_BELLY, DEER_WHITE, DEER_DARK = hexc('#5C4230'), hexc('#7A5A3E'), hexc('#C9A77E'), hexc('#E8E0D0'), hexc('#2A211B')
ANTLER = hexc('#CDB999')


def ring_pts(y, cx, cz, w, top, bot, n=8, jag=0.0, rng=None):
    pts = []
    zc, hz = (top + bot) / 2, (top - bot) / 2
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + (rng.uniform(-jag, jag) if rng else 0)
        pts.append(Vector((cx + math.cos(a) * w * k, y, zc + math.sin(a) * hz * k)))
    return pts


def hull_part(mb, pts, color_fn, angle=40):
    bm = bm_hull(pts)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(2.0), use_dissolve_boundaries=False,
                             verts=bm.verts[:], edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mb.add(bm, color_fn=color_fn, shade='auto', angle=angle, jitter=0.03)


def tube(mb, pts, radii, col, segs=5):
    for (a, b), (r0, r1) in zip(zip(pts, pts[1:]), zip(radii, radii[1:])):
        mb.add(bm_cyl_between(a, b, r0, segs=segs, r2=r1, cap=False), color=col, shade='smooth')


def deer_parts(stag, s=1.0):
    """Returns {name: (MeshBuilder, pivot)} in model space (faces +Y, feet at z=0)."""
    rng = random.Random(4100 if stag else 4200)
    tone = 1.0 if stag else 1.1
    back, main, belly = [C.scale_col(c, tone) for c in (DEER_BACK, DEER, DEER_BELLY)]
    S = lambda *p: Vector(p) * s
    out = {}

    def fur(zmid):
        def fn(l, f):
            c = f.calc_center_median()
            nz = f.normal.z
            col = mix(main, back, smoothstep(0.2, 0.9, nz))
            col = mix(col, belly, smoothstep(-0.2, -0.75, nz))
            if c.y < -0.6 * s and c.z > 0.78 * s:          # white rump patch
                col = mix(col, DEER_WHITE, 0.7)
            return col
        return fn

    # ---- body (torso + tail)
    mb = C.MeshBuilder('Body', seed=1)
    rings = [(-0.72, 0.1, 1.0, 0.84), (-0.6, 0.18, 1.08, 0.72), (-0.35, 0.21, 1.06, 0.68), (-0.05, 0.2, 1.03, 0.7),
             (0.22, 0.22, 1.07, 0.62), (0.44, 0.2, 1.12, 0.6), (0.6, 0.13, 1.06, 0.72)]
    pts = []
    for y, w, top, bot in rings:
        pts += ring_pts(y * s, 0, 0, w * s, top * s, bot * s, 10, 0.02, rng)
    hull_part(mb, pts, fur(0.9))
    tail = [S(-0.08, -0.66, 1.02), S(0.08, -0.66, 1.02), S(0, -0.8, 0.98), S(0, -0.7, 0.9), S(0, -0.78, 1.06)]
    hull_part(mb, tail, lambda l, f: DEER_WHITE if f.normal.z < 0.3 else main)
    out['Body'] = (mb, Vector((0, 0, 0)))

    # ---- neck + head (+ antlers); pivot at the neck base
    piv = S(0, 0.44, 1.02)
    mb = C.MeshBuilder('Neck', seed=2)
    pts = ring_pts(0.36 * s, 0, 0, 0.15 * s, 1.12 * s, 0.78 * s, 8)
    pts += ring_pts(0.58 * s, 0, 0, 0.12 * s, 1.30 * s, 1.0 * s, 8)
    pts += ring_pts(0.74 * s, 0, 0, 0.085 * s, 1.54 * s, 1.34 * s, 8)
    hull_part(mb, pts, fur(1.3))
    head = ring_pts(0.76 * s, 0, 0, 0.1 * s, 1.68 * s, 1.44 * s, 8) + ring_pts(0.92 * s, 0, 0, 0.085 * s, 1.64 * s, 1.42 * s, 8)
    head += ring_pts(1.12 * s, 0, 0, 0.048 * s, 1.52 * s, 1.39 * s, 6) + [S(0, 1.17, 1.45)]

    def head_col(l, f):
        c = f.calc_center_median()
        if c.y > 1.08 * s:
            return DEER_DARK                      # nose
        if c.z < 1.46 * s and c.y > 0.9 * s:
            return mix(main, DEER_WHITE, 0.6)     # muzzle / chin
        if abs(abs(c.x) - 0.085 * s) < 0.03 * s and abs(c.y - 0.9 * s) < 0.04 * s and c.z > 1.52 * s:
            return DEER_DARK                      # eyes
        return mix(main, back, smoothstep(0.3, 0.9, f.normal.z))
    hull_part(mb, head, head_col, angle=38)
    for sx in (-1, 1):                            # ears
        e0 = S(sx * 0.07, 0.78, 1.64)
        ear = [e0, e0 + S(sx * 0.03, -0.03, -0.04), e0 + S(sx * 0.2, -0.05, 0.1), e0 + S(sx * 0.16, -0.02, 0.15),
               e0 + S(sx * 0.1, -0.05, 0.06)]
        hull_part(mb, ear, lambda l, f: mix(main, belly, 0.3), angle=60)
    if stag:
        for sx in (-1, 1):
            beam = [S(sx * 0.05, 0.78, 1.66), S(sx * 0.13, 0.74, 1.84), S(sx * 0.24, 0.66, 1.98),
                    S(sx * 0.28, 0.66, 2.14), S(sx * 0.22, 0.74, 2.28)]
            tube(mb, beam, [0.026 * s, 0.022 * s, 0.018 * s, 0.014 * s, 0.008 * s], ANTLER, 4)
            for i, (lift, fwd) in enumerate(((0.16, 0.14), (0.2, 0.1), (0.14, 0.12))):
                b = beam[i + 1]
                tube(mb, [b, b + S(sx * 0.02, fwd, lift)], [0.014 * s, 0.006 * s], ANTLER, 4)
    out['Neck'] = (mb, piv)

    # ---- legs; pivot at shoulder / hip
    for key, sx, front in (('LegFL', -1, True), ('LegFR', 1, True), ('LegRL', -1, False), ('LegRR', 1, False)):
        mb = C.MeshBuilder(key, seed=3)
        x = sx * 0.12
        if front:
            piv = S(x, 0.42, 0.84)
            thigh = ring_pts(0.42 * s, x * s, 0, 0.085 * s, 0.95 * s, 0.7 * s, 7) + ring_pts(0.45 * s, x * s, 0, 0.05 * s, 0.5 * s, 0.4 * s, 6)
            knee, fet, hoof = S(x, 0.45, 0.44), S(x, 0.44, 0.09), S(x, 0.47, 0.0)
        else:
            piv = S(x, -0.5, 0.9)
            thigh = ring_pts(-0.46 * s, x * s, 0, 0.09 * s, 1.02 * s, 0.7 * s, 7) + ring_pts(-0.62 * s, x * s, 0, 0.05 * s, 0.52 * s, 0.44 * s, 6)
            thigh += ring_pts(-0.38 * s, x * s, 0, 0.07 * s, 0.9 * s, 0.66 * s, 6)
            knee, fet, hoof = S(x, -0.62, 0.47), S(x, -0.56, 0.09), S(x, -0.53, 0.0)
        hull_part(mb, thigh, fur(0.7))
        tube(mb, [knee, fet], [0.034 * s, 0.024 * s], mix(main, back, 0.3), 5)
        mb.add(bm_cyl_between(fet, hoof, 0.03 * s, segs=5, r2=0.036 * s), color=DEER_DARK, shade='flat')
        out[key] = (mb, piv)
    return out


EAGLE_D, EAGLE_M, EAGLE_W, EAGLE_Y = hexc('#2E2119'), hexc('#4A3526'), hexc('#EFEDE6'), hexc('#E5B532')


def eagle_parts():
    out = {}
    mb = C.MeshBuilder('Body', seed=5)
    pts = []
    for y, w, top, bot in ((-0.30, 0.07, 0.05, -0.04), (-0.12, 0.13, 0.09, -0.1), (0.1, 0.14, 0.1, -0.1),
                           (0.25, 0.1, 0.09, -0.05)):
        pts += ring_pts(y, 0, 0, w, top, bot, 8)
    hull_part(mb, pts, lambda l, f: mix(EAGLE_M, EAGLE_D, 0.5 if f.normal.z > 0 else 0.1))
    head = ring_pts(0.26, 0, 0, 0.075, 0.12, -0.02, 8) + ring_pts(0.40, 0, 0, 0.06, 0.1, 0.0, 7)
    hull_part(mb, head, lambda l, f: EAGLE_W)
    beak = [Vector((0.03, 0.42, 0.06)), Vector((-0.03, 0.42, 0.06)), Vector((0.025, 0.43, 0.02)), Vector((-0.025, 0.43, 0.02)),
            Vector((0, 0.51, 0.04)), Vector((0, 0.5, 0.0))]
    hull_part(mb, beak, lambda l, f: EAGLE_Y, angle=60)
    tail = [Vector((0.05, -0.28, 0.03)), Vector((-0.05, -0.28, 0.03)), Vector((0.05, -0.28, -0.01)), Vector((-0.05, -0.28, -0.01)),
            Vector((0.15, -0.56, 0.01)), Vector((-0.15, -0.56, 0.01)), Vector((0.1, -0.6, 0.0)), Vector((-0.1, -0.6, 0.0))]
    hull_part(mb, tail, lambda l, f: EAGLE_W, angle=60)
    for sx in (-1, 1):
        f0 = Vector((sx * 0.05, -0.08, -0.09))
        mb.add(bm_cyl_between(f0, f0 + Vector((0, -0.12, -0.03)), 0.022, segs=5, r2=0.014), color=EAGLE_Y, shade='flat')
    out['Body'] = (mb, Vector((0, 0, 0)))
    # wings: horizontal, dihedral up slightly, primary "fingers" at the tip
    for key, sx in (('WingL', -1), ('WingR', 1)):
        mb = C.MeshBuilder(key, seed=6)
        piv = Vector((sx * 0.1, 0.06, 0.05))
        lead = [(0.1, 0.16), (0.35, 0.24), (0.62, 0.22), (0.8, 0.16)]
        trail = [(0.8, -0.1), (0.55, -0.16), (0.3, -0.18), (0.1, -0.12)]
        poly = lead + trail
        n = len(poly)
        verts = []
        for (x, y) in poly:
            th = 0.035 * (1 - x) + 0.008
            z = 0.05 + 0.08 * x
            verts.append(Vector((sx * x, y, z + th)))
        for (x, y) in poly:
            th = 0.035 * (1 - x) + 0.008
            z = 0.05 + 0.08 * x
            verts.append(Vector((sx * x, y, z - th * 0.6)))
        faces = [list(range(n)), list(range(2 * n - 1, n - 1, -1))]
        for i in range(n):
            j = (i + 1) % n
            faces.append([i, j, n + j, n + i])
        bm = bm_from(verts, faces)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])

        def wcol(l, f, sx=sx):
            c = f.calc_center_median()
            return mix(EAGLE_M, EAGLE_D, smoothstep(0.25, 0.7, abs(c.x)) * 0.8 + (0.2 if f.normal.z < 0 else 0))
        mb.add(bm, color_fn=wcol, shade='flat')
        for k in range(5):                        # primaries
            y0 = 0.14 - k * 0.055
            base = Vector((sx * 0.78, y0, 0.05 + 0.08 * 0.78))
            tip = Vector((sx * (1.0 - k * 0.018), y0 + 0.03 - k * 0.02, 0.05 + 0.08 + 0.02))
            w = 0.022
            for flip in (False, True):             # both windings: visible from above and below
                fb = bm_from([base + Vector((0, w, 0)), base - Vector((0, w, 0)), tip], [[0, 1, 2]])
                C.orient(fb, lambda f, flip=flip: -UP if flip else UP)
                mb.add(fb, color=EAGLE_D, shade='flat')
        out[key] = (mb, piv)
    return out


def build_multi(parts, mats, col, fname):
    objs = []
    tris = 0
    pivots = {}
    for name, (mb, piv) in parts.items():
        tris += mb.tris()
        ob = mb.build(mats, vcolor=True, collection_obj=col)
        ob.data.transform(Matrix.Translation(-piv))
        ob.location = piv
        objs.append(ob)
        pivots[name] = [round(piv.x, 3), round(piv.y, 3), round(piv.z, 3)]
    bpy.context.view_layer.update()
    C.export_glb(objs, fname, vcolor=True)
    return objs, tris, pivots


# ================================================================== main
TREES = ['maple_red', 'maple_orange', 'birch', 'larch_gold']
TREE_BUDGET = {'maple_red': (1200, 300), 'maple_orange': (1200, 300), 'birch': (1200, 300), 'larch_gold': (1400, 350),
               'grass_tall': (150, 48)}
SINGLES = {'flowers_a': (build_flowers_a, 180), 'flowers_b': (build_flowers_b, 180),
           'boulder_a': (lambda: build_big_boulder('boulder_a'), 320),
           'boulder_b': (lambda: build_big_boulder('boulder_b'), 320),
           'boulder_c': (lambda: build_big_boulder('boulder_c'), 320),
           'sandstone_a': (build_sandstone_a, 1600), 'sandstone_b': (build_sandstone_b, 1600),
           'sandstone_c': (build_sandstone_c, 1600), 'sandstone_arch': (build_sandstone_arch, 1600)}


def lod_builder(name):
    if name.startswith('maple'):
        return lambda lod: build_maple(name, lod)
    return {'birch': build_birch, 'larch_gold': build_larch, 'grass_tall': build_grass_tall}[name]


def bbox_info(objs):
    mn, mx = C.world_bbox(objs)
    size = mx - mn
    return {'size': [round(v, 2) for v in size], 'min': [round(v, 2) for v in mn], 'max': [round(v, 2) for v in mx]}


def main():
    C.reset_scene()
    mats = {'VC': C.mat_vc('VC'), 'VC_2S': C.mat_vc('VC_2S', double_sided=True)}
    col0, col1 = C.collection('Nature_LOD0'), C.collection('Nature_LOD1')
    colF = C.collection('Nature_Fauna')
    objs, report = {}, {}
    warn = []
    for name, (b0, b1) in TREE_BUDGET.items():
        for lod in (0, 1):
            mb = lod_builder(name)(lod)
            nm = name + ('_lod1' if lod else '')
            t = mb.tris()
            ob = mb.build(mats, vcolor=True, collection_obj=col1 if lod else col0)
            objs[nm] = ob
            C.export_glb([ob], nm + '.glb', vcolor=True)
            report[nm] = dict(tris=t, **bbox_info([ob]))
            if t > (b1 if lod else b0):
                warn.append('%s %d > %d' % (nm, t, b1 if lod else b0))
    for name, (fn, budget) in SINGLES.items():
        mb = fn()
        t = mb.tris()
        ob = mb.build(mats, vcolor=True, collection_obj=col0)
        objs[name] = ob
        C.export_glb([ob], name + '.glb', vcolor=True)
        info = dict(tris=t, **bbox_info([ob]))
        if name.startswith('boulder') or name.startswith('sandstone'):
            mn, mx = C.world_bbox([ob])
            # collider: box on the footprint, slightly inside the silhouette, from the ground up
            info['collider_half'] = [round((mx.x - mn.x) * 0.45, 2), round((mx.y - mn.y) * 0.45, 2), round(max(0.0, mx.z) * 0.5, 2)]
        if name == 'sandstone_arch':
            info['colliders'] = {'legs': [{'center': [sx * 5.3, 0, 2.7], 'half': [1.9, 1.9, 2.7]} for sx in (-1, 1)],
                                 'span': {'center': [0, 0, 7.05], 'half': [6.9, 1.9, 1.85]},
                                 'opening': 'x in [-3.2, 3.2], z in [0, ~5.2] clear (arched to ~6.0 at centre)'}
        report[name] = info
        if t > budget:
            warn.append('%s %d > %d' % (name, t, budget))
    fauna = {}
    for fname, parts in (('deer_stag', deer_parts(True)), ('deer_doe', deer_parts(False, 0.93)), ('eagle', eagle_parts())):
        fo, t, piv = build_multi(parts, mats, colF, fname + '.glb')
        for o in fo:
            o.name = fname + '_' + o.name          # free the node names for the next asset
        fauna[fname] = fo
        report[fname] = dict(tris=t, pivots=piv, **bbox_info(fo))
        if t > (600 if fname == 'eagle' else 900):
            warn.append('%s %d' % (fname, t))
    for k, v in report.items():
        print('NATURE2 %-16s tris %5d size %s' % (k, v['tris'], v['size']))
    print('NATURE2 WARN', warn or 'none')
    with open(os.path.join(C.ART, 'nature2-report.json'), 'w') as f:
        json.dump(report, f, indent=1)

    # ---- previews
    C.setup_render(res=(1280, 720), sky='#E9C9A0')
    C.add_sun((55, 0, 135), 4.2, color='#FFE2BD')
    C.add_ground(0.0, color='#B8964F')
    allo = list(objs.values()) + [o for fo in fauna.values() for o in fo]
    for o in allo:
        o.hide_render = True

    def shot(names, fname, gap, az=20, el=10, lens=50):
        sel = [objs[n] for n in names]
        for o in sel:
            o.hide_render = False
        C.lineup(sel, gap)
        C.frame_camera(sel, az=az, el=el, lens=lens)
        C.render(fname)
        for o in sel:
            o.hide_render = True
            o.location = (0, 0, 0)

    shot(TREES, 'nature_trees.png', 1.5)
    shot([n + '_lod1' for n in TREES], 'nature_trees_lod1.png', 1.5)
    shot(['grass_tall', 'grass_tall_lod1', 'flowers_a', 'flowers_b'], 'nature_small.png', 0.3, el=18)
    shot(['boulder_a', 'boulder_b', 'boulder_c'], 'nature_boulders.png', 1.0, az=30, el=14)
    shot(['sandstone_a', 'sandstone_b', 'sandstone_c', 'sandstone_arch'], 'nature_sandstone.png', 2.0, az=25, el=8)
    # fauna lineup: move each group along X
    sel = []
    for i, (fname, fo) in enumerate(fauna.items()):
        dx = (i - 1) * 2.6
        for o in fo:
            o.location.x += dx
            if fname == 'eagle':
                o.location.z += 1.2
            o.hide_render = False
            sel.append(o)
    bpy.context.view_layer.update()
    C.frame_camera(sel, az=55, el=10, lens=60)
    C.render('nature_fauna.png')
    stag = fauna['deer_stag']
    for o in sel:
        o.hide_render = o not in stag
    C.frame_camera(stag, az=70, el=6, lens=70)
    C.render('nature_deer_closeup.png')
    for o in sel:
        o.hide_render = True
    # meadow composition: many grass clumps + flowers, autumn trees behind
    rng = random.Random(9)
    meadow = []
    for k in range(260):
        src = objs['grass_tall'] if rng.random() < 0.9 else objs[rng.choice(['flowers_a', 'flowers_b'])]
        o = bpy.data.objects.new('m%d' % k, src.data)
        bpy.context.scene.collection.objects.link(o)
        o.location = (rng.uniform(-7, 7), rng.uniform(-5, 9), 0)
        o.rotation_euler = (0, 0, rng.uniform(0, 6.28))
        s = rng.uniform(0.8, 1.25)
        o.scale = (s, s, s)
        meadow.append(o)
    for i, n in enumerate(['maple_red', 'birch', 'larch_gold', 'maple_orange', 'birch', 'larch_gold', 'maple_red']):
        o = bpy.data.objects.new('t%d' % i, objs[n].data)
        bpy.context.scene.collection.objects.link(o)
        o.location = (-16 + i * 5.5 + rng.uniform(-1, 1), 16 + rng.uniform(-3, 4), 0)
        meadow.append(o)
    b = bpy.data.objects.new('bm', objs['boulder_a'].data)
    bpy.context.scene.collection.objects.link(b)
    b.location = (4, 4, 0)
    meadow.append(b)
    cam = C.frame_camera(meadow, az=180, el=4, lens=35)
    cam.location = (0, -9, 1.5)
    cam.rotation_euler = (math.radians(86), 0, 0)
    cam.data.shift_x = cam.data.shift_y = 0
    C.render('nature_meadow.png')
    for o in meadow:
        bpy.data.objects.remove(o)
    for o in allo:
        o.hide_render = False
    col1.hide_viewport = True
    C.save_blend('nature2.blend')
    return report


if __name__ == '__main__':
    main()
