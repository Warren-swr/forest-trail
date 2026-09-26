// Simple path-following driver used for automated playtests and the debug API.
import type { Path2 } from './world/spline';
import type { Vehicle, DriveInput } from './physics/vehicle';
import { rotate, v3 } from './physics/vmath';
import { clamp } from './world/noise';

export class Autopilot {
  s = 0;
  targetKmh = 22;
  /** optional speed limit along the path (terrain features), km/h */
  limit: ((s: number) => number) | null = null;
  /** optional grade lookup (degrees uphill ahead) for automatic low range */
  grade: ((s: number) => number) | null = null;
  autoGear = false;
  private lowHold = 0;
  private f = v3();
  constructor(public path: Path2, public closed = true) {}

  reset(x: number, z: number) {
    this.s = this.path.nearest(x, z).s;
  }

  update(v: Vehicle, out: DriveInput): DriveInput {
    const p = v.pos;
    const near = this.path.nearest(p.x, p.z, this.s, 30);
    this.s = near.s;
    const kmh = v.forwardSpeed * 3.6;
    const look = 5 + Math.abs(kmh) * 0.35;
    let ls = this.s + look;
    if (this.closed) ls = ls % this.path.length;
    else ls = Math.min(ls, this.path.length);
    const t = this.path.at(ls);
    rotate(this.f, v.rot, 0, 0, -1);
    const dx = t.x - p.x, dz = t.z - p.z;
    const fx = this.f.x, fz = this.f.z;
    // right = (-fz, fx)?? with +X east/+Z south and forward -Z, right is +X: right = (-fz, fx) → (1,0) for f=(0,-1)
    const rx = -fz, rz = fx;
    const lat = dx * rx + dz * rz;
    const fwd = dx * fx + dz * fz;
    const ang = Math.atan2(lat, Math.max(0.1, fwd));
    out.steer = clamp(ang * 2.2, -1, 1);
    // slow down in curves
    const far = this.path.at(this.closed ? (this.s + 18) % this.path.length : Math.min(this.s + 18, this.path.length));
    const turn = Math.abs(Math.atan2(far.tx * t.tz - far.tz * t.tx, far.tx * t.tx + far.tz * t.tz));
    let target = this.targetKmh * clamp(1.2 - turn * 1.1, 0.45, 1);
    const lim = this.limit ? this.limit(this.s) : Infinity;
    target = Math.min(target, lim);
    if (this.autoGear) {
      const g = this.grade ? Math.max(this.grade(this.s), this.grade(this.s + 10)) : 0;
      if (lim <= 10 || g > 12) this.lowHold = 3;
      else this.lowHold -= 1 / 60;
      v.gear = this.lowHold > 0 ? 'low' : 'high';
    }
    out.drive = clamp((target - kmh) * 0.25, -1, 1);
    if (fwd < 0) out.drive = 0.6;
    out.handbrake = false;
    out.digital = false;
    return out;
  }
}
