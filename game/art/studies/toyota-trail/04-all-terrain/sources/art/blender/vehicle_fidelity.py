"""Reference-led expedition vehicles, in metres, +Y forward and +Z up.

The three silhouettes are authored independently. Small mechanical components are
shared; opaque parts are batched by material, glazing and running gear stay separate.
See docs/VEHICLE-FIDELITY.md for references, game adaptations and verification.
"""
import bpy, bmesh, math, os, sys, json
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import vehicle_parts as P

TAU = math.tau
SPECS = {
    'scout': dict(reference='Land Rover Defender 90 · 300Tdi', wb=2.36, tx=.825, r=.38, tw=.30,
                  width=.90, front=1.84, rear=-1.80, belt=.93, roof=1.62, cowl=.48, cabrear=-1.75,
                  topfront=.29, paint='#A56F53', accent='#E3DECA', spring='coil', spring_x=.45,
                  spring_top=.53, spring_seat=.065, bump=.24, droop=.12, lock=38.7),
    'toyota': dict(reference='Toyota Land Cruiser FJ60 · 1980–1987', wb=2.73, tx=.86, r=.40, tw=.30,
                   width=.90, front=2.16, rear=-2.34, belt=.90, roof=1.46, cowl=.69, cabrear=-2.26,
                   topfront=.34, paint='#C3B28F', accent='#D9CBAA', spring='leaf', spring_x=.47,
                   spring_top=.48, spring_seat=.055, bump=.25, droop=.13, lock=35.3),
    'ranger': dict(reference='Toyota Hilux RN46 · 1979–1983', wb=2.80, tx=.79, r=.36, tw=.27,
                   width=.845, front=2.08, rear=-2.49, belt=.83, roof=1.405, cowl=.77, cabrear=-.47,
                   topfront=.48, paint='#6C9A94', accent='#E5DFCC', spring='leaf', spring_x=.44,
                   spring_top=.46, spring_seat=.055, bump=.23, droop=.13, lock=38.6),
}


def box(mb, loc, size, mat='Paint', bevel=.008, segs=3, rot=(0, 0, 0)):
    mb.add(C.bm_box(size, loc, bevel, segs, rot), mat=mat, shade='auto', angle=45)


def tube(mb, a, b, r=.012, mat='Metal', segs=12):
    mb.add(C.bm_cyl_between(a, b, r, segs=segs), mat=mat, shade='auto', angle=48)


def path(mb, points, r=.006, mat='Trim', segs=8, closed=False):
    """Continuous swept tube, without the beads/joints of overlapping cylinders."""
    pts = [Vector(p) for p in points]
    if closed:
        pts.append(pts[0])
    verts, faces = [], []
    for i, p in enumerate(pts):
        tangent = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        ref = Vector((1, 0, 0)) if abs(tangent.x) < .9 else Vector((0, 1, 0))
        u = tangent.cross(ref).normalized()
        v = tangent.cross(u).normalized()
        for j in range(segs):
            verts.append(p + r * (u * math.cos(j * TAU / segs) + v * math.sin(j * TAU / segs)))
        if i:
            for j in range(segs):
                a, b = (i - 1) * segs + j, (i - 1) * segs + (j + 1) % segs
                faces.append([a, b, b + segs, a + segs])
    bm = C.bm_from(verts, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mb.add(bm, mat=mat, shade='smooth')


def lathe(mb, profile, axis='X', mat='Metal', M=Matrix(), segs=64):
    bm = C.bm_lathe(profile, segs, axis=axis)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mb.add(C.xform(bm, M), mat=mat, shade='auto', angle=48)


def text(mb, value, loc, size=.06, facing='front', mat='Chrome'):
    # text XY -> outward-facing plane; readers see the correct handedness on all sides
    rotations = {
        'front': Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))),
        'rear': Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1))),
        'right': Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))),
        'left': Matrix(((0, 0, -1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))),
    }
    mb.add(P.bm_text(value, size, .0015, Matrix.Translation(loc) @ rotations[facing]), mat=mat, shade='flat')


def panel(mb, pts, mat='Paint', thickness=.014, bevel=.008):
    bm = C.bm_from(pts, [list(range(len(pts)))])
    bm.normal_update()
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    vs = [x for x in ret['geom'] if isinstance(x, bmesh.types.BMVert)]
    normal = next(iter(bm.faces)).normal.copy()
    bmesh.ops.translate(bm, verts=vs, vec=-normal * thickness)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    C.bevel(bm, bevel, 3)
    mb.add(bm, mat=mat, shade='auto', angle=42)


def rounded_loop(points, radius=.05, steps=6):
    """Round polygon corners in their own plane (window seals / stampings)."""
    pts = [Vector(p) for p in points]
    out = []
    for i, p in enumerate(pts):
        a, b = pts[i - 1] - p, pts[(i + 1) % len(pts)] - p
        d = min(radius, a.length * .22, b.length * .22)
        a, b = p + a.normalized() * d, p + b.normalized() * d
        for j in range(steps + 1):
            t = j / steps
            out.append((1 - t) ** 2 * a + 2 * t * (1 - t) * p + t * t * b)
    return out


def window(body, glass, points, chrome=False):
    pts = rounded_loop(points)
    panel(glass, pts, 'Glass', .003, 0)
    path(body, pts, .014, 'Rubber', 10, True)
    if chrome:
        center = sum(pts, Vector()) / len(pts)
        path(body, [center + (p - center) * 1.022 for p in pts], .004, 'Chrome', 8, True)


def materials(s):
    mats = P.base_materials(s['paint'], s['accent'], '#D2CDC0')
    for key, color, rough, metal in (
        ('Paint', s['paint'], .27, .15), ('PaintAccent', s['accent'], .32, .06),
        ('Interior', '#574B3E', .82, 0), ('Seat', '#81705B', .93, 0),
        ('Trim', '#252B2B', .54, .08), ('Rubber', '#171B1C', .86, 0),
        ('Tire', '#24292A', .88, 0), ('Sidewall', '#303638', .76, 0),
        ('Metal', '#7E898B', .33, .82), ('Chrome', '#C8D1D3', .17, .97),
        ('Chassis', '#333D3C', .64, .62), ('Dial', '#E6D7BB', .61, 0),
        ('Rim', '#D3CEC0' if s['spring'] == 'coil' else '#B6BFC0', .27, .68),
        ('Cargo', '#75715A', .87, 0), ('Recovery', '#BE602C', .72, .05),
        ('Badge', '#1B392D', .31, .08), ('Reflector', '#DDE2DF', .20, .92),
    ):
        if key in mats:
            bpy.data.materials.remove(mats[key])
        mats[key] = C.mat_pbr(key, color, rough, metal)
    for key in ('Paint', 'PaintAccent'):
        bs = mats[key].node_tree.nodes['Principled BSDF']
        bs.inputs['Coat Weight'].default_value = .38
        bs.inputs['Coat Roughness'].default_value = .19
    # glTF alpha blend is intentional: all three hollow cabins have actual interiors.
    gl = mats['Glass']
    bs = gl.node_tree.nodes['Principled BSDF']
    bs.inputs['Base Color'].default_value = (*C.s2l(C.hexc('#6E8D91')), .24)
    bs.inputs['Alpha'].default_value = .24
    bs.inputs['Roughness'].default_value = .12
    bs.inputs['Metallic'].default_value = .12
    gl.surface_render_method = 'BLENDED'
    gl.use_backface_culling = False
    gl.diffuse_color = (*C.s2l(C.hexc('#6E8D91')), .24)
    # Lamps have reflectors and lens flutes; illumination is controlled by the game.
    for key in ('Lamp', 'LampAux', 'LampRear', 'LampAmber', 'LampReverse'):
        bs = mats[key].node_tree.nodes['Principled BSDF']
        bs.inputs['Emission Strength'].default_value = 0
        bs.inputs['Metallic'].default_value = .22
    return mats


