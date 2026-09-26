"""Render a real 3D lineup from the three saved, assembled Blender vehicles."""
import bpy, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
from vehicle_fidelity import SPECS

C.reset_scene()
objects = []
for i, vid in enumerate(('scout', 'toyota', 'ranger')):
    with bpy.data.libraries.load(os.path.join(C.HERE, 'vehicle_' + vid + '.blend')) as (src, dst):
        dst.collections = ['Assembled vehicle']
    col = dst.collections[0]
    bpy.context.scene.collection.children.link(col)
    col.hide_render = col.hide_viewport = False
    for obj in col.all_objects:
        obj.location.x += (i - 1) * 3.5
        obj.location.z += SPECS[vid]['r'] - .40
        objects.append(obj)
C.setup_render((2200, 1200), '#ADBCC9', .70, 96)
C.add_sun((40, -12, 130), 2.5, 12)
C.add_ground(-.40, color='#73818B')
for name, loc, energy, size in [('Key', (2, 5, 8), 3200, 8), ('Rim', (-6, -3, 5), 2400, 6)]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size = energy, 'DISK', size
    ob = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector((0, 0, .7)) - ob.location).to_track_quat('-Z', 'Y').to_euler()
C.frame_camera(objects, az=23, el=17, lens=65, margin=.045)
C.render('vehicle_lineup.png')
