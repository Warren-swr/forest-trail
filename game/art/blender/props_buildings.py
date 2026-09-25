"""Landmark buildings for Forest Trail: cabin, lookout (+fire tower), shed, dock, bridge_plank."""
import bmesh, math
from mathutils import Vector, Matrix, Euler

import common as C
from common import hexc, mix, bm_box, bm_cyl_between, bm_from, xform
from props_lib import (Kit, UP, WOOD_D, WOOD_L, WOOD_DARK, WOOD_GREY, ROOF_D, ROOF_RED, WINDOW,
                       STONE_D, STONE_L, METAL, DARK)

GLASS_DARK = hexc('#2F3E44')
GLOW = hexc('#FFD28A')


class GlowKit(Kit):
    """Kit whose window panes and lamp glass use the second material 'Glow'
    (the game drives its emission at night)."""

    def window(self, x0, x1, z0, z1, y, facing=1, frame=0.07, depth=0.08, mullion=True, col=WINDOW):
        f = facing
        self.box((x0, y - 0.01 * f, z0), (x1, y + 0.03 * f, z1), col, jitter=0.02, mat='Glow')
        fc = WOOD_DARK
        yo0, yo1 = sorted((y, y + depth * f))
        self.box((x0 - frame, yo0, z0 - frame), (x1 + frame, yo1, z0), fc)
        self.box((x0 - frame, yo0, z1), (x1 + frame, yo1, z1 + frame), fc)
        self.box((x0 - frame, yo0, z0), (x0, yo1, z1), fc)
        self.box((x1, yo0, z0), (x1 + frame, yo1, z1), fc)
        if mullion:
            xm, zm = (x0 + x1) / 2, (z0 + z1) / 2
            self.box((xm - 0.025, yo0, z0), (xm + 0.025, yo1, z1), fc)
            self.box((x0, yo0, zm - 0.025), (x1, yo1, zm + 0.025), fc)

    def lamp(self, x, y, z, r=0.09, h=0.2):
        """Small hanging lantern: dark cap + Glow glass + wire."""
        self.box((x - r, y - r, z - h / 2), (x + r, y + r, z + h / 2), GLOW, jitter=0.0, mat='Glow')
        self.box((x - r * 1.2, y - r * 1.2, z + h / 2), (x + r * 1.2, y + r * 1.2, z + h / 2 + 0.05), DARK)
        self.box((x - r * 1.1, y - r * 1.1, z - h / 2 - 0.04), (x + r * 1.1, y + r * 1.1, z - h / 2), DARK)
        self.log((x, y, z + h / 2 + 0.05), (x, y, z + h / 2 + 0.35), 0.01, DARK, segs=3)

    def build(self, mats, col):
        if 'Glow' not in mats:
            mats = dict(mats, Glow=C.mat_vc('Glow', roughness=0.4))
        return self.mb.build(mats, vcolor=True, collection_obj=col)


def roof_slab(k, outer_lo, outer_hi, inner_lo, inner_hi, y0, y1, top_col, under_col, edge_col):
    """Sloped roof plate from a convex (x,z) quad, extruded along Y."""
    pts = [outer_lo, inner_lo, inner_hi, outer_hi]
    bm = C.bm_extrude_poly(pts, y1 - y0, 'Y', (y0 + y1) / 2)
    ox = outer_hi[0] - outer_lo[0]
    oz = outer_hi[1] - outer_lo[1]
    n_out = Vector((-oz, 0, ox)).normalized()
    if n_out.z < 0:
        n_out = -n_out

    def cfn(l, f):
        n = f.normal
        if abs(n.y) > 0.9:
            return edge_col
        if n.dot(n_out) > 0.8:
            return top_col
        if n.dot(n_out) < -0.8:
            return under_col
        return edge_col
    k.mb.add(bm, color_fn=cfn, shade='flat', jitter=0.03)
    return n_out


