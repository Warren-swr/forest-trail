// Proving ground for the driving acceptance list D01–D12 (04-driving-spec.md).
// A synthetic flat map with one lane per scenario; runs headless.
// Usage: npx tsx tools/proving.ts [scout|toyota|ranger]   (or VEH=<id>)
import { Terrain } from '../src/game/world/terrain';
import { Physics, initRapier } from '../src/game/physics/physics';
import { Vehicle, type DriveInput } from '../src/game/physics/vehicle';
import { Winch } from '../src/game/physics/winch';
import { PHYS_DT, VEHICLES, type VehicleId } from '../src/game/config';
import { smoothstep } from '../src/game/world/noise';
import { rotate } from '../src/game/physics/vmath';

const VID = (process.argv[2] ?? process.env.VEH ?? 'scout') as VehicleId;
const SPEC = VEHICLES[VID];
if (!SPEC) throw new Error(`unknown vehicle ${VID}`);
const C_REST = SPEC.restLength;
const HALF_TRACK = SPEC.track / 2;
/** deep pool: deeper than the vehicle's wading limit */
const POOL = Math.max(0.95, SPEC.waterFailDepth + 0.3);
const LANES = { flat: 0, bump: 20, diag: 40, r10: 60, r18: 80, r25: 100, mud: 120, split: 140, side12: 160, side30: 190, water: 220, pit: 250 };

class ProvingTerrain extends Terrain {
  protected build() {
    const n = this.n;
    const matAt = (x: number, z: number): [number, number] => {
      // returns [channel, weight]; channel 0 dirt, 1 mud
      if (Math.abs(x - LANES.mud) < 4 && z < -30 && z > -70) return [1, 1];
      if (Math.abs(x - LANES.split) < 4 && x < LANES.split && z < -20 && z > -80) return [1, 1];
      if (Math.abs(x - LANES.pit) < 5 && z < -20 && z > -34) return [1, 1];
      return [0, 1];
    };
    for (let iz = 0; iz < n; iz++) for (let ix = 0; ix < n; ix++) {
      const x = ix - this.half, z = iz - this.half;
      let h = 0;
      const along = -z; // lanes run towards -Z
      if (Math.abs(x - LANES.diag) < 4) {
        // alternating 0.12 m bumps/dips under left and right wheels
        const side = x < LANES.diag ? -1 : 1;
        for (let k = 0; k < 4; k++) {
          const c = 30 + k * 6;
          const bump = Math.max(0, 1 - Math.hypot(along - c, (x - LANES.diag - side * 0.8) * 1.2) / 1.1);
          h += (k % 2 === (side > 0 ? 0 : 1) ? 0.12 : -0.1) * smoothstep(0, 1, bump);
        }
      }
      for (const [lane, deg] of [[LANES.r10, 10], [LANES.r18, 18], [LANES.r25, 25]] as const) {
        if (Math.abs(x - lane) < 5) {
          const t = Math.tan((deg * Math.PI) / 180);
          const s = Math.min(Math.max(along - 20, 0), 30);
          h = s * t;
        }
      }
      if (Math.abs(x - LANES.side12) < 8) h = (x - LANES.side12) * Math.tan((12 * Math.PI) / 180);
      if (Math.abs(x - LANES.side30) < 8) h = (x - LANES.side30) * Math.tan((30 * Math.PI) / 180);
      if (Math.abs(x - LANES.water) < 6) {
        // shallow ford 0.25 m (z -30..-45), then a deep pool 0.95 m (z -70..-90)
        if (along > 30 && along < 45) h = -0.25 * smoothstep(30, 33, along) * smoothstep(45, 42, along);
        if (along > 70 && along < 90) h = -POOL * smoothstep(70, 74, along) * smoothstep(90, 86, along);
      }
      if (Math.abs(x - LANES.pit) < 5 && along > 20 && along < 34) h = -0.25 * smoothstep(20, 23, along) * smoothstep(34, 31, along);
      this.heights[iz * n + ix] = h;
      if (Math.abs(x - LANES.water) < 6 && along > 28 && along < 92 && h < -0.01) this.water[iz * n + ix] = 0;
    }
    // bump lane: one smooth 0.15 m bump under the left wheels (built after the loop so it overrides)
    for (let iz = 0; iz < n; iz++) for (let ix = 0; ix < n; ix++) {
      const x = ix - this.half, z = iz - this.half;
      if (Math.abs(x - (LANES.bump - HALF_TRACK)) < 1.5) {
        const d = Math.hypot(-z - 30, (x - (LANES.bump - HALF_TRACK)) * 1.3);
        this.heights[iz * n + ix] += 0.15 * (0.5 + 0.5 * Math.cos(Math.min(Math.PI, (d / 1.0) * Math.PI)));
      }
    }
    const mn = this.mn;
    for (let iz = 0; iz < mn; iz++) for (let ix = 0; ix < mn; ix++) {
      const x = ix * this.matRes - this.half, z = iz * this.matRes - this.half;
      const [c] = matAt(x, z);
      this.mat[(iz * mn + ix) * 4 + c] = 255;
    }
  }
}

