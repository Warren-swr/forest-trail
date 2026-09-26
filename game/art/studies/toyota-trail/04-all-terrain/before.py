"""Toyota style study: refine the V2 silhouette, not the rejected dense body.

V2 body proportions, chunky tyres/flares, dark glazing and expedition equipment
are the starting point. FJ60 references guide the front, greenhouse and seams.
Only this candidate is exported; the other vehicles and earlier assets are kept.
"""
import bpy, bmesh, math, os, sys, json, importlib.util
from datetime import datetime, timezone
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import vehicle_parts as P
import vehicle_fidelity as F

MODULE = importlib.util.spec_from_file_location('toyota_v2', os.path.join(C.HERE, 'reference', 'vehicle_toyota_v2.py'))
L = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(L)

MODEL = 'vehicle_toyota_trail'
REVISION = '03-flat-glazing'
STUDY = os.path.join(C.ART, 'studies', 'toyota-trail', REVISION,
                     'build-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
COWL, HEADER = .74, .51
NOSE_SCALE = .97
WB, TX, R, W = L.WHEELBASE, L.TRACK_X, L.TYRE_R, L.TYRE_W
FRONT, REAR, BELT, ROOF = L.FRONT_Y, L.REAR_Y, L.BELT_Z, L.ROOF_Z
S = dict(F.SPECS['toyota'], front=FRONT, rear=REAR, belt=BELT, roof=ROOF,
         cowl=COWL, topfront=HEADER, cabrear=-2.08)
DIMS = dict(id='toyota', fidelity=3, R=R, W=W, wheelbase=WB, track_x=TX,
            spring_x=S['spring_x'], spring_top=S['spring_top'], spring_seat=S['spring_seat'],
            pinion_y=.235, pinion_z=.025, tcase_y=.30, tcase_z=.05,
            bump=.25, droop=.13, lock=35.3)


def materials():
    mats = F.materials(S)
    # Matte painted steel and a closed, dark greenhouse match the forest's large
    # colour blocks. Avoid a clearcoat lobe and transparent double-pane sorting.
    for name, color, rough, metal in (
        ('Paint', '#8E8872', .56, 0), ('PaintAccent', '#B8B097', .60, 0),
        ('Trim', '#272D29', .76, .02), ('Rubber', '#20231F', .91, 0),
        ('Glass', '#203437', .25, .22), ('Chrome', '#ABB0A7', .34, .66),
        ('Metal', '#7B837A', .47, .60), ('Rim', '#89917D', .56, .36),
        ('Interior', '#393D34', .88, 0),
        ('Tire', '#272923', .94, 0), ('Lamp', '#D2D7C8', .27, .14),
        ('LampAux', '#D4D5BD', .29, .08), ('Board', '#C78236', .81, 0),
        ('PanelGap', '#45483B', .88, 0),
    ):
        if name in mats:
            bpy.data.materials.remove(mats[name])
        mats[name] = C.mat_pbr(name, color, rough, metal)
    return mats


def refined_wheel(mb, M=Matrix(), R=R, W=W, **unused):
    # Keep V2's deep chevrons and broad steel rim. Higher circular resolution
    # smooths the silhouette without turning the tread into thin visual noise.
    tmp = C.MeshBuilder('V2 tyre and hub')
    P.add_wheel(tmp, segs=32, lugs=22, style='steel', sidewall_lugs=16)
    # Replace only the old solid rim and painted ventilation dots with a pressed
    # steel dish. Keep V2's tyre, hub and hexagonal lug nuts unchanged in character.
    scale = Matrix.Diagonal((W / .30, R / .38, R / .38, 1))
    transform = M @ scale
    start = len(mb.V)
    mb.V.extend(transform @ v for v in tmp.V)
    normal_matrix = transform.to_3x3().inverted().transposed()
    for face, mat, colors, normals in zip(tmp.F, tmp.FM, tmp.LC, tmp.LN):
        dot = mat == 'Tire' and all(abs(tmp.V[i].x - .0752) < .00001 for i in face)
        if mat == 'Rim' or dot:
            continue
        mb.F.append([start + i for i in face]); mb.FM.append(mat)
        mb.LC.append(colors); mb.LN.append([(normal_matrix @ n).normalized() for n in normals])
    dish = C.bm_lathe([(.057, .107), (.106, .088), (.136, .078), (.200, .078),
                       (.225, .117), (.235, .125), (.235, .111), (.225, .103),
                       (.200, .064), (.136, .064), (.106, .074), (.057, .093), (.057, .107)], 32, axis='X')
    bmesh.ops.recalc_face_normals(dish, faces=dish.faces)
    cuts = []
    for k in range(6):
        a = (k + .5) * math.tau / 6
        y, z = .169 * math.cos(a), .169 * math.sin(a)
        cuts.append(C.bm_cyl_between((.03, y, z), (.15, y, z), .026, segs=16))
    dish = P.bm_boolean(dish, cuts)
    C.bevel(dish, .0025, 2)
    mb.add(C.xform(dish, transform), mat='Rim', shade='auto', angle=42)
    rim = C.bm_lathe([(.245, -.126), (.237, -.13), (.223, -.12), (.223, .101),
                      (.242, .123), (.25, .129), (.248, .140), (.239, .141), (.230, .127)], 32, axis='X')
    C.orient(rim, lambda f: Vector((.4, f.calc_center_median().y, f.calc_center_median().z)))
    mb.add(C.xform(rim, transform), mat='Rim', shade='auto', angle=40)
    for side in (-1, 1):
        ring = C.bm_lathe([(.271, side * .149), (.274, side * .151), (.278, side * .149)], 32, axis='X')
        C.orient(ring, lambda f: (side, 0, 0))
        mb.add(C.xform(ring, M @ scale), mat='Tire', shade='smooth')
    # Valve and hub indexing add a few readable details instead of embossed text.
    mb.add(C.xform(C.bm_cyl_between((.126, .20, .04), (.150, .20, .05), .005, segs=8), M @ scale), mat='Rubber', shade='auto')


# The retained V2 spare now matches the four road wheels.
L.add_wheel = refined_wheel


def arch(yc, r=L.ARCH_R, zc=L.ARCH_ZC, zr=.30, zf=.36, steps=28):
    return L.arch_poly(yc, r, zc, zr, zf, steps)


def nose_x(x, y):
    # A restrained plan-view taper of the sheet metal, starting at the cowl.
    # Expedition bumpers, tyre spacing and mechanical mounting points stay fixed.
    return x * (1 - (1 - NOSE_SCALE) * C.smoothstep(COWL, FRONT, y))


def add_tub(mb):
    # V2's single closed tub keeps the vehicle visually solid. Door gaps are cut
    # into that tub; no separate black lines sit above a floating sheet panel.
    prof = [(REAR, .36), (REAR + .05, .30)]
    prof += arch(-WB / 2)
    prof += [(-.36, .15), (.36, .15)]
    prof += arch(WB / 2, zr=.36, zf=.30)
    prof += [(FRONT - .05, .30), (FRONT, .36), (FRONT, BELT - .025),
             (FRONT - .025, BELT), (REAR + .025, BELT), (REAR, BELT - .025)]
    bm = C.bm_extrude_poly(prof, 1.80, axis='X')
    C.bevel(bm, .022, 3)
    cuts = []
    for side in (-1, 1):
        for y, z0 in ((COWL - .022, .23), (-.15, .23), (-1.025, .645)):
            cuts.append(C.bm_box((.025, .006, BELT - z0 + .008), (side * .899, y, (BELT + z0) / 2)))
        cuts.append(C.bm_box((.025, 1.455, .006), (side * .899, -.0115, .228)))
    bm = P.bm_boolean(bm, cuts)
    bm.normal_update()
    def mat(face):
        p, n = face.calc_center_median(), face.normal
        if abs(n.x) > .8 and .884 < abs(p.x) < .894:
            return 'PanelGap'
        if n.z < -.3 or (abs(n.x) < .5 and L.in_arch(p)):
            return 'Trim'
        return 'Paint'
    # Identify the recessed door seams before tapering the front sheet metal;
    # their material must not depend on the later X displacement of the fenders.
    face_materials = {f: mat(f) for f in bm.faces}
    for v in bm.verts:
        v.co.x = nose_x(v.co.x, v.co.y)
    bm.normal_update()
    mb.add(bm, mat_fn=face_materials.__getitem__, shade='auto', angle=32)
    # Opaque wheel-well backs stop daylight from showing through the body.
    for yc in (-WB / 2, WB / 2):
        pts = arch(yc, r=.508, zr=.35, zf=.35)
        for side in (-1, 1):
            mb.add(C.bm_extrude_poly(pts, .018, axis='X', center=side * .36), mat='Trim', shade='flat')
    # Rocker lip and shallow belt pressing read as continuous body structure.
    for side in (-1, 1):
        F.box(mb, (side * .901, -.02, .174), (.025, 1.51, .052), 'Trim', .008, 2)
        F.box(mb, (side * .891, -.61, BELT - .008), (.025, 2.98, .024), 'Paint', .007, 2)


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


def hood_point(u, t):
    # Broad two-way crown, two tapered pressings and a rolled-down leading edge.
    # The pressings fade into the same sheet at both ends; no applied strips.
    x = u * (.858 + .006 * math.sin(math.pi * t))
    nose = C.smoothstep(.87, 1, t)
    y = COWL + .014 + (FRONT - COWL - .005) * t + .017 * (1 - u * u) * nose
    shoulder = max(0, 1 - u * u)
    crown = (.021 + .038 * math.sin(math.pi * t) ** .8) * shoulder
    fade = C.smoothstep(.05, .20, t) * (1 - C.smoothstep(.76, .94, t))
    centre = .53 - .075 * t
    bead = .018 * math.exp(-((abs(x) - centre) / .051) ** 2) * fade
    z = BELT + .009 + .007 * math.sin(math.pi * t) + (crown + bead) * (1 - nose)
    return (nose_x(x, y), y, z)


def cowl_point(u, t):
    # The scuttle rises into the windshield and meets the bonnet crown.
    x = u * .871
    y = COWL - .104 + .109 * t
    z = BELT + .010 + .020 * (1 - u * u) + .005 * math.sin(math.pi * t)
    return (x, y, z)


def add_hood(mb):
    skin(mb, hood_point, 80, 48, BELT - .006)
    skin(mb, cowl_point, 48, 8, BELT - .009)
    # The narrow separation follows the cowl crown instead of crossing it as a
    # straight dark bar. The bonnet's closed edge supplies the side seam.
    seam = [(x, y + .003, z - .003) for x, y, z in (cowl_point(-1 + i / 24, 1) for i in range(49))]
    F.path(mb, seam, .002, 'PanelGap', 6)
    for side in (-1, 1):
        for k in range(5):
            x = side * (.32 + k * .036)
            z = cowl_point(x / .871, .48)[2]
            F.box(mb, (x, COWL - .053, z + .001), (.021, .040, .003), 'Trim', .002, 2)


def roof_point(u, t):
    # A low roof with rounded shoulders, not the tall optional FJ62 roof.
    x = .837 * u
    y = -2.077 + (HEADER + 2.108) * t
    z = ROOF + .024 + .052 * max(0, 1 - u * u) + .010 * math.sin(math.pi * t)
    fade = C.smoothstep(.025, .10, t) * (1 - C.smoothstep(.90, .98, t))
    for rib in (-.53, -.27, .27, .53):
        z += .005 * math.exp(-((x - rib) / .017) ** 2) * fade
    return (x, y, z)


def add_greenhouse(mb):
    # Restore the first sample's straight inclined pillars and planar panes.
    # Keep the geometric tilt, with no bowing or shared nonlinear deformation.
    xb, xt, zb, zt = .885, .818, BELT, ROOF
    stations = [(COWL, HEADER), (-.15, -.17), (-1.025, -1.04), (-2.10, -2.055)]
    vs = []
    for yb, yt in stations:
        vs += [(-xb, yb, zb), (xb, yb, zb), (xt, yt, zt), (-xt, yt, zt)]
    fs = [[3, 2, 1, 0], [12, 13, 14, 15]]
    for i in range(3):
        a, b = i * 4, (i + 1) * 4
        fs += [[a + 1, b + 1, b + 2, a + 2], [a, a + 3, b + 3, b],
               [a + 3, a + 2, b + 2, b + 3], [a, b, b + 1, a + 1]]
    bm = C.bm_from(vs, fs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bottom = [f for f in bm.faces if f.normal.z < -.9]
    edges = [e for e in bm.edges if not any(f in bottom for f in e.link_faces)]
    bevel_faces = set(C.bevel(bm, .025, 3, edges).get('faces', []))
    bm.normal_update()
    wins = [f for f in bm.faces if f not in bevel_faces and abs(f.normal.z) < .5 and f.calc_area() > .05]
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z < -.9], context='FACES_ONLY')
    bmesh.ops.inset_individual(bm, faces=wins, thickness=.035, depth=-.009)
    seals = set(bmesh.ops.inset_individual(bm, faces=wins, thickness=.009, depth=-.003)['faces'])
    windows = set(wins)
    mb.add(bm, mat_fn=lambda f: 'Glass' if f in windows else 'Rubber' if f in seals else 'Paint', shade='auto', angle=32)
    skin(mb, roof_point, 80, 32, ROOF - .008, 'PaintAccent')
    for side in (-1, 1):
        gutter = [(side * .843, -2.085 + (HEADER + 2.14) * t, ROOF + .018 + .010 * math.sin(math.pi * t)) for t in (i / 32 for i in range(33))]
        F.path(mb, gutter, .012, 'Paint', 8)
        # The front rack feet used to stand ahead of the sloped windscreen.
        # A small landing plate now reaches the roof's leading edge.
        F.box(mb, (side * .758, .533, ROOF + .024), (.076, .20, .018), 'Trim', .008, 3)
    # Wipers sit against the lower windshield, never hover above it.
    for x in (-.38, .34):
        a = (x, COWL - .018, zb + .034)
        b = (x + .17, COWL - .058, zb + .139)
        F.tube(mb, a, b, .006, 'Trim', 8)
        F.tube(mb, (b[0] - .15, b[1], b[2]), (b[0] + .15, b[1], b[2]), .008, 'Rubber', 8)
    # The front-door quarter light is a recognisable FJ60 cue.
    for side in (-1, 1):
        F.tube(mb, (side * .875, .46, zb + .052), (side * .822, .39, zt - .044), .007, 'Paint', 8)


