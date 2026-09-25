"""Forest Trail props, second batch: aframe_cabin, boathouse, plank_bridge, camper, lantern,
lamp_post, string_pole, trail-park props (cone, flag_marker, tyre_stack, tyre_wall, gate_arch,
log_step, sign_board, barrier) and lake/camp clutter (rowboat, crate_stack, firewood, canoe_rack).

Run: blender --background --python props2.py
Conventions as props.py: one mesh per GLB, vertex colours (sRGB) in material 'VC', model
front +Y, origin at the base centre on the ground (Z=0) unless noted. Parts that light up at
night (window panes, bulbs, lantern glass) use a second vertex-colour material 'Glow'; the
game drives its emission. Writes art/props2-report.json (tris, bbox, collider suggestions).
"""
import bpy, bmesh, math, os, sys, json
from mathutils import Vector, Matrix, Euler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
from common import hexc, mix, bm_box, bm_box_mm, bm_cyl, bm_cyl_between, bm_lathe, bm_from, xform, mat_trs
from props_lib import (UP, WOOD_D, WOOD_L, WOOD_DARK, WOOD_GREY, ROOF_D, STONE_D, STONE_L, METAL, DARK)
from props_buildings import GlowKit as Kit, roof_slab, GLOW

RED, RED_D = hexc('#A8392B'), hexc('#7E2A21')
WHITE = hexc('#ECE7DA')
ROOF_GREY, ROOF_GREY_D = hexc('#6F6B66'), hexc('#4E4B48')
ORANGE = hexc('#E0762A')
RUBBER = hexc('#262523')
YELLOW, YELLOW_D = hexc('#E2B55A'), hexc('#B98B3A')
CREAM = hexc('#EFE6CF')
ROPE = hexc('#C9B690')

# collider suggestions per asset (half extents x, y, z and centre), filled by the builders
COLLIDERS = {}


def win(k, x0, x1, z0, z1, y, facing=1, frame=0.07, depth=0.08, fcol=WHITE, mull=True, glow=GLOW):
    """Window pane (Glow) with a proud frame on a wall plane at y, in the XZ plane."""
    f = facing
    k.box((x0, y - 0.01 * f, z0), (x1, y + 0.03 * f, z1), glow, jitter=0.02, mat='Glow')
    yo0, yo1 = sorted((y, y + depth * f))
    k.box((x0 - frame, yo0, z0 - frame), (x1 + frame, yo1, z0), fcol, jitter=0.0)
    k.box((x0 - frame, yo0, z1), (x1 + frame, yo1, z1 + frame), fcol, jitter=0.0)
    k.box((x0 - frame, yo0, z0), (x0, yo1, z1), fcol, jitter=0.0)
    k.box((x1, yo0, z0), (x1 + frame, yo1, z1), fcol, jitter=0.0)
    if mull:
        xm, zm = (x0 + x1) / 2, (z0 + z1) / 2
        k.box((xm - 0.022, yo0, z0), (xm + 0.022, yo1, z1), fcol, jitter=0.0)
        k.box((x0, yo0, zm - 0.022), (x1, yo1, zm + 0.022), fcol, jitter=0.0)


def text_bm(text, size, extrude=0.012):
    """Blender text -> bmesh lying in XY (facing +Z), centred on the origin."""
    cu = bpy.data.curves.new('txt_' + text, 'FONT')
    cu.body = text
    cu.size = size
    cu.extrude = extrude
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.resolution_u = 3
    ob = bpy.data.objects.new('txt_' + text, cu)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    return bm


def lathe_col(k, prof, segs, M, colfn, shade='auto', angle=40, mat='VC'):
    bm = bm_lathe(prof, segs, 'Z')
    C.orient(bm, lambda f: f.calc_center_median() * Vector((1, 1, 0)) + Vector((0, 0, 0.001)))
    xform(bm, M)
    k.mb.add(bm, color_fn=colfn, shade=shade, angle=angle, mat=mat, jitter=0.02)


