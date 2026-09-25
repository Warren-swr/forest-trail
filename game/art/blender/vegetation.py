"""Forest Trail vegetation: pines, aspen, snag, bushes, fern, grass (+ _lod1 of each).

Run: blender --background --python vegetation.py
Every asset is one mesh with the vertex-colour material "VC"; origin = trunk base on the ground.
Crowns get soft custom normals pointing away from the tree axis.
"""
import bpy, bmesh, math, os, random, sys
from mathutils import Vector, Matrix, Euler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
from common import hexc, mix, ramp, bm_lathe, bm_cyl_between, bm_icosphere, bm_from, xform, mat_trs

UP = Vector((0, 0, 1))
NEEDLE_DARK = hexc('#203E35')
NEEDLE_MID = hexc('#35573F')
NEEDLE_LIGHT = hexc('#5E7F52')
BARK_DARK = hexc('#3E3530')
BARK = hexc('#5A4636')
BARK_LIGHT = hexc('#6B4A32')


def radial_normal(p, up=0.55, face_n=None, face_w=0.25, rmin=0.25):
    """Soft normal pointing away from the tree axis (Z), tilted up."""
    r = Vector((p.x, p.y, 0))
    k = min(1.0, r.length / rmin)
    n = (r.normalized() * k if r.length > 1e-6 else Vector()) + UP * (up + (1 - k) * 0.6)
    if face_n is not None:
        n = n.normalized() + face_n * face_w
    return n.normalized()


def center_normal(p, c, face_n=None, face_w=0.3, squash=1.0):
    d = p - Vector(c)
    d.z *= squash
    n = d.normalized() if d.length > 1e-6 else UP.copy()
    if face_n is not None:
        n = (n + face_n * face_w).normalized()
    return n


