"""Shared running gear and export helpers for the Forest Trail vehicles.

Blender coords: +Y front, +Z up, +X = vehicle right. Origin = midpoint between axles at
static wheel-centre height; the ground is at Z = -tyre radius.

Every vehicle exports vehicle_<id>.glb with top-level nodes Body, Wheel, AxleFront,
AxleRear, Spring, Driveshaft (all at the origin; the game places them) and a sidecar
vehicle_<id>.json with the suspension mounts and lamp positions in game coordinates
(game = (x, z, -y) of Blender: +Y up, front = -Z).
"""
import bpy, math, os, json, sys
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
from common import bm_box, bm_box_mm, bm_cyl, bm_cyl_between, bm_lathe, bm_from, xform


def base_materials(paint='#B75B3D', accent='#E8DFC8', rim='#DCD4C0'):
    """Material set shared by all vehicles. Names are fixed: the game swaps paint,
    drives lamp emission and adds mud per material name."""
    return {
        'Paint': C.mat_pbr('Paint', paint, 0.42, 0.0),
        'PaintAccent': C.mat_pbr('PaintAccent', accent, 0.5, 0.0),
        'Trim': C.mat_pbr('Trim', '#262624', 0.62, 0.0),
        'Rubber': C.mat_pbr('Rubber', '#1B1B1A', 0.85, 0.0),
        'Metal': C.mat_pbr('Metal', '#A9ABAA', 0.38, 0.75),
        'Chrome': C.mat_pbr('Chrome', '#D8DADA', 0.16, 1.0),
        'Glass': C.mat_pbr('Glass', '#1E2A31', 0.06, 0.0),
        'Lamp': C.mat_pbr('Lamp', '#F6F0DE', 0.12, 0.0, emission='#FFF1C9', emit_strength=0.6),
        'LampAux': C.mat_pbr('LampAux', '#F3EEDF', 0.12, 0.0, emission='#FFF1C9', emit_strength=0.3),
        'LampAmber': C.mat_pbr('LampAmber', '#E0901F', 0.15, 0.0, emission='#FF9A1E', emit_strength=0.3),
        'LampRear': C.mat_pbr('LampRear', '#A3231A', 0.15, 0.0, emission='#B01E12', emit_strength=0.4),
        'LampReverse': C.mat_pbr('LampReverse', '#E9E6DE', 0.15, 0.0),
        'Interior': C.mat_pbr('Interior', '#3B3A37', 0.8, 0.0),
        'Canvas': C.mat_pbr('Canvas', '#5A5E4A', 0.9, 0.0),
        'Decal': C.mat_pbr('Decal', '#EDEBE4', 0.35, 0.2),
        'Tire': C.mat_pbr('Tire', '#252422', 0.9, 0.0),
        'Rim': C.mat_pbr('Rim', rim, 0.45, 0.3),
    }


# ------------------------------------------------------------------ wheel
REF_R, REF_W = 0.38, 0.30


