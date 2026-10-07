"""Small stamped-panel and glazing helpers for the three classic trail vehicles.

Metres, +Y forward, +Z up. Curvature belongs to the sheet or aperture; glass
remains planar and bent tubes have continuous, constant-radius sections.
"""
import math
import bmesh
from mathutils import Vector, Matrix
import common as C
import vehicle_fidelity as F


def inset(points, distance):
    pts = [Vector(p) for p in points]
    result = []
    for i, p in enumerate(pts):
        a = (pts[i - 1] - p).normalized()
        b = (pts[(i + 1) % len(pts)] - p).normalized()
        sine = math.sqrt(max(1e-8, (1 - a.dot(b)) / 2))
        result.append(p + (a + b).normalized() * distance / sine)
    return result


def corner_arc(previous, p, following, radius, steps=8):
    a, b = previous - p, following - p
    ua, ub = a.normalized(), b.normalized()
    theta = math.acos(max(-.99999, min(.99999, ua.dot(ub))))
    tangent = min(radius / math.tan(theta / 2), a.length * .35, b.length * .35)
    r = tangent * math.tan(theta / 2)
    center = p + (ua + ub).normalized() * r / math.sin(theta / 2)
    start, end = p + ua * tangent - center, p + ub * tangent - center
    axis = start.cross(end).normalized()
    angle = start.angle(end)
    return [center + Matrix.Rotation(angle * k / steps, 3, axis) @ start for k in range(steps + 1)]


def rounded(points, radius, steps=8):
    pts = [Vector(p) for p in points]
    return [v for i, p in enumerate(pts)
            for v in corner_arc(pts[i - 1], p, pts[(i + 1) % len(pts)], radius, steps)]


def bent_tube(mb, points, radius=.016, bend=.05, mat='Trim', segs=12):
    pts = [Vector(p) for p in points]
    curve = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b = pts[i - 1] - pts[i], pts[i + 1] - pts[i]
        if a.cross(b).length < 1e-8:
            curve.append(pts[i])
        else:
            curve.extend(corner_arc(pts[i - 1], pts[i], pts[i + 1], bend, 6))
    curve.append(pts[-1])
    F.path(mb, curve, radius, mat, segs)


def glazing(mb, points, normal, border=.03, radius=.045, chrome=False):
    """Fill one hull face with a radiused opening, recessed seal and flat glass.

    The painted fan meets the original hull perimeter exactly. Independent rings
    step inward in depth, so a seal cannot z-fight with the pane or disappear into
    its middle. The glass uses one planar ngon, including after triangulation.
    """
    pts, n = [Vector(p) for p in points], Vector(normal).normalized()
    aperture = rounded(inset(pts, border), radius)
    seal = [v - n * .004 for v in rounded(inset(pts, border + .009), max(.008, radius - .009))]
    glass = [v - n * .009 for v in rounded(inset(pts, border + .014), max(.006, radius - .014))]
    count, arc = len(aperture), 9
    verts = pts + aperture
    faces = []
    for i in range(len(pts)):
        for k in range(arc - 1):
            a = len(pts) + i * arc + k
            faces.append([i, a, a + 1])
        j = (i + 1) % len(pts)
        faces.append([i, j, len(pts) + j * arc, len(pts) + i * arc + arc - 1])
    bm = C.bm_from(verts, faces)
    C.orient(bm, lambda f: n)
    mb.add(bm, mat='Paint', shade='flat')
    for outer, inner, material in ((aperture, seal, 'Rubber'), (seal, glass, 'Rubber')):
        faces = [[i, (i + 1) % count, (i + 1) % count + count, i + count] for i in range(count)]
        bm = C.bm_from(outer + inner, faces)
        C.orient(bm, lambda f: n)
        mb.add(bm, mat=material, shade='auto', angle=38)
    bm = C.bm_from(glass, [list(range(count))])
    C.orient(bm, lambda f: n)
    mb.add(bm, mat='Glass', shade='flat')
    if chrome:
        F.path(mb, [v + n * .0005 for v in seal], .0015, 'Metal', 6, True)


def glazed_hull(mb, bm, windows, border=.03, radius=.045, chrome=False):
    records = [([v.co.copy() for v in face.verts], face.normal.copy()) for face in windows]
    bmesh.ops.delete(bm, geom=windows, context='FACES_ONLY')
    mb.add(bm, mat='Paint', shade='auto', angle=32)
    for points, normal in records:
        glazing(mb, points, normal, border, radius, chrome)


def surround(mb, points, radius=.025, width=.006, mat='Metal', normal=(0, 1, 0)):
    """Flat stamped trim ring, with an opening instead of a solid backing plate."""
    outer = rounded(points, radius)
    inner = rounded(inset(points, width), max(.004, radius - width))
    count = len(outer)
    bm = C.bm_from(outer + inner, [[i, (i + 1) % count, (i + 1) % count + count, i + count]
                                 for i in range(count)])
    n = Vector(normal).normalized()
    C.orient(bm, lambda f: n)
    mb.add(bm, mat=mat, shade='flat')