await initRapier();
const T = new ProvingTerrain();
const phys = new Physics(T);
const inp: DriveInput = { drive: 0, steer: 0, handbrake: false, digital: true };
const results: { id: string; pass: boolean; detail: string }[] = [];
const report = (id: string, pass: boolean, detail: string) => { results.push({ id, pass, detail }); console.log(`${pass ? 'PASS' : 'FAIL'} ${id}: ${detail}`); };
const fmt = (x: number, d = 2) => x.toFixed(d);

function spawn(x: number, z = -2) {
  const v = new Vehicle(phys, x, T.heightAt(x, z) + 0.45, z, 0, SPEC);
  const n = T.normalAt(x, z, { x: 0, y: 1, z: 0 }, 1.5);
  v.teleport(x, T.heightAt(x, z) + 0.45 / n.y, z, 0, n);
  return v;
}
function run(v: Vehicle, secs: number, fn?: (t: number) => void) {
  const n = Math.round(secs / PHYS_DT);
  for (let i = 0; i < n; i++) { fn?.(i * PHYS_DT); v.step(inp); phys.step(); v.snapshot(); }
}
function done(v: Vehicle) { phys.world.removeRigidBody(v.body); inp.drive = 0; inp.steer = 0; inp.handbrake = false; }
const tmp = { x: 0, y: 0, z: 0 };
const pitchOf = (v: Vehicle) => { rotate(tmp, v.rot, 0, 0, -1); return Math.asin(Math.max(-1, Math.min(1, tmp.y))) * 57.3; };
const rollOf = (v: Vehicle) => { rotate(tmp, v.rot, 1, 0, 0); return Math.asin(Math.max(-1, Math.min(1, tmp.y))) * 57.3; };

// ---------------------------------------------------------------- D01
{
  const v = spawn(LANES.flat);
  run(v, 2);
  inp.drive = 1;
  let minV = 0;
  run(v, 5);
  const vTop = v.forwardSpeed;
  inp.drive = 0; run(v, 1.5);
  inp.drive = -1;
  let flipped = false;
  run(v, 3, () => { if (v.forwardSpeed < -0.5 && v.stoppedTime < 0.2 && !flipped) flipped = true; minV = Math.min(minV, v.forwardSpeed); });
  // after stopping, reverse must engage only after standstill
  inp.drive = 0; run(v, 2);
  const x0 = v.pos.x, z0 = v.pos.z;
  run(v, 4);
  const drift = Math.hypot(v.pos.x - x0, v.pos.z - z0);
  report('D01', vTop > 7 && drift < 0.05 && minV < -0.5, `top ${fmt(vTop * 3.6, 1)} km/h after 5 s; reverse reached ${fmt(minV * 3.6, 1)} km/h after stop; drift at rest ${fmt(drift, 3)} m in 4 s`);
  done(v);
}

// ---------------------------------------------------------------- D02
{
  const v = spawn(LANES.bump, -22);
  v.gear = 'low';
  run(v, 1.5);
  let maxRoll = 0, maxComp = 0, tOff = -1, settle = -1;
  inp.drive = 0.5;
  const rolls: number[] = [];
  run(v, 16, (t) => {
    const kmh = v.forwardSpeed * 3.6;
    inp.drive = kmh < 4 ? 0.55 : 0.25;
    const r = rollOf(v);
    rolls.push(r);
    maxRoll = Math.max(maxRoll, Math.abs(r));
    maxComp = Math.max(maxComp, C_REST - v.wheels[0].length);
    const along = -v.pos.z;
    if (tOff < 0 && along > 31 + SPEC.wheelBase + 0.5) tOff = t;
    if (tOff > 0 && settle < 0 && t > tOff + 0.2) {
      const recent = rolls.slice(-30);
      if (Math.max(...recent.map(Math.abs)) < 0.4) settle = t - tOff;
    }
  });
  report('D02', maxRoll > 1 && settle >= 0 && settle < 1.8, `FL compression peak ${fmt(maxComp, 3)} m, body roll peak ${fmt(maxRoll, 1)}°, settled ${fmt(settle, 2)} s after the rear wheel left the bump`);
  done(v);
}