# ------------------------------------------------------------------ cabin
def build_cabin():
    """A-frame cabin, footprint ~7 m (X) x 9 m (Y); porch, steps and door face +Y."""
    k = GlowKit('cabin', 301)
    Y0, Y1 = -4.4, 2.4              # enclosed body
    FL = 0.5                         # floor level
    # stone plinth, blocks with colour variation
    for i in range(6):
        ya, yb = Y0 + (Y1 - Y0) * i / 6, Y0 + (Y1 - Y0) * (i + 1) / 6
        k.box((-3.1, ya, 0.0), (3.1, yb, FL), k.stone(), jitter=0.02)
    # knee walls
    for s in (-1, 1):
        k.box((min(s * 3.1, s * 2.95), Y0, FL), (max(s * 3.1, s * 2.95), Y1, 1.16), k.wood(0.6))
    # gable walls, board-and-batten strips
    top_z = lambda x: 1.12 + (3.1 - abs(x)) / 3.1 * (6.9 - 1.12)
    nstrip = 10
    for yc, facing in ((Y1 - 0.08, 1), (Y0 + 0.08, -1)):
        for i in range(nstrip):
            xa, xb = -3.1 + 6.2 * i / nstrip, -3.1 + 6.2 * (i + 1) / nstrip
            pts = [(xa, FL), (xb, FL), (xb, top_z(xb))]
            if xa < 0 < xb:
                pts.append((0.0, 6.9))
            pts.append((xa, top_z(xa)))
            k.poly(pts, 0.16, 'Y', yc, mix(WOOD_D, WOOD_L, 0.45 + 0.4 * ((i * 7) % 3) / 2), jitter=0.02)
            if i:
                k.box((xa - 0.03, yc + facing * 0.08, FL), (xa + 0.03, yc + facing * 0.12, top_z(xa) - 0.05),
                      WOOD_D, jitter=0.02)
    # roof: two plates + shingle courses + ridge cap
    ang = math.atan2(7.2 - 0.75, 3.55)
    for s in (-1, 1):
        n_out = roof_slab(k, (s * 3.55, 0.75), (0.0, 7.2), (s * 3.3, 0.75), (0.0, 6.85), Y0 - 0.25, Y1 + 0.45,
                          ROOF_RED, WOOD_D, WOOD_DARK)
        for j in range(1, 8):
            t = j / 8.4
            p = Vector((s * 3.55 * (1 - t), 0, 0.75 + 6.45 * t))
            c = p + Vector((s * abs(n_out.x), 0, n_out.z)) * 0.02
            bm = bm_box((0.16, Y1 - Y0 + 0.72, 0.045), (0, 0, 0))
            xform(bm, Matrix.Translation((c.x, (Y0 + Y1) / 2 + 0.1, c.z)) @ Euler((0, s * ang, 0)).to_matrix().to_4x4())
            k.mb.add(bm, color=mix(ROOF_RED, ROOF_D, 0.25 + 0.15 * (j % 2)), shade='flat', jitter=0.04)
    k.beam((0, Y0 - 0.3, 7.2), (0, Y1 + 0.5, 7.2), 0.26, 0.2, WOOD_DARK, roll=math.pi / 4)
    # front gable: door, windows (warm light), lantern
    yf = Y1
    k.box((-0.5, yf, FL), (0.5, yf + 0.06, 2.6), WOOD_DARK)
    k.window(-0.18, 0.18, 1.85, 2.35, yf + 0.06, 1, 0.05, 0.04, mullion=False)
    k.box((0.32, yf + 0.06, 1.45), (0.4, yf + 0.12, 1.55), METAL)
    for xa, xb in ((-2.2, -1.1), (1.1, 2.2)):
        k.window(xa, xb, 1.3, 2.4, yf, 1)
    k.window(-0.9, 0.9, 3.2, 4.6, yf, 1)
    k.window(-0.32, 0.32, 5.1, 5.75, yf, 1, mullion=False)
    k.box((0.75, yf, 2.15), (0.95, yf + 0.2, 2.45), WINDOW, jitter=0.0, mat='Glow')
    k.window(-0.6, 0.6, 3.0, 4.0, Y0, -1)
    k.window(-1.9, -1.0, 1.3, 2.2, Y0, -1)
    # chimney (stacked stone) through the right roof plate
    z = FL
    for i in range(7):
        h = 0.85 + k.rng.uniform(-0.1, 0.1)
        z1 = min(6.3, z + h)
        o = k.rng.uniform(-0.03, 0.03)
        k.box((1.15 + o, -2.4 + o, z), (1.95 + o, -1.6 - o, z1), k.stone(), jitter=0.02)
        z = z1
        if z >= 6.3:
            break
    k.box((1.08, -2.47, 6.3), (2.02, -1.53, 6.42), STONE_D)
    k.box((1.35, -2.2, 6.42), (1.75, -1.8, 6.6), DARK)
    # porch deck, posts, railing and steps
    P0, P1 = Y1, 4.1
    k.planks_x(-3.1, 3.1, P0, P1, FL - 0.07, FL, 7)
    for x in (-3.0, -1.0, 1.0, 3.0):
        for y in (P0 + 0.2, P1 - 0.1):
            k.post(x, y, 0.0, FL - 0.07, 0.18, k.wood(0.2))
    k.railing([(-3.0, P0 + 0.05), (-3.0, P1 - 0.05), (-0.75, P1 - 0.05)], FL, 0.95, 1.2)
    k.railing([(0.75, P1 - 0.05), (3.0, P1 - 0.05), (3.0, P0 + 0.05)], FL, 0.95, 1.2)
    for i in range(3):
        y0 = P1 + 0.3 * i
        k.box((-0.75, y0, 0.0), (0.75, y0 + 0.32, FL - 0.07 - i * 0.14), k.wood(0.5))
    # firewood stacked under the left eave
    for row in range(3):
        for j in range(5):
            y = -3.6 + j * 0.9 + (0.45 if row % 2 else 0)
            yz = 0.12 + row * 0.22
            if y < -0.4:
                k.log((-3.35, y - 0.4, yz), (-3.35, y + 0.4, yz), 0.11, k.wood(), segs=5)
                if row < 2:
                    k.log((-3.58, y - 0.4, yz), (-3.58, y + 0.4, yz), 0.11, k.wood(), segs=5)
    return k