# ------------------------------------------------------------------ conifer tier
def pine_tier(rng, n, R, dh, detail=1, tip_jit=0.12, droop_jit=0.15):
    """One drooping, serrated branch whorl. Local apex at the origin, rim below at z=-dh.
    detail 1: apex, ring A, ring B, rim (notches + tips), underside ring, bottom centre (10n tris)
    detail 0: apex, rim, bottom centre (4n tris)."""
    ph = rng.uniform(0, 2 * math.pi)
    ang = [ph + 2 * math.pi * i / n + rng.uniform(-0.12, 0.12) * 2 * math.pi / n for i in range(n)]
    ang.append(ang[0] + 2 * math.pi)
    verts = []

    def add(p):
        verts.append(Vector(p))
        return len(verts) - 1

    def ring(rf, zf, angles, rj=0.0, zj=0.0):
        out = []
        for a in angles:
            r = R * rf * (1 + rng.uniform(-rj, rj))
            out.append(add((r * math.cos(a), r * math.sin(a), -dh * (zf + rng.uniform(-zj, zj)))))
        return out

    apex = add((0, 0, 0))
    mids = [(ang[i] + ang[i + 1]) / 2 for i in range(n)]
    faces = []
    if detail:
        A = ring(0.30, 0.20, ang[:n])
        B = ring(0.64, 0.50, ang[:n], 0.05, 0.04)
        notch = ring(0.74, 0.74, ang[:n], 0.06, 0.05)
        tip = ring(1.0, 1.0, mids, tip_jit, droop_jit)
        U = ring(0.46, 0.64, ang[:n])
        bot = add((0, 0, -dh * 0.46))
        for i in range(n):
            j = (i + 1) % n
            faces += [[apex, A[j], A[i]],
                      [A[i], A[j], B[j], B[i]],
                      [B[i], tip[i], notch[i]], [B[i], B[j], tip[i]], [B[j], notch[j], tip[i]],
                      [U[i], notch[i], tip[i]], [U[i], tip[i], U[j]], [U[j], tip[i], notch[j]],
                      [bot, U[i], U[j]]]
    else:
        notch = ring(0.70, 0.70, ang[:n], 0.05, 0.04)
        tip = ring(1.0, 1.0, mids, tip_jit, droop_jit)
        bot = add((0, 0, -dh * 0.50))
        for i in range(n):
            j = (i + 1) % n
            faces += [[apex, tip[i], notch[i]], [apex, notch[j], tip[i]],
                      [bot, notch[i], tip[i]], [bot, tip[i], notch[j]]]
    bm = bm_from(verts, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def add_pine_crown(mb, rng, tiers, H, lod, colors=(NEEDLE_DARK, NEEDLE_MID, NEEDLE_LIGHT)):
    """tiers: list of dict(z=apex height, R, dh, n, off=(x,y), tilt, detail)."""
    dark, mid_c, light = colors
    for t in tiers:
        bm = pine_tier(rng, t['n'], t['R'], t['dh'], t['detail'], t.get('tip_jit', 0.12))
        rot = Euler((t.get('tilt', (0, 0))[0], t.get('tilt', (0, 0))[1], rng.uniform(0, 6.283)))
        M = Matrix.Translation((t['off'][0], t['off'][1], t['z'])) @ rot.to_matrix().to_4x4()
        xform(bm, M)
        R, z = t['R'], t['z']
        hf = z / H

        def cfn(l, f, R=R, hf=hf, z=z, dh=t['dh']):
            p = l.vert.co
            rf = min(1.0, Vector((p.x, p.y, 0)).length / R)
            below = f.normal.z < -0.05
            v = 0.0 + 0.62 * rf ** 1.6 + 0.30 * hf
            if below:
                v *= 0.3
            c = ramp([(0.0, dark), (0.5, mid_c), (1.0, light)], v)
            return c

        def nfn(l, f, R=R):
            return radial_normal(l.vert.co, up=0.6, face_n=f.normal, face_w=0.22, rmin=R * 0.5)

        mb.add(bm, color_fn=cfn, normal_fn=nfn, jitter=0.05, hue=0.03)


def add_trunk(mb, rng, H, r0, segs, rings, top=0.97, lean=(0.0, 0.0), cols=(BARK_DARK, BARK, BARK_LIGHT),
              flare=1.35, bumpy=0.0):
    prof = [(r0 * flare, 0.0), (r0 * 1.02, 0.35)]
    for k in range(1, rings):
        t = k / rings
        prof.append((max(0.02, r0 * (1 - t) ** 1.05 * 0.92), 0.35 + (H * top - 0.35) * t))
    prof.append((0, H * top))
    bm = bm_lathe(prof, segs, 'Z', phase=rng.uniform(0, 1))
    for v in bm.verts:
        v.co.x += lean[0] * (v.co.z / H) ** 2
        v.co.y += lean[1] * (v.co.z / H) ** 2
        if bumpy:
            v.co.x *= 1 + rng.uniform(-bumpy, bumpy)
            v.co.y *= 1 + rng.uniform(-bumpy, bumpy)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    d, m, l = cols

    def cfn(lp, f):
        z = lp.vert.co.z / H
        return ramp([(0.0, d), (0.25, m), (1.0, l)], z)

    mb.add(bm, color_fn=cfn, shade='smooth', jitter=0.06)


def add_stub(mb, base, direction, length, r, segs=4, col=BARK, up=0.0):
    d = Vector(direction).normalized()
    tip = Vector(base) + d * length
    bm = bm_cyl_between(base, tip, r, segs=segs, r2=r * 0.25, cap=False)
    mb.add(bm, color=col, shade='smooth', jitter=0.08)


# ------------------------------------------------------------------ pine layouts
PINES = {
    #            H     crown_start  Rmax  tiers lod0  n lod0  tiers lod1  n lod1  trunk r
    'pine_tall_a': dict(H=19.0, z0=0.36, Rmax=3.3, N=8, n=12, N1=6, n1=7, r0=0.40, shape=0.85,
                        stubs=5, seed=11, tj=0.12, off=0.12),
    'pine_tall_b': dict(H=17.5, z0=0.40, Rmax=2.8, N=9, n=11, N1=6, n1=7, r0=0.36, shape=0.95,
                        stubs=6, seed=23, tj=0.20, off=0.22),
    'pine_mid': dict(H=11.0, z0=0.14, Rmax=2.6, N=7, n=11, N1=5, n1=7, r0=0.22, shape=0.9,
                     stubs=2, seed=37, tj=0.12, off=0.10),
    'pine_young': dict(H=4.3, z0=0.05, Rmax=1.35, N=4, n=8, N1=3, n1=6, r0=0.09, shape=0.9,
                       stubs=0, seed=41, tj=0.10, off=0.04),
}


def pine_tiers(cfg, lod, rng):
    H, N = cfg['H'], (cfg['N'] if lod == 0 else cfg['N1'])
    n = cfg['n'] if lod == 0 else cfg['n1']
    z0 = cfg['z0'] * H
    Hc = H * 0.90                           # apex of the highest full tier
    tiers = []
    # rim heights are spaced evenly (slightly tighter near the top)
    for k in range(N):
        t = k / N
        rim = z0 + (Hc - z0) * (t ** 1.05)
        spacing = (Hc - z0) / N
        dh = spacing * (2.05 if lod == 0 else 2.2) + 0.35 * (1 - t)
        R = cfg['Rmax'] * (1 - t) ** cfg['shape'] * (1 + rng.uniform(-0.08, 0.08)) + 0.25
        o = cfg['off'] * (1 - t)
        apex = min(rim + dh, H * 0.93)
        dh = apex - rim
        tiers.append(dict(z=apex, R=R, dh=dh, n=n, detail=1 if lod == 0 else 0,
                          off=(rng.uniform(-o, o), rng.uniform(-o, o)),
                          tilt=(rng.uniform(-0.07, 0.07), rng.uniform(-0.07, 0.07)), tip_jit=cfg['tj']))
    # leader / top spike
    top_dh = H - Hc + spacing * 0.9
    tiers.append(dict(z=H, R=0.25 + cfg['Rmax'] * 0.09, dh=top_dh, n=max(5, n // 2),
                      detail=1 if lod == 0 else 0, off=(0, 0), tilt=(0, 0), tip_jit=0.1))
    return tiers


def build_pine(name, lod):
    cfg = PINES[name]
    rng = random.Random(cfg['seed'] * 10 + lod)
    mb = C.MeshBuilder(name + ('_lod1' if lod else ''), seed=cfg['seed'] + lod)
    H = cfg['H']
    add_trunk(mb, rng, H, cfg['r0'], 8 if lod == 0 else 4, 4 if lod == 0 else 1, top=0.9)
    if lod == 0:
        for k in range(cfg['stubs']):
            z = cfg['z0'] * H * rng.uniform(0.35, 0.95)
            a = rng.uniform(0, 6.283)
            d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.45, -0.1)))
            rr = cfg['r0'] * (1 - z / H)
            add_stub(mb, (math.cos(a) * rr * 0.6, math.sin(a) * rr * 0.6, z), d,
                     rng.uniform(0.5, 1.3) * H / 19, 0.05 * H / 19 + 0.015)
    add_pine_crown(mb, rng, pine_tiers(cfg, lod, rng), H, lod)
    return mb