def add_wheel(mb, M=Matrix(), R=REF_R, W=REF_W, tire='Tire', rim='Rim', lugs=15, segs=16, style='steel',
              sidewall_lugs=0, tread_bevel=0):
    """Wheel centred at origin, axle along X, outer face +X (before transform M).
    Geometry is authored for a 0.38 x 0.30 tyre and scaled to R x W.
    style: 'steel' (dished with round vents), 'slot' (slotted steel), 'spoke' (6-spoke alloy).
    sidewall_lugs: number of raised shoulder blocks per sidewall (0 = plain sidewall)."""
    M = M @ Matrix.Diagonal((W / REF_W, R / REF_R, R / REF_R, 1))

    def radial(c):
        v = Vector((0, c.y, c.z))
        return v.normalized() if v.length > 1e-6 else Vector((0, 0, 1))

    prof = [(0.235, -0.125), (0.278, -0.148), (0.318, -0.153), (0.345, -0.140), (0.357, -0.112),
            (0.358, 0.0), (0.357, 0.112), (0.345, 0.140), (0.318, 0.153), (0.278, 0.148), (0.235, 0.125)]
    bm = bm_lathe(prof, segs, axis='X')
    C.orient(bm, lambda f: f.calc_center_median() - radial(f.calc_center_median()) * 0.30)
    mb.add(xform(bm, M), mat=tire, shade='auto', angle=50)
    # tread lugs: two staggered rows of chevron blocks wrapping over the shoulders
    pitch = 2 * math.pi / lugs
    hw = pitch * 0.29
    xs = [0.012, 0.128, 0.168]
    tops = [0.381, 0.378, 0.332]
    bots = [0.347, 0.345, 0.292]
    for k in range(lugs):
        for side in (1, -1):
            a0 = k * pitch + (0 if side > 0 else pitch / 2)
            verts, faces = [], []
            for x, rt, rb in zip(xs, tops, bots):
                ac = a0 + 0.9 * x
                for r, a in ((rt, ac - hw), (rt, ac + hw), (rb, ac + hw), (rb, ac - hw)):
                    verts.append((side * x, r * math.cos(a), r * math.sin(a)))
            for s in range(len(xs) - 1):
                b, n = 4 * s, 4 * (s + 1)
                faces += [[b, b + 1, n + 1, n], [b + 1, b + 2, n + 2, n + 1], [b + 3, b, n, n + 3]]
            faces += [[0, 3, 2, 1], [8, 9, 10, 11]]
            blk = bm_from(verts, faces)
            cen = sum((Vector(v) for v in verts), Vector()) / len(verts)
            C.orient(blk, lambda f: f.calc_center_median() - cen)
            if tread_bevel:
                C.bevel(blk, tread_bevel, 2)
            mb.add(xform(blk, M), mat=tire, shade='flat')
    # sidewall shoulder blocks (mud-terrain look): radial ribs just below the tread shoulder
    for k in range(sidewall_lugs):
        for side in (1, -1):
            a = (k + (0.25 if side > 0 else 0.75)) * 2 * math.pi / sidewall_lugs
            da = 0.55 * math.pi / sidewall_lugs
            verts = []
            for r, x in ((0.338, 0.149), (0.298, 0.156)):
                for u in (a - da, a + da):
                    verts.append((side * x, r * math.cos(u), r * math.sin(u)))
            for r, x in ((0.338, 0.168), (0.298, 0.170)):
                for u in (a - da * 0.8, a + da * 0.8):
                    verts.append((side * x, r * math.cos(u), r * math.sin(u)))
            faces = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
            blk = bm_from(verts, faces)
            cen = sum((Vector(v) for v in verts), Vector()) / 8
            C.orient(blk, lambda f: f.calc_center_median() - cen)
            if tread_bevel:
                C.bevel(blk, tread_bevel, 2)
            mb.add(xform(blk, M), mat=tire, shade='flat')
    # rim: outer lip + dish (faces +X), inner barrel + dish back (faces the axle)
    front = [(0.250, 0.126), (0.246, 0.137), (0.226, 0.120), (0.206, 0.083), (0.135, 0.073),
             (0.108, 0.086), (0.072, 0.093), (0.056, 0.106), (0, 0.108)]
    bm = bm_lathe(front, segs, axis='X')
    C.orient(bm, lambda f: Vector((1, 0, 0)) + radial(f.calc_center_median()) * 0.2)
    mb.add(xform(bm, M), mat=rim, shade='auto', angle=40)
    back = [(0.250, -0.126), (0.236, -0.133), (0.222, -0.118), (0.222, 0.040), (0.200, 0.056), (0, 0.060)]
    bm = bm_lathe(back, segs, axis='X')
    C.orient(bm, lambda f: Vector((-0.5, 0, 0)) - radial(f.calc_center_median()))
    mb.add(xform(bm, M), mat=rim, shade='auto', angle=40)
    if style == 'steel':
        for i in range(6):
            a = i * math.pi / 3 + math.pi / 6
            c = Vector((0.0752, 0.168 * math.cos(a), 0.168 * math.sin(a)))
            pts = [c + Vector((0, 0.027 * math.cos(t * math.pi / 4), 0.027 * math.sin(t * math.pi / 4))) for t in range(8)]
            hole = bm_from(pts, [list(range(8))])
            C.orient(hole, lambda f: (1, 0, 0))
            mb.add(xform(hole, M), mat=tire)
    elif style == 'slot':
        for i in range(8):
            a = i * math.pi / 4
            pts = []
            for t in range(6):
                u = a - 0.16 + 0.32 * t / 5
                pts.append(Vector((0.0752, 0.195 * math.cos(u), 0.195 * math.sin(u))))
            for t in range(6):
                u = a + 0.16 - 0.32 * t / 5
                pts.append(Vector((0.0752, 0.150 * math.cos(u), 0.150 * math.sin(u))))
            slot = bm_from(pts, [list(range(12))])
            C.orient(slot, lambda f: (1, 0, 0))
            mb.add(xform(slot, M), mat=tire)
    elif style == 'spoke':
        for i in range(6):
            a = i * math.pi / 3
            d = Vector((0, math.cos(a), math.sin(a)))
            p0 = Vector((0.108, 0, 0)) + d * 0.06
            p1 = Vector((0.118, 0, 0)) + d * 0.215
            sp = bm_cyl_between(p0, p1, 0.024, segs=5, r2=0.03)
            mb.add(xform(sp, M), mat=rim, shade='auto', angle=40)
    # hub cap and lug nuts
    cap = bm_lathe([(0.052, 0.10), (0.05, 0.125), (0.03, 0.135), (0, 0.137)], 10, axis='X')
    C.orient(cap, lambda f: (1, 0, 0))
    mb.add(xform(cap, M), mat='Metal' if rim != 'Metal' else 'Trim', shade='smooth')
    for i in range(6):
        a = i * 2 * math.pi / 6
        p = Vector((0.090, 0.082 * math.cos(a), 0.082 * math.sin(a)))
        nut = bm_cyl_between(p, p + Vector((0.024, 0, 0)), 0.014, segs=6)
        mb.add(xform(nut, M), mat='Metal', shade='flat')