# ------------------------------------------------------------------ lookout
def build_lookout():
    """Ridge viewpoint: 6 x 4 m deck at 1.2 m (centred on the origin, view side +Y) with rails,
    stairs (-Y), bench and a coin-operated viewer; a ~9.2 m wooden fire tower stands at x = +8."""
    k = GlowKit('lookout', 302)
    DZ = 1.2
    k.planks_x(-3.0, 3.0, -2.0, 2.0, DZ - 0.08, DZ, 11)
    for x in (-2.85, 0.0, 2.85):
        for y in (-1.85, 0.0, 1.85):
            k.post(x, y, 0.0, DZ - 0.08, 0.18, k.wood(0.2))
        k.beam((x, -1.85, 0.25), (x, 1.85, DZ - 0.2), 0.08, 0.08, k.wood(0.3))
    for y in (-1.85, 1.85):
        k.box((-3.0, y - 0.08, DZ - 0.3), (3.0, y + 0.08, DZ - 0.08), k.wood(0.3))
    k.railing([(-0.7, -1.95), (-2.95, -1.95), (-2.95, 1.95), (2.95, 1.95), (2.95, -1.95), (0.7, -1.95)],
              DZ, 1.05, 1.5)
    # stairs down to -Y
    steps = 6
    for i in range(steps):
        z = DZ - (i + 1) * DZ / (steps + 0.2)
        y = -2.0 - (i + 0.5) * 0.3
        k.box((-0.65, y - 0.15, z - 0.05), (0.65, y + 0.15, z), k.wood(0.5))
    for x in (-0.72, 0.72):
        k.beam((x, -2.0, DZ - 0.05), (x, -2.0 - 0.3 * steps - 0.1, 0.0), 0.06, 0.22, k.wood(0.2))
        k.beam((x, -2.0, DZ + 0.95), (x, -2.0 - 0.3 * steps, 0.95), 0.07, 0.07, WOOD_L)
        k.post(x, -2.0 - 0.3 * steps, 0.0, 0.95, 0.1, k.wood(0.3))
    # bench facing the view
    k.planks_x(-1.9, -0.3, -1.45, -1.05, DZ + 0.42, DZ + 0.46, 2)
    k.planks_x(-1.9, -0.3, -1.52, -1.46, DZ + 0.55, DZ + 0.85, 1)
    for x in (-1.8, -0.4):
        k.box((x - 0.04, -1.5, DZ), (x + 0.04, -1.1, DZ + 0.42), WOOD_DARK)
    # coin-operated viewer
    vx, vy = 1.4, 1.45
    body = hexc('#3F5A4E')
    k.log((vx, vy, DZ), (vx, vy, DZ + 1.0), 0.05, METAL, segs=6)
    k.box((vx - 0.14, vy - 0.14, DZ), (vx + 0.14, vy + 0.14, DZ + 0.05), METAL)
    k.cbox((0.34, 0.26, 0.24), (vx, vy, DZ + 1.14), body, rot=(0.15, 0, 0), bev=0.03)
    for s in (-1, 1):
        k.log((vx + s * 0.08, vy + 0.1, DZ + 1.16), (vx + s * 0.08, vy + 0.24, DZ + 1.18), 0.06, body, segs=8)
        k.log((vx + s * 0.08, vy + 0.24, DZ + 1.18), (vx + s * 0.08, vy + 0.25, DZ + 1.18), 0.05, GLASS_DARK, segs=8)
        k.log((vx + s * 0.06, vy - 0.12, DZ + 1.14), (vx + s * 0.06, vy - 0.2, DZ + 1.14), 0.03, DARK, segs=6)
    build_fire_tower(k, Vector((8.0, 0.5, 0.0)))
    return k


