"""Forest Trail props: cabin, lookout, tent, campfire, bench_log, picnic_table, signpost,
toolbox, shed, dock, fence, bridge_plank.

Run: blender --background --python props.py
All props use the vertex-colour material "VC"; origin = base centre on the ground (Z=0).
Buildings live in props_buildings.py.
"""
import bpy, bmesh, math, os, random, sys
from mathutils import Vector, Matrix, Euler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
from common import hexc, mix, bm_box, bm_cyl_between, bm_lathe, bm_from, xform, mat_trs
from props_lib import (Kit, UP, WOOD_D, WOOD_L, WOOD_DARK, WOOD_GREY, ROOF_D, ROOF_RED, WINDOW,
                       STONE_D, STONE_L, METAL, DARK)
import props_buildings as PB

CANVAS_O, CANVAS_O2 = hexc('#C8642E'), hexc('#A94F26')
CANVAS_G = hexc('#2F4A3A')


# ------------------------------------------------------------------ tent
def build_tent():
    """A-frame tent: 2.4 m long (Y, door toward +Y), 1.9 m wide, 1.35 m tall."""
    k = Kit('tent', 201)
    L, W, H = 2.4, 1.9, 1.35
    # fly sheet: two sloped panels with thickness, slight sag in the middle
    for s in (-1, 1):
        verts, faces = [], []
        nx = 5
        for i in range(nx + 1):
            y = -L / 2 + L * i / nx
            sag = 0.06 * math.sin(math.pi * i / nx)
            for t in (0.0, 1.0):              # t=0 ridge, t=1 hem
                x = s * (W / 2 + 0.06) * t
                z = H - (H - 0.05) * t - sag * (1 - t) * 0.9
                x -= s * sag * 0.4 * math.sin(math.pi * t)
                verts.append((x, y, z))
        for i in range(nx):
            a = 2 * i
            faces.append([a, a + 2, a + 3, a + 1] if s > 0 else [a, a + 1, a + 3, a + 2])
        bm = bm_from(verts, faces)
        bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.03)
        C.orient(bm, lambda f, s=s: Vector((s, 0, 0.6)) if abs(f.normal.y) < 0.9 else f.normal)
        k.mb.add(bm, color_fn=lambda l, f: mix(CANVAS_O, CANVAS_O2, 0.0 if f.normal.z > 0 else 0.7),
                 shade='auto', angle=30, jitter=0.02)
    # green inner tent walls (ends) with an open door at +Y
    tri = [(-W / 2 + 0.08, 0.02), (W / 2 - 0.08, 0.02), (0.0, H - 0.08)]
    k.poly(tri, 0.04, 'Y', -L / 2 + 0.1, CANVAS_G)
    door_side = [(-W / 2 + 0.08, 0.02), (-0.12, 0.02), (0.0, H - 0.08)]
    k.poly(door_side, 0.04, 'Y', L / 2 - 0.1, CANVAS_G)
    k.poly([(0.12, 0.02), (W / 2 - 0.08, 0.02), (0.0, H - 0.08)], 0.04, 'Y', L / 2 - 0.1, CANVAS_G)
    k.poly([(-0.5, 0.02), (0.5, 0.02), (0.0, H - 0.12)], 0.02, 'Y', L / 2 - 0.3, DARK, jitter=0.0)
    # rolled-up door flap, floor, ridge pole ends, stakes and guy lines
    k.log((-0.35, L / 2 - 0.05, 0.75), (-0.12, L / 2 - 0.05, 1.2), 0.05, CANVAS_O2, segs=5)
    k.box((-W / 2 + 0.05, -L / 2 + 0.05, 0.0), (W / 2 - 0.05, L / 2 - 0.08, 0.03), CANVAS_G)
    for y in (-L / 2 - 0.12, L / 2 + 0.12):
        k.log((0, y, 0.0), (0, y, H + 0.12), 0.018, METAL, segs=4)
        yy = y + (0.9 if y > 0 else -0.9)
        k.log((0, y, H + 0.05), (0, yy, 0.0), 0.006, hexc('#D8D0B8'), segs=3, cap=False)
        k.log((0, yy, 0.12), (0, yy, -0.05), 0.015, METAL, segs=4)
    for s in (-1, 1):
        for y in (-L / 2 + 0.15, L / 2 - 0.15):
            k.log((s * (W / 2 + 0.12), y, 0.1), (s * (W / 2 + 0.12), y, -0.05), 0.015, METAL, segs=4)
    return k