def add_front(mb):
    # FJ60's wide horizontal grille, inset round lamps and stacked amber/clear
    # corner units. Large contrasts are retained at a normal chase-camera scale.
    y, z = FRONT, .652
    F.box(mb, (0, y + .009, z), (1.75 * NOSE_SCALE, .061, .407), 'Trim', .014, 3)
    for zz in (.470, .837):
        F.box(mb, (0, y + .044, zz), (1.72 * NOSE_SCALE, .023, .016), 'Metal', .004, 2)
    for k in range(5):
        F.box(mb, (0, y + .047, .501 + k * .060), (1.02 * NOSE_SCALE, .023, .017), 'Metal', .003, 2)
    for x in (-.34, 0, .34):
        F.box(mb, (x, y + .044, .635), (.012, .02, .288), 'Trim', .002, 1)
    for side in (-1, 1):
        x = side * .624 * NOSE_SCALE
        F.box(mb, (x, y + .033, z), (.281, .05, .30), 'Trim', .025, 3)
        L.lamp_round(mb, x, z, y + .073, .101, 'Lamp', 'Metal', depth=.045, ring=.018, segs=32)
        # Restrained lens fluting and three mounting tabs; no bright wire mesh.
        for k in range(-3, 4):
            dx = k * .023
            h = math.sqrt(.091 ** 2 - dx ** 2)
            F.tube(mb, (x + dx, y + .074, z - h), (x + dx, y + .074, z + h), .0011, 'Lamp', 5)
        F.box(mb, (side * .821 * NOSE_SCALE, y + .045, .671), (.092, .035, .176), 'LampAmber', .008, 3)
        F.box(mb, (side * .821 * NOSE_SCALE, y + .046, .555), (.092, .036, .049), 'Lamp', .006, 2)
        F.box(mb, (nose_x(side * .896, 1.73), 1.73, .708), (.016, .083, .032), 'LampAmber', .004, 2)
    F.box(mb, (0, y + .065, .692), (.366, .025, .081), 'Trim', .004, 2)
    L.add_text(mb, 'TOYOTA', (0, y + .081, .692), .076, .0015, 'Decal', .0010)
    # Painted leading edge meets the grille; no opening beneath the bonnet.
    F.box(mb, (0, y - .004, .865), (1.77 * NOSE_SCALE, .036, .026), 'Paint', .007, 2)