def build_fire_tower(k, base):
    bx, by = base.x, base.y
    B, T, H = 1.7, 1.1, 6.4             # half-size at the ground / under the cab, cab floor height
    corner = lambda z, sx, sy: Vector((bx + sx * (B + (T - B) * z / H), by + sy * (B + (T - B) * z / H), z))
    legs = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for sx, sy in legs:
        k.beam(corner(0, sx, sy), corner(H, sx, sy), 0.22, 0.22, k.wood(0.25))
        k.box((corner(0, sx, sy).x - 0.25, corner(0, sx, sy).y - 0.25, 0.0),
              (corner(0, sx, sy).x + 0.25, corner(0, sx, sy).y + 0.25, 0.25), STONE_L)
    levels = [0.3, 2.3, 4.3, H - 0.1]
    for (ax, ay), (bx2, by2) in zip(legs, legs[1:] + legs[:1]):
        for z0, z1 in zip(levels, levels[1:]):
            k.beam(corner(z0, ax, ay), corner(z0, bx2, by2), 0.12, 0.14, k.wood(0.4))
            k.beam(corner(z0, ax, ay), corner(z1, bx2, by2), 0.09, 0.09, k.wood(0.5))
            k.beam(corner(z0, bx2, by2), corner(z1, ax, ay), 0.09, 0.09, k.wood(0.5))
    # cab floor with catwalk, railing
    F = T + 0.55
    k.planks_x(bx - F, bx + F, by - F, by + F, H, H + 0.12, 6)
    k.railing([(bx - F + 0.05, by - F + 0.05), (bx + F - 0.05, by - F + 0.05), (bx + F - 0.05, by + F - 0.05),
               (bx - F + 0.05, by + F - 0.05), (bx - F + 0.05, by - F + 0.05)], H + 0.12, 1.0, 1.1, 0.08, (0.5, 0.95))
    # cab: lower wall, window band with posts, roof
    W = 1.1
    z0 = H + 0.12
    k.box((bx - W, by - W, z0), (bx + W, by + W, z0 + 0.95), mix(WOOD_L, WOOD_GREY, 0.3))
    k.box((bx - W + 0.04, by - W + 0.04, z0 + 0.95), (bx + W - 0.04, by + W - 0.04, z0 + 1.85), GLASS_DARK, jitter=0.0)
    for sx in (-1, 0, 1):
        for sy in (-1, 0, 1):
            if sx == 0 and sy == 0:
                continue
            x, y = bx + sx * (W - 0.02), by + sy * (W - 0.02)
            k.box((x - 0.05, y - 0.05, z0 + 0.95), (x + 0.05, y + 0.05, z0 + 1.85), WOOD_DARK)
    k.box((bx - W - 0.02, by - W - 0.02, z0 + 1.85), (bx + W + 0.02, by + W + 0.02, z0 + 1.97), WOOD_DARK)
    k.lamp(bx, by, z0 + 1.5, 0.12, 0.26)
    R, rz = W + 0.45, z0 + 1.97
    apex = Vector((bx, by, rz + 1.05))
    verts = [Vector((bx - R, by - R, rz)), Vector((bx + R, by - R, rz)), Vector((bx + R, by + R, rz)),
             Vector((bx - R, by + R, rz)), apex]
    roof = bm_from(verts, [[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4], [3, 2, 1, 0]])
    bmesh.ops.recalc_face_normals(roof, faces=roof.faces)
    k.mb.add(roof, color_fn=lambda l, f: ROOF_D if f.normal.z > 0 else WOOD_D, shade='flat', jitter=0.04)
    k.log(apex - Vector((0, 0, 0.1)), apex + Vector((0, 0, 0.35)), 0.025, METAL, segs=4)
    # ladder up the -Y face
    ly0, ly1 = corner(0, 0, -1).y - 0.35, corner(H, 0, -1).y - 0.3
    for s in (-1, 1):
        k.beam((bx + s * 0.28, ly0, 0.0), (bx + s * 0.28, ly1, H + 1.0), 0.07, 0.07, WOOD_DARK)
    n = 18
    for i in range(1, n):
        t = i / n
        y = ly0 + (ly1 - ly0) * t
        k.beam((bx - 0.28, y, t * (H + 1.0)), (bx + 0.28, y, t * (H + 1.0)), 0.04, 0.04, k.wood(0.6))