# ------------------------------------------------------------------ axles
def add_axle(mb, front=True, track_x=0.825, spring_x=0.55, pinion_y=0.235, pinion_z=0.03, detail=False):
    """Solid axle centred at origin, tube along X to the hub faces at +-(track_x - 0.08).
    detail=True adds a diff guard, brake calipers, sway bar with drop links and (front) a steering damper."""
    s = -1 if front else 1                       # pinion direction along Y
    hub = track_x - 0.08
    tube = track_x - 0.125
    mb.add(bm_cyl_between((-tube, 0, 0), (tube, 0, 0), 0.046, segs=8), mat='Trim', shade='auto', angle=50)
    for sx in (-1, 1):
        mb.add(bm_cyl_between((sx * 0.12, 0, 0), (sx * 0.32, 0, 0), 0.058, segs=8), mat='Trim', shade='auto', angle=50)
    prof = [(0, -0.125), (0.085, -0.12), (0.122, -0.085), (0.132, -0.02), (0.122, 0.05),
            (0.085, 0.11), (0.048, 0.16), (0.042, 0.205), (0, 0.205)]
    prof = [(r, s * h) for r, h in prof]
    bm = bm_lathe(prof, 12, axis='Y')
    C.orient(bm, lambda f: f.calc_center_median())
    mb.add(xform(bm, Matrix.Translation((0, 0, pinion_z))), mat='Trim', shade='auto', angle=45)
    cov = bm_lathe([(0.108, -s * 0.118), (0.112, -s * 0.132), (0.09, -s * 0.142), (0, -s * 0.146)], 12, axis='Y')
    C.orient(cov, lambda f: (0, -s, 0))
    mb.add(xform(cov, Matrix.Translation((0, 0, pinion_z))), mat='Metal', shade='auto', angle=45)
    mb.add(bm_cyl_between((0, s * 0.200, pinion_z), (0, s * pinion_y, pinion_z), 0.052, segs=8), mat='Metal', shade='auto')
    for sx in (-1, 1):
        mb.add(bm_cyl(0.078, 0.078, 0.016, 10, Matrix.Translation((sx * spring_x, 0, 0.044)), base=True), mat='Metal', shade='auto')
        mb.add(bm_box((0.05, 0.16, 0.05), (sx * (spring_x - 0.10), 0, -0.06), 0.008), mat='Trim', shade='auto')
    if detail:
        # diff guard: skid plate under the pumpkin with two side cheeks
        mb.add(bm_box_mm((-0.15, -0.13, pinion_z - 0.155), (0.15, 0.13, pinion_z - 0.135), 0.006), mat='Metal', shade='auto')
        for sx in (-1, 1):
            mb.add(bm_box_mm((sx * 0.145 - 0.0075, -0.13, pinion_z - 0.135), (sx * 0.145 + 0.0075, 0.13, -0.01), 0.004),
                   mat='Metal', shade='auto')
        # sway bar on the outer side of the axle with drop links
        yb = -s * 0.13
        mb.add(bm_cyl_between((-0.30, yb, -0.035), (0.30, yb, -0.035), 0.016, segs=6), mat='Trim', shade='auto', angle=60)
        for sx in (-1, 1):
            mb.add(bm_cyl_between((sx * 0.30, yb, -0.035), (sx * 0.30, yb * 0.2, -0.035), 0.016, segs=6), mat='Trim', shade='auto', angle=60)
            mb.add(bm_cyl_between((sx * 0.26, yb, -0.035), (sx * 0.26, yb, 0.11), 0.012, segs=6), mat='Metal', shade='auto', angle=60)
            mb.add(bm_box((0.05, 0.05, 0.03), (sx * 0.26, yb, -0.035), 0.005), mat='Rubber', shade='auto')
            # brake caliper behind the hub
            mb.add(bm_box((0.05, 0.09, 0.07), (sx * (hub - 0.05), -s * 0.11, 0.09), 0.01), mat='Metal', shade='auto')
    if front:
        if detail:
            # steering damper parallel to the tie rod
            mb.add(bm_cyl_between((-(hub - 0.32), 0.215, -0.02), (0.05, 0.215, -0.02), 0.028, segs=8), mat='Metal', shade='auto', angle=50)
            mb.add(bm_cyl_between((0.05, 0.215, -0.02), ((hub - 0.34), 0.215, -0.02), 0.012, segs=6), mat='Chrome', shade='auto', angle=60)
        for sx in (-1, 1):
            mb.add(bm_cyl(0.068, 0.068, 0.24, 10, Matrix.Translation((sx * (hub - 0.065), 0, -0.12)), base=True), mat='Trim', shade='auto', angle=50)
            mb.add(bm_cyl_between((sx * (hub - 0.085), 0, 0), (sx * hub, 0, 0), 0.095, segs=12), mat='Metal', shade='auto', angle=50)
            # steering arm angled inward (Ackermann) so the tyre clears it at full lock
            mb.add(bm_cyl_between((sx * (hub - 0.125), 0.03, -0.05), (sx * (hub - 0.275), 0.19, -0.05), 0.02, segs=6),
                   mat='Trim', shade='auto', angle=50)
            mb.add(bm_cyl(0.028, 0.028, 0.05, 8, Matrix.Translation((sx * (hub - 0.275), 0.19, -0.075)), base=True), mat='Metal', shade='auto')
        mb.add(bm_cyl_between((-(hub - 0.275), 0.19, -0.05), ((hub - 0.275), 0.19, -0.05), 0.019, segs=6), mat='Metal', shade='auto', angle=50)
    else:
        for sx in (-1, 1):
            mb.add(bm_cyl_between((sx * (hub - 0.125), 0, 0), (sx * (hub - 0.045), 0, 0), 0.125, segs=14), mat='Trim', shade='auto', angle=50)
            mb.add(bm_cyl_between((sx * (hub - 0.045), 0, 0), (sx * hub, 0, 0), 0.085, segs=12), mat='Metal', shade='auto', angle=50)


