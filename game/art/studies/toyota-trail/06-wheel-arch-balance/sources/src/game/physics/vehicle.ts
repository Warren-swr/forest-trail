// Custom 4x4 vehicle on a Rapier rigid body.
// Each wheel is a circle probed by several rays along its lower arc so that
// steps and rock edges push back and can be climbed. Suspension is a spring +
// bump/rebound damper with a stiff bump stop; tyres use a brush/relaxation
// model laterally and a friction-capped stiction model for brakes, both
// limited by a friction circle scaled by surface grip.
import { RAPIER, G_CHASSIS, G_STATIC, G_TERRAIN, G_WALL, groups, type Physics } from './physics';
import { PHYS_DT, SURFACES, UPGRADE_ALL_MU, UPGRADE_MUD_MU, VEHICLE, type VehicleSpec } from '../config';
import { clamp, lerp, smoothstep } from '../world/noise';
import { addScaled, copy, cross, dot, normalize, rotate, set, v3, type Q4, type V3 } from './vmath';
import type { SurfaceKind } from '../world/layout';

export type Gear = 'high' | 'low';

export interface DriveInput {
  /** -1..1: W positive, S negative (keyboard gives ±1, gamepad analog) */
  drive: number;
  /** analog brake override for gamepad (0..1), added to S logic */
  steer: number;
  handbrake: boolean;
  /** true when the steering input is digital (keyboard) */
  digital: boolean;
}

export interface WheelState {
  /** body-space hardpoint */
  hp: V3;
  front: boolean;
  left: boolean;
  steer: number;
  length: number;
  prevLength: number;
  grounded: boolean;
  contact: V3;
  normal: V3;
  load: number;
  latDisp: number;
  longDisp: number;
  spin: number;
  prevSpin: number;
  prevSteer: number;
  omega: number;
  spinning: boolean;
  sliding: boolean;
  slipAmount: number;
  surface: SurfaceKind;
  mud: number;
  gravel: number;
  water: number;
  onStatic: boolean;
  /** compression speed (m/s, positive = compressing) */
  compVel: number;
}

const SHOULDERS = [-.38, -.19, 0, .19, .38];
const CENTRE = [0];
const ARC = [-0.95, -0.6, -0.3, 0, 0.3, 0.6, 0.95]; // forward offset as fraction of radius

export class Vehicle {
  body: RAPIER.RigidBody;
  wheels: WheelState[] = [];
  gear: Gear = 'high';
  /** +1 forward, -1 reverse */
  dir = 1;
  throttle = 0;
  brake = 0;
  steerAngle = 0;
  handbrake = false;
  mudUpgrade = false;
  /** slower keyboard throttle build-up (accessibility option) */
  fineThrottle = false;
  speed = 0;
  forwardSpeed = 0;
  stoppedTime = 0;
  bodyWater = 0;
  deepWaterTime = 0;
  airTime = 0;
  groundedCount = 0;
  /** extra external force this step (winch), world, applied at point */
  private ext: { f: V3; p: V3 }[] = [];
  /** interpolation snapshots */
  prevPos = v3();
  prevRot: Q4 = { x: 0, y: 0, z: 0, w: 1 };
  pos = v3();
  rot: Q4 = { x: 0, y: 0, z: 0, w: 1 };
  /** impact events for audio/camera (0..1) */
  impact = 0;
  scrape = 0;
  engineLoad = 0;
  /** Axle colliders follow suspension travel instead of remaining welded to the body. */
  private axleColliders: RAPIER.Collider[] = [];

  // scratch
  private up = v3(); private fwd = v3(); private right = v3();
  private com = v3(); private linv = v3(); private angv = v3();
  private t0 = v3(); private t1 = v3(); private t2 = v3(); private t3 = v3(); private tn = v3();
  private wf = v3(); private ws = v3(); private hpW = v3(); private cW = v3(); private pW = v3();