# ------------------------------------------------------------------ A-frame cabin
def build_aframe_cabin():
    """Red A-frame cabin (steam-01): body 7 x 6.5 m, porch deck toward +Y, ridge ~8 m."""
    k = Kit('aframe_cabin', 401)
    Y0, Y1 = -4.6, 1.9          # enclosed body
    FL = 0.55
    EAVE_X, EAVE_Z, RIDGE = 3.55, 0.45, 8.0
    # stone plinth
    for i in range(7):
        ya, yb = Y0 + (Y1 - Y0) * i / 7, Y0 + (Y1 - Y0) * (i + 1) / 7
        k.box((-3.3, ya, 0.0), (3.3, yb, FL), k.stone(), jitter=0.03)
    # inner roof line (under side of the roof), walls stop just below it
    zin = lambda x: EAVE_Z + (EAVE_X - abs(x)) / EAVE_X * (RIDGE - 0.35 - EAVE_Z)
    # red gable walls, board and batten
    n = 12
    for yc, facing in ((Y1 - 0.08, 1), (Y0 + 0.08, -1)):
        for i in range(n):
            xa, xb = -3.3 + 6.6 * i / n, -3.3 + 6.6 * (i + 1) / n
            pts = [(xa, FL), (xb, FL), (xb, zin(xb) - 0.05)]
            if xa < 0 < xb:
                pts.append((0.0, zin(0) - 0.05))
            pts.append((xa, zin(xa) - 0.05))
            k.poly(pts, 0.16, 'Y', yc, mix(RED, RED_D, 0.15 + 0.3 * ((i * 5) % 3) / 2), jitter=0.02)
            if i:
                x = xa
                k.box((x - 0.035, yc + facing * 0.08 - 0.03, FL), (x + 0.035, yc + facing * 0.08 + 0.03, zin(x) - 0.1), RED_D)
        # white fascia boards following the roof edge
        for s in (-1, 1):
            k.beam((s * 3.45, yc + facing * 0.12, EAVE_Z + 0.2), (0, yc + facing * 0.12, RIDGE - 0.1), 0.2, 0.08, WHITE, jitter=0)
    # knee walls under the eaves (visible strip on the sides)
    for s in (-1, 1):
        k.box((min(s * 3.3, s * 3.16), Y0, FL), (max(s * 3.3, s * 3.16), Y1, 1.2), RED_D)
    # roof: two thick weathered slabs meeting at the ridge, overhang front and back
    ry0, ry1 = Y0 - 0.5, Y1 + 1.0
    for s in (-1, 1):
        lo_o, hi_o = (s * (EAVE_X + 0.25), EAVE_Z - 0.05), (0.0, RIDGE + 0.12)
        lo_i, hi_i = (s * EAVE_X, EAVE_Z - 0.28), (0.0, RIDGE - 0.35)
        if s < 0:
            roof_slab(k, lo_o, hi_o, lo_i, hi_i, ry0, ry1, ROOF_GREY, WOOD_D, ROOF_GREY_D)
        else:
            roof_slab(k, hi_o, lo_o, hi_i, lo_i, ry0, ry1, ROOF_GREY, WOOD_D, ROOF_GREY_D)
        # shingle courses: thin strips proud of the roof, light/dark alternation
        for j in range(1, 9):
            t = j / 9
            x = s * (EAVE_X + 0.25) * (1 - t)
            z = EAVE_Z - 0.05 + (RIDGE + 0.12 - EAVE_Z + 0.05) * t
            k.beam((x, ry0, z), (x, ry1, z), 0.1, 0.05, mix(ROOF_GREY, ROOF_GREY_D, (j % 2) * 0.6), jitter=0.04)
    k.beam((0, ry0, RIDGE + 0.1), (0, ry1, RIDGE + 0.1), 0.26, 0.16, ROOF_GREY_D)
    # front gable: door, flanking windows, big glazing, small top window
    yf = Y1
    k.box((-0.55, yf, FL), (0.55, yf + 0.06, 2.75), mix(RED_D, WOOD_DARK, 0.5))
    for x in (-0.55, 0.55):
        k.box((x - 0.07, yf, FL), (x + 0.07, yf + 0.1, 2.82), WHITE, jitter=0)
    k.box((-0.62, yf, 2.75), (0.62, yf + 0.1, 2.85), WHITE, jitter=0)
    win(k, -0.16, 0.16, 1.9, 2.45, yf + 0.06, 1, 0.04, 0.04, mull=False)
    k.box((0.38, yf + 0.06, 1.55), (0.45, yf + 0.12, 1.7), METAL)
    for xa, xb in ((-2.35, -1.25), (1.25, 2.35)):
        win(k, xa, xb, 1.35, 2.55, yf, 1)
    for xa, xb in ((-1.7, -0.62), (-0.52, 0.52), (0.62, 1.7)):
        win(k, xa, xb, 3.3, 4.9, yf, 1)
    win(k, -0.55, 0.55, 5.4, 6.5, yf, 1)
    k.box((0.8, yf + 0.02, 2.2), (0.98, yf + 0.2, 2.45), GLOW, jitter=0.0, mat='Glow')     # porch light
    # back gable windows
    win(k, -0.7, 0.7, 3.0, 4.2, Y0, -1)
    win(k, -2.1, -1.2, 1.4, 2.3, Y0, -1)
    # porch deck, railing, steps
    k.planks_x(-3.3, 3.3, Y1, Y1 + 2.1, FL - 0.1, FL, 9)
    for x in (-3.2, -1.1, 1.1, 3.2):
        k.post(x, Y1 + 2.0, 0.0, FL - 0.1, 0.18, k.wood(0.25))
    rz = FL
    k.railing([(-1.0, Y1 + 2.02), (-3.22, Y1 + 2.02), (-3.22, Y1 + 0.1)], rz, 0.95, 1.1, 0.09, (0.5, 0.95), WHITE)
    k.railing([(1.0, Y1 + 2.02), (3.22, Y1 + 2.02), (3.22, Y1 + 0.1)], rz, 0.95, 1.1, 0.09, (0.5, 0.95), WHITE)
    for i in range(3):
        z = FL - (i + 1) * FL / 3.3
        y = Y1 + 2.1 + (i + 0.5) * 0.3
        k.box((-0.95, y - 0.15, z - 0.06), (0.95, y + 0.15, z), k.wood(0.5))
    # stone chimney through the right roof slope
    cx, cy = 1.8, -2.8
    for i in range(14):
        z0, z1 = i * 0.48, (i + 1) * 0.48
        o = 0.03 * ((i * 7) % 3 - 1)
        k.box((cx - 0.45 + o, cy - 0.45, z0), (cx + 0.45 + o, cy + 0.45, z1), k.stone(), jitter=0.04)
    k.box((cx - 0.52, cy - 0.52, 6.72), (cx + 0.52, cy + 0.52, 6.85), STONE_D)
    k.box((cx - 0.2, cy - 0.2, 6.85), (cx + 0.2, cy + 0.2, 7.05), DARK)
    # firewood + bench on the porch, flower boxes under the front windows
    for i in range(4):
        z = FL + 0.12 + i * 0.2
        for j in range(4 - i):
            x = -2.9 + j * 0.22 + i * 0.11
            k.log((x, Y1 + 0.2, z), (x, Y1 + 0.75, z), 0.1, k.wood(0.2), segs=6)
    k.box((1.6, Y1 + 0.2, FL + 0.42), (2.9, Y1 + 0.6, FL + 0.5), k.wood(0.6))
    for x in (1.7, 2.8):
        k.box((x - 0.05, Y1 + 0.25, FL), (x + 0.05, Y1 + 0.55, FL + 0.42), WOOD_DARK)
    for xa, xb in ((-2.4, -1.2), (1.2, 2.4)):
        k.box((xa, yf + 0.05, 1.05), (xb, yf + 0.3, 1.25), WHITE, jitter=0)
        for i in range(5):
            x = xa + 0.12 + i * (xb - xa - 0.24) / 4
            k.box((x - 0.07, yf + 0.1, 1.25), (x + 0.07, yf + 0.25, 1.38), (hexc('#C64E3E'), hexc('#E7C24E'), hexc('#6E8B4A'))[i % 3])
    COLLIDERS['aframe_cabin'] = {'half': [3.4, 3.6, 3.3], 'center': [0, 3.6, (Y0 + Y1) / 2],
                                 'note': 'box over the enclosed body; porch deck (y %.1f..%.1f, top z %.2f) is walkable' % (Y1, Y1 + 2.1, FL)}
    return k


