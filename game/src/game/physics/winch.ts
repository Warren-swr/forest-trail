// Winch: pick a front/rear attach point and a designated anchor within range,
// then reel in with a pull-only, force-limited rope.
import type { Vehicle } from './vehicle';
import type { Physics } from './physics';
import type { WinchAnchor } from '../world/scatter';
import { WINCH } from '../config';
import { rotate, v3, type V3 } from './vmath';
import { clamp } from '../world/noise';

export type WinchMode = 'off' | 'select' | 'attached';

export interface AnchorCandidate {
  anchor: WinchAnchor;
  dist: number;
  valid: boolean;
  reason: string | null;
  front: boolean;
  score: number;
}


export class Winch {
  mode: WinchMode = 'off';
  candidates: AnchorCandidate[] = [];
  selected: AnchorCandidate | null = null;
  anchor: WinchAnchor | null = null;
  front = true;
  length = 0;
  tension = 0;
  reeling = false;
  message: string | null = null;
  attachWorld = v3();
  anchorWorld = v3();
  private tmp = v3();

  constructor(private phys: Physics, public v: Vehicle, private anchors: WinchAnchor[]) {}

  attachPoint(front: boolean, out: V3): V3 {
    const a = front ? this.v.spec.winchFront : this.v.spec.hitchRear;
    rotate(out, this.v.rot, a[0], a[1], a[2]);
    out.x += this.v.pos.x; out.y += this.v.pos.y; out.z += this.v.pos.z;
    return out;
  }

  /** E key: enter selection, or detach */
  toggle(): string | null {
    if (this.mode === 'attached') {
      this.detach();
      return '已断开绞盘';
    }
    if (this.mode === 'select') {
      this.mode = 'off';
      return null;
    }
    if (Math.abs(this.v.forwardSpeed) * 3.6 > 2) return '先停稳车辆（低于 2 km/h）再使用绞盘';
    this.mode = 'select';
    this.refresh(null);
    if (!this.candidates.length) return '18 米内没有可用的树干或岩桩';
    return null;
  }

  detach() {
    this.mode = 'off';
    this.anchor = null;
    this.tension = 0;
    this.reeling = false;
  }

  /** recompute candidates; camForward picks the preferred one */
  refresh(camForward: { x: number; z: number } | null) {
    const out: AnchorCandidate[] = [];
    const fwd = this.tmp;
    rotate(fwd, this.v.rot, 0, 0, -1);
    const pf = this.attachPoint(true, v3()), pr = this.attachPoint(false, v3());
    for (const a of this.anchors) {
      const ax = a.x, ay = a.y + a.h, az = a.z;
      const dxC = ax - this.v.pos.x, dzC = az - this.v.pos.z;
      const dc = Math.hypot(dxC, dzC);
      if (dc > WINCH.range + 6) continue;
      const front = dxC * fwd.x + dzC * fwd.z >= 0;
      const p = front ? pf : pr;
      const d = Math.hypot(ax - p.x, ay - p.y, az - p.z);
      let valid = true;
      let reason: string | null = null;
      if (d > WINCH.range) { valid = false; reason = `超出范围（${d.toFixed(0)} m）`; }
      else if (d < 3) { valid = false; reason = '太近'; }
      else if (this.phys.lineBlocked(p.x, p.y, p.z, ax, ay, az)) { valid = false; reason = '中间有阻挡'; }
      let score = -d;
      if (camForward) {
        const l = dc || 1;
        score = (dxC / l) * camForward.x + (dzC / l) * camForward.z - d * 0.01;
      }
      out.push({ anchor: a, dist: d, valid, reason, front, score });
    }
    out.sort((a, b) => b.score - a.score);
    this.candidates = out;
    this.selected = out.find((c) => c.valid) ?? null;
  }

  connect(): string | null {
    const c = this.selected;
    if (!c || !c.valid) return '没有可连接的锚点';
    this.anchor = c.anchor;
    this.front = c.front;
    this.mode = 'attached';
    this.attachPoint(this.front, this.attachWorld);
    this.anchorWorld.x = c.anchor.x; this.anchorWorld.y = c.anchor.y + c.anchor.h; this.anchorWorld.z = c.anchor.z;
    this.length = Math.hypot(this.anchorWorld.x - this.attachWorld.x, this.anchorWorld.y - this.attachWorld.y, this.anchorWorld.z - this.attachWorld.z) + 0.3;
    this.tension = 0;
    return `绞盘已连接${c.anchor.kind === 'tree' ? '树干' : '岩桩'}（${c.front ? '车头' : '车尾'}）· 按住左键或 F 收绳`;
  }

  /** physics step */
  step(dt: number, reel: boolean) {
    if (this.mode !== 'attached' || !this.anchor) { this.tension = 0; return; }
    this.reeling = reel;
    const p = this.attachPoint(this.front, this.attachWorld);
    const a = this.anchorWorld;
    const dx = a.x - p.x, dy = a.y - p.y, dz = a.z - p.z;
    const dist = Math.hypot(dx, dy, dz);
    if (reel) this.length = Math.max(WINCH.minLength, this.length - WINCH.reelSpeed * dt);
    // slack is taken up slowly by the drum when the car rolls towards the anchor
    if (dist < this.length - 0.6) this.length = dist + 0.6;
    const stretch = dist - this.length;
    let target = 0;
    if (stretch > 0) {
      const lv = this.v.body.linvel();
      const closing = -(lv.x * dx + lv.y * dy + lv.z * dz) / (dist || 1);
      target = clamp(WINCH.ropeK * stretch - WINCH.ropeDamp * closing, 0, WINCH.maxForce);
    }
    // smooth force onset so the car never jumps
    this.tension += (target - this.tension) * Math.min(1, dt * 6);
    if (this.tension < 1) return;
    const inv = 1 / (dist || 1);
    let fx = dx * inv * this.tension, fy = dy * inv * this.tension, fz = dz * inv * this.tension;
    // limit lift when the anchor is above the car
    const maxUp = this.tension * 0.3;
    if (fy > maxUp) fy = maxUp;
    this.v.addForce({ x: fx, y: fy, z: fz }, p);
    if (dist > WINCH.range + 4) {
      this.detach();
      this.message = '绳索拉得过长，已自动松开';
    }
    void fx; void fz;
  }
}