def add_sides(mb):
    # Keep the broad flares that make V2 feel planted, but use a continuous rolled
    # profile instead of a stack of thin arcs or visible cylindrical segments.
    for side in (-1, 1):
        for yc, zr, zf in ((-WB / 2, .24, .30), (WB / 2, .30, .24)):
            outer = arch(yc, r=.60, zr=zr, zf=zf)
            inner = arch(yc, r=.50, zr=zr, zf=zf)[::-1]
            bm = C.bm_extrude_poly(outer + inner, .14, axis='X', center=side * .93)
            outer_edges = [e for e in bm.edges if all(abs(v.co.x) > .995 for v in e.verts)]
            C.bevel(bm, .014, 3, outer_edges)
            mb.add(bm, mat='Trim', shade='auto', angle=38)
        x = side * .90
        # FJ60 concealed hinges; compact recessed pulls align with the window posts.
        for y in (-.027, -.906):
            F.box(mb, (x + side * .003, y, .773), (.010, .133, .047), 'PanelGap', .010, 3)
            F.box(mb, (x + side * .012, y, .779), (.020, .108, .017), 'Metal', .006, 2)
            F.tube(mb, (x + side * .003, y - .095, .775), (x + side * .010, y - .095, .775), .007, 'Metal', 12)
        for y0, y1 in ((-2.08, -1.79), (-.93, .96), (1.79, 1.92)):
            F.box(mb, (x + side * .006, (y0 + y1) / 2, .551), (.015, y1 - y0, .025), 'Trim', .006, 2)
        # Shoulder line is a pressed crease in the same paint, not chrome piping.
        F.box(mb, (side * .900, -.70, .846), (.008, 2.77, .010), 'Paint', .002, 1)
        if side > 0:
            F.box(mb, (x + .003, -1.84, .774), (.009, .153, .13), 'PanelGap', .012, 3)
            F.box(mb, (x + .006, -1.84, .774), (.010, .140, .116), 'Paint', .010, 3)
        # Old sliders are useful graphic weight below the body.
        F.path(mb, [(side * .93, .75, .135), (side * .955, .69, .105),
                    (side * .955, -.78, .105), (side * .93, -.85, .135)], .033, 'Trim', 10)
        F.box(mb, (side * .923, -.04, .140), (.104, 1.34, .018), 'Metal', .006, 2)
        for y in (-.58, 0, .53):
            F.box(mb, (side * .72, y, .104), (.45, .055, .035), 'Trim', .006, 2)
        for yc, zz in ((.835, .075), (-1.935, .063)):
            F.box(mb, (side * .835, yc, zz), (.26, .018, .37), 'Rubber', .005, 2)
        # Small boxed mirror on one continuous arm, attached to the door frame.
        F.path(mb, [(side * .905, .65, .876), (side * 1.025, .675, .967), (side * 1.065, .674, .989)], .012, 'Trim', 10)
        F.box(mb, (side * 1.07, .674, 1.005), (.053, .100, .166), 'Trim', .018, 3)
        F.box(mb, (side * 1.071, .620, 1.007), (.043, .004, .139), 'Glass', .011, 3)
        F.text(mb, 'LAND CRUISER', (nose_x(side * .905, 1.135), 1.135, .807), .025, 'right' if side > 0 else 'left', 'Metal')
    # Snorkel follows the revised A-pillar, with visible collars at the mounts.
    F.box(mb, (-.928, .974, .796), (.114, .228, .139), 'Trim', .023, 3)
    F.path(mb, [(-.938, 1.0, .848), (-.937, .848, .913), (-.910, .700, 1.022),
                (-.864, .518, 1.456), (-.864, .49, 1.566)], .043, 'Trim', 16)
    F.box(mb, (-.864, .489, 1.589), (.124, .157, .087), 'Trim', .027, 4)
    for z in (1.068, 1.348):
        y = .700 - (z - 1.022) / (.434 / .182)
        F.box(mb, (-.887, y, z), (.105, .027, .020), 'Metal', .004, 2)
    F.tube(mb, (.81, 1.62, .901), (.79, 1.60, 1.86), .004, 'Trim', 8)


