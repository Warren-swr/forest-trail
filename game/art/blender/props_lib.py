"""Shared building blocks for the Forest Trail props (wood, stone, cloth)."""
import bmesh, math, random
from mathutils import Vector, Matrix, Euler

import common as C
from common import hexc, mix, bm_box, bm_box_mm, bm_cyl_between, bm_hull, bm_from, bm_extrude_poly, xform, mat_trs

UP = Vector((0, 0, 1))
WOOD_D, WOOD_L = hexc('#6B4A32'), hexc('#8C6440')
WOOD_DARK = hexc('#4A3526')
WOOD_GREY = hexc('#8A7F70')          # weathered boards
ROOF_D = hexc('#3E3A36')
ROOF_RED = hexc('#8C4A36')
WINDOW = hexc('#F2C66D')
STONE_D, STONE_L = hexc('#6F706A'), hexc('#8A8B83')
METAL = hexc('#8E9092')
DARK = hexc('#2B2826')


class Kit:
    """Thin wrapper around a MeshBuilder with wood/stone helpers."""

    def __init__(self, name, seed):
        self.mb = C.MeshBuilder(name, seed=seed)
        self.rng = random.Random(seed)

    # colours
    def wood(self, t=None):
        t = self.rng.random() if t is None else t
        return mix(WOOD_D, WOOD_L, t)

    def stone(self):
        return mix(STONE_D, STONE_L, self.rng.random())

    # geometry
    def box(self, mn, mx, col, bev=0.0, jitter=0.03, mat='VC'):
        self.mb.add(bm_box_mm(mn, mx, bev), color=col, shade='flat', jitter=jitter, mat=mat)

    def cbox(self, size, center, col, rot=(0, 0, 0), bev=0.0, jitter=0.03):
        self.mb.add(bm_box(size, center, bev, 1, rot), color=col, shade='flat', jitter=jitter)

    def beam(self, p1, p2, w, h=None, col=None, roll=0.0, jitter=0.03):
        """Rectangular timber from p1 to p2 (w x h cross-section)."""
        h = w if h is None else h
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        L = d.length
        z = d.normalized()
        ref = UP if abs(z.dot(UP)) < 0.95 else Vector((1, 0, 0))
        x = ref.cross(z).normalized()
        y = z.cross(x)
        R = Matrix((x, y, z)).transposed().to_4x4() @ Matrix.Rotation(roll, 4, 'Z')
        bm = bm_box((w, h, L), (0, 0, L / 2))
        xform(bm, Matrix.Translation(p1) @ R)
        self.mb.add(bm, color=col or self.wood(), shade='flat', jitter=jitter)

    def log(self, p1, p2, r, col=None, segs=7, r2=None, cap=True):
        bm = bm_cyl_between(p1, p2, r, segs=segs, r2=r2, cap=cap, rot=self.rng.uniform(0, 1))
        self.mb.add(bm, color=col or self.wood(0.2), shade='auto', angle=40, jitter=0.05)

    def post(self, x, y, z0, z1, w=0.14, col=None):
        self.box((x - w / 2, y - w / 2, z0), (x + w / 2, y + w / 2, z1), col or self.wood())

    def planks_x(self, x0, x1, y0, y1, z0, z1, n, gap=0.012, cols=None):
        """n boards running along X, laid side by side across Y."""
        step = (y1 - y0) / n
        for i in range(n):
            self.box((x0, y0 + i * step + gap / 2, z0), (x1, y0 + (i + 1) * step - gap / 2, z1 + self.rng.uniform(-0.006, 0.006)),
                     self.wood())

    def planks_y(self, x0, x1, y0, y1, z0, z1, n, gap=0.012):
        step = (x1 - x0) / n
        for i in range(n):
            self.box((x0 + i * step + gap / 2, y0, z0), (x0 + (i + 1) * step - gap / 2, y1, z1 + self.rng.uniform(-0.006, 0.006)),
                     self.wood())

    def rock(self, center, size, n=10, sink=0.3, col=None):
        rng = self.rng
        pts = []
        for _ in range(n):
            d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
            p = Vector((d.x * size[0] / 2, d.y * size[1] / 2, max(d.z, -0.4) * size[2] / 2))
            pts.append(p * rng.uniform(0.85, 1.1))
        bm = bm_hull(pts)
        zmin = min(v.co.z for v in bm.verts)
        bmesh.ops.translate(bm, vec=Vector(center) - Vector((0, 0, zmin + sink * size[2])), verts=bm.verts)
        self.mb.add(bm, color=col or self.stone(), shade='flat', jitter=0.06)

    def poly(self, pts, depth, axis, center, col, jitter=0.03, M=None):
        bm = bm_extrude_poly(pts, depth, axis, center)
        if M is not None:
            xform(bm, M)
        self.mb.add(bm, color=col, shade='flat', jitter=jitter)

    def window(self, x0, x1, z0, z1, y, facing=1, frame=0.07, depth=0.08, mullion=True, col=WINDOW):
        """Warm-lit window on a wall plane at y (facing +Y if facing>0), in the XZ plane."""
        f = facing
        self.box((x0, y - 0.01 * f, z0), (x1, y + 0.03 * f, z1), col, jitter=0.02)
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

    def railing(self, pts, z0, h=1.0, post_every=1.5, w=0.1, rails=(0.45, 0.95), col=None):
        """Posts + horizontal rails along a polyline at deck height z0."""
        col = col or WOOD_L
        for a, b in zip(pts, pts[1:]):
            a, b = Vector(a), Vector(b)
            L = (b - a).length
            n = max(1, round(L / post_every))
            for i in range(n + 1):
                p = a.lerp(b, i / n)
                self.post(p.x, p.y, z0, z0 + h, w, self.wood(0.35))
            for r in rails:
                self.beam(Vector((a.x, a.y, z0 + r * h)), Vector((b.x, b.y, z0 + r * h)), w * 0.6, w * 0.8, col)

    def build(self, mats, col):
        return self.mb.build(mats, vcolor=True, collection_obj=col)
