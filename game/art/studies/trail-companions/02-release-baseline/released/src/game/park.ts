// Trail park time trial: drive through the start arch to start the clock,
// pass every checkpoint flag pair in order, and come back through the arch.
// Splits and the best lap are kept in the save.
import type { Game } from './Game';
import type { Journey } from './journey';
import { PARK_GATES } from './world/layout';
import { store } from './store';

interface Gate { x: number; z: number; tx: number; tz: number; s: number }

const GATE_RADIUS = 5.5;

export class TrailPark {
  gates: Gate[] = [];
  running = false;
  time = 0;
  next = 1;
  splits: number[] = [];
  private offCourse = 0;
  private armed = true;
  private lastSplit = 0;

  constructor(private g: Game, private j: Journey) {
    const road = g.terrain.roads.find((r) => r.def.id === 'park');
    if (!road) return;
    for (const [x, z] of PARK_GATES) {
      const q = road.path.nearest(x, z);
      const p = road.path.at(q.s);
      this.gates.push({ x: p.x, z: p.z, tx: p.tx, tz: p.tz, s: q.s });
    }
    this.publish();
  }

  /** passing a gate: close to its centre while moving along the course direction */
  private through(gi: number): boolean {
    const gt = this.gates[gi];
    const v = this.g.vehicle;
    const dx = v.pos.x - gt.x, dz = v.pos.z - gt.z;
    if (dx * dx + dz * dz > GATE_RADIUS * GATE_RADIUS) return false;
    const lv = v.body.linvel();
    return lv.x * gt.tx + lv.z * gt.tz > 0.4;
  }

  cancel(reason: string | null) {
    if (!this.running) return;
    this.running = false;
    this.armed = false;
    if (reason) store.toast(reason, 'warn', 4);
    this.publish();
  }

  update(dt: number) {
    if (!this.gates.length) return;
    const v = this.g.vehicle;
    const g0 = this.gates[0];
    const d0 = Math.hypot(v.pos.x - g0.x, v.pos.z - g0.z);
    if (!this.running) {
      // re-arm once the car has left the start area
      if (d0 > GATE_RADIUS + 4) this.armed = true;
      if (this.armed && this.through(0)) {
        this.running = true;
        this.time = 0;
        this.next = 1;
        this.splits = [];
        this.lastSplit = 0;
        this.offCourse = 0;
        this.armed = false;
        store.toast('训练场计时开始：依次通过每一对旗门', 'info', 3);
        this.publish();
      }
      return;
    }
    this.time += dt;
    // leaving the course cancels the run
    const road = this.g.terrain.roads.find((r) => r.def.id === 'park')!;
    const near = road.path.nearest(v.pos.x, v.pos.z);
    if (near.d > 14) this.offCourse += dt; else this.offCourse = 0;
    if (this.offCourse > 4) { this.cancel('离开训练场赛道，计时取消'); return; }
    if (this.time > 900) { this.cancel('计时超过 15 分钟，已取消'); return; }
    const target = this.next < this.gates.length ? this.next : 0;
    if (this.through(target)) {
      const split = this.time - this.lastSplit;
      this.lastSplit = this.time;
      this.splits.push(split);
      if (target === 0) {
        this.finish();
        return;
      }
      const prevBest = this.j.save.parkSplits[this.splits.length - 1];
      const delta = prevBest ? split - prevBest : null;
      store.toast(`旗门 ${this.next}/${this.gates.length - 1} · ${fmtTime(this.time)}${delta !== null ? `（${delta <= 0 ? '' : '+'}${delta.toFixed(1)} 秒）` : ''}`, delta !== null && delta <= 0 ? 'good' : 'info', 2.5);
      this.next++;
    }
    this.publish();
  }

  private finish() {
    const t = this.time;
    const s = this.j.save;
    const best = s.parkBest;
    const record = best === null || t < best;
    if (record) {
      s.parkBest = t;
      s.parkSplits = [...this.splits];
    }
    this.running = false;
    this.armed = false;
    store.toast(record ? `新纪录！训练场一圈 ${fmtTime(t)}` : `完成一圈 ${fmtTime(t)} · 最佳 ${fmtTime(best!)}`, 'good', 6);
    this.last = t;
    this.j.persist();
    this.publish();
  }

  last: number | null = null;

  private publish() {
    store.set({
      park: {
        running: this.running, time: this.time, split: this.splits.length ? this.splits[this.splits.length - 1] : 0,
        gate: this.next - 1, gates: this.gates.length - 1, best: this.j.save.parkBest, last: this.last, splits: this.splits,
      },
    });
  }
}

export function fmtTime(t: number): string {
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${m}:${s < 10 ? '0' : ''}${s.toFixed(1)}`;
}
