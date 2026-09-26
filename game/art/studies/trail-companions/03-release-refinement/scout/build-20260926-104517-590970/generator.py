"""Refine the published Scout/Kestrel bodies and expedition kit in Toyota's style.

The immutable sources are the game release 33439c3, not the discarded fidelity
remake. Original equipment is transferred component by component; changes replace
specific pressings, lamps and mounts. Reference photographs and retention notes:
art/studies/trail-companions/03-release-refinement/reference/.
Metres, +Y forward, +Z up. Only these two vehicles are exported.
"""
import bpy, bmesh, math, os, sys, json, importlib.util
from datetime import datetime, timezone
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import vehicle_parts as P
import vehicle_fidelity as F

REVISION = '03-release-refinement'
RELEASE = '33439c37d453c87279797d7365d8874cff5b747a'
SPECS = {
    'scout': dict(F.SPECS['scout'], wb=2.50, width=.89, front=1.80, rear=-1.82,
                  belt=.82, roof=1.50, cowl=.56, topfront=.40, cabrear=-1.80,
                  paint='#B75B3D', accent='#E8DFC8', r=.43, tw=.30, tx=.89,
                  arch_r=.53, arch_z=.18, flare=.055, bump=.24, droop=.20, lock=39.4,
                  tank=dict(y=-.45, length=.36), exhaust_tip=False,
                  shock=dict(bottom=[.245, .035, .09], top=[.245, .55, -.30], barrelLength=.415)),
    'ranger': dict(F.SPECS['ranger'], wb=2.62, width=.82, front=2.045, rear=-2.28,
                   belt=.80, roof=1.28, cowl=.93, topfront=.60, cabrear=-.245,
                   paint='#6E9E93', accent='#E6DDC4', r=.42, tw=.29, tx=.875,
                   arch_r=.52, arch_z=.17, flare=.045, bump=.23, droop=.18, lock=40.0,
                   exhaust_tip=False,
                   shock=dict(bottom=[.28, .035, .09], top=[.265, .410, -.40], barrelLength=.410)),
}