# ------------------------------------------------------------------ aspen
ASPEN_DARK = hexc('#6E4C16')
ASPEN = hexc('#C08A2A')
ASPEN_LIGHT = hexc('#D9A93B')


def lumpy_blob(rng, r, center, subdiv, squash=0.85, amp=0.16):
    bm = bm_icosphere(1.0, subdiv)
    for v in bm.verts:
        k = 1 + rng.uniform(-amp, amp)
        v.co = Vector((v.co.x * r * k, v.co.y * r * k, v.co.z * r * k * squash)) + Vector(center)
    bm.normal_update()
    return bm


def build_aspen(lod):
    rng = random.Random(501 + lod)
    mb = C.MeshBuilder('aspen_gold' + ('_lod1' if lod else ''), seed=5 + lod)
    H = 10.0
    bark_w, bark_d = hexc('#7A7569'), hexc('#3F3A33')  # linear in the engine, see nature2 birch
    segs, rings = (7, 6) if lod == 0 else (5, 2)
    prof = [(0.20, 0.0), (0.16, 0.3)]
    for k in range(1, rings + 1):
        t = k / rings
        prof.append((0.15 * (1 - t) ** 0.9 + 0.025, 0.3 + (H * 0.82 - 0.3) * t))
    prof.append((0, H * 0.86))
    bm = bm_lathe(prof, segs, 'Z')
    for v in bm.verts:                     # gentle S-bend
        v.co.x += 0.25 * math.sin(v.co.z / H * 3.0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    marks = {}

    def cfn(l, f):
        if f.index not in marks:
            marks[f.index] = rng.random() < (0.22 if f.calc_center_median().z > 0.6 else 0.7)
        base = mix(bark_w, bark_d, 0.85 if marks[f.index] else 0.0)
        return base if l.vert.co.z > 0.5 else mix(base, bark_d, 0.5)

    mb.add(bm, color_fn=cfn, shade='smooth', jitter=0.03)
    # clumps on an egg-shaped crown
    cz, crx, crz = 7.0, 2.2, 2.7
    clumps = [((0, 0, 9.0), 1.45)]
    n_cl = 10 if lod == 0 else 8
    for i in range(n_cl - 1):
        a = i * 2.39996 + rng.uniform(-0.3, 0.3)
        t = (i + 0.5) / (n_cl - 1)
        z = cz + crz * (0.75 - 1.35 * t)
        rr = crx * math.sqrt(max(0.05, 1 - ((z - cz) / crz) ** 2)) * rng.uniform(0.5, 0.72)
        clumps.append(((rr * math.cos(a) + 0.2, rr * math.sin(a), z), rng.uniform(1.05, 1.4)))
    ctr = Vector((0.1, 0, cz))
    for (c, r) in clumps:
        if lod == 0 and c[2] < 8.5:          # a thin branch into each lower clump
            z0 = c[2] - 1.6
            p0 = Vector((0.25 * math.sin(z0 / H * 3.0), 0, z0))
            b = bm_cyl_between(p0, Vector(c) * 0.7 + p0 * 0.3, 0.045, segs=4, r2=0.02, cap=False)
            mb.add(b, color=hexc('#BDB6A5'), shade='smooth')
        bm = lumpy_blob(rng, r if lod == 0 else r * 1.08, c, 2 if lod == 0 else 1, 0.82, 0.18 if lod == 0 else 0.1)

        def cfn2(l, f):
            p = l.vert.co
            out = (p - ctr).length / (crx * 1.3)
            v = 0.0 + 0.55 * min(1.0, out) ** 1.5 + 0.35 * (p.z - (cz - crz)) / (2 * crz)
            v *= 0.5 if f.normal.z < -0.3 else 1.0
            return ramp([(0.0, ASPEN_DARK), (0.55, ASPEN), (1.0, ASPEN_LIGHT)], v)

        def nfn(l, f):
            return center_normal(l.vert.co, ctr, f.normal, 0.35, squash=0.8)

        mb.add(bm, color_fn=cfn2, normal_fn=nfn, jitter=0.07, hue=0.04)
    return mb


# ------------------------------------------------------------------ snag
def build_snag(lod):
    rng = random.Random(601 + lod)
    mb = C.MeshBuilder('snag' + ('_lod1' if lod else ''), seed=6 + lod)
    H = 9.0
    grey_d, grey, grey_l = hexc('#4E4942'), hexc('#7E7A71'), hexc('#9A958A')
    segs = 9 if lod == 0 else 5
    prof = [(0.46, 0.0), (0.31, 0.45), (0.27, 1.6), (0.25, 3.2), (0.21, 5.0), (0.18, 6.8), (0.16, 8.2)] \
        if lod == 0 else [(0.40, 0.0), (0.24, 3.0), (0.16, 8.2)]
    bm = bm_lathe(prof, segs, 'Z')
    top = [v for v in bm.verts if abs(v.co.z - 8.2) < 1e-4]
    for i, v in enumerate(sorted(top, key=lambda v: math.atan2(v.co.y, v.co.x))):
        v.co.z = 8.2 + (0.8 if i % 2 == 0 else 0.0) * rng.uniform(0.4, 1.0) + (0.1 if i == 0 else 0)
    c = bm.verts.new((0.02, 0.0, 8.35))
    ring = sorted(top, key=lambda v: math.atan2(v.co.y, v.co.x))
    for i in range(len(ring)):
        try:
            bm.faces.new([c, ring[i], ring[(i + 1) % len(ring)]])
        except ValueError:
            pass
    for v in bm.verts:
        v.co.x += 0.35 * (v.co.z / H) ** 2
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    def cfn(l, f):
        return ramp([(0.0, grey_d), (0.2, grey), (1.0, grey_l)], l.vert.co.z / H)

    mb.add(bm, color_fn=cfn, shade='auto', angle=55, jitter=0.07)
    n_br = 10 if lod == 0 else 3
    for k in range(n_br):
        z = 2.5 + 5.2 * (k + 0.5) / n_br + rng.uniform(-0.3, 0.3)
        a = k * 2.2 + rng.uniform(-0.4, 0.4)
        rr = 0.2 * (1 - z / 10)
        base = Vector((math.cos(a) * rr + 0.35 * (z / H) ** 2, math.sin(a) * rr, z))
        d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.5, 0.35))).normalized()
        L = rng.uniform(0.5, 1.6) * (1.2 - z / H)
        bm = bm_cyl_between(base, base + d * L, 0.07 * (1.1 - z / H) + 0.02, segs=4 if lod == 0 else 3,
                            r2=0.015, cap=False)
        mb.add(bm, color=mix(grey, grey_l, 0.4), shade='smooth', jitter=0.05)
        if lod == 0 and k % 3 == 0:          # a forked twig on some branches
            p = base + d * L * 0.6
            d2 = (d + Vector((rng.uniform(-.6, .6), rng.uniform(-.6, .6), 0.5))).normalized()
            mb.add(bm_cyl_between(p, p + d2 * L * 0.45, 0.03, segs=3, r2=0.01, cap=False),
                   color=grey_l, shade='smooth')
    return mb