# ------------------------------------------------------------------ spring + damper
def add_spring(mb, coil_mat='Metal', rc=0.062):
    """Bottom at origin, unit height along +Z, outer diameter ~2*(rc+0.011)."""
    mb.add(bm_cyl(0.075, 0.075, 0.02, 10, base=True), mat='Metal', shade='auto')
    mb.add(bm_cyl(0.075, 0.075, 0.02, 10, Matrix.Translation((0, 0, 0.98)), base=True), mat='Metal', shade='auto')
    mb.add(bm_cyl(0.031, 0.031, 0.54, 8, Matrix.Translation((0, 0, 0.02)), base=True), mat='Trim', shade='auto', angle=50)
    mb.add(bm_cyl(0.013, 0.013, 0.43, 6, Matrix.Translation((0, 0, 0.55)), base=True), mat='Metal', shade='auto', angle=60)
    turns, per, rw, ns = 6.0, 7, 0.011, 4
    n = int(turns * per)
    pts = []
    for i in range(n + 1):
        t = i / n
        th = 2 * math.pi * turns * t
        u = t + 0.08 * math.sin(2 * math.pi * t)
        z = 0.02 + rw + (0.96 - 2 * rw) * min(1.0, max(0.0, u))
        pts.append(Vector((rc * math.cos(th), rc * math.sin(th), z)))
    verts, faces = [], []
    for i, p in enumerate(pts):
        tan = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
        nrm = Vector((p.x, p.y, 0)).normalized()
        bi = tan.cross(nrm).normalized()
        nrm = bi.cross(tan).normalized()
        for k in range(ns):
            a = 2 * math.pi * k / ns + math.pi / 4
            verts.append(p + (nrm * math.cos(a) + bi * math.sin(a)) * rw)
    for i in range(n):
        for k in range(ns):
            k2 = (k + 1) % ns
            faces.append([i * ns + k, i * ns + k2, (i + 1) * ns + k2, (i + 1) * ns + k])
    bm = bm_from(verts, faces)
    bm.faces.ensure_lookup_table()
    fc = {f: (pts[f.index // ns] + pts[f.index // ns + 1]) / 2 for f in bm.faces}
    C.orient(bm, lambda f: f.calc_center_median() - fc[f])
    mb.add(bm, mat=coil_mat, shade='smooth')


# ------------------------------------------------------------------ driveshaft
def add_driveshaft(mb):
    """From origin along +Y, unit length."""
    ax = lambda y0, y1, r, sg=8: bm_cyl_between((0, y0, 0), (0, y1, 0), r, segs=sg)
    mb.add(ax(0.0, 0.022, 0.048), mat='Trim', shade='auto')
    mb.add(ax(0.978, 1.0, 0.048), mat='Trim', shade='auto')
    for yc in (0.045, 0.955):
        mb.add(bm_box((0.09, 0.03, 0.022), (0, yc, 0)), mat='Metal', shade='flat')
        mb.add(bm_box((0.022, 0.03, 0.09), (0, yc, 0)), mat='Metal', shade='flat')
    mb.add(ax(0.06, 0.22, 0.040), mat='Trim', shade='auto', angle=50)
    mb.add(ax(0.07, 0.94, 0.031), mat='Metal', shade='auto', angle=50)


# ------------------------------------------------------------------ text + boolean helpers
def bm_text(text, size=0.1, depth=0.01, M=Matrix(), align='CENTER', bold=False):
    """Extruded text (default Blender font) as a bmesh. Text lies in local XY, extruded
    +-depth/2 along Z, centred on X, baseline at Y=0; transform with M."""
    import bmesh
    cu = bpy.data.curves.new('txt_' + text, 'FONT')
    cu.body = text
    cu.size = size
    cu.extrude = depth / 2
    cu.align_x = align
    cu.resolution_u = 2
    if bold:
        cu.offset = size * 0.02
    ob = bpy.data.objects.new('txt_' + text, cu)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    ob.evaluated_get(dg).to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bpy.context.view_layer.update()
    return xform(bm, M)


def bm_boolean(bm, cutters, op='DIFFERENCE'):
    """Apply exact booleans of bmesh cutters to bm; returns a new bmesh (inputs are freed)."""
    import bmesh
    me = bpy.data.meshes.new('bool_tmp')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('bool_tmp', me)
    bpy.context.scene.collection.objects.link(ob)
    tmp = []
    for i, c in enumerate(cutters):
        cm = bpy.data.meshes.new('cut%d' % i)
        c.to_mesh(cm)
        c.free()
        co = bpy.data.objects.new('cut%d' % i, cm)
        bpy.context.scene.collection.objects.link(co)
        co.hide_render = True
        tmp.append(co)
        mod = ob.modifiers.new('b%d' % i, 'BOOLEAN')
        mod.operation = op
        mod.solver = 'EXACT'
        mod.object = co
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    out = bmesh.new()
    out.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    for co in tmp:
        m = co.data
        bpy.data.objects.remove(co)
        bpy.data.meshes.remove(m)
    out.normal_update()
    bpy.context.view_layer.update()
    return out


# ------------------------------------------------------------------ assembly + export
def g(p):
    """Blender -> game coordinates."""
    return [round(p[0], 4), round(p[2], 4), round(-p[1], 4)]


def assemble(parts, col, dims, pose=None):
    """Linked copies of the parts in a suspension pose (preview only).
    dims: dict with wheelbase, track_x, spring_x, spring_top, spring_seat, pinion_y, pinion_z, tcase_y, tcase_z.
    pose: optional dict wheel key -> (dz, steer_deg) for articulation / steering checks."""
    if dims.get('fidelity'):
        from vehicle_fidelity import assemble as assemble_fidelity
        return assemble_fidelity(parts, col, dims, pose)
    pose = pose or {}
    ay = dims['wheelbase'] / 2
    objs = []

    def inst(src, loc, rot=(0, 0, 0), scale=(1, 1, 1), q=None):
        o = bpy.data.objects.new(src.name + '_asm', src.data)
        col.objects.link(o)
        o.location = loc
        if q is not None:
            o.rotation_mode = 'QUATERNION'
            o.rotation_quaternion = q
        else:
            o.rotation_euler = rot
        o.scale = scale
        objs.append(o)
        return o
    inst(parts['Body'], (0, 0, 0))
    zs = {}
    for k, sx, sy in (('FL', -1, 1), ('FR', 1, 1), ('RL', -1, -1), ('RR', 1, -1)):
        dz, steer = pose.get(k, (0.0, 0.0))
        zs[k] = dz
        yaw = (math.pi if sx < 0 else 0) + math.radians(-steer)
        inst(parts['Wheel'], (sx * dims['track_x'], sy * ay, dz), (0, 0, yaw))
    for name, sy, kl, kr in (('AxleFront', 1, 'FL', 'FR'), ('AxleRear', -1, 'RL', 'RR')):
        zl, zr = zs[kl], zs[kr]
        # right wheel higher -> right end of the axle up (Blender rotation about +Y lowers +X, hence the minus)
        roll = math.atan2(zr - zl, 2 * dims['track_x'])
        inst(parts[name], (0, sy * ay, (zl + zr) / 2), (0, -roll, 0))
        for side, sx in (('L', -1), ('R', 1)):
            x = sx * dims['spring_x']
            axle_z = zl + (zr - zl) * ((x + dims['track_x']) / (2 * dims['track_x']))
            base = Vector((x, sy * ay, axle_z + dims['spring_seat']))
            inst(parts['Spring'], base, scale=(1, 1, dims['spring_top'] - base.z))
        a = Vector((0, sy * dims['tcase_y'], dims['tcase_z']))
        b = Vector((0, sy * (ay - dims['pinion_y']), (zl + zr) / 2 + dims['pinion_z']))
        d = b - a
        inst(parts['Driveshaft'], a, scale=(1, d.length, 1), q=Vector((0, 1, 0)).rotation_difference(d))
    return objs


def export_vehicle(vid, parts, dims, lamps, tris, extra=None):
    """Write vehicle_<vid>.glb (+ .json sidecar). lamps: dict kind -> list of Blender points."""
    C.export_glb([parts[k] for k in ('Body', 'Wheel', 'AxleFront', 'AxleRear', 'Spring', 'Driveshaft')],
                 'vehicle_%s.glb' % vid, vcolor=False)
    info = {
        'id': vid,
        'note': 'game coordinates: +Y up, front = -Z, origin = axle midpoint at static wheel-centre height',
        'wheelBase': dims['wheelbase'],
        'trackX': dims['track_x'],
        'wheelRadius': dims['R'],
        'spring': {'x': dims['spring_x'], 'top': dims['spring_top'], 'seat': dims['spring_seat']},
        'driveshaft': {'tcaseZ': dims['tcase_y'], 'tcaseY': dims['tcase_z'],
                       'pinionZ': dims['pinion_y'], 'pinionY': dims['pinion_z']},
        'lamps': {k: [g(p) for p in v] for k, v in lamps.items()},
        'tris': tris,
    }
    mn, mx = C.world_bbox([parts['Body']])
    info['bodyBox'] = {'min': g((mn.x, mx.y, mn.z)), 'max': g((mx.x, mn.y, mx.z))}
    if extra:
        info.update(extra)
    path = os.path.join(C.MODELS, 'vehicle_%s.json' % vid)
    with open(path, 'w') as f:
        json.dump(info, f, indent=1)
    return path


def render_previews(vid, parts, col, dims):
    """Standard preview set: 3/4 front, 3/4 rear, side, underside, articulation, full lock, parts."""
    C.setup_render()
    C.add_sun((52, 0, 145), 4.2)
    ground = C.add_ground(-dims['R'])
    col.hide_render = True
    for o in parts.values():
        o.hide_render = True
    shots = []

    def pose_set(name, pose, views):
        pc = C.collection('Pose_' + name)
        objs = assemble(parts, pc, dims, pose)
        for fname, az, el, lens, gnd in views:
            ground.hide_render = not gnd
            C.frame_camera(objs, az=az, el=el, lens=lens)
            C.render('%s_%s.png' % (vid, fname))
            shots.append(fname)
        ground.hide_render = False
        pc.hide_render = True
        return objs

    pose_set('rest', None, [('front34', 48, 14, 55, True), ('rear34', -128, 16, 55, True),
                            ('side', 90, 2, 80, True), ('underside', 30, -28, 55, False),
                            ('front', 0, 6, 70, True)])
    # articulation: front left and rear right at full bump, the others at full droop, plus full lock
    up, dn = dims['bump'], -dims['droop']
    pose_set('flex', {'FL': (up, 0), 'FR': (dn, 0), 'RL': (dn, 0), 'RR': (up, 0)},
             [('flex', 35, 8, 55, False)])
    lock = dims.get('lock', 32)
    pose_set('lock', {'FL': (up * 0.8, lock), 'FR': (up * 0.8, lock * 0.86), 'RL': (0, 0), 'RR': (0, 0)},
             [('lock_top', 0, 88, 60, False), ('lock_front', 20, 4, 70, False)])
    return shots
