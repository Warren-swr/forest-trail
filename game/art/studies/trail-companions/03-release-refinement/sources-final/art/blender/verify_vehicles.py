"""Validate the actual saved meshes in nine steering/suspension poses per car.

    blender --background --python art/blender/verify_vehicles.py

Uses evaluated shape keys, not the undeformed leaf-spring base mesh.
"""
import bpy, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import vehicle_check

results = {}
for vid in ('scout', 'toyota', 'ranger'):
    model = 'vehicle_toyota_trail' if vid == 'toyota' else 'vehicle_' + vid
    bpy.ops.wm.open_mainfile(filepath=os.path.join(C.HERE, model + '.blend'))
    with open(os.path.join(C.MODELS, model + '.json')) as f:
        info = json.load(f)
    with open(os.path.join(C.GAME, info.get('rigFile', 'art/vehicle-' + vid + '-rig.json'))) as f:
        dims = json.load(f)
    names = ('Body', 'Wheel', 'Spring', 'Glazing', 'SteeringWheel', 'AxleFront', 'AxleRear',
             'BrakeFront', 'BrakeRear', 'ShockBody', 'ShockRod', 'Driveshaft')
    parts = {n: bpy.data.objects[n] for n in names if n in bpy.data.objects}
    results[vid] = vehicle_check.run(parts, dims, shrink=1.0)
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
output = args[0] if args else os.path.join(C.ART, 'vehicle-clearance.json')
with open(output, 'x' if args else 'w') as f:
    json.dump(results, f, indent=2)
failed = sum(bool(pairs) for poses in results.values() for pairs in poses.values())
print('CLEARANCE SUMMARY:', failed, 'of 27 poses have intersections', flush=True)
if failed:
    raise RuntimeError('Vehicle clearance needs attention; see art/vehicle-clearance.json')