def wheel(mb, s, M=Matrix()):
    """Rounded 64-sided carcass; 144 tread blocks; open steel-wheel ventilation.

    The rim face is an annulus + disconnected radial webs, so the holes are real.
    Tyre radius and width match the physical envelope including the tread.
    """
    r, w = s['r'], s['tw']
    sc = Matrix.Diagonal((w / .30, r / .38, r / .38, 1))
    M = M @ sc
    profile = [(.204, -.121), (.218, -.137), (.255, -.146), (.288, -.149), (.323, -.142),
               (.346, -.126), (.36, -.099), (.361, -.05), (.362, 0), (.361, .05),
               (.36, .099), (.346, .126), (.323, .142), (.288, .149), (.255, .146), (.218, .137), (.204, .121)]
    lathe(mb, profile, mat='Tire', M=M)
    for side in (-1, 1):
        for rr in (.225, .254, .307):
            ring = [(rr + .0018 * math.cos(a), side * (.144 + .0018 * math.sin(a))) for a in [i * TAU / 8 for i in range(9)]]
            lathe(mb, ring, mat='Sidewall', M=M)
    for k in range(48):
        for row in (-1, 0, 1):
            a = TAU * (k + (row % 2) * .48) / 48
            x = row * .093
            # chamfered tread blocks, staggered chevrons with small open sipes
            T = M @ Matrix.Rotation(a, 4, 'X') @ Matrix.Translation((x, 0, .367))
            for offset in (-.0115, .0115):
                blk = C.bm_box((.078 if row else .075, .018, .025), (0, offset, 0), .003, 2,
                               (0, 0, .28 * (1 if row >= 0 else -1)))
                mb.add(C.xform(blk, T), mat='Tire', shade='auto', angle=42)
        for side in (-1, 1):
            a = TAU * (k + .2) / 48
            T = M @ Matrix.Rotation(a, 4, 'X')
            mb.add(C.xform(C.bm_box((.012, .020, .031), (side * .143, 0, .32), .003, 2), T), mat='Tire', shade='auto')
    # Rolled lip and barrel, with an open front face inside the ventilation ring.
    lathe(mb, [(.205, -.117), (.211, -.125), (.217, -.123), (.219, -.117), (.215, .116),
               (.219, .125), (.215, .137), (.206, .139), (.202, .131), (.199, .106), (.174, .078)], mat='Rim', M=M)
    lathe(mb, [(0, .103), (.058, .103), (.065, .089), (.096, .079), (.120, .058)], mat='Rim', M=M)
    # Pressed steel dish with eight radiused ventilation slots, not decorative dots.
    dish = C.bm_lathe([(.070, .098), (.120, .079), (.177, .079), (.204, .121),
                       (.204, .107), (.177, .064), (.120, .064), (.070, .083), (.070, .098)], 64, axis='X')
    bmesh.ops.recalc_face_normals(dish, faces=dish.faces)
    cuts = []
    for k in range(8):
        a = k * TAU / 8
        cut = C.bm_cyl_between((-.03, 0, .151), (.18, 0, .151), .024, segs=24)
        for v in cut.verts:
            v.co.z = .151 + (v.co.z - .151) * 1.30
        cuts.append(C.xform(cut, Matrix.Rotation(a, 4, 'X')))
    dish = P.bm_boolean(dish, cuts)
    C.bevel(dish, .0025, 2)
    mb.add(C.xform(dish, M), mat='Rim', shade='auto', angle=42)
    lathe(mb, [(0, .108), (.048, .108), (.050, .145), (.041, .161), (0, .161)], mat='Metal', M=M, segs=32)
    for k in range(5 if s['spring'] == 'coil' else 6):
        a = k * TAU / (5 if s['spring'] == 'coil' else 6)
        y, z = .082 * math.sin(a), .082 * math.cos(a)
        mb.add(C.xform(C.bm_cyl_between((.079, y, z), (.104, y, z), .010, segs=6), M), mat='Chrome', shade='auto')
    if s['spring'] == 'leaf':
        lathe(mb, [(0, .162), (.027, .162), (.027, .174), (0, .174)], mat='Recovery', M=M, segs=24)
        mb.add(C.xform(C.bm_box((.009, .045, .008), (.179, 0, 0), .002, 2), M), mat='Metal', shade='auto')
    # valve stem and embossed tyre identification, all on the actual sidewall
    tube(mb, M @ Vector((.129, .184, .038)), M @ Vector((.155, .184, .043)), .006, 'Rubber', 10)
    for phrase, center in (('ALL TERRAIN', math.pi / 2), ('RADIAL 4WD', -math.pi / 2)):
        for i, ch in enumerate(phrase):
            a = center + (i - (len(phrase) - 1) / 2) * .094
            pos = Vector((.153, .28 * math.cos(a), .28 * math.sin(a)))
            R = Matrix(((0, 0, 1, 0), (-math.sin(a), math.cos(a), 0, 0),
                        (math.cos(a), math.sin(a), 0, 0), (0, 0, 0, 1)))
            mb.add(P.bm_text(ch, .023, .0011, M @ Matrix.Translation(pos) @ R), mat='Sidewall', shade='flat')


def round_lamp(mb, x, y, z, radius=.095, mat='Lamp', facing=1):
    M = Matrix.Translation((x, y, z)) @ Matrix.Rotation(0 if facing == 1 else math.pi, 4, 'Z')
    lathe(mb, [(radius + .015, -.035), (radius + .018, -.013), (radius + .013, .009),
               (radius, .013), (radius - .006, -.003)], axis='Y', mat='Chrome', M=M, segs=48)
    lathe(mb, [(radius - .008, -.008), (radius * .70, -.037), (0, -.044)], axis='Y', mat='Reflector', M=M, segs=40)
    lathe(mb, [(radius, -.001), (radius * .82, .008), (radius * .4, .014), (0, .016)], axis='Y', mat=mat, M=M, segs=48)
    for i in range(-7, 8):
        xx = i * radius / 8
        h = math.sqrt(max(0, (radius * .95) ** 2 - xx * xx))
        if h > 0:
            tube(mb, M @ Vector((xx, .015, -h)), M @ Vector((xx, .015, h)), .0014, 'Reflector', 6)
    for a in (0, 2.094, 4.189):
        p = Vector(((radius + .011) * math.cos(a), .008, (radius + .011) * math.sin(a)))
        tube(mb, M @ p, M @ (p + Vector((0, .004, 0))), .0035, 'Trim', 6)


def rect_lamp(mb, loc, size, mat='LampRear'):
    x, y, z = loc
    box(mb, loc, (size[0] + .025, .032, size[2] + .025), 'Chrome', .015)
    box(mb, (x, y - .020, z), size, mat, .009)
    for i in range(1, 10):
        zz = z - size[2] / 2 + size[2] * i / 10
        box(mb, (x, y - .028, zz), (size[0] * .88, .002, .0017), mat, .0007, 1)