def build_body(mb):
    add_tub(mb)
    add_hood(mb)
    add_greenhouse(mb)
    add_front(mb)
    L.add_bumper_front(mb)
    L.add_rear(mb)
    add_sides(mb)
    # Reuse the corrected moving-gear architecture without the rejected body.
    F.chassis(mb, S)
    add_rack(mb)


def add_rack(mb):
    # Preserve the expedition luggage, repairing the V2 straps that were tall
    # solid boxes through the bags. Bent ribbons now follow the bag surfaces.
    rack = C.MeshBuilder('V2 expedition rack')
    L.add_rack(rack)
    start = len(mb.V)
    mb.V.extend(v.copy() for v in rack.V)
    for face, mat, colors, normals in zip(rack.F, rack.FM, rack.LC, rack.LN):
        if mat == 'Rubber':
            continue
        mb.F.append([start + i for i in face]); mb.FM.append(mat)
        mb.LC.append(colors); mb.LN.append(normals)
    base = ROOF + .035 + .08 + .015
    for x0 in (-.70, .04):
        for y in (.22, -.28):
            profile = [(x0 - .002, base + .015), (x0 + .002, base + .14),
                       (x0 + .054, base + .267), (x0 + .13, base + .292),
                       (x0 + .51, base + .292), (x0 + .586, base + .267),
                       (x0 + .638, base + .14), (x0 + .642, base + .015)]
            verts, faces = [], []
            for i, (x, z) in enumerate(profile):
                verts.extend([(x, y - .019, z + .004), (x, y + .019, z + .004)])
                if i:
                    faces.append([i * 2 - 2, i * 2, i * 2 + 1, i * 2 - 1])
            bm = C.bm_from(verts, faces)
            C.orient(bm, lambda f: Vector((f.calc_center_median().x - x0 - .32, 0, .15)))
            mb.add(bm, mat='Rubber', shade='auto', angle=35)
            F.box(mb, (x0 + .1, y, base + .290), (.052, .05, .014), 'Metal', .004, 2)


