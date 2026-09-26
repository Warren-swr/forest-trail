// Asset/physics contract and regressions for tyre shoulders and moving axle colliders.
// Run with npm run test:rig. These checks read the exported GLBs, not generator constants.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { VEHICLES, VEHICLE_ORDER, PHYS_DT } from '../src/game/config';
import { Terrain } from '../src/game/world/terrain';
import { Physics, initRapier, RAPIER, groups, G_STATIC, G_CHASSIS } from '../src/game/physics/physics';
import { Vehicle, type DriveInput } from '../src/game/physics/vehicle';
import { rotate } from '../src/game/physics/vmath';

const results: { vehicle: string; check: string; detail: unknown }[] = [];
const close = (a: number, b: number, epsilon = 1e-5) => assert(Math.abs(a - b) <= epsilon, `${a} != ${b}`);

class FlatTerrain extends Terrain {
  protected build() {
    this.heights.fill(0);
    for (let i = 0; i < this.mat.length; i += 4) this.mat[i] = 255;
  }
}

await initRapier();
const terrain = new FlatTerrain();
for (const id of VEHICLE_ORDER) {
  const spec = VEHICLES[id];
  const info = JSON.parse(readFileSync(`public/assets/models/${spec.model}.json`, 'utf8'));
  close(info.wheelBase, spec.wheelBase);
  close(info.trackX * 2, spec.track);
  close(info.wheelRadius, spec.wheelRadius);
  close(info.wheelWidth, spec.wheelWidth);
  close(info.bodyBox.max[2] - info.bodyBox.min[2], spec.bodyLength, .015);
  assert.equal(info.spring.kind, spec.suspension);
  const rig = JSON.parse(readFileSync(info.rigFile ?? `art/vehicle-${id}-rig.json`, 'utf8'));
  close(rig.bump, spec.hardpointY - (spec.minLength - .06));
  close(rig.droop, spec.restLength - spec.hardpointY);
  const radius = spec.wheelBase / Math.tan(spec.steerMaxLow * Math.PI / 180);
  const innerLock = Math.atan(spec.wheelBase / (radius - spec.track / 2)) * 180 / Math.PI;
  assert(rig.lock >= innerLock, 'Clearance poses must cover the actual inner-wheel steering lock');
  for (let axis = 0; axis < 3; axis++) {
    close(info.lamps.winch[0][axis], spec.winchFront[axis]);
    close(info.lamps.hitch[0][axis], spec.hitchRear[axis]);
  }
  const file = readFileSync(`public/assets/models/${spec.model}.glb`);
  assert.equal(file.readUInt32LE(0), 0x46546c67);
  assert.equal(file.readUInt32LE(8), file.length);
  const jsonLength = file.readUInt32LE(12);
  const gl = JSON.parse(file.toString('utf8', 20, 20 + jsonLength));
  const binStart = 20 + jsonLength + 8;
  const node = (name: string) => {
    const n = gl.nodes.find((n: { name: string }) => n.name === name);
    assert(n, `Missing exported ${name}`);
    return gl.meshes[n.mesh];
  };
  for (const n of ['Body', 'Wheel', 'Body_LOD1', 'Wheel_LOD1', 'AxleFront', 'AxleRear',
    'BrakeFront', 'BrakeRear', 'ShockBody', 'ShockRod', 'Driveshaft']) node(n);
  assert(info.tris.Body_LOD1 < info.tris.Body * .5);
  assert(info.tris.Wheel_LOD1 < info.tris.Wheel * .4);
  const glass = gl.materials.find((m: { name: string }) => m.name === 'Glass');
  if (info.style === 'trail-v2-refinement/1') {
    assert.equal(glass.alphaMode ?? 'OPAQUE', 'OPAQUE');
    close(glass.pbrMetallicRoughness.baseColorFactor[3], 1);
    const paint = gl.materials.find((m: { name: string }) => m.name === 'Paint');
    assert(paint.pbrMetallicRoughness.roughnessFactor >= .5);
    assert(!paint.extensions?.KHR_materials_clearcoat, 'Trail paint should not regain the rejected clearcoat');
  } else {
    node('Glazing'); node('SteeringWheel');
    assert.equal(glass.alphaMode, 'BLEND');
    assert(glass.pbrMetallicRoughness.baseColorFactor[3] < .4);
  }
  const primitive = node('Spring').primitives[0];
  assert.equal(primitive.targets.length, 2);
  const values = (index: number) => {
    const a = gl.accessors[index], view = gl.bufferViews[a.bufferView];
    assert.equal(a.componentType, 5126);
    assert.equal(a.type, 'VEC3');
    return Array.from({ length: a.count }, (_, i) => [0, 1, 2].map(c =>
      file.readFloatLE(binStart + (view.byteOffset ?? 0) + (a.byteOffset ?? 0) + i * (view.byteStride ?? 12) + c * 4)));
  };
  const base = values(primitive.attributes.POSITION);
  const bump = values(primitive.targets[0].POSITION);
  const droop = values(primitive.targets[1].POSITION);
  assert(base.every(v => v.every(Number.isFinite)));
  let eyes = 0, moving = 0;
  for (let i = 0; i < base.length; i++) {
    close(bump[i][0], 0); close(bump[i][2], 0);
    if (spec.suspension === 'leaf' && Math.abs(base[i][2]) > .529) {
      close(bump[i][1], 0); close(droop[i][1], 0); eyes++;
    }
    if (bump[i][1] > .20 && droop[i][1] < -.16) moving++;
  }
  assert(moving > 0, 'Spring must have a real travel morph');
  if (spec.suspension === 'leaf') assert(eyes > 0, 'Leaf eyes stay fixed to the chassis');
  results.push({ vehicle: id, check: 'exported asset contract', detail: { bytes: file.length, morphVertices: moving, fixedLeafEyeVertices: eyes } });

  const phys = new Physics(terrain);
  const v = new Vehicle(phys, 0, spec.wheelRadius + .04, 0, 0, spec);
  const input: DriveInput = { drive: 0, steer: 0, handbrake: false, digital: true };
  const step = () => { v.step(input); phys.step(); v.snapshot(); };
  for (let i = 0; i < 120; i++) step();
  const right = v.wheels[1];
  // A 52 mm ledge lies beneath the tyre shoulder, outside all seven centre rays.
  const obstacle = phys.world.createCollider(RAPIER.ColliderDesc.cuboid(.026, .060, .22)
    .setTranslation(spec.track / 2 + .10, .060, -spec.wheelBase / 2)
    .setCollisionGroups(groups(G_STATIC, G_CHASSIS)));
  let detected = false, maxCompressionDifference = 0;
  for (let i = 0; i < 30; i++) {
    step();
    detected ||= right.onStatic;
    maxCompressionDifference = Math.max(maxCompressionDifference, v.wheels[0].length - right.length);
  }
  assert(detected, `${id}: tyre shoulder missed the narrow ledge`);
  assert(maxCompressionDifference > .025, `${id}: shoulder contact did not compress suspension`);
  const q = v.body.rotation(), t = v.body.translation();
  const offset = { x: 0, y: 0, z: 0 };
  const frontAxle = v.body.collider(v.body.numColliders() - 2);
  const axleY = spec.hardpointY - (v.wheels[0].length + right.length) / 2 + .02;
  rotate(offset, q, 0, axleY, -spec.wheelBase / 2);
  const at = frontAxle.translation();
  close(at.x, t.x + offset.x); close(at.y, t.y + offset.y); close(at.z, t.z + offset.z);
  results.push({ vehicle: id, check: 'shoulder contact and moving axle collider', detail: { maxCompressionDifference, axleY } });
  phys.world.removeCollider(obstacle, true);
  input.drive = 1;
  for (let i = 0; i < 60; i++) step();
  const before = right.spin;
  step();
  close(right.prevSpin, before);
  assert(Math.abs(right.spin - right.prevSpin) > .01, 'snapshot erased the wheel interpolation history');
  results.push({ vehicle: id, check: 'wheel interpolation history', detail: { physicsHz: 1 / PHYS_DT, spinDelta: right.spin - right.prevSpin } });
  phys.world.free();
}
writeFileSync('tools/vehicle-rig-results.json', JSON.stringify({ passed: results.length, results }, null, 2) + '\n');
console.log(`${results.length}/${results.length} vehicle asset and physics checks passed`);
