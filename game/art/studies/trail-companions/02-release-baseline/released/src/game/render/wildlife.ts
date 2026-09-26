// Wildlife: deer herds graze in the meadows (head down, look up, wander) and
// bolt away from the car; eagles circle high over the valley, flapping now
// and then. Both are procedurally animated node hierarchies from the GLBs.
import * as pc from 'playcanvas';
import type { ModelLibrary } from './models';
import type { Terrain } from '../world/terrain';
import { DEER_HERDS, EAGLES } from '../world/layout';
import { mulberry32 } from '../world/noise';

type DeerMode = 'graze' | 'look' | 'walk' | 'flee';

interface Deer {
  root: pc.Entity;
  neck: pc.Entity | null;
  legs: (pc.Entity | null)[];
  home: [number, number, number];
  x: number;
  z: number;
  yaw: number;
  mode: DeerMode;
  t: number;
  phase: number;
  speed: number;
  neckPitch: number;
  target: [number, number];
  calm: number;
}

interface Eagle {
  root: pc.Entity;
  wings: (pc.Entity | null)[];
  cx: number;
  cz: number;
  r: number;
  h: number;
  a: number;
  dir: number;
  flapT: number;
}

const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));

export class Wildlife {
  deer: Deer[] = [];
  eagles: Eagle[] = [];
  private rnd = mulberry32(777);
  private time = 0;

  constructor(app: pc.AppBase, lib: ModelLibrary, private T: Terrain) {
    const rnd = this.rnd;
    const make = (name: string) => {
      const m = lib.models.get(name);
      if (!m?.container) return null;
      const e = m.container.instantiateRenderEntity();
      for (const r of e.findComponents('render') as pc.RenderComponent[]) { r.castShadows = true; r.receiveShadows = true; }
      app.root.addChild(e);
      return e;
    };
    for (const [cx, cz, radius, count] of DEER_HERDS) {
      for (let i = 0; i < count; i++) {
        const root = make(i === 0 ? 'deer_stag' : 'deer_doe');
        if (!root) continue;
        const a = rnd() * Math.PI * 2, d = rnd() * radius * 0.6;
        const x = cx + Math.cos(a) * d, z = cz + Math.sin(a) * d;
        const find = (n: string) => root.findByName(n) as pc.Entity | null;
        this.deer.push({
          root, neck: find('Neck'), legs: ['LegFL', 'LegFR', 'LegRL', 'LegRR'].map(find),
          home: [cx, cz, radius], x, z, yaw: rnd() * 6.28, mode: 'graze', t: rnd() * 5, phase: rnd() * 6,
          speed: 0, neckPitch: 0, target: [x, z], calm: 0,
        });
      }
    }
    for (const [cx, cz, r, h] of EAGLES) {
      const root = make('eagle');
      if (!root) continue;
      const find = (n: string) => root.findByName(n) as pc.Entity | null;
      this.eagles.push({ root, wings: [find('WingL'), find('WingR')], cx, cz, r, h, a: rnd() * 6.28, dir: rnd() < 0.5 ? 1 : -1, flapT: rnd() * 6 });
    }
  }