# ------------------------------------------------------------------ boathouse
def build_boathouse():
    """Pier + stilt boathouse (steam-09). Origin = shore end of the deck, deck top z=0,
    pier 3 m wide along +Y to y=16, platform 7 x 7 m (y 16..23) with a 4 x 5 m hut."""
    k = Kit('boathouse', 402)
    PW = 1.5
    k.planks_x(-PW, PW, 0.0, 16.0, -0.1, 0.0, 44)
    k.planks_x(-3.5, 3.5, 16.0, 23.0, -0.1, 0.0, 20)
    # stringers + piles
    for x in (-PW + 0.15, PW - 0.15):
        k.box((x - 0.1, 0.0, -0.32), (x + 0.1, 16.0, -0.1), WOOD_DARK)
    for y in (0.4, 3.5, 6.6, 9.7, 12.8, 15.8):
        for x in (-PW + 0.15, PW - 0.15):
            k.log((x, y, -4.0), (x, y, -0.05), 0.12, k.wood(0.15), segs=6)
        k.box((-PW, y - 0.1, -0.34), (PW, y + 0.1, -0.12), WOOD_DARK)
    for y in (16.3, 19.6, 22.7):
        for x in (-3.3, 0.0, 3.3):
            k.log((x, y, -4.0), (x, y, -0.05), 0.14, k.wood(0.15), segs=6)
        k.box((-3.5, y - 0.1, -0.34), (3.5, y + 0.1, -0.12), WOOD_DARK)
    # low rail along the pier, railing round the platform
    for x in (-PW + 0.05, PW - 0.05):
        k.railing([(x, 0.6), (x, 16.0)], 0.0, 0.8, 3.1, 0.08, (0.55, 0.95))
    k.railing([(-PW, 16.05), (-3.45, 16.05), (-3.45, 22.95), (3.45, 22.95), (3.45, 16.05), (PW, 16.05)], 0.0, 0.9, 1.4, 0.09,
              (0.5, 0.95))
    # hut: orange-tan board walls, red side panel, pitched roof along Y, door toward the shore
    hx0, hx1, hy0, hy1, H = -2.0, 2.0, 17.3, 22.3, 2.5
    tan, tan_d = hexc('#D9A45C'), hexc('#B98246')
    for i in range(10):
        ya, yb = hy0 + (hy1 - hy0) * i / 10, hy0 + (hy1 - hy0) * (i + 1) / 10
        k.box((hx0, ya, 0.0), (hx0 + 0.12, yb, H), mix(tan, tan_d, (i % 2) * 0.5))
        k.box((hx1 - 0.12, ya, 0.0), (hx1, yb, H), mix(RED, RED_D, (i % 2) * 0.5))
    for yc, f in ((hy0 + 0.06, -1), (hy1 - 0.06, 1)):
        k.poly([(hx0, 0.0), (hx1, 0.0), (hx1, H), (0.0, H + 1.2), (hx0, H)], 0.12, 'Y', yc, tan)
    roof_slab(k, (hx0 - 0.4, H - 0.2), (0.0, H + 1.45), (hx0 - 0.4, H - 0.36), (0.0, H + 1.25), hy0 - 0.4, hy1 + 0.4,
              ROOF_D, WOOD_D, WOOD_DARK)
    roof_slab(k, (0.0, H + 1.45), (hx1 + 0.4, H - 0.2), (0.0, H + 1.25), (hx1 + 0.4, H - 0.36), hy0 - 0.4, hy1 + 0.4,
              ROOF_D, WOOD_D, WOOD_DARK)
    k.box((-0.5, hy0 - 0.02, 0.0), (0.5, hy0 + 0.02, 2.0), WOOD_DARK)
    win(k, 1.0, 1.6, 1.1, 1.8, hy0, -1, 0.06, 0.06, WOOD_DARK)
    win(k, -0.4, 0.4, 1.0, 1.7, hy1, 1, 0.06, 0.06, WOOD_DARK)
    for y0 in (18.2, 20.4):
        k.box((hx0 - 0.03, y0, 1.1), (hx0 + 0.02, y0 + 0.9, 1.8), GLOW, jitter=0.0, mat='Glow')
        k.box((hx0 - 0.08, y0 - 0.06, 1.04), (hx0 - 0.02, y0 + 0.96, 1.86), WOOD_DARK)
    # life ring on the shore-side wall
    ring = bm_lathe([(0.26 + 0.07 * math.cos(a), 0.07 * math.sin(a)) for a in [i * math.pi / 3 for i in range(7)]], 12, 'Y')
    xform(ring, Matrix.Translation((-1.2, hy0 - 0.12, 1.4)))
    k.mb.add(ring, color_fn=lambda l, f: WHITE if (int((math.atan2(l.vert.co.z - 1.4, l.vert.co.x + 1.2) + 4) / 0.785) % 2) else hexc('#D5452E'),
             shade='smooth')
    # lamp posts
    for x, y in ((-PW + 0.1, 5.0), (PW - 0.1, 12.5)):
        k.post(x, y, 0.0, 2.6, 0.12, k.wood(0.2))
        ax = x + (0.45 if x < 0 else -0.45)
        k.beam((x, y, 2.5), (ax, y, 2.5), 0.07, 0.07, k.wood(0.3))
        k.lamp(ax, y, 2.1, 0.1, 0.24)
    # coiled rope, bollards
    for x, y in ((-PW + 0.2, 15.6), (PW - 0.2, 15.6), (-3.2, 22.6), (3.2, 22.6)):
        k.log((x, y, 0.0), (x, y, 0.35), 0.1, WOOD_DARK, segs=6)
    COLLIDERS['boathouse'] = {'deck_pier': {'x': [-PW, PW], 'y': [0.0, 16.0], 'top': 0.0},
                              'deck_platform': {'x': [-3.5, 3.5], 'y': [16.0, 23.0], 'top': 0.0},
                              'hut': {'half': [2.0, 1.85, 2.5], 'center': [0, 1.85, 19.8]}}
    return k


# ------------------------------------------------------------------ plank bridge
BR_HALF, BR_SAG, BR_W = 13.0, 0.25, 3.6


def bridge_top(y):
    """Deck top height: 0 at both ends, sags 0.25 m in the middle (the game uses this formula)."""
    t = max(-1.0, min(1.0, y / BR_HALF))
    return -BR_SAG * (1 - t * t)


