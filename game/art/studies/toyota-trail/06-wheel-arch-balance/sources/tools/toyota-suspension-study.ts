// Controlled comparison: slowly lift the front-left contact patch on a level
// floor, using both the preserved baseline and the current production physics.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { VEHICLES, PHYS_DT, type VehicleSpec } from '../src/game/config';
import { Terrain } from '../src/game/world/terrain';
import { Physics, initRapier, RAPIER, groups, G_STATIC, G_CHASSIS } from '../src/game/physics/physics';
import { Vehicle } from '../src/game/physics/vehicle';

const info = JSON.parse(readFileSync('public/assets/models/vehicle_toyota_trail.json', 'utf8'));
const study = `art/studies/toyota-trail/${info.revision}`;
const output = process.argv[2];
assert(output, 'Pass a new output JSON path; existing measurements are preserved');
class FlatTerrain extends Terrain {
  protected build() {
    this.heights.fill(0);
    for (let i = 0; i < this.mat.length; i += 4) this.mat[i] = 255;
  }
}
await initRapier();
const terrain = new FlatTerrain();
const baseline: VehicleSpec = JSON.parse(readFileSync(`${study}/before-spec.json`, 'utf8'));
const variants = [];
for (const [name, spec] of [['before', baseline], ['after', VEHICLES.toyota]] as const) {
  const phys = new Physics(terrain);
  const v = new Vehicle(phys, 0, spec.wheelRadius + .06, 0, 0, spec);
  const neutral = { drive: 0, steer: 0, handbrake: true, digital: true };
  const step = () => { v.step(neutral); phys.step(); v.snapshot(); };
  for (let i = 0; i < 240; i++) step();
  const settled = { bodyHeight: v.pos.y, wheelLengths: v.wheels.map(w => w.length), loads: v.wheels.map(w => w.load) };
  const platform = phys.world.createCollider(RAPIER.ColliderDesc.cuboid(.25, .05, .60)
    .setTranslation(-spec.track / 2, -.05, -spec.wheelBase / 2)
    .setCollisionGroups(groups(G_STATIC, G_CHASSIS)));
  const samples = [];
  let supportedHeight = 0;
  for (let i = 0; i <= 600; i++) {
    const height = .50 * i / 600;
    platform.setTranslation({ x: -spec.track / 2, y: height - .05, z: -spec.wheelBase / 2 });
    step();
    if (v.wheels.every(w => w.grounded && w.load > 100)) supportedHeight = height;
    if (i % 30 === 0) samples.push({ time: i * PHYS_DT, height,
      bodyHeight: v.pos.y, uprightness: v.uprightness,
      wheelLengths: v.wheels.map(w => w.length), loads: v.wheels.map(w => w.load), grounded: v.groundedCount });
  }
  assert(v.uprightness > .9, `${name}: unstable slow articulation`);
  assert(Math.hypot(v.pos.x, v.pos.z) < .2, `${name}: moved off the test platform`);
  variants.push({ name, tyreDiameter: spec.wheelRadius * 2, travel: spec.restLength - spec.minLength,
    settled, supportedHeight, samples });
  phys.world.free();
}
const result = { method: 'Front-left platform rises from 0 to 0.50 m over 10 seconds at fixed 60 Hz. Same mass, flat terrain and handbrake; each variant uses its own track, tyre and suspension. Supported height requires all four tyres grounded with >100 N load. This controlled articulation check is not a real-world RTI measurement.',
  bodyLift: variants[1].settled.bodyHeight - variants[0].settled.bodyHeight, variants };
writeFileSync(output, JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ bodyLift: result.bodyLift,
  variants: variants.map(v => ({ name: v.name, supportedHeight: v.supportedHeight, settled: v.settled })) }, null, 2));
