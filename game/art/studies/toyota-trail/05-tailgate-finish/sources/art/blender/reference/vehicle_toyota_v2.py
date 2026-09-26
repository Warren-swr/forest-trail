"""Forest Trail vehicle "toyota": TOYOTA Land Cruiser 60-series style 5-door wagon.

Built after assets/reference/车辆正面_白天.png / 车辆正面_黑夜.png: round headlights in a
black grille with TOYOTA letters, amber signals outboard, black steel bumper with winch,
fairlead, hook and four small driving lamps, left snorkel (as in the reference photo),
full-length roof rack with bags, barn doors with spare wheel and ladder.

Blender coords: +Y front, +Z up, +X = vehicle right. Origin = midpoint between axles
at static wheel-centre height; ground is at Z = -0.40.
Exports vehicle_toyota.glb (+ .json mounts/lamps) through vehicle_parts.export_vehicle.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
from common import bm_box, bm_box_mm, bm_cyl, bm_cyl_between, bm_lathe, bm_from, xform, mat_trs
import vehicle_parts as P
from vehicle_parts import add_wheel

# ------------------------------------------------------------------ key dimensions
WHEELBASE = 2.73
AXLE_Y = WHEELBASE / 2          # front +1.365, rear -1.365
TRACK_X = 0.86                  # wheel centre X
TYRE_R, TYRE_W = 0.40, 0.30
GROUND_Z = -0.40
SILL_Z = 0.15                   # rocker / floor bottom: 0.55 above ground
OVERHANG_Z = 0.30               # tub bottom in front of / behind the axles (bumpers cover it)
ARCH_LEG_Z = 0.36               # floor rises to this at the inner arch legs (driveshaft clearance)
BELT_Z = 0.88
ROOF_Z = 1.43
HALF_W = 0.90
FRONT_Y, REAR_Y = 1.98, -2.12   # tub front (grille plane) / rear (door plane)
ARCH_R, ARCH_ZC = 0.50, 0.18    # wheel arch radius / centre height
FLARE_R, FLARE_X = 0.60, 1.00
SPRING_X = 0.54
SPRING_TOP_Z = 0.50             # upper spring seat (body coords)
SPRING_SEAT_Z = 0.06            # lower spring seat (axle-local coords)
PINION_Y, PINION_Z = 0.235, 0.03
TCASE_Y, TCASE_Z = 0.30, 0.02
RAIL_X0, RAIL_X1 = 0.38, 0.46   # frame rail inner / outer X
LINER_X = 0.36                  # wheel-well inner wall
LINER_Z = 0.32                  # liner lower edge (above the axle tube at full bump)

HEAD_X, HEAD_Z, HEAD_R = 0.60, 0.64, 0.105


def make_materials():
    m = P.base_materials('#8E8872', '#9C957E', '#4B4C4A')
    m['Board'] = C.mat_pbr('Board', '#D98A2E', 0.7, 0.0)   # recovery boards (not a lamp)
    return m


# ------------------------------------------------------------------ helpers
def arch_poly(yc, r, zc, z_rear, z_front, steps=16):
    """Arch outline (Y,Z) from the rear leg (at z_rear) over the top to the front leg (z_front)."""
    a_r = math.pi - math.asin(max(-1.0, min(1.0, (z_rear - zc) / r)))
    a_f = math.asin(max(-1.0, min(1.0, (z_front - zc) / r)))
    pts = []
    for i in range(steps + 1):
        a = a_r + (a_f - a_r) * i / steps
        pts.append((yc + r * math.cos(a), zc + r * math.sin(a)))
    return pts


def in_arch(c, pad=0.02):
    return any(Vector((c.y - yc, c.z - ARCH_ZC)).length < ARCH_R + pad and c.z > ARCH_ZC - 0.1
               for yc in (-AXLE_Y, AXLE_Y))


def tube(mb, a, b, r=0.016, mat='Trim', segs=6):
    mb.add(bm_cyl_between(a, b, r, segs=segs, cap=False), mat=mat, shade='auto', angle=70)


def tube_path(mb, pts, r=0.02, mat='Trim', segs=8):
    for a, b in zip(pts, pts[1:]):
        mb.add(bm_cyl_between(a, b, r, segs=segs, cap=True), mat=mat, shade='auto', angle=60)
    for p in pts[1:-1]:
        mb.add(C.bm_icosphere(r * 1.02, 1, Matrix.Translation(p)), mat=mat, shade='smooth')


def lamp_round(mb, cx, cz, y, r, lens='Lamp', bezel='Chrome', depth=0.05, ring=0.02, segs=18):
    """Round lamp facing +Y whose lens front sits at y."""
    bez = bm_lathe([(r + ring, y - depth), (r + ring, y - 0.012), (r + ring * 0.6, y + 0.002),
                    (r + 0.004, y - 0.004), (r, y - 0.01)], segs, axis='Y')
    C.orient(bez, lambda f: Vector((0, 0.7, 0)) + Vector((f.calc_center_median().x - cx, 0, f.calc_center_median().z - cz)))
    mb.add(xform(bez, Matrix.Translation((cx, 0, cz))), mat=bezel, shade='auto', angle=50)
    ln = bm_lathe([(r, y - 0.012), (r * 0.7, y - 0.004), (0.0, y)], segs, axis='Y')
    C.orient(ln, lambda f: (0, 1, 0))
    mb.add(xform(ln, Matrix.Translation((cx, 0, cz))), mat=lens, shade='smooth')


def lamp_round_rear(mb, cx, cz, y, r, lens):
    """Round lamp facing -Y with front at y."""
    ln = bm_lathe([(r + 0.01, y + 0.03), (r + 0.01, y + 0.004), (r, y), (0.0, y - 0.006)], 12, axis='Y')
    C.orient(ln, lambda f: (0, -1, 0))
    mb.add(xform(ln, Matrix.Translation((cx, 0, cz))), mat=lens, shade='auto', angle=50)


def add_text(mb, text, loc, size=0.1, extrude=0.006, mat='Decal', offset=0.0028, facing=1):
    """Extruded Bfont text on a vertical plane facing +Y (facing=1) or -Y (facing=-1); loc = centre of the front face."""
    cu = bpy.data.curves.new('txt_' + text, 'FONT')
    cu.body = text
    cu.size = size
    cu.extrude = extrude
    cu.offset = offset
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.space_character = 1.08
    ob = bpy.data.objects.new('txt_' + text, cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    bpy.context.view_layer.update()
    # text x -> -X*facing (reads left-to-right from outside), text y -> +Z, text normal -> +Y*facing
    R = Matrix(((-facing, 0, 0, 0), (0, 0, facing, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    if facing < 0:
        R = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    M = Matrix.Translation((loc[0], loc[1] - facing * extrude, loc[2])) @ R
    xform(bm, M)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mb.add(bm, mat=mat, shade='flat')


# ------------------------------------------------------------------ body tub
def add_tub(mb):
    b, t = SILL_Z, BELT_Z
    ry, fy = REAR_Y, FRONT_Y
    prof = [(ry, OVERHANG_Z + 0.06), (ry + 0.05, OVERHANG_Z)]
    prof += arch_poly(-AXLE_Y, ARCH_R, ARCH_ZC, OVERHANG_Z, ARCH_LEG_Z)
    prof += [(-0.36, b), (0.36, b)]
    prof += arch_poly(AXLE_Y, ARCH_R, ARCH_ZC, ARCH_LEG_Z, OVERHANG_Z)
    prof += [(fy - 0.05, OVERHANG_Z), (fy, OVERHANG_Z + 0.06), (fy, t - 0.03), (fy - 0.025, t),
             (ry + 0.025, t), (ry, t - 0.03)]
    bm = C.bm_extrude_poly(prof, 2 * HALF_W, axis='X')
    C.bevel(bm, 0.03, 2)
    bm.normal_update()

    def mat(f):
        c, n = f.calc_center_median(), f.normal
        if n.z < -0.5 and abs(c.x) < HALF_W - 0.01:
            return 'Trim'
        if abs(n.x) < 0.5 and in_arch(c) and n.z < 0.3 and abs(c.x) < HALF_W - 0.02:
            return 'Trim'
        return 'Paint'
    mb.add(bm, mat_fn=mat, shade='auto', angle=32)
    # rocker skins hide the raised floor between the wheels
    for sx in (-1, 1):
        xs = sorted((sx * (HALF_W - 0.03), sx * HALF_W))
        mb.add(bm_box_mm((xs[0], -0.86, b), (xs[1], 0.86, ARCH_LEG_Z + 0.08)), mat='Paint', shade='flat')
        mb.add(bm_box_mm((min(sx * (HALF_W - 0.035), sx * (HALF_W + 0.005)), -0.86, b - 0.005),
                         (max(sx * (HALF_W - 0.035), sx * (HALF_W + 0.005)), 0.86, b + 0.06), 0.01),
               mat='Trim', shade='auto')
    # wheel-well inner walls above the axle travel, so the arch tunnel does not show through
    for yc in (-AXLE_Y, AXLE_Y):
        a0 = math.asin((LINER_Z - ARCH_ZC) / (ARCH_R + 0.005))
        pts = [(yc + (ARCH_R + 0.005) * math.cos(a), ARCH_ZC + (ARCH_R + 0.005) * math.sin(a))
               for a in [math.pi - a0 + (2 * a0 - math.pi) * i / 14 for i in range(15)]]
        for sx in (-1, 1):
            mb.add(C.bm_extrude_poly(pts, 0.02, axis='X', center=sx * LINER_X), mat='Trim', shade='flat')
    # hood with a slight centre crease, cowl and hood seams
    hz = t + 0.012
    V = [(-0.86, 0.87, hz), (0.0, 0.87, hz + 0.018), (0.86, 0.87, hz), (-0.86, 1.965, hz - 0.004),
         (0.0, 1.965, hz + 0.012), (0.86, 1.965, hz - 0.004)]
    V2 = [(x, y, z - 0.03) for x, y, z in V]
    verts = V + V2
    faces = [[0, 3, 4, 1], [1, 4, 5, 2], [9, 10, 7, 6][::-1], [10, 11, 8, 7][::-1],
             [0, 1, 7, 6], [1, 2, 8, 7], [3, 9, 10, 4], [4, 10, 11, 5], [0, 6, 9, 3], [2, 5, 11, 8]]
    hood = bm_from(verts, faces)
    bmesh.ops.recalc_face_normals(hood, faces=hood.faces)
    C.bevel(hood, 0.008, 1)
    mb.add(hood, mat='Paint', shade='auto', angle=20)
    for sx in (-1, 1):
        mb.add(bm_box_mm((sx * 0.868 - 0.004, 0.87, t - 0.02), (sx * 0.868 + 0.004, 1.97, t + 0.016)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.86, 0.80, t - 0.005), (0.86, 0.872, t + 0.03), 0.008), mat='Trim', shade='auto')
    for i in range(9):
        x = -0.4 + i * 0.1
        mb.add(bm_box_mm((x - 0.03, 0.815, t + 0.03), (x + 0.03, 0.855, t + 0.034)), mat='Rubber', shade='flat')


# ------------------------------------------------------------------ greenhouse
def add_greenhouse(mb):
    zb, zt = BELT_Z, ROOF_Z
    xb, xt = 0.885, 0.845
    st = [(0.86, 0.70), (-0.11, -0.13), (-1.02, -1.04), (-2.10, -2.08)]
    V = []
    for yb, yt in st:
        V += [(-xb, yb, zb), (xb, yb, zb), (xt, yt, zt), (-xt, yt, zt)]
    F = [[0, 1, 2, 3][::-1], [12, 13, 14, 15]]
    for i in range(3):
        a, n = 4 * i, 4 * (i + 1)
        F += [[a + 1, n + 1, n + 2, a + 2], [a, a + 3, n + 3, n], [a + 3, a + 2, n + 2, n + 3], [a, n, n + 1, a + 1]]
    bm = bm_from(V, F)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bottom = [f for f in bm.faces if f.normal.z < -0.9]
    edges = [e for e in bm.edges if not any(f in bottom for f in e.link_faces)]
    res = C.bevel(bm, 0.035, 2, edges)
    new = set(res.get('faces', []))
    bm.normal_update()
    wins = [f for f in bm.faces if f not in new and abs(f.normal.z) < 0.5 and f.calc_area() > 0.05]
    kill = [f for f in bm.faces if f.normal.z < -0.9]
    bmesh.ops.delete(bm, geom=kill, context='FACES_ONLY')
    bmesh.ops.inset_individual(bm, faces=wins, thickness=0.06, depth=-0.02)
    glass = set(wins)
    mb.add(bm, mat_fn=lambda f: 'Glass' if f in glass else 'Paint', shade='auto', angle=32)
    # roof skin with drip rails (rain gutters) along both sides
    mb.add(bm_box_mm((-xt + 0.01, -2.075, zt - 0.01), (xt - 0.01, 0.70, zt + 0.025), 0.018, 2), mat='PaintAccent', shade='auto', angle=40)
    for sx in (-1, 1):
        g0 = (sx * (xt + 0.012), -2.07, zt - 0.03)
        g1 = (sx * (xt + 0.012), 0.69, zt - 0.03)
        tube(mb, g0, g1, 0.011, 'Paint', 6)
    # roof ribs
    for y in (-0.35, -0.95, -1.55):
        mb.add(bm_box_mm((-xt + 0.06, y - 0.02, zt + 0.02), (xt - 0.06, y + 0.02, zt + 0.032), 0.006), mat='PaintAccent', shade='auto')
    # windshield rubber frame, wipers, interior mirror
    for x0 in (-0.36, 0.26):
        tube(mb, (x0, 0.845, zb + 0.03), (x0 + 0.34, 0.80, zb + 0.13), 0.007, 'Rubber', 5)
        mb.add(bm_box((0.035, 0.03, 0.02), (x0, 0.85, zb + 0.03)), mat='Trim', shade='flat')
    mb.add(bm_box((0.2, 0.02, 0.055), (0, 0.66, zt - 0.1)), mat='Trim', shade='auto')
    # B/C pillar and door-top seams on the greenhouse
    for sx in (-1, 1):
        for yb, yt in st[1:3]:
            p0 = (sx * (xb + 0.002), yb + 0.012, zb + 0.01)
            p1 = (sx * (xt + 0.002), yt + 0.012, zt - 0.03)
            tube(mb, p0, p1, 0.004, 'Trim', 4)
    return st


# ------------------------------------------------------------------ front end
def add_front(mb):
    y = FRONT_Y
    # black grille panel with square headlight surrounds
    mb.add(bm_box_mm((-0.86, y - 0.02, 0.44), (0.86, y + 0.012, 0.845), 0.012), mat='Trim', shade='auto')
    # grille slats and centre field
    mb.add(bm_box_mm((-0.44, y + 0.005, 0.46), (0.44, y + 0.02, 0.705)), mat='Rubber', shade='flat')
    for i in range(6):
        z = 0.48 + i * 0.04
        mb.add(bm_box_mm((-0.43, y + 0.012, z - 0.009), (0.43, y + 0.03, z + 0.009), 0.003), mat='Trim', shade='auto')
    for x in (-0.3, -0.15, 0.0, 0.15, 0.3):
        mb.add(bm_box_mm((x - 0.008, y + 0.012, 0.465), (x + 0.008, y + 0.028, 0.70)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.46, y + 0.012, 0.44), (0.46, y + 0.034, 0.46), 0.004), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.46, y + 0.012, 0.705), (0.46, y + 0.034, 0.725), 0.004), mat='Trim', shade='auto')
    add_text(mb, 'TOYOTA', (0.0, y + 0.03, 0.772), size=0.088, extrude=0.006)
    # round headlights in square black bezels, amber signals outboard, side markers
    for sx in (-1, 1):
        cx = sx * HEAD_X
        mb.add(bm_box_mm((cx - 0.15, y - 0.01, HEAD_Z - 0.15), (cx + 0.15, y + 0.03, HEAD_Z + 0.15), 0.02, 2), mat='Trim', shade='auto', angle=40)
        lamp_round(mb, cx, HEAD_Z, y + 0.075, HEAD_R, 'Lamp', 'Chrome', depth=0.05, ring=0.022, segs=20)
        # reflector ring behind the lens
        rf = bm_lathe([(HEAD_R * 0.98, y + 0.03), (HEAD_R * 0.6, y + 0.02)], 18, axis='Y')
        C.orient(rf, lambda f: (0, 1, 0))
        mb.add(xform(rf, Matrix.Translation((cx, 0, HEAD_Z))), mat='Metal', shade='smooth')
        ax = sx * 0.815
        mb.add(bm_box_mm((ax - 0.042, y - 0.005, 0.57), (ax + 0.042, y + 0.04, 0.72), 0.008), mat='Trim', shade='auto')
        mb.add(bm_box_mm((ax - 0.032, y + 0.03, 0.58), (ax + 0.032, y + 0.052, 0.71), 0.008), mat='LampAmber', shade='auto')
        mb.add(bm_box_mm((sx * HALF_W - 0.01 * sx - 0.006, 1.62, 0.70), (sx * HALF_W + 0.006 * sx + 0.006, 1.70, 0.73), 0.004), mat='LampAmber', shade='auto')
    # front fender tops meet the grille: small chrome trims
    for sx in (-1, 1):
        mb.add(bm_box_mm((min(sx * 0.46, sx * 0.84), y + 0.01, 0.84), (max(sx * 0.46, sx * 0.84), y + 0.03, 0.85)), mat='Chrome', shade='flat')


def add_bumper_front(mb):
    y0, y1 = FRONT_Y + 0.01, FRONT_Y + 0.235
    z0, z1 = 0.19, 0.44
    # main steel beam with a winch recess, end caps angled back
    for x0, x1 in ((-0.96, -0.34), (0.34, 0.96)):
        mb.add(bm_box_mm((x0, y0, z0), (x1, y1, z1), 0.025, 2), mat='Trim', shade='auto', angle=40)
    mb.add(bm_box_mm((-0.34, y0, z0), (0.34, y1 - 0.09, z1 - 0.02), 0.02), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.34, y0, z1 - 0.03), (0.34, y1, z1)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.34, y1 - 0.03, z0), (0.34, y1, z0 + 0.05)), mat='Trim', shade='flat')
    for sx in (-1, 1):
        wing = bm_box((0.1, 0.16, z1 - z0 - 0.04), (sx * 1.0, y0 + 0.02, (z0 + z1) / 2), 0.02, 1, rot=(0, 0, sx * math.radians(28)))
        mb.add(wing, mat='Trim', shade='auto')
        # bolts on the face
        for x in (0.42, 0.9):
            for z in (z0 + 0.04, z1 - 0.04):
                mb.add(bm_cyl_between((sx * x, y1, z), (sx * x, y1 + 0.008, z), 0.009, segs=6), mat='Metal', shade='flat')
    # winch: drum, motor, control box, cable, hawse fairlead and hook
    wy = y1 - 0.14
    mb.add(bm_cyl_between((-0.30, wy, 0.33), (-0.14, wy, 0.33), 0.07, segs=12), mat='Trim', shade='auto', angle=50)
    mb.add(bm_cyl_between((-0.14, wy, 0.33), (0.14, wy, 0.33), 0.052, segs=12), mat='Rubber', shade='auto', angle=50)
    for i in range(9):
        x = -0.12 + i * 0.03
        mb.add(bm_cyl_between((x - 0.011, wy, 0.33), (x + 0.011, wy, 0.33), 0.062, segs=10), mat='Metal', shade='auto', angle=50)
    mb.add(bm_cyl_between((0.14, wy, 0.33), (0.28, wy, 0.33), 0.066, segs=12), mat='Trim', shade='auto', angle=50)
    mb.add(bm_box_mm((0.10, wy - 0.05, 0.40), (0.26, wy + 0.06, 0.48), 0.012), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.12, y1 - 0.012, 0.28), (0.12, y1 + 0.012, 0.38), 0.01), mat='Metal', shade='auto')
    mb.add(bm_box_mm((-0.075, y1 + 0.008, 0.315), (0.075, y1 + 0.016, 0.345)), mat='Rubber', shade='flat')
    tube(mb, (0.0, wy + 0.05, 0.285), (0.0, y1 + 0.02, 0.33), 0.006, 'Metal')
    tube(mb, (0.0, y1 + 0.02, 0.33), (0.0, y1 + 0.03, 0.19), 0.006, 'Metal')
    hook = bm_lathe([(0.03 + 0.009 * math.cos(a), 0.009 * math.sin(a)) for a in [i * math.pi / 3 for i in range(7)]], 10, axis='X', arc=math.pi * 1.4)
    mb.add(xform(hook, mat_trs((0, y1 + 0.03, 0.165), (0, math.radians(90), 0))), mat='Metal', shade='smooth')
    # four small round driving lamps
    for x in (-0.76, -0.60, 0.60, 0.76):
        lamp_round(mb, x, 0.35, y1 + 0.03, 0.036, 'LampAux', 'Chrome', depth=0.035, ring=0.012, segs=12)
    # front licence plate on the right bumper wing
    mb.add(bm_box_mm((0.46, y1, 0.215), (0.74, y1 + 0.01, 0.285), 0.004), mat='Decal', shade='auto')
    mb.add(bm_box_mm((0.475, y1 + 0.008, 0.23), (0.725, y1 + 0.012, 0.27)), mat='Trim', shade='flat')
    # tow hooks under the bumper
    for sx in (-1, 1):
        mb.add(bm_box_mm((sx * 0.55 - 0.03, y1 - 0.12, 0.13), (sx * 0.55 + 0.03, y1 - 0.02, 0.2)), mat='Trim', shade='flat')
        th = bm_lathe([(0.04 + 0.012 * math.cos(a), 0.012 * math.sin(a)) for a in [i * math.pi / 3 for i in range(7)]], 10, axis='X', arc=math.pi)
        mb.add(xform(th, mat_trs((sx * 0.55, y1 - 0.02, 0.15), (0, 0, 0))), mat='Paint', shade='smooth')
    # nudge bar hoop in front of the grille
    for sx in (-1, 1):
        tube_path(mb, [(sx * 0.43, y1 - 0.06, z1), (sx * 0.43, y1 - 0.08, 0.70), (sx * 0.36, y1 - 0.10, 0.80), (sx * 0.22, y1 - 0.11, 0.83)], 0.022)
    tube(mb, (-0.22, y1 - 0.11, 0.83), (0.22, y1 - 0.11, 0.83), 0.022)


# ------------------------------------------------------------------ rear end
SPARE_C = (0.40, -2.36, 0.58)
SPARE_W = 0.24


def add_rear(mb):
    y = REAR_Y
    # barn doors: centre seam, hinges, handles, licence plate
    mb.add(bm_box_mm((-0.004, y - 0.006, SILL_Z + 0.16), (0.004, y + 0.002, BELT_Z + 0.52)), mat='Trim', shade='flat')
    for sx in (-1, 1):
        for x0, x1 in ((sx * 0.78, sx * 0.785),):
            mb.add(bm_box_mm((min(x0, x1) - 0.003, y - 0.006, SILL_Z + 0.16), (max(x0, x1) + 0.003, y + 0.002, BELT_Z)), mat='Trim', shade='flat')
        for z in (0.42, 0.80, 1.18):
            mb.add(bm_box_mm((sx * 0.80 - 0.03, y - 0.03, z - 0.035), (sx * 0.80 + 0.03, y, z + 0.035), 0.006), mat='Trim', shade='auto')
        mb.add(bm_box_mm((sx * 0.12 - 0.045, y - 0.03, 0.78), (sx * 0.12 + 0.045, y, 0.81), 0.008), mat='Chrome', shade='auto')
    mb.add(bm_box_mm((-0.78, y - 0.006, SILL_Z + 0.155), (0.78, y + 0.002, SILL_Z + 0.165)), mat='Trim', shade='flat')
    # vertical tail lamp clusters in the rear corners: amber / red / reverse
    for sx in (-1, 1):
        cx = sx * 0.83
        mb.add(bm_box_mm((cx - 0.055, y - 0.018, 0.30), (cx + 0.055, y + 0.01, 0.74), 0.01), mat='Chrome', shade='auto')
        mb.add(bm_box_mm((cx - 0.045, y - 0.03, 0.62), (cx + 0.045, y - 0.012, 0.73), 0.006), mat='LampAmber', shade='auto')
        mb.add(bm_box_mm((cx - 0.045, y - 0.03, 0.43), (cx + 0.045, y - 0.012, 0.61), 0.006), mat='LampRear', shade='auto')
        mb.add(bm_box_mm((cx - 0.045, y - 0.03, 0.31), (cx + 0.045, y - 0.012, 0.42), 0.006), mat='LampReverse', shade='auto')
    # rear bumper, step plate, hitch receiver
    mb.add(bm_box_mm((-0.95, y - 0.10, 0.18), (0.95, y + 0.02, 0.38), 0.025, 2), mat='Trim', shade='auto', angle=40)
    mb.add(bm_box_mm((-0.30, y - 0.12, 0.36), (0.30, y - 0.02, 0.39)), mat='Metal', shade='flat')
    for i in range(6):
        x = -0.25 + i * 0.1
        mb.add(bm_box_mm((x - 0.03, y - 0.118, 0.389), (x + 0.03, y - 0.03, 0.395)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.045, y - 0.20, 0.19), (0.045, y - 0.08, 0.26), 0.006), mat='Trim', shade='auto')
    mb.add(bm_cyl_between((-0.05, y - 0.17, 0.225), (0.05, y - 0.17, 0.225), 0.008, segs=6), mat='Metal', shade='flat')
    mb.add(bm_box_mm((-0.62, y - 0.104, 0.22), (-0.30, y - 0.096, 0.30), 0.004), mat='Decal', shade='auto')
    mb.add(bm_box_mm((-0.605, y - 0.106, 0.235), (-0.315, y - 0.10, 0.285)), mat='Trim', shade='flat')
    add_text(mb, 'LAND CRUISER', (-0.40, y - 0.004, 0.99), size=0.045, extrude=0.003, mat='Chrome', offset=0.001, facing=-1)
    # spare wheel on a door-mounted carrier (right door)
    cx, cy, cz = SPARE_C
    mb.add(bm_box_mm((cx - 0.16, y - 0.03, cz - 0.04), (cx + 0.16, y, cz + 0.04), 0.01), mat='Trim', shade='auto')
    mb.add(bm_box_mm((cx - 0.04, y - 0.03, cz - 0.30), (cx + 0.04, y, cz + 0.16), 0.01), mat='Trim', shade='auto')
    mb.add(bm_cyl_between((cx, y - 0.03, cz), (cx, cy + SPARE_W / 2 - 0.03, cz), 0.05, segs=8), mat='Trim', shade='auto')
    M = Matrix.Translation(SPARE_C) @ Matrix.Rotation(-math.pi / 2, 4, 'Z')
    add_wheel(mb, M, R=TYRE_R, W=SPARE_W, tire='Tire', rim='Rim', lugs=14, segs=16, style='steel')
    # ladder on the left door up to the rack
    for x in (-0.62, -0.30):
        tube(mb, (x, y - 0.06, 0.46), (x, y - 0.06, ROOF_Z + 0.26), 0.014, 'Trim')
        for z in (0.50, 1.30):
            tube(mb, (x, y - 0.06, z), (x, y, z), 0.012, 'Trim')
    for i in range(8):
        z = 0.56 + i * 0.13
        tube(mb, (-0.62, y - 0.06, z), (-0.30, y - 0.06, z), 0.011, 'Metal')
    # exhaust tip exits under the rear left
    tube(mb, (-0.30, -1.92, 0.33), (-0.30, -2.08, 0.16), 0.03, 'Metal', 8)
    tube(mb, (-0.30, -2.08, 0.16), (-0.30, -2.30, 0.14), 0.03, 'Metal', 8)
    # rear mud flaps
    for sx in (-1, 1):
        mb.add(bm_box_mm((min(sx * 0.70, sx * 0.97), -1.935, -0.18), (max(sx * 0.70, sx * 0.97), -1.92, 0.30), 0.004), mat='Rubber', shade='auto')


# ------------------------------------------------------------------ sides
def add_sides(mb):
    for sx in (-1, 1):
        # fender flares following the arches
        for yc, zr, zf in ((-AXLE_Y, OVERHANG_Z, ARCH_LEG_Z), (AXLE_Y, ARCH_LEG_Z, OVERHANG_Z)):
            outer = arch_poly(yc, FLARE_R, ARCH_ZC, zr - 0.06, zf - 0.06)
            inner = arch_poly(yc, ARCH_R, ARCH_ZC, zr - 0.06, zf - 0.06)[::-1]
            fl = C.bm_extrude_poly(outer + inner, FLARE_X - (HALF_W - 0.04), axis='X', center=sx * (FLARE_X + HALF_W - 0.04) / 2)
            fl.normal_update()
            oe = [e for e in fl.edges if all(abs(v.co.x) > FLARE_X - 0.005 for v in e.verts)]
            C.bevel(fl, 0.02, 1, oe)
            mb.add(fl, mat='Trim', shade='auto', angle=40)
        x = sx * (HALF_W + 0.001)
        # door seams (front door 0.86..-0.11, rear door -0.11..-1.02), bottom seam
        for y0, y1, z0, z1 in ((0.845, 0.857, 0.22, BELT_Z), (-0.118, -0.106, 0.22, BELT_Z), (-1.03, -1.018, 0.60, BELT_Z),
                               (-0.85, 0.857, 0.215, 0.227)):
            mb.add(bm_box_mm((x - 0.004, y0, z0), (x + 0.004, y1, z1)), mat='Trim', shade='flat')
        # hinges and handles
        for yh in (0.80, -0.16):
            for zh in (0.36, 0.74):
                mb.add(bm_box_mm((x - 0.012 * (sx < 0) - 0.002, yh - 0.035, zh - 0.03), (x + 0.012 * (sx > 0) + 0.002, yh + 0.03, zh + 0.03), 0.005), mat='Trim', shade='auto')
        for yh in (-0.02, -0.94):
            mb.add(bm_box_mm((x - 0.015 * (sx < 0), yh - 0.075, 0.755), (x + 0.015 * (sx > 0), yh + 0.005, 0.78), 0.006), mat='Chrome', shade='auto')
            mb.add(bm_box_mm((x - 0.004, yh - 0.08, 0.74), (x + 0.004, yh + 0.01, 0.795)), mat='Trim', shade='flat')
        # body side trim strip
        for y0, y1 in ((-2.08, -1.73), (-1.00, 1.00), (1.73, 1.93)):
            mb.add(bm_box_mm((x - 0.006 * (sx < 0), y0, 0.55), (x + 0.006 * (sx > 0), y1, 0.565)), mat='Trim', shade='flat')
        # fuel filler on the right rear quarter
        if sx > 0:
            mb.add(bm_cyl_between((x, -1.45, 0.74), (x + 0.012, -1.45, 0.74), 0.06, segs=12), mat='Paint', shade='auto')
            mb.add(bm_cyl_between((x + 0.004, -1.45, 0.74), (x + 0.014, -1.45, 0.74), 0.066, segs=12, cap=False), mat='Trim', shade='auto')
        # tube rock sliders / side steps with three brackets
        tube_path(mb, [(sx * 0.93, 0.78, 0.13), (sx * 0.95, 0.70, 0.10), (sx * 0.95, -0.80, 0.10), (sx * 0.93, -0.88, 0.13)], 0.035, 'Trim')
        mb.add(bm_box_mm((min(sx * 0.86, sx * 0.97), -0.70, 0.125), (max(sx * 0.86, sx * 0.97), 0.62, 0.14), 0.005), mat='Metal', shade='auto')
        for yb in (-0.6, 0.0, 0.55):
            mb.add(bm_box_mm((min(sx * 0.46, sx * 0.93), yb - 0.03, 0.08), (max(sx * 0.46, sx * 0.93), yb + 0.03, 0.12)), mat='Trim', shade='flat')
        # front mud flaps behind the front wheels
        mb.add(bm_box_mm((min(sx * 0.70, sx * 0.97), 0.835, -0.18), (max(sx * 0.70, sx * 0.97), 0.85, ARCH_LEG_Z)), mat='Rubber', shade='auto')
        # door mirrors on arms
        mb.add(bm_box_mm((x - 0.02 * (sx < 0) - 0.005, 0.70, BELT_Z - 0.02), (x + 0.02 * (sx > 0) + 0.005, 0.80, BELT_Z + 0.03), 0.008), mat='Trim', shade='auto')
        tube(mb, (sx * 0.91, 0.76, BELT_Z + 0.02), (sx * 1.05, 0.80, BELT_Z + 0.12), 0.012, 'Chrome')
        tube(mb, (sx * 0.91, 0.72, BELT_Z + 0.02), (sx * 1.05, 0.79, BELT_Z + 0.06), 0.009, 'Chrome')
        mb.add(bm_box((0.04, 0.10, 0.17), (sx * 1.07, 0.79, BELT_Z + 0.11), 0.014, 1, rot=(0, 0, sx * math.radians(-8))), mat='Trim', shade='auto')
        mb.add(bm_box((0.006, 0.085, 0.15), (sx * 1.07, 0.742, BELT_Z + 0.11), 0.0, 1, rot=(0, 0, sx * math.radians(-8))), mat='Glass', shade='flat')
    # snorkel on the left (-X) side, as in the reference photo: fender intake, A-pillar riser, mushroom head
    sx = -1
    mb.add(bm_box_mm((-HALF_W - 0.06, 0.93, 0.71), (-HALF_W + 0.01, 1.16, 0.86), 0.02, 2), mat='Trim', shade='auto', angle=40)
    tube_path(mb, [(-HALF_W - 0.035, 1.02, 0.84), (-HALF_W - 0.04, 0.93, BELT_Z + 0.06), (-0.915, 0.80, BELT_Z + 0.14),
                   (-0.885, 0.71, ROOF_Z - 0.02), (-0.88, 0.69, ROOF_Z + 0.10)], 0.045, 'Trim', 10)
    head = bm_lathe([(0.0, ROOF_Z + 0.10), (0.07, ROOF_Z + 0.10), (0.085, ROOF_Z + 0.13), (0.08, ROOF_Z + 0.19),
                     (0.05, ROOF_Z + 0.215), (0.0, ROOF_Z + 0.22)], 12, axis='Z')
    C.orient(head, lambda f: f.calc_center_median() - Vector((0, 0, ROOF_Z + 0.15)))
    mb.add(xform(head, Matrix.Translation((-0.88, 0.69, 0))), mat='Trim', shade='auto', angle=40)
    for zc in (ROOF_Z - 0.2, BELT_Z + 0.2):
        mb.add(bm_box_mm((-0.93, 0.745, zc - 0.015), (-0.86, 0.77, zc + 0.015)), mat='Metal', shade='flat')
    # antenna on the right front fender
    mb.add(bm_cyl_between((0.82, 1.62, BELT_Z + 0.01), (0.80, 1.58, BELT_Z + 1.05), 0.005, segs=4), mat='Trim', shade='flat')
    mb.add(bm_cyl(0.02, 0.014, 0.04, 6, Matrix.Translation((0.82, 1.62, BELT_Z - 0.01)), base=True), mat='Chrome', shade='auto')


# ------------------------------------------------------------------ chassis and underbody
def add_chassis(mb):
    lo0, lo1, hi0, hi1 = -0.03, 0.12, 0.33, 0.47
    for sx in (-1, 1):
        xa, xb = sorted((sx * RAIL_X0, sx * RAIL_X1))
        # mid section low, kicked up over both axles
        mb.add(bm_box_mm((xa, -0.60, lo0), (xb, 0.60, lo1)), mat='Trim', shade='flat')
        for s in (-1, 1):
            y0, y1 = s * 0.60, s * 0.92
            V = [(xa, y0, lo0), (xb, y0, lo0), (xb, y0, lo1), (xa, y0, lo1), (xa, y1, hi0), (xb, y1, hi0), (xb, y1, hi1), (xa, y1, hi1)]
            ramp = bm_from(V, [[0, 1, 2, 3], [4, 7, 6, 5], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]])
            bmesh.ops.recalc_face_normals(ramp, faces=ramp.faces)
            mb.add(ramp, mat='Trim', shade='flat')
            ye = 2.14 if s > 0 else -2.12
            mb.add(bm_box_mm((xa, min(y1, ye), hi0), (xb, max(y1, ye), hi1)), mat='Trim', shade='flat')
        # spring towers, upper seats, brackets to the rails and bump stops
        for yc in (-AXLE_Y, AXLE_Y):
            mb.add(bm_box_mm((sx * SPRING_X - 0.075, yc - 0.085, SPRING_TOP_Z + 0.012), (sx * SPRING_X + 0.075, yc + 0.085, 0.70), 0.012),
                   mat='Trim', shade='auto')
            mb.add(bm_cyl(0.078, 0.078, 0.012, 12, Matrix.Translation((sx * SPRING_X, yc, SPRING_TOP_Z)), base=True), mat='Metal', shade='auto')
            xs = sorted((sx * RAIL_X0, sx * (SPRING_X - 0.07)))
            mb.add(bm_box_mm((xs[0], yc - 0.06, hi1 - 0.02), (xs[1], yc + 0.06, SPRING_TOP_Z + 0.08)), mat='Trim', shade='flat')
            mb.add(bm_box_mm((sx * 0.42 - 0.03, yc - 0.03, 0.30), (sx * 0.42 + 0.03, yc + 0.03, hi0)), mat='Rubber', shade='flat')
    # cross members at the bumpers
    for y0, y1 in ((1.92, 2.0), (-2.0, -1.92)):
        mb.add(bm_box_mm((-RAIL_X1, y0, hi0 + 0.02), (RAIL_X1, y1, hi1 - 0.02)), mat='Trim', shade='flat')
    # transfer case (under the floor) with outputs at +-TCASE_Y
    mb.add(bm_box_mm((-0.15, -0.26, TCASE_Z - 0.10), (0.15, 0.26, SILL_Z + 0.01), 0.025), mat='Trim', shade='auto')
    for s in (-1, 1):
        mb.add(bm_cyl_between((0, s * 0.25, TCASE_Z), (0, s * TCASE_Y, TCASE_Z), 0.052, segs=8), mat='Metal', shade='auto')
    mb.add(bm_box_mm((-0.16, -0.05, TCASE_Z - 0.12), (-0.08, 0.05, TCASE_Z - 0.09)), mat='Metal', shade='flat')
    # engine sump and block visible from the front wheel wells
    mb.add(bm_box_mm((-0.28, 0.95, 0.46), (0.28, 1.88, 0.84), 0.03), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.20, 1.02, 0.44), (0.20, 1.60, 0.50), 0.02), mat='Metal', shade='auto')
    # exhaust: down pipe, under the floor, over the rear axle in the arch tunnel
    tube_path(mb, [(-0.30, 1.00, 0.48), (-0.30, 0.78, 0.07), (-0.30, -0.62, 0.07), (-0.30, -0.86, 0.36), (-0.30, -1.92, 0.36)], 0.03, 'Metal', 8)
    mb.add(bm_cyl_between((-0.30, -0.10, 0.07), (-0.30, -0.55, 0.07), 0.07, segs=10), mat='Metal', shade='auto', angle=50)
    # fuel tank between the rails
    mb.add(bm_box_mm((0.08, -0.86, -0.02), (0.35, -0.34, SILL_Z + 0.01), 0.025), mat='Trim', shade='auto')
    for yb in (-0.76, -0.44):
        mb.add(bm_box_mm((0.07, yb - 0.015, -0.03), (0.36, yb + 0.015, -0.015)), mat='Metal', shade='flat')
    # floor under-seal (dark) so the underside reads as chassis
    mb.add(bm_box_mm((-0.86, -0.36, SILL_Z - 0.01), (0.86, 0.36, SILL_Z + 0.005)), mat='Trim', shade='flat')


# ------------------------------------------------------------------ roof rack and cargo
def add_rack(mb):
    z0 = ROOF_Z + 0.035
    zb, zu = z0 + 0.08, z0 + 0.22
    xr, yf, yr = 0.80, 0.66, -2.02
    for x in (-0.76, 0.76):
        for y in (0.60, -0.30, -1.20, -1.96):
            mb.add(bm_box((0.05, 0.08, zb - z0 + 0.01), (x, y, (z0 + zb) / 2)), mat='Trim', shade='flat')
    for z in (zb, zu):
        for x in (-xr, xr):
            tube(mb, (x, yr, z), (x, yf - 0.04, z), 0.017)
        tube(mb, (-xr, yr, z), (xr, yr, z), 0.017)
    # front rail sweeps forward as a wind deflector
    tube_path(mb, [(-xr, yf - 0.04, zu), (-xr + 0.06, yf + 0.06, zb + 0.04), (xr - 0.06, yf + 0.06, zb + 0.04), (xr, yf - 0.04, zu)], 0.017)
    tube(mb, (-xr, yf - 0.04, zb), (xr, yf - 0.04, zb), 0.017)
    for i in range(12):
        y = yf - 0.12 - i * 0.215
        tube(mb, (-xr, y, zb), (xr, y, zb), 0.012)
    for x in (-0.3, 0.3):
        tube(mb, (x, yr, zb), (x, yf - 0.04, zb), 0.012)
    for x in (-xr, xr):
        for y in (yf - 0.04, 0.10, -0.46, -1.02, -1.58, yr):
            tube(mb, (x, y, zb), (x, y, zu), 0.013)
    zc = zb + 0.015
    # two big soft roof bags on the front half, strapped down
    for x0 in (-0.70, 0.04):
        bag = C.bm_hull([(x0 + dx, y, zc + dz) for dx in (0.0, 0.64) for y in (0.46, -0.52) for dz in (0.0,)]
                        + [(x0 + dx, y, zc + 0.27) for dx in (0.05, 0.59) for y in (0.40, -0.46)]
                        + [(x0 + 0.32, 0.43, zc + 0.30), (x0 + 0.32, -0.49, zc + 0.30)])
        C.bevel(bag, 0.05, 2)
        mb.add(bag, mat='Interior', shade='smooth')
        for y in (0.22, -0.28):
            strap = bm_box_mm((x0 - 0.01, y - 0.025, zc - 0.005), (x0 + 0.65, y + 0.025, zc + 0.31))
            mb.add(strap, mat='Rubber', shade='flat')
        mb.add(bm_box_mm((x0 + 0.05, 0.46, zc + 0.12), (x0 + 0.59, 0.475, zc + 0.14)), mat='Trim', shade='flat')
    # duffel bag, jerry cans, recovery boards, shovel on the rear half
    duf = bm_lathe([(0.0, -0.36), (0.10, -0.35), (0.155, -0.30), (0.165, 0.0), (0.155, 0.30), (0.10, 0.35), (0.0, 0.36)], 10, axis='X')
    C.orient(duf, lambda f: f.calc_center_median())
    mb.add(xform(duf, mat_trs((-0.38, -0.95, zc + 0.14), (0, 0, 0.05), (1, 1, 0.85))), mat='Interior', shade='smooth')
    for x in (0.18, 0.40):
        mb.add(bm_box_mm((x - 0.085, -1.56, zc), (x + 0.085, -1.22, zc + 0.46), 0.022, 2), mat='Canvas', shade='auto', angle=40)
        for dx in (-0.03, 0.0, 0.03):
            mb.add(bm_box_mm((x + dx - 0.008, -1.54, zc + 0.46), (x + dx + 0.008, -1.40, zc + 0.49)), mat='Canvas', shade='flat')
        mb.add(bm_box_mm((x - 0.03, -1.28, zc + 0.46), (x + 0.03, -1.24, zc + 0.50)), mat='Trim', shade='flat')
        mb.add(bm_box_mm((x - 0.087, -1.40, zc + 0.12), (x + 0.087, -1.36, zc + 0.34)), mat='Trim', shade='flat')
    for i, x in enumerate((-0.70, -0.56)):
        mb.add(bm_box_mm((x - 0.06, -1.95, zc + 0.02 + i * 0.03), (x + 0.06, -1.05, zc + 0.045 + i * 0.03), 0.01), mat='Board', shade='auto')
        for j in range(8):
            y = -1.9 + j * 0.11
            mb.add(bm_box_mm((x - 0.05, y - 0.02, zc + 0.045 + i * 0.03), (x + 0.05, y + 0.02, zc + 0.055 + i * 0.03)), mat='Trim', shade='flat')
    tube(mb, (0.70, -1.95, zc + 0.03), (0.70, -0.95, zc + 0.03), 0.016, 'Trim')
    mb.add(bm_box_mm((0.62, -0.97, zc + 0.02), (0.78, -0.68, zc + 0.04), 0.008), mat='Metal', shade='auto')
    # tarp roll across the back
    tarp = bm_cyl_between((-0.30, -1.80, zc + 0.09), (0.02, -1.80, zc + 0.09), 0.08, segs=10)
    mb.add(tarp, mat='Canvas', shade='smooth')


# ------------------------------------------------------------------ interior
def add_interior(mb):
    zf = BELT_Z - 0.06
    mb.add(bm_box_mm((-0.84, 0.54, zf), (0.84, 0.78, BELT_Z + 0.14), 0.03), mat='Interior', shade='auto')
    mb.add(bm_box_mm((-0.62, 0.52, BELT_Z + 0.04), (-0.20, 0.55, BELT_Z + 0.12), 0.01), mat='Trim', shade='auto')
    for x in (-0.52, -0.32):
        mb.add(bm_cyl_between((x, 0.515, BELT_Z + 0.08), (x, 0.53, BELT_Z + 0.08), 0.035, segs=10), mat='Chrome', shade='auto')
    for sx in (-1, 1):
        mb.add(bm_box_mm((sx * 0.42 - 0.24, -0.05, zf - 0.05), (sx * 0.42 + 0.24, 0.40, zf + 0.08), 0.035), mat='Interior', shade='auto')
        mb.add(bm_box((0.46, 0.12, 0.56), (sx * 0.42, -0.08, zf + 0.34), 0.035, 1, rot=(math.radians(-10), 0, 0)), mat='Interior', shade='auto')
        mb.add(bm_box((0.26, 0.08, 0.14), (sx * 0.42, -0.14, zf + 0.68), 0.03, 1), mat='Interior', shade='auto')
    mb.add(bm_box_mm((-0.80, -0.95, zf - 0.05), (0.80, -0.50, zf + 0.08), 0.035), mat='Interior', shade='auto')
    mb.add(bm_box((1.58, 0.12, 0.52), (0, -0.98, zf + 0.33), 0.035, 1, rot=(math.radians(-8), 0, 0)), mat='Interior', shade='auto')
    mb.add(bm_box_mm((-0.80, -2.05, zf - 0.02), (0.80, -1.10, zf + 0.02)), mat='Rubber', shade='flat')
    wheel = bm_lathe([(0.19 + 0.018 * math.cos(a), 0.018 * math.sin(a)) for a in [i * math.pi / 2 for i in range(5)]], 14, axis='Y')
    mb.add(xform(wheel, mat_trs((-0.42, 0.40, BELT_Z + 0.16), (math.radians(-28), 0, 0))), mat='Trim', shade='smooth')
    for a in (0.0, 2.1, 4.2):
        tube(mb, (-0.42, 0.40, BELT_Z + 0.16), (-0.42 + 0.18 * math.cos(a), 0.40 + 0.08 * math.sin(a), BELT_Z + 0.16 + 0.15 * math.sin(a)), 0.012)
    tube(mb, (-0.42, 0.40, BELT_Z + 0.16), (-0.42, 0.62, BELT_Z + 0.02), 0.024)
    tube(mb, (0.02, 0.30, zf + 0.02), (0.05, 0.22, zf + 0.32), 0.012, 'Chrome')
    tube(mb, (0.12, 0.30, zf + 0.02), (0.14, 0.24, zf + 0.25), 0.01, 'Chrome')


def build_body(mb):
    add_tub(mb)
    add_greenhouse(mb)
    add_front(mb)
    add_bumper_front(mb)
    add_rear(mb)
    add_sides(mb)
    add_chassis(mb)
    add_rack(mb)
    add_interior(mb)


# ------------------------------------------------------------------ assembly info (for the game)
DIMS = {
    'R': TYRE_R, 'W': TYRE_W, 'wheelbase': WHEELBASE, 'track_x': TRACK_X,
    'spring_x': SPRING_X, 'spring_top': SPRING_TOP_Z, 'spring_seat': SPRING_SEAT_Z,
    'pinion_y': PINION_Y, 'pinion_z': PINION_Z, 'tcase_y': TCASE_Y, 'tcase_z': TCASE_Z,
    # game: hardpoint 0.32, min length 0.13 (visual clamp -0.04), rest 0.45
    'bump': 0.23, 'droop': 0.13, 'lock': 30,
}

_BUMPER_Y = FRONT_Y + 0.235
LAMPS = {
    'head': [(-HEAD_X, FRONT_Y + 0.075, HEAD_Z), (HEAD_X, FRONT_Y + 0.075, HEAD_Z)],
    'fog': [(x, _BUMPER_Y + 0.03, 0.35) for x in (-0.76, -0.60, 0.60, 0.76)],
    'indicator': [(-0.815, FRONT_Y + 0.052, 0.645), (0.815, FRONT_Y + 0.052, 0.645)],
    'tail': [(-0.83, REAR_Y - 0.03, 0.52), (0.83, REAR_Y - 0.03, 0.52)],
    'brake': [(-0.83, REAR_Y - 0.03, 0.52), (0.83, REAR_Y - 0.03, 0.52)],
    'reverse': [(-0.83, REAR_Y - 0.03, 0.365), (0.83, REAR_Y - 0.03, 0.365)],
    'winch': [(0.0, _BUMPER_Y + 0.016, 0.33)],
    'hitch': [(0.0, REAR_Y - 0.20, 0.225)],
}


def main():
    C.reset_scene()
    mats = make_materials()
    col = C.collection('Vehicle')
    parts, tris = {}, {}
    builders = {
        'Body': build_body,
        'Wheel': lambda mb: add_wheel(mb, R=TYRE_R, W=TYRE_W, lugs=16, style='steel'),
        'AxleFront': lambda mb: P.add_axle(mb, True, TRACK_X, SPRING_X, PINION_Y, PINION_Z, detail=True),
        'AxleRear': lambda mb: P.add_axle(mb, False, TRACK_X, SPRING_X, PINION_Y, PINION_Z, detail=True),
        'Spring': P.add_spring,
        'Driveshaft': P.add_driveshaft,
    }
    for name, fn in builders.items():
        mb = C.MeshBuilder(name)
        fn(mb)
        tris[name] = mb.tris()
        parts[name] = mb.build(mats, vcolor=False, collection_obj=col)
    print('VEHICLE toyota TRIS', tris, 'total', sum(tris.values()))
    P.export_vehicle('toyota', parts, DIMS, LAMPS, tris)
    import vehicle_check
    vehicle_check.run(parts, dict(DIMS, id='toyota'))
    P.render_previews('toyota', parts, col, DIMS)
    # extra: the reference photo camera (low front-left three-quarter)
    rc = C.collection('Pose_ref')
    objs = P.assemble(parts, rc, DIMS, None)
    C.frame_camera(objs, az=-35, el=10, lens=55)
    C.render('toyota_ref_angle.png')
    rc.hide_render = True
    C.save_blend('vehicle_toyota.blend')
    return tris


if __name__ == '__main__':
    main()