def hood(mb, s, defender=False):
    """Crowned sheet, with a rolled perimeter and longitudinal pressed creases."""
    y0, y1, w = s['cowl'] + .035, s['front'] - .035, s['width'] - .035
    verts, faces = [], []
    nx, ny = 32, 16
    for j in range(ny + 1):
        t = j / ny
        y = y0 + (y1 - y0) * t
        for i in range(nx + 1):
            u = i / nx * 2 - 1
            z = s['belt'] + .015 - t * (.045 if not defender else .018)
            z += (.035 if not defender else .014) * (1 - u ** 4)
            z += .008 * math.exp(-((abs(u) - .72) / .05) ** 2)
            verts.append((u * w * (1 - .018 * t), y, z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append([a, a + 1, a + nx + 2, a + nx + 1])
    bm = C.bm_from(verts, faces)
    C.orient(bm, lambda f: (0, 0, 1))
    mb.add(bm, mat='Paint', shade='smooth')
    edge = verts[:nx + 1] + [verts[j * (nx + 1) + nx] for j in range(1, ny + 1)]
    edge += list(reversed(verts[-nx - 1:-1])) + [verts[j * (nx + 1)] for j in range(ny - 1, 0, -1)]
    path(mb, edge, .006, 'Trim', 8, True)
    for sx in (-1, 1):
        tube(mb, (sx * w, y0, s['belt'] + .014), (sx * w * .982, y1, s['belt'] - .035), .012, 'Paint', 12)
    # Rolled-down leading edge closes the bonnet above the grille at every crown height.
    front_row = verts[-nx - 1:]
    skirt, fs = [], []
    for i, (x, y, z) in enumerate(front_row):
        skirt.extend([(x, y, z), (x, y + .025, z - .009), (x, y + .025, z - .072)])
        if i:
            a = (i - 1) * 3
            fs.extend([[a, a + 3, a + 4, a + 1], [a + 1, a + 4, a + 5, a + 2]])
    bm = C.bm_from(skirt, fs)
    C.orient(bm, lambda f: (0, 1, .15))
    mb.add(bm, mat='Paint', shade='smooth')


def side_shell(mb, s, start, end, top, arches, mat='Paint', bottom=.18):
    """Thin shaped body skin with genuine wheel openings, never a solid box cabin."""
    for side in (-1, 1):
        pts = [(start, top), (end, top), (end, bottom)]
        for axle in sorted(arches, reverse=True):
            rr = s['r'] + .14
            zc = .17
            # follow the top of each arch from front to rear along the lower edge
            for i in range(49):
                a = i * math.pi / 48
                pts.append((axle + rr * math.cos(a), zc + rr * math.sin(a)))
        pts.append((start, bottom))
        bm = C.bm_extrude_poly(pts, .027, axis='X', center=side * (s['width'] - .015))
        # rolled lower edge / belt shoulder: the body has curvature in section
        for v in bm.verts:
            f = max(0, min(1, (v.co.z - bottom) / (top - bottom)))
            v.co.x -= side * (.035 * (1 - f) ** 3 + .014 * f ** 8)
        C.bevel(bm, .006, 3)
        mb.add(bm, mat=mat, shade='auto', angle=42)
        for axle in arches:
            rr = s['r'] + .14
            # shaped fender lip with a rounded return and a dark inner wheel well
            verts, faces = [], []
            for i in range(49):
                a = i * math.pi / 48
                for off, xx in ((0, s['width'] - .028), (.003, s['width'] + .003),
                                (.027, s['width'] + .032), (.043, s['width'] + .018)):
                    verts.append((side * xx, axle + (rr + off) * math.cos(a), .17 + (rr + off) * math.sin(a)))
                if i:
                    for j in range(3):
                        a0 = (i - 1) * 4 + j
                        faces.append([a0, a0 + 4, a0 + 5, a0 + 1])
            bm = C.bm_from(verts, faces)
            C.orient(bm, lambda f: (side, 0, 1))
            mb.add(bm, mat='Trim' if s['spring'] == 'coil' else mat, shade='smooth')
            # inner arch roof only: leaves the steering/axle travel corridor open
            verts, faces = [], []
            for i in range(33):
                a = .22 + (math.pi - .44) * i / 32
                for xx in (.34, s['width'] - .025):
                    verts.append((side * xx, axle + (rr + .012) * math.cos(a), .18 + (rr + .012) * math.sin(a)))
                if i:
                    faces.append([i * 2 - 2, i * 2, i * 2 + 1, i * 2 - 1])
            bm = C.bm_from(verts, faces)
            C.orient(bm, lambda f: (0, 0, -1))
            mb.add(bm, mat='Rubber', shade='smooth')


def door_details(mb, s, y0, y1, side, hinges=False):
    x, top = side * (s['width'] + .002), s['belt']
    pts = [(x, y0, top - .012)]
    for i in range(33):
        y = y0 + (y1 - y0) * i / 32
        z = .245
        for axle_y in (-s['wb'] / 2, s['wb'] / 2):
            dy, rr = y - axle_y, s['r'] + .163
            if abs(dy) < rr:
                z = max(z, .17 + math.sqrt(rr * rr - dy * dy))
        pts.append((x, y, z))
    pts.append((x, y1, top - .012))
    path(mb, rounded_loop(pts, .025), .0032, 'Trim', 6)
    # recess, pull handle, key cylinder, belt moulding
    yh = y0 + .15
    box(mb, (x, yh, top - .105), (.012, .15, .045), 'Trim', .015)
    box(mb, (x + side * .017, yh, top - .10), (.018, .11, .016), 'Chrome', .006)
    tube(mb, (x, yh - .11, top - .10), (x + side * .008, yh - .11, top - .10), .008, 'Chrome', 16)
    if hinges:
        for z in (.38, .81):
            box(mb, (x + side * .008, y1 - .022, z), (.029, .08, .038), 'PaintAccent', .005)
            tube(mb, (x + side * .032, y1 - .025, z - .024), (x + side * .032, y1 - .025, z + .024), .012, 'Metal')
            for dy in (-.028, .028):
                tube(mb, (x, y1 - .022 + dy, z), (x + side * .025, y1 - .022 + dy, z), .004, 'Metal', 6)


def cabin(body, glass, s, windows, defender=False):
    b, top, f, back, tf = s['belt'], s['roof'], s['cowl'], s['cabrear'], s['topfront']
    w, wt = s['width'], s['width'] - (.04 if defender else .085)
    # A/B/C pillars, narrow header, curved roof sheet and rain gutter
    for side in (-1, 1):
        for y, yt in ((f, tf), (back, back + .06)):
            tube(body, (side * (w - .025), y, b), (side * wt, yt, top - .045), .030 if defender else .036, 'Paint', 12)
        box(body, (side * (wt + .003), (tf + back) / 2, top - .027), (.063, tf - back + .06, .055), 'Paint', .019)
        tube(body, (side * (wt + .046), back - .055, top + .008), (side * (wt + .046), tf + .05, top + .008), .014, 'Chrome' if not defender else 'PaintAccent')
        for lower0, lower1, upper0, upper1 in windows:
            def p(y, z):
                x = w - .025 + ((z - b) / (top - b)) * (wt - w + .025)
                return (side * x, y, z)
            window(body, glass, [p(lower0, b + .038), p(lower1, b + .038),
                                 p(upper1, top - .075), p(upper0, top - .075)], chrome=not defender)
            tube(body, p(lower0 - .033, b + .012), p(upper0 - .033, top - .048), .028, 'Paint', 12)
    window(body, glass, [(-w + .055, f + .014, b + .05), (w - .055, f + .014, b + .05),
                         (wt - .035, tf + .022, top - .073), (-wt + .035, tf + .022, top - .073)], chrome=not defender)
    window(body, glass, [(wt - .035, back - .015, top - .075), (-wt + .035, back - .015, top - .075),
                         (-w + .07, back - .046, b + .075), (w - .07, back - .046, b + .075)], chrome=not defender)
    # roof crown: a dense cross section avoids a flat shoebox silhouette
    roof_mat = 'PaintAccent' if defender or s['wb'] > 2.79 else 'Paint'
    verts, faces = [], []
    for j in range(25):
        t = j / 24
        y = back - .07 + (tf - back + .13) * t
        for i in range(33):
            u = i / 32 * 2 - 1
            z = top + .048 * (1 - u ** 4) + .012 * math.sin(math.pi * t)
            z -= .020 * abs(2 * t - 1) ** 14
            verts.append((u * (wt + .042), y, z))
    for j in range(24):
        for i in range(32):
            a = j * 33 + i
            faces.append([a, a + 1, a + 34, a + 33])
    bm = C.bm_from(verts, faces)
    C.orient(bm, lambda f: (0, 0, 1))
    body.add(bm, mat=roof_mat, shade='smooth')
    for x in (-wt, wt):
        tube(body, (x, back - .07, top), (x, tf + .06, top), .025, roof_mat)
    for yy in (back - .063, tf + .044):
        tube(body, (-wt, yy, top), (wt, yy, top), .025, roof_mat)
    # cowl plenum and functional-looking wipers, with blade separate from arm
    box(body, (0, f + .01, b + .012), (w * 1.93, .12, .052), 'Paint', .015)
    slope = (top - b) / (f - tf)
    for x in (-.40, .40):
        arm0, arm1 = (x, f + .032, b + .07), (x - .14, f - .066, b + .07 + slope * .07)
        tube(body, arm0, arm1, .007, 'Trim', 8)
        tube(body, (arm1[0] - .19, arm1[1], arm1[2]), (arm1[0] + .19, arm1[1], arm1[2]), .010, 'Rubber', 8)
        tube(body, (x, f + .033, b + .06), (x, f + .046, b + .065), .014, 'Metal', 12)
    for side in (-1, 1):
        # angled mirror stalk, molded housing, recessed reflective face
        y, z = f - .15, b + .17
        x = side * (w + .17)
        path(body, [(side * w, y + .06, b), (x, y + .10, z - .05), (x, y, z)], .012, 'Metal', 12)
        box(body, (x, y, z), (.15, .07, .205), 'Trim', .033, 5)
        box(body, (x, y - .039, z), (.124, .005, .176), 'Chrome', .027, 5)


def interior(mb, s):
    w, b, f, rear = s['width'], s['belt'], s['cowl'], s['cabrear']
    box(mb, (0, (f + rear) / 2, .46), (.40, f - rear, .04), 'Interior', .008)
    # Floor wings end before the wheel wells, leaving full steering/bump clearance.
    ay, radius = s['wb'] / 2, s['r'] + .16
    intervals = [(rear, f)]
    for axle_y in (-ay, ay):
        clipped = []
        for a, b in intervals:
            if a < axle_y - radius:
                clipped.append((a, min(b, axle_y - radius)))
            if b > axle_y + radius:
                clipped.append((max(a, axle_y + radius), b))
        intervals = [(a, b) for a, b in clipped if b > a]
    for a, b in intervals:
        box(mb, (0, (a + b) / 2, .46), (w * 1.82, b - a, .04), 'Interior', .008)
    box(mb, (0, .1, .54), (.25, 1.10, .18), 'Trim', .055, 5)
    for x in (-.43, .43):
        y = f - .68
        box(mb, (x, y, .61), (.55, .52, .13), 'Seat', .065, 5)
        box(mb, (x, y - .22, .88), (.55, .125, .51), 'Seat', .058, 5, (math.radians(-9), 0, 0))
        for dy in (-.20, -.12, -.04, .04, .12, .20):
            tube(mb, (x - .23, y + dy, .679), (x + .23, y + dy, .679), .002, 'Interior', 6)
        for xx in (-.15, -.075, 0, .075, .15):
            tube(mb, (x + xx, y - .143, .72), (x + xx, y - .20, 1.10), .002, 'Interior', 6)
        for dx in (-.10, .10):
            tube(mb, (x + dx, y - .24, 1.10), (x + dx, y - .24, 1.19), .007, 'Metal')
        box(mb, (x, y - .24, 1.20), (.29, .115, .14), 'Seat', .045, 4)
        box(mb, (x * .42, y - .04, .66), (.034, .05, .07), 'Trim', .005)
        box(mb, (x * .42, y - .04, .70), (.027, .027, .012), 'Recovery', .003)
    if rear < -1:
        box(mb, (0, rear + .64, .74), (1.44, .49, .13), 'Seat', .056, 5)
        box(mb, (0, rear + .40, .92), (1.44, .12, .47), 'Seat', .045, 5)
    box(mb, (0, f - .10, b - .04), (w * 1.80, .30, .18), 'Interior', .048, 5)
    box(mb, (0, f - .265, b - .035), (w * 1.73, .025, .16), 'Trim', .012)
    # gauge binnacle, concentric bezels, needles, individual scale marks
    box(mb, (-.43, f - .282, b + .025), (.46, .025, .22), 'Trim', .035, 5)
    for x, radius in ((-.55, .068), (-.37, .068), (-.21, .031)):
        round_lamp(mb, x, f - .305, b + .028, radius, 'Trim', -1)
        for k in range(13):
            a = math.radians(-130 + k * 260 / 12)
            tube(mb, (x + math.sin(a) * radius * .78, f - .33, b + .028 + math.cos(a) * radius * .78),
                 (x + math.sin(a) * radius * .89, f - .33, b + .028 + math.cos(a) * radius * .89), .0013, 'Dial', 5)
        tube(mb, (x, f - .332, b + .028), (x - radius * .56, f - .333, b + .054), .002, 'Recovery', 6)
    # radio, vent slots, rotary controls, glovebox and knee shelf
    box(mb, (.10, f - .289, b + .005), (.24, .012, .064), 'Metal', .006)
    for x in (.015, .185, .31, .43, .55):
        tube(mb, (x, f - .30, b - .035), (x, f - .321, b - .035), .013, 'Trim', 16)
    for x in (-.70, .67):
        for k in range(5):
            box(mb, (x + k * .018, f - .287, b + .025), (.009, .008, .07), 'Rubber', .002)
    # steering wheel is a separate animated node; column remains on the body
    tube(mb, (-.43, f - .24, b - .04), (-.43, f - .49, b + .13), .023, 'Chassis', 16)
    for x, height in ((0, .25), (.105, .16)):
        tube(mb, (x, f - .56, .60), (x - .02, f - .68, .60 + height), .008, 'Metal')
        box(mb, (x - .02, f - .68, .60 + height), (.039, .045, .040), 'Trim', .016, 4)
    for side in (-1, 1):
        box(mb, (side * (w - .05), f - .59, .73), (.028, .78, .36), 'Interior', .02)
        box(mb, (side * (w - .09), f - .61, .84), (.07, .28, .043), 'Trim', .012)
        tube(mb, (side * (w - .09), f - .43, .71), (side * (w - .10), f - .49, .75), .009, 'Metal')
        box(mb, (side * .43, s['topfront'] - .10, s['roof'] - .085), (.40, .16, .015), 'Seat', .012)
    box(mb, (0, s['topfront'] - .055, s['roof'] - .135), (.22, .035, .07), 'Trim', .017)
    box(mb, (0, s['topfront'] - .075, s['roof'] - .135), (.193, .004, .045), 'Chrome', .008)


def steering_wheel(mb):
    pts = [(math.cos(a) * .175, 0, math.sin(a) * .175) for a in [k * TAU / 80 for k in range(80)]]
    path(mb, pts, .014, 'Rubber', 10, True)
    for a in (math.pi / 6, math.pi * 5 / 6, -math.pi / 2):
        tube(mb, (0, 0, 0), (math.cos(a) * .164, 0, math.sin(a) * .164), .013, 'Metal')
    box(mb, (0, -.012, 0), (.08, .042, .075), 'Trim', .024, 5)


def chassis(mb, s):
    ay = s['wb'] / 2
    rail_x = .33 if s['spring'] == 'coil' else .35
    for side in (-1, 1):
        # boxed rails kicked above the axles; avoid intersecting the differential travel
        points = [(side * rail_x, s['rear'] + .10, .37), (side * rail_x, -ay - .4, .37),
                  (side * rail_x, -ay + .35, .37), (side * rail_x, -.5, .19),
                  (side * rail_x, .55, .19), (side * rail_x, ay - .32, .39),
                  (side * rail_x, s['front'] - .08, .39)]
        for p, q in zip(points, points[1:]):
            d = Vector(q) - Vector(p)
            M = Matrix.Translation((Vector(p) + Vector(q)) / 2) @ Vector((0, 1, 0)).rotation_difference(d).to_matrix().to_4x4()
            mb.add(C.xform(C.bm_box((.085, d.length + .016, .12), bev=.009, segs=3), M), mat='Chassis', shade='auto')
        # body mounts / frame bolts
        for y in (s['rear'] + .22, -.53, .35, s['front'] - .15):
            box(mb, (side * .45, y, .30), (.22, .08, .045), 'Chassis')
            tube(mb, (side * .48, y, .28), (side * .48, y, .35), .018, 'Rubber', 16)
            tube(mb, (side * .48, y, .345), (side * .48, y, .356), .012, 'Metal', 6)
        for sign in (-1, 1):
            y = sign * ay
            if s['spring'] == 'coil':
                tube(mb, (side * s['spring_x'], y, .50), (side * s['spring_x'], y, .55), .084, 'Chassis', 32)
                box(mb, (side * (s['spring_x'] + .35) / 2, y, .53), (s['spring_x'] - .35 + .12, .18, .05), 'Chassis')
            else:
                for dy in (-.53, .53):
                    box(mb, (side * s['spring_x'], y + dy, .23), (.12, .08, .14), 'Chassis')
                    tube(mb, (side * s['spring_x'] - .065, y + dy, .16),
                         (side * s['spring_x'] + .065, y + dy, .16), .012, 'Metal', 12)
            # rubber bump stops under the rail, facing the axle
            box(mb, (side * .34, y, .32), (.05, .13, .05), 'Rubber', .012)
            # upper shock eye fixed to the chassis, independent of the exposed piston
            top = s.get('shock', {}).get('top', [.245 if s['spring'] == 'coil' else .265, s['spring_top'] + .055, -.10])
            if s.get('shock'):
                # The longer inclined damper needs a real tower tied into the
                # frame rail, with two gusset plates around its upper eye.
                ty = y - top[2]
                profile = [(ty - .018, top[1] - .012), (ty - .018, top[1] + .026),
                           (ty + .05, top[1] + .026), (ty + .07, .405), (ty + .014, .405)]
                for dx in (-.026, .026):
                    bm = C.bm_extrude_poly(profile, .014, axis='X', center=side * (top[0] + dx))
                    C.bevel(bm, .003, 2)
                    mb.add(bm, mat='Chassis', shade='auto')
                box(mb, (side * (top[0] + rail_x) / 2, ty + .04, .408),
                    (rail_x - top[0] + .07, .07, .024), 'Chassis', .004)
            M = Matrix.Translation((side * top[0], y - top[2], top[1]))
            lathe(mb, [(.010, -.018), (.025, -.018), (.025, .018), (.010, .018), (.010, -.018)], mat='Chassis', M=M, segs=24)
            tube(mb, M @ Vector((-.026, 0, 0)), M @ Vector((.026, 0, 0)), .008, 'Metal', 12)
    for y, z in ((s['front'] - .13, .37), (.10, .14), (s['rear'] + .17, .35)):
        box(mb, (0, y, z), (.79, .07, .085), 'Chassis')
    # transmission and flanged transfer outputs
    box(mb, (0, 0, .14), (.30, .48, .22), 'Chassis', .038, 5)
    for sign in (-1, 1):
        tube(mb, (0, sign * .23, .05), (0, sign * .30, .05), .048, 'Metal', 24)
    tube(mb, (0, .22, .28), (0, .65, .38), .105, 'Metal', 24)
    for y in (.30, .36, .42, .48, .54):
        box(mb, (0, y, .28), (.24, .015, .17), 'Chassis', .015)
    # sump/engine: visible from the wheel wells; hollow cabin remains unobstructed
    box(mb, (0, 1.11, .605), (.42, .70, .33), 'Chassis', .065, 5)
    box(mb, (0, 1.06, .775), (.28, .59, .08), 'Metal', .027, 4)
    # protected tank inside the rails and two metal straps
    box(mb, (.59, -.56, .27), (.23, .46, .22), 'Chassis', .035, 5)
    for y in (-.70, -.42):
        box(mb, (.59, y, .155), (.26, .03, .018), 'Metal', .005)
    # routed exhaust clears the differential and rises over the rear axle
    ex_x = -.15 if s['spring'] == 'coil' else -.25
    ex = [(-.12 if s['spring'] == 'coil' else -.20, 1.23, .50), (ex_x, .83, .19), (ex_x, -.58, .18),
          (-.17, -ay + .31, .41), (-.17, -ay - .32, .41), (-.55, s['rear'] + .06, .26)]
    path(mb, ex, .025, 'Metal', 16)
    tube(mb, (ex_x, -.14, .18), (ex_x, -.55, .18), .062, 'Metal', 24)
    end = Vector(ex[-1])
    tube(mb, end, end + Vector((-.08, -.09, 0)), .029, 'Chassis', 20)
    # brake hardlines along the rails
    pipe_x = .365 if s['spring'] == 'coil' else .395
    path(mb, [(pipe_x, s['front'] - .4, .44), (pipe_x, .5, .30), (pipe_x, -.65, .30), (pipe_x, s['rear'] + .2, .44)], .0035, 'Metal', 6)


def axle(mb, s, front):
    tx = s['tx']
    tube(mb, (-tx + .10, 0, 0), (tx - .10, 0, 0), .043, 'Chassis', 24)
    sign = -1 if front else 1
    # differential carrier, pinion flange, machined cover and ten fasteners
    profile = [(0, -.115), (.09, -.11), (.138, -.07), (.150, -.01), (.138, .065), (.087, .12), (.043, .18), (0, .18)]
    lathe(mb, [(r, sign * y) for r, y in profile], axis='Y', mat='Chassis', M=Matrix.Translation((0, 0, .025)), segs=40)
    lathe(mb, [(0, -.121 * sign), (.103, -.12 * sign), (.124, -.106 * sign)], axis='Y', mat='Metal', M=Matrix.Translation((0, 0, .025)), segs=40)
    for k in range(10):
        a = TAU * k / 10
        tube(mb, (.111 * math.cos(a), -.111 * sign, .025 + .111 * math.sin(a)),
             (.111 * math.cos(a), -.124 * sign, .025 + .111 * math.sin(a)), .0065, 'Metal', 6)
    tube(mb, (0, sign * .175, .025), (0, sign * .235, .025), .047, 'Metal', 20)
    for side in (-1, 1):
        x = side * s['spring_x']
        if s['spring'] == 'coil':
            tube(mb, (x, 0, .040), (x, 0, .065), .082, 'Chassis', 32)
        else:
            box(mb, (x, 0, -.032), (.105, .16, .025), 'Chassis')
            # U-bolts clamp the steel leaf pack to the axle tube
            for yy in (-.067, .067):
                path(mb, [(x - .050, yy, -.11), (x - .050, yy, .031), (x - .035, yy, .05),
                          (x + .035, yy, .05), (x + .050, yy, .031), (x + .050, yy, -.11)], .006, 'Metal', 8)
        for y in (-.017, .017):
            tube(mb, (x, y, .026), (x, y, .08), .007, 'Metal', 8)
        tube(mb, (side * (tx - .19), 0, 0), (side * (tx - .09), 0, 0), .076, 'Metal', 24)
    if front:
        # tie rod sits inboard of the tyre steering sweep
        tube(mb, (-.39, .17, -.045), (.39, .17, -.045), .018, 'Metal', 16)
        for side in (-1, 1):
            tube(mb, (side * .39, .17, -.045), (side * (tx - .23), 0, -.035), .023, 'Chassis')
        tube(mb, (-.24, .22, -.025), (.08, .22, -.025), .028, 'Recovery', 16)
        tube(mb, (.08, .22, -.025), (.32, .22, -.025), .011, 'Chrome', 16)


def brake(mb, s, rear=False):
    """Stationary brake assembly, steers with knuckle but never spins with the tyre."""
    x = .053
    if rear:
        lathe(mb, [(0, x - .058), (.143, x - .058), (.153, x - .042), (.153, x), (0, x)], mat='Chassis', segs=48)
        for a in range(16):
            T = Matrix.Rotation(a * TAU / 16, 4, 'X')
            mb.add(C.xform(C.bm_box((.04, .007, .012), (x - .024, 0, .149), .002, 2), T), mat='Metal', shade='auto')
    else:
        lathe(mb, [(.062, x - .021), (.157, x - .021), (.161, x - .016), (.161, x), (.062, x), (.062, x - .021)], mat='Metal', segs=64)
        for i in range(32):
            a = TAU * i / 32
            tube(mb, (x - .010, .148 * math.cos(a), .148 * math.sin(a)),
                 (x - .010, .161 * math.cos(a), .161 * math.sin(a)), .002, 'Chassis', 6)
        box(mb, (x - .015, -.137, .034), (.068, .067, .15), 'Chassis', .024, 5)
        tube(mb, (x - .03, -.17, .052), (x - .03, -.16, .079), .007, 'Metal', 8)


def coil(mb):
    # normalized height, constant diameter; piston is an independent rigid component
    pts = []
    for i in range(257):
        t = i / 256
        a = t * TAU * 8
        pts.append((.065 * math.cos(a), .065 * math.sin(a), .045 + t * .91))
    path(mb, pts, .009, 'Chassis', 8)


def shock(mb, rod=False, length=.226):
    if rod:
        # Only the exposed piston is drawn. The barrel retains its physical length.
        tube(mb, (0, 0, -1), (0, 0, 0), .010, 'Chrome', 20)
        return
    else:
        tube(mb, (0, 0, .015), (0, 0, length - .001), .028, 'Recovery', 24)
        tube(mb, (0, 0, length - .012), (0, 0, length + .011), .030, 'Chassis', 24)
        tube(mb, (0, 0, .010), (0, 0, .035), .029, 'Metal', 24)
    # mounting eye, sleeve and rubber bushing
    lathe(mb, [(.009, -.021), (.024, -.021), (.024, .021), (.009, .021), (.009, -.021)], mat='Chassis', segs=24)
    tube(mb, (-.026, 0, 0), (.026, 0, 0), .008, 'Metal', 12)


def leaf(mb):
    """Five curved steel strips with fixed eyes. Exported Bump/Droop shape keys
    displace their centres with the axle and preserve the pack's strip thickness.
    """
    for layer in range(5):
        half = .53 - layer * .066
        verts, faces = [], []
        for i in range(49):
            y = -half + 2 * half * i / 48
            z = -.07 + .23 * (y / .53) ** 2
            for x, dz in ((-.035, 0), (.035, 0), (.035, -.008), (-.035, -.008)):
                verts.append((x, y, z + dz - layer * .008))
            if i:
                for j in range(4):
                    a = (i - 1) * 4 + j
                    b = (i - 1) * 4 + (j + 1) % 4
                    faces.append([a, b, b + 4, a + 4])
        bm = C.bm_from(verts, faces)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        mb.add(bm, mat='Chassis', shade='auto')


def bumper(mb, s, winch=False):
    f, w = s['front'], s['width']
    box(mb, (0, f + .085, .295), (w * 2 + .035, .16, .14), 'Chassis' if winch else 'Chrome', .025, 5)
    for side in (-1, 1):
        box(mb, (side * (w - .01), f + .046, .295), (.14, .19, .16), 'Trim', .026, 4)
        for x in (.34, .69):
            tube(mb, (side * x, f + .163, .30), (side * x, f + .168, .30), .007, 'Metal', 6)
        # forged tow shackles with separate pin
        pts = [(side * .56 + .031 * math.cos(a), f + .169, .248 + .038 * math.sin(a)) for a in [k * TAU / 28 for k in range(28)]]
        path(mb, pts, .008, 'Recovery', 8, True)
        tube(mb, (side * .56 - .042, f + .17, .277), (side * .56 + .042, f + .17, .277), .009, 'Metal')
    if winch:
        box(mb, (0, f + .06, .39), (.57, .21, .045), 'Chassis')
        tube(mb, (-.19, f + .055, .452), (.19, f + .055, .452), .058, 'Metal', 32)
        for k in range(23):
            x = -.17 + k * .015
            lathe(mb, [(.058 + .003 * math.cos(a), x + .003 * math.sin(a)) for a in [j * TAU / 8 for j in range(9)]], mat='Chassis',
                  M=Matrix.Translation((0, f + .055, .452)), segs=28)
        for x in (-.225, .225):
            box(mb, (x, f + .055, .447), (.085, .18, .14), 'Chassis', .016, 4)
        box(mb, (0, f + .185, .324), (.25, .028, .077), 'Chrome', .022, 4)
        box(mb, (0, f + .202, .324), (.19, .007, .030), 'Trim', .014, 4)
        path(mb, [(0, f + .213, .324), (0, f + .23, .278), (.03, f + .23, .257)], .008, 'Metal', 10)
    # legible front registration plate on the bumper
    box(mb, (-.25 if winch else 0, f + .174, .289), (.27, .006, .077), 'Decal', .007)
    text(mb, 'FT  090' if s['spring'] == 'coil' else 'FT  060' if s['wb'] < 2.79 else 'FT  079',
         (-.25 if winch else 0, f + .179, .272), .034, mat='Trim')


def rack(mb, s):
    # slim expedition basket, restrained load so the reference silhouette stays legible
    y0, y1, z = s['cabrear'] + .10, s['topfront'] - .07, s['roof'] + .14
    for side in (-1, 1):
        for y in (y0 + .1, (y0 + y1) / 2, y1 - .12):
            path(mb, [(side * .81, y, s['roof']), (side * .76, y, z), (side * .64, y, z)], .012, 'Chassis', 10)
    for zz in (z, z + .095):
        path(mb, rounded_loop([(-.76, y0, zz), (.76, y0, zz), (.76, y1, zz), (-.76, y1, zz)], .12), .014, 'Chassis', 12, True)
    for i in range(10):
        y = y0 + .04 + (y1 - y0 - .08) * i / 9
        tube(mb, (-.75, y, z), (.75, y, z), .009, 'Metal', 10)
    for x in (-.76, .76):
        for i in range(6):
            y = y0 + .1 + (y1 - y0 - .2) * i / 5
            tube(mb, (x, y, z), (x, y, z + .095), .008, 'Chassis', 10)
    cargo(mb, (-.23, y0 + .52, z + .02), (.57, .63, .18))
    # folded blanket roll, woven seams and two tie-down straps
    tube(mb, (.20, y0 + .32, z + .12), (.20, y0 + .85, z + .12), .11, 'Canvas', 32)
    for y in (y0 + .38, y0 + .76):
        lathe(mb, [(.113, -.014), (.113, .014)], axis='Y', mat='Trim', M=Matrix.Translation((.20, y, z + .12)), segs=32)
    for x in (-.41, .37):
        path(mb, [(x, y0 + .1, z), (x, y0 + .16, z + .27), (x, y0 + .90, z + .27), (x, y0 + 1.02, z)], .009, 'Trim', 8)


def cargo(mb, loc, size):
    x, y, z = loc
    sx, sy, sz = size
    box(mb, (x, y, z + sz / 2), size, 'Cargo', .045, 5)
    box(mb, (x, y, z + sz), (sx + .012, sy + .012, .045), 'Cargo', .014, 4)
    for xx in (-sx * .38, sx * .38):
        for yy in (-sy * .38, sy * .38):
            box(mb, (x + xx, y + yy, z + sz + .008), (.036, .065, .018), 'Trim', .004)
    for xx in (-sx * .26, sx * .26):
        path(mb, [(x + xx, y - sy / 2 - .005, z + .03), (x + xx, y - sy / 2 - .005, z + sz + .026),
                  (x + xx, y + sy / 2 + .005, z + sz + .026), (x + xx, y + sy / 2 + .005, z + .03)], .008, 'Trim', 8)


def rear_body(mb, s):
    rear, w, b = s['rear'], s['width'], s['belt']
    box(mb, (0, rear, (.30 + b) / 2), (w * 2 - .025, .05, b - .30), 'Paint', .028, 5)
    box(mb, (0, rear - .07, .275), (w * 2 + .015, .15, .135), 'Chrome', .023, 4)
    box(mb, (0, rear - .154, .275), (.30, .006, .087), 'Decal', .005)
    text(mb, 'FOREST TRAIL', (0, rear - .159, .251), .031, 'rear', 'Trim')
    box(mb, (0, rear - .17, .17), (.07, .16, .065), 'Chassis', .009)
    tube(mb, (-.09, rear - .21, .17), (.09, rear - .21, .17), .013, 'Metal', 12)
    for side in (-1, 1):
        for yy in (s['wb'] / 2, -s['wb'] / 2):
            # mud flaps behind each tyre, with a stamped mounting strip and rivets
            y = yy - s['r'] - .17
            box(mb, (side * (s['width'] - .09), y, .13), (.22, .016, .22), 'Rubber', .010, 3)
            box(mb, (side * (s['width'] - .09), y - .009, .228), (.22, .008, .028), 'Metal', .003)
            for dx in (-.075, .075):
                tube(mb, (side * (s['width'] - .09) + dx, y - .011, .228),
                     (side * (s['width'] - .09) + dx, y - .017, .228), .005, 'Chassis', 6)


def build_defender(body, glass, s):
    ay, f, rear, w = s['wb'] / 2, s['front'], s['rear'], s['width']
    side_shell(body, s, rear, f, s['belt'], [-ay, ay])
    hood(body, s, True)
    cabin(body, glass, s, [(-.54, .39, -.54, .23), (-1.63, -.63, -1.59, -.63)], True)
    # recessed centre grille and separate flat fender headlamp wings
    box(body, (0, f - .002, .666), (1.02, .075, .43), 'Trim', .017)
    for i in range(10):
        box(body, (0, f + .042, .482 + i * .034), (.92, .018, .012), 'Chassis', .003)
    for x in (-.30, 0, .30):
        box(body, (x, f + .048, .655), (.011, .012, .355), 'Trim', .002)
    for side in (-1, 1):
        box(body, (side * .698, f - .002, .658), (.35, .078, .438), 'Paint', .017, 4)
        round_lamp(body, side * .692, f + .046, .694, .091)
        round_lamp(body, side * .809, f + .044, .477, .028, 'LampAmber')
        round_lamp(body, side * .576, f + .044, .477, .028, 'Lamp')
        for yy in (.92, 1.48):
            box(body, (side * .76, yy, s['belt'] + .034), (.15, .33, .012), 'Chassis', .008)
            for j in range(7):
                box(body, (side * .76, yy - .125 + j * .04, s['belt'] + .042), (.125, .008, .004), 'Metal', .001)
        door_details(body, s, -.56, .40, side, True)
        # riveted aluminum quarter panels and body capping
        tube(body, (side * .907, rear + .03, .947), (side * .907, .40, .947), .008, 'Metal', 10)
        for yy in [rear + .06 + i * .11 for i in range(12)]:
            tube(body, (side * .899, yy, .918), (side * .906, yy, .918), .0034, 'Metal', 6)
        # fuel filler on the right rear quarter
        if side == 1:
            box(body, (.903, -1.51, .79), (.015, .17, .14), 'Trim', .012)
            tube(body, (.912, -1.51, .79), (.930, -1.51, .79), .043, 'Chassis', 32)
        box(body, (side * .93, -.05, .205), (.16, .86, .045), 'Chassis', .015)
    box(body, (0, f + .040, .843), (.22, .020, .079), 'Badge', .030, 5)
    text(body, 'LAND ROVER', (0, f + .052, .829), .023, mat='Decal')
    text(body, 'DEFENDER', (0, f + .010, .926), .052, mat='Chrome')
    # rear door framing, hinges, spare carrier and signature round lamps
    rear_body(body, s)
    for side in (-1, 1):
        for zz, mat in ((.72, 'LampAmber'), (.57, 'LampRear'), (.39, 'LampReverse')):
            round_lamp(body, side * .77, rear - .04, zz, .034, mat, -1)
    path(body, [(-.66, rear - .028, .32), (-.66, rear - .028, 1.46), (.66, rear - .028, 1.46), (.66, rear - .028, .32)], .004, 'Trim', 8)
    wheel(body, s, Matrix.Translation((.13, rear - .20, .75)) @ Matrix.Rotation(-math.pi / 2, 4, 'Z'))
    bumper(body, s, True)
    rack(body, s)


def build_fj60(body, glass, s):
    ay, f, rear, w = s['wb'] / 2, s['front'], s['rear'], s['width']
    side_shell(body, s, rear, f, s['belt'], [-ay, ay])
    hood(body, s)
    cabin(body, glass, s, [(-.28, .59, -.28, .28), (-1.17, -.38, -1.17, -.38), (-2.17, -1.28, -2.12, -1.28)])
    # FJ60: broad grille with round headlights, horizontal louvres, wraparound corners
    box(body, (0, f - .013, .65), (1.74, .07, .405), 'Paint', .042, 5)
    box(body, (0, f + .029, .651), (1.565, .018, .306), 'Trim', .025, 4)
    for i in range(6):
        box(body, (0, f + .045, .528 + i * .047), (1.03, .020, .017), 'Chrome', .004)
    for x in (-.40, -.2, 0, .2, .4):
        box(body, (x, f + .05, .652), (.008, .012, .248), 'Chassis', .002)
    for side in (-1, 1):
        round_lamp(body, side * .650, f + .057, .657, .100)
        box(body, (side * .853, f + .025, .643), (.060, .040, .182), 'LampAmber', .014, 4)
        box(body, (side * .685, f + .031, .404), (.16, .025, .064), 'LampAmber', .007)
        # cowl side vent, door seams and wide, very subtle lower protective moulding
        for j in range(7):
            box(body, (side * .902, .735 + j * .025, .831), (.007, .012, .051), 'Trim', .003)
        door_details(body, s, -.30, .60, side)
        door_details(body, s, -1.20, -.33, side)
        box(body, (side * .902, -.08, .482), (.012, 1.22, .040), 'Trim', .006)
        path(body, [(side * .902, rear + .06, .858), (side * .904, .63, .858)], .004, 'Chrome', 8)
        text(body, 'LAND CRUISER', (side * .907, 1.00, .778), .036, 'right' if side > 0 else 'left')
        box(body, (side * .901, -1.96, .76), (.007, .21, .15), 'Trim', .016)
        box(body, (side * .905, -1.96, .76), (.009, .195, .135), 'Paint', .014)
    box(body, (0, f + .070, .665), (.40, .017, .094), 'Trim', .006)
    text(body, 'TOYOTA', (0, f + .081, .638), .068, mat='Decal')
    rear_body(body, s)
    # horizontal split tailgate, recessed number plate, rear wiper, vertical rear lamps
    path(body, [(-.70, rear - .029, .56), (.70, rear - .029, .56)], .0035, 'Trim')
    box(body, (0, rear - .032, .765), (.23, .028, .044), 'Chrome', .009)
    text(body, 'TOYOTA', (-.48, rear - .036, .707), .051, 'rear')
    text(body, '4WD', (.58, rear - .036, .707), .044, 'rear')
    for side in (-1, 1):
        for z, h, mat in ((.742, .106, 'LampAmber'), (.612, .13, 'LampRear'), (.49, .079, 'LampReverse')):
            rect_lamp(body, (side * .791, rear - .031, z), (.124, .02, h), mat)
    # snorkel follows A pillar and does not replace the body silhouette
    path(body, [(.935, 1.08, .80), (.978, .92, .87), (.976, .66, 1.00), (.889, .33, 1.57)], .036, 'Trim', 20)
    box(body, (.89, .32, 1.60), (.105, .15, .071), 'Trim', .023, 5)
    for j in range(5):
        box(body, (.89, .395, 1.578 + j * .009), (.072, .004, .003), 'Chassis', .001)
    bumper(body, s, True)
    rack(body, s)


def build_hilux(body, glass, s):
    ay, f, rear, w = s['wb'] / 2, s['front'], s['rear'], s['width']
    side_shell(body, s, s['cabrear'], f, s['belt'], [ay])
    hood(body, s)
    cabin(body, glass, s, [(-.355, .673, -.32, .418)])
    # separate pressed-steel cabin rear bulkhead and large rear window
    box(body, (0, s['cabrear'] + .01, .65), (1.63, .04, .39), 'Paint', .02)
    for side in (-1, 1):
        door_details(body, s, -.38, .68, side)
        text(body, 'HILUX 4WD', (side * .847, 1.03, .754), .040, 'right' if side > 0 else 'left')
        # triangular front vent window division and bright belt trim
        tube(body, (side * .812, .40, .867), (side * .776, .32, 1.33), .009, 'Chrome')
        box(body, (side * .846, .07, .788), (.012, 1.10, .018), 'Chrome', .005)
    # early Hilux upright grille and round lamps in rectangular chrome bezels
    box(body, (0, f, .635), (1.61, .08, .38), 'Paint', .031, 5)
    box(body, (0, f + .043, .633), (1.48, .028, .305), 'Chrome', .015)
    box(body, (0, f + .060, .633), (1.43, .018, .264), 'Trim', .009)
    for i in range(5):
        box(body, (0, f + .074, .533 + i * .046), (.96, .014, .012), 'Chrome', .003)
    for side in (-1, 1):
        round_lamp(body, side * .605, f + .075, .643, .093)
        box(body, (side * .61, f + .048, .416), (.163, .027, .06), 'LampAmber', .008)
    box(body, (0, f + .091, .642), (.32, .015, .073), 'Trim', .004)
    text(body, 'TOYOTA', (0, f + .101, .620), .055, mat='Decal')
    bumper(body, s)
    # separated cargo tub: hollow floor, inner wheel tubs and longitudinal bed ribs
    bedfront, rail, floor = -.53, .842, .59
    side_shell(body, s, rear, bedfront, rail, [-ay], bottom=.24)
    box(body, (0, (rear + bedfront) / 2, floor), (1.04, bedfront - rear, .035), 'Paint', .01)
    for xx in (-.42, -.28, -.14, 0, .14, .28, .42):
        box(body, (xx, (rear + bedfront) / 2, floor + .022), (.042, bedfront - rear - .04, .012), 'Paint', .006)
    for side in (-1, 1):
        tube(body, (side * w, rear, rail), (side * w, bedfront, rail), .026, 'Paint', 16)
        for yy in (-.69, -1.18, -1.85, -2.32):
            path(body, [(side * (w + .015), yy - .03, .80), (side * (w + .055), yy, .77),
                       (side * (w + .015), yy + .03, .80)], .006, 'Metal', 8)
        # smooth rolled inner tub housing
        rr = s['r'] + .15
        amin = math.asin((floor - .17) / rr)
        pts = [(-ay + rr * math.cos(amin + i * (math.pi - 2 * amin) / 40),
                .17 + rr * math.sin(amin + i * (math.pi - 2 * amin) / 40)) for i in range(41)]
        mb = C.bm_extrude_poly(pts, .028, axis='X', center=side * .53)
        body.add(mb, mat='Paint', shade='auto')
        for y0, y1 in ((rear, -ay - rr), (-ay + rr, bedfront)):
            box(body, (side * .68, (y0 + y1) / 2, floor), (.32, abs(y1 - y0), .03), 'Paint', .006)
        # stamped long recesses in the outer bed sides
        for yy in (-.77, -2.17):
            path(body, rounded_loop([(side * .846, yy - .12, .32), (side * .846, yy + .12, .32),
                                     (side * .846, yy + .12, .69), (side * .846, yy - .12, .69)], .055), .004, 'PaintAccent', 8, True)
    box(body, (0, bedfront, .64), (1.66, .033, .40), 'Paint', .017)
    rear_body(body, s)
    # pressed tailgate inset, stamped Toyota lettering and external hinges
    box(body, (0, rear - .029, .59), (1.32, .012, .31), 'PaintAccent', .026)
    box(body, (0, rear - .041, .59), (1.29, .015, .284), 'Paint', .019)
    text(body, 'T O Y O T A', (0, rear - .052, .555), .117, 'rear', 'Decal')
    for x in (-.56, .56):
        tube(body, (x - .065, rear - .039, .367), (x + .065, rear - .039, .367), .013, 'Metal')
    for side in (-1, 1):
        for z, h, mat in ((.740, .083, 'LampAmber'), (.616, .126, 'LampRear'), (.499, .065, 'LampReverse')):
            rect_lamp(body, (side * .766, rear - .041, z), (.089, .018, h), mat)
    # factory-style load guard, with fine vertical bars behind the rear window
    path(body, [(-.70, -.60, rail), (-.70, -.60, 1.36), (-.64, -.60, 1.41),
               (.64, -.60, 1.41), (.70, -.60, 1.36), (.70, -.60, rail)], .019, 'Chrome', 16)
    for x in (-.45, -.15, .15, .45):
        tube(body, (x, -.60, rail), (x, -.60, 1.40), .008, 'Metal')
    cargo(body, (-.26, -.92, floor + .025), (.46, .45, .26))
    wheel(body, s, Matrix.Translation((.24, -1.66, floor + s['tw'] / 2 + .04)) @ Matrix.Rotation(-math.pi / 2, 4, 'Y'))
    # two planks, towing rope, small folded canvas roll
    box(body, (-.63, -1.62, .75), (.15, 1.55, .045), 'Cargo', .009, 3, (0, .05, .03))
    for k in range(4):
        path(body, [(.22 + .17 * math.cos(a), -1.66 + .17 * math.sin(a), .96 + k * .014)
                    for a in [i * TAU / 48 for i in range(48)]], .007, 'Canvas', 8, True)


def morph_spring(obj, s):
    obj.shape_key_add(name='Basis')
    for name, travel in (('Bump', .25), ('Droop', -.20)):
        key = obj.shape_key_add(name=name)
        for v in key.data:
            if s['spring'] == 'leaf':
                v.co.z += travel * (1 - (v.co.y / .53) ** 2)
            else:
                # move the lower end, keep the upper seat fixed and wire gauge constant
                t = min(1, max(0, v.co.z / (s['spring_top'] - s['spring_seat'])))
                v.co.z += travel * (1 - t)


def assemble(parts, col, dims, pose=None):
    """Blender counterpart of VehicleView. Rig, previews and clearance share mounts."""
    s = dict(SPECS[dims['id']], tx=dims['track_x'], wb=dims['wheelbase'])
    shock = dims.get('shock', {})
    pose = pose or {}
    objs, ys = [], []
    def inst(name, pos=(0, 0, 0), rot=None, scale=(1, 1, 1), morph=0):
        src = parts.get(name)
        if src is None:
            return None
        data = src.data.copy() if name == 'Spring' else src.data
        o = bpy.data.objects.new(name + '_asm', data)
        col.objects.link(o)
        o.location, o.scale = pos, scale
        if rot is not None:
            o.rotation_mode = 'QUATERNION'
            o.rotation_quaternion = rot
        if name == 'Spring' and data.shape_keys:
            data.shape_keys.key_blocks['Bump'].value = max(0, morph / .25)
            data.shape_keys.key_blocks['Droop'].value = max(0, -morph / .20)
        objs.append(o)
        return o
    inst('Body')
    inst('Glazing')
    inst('SteeringWheel', (-.43, s['cowl'] - .49, s['belt'] + .13))
    for i, k in enumerate(('FL', 'FR', 'RL', 'RR')):
        dz, steer = pose.get(k, (0, 0))
        ys.append(dz)
        side, sy = (-1 if i % 2 == 0 else 1), (1 if i < 2 else -1)
        lk, rk = ('FL', 'FR') if i < 2 else ('RL', 'RR')
        roll = math.asin((pose.get(rk, (0, 0))[0] - pose.get(lk, (0, 0))[0]) / (2 * s['tx']))
        q = (Matrix.Rotation(-roll, 4, 'Y') @ Matrix.Rotation(math.radians(-steer) + (math.pi if side < 0 else 0), 4, 'Z')).to_quaternion()
        inst('Wheel', (side * s['tx'] * math.cos(roll), sy * s['wb'] / 2, dz), q)
        inst('BrakeFront' if i < 2 else 'BrakeRear', (side * s['tx'] * math.cos(roll), sy * s['wb'] / 2, dz), q)
    for a in range(2):
        sy = 1 if a == 0 else -1
        y = sy * s['wb'] / 2
        zl, zr = ys[a * 2:a * 2 + 2]
        roll = math.asin((zr - zl) / (s['tx'] * 2))
        inst('AxleFront' if a == 0 else 'AxleRear', (0, y, (zl + zr) / 2), Matrix.Rotation(-roll, 4, 'Y').to_quaternion())
        for side in (-1, 1):
            x = side * s['spring_x']
            az = (zl + zr) / 2 + (zr - zl) * x / (2 * s['tx'])
            inst('Spring', (x, y, s['spring_seat'] if s['spring'] == 'coil' else 0), morph=az)
            bottom = shock.get('bottom', [.25 if s['spring'] == 'coil' else .28, .035, .09])
            upper = shock.get('top', [.245 if s['spring'] == 'coil' else .265, s['spring_top'] + .055, -.10])
            bx = bottom[0]
            shock_z = (zl + zr) / 2 + (zr - zl) * side * bx / (2 * s['tx'])
            bot = Vector((side * bx, y - bottom[2], shock_z + bottom[1]))
            top = Vector((side * upper[0], y - upper[2], upper[1]))
            q = Vector((0, 0, 1)).rotation_difference(top - bot)
            inst('ShockBody', bot, q)
            inst('ShockRod', top, q, (1, 1, max(.02, (top - bot).length - shock.get('barrelLength', .226))))
        p = Vector((0, sy * .30, .05))
        q = Vector((0, sy * (s['wb'] / 2 - .235), (zl + zr) / 2 + .025))
        inst('Driveshaft', p, Vector((0, 1, 0)).rotation_difference(q - p), (1, (q - p).length, 1))
    return objs


def preview(parts, col, dims, vid):
    C.setup_render((1600, 1000), '#B7C5CF', .65, 64)
    sc = bpy.context.scene
    C.add_sun((38, -18, 132), 2.4, 14)
    for name, loc, energy, size in [('Key', (3, 4, 6), 1700, 5), ('RimLight', (-4, -3, 4), 2100, 4), ('Fill', (1, -4, 3), 950, 5)]:
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.shape, data.size = energy, 'DISK', size
        ob = bpy.data.objects.new(name, data)
        sc.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector((0, 0, .7)) - ob.location).to_track_quat('-Z', 'Y').to_euler()
    ground = C.add_ground(-dims['R'], color='#7A858B')
    col.hide_render = True
    asm = C.collection('Assembled vehicle')
    objects = assemble(parts, asm, dims)
    for shot, az, el in [('front34', 44, 13), ('rear34', -138, 15), ('side', 90, 2), ('front', 0, 5), ('underside', 38, -25)]:
        ground.hide_render = shot == 'underside'
        C.frame_camera(objects, az=az, el=el, lens=60, margin=.065)
        C.render(vid + '_' + shot + '.png')
    ground.hide_render = True
    asm.hide_render = True
    flexcol = C.collection('Articulation')
    poses = {'FL': (dims['bump'], dims['lock']), 'FR': (-dims['droop'], dims['lock'] * .78),
             'RL': (-dims['droop'], 0), 'RR': (dims['bump'], 0)}
    flex = assemble(parts, flexcol, dims, poses)
    C.frame_camera(flex, az=35, el=3, lens=58)
    C.render(vid + '_flex.png')
    flexcol.hide_render = True
    flexcol.hide_viewport = True
    lockcol = C.collection('Steering clearance')
    lockpose = {'FL': (dims['bump'], dims['lock']), 'FR': (dims['bump'], dims['lock'] * .78)}
    locked = assemble(parts, lockcol, dims, lockpose)
    for shot, az, el in [('lock_top', 0, 86), ('lock_front', 16, 4)]:
        C.frame_camera(locked, az=az, el=el, lens=65)
        C.render(vid + '_' + shot + '.png')
    lockcol.hide_render = True
    lockcol.hide_viewport = True
    asm.hide_render = False
    col.hide_viewport = True
    ground.hide_render = False
    C.frame_camera(objects, az=44, el=13, lens=60)


def main(vid):
    C.reset_scene()
    s = SPECS[vid]
    mats, parts, tris = materials(s), {}, {}
    col = C.collection('Export parts — origin at axle midpoint')
    body, glazing = C.MeshBuilder('Body'), C.MeshBuilder('Glazing')
    {'scout': build_defender, 'toyota': build_fj60, 'ranger': build_hilux}[vid](body, glazing, s)
    interior(body, s)
    chassis(body, s)
    def spring(mb):
        if s['spring'] == 'leaf':
            leaf(mb)
        else:
            coil(mb)
            # normalized coil -> physical height before adding morphs
            h = s['spring_top'] - s['spring_seat']
            for v in mb.V:
                v.z *= h
    builders = {'Wheel': lambda mb: wheel(mb, s), 'AxleFront': lambda mb: axle(mb, s, True),
                'AxleRear': lambda mb: axle(mb, s, False), 'Spring': spring,
                'ShockBody': shock, 'ShockRod': lambda mb: shock(mb, True),
                'BrakeFront': lambda mb: brake(mb, s), 'BrakeRear': lambda mb: brake(mb, s, True),
                'Driveshaft': P.add_driveshaft, 'SteeringWheel': steering_wheel}
    mbs = {'Body': body, 'Glazing': glazing}
    for name, fn in builders.items():
        mb = C.MeshBuilder(name)
        fn(mb)
        mbs[name] = mb
    for name, mb in mbs.items():
        tris[name] = mb.tris()
        parts[name] = mb.build(mats, vcolor=False, collection_obj=col)
    morph_spring(parts['Spring'], s)
    # High silhouette quality near the camera; reduced meshes for distant viewpoints.
    for name, ratio in (('Body', .36), ('Wheel', .28)):
        src = parts[name]
        o = bpy.data.objects.new(name + '_LOD1', src.data.copy())
        col.objects.link(o)
        mod = o.modifiers.new('Distance LOD', 'DECIMATE')
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=mod.name)
        tris[o.name] = sum(len(p.vertices) - 2 for p in o.data.polygons)
        parts[o.name] = o
    bpy.context.view_layer.update()
    C.export_glb(list(parts.values()), 'vehicle_' + vid + '.glb', vcolor=False, morph=True)
    mn, mx = C.world_bbox([parts['Body']])
    dims = dict(id=vid, fidelity=3, R=s['r'], W=s['tw'], wheelbase=s['wb'], track_x=s['tx'],
                spring_x=s['spring_x'], spring_top=s['spring_top'], spring_seat=s['spring_seat'],
                pinion_y=.235, pinion_z=.025, tcase_y=.30, tcase_z=.05,
                bump=s['bump'], droop=s['droop'], lock=s['lock'])
    head_x, head_z = {'scout': (.692, .694), 'toyota': (.650, .657), 'ranger': (.605, .643)}[vid]
    lamps = {
        'head': [(x, s['front'] + .08, head_z) for x in (-head_x, head_x)],
        'tail': [(x, s['rear'] - .07, .615) for x in (-.78, .78)],
        'brake': [(x, s['rear'] - .07, .615) for x in (-.78, .78)],
        'reverse': [(x, s['rear'] - .07, .49) for x in (-.78, .78)],
        'winch': [(0, s['front'] + .215, .324)], 'hitch': [(0, s['rear'] - .21, .17)],
    }
    info = dict(id=vid, fidelity=3, reference=s['reference'],
                note='Original reference-led expedition model; game coordinates +Y up, front -Z. See docs/VEHICLE-FIDELITY.md.',
                wheelBase=s['wb'], trackX=s['tx'], wheelRadius=s['r'], wheelWidth=s['tw'],
                spring=dict(x=s['spring_x'], top=s['spring_top'], seat=s['spring_seat'], kind=s['spring'],
                            morphBump=.25, morphDroop=.20, leafHalf=.53, leafEyeY=.16),
                shock=dict(bottom=[.25 if s['spring'] == 'coil' else .28, .035, .09],
                           top=[.245 if s['spring'] == 'coil' else .265, s['spring_top'] + .055, -.10]),
                steeringWheel=P.g((-.43, s['cowl'] - .49, s['belt'] + .13)),
                driveshaft=dict(tcaseZ=.30, tcaseY=.05, pinionZ=.235, pinionY=.025),
                lamps={k: [P.g(p) for p in v] for k, v in lamps.items()}, tris=tris,
                bodyBox=dict(min=P.g((mn.x, mx.y, mn.z)), max=P.g((mx.x, mn.y, mx.z))),
                lod=dict(near=18, far=23))
    with open(os.path.join(C.MODELS, 'vehicle_' + vid + '.json'), 'w') as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
    print('FIDELITY', vid, json.dumps(tris), flush=True)
    with open(os.path.join(C.ART, 'vehicle-' + vid + '-rig.json'), 'w') as f:
        json.dump(dims, f, indent=2)
    if '--no-preview' not in sys.argv:
        preview(parts, col, dims, vid)
    else:
        col.hide_render = True
        assemble(parts, C.collection('Assembled vehicle'), dims)
    C.save_blend('vehicle_' + vid + '.blend')
    return tris


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    for vid in [x for x in args if x in SPECS] or list(SPECS):
        main(vid)