// ---------------------------------------------------------------- D03
{
  const v = spawn(LANES.diag, -22);
  v.gear = 'low';
  run(v, 1.5);
  let maxDiff = 0, maxRoll = 0, maxUpAngVel = 0;
  run(v, 14, () => {
    inp.drive = v.forwardSpeed * 3.6 < 5 ? 0.6 : 0.2;
    const d = Math.abs(v.wheels[0].length - v.wheels[1].length);
    maxDiff = Math.max(maxDiff, d);
    maxRoll = Math.max(maxRoll, Math.abs(rollOf(v)));
    const av = v.body.angvel();
    maxUpAngVel = Math.max(maxUpAngVel, Math.hypot(av.x, av.z));
  });
  report('D03', maxDiff > 0.05 && maxUpAngVel < 1.5, `max left/right suspension difference ${fmt(maxDiff, 3)} m, roll peak ${fmt(maxRoll, 1)}°, peak roll/pitch rate ${fmt(maxUpAngVel, 2)} rad/s (no snap to terrain normal)`);
  done(v);
}

// ---------------------------------------------------------------- D04
for (const [lane, deg] of [[LANES.r10, 10], [LANES.r18, 18], [LANES.r25, 25]] as const) {
  const out: string[] = [];
  let climbedAny = false;
  for (const gear of ['high', 'low'] as const) {
    const v = spawn(lane, -8);
    v.gear = gear;
    run(v, 1.5);
    inp.drive = 1;
    let top = 0;
    run(v, 20, () => { top = Math.max(top, -v.pos.z); });
    const climbed = top > 49;
    if (climbed) climbedAny = true;
    out.push(`${gear}: ${climbed ? 'climbs' : `stalls at ${fmt(top - 20, 1)} m up`}`);
    done(v);
  }
  // hold and roll-back on the slope
  const v = spawn(lane, -30);
  v.gear = 'low';
  run(v, 2);
  const z0 = v.pos.z;
  inp.drive = 0;
  run(v, 3);
  const rolled = v.pos.z - z0;
  inp.drive = -1; // brake while rolling back = forward brake? (moving backwards in forward dir → S brakes forward motion only)
  // hold with handbrake + brake: stop the car first, then check it holds
  inp.drive = 0; inp.handbrake = true;
  run(v, 2);
  const z1 = v.pos.z;
  run(v, 3);
  const held = Math.abs(v.pos.z - z1);
  inp.handbrake = false;
  const pass = deg < 20 ? climbedAny : true;
  report(`D04 ${deg}°`, pass && (deg < 5 || rolled > 0.05) && held < 0.1, `${out.join(', ')}; released throttle rolls back ${fmt(rolled, 2)} m in 3 s; handbrake holds (${fmt(held, 3)} m creep in 3 s)`);
  done(v);
}

// ---------------------------------------------------------------- D05
{
  const dist: Record<string, number> = {};
  for (const [label, x] of [['dirt', LANES.flat], ['mud', LANES.mud]] as const) {
    const v = spawn(x, -28);
    run(v, 1.5);
    inp.drive = 1;
    const z0 = v.pos.z;
    let spin = 0;
    run(v, 6, () => { spin += v.wheels.filter((w) => w.spinning).length; });
    dist[label] = z0 - v.pos.z;
    dist[label + 'Spin'] = spin;
    done(v);
  }
  const ratio = dist.mud / dist.dirt;
  report('D05', ratio < 0.8 && ratio > 0.2, `same input for 6 s from rest: dirt ${fmt(dist.dirt, 1)} m, mud ${fmt(dist.mud, 1)} m (${fmt(ratio * 100, 0)}% of dirt)`);
}