def build_plank_bridge():
    """26 m plank bridge along Y (steam-05). Deck top follows bridge_top(y)."""
    k = Kit('plank_bridge', 403)
    hw = BR_W / 2
    pitch = 0.33
    n = int(round(2 * BR_HALF / pitch))
    step = 2 * BR_HALF / n
    for i in range(n):
        y0 = -BR_HALF + i * step + 0.015
        y1 = -BR_HALF + (i + 1) * step - 0.015
        yc = (y0 + y1) / 2
        top = bridge_top(yc) - k.rng.uniform(0.0, 0.012)
        dx = k.rng.uniform(-0.06, 0.06)
        k.box((-hw + dx, y0, top - 0.08), (hw + dx, y1, top), mix(WOOD_GREY, WOOD_L, k.rng.uniform(0.0, 0.7)), jitter=0.05)
    # two runner beams following the sag (segments) + edge beams
    segs = 8
    for x in (-1.15, 1.15, -hw + 0.1, hw - 0.1):
        w = 0.24 if abs(x) < 1.5 else 0.14
        for j in range(segs):
            ya, yb = -BR_HALF + 2 * BR_HALF * j / segs, -BR_HALF + 2 * BR_HALF * (j + 1) / segs
            k.beam((x, ya, bridge_top(ya) - 0.2), (x, yb, bridge_top(yb) - 0.2), w, 0.24, WOOD_DARK, jitter=0.02)
    # rope railing: posts every 2.6 m, two sagging ropes between post tops
    posts = [(-BR_HALF + 0.3) + (2 * BR_HALF - 0.6) * i / 10 for i in range(11)]
    for sx in (-1, 1):
        x = sx * (hw + 0.08)
        for y in posts:
            z0 = bridge_top(y)
            k.log((x, y, z0 - 0.35), (x, y, z0 + 1.1), 0.07, k.wood(0.3), segs=5)
        for a, b in zip(posts, posts[1:]):
            for zr, sag in ((1.0, 0.18), (0.55, 0.1)):
                pa = Vector((x, a, bridge_top(a) + zr))
                pb = Vector((x, b, bridge_top(b) + zr))
                ns = 4
                pts = [pa.lerp(pb, i / ns) - Vector((0, 0, 4 * sag * (i / ns) * (1 - i / ns))) for i in range(ns + 1)]
                for q0, q1 in zip(pts, pts[1:]):
                    k.log(q0, q1, 0.022, ROPE, segs=3, cap=False)
    # log trestles
    for y in (-6.5, 0.0, 6.5):
        zt = bridge_top(y) - 0.32
        k.log((-2.0, y, zt), (2.0, y, zt), 0.16, k.wood(0.15), segs=7)
        for x in (-1.45, 1.45):
            k.log((x * 1.15, y, -6.3), (x, y, zt), 0.17, k.wood(0.2), segs=7)
        k.log((-1.6, y, -5.4), (1.45, y, zt - 0.3), 0.09, k.wood(0.4), segs=5)
        k.log((1.6, y, -5.4), (-1.45, y, zt - 0.3), 0.09, k.wood(0.4), segs=5)
        k.log((-1.62, y, -3.2), (1.62, y, -3.2), 0.09, k.wood(0.4), segs=5)
    # stone abutments under both ends
    for sy in (-1, 1):
        for i in range(3):
            for j in range(4):
                x = -2.1 + j * 1.4 + k.rng.uniform(-0.1, 0.1)
                y = sy * (12.2 + i * 0.9)
                z = -0.4 - 0.05 * i
                k.rock((x, y, z), (1.5, 1.1, 2.1), 8, 0.9)
    COLLIDERS['plank_bridge'] = {'deck': {'x': [-hw, hw], 'y': [-BR_HALF, BR_HALF],
                                          'top': 'z(y) = -0.25 * (1 - (y/13)^2)'},
                                 'rails': {'x': [-(hw + 0.08), hw + 0.08], 'height': 1.1}}
    return k


# ------------------------------------------------------------------ camper
def build_camper():
    """Vintage box camper trailer (steam-02): body 3.6 x 2.1 m, hitch toward +Y."""
    k = Kit('camper', 404)
    B0, B1 = -1.9, 1.7           # body along Y
    W = 1.05
    zb, zt = 0.5, 2.45
    # body: yellow upper, darker band below, rounded top edge
    k.mb.add(bm_box_mm((-W, B0, zb + 0.35), (W, B1, zt), 0.08, 2), color=YELLOW, shade='auto', angle=35, jitter=0.02)
    k.mb.add(bm_box_mm((-W - 0.01, B0 - 0.01, zb), (W + 0.01, B1 + 0.01, zb + 0.38), 0.03), color=YELLOW_D, shade='auto', jitter=0.02)
    k.box((-W - 0.015, B0, zb + 0.36), (W + 0.015, B1, zb + 0.42), CREAM, jitter=0)
    # side roll-up door (+X) with horizontal slats
    k.box((W, -1.2, zb + 0.3), (W + 0.03, 0.6, zt - 0.2), WHITE, jitter=0)
    for i in range(12):
        z = zb + 0.36 + i * 0.13
        k.box((W + 0.02, -1.18, z), (W + 0.045, 0.58, z + 0.02), hexc('#C9C4B8'), jitter=0)
    k.box((W + 0.03, -0.35, zb + 0.34), (W + 0.06, -0.25, zb + 0.4), METAL)
    # windows (Glow) front and left side, trim
    win(k, -0.5, 0.5, 1.45, 1.95, B1, 1, 0.06, 0.05, DARK, mull=False)
    for x0 in (-0.5,):
        pass
    k.box((-W - 0.04, -0.9, 1.3), (-W + 0.01, 0.3, 1.95), GLOW, jitter=0.0, mat='Glow')
    k.box((-W - 0.06, -0.96, 1.24), (-W - 0.01, 0.36, 1.3), DARK)
    k.box((-W - 0.06, -0.96, 1.95), (-W - 0.01, 0.36, 2.01), DARK)
    k.box((-W - 0.03, 0.7, zb + 0.35), (-W + 0.01, 1.4, 2.1), CREAM)          # entry door
    k.box((-W - 0.06, 1.25, 1.2), (-W - 0.02, 1.33, 1.3), METAL)
    # rolled awning on the door side + roof rack with a box
    k.log((W + 0.12, -1.7, zt - 0.1), (W + 0.12, 1.5, zt - 0.1), 0.1, hexc('#5E8C84'), segs=8)
    for y in (-1.6, -1.2, 1.4):
        k.box((W + 0.0, y - 0.03, zt - 0.2), (W + 0.12, y + 0.03, zt - 0.05), DARK)
    for x in (-0.9, 0.9):
        k.box((x - 0.03, B0 + 0.1, zt), (x + 0.03, B1 - 0.1, zt + 0.08), DARK)
    k.box((-0.7, -1.2, zt + 0.08), (0.6, 0.3, zt + 0.45), hexc('#3D4A45'), bev=0.03)
    k.box((-0.3, 0.6, zt), (0.3, 1.2, zt + 0.25), hexc('#D8D2C4'))            # roof vent
    # chassis, fenders, wheels, lights
    k.box((-0.8, B0 - 0.05, zb - 0.16), (0.8, B1 + 0.05, zb), DARK)
    for sx in (-1, 1):
        x = sx * (W + 0.02)
        whl = bm_cyl_between((x - sx * 0.25, -0.4, 0.34), (x, -0.4, 0.34), 0.34, segs=12)
        k.mb.add(whl, color=RUBBER, shade='auto', angle=40)
        hub = bm_cyl_between((x - sx * 0.0, -0.4, 0.34), (x + sx * 0.02, -0.4, 0.34), 0.16, segs=10)
        k.mb.add(hub, color=CREAM, shade='auto', angle=40)
        k.mb.add(bm_box_mm((min(x, x + sx * 0.12), -0.95, 0.66), (max(x, x + sx * 0.12), 0.15, 0.74), 0.02), color=DARK, shade='flat')
    for sx in (-1, 1):
        k.box((sx * 0.8 - 0.1, B0 - 0.04, zb + 0.1), (sx * 0.8 + 0.1, B0, zb + 0.24), hexc('#B8261B'), jitter=0)
    # A-frame tow hitch and jack stand toward +Y
    k.beam((-0.7, B1, zb - 0.1), (0, B1 + 1.1, zb - 0.12), 0.1, 0.1, DARK)
    k.beam((0.7, B1, zb - 0.1), (0, B1 + 1.1, zb - 0.12), 0.1, 0.1, DARK)
    k.box((-0.08, B1 + 1.05, zb - 0.2), (0.08, B1 + 1.3, zb - 0.05), METAL)
    k.log((0.25, B1 + 0.6, 0.0), (0.25, B1 + 0.6, zb - 0.05), 0.04, METAL, segs=6)
    k.box((0.17, B1 + 0.52, 0.0), (0.33, B1 + 0.68, 0.03), DARK)
    k.box((-0.3, B1 + 0.2, zb - 0.02), (0.3, B1 + 0.5, zb + 0.28), hexc('#6E8B8A'))  # propane box
    # stabiliser legs at the rear
    for sx in (-1, 1):
        k.beam((sx * 0.7, B0 + 0.2, zb - 0.1), (sx * 0.85, B0 + 0.2, 0.0), 0.05, 0.05, METAL)
    COLLIDERS['camper'] = {'half': [1.1, 1.25, 2.1], 'center': [0, 1.25, -0.1]}
    return k