# ------------------------------------------------------------------ bushes
def build_bush_a(lod):
    rng = random.Random(701 + lod)
    mb = C.MeshBuilder('bush_a' + ('_lod1' if lod else ''), seed=7 + lod)
    dark, mid_c, light = hexc('#1E3A31'), hexc('#3A5A40'), hexc('#6E8A55')
    blobs = [((0.0, 0.0, 0.62), 0.62), ((0.55, 0.18, 0.45), 0.46), ((-0.42, -0.25, 0.42), 0.44)]
    ctr = Vector((0.05, 0, 0.45))
    for c, r in blobs:
        bm = lumpy_blob(rng, r, c, 2 if lod == 0 else 1, 0.9, 0.26 if lod == 0 else 0.12)
        for v in bm.verts:
            v.co.z = max(v.co.z, 0.03)

        def cfn(l, f):
            p = l.vert.co
            v = 0.55 * min(1, (p - ctr).length / 0.8) ** 1.5 + 0.4 * p.z / 1.2
            return ramp([(0, dark), (0.5, mid_c), (1, light)], v * (0.5 if f.normal.z < -0.4 else 1))

        mb.add(bm, color_fn=cfn, normal_fn=lambda l, f: center_normal(l.vert.co, ctr, f.normal, 0.35, 0.8),
               jitter=0.12, hue=0.05)
    return mb


