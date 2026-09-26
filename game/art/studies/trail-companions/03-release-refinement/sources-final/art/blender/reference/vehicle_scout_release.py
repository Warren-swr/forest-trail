"""Forest Trail vehicle "Scout": short-wheelbase boxy retro 4x4 (no real brand).

Blender coords: +Y front, +Z up, +X = vehicle right. Origin = midpoint between axles
at static wheel-centre height; ground is at Z = -0.38.
Exports vehicle_scout.glb (+ .json mounts/lamps) through vehicle_parts.export_vehicle.

Clearance layout (checked by vehicle_check across bump/droop/cross-axle/full lock):
- body-on-frame: rails at x +-0.30..0.38 kick up over the axles (rail bottom z 0.30,
  axle tube top at full bump z 0.266) with rubber bump stops;
- coil springs at x +-0.50 with towers x 0.425..0.575, inboard of the tyre sweep at lock;
- wheel-well liners are arch bands above z 0.30 (the axle passes underneath);
- a transmission tunnel is cut into the floor for the driveshafts, the gearbox sits high.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix, Euler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
from common import bm_box, bm_box_mm, bm_cyl, bm_cyl_between, bm_lathe, bm_from, xform, mat_trs
import vehicle_parts as P
from vehicle_parts import add_wheel

# ------------------------------------------------------------------ key dimensions
WHEELBASE = 2.50
AXLE_Y = WHEELBASE / 2          # front +1.25, rear -1.25
TRACK_X = 0.825                 # wheel centre X
TYRE_R, TYRE_W = 0.38, 0.30
GROUND_Z = -0.38
BODY_BOTTOM = 0.12              # 0.50 above ground
BELT_Z = 0.82
ROOF_Z = 1.50
HALF_W = 0.89
ARCH_R, ARCH_ZC = 0.465, 0.18   # wheel arch radius / centre height
FLARE_R, FLARE_X = 0.565, 0.99
SPRING_X = 0.50
SPRING_TOP_Z = 0.46             # upper spring seat (body coords)
SPRING_SEAT_Z = 0.06            # lower spring seat (axle-local coords)
PINION_Y, PINION_Z = 0.235, 0.03  # axle-local pinion yoke (front axle uses -Y)
TCASE_Y, TCASE_Z = 0.31, 0.10   # transfer case outputs (body coords, +/-Y)
RAIL_X0, RAIL_X1 = 0.30, 0.38   # frame rails (each side)
RAIL_LOW, RAIL_HIGH = 0.0, 0.30  # rail bottom between / over the axles
RAIL_H = 0.12
LINER_Z = 0.30                  # wheel-well liner lower edge
LINER_X = 0.40


def make_materials():
    m = P.base_materials('#B75B3D', '#E8DFC8', '#DCD4C0')
    m['Board'] = C.mat_pbr('Board', '#D9772B', 0.6, 0.0)      # recovery boards, jack
    m['Can'] = C.mat_pbr('Can', '#5B6644', 0.5, 0.2)          # jerry cans
    return m


def tube(mb, a, b, r=0.016, mat='Trim', segs=6):
    mb.add(bm_cyl_between(a, b, r, segs=segs, cap=False), mat=mat, shade='auto', angle=70)


def text(mb, s, size, M, mat='Decal', depth=0.008):
    mb.add(P.bm_text(s, size, depth, M), mat=mat, shade='flat')


# text planes: local X = reading direction, local Y = up, local Z = out of the panel
def side_frame(sx, loc):
    """Text on a side panel facing +X (sx=1) or -X (sx=-1), reading front-to-back as seen from outside."""
    if sx > 0:
        R = Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0))).to_4x4()
    else:
        R = Matrix(((0, 0, -1), (-1, 0, 0), (0, 1, 0))).to_4x4()
    return Matrix.Translation(loc) @ R


def rear_frame(loc):
    return Matrix.Translation(loc) @ Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0))).to_4x4()


def front_frame(loc):
    return Matrix.Translation(loc) @ Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0))).to_4x4()


# ------------------------------------------------------------------ body shell
def arch_pts(yc, r, zc, z0, steps=12, reverse=False):
    """Wheel-arch outline (Y,Z) going from rear leg over the top to the front leg."""
    pts = [(yc - r, z0), (yc - r, zc)]
    for i in range(1, steps):
        a = math.pi - math.pi * i / steps
        pts.append((yc + r * math.cos(a), zc + r * math.sin(a)))
    pts += [(yc + r, zc), (yc + r, z0)]
    return pts[::-1] if reverse else pts


def arch_band(yc, r, zc, zmin, steps=14):
    """Arch region above z = zmin (Y,Z polygon) for the wheel-well liners."""
    a0 = math.asin(max(-1.0, min(1.0, (zmin - zc) / r)))
    pts = []
    for i in range(steps + 1):
        a = math.pi - a0 - (math.pi - 2 * a0) * i / steps
        pts.append((yc + r * math.cos(a), zc + r * math.sin(a)))
    return pts


def in_arch(c):
    return any(abs(c.y - yc) < ARCH_R + 0.02 and c.z > BODY_BOTTOM + 0.01 and
               (Vector((c.y - yc, c.z - ARCH_ZC)).length < ARCH_R + 0.02 or c.z < ARCH_ZC + 0.02)
               for yc in (-AXLE_Y, AXLE_Y))


def add_tub(mb):
    b, t = BODY_BOTTOM, BELT_Z
    prof = [(-1.82, 0.24), (-1.77, b)]
    prof += arch_pts(-AXLE_Y, ARCH_R, ARCH_ZC, b)
    prof += arch_pts(AXLE_Y, ARCH_R, ARCH_ZC, b)
    prof += [(1.765, b), (1.80, 0.21), (1.80, t - 0.03), (1.775, t), (-1.795, t), (-1.82, t - 0.03)]
    bm = C.bm_extrude_poly(prof, 2 * HALF_W, axis='X')
    C.bevel(bm, 0.028, 2)
    # transmission tunnel for the driveshafts and gearbox (open from below)
    tunnel = bm_box_mm((-0.20, -(AXLE_Y - ARCH_R) - 0.02, BODY_BOTTOM - 0.05),
                       (0.20, (AXLE_Y - ARCH_R) + 0.02, 0.36))
    bm = P.bm_boolean(bm, [tunnel])
    bm.normal_update()

    def mat(f):
        c = f.calc_center_median()
        if abs(c.x) < 0.205 and c.z < 0.365 and abs(c.y) < AXLE_Y - ARCH_R + 0.03:
            return 'Trim'
        if f.normal.z < -0.9 and c.z < b + 0.01:
            return 'Trim'
        if abs(f.normal.x) < 0.5 and in_arch(c) and f.normal.z < 0.2 and abs(c.x) < HALF_W - 0.02:
            return 'Interior'
        return 'Paint'
    mb.add(bm, mat_fn=mat, shade='auto', angle=32)
    # wheel-well liners: arch bands above the axle travel so the tunnel does not show through
    for yc in (-AXLE_Y, AXLE_Y):
        band = arch_band(yc, ARCH_R + 0.005, ARCH_ZC, LINER_Z)
        for sx in (-1, 1):
            mb.add(C.bm_extrude_poly(band, 0.02, axis='X', center=sx * LINER_X), mat='Interior', shade='flat')
    # hood panel with a centre crease, cowl vent, hood latches and hinges
    mb.add(bm_box_mm((-0.84, 0.66, t - 0.01), (0.84, 1.76, t + 0.028), 0.012), mat='Paint', shade='auto')
    for sx in (-1, 1):
        mb.add(bm_box_mm((sx * 0.30 - 0.004, 0.70, t + 0.028), (sx * 0.30 + 0.004, 1.74, t + 0.034)), mat='Trim', shade='flat')
        mb.add(bm_box_mm((sx * 0.62 - 0.035, 1.735, t - 0.03), (sx * 0.62 + 0.035, 1.785, t + 0.035), 0.006), mat='Metal', shade='auto')
        mb.add(bm_box_mm((sx * 0.62 - 0.012, 1.775, t - 0.09), (sx * 0.62 + 0.012, 1.79, t - 0.02)), mat='Metal', shade='flat')
        mb.add(bm_cyl_between((sx * 0.58, 0.665, t + 0.03), (sx * 0.72, 0.665, t + 0.03), 0.014, segs=6), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.85, 0.50, t - 0.01), (0.85, 0.64, t + 0.035), 0.01), mat='Trim', shade='auto')
    for i in range(12):
        x = -0.55 + i * 0.1
        mb.add(bm_box_mm((x - 0.03, 0.53, t + 0.035), (x + 0.03, 0.61, t + 0.04)), mat='Rubber', shade='flat')
    # body side swage line, broken around the wheel arches
    gap = math.sqrt(ARCH_R ** 2 - (0.60 - ARCH_ZC) ** 2) + 0.03
    for sx in (-1, 1):
        for y0, y1 in ((-1.78, -AXLE_Y - gap), (-AXLE_Y + gap, AXLE_Y - gap), (AXLE_Y + gap, 1.76)):
            mb.add(bm_box_mm((sx * HALF_W - 0.004, y0, 0.59), (sx * HALF_W + 0.004, y1, 0.605)), mat='Paint', shade='auto')


def add_greenhouse(mb):
    zb, zt = BELT_Z, ROOF_Z
    xb, xt = 0.87, 0.81
    st = [(0.56, 0.40), (-0.36, -0.38), (-1.12, -1.14), (-1.80, -1.77)]
    V = []
    for yb, yt in st:
        V += [(-xb, yb, zb), (xb, yb, zb), (xt, yt, zt), (-xt, yt, zt)]
    F = [[0, 1, 2, 3][::-1], [12, 13, 14, 15]]            # front, rear
    for i in range(3):
        a, n = 4 * i, 4 * (i + 1)
        F += [[a + 1, n + 1, n + 2, a + 2], [a, a + 3, n + 3, n], [a + 3, a + 2, n + 2, n + 3], [a, n, n + 1, a + 1]]
    bm = bm_from(V, F)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bottom = [f for f in bm.faces if f.normal.z < -0.9]
    edges = [e for e in bm.edges if not any(f in bottom for f in e.link_faces)]
    res = C.bevel(bm, 0.03, 2, edges)
    new = set(res.get('faces', []))
    bm.normal_update()
    wins = [f for f in bm.faces if f not in new and abs(f.normal.z) < 0.5 and f.calc_area() > 0.05]
    roof = [f for f in bm.faces if f not in new and f.normal.z > 0.9]
    kill = [f for f in bm.faces if f.normal.z < -0.9]
    bmesh.ops.delete(bm, geom=kill, context='FACES_ONLY')
    # window: painted frame -> black rubber gasket -> recessed glass
    ins = bmesh.ops.inset_individual(bm, faces=wins, thickness=0.045, depth=0.0)
    ring1 = set(ins['faces'])
    ins2 = bmesh.ops.inset_individual(bm, faces=wins, thickness=0.016, depth=-0.016)
    rubber = set(ins2['faces'])
    glass = set(wins)
    roofs = set(roof)
    mb.add(bm, mat_fn=lambda f: 'Glass' if f in glass else ('Rubber' if f in rubber else
                                                           ('PaintAccent' if f in roofs else 'Paint')),
           shade='auto', angle=32)
    # roof skin with drip rails (rain gutters) along both sides
    mb.add(bm_box_mm((-xt - 0.025, -1.80, zt - 0.02), (xt + 0.025, 0.43, zt + 0.03), 0.02, 2),
           mat='PaintAccent', shade='auto', angle=40)
    for sx in (-1, 1):
        mb.add(bm_box_mm((sx * (xt + 0.022) - 0.012, -1.79, zt - 0.045), (sx * (xt + 0.022) + 0.012, 0.42, zt - 0.02), 0.004),
               mat='Paint', shade='auto')
    # windscreen frame hinges + wipers parked at the bottom of the screen
    wy = lambda z: 0.56 - 0.16 * (z - zb) / (zt - zb)
    n = Vector((0, 0.973, 0.229))
    for x0 in (-0.52, 0.10):
        p0 = Vector((x0 + 0.34, wy(0.87), 0.87)) + n * 0.02
        p1 = Vector((x0 - 0.02, wy(0.93), 0.93)) + n * 0.02
        mb.add(bm_cyl_between(p0 - n * 0.02, p0 + n * 0.005, 0.014, segs=6), mat='Trim', shade='auto')
        tube(mb, p0, p1, 0.007, 'Trim', 4)
        q0 = p0 + (p1 - p0) * 0.1 + n * 0.008
        q1 = p1 + (p1 - p0) * 0.05 + n * 0.008
        mb.add(bm_cyl_between(q0, q1, 0.006, segs=4), mat='Rubber', shade='flat')
    for sx in (-1, 1):
        mb.add(bm_box_mm((sx * 0.62 - 0.05, wy(zt) - 0.02, zt - 0.03), (sx * 0.62 + 0.05, wy(zt) + 0.02, zt + 0.01), 0.005),
               mat='Trim', shade='auto')
    return st


def headlight(mb, cx, cz, y):
    """Round headlight in a square black bezel: chrome ring, reflector bowl, lens."""
    mb.add(bm_box_mm((cx - 0.14, y - 0.01, cz - 0.14), (cx + 0.14, y + 0.018, cz + 0.14), 0.012), mat='Trim', shade='auto')
    bez = bm_lathe([(0.121, y + 0.012), (0.123, y + 0.046), (0.104, y + 0.060), (0.094, y + 0.054)], 20, axis='Y')
    C.orient(bez, lambda f: Vector((0, 0.6, 0)) + Vector((f.calc_center_median().x, 0, f.calc_center_median().z)))
    mb.add(xform(bez, Matrix.Translation((cx, 0, cz))), mat='Chrome', shade='auto', angle=50)
    refl = bm_lathe([(0.093, y + 0.052), (0.075, y + 0.036), (0.03, y + 0.024), (0.0, y + 0.022)], 16, axis='Y')
    C.orient(refl, lambda f: (0, 1, 0))
    mb.add(xform(refl, Matrix.Translation((cx, 0, cz))), mat='Metal', shade='smooth')
    lens = bm_lathe([(0.092, y + 0.052), (0.07, y + 0.066), (0.0, y + 0.073)], 16, axis='Y')
    C.orient(lens, lambda f: (0, 1, 0))
    mb.add(xform(lens, Matrix.Translation((cx, 0, cz))), mat='Lamp', shade='smooth')
    # lens flutes (subtle ribs)
    for i in (-1, 0, 1):
        mb.add(bm_box_mm((cx - 0.06, y + 0.066, cz + i * 0.03 - 0.002), (cx + 0.06, y + 0.071, cz + i * 0.03 + 0.002)), mat='Lamp', shade='flat')


def add_front(mb):
    y = 1.80
    # grille: dark mesh backing, surround, chrome horizontal bars and two vertical dividers
    mb.add(bm_box_mm((-0.47, y - 0.02, 0.38), (0.47, y + 0.006, 0.76)), mat='Trim', shade='flat')
    for i in range(9):
        x = -0.40 + i * 0.1
        mb.add(bm_box_mm((x - 0.004, y + 0.004, 0.40), (x + 0.004, y + 0.012, 0.74)), mat='Rubber', shade='flat')
    for i in range(6):
        z = 0.42 + i * 0.066
        mb.add(bm_box_mm((-0.44, y + 0.004, z - 0.004), (0.44, y + 0.012, z + 0.004)), mat='Rubber', shade='flat')
    for i in range(5):
        z = 0.43 + i * 0.07
        mb.add(bm_box_mm((-0.44, y + 0.01, z - 0.014), (0.44, y + 0.034, z + 0.014), 0.006), mat='Chrome', shade='auto')
    for x in (-0.15, 0.15):
        mb.add(bm_box_mm((x - 0.012, y + 0.012, 0.39), (x + 0.012, y + 0.04, 0.75), 0.004), mat='Metal', shade='auto')
    for x0, x1, z0, z1 in ((-0.49, 0.49, 0.36, 0.39), (-0.49, 0.49, 0.75, 0.78), (-0.49, -0.46, 0.36, 0.78), (0.46, 0.49, 0.36, 0.78)):
        mb.add(bm_box_mm((x0, y, z0), (x1, y + 0.035, z1), 0.006), mat='Paint', shade='auto')
    # badge plate on the top grille bar
    mb.add(bm_box_mm((-0.13, y + 0.035, 0.752), (0.13, y + 0.042, 0.778), 0.003), mat='Trim', shade='auto')
    text(mb, 'SCOUT', 0.022, front_frame((0, y + 0.044, 0.757)), depth=0.004)
    for sx in (-1, 1):
        headlight(mb, sx * 0.665, 0.60, y)
        # amber indicator under each headlight with a chrome rim
        mb.add(bm_box_mm((sx * 0.665 - 0.078, y - 0.004, 0.398), (sx * 0.665 + 0.078, y + 0.028, 0.452), 0.008), mat='Chrome', shade='auto')
        mb.add(bm_box_mm((sx * 0.665 - 0.066, y + 0.02, 0.405), (sx * 0.665 + 0.066, y + 0.036, 0.445), 0.006), mat='LampAmber', shade='auto')
    add_front_bumper(mb)


def add_front_bumper(mb):
    # tube-end steel bumper with winch cradle, fairlead, D-rings, number plate and underbody guard
    mb.add(bm_box_mm((-0.94, 1.82, 0.17), (0.94, 1.98, 0.38), 0.03, 2), mat='Metal', shade='auto', angle=40)
    for sx in (-1, 1):
        mb.add(bm_cyl_between((sx * 0.94, 1.90, 0.17), (sx * 0.94, 1.90, 0.38), 0.08, segs=10), mat='Metal', shade='auto', angle=40)
        # hoops up to the headlight guard
        tube(mb, (sx * 0.52, 1.95, 0.38), (sx * 0.52, 1.96, 0.62), 0.024, 'Trim', 8)
    tube(mb, (-0.52, 1.96, 0.62), (0.52, 1.96, 0.62), 0.024, 'Trim', 8)
    for x in (-0.24, 0.24):
        tube(mb, (x, 1.955, 0.38), (x, 1.96, 0.62), 0.018, 'Trim', 8)
    mb.add(bm_box_mm((-0.40, 1.80, 0.12), (0.40, 1.83, 0.36)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.36, 1.84, 0.38), (0.36, 1.97, 0.40)), mat='Metal', shade='flat')
    # winch: motor, drum with cable wraps, gearbox, control box
    mb.add(bm_cyl_between((-0.34, 1.915, 0.47), (-0.16, 1.915, 0.47), 0.072, segs=12), mat='Trim', shade='auto', angle=50)
    for i in range(3):
        x = -0.32 + i * 0.07
        mb.add(bm_cyl_between((x - 0.006, 1.915, 0.47), (x + 0.006, 1.915, 0.47), 0.076, segs=12), mat='Metal', shade='auto', angle=50)
    mb.add(bm_cyl_between((-0.16, 1.915, 0.47), (0.15, 1.915, 0.47), 0.05, segs=12), mat='Trim', shade='auto', angle=50)
    for x in (-0.13, -0.08, -0.03, 0.02, 0.07, 0.12):
        mb.add(bm_cyl_between((x - 0.02, 1.915, 0.47), (x + 0.02, 1.915, 0.47), 0.058, segs=12), mat='Metal', shade='auto', angle=50)
    mb.add(bm_box_mm((0.15, 1.85, 0.40), (0.29, 1.98, 0.55), 0.012), mat='Trim', shade='auto')
    mb.add(bm_box_mm((0.17, 1.86, 0.55), (0.27, 1.95, 0.60), 0.01), mat='Trim', shade='auto')
    mb.add(bm_cyl_between((0.22, 1.90, 0.60), (0.22, 1.90, 0.63), 0.012, segs=6), mat='Rubber', shade='auto')
    # hawse fairlead + hook
    mb.add(bm_box_mm((-0.14, 1.978, 0.25), (0.14, 2.0, 0.36), 0.01), mat='Metal', shade='auto')
    mb.add(bm_box_mm((-0.085, 1.998, 0.285), (0.085, 2.004, 0.325)), mat='Rubber', shade='flat')
    hook = bm_lathe([(0.024 + 0.008 * math.cos(a), 0.008 * math.sin(a)) for a in [i * math.pi / 3 for i in range(7)]], 10, axis='X')
    mb.add(xform(hook, Matrix.Translation((0, 2.015, 0.27))), mat='Chrome', shade='smooth')
    mb.add(bm_cyl_between((0, 2.004, 0.305), (0, 2.012, 0.29), 0.008, segs=5), mat='Metal', shade='flat')
    # number plate
    mb.add(bm_box_mm((-0.58, 1.978, 0.205), (-0.24, 1.99, 0.30), 0.004), mat='Decal', shade='auto')
    text(mb, 'FT 1972', 0.05, front_frame((-0.41, 1.992, 0.232)), mat='Trim', depth=0.004)
    # D-ring shackles on tabs
    for sx in (-1, 1):
        ring = bm_lathe([(0.036 + 0.011 * math.cos(a), 0.011 * math.sin(a))
                         for a in [i * math.pi / 3 for i in range(7)]], 10, axis='X')
        C.orient(ring, lambda f: (lambda c: c - Vector((0, c.y, c.z)).normalized() * 0.036)(f.calc_center_median()))
        mb.add(xform(ring, Matrix.Translation((sx * 0.72, 2.03, 0.26))), mat='Paint', shade='smooth')
        mb.add(bm_box_mm((sx * 0.72 - 0.035, 1.97, 0.24), (sx * 0.72 + 0.035, 2.02, 0.30)), mat='Metal', shade='flat')
    # skid plate under the front overhang
    mb.add(bm_box_mm((-0.40, 1.60, 0.14), (0.40, 1.84, 0.16), 0.006), mat='Metal', shade='auto')


def add_rear(mb):
    y = -1.82
    for sx in (-1, 1):
        x = sx * 0.78
        # tail cluster: chrome surround, red tail/brake, amber, white reverse
        mb.add(bm_box_mm((x - 0.085, y - 0.014, 0.35), (x + 0.085, y + 0.01, 0.71), 0.01), mat='Chrome', shade='auto')
        mb.add(bm_box_mm((x - 0.068, y - 0.026, 0.52), (x + 0.068, y - 0.004, 0.69), 0.008), mat='LampRear', shade='auto')
        mb.add(bm_box_mm((x - 0.068, y - 0.026, 0.44), (x + 0.068, y - 0.004, 0.505), 0.006), mat='LampAmber', shade='auto')
        mb.add(bm_box_mm((x - 0.068, y - 0.026, 0.37), (x + 0.068, y - 0.004, 0.425), 0.006), mat='LampReverse', shade='auto')
        for z in (0.605,):
            mb.add(bm_box_mm((x - 0.066, y - 0.03, z - 0.003), (x + 0.066, y - 0.024, z + 0.003)), mat='LampRear', shade='flat')
        # rear tow loops under the bumper
        loop = bm_lathe([(0.03 + 0.01 * math.cos(a), 0.01 * math.sin(a)) for a in [i * math.pi / 3 for i in range(7)]], 10, axis='Y')
        mb.add(xform(loop, Matrix.Translation((sx * 0.62, -1.975, 0.13))), mat='Metal', shade='smooth')
        # mud flaps behind the rear wheels
        mb.add(bm_box_mm((min(sx * 0.66, sx * 0.90), -1.745, -0.16), (max(sx * 0.66, sx * 0.90), -1.73, BODY_BOTTOM + 0.02), 0.006),
               mat='Rubber', shade='auto')
    # rear bumper, hitch receiver with pin, number plate
    mb.add(bm_box_mm((-0.93, -1.96, 0.14), (0.93, -1.815, 0.32), 0.025, 2), mat='Metal', shade='auto', angle=40)
    for x in (-0.93, 0.93):
        mb.add(bm_box_mm((x - 0.02, -1.965, 0.14), (x + 0.02, -1.80, 0.32), 0.01), mat='Rubber', shade='auto')
    mb.add(bm_box_mm((-0.045, -2.03, 0.19), (0.045, -1.95, 0.26), 0.006), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.03, -2.031, 0.205), (0.03, -2.02, 0.245)), mat='Rubber', shade='flat')
    mb.add(bm_cyl_between((-0.07, -1.995, 0.225), (0.07, -1.995, 0.225), 0.007, segs=6), mat='Chrome', shade='flat')
    mb.add(bm_box_mm((0.30, -1.972, 0.18), (0.64, -1.96, 0.28), 0.004), mat='Decal', shade='auto')
    text(mb, 'FT 1972', 0.05, rear_frame((0.47, -1.974, 0.207)), mat='Trim', depth=0.004)
    mb.add(bm_box_mm((0.40, -1.975, 0.285), (0.54, -1.962, 0.3)), mat='LampReverse', shade='flat')
    # tailgate: seams, hinges on the left, handle, badge
    for x in (-0.70, 0.70):
        mb.add(bm_box_mm((x - 0.006, y - 0.004, 0.18), (x + 0.006, y + 0.002, 0.80)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.70, y - 0.004, 0.18), (0.70, y + 0.002, 0.192)), mat='Trim', shade='flat')
    for z in (0.28, 0.70):
        mb.add(bm_box_mm((-0.715, y - 0.02, z - 0.04), (-0.66, y + 0.002, z + 0.04), 0.006), mat='Trim', shade='auto')
        mb.add(bm_cyl_between((-0.705, y - 0.022, z - 0.045), (-0.705, y - 0.022, z + 0.045), 0.009, segs=6), mat='Metal', shade='auto')
    mb.add(bm_box_mm((0.46, y - 0.02, 0.73), (0.60, y, 0.76), 0.006), mat='Chrome', shade='auto')
    mb.add(bm_cyl_between((0.62, y, 0.745), (0.62, y - 0.012, 0.745), 0.012, segs=8), mat='Chrome', shade='auto')
    text(mb, 'SCOUT', 0.055, rear_frame((-0.54, y - 0.004, 0.26)), mat='Chrome', depth=0.006)
    # spare wheel on a swing-out carrier (outer face toward -Y) with a centre cap
    mb.add(bm_box_mm((-0.16, -1.86, 0.54), (0.16, -1.815, 0.86), 0.012), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.05, -1.87, 0.30), (0.05, -1.83, 0.56)), mat='Trim', shade='flat')
    M = Matrix.Translation((0, -1.87 - 0.155, 0.70)) @ Matrix.Rotation(-math.pi / 2, 4, 'Z')
    add_wheel(mb, M, tire='Tire', rim='PaintAccent', lugs=13, segs=16, sidewall_lugs=13)
    # rear ladder on the right, clear of the spare and the tail lamps
    for x in (0.45, 0.63):
        tube(mb, (x, -1.87, 0.34), (x, -1.87, ROOF_Z - 0.02), 0.014, 'Trim', 6)
        for z in (0.45, 1.35):
            tube(mb, (x, -1.87, z), (x, y + 0.002, z), 0.01, 'Trim', 6)
    tube(mb, (0.45, -1.87, ROOF_Z - 0.02), (0.45, -1.72, ROOF_Z + 0.2), 0.014, 'Trim', 6)
    tube(mb, (0.63, -1.87, ROOF_Z - 0.02), (0.63, -1.72, ROOF_Z + 0.2), 0.014, 'Trim', 6)
    for i in range(8):
        z = 0.42 + i * 0.13
        tube(mb, (0.45, -1.872, z), (0.63, -1.872, z), 0.011, 'Metal', 6)


def add_sides(mb):
    for sx in (-1, 1):
        # fender flares (black plastic) with bolt heads, following the arches
        for yc in (-AXLE_Y, AXLE_Y):
            outer = arch_pts(yc, FLARE_R, ARCH_ZC, 0.10)
            inner = arch_pts(yc, ARCH_R, ARCH_ZC, 0.10, reverse=True)
            fl = C.bm_extrude_poly(outer + inner, FLARE_X - 0.855, axis='X', center=sx * (FLARE_X + 0.855) / 2)
            fl.normal_update()
            outer_edges = [e for e in fl.edges if all(abs(v.co.x) > FLARE_X - 0.005 for v in e.verts)]
            C.bevel(fl, 0.018, 1, outer_edges)
            mb.add(fl, mat='Trim', shade='auto', angle=40)
            for i in range(7):
                a = math.pi * (0.08 + 0.84 * i / 6)
                r = (ARCH_R + FLARE_R) / 2
                p = (sx * (FLARE_X + 0.001), yc + r * math.cos(a), ARCH_ZC + r * math.sin(a))
                mb.add(bm_cyl_between(p, (p[0] + sx * 0.008, p[1], p[2]), 0.009, segs=6), mat='Metal', shade='flat')
        x = sx * (HALF_W + 0.001)
        # door shut lines
        for y0, y1, z0, z1 in ((0.555, 0.567, 0.17, BELT_Z), (-0.372, -0.36, 0.17, BELT_Z), (-0.372, 0.567, 0.17, 0.182)):
            mb.add(bm_box_mm((x - 0.004, y0, z0), (x + 0.004, y1, z1)), mat='Trim', shade='flat')
        # exposed door hinges on the front edges of both doors
        for yh in (0.585,):
            for z in (0.30, 0.68):
                mb.add(bm_box_mm((min(x, x + sx * 0.022), yh - 0.03, z - 0.045), (max(x, x + sx * 0.022), yh + 0.03, z + 0.045), 0.006),
                       mat='Trim', shade='auto')
                mb.add(bm_cyl_between((x + sx * 0.02, yh + 0.03, z - 0.05), (x + sx * 0.02, yh + 0.03, z + 0.05), 0.008, segs=6),
                       mat='Metal', shade='auto')
        # door handles with key locks (front door and rear door)
        for yh in (-0.24,):
            mb.add(bm_box_mm((min(x, x + sx * 0.022), yh - 0.07, 0.70), (max(x, x + sx * 0.022), yh + 0.07, 0.728), 0.006), mat='Chrome', shade='auto')
            mb.add(bm_cyl_between((x, yh + 0.1, 0.714), (x + sx * 0.012, yh + 0.1, 0.714), 0.011, segs=8), mat='Chrome', shade='auto')
        # side marker / repeater lamp on the front fender
        mb.add(bm_box_mm((min(x, x + sx * 0.014), 1.62, 0.66), (max(x, x + sx * 0.014), 1.70, 0.69), 0.004), mat='LampAmber', shade='auto')
        # badge on the front fender
        text(mb, 'SCOUT', 0.05, side_frame(sx, (x + sx * 0.002, 1.50, 0.745)), mat='Chrome', depth=0.006)
        # cream double pinstripe from the tailgate to the door front
        for z in (0.775, 0.795):
            mb.add(bm_box_mm((min(x, x + sx * 0.004), -1.80, z - 0.006), (max(x, x + sx * 0.004), 0.54, z + 0.006)), mat='PaintAccent', shade='flat')
        # sliding-window divider in the rear side window
        mb.add(bm_box_mm((sx * 0.842 - 0.012, -0.755, BELT_Z + 0.06), (sx * 0.842 + 0.012, -0.735, ROOF_Z - 0.07)), mat='Rubber', shade='auto')
        # tube rock sliders with three frame brackets
        tube(mb, (sx * 0.90, -0.76, 0.06), (sx * 0.90, 0.72, 0.06), 0.045, 'Trim', 8)
        tube(mb, (sx * 0.72, -0.76, 0.03), (sx * 0.72, 0.72, 0.03), 0.035, 'Trim', 8)
        for y in ((-0.70, 0.0, 0.66) if sx > 0 else (-0.70, 0.66)):   # left middle bracket would cross the muffler
            mb.add(bm_box_mm((min(sx * RAIL_X1, sx * 0.90), y - 0.03, 0.02), (max(sx * RAIL_X1, sx * 0.90), y + 0.03, 0.08)), mat='Trim', shade='flat')
        for y in (-0.76, 0.72):
            tube(mb, (sx * 0.72, y, 0.03), (sx * 0.90, y, 0.06), 0.035, 'Trim', 8)
        # mud flaps behind the front wheels
        mb.add(bm_box_mm((min(sx * 0.66, sx * 0.90), 0.735, -0.14), (max(sx * 0.66, sx * 0.90), 0.75, BODY_BOTTOM + 0.02), 0.006),
               mat='Rubber', shade='auto')
        # mirrors: arm + head with glass
        tube(mb, (sx * 0.875, 0.50, 0.86), (sx * 0.99, 0.47, 0.95), 0.012, 'Trim', 5)
        mb.add(bm_box((0.035, 0.10, 0.15), (sx * 1.005, 0.465, 0.98), 0.012), mat='Chrome', shade='auto')
        mb.add(bm_box((0.02, 0.085, 0.13), (sx * 1.005, 0.465 - 0.012, 0.98), 0.006), mat='Glass', shade='auto')
    # fuel filler on the left rear quarter
    mb.add(bm_cyl_between((-HALF_W, -1.45, 0.66), (-HALF_W - 0.012, -1.45, 0.66), 0.06, segs=12), mat='Chrome', shade='auto')
    mb.add(bm_cyl_between((-HALF_W - 0.012, -1.45, 0.66), (-HALF_W - 0.022, -1.45, 0.66), 0.042, segs=12), mat='Metal', shade='auto')
    # snorkel on the right (+X) side with clamps
    mb.add(bm_box_mm((0.885, 0.58, 0.44), (0.935, 0.74, 0.80), 0.015), mat='Trim', shade='auto')
    mb.add(bm_cyl_between((0.915, 0.64, 0.78), (0.868, 0.465, 1.58), 0.04, segs=10), mat='Trim', shade='auto', angle=50)
    for t in (0.2, 0.55, 0.85):
        p = Vector((0.915, 0.64, 0.78)).lerp(Vector((0.868, 0.465, 1.58)), t)
        d = (Vector((0.868, 0.465, 1.58)) - Vector((0.915, 0.64, 0.78))).normalized()
        mb.add(bm_cyl_between(p - d * 0.012, p + d * 0.012, 0.047, segs=10), mat='Metal', shade='auto')
    mb.add(bm_box((0.11, 0.17, 0.11), (0.866, 0.49, 1.61), 0.02, 1, rot=(math.radians(-8), 0, 0)), mat='Trim', shade='auto')
    mb.add(bm_box((0.09, 0.006, 0.07), (0.866, 0.574, 1.60), 0.0, 1, rot=(math.radians(-8), 0, 0)), mat='Rubber', shade='flat')
    # antenna (left front fender) with base spring
    mb.add(bm_cyl_between((-0.86, 1.62, 0.84), (-0.86, 1.58, 1.95), 0.006, segs=4), mat='Trim', shade='flat')
    mb.add(bm_cyl(0.02, 0.014, 0.04, 6, Matrix.Translation((-0.86, 1.62, 0.82)), base=True), mat='Trim', shade='auto')
    mb.add(bm_cyl(0.012, 0.012, 0.06, 6, Matrix.Translation((-0.86, 1.619, 0.86)), base=True), mat='Chrome', shade='auto')


def rail_profile():
    """Frame rail side profile (Y, Z): low between the axles, kicked up over them."""
    lo, hi, h = RAIL_LOW, RAIL_HIGH, RAIL_H
    y0, y1 = 0.52, 0.80          # start / end of the kick-up
    bot = [(-1.84, hi), (-y1, hi), (-y0, lo), (y0, lo), (y1, hi), (1.84, hi)]
    top = [(1.84, hi + h), (y1 - 0.02, hi + h), (y0 - 0.02, lo + h), (-(y0 - 0.02), lo + h), (-(y1 - 0.02), hi + h), (-1.84, hi + h)]
    return bot + top


def add_chassis(mb):
    xc = (RAIL_X0 + RAIL_X1) / 2
    for sx in (-1, 1):
        rail = C.bm_extrude_poly(rail_profile(), RAIL_X1 - RAIL_X0, axis='X', center=sx * xc)
        mb.add(rail, mat='Trim', shade='auto', angle=30)
        for yc in (-AXLE_Y, AXLE_Y):
            # coil spring tower with upper seat, gusset to the rail
            mb.add(bm_box_mm((sx * SPRING_X - 0.075, yc - 0.085, SPRING_TOP_Z + 0.01), (sx * SPRING_X + 0.075, yc + 0.085, 0.66), 0.012),
                   mat='Trim', shade='auto')
            mb.add(bm_cyl(0.078, 0.078, 0.012, 12, Matrix.Translation((sx * SPRING_X, yc, SPRING_TOP_Z)), base=True), mat='Metal', shade='auto')
            mb.add(bm_box_mm((min(sx * RAIL_X1, sx * (SPRING_X - 0.075)), yc - 0.05, RAIL_HIGH + RAIL_H),
                             (max(sx * RAIL_X1, sx * (SPRING_X - 0.075)), yc + 0.05, 0.60)), mat='Trim', shade='flat')
            # rubber bump stop under the rail, above the axle tube
            mb.add(bm_box_mm((sx * xc - 0.035, yc - 0.035, RAIL_HIGH - 0.022), (sx * xc + 0.035, yc + 0.035, RAIL_HIGH)), mat='Rubber', shade='auto')
            # radius-arm / link mounts under the rail ahead of each axle (toward the centre)
            ym = yc - math.copysign(0.62, yc)
            mb.add(bm_box_mm((sx * xc - 0.04, ym - 0.05, -0.06), (sx * xc + 0.04, ym + 0.05, 0.02)), mat='Trim', shade='flat')
    # crossmembers: front and rear at the raised rail height, one under the transfer case
    for y0, y1 in ((1.74, 1.83), (-1.83, -1.74)):
        mb.add(bm_box_mm((-RAIL_X0, y0, RAIL_HIGH), (RAIL_X0, y1, RAIL_HIGH + RAIL_H)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-RAIL_X1, -0.07, -0.035), (RAIL_X1, 0.07, 0.0)), mat='Trim', shade='flat')
    # transfer case + outputs (driveshafts connect at (0, +-TCASE_Y, TCASE_Z)), high gearbox, engine block
    mb.add(bm_box_mm((-0.14, -0.27, 0.00), (0.14, 0.27, 0.22), 0.025), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.10, -0.20, -0.012), (0.10, 0.20, 0.0)), mat='Metal', shade='flat')
    for s in (-1, 1):
        mb.add(bm_cyl_between((0, s * 0.26, TCASE_Z), (0, s * TCASE_Y, TCASE_Z), 0.05, segs=8), mat='Metal', shade='auto')
    mb.add(bm_cyl_between((0.0, 0.26, 0.33), (0.0, 0.80, 0.42), 0.10, r2=0.12, segs=12), mat='Trim', shade='auto', angle=50)
    mb.add(bm_box_mm((-0.24, 0.84, 0.44), (0.24, 1.62, 0.66), 0.03), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.16, 0.90, 0.40), (0.16, 1.20, 0.44), 0.01), mat='Metal', shade='auto')
    # steering box on the left rail
    mb.add(bm_box_mm((-RAIL_X1 - 0.10, 1.52, RAIL_HIGH + 0.02), (-RAIL_X1, 1.68, RAIL_HIGH + 0.12), 0.01), mat='Metal', shade='auto')
    # fuel tank beside the tunnel (right) with skid plate
    mb.add(bm_box_mm((0.42, -0.62, 0.02), (0.74, 0.10, BODY_BOTTOM), 0.02), mat='Trim', shade='auto')
    mb.add(bm_box_mm((0.40, -0.64, 0.0), (0.76, 0.12, 0.02), 0.005), mat='Metal', shade='auto')
    # exhaust: down-pipe from the engine, muffler under the left floor, side exit ahead of the rear wheel
    tube(mb, (-0.12, 0.84, 0.46), (-0.53, 0.58, 0.07), 0.028, 'Metal', 8)
    tube(mb, (-0.53, 0.58, 0.07), (-0.53, 0.50, 0.06), 0.028, 'Metal', 8)
    mb.add(bm_cyl_between((-0.53, 0.50, 0.06), (-0.53, -0.30, 0.06), 0.06, segs=10), mat='Metal', shade='auto', angle=50)
    tube(mb, (-0.53, -0.30, 0.06), (-0.62, -0.50, 0.05), 0.028, 'Metal', 8)
    tube(mb, (-0.62, -0.50, 0.05), (-0.80, -0.58, -0.01), 0.028, 'Metal', 8)
    for y in (0.40, -0.20):
        mb.add(bm_box_mm((-0.545, y - 0.015, 0.11), (-0.515, y + 0.015, BODY_BOTTOM + 0.005)), mat='Rubber', shade='flat')


def add_rack(mb):
    z0 = ROOF_Z + 0.03
    zb, zu = z0 + 0.09, z0 + 0.21
    xr, yf, yr = 0.76, 0.32, -1.70
    for x in (-0.74, 0.74):
        for y in (0.28, -0.72, -1.66):
            mb.add(bm_box((0.05, 0.07, zb - z0), (x, y, (z0 + zb) / 2)), mat='Trim', shade='flat')
            mb.add(bm_box((0.07, 0.09, 0.012), (x, y, z0 + 0.006)), mat='Rubber', shade='flat')
    for z in (zb, zu):
        for x in (-xr, xr):
            tube(mb, (x, yr, z), (x, yf, z))
        tube(mb, (-xr, yf, z), (xr, yf, z))
        tube(mb, (-xr, yr, z), (xr, yr, z))
    for y in (-0.10, -0.52, -0.94, -1.36):
        tube(mb, (-xr, y, zb), (xr, y, zb), 0.013)
    for x in (-xr, xr):
        for y in (yf, -0.36, -1.04, yr):
            tube(mb, (x, y, zb), (x, y, zu), 0.013)
    # light bar with four round lamps on the front rail
    mb.add(bm_box_mm((-0.46, yf + 0.01, zu - 0.03), (0.46, yf + 0.06, zu + 0.075), 0.012), mat='Trim', shade='auto')
    for x in (-0.33, -0.11, 0.11, 0.33):
        rim = bm_lathe([(0.052, yf + 0.06), (0.054, yf + 0.085), (0.046, yf + 0.092)], 14, axis='Y')
        C.orient(rim, lambda f: (0, 1, 0))
        mb.add(xform(rim, Matrix.Translation((x, 0, zu + 0.02))), mat='Chrome', shade='auto')
        lens = bm_lathe([(0.045, yf + 0.087), (0.03, yf + 0.093), (0.0, yf + 0.096)], 14, axis='Y')
        C.orient(lens, lambda f: (0, 1, 0))
        mb.add(xform(lens, Matrix.Translation((x, 0, zu + 0.02))), mat='LampAux', shade='smooth')
    zc = zb + 0.015
    # two orange recovery boards along the right side, with traction studs and a strap
    for i, z in enumerate((zc, zc + 0.035)):
        mb.add(bm_box_mm((0.34, -1.52, z), (0.70, -0.30, z + 0.03), 0.01), mat='Board', shade='auto')
        if i == 1:
            for yy in range(10):
                for xx in range(3):
                    y = -1.46 + yy * 0.12
                    x = 0.40 + xx * 0.12
                    mb.add(bm_box_mm((x - 0.018, y - 0.018, z + 0.03), (x + 0.018, y + 0.018, z + 0.045)), mat='Board', shade='flat')
    for y in (-1.2, -0.62):
        mb.add(bm_box_mm((0.32, y - 0.02, zc - 0.005), (0.72, y + 0.02, zc + 0.075)), mat='Canvas', shade='flat')
    # duffel bag with straps (Canvas) and a coiled rope
    bag = bm_lathe([(0.0, -0.40), (0.10, -0.39), (0.16, -0.33), (0.17, 0.0), (0.16, 0.33), (0.10, 0.39), (0.0, 0.40)], 12, axis='X')
    C.orient(bag, lambda f: f.calc_center_median())
    mb.add(xform(bag, mat_trs((-0.30, -0.30, zc + 0.15), (0, 0, 0.12), (1, 1, 0.85))), mat='Canvas', shade='smooth')
    for xo in (-0.18, 0.18):
        st = bm_lathe([(0.176, -0.022), (0.176, 0.022)], 12, axis='X', cap_start=False)
        C.orient(st, lambda f: Vector((0, f.calc_center_median().y, f.calc_center_median().z)))
        mb.add(xform(st, mat_trs((-0.30 + xo * math.cos(0.12), -0.30 + xo * math.sin(0.12), zc + 0.15), (0, 0, 0.12), (1, 1, 0.85))),
               mat='Trim', shade='smooth')
    for k in range(3):
        ring = bm_lathe([(0.11 + 0.014 * math.cos(a), 0.014 * math.sin(a) + k * 0.024) for a in [i * math.pi / 3 for i in range(7)]], 14, axis='Z')
        mb.add(xform(ring, Matrix.Translation((0.10, 0.06, zc + 0.02))), mat='Canvas', shade='smooth')
    # two olive jerry cans with handles and caps
    for x in (-0.20, 0.02):
        mb.add(bm_box_mm((x - 0.08, -1.62, zc), (x + 0.08, -1.30, zc + 0.44), 0.02, 2), mat='Can', shade='auto', angle=40)
        for dz in (0.12, 0.30):
            mb.add(bm_box_mm((x - 0.082, -1.60, zc + dz), (x + 0.082, -1.32, zc + dz + 0.02)), mat='Can', shade='flat')
        for dx in (-0.03, 0.0, 0.03):
            mb.add(bm_box_mm((x + dx - 0.008, -1.60, zc + 0.44), (x + dx + 0.008, -1.46, zc + 0.47)), mat='Can', shade='flat')
        mb.add(bm_cyl(0.022, 0.022, 0.04, 8, Matrix.Translation((x, -1.36, zc + 0.44)), base=True), mat='Trim', shade='auto')
    # hi-lift jack along the left rail and a shovel
    mb.add(bm_box_mm((-0.70, -1.50, zc + 0.01), (-0.64, -0.10, zc + 0.05), 0.005), mat='Board', shade='auto')
    for y in (-1.40, -0.20):
        mb.add(bm_box_mm((-0.72, y - 0.05, zc), (-0.62, y + 0.05, zc + 0.09), 0.01), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.71, -1.10, zc + 0.05), (-0.63, -0.94, zc + 0.12), 0.01), mat='Board', shade='auto')
    tube(mb, (-0.67, -0.94, zc + 0.10), (-0.67, -0.30, zc + 0.10), 0.013, 'Metal')
    tube(mb, (-0.56, -1.60, zc + 0.03), (-0.56, -0.62, zc + 0.03), 0.017, 'Board')
    mb.add(bm_box_mm((-0.62, -0.62, zc + 0.02), (-0.50, -0.34, zc + 0.04), 0.008), mat='Metal', shade='auto')
    mb.add(bm_box_mm((-0.60, -1.66, zc + 0.02), (-0.52, -1.58, zc + 0.05), 0.006), mat='Trim', shade='auto')


def add_interior(mb):
    # dashboard with an instrument binnacle, gauges, glovebox, radio
    mb.add(bm_box_mm((-0.80, 0.34, 0.80), (0.80, 0.56, 1.00), 0.03), mat='Interior', shade='auto')
    mb.add(bm_box_mm((-0.58, 0.30, 0.94), (-0.22, 0.40, 1.04), 0.02), mat='Trim', shade='auto')
    for x in (-0.49, -0.40, -0.31):
        ring = bm_lathe([(0.036, 0.0), (0.036, 0.012)], 12, axis='Y')
        mb.add(xform(ring, Matrix.Translation((x, 0.296, 0.99))), mat='Chrome', shade='auto')
        face = bm_lathe([(0.032, 0.004), (0.0, 0.004)], 12, axis='Y')
        C.orient(face, lambda f: (0, -1, 0))
        mb.add(xform(face, Matrix.Translation((x, 0.296, 0.99))), mat='Decal', shade='flat')
    mb.add(bm_box_mm((0.20, 0.335, 0.86), (0.56, 0.345, 0.95), 0.005), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.10, 0.33, 0.86), (0.10, 0.345, 0.92), 0.004), mat='Metal', shade='auto')
    for sx in (-1, 1):
        # bucket seats with piping / stitching lines and headrests
        cx = sx * 0.40
        mb.add(bm_box_mm((cx - 0.24, -0.35, 0.80), (cx + 0.24, 0.12, 0.92), 0.03), mat='Interior', shade='auto')
        mb.add(bm_box((0.46, 0.12, 0.58), (cx, -0.36, 1.15), 0.035, 1, rot=(math.radians(-10), 0, 0)), mat='Interior', shade='auto')
        mb.add(bm_box((0.26, 0.10, 0.14), (cx, -0.42, 1.50), 0.03, 1, rot=(math.radians(-10), 0, 0)), mat='Interior', shade='auto')
        for dx in (-0.12, 0.0, 0.12):
            mb.add(bm_box_mm((cx + dx - 0.004, -0.33, 0.92), (cx + dx + 0.004, 0.10, 0.926)), mat='Trim', shade='flat')
            mb.add(bm_box((0.008, 0.01, 0.50), (cx + dx, -0.296, 1.16), 0.0, 1, rot=(math.radians(-10), 0, 0)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.78, -1.45, 0.80), (0.78, -0.95, 0.92), 0.03), mat='Interior', shade='auto')
    mb.add(bm_box((1.52, 0.12, 0.50), (0, -1.46, 1.13), 0.03, 1, rot=(math.radians(-8), 0, 0)), mat='Interior', shade='auto')
    # steering wheel with spokes, column
    wheel = bm_lathe([(0.17 + 0.018 * math.cos(a), 0.018 * math.sin(a)) for a in [i * math.pi / 3 for i in range(7)]], 16, axis='Y')
    Mw = mat_trs((-0.40, 0.26, 1.05), (math.radians(-25), 0, 0))
    mb.add(xform(wheel, Mw), mat='Trim', shade='smooth')
    for a in (0.0, 2.1, 4.2):
        mb.add(xform(bm_cyl_between((0, 0, 0), (0.16 * math.cos(a), 0, 0.16 * math.sin(a)), 0.01, segs=5), Mw.copy()), mat='Metal', shade='flat')
    mb.add(xform(bm_cyl_between((0, -0.01, 0), (0, 0.02, 0), 0.04, segs=10), Mw.copy()), mat='Trim', shade='auto')
    tube(mb, (-0.40, 0.26, 1.05), (-0.40, 0.42, 0.97), 0.02)
    # gear lever + transfer lever with knobs, handbrake
    for x, lean in ((-0.06, 0.08), (0.04, 0.05)):
        tube(mb, (x, 0.12, 0.84), (x, 0.12 - lean, 1.08), 0.009, 'Metal', 5)
        mb.add(bm_icos((x, 0.12 - lean, 1.09), 0.025), mat='Trim', shade='smooth')
    mb.add(bm_box_mm((-0.12, 0.02, 0.80), (0.12, 0.26, 0.86), 0.02), mat='Trim', shade='auto')
    tube(mb, (0.0, -0.10, 0.86), (0.0, 0.02, 0.93), 0.012, 'Metal', 5)
    # roll bar behind the front seats
    for sx in (-1, 1):
        tube(mb, (sx * 0.74, -0.52, 0.82), (sx * 0.72, -0.52, 1.42), 0.024, 'Trim', 8)
        tube(mb, (sx * 0.72, -0.52, 1.42), (sx * 0.70, -1.40, 1.42), 0.02, 'Trim', 8)
    tube(mb, (-0.72, -0.52, 1.42), (0.72, -0.52, 1.42), 0.024, 'Trim', 8)
    tube(mb, (-0.72, -0.52, 1.10), (0.72, -0.52, 1.10), 0.018, 'Trim', 8)


def bm_icos(c, r):
    return C.bm_icosphere(r, 1, Matrix.Translation(c))


def build_body(mb):
    add_tub(mb)
    add_greenhouse(mb)
    add_front(mb)
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
    # suspension travel shown in the previews (game: hardpoint 0.30, min length 0.12, rest 0.42)
    'bump': 0.22, 'droop': 0.12, 'lock': 32,
}

LAMPS = {
    'head': [(-0.665, 1.873, 0.60), (0.665, 1.873, 0.60)],
    'indicator': [(-0.665, 1.836, 0.425), (0.665, 1.836, 0.425)],
    'bar': [(x, 0.416, ROOF_Z + 0.26) for x in (-0.33, -0.11, 0.11, 0.33)],
    'tail': [(-0.78, -1.846, 0.605), (0.78, -1.846, 0.605)],
    'brake': [(-0.78, -1.846, 0.605), (0.78, -1.846, 0.605)],
    'rearIndicator': [(-0.78, -1.846, 0.472), (0.78, -1.846, 0.472)],
    'reverse': [(-0.78, -1.846, 0.397), (0.78, -1.846, 0.397)],
    'winch': [(0.0, 2.0, 0.305)],
    'hitch': [(0.0, -2.03, 0.225)],
}


def main():
    C.reset_scene()
    mats = make_materials()
    col = C.collection('Vehicle')
    parts, tris = {}, {}
    builders = {
        'Body': build_body,
        'Wheel': lambda mb: add_wheel(mb, R=TYRE_R, W=TYRE_W, segs=20, sidewall_lugs=15),
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
    print('VEHICLE scout TRIS', tris, 'total', sum(tris.values()))
    P.export_vehicle('scout', parts, DIMS, LAMPS, tris)
    import vehicle_check
    vehicle_check.run(parts, dict(DIMS, id='scout'))
    if '--no-previews' not in sys.argv:
        P.render_previews('scout', parts, col, DIMS)
    C.save_blend('vehicle_scout.blend')
    return tris


if __name__ == '__main__':
    main()