  constructor(private phys: Physics, x: number, y: number, z: number, yaw: number, readonly spec: VehicleSpec = VEHICLE) {
    const C = spec;
    const world = phys.world;
    const q = { x: 0, y: Math.sin(yaw / 2), z: 0, w: Math.cos(yaw / 2) };
    const desc = RAPIER.RigidBodyDesc.dynamic()
      .setTranslation(x, y, z)
      .setRotation(q)
      .setCcdEnabled(true)
      .setLinearDamping(0.02)
      .setAngularDamping(0.25)
      .setAdditionalMassProperties(C.mass, { x: C.com[0], y: C.com[1], z: C.com[2] }, { x: C.inertia[0], y: C.inertia[1], z: C.inertia[2] }, { x: 0, y: 0, z: 0, w: 1 });
    this.body = world.createRigidBody(desc);
    const g = groups(G_CHASSIS, G_TERRAIN | G_STATIC | G_WALL);
    for (const b of C.colliders) {
      world.createCollider(
        RAPIER.ColliderDesc.cuboid(b.half[0], b.half[1], b.half[2]).setTranslation(b.at[0], b.at[1], b.at[2])
          .setDensity(0).setFriction(b.friction ?? 0.35).setRestitution(0.05).setCollisionGroups(g),
        this.body,
      );
    }
    // solid axles as low rounded pieces (diff pumpkins)
    const axle = (z: number) =>
      world.createCollider(
        RAPIER.ColliderDesc.capsule(C.axleHalf, 0.09).setRotation({ x: 0, y: 0, z: Math.SQRT1_2, w: Math.SQRT1_2 }).setTranslation(0, 0.02, z).setDensity(0).setFriction(0.3).setCollisionGroups(g),
        this.body,
      );
    this.axleColliders = [axle(-C.wheelBase / 2), axle(C.wheelBase / 2)];

    for (let i = 0; i < 4; i++) {
      const front = i < 2;
      const left = i % 2 === 0;
      const staticLen = C.hardpointY;
      this.wheels.push({
        hp: v3((left ? -1 : 1) * C.track / 2, C.hardpointY, (front ? -1 : 1) * C.wheelBase / 2),
        front, left, steer: 0,
        length: staticLen, prevLength: staticLen,
        grounded: false, contact: v3(), normal: v3(0, 1, 0), load: 0,
        latDisp: 0, longDisp: 0, spin: 0, prevSpin: 0, prevSteer: 0, omega: 0,
        spinning: false, sliding: false, slipAmount: 0,
        surface: 'dirt', mud: 0, gravel: 0, water: 0, onStatic: false, compVel: 0,
      });
    }
    this.snapshot();
    this.snapshot();
  }

  /** queue an external force (world space) for the next step */
  addForce(f: V3, p: V3) {
    this.ext.push({ f: { ...f }, p: { ...p } });
  }

  /** place the body; when a ground normal is given the car is tilted to match it */
  teleport(x: number, y: number, z: number, yaw: number, normal?: V3) {
    const C = this.spec;
    let q: Q4 = { x: 0, y: Math.sin(yaw / 2), z: 0, w: Math.cos(yaw / 2) };
    if (normal) {
      // shortest rotation from +Y to the normal, applied after the yaw
      const nx = normal.x, ny = normal.y, nz = normal.z;
      const ax = nz, az = -nx; // (0,1,0) x n
      const w = 1 + ny;
      const l = Math.hypot(ax, w, az);
      const t = { x: ax / l, y: 0, z: az / l, w: w / l };
      q = {
        w: t.w * q.w - t.y * q.y,
        x: t.x * q.w - t.z * q.y,
        y: t.w * q.y + t.y * q.w,
        z: t.z * q.w + t.x * q.y,
      };
    }
    this.body.setTranslation({ x, y, z }, true);
    this.body.setRotation(q, true);
    this.body.setLinvel({ x: 0, y: 0, z: 0 }, true);
    this.body.setAngvel({ x: 0, y: 0, z: 0 }, true);
    for (const w of this.wheels) {
      w.latDisp = 0; w.longDisp = 0; w.omega = 0; w.length = C.hardpointY; w.prevLength = w.length;
      w.spinning = false; w.sliding = false;
      w.steer = 0; w.prevSteer = 0; w.prevSpin = w.spin;
      w.grounded = false; w.load = 0; w.compVel = 0;
    }
    this.throttle = 0; this.steerAngle = 0; this.dir = 1; this.deepWaterTime = 0;
    this.snapshot();
    this.snapshot();
  }

  snapshot() {
    copy(this.prevPos, this.pos);
    this.prevRot.x = this.rot.x; this.prevRot.y = this.rot.y; this.prevRot.z = this.rot.z; this.prevRot.w = this.rot.w;
    const t = this.body.translation();
    const r = this.body.rotation();
    set(this.pos, t.x, t.y, t.z);
    this.rot.x = r.x; this.rot.y = r.y; this.rot.z = r.z; this.rot.w = r.w;
  }