def release_module(vid):
    spec = importlib.util.spec_from_file_location(vid + '_release',
        os.path.join(C.HERE, 'reference', 'vehicle_' + vid + '_release.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCOUT, RANGER = release_module('scout'), release_module('ranger')


def retain(mb, builder, edit=None):
    """Transfer complete authored components, never use face count as a detail mask.

    The callback can replace an identified component, or adjust its mount. New
    normals are baked after the adjustment; untouched components keep their shape.
    """
    class Transfer:
        index = 0
        def add(self, bm, **kw):
            lo = Vector(tuple(min(v.co[k] for v in bm.verts) for k in range(3)))
            hi = Vector(tuple(max(v.co[k] for v in bm.verts) for k in range(3)))
            keep = edit(bm, kw, lo, hi, self.index) if edit else True
            self.index += 1
            if keep is False:
                bm.free()
            else:
                mb.add(bm, **kw)
    builder(Transfer())


def improve_primitives(module):
    # Circular silhouettes and small bevels are refined without simplifying any
    # of the release's bags, tools, recovery gear or body hardware.
    def box_mm(mn, mx, bev=0, segs=1):
        return C.bm_box_mm(mn, mx, bev, max(segs, 3) if bev else segs)
    def box(size, center=(0, 0, 0), bev=0, segs=1, rot=(0, 0, 0)):
        return C.bm_box(size, center, bev, max(segs, 3) if bev else segs, rot)
    def cylinder(a, b, r, r2=None, segs=12, cap=True):
        return C.bm_cyl_between(a, b, r, r2=r2, segs=max(segs, 12), cap=cap)
    original_lathe = module.bm_lathe
    def lathe(profile, segs=32, **kw):
        return original_lathe(profile, max(segs, 28), **kw)
    module.bm_box_mm, module.bm_box = box_mm, box
    module.bm_cyl_between, module.bm_lathe = cylinder, lathe
    module.tube = lambda mb, a, b, r=.016, mat='Trim', segs=12: F.tube(mb, a, b, r, mat, max(segs, 12))


for vid, module in (('scout', SCOUT), ('ranger', RANGER)):
    improve_primitives(module)
    s = SPECS[vid]
    module.ARCH_R, module.ARCH_ZC = s['arch_r'], s['arch_z']
    module.TYRE_R, module.TYRE_W, module.TRACK_X = s['r'], s['tw'], s['tx']
SCOUT.FLARE_R, SCOUT.FLARE_X = .585, 1.00
SCOUT.LINER_X = .32
RANGER.FLARE_X = .975


def materials(s):
    mats = F.materials(s)
    for name, color, rough, metal in (
        ('Paint', s['paint'], .56, 0), ('PaintAccent', s['accent'], .60, 0),
        ('Trim', '#272D29', .76, .02), ('Rubber', '#20231F', .91, 0),
        ('Glass', '#203437', .25, .22), ('Mirror', '#526B69', .24, .56),
        ('Chrome', '#ABB0A7', .34, .66), ('Metal', '#7B837A', .47, .60),
        ('Rim', '#B6B49D', .56, .36), ('Tire', '#272923', .94, 0),
        ('Lamp', '#D2D7C8', .27, .14), ('LampAux', '#D4D5BD', .29, .08),
        ('LampPlate', '#DDD6BC', .30, .05), ('PanelGap', '#45483B', .88, 0),
        ('Recovery', '#B37838', .72, .05), ('Board', '#C78236', .81, 0),
        ('Can', '#5B6644', .64, .08), ('CargoRed', '#A8412F', .76, 0),
        ('CargoBlue', '#3E6C8C', .72, 0), ('Rope', '#B89A62', .92, 0),
        ('Canvas', '#77775B', .94, 0), ('Interior', '#393D34', .88, 0),
    ):
        if name in mats:
            bpy.data.materials.remove(mats[name])
        mats[name] = C.mat_pbr(name, color, rough, metal)
    return mats


def wheel(mb, s, M=Matrix(), detailed=True):
    """Grow the tyre above a fixed bead; rim and brake dimensions stay fixed.

    Chevron blocks follow the FJ60, with five-bolt Defender / six-bolt Hilux hubs.
    Both LODs retain open steel-wheel vents and the same contact envelope.
    """
    tmp = C.MeshBuilder('Tyre source')
    P.add_wheel(tmp, segs=40 if detailed else 24, lugs=24 if detailed else 16,
                sidewall_lugs=16 if detailed else 0, tread_bevel=.002 if detailed else 0)
    faces = [face for face, mat in zip(tmp.F, tmp.FM) if mat == 'Tire'
             and not all(abs(tmp.V[i].x - .0752) < .00001 for i in face)]
    used = sorted({i for face in faces for i in face})
    indices = {old: new for new, old in enumerate(used)}
    bm = C.bm_from([tmp.V[i] for i in used], [[indices[i] for i in f] for f in faces])
    for v in bm.verts:
        p = v.co
        radius = math.hypot(p.y, p.z)
        grown = .230 + (radius - .235) * (s['r'] - .230) / (.381 - .235)
        p.x *= s['tw'] / .30
        p.y *= grown / radius
        p.z *= grown / radius
    mb.add(C.xform(bm, M), mat='Tire', shade='auto', angle=50)
    segs = 40 if detailed else 20
    # Rolled rim and barrel. The dish is a closed pressing with actual holes.
    F.lathe(mb, [(.232, -.126), (.226, -.131), (.211, -.119), (.211, .096),
                 (.230, .124), (.239, .135), (.237, .143), (.226, .140), (.217, .122)],
            M=M, mat='Rim', segs=segs)
    dish = C.bm_lathe([(.055, .106), (.100, .089), (.132, .077), (.186, .077),
                       (.218, .116), (.224, .123), (.224, .109), (.218, .102),
                       (.186, .063), (.132, .063), (.100, .075), (.055, .092), (.055, .106)],
                      segs, axis='X')
    bmesh.ops.recalc_face_normals(dish, faces=dish.faces)
    bolts = 5 if s['spring'] == 'coil' else 6
    cuts = []
    for k in range(bolts):
        a = (k + .5) * math.tau / bolts
        y, z = .161 * math.cos(a), .161 * math.sin(a)
        cuts.append(C.bm_cyl_between((.03, y, z), (.15, y, z), .028, segs=16 if detailed else 8))
    dish = P.bm_boolean(dish, cuts)
    if detailed:
        C.bevel(dish, .0025, 2)
    mb.add(C.xform(dish, M), mat='Rim', shade='auto', angle=42)
    F.lathe(mb, [(0, .106), (.049, .106), (.049, .142), (.038, .153), (0, .153)],
            M=M, mat='Metal', segs=24 if detailed else 12)
    for k in range(bolts):
        a = k * math.tau / bolts
        y, z = .080 * math.cos(a), .080 * math.sin(a)
        mb.add(C.xform(C.bm_cyl_between((.088, y, z), (.113, y, z), .012, segs=6), M),
               mat='Metal', shade='flat')
    if s['spring'] == 'leaf':
        F.lathe(mb, [(0, .154), (.026, .154), (.026, .164), (0, .164)], M=M, mat='Recovery', segs=16)
    if detailed:
        for side in (-1, 1):
            F.lathe(mb, [(.274, side * .145), (.277, side * .148), (.280, side * .146)],
                    M=M, mat='Tire', segs=40)
        F.tube(mb, M @ Vector((.126, .193, .038)), M @ Vector((.150, .193, .045)), .005, 'Rubber', 8)


def skin(mb, point, nx, ny, bottom, mat='Paint'):
    """Sample a continuous stamped surface, with a closed underside and hem.

    Ribs are part of the surface, so their normals and silhouettes agree. The
    lower perimeter overlaps the existing tub instead of leaving an open seam.
    """
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            verts.append(point(2 * i / nx - 1, j / ny))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append([a, a + 1, a + nx + 2, a + nx + 1])
    edge = list(range(nx + 1)) + [j * (nx + 1) + nx for j in range(1, ny + 1)]
    edge += list(range(ny * (nx + 1) + nx - 1, ny * (nx + 1) - 1, -1))
    edge += [j * (nx + 1) for j in range(ny - 1, 0, -1)]
    start = len(verts)
    verts += [(verts[k][0], verts[k][1], bottom) for k in edge]
    for i, k in enumerate(edge):
        j = (i + 1) % len(edge)
        faces.append([k, edge[j], start + j, start + i])
    faces.append(list(range(start, len(verts)))[::-1])
    bm = C.bm_from(verts, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mb.add(bm, mat=mat, shade='auto', angle=38)


scout_arch, ranger_arch = SCOUT.arch_pts, RANGER.arch_over
SCOUT.arch_pts = lambda yc, r, zc, z0, steps=32, reverse=False: scout_arch(yc, r, zc, z0, max(steps, 32), reverse)
RANGER.arch_over = lambda yc, r, zc, z0, steps=32: ranger_arch(yc, r, zc, z0, max(steps, 32))


def bolt(mb, p, normal=(0, 0, 1), r=.006, mat='Metal'):
    p, n = Vector(p), Vector(normal)
    F.tube(mb, p, p + n * .005, r, mat, 6)


def strap(mb, points, width=.035, axis=(0, 1, 0), mat='Trim'):
    """A thin webbing ribbon following the load, with a closed 3 mm section."""
    pts, across = [Vector(p) for p in points], Vector(axis).normalized() * width / 2
    for a, b in zip(pts, pts[1:]):
        F.panel(mb, [a - across, b - across, b + across, a + across], mat, .003, .001)


def flare(mb, s, side, yc, floor):
    # A narrow rolled flare returns into the well. Its radial width is distinct
    # from its lateral coverage, so a wide tyre does not need a huge black band.
    width, r, zc = s['width'], s['arch_r'], s['arch_z']
    outer = 1.00 if s['spring'] == 'coil' else .995
    section = [(width - .005, r + s['flare']), (outer - .044, r + s['flare']),
               (outer - .006, r + .036), (outer + .008, r + .011),
               (outer - .004, r - .001), (width - .008, r - .001)]
    verts, faces, rings = [], [], []
    for x, radius in section:
        outline = SCOUT.arch_pts(yc, radius, zc, floor) if floor < zc else RANGER.arch_over(yc, radius, zc, floor)
        rings.append(outline)
        verts.extend((side * x, y, z) for y, z in outline)
    count = len(rings[0])
    for j in range(len(section)):
        nxt = (j + 1) % len(section)
        for i in range(count - 1):
            faces.append([j * count + i, j * count + i + 1, nxt * count + i + 1, nxt * count + i])
    faces += [[j * count for j in range(len(section))][::-1],
              [j * count + count - 1 for j in range(len(section))]]
    bm = C.bm_from(verts, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if s['spring'] == 'coil':
        mb.add(bm, mat='Trim', shade='auto', angle=38)
    else:
        # The Hilux reference has painted pressed wings. Keep the release's
        # cream arch accent as a narrow outer lip, not a broad white shelf.
        bm.faces.ensure_lookup_table()
        lip = {bm.faces[i] for i in range(2 * (count - 1), 4 * (count - 1))}
        underside = {bm.faces[i] for i in range(4 * (count - 1), 5 * (count - 1))}
        mb.add(bm, mat_fn=lambda f: 'PaintAccent' if f in lip else 'Interior' if f in underside else 'Paint', shade='auto', angle=38)
    if s['spring'] == 'coil':
        for k in range(7):
            a = math.pi * (.09 + .82 * k / 6)
            bolt(mb, (side * (outer - .013), yc + (r + .032) * math.cos(a), zc + (r + .032) * math.sin(a)),
                 (side, 0, 0), .006)


def hood_point(s, u, t):
    scout = s['spring'] == 'coil'
    x = u * (.837 if scout else .770)
    y = (.657 + 1.116 * t) if scout else (1.007 + 1.012 * t)
    crown = (.014 + .026 * math.sin(math.pi * t) ** .8) * max(0, 1 - u * u)
    fade = C.smoothstep(.04, .16, t) * (1 - C.smoothstep(.82, .98, t))
    bead = (.008 * math.exp(-((abs(x) - .49) / .055) ** 2) if scout
            else .008 * math.exp(-(x / .10) ** 4)) * fade
    z = s['belt'] + (.011 if scout else .009 - .057 * t) + crown + bead
    z -= .009 * C.smoothstep(.89, 1, t) * (1 - u * u)
    return (x, y, z)


def hood(mb, s):
    scout = s['spring'] == 'coil'
    skin(mb, lambda u, t: hood_point(s, u, t), 64, 40, .814 if scout else .741)
    start, end = (.50, .650) if scout else (.925, 1.000)
    w = .853 if scout else .797
    def cowl(u, t):
        return (u * w, start + (end - start) * t,
                s['belt'] + .012 + .018 * (1 - u * u) + .003 * math.sin(math.pi * t))
    skin(mb, cowl, 40, 10, s['belt'] - .01)
    seam = [(x, y, z + .001) for x, y, z in (cowl(-1 + i / 24, 1) for i in range(49))]
    F.path(mb, seam, .002, 'PanelGap', 6)
    for side in (-1, 1):
        for i in range(6):
            x = side * (.26 + i * .043)
            z = cowl(x / w, .50)[2]
            F.box(mb, (x, (start + end) / 2, z + .001), (.024, (end - start) * .54, .004), 'Trim', .002, 2)
        if scout:
            # The old latch and hinge locations are retained, now with pivots,
            # clamping plates and visible fasteners against the crowned bonnet.
            F.box(mb, (side * .62, 1.775, .807), (.074, .027, .062), 'Metal', .006, 3)
            F.box(mb, (side * .62, 1.790, .793), (.020, .016, .086), 'Trim', .004, 2)
            F.tube(mb, (side * .62 - .039, 1.791, .820), (side * .62 + .039, 1.791, .820), .007, 'Metal', 12)
            for dx in (-.022, .022):
                bolt(mb, (side * .62 + dx, 1.790, .791), (0, 1, 0), .004)
            F.box(mb, (side * .62, .665, .849), (.136, .076, .009), 'Paint', .005, 3)
            F.tube(mb, (side * .62 - .071, .668, .857), (side * .62 + .071, .668, .857), .010, 'Metal', 16)
            for dx in (-.044, .044):
                bolt(mb, (side * .62 + dx, .643, .853), r=.004)
        else:
            F.text(mb, '4WD', (side * .826, 1.61, .712), .040, 'right' if side > 0 else 'left', 'Metal')


def tub(mb, s):
    if s['spring'] == 'coil':
        # The release's tiny lower corners must move outward with the opening:
        # otherwise the enlarged arch doubles back across its own sill polygon.
        prof = [(-1.82, .24), (-1.815, .145), (-1.805, .12)]
        prof += SCOUT.arch_pts(-1.25, s['arch_r'], s['arch_z'], .12)
        prof += SCOUT.arch_pts(1.25, s['arch_r'], s['arch_z'], .12)
        prof += [(1.791, .12), (1.80, .21), (1.80, .79), (1.775, .82), (-1.795, .82), (-1.82, .79)]
        bm = C.bm_extrude_poly(prof, 1.78, axis='X')
        C.bevel(bm, .022, 3)
        bm = P.bm_boolean(bm, [C.bm_box_mm((-.20, -.74, .065), (.20, .74, .36))])
        bm.normal_update()
        mb.add(bm, mat_fn=lambda f: 'Interior' if abs(f.normal.x) < .5 and SCOUT.in_arch(f.calc_center_median()) and f.normal.z < .2
               else 'Trim' if f.normal.z < -.8 and f.calc_center_median().z < .14 else 'Paint', shade='auto', angle=32)
        def edit(bm, kw, lo, hi, i):
            # Retain the released closed tub, tunnel, liners and swage lines.
            # Replace the old bonnet, applied crease strips and cowl as a unit.
            return i != 0 and not (i >= 5 and lo.z > .72)
        retain(mb, SCOUT.add_tub, edit)
    else:
        # Keep the released cab/front-clip stamping. The separate original bed
        # is still built by add_bed, including its real wheel-tub recesses.
        retain(mb, RANGER.add_lower_body, lambda bm, kw, lo, hi, i: i == 0)
    hood(mb, s)


def greenhouse(mb, s):
    scout = s['spring'] == 'coil'
    xb, xt = (.87, .81) if scout else (.80, .735)
    zb, zt = s['belt'], s['roof']
    stations = [(0.56, 0.40), (-.36, -.38), (-1.12, -1.14), (-1.80, -1.77)] if scout else [(.93, .60), (-.06, -.05), (-.245, -.215)]
    vs, fs = [], []
    for yb, yt in stations:
        vs += [(-xb, yb, zb), (xb, yb, zb), (xt, yt, zt), (-xt, yt, zt)]
    end = (len(stations) - 1) * 4
    fs += [[3, 2, 1, 0], [end, end + 1, end + 2, end + 3]]
    for i in range(len(stations) - 1):
        a, b = i * 4, (i + 1) * 4
        fs += [[a + 1, b + 1, b + 2, a + 2], [a, a + 3, b + 3, b],
               [a + 3, a + 2, b + 2, b + 3], [a, b, b + 1, a + 1]]
    bm = C.bm_from(vs, fs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bottom = [f for f in bm.faces if f.normal.z < -.9]
    edges = [e for e in bm.edges if not any(f in bottom for f in e.link_faces)]
    rounded = set(C.bevel(bm, .024 if scout else .033, 3, edges).get('faces', []))
    bm.normal_update()
    windows = [f for f in bm.faces if f not in rounded and abs(f.normal.z) < .65 and f.calc_area() > .05
               and (scout or abs(f.normal.y) > .5 or f.calc_center_median().y > -.05)]
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < -.9], context='FACES_ONLY')
    bmesh.ops.inset_individual(bm, faces=windows, thickness=.034, depth=-.006)
    seals = set(bmesh.ops.inset_individual(bm, faces=windows, thickness=.010, depth=-.006)['faces'])
    glass = set(windows)
    mb.add(bm, mat_fn=lambda f: 'Glass' if f in glass else 'Rubber' if f in seals else 'Paint', shade='auto', angle=32)
    rear, front, width = (-1.80, .433, .839) if scout else (-.248, .631, .764)
    def roof_point(u, t):
        x, y = width * u, rear + (front - rear) * t
        z = zt + .028 + (.045 if scout else .031) * (1 - u * u) + .005 * math.sin(math.pi * t)
        fade = C.smoothstep(.03, .13, t) * (1 - C.smoothstep(.86, .98, t))
        for rib in (-.48, -.24, .24, .48):
            z += .004 * math.exp(-((x - rib) / .020) ** 2) * fade
        return (x, y, z)
    skin(mb, roof_point, 64, 30 if scout else 16, zt - .005, 'PaintAccent')
    def details(bm, kw, lo, hi, i):
        if i == 0 or (scout and i == 1):
            return False
        return True
    # Preserve the release wipers, screen hinges, gutters and quarter dividers.
    retain(mb, SCOUT.add_greenhouse if scout else RANGER.add_greenhouse, details)
    for side in (-1, 1):
        F.path(mb, [(side * (width + .006), rear + (front - rear) * t, zt + .009) for t in (i / 20 for i in range(21))],
               .008, 'PaintAccent', 10)
        if not scout:
            # Behind-door extractor vents are a distinctive early Hilux cue.
            F.box(mb, (side * .790, -.145, 1.037), (.011, .115, .158), 'Trim', .012, 3)
            for k in range(4):
                F.box(mb, (side * .799, -.145, .990 + k * .030), (.006, .083, .006), 'Metal', .002, 2)


def road_mudflaps(mb, s):
    for side in (-1, 1):
        for axle in (-s['wb'] / 2, s['wb'] / 2):
            y = axle - s['arch_r'] - .018
            x = side * s['tx']
            F.box(mb, (x, y, .025), (s['tw'] * .93, .016, .31), 'Rubber', .004, 2)
            F.box(mb, (x, y - .010, .153), (s['tw'] * .88, .018, .036), 'Metal', .004, 2)
            for dx in (-.09, 0, .09):
                bolt(mb, (x + dx, y - .021, .153), (0, -1, 0), .004)


def scout_sides(mb, s):
    def details(bm, kw, lo, hi, i):
        c, span = (lo + hi) / 2, hi - lo
        if span.y > 1 and span.z > .55 and abs(c.x) > .89:
            return False  # flare cross section is replaced, not the door trim
        if kw.get('mat') == 'Metal' and abs(c.x) > .995 and hi.z < .80:
            return False  # old flare bolt positions
        if kw.get('mat') == 'PaintAccent' and span.y > 1:
            return False  # split both pinstripes at the actual door shut line
        if hi.z < .15:
            return False  # sliders and flaps get frame mounts and tyre clearance
        if kw.get('mat') == 'Glass':
            kw['mat'] = 'Mirror'
        if c.x < -.89 and abs(c.y + 1.45) < .015 and .60 < c.z < .70:
            for v in bm.verts:
                v.co.y -= .22
                v.co.z += .068
        if abs(c.y + .745) < .012 and span.z > .40:
            # The sliding-window rail follows the flat side glass, not a
            # constant-X box that disappears into its lower half.
            for v in bm.verts:
                v.co.x = math.copysign(.87 - .06 * (v.co.z - .82) / .68 - .010, c.x) + (v.co.x - c.x) * .30
        return True
    retain(mb, SCOUT.add_sides, details)
    for side in (-1, 1):
        for axle in (-s['wb'] / 2, s['wb'] / 2):
            flare(mb, s, side, axle, .105)
        for a, b in ((-1.80, -.373), (-.359, .54)):
            for z in (.775, .795):
                F.box(mb, (side * .893, (a + b) / 2, z), (.004, b - a, .012), 'PaintAccent', 0)
        # Preserve both release sliders; fit proper tread pads on their tubes.
        F.path(mb, [(side * .74, -.64, .08), (side * .925, -.64, .08),
                    (side * .925, .64, .08), (side * .74, .64, .08)], .034, 'Trim', 14)
        F.box(mb, (side * .888, 0, .108), (.12, 1.22, .018), 'Metal', .007, 3)
        for y in (-.31, .31):
            F.box(mb, (side * .888, y, .121), (.092, .46, .012), 'Rubber', .009, 3)
            for k in range(6):
                F.box(mb, (side * .888, y + (k - 2.5) * .065, .130), (.077, .010, .005), 'Trim', .002, 2)
        for y in (-.56, 0, .56):
            F.box(mb, (side * .64, y, .08), (.58, .055, .038), 'Trim', .006, 3)
            F.box(mb, (side * .35, y, .152), (.10, .083, .16), 'Trim', .005, 3)
            bolt(mb, (side * .403, y, .159), (side, 0, 0), .010)
        # Rivets follow the body capping and hinge plates, large enough to read
        # close up without adding a checkerboard over every painted panel.
        for y in (-1.69, -1.41, -1.06, -.78, -.44):
            bolt(mb, (side * .895, y, .750), (side, 0, 0), .0038)
        for z in (.31, .68):
            for dz in (-.026, .026):
                bolt(mb, (side * .916, .582, z + dz), (side, 0, 0), .004)
        F.box(mb, (side * .901, -.24, .714), (.012, .172, .053), 'PanelGap', .009, 3)
        F.box(mb, (side * .919, -.24, .722), (.021, .112, .017), 'Metal', .005, 3)
        # Mirror swivel and bolted base retain the original rectangular heads.
        F.box(mb, (side * .877, .50, .865), (.026, .063, .067), 'Trim', .007, 3)
        for z in (.845, .885):
            bolt(mb, (side * .894, .50, z), (side, 0, 0), .004)
    road_mudflaps(mb, s)
    # Real collars already exist in the release; join them to the A-pillar.
    for t in (.55, .85):
        p = Vector((.915, .64, .78)).lerp(Vector((.868, .465, 1.58)), t)
        F.box(mb, (p.x - .041, p.y, p.z), (.095, .027, .029), 'Trim', .005, 3)
        bolt(mb, (p.x + .040, p.y, p.z), (1, 0, 0), .005)
    for k in range(5):
        F.box(mb, (.832 + k * .016, .578, 1.607), (.006, .008, .061), 'Trim', .001, 1)
    # Loaded antenna spring and insulating base, keeping the tall release whip.
    for k in range(5):
        F.lathe(mb, [(.012, 0), (.013, .004), (.012, .008)], axis='Z', mat='Metal',
                M=Matrix.Translation((-.86, 1.619, .852 + k * .010)), segs=16)


def tail_cluster(mb, x, y, z, width, height, levels):
    F.box(mb, (x, y - .009, z), (width + .036, .030, height + .026), 'Rubber', .009, 3)
    F.box(mb, (x, y - .026, z), (width + .018, .024, height + .010), 'Metal', .007, 3)
    for cz, h, mat in levels:
        F.box(mb, (x, y - .047, cz), (width, .018, h), mat, .006, 3)
        for k in range(5):
            dx = width * (k - 2) / 6
            F.tube(mb, (x + dx, y - .058, cz - h / 2 + .010),
                   (x + dx, y - .058, cz + h / 2 - .010), .0012, mat, 6)
    for dz in (-height / 2 + .016, height / 2 - .016):
        bolt(mb, (x + width / 2 + .006, y - .040, z + dz), (0, -1, 0), .0035, 'Trim')


def plate_light(mb, x, y, z):
    F.box(mb, (x, y, z), (.124, .040, .026), 'Trim', .006, 3)
    F.box(mb, (x, y - .006, z - .015), (.088, .024, .007), 'LampPlate', .002, 2)


def scout_rear(mb, s):
    SCOUT.add_wheel = lambda *args, **kwargs: None
    def details(bm, kw, lo, hi, i):
        c, span = (lo + hi) / 2, hi - lo
        if abs(c.x) > .69 and lo.z > .32 and hi.z < .75 and hi.y < -1.799:
            return False  # replace all three lenses and their housings together
        if abs(c.x) < .17 and lo.y < -1.825 and hi.y > -1.875 and lo.z >= .29:
            return False  # old unsupported spare mounting blocks
        if kw.get('mat') == 'LampReverse' and hi.z < .32:
            return False  # a dedicated plate-light material replaces this patch
        if kw.get('mat') == 'Rubber' and lo.z < 0:
            return False  # new full-width rear mudflaps
        return True
    retain(mb, SCOUT.add_rear, details)
    for side in (-1, 1):
        tail_cluster(mb, side * .78, -1.82, .525, .120, .354,
                     ((.607, .158, 'LampRear'), (.472, .065, 'LampAmber'), (.397, .060, 'LampReverse')))
    plate_light(mb, .47, -1.982, .309)
    for x in (.33, .61):
        bolt(mb, (x, -1.978, .254), (0, -1, 0), .004, 'Trim')
    # Bumper-mounted swing carrier, with pivot collars, diagonal load path,
    # centre boss and over-centre latch. The larger spare clears the rear ladder.
    cy, cz = -2.135, .81
    F.box(mb, (-.911, -1.927, .300), (.077, .107, .049), 'Trim', .008, 3)
    F.tube(mb, (-.925, -1.927, .23), (-.925, -1.927, .443), .026, 'Trim', 20)
    for z in (.274, .413):
        F.tube(mb, (-.925, -1.927, z - .010), (-.925, -1.927, z + .010), .032, 'Metal', 20)
    F.path(mb, [(-.925, -1.927, .419), (-.915, -1.956, .344),
                (-.65, -1.940, .343), (.42, -1.940, .343)], .027, 'Trim', 14)
    F.box(mb, (0, -1.945, .585), (.063, .050, .487), 'Trim', .007, 3)
    F.tube(mb, (-.68, -1.946, .347), (0, -1.945, .792), .024, 'Trim', 14)
    F.box(mb, (0, -1.953, cz), (.23, .035, .173), 'Metal', .012, 3)
    F.tube(mb, (0, -1.965, cz), (0, cy + .070, cz), .046, 'Metal', 20)
    F.box(mb, (.41, -1.952, .412), (.052, .042, .10), 'Metal', .006, 3)
    F.path(mb, [(.409, -1.983, .400), (.409, -1.995, .447), (.443, -1.995, .447)], .008, 'Trim', 12)
    wheel(mb, s, Matrix.Translation((0, cy, cz)) @ Matrix.Rotation(-math.pi / 2, 4, 'Z'))
    # The retained eight-rung ladder gets grip sleeves, clamping feet and a
    # roof-rack connection. Its original position stays clear of all rear lamps.
    for k in range(8):
        z = .42 + k * .13
        F.tube(mb, (.473, -1.872, z), (.607, -1.872, z), .014, 'Rubber', 12)
    for x in (.45, .63):
        for z in (.45, 1.35):
            back = -1.82 + max(0, z - .82) * .03 / .68
            F.box(mb, (x, back - .011, z), (.060, .027, .073), 'Trim', .006, 3)
            for dz in (-.022, .022):
                bolt(mb, (x, back - .026, z + dz), (0, -1, 0), .004)
        F.path(mb, [(x, -1.72, 1.70), (x, -1.72, 1.748), (x, -1.70, 1.750)], .013, 'Trim', 12)


def scout_rack(mb):
    base = SCOUT.ROOF_Z + .135
    def details(bm, kw, lo, hi, i):
        c, span = (lo + hi) / 2, hi - lo
        if kw.get('mat') == 'Canvas' and span.x > .39 and span.y < .06 and span.z > .07:
            return False  # replace thick board straps with fitted webbing
        if kw.get('mat') == 'Board':
            if span.y > 1.20 and .35 < span.x < .37:
                return False  # both boards now have real open carry handles
            if span.y > 1.3 and -.71 < c.x < -.63:
                return False  # real perforated jack beam
            if abs(c.x - .52) < .004 and span.x < .04 and (c.y < -1.40 or c.y > -.44):
                return False  # clearance at the board handle openings
        return True
    retain(mb, SCOUT.add_rack, details)
    for dz in (0, .035):
        board = C.bm_box_mm((.34, -1.52, base + dz), (.70, -.30, base + dz + .030), .010, 3)
        cuts = [C.bm_box((.15, .055, .14), (.52, y, base + .038), .015, 4) for y in (-1.43, -.40)]
        board = P.bm_boolean(board, cuts)
        C.bevel(board, .0015, 2)
        mb.add(board, mat='Board', shade='auto', angle=38)
    for y in (-1.20, -.62):
        strap(mb, [(.322, y, base), (.333, y, base + .062), (.365, y, base + .075),
                   (.685, y, base + .075), (.715, y, base + .062), (.723, y, base)], .035)
        F.box(mb, (.62, y, base + .081), (.055, .050, .012), 'Metal', .004, 3)
    # Clamp knobs actually reach the basket floor beside the open board handles.
    for y in (-1.43, -.40):
        for x in (.357, .690):
            bolt(mb, (x, y, base + .070), r=.007)
    # Basket clamps sit on the curved roof, with bolts and rubber pads.
    for x in (-.74, .74):
        for y in (.28, -.72, -1.66):
            F.box(mb, (x, y, 1.544), (.100, .100, .013), 'Rubber', .007, 3)
            for dy in (-.032, .032):
                bolt(mb, (x, y + dy, 1.557), r=.005)
    # Jerry-can pressings, cap rims, open carry handles and the shared retaining
    # band enrich the release's two cans without substituting generic boxes.
    for x in (-.20, .02):
        for side in (-1, 1):
            for a, b in (((x + side * .084, -1.57, base + .085), (x + side * .084, -1.35, base + .33)),
                         ((x + side * .084, -1.57, base + .33), (x + side * .084, -1.35, base + .085))):
                F.tube(mb, a, b, .006, 'Can', 8)
        F.lathe(mb, [(.020, 0), (.027, .007), (.026, .018)], axis='Z', mat='Metal',
                M=Matrix.Translation((x, -1.36, base + .475)), segs=20)
        strap(mb, [(x - .083, -1.46, base + .025), (x - .083, -1.46, base + .418),
                   (x - .058, -1.46, base + .445), (x + .058, -1.46, base + .445),
                   (x + .083, -1.46, base + .418), (x + .083, -1.46, base + .025)], .028)
        F.box(mb, (x + .088, -1.46, base + .25), (.013, .05, .065), 'Metal', .004, 3)
    # Jack rack perforations and its climbing block, shovel socket, tool clamps.
    beam = C.bm_box_mm((-.70, -1.50, base + .010), (-.64, -.10, base + .050), .004, 3)
    cuts = [C.bm_box((.026, .035, .10), (-.67, -1.44 + k * .086, base + .030), .003, 2) for k in range(15)]
    beam = P.bm_boolean(beam, cuts)
    mb.add(beam, mat='Board', shade='auto', angle=38)
    F.box(mb, (-.67, -.995, base + .135), (.114, .065, .025), 'Metal', .005, 3)
    for y in (-1.38, -.22):
        for x in (-.716, -.628):
            bolt(mb, (x, y, base + .09), r=.005)
    F.tube(mb, (-.56, -.73, base + .03), (-.56, -.56, base + .03), .023, 'Metal', 16)
    for y in (-1.52, -.70):
        strap(mb, [(-.59, y, base + .005), (-.589, y, base + .055),
                   (-.531, y, base + .055), (-.53, y, base + .005)], .030)
    # Four roof lamps are preserved; add yokes and a routed power loom.
    for x in (-.33, -.11, .11, .33):
        F.box(mb, (x, .342, 1.730), (.035, .078, .034), 'Metal', .004, 3)
        bolt(mb, (x, .365, 1.752), r=.005)
    F.path(mb, [(-.39, .318, 1.718), (-.71, .318, 1.718), (-.745, .24, 1.65),
                (-.745, -.72, 1.632)], .004, 'Rubber', 8)


def ranger_sides(mb, s):
    def details(bm, kw, lo, hi, i):
        c, span = (lo + hi) / 2, hi - lo
        if span.y > .9 and span.z > .35 and abs(c.x) > .82:
            return False  # narrow returned wheel flares
        if kw.get('mat') == 'PaintAccent' and span.y > 1:
            return False  # stripe is split at the enlarged wheel openings
        if kw.get('mat') == 'Rubber' and lo.z < 0:
            return False
        if kw.get('mat') == 'Glass':
            kw['mat'] = 'Mirror'
        if span.y > .9 and .31 < c.z < .33:
            for v in bm.verts:
                v.co.y = -.10 + (v.co.y + .10) * .88
        if .85 < c.y < .91 and .39 < c.z < .48:
            for v in bm.verts:
                v.co.z += .12
        return True
    retain(mb, RANGER.add_sides, details)
    for side in (-1, 1):
        for axle, floor in ((s['wb'] / 2, .26), (-s['wb'] / 2, .28)):
            flare(mb, s, side, axle, floor)
        # Preserve the characteristic cream stripe. Cut its lower edge along
        # each arch instead of leaving a floating line through the tyre opening.
        for a, b in ((-.25, 2.00), (-2.27, -.37)):
            for k in range(96):
                y0, y1 = a + (b - a) * k / 96, a + (b - a) * (k + 1) / 96
                mid = (y0 + y1) / 2
                axle = s['wb'] / 2 if mid > 0 else -s['wb'] / 2
                rad = s['arch_r'] + s['flare'] + .013
                cutoff = s['arch_z'] + math.sqrt(max(0, rad * rad - (mid - axle) ** 2)) if abs(mid - axle) < rad else 0
                z0 = max(.645, cutoff)
                if z0 < .690:
                    F.box(mb, (side * .824, mid, (z0 + .690) / 2), (.005, y1 - y0 + .0001, .690 - z0), 'PaintAccent', 0)
        F.box(mb, (side * .825, .031, .745), (.010, .166, .052), 'PanelGap', .009, 3)
        F.box(mb, (side * .839, .031, .754), (.019, .122, .017), 'Metal', .006, 3)
        # Boxed original rocker sill and a small frame-connected tread step.
        F.box(mb, (side * .855, .26, .222), (.13, .85, .037), 'Metal', .013, 3)
        F.box(mb, (side * .856, .25, .246), (.09, .62, .015), 'Rubber', .008, 3)
        for k in range(9):
            F.box(mb, (side * .856, -.02 + k * .066, .256), (.077, .009, .005), 'Trim', .002, 2)
        for y in (-.06, .58):
            F.box(mb, (side * .61, y, .197), (.53, .050, .038), 'Trim', .005, 3)
            F.box(mb, (side * .35, y, .195), (.09, .073, .090), 'Trim', .006, 3)
        for y in (.70, .86):
            F.box(mb, (side * .805, y, .798), (.023, .070, .040), 'Metal', .005, 3)
            for dy in (-.022, .022):
                bolt(mb, (side * .820, y + dy, .801), (side, 0, 0), .004)
        # Bed lashing hooks live on the rolled rail, not painted onto its side.
        for y in (-.58, -.95, -1.73, -2.12):
            F.path(mb, [(side * .826, y - .031, .735), (side * .845, y - .027, .700),
                        (side * .845, y + .027, .700), (side * .826, y + .031, .735)], .006, 'Metal', 10)
    road_mudflaps(mb, s)
    # Antenna base and visible telescoping collar, on the original right wing.
    F.tube(mb, (.72, .99, .814), (.72, .989, .849), .015, 'Rubber', 16)
    F.tube(mb, (.72, .989, .843), (.72, .988, .866), .010, 'Metal', 16)


def ranger_bed(mb, s):
    def details(bm, kw, lo, hi, i):
        c, span = (lo + hi) / 2, hi - lo
        if kw.get('mat') == 'Paint' and span.y > 1.6 and span.x < 1.21 and lo.z >= .449 and hi.z <= .494:
            return False  # replace floor + applied ribs with one pressed deck
        if lo.y < -2.285 and abs(c.x) > .74 and lo.z > .39:
            return False  # replace the original lamp bodies and all three lenses
        if kw.get('mat') == 'Trim' and span.x > 1.3 and lo.y < -2.28 and .41 < c.z < .49:
            return False  # integrated painted tailgate pressings replace black bars
        return True
    retain(mb, RANGER.add_bed, details)
    def deck(u, t):
        x, y = .60 * u, -2.237 + 1.835 * t
        ribs = .010 * (.5 + .5 * math.cos(x * math.pi / .043)) ** 4
        fade = C.smoothstep(.012, .032, t) * (1 - C.smoothstep(.97, .99, t))
        return (x, y, .482 + ribs * fade)
    skin(mb, deck, 140, 12, .45)
    for side in (-1, 1):
        # Two subtle ribs over the retained wheel tub make its pressed, rounded
        # sheet construction visible between the cargo and the bed side.
        for x in (side * .665, side * .747):
            pts = []
            for k in range(27):
                y = -s['wb'] / 2 - .36 + .72 * k / 26
                z = s['arch_z'] + math.sqrt((s['arch_r'] + .031) ** 2 - (y + s['wb'] / 2) ** 2)
                pts.append((x, y, z))
            F.path(mb, pts, .003, 'Paint', 8)
        for y in (-.62, -1.31, -2.02):
            x = side * .775
            # Raised stake-pocket lips; the old dark recess is kept inside.
            F.path(mb, [(x - .026, y - .045, .776), (x + .026, y - .045, .776),
                        (x + .026, y + .045, .776), (x - .026, y + .045, .776)], .004, 'Metal', 8, True)
        # Front bed wall / load-guard brackets have a visible load path down to
        # the floor, with gussets, backing plates and four bolts per pedestal.
        F.box(mb, (side * .70, -.48, .754), (.122, .126, .032), 'Metal', .006, 3)
        for dx in (-.041, .041):
            for dy in (-.042, .042):
                bolt(mb, (side * .70 + dx, -.48 + dy, .773), r=.005)
        F.panel(mb, [(side * .694, -.48, .785), (side * .694, -.48, .891),
                     (side * .694, -.59, .785)], 'Trim', .018, .003)
        # Hinges with barrels and through-pins, plus chain anchors on the gate.
        x = side * .54
        F.box(mb, (x, -2.295, .384), (.15, .018, .064), 'Paint', .006, 3)
        F.tube(mb, (x - .082, -2.305, .364), (x + .082, -2.305, .364), .013, 'Metal', 18)
        for dx in (-.05, .05):
            bolt(mb, (x + dx, -2.309, .395), (0, -1, 0), .004)
        for y in (-2.225, -1.98):
            F.box(mb, (side * .76, y, .704), (.025, .055, .062), 'Metal', .005, 3)
            bolt(mb, (side * .744, y, .710), (-side, 0, 0), .005)
        tail_cluster(mb, side * .785, -2.28, .575, .056, .337,
                     ((.650, .146, 'LampRear'), (.535, .055, 'LampAmber'), (.455, .072, 'LampReverse')))
    # Shallow, rounded pressings and a soft hem below the original KESTREL stamp.
    for z in (.432, .470):
        F.path(mb, [(-.70, -2.287, z + .012), (-.66, -2.291, z),
                    (.66, -2.291, z), (.70, -2.287, z + .012)], .004, 'Paint', 10)
    F.box(mb, (0, -2.295, .673), (.237, .014, .052), 'PanelGap', .010, 3)
    F.box(mb, (0, -2.311, .680), (.163, .022, .019), 'Metal', .005, 3)
    retain(mb, RANGER.add_rear)
    F.text(mb, 'FT 1979', (0, -2.441, .230), .043, 'rear', 'Trim')
    plate_light(mb, 0, -2.422, .321)


def ranger_cargo(mb, s):
    def spare(builder, M=Matrix(), **kw):
        M = Matrix.Translation((-.05, -.02, .005)) @ M
        wheel(builder, s, M)
    RANGER.add_wheel = spare
    def details(bm, kw, lo, hi, i):
        c = (lo + hi) / 2
        if kw.get('mat') == 'Rope':
            for v in bm.verts:
                v.co += Vector((-.05, -.02, .005))
        # Both original duffels stay to the left of the full-size spare.
        if -.59 < c.x < -.25 and -2.09 < c.y < -1.03:
            for v in bm.verts:
                v.co.x -= .02
        return True
    retain(mb, RANGER.add_cargo, details)
    base = RANGER.BED_FLOOR + .042
    # Cooler lid gasket, two latches, hinge knuckles and a tied-down webbing belt.
    F.path(mb, [(-.559, -.919, base + .305), (-.181, -.919, base + .305),
                (-.181, -.481, base + .305), (-.559, -.481, base + .305)], .004, 'Rubber', 8, True)
    for y in (-.83, -.57):
        F.box(mb, (-.573, y, base + .275), (.016, .050, .083), 'Metal', .006, 3)
        bolt(mb, (-.583, y, base + .27), (-1, 0, 0), .005)
    for y in (-.80, -.60):
        F.tube(mb, (-.176, y - .035, base + .318), (-.176, y + .035, base + .318), .009, 'Metal', 12)
    strap(mb, [(-.60, -.70, base), (-.577, -.70, base + .328), (-.538, -.70, base + .363),
               (-.202, -.70, base + .363), (-.166, -.70, base + .328), (-.12, -.70, base)], .035)
    F.box(mb, (-.48, -.70, base + .369), (.053, .051, .011), 'Metal', .004, 3)
    # Retain the rolled tent and both bags, adding stitching and buckle hardware.
    for x in (.10, .44):
        F.box(mb, (x, -.625, base + .250), (.041, .059, .012), 'Metal', .004, 3)
        strap(mb, [(x, -.96, base), (x, -.727, base + .193),
                   (x, -.66, base + .251), (x, -.58, base + .251), (x, -.50, base + .18),
                   (x, -.415, base)], .029, (1, 0, 0))
    for y, radius in ((-1.30, .15), (-1.82, .13)):
        for dy in (-.115, .115):
            pts = []
            for k in range(13):
                a = math.pi * k / 12
                pts.append((-.42 + radius * .97 * math.cos(a), y + dy, base + radius * .8 + radius * .8 * math.sin(a) + .003))
            strap(mb, pts, .024)
            F.box(mb, (-.455, y + dy, base + radius * 1.59), (.052, .037, .010), 'Metal', .003, 3)
    # Full-size spare is located inside both wheel tubs. A ratchet belt spans
    # its shoulders and terminates in bed-mounted eyes; the coiled rope remains.
    y = -1.675
    strap(mb, [(-.42, y, base + .013), (-.235, y, base + .13), (-.11, y, base + .296),
               (.40, y, base + .296), (.535, y, base + .15), (.58, y, base + .015)], .036)
    F.box(mb, (.35, y, base + .306), (.074, .052, .017), 'Metal', .005, 3)
    for x in (-.42, .58):
        F.path(mb, [(x - .025, y, base + .010), (x - .024, y, base + .032),
                    (x + .024, y, base + .032), (x + .025, y, base + .010)], .005, 'Metal', 10)
    # Red jerry can: diagonal pressed ribs, cap latch and a fitted retaining band.
    for x in (.315, .485):
        for a, b in (((x, -2.15, base + .10), (x, -1.91, base + .36)),
                     ((x, -2.15, base + .36), (x, -1.91, base + .10))):
            F.tube(mb, a, b, .007, 'CargoRed', 10)
    F.lathe(mb, [(.020, 0), (.026, .006), (.026, .019)], axis='Z', mat='Metal',
            M=Matrix.Translation((.40, -1.93, base + .478)), segs=20)
    strap(mb, [(.31, -2.04, base), (.31, -2.04, base + .424), (.34, -2.04, base + .448),
               (.46, -2.04, base + .448), (.49, -2.04, base + .424), (.49, -2.04, base)], .030)
    F.box(mb, (.496, -2.04, base + .26), (.013, .050, .061), 'Metal', .004, 3)
    F.box(mb, (.40, -2.04, base - .003), (.23, .41, .018), 'Trim', .008, 3)


def front(mb, s):
    if s['spring'] == 'coil':
        def headlight(builder, x, z, y):
            F.box(builder, (x, y + .006, z), (.277, .030, .279), 'Trim', .014, 3)
            F.round_lamp(builder, x, y + .045, z, .098, 'Lamp', flute_mat='Lamp')
            for dx in (-.113, .113):
                for dz in (-.112, .112):
                    bolt(builder, (x + dx, y + .025, z + dz), (0, 1, 0), .004)
        SCOUT.headlight = headlight
        retain(mb, SCOUT.add_front)
        # The complete released winch stays: refine its mounts, drum flanges,
        # electrical lead and recovery-shackle pins instead of hiding it away.
        for x in (-.30, .20):
            F.box(mb, (x, 1.911, .402), (.09, .126, .023), 'Metal', .005, 3)
            for y in (1.872, 1.948):
                bolt(mb, (x, y, .418), r=.006)
        for x in (-.16, .151):
            F.tube(mb, (x - .005, 1.915, .47), (x + .005, 1.915, .47), .074, 'Metal', 24)
        F.path(mb, [(-.20, 1.865, .496), (-.20, 1.817, .566), (.22, 1.820, .568), (.22, 1.859, .569)], .007, 'Rubber', 10)
        for side in (-1, 1):
            F.tube(mb, (side * .72 - .044, 2.028, .289), (side * .72 + .044, 2.028, .289), .009, 'Metal', 12)
            bolt(mb, (side * .72 + .048, 2.028, .289), (1, 0, 0), .013)
            F.box(mb, (side * .34, 1.827, .272), (.087, .25, .095), 'Trim', .009, 3)
        # Narrow wing-top vents and a relief edge keep the front from becoming
        # a featureless box while respecting the release bonnet and grille.
        for side in (-1, 1):
            for k in range(4):
                F.box(mb, (side * .859, .905 + k * .052, .826), (.057, .019, .004), 'Trim', .003, 3)
    else:
        def lens(builder, x, z, y, r, mat, facing=1, segs=16, bezel='Chrome'):
            F.round_lamp(builder, x, y + .021, z, r, mat, facing, flute_mat=mat)
        RANGER.lens = lens
        retain(mb, RANGER.add_front)
        for side in (-1, 1):
            for x in (side * .745, side * .495):
                for z in (.414, .626):
                    bolt(mb, (x, 2.071, z), (0, 1, 0), .004)
            F.box(mb, (side * .40, 2.173, .237), (.044, .012, .156), 'Rubber', .006, 3)
            F.tube(mb, (side * .52 - .040, 2.104, .149), (side * .52 + .040, 2.104, .149), .009, 'Metal', 12)
        F.text(mb, 'FT 1979', (0, 2.160, .227), .043, 'front', 'Trim')


def chassis(mb, s):
    def details(bm, kw, lo, hi, i):
        # The running gear is shared with the Toyota, but the engine and tank
        # must fit the lower released bonnet and the short pickup wheelbase.
        if s['spring'] == 'leaf' and hi.z > .80 and lo.y > .7:
            for v in bm.verts:
                v.co.z -= .028
        return True
    retain(mb, lambda builder: F.chassis(builder, s), details)
    end = Vector(s.get('exhaust_exit', (-.55, s['rear'] + .06, .26)))
    finish = end + Vector((-.08, -.10, 0))
    length = (finish - end).length
    bm = C.bm_lathe([(.029, 0), (.029, length - .007), (.031, length),
                     (.022, length), (.022, length - .030)], 24, axis='Z')
    M = Matrix.Translation(end) @ Vector((0, 0, 1)).rotation_difference(finish - end).to_matrix().to_4x4()
    mb.add(C.xform(bm, M), mat='Metal', shade='auto', angle=40)


def build_body(mb, s):
    tub(mb, s)
    greenhouse(mb, s)
    front(mb, s)
    if s['spring'] == 'coil':
        scout_sides(mb, s)
        scout_rear(mb, s)
        scout_rack(mb)
    else:
        ranger_sides(mb, s)
        ranger_bed(mb, s)
        retain(mb, RANGER.add_rollbar)
        ranger_cargo(mb, s)
        # Keep both original guarded spotlights and brace feet on the load bar.
        for side in (-1, 1):
            F.box(mb, (side * .77, -.98, .777), (.09, .11, .018), 'Metal', .004, 3)
            for dy in (-.034, .034):
                bolt(mb, (side * .77, -.98 + dy, .790), r=.005)
        F.path(mb, [(-.32, -.523, 1.462), (-.61, -.518, 1.374),
                    (-.704, -.51, 1.28), (-.704, -.51, .798)], .004, 'Rubber', 8)
    chassis(mb, s)


def main(vid):
    C.reset_scene()
    s = SPECS[vid]
    study = os.path.join(C.ART, 'studies', 'trail-companions', REVISION, vid,
                         'build-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    os.makedirs(study, exist_ok=False)
    with open(__file__, 'rb') as source, open(os.path.join(study, 'generator.py'), 'wb') as snapshot:
        snapshot.write(source.read())
    mats, parts, tris = materials(s), {}, {}
    col = C.collection('Trail source parts')
    def body(mb):
        build_body(mb, s)
    def spring(mb):
        if s['spring'] == 'leaf':
            F.leaf(mb)
        else:
            height = s['spring_top'] - s['spring_seat']
            pts = [(.065 * math.cos(i * math.tau / 32), .065 * math.sin(i * math.tau / 32),
                    .009 + (height - .018) * i / 256) for i in range(257)]
            F.path(mb, pts, .009, 'Chassis', 8)
    builders = {'Body': body, 'Wheel': lambda mb: wheel(mb, s),
                'AxleFront': lambda mb: F.axle(mb, s, True), 'AxleRear': lambda mb: F.axle(mb, s, False),
                'Spring': spring, 'ShockBody': lambda mb: F.shock(mb, length=s['shock']['barrelLength']),
                'ShockRod': lambda mb: F.shock(mb, True),
                'BrakeFront': lambda mb: F.brake(mb, s), 'BrakeRear': lambda mb: F.brake(mb, s, True),
                'Driveshaft': P.add_driveshaft, 'Wheel_LOD1': lambda mb: wheel(mb, s, detailed=False)}
    for name, fn in builders.items():
        mb = C.MeshBuilder(name)
        fn(mb)
        tris[name] = mb.tris()
        parts[name] = mb.build(mats, vcolor=False, collection_obj=col)
    if s['spring'] == 'leaf':
        F.morph_spring(parts['Spring'], s)
    else:
        spring_obj = parts['Spring']
        spring_obj.shape_key_add(name='Basis')
        for name, travel in (('Bump', .25), ('Droop', -.20)):
            key = spring_obj.shape_key_add(name=name)
            for i, v in enumerate(key.data):
                # Translate each wire cross section intact. Scaling all Z
                # coordinates would make the wire thinner during compression.
                v.co.z += travel * (1 - (i // 8) / 256)
    low = bpy.data.objects.new('Body_LOD1', parts['Body'].data.copy())
    col.objects.link(low)
    mod = low.modifiers.new('Distance LOD', 'DECIMATE')
    mod.ratio, mod.use_collapse_triangulate = .40, True
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.modifier_apply(modifier=mod.name)
    # Edge collapse can move a pane's border out of its plane. Restore the
    # authored glass planes, moving their shared seal vertices with them.
    source = parts['Body'].data
    glass_index = next(i for i, mat in enumerate(source.materials) if mat.name == 'Glass')
    planes = [(face.center.copy(), face.normal.copy()) for face in source.polygons if face.material_index == glass_index]
    for face in low.data.polygons:
        if face.material_index != glass_index:
            continue
        points = [low.data.vertices[i].co for i in face.vertices]
        center, normal = min(planes, key=lambda p: sum(abs((v - p[0]).dot(p[1])) for v in points)
                             + (1 - abs(face.normal.dot(p[1]))))
        for v in points:
            v -= normal * (v - center).dot(normal)
    low.data.update()
    parts[low.name] = low
    tris[low.name] = sum(len(p.vertices) - 2 for p in low.data.polygons)
    dims = dict(id=vid, fidelity=3, R=s['r'], W=s['tw'], wheelbase=s['wb'], track_x=s['tx'],
                spring_x=s['spring_x'], spring_top=s['spring_top'], spring_seat=s['spring_seat'],
                pinion_y=.235, pinion_z=.025, tcase_y=.30, tcase_z=.05,
                bump=s['bump'], droop=s['droop'], lock=s['lock'], shock=s['shock'])
    with open(os.path.join(study, 'rig.json'), 'w') as f:
        json.dump(dims, f, indent=2)
    import vehicle_check
    checks = vehicle_check.run(parts, dims, shrink=1.0)
    with open(os.path.join(study, 'clearance.json'), 'w') as f:
        json.dump(checks, f, indent=2)
    # Save failed candidates for inspection; only clean builds replace game assets.
    col.hide_render = True
    F.assemble(parts, C.collection('Assembled vehicle'), dims)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(study, 'candidate.blend'), compress=True)
    if any(checks.values()):
        raise RuntimeError('Trail running-gear clearance failed; see ' + study)
    bpy.context.view_layer.update()
    C.export_glb(list(parts.values()), 'vehicle_' + vid + '.glb', vcolor=False, morph=True)
    mn, mx = C.world_bbox([parts['Body']])
    lamps = dict(SCOUT.LAMPS if vid == 'scout' else RANGER.LAMPS)
    if vid == 'scout':
        lamps['head'] = [(x, 1.861, .60) for x in (-.665, .665)]
        lamps['tail'] = lamps['brake'] = [(x, -1.878, .607) for x in (-.78, .78)]
        lamps['reverse'] = [(x, -1.878, .397) for x in (-.78, .78)]
    else:
        lamps['head'] = [(x, 2.102, .52) for x in (-.62, .62)]
        lamps['bar'] = [(x, -.413, 1.48) for x in (-.32, .32)]
        lamps['tail'] = lamps['brake'] = [(x, -2.338, .650) for x in (-.785, .785)]
        lamps['reverse'] = [(x, -2.338, .455) for x in (-.785, .785)]
    info = dict(id=vid, fidelity=3, style='published-release-refinement/1', sourceRelease=RELEASE, revision=REVISION, reference=s['reference'],
                rigFile='art/vehicle-' + vid + '-rig.json',
                wheelBase=s['wb'], trackX=s['tx'], wheelRadius=s['r'], wheelWidth=s['tw'],
                spring=dict(x=s['spring_x'], top=s['spring_top'], seat=s['spring_seat'], kind=s['spring'],
                            morphBump=.25, morphDroop=.20),
                shock=s['shock'], driveshaft=dict(tcaseZ=.30, tcaseY=.05, pinionZ=.235, pinionY=.025),
                lamps={k: [P.g(p) for p in ps] for k, ps in lamps.items()},
                lampSample=dict(tail=[.018, .018], reverse=[.018, .016]),
                bodyBox=dict(min=P.g((mn.x, mx.y, mn.z)), max=P.g((mx.x, mn.y, mx.z))),
                lod=dict(near=18, far=23), tris=tris, build=os.path.relpath(study, C.GAME))
    for file, data in ((os.path.join(C.MODELS, 'vehicle_' + vid + '.json'), info),
                       (os.path.join(C.ART, 'vehicle-' + vid + '-rig.json'), dims),
                       (os.path.join(study, 'rig.json'), dims)):
        with open(file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    col.hide_viewport = True
    C.save_blend('vehicle_' + vid + '.blend')
    print('TRAIL', vid, json.dumps(dict(tris=tris, bounds=info['bodyBox'], study=study)), flush=True)
    return tris


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for vid in [x for x in args if x in SPECS] or list(SPECS):
        main(vid)
