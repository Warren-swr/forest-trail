// Headless physics checks: ride height, acceleration, braking, slope hold,
// and a full autopilot lap of the loop. Usage: npx tsx tools/sim-test.ts [lap]
import { Terrain } from '../src/game/world/terrain';
import { Physics, initRapier } from '../src/game/physics/physics';
import { Vehicle, type DriveInput } from '../src/game/physics/vehicle';
import { Autopilot } from '../src/game/autopilot';
import { scatter } from '../src/game/world/scatter';
import { PHYS_DT, VEHICLES, type VehicleId } from '../src/game/config';

const SPEC = VEHICLES[(process.env.VEH ?? 'scout') as VehicleId];

await initRapier();
const terrain = new Terrain();
const phys = new Physics(terrain);
const loop = terrain.roads.find((r) => r.def.id === 'loop')!;
const inp: DriveInput = { drive: 0, steer: 0, handbrake: false, digital: true };

function spawnAt(s: number) {
  const p = loop.path.at(s);
  const yaw = Math.atan2(-p.tx, -p.tz);
  const y = terrain.heightAt(p.x, p.z) + 0.5;
  return new Vehicle(phys, p.x, y, p.z, yaw, SPEC);
}
function run(v: Vehicle, secs: number, fn?: (t: number) => void) {
  const n = Math.round(secs / PHYS_DT);
  for (let i = 0; i < n; i++) {
    fn?.(i * PHYS_DT);
    v.step(inp);
    phys.step();
    v.snapshot();
  }
}
const fmt = (x: number, d = 2) => x.toFixed(d);
const mode = process.argv[2] ?? 'basic';

if (mode === 'basic') {
  const v = spawnAt(20);
  run(v, 3);
  const gh = terrain.heightAt(v.pos.x, v.pos.z);
  console.log(`settle: body y above ground ${fmt(v.pos.y - gh)} lens ${v.wheels.map((w) => fmt(w.length)).join(' ')} loads ${v.wheels.map((w) => w.load.toFixed(0)).join(' ')} speed ${fmt(v.speed)}`);
  inp.drive = 1;
  let t10 = -1, t20 = -1;
  run(v, 12, (t) => {
    const k = v.forwardSpeed * 3.6;
    if (t10 < 0 && k > 10) t10 = t;
    if (t20 < 0 && k > 20) t20 = t;
  });
  console.log(`accel: 0-10 ${fmt(t10)} s, 0-20 ${fmt(t20)} s, after 12 s ${fmt(v.forwardSpeed * 3.6, 1)} km/h`);
  inp.drive = -1;
  const x0 = v.pos.x, z0 = v.pos.z;
  let tStop = -1;
  run(v, 4, (t) => { if (tStop < 0 && v.forwardSpeed < 0.3) tStop = t; });
  console.log(`brake: stop in ${fmt(tStop)} s, dist ${fmt(Math.hypot(v.pos.x - x0, v.pos.z - z0))} m; then reverse ${fmt(v.forwardSpeed * 3.6, 1)} km/h`);
  inp.drive = 1;
  run(v, 0.6);
  // brake to a stop, then release
  inp.drive = -1;
  for (let i = 0; i < 300 && Math.abs(v.forwardSpeed) > 0.2; i++) run(v, PHYS_DT);
  inp.drive = 0;
  run(v, 1);
  console.log(`after release: ${fmt(v.forwardSpeed * 3.6, 2)} km/h`);
  const px = v.pos.x, pz = v.pos.z;
  run(v, 5);
  console.log(`idle creep over 5 s: ${fmt(Math.hypot(v.pos.x - px, v.pos.z - pz), 3)} m`);
  // steering
  inp.drive = 0.7; inp.steer = 1;
  run(v, 6);
  console.log(`full lock at ${fmt(v.forwardSpeed * 3.6, 1)} km/h: yaw rate ${fmt(v.body.angvel().y, 2)} rad/s upright ${fmt(v.uprightness, 3)}`);
  inp.steer = 0; inp.drive = 0;
}

