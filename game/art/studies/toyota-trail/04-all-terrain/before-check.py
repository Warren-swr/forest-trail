"""Clearance check for the vehicle running gear.

Poses the parts like the game does (vehicle_parts.assemble) across the suspension
travel and steering lock, then intersects triangle BVHs between moving parts and the
body. Moving parts are shrunk 1.5 % about their own centre, and overlaps are ignored
only at designed mount contacts: a spring triangle within 0.10 m of its upper seat
(spring_x, +-axle, spring_top), and a driveshaft triangle within 0.09 m of a transfer
case output (0, +-tcase_y, tcase_z). Everything else counts.

    import vehicle_check; vehicle_check.run(parts, DIMS)  # from a vehicle script
Returns {pose: {pair: overlapping triangle pairs}} and prints a table; 0 everywhere = clean.
"""
import bpy, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import common as C
import vehicle_parts as P


def _tree(obj, shrink=1.0):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = evaluated.to_mesh()
    mw = obj.matrix_world
    ctr = sum((Vector(c) for c in obj.bound_box), Vector()) / 8
    S = Matrix.Translation(ctr) @ Matrix.Diagonal((shrink, shrink, shrink, 1)) @ Matrix.Translation(-ctr)
    verts = [mw @ (S @ v.co) for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    tree = BVHTree.FromPolygons(verts, polys, all_triangles=False)
    evaluated.to_mesh_clear()
    return tree


def mounts(dims):
    ay = dims['wheelbase'] / 2
    sp = [Vector((sx * dims['spring_x'], sy * ay, dims['spring_top'])) for sx in (-1, 1) for sy in (-1, 1)]
    tc = [Vector((0, sy * dims['tcase_y'], dims['tcase_z'])) for sy in (-1, 1)]
    result = {'Spring': (sp, 0.10), 'Driveshaft': (tc, 0.09)}
    if dims.get('fidelity'):
        from vehicle_fidelity import SPECS
        s = SPECS[dims['id']]
        if s['spring'] == 'leaf':
            eyes = [Vector((sx * s['spring_x'], sy * ay + dy, .16))
                    for sx in (-1, 1) for sy in (-1, 1) for dy in (-.53, .53)]
            result['Spring'] = (eyes, .07)
        shock = [Vector((sx * (.245 if s['spring'] == 'coil' else .265), sy * ay + .1, s['spring_top'] + .055))
                 for sx in (-1, 1) for sy in (-1, 1)]
        result['ShockRod'] = (shock, .055)
    return result


def _centre(obj, idx):
    return obj.matrix_world @ obj.data.polygons[idx].center


def poses(dims):
    up, dn, lock = dims['bump'], -dims['droop'], dims.get('lock', 32)
    return {
        'rest': {},
        'bump_all': {k: (up, 0) for k in ('FL', 'FR', 'RL', 'RR')},
        'droop_all': {k: (dn, 0) for k in ('FL', 'FR', 'RL', 'RR')},
        'cross_axle': {'FL': (up, 0), 'FR': (dn, 0), 'RL': (dn, 0), 'RR': (up, 0)},
        'cross_axle_2': {'FL': (dn, 0), 'FR': (up, 0), 'RL': (up, 0), 'RR': (dn, 0)},
        'lock_left_bump': {'FL': (up, lock), 'FR': (up, lock * 0.86)},
        'lock_right_bump': {'FL': (up, -lock * 0.86), 'FR': (up, -lock)},
        'lock_left_flex': {'FL': (up, lock), 'FR': (dn, lock * 0.86)},
        'lock_right_flex': {'FL': (dn, -lock * 0.86), 'FR': (up, -lock)},
    }


def run(parts, dims, shrink=0.985, verbose=True):
    col = C.collection('ClearanceCheck')
    results = {}
    for name, pose in poses(dims).items():
        objs = P.assemble(parts, col, dims, pose)
        bpy.context.view_layer.update()
        body = [o for o in objs if o.data == parts['Body'].data][0]
        movers = [o for o in objs if o is not body and o.name.split('_asm')[0] not in ('Glazing', 'SteeringWheel')]
        bt = _tree(body)
        res = {}
        mt = mounts(dims)
        for o in movers:
            kind = o.name.split('_asm')[0]
            pairs = _tree(o, shrink).overlap(bt)
            if kind in mt:
                pts, rad = mt[kind]
                # Long piston triangles span the stroke. Use the body-side contact
                # witness too so the pin/eye joint is exempt only at its actual mount.
                pairs = [p for p in pairs if min(min((_centre(o, p[0]) - q).length,
                                                     (_centre(body, p[1]) - q).length) for q in pts) > rad]
            n = len(pairs)
            if n:
                key = o.name.split('_asm')[0]
                res[key] = res.get(key, 0) + n
        # wheels against the axles / springs (e.g. tyre hitting a spring at full lock)
        wheels = [o for o in movers if o.data == parts['Wheel'].data]
        # Spring clones own independent morph data, so mesh identity would skip
        # them here. Select the assembled part name and test its evaluated shape.
        others = [o for o in movers if o.name.split('_asm')[0] in ('Spring', 'AxleFront', 'AxleRear')]
        for w in wheels:
            wt = _tree(w, shrink)
            for o in others:
                # a wheel always touches its own hub face: test the tyre only (outer radius band)
                n = len([p for p in wt.overlap(_tree(o, shrink)) if _tyre_face(w, p[0], dims)])
                if n:
                    key = 'Wheel~' + o.name.split('_asm')[0]
                    res[key] = res.get(key, 0) + n
        results[name] = res
        for o in objs:
            bpy.data.objects.remove(o)
    if verbose:
        print('CLEARANCE', dims.get('id', ''), {k: (v or 'ok') for k, v in results.items()})
    return results


def _tyre_face(wheel_obj, poly_index, dims):
    p = wheel_obj.data.polygons[poly_index]
    c = p.center
    return math.hypot(c.y, c.z) > dims['R'] * 0.72