# ------------------------------------------------------------------ campfire
def build_campfire():
    k = Kit('campfire', 202)
    n = 10
    for i in range(n):
        a = 2 * math.pi * i / n + k.rng.uniform(-0.1, 0.1)
        r = 0.62
        s = k.rng.uniform(0.2, 0.3)
        k.rock((r * math.cos(a), r * math.sin(a), 0), (s * 1.3, s, s * 0.85), 10, 0.25)
    ash = bm_lathe([(0.5, 0.0), (0.42, 0.035), (0, 0.05)], 10, 'Z')
    k.mb.add(ash, color=hexc('#3A3632'), shade='smooth', jitter=0.1)
    # charred ends near the centre, teepee of split wood
    for i in range(5):
        a = 2 * math.pi * i / 5 + 0.3
        p0 = Vector((0.42 * math.cos(a), 0.42 * math.sin(a), 0.04))
        p1 = Vector((0.04 * math.cos(a), 0.04 * math.sin(a), 0.55))
        k.log(p0, p1, 0.05, k.wood(0.3), segs=5, r2=0.035)
        k.log(p1 * 0.6 + p0 * 0.4 + Vector((0, 0, -0.02)), p1, 0.052, hexc('#221E1B'), segs=5, r2=0.036)
    for i in range(4):
        a = 2 * math.pi * i / 4 + 0.8
        k.box((math.cos(a) * 0.15 - 0.05, math.sin(a) * 0.15 - 0.05, 0.03),
              (math.cos(a) * 0.15 + 0.05, math.sin(a) * 0.15 + 0.05, 0.09), hexc('#4A2A1C'), jitter=0.2)
    # a small stack of spare firewood beside the ring
    for j, (x, z) in enumerate(((1.05, 0.07), (1.2, 0.07), (1.35, 0.07), (1.12, 0.19), (1.28, 0.19))):
        k.log((x, -0.35, z), (x, 0.35, z), 0.07, k.wood(), segs=6)
    return k


# ------------------------------------------------------------------ bench, table, sign, toolbox, fence
def build_bench_log():
    """Half-log seat on two log blocks, 1.9 m along X, seat top ~0.46 m."""
    k = Kit('bench_log', 203)
    L, r = 1.9, 0.2
    half = [(r * math.cos(a), r * math.sin(a)) for a in (math.pi + math.pi * i / 8 for i in range(9))]
    seat = C.bm_extrude_poly(half, L, 'X', 0.0)
    xform(seat, Matrix.Translation((0, 0, 0.46)))
    bark, cut = k.wood(0.1), mix(WOOD_L, hexc('#B89163'), 0.6)
    k.mb.add(seat, color_fn=lambda l, f: cut if f.normal.z > 0.9 or abs(f.normal.x) > 0.9 else bark,
             shade='auto', angle=30, jitter=0.04)
    for x in (-0.6, 0.6):
        k.log((x, 0, 0.0), (x, 0, 0.29), 0.17, k.wood(0.25), segs=8)
    return k


def build_picnic_table():
    """Classic table: 1.8 m long (X), top at 0.76 m, benches both sides."""
    k = Kit('picnic_table', 204)
    L = 1.8
    k.planks_x(-L / 2, L / 2, -0.4, 0.4, 0.72, 0.76, 5)
    for s in (-1, 1):
        k.planks_x(-L / 2, L / 2, s * 0.58 - 0.15, s * 0.58 + 0.15, 0.42, 0.46, 2)
    for x in (-0.62, 0.62):
        for s in (-1, 1):
            k.beam((x, s * 0.72, 0.0), (x, s * 0.08, 0.72), 0.09, 0.05, k.wood(0.2))
        k.beam((x, -0.76, 0.38), (x, 0.76, 0.38), 0.09, 0.06, k.wood(0.2))
        k.box((x - 0.045, -0.36, 0.66), (x + 0.045, 0.36, 0.72), k.wood(0.2))
    k.beam((-0.62, 0, 0.38), (0.0, 0, 0.7), 0.06, 0.05, k.wood(0.3))
    k.beam((0.62, 0, 0.38), (0.0, 0, 0.7), 0.06, 0.05, k.wood(0.3))
    return k


def build_signpost():
    """Square post (2.3 m) with two arrow boards at different headings."""
    k = Kit('signpost', 205)
    k.post(0, 0, 0.0, 2.3, 0.13, k.wood(0.2))
    k.cbox((0.19, 0.19, 0.05), (0, 0, 2.32), WOOD_DARK, rot=(0, 0, math.pi / 4))
    boards = ((1.85, 0.25, 1), (1.45, -0.9, -1))
    for z, yaw, dirn in boards:
        L, h = 1.0, 0.24
        pts = [(0.08, -h / 2), (L - 0.16, -h / 2), (L, 0.0), (L - 0.16, h / 2), (0.08, h / 2)]
        if dirn < 0:
            pts = [(-x, y) for x, y in reversed(pts)]
        R = Matrix.Rotation(yaw, 4, 'Z')
        M = Matrix.Translation((0, 0, z)) @ R
        k.poly(pts, 0.04, 'Y', 0.09, mix(WOOD_L, hexc('#B08556'), 0.5), M=M)
        # carved "lettering" as dark strokes on both faces
        for side in (-1, 1):
            for i in range(4):
                x0 = 0.18 + i * 0.16
                xs = (x0, x0 + 0.11) if dirn > 0 else (-x0 - 0.11, -x0)
                bm = bm_box((xs[1] - xs[0], 0.006, 0.09), ((xs[0] + xs[1]) / 2, 0.09 + side * 0.021, 0))
                k.mb.add(xform(bm, M), color=WOOD_DARK, shade='flat')
    return k