if (mode === 'lap') {
  if (process.env.FULL) {
    // all static colliders: trees, rocks, props, bridge, logs
    const sc = scatter(terrain);
    phys.addCylinders(sc.cylinders);
    phys.addBoxes(sc.boxes);
    phys.addOriented(sc.areas.oriented);
    phys.addCapsules(sc.areas.capsules);
  }
  const v = spawnAt(10);
  const ap = new Autopilot(loop.path, true);
  ap.limit = (s) => terrain.featureLimit('loop', s);
  ap.reset(v.pos.x, v.pos.z);
  const start = ap.s;
  let travelled = 0, lastS = ap.s, t = 0, stuck = 0, maxStuck = 0, resets = 0;
  let minUp = 1, maxKmh = 0, lastLog = 0;
  const timeLimit = 900;
  while (t < timeLimit) {
    ap.update(v, inp);
    v.step(inp);
    phys.step();
    v.snapshot();
    t += PHYS_DT;
    let ds = ap.s - lastS;
    if (ds < -loop.path.length / 2) ds += loop.path.length;
    if (ds > loop.path.length / 2) ds -= loop.path.length;
    travelled += ds; lastS = ap.s;
    minUp = Math.min(minUp, v.uprightness);
    maxKmh = Math.max(maxKmh, v.forwardSpeed * 3.6);
    if (Math.abs(v.forwardSpeed) < 0.5) stuck += PHYS_DT; else stuck = 0;
    maxStuck = Math.max(maxStuck, stuck);
    if (stuck > 8 || v.uprightness < 0.3) {
      const p = loop.path.at((ap.s + 6) % loop.path.length);
      console.log(`  !! reset at s=${ap.s.toFixed(0)} (${v.pos.x.toFixed(0)},${v.pos.z.toFixed(0)}) up=${fmt(v.uprightness)} surf=${v.wheels.map((w) => w.surface).join(',')}`);
      v.teleport(p.x, terrain.heightAt(p.x, p.z) + 0.6, p.z, Math.atan2(-p.tx, -p.tz));
      ap.reset(p.x, p.z); lastS = ap.s; stuck = 0; resets++;
    }
    if (t - lastLog > 30) {
      lastLog = t;
      console.log(`t=${t.toFixed(0)} s=${ap.s.toFixed(0)} travelled=${travelled.toFixed(0)} kmh=${fmt(v.forwardSpeed * 3.6, 1)} pos=(${v.pos.x.toFixed(0)},${v.pos.z.toFixed(0)})`);
    }
    if (travelled >= loop.path.length - 5) break;
  }
  console.log(`lap: ${travelled.toFixed(0)}/${loop.path.length.toFixed(0)} m in ${t.toFixed(0)} s, resets ${resets}, maxStuck ${fmt(maxStuck)} s, minUp ${fmt(minUp)}, max ${fmt(maxKmh, 1)} km/h`);
  void start;
}

if (mode === 'creep') {
  const v = spawnAt(20);
  run(v, 3);
  inp.drive = -1;
  run(v, 4);
  console.log('reverse', fmt(v.forwardSpeed * 3.6));
  inp.drive = 0;
  for (let i = 0; i < 8; i++) {
    run(v, 0.5);
    console.log(`t=${fmt(i * 0.5 + 0.5)} vf=${fmt(v.forwardSpeed, 3)} thr=${fmt(v.throttle)} brk=${fmt(v.brake)} dir=${v.dir} up.y=${fmt(v.uprightness, 4)} loads=${v.wheels.map((w) => w.load.toFixed(0)).join(',')} long=${v.wheels.map((w) => w.longDisp.toFixed(3)).join(',')}`);
  }
}

if (mode === 'hold') {
  const v = spawnAt(20);
  run(v, 2);
  inp.drive = 1; run(v, 3);
  inp.drive = -1;
  let n = 0;
  while (Math.abs(v.forwardSpeed) > 0.1 && n++ < 400) run(v, PHYS_DT);
  console.log(`stopped vf=${fmt(v.forwardSpeed)} dir=${v.dir} stoppedTime=${fmt(v.stoppedTime)} brake=${fmt(v.brake)}`);
  inp.drive = 0;
  for (let i = 0; i < 6; i++) {
    run(v, 0.5);
    console.log(`t=${fmt(i * 0.5 + 0.5)} vf=${fmt(v.forwardSpeed, 3)} thr=${fmt(v.throttle)} brk=${fmt(v.brake)} dir=${v.dir} up.y=${fmt(v.uprightness, 4)}`);
  }
}