  update(dt: number, car: { x: number; z: number; speed: number }, cam: pc.Vec3) {
    this.time += dt;
    const T = this.T;
    for (const d of this.deer) {
      const far = Math.hypot(d.x - cam.x, d.z - cam.z) > 220;
      d.t -= dt;
      const dc = Math.hypot(d.x - car.x, d.z - car.z);
      const scared = dc < 15 + Math.min(car.speed, 10) * 1.2;
      if (scared && d.mode !== 'flee') {
        d.mode = 'flee';
        d.t = 4 + this.rnd() * 2;
        const away = Math.atan2(-(d.x - car.x), -(d.z - car.z));
        d.yaw = away + Math.PI + (this.rnd() - 0.5) * 0.8;
      }
      let targetSpeed = 0, neck = 0;
      switch (d.mode) {
        case 'graze':
          neck = 1;
          if (d.t <= 0) { d.mode = this.rnd() < 0.5 ? 'look' : 'walk'; d.t = 2 + this.rnd() * 3; this.pickTarget(d); }
          break;
        case 'look':
          neck = -0.15;
          if (d.t <= 0) { d.mode = 'graze'; d.t = 4 + this.rnd() * 6; }
          break;
        case 'walk': {
          targetSpeed = 0.7;
          neck = 0.2;
          const want = Math.atan2(-(d.target[0] - d.x), -(d.target[1] - d.z));
          d.yaw += wrap(want - d.yaw) * Math.min(1, dt * 1.5);
          if (d.t <= 0 || Math.hypot(d.target[0] - d.x, d.target[1] - d.z) < 1) { d.mode = 'graze'; d.t = 5 + this.rnd() * 6; }
          break;
        }
        case 'flee':
          targetSpeed = 7.5;
          neck = -0.3;
          if (d.t <= 0 && !scared) { d.mode = 'look'; d.t = 3; d.calm = 0; }
          break;
      }
      // drift back towards the meadow once calm
      if (d.mode !== 'flee' && Math.hypot(d.x - d.home[0], d.z - d.home[1]) > d.home[2] * 1.3) {
        d.mode = 'walk'; d.target = [d.home[0], d.home[1]]; d.t = 12;
      }
      d.speed += (targetSpeed - d.speed) * Math.min(1, dt * (d.mode === 'flee' ? 3 : 1.5));
      d.neckPitch += (neck - d.neckPitch) * Math.min(1, dt * 2.5);
      const nx = d.x - Math.sin(d.yaw) * d.speed * dt, nz = d.z - Math.cos(d.yaw) * d.speed * dt;
      // do not walk into water or onto the road while grazing
      if (T.waterDepthAt(nx, nz) < 0.15) { d.x = nx; d.z = nz; } else d.yaw += Math.PI * 0.5;
      if (far) { d.root.enabled = false; continue; }
      d.root.enabled = true;
      d.phase += dt * (d.speed > 3 ? d.speed * 1.35 : d.speed * 4.2);
      const bob = d.speed > 3 ? Math.abs(Math.sin(d.phase)) * 0.22 : 0;
      d.root.setPosition(d.x, T.heightAt(d.x, d.z) + bob, d.z);
      d.root.setEulerAngles(d.speed > 3 ? Math.sin(d.phase * 2) * 4 : 0, (d.yaw * 180) / Math.PI, 0);
      if (d.neck) d.neck.setLocalEulerAngles(d.neckPitch * 58 + Math.sin(this.time * 0.7 + d.phase) * 3 * (d.mode === 'graze' ? 1 : 0), d.mode === 'look' ? Math.sin(this.time * 0.9 + d.phase) * 25 : 0, 0);
      const amp = d.speed > 3 ? 42 : 24 * Math.min(1, d.speed / 0.7);
      const ph = [0, Math.PI, Math.PI * (d.speed > 3 ? 0.15 : 1), d.speed > 3 ? Math.PI * 1.15 : 0];
      d.legs.forEach((l, i) => l?.setLocalEulerAngles(Math.sin(d.phase + ph[i]) * amp, 0, 0));
    }
    for (const e of this.eagles) {
      const speed = 11;
      e.a += (e.dir * speed * dt) / e.r;
      const x = e.cx + Math.cos(e.a) * e.r, z = e.cz + Math.sin(e.a) * e.r;
      const y = Math.max(T.heightAt(x, z) + 25, e.h) + Math.sin(this.time * 0.3 + e.cx) * 3;
      // tangent direction of travel
      const tx = -Math.sin(e.a) * e.dir, tz = Math.cos(e.a) * e.dir;
      const yaw = Math.atan2(-tx, -tz);
      e.root.setPosition(x, y, z);
      e.root.setEulerAngles(-2, (yaw * 180) / Math.PI, e.dir * 22);
      e.flapT -= dt;
      if (e.flapT < -1.6) e.flapT = 4 + this.rnd() * 5;
      const flap = e.flapT < 0 ? Math.sin(this.time * 9) * 32 : 6 + Math.sin(this.time * 1.3) * 2;
      e.wings[0]?.setLocalEulerAngles(0, 0, flap);
      e.wings[1]?.setLocalEulerAngles(0, 0, -flap);
    }
  }

  private pickTarget(d: Deer) {
    const a = this.rnd() * Math.PI * 2, r = this.rnd() * d.home[2] * 0.7;
    d.target = [d.home[0] + Math.cos(a) * r, d.home[1] + Math.sin(a) * r];
  }
}