  /** heading yaw of the body (0 = facing -Z) */
  get yaw(): number {
    rotate(this.t0, this.rot, 0, 0, -1);
    return Math.atan2(-this.t0.x, -this.t0.z);
  }

  /** body up vector y component (1 = level) */
  get uprightness(): number {
    rotate(this.t0, this.rot, 0, 1, 0);
    return this.t0.y;
  }

  // ------------------------------------------------------------- driver

  private updateDriver(inp: DriveInput, dt: number) {
    const C = this.spec;
    const vf = this.forwardSpeed;
    const want = clamp(inp.drive, -1, 1);
    let thr = 0;
    let brk = 0;
    const moving = Math.abs(vf) > 0.6;
    if (Math.abs(vf) < 0.35) this.stoppedTime += dt; else this.stoppedTime = 0;
    if (want > 0.05) {
      if (this.dir < 0 && vf < -0.35) brk = want;
      else if (this.dir < 0 && this.stoppedTime < 0.2) brk = want;
      else { this.dir = 1; thr = want; }
    } else if (want < -0.05) {
      if (this.dir > 0 && vf > 0.35) brk = -want;
      else if (this.dir > 0 && this.stoppedTime < 0.25) brk = -want;
      else { this.dir = -1; thr = -want; }
    }
    void moving;
    // throttle ramps: keyboard needs progressive application for fine control
    const rise = inp.digital ? dt / (this.fineThrottle ? 1.1 : C.throttleRise) : dt / 0.08;
    const fall = dt / C.throttleFall;
    if (thr > this.throttle) this.throttle = Math.min(thr, this.throttle + rise);
    else this.throttle = Math.max(thr, this.throttle - fall);
    this.brake = brk > this.brake ? Math.min(brk, this.brake + dt / 0.12) : Math.max(brk, this.brake - dt / 0.1);
    this.handbrake = inp.handbrake;

    // steering: speed-sensitive lock + rate limit
    const kmh = Math.abs(vf) * 3.6;
    const maxDeg = lerp(C.steerMaxLow, C.steerMaxHigh, smoothstep(0, C.steerSpeedKmh, kmh));
    const target = clamp(inp.steer, -1, 1) * maxDeg * (Math.PI / 180);
    const cur = this.steerAngle;
    const returning = Math.abs(target) < Math.abs(cur) && Math.sign(target) !== -Math.sign(cur) ? true : target * cur < 0;
    const rate = ((returning ? C.steerReturnRate : C.steerRate) * Math.PI) / 180 * (inp.digital ? 1 : 2.2);
    this.steerAngle = cur + clamp(target - cur, -rate * dt, rate * dt);
    // Ackermann
    const d = this.steerAngle;
    if (Math.abs(d) < 1e-4) {
      for (const w of this.wheels) w.steer = 0;
    } else {
      const R = C.wheelBase / Math.tan(Math.abs(d));
      const inner = Math.atan(C.wheelBase / (R - C.track / 2));
      const outer = Math.atan(C.wheelBase / (R + C.track / 2));
      const s = Math.sign(d);
      // positive steer = turn right (towards +X): right wheel is inner
      this.wheels[0].steer = s * (s > 0 ? outer : inner);
      this.wheels[1].steer = s * (s > 0 ? inner : outer);
      this.wheels[2].steer = 0;
      this.wheels[3].steer = 0;
    }
  }

  // ----------------------------------------------------------- terrain ray

  /** analytic ray vs heightfield (with tyre sink); returns distance or -1 */
  private terrainRay(o: V3, d: V3, maxT: number, sink: number): number {
    const T = this.phys.terrain;
    const f = (t: number) => o.y + d.y * t - (T.heightAt(o.x + d.x * t, o.z + d.z * t) - sink);
    let prev = f(0);
    if (prev <= 0) return 0;
    const step = 0.07;
    let t0 = 0;
    for (let t = step; t <= maxT + step; t += step) {
      const tt = Math.min(t, maxT);
      const v = f(tt);
      if (v <= 0) {
        let a = t0, b = tt;
        for (let k = 0; k < 6; k++) {
          const m = (a + b) / 2;
          if (f(m) > 0) a = m; else b = m;
        }
        return (a + b) / 2;
      }
      prev = v;
      t0 = tt;
      if (tt >= maxT) break;
    }
    return -1;
  }