# ------------------------------------------------------------------ lights
def build_lantern():
    k = Kit('lantern', 405)
    k.mb.add(bm_cyl(0.1, 0.11, 0.05, 10, base=True), color=DARK, shade='auto')
    k.mb.add(bm_cyl(0.075, 0.075, 0.17, 10, Matrix.Translation((0, 0, 0.05)), base=True), color=GLOW, shade='smooth', mat='Glow')
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4
        x, y = 0.085 * math.cos(a), 0.085 * math.sin(a)
        k.log((x, y, 0.05), (x, y, 0.22), 0.008, DARK, segs=4)
    k.mb.add(bm_cyl(0.1, 0.03, 0.07, 10, Matrix.Translation((0, 0, 0.22)), base=True), color=hexc('#2F4B3E'), shade='auto')
    for a, b in (((-0.07, 0, 0.27), (0, 0, 0.35)), ((0, 0, 0.35), (0.07, 0, 0.27))):
        k.log(a, b, 0.007, METAL, segs=3)
    return k


def build_lamp_post():
    """3 m wooden post with an arm and a hanging lantern (Glow)."""
    k = Kit('lamp_post', 406)
    k.post(0, 0, 0.0, 3.0, 0.16, k.wood(0.25))
    k.box((-0.13, -0.13, 0.0), (0.13, 0.13, 0.25), STONE_D)
    k.beam((0, 0, 2.85), (0, 0.6, 2.85), 0.08, 0.08, k.wood(0.35))
    k.beam((0, 0.05, 2.45), (0, 0.4, 2.83), 0.05, 0.05, k.wood(0.35))
    k.lamp(0, 0.55, 2.45, 0.1, 0.24)
    return k


def build_string_pole():
    """2.6 m pole for string lights; hook ring at (0, 0.05, 2.55)."""
    k = Kit('string_pole', 407)
    k.log((0, 0, -0.2), (0, 0, 2.6), 0.035, k.wood(0.3), segs=6)
    k.log((0, 0, 2.55), (0, 0.06, 2.55), 0.012, METAL, segs=4)
    ring = bm_lathe([(0.025 + 0.006 * math.cos(a), 0.006 * math.sin(a)) for a in [i * math.pi / 2 for i in range(5)]], 8, 'X')
    xform(ring, Matrix.Translation((0, 0.08, 2.55)))
    k.mb.add(ring, color=METAL, shade='smooth')
    for a in (0.3, 2.4, 4.4):
        k.log((0, 0, 1.4), (0.9 * math.cos(a), 0.9 * math.sin(a), 0.0), 0.006, ROPE, segs=3, cap=False)
    return k


# ------------------------------------------------------------------ trail park
def tyre_bm(r_out=0.45, width=0.3, segs=14):
    """Tyre torus-ish lathe around Z (lying flat), centred on the origin."""
    ri = r_out * 0.52
    prof = [(ri, -width / 2 + 0.04), (ri + 0.03, -width / 2), (r_out - 0.05, -width / 2), (r_out, -width / 2 + 0.06),
            (r_out, width / 2 - 0.06), (r_out - 0.05, width / 2), (ri + 0.03, width / 2), (ri, width / 2 - 0.04)]
    bm = bm_lathe(prof + [prof[0]], segs, 'Z')
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    C.orient(bm, lambda f: (lambda c: Vector((c.x, c.y, 0)).normalized() * (1 if Vector((c.x, c.y)).length > (ri + r_out) / 2 else -1)
                           + Vector((0, 0, c.z * 4)))(f.calc_center_median()))
    return bm


def build_cone():
    k = Kit('cone', 408)
    k.box((-0.2, -0.2, 0.0), (0.2, 0.2, 0.04), DARK, jitter=0)
    prof = [(0.15, 0.04), (0.13, 0.2), (0.105, 0.34), (0.08, 0.48), (0.055, 0.62), (0.03, 0.7), (0.0, 0.7)]
    bm = bm_lathe(prof, 12, 'Z')
    C.orient(bm, lambda f: f.calc_center_median() * Vector((1, 1, 0)) + Vector((0, 0, 0.01)))
    k.mb.add(bm, color_fn=lambda l, f: WHITE if 0.34 < f.calc_center_median().z < 0.48 else ORANGE, shade='auto', angle=45, jitter=0.02)
    return k


