"""Forest Trail rocks and ground clutter: boulders, slab, post, pebbles, log, stump.

Run: blender --background --python rocks.py
Faceted (flat shaded) convex-hull rocks, grey #6F706A..#8A8B83 with moss (#7D8D53) on
upward faces. Origin = base centre; boulders are sunk into the ground by ~0.25 m.
"""
import bpy, bmesh, math, os, random, sys
from mathutils import Vector, Matrix, Euler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
from common import hexc, mix, ramp, smoothstep, bm_hull, bm_lathe, bm_cyl_between, bm_from, xform, mat_trs

UP = Vector((0, 0, 1))
GREY_D, GREY_L = hexc('#6F706A'), hexc('#8A8B83')
MOSS, MOSS_D = hexc('#7D8D53'), hexc('#49694B')
DIRT = hexc('#51483D')
BARK_D, BARK = hexc('#3F3731'), hexc('#5E4A38')
WOOD, WOOD_L = hexc('#8C6440'), hexc('#C39A68')


def rock_points(rng, n, size, bottom=-0.55, top=0.9, flat_side=None, noise=0.18):
    sx, sy, sz = size
    pts = []
    for _ in range(n):
        d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
        k = 1 + rng.uniform(-noise, noise)
        p = Vector((d.x * sx / 2 * k, d.y * sy / 2 * k, d.z * sz / 2 * k))
        p.z = max(p.z, bottom * sz / 2)
        p.z = min(p.z, top * sz / 2 + rng.uniform(-0.03, 0.03) * sz)
        if flat_side is not None:
            ax, lim = flat_side
            setattr(p, ax, max(getattr(p, ax), lim))
        pts.append(p)
    return pts


def hull_rock(rng, pts, dissolve=6.0, rough=0.0):
    """Convex hull, optionally subdivided once and dented with noise (gives concave facets)."""
    bm = bm_hull(pts)
    if rough:
        from mathutils import noise
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
        size = max((v.co.length for v in bm.verts), default=1.0)
        off = Vector((rng.uniform(0, 50), rng.uniform(0, 50), rng.uniform(0, 50)))
        bm.normal_update()
        for v in bm.verts:
            q = v.co / size * 2.2 + off
            n = noise.noise(q) * 0.7 + noise.noise(q * 2.3) * 0.3
            v.co += v.normal * n * rough * size
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(dissolve), use_dissolve_boundaries=False,
                             verts=bm.verts[:], edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def sink(bm, depth):
    zmin = min(v.co.z for v in bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, -zmin - depth), verts=bm.verts)
    return bm


def rock_color_fn(rng, zmax, moss_amt=1.0, moss_thr=(0.55, 0.9)):
    from mathutils import noise
    cache = {}
    off = Vector((rng.uniform(0, 40), rng.uniform(0, 40), 0))

    def fn(l, f):
        if f.index not in cache:
            nz = f.normal.z
            c = f.calc_center_median()
            h = max(0.0, c.z) / max(zmax, 1e-3)
            g = mix(GREY_D, GREY_L, 0.25 + 0.55 * h + rng.uniform(-0.25, 0.25))
            patch = smoothstep(-0.25, 0.25, noise.noise(c * 1.1 + off))
            m = smoothstep(moss_thr[0], moss_thr[1], nz) * moss_amt * rng.uniform(0.55, 1.0) * patch
            moss = mix(MOSS_D, MOSS, rng.uniform(0.45, 1.0))
            col = mix(g, moss, m)
            if c.z < 0.08:                        # dirt contact near the ground line
                col = mix(col, DIRT, 0.45 * (1 - max(0.0, c.z + 0.2) / 0.28))
            cache[f.index] = col
        return cache[f.index]
    return fn


def build_boulder(name, seed, size, n=34, sink_d=0.25, dissolve=4.0, top=0.85, moss=1.0, rough=0.09):
    rng = random.Random(seed)
    mb = C.MeshBuilder(name, seed=seed)
    bm = sink(hull_rock(rng, rock_points(rng, n, size, top=top), dissolve, rough), sink_d)
    zmax = max(v.co.z for v in bm.verts)
    mb.add(bm, color_fn=rock_color_fn(rng, zmax, moss), shade='flat', jitter=0.03)
    return mb