# ------------------------------------------------------------------ shed
def build_shed():
    """Old sawmill shed: open front (+Y), 6 x 4 m, lean-to roof, lumber stack, saw bench, log pile."""
    k = GlowKit('shed', 303)
    rust, rust_d = hexc('#7A4E3A'), hexc('#5A3B2E')
    zf, zb = 3.3, 2.45                     # roof height at front / back
    zroof = lambda y: zb + (zf - zb) * (y + 2.0) / 4.0
    for x in (-3.0, -1.0, 1.0, 3.0):
        k.post(x, 2.0, 0.0, zroof(2.0), 0.2, k.wood(0.2))
        k.post(x, -2.0, 0.0, zroof(-2.0), 0.2, k.wood(0.2))
        k.beam((x, -2.1, zroof(-2.1) - 0.05), (x, 2.1, zroof(2.1) - 0.05), 0.1, 0.18, k.wood(0.3))
    for y in (-2.0, 2.0):
        k.box((-3.1, y - 0.1, zroof(y) - 0.4), (3.1, y + 0.1, zroof(y) - 0.12), k.wood(0.3))
    # corrugated roof: plate + ribs running down the slope
    ang = math.atan2(zf - zb, 4.0)
    L = 4.8 / math.cos(ang)
    ctr = Vector((0, 0, (zf + zb) / 2 + 0.02))
    bm = bm_box((6.8, L, 0.05), (0, 0, 0))
    xform(bm, Matrix.Translation(ctr) @ Euler((ang, 0, 0)).to_matrix().to_4x4())
    k.mb.add(bm, color_fn=lambda l, f: rust if f.normal.z > 0.5 else rust_d, shade='flat', jitter=0.05)
    for i in range(14):
        x = -3.25 + 6.5 * i / 13
        bm = bm_box((0.07, L, 0.05), (x, 0, 0.04))
        xform(bm, Matrix.Translation(ctr) @ Euler((ang, 0, 0)).to_matrix().to_4x4())
        k.mb.add(bm, color=mix(rust, rust_d, k.rng.random()), shade='flat', jitter=0.08)
    # back wall and left side wall (vertical weathered boards)
    for i in range(14):
        xa, xb = -3.0 + 6.0 * i / 14, -3.0 + 6.0 * (i + 1) / 14 - 0.02
        k.box((xa, -2.08, 0.0), (xb, -1.96, zroof(-2.0) - 0.1 - k.rng.uniform(0, 0.15)),
              mix(WOOD_GREY, WOOD_D, k.rng.uniform(0.1, 0.6)))
    for i in range(8):
        ya, yb = -2.0 + 3.0 * i / 8, -2.0 + 3.0 * (i + 1) / 8 - 0.02
        k.box((-3.08, ya, 0.0), (-2.96, yb, zroof(yb) - 0.45 - k.rng.uniform(0, 0.2)),
              mix(WOOD_GREY, WOOD_D, k.rng.uniform(0.1, 0.6)))
    # stacked lumber with spacers
    for layer in range(5):
        z = 0.12 + layer * 0.14
        for j in range(6):
            x = -2.4 + j * 0.25
            k.box((x, -1.7, z), (x + 0.22, 0.6, z + 0.1), mix(WOOD_L, hexc('#B08556'), k.rng.uniform(0.2, 0.8)))
        for y in (-1.5, -0.55, 0.4):
            k.box((-2.45, y - 0.04, z - 0.04), (-0.9, y + 0.04, z), WOOD_DARK)
    # saw bench with a big circular blade
    k.box((0.2, -0.6, 0.0), (0.35, 1.2, 0.8), WOOD_DARK)
    k.box((2.0, -0.6, 0.0), (2.15, 1.2, 0.8), WOOD_DARK)
    k.box((0.1, -0.7, 0.8), (2.25, 1.3, 0.9), k.wood(0.4))
    blade = C.bm_cyl(0.42, 0.42, 0.012, 14, Matrix.Translation((1.2, 0.3, 0.95)) @ Euler((0, math.pi / 2, 0)).to_matrix().to_4x4())
    k.mb.add(blade, color=METAL, shade='flat')
    k.log((1.12, 0.3, 0.95), (1.28, 0.3, 0.95), 0.05, DARK, segs=6)
    # log pile outside the right wall
    for row, xs in enumerate(((3.7, 4.05, 4.4, 4.75), (3.87, 4.22, 4.57), (4.05, 4.4))):
        for x in xs:
            z = 0.17 + row * 0.3
            k.log((x, -1.9, z), (x, 1.9, z), 0.17, k.wood(0.15), segs=7)
    k.box((3.45, -0.1, 0.0), (3.55, 0.1, 0.5), WOOD_DARK)
    k.box((4.95, -0.1, 0.0), (5.05, 0.1, 0.5), WOOD_DARK)
    # work lamp hanging under the roof at the open front
    k.lamp(1.2, 1.6, zroof(1.6) - 0.7)
    return k