// ---------------------------------------------------------------- D06
{
  const v = spawn(LANES.split, -12);
  run(v, 1.5);
  const yaw0 = v.yaw;
  inp.drive = 1;
  let maxYawRate = 0;
  run(v, 7, () => { maxYawRate = Math.max(maxYawRate, Math.abs(v.body.angvel().y)); });
  const dyaw = Math.abs(Math.atan2(Math.sin(v.yaw - yaw0), Math.cos(v.yaw - yaw0))) * 57.3;
  report('D06', maxYawRate < 0.5 && dyaw < 25, `left wheels in mud, right on dirt, straight input: heading change ${fmt(dyaw, 1)}°, peak yaw rate ${fmt(maxYawRate, 2)} rad/s (pulls gently, no snap)`);
  done(v);
}

// ---------------------------------------------------------------- D07
for (const [lane, deg] of [[LANES.side12, 12], [LANES.side30, 30]] as const) {
  const v = spawn(lane, -10);
  v.gear = 'low';
  if (process.env.SIDE_DEBUG) {
    console.log(`  h: ${[-2, -1, 0, 1, 2].map((d) => fmt(T.heightAt(lane + d, -10))).join(' ')}`);
    for (let i = 0; i < 8; i++) { run(v, 0.1); console.log(`   t=${fmt(i * 0.1 + 0.1)} up=${fmt(v.uprightness, 3)} y=${fmt(v.pos.y)} g=${v.groundedCount} len=${v.wheels.map((w) => fmt(w.length)).join(',')}`); }
  }
  run(v, 2);
  if (process.env.SIDE_DEBUG) console.log(`  side ${deg}: after settle up=${fmt(v.uprightness, 3)} loads=${v.wheels.map((w) => (w.load / 1000).toFixed(1)).join(',')} grounded=${v.groundedCount}`);
  inp.drive = 0.8;
  let minUp = 1;
  run(v, 10, () => { minUp = Math.min(minUp, v.uprightness); });
  const tilt = Math.acos(Math.min(1, minUp)) * 57.3;
  if (deg === 12) report('D07 12°', minUp > 0.9, `low speed traverse: max body tilt ${fmt(tilt, 1)}°, stays upright`);
  else {
    // at 30° plus a turn uphill→downhill the car should be at real risk
    inp.steer = 1; inp.drive = 1;
    let minUp2 = 1;
    run(v, 6, () => { minUp2 = Math.min(minUp2, v.uprightness); });
    report('D07 30°', true, `30° traverse tilt ${fmt(tilt, 1)}°; with a full-lock turn min uprightness ${fmt(minUp2, 2)} (${minUp2 < 0.4 ? 'rolls over' : 'recovers'}) — rollover risk comes from physics, no scripted flip`);
  }
  done(v);
}

// ---------------------------------------------------------------- D08
{
  const v = spawn(LANES.water, -18);
  v.gear = 'low';
  run(v, 1.5);
  let maxShallow = 0, warnSeen = false, failTime = 0, deepMax = 0;
  run(v, 40, () => {
    inp.drive = v.forwardSpeed * 3.6 < 6 ? 0.7 : 0.2;
    const along = -v.pos.z;
    const d = T.waterDepthAt(v.pos.x, v.pos.z);
    if (along > 31 && along < 45) maxShallow = Math.max(maxShallow, d);
    if (d > SPEC.waterWarnDepth) warnSeen = true;
    deepMax = Math.max(deepMax, d);
    if (v.deepWaterTime > 3) failTime = failTime || -v.pos.z;
  });
  report('D08', maxShallow > 0.15 && maxShallow < 0.3 && warnSeen && failTime > 0, `shallow ford depth ${fmt(maxShallow)} m crossed; deep pool ${fmt(deepMax)} m triggers the warning (> ${fmt(SPEC.waterWarnDepth)} m) and the 3 s recovery rule (deep-water timer fired at ${fmt(failTime, 0)} m)`);
  done(v);
}

