// Compare preserved production specifications on the same controlled platform.
// Pass a NEW output JSON path; baseline assets and previous measurements stay intact.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { VEHICLES, PHYS_DT, type VehicleSpec } from '../src/game/config';
import { Terrain } from '../src/game/world/terrain';
import { Physics, initRapier, RAPIER, groups, G_STATIC, G_CHASSIS } from '../src/game/physics/physics';
import { Vehicle } from '../src/game/physics/vehicle';
import { Vehicle as ReleasedVehicle } from '../art/studies/trail-companions/02-release-baseline/released/src/game/physics/vehicle';
import { Physics as ReleasedPhysics } from '../art/studies/trail-companions/02-release-baseline/released/src/game/physics/physics';
import { Terrain as ReleasedTerrain } from '../art/studies/trail-companions/02-release-baseline/released/src/game/world/terrain';

const study = 'art/studies/trail-companions/02-release-baseline';
const output = process.argv[2];
assert(output, 'Pass a new output path');
const baseline = JSON.parse(readFileSync(study + '/baseline.json', 'utf8'));
assert.equal(baseline.kind, 'published-release');
// Changes to shared code must not silently retune or replace the accepted FJ60.
assert.deepEqual(VEHICLES.toyota, JSON.parse(readFileSync(study + '/toyota-spec.json', 'utf8')));
for (const [file, expected] of Object.entries(baseline.toyotaReference)) {
  const actual = createHash('sha256').update(readFileSync(file)).digest('hex');
  assert.equal(actual, expected, 'The accepted FJ60 reference changed: ' + file);
}
class FlatTerrain extends Terrain {
  protected build() {
    this.heights.fill(0);
    for (let i = 0; i < this.mat.length; i += 4) this.mat[i] = 255;
  }
}
class ReleasedFlatTerrain extends ReleasedTerrain {
  protected build() {
    this.heights.fill(0);
    for (let i = 0; i < this.mat.length; i += 4) this.mat[i] = 255;
  }
}
await initRapier();
const terrain = new FlatTerrain();
const releasedTerrain = new ReleasedFlatTerrain();
const vehicles = [];
for (const id of ['scout', 'ranger'] as const) {
  const before: VehicleSpec = JSON.parse(readFileSync(study + '/' + id + '/before-spec.json', 'utf8'));
  const variants = [];
  for (const [name, spec] of [['before', before], ['after', VEHICLES[id]]] as const) {
    const phys = name === 'before' ? new ReleasedPhysics(releasedTerrain) : new Physics(terrain);
    const v = name === 'before'
      ? new ReleasedVehicle(phys as ReleasedPhysics, 0, .55, 0, 0, spec)
      : new Vehicle(phys as Physics, 0, .55, 0, 0, spec);
    const neutral = { drive: 0, steer: 0, handbrake: true, digital: true };
    const step = () => { v.step(neutral); phys.step(); v.snapshot(); };
    for (let i = 0; i < 240; i++) step();
    assert(v.wheels.every(w => w.grounded && w.load > 100), name + ': failed to settle on all four tyres');
    const settled = { bodyHeight: v.pos.y, wheelLengths: v.wheels.map(w => w.length),
      loads: v.wheels.map(w => w.load), sag: v.wheels.map(w => spec.restLength - w.length),
      bumpReserve: v.wheels.map(w => w.length - spec.minLength),
      droopReserve: v.wheels.map(w => spec.restLength - w.length) };
    const platform = phys.world.createCollider(RAPIER.ColliderDesc.cuboid(.25, .05, .60)
      .setTranslation(-spec.track / 2, -.05, -spec.wheelBase / 2)
      .setCollisionGroups(groups(G_STATIC, G_CHASSIS)));
    const samples = [];
    let supportedHeight = 0, maxRollDegrees = 0;
    for (let i = 0; i <= 600; i++) {
      const height = .50 * i / 600;
      platform.setTranslation({ x: -spec.track / 2, y: height - .05, z: -spec.wheelBase / 2 });
      step();
      if (v.wheels.every(w => w.grounded && w.load > 100)) supportedHeight = height;
      maxRollDegrees = Math.max(maxRollDegrees, Math.acos(Math.min(1, v.uprightness)) * 180 / Math.PI);
      for (const w of v.wheels) assert(w.length >= spec.minLength - .06001 && w.length <= spec.restLength + 1e-5);
      if (i % 30 === 0) samples.push({ time: i * PHYS_DT, height, bodyHeight: v.pos.y,
        uprightness: v.uprightness, grounded: v.groundedCount,
        wheelLengths: v.wheels.map(w => w.length), loads: v.wheels.map(w => w.load) });
    }
    assert(v.uprightness > .9, name + ': unstable slow articulation');
    assert(Math.hypot(v.pos.x, v.pos.z) < .2, name + ': moved off the test platform');
    variants.push({ name, runtime: name === 'before' ? baseline.releaseCommit : 'current',
      tyreDiameter: spec.wheelRadius * 2, track: spec.track,
      travel: spec.restLength - spec.minLength, settled, supportedHeight, maxRollDegrees, samples });
    phys.world.free();
  }
  assert(variants[1].supportedHeight > variants[0].supportedHeight + .025, id + ': no useful articulation gain');
  vehicles.push({ id, variants });
}
const result = { recordedAt: new Date().toISOString(), toyotaReferenceUnchanged: true, releaseCommit: baseline.releaseCommit,
  method: 'Before uses the prior published release physics and specifications; after uses the current physics and specifications. Both settle 4 s on a flat floor, then the front-left platform rises 0–0.50 m over 10 s at 60 Hz. Supported height requires all four tyres grounded with >100 N load. This compares complete released/current vehicle systems, not just spring settings or a real-world RTI rating.',
  vehicles };
writeFileSync(output, JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify(vehicles.map(v => ({ id: v.id, variants: v.variants.map(p => ({
  name: p.name, supportedHeight: p.supportedHeight, bodyHeight: p.settled.bodyHeight,
  travel: p.travel, bumpReserve: p.settled.bumpReserve, sag: p.settled.sag,
})) })), null, 2));
