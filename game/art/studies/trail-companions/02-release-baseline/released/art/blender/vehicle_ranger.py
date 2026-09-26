"""Forest Trail vehicle "Kestrel" (game id 'ranger'): 1970s-style compact 4x4 pickup, no real brand.

Blender coords: +Y front, +Z up, +X = vehicle right. Origin = midpoint between axles
at static wheel-centre height; ground is at Z = -0.36.
Exports vehicle_ranger.glb (+ .json mounts/lamps) through vehicle_parts.export_vehicle.

Packaging (all heights body coords, wheel centre = 0):
  * wheels R 0.36 travel +0.21 / -0.13, front lock 33 deg; arches r 0.47 centred 0.14 above the hub
  * frame rails at x +-0.30..0.38 kick up to 0.30..0.44 over both axles, low (0.10..0.24) under the cab
  * coil seats at x +-0.49 / z 0.44 (inboard of the tyre sidewall sweep at full lock + bump): front towers hang from the arch ceiling, rear seats sit under the bed floor
  * cab floor 0.28 and bed floor 0.45 clear the driveshafts, pinions and diff at full bump
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
from common import bm_box, bm_box_mm, bm_cyl, bm_cyl_between, bm_lathe, bm_from, xform, mat_trs
import vehicle_parts as P
from vehicle_parts import add_wheel

# ------------------------------------------------------------------ key dimensions
WHEELBASE = 2.62
AXLE_Y = WHEELBASE / 2          # front +1.31, rear -1.31
TRACK_X = 0.79
TYRE_R, TYRE_W = 0.36, 0.27
GROUND_Z = -0.36
HALF_W = 0.82                   # body side
FLARE_X = 0.852                 # outer face of the cream arch trims
ARCH_R, ARCH_ZC = 0.47, 0.14    # wheel-arch radius / centre height
CAB_BOTTOM = 0.28               # lower body underside (cab + front clip)
BELT_Z = 0.80                   # cab belt line
ROOF_Z = 1.28
BED_Y0, BED_Y1 = -0.36, -2.28   # bed front wall / tailgate outer face
BED_FLOOR = 0.45                # bed floor underside (top at 0.48)
BED_RAIL = 0.74
BED_SIDE_BOTTOM = 0.30
FRONT_Y = 2.045                 # front face of the body (bumper to 2.15)
SPRING_X = 0.49
SPRING_TOP_Z = 0.44             # upper spring seat (body coords)
SPRING_SEAT_Z = 0.06            # lower spring seat (axle-local coords)
PINION_Y, PINION_Z = 0.235, 0.03
TCASE_Y, TCASE_Z = 0.31, 0.10
RAIL_X0, RAIL_X1 = 0.30, 0.38


def make_materials():
    m = P.base_materials('#6E9E93', '#E6DDC4', '#E9E6DC')
    m['CargoRed'] = C.mat_pbr('CargoRed', '#A8412F', 0.55, 0.0)
    m['CargoBlue'] = C.mat_pbr('CargoBlue', '#3E6C8C', 0.5, 0.0)
    m['Rope'] = C.mat_pbr('Rope', '#B89A62', 0.9, 0.0)
    return m


# ------------------------------------------------------------------ helpers
def arch_over(yc, r, zc, z0, steps=16):
    """Arc of the wheel-arch circle above z0, from the rear end (y < yc) to the front end."""
    a0 = math.asin(max(-1.0, min(1.0, (z0 - zc) / r)))
    pts = []
    for i in range(steps + 1):
        a = math.pi - a0 - (math.pi - 2 * a0) * i / steps
        pts.append((yc + r * math.cos(a), zc + r * math.sin(a)))
    return pts


def in_arch(c, z0):
    for yc in (-AXLE_Y, AXLE_Y):
        if c.z > z0 - 0.01 and Vector((c.y - yc, c.z - ARCH_ZC)).length < ARCH_R + 0.02:
            return True
    return False


def tube(mb, a, b, r=0.016, mat='Trim', segs=6):
    mb.add(bm_cyl_between(a, b, r, segs=segs, cap=False), mat=mat, shade='auto', angle=70)


def polyline_tube(mb, pts, r, mat='Metal', segs=8):
    for a, b in zip(pts, pts[1:]):
        mb.add(bm_cyl_between(a, b, r, segs=segs), mat=mat, shade='auto', angle=60)
    for p in pts[1:-1]:
        mb.add(C.bm_icosphere(r, 1, Matrix.Translation(p)), mat=mat, shade='smooth')


def lens(mb, cx, cz, y, r, mat, facing=1, segs=16, bezel='Chrome'):
    """Round lamp at (cx, y, cz) facing +Y (facing=1) or -Y: chrome bezel ring + domed lens."""
    s = facing
    bez = bm_lathe([(r + 0.022, y - s * 0.012), (r + 0.024, y + s * 0.02), (r + 0.006, y + s * 0.034), (r - 0.004, y + s * 0.028)], segs, axis='Y')
    C.orient(bez, lambda f: Vector((0, 0.6 * s, 0)) + Vector((f.calc_center_median().x - cx, 0, f.calc_center_median().z - cz)))
    mb.add(xform(bez, Matrix.Translation((cx, 0, cz))), mat=bezel, shade='auto', angle=50)
    ln = bm_lathe([(r, y + s * 0.022), (r * 0.7, y + s * 0.036), (0.0, y + s * 0.042)], segs, axis='Y')
    C.orient(ln, lambda f: (0, s, 0))
    mb.add(xform(ln, Matrix.Translation((cx, 0, cz))), mat=mat, shade='smooth')


def text_front(txt, size, x, y, z, depth=0.012):
    """Text readable from the front (+Y) with its face on the plane y."""
    M = Matrix.Translation((x, y + depth / 2, z)) @ Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'X')
    return P.bm_text(txt, size, depth, M)


def text_rear(txt, size, x, y, z, depth=0.012):
    """Text readable from behind (-Y) with its face on the plane y."""
    M = Matrix.Translation((x, y - depth / 2, z)) @ Matrix.Rotation(math.pi / 2, 4, 'X')
    return P.bm_text(txt, size, depth, M)


# ------------------------------------------------------------------ lower body: front clip + cab tub
def add_lower_body(mb):
    b, t = CAB_BOTTOM, BELT_Z
    prof = [(-0.26, t - 0.02), (-0.26, b + 0.03), (-0.235, b)]
    prof += arch_over(AXLE_Y, ARCH_R, ARCH_ZC, b)
    prof += [(1.80, b), (1.83, 0.24), (2.02, 0.24), (FRONT_Y, 0.27), (FRONT_Y, 0.70), (2.012, 0.745),
             (0.98, 0.79), (0.945, t), (-0.235, t)]
    bm = C.bm_extrude_poly(prof, 2 * HALF_W, axis='X')
    C.bevel(bm, 0.026, 2)
    bm.normal_update()

    def mat(f):
        c = f.calc_center_median()
        if abs(f.normal.x) < 0.5 and in_arch(c, b) and f.normal.z < 0.2 and abs(c.x) < HALF_W - 0.02:
            return 'Interior'
        if f.normal.z < -0.7:
            return 'Trim'
        return 'Paint'
    mb.add(bm, mat_fn=mat, shade='auto', angle=32)
    # bonnet panel (slightly proud, sloping to the front) with a centre crease and cowl vents
    ang = -math.atan2(0.79 - 0.745, 2.01 - 0.98)
    mb.add(bm_box((1.50, 1.02, 0.02), (0, 1.50, 0.78), 0.008, 1, rot=(ang, 0, 0)), mat='Paint', shade='auto')
    mb.add(bm_box((0.10, 1.00, 0.012), (0, 1.50, 0.793), 0.004, 1, rot=(ang, 0, 0)), mat='Paint', shade='auto')
    for sx in (-1, 1):
        for i in range(4):
            y = 1.08 + i * 0.05
            z = 0.79 + (1.50 - y) * 0.0437 + 0.006
            mb.add(bm_box((0.20, 0.018, 0.012), (sx * 0.38, y, z), 0.003, 1, rot=(ang, 0, 0)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.80, 0.93, 0.785), (0.80, 0.99, 0.815), 0.008), mat='Trim', shade='auto')
    # interior floor visible through the glass
    mb.add(bm_box_mm((-0.76, -0.22, t - 0.005), (0.76, 0.90, t + 0.005)), mat='Interior', shade='flat')


def add_greenhouse(mb):
    zb, zt = BELT_Z, ROOF_Z
    xb, xt = 0.80, 0.735
    st = [(0.93, 0.60), (-0.06, -0.05), (-0.245, -0.215)]
    V = []
    for yb, yt in st:
        V += [(-xb, yb, zb), (xb, yb, zb), (xt, yt, zt), (-xt, yt, zt)]
    n_st = len(st)
    F = [[0, 1, 2, 3][::-1], [4 * (n_st - 1), 4 * (n_st - 1) + 1, 4 * (n_st - 1) + 2, 4 * (n_st - 1) + 3]]
    for i in range(n_st - 1):
        a, n = 4 * i, 4 * (i + 1)
        F += [[a + 1, n + 1, n + 2, a + 2], [a, a + 3, n + 3, n], [a + 3, a + 2, n + 2, n + 3], [a, n, n + 1, a + 1]]
    bm = bm_from(V, F)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bottom = [f for f in bm.faces if f.normal.z < -0.9]
    edges = [e for e in bm.edges if not any(f in bottom for f in e.link_faces)]
    res = C.bevel(bm, 0.05, 3, edges)
    new = set(res.get('faces', []))
    bm.normal_update()
    wins = [f for f in bm.faces if f not in new and abs(f.normal.z) < 0.6 and f.calc_area() > 0.05
            and (abs(f.normal.y) > 0.5 or f.calc_center_median().y > -0.05)]
    roof = [f for f in bm.faces if f not in new and f.normal.z > 0.9]
    kill = [f for f in bm.faces if f.normal.z < -0.9]
    bmesh.ops.delete(bm, geom=kill, context='FACES_ONLY')
    bmesh.ops.inset_individual(bm, faces=wins, thickness=0.045, depth=-0.016)
    glass, roofs = set(wins), set(roof)
    mb.add(bm, mat_fn=lambda f: 'Glass' if f in glass else ('PaintAccent' if (f in roofs or f.normal.z > 0.75) else 'Paint'),
           shade='auto', angle=32)
    # drip rails along the roof edge
    for sx in (-1, 1):
        tube(mb, (sx * (xt + 0.012), 0.58, zt - 0.035), (sx * (xt + 0.012), -0.20, zt - 0.035), 0.011, 'Chrome')
    # windscreen and rear glass rubber / chrome surrounds
    for (y0, z0), (y1, z1) in (((0.905, zb + 0.04), (0.605, zt - 0.05)),):
        for sx in (-1, 1):
            tube(mb, (sx * 0.74, y0 + 0.012, z0), (sx * 0.69, y1 + 0.012, z1), 0.012, 'Chrome')
        tube(mb, (-0.74, y0 + 0.012, z0), (0.74, y0 + 0.012, z0), 0.012, 'Chrome')
        tube(mb, (-0.69, y1 + 0.012, z1), (0.69, y1 + 0.012, z1), 0.012, 'Chrome')
    # quarter vent dividers in the door glass
    for sx in (-1, 1):
        tube(mb, (sx * 0.797, 0.66, zb + 0.04), (sx * 0.752, 0.53, zt - 0.10), 0.009, 'Chrome')
    # wipers resting on the windscreen: arm + rubber blade laid on the glass
    gz = lambda y: zb + (0.93 - y) * (zt - zb) / (0.93 - 0.60) + 0.012
    for px in (-0.60, -0.04):
        a = Vector((px, 0.915, gz(0.915)))
        b = Vector((px + 0.40, 0.86, gz(0.86)))
        tube(mb, a, b, 0.007, 'Trim')
        d = (b - a).normalized()
        mid = a + (b - a) * 0.55
        tube(mb, mid - d * 0.19 + Vector((0, 0, 0.006)), mid + d * 0.19 + Vector((0, 0, 0.006)), 0.006, 'Rubber')
        mb.add(bm_cyl(0.016, 0.016, 0.015, 8, Matrix.Translation(a - Vector((0, 0, 0.006))), base=True), mat='Trim', shade='auto')


def add_front(mb):
    y = FRONT_Y
    # grille: dark backing, chrome frame, horizontal bars, badge
    mb.add(bm_box_mm((-0.44, y - 0.02, 0.36), (0.44, y + 0.008, 0.64)), mat='Trim', shade='flat')
    for i in range(5):
        z = 0.395 + i * 0.052
        mb.add(bm_box_mm((-0.42, y, z - 0.011), (0.42, y + 0.026, z + 0.011), 0.004), mat='Chrome', shade='auto')
    for x0, x1, z0, z1 in ((-0.46, 0.46, 0.34, 0.365), (-0.46, 0.46, 0.635, 0.66), (-0.46, -0.435, 0.34, 0.66), (0.435, 0.46, 0.34, 0.66)):
        mb.add(bm_box_mm((x0, y, z0), (x1, y + 0.03, z1), 0.006), mat='Chrome', shade='auto')
    mb.add(bm_box_mm((-0.012, y, 0.365), (0.012, y + 0.03, 0.635)), mat='Chrome', shade='flat')
    mb.add(bm_box_mm((-0.17, y + 0.025, 0.575), (0.17, y + 0.037, 0.625), 0.006), mat='Trim', shade='auto')
    mb.add(text_front('KESTREL', 0.042, 0, y + 0.037, 0.584, 0.008), mat='Decal', shade='flat')
    # headlights in square bezels, amber indicators below
    for sx in (-1, 1):
        cx = sx * 0.62
        mb.add(bm_box_mm((cx - 0.13, y - 0.01, 0.40), (cx + 0.13, y + 0.02, 0.64), 0.014), mat='Trim', shade='auto')
        lens(mb, cx, 0.52, y + 0.02, 0.088, 'Lamp', 1)
        mb.add(bm_box_mm((cx - 0.075, y, 0.305), (cx + 0.075, y + 0.03, 0.355), 0.008), mat='Chrome', shade='auto')
        mb.add(bm_box_mm((cx - 0.064, y + 0.02, 0.312), (cx + 0.064, y + 0.036, 0.348), 0.005), mat='LampAmber', shade='auto')
        # side marker on the fender
        mb.add(bm_box_mm((sx * HALF_W - 0.01, 1.84, 0.52), (sx * HALF_W + 0.01, 1.92, 0.56), 0.004), mat='LampAmber', shade='auto')
    # chrome front bumper with over-riders, plate and tow hooks
    mb.add(bm_box_mm((-0.86, 2.05, 0.17), (0.86, 2.14, 0.30), 0.03, 2), mat='Chrome', shade='auto', angle=40)
    for sx in (-1, 1):
        xa, xb = sorted((sx * 0.78, sx * 0.865))
        mb.add(bm_box_mm((xa, 1.97, 0.17), (xb, 2.10, 0.30), 0.025), mat='Chrome', shade='auto')
        mb.add(bm_box_mm((sx * 0.40 - 0.03, 2.10, 0.14), (sx * 0.40 + 0.03, 2.17, 0.33), 0.012), mat='Chrome', shade='auto')
        mb.add(bm_box_mm((sx * 0.40 - 0.035, 1.90, 0.20), (sx * 0.40 + 0.035, 2.06, 0.26)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.17, 2.138, 0.185), (0.17, 2.150, 0.285), 0.004), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.16, 2.148, 0.192), (0.16, 2.156, 0.278)), mat='Decal', shade='flat')
    for sx in (-1, 1):
        hook = bm_lathe([(0.038 + 0.012 * math.cos(a), 0.012 * math.sin(a)) for a in [i * math.pi / 3 for i in range(7)]], 10, axis='X')
        C.orient(hook, lambda f: (lambda c: c - Vector((0, c.y, c.z)).normalized() * 0.038)(f.calc_center_median()))
        mb.add(xform(hook, Matrix.Translation((sx * 0.52, 2.10, 0.12))), mat='CargoRed', shade='smooth')
        mb.add(bm_box_mm((sx * 0.52 - 0.02, 1.98, 0.13), (sx * 0.52 + 0.02, 2.09, 0.19)), mat='Trim', shade='flat')
    # valance under the bumper
    mb.add(bm_box_mm((-0.74, 1.86, 0.20), (0.74, 2.03, 0.25), 0.01), mat='Trim', shade='auto')


def add_sides(mb):
    for sx in (-1, 1):
        # cream arch trims
        for yc, z0 in ((AXLE_Y, CAB_BOTTOM), (-AXLE_Y, BED_SIDE_BOTTOM)):
            outer = arch_over(yc, ARCH_R + 0.055, ARCH_ZC, z0 - 0.02)
            inner = arch_over(yc, ARCH_R, ARCH_ZC, z0 - 0.02)[::-1]
            fl = C.bm_extrude_poly(outer + inner, FLARE_X - (HALF_W - 0.01), axis='X', center=sx * (FLARE_X + HALF_W - 0.01) / 2)
            fl.normal_update()
            oe = [e for e in fl.edges if all(abs(v.co.x) > FLARE_X - 0.005 for v in e.verts)]
            C.bevel(fl, 0.012, 1, oe)
            mb.add(fl, mat='PaintAccent', shade='auto', angle=40)
        x = sx * (HALF_W + 0.002)
        # cream stripe along cab and bed
        for y0, y1 in ((-0.25, 2.0), (BED_Y1 + 0.01, BED_Y0 - 0.01)):
            mb.add(bm_box_mm((x - 0.003, y0, 0.645), (x + 0.003, y1, 0.69)), mat='PaintAccent', shade='flat')
        # door seams, handle, key, hinges
        arch_top_at = lambda y: ARCH_ZC + math.sqrt(max(0.0, ARCH_R ** 2 - (y - AXLE_Y) ** 2))
        for y0, y1, z0, z1 in ((0.892, 0.902, max(CAB_BOTTOM + 0.03, arch_top_at(0.9) + 0.07), BELT_Z),
                               (-0.105, -0.095, CAB_BOTTOM + 0.03, BELT_Z), (-0.10, 0.90, CAB_BOTTOM + 0.035, CAB_BOTTOM + 0.045)):
            mb.add(bm_box_mm((x - 0.004, y0, z0), (x + 0.004, y1, z1)), mat='Trim', shade='flat')
        mb.add(bm_box_mm((x - 0.014 * (sx < 0), -0.03, 0.735), (x + 0.014 * (sx > 0), 0.09, 0.755), 0.005), mat='Chrome', shade='auto')
        mb.add(bm_cyl_between((x, 0.12, 0.745), (x + sx * 0.01, 0.12, 0.745), 0.01, segs=8), mat='Chrome', shade='auto')
        for z in (0.40, 0.68):
            mb.add(bm_box_mm((x - 0.012 * (sx < 0), 0.86, z), (x + 0.012 * (sx > 0), 0.905, z + 0.06), 0.004), mat='Trim', shade='auto')
        # rocker sills
        mb.add(bm_box_mm((sx * 0.70 if sx > 0 else -HALF_W - 0.005, -0.24, 0.20), (HALF_W + 0.005 if sx > 0 else -0.70, 0.84, CAB_BOTTOM + 0.02), 0.015), mat='Trim', shade='auto')
        # tall chrome mirror arms + heads
        tube(mb, (sx * 0.80, 0.86, 0.80), (sx * 0.93, 0.83, 0.97), 0.011, 'Chrome')
        tube(mb, (sx * 0.80, 0.70, 0.80), (sx * 0.93, 0.83, 0.97), 0.009, 'Chrome')
        mb.add(bm_box((0.035, 0.06, 0.16), (sx * 0.945, 0.83, 1.05), 0.012), mat='Chrome', shade='auto')
        mb.add(bm_box((0.028, 0.004, 0.14), (sx * 0.945, 0.798, 1.05)), mat='Glass', shade='flat')
        # mud flaps behind both wheels
        for y0 in (0.855, -1.815):
            mb.add(bm_box_mm((sx * 0.66 if sx > 0 else -0.84, y0, -0.08), (0.84 if sx > 0 else -0.66, y0 + 0.014, CAB_BOTTOM + 0.01)), mat='Rubber', shade='flat')
        # bed-side red marker
        mb.add(bm_box_mm((x - 0.008, -2.18, 0.60), (x + 0.008, -2.10, 0.63), 0.003), mat='LampRear', shade='auto')
    # fuel filler on the left bed side
    mb.add(bm_cyl_between((-HALF_W - 0.002, -0.62, 0.58), (-HALF_W - 0.014, -0.62, 0.58), 0.045, segs=12), mat='Chrome', shade='auto')
    # antenna on the right front fender
    mb.add(bm_cyl_between((0.72, 0.99, 0.79), (0.72, 0.96, 1.86), 0.005, segs=4), mat='Chrome', shade='flat')
    mb.add(bm_cyl(0.018, 0.012, 0.03, 6, Matrix.Translation((0.72, 0.99, 0.785)), base=True), mat='Trim', shade='auto')


def add_interior(mb):
    # bench seat against the back wall
    mb.add(bm_box_mm((-0.72, -0.20, BELT_Z), (0.72, 0.10, BELT_Z + 0.07), 0.03), mat='Interior', shade='auto')
    mb.add(bm_box((1.44, 0.10, 0.36), (0, -0.17, BELT_Z + 0.22), 0.035, 1, rot=(math.radians(-8), 0, 0)), mat='Interior', shade='auto')
    for x in (-0.36, 0.36):
        mb.add(bm_box((0.50, 0.012, 0.30), (x, -0.113, BELT_Z + 0.23), 0.004, 1, rot=(math.radians(-8), 0, 0)), mat='Trim', shade='flat')
    # dash with gauges
    mb.add(bm_box_mm((-0.74, 0.60, BELT_Z), (0.74, 0.80, BELT_Z + 0.12), 0.03), mat='Interior', shade='auto')
    mb.add(bm_box_mm((-0.74, 0.56, BELT_Z + 0.08), (0.74, 0.64, BELT_Z + 0.13), 0.02), mat='Trim', shade='auto')
    for gx in (-0.46, -0.32):
        mb.add(bm_cyl_between((gx, 0.562, BELT_Z + 0.105), (gx, 0.556, BELT_Z + 0.105), 0.04, segs=12), mat='Decal', shade='flat')
    # steering wheel (left hand drive) + column, gear lever, transfer lever
    wheel = bm_lathe([(0.17 + 0.016 * math.cos(a), 0.016 * math.sin(a)) for a in [i * math.pi / 2 for i in range(5)]], 14, axis='Y')
    mb.add(xform(wheel, mat_trs((-0.38, 0.50, BELT_Z + 0.24), (math.radians(-28), 0, 0))), mat='Trim', shade='smooth')
    tube(mb, (-0.38, 0.50, BELT_Z + 0.24), (-0.38, 0.64, BELT_Z + 0.10), 0.022)
    for i in range(3):
        a = i * 2 * math.pi / 3 + math.pi / 2
        tube(mb, (-0.38, 0.50, BELT_Z + 0.24), (-0.38 + 0.16 * math.cos(a), 0.50 + 0.16 * math.sin(a) * math.sin(math.radians(28)),
                                                   BELT_Z + 0.24 + 0.16 * math.sin(a) * math.cos(math.radians(28))), 0.009)
    tube(mb, (0.0, 0.42, BELT_Z), (-0.02, 0.36, BELT_Z + 0.26), 0.009, 'Chrome')
    mb.add(C.bm_icosphere(0.025, 1, Matrix.Translation((-0.02, 0.36, BELT_Z + 0.27))), mat='Trim', shade='smooth')
    tube(mb, (0.10, 0.36, BELT_Z), (0.12, 0.30, BELT_Z + 0.18), 0.008, 'Chrome')
    mb.add(C.bm_icosphere(0.02, 1, Matrix.Translation((0.12, 0.30, BELT_Z + 0.19))), mat='CargoRed', shade='smooth')
    # rear-view mirror
    mb.add(bm_box((0.18, 0.02, 0.05), (0, 0.62, ROOF_Z - 0.07)), mat='Trim', shade='auto')


# ------------------------------------------------------------------ cargo bed
def add_bed(mb):
    y0, y1 = BED_Y0, BED_Y1
    zf, zr = BED_FLOOR, BED_RAIL
    tub_in = 0.60                                 # inner face of the wheel tubs
    # side panels with the rear arch cut out
    prof = [(y1, zr), (y0, zr), (y0, BED_SIDE_BOTTOM)]
    prof += arch_over(-AXLE_Y, ARCH_R, ARCH_ZC, BED_SIDE_BOTTOM)[::-1]
    prof += [(y1, BED_SIDE_BOTTOM)]
    for sx in (-1, 1):
        bm = C.bm_extrude_poly(prof, 0.035, axis='X', center=sx * (HALF_W - 0.0175))
        C.bevel(bm, 0.008, 1)
        bm.normal_update()
        mb.add(bm, mat_fn=lambda f: 'Interior' if (abs(f.normal.x) < 0.5 and in_arch(f.calc_center_median(), BED_SIDE_BOTTOM)) else 'Paint',
               shade='auto', angle=32)
        # rail caps with stake pockets
        mb.add(bm_box_mm((sx * (HALF_W - 0.06) if sx > 0 else -HALF_W - 0.01, y1 + 0.005, zr),
                         (HALF_W + 0.01 if sx > 0 else -(HALF_W - 0.06), y0, zr + 0.03), 0.01), mat='PaintAccent', shade='auto')
        for yp in (-0.62, -1.31, -2.02):
            mb.add(bm_box_mm((sx * (HALF_W - 0.045) - 0.018, yp - 0.035, zr + 0.029), (sx * (HALF_W - 0.045) + 0.018, yp + 0.035, zr + 0.034)),
                   mat='Trim', shade='flat')
        # wheel tub: arch shell over the tyre plus its inner wall
        ring = arch_over(-AXLE_Y, ARCH_R + 0.03, ARCH_ZC, zf) + arch_over(-AXLE_Y, ARCH_R, ARCH_ZC, zf)[::-1]
        xa, xb = sorted((sx * tub_in, sx * (HALF_W - 0.03)))
        mb.add(C.bm_extrude_poly(ring, xb - xa, axis='X', center=(xa + xb) / 2), mat='Paint', shade='auto', angle=40)
        wall = arch_over(-AXLE_Y, ARCH_R + 0.03, ARCH_ZC, zf)
        mb.add(C.bm_extrude_poly(wall, 0.02, axis='X', center=sx * (tub_in - 0.01)), mat='Paint', shade='auto', angle=40)
        # outer floor strips ahead of and behind the tub
        cut = math.sqrt(ARCH_R ** 2 - (zf - ARCH_ZC) ** 2) + 0.03
        for ya, yb in ((-AXLE_Y + cut, y0 - 0.04), (y1 + 0.04, -AXLE_Y - cut)):
            mb.add(bm_box_mm((xa, ya, zf), (xb, yb, zf + 0.03)), mat='Paint', shade='flat')
    # centre floor with raised ribs, front wall and tailgate
    mb.add(bm_box_mm((-tub_in, y1 + 0.04, zf), (tub_in, y0 - 0.04, zf + 0.03)), mat='Paint', shade='flat')
    for i in range(7):
        x = -0.48 + i * 0.16
        mb.add(bm_box_mm((x - 0.025, y1 + 0.06, zf + 0.03), (x + 0.025, y0 - 0.06, zf + 0.042), 0.006), mat='Paint', shade='auto')
    mb.add(bm_box_mm((-HALF_W, y0 - 0.045, BED_SIDE_BOTTOM), (HALF_W, y0, zr + 0.03), 0.012), mat='Paint', shade='auto')
    mb.add(bm_box_mm((-HALF_W + 0.01, y0 - 0.047, zr), (HALF_W - 0.01, y0 + 0.002, zr + 0.035), 0.01), mat='PaintAccent', shade='auto')
    tg = bm_box_mm((-(HALF_W - 0.045), y1, 0.36), (HALF_W - 0.045, y1 + 0.045, zr + 0.02), 0.012)
    mb.add(tg, mat='Paint', shade='auto')
    mb.add(bm_box_mm((-(HALF_W - 0.05), y1 - 0.004, zr - 0.035), (HALF_W - 0.05, y1 + 0.01, zr + 0.022)), mat='PaintAccent', shade='flat')
    for z in (0.43, 0.47):
        mb.add(bm_box_mm((-0.70, y1 - 0.006, z - 0.004), (0.70, y1 + 0.002, z + 0.004)), mat='Trim', shade='flat')
    mb.add(text_rear('KESTREL', 0.105, 0, y1 - 0.002, 0.535, 0.012), mat='Decal', shade='flat')
    mb.add(bm_box_mm((-0.10, y1 - 0.02, 0.665), (0.10, y1, 0.69), 0.006), mat='Chrome', shade='auto')
    # tailgate chains: sagging links from the gate corners to the bed sides
    for sx in (-1, 1):
        pts = []
        for i in range(9):
            t = i / 8
            pts.append(Vector((sx * (HALF_W - 0.05), y1 + 0.04 + 0.26 * t, zr - 0.02 - 0.09 * math.sin(math.pi * t))))
        for a, b in zip(pts, pts[1:]):
            mb.add(bm_cyl_between(a, b, 0.006, segs=4), mat='Metal', shade='flat')
    # tall tail lamps on the rear corners: tail/brake, indicator, reverse
    for sx in (-1, 1):
        xa, xb = sorted((sx * (HALF_W - 0.06), sx * (HALF_W + 0.012)))
        mb.add(bm_box_mm((xa, y1 - 0.02, 0.40), (xb, y1 + 0.01, 0.745), 0.01), mat='Chrome', shade='auto')
        for (z0, z1), m in (((0.575, 0.73), 'LampRear'), ((0.505, 0.565), 'LampAmber'), ((0.415, 0.495), 'LampReverse')):
            mb.add(bm_box_mm((xa + 0.01, y1 - 0.03, z0), (xb - 0.01, y1 - 0.01, z1), 0.005), mat=m, shade='auto')


def add_rear(mb):
    y = BED_Y1
    # chrome step bumper with a ribbed step pad, plate and hitch receiver + ball
    mb.add(bm_box_mm((-0.84, y - 0.14, 0.18), (0.84, y - 0.02, 0.32), 0.025, 2), mat='Chrome', shade='auto', angle=40)
    mb.add(bm_box_mm((-0.30, y - 0.13, 0.318), (0.30, y - 0.03, 0.33)), mat='Trim', shade='flat')
    for i in range(6):
        x = -0.25 + i * 0.1
        mb.add(bm_box_mm((x - 0.02, y - 0.125, 0.33), (x + 0.02, y - 0.035, 0.338)), mat='Rubber', shade='flat')
    mb.add(bm_box_mm((-0.17, y - 0.148, 0.195), (0.17, y - 0.138, 0.30), 0.004), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.16, y - 0.156, 0.202), (0.16, y - 0.146, 0.292)), mat='Decal', shade='flat')
    for sx in (-1, 1):
        mb.add(bm_box_mm((sx * 0.40 - 0.03, y - 0.03, 0.20), (sx * 0.40 + 0.03, y + 0.30, 0.28)), mat='Trim', shade='flat')
    mb.add(bm_box_mm((-0.04, y - 0.22, 0.16), (0.04, y - 0.10, 0.22), 0.006), mat='Trim', shade='auto')
    mb.add(bm_box_mm((-0.028, y - 0.25, 0.175), (0.028, y - 0.20, 0.205)), mat='Metal', shade='flat')
    mb.add(bm_cyl(0.012, 0.012, 0.05, 8, Matrix.Translation((0, y - 0.225, 0.205)), base=True), mat='Chrome', shade='auto')
    mb.add(C.bm_icosphere(0.028, 2, Matrix.Translation((0, y - 0.225, 0.268))), mat='Chrome', shade='smooth')


def add_chassis(mb):
    # frame rails: kicked up over both axles, low under the cab
    top = [(2.02, 0.42), (1.72, 0.44), (0.95, 0.44), (0.74, 0.24), (-0.62, 0.24), (-0.88, 0.44), (-2.27, 0.44)]
    bot = [(-2.27, 0.30), (-0.90, 0.30), (-0.64, 0.10), (0.76, 0.10), (0.97, 0.30), (1.72, 0.30), (2.02, 0.28)]
    for sx in (-1, 1):
        mb.add(C.bm_extrude_poly(top + bot, RAIL_X1 - RAIL_X0, axis='X', center=sx * (RAIL_X0 + RAIL_X1) / 2), mat='Trim', shade='flat')
    for y0, y1, z0, z1 in ((1.84, 1.92, 0.28, 0.40), (-0.05, 0.05, 0.10, 0.20), (-2.13, -2.05, 0.30, 0.42)):
        mb.add(bm_box_mm((-RAIL_X1, y0, z0), (RAIL_X1, y1, z1)), mat='Trim', shade='flat')
    # upper spring seats: front towers under the arch ceiling, rear seats under the bed floor
    for sx in (-1, 1):
        for yc in (-AXLE_Y, AXLE_Y):
            xa, xb = sorted((sx * (SPRING_X - 0.075), sx * (SPRING_X + 0.06)))
            ztop = 0.64 if yc > 0 else BED_FLOOR + 0.01
            mb.add(bm_box_mm((xa, yc - 0.09, SPRING_TOP_Z + 0.012), (xb, yc + 0.09, ztop), 0.01), mat='Trim', shade='auto')
            mb.add(bm_cyl(0.078, 0.078, 0.012, 10, Matrix.Translation((sx * SPRING_X, yc, SPRING_TOP_Z)), base=True), mat='Metal', shade='auto')
            # link from the seat to the frame rail
            xa, xb = sorted((sx * (RAIL_X1 - 0.01), sx * (SPRING_X - 0.06)))
            mb.add(bm_box_mm((xa, yc - 0.05, 0.40), (xb, yc + 0.05, SPRING_TOP_Z + 0.03)), mat='Trim', shade='flat')
    # transfer case + outputs (driveshafts connect at (0, +-TCASE_Y, TCASE_Z)), gearbox tail
    mb.add(bm_box_mm((-0.14, -0.27, 0.00), (0.14, 0.27, 0.22), 0.025), mat='Trim', shade='auto')
    for s in (-1, 1):
        mb.add(bm_cyl_between((0, s * 0.26, TCASE_Z), (0, s * TCASE_Y, TCASE_Z), 0.05, segs=8), mat='Metal', shade='auto')
    mb.add(bm_cyl_between((0.0, 0.20, 0.30), (0.0, 0.80, 0.33), 0.08, r2=0.1, segs=10), mat='Trim', shade='auto', angle=50)
    # fuel tank with straps on the right, behind the cab
    mb.add(bm_box_mm((0.44, -0.84, 0.14), (0.74, -0.42, 0.40), 0.03, 2), mat='Trim', shade='auto', angle=40)
    for y in (-0.52, -0.74):
        mb.add(bm_box_mm((0.43, y - 0.015, 0.13), (0.75, y + 0.015, 0.145)), mat='Metal', shade='flat')
    # exhaust: downpipe, under the cab, muffler, over the rear axle, tailpipe out to the left rear
    ex = [(-0.22, 0.82, 0.30), (-0.22, 0.70, 0.15), (-0.22, -0.88, 0.15), (-0.22, -1.02, 0.36),
          (-0.22, -1.60, 0.36), (-0.52, -1.92, 0.25), (-0.52, BED_Y1 + 0.02, 0.24)]
    polyline_tube(mb, [Vector(p) for p in ex], 0.028, 'Metal')
    mb.add(bm_cyl_between((-0.22, -0.28, 0.15), (-0.22, -0.74, 0.15), 0.075, segs=12), mat='Metal', shade='auto', angle=50)
    # steering box on the left rail
    mb.add(bm_box_mm((-0.52, 1.66, 0.34), (-0.41, 1.80, 0.44), 0.01), mat='Trim', shade='auto')


def add_rollbar(mb):
    yb = BED_Y0 - 0.12
    zb, zt = BED_RAIL + 0.03, 1.38
    xs = 0.70
    polyline_tube(mb, [Vector((-xs, yb, zb)), Vector((-xs, yb, zt - 0.08)), Vector((-xs + 0.08, yb, zt)),
                       Vector((xs - 0.08, yb, zt)), Vector((xs, yb, zt - 0.08)), Vector((xs, yb, zb))], 0.03, 'Trim')
    for sx in (-1, 1):
        tube(mb, (sx * (xs - 0.02), yb - 0.02, zt - 0.10), (sx * (HALF_W - 0.05), -0.98, zb), 0.024, 'Trim', 8)
        mb.add(bm_box_mm((sx * xs - 0.05, yb - 0.05, zb - 0.01), (sx * xs + 0.05, yb + 0.05, zb + 0.01)), mat='Metal', shade='flat')
    # two round lamps on the top bar, aimed forward over the roof
    for x in (-0.32, 0.32):
        mb.add(bm_box_mm((x - 0.015, yb - 0.02, zt + 0.02), (x + 0.015, yb + 0.02, zt + 0.06)), mat='Trim', shade='flat')
        mb.add(bm_cyl_between((x, yb - 0.04, zt + 0.10), (x, yb + 0.04, zt + 0.10), 0.075, segs=14), mat='Trim', shade='auto', angle=50)
        lens(mb, x, zt + 0.10, yb + 0.03, 0.062, 'LampAux', 1, 14)
        # little stone guard cross
        for a in (0.785, -0.785):
            mb.add(bm_box((0.13, 0.006, 0.01), (x, yb + 0.08, zt + 0.10), 0, 1, rot=(0, a, 0)), mat='Trim', shade='flat')


def add_cargo(mb):
    zf = BED_FLOOR + 0.042
    # cooler (white, dark lid seal and handles)
    mb.add(bm_box_mm((-0.56, -0.92, zf), (-0.18, -0.48, zf + 0.32), 0.03, 2), mat='Decal', shade='auto', angle=40)
    mb.add(bm_box_mm((-0.57, -0.93, zf + 0.30), (-0.17, -0.47, zf + 0.36), 0.02), mat='CargoBlue', shade='auto')
    for y in (-0.93, -0.47):
        mb.add(bm_box_mm((-0.44, y - 0.012 * (y < -0.7), zf + 0.22), (-0.30, y + 0.012 * (y > -0.7), zf + 0.25)), mat='Trim', shade='flat')
    # rolled tent across the front of the bed, two straps
    tent = bm_cyl_between((-0.02, -0.62, zf + 0.12), (0.56, -0.62, zf + 0.12), 0.12, segs=12)
    mb.add(tent, mat='Canvas', shade='smooth')
    for x in (0.10, 0.44):
        st = bm_lathe([(0.126, -0.018), (0.126, 0.018)], 12, axis='X')
        C.orient(st, lambda f: Vector((0, f.calc_center_median().y, f.calc_center_median().z)))
        mb.add(xform(st, Matrix.Translation((x, -0.62, zf + 0.12))), mat='Trim', shade='smooth')
    # duffel bags on the left behind the cooler
    for yc, m, rs in ((-1.30, 'Canvas', 0.15), (-1.82, 'CargoRed', 0.13)):
        bag = bm_lathe([(0.0, -0.24), (0.08, -0.235), (0.13, -0.19), rs and (rs, 0.0), (0.13, 0.19), (0.08, 0.235), (0.0, 0.24)], 10, axis='Y')
        C.orient(bag, lambda f: f.calc_center_median())
        mb.add(xform(bag, mat_trs((-0.40, yc, zf + rs * 0.8), (0, 0, 0.08), (1, 1, 0.8))), mat=m, shade='smooth')
        tube(mb, (-0.45, yc - 0.06, zf + rs * 1.55), (-0.35, yc + 0.06, zf + rs * 1.55), 0.012, 'Trim')
    # spare tyre lying flat, a coil of rope on top
    M = Matrix.Translation((0.20, -1.42, zf + TYRE_W / 2 + 0.005)) @ Matrix.Rotation(-math.pi / 2, 4, 'Y')
    add_wheel(mb, M, R=TYRE_R, W=TYRE_W, lugs=16, segs=14, style='slot')
    for k in range(3):
        ring = bm_lathe([(0.16 + 0.012 * math.cos(a), 0.012 * math.sin(a)) for a in [i * math.pi / 3 for i in range(7)]], 16, axis='Z')
        C.orient(ring, lambda f: (lambda c: c - Vector((c.x, c.y, 0)).normalized() * 0.16)(f.calc_center_median()))
        mb.add(xform(ring, Matrix.Translation((0.20 + 0.01 * k, -1.42 - 0.008 * k, zf + TYRE_W + 0.02 + 0.022 * k))), mat='Rope', shade='smooth')
    # jerry can standing by the tailgate
    mb.add(bm_box_mm((0.32, -2.20, zf), (0.48, -1.86, zf + 0.44), 0.02, 2), mat='CargoRed', shade='auto', angle=40)
    for dx in (-0.035, 0.0, 0.035):
        mb.add(bm_box_mm((0.40 + dx - 0.01, -2.16, zf + 0.44), (0.40 + dx + 0.01, -2.00, zf + 0.47)), mat='CargoRed', shade='flat')
    mb.add(bm_cyl(0.022, 0.022, 0.05, 8, Matrix.Translation((0.40, -1.93, zf + 0.44)), base=True), mat='Trim', shade='auto')


def build_body(mb):
    add_lower_body(mb)
    add_greenhouse(mb)
    add_front(mb)
    add_sides(mb)
    add_interior(mb)
    add_bed(mb)
    add_rear(mb)
    add_chassis(mb)
    add_rollbar(mb)
    add_cargo(mb)


# ------------------------------------------------------------------ front axle
def add_front_axle(mb):
    """vehicle_parts.add_axle(front=True) with the steering linkage kept inside the tyre sweep:
    at 33 deg lock the steered tyre reaches x ~0.60 just ahead of the axle, so the steering arms
    angle inboard and the tie rod ends at +-0.44 instead of +-0.605."""
    s = -1
    hub = TRACK_X - 0.08
    tube_x = TRACK_X - 0.125
    mb.add(bm_cyl_between((-tube_x, 0, 0), (tube_x, 0, 0), 0.046, segs=8), mat='Trim', shade='auto', angle=50)
    for sx in (-1, 1):
        mb.add(bm_cyl_between((sx * 0.12, 0, 0), (sx * 0.32, 0, 0), 0.058, segs=8), mat='Trim', shade='auto', angle=50)
    prof = [(0, -0.125), (0.085, -0.12), (0.122, -0.085), (0.132, -0.02), (0.122, 0.05),
            (0.085, 0.11), (0.048, 0.16), (0.042, 0.205), (0, 0.205)]
    bm = bm_lathe([(r, s * h) for r, h in prof], 12, axis='Y')
    C.orient(bm, lambda f: f.calc_center_median())
    mb.add(xform(bm, Matrix.Translation((0, 0, PINION_Z))), mat='Trim', shade='auto', angle=45)
    cov = bm_lathe([(0.108, -s * 0.118), (0.112, -s * 0.132), (0.09, -s * 0.142), (0, -s * 0.146)], 12, axis='Y')
    C.orient(cov, lambda f: (0, -s, 0))
    mb.add(xform(cov, Matrix.Translation((0, 0, PINION_Z))), mat='Metal', shade='auto', angle=45)
    mb.add(bm_cyl_between((0, s * 0.200, PINION_Z), (0, s * PINION_Y, PINION_Z), 0.052, segs=8), mat='Metal', shade='auto')
    for sx in (-1, 1):
        mb.add(bm_cyl(0.078, 0.078, 0.016, 10, Matrix.Translation((sx * SPRING_X, 0, 0.044)), base=True), mat='Metal', shade='auto')
        mb.add(bm_box((0.05, 0.16, 0.05), (sx * (SPRING_X - 0.10), 0, -0.06), 0.008), mat='Trim', shade='auto')
        # knuckle, hub, steering arm angled inboard to the tie-rod end
        mb.add(bm_cyl(0.068, 0.068, 0.24, 10, Matrix.Translation((sx * (hub - 0.065), 0, -0.12)), base=True), mat='Trim', shade='auto', angle=50)
        mb.add(bm_cyl_between((sx * (hub - 0.085), 0, 0), (sx * hub, 0, 0), 0.095, segs=12), mat='Metal', shade='auto', angle=50)
        mb.add(bm_cyl_between((sx * (hub - 0.13), 0.0, -0.05), (sx * 0.44, 0.19, -0.05), 0.02, segs=6), mat='Trim', shade='auto', angle=50)
        mb.add(C.bm_icosphere(0.026, 1, Matrix.Translation((sx * 0.44, 0.19, -0.05))), mat='Trim', shade='smooth')
    mb.add(bm_cyl_between((-0.44, 0.19, -0.05), (0.44, 0.19, -0.05), 0.019, segs=6), mat='Metal', shade='auto', angle=50)
    # steering damper alongside the tie rod
    mb.add(bm_cyl_between((-0.30, 0.235, -0.03), (0.10, 0.235, -0.03), 0.026, segs=8), mat='CargoRed', shade='auto', angle=50)
    mb.add(bm_cyl_between((0.10, 0.235, -0.03), (0.34, 0.235, -0.03), 0.012, segs=6), mat='Chrome', shade='auto', angle=50)


# ------------------------------------------------------------------ assembly info (for the game)
DIMS = {
    'R': TYRE_R, 'W': TYRE_W, 'wheelbase': WHEELBASE, 'track_x': TRACK_X,
    'spring_x': SPRING_X, 'spring_top': SPRING_TOP_Z, 'spring_seat': SPRING_SEAT_Z,
    'pinion_y': PINION_Y, 'pinion_z': PINION_Z, 'tcase_y': TCASE_Y, 'tcase_z': TCASE_Z,
    # game: hardpoint 0.30, rest 0.43, min 0.13
    'bump': 0.21, 'droop': 0.13, 'lock': 33,
}

LAMPS = {
    'head': [(-0.62, FRONT_Y + 0.062, 0.52), (0.62, FRONT_Y + 0.062, 0.52)],
    'indicator': [(-0.62, FRONT_Y + 0.036, 0.33), (0.62, FRONT_Y + 0.036, 0.33)],
    'bar': [(-0.32, BED_Y0 - 0.12 + 0.07, 1.48), (0.32, BED_Y0 - 0.12 + 0.07, 1.48)],
    'tail': [(-0.785, BED_Y1 - 0.03, 0.66), (0.785, BED_Y1 - 0.03, 0.66)],
    'brake': [(-0.785, BED_Y1 - 0.03, 0.66), (0.785, BED_Y1 - 0.03, 0.66)],
    'reverse': [(-0.785, BED_Y1 - 0.03, 0.455), (0.785, BED_Y1 - 0.03, 0.455)],
    'winch': [(0.0, 2.15, 0.22)],
    'hitch': [(0.0, BED_Y1 - 0.225, 0.268)],
}


def main():
    C.reset_scene()
    mats = make_materials()
    col = C.collection('Vehicle')
    parts, tris = {}, {}
    builders = {
        'Body': build_body,
        'Wheel': lambda mb: add_wheel(mb, R=TYRE_R, W=TYRE_W, lugs=18, style='slot'),
        'AxleFront': add_front_axle,
        'AxleRear': lambda mb: P.add_axle(mb, False, TRACK_X, SPRING_X, PINION_Y, PINION_Z),
        'Spring': P.add_spring,
        'Driveshaft': P.add_driveshaft,
    }
    for name, fn in builders.items():
        mb = C.MeshBuilder(name)
        fn(mb)
        tris[name] = mb.tris()
        parts[name] = mb.build(mats, vcolor=False, collection_obj=col)
    print('VEHICLE ranger TRIS', tris, 'total', sum(tris.values()))
    bpy.context.view_layer.update()   # text helpers delete temp objects; refresh before export
    P.export_vehicle('ranger', parts, DIMS, LAMPS, tris)
    import vehicle_check
    vehicle_check.run(parts, dict(DIMS, id='ranger'))
    P.render_previews('ranger', parts, col, DIMS)
    C.save_blend('vehicle_ranger.blend')
    return tris


if __name__ == '__main__':
    main()
