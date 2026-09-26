"""Shared helpers for the Forest Trail procedural asset scripts (Blender 4.5).

Geometry is authored as small bmesh "parts" which are baked into a MeshBuilder.
The builder keeps per-corner colours (sRGB), per-corner custom normals and a
per-face material name, then emits a single Blender mesh object.
"""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix, Euler
from bpy_extras.object_utils import world_to_camera_view

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)
GAME = os.path.dirname(ART)
MODELS = os.path.join(GAME, 'public', 'assets', 'models')
PREVIEWS = os.path.join(ART, 'previews')
UP = Vector((0, 0, 1))


# ----------------------------------------------------------------- colour
def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def s2l(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def ramp(stops, t):
    """stops: list of (pos, colour) sorted by pos."""
    t = max(stops[0][0], min(stops[-1][0], t))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            return mix(c0, c1, (t - p0) / max(1e-6, p1 - p0))
    return stops[-1][1]


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def scale_col(c, k):
    return tuple(max(0.0, min(1.0, x * k)) for x in c)


# ----------------------------------------------------------------- scene
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0


def collection(name):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    return col


# ----------------------------------------------------------------- bmesh primitives
def bm_from(verts, faces):
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(v)) for v in verts]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    return bm


def xform(bm, M):
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm


def mat_trs(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    return (Matrix.Translation(Vector(loc)) @ Euler(rot).to_matrix().to_4x4()
            @ Matrix.Diagonal((*scale, 1)))


def bevel(bm, offset, segs=1, edges=None, profile=0.5):
    edges = list(bm.edges) if edges is None else edges
    if offset <= 0 or not edges:
        return {}
    return bmesh.ops.bevel(bm, geom=edges, offset=offset, offset_type='OFFSET', segments=segs,
                           profile=profile, affect='EDGES', clamp_overlap=True)


def bm_box(size, center=(0, 0, 0), bev=0.0, segs=1, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    if bev:
        bevel(bm, bev, segs)
    return xform(bm, mat_trs(center, rot))


def bm_box_mm(mn, mx, bev=0.0, segs=1):
    """Axis aligned box from min/max corners."""
    c = [(a + b) / 2 for a, b in zip(mn, mx)]
    s = [abs(b - a) for a, b in zip(mn, mx)]
    return bm_box(s, c, bev, segs)


def align_z(direction):
    d = Vector(direction).normalized()
    return UP.rotation_difference(d).to_matrix().to_4x4()


def bm_cyl(r1, r2, depth, segs=8, M=Matrix(), cap=True, base=False):
    """Cone/cylinder along local Z. base=True puts the bottom at z=0."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs,
                          radius1=r1, radius2=r2, depth=depth)
    if base:
        bmesh.ops.translate(bm, vec=(0, 0, depth / 2), verts=bm.verts)
    return xform(bm, M)


def bm_cyl_between(p1, p2, r, segs=6, r2=None, cap=True, rot=0.0):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    M = Matrix.Translation(p1) @ align_z(d) @ Matrix.Rotation(rot, 4, 'Z')
    return bm_cyl(r, r if r2 is None else r2, d.length, segs, M, cap, base=True)


def bm_lathe(profile, segs=16, axis='Z', cap_start=False, cap_end=False, phase=0.0, arc=None):
    """Revolve a profile [(radius, height)] about an axis. radius 0 -> pole vertex."""
    bm = bmesh.new()
    rings = []
    full = arc is None
    arc = 2 * math.pi if full else arc
    nseg = segs if full else segs + 1
    for r, h in profile:
        ring = []
        count = 1 if r == 0 else nseg
        for i in range(count):
            a = phase + arc * i / segs
            x, y = r * math.cos(a), r * math.sin(a)
            p = {'Z': (x, y, h), 'X': (h, x, y), 'Y': (y, h, x)}[axis]
            ring.append(bm.verts.new(p))
        rings.append(ring)
    for ra, rb in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % nseg
            if len(ra) == 1 and len(rb) == 1:
                continue
            if len(ra) == 1:
                vs = [ra[0], rb[i], rb[j]]
            elif len(rb) == 1:
                vs = [ra[i], rb[0], ra[j]]
            else:
                vs = [ra[i], rb[i], rb[j], ra[j]]
            try:
                bm.faces.new(vs)
            except ValueError:
                pass
    if full:
        if cap_start and len(rings[0]) > 2:
            bm.faces.new(list(reversed(rings[0])))
        if cap_end and len(rings[-1]) > 2:
            bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces) if (cap_start and cap_end) else None
    return bm


def bm_extrude_poly(pts, depth, axis='X', center=0.0):
    """Extrude 2D polygon (u, v) along axis. For axis X: (u,v)=(y,z)."""
    n = len(pts)
    vs = []
    for s in (-0.5, 0.5):
        w = center + s * depth
        for u, v in pts:
            vs.append({'X': (w, u, v), 'Y': (u, w, v), 'Z': (u, v, w)}[axis])
    faces = [list(range(n)), list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    bm = bm_from(vs, faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def bm_hull(points):
    bm = bmesh.new()
    for p in points:
        bm.verts.new(Vector(p))
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:], use_existing_faces=False)
    kill = list({g for g in res['geom_interior'] + res['geom_unused'] if isinstance(g, bmesh.types.BMVert)})
    kill += [v for v in bm.verts if not v.link_faces and v not in kill]
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def bm_icosphere(r=1.0, subdiv=1, M=Matrix()):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    return xform(bm, M)


def tri_count_bm(bm):
    return sum(len(f.verts) - 2 for f in bm.faces)


# ----------------------------------------------------------------- mesh builder
class MeshBuilder:
    def __init__(self, name, seed=1):
        self.name = name
        self.V, self.F, self.FM, self.LC, self.LN = [], [], [], [], []
        self.rng = random.Random(seed)

    def add(self, bm, color=(1, 1, 1), mat='VC', shade='flat', angle=35.0,
            normal_fn=None, color_fn=None, jitter=0.0, hue=0.0, mat_fn=None):
        """Bake a bmesh part. shade: 'flat' | 'smooth' | 'auto' (angle threshold)."""
        bm.verts.index_update()
        bm.faces.index_update()
        bm.normal_update()
        base = len(self.V)
        self.V.extend(v.co.copy() for v in bm.verts)
        cos_thr = math.cos(math.radians(angle))
        for f in bm.faces:
            if len(f.verts) < 3:
                continue
            fj = 1.0 + (self.rng.uniform(-jitter, jitter) if jitter else 0.0)
            hj = self.rng.uniform(-hue, hue) if hue else 0.0
            cols, nors = [], []
            for l in f.loops:
                c = color_fn(l, f) if color_fn else color
                c = (c[0] * fj * (1 + hj), c[1] * fj, c[2] * fj * (1 - hj))
                cols.append(tuple(max(0.0, min(1.0, x)) for x in c))
                if normal_fn:
                    n = Vector(normal_fn(l, f))
                elif shade == 'flat':
                    n = f.normal.copy()
                elif shade == 'smooth':
                    n = l.vert.normal.copy()
                else:
                    n = Vector()
                    for lf in l.vert.link_faces:
                        if lf.normal.dot(f.normal) >= cos_thr:
                            n += lf.normal * max(lf.calc_area(), 1e-6)
                    if n.length < 1e-8:
                        n = f.normal.copy()
                n.normalize()
                nors.append(n)
            self.F.append([base + l.vert.index for l in f.loops])
            self.FM.append(mat_fn(f) if mat_fn else mat)
            self.LC.append(cols)
            self.LN.append(nors)
        bm.free()
        return self

    def tris(self):
        return sum(len(f) - 2 for f in self.F)

    def build(self, materials, vcolor=True, collection_obj=None):
        """materials: dict name -> bpy material. Slots are ordered by first use."""
        me = bpy.data.meshes.new(self.name)
        me.from_pydata([tuple(v) for v in self.V], [], self.F)
        order = []
        for m in self.FM:
            if m not in order:
                order.append(m)
        for m in order:
            me.materials.append(materials[m])
        me.polygons.foreach_set('material_index', [order.index(m) for m in self.FM])
        me.polygons.foreach_set('use_smooth', [True] * len(self.F))
        if vcolor:
            attr = me.color_attributes.new('Color', 'BYTE_COLOR', 'CORNER')
            flat = []
            for cols in self.LC:
                for c in cols:
                    flat.extend((c[0], c[1], c[2], 1.0))
            attr.data.foreach_set('color_srgb', flat)
            me.color_attributes.active_color = attr
            me.color_attributes.render_color_index = 0
        me.normals_split_custom_set([tuple(n) for ns in self.LN for n in ns])
        me.update()
        obj = bpy.data.objects.new(self.name, me)
        (collection_obj or bpy.context.scene.collection).objects.link(obj)
        return obj


# ----------------------------------------------------------------- materials
def mat_vc(name='VC', double_sided=False, roughness=0.85):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (1, 1, 1, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = 0.0
    ca = nt.nodes.new('ShaderNodeVertexColor')
    ca.layer_name = 'Color'
    ca.location = (-300, 200)
    nt.links.new(ca.outputs['Color'], bsdf.inputs['Base Color'])
    m.use_backface_culling = not double_sided
    return m


def mat_pbr(name, color_hex, roughness=0.5, metallic=0.0, emission=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*s2l(hexc(color_hex)), 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*s2l(hexc(emission)), 1)
        bsdf.inputs['Emission Strength'].default_value = emit_strength
    m.diffuse_color = (*s2l(hexc(color_hex)), 1)
    m.use_backface_culling = True
    return m


# ----------------------------------------------------------------- export
def export_glb(objs, filename, vcolor=True, morph=False):
    os.makedirs(MODELS, exist_ok=True)
    path = os.path.join(MODELS, filename)
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = objs[0]
    # the double-sided vertex colour material must also be called "VC" in the file
    renamed = []
    used = {s.material for o in objs for s in o.material_slots if s.material}
    if any(m.name == 'VC_2S' for m in used):
        a, b = bpy.data.materials.get('VC'), bpy.data.materials.get('VC_2S')
        if a:
            a.name = 'VC_tmp'
        b.name = 'VC'
        renamed = [(a, 'VC'), (b, 'VC_2S')]
    try:
        bpy.ops.export_scene.gltf(
            filepath=path, export_format='GLB', use_selection=True, export_yup=True,
            export_apply=True, export_normals=True, export_tangents=False,
            export_texcoords=False, export_cameras=False, export_lights=False,
            export_animations=False, export_skins=False, export_morph=morph,
            export_extras=False, export_materials='EXPORT',
            export_vertex_color='ACTIVE' if vcolor else 'NONE',
            export_all_vertex_colors=False)
    finally:
        if renamed:
            renamed[1][0].name = 'VC_2S'
            if renamed[0][0]:
                renamed[0][0].name = 'VC'
    return path


def save_blend(name):
    path = os.path.join(HERE, name)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    return path


# ----------------------------------------------------------------- preview rendering
def world_bbox(objs):
    mn = Vector((1e9, 1e9, 1e9))
    mx = -mn
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector(map(min, mn, w))
            mx = Vector(map(max, mx, w))
    return mn, mx


def setup_render(res=(1024, 640), sky='#B7C9CB', world_strength=0.9, samples=48):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE_NEXT'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.eevee.taa_render_samples = samples
    for attr, val in (('use_shadows', True), ('use_gtao', True), ('shadow_ray_count', 2),
                      ('shadow_step_count', 8), ('use_raytracing', False)):
        try:
            setattr(sc.eevee, attr, val)
        except Exception:
            pass
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    w = bpy.data.worlds.new('PreviewWorld')
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (*s2l(hexc(sky)), 1)
    bg.inputs['Strength'].default_value = world_strength
    sc.world = w


def add_sun(rot_deg=(50, 0, 140), energy=4.0, angle_deg=4.0, color='#FFF1DC'):
    ld = bpy.data.lights.new('Sun', 'SUN')
    ld.energy = energy
    ld.angle = math.radians(angle_deg)
    ld.color = s2l(hexc(color))
    ob = bpy.data.objects.new('Sun', ld)
    ob.rotation_euler = [math.radians(a) for a in rot_deg]
    bpy.context.scene.collection.objects.link(ob)
    return ob


def add_ground(z=0.0, size=400.0, color='#9C8F6E', name='PreviewGround'):
    bm = bm_box((size, size, 0.02), (0, 0, z - 0.01))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    m = mat_pbr(name + 'Mat', color, roughness=0.95)
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def frame_camera(objs, az=35.0, el=18.0, lens=50.0, margin=0.06, target_off=(0, 0, 0)):
    """Place a camera at azimuth/elevation (degrees, az measured from +Y toward +X)
    so that the bounding box of objs fills the frame."""
    sc = bpy.context.scene
    cam = sc.camera
    if cam is None:
        cam = bpy.data.objects.new('PreviewCam', bpy.data.cameras.new('PreviewCam'))
        sc.collection.objects.link(cam)
        sc.camera = cam
    cam.data.lens = lens
    cam.data.shift_x = cam.data.shift_y = 0.0
    cam.data.clip_end = 2000
    bpy.context.view_layer.update()
    mn, mx = world_bbox(objs)
    corners = [Vector((x, y, z)) for x in (mn.x, mx.x) for y in (mn.y, mx.y) for z in (mn.z, mx.z)]
    ctr = (mn + mx) / 2 + Vector(target_off)
    a, e = math.radians(az), math.radians(el)
    d = Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    aspect = sc.render.resolution_y / sc.render.resolution_x

    def extents(dist):
        cam.location = ctr + d * dist
        bpy.context.view_layer.update()
        ps = [world_to_camera_view(sc, cam, c) for c in corners]
        return (min(p.x for p in ps), max(p.x for p in ps), min(p.y for p in ps), max(p.y for p in ps))

    diag = (mx - mn).length
    for _ in range(3):
        lo, hi = diag * 0.2, diag * 20
        for _ in range(40):
            mid = (lo + hi) / 2
            x0, x1, y0, y1 = extents(mid)
            if x0 < margin or y0 < margin or x1 > 1 - margin or y1 > 1 - margin:
                lo = mid
            else:
                hi = mid
        x0, x1, y0, y1 = extents(hi)
        cam.data.shift_x += ((x0 + x1) / 2 - 0.5)
        cam.data.shift_y += ((y0 + y1) / 2 - 0.5) * aspect
    extents(hi)
    return cam


def render(filename):
    os.makedirs(PREVIEWS, exist_ok=True)
    sc = bpy.context.scene
    sc.render.filepath = os.path.join(PREVIEWS, filename)
    bpy.ops.render.render(write_still=True)
    return sc.render.filepath


def lineup(objs, gap=1.0, y=0.0):
    """Arrange objects left-to-right along X (by bbox width). Returns list of (obj, x)."""
    widths = []
    for o in objs:
        o.location = (0, 0, 0)
    bpy.context.view_layer.update()
    for o in objs:
        mn, mx = world_bbox([o])
        widths.append((mn.x, mx.x))
    total = sum(b - a for a, b in widths) + gap * (len(objs) - 1)
    x = -total / 2
    for o, (a, b) in zip(objs, widths):
        o.location = (x - a, y, 0)
        x += (b - a) + gap
    bpy.context.view_layer.update()


def label(text, loc, size=0.6, color='#2A2A28'):
    cu = bpy.data.curves.new('lbl_' + text, 'FONT')
    cu.body = text
    cu.size = size
    cu.align_x = 'CENTER'
    ob = bpy.data.objects.new('lbl_' + text, cu)
    ob.location = loc
    ob.rotation_euler = (math.radians(90), 0, 0)
    m = bpy.data.materials.get('LabelMat') or mat_pbr('LabelMat', color, 0.9)
    cu.materials.append(m)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def orient(bm, dir_fn, faces=None):
    """Flip faces whose normal disagrees with dir_fn(face) (for open surfaces)."""
    bm.normal_update()
    flip = [f for f in (faces or bm.faces) if f.normal.dot(Vector(dir_fn(f))) < 0]
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
    bm.normal_update()
    return bm
