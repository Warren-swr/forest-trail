"""Regenerate every Forest Trail art asset from scratch.

    blender --background --python game/art/blender/build_all.py

Builds the three vehicles, vegetation, rocks, props and the second-wave nature/props packs (GLBs -> game/public/assets/models, .blend files
next to this script, previews -> game/art/previews) and then writes game/art/asset-report.json.
"""
import os, sys, time, glob
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C

# start clean: remove the GLBs and previews this pipeline owns
OWNED = ['vehicle_scout', 'vehicle_toyota', 'vehicle_ranger', 'pine_tall_a', 'pine_tall_b', 'pine_mid', 'pine_young', 'aspen_gold', 'snag', 'bush_a',
         'bush_b', 'fern', 'grass_tuft', 'rock_a', 'rock_b', 'rock_c', 'rock_slab', 'rock_post', 'pebbles', 'log',
         'stump', 'cabin', 'lookout', 'tent', 'campfire', 'bench_log', 'picnic_table', 'signpost', 'toolbox',
         'shed', 'dock', 'fence', 'bridge_plank',
         # nature2.py
         'maple_red', 'maple_orange', 'birch', 'larch_gold', 'grass_tall', 'flowers_a', 'flowers_b',
         'boulder_a', 'boulder_b', 'boulder_c', 'sandstone_a', 'sandstone_b', 'sandstone_c', 'sandstone_arch',
         'deer_stag', 'deer_doe', 'eagle',
         # props2.py
         'aframe_cabin', 'boathouse', 'plank_bridge', 'camper', 'lantern', 'lamp_post', 'string_pole', 'cone',
         'flag_marker', 'tyre_stack', 'tyre_wall', 'gate_arch', 'log_step', 'sign_board', 'barrier', 'rowboat',
         'crate_stack', 'firewood', 'canoe_rack']
for name in OWNED:
    for suffix in ('.glb', '_lod1.glb', '.json'):
        p = os.path.join(C.MODELS, name + suffix)
        if os.path.exists(p):
            os.remove(p)
for p in glob.glob(os.path.join(C.PREVIEWS, '*.png')):
    os.remove(p)

import vehicle_scout, vehicle_toyota, vehicle_ranger, vegetation, rocks, props, nature2, props2, report

t0 = time.time()
summary = {}
for mod in (vehicle_scout, vehicle_toyota, vehicle_ranger, vegetation, rocks, props, nature2, props2):
    t = time.time()
    summary[mod.__name__] = mod.main()
    print('BUILD %-10s done in %.1fs' % (mod.__name__, time.time() - t))

out = report.main({'vehicles': 'see public/assets/models/vehicle_<id>.json for mounts, lamps and body boxes'})
print('BUILD ALL done in %.1fs -> %s' % (time.time() - t0, out))