def build_bush_b(lod):
    """Low juniper-like conifer shrub built from the pine tiers."""
    rng = random.Random(801 + lod)
    mb = C.MeshBuilder('bush_b' + ('_lod1' if lod else ''), seed=8 + lod)
    H = 1.25
    if lod == 0:
        tiers = [dict(z=0.55, R=0.75, dh=0.55, n=7), dict(z=0.85, R=0.62, dh=0.55, n=7),
                 dict(z=1.08, R=0.45, dh=0.5, n=7), dict(z=H, R=0.26, dh=0.4, n=7)]
    else:
        tiers = [dict(z=0.62, R=0.76, dh=0.62, n=5), dict(z=0.98, R=0.56, dh=0.62, n=5),
                 dict(z=H, R=0.3, dh=0.45, n=5)]
    for t in tiers:
        t.update(detail=1 if lod == 0 else 0, off=(rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05)),
                 tilt=(rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1)), tip_jit=0.18)
    add_pine_crown(mb, rng, tiers, H, lod, (hexc('#1F3B33'), hexc('#34563F'), hexc('#5E7F52')))
    return mb


# ------------------------------------------------------------------ fern & grass (double sided)
def build_fern(lod):
    rng = random.Random(901 + lod)
    mb = C.MeshBuilder('fern' + ('_lod1' if lod else ''), seed=9 + lod)
    base_c, mid_c, tip_c = hexc('#2B4A38'), hexc('#49694B'), hexc('#7D8D53')
    fronds, segs = (10, 8) if lod == 0 else (5, 4)
    for k in range(fronds):
        a = k * 2 * math.pi / fronds + rng.uniform(-0.2, 0.2)
        L = rng.uniform(0.62, 0.8)
        el0 = rng.uniform(1.25, 1.45)            # start steep, arch over
        d_h = Vector((math.cos(a), math.sin(a), 0))
        side = Vector((-math.sin(a), math.cos(a), 0))
        spine = []
        for j in range(segs + 1):
            t = j / segs
            el = el0 - 1.6 * t
            ds = L / segs
            if j == 0:
                p = Vector((0, 0, 0.02))
            else:
                p = spine[-1] + (d_h * math.cos(el) + UP * math.sin(el)) * ds
            spine.append(p)
        verts, faces = [], []
        for j in range(segs):
            t = (j + 0.5) / segs
            w = 0.16 * math.sin(math.pi * (0.15 + 0.85 * t)) * (1.0 if lod == 0 else 1.15)
            s0, s1 = spine[j], spine[j + 1]
            mid = (s0 + s1) / 2
            for sg in (1, -1):
                tip = mid + side * sg * w + (s1 - s0) * 0.6 + UP * 0.03
                i0 = len(verts)
                verts += [s0, s1, tip]
                faces.append([i0, i0 + 1, i0 + 2] if sg > 0 else [i0, i0 + 2, i0 + 1])
        bm = bm_from(verts, faces)
        for v in bm.verts:
            v.co.z *= 1.4
        C.orient(bm, lambda f: UP)

        def cfn(l, f, L=L):
            p = l.vert.co
            t = Vector((p.x, p.y, 0)).length / (L * 0.8)
            return ramp([(0, base_c), (0.45, mid_c), (1, tip_c)], t)

        mb.add(bm, mat='VC_2S', color_fn=cfn,
               normal_fn=lambda l, f: radial_normal(l.vert.co, up=1.4, rmin=0.2), jitter=0.06, hue=0.03)
    return mb