# ------------------------------------------------------------------ dock
def build_dock():
    """Lake dock: starts at the shore at y=0 and runs 10 m along +Y; deck top 0.5 m, 2 m wide.
    Pilings reach down to z=-1.5 (below the water line)."""
    k = Kit('dock', 304)
    DZ, W = 0.5, 1.0
    k.planks_x(-W, W, 0.0, 10.0, DZ - 0.06, DZ, 30, gap=0.03)
    for x in (-0.75, 0.0, 0.75):
        k.box((x - 0.06, 0.0, DZ - 0.24), (x + 0.06, 10.0, DZ - 0.06), k.wood(0.2))
    for y in (0.3, 2.7, 5.1, 7.5, 9.8):
        for s in (-1, 1):
            top = DZ + (0.45 if y > 9 or y < 1 else -0.06)
            k.log((s * (W + 0.1), y, -1.5), (s * (W + 0.1), y, top), 0.12, k.wood(0.15), segs=7)
        k.beam((-W - 0.1, y, DZ - 0.2), (W + 0.1, y, DZ - 0.2), 0.1, 0.16, k.wood(0.2))
        k.beam((-W - 0.1, y, -0.9), (W + 0.1, y, DZ - 0.25), 0.07, 0.07, k.wood(0.3))
    for y in (4.0, 8.6):
        for s in (-1, 1):
            k.box((s * (W - 0.12) - 0.05, y - 0.15, DZ), (s * (W - 0.12) + 0.05, y + 0.15, DZ + 0.06), DARK)
    # swim ladder at the end
    for s in (-1, 1):
        k.log((s * 0.3, 10.1, -1.0), (s * 0.3, 10.1, DZ + 0.6), 0.025, METAL, segs=5)
    for i in range(4):
        z = -0.7 + i * 0.35
        k.log((-0.3, 10.1, z), (0.3, 10.1, z), 0.018, METAL, segs=4)
    # a coil of rope
    k.log((0.45, 9.2, DZ), (0.45, 9.2, DZ + 0.08), 0.2, hexc('#C8B88E'), segs=10)
    return k


# ------------------------------------------------------------------ bridge
def build_bridge_plank():
    """Log-and-plank bridge: 6 m span along Y, 3 m wide deck, deck top at 0.46 m.
    Log sills at both ends sit on the ground (origin = centre at ground level)."""
    k = Kit('bridge_plank', 305)
    for y in (-2.9, 2.9):
        k.log((-1.7, y, 0.14), (1.7, y, 0.14), 0.16, k.wood(0.1), segs=8)
    for x in (-1.05, 0.0, 1.05):
        k.log((x, -3.1, 0.24), (x, 3.1, 0.24), 0.14, k.wood(0.15), segs=8)
    k.planks_x(-1.5, 1.5, -3.0, 3.0, 0.38, 0.46, 18, gap=0.035)
    for s in (-1, 1):
        k.box((s * 1.38 - 0.1, -3.0, 0.46), (s * 1.38 + 0.1, 3.0, 0.62), k.wood(0.3))
        for y in (-2.4, 0.0, 2.4):
            k.box((s * 1.38 - 0.03, y - 0.05, 0.62), (s * 1.38 + 0.03, y + 0.05, 0.66), METAL)
    return k