def build_toolbox():
    """Red steel toolbox 0.7 (X) x 0.35 (Y) x 0.35 (Z) incl. handle."""
    k = Kit('toolbox', 206)
    red, red_d = hexc('#B8342A'), hexc('#8E2620')
    k.box((-0.35, -0.175, 0.0), (0.35, 0.175, 0.2), red, bev=0.012, jitter=0.0)
    k.box((-0.345, -0.172, 0.2), (0.345, 0.172, 0.21), DARK, jitter=0.0)
    k.box((-0.35, -0.175, 0.21), (0.35, 0.175, 0.29), red_d, bev=0.012, jitter=0.0)
    k.box((-0.33, -0.16, 0.0), (0.33, 0.16, 0.015), DARK, jitter=0.0)
    for x in (-0.22, 0.22):
        k.box((x - 0.03, -0.185, 0.17), (x + 0.03, -0.172, 0.24), METAL, jitter=0.0)
    # carry handle
    for x in (-0.2, 0.2):
        k.box((x - 0.02, -0.02, 0.29), (x + 0.02, 0.02, 0.33), METAL, jitter=0.0)
    k.log((-0.21, 0, 0.335), (0.21, 0, 0.335), 0.018, DARK, segs=6)
    return k


def build_fence():
    """3 m split-rail fence section along X (posts at -1.35, 0, +1.35), 1.1 m tall."""
    k = Kit('fence', 207)
    grey = lambda: mix(WOOD_GREY, WOOD_D, k.rng.uniform(0.0, 0.5))
    for x in (-1.35, 0.0, 1.35):
        k.post(x, 0, -0.1, 1.12 + k.rng.uniform(-0.03, 0.03), 0.13, grey())
        k.cbox((0.15, 0.15, 0.03), (x, 0, 1.14), grey(), rot=(0, 0, 0.1))
    for z in (0.45, 0.85):
        for x0, x1 in ((-1.5, 0.0), (0.0, 1.5)):
            k.log((x0, 0.09, z + k.rng.uniform(-0.02, 0.02)), (x1, 0.09, z + k.rng.uniform(-0.02, 0.02)),
                  0.055, grey(), segs=6)
    return k


# ------------------------------------------------------------------ main
BUILDERS = [
    ('cabin', PB.build_cabin), ('lookout', PB.build_lookout), ('shed', PB.build_shed),
    ('dock', PB.build_dock), ('bridge_plank', PB.build_bridge_plank),
    ('tent', build_tent), ('campfire', build_campfire), ('bench_log', build_bench_log),
    ('picnic_table', build_picnic_table), ('signpost', build_signpost), ('toolbox', build_toolbox),
    ('fence', build_fence),
]


def main():
    C.reset_scene()
    mats = {'VC': C.mat_vc('VC')}
    col = C.collection('Props')
    objs, stats = {}, {}
    for name, fn in BUILDERS:
        k = fn()
        stats[name] = k.mb.tris()
        ob = k.build(mats, col)
        objs[name] = ob
        C.export_glb([ob], name + '.glb', vcolor=True)
    print('PROPS TRIS', stats)

    C.setup_render()
    C.add_sun((50, 0, 150), 4.0)
    C.add_ground(0.0, color='#7C7457')
    for o in objs.values():
        o.hide_render = True

    def shot(names, fname, gap, az=20, el=14, lens=50, y=0.0):
        sel = [objs[n] for n in names]
        for o in sel:
            o.hide_render = False
        C.lineup(sel, gap, y)
        C.frame_camera(sel, az=az, el=el, lens=lens)
        C.render(fname)
        for o in sel:
            o.hide_render = True

    shot(['cabin', 'lookout'], 'props_buildings.png', 3.0, az=30, el=16)
    shot(['cabin'], 'props_cabin.png', 1.0, az=35, el=12)
    shot(['lookout'], 'props_lookout.png', 1.0, az=210, el=14)
    shot(['shed', 'dock', 'bridge_plank'], 'props_shed_dock_bridge.png', 2.0, az=25, el=24)
    shot(['tent', 'campfire', 'bench_log', 'toolbox'], 'props_small_a.png', 0.6, az=200, el=22)
    shot(['picnic_table', 'signpost', 'fence'], 'props_small_b.png', 0.6, az=200, el=16)
    for o in objs.values():
        o.location = (0, 0, 0)
        o.hide_render = False
    C.save_blend('props.blend')
    return stats


if __name__ == '__main__':
    main()