def build_grass(lod):
    rng = random.Random(1001 + lod)
    mb = C.MeshBuilder('grass_tuft' + ('_lod1' if lod else ''), seed=10 + lod)
    base_c, mid_c, tip_c = hexc('#6E6346'), hexc('#8D795B'), hexc('#C5A861')
    green = hexc('#8C8F58')
    blades = 14 if lod == 0 else 4
    for k in range(blades):
        a = k * 2.39996 + rng.uniform(-0.3, 0.3)
        h = rng.uniform(0.45, 0.68) if lod == 0 else rng.uniform(0.55, 0.65)
        lean = rng.uniform(0.12, 0.32)
        d = Vector((math.cos(a), math.sin(a), 0))
        side = Vector((-math.sin(a), math.cos(a), 0))
        w = rng.uniform(0.03, 0.045) if lod == 0 else 0.085
        root = d * rng.uniform(0.02, 0.11)
        mid = root + d * lean * 0.35 * h + UP * h * 0.55
        tip = root + d * lean * h + UP * h
        if lod == 0:
            verts = [root - side * w, root + side * w, mid + side * w * 0.7, mid - side * w * 0.7, tip]
            faces = [[0, 1, 2, 3], [3, 2, 4]]
        else:
            verts = [root - side * w, root + side * w, tip + side * w * 0.25, tip - side * w * 0.25]
            faces = [[0, 1, 2, 3]]
        bm = bm_from(verts, faces)
        C.orient(bm, lambda f, d=d: d + UP * 0.2)
        tint = mix(tip_c, green, rng.uniform(0, 0.45))

        def cfn(l, f, h=h, tint=tint):
            return ramp([(0, base_c), (0.4, mid_c), (1, tint)], l.vert.co.z / h)

        mb.add(bm, mat='VC_2S', color_fn=cfn,
               normal_fn=lambda l, f, d=d: (d * 0.45 + UP).normalized(), jitter=0.05)
    return mb