if (mode === 'mud') {
  // flat mud patch C→D and the mud shortcut, stock and upgraded tyres
  for (const upgraded of [false, true]) {
    for (const gear of ['high', 'low'] as const) {
      const v = spawnAt(loop.path.nearest(46, -10).s);
      v.mudUpgrade = upgraded; v.gear = gear;
      run(v, 1.5);
      inp.drive = 1;
      let maxK = 0;
      run(v, 8, () => { maxK = Math.max(maxK, v.forwardSpeed * 3.6); });
      console.log(`mud patch ${upgraded ? 'AT' : 'stock'} ${gear}: max ${fmt(maxK, 1)} km/h, x=${fmt(v.pos.x, 0)} spin=${v.wheels.filter((w) => w.spinning).length}`);
      inp.drive = 0;
      phys.world.removeRigidBody(v.body);
    }
  }
  const mudRoad = terrain.roads.find((r) => r.def.id === 'mudShortcut')!;
  for (const upgraded of [false, true]) {
    for (const thr of [1, 0.8, 0.65]) {
      const p = mudRoad.path.at(8);
      const v = new Vehicle(phys, p.x, terrain.heightAt(p.x, p.z) + 0.5, p.z, Math.atan2(-p.tx, -p.tz), SPEC);
      v.mudUpgrade = upgraded; v.gear = 'low';
      run(v, 1.5);
      inp.drive = thr;
      let t = 0; let done = -1;
      run(v, 60, () => { t += PHYS_DT; if (done < 0 && mudRoad.path.nearest(v.pos.x, v.pos.z).s > mudRoad.path.length - 6) done = t; });
      const s = mudRoad.path.nearest(v.pos.x, v.pos.z).s;
      console.log(`mud shortcut ${upgraded ? 'AT' : 'stock'} low thr ${thr}: ${done > 0 ? `climbed in ${fmt(done, 1)} s` : `stuck at s=${fmt(s, 0)}/${fmt(mudRoad.path.length, 0)}`}`);
      inp.drive = 0;
      phys.world.removeRigidBody(v.body);
    }
  }
}

if (mode === 'mud2') {
  const mudRoad = terrain.roads.find((r) => r.def.id === 'mudShortcut')!;
  const p = mudRoad.path.at(8);
  const v = new Vehicle(phys, p.x, terrain.heightAt(p.x, p.z) + 0.5, p.z, Math.atan2(-p.tx, -p.tz), SPEC);
  v.gear = 'low';
  run(v, 1.5);
  inp.drive = 1;
  for (let i = 0; i < 12; i++) {
    run(v, 2.5);
    const s = mudRoad.path.nearest(v.pos.x, v.pos.z).s;
    console.log(`s=${fmt(s, 0)} v=${fmt(v.forwardSpeed * 3.6, 1)} mud=${v.wheels.map((w) => fmt(w.mud, 2)).join(',')} spin=${v.wheels.map((w) => (w.spinning ? 'S' : '-')).join('')} load=${v.wheels.map((w) => (w.load / 1000).toFixed(1)).join(',')} pitch=${fmt(Math.asin(Math.max(-1, Math.min(1, -(() => { const f = { x: 0, y: 0, z: 0 }; return f; })().y))), 2)}`);
  }
}