def main():
    C.reset_scene()
    os.makedirs(STUDY, exist_ok=False)
    with open(__file__, 'rb') as source, open(os.path.join(STUDY, 'generator.py'), 'wb') as snapshot:
        snapshot.write(source.read())
    mats, parts, tris = materials(), {}, {}
    col = C.collection('Toyota Trail source parts')
    builders = {'Body': build_body, 'Wheel': refined_wheel,
                'AxleFront': lambda mb: F.axle(mb, S, True), 'AxleRear': lambda mb: F.axle(mb, S, False),
                'Spring': F.leaf, 'ShockBody': F.shock, 'ShockRod': lambda mb: F.shock(mb, True),
                'BrakeFront': lambda mb: F.brake(mb, S), 'BrakeRear': lambda mb: F.brake(mb, S, True),
                'Driveshaft': P.add_driveshaft}
    for name, fn in builders.items():
        mb = C.MeshBuilder(name)
        fn(mb)
        tris[name] = mb.tris()
        parts[name] = mb.build(mats, vcolor=False, collection_obj=col)
    F.morph_spring(parts['Spring'], S)
    for name, ratio in (('Body', .44), ('Wheel', .36)):
        if name == 'Wheel':
            low = C.MeshBuilder('Wheel_LOD1')
            P.add_wheel(low, R=R, W=W, segs=20, lugs=16, style='steel')
            parts['Wheel_LOD1'] = low.build(mats, vcolor=False, collection_obj=col)
            tris['Wheel_LOD1'] = low.tris()
            continue
        o = bpy.data.objects.new(name + '_LOD1', parts[name].data.copy())
        col.objects.link(o)
        mod = o.modifiers.new('Distance LOD', 'DECIMATE')
        mod.ratio, mod.use_collapse_triangulate = ratio, True
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=mod.name)
        parts[o.name] = o
        tris[o.name] = sum(len(p.vertices) - 2 for p in o.data.polygons)
    bpy.context.view_layer.update()
    C.export_glb(list(parts.values()), MODEL + '.glb', vcolor=False, morph=True)
    mn, mx = C.world_bbox([parts['Body']])
    lamps = dict(L.LAMPS)
    lamps['head'] = [(-.624 * NOSE_SCALE, FRONT + .073, .652), (.624 * NOSE_SCALE, FRONT + .073, .652)]
    lamps['indicator'] = [(x * NOSE_SCALE, y, z) for x, y, z in lamps['indicator']]
    info = dict(id='toyota', fidelity=3, style='trail-v2-refinement/1', revision=REVISION, reference='Toyota Land Cruiser FJ60',
                rigFile=os.path.relpath(os.path.join(STUDY, 'rig.json'), C.GAME),
                wheelBase=WB, trackX=TX, wheelRadius=R, wheelWidth=W,
                spring=dict(x=S['spring_x'], top=S['spring_top'], seat=S['spring_seat'], kind='leaf', morphBump=.25, morphDroop=.20),
                shock=dict(bottom=[.28, .035, .09], top=[.265, .535, -.10]),
                driveshaft=dict(tcaseZ=.30, tcaseY=.05, pinionZ=.235, pinionY=.025),
                lamps={k: [P.g(p) for p in ps] for k, ps in lamps.items()},
                bodyBox=dict(min=P.g((mn.x, mx.y, mn.z)), max=P.g((mx.x, mn.y, mx.z))),
                lod=dict(near=18, far=23), tris=tris)
    with open(os.path.join(C.MODELS, MODEL + '.json'), 'w') as f:
        json.dump(info, f, indent=2)
    with open(os.path.join(STUDY, 'rig.json'), 'w') as f:
        json.dump(DIMS, f, indent=2)
    import vehicle_check
    checks = vehicle_check.run(parts, DIMS, shrink=1.0)
    with open(os.path.join(STUDY, 'clearance.json'), 'w') as f:
        json.dump(checks, f, indent=2)
    if any(checks.values()):
        raise RuntimeError('Toyota Trail running-gear clearance failed; see ' + STUDY)
    print('TRAIL STUDY', json.dumps(tris), flush=True)
    if '--no-preview' not in sys.argv:
        previous = C.PREVIEWS
        C.PREVIEWS = STUDY
        # Same rendering and framing for old and refined assets. Final assessment
        # is made in the game, not with stronger studio lighting on the candidate.
        C.setup_render((1440, 900), '#B7C9CB', .9, 64)
        C.add_sun((52, 0, 145), 4.2)
        ground = C.add_ground(-R)
        col.hide_render = True
        rest = C.collection('Toyota Trail assembled')
        objects = F.assemble(parts, rest, DIMS)
        for label, az, el in [('front', -35, 10), ('side', 90, 2), ('rear', -135, 12), ('under', 35, -22)]:
            ground.hide_render = label == 'under'
            C.frame_camera(objects, az=az, el=el, lens=55)
            C.render('study-' + label + '.png')
        ground.hide_render = False
        C.frame_camera(objects, az=-35, el=10, lens=55)
        C.PREVIEWS = previous
    else:
        F.assemble(parts, C.collection('Toyota Trail assembled'), DIMS)
    col.hide_render = col.hide_viewport = True
    C.save_blend(MODEL + '.blend')
    return tris


if __name__ == '__main__':
    main()