def build_flag_marker():
    k = Kit('flag_marker', 409)
    k.log((0, 0, -0.2), (0, 0, 1.8), 0.02, WHITE, segs=5)
    k.log((0, 0, 1.78), (0, 0, 1.83), 0.03, DARK, segs=5)
    for i, col in enumerate((hexc('#D23B2A'), WHITE)):
        z1, z0 = 1.76 - i * 0.2, 1.36
        pts = [(0.02, 1.76 - i * 0.2), (0.02, 1.36 + i * 0.2), (0.62 - i * 0.3, 1.56)]
        k.poly(pts, 0.015 + i * 0.004, 'Y', 0.0, col, jitter=0)
    return k


def build_tyre_stack():
    k = Kit('tyre_stack', 410)
    for i in range(3):
        bm = tyre_bm(0.45, 0.28)
        xform(bm, mat_trs((k.rng.uniform(-0.04, 0.04), k.rng.uniform(-0.04, 0.04), 0.14 + i * 0.28), (0, 0, k.rng.uniform(0, 1))))
        k.mb.add(bm, color=RUBBER, shade='auto', angle=40, jitter=0.05)
    COLLIDERS['tyre_stack'] = {'cylinder': {'r': 0.45, 'h': 0.84}}
    return k


def build_tyre_wall():
    """Four upright half-buried tyres along X, 3.6 m, painted alternately."""
    k = Kit('tyre_wall', 411)
    for i in range(4):
        x = -1.35 + i * 0.9
        bm = tyre_bm(0.45, 0.3)
        xform(bm, mat_trs((x, 0, 0.12), (math.pi / 2, 0, math.pi / 2)))
        col = RUBBER if i % 2 else hexc('#D9D4C8')
        k.mb.add(bm, color=col, shade='auto', angle=40, jitter=0.04)
    k.box((-1.8, -0.3, -0.05), (1.8, 0.3, 0.05), hexc('#5C4E3D'), jitter=0.1)
    COLLIDERS['tyre_wall'] = {'half': [1.8, 0.28, 0.15], 'center': [0, 0.28, 0]}
    return k


def build_gate_arch():
    """Log arch gate 8 m wide x 5 m tall with a 'TRAIL PARK' sign board."""
    k = Kit('gate_arch', 412)
    for x in (-4.0, 4.0):
        k.log((x, 0, -0.4), (x, 0, 5.0), 0.2, k.wood(0.2), segs=8)
        k.rock((x, 0, 0), (0.9, 0.9, 0.6), 9, 0.5)
        k.log((x, 0, 3.6), (x * 0.78, 0, 4.72), 0.08, k.wood(0.35), segs=5)
    k.log((-4.5, 0, 4.85), (4.5, 0, 4.85), 0.19, k.wood(0.25), segs=8)
    k.log((-4.3, 0, 4.4), (4.3, 0, 4.4), 0.1, k.wood(0.35), segs=6)
    # hanging sign board with chains
    bw, bz0, bz1 = 1.9, 3.35, 4.05
    k.box((-bw, -0.06, bz0), (bw, 0.06, bz1), WOOD_DARK, bev=0.02, jitter=0.03)
    k.box((-bw - 0.06, -0.08, bz0 - 0.06), (bw + 0.06, 0.08, bz0), k.wood(0.3))
    k.box((-bw - 0.06, -0.08, bz1), (bw + 0.06, 0.08, bz1 + 0.06), k.wood(0.3))
    for x in (-1.5, 1.5):
        k.log((x, 0, bz1 + 0.06), (x, 0, 4.32), 0.015, METAL, segs=4)
    for face in (1, -1):
        bm = text_bm('TRAIL PARK', 0.46, 0.015)
        R = Euler((math.pi / 2, 0, 0 if face < 0 else math.pi)).to_matrix().to_4x4()
        xform(bm, Matrix.Translation((0, face * 0.07, (bz0 + bz1) / 2)) @ R)
        k.mb.add(bm, color=CREAM, shade='flat')
    COLLIDERS['gate_arch'] = {'cylinders': [{'x': -4.0, 'r': 0.25, 'h': 5.0}, {'x': 4.0, 'r': 0.25, 'h': 5.0}]}
    return k


def build_log_step():
    """6 m log along X, radius 0.35, origin on the ground under the log."""
    k = Kit('log_step', 413)
    r, L = 0.35, 6.0
    bm = bm_cyl_between((-L / 2, 0, r), (L / 2, 0, r), r, segs=12, rot=0.3)
    bark = hexc('#4E3B2C')
    sawn = hexc('#C79C69')
    ring = hexc('#9C7248')

    def cfn(l, f):
        if abs(f.normal.x) > 0.9:
            d = math.hypot(l.vert.co.y, l.vert.co.z - r)
            return sawn if d < 0.1 else ring
        return mix(bark, WOOD_DARK, 0.5 + 0.5 * math.sin(l.vert.co.x * 3.1))
    k.mb.add(bm, color_fn=cfn, shade='auto', angle=40, jitter=0.05)
    # end rings: inset discs on both sawn faces
    for sx in (-1, 1):
        for rr, col in ((0.24, ring), (0.13, sawn)):
            d = bm_cyl_between((sx * L / 2, 0, r), (sx * (L / 2 + 0.008), 0, r), rr, segs=10)
            k.mb.add(d, color=col, shade='flat')
    # broken branch stubs and moss
    for x, a in ((-1.6, 0.8), (0.9, 2.2), (2.1, -0.4)):
        p = Vector((x, math.cos(a) * r, r + math.sin(a) * r))
        k.log(p, p + Vector((0.05, math.cos(a) * 0.25, math.sin(a) * 0.25)), 0.05, bark, segs=5)
    k.box((-0.8, -0.2, 2 * r - 0.03), (0.4, 0.15, 2 * r + 0.01), hexc('#5F7A3E'), jitter=0.1)
    COLLIDERS['log_step'] = {'capsule_x': {'half_len': L / 2, 'r': r, 'center': [0, r, 0]}}
    return k


def build_sign_board():
    k = Kit('sign_board', 414)
    k.post(0, 0, -0.3, 1.9, 0.12, k.wood(0.25))
    for z, d in ((1.55, 1), (1.2, -1)):
        pts = [(-0.05 if d > 0 else -0.85, z - 0.14), (0.75 if d > 0 else 0.05, z - 0.14), (0.9 if d > 0 else 0.05, z),
               (0.75 if d > 0 else 0.05, z + 0.14), (-0.05 if d > 0 else -0.85, z + 0.14)]
        if d < 0:
            pts = [(-0.85, z), (-0.7, z - 0.14), (0.05, z - 0.14), (0.05, z + 0.14), (-0.7, z + 0.14)]
        k.poly(pts, 0.05, 'Y', 0.09, k.wood(0.7), jitter=0.03)
    return k