if (mode === 'rock') {
  const rockRoad = terrain.roads.find((r) => r.def.id === 'rockShortcut')!;
  for (const upgraded of [false, true]) {
    for (const gear of ['low', 'high'] as const) {
      const p = rockRoad.path.at(1);
      const v = new Vehicle(phys, p.x, terrain.heightAt(p.x, p.z) + 0.5, p.z, Math.atan2(-p.tx, -p.tz), SPEC);
      v.mudUpgrade = upgraded; v.gear = gear;
      run(v, 1.5);
      const ap = new Autopilot(rockRoad.path, false);
      ap.targetKmh = 8;
      ap.reset(v.pos.x, v.pos.z);
      let t = 0, done = -1, minUp = 1;
      run(v, 45, () => {
        ap.update(v, inp);
        t += PHYS_DT;
        minUp = Math.min(minUp, v.uprightness);
        if (done < 0 && ap.s > rockRoad.path.length - 3) done = t;
      });
      console.log(`rock steps ${upgraded ? 'AT' : 'stock'} ${gear}: ${done > 0 ? `through in ${fmt(done, 1)} s` : `stuck at s=${fmt(ap.s, 0)}/${fmt(rockRoad.path.length, 0)}`}, min upright ${fmt(minUp, 2)}`);
      inp.drive = 0; inp.steer = 0;
      phys.world.removeRigidBody(v.body);
    }
  }
}

// trail park course and the canyon bridge with all static colliders, autopilot with auto low range
if (mode === 'park' || mode === 'canyon') {
  const sc = scatter(terrain);
  phys.addCylinders(sc.cylinders);
  phys.addBoxes(sc.boxes);
  phys.addOriented(sc.areas.oriented);
  phys.addCapsules(sc.areas.capsules);
  const road = terrain.roads.find((r) => r.def.id === mode)!;
  const closed = !!road.def.closed;
  const grade = (s: number) => {
    const L = road.path.length;
    const a = road.path.at(closed ? ((s % L) + L) % L : Math.min(Math.max(s, 0), L));
    const b = road.path.at(closed ? (((s + 4) % L) + L) % L : Math.min(Math.max(s + 4, 0), L));
    return (Math.atan2(terrain.heightAt(b.x, b.z) - terrain.heightAt(a.x, a.z), 4) * 180) / Math.PI;
  };
  const p = road.path.at(mode === 'park' ? 4 : 2);
  const v = new Vehicle(phys, p.x, terrain.heightAt(p.x, p.z) + 0.6, p.z, Math.atan2(-p.tx, -p.tz), SPEC);
  run(v, 1.5);
  const ap = new Autopilot(road.path, closed);
  ap.targetKmh = 16;
  ap.autoGear = true;
  ap.limit = (s) => terrain.featureLimit(road.def.id, s);
  ap.grade = grade;
  ap.reset(v.pos.x, v.pos.z);
  let t = 0, dist = 0, minUp = 1, stall = 0, maxStall = 0, lastS = ap.s, lapDone = -1, minY = Infinity;
  const L = road.path.length;
  run(v, 420, () => {
    if (lapDone > 0) { inp.drive = 0; return; }
    ap.update(v, inp);
    t += PHYS_DT;
    minUp = Math.min(minUp, v.uprightness);
    minY = Math.min(minY, v.pos.y - terrain.heightAt(v.pos.x, v.pos.z));
    let ds = ap.s - lastS;
    if (closed && ds < -L / 2) ds += L;
    if (ds > 0) dist += ds;
    lastS = ap.s;
    if (Math.abs(v.forwardSpeed) < 0.3) stall += PHYS_DT; else stall = 0;
    maxStall = Math.max(maxStall, stall);
    if (lapDone < 0 && dist > (closed ? L - 4 : L - 3)) lapDone = t;
    if (process.env.TRACE && Math.round(t / PHYS_DT) % 300 === 0) console.log(`  t=${fmt(t, 0)} s=${fmt(ap.s, 0)} kmh=${fmt(v.forwardSpeed * 3.6, 1)} gear=${v.gear} pos=${fmt(v.pos.x, 1)},${fmt(v.pos.z, 1)} drive=${fmt(inp.drive, 2)} steer=${fmt(inp.steer, 2)} gr=${v.groundedCount} static=${v.wheels.map((w) => (w.onStatic ? 1 : 0)).join('')} yaw=${fmt(v.yaw, 2)}`);
  });
  console.log(`${mode} ${SPEC.id}: ${lapDone > 0 ? `completed ${fmt(dist, 0)} m in ${fmt(lapDone, 1)} s` : `NOT completed, ${fmt(dist, 0)}/${fmt(L, 0)} m`}; min upright ${fmt(minUp, 2)}; longest stop ${fmt(maxStall, 1)} s; lowest body above ground ${fmt(minY, 2)} m`);
}