  // ------------------------------------------------------------------ step

  step(inp: DriveInput, dt = PHYS_DT) {
    const C = this.spec;
    const body = this.body;
    const T = this.phys.terrain;
    const tr = body.translation();
    const q = body.rotation();
    const lv = body.linvel();
    const av = body.angvel();
    set(this.linv, lv.x, lv.y, lv.z);
    set(this.angv, av.x, av.y, av.z);
    rotate(this.up, q, 0, 1, 0);
    rotate(this.fwd, q, 0, 0, -1);
    rotate(this.right, q, 1, 0, 0);
    rotate(this.com, q, C.com[0], C.com[1], C.com[2]);
    this.com.x += tr.x; this.com.y += tr.y; this.com.z += tr.z;
    this.forwardSpeed = dot(this.linv, this.fwd);
    this.speed = Math.hypot(lv.x, lv.y, lv.z);
    // Capture before integrating. snapshot() used to overwrite prevLength after
    // the step, which removed suspension interpolation at 30/120 Hz rendering.
    for (const w of this.wheels) {
      w.prevLength = w.length;
      w.prevSpin = w.spin;
      w.prevSteer = w.steer;
    }
    this.updateDriver(inp, dt);

    const r = C.wheelRadius;
    const maxLen = C.restLength;
    const surfW = { grass: 0, dirt: 0, mud: 0, gravel: 0, rock: 0 };
    const up = this.up;

    // ---- probe wheels
    let grounded = 0;
    let loadSum = 0;
    for (const w of this.wheels) {
      rotate(this.hpW, q, w.hp.x, w.hp.y, w.hp.z);
      this.hpW.x += tr.x; this.hpW.y += tr.y; this.hpW.z += tr.z;
      // wheel heading
      const cs = Math.cos(w.steer), sn = Math.sin(w.steer);
      set(this.wf, this.fwd.x * cs + this.right.x * sn, this.fwd.y * cs + this.right.y * sn, this.fwd.z * cs + this.right.z * sn);
      set(this.ws, this.right.x * cs - this.fwd.x * sn, this.right.y * cs - this.fwd.y * sn, this.right.z * cs - this.fwd.z * sn);
      T.surfaceAt(this.hpW.x, this.hpW.z, surfW);
      const sink = surfW.mud * SURFACES.mud.sink + surfW.grass * SURFACES.grass.sink + surfW.gravel * SURFACES.gravel.sink;
      let bestL = Infinity;
      let bestStatic = false;
      set(this.t3, 0, 0, 0);
      set(this.down, -up.x, -up.y, -up.z);
      for (const a of ARC) {
        const fo = a * r;
        const dropc = Math.sqrt(Math.max(0, r * r - fo * fo));
        // A finite-width tyre must pick up an offset rock at its shoulder.
        // Extra shoulder probes only at the centre of the contact patch keep
        // ray costs bounded (11 probes per wheel instead of a 21-ray grid).
        for (const lateral of a === 0 ? SHOULDERS : CENTRE) {
          addScaled(this.t0, this.hpW, this.wf, fo);
          addScaled(this.t0, this.t0, this.ws, lateral * C.wheelWidth);
          const maxT = maxLen + dropc + 0.02;
          let t = this.terrainRay(this.t0, this.down, maxT, sink);
          let isStatic = false;
          const ts = this.phys.castStatic(this.t0.x, this.t0.y, this.t0.z, this.down.x, this.down.y, this.down.z, maxT, this.tn);
          if (ts >= 0 && (t < 0 || ts < t)) { t = ts; isStatic = true; }
          if (t < 0) continue;
          const L = t - dropc;
          if (L < bestL) {
            bestL = L;
            bestStatic = isStatic;
            addScaled(this.t3, this.t0, this.down, t); // hit point
          }
        }
      }
      w.onStatic = bestStatic;
      if (bestL <= maxLen) {
        w.grounded = true;
        w.length = Math.max(bestL, C.minLength - 0.06);
        copy(w.contact, this.t3);
        if (bestStatic) {
          // circle contact: normal from contact to hub
          addScaled(this.cW, this.hpW, up, -Math.max(bestL, C.minLength));
          set(w.normal, this.cW.x - w.contact.x, this.cW.y - w.contact.y, this.cW.z - w.contact.z);
          normalize(w.normal);
        } else {
          T.normalAt(w.contact.x, w.contact.z, w.normal, 0.45);
          // blend in the edge normal when the limiting ray is far forward/back (steps)
          addScaled(this.cW, this.hpW, up, -Math.max(bestL, C.minLength));
          set(this.t1, this.cW.x - w.contact.x, this.cW.y - w.contact.y, this.cW.z - w.contact.z);
          normalize(this.t1);
          addScaled(w.normal, w.normal, this.t1, 0.35);
          normalize(w.normal);
        }
        grounded++;
      } else {
        w.grounded = false;
        w.length = Math.min(maxLen, w.length + 2.5 * dt);
      }
      w.mud = surfW.mud;
      w.gravel = surfW.gravel;
      w.surface = bestStatic ? 'rock' : dominant(surfW);
      w.water = T.waterDepthAt(this.hpW.x, this.hpW.z);
    }
    this.groundedCount = grounded;
    for (let a = 0; a < 2; a++) {
      const l = this.wheels[a * 2], r = this.wheels[a * 2 + 1];
      const yl = l.hp.y - l.length, yr = r.hp.y - r.length;
      const roll = Math.atan2(yr - yl, C.track);
      this.axleColliders[a].setTranslationWrtParent({ x: 0, y: (yl + yr) / 2 + .02, z: l.hp.z });
      const angle = Math.PI / 2 + roll;
      this.axleColliders[a].setRotationWrtParent({ x: 0, y: 0, z: Math.sin(angle / 2), w: Math.cos(angle / 2) });
    }
    if (grounded === 0) this.airTime += dt; else this.airTime = 0;

    // ---- suspension forces (with anti-roll coupling)
    const comp = this.wheels.map((w) => (w.grounded ? maxLen - w.length : 0));
    const fs: number[] = [0, 0, 0, 0];
    let impact = 0;
    for (let i = 0; i < 4; i++) {
      const w = this.wheels[i];
      if (!w.grounded) { w.load = 0; w.compVel = 0; continue; }
      const vComp = (w.prevLength - w.length) / dt; // positive when compressing
      w.compVel = vComp;
      let f = C.springK * comp[i] + (vComp > 0 ? C.damperBump : C.damperRebound) * vComp;
      if (w.length < C.minLength) {
        const pen = C.minLength - w.length;
        // stiff but bounded so a deep embed never launches the car
        f += Math.min(45000, C.bumpStopK * pen + 9000 * Math.max(0, vComp));
        impact = Math.max(impact, clamp(vComp / 2.5, 0, 1));
      }
      fs[i] = f;
    }
    for (const [a, b, k] of [[0, 1, C.antiRollFront], [2, 3, C.antiRollRear]] as const) {
      if (!this.wheels[a].grounded || !this.wheels[b].grounded) continue;
      const d = (comp[a] - comp[b]) * k;
      fs[a] += d;
      fs[b] -= d;
    }
    for (let i = 0; i < 4; i++) {
      const w = this.wheels[i];
      w.load = Math.max(0, fs[i]);
      loadSum += w.load;
    }
    this.impact = Math.max(this.impact * 0.9, impact);

    // ---- drive force
    const kmh = Math.abs(this.forwardSpeed) * 3.6;
    let peak: number, vmax: number;
    if (this.dir < 0) { peak = C.reversePeak; vmax = C.reverseMaxKmh; }
    else if (this.gear === 'low') { peak = C.lowPeak; vmax = C.lowMaxKmh; }
    else { peak = C.highPeak; vmax = C.highMaxKmh; }
    const vAlong = this.forwardSpeed * this.dir * 3.6;
    const curve = 1 - smoothstep(vmax * 0.72, vmax, vAlong);
    const driveTotal = this.throttle * peak * curve * this.dir;
    const eb = (this.dir < 0 ? C.engineBrakeLow * 0.6 : this.gear === 'low' ? C.engineBrakeLow : C.engineBrakeHigh) * (1 - this.throttle);
    const over = vAlong > vmax ? (vAlong - vmax) * 600 : 0;
    this.engineLoad = this.throttle * curve;
    void kmh;

    // auto hold on gentle slopes when idle so the car does not creep
    const slopeCos = up.y;
    const idle = this.throttle < 0.02 && this.brake < 0.02;
    const hold = idle && Math.abs(this.forwardSpeed) < 0.5 && slopeCos > Math.cos((5 * Math.PI) / 180) ? 0.6 : 0;

    const muMul = this.mudUpgrade ? UPGRADE_ALL_MU : 1;
    let scrape = 0;
    for (let i = 0; i < 4; i++) {
      const w = this.wheels[i];
      const cs = Math.cos(w.steer), sn = Math.sin(w.steer);
      set(this.wf, this.fwd.x * cs + this.right.x * sn, this.fwd.y * cs + this.right.y * sn, this.fwd.z * cs + this.right.z * sn);
      if (!w.grounded || w.load <= 0) {
        // free wheel: spin decays, throttle spins it up
        const target = this.throttle * this.dir * 25;
        w.omega += (target - w.omega) * Math.min(1, dt * (this.throttle > 0 ? 3 : 0.6));
        if (this.brake > 0.1 || (this.handbrake && !w.front)) w.omega *= 0.8;
        w.spin += w.omega * dt;
        w.latDisp *= 0.9; w.longDisp = 0; w.spinning = false; w.sliding = false; w.slipAmount = 0;
        continue;
      }
      const n = w.normal;
      // contact frame
      addScaled(this.t0, this.wf, n, -dot(this.wf, n));
      normalize(this.t0); // longitudinal
      cross(this.ws, n, this.t0); // lateral (points left)
      normalize(this.ws);
      // application point: between hub and contact
      rotate(this.hpW, q, w.hp.x, w.hp.y, w.hp.z);
      this.hpW.x += tr.x; this.hpW.y += tr.y; this.hpW.z += tr.z;
      addScaled(this.cW, this.hpW, up, -Math.max(w.length, C.minLength));
      addScaled(this.pW, this.cW, n, -r * 0.55);
      // point velocity
      set(this.t1, this.pW.x - this.com.x, this.pW.y - this.com.y, this.pW.z - this.com.z);
      cross(this.t2, this.angv, this.t1);
      this.t2.x += this.linv.x; this.t2.y += this.linv.y; this.t2.z += this.linv.z;
      const vLong = dot(this.t2, this.t0);
      const vLat = dot(this.t2, this.ws);

      // surface grip
      T.surfaceAt(w.contact.x, w.contact.z, surfW);
      let mu = 0, roll = 0;
      if (w.onStatic) { mu = SURFACES.rock.mu; roll = SURFACES.rock.roll; }
      else {
        for (const k of ['grass', 'dirt', 'mud', 'gravel', 'rock'] as const) {
          mu += SURFACES[k].mu * surfW[k];
          roll += SURFACES[k].roll * surfW[k];
        }
      }
      if (this.mudUpgrade) mu *= lerp(muMul, UPGRADE_MUD_MU, surfW.mud);
      if (w.water > 0.05) { mu *= 0.9; roll += w.water * 2.5; }
      const N = w.load;
      const fMax = mu * N;

      // lateral brush model
      const relax = Math.abs(vLong) / C.tyreRelax;
      w.latDisp += (vLat - relax * w.latDisp) * dt;
      const dispMax = (fMax / C.tyreLatK) * 1.05;
      w.latDisp = clamp(w.latDisp, -dispMax, dispMax);
      let fLat = -C.tyreLatK * w.latDisp - C.tyreLatDamp * vLat;

      // longitudinal: drive + rolling resistance + engine braking + brakes
      const share = loadSum > 0 ? N / loadSum : 0.25;
      let fDrive = driveTotal * share;
      const fRoll = -Math.tanh(vLong / 0.12) * C.rollResist * N * roll - vLong * (C.mudDrag / 4) * (w.onStatic ? 0 : surfW.mud);
      const fEng = -Math.tanh(vLong / 1.2) * (eb + over) * share;
      const brake = Math.max(this.brake, hold, this.handbrake && !w.front ? 1.2 : 0);
      let fBrake = 0;
      if (brake > 0.01) {
        w.longDisp += vLong * dt;
        const cap = brake * C.brakeMax;
        fBrake = -C.tyreLongK * w.longDisp - 2500 * vLong;
        if (Math.abs(fBrake) > cap) {
          fBrake = Math.sign(fBrake) * cap;
          w.longDisp = -(fBrake + 2500 * vLong) / C.tyreLongK;
        }
      } else {
        w.longDisp = 0;
      }
      // traction limit: demand beyond grip starts wheel spin and grip falls
      if (w.spinning) { if (Math.abs(fDrive) < fMax * 0.62) w.spinning = false; }
      else if (Math.abs(fDrive) > fMax * 0.97 && this.throttle > 0.3) w.spinning = true;
      // spinning costs grip in proportion to how far demand exceeds it
      const excess = fMax > 0 ? Math.abs(fDrive) / fMax - 1 : 0;
      const muEff = w.spinning ? 1 - (1 - C.spinMu) * clamp(0.35 + excess * 1.3, 0, 1) : 1;
      // tyre-road friction carries drive/brake/engine forces; rolling and mud
      // resistance act on top and do not consume grip
      let fLong = fDrive + fEng + fBrake;
      const lim = fMax * muEff;
      const mag = Math.hypot(fLong, fLat);
      let sliding = false;
      if (mag > lim && mag > 0) {
        const s = lim / mag;
        fLong *= s;
        fLat *= s;
        w.latDisp *= Math.max(s, 0.6);
        sliding = Math.abs(vLat) > 0.6 || (brake > 0.5 && Math.abs(vLong) > 0.8);
      }
      // resistance cannot push the wheel backwards past standstill
      fLong += brake > 0.01 ? 0 : fRoll;
      w.sliding = sliding;
      w.slipAmount = clamp((w.spinning ? 0.6 : 0) + (sliding ? Math.min(1, Math.abs(vLat) / 3 + (brake > 0.5 ? 0.4 : 0)) : 0), 0, 1);
      fDrive = 0;

      // wheel rotation for visuals
      const rollOmega = vLong / r;
      if (brake > 0.9 && Math.abs(fBrake) >= brake * C.brakeMax * 0.99 && !w.front === this.handbrake) w.omega *= 0.6;
      else if (w.spinning) w.omega += (rollOmega + this.dir * 14 * this.throttle - w.omega) * Math.min(1, dt * 6);
      else w.omega = rollOmega;
      w.spin += w.omega * dt;

      // apply: normal force along contact normal at the hub, tyre forces lower down
      const J = dt;
      body.applyImpulseAtPoint({ x: n.x * N * J, y: n.y * N * J, z: n.z * N * J }, { x: this.cW.x, y: this.cW.y, z: this.cW.z }, true);
      const fx = this.t0.x * fLong + this.ws.x * fLat;
      const fy = this.t0.y * fLong + this.ws.y * fLat;
      const fz = this.t0.z * fLong + this.ws.z * fLat;
      body.applyImpulseAtPoint({ x: fx * J, y: fy * J, z: fz * J }, { x: this.pW.x, y: this.pW.y, z: this.pW.z }, true);
      if (w.onStatic) scrape = Math.max(scrape, clamp(Math.abs(vLong) / 3, 0, 1) * 0.5);
    }
    this.scrape = scrape;

    // ---- water: depth at the body centre, drag
    const depth = T.waterDepthAt(this.com.x, this.com.z);
    const bodyBottom = this.com.y - 0.55;
    const lvl = T.waterLevelAt(this.com.x, this.com.z);
    this.bodyWater = Number.isNaN(lvl) ? 0 : Math.max(0, lvl - bodyBottom + 0.1);
    if (depth > 0.05) {
      const k = Math.min(depth, 1.2) * 650;
      body.applyImpulse({ x: -this.linv.x * k * dt, y: 0, z: -this.linv.z * k * dt }, true);
    }
    if (depth > C.waterFailDepth) this.deepWaterTime += dt; else this.deepWaterTime = Math.max(0, this.deepWaterTime - dt);

    // aero drag
    const sp = this.speed;
    const dk = 0.45 * sp * dt;
    body.applyImpulse({ x: -this.linv.x * dk, y: -this.linv.y * dk, z: -this.linv.z * dk }, true);

    // external (winch)
    for (const e of this.ext) body.applyImpulseAtPoint({ x: e.f.x * dt, y: e.f.y * dt, z: e.f.z * dt }, e.p, true);
    this.ext.length = 0;
  }

  private down = v3();
}

function dominant(s: { grass: number; dirt: number; mud: number; gravel: number; rock: number }): SurfaceKind {
  let best: SurfaceKind = 'grass', bw = -1;
  for (const k of ['grass', 'dirt', 'mud', 'gravel', 'rock'] as const) if (s[k] > bw) { bw = s[k]; best = k; }
  return best;
}