# ------------------------------------------------------------------ main
BUDGET = {'pine_tall_a': 1400, 'pine_tall_b': 1400, 'pine_mid': 1000, 'pine_young': 500,
          'aspen_gold': 1200, 'snag': 300, 'bush_a': 300, 'bush_b': 300, 'fern': 200, 'grass_tuft': 60}


def builder(name):
    if name.startswith('pine'):
        return lambda lod: build_pine(name, lod)
    return {'aspen_gold': build_aspen, 'snag': build_snag, 'bush_a': build_bush_a, 'bush_b': build_bush_b,
            'fern': build_fern, 'grass_tuft': build_grass}[name]


def main():
    C.reset_scene()
    mats = {'VC': C.mat_vc('VC'), 'VC_2S': C.mat_vc('VC_2S', double_sided=True)}
    col0, col1 = C.collection('Vegetation_LOD0'), C.collection('Vegetation_LOD1')
    objs, stats = {}, {}
    for name in BUDGET:
        for lod in (0, 1):
            mb = builder(name)(lod)
            nm = name + ('_lod1' if lod else '')
            stats[nm] = mb.tris()
            ob = mb.build(mats, vcolor=True, collection_obj=col1 if lod else col0)
            objs[nm] = ob
            C.export_glb([ob], nm + '.glb', vcolor=True)
        r = stats[name + '_lod1'] / stats[name]
        flag = '' if stats[name] <= BUDGET[name] and 1 / 6.05 <= r <= 1 / 3.95 else '  <-- CHECK'
        print('VEG %-12s lod0 %5d (<=%d)  lod1 %4d  ratio 1/%.2f%s' % (name, stats[name], BUDGET[name],
              stats[name + '_lod1'], 1 / r, flag))

    # ---- previews
    C.setup_render()
    C.add_sun((50, 0, 150), 4.0)
    C.add_ground(0.0, color='#7C7457')
    trees = ['pine_tall_a', 'pine_tall_b', 'pine_mid', 'pine_young', 'aspen_gold', 'snag']
    small = ['bush_a', 'bush_b', 'fern', 'grass_tuft']
    for o in objs.values():
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

    shot(trees, 'vegetation_trees.png', 1.5)
    shot([n + '_lod1' for n in trees], 'vegetation_trees_lod1.png', 1.5)
    shot(small + [n + '_lod1' for n in small], 'vegetation_small.png', 0.35, el=22)
    # close-up of a tall pine crown (LOD0) to judge the tiers
    shot(['pine_tall_a', 'pine_mid'], 'vegetation_pine_closeup.png', 0.5, az=35, el=6, lens=70)
    for o in objs.values():
        o.location = (0, 0, 0)
        o.hide_render = False
    col1.hide_viewport = True
    C.save_blend('vegetation.blend')
    return stats


if __name__ == '__main__':
    main()