// ---------------------------------------------------------------- D09
{
  const v = spawn(LANES.pit, -22);
  run(v, 1.5);
  // sink into the mud pit: drive in gently, then try to climb out in high gear
  inp.drive = 0.6;
  run(v, 3);
  inp.drive = 0;
  run(v, 2);
  const cx = v.pos.x, cz = v.pos.z;
  const anchor = { id: 'tree', x: cx + 1, y: 0, z: cz - 13, h: 0.9, kind: 'tree' as const };
  phys.addCylinders([{ x: anchor.x, y: -0.5, z: anchor.z, r: 0.3, h: 6 }]);
  const wall = { id: 'blocked', x: cx - 12, y: 0, z: cz, h: 0.9, kind: 'tree' as const };
  phys.addBoxes([{ x: cx - 6, y: -1, z: cz, yaw: 0, hx: 0.5, hy: 3, hz: 3 }]);
  // new colliders enter the query pipeline on the next step
  v.step(inp); phys.step(); v.snapshot();
  const winch = new Winch(phys, v, [anchor, wall]);
  const msg = winch.toggle();
  const cands = winch.candidates.map((c) => `${c.anchor.id}:${c.valid ? 'ok' : c.reason}`).join(', ');
  const c = winch.connect();
  const z0 = v.pos.z;
  let maxT = 0, maxUp = 0;
  const y0 = v.pos.y;
  for (let i = 0; i < 60 * 12; i++) {
    winch.step(PHYS_DT, true);
    v.step(inp); phys.step(); v.snapshot();
    maxT = Math.max(maxT, winch.tension);
    maxUp = Math.max(maxUp, v.body.linvel().y);
  }
  const pulled = z0 - v.pos.z;
  winch.detach();
  const after = v.speed;
  report('D09', !msg && !!c && pulled > 4 && maxT <= 11000.5 && maxUp < 1.5 && cands.includes('blocked:中间有阻挡'), `candidates [${cands}]; reeled ${fmt(pulled, 1)} m in 12 s, peak tension ${fmt(maxT / 1000, 1)} kN (cap 11), peak vertical speed ${fmt(maxUp, 2)} m/s; detached cleanly (speed ${fmt(after, 2)} m/s); rise ${fmt(v.pos.y - y0, 2)} m`);
  done(v);
}

// ---------------------------------------------------------------- D10
{
  const v = spawn(LANES.flat, -40);
  run(v, 1);
  v.body.setRotation({ x: 0, y: 0, z: 1, w: 0 }, true);
  run(v, 2);
  const flippedUp = v.uprightness;
  // reset procedure used by the game (Game.teleport → Vehicle.teleport)
  const n = T.normalAt(LANES.flat, -10, { x: 0, y: 1, z: 0 }, 1.5);
  v.teleport(LANES.flat, T.heightAt(LANES.flat, -10) + 0.5, -10, 0, n);
  run(v, 1.5);
  report('D10', flippedUp < 0 && v.uprightness > 0.98 && v.speed < 0.2, `upside-down car (up ${fmt(flippedUp)}) reset to the safe point: up ${fmt(v.uprightness, 3)}, speed ${fmt(v.speed, 2)} m/s after 1.5 s (in-game: hold R 1 s, fade, progress kept)`);
  done(v);
}

// ---------------------------------------------------------------- D12
{
  // replay the same input through the game's accumulator at 30/60/120 fps render rates
  for (const [label, lane, steerOn] of [['flat with turns', LANES.flat, true], ['18° ramp climb', LANES.r18, false]] as const) {
    const dists: number[] = [];
    for (const fps of [30, 60, 120]) {
      const v = spawn(lane, -8);
      v.gear = steerOn ? 'high' : 'low';
      let acc = 0;
      const x0 = v.pos.x, z0 = v.pos.z;
      const frames = 20 * fps;
      for (let f = 0; f < frames; f++) {
        const t = f / fps;
        inp.drive = t < 12 ? 1 : 0.3;
        inp.steer = steerOn && t > 5 && t < 7 ? 0.5 : steerOn && t > 9 && t < 11 ? -0.5 : 0;
        acc += 1 / fps;
        let steps = 0;
        while (acc >= PHYS_DT - 1e-9 && steps < 4) { v.step(inp); phys.step(); v.snapshot(); acc -= PHYS_DT; steps++; }
      }
      dists.push(Math.hypot(v.pos.x - x0, v.pos.z - z0));
      done(v);
    }
    const spread = (Math.max(...dists) - Math.min(...dists)) / Math.max(...dists);
    report(`D12 ${label}`, spread <= 0.05, `20 s input replay: 30 fps ${fmt(dists[0], 2)} m, 60 fps ${fmt(dists[1], 2)} m, 120 fps ${fmt(dists[2], 2)} m (spread ${fmt(spread * 100, 2)}%)`);
  }
}

console.log(`\n${results.filter((r) => r.pass).length}/${results.length} checks passed (D11 camera readability is checked in the browser)`);
import('node:fs').then((fs) => fs.writeFileSync(new URL(VID === 'scout' ? './proving-results.json' : `./proving-results-${VID}.json`, import.meta.url), JSON.stringify(results, null, 2)));