def build_slab():
    """2.4 x 1.6 x 0.5 flat rock step. Bottom at z=0, top ~0.5."""
    rng = random.Random(77)
    mb = C.MeshBuilder('rock_slab', seed=77)
    pts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (0, 1):
                top = 0.5 - rng.uniform(0.0, 0.07) if sz else 0.0
                c = Vector((sx * 1.2, sy * 0.8, top))
                ins = (rng.uniform(0.08, 0.3), rng.uniform(0.06, 0.22), rng.uniform(0.06, 0.16))
                for k in range(3):
                    p = c.copy()
                    p[k] -= (sx, sy, 1 if sz else -1)[k] * ins[k]
                    pts.append(p)
    for _ in range(8):                          # a few extra points on the sides for irregularity
        a = rng.uniform(0, 6.283)
        pts.append(Vector((1.17 * math.cos(a), 0.77 * math.sin(a), rng.uniform(0.12, 0.4))))
    pts.append(Vector((rng.uniform(-0.5, 0.5), rng.uniform(-0.3, 0.3), 0.5)))
    bm = hull_rock(rng, pts, 3.0, 0.025)
    zmin = min(v.co.z for v in bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, -zmin), verts=bm.verts)
    mb.add(bm, color_fn=rock_color_fn(rng, 0.5, 0.7, (0.75, 0.97)), shade='flat', jitter=0.03)
    return mb


def build_post():
    """Upright rock post (winch anchor): ~1.6 m above ground, ~0.8 m diameter, sunk 0.2 m."""
    rng = random.Random(88)
    mb = C.MeshBuilder('rock_post', seed=88)
    pts = []
    for ring in range(6):
        z = -0.2 + 1.8 * ring / 5
        r = 0.40 * (1.0 - 0.28 * (ring / 5) ** 1.5)
        for k in range(6):
            a = k * math.pi / 3 + ring * 0.5 + rng.uniform(-0.25, 0.25)
            rr = r * rng.uniform(0.85, 1.05)
            zz = z if ring < 5 else z - rng.uniform(0.0, 0.18) - (0.12 * k % 2)
            pts.append(Vector((rr * math.cos(a), rr * math.sin(a) * 0.92, zz)))
    pts.append(Vector((0.05, 0.02, 1.62)))
    bm = hull_rock(rng, pts, 4.0, 0.05)
    mb.add(bm, color_fn=rock_color_fn(rng, 1.6, 0.9, (0.5, 0.85)), shade='flat', jitter=0.04)
    return mb


def build_pebbles():
    rng = random.Random(99)
    mb = C.MeshBuilder('pebbles', seed=99)
    for i in range(13):
        a, d = rng.uniform(0, 6.283), 0.9 * math.sqrt(rng.random())
        s = rng.uniform(0.10, 0.34) * (1.25 if i < 3 else 1.0)
        size = (s * rng.uniform(1.0, 1.5), s * rng.uniform(0.8, 1.2), s * rng.uniform(0.5, 0.8))
        pts = rock_points(rng, 11, size, bottom=-0.5, top=0.9, noise=0.25)
        bm = hull_rock(rng, pts, 8.0)
        sink(bm, size[2] * 0.3)
        xform(bm, mat_trs((d * math.cos(a), d * math.sin(a), 0), (0, 0, rng.uniform(0, 6.283))))
        mb.add(bm, color_fn=rock_color_fn(rng, 0.3, 0.5), shade='flat', jitter=0.08)
    return mb


# ------------------------------------------------------------------ wood
def bark_fn(rng, zlo, zhi, moss_top=0.0):
    cache = {}

    def fn(l, f):
        if f.index not in cache:
            c = f.calc_center_median()
            col = mix(BARK_D, BARK, rng.uniform(0.0, 1.0) * 0.8 + 0.2 * (c.z - zlo) / max(1e-3, zhi - zlo))
            if moss_top and f.normal.z > 0.6 and rng.random() < 0.45:
                col = mix(col, mix(MOSS_D, MOSS, rng.random()), moss_top * rng.uniform(0.5, 1.0))
            cache[f.index] = col
        return cache[f.index]
    return fn


def end_grain(mb, center, axis_dir, r, segs, rng, phase=0.0):
    """Cut end: a disc with bark rim, sapwood ring and darker heart (face fan)."""
    d = Vector(axis_dir).normalized()
    M = Matrix.Translation(center) @ C.align_z(d)
    for r_in, r_out, col in ((0.0, 0.34, mix(WOOD, BARK_D, 0.35)), (0.34, 0.86, WOOD_L), (0.86, 1.0, BARK)):
        verts, faces = [], []
        for i in range(segs):
            a = phase + 2 * math.pi * i / segs
            verts.append((r * r_out * math.cos(a), r * r_out * math.sin(a), 0.0))
        if r_in == 0:
            faces = [list(range(segs))]
        else:
            for i in range(segs):
                a = phase + 2 * math.pi * i / segs
                verts.append((r * r_in * math.cos(a), r * r_in * math.sin(a), 0.0))
            faces = [[i, (i + 1) % segs, segs + (i + 1) % segs, segs + i] for i in range(segs)]
        bm = xform(bm_from(verts, faces), M)
        C.orient(bm, lambda f: d)
        mb.add(bm, color=col, shade='flat', jitter=0.04)