def build_barrier():
    k = Kit('barrier', 415)
    for x in (-1.3, 1.3):
        k.beam((x, -0.3, 0.0), (x, 0.0, 0.95), 0.07, 0.07, k.wood(0.3))
        k.beam((x, 0.3, 0.0), (x, 0.0, 0.95), 0.07, 0.07, k.wood(0.3))
    n = 8
    for i in range(n):
        x0, x1 = -1.5 + 3.0 * i / n, -1.5 + 3.0 * (i + 1) / n
        k.box((x0, -0.04, 0.78), (x1, 0.04, 1.02), hexc('#D23B2A') if i % 2 else WHITE, jitter=0)
    COLLIDERS['barrier'] = {'half': [1.5, 0.5, 0.3], 'center': [0, 0.5, 0]}
    return k


# ------------------------------------------------------------------ lake + camp clutter
def hull_bm(L, B, D, fine=1.0, stern_w=0.0, pointed_both=False, n=14, m=8):
    """Boat hull loft along Y from sections; gunwale at z=D*0.6, keel at z=-D*0.4. Open top."""
    verts, faces = [], []
    for i in range(n + 1):
        t = i / n                          # 0 stern (-Y) .. 1 bow (+Y)
        y = -L / 2 + L * t
        if pointed_both:
            w = B / 2 * math.sin(math.pi * t) ** 0.7
        elif t > 0.45:
            w = B / 2 * max(0.0, 1 - ((t - 0.45) / 0.55) ** 2.2) ** 0.75
        else:
            w = B / 2 * (1 - ((0.45 - t) / 0.45) ** 2 * (1 - stern_w)) ** 0.5
        sheer = 0.08 * ((2 * t - 1) ** 2)
        for j in range(m + 1):
            a = math.pi * j / m                     # 0 right gunwale .. pi left gunwale
            x = w * math.cos(a)
            z = D * 0.6 + sheer - D * math.sin(a) ** fine * (1.0 - 0.3 * abs(2 * t - 1) ** 3)
            verts.append((x, y, z))
    for i in range(n):
        for j in range(m):
            a = i * (m + 1) + j
            faces.append([a, a + 1, a + m + 2, a + m + 1])
    bm = bm_from(verts, faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    return bm


def build_rowboat():
    """3.6 m wooden rowboat at the waterline z=0, bow +Y, with two oars."""
    k = Kit('rowboat', 416)
    L, B, D = 3.6, 1.35, 0.55
    out = hull_bm(L, B, D, 0.8, stern_w=0.55)
    C.orient(out, lambda f: f.calc_center_median() * Vector((1, 0, 0)) - Vector((0, 0, 0.3)))
    k.mb.add(xform(out, Matrix.Translation((0, 0, -0.1))),
             color_fn=lambda l, f: hexc('#3C6E5E') if l.vert.co.z > 0.1 else (WHITE if l.vert.co.z > -0.08 else hexc('#8E3A2C')),
             shade='auto', angle=55, jitter=0.02)
    inner = hull_bm(L * 0.97, B * 0.9, D * 0.85, 0.8, stern_w=0.55)
    xform(inner, Matrix.Translation((0, 0, -0.1 + 0.15 * D * 0.6)))
    C.orient(inner, lambda f: -(f.calc_center_median() * Vector((1, 0, 0)) - Vector((0, 0, 0.3))))
    k.mb.add(inner, color=WOOD_L, shade='auto', angle=55, jitter=0.03)
    # gunwale caps following the sheer line
    n = 10
    for sx in (-1, 1):
        pts = []
        for i in range(n + 1):
            t = i / n
            if t > 0.45:
                w = B / 2 * max(0.0, 1 - ((t - 0.45) / 0.55) ** 2.2) ** 0.75
            else:
                w = B / 2 * (1 - ((0.45 - t) / 0.45) ** 2 * 0.45) ** 0.5
            pts.append(Vector((sx * w * 0.97, -L / 2 + L * t, D * 0.6 + 0.08 * (2 * t - 1) ** 2 - 0.1)))
        for q0, q1 in zip(pts, pts[1:]):
            k.log(q0, q1, 0.035, WOOD_D, segs=4)
    # transom, gunwale rails, thwarts, oars
    k.box((-0.48, -L / 2 - 0.02, -0.1), (0.48, -L / 2 + 0.05, 0.27), WOOD_D)
    for y, w in ((-0.9, 0.52), (0.15, 0.62), (1.0, 0.44)):
        k.box((-w, y - 0.12, 0.08), (w, y + 0.12, 0.12), k.wood(0.7))
    for sx in (-1, 1):
        k.log((sx * 0.35, -1.3, 0.18), (sx * 0.12, 1.05, 0.16), 0.022, k.wood(0.7), segs=5)
        k.box((sx * 0.12 - 0.06, 1.05, 0.13), (sx * 0.12 + 0.06, 1.35, 0.18), k.wood(0.6))
    COLLIDERS['rowboat'] = {'half': [0.68, 0.35, 1.8], 'center': [0, 0.1, 0]}
    return k


def build_crate_stack():
    k = Kit('crate_stack', 417)
    for (x, y, z, s) in ((-0.35, 0, 0, 0.6), (0.33, 0.05, 0, 0.6), (0.0, 0.0, 0.6, 0.55), (0.75, -0.6, 0, 0.45)):
        h = s / 2
        k.box((x - h, y - h, z), (x + h, y + h, z + s), k.wood(0.6), jitter=0.04)
        c = k.wood(0.2)
        for dz in (0.03, s - 0.07):
            for sy in (-1, 1):
                k.box((x - h - 0.01, y + sy * h - 0.01, z + dz), (x + h + 0.01, y + sy * h + 0.01, z + dz + 0.05), c, jitter=0)
        for sx in (-1, 1):
            k.box((x + sx * h - 0.015, y - h - 0.015, z), (x + sx * h + 0.015, y + h + 0.015, z + s), c, jitter=0)
    COLLIDERS['crate_stack'] = {'half': [0.8, 0.6, 0.8], 'center': [0.15, 0.6, -0.15]}
    return k


def build_firewood():
    """Split firewood stacked between two stakes, 1.6 m long pile."""
    k = Kit('firewood', 418)
    for x in (-0.85, 0.85):
        k.post(x, 0, 0.0, 1.05, 0.08, k.wood(0.2))
    for row in range(5):
        z = 0.09 + row * 0.18
        for j in range(8):
            x = -0.72 + j * 0.205 + (0.1 if row % 2 else 0)
            if x > 0.75:
                continue
            k.log((x, -0.28, z), (x, 0.28, z), 0.09, k.wood(0.2), segs=k.rng.choice((3, 4, 5)))
            k.mb.add(bm_cyl_between((x, 0.28, z), (x, 0.285, z), 0.075, segs=5), color=hexc('#C9A070'), shade='flat')
    k.box((-0.95, -0.4, 0.95), (0.95, 0.4, 1.0), hexc('#3F4B45'), jitter=0.05)   # tarp over the top
    COLLIDERS['firewood'] = {'half': [0.9, 0.5, 0.35], 'center': [0, 0.5, 0]}
    return k


def build_canoe_rack():
    """A-frame rack (2.4 m) carrying a yellow-green and a red canoe (4.2 m)."""
    k = Kit('canoe_rack', 419)
    for y in (-1.2, 1.2):
        for sx in (-1, 1):
            k.beam((sx * 0.8, y, 0.0), (sx * 0.15, y, 1.5), 0.08, 0.08, k.wood(0.3))
        for z, w in ((0.55, 0.62), (1.1, 0.34)):
            k.beam((-w - 0.15, y, z), (w + 0.15, y, z), 0.07, 0.09, k.wood(0.45))
    for y in (-0.6, 0.6):
        k.beam((-0.2, -1.25, 1.45 + 0.0 * y), (-0.2, 1.25, 1.45), 0.06, 0.06, k.wood(0.4))
    grad = lambda l, f: mix(hexc('#E9C640'), hexc('#77B04A'), (l.vert.co.y + 2.1) / 4.2)
    for (z, x, cf) in ((0.62, 0.0, lambda l, f: hexc('#C8452F') if l.vert.co.z > -0.05 else hexc('#9A3325')), (1.17, 0.0, grad)):
        bm = hull_bm(4.2, 0.75, 0.34, 1.0, pointed_both=True, n=14, m=6)
        # upside-down on the rack: flip and close with a deck plane
        xform(bm, Matrix.Translation((x, 0, z + 0.2)) @ Matrix.Rotation(math.pi, 4, 'Y'))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        C.orient(bm, lambda f, z=z: f.calc_center_median() - Vector((0, f.calc_center_median().y, z + 0.1)))
        k.mb.add(bm, color_fn=cf, shade='auto', angle=60, jitter=0.02)
    COLLIDERS['canoe_rack'] = {'half': [0.9, 0.8, 2.1], 'center': [0, 0.8, 0]}
    return k


BUILDERS = [
    ('aframe_cabin', build_aframe_cabin), ('boathouse', build_boathouse), ('plank_bridge', build_plank_bridge),
    ('camper', build_camper), ('lantern', build_lantern), ('lamp_post', build_lamp_post),
    ('string_pole', build_string_pole), ('cone', build_cone), ('flag_marker', build_flag_marker),
    ('tyre_stack', build_tyre_stack), ('tyre_wall', build_tyre_wall), ('gate_arch', build_gate_arch),
    ('log_step', build_log_step), ('sign_board', build_sign_board), ('barrier', build_barrier),
    ('rowboat', build_rowboat), ('crate_stack', build_crate_stack), ('firewood', build_firewood),
    ('canoe_rack', build_canoe_rack),
]


def main(previews=True):
    C.reset_scene()
    mats = {'VC': C.mat_vc('VC'), 'Glow': C.mat_vc('Glow', roughness=0.4)}
    col = C.collection('Props2')
    objs, report = {}, {}
    for name, fn in BUILDERS:
        k = fn()
        tris = k.mb.tris()
        ob = k.build(mats, col)
        objs[name] = ob
        C.export_glb([ob], name + '.glb', vcolor=True)
        mn, mx = C.world_bbox([ob])
        glow = 'Glow' in [s.material.name for s in ob.material_slots if s.material]
        # bbox in game coordinates (x, z, -y): +Y up, front = -Z
        report[name] = {'tris': tris, 'glow': glow,
                        'bbox_blender': {'min': [round(v, 3) for v in mn], 'max': [round(v, 3) for v in mx]},
                        'size_m': [round(mx.x - mn.x, 2), round(mx.y - mn.y, 2), round(mx.z - mn.z, 2)],
                        'collider': COLLIDERS.get(name)}
    print('PROPS2 TRIS', {k: v['tris'] for k, v in report.items()})
    with open(os.path.join(C.ART, 'props2-report.json'), 'w') as f:
        json.dump({'note': 'bbox in Blender coords (+Y front, +Z up); collider centre/half as [x, y_up, z_game] where '
                           'z_game = -y_blender unless given as named deck ranges (Blender x/y)', 'assets': report}, f, indent=1)
    if not previews:
        return report
    C.setup_render()
    C.add_sun((50, 0, 150), 4.0)
    ground = C.add_ground(0.0, color='#7C7457')
    for o in objs.values():
        o.hide_render = True

    def shot(names, fname, gap, az=20, el=14, lens=50, gz=0.0):
        ground.location.z = gz
        sel = [objs[n] for n in names]
        for o in sel:
            o.hide_render = False
        C.lineup(sel, gap)
        C.frame_camera(sel, az=az, el=el, lens=lens)
        C.render(fname)
        for o in sel:
            o.hide_render = True

    shot(['aframe_cabin'], 'props2_aframe.png', 1.0, az=30, el=10)
    shot(['aframe_cabin'], 'props2_aframe_back.png', 1.0, az=215, el=18)
    shot(['boathouse'], 'props2_boathouse.png', 1.0, az=60, el=12, gz=-1.2)
    shot(['plank_bridge'], 'props2_bridge.png', 1.0, az=65, el=10, gz=-4.0)
    shot(['camper'], 'props2_camper.png', 1.0, az=40, el=12)
    shot(['camper'], 'props2_camper_back.png', 1.0, az=235, el=12)
    shot(['gate_arch', 'log_step', 'tyre_wall', 'tyre_stack', 'cone', 'flag_marker', 'barrier'], 'props2_park.png', 0.8, az=18, el=12)
    shot(['lantern', 'lamp_post', 'string_pole', 'sign_board', 'crate_stack', 'firewood'], 'props2_small.png', 0.6, az=20, el=12)
    shot(['rowboat', 'canoe_rack'], 'props2_lake.png', 1.0, az=35, el=20, gz=-0.6)
    for o in objs.values():
        o.location = (0, 0, 0)
        o.hide_render = False
    C.save_blend('props2.blend')
    return report


if __name__ == '__main__':
    main()