def build_log():
    """Fallen log along X, 6 m long, 0.5 m diameter, resting on the ground (origin = base centre)."""
    rng = random.Random(123)
    mb = C.MeshBuilder('log', seed=123)
    segs, r, L = 10, 0.25, 6.0
    prof = []
    for k in range(7):
        x = -L / 2 + L * k / 6
        rr = r * (1.06 - 0.12 * k / 6) * rng.uniform(0.97, 1.03)
        prof.append((rr, x))
    bm = bm_lathe(prof, segs, 'X', phase=0.3)
    for v in bm.verts:                     # slight sag and bark irregularity
        v.co.z += 0.03 * math.sin(v.co.x * 0.9) + rng.uniform(-0.012, 0.012)
        v.co.y += rng.uniform(-0.012, 0.012)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.translate(bm, vec=(0, 0, r - 0.03), verts=bm.verts)
    mb.add(bm, color_fn=bark_fn(rng, 0, 2 * r, 0.6), shade='auto', angle=40, jitter=0.04)
    end_grain(mb, Vector((-L / 2, 0, r - 0.03)), (-1, 0, 0), r * 1.06, segs, rng, 0.3)
    end_grain(mb, Vector((L / 2, 0, r - 0.03 + 0.03 * math.sin(2.7))), (1, 0, 0), r * 0.94, segs, rng, 0.3)
    for x, a, ln in ((-1.4, 1.1, 0.55), (0.6, -0.9, 0.4), (1.9, 2.0, 0.35), (-0.3, 2.6, 0.3)):
        base = Vector((x, math.cos(a) * r * 0.7, r + math.sin(a) * r * 0.7))
        d = Vector((0.35, math.cos(a), math.sin(a))).normalized()
        mb.add(bm_cyl_between(base, base + d * ln, 0.055, segs=5, r2=0.03), color=BARK, shade='smooth')
    return mb


def build_stump():
    rng = random.Random(321)
    mb = C.MeshBuilder('stump', seed=321)
    segs, r, H = 12, 0.42, 0.62
    prof = [(r * 1.18, 0.0), (r * 1.04, 0.12), (r, 0.3), (r * 0.98, H)]
    bm = bm_lathe(prof, segs, 'Z', phase=0.1)
    top = [v for v in bm.verts if abs(v.co.z - H) < 1e-5]
    for v in top:                          # slanted saw cut
        v.co.z += 0.05 * v.co.x / r
    bmesh.ops.translate(bm, vec=(0, 0, -0.05), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mb.add(bm, color_fn=bark_fn(rng, 0, H), shade='auto', angle=40, jitter=0.05)
    n = Vector((-0.05 / r, 0, 1)).normalized()
    end_grain(mb, Vector((0, 0, H - 0.05 + 0.001)), n, r * 0.98, segs, rng, 0.1)
    # roots
    for k in range(6):
        a = k * math.pi / 3 + rng.uniform(-0.2, 0.2)
        d = Vector((math.cos(a), math.sin(a), 0))
        p0 = d * r * 0.7 + Vector((0, 0, 0.26))
        p1 = d * (r + rng.uniform(0.35, 0.6)) + Vector((0, 0, -0.08))
        mb.add(bm_cyl_between(p0, p1, 0.13, segs=5, r2=0.04), color_fn=bark_fn(rng, 0, H), shade='smooth')
    return mb


# ------------------------------------------------------------------ main
def main():
    C.reset_scene()
    mats = {'VC': C.mat_vc('VC')}
    col = C.collection('Rocks')
    builders = [
        ('rock_a', lambda: build_boulder('rock_a', 1, (2.5, 2.0, 1.75), 38, 0.3)),
        ('rock_b', lambda: build_boulder('rock_b', 2, (1.8, 1.45, 1.5), 30, 0.25, top=0.75)),
        ('rock_c', lambda: build_boulder('rock_c', 3, (1.45, 1.2, 0.95), 26, 0.2, top=0.7)),
        ('rock_slab', build_slab), ('rock_post', build_post), ('pebbles', build_pebbles),
        ('log', build_log), ('stump', build_stump),
    ]
    objs, stats = [], {}
    for name, fn in builders:
        mb = fn()
        stats[name] = mb.tris()
        ob = mb.build(mats, vcolor=True, collection_obj=col)
        objs.append(ob)
        C.export_glb([ob], name + '.glb', vcolor=True)
    print('ROCKS TRIS', stats)
    C.setup_render()
    C.add_sun((50, 0, 150), 4.0)
    C.add_ground(0.0, color='#7C7457')
    rocks, wood = objs[:6], objs[6:]
    C.lineup(rocks, 0.8, y=0.0)
    C.lineup(wood, 1.2, y=4.0)
    for o in wood:
        o.location.x -= 1.0
    C.frame_camera(objs, az=15, el=24, lens=50)
    C.render('rocks_lineup.png')
    close = objs[:3]
    for o in objs[3:]:
        o.hide_render = True
    C.frame_camera(close, az=30, el=22, lens=60)
    C.render('rocks_closeup.png')
    for o in objs:
        o.location = (0, 0, 0)
        o.hide_render = False
    C.save_blend('rocks.blend')
    return stats


if __name__ == '__main__':
    main()
