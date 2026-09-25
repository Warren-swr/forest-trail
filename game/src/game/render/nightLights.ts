// Night light sources: campfire, lanterns, lamp posts and windows as clustered
// omni lights that fade in after dusk (the campfire flickers), camp string
// lights drawn as instanced emissive bulbs on a sagging cable, and fireflies
// drifting over the camp and the meadows.
import * as pc from 'playcanvas';
import type { AreaResult, LightDef } from '../world/areas';
import type { Terrain } from '../world/terrain';

/** firefly swarms [x, z, radius, count] */
const SWARMS: [number, number, number, number][] = [[-186, 180, 16, 40], [-22, 12, 18, 36], [140, 60, 22, 40], [-120, 248, 22, 36], [184, 84, 10, 20]];

interface Fly { cx: number; cz: number; r: number; ph: number; sp: number; h: number; blink: number }

interface Live { e: pc.Entity; def: LightDef; seed: number }

export class NightLights {
  private live: Live[] = [];
  private bulbMat: pc.StandardMaterial;
  private cableMat: pc.StandardMaterial;
  private time = 0;
  private night = -1;
  private flies: Fly[] = [];
  private flyVb: pc.VertexBuffer | null = null;
  private flyData: Float32Array | null = null;
  private flyEntity: pc.Entity | null = null;
  private flyMat: pc.StandardMaterial;

  constructor(app: pc.AppBase, areas: AreaResult, private T: Terrain) {
    const root = new pc.Entity('nightLights');
    app.root.addChild(root);
    for (const def of areas.lights) {
      const e = new pc.Entity('nightLight');
      e.addComponent('light', {
        type: 'omni',
        color: new pc.Color(def.color[0], def.color[1], def.color[2]),
        intensity: 0,
        range: def.range,
        falloffMode: pc.LIGHTFALLOFF_INVERSESQUARED,
        castShadows: false,
        enabled: false,
      });
      e.setPosition(def.x, def.y, def.z);
      root.addChild(e);
      this.live.push({ e, def, seed: Math.random() * 100 });
    }
    // string lights
    this.bulbMat = new pc.StandardMaterial();
    this.bulbMat.diffuse = new pc.Color(0.9, 0.85, 0.7);
    this.bulbMat.emissive = new pc.Color(1, 0.78, 0.45);
    this.bulbMat.emissiveIntensity = 0;
    this.bulbMat.update();
    this.cableMat = new pc.StandardMaterial();
    this.cableMat.diffuse = new pc.Color(0.05, 0.05, 0.05);
    this.cableMat.update();
    const dev = app.graphicsDevice;
    const bulb = pc.Mesh.fromGeometry(dev, new pc.SphereGeometry({ radius: 0.055, latitudeBands: 5, longitudeBands: 6 }));
    const mats: number[] = [];
    const cablePos: number[] = [];
    const cableIdx: number[] = [];
    const m = new pc.Mat4();
    for (const s of areas.strings) {
      const [ax, ay, az] = s.a, [bx, by, bz] = s.b;
      const len = Math.hypot(bx - ax, bz - az);
      const sag = 0.35 + len * 0.025;
      const n = Math.max(6, Math.round(len / 0.9));
      const base = cablePos.length / 3;
      for (let i = 0; i <= n * 2; i++) {
        const t = i / (n * 2);
        const x = ax + (bx - ax) * t, z = az + (bz - az) * t;
        const y = ay + (by - ay) * t - sag * 4 * t * (1 - t);
        cablePos.push(x, y, z, x, y - 0.012, z);
        if (i > 0) {
          const k = base + (i - 1) * 2;
          cableIdx.push(k, k + 2, k + 1, k + 1, k + 2, k + 3);
        }
        if (i % 2 === 1) {
          m.setTranslate(x, y - 0.07, z);
          mats.push(...m.data);
        }
      }
    }
    if (mats.length) {
      const vb = new pc.VertexBuffer(dev, pc.VertexFormat.getDefaultInstancingFormat(dev), mats.length / 16, { data: new Float32Array(mats) });
      const mi = new pc.MeshInstance(bulb, this.bulbMat);
      mi.setInstancing(vb);
      mi.cull = false;
      const e = new pc.Entity('stringBulbs');
      e.addComponent('render', { meshInstances: [mi], castShadows: false, receiveShadows: false });
      root.addChild(e);
      const cable = new pc.Mesh(dev);
      cable.setPositions(cablePos);
      cable.setNormals(cablePos.map((_, i) => (i % 3 === 1 ? 1 : 0)));
      cable.setIndices(cableIdx);
      cable.update();
      const ce = new pc.Entity('stringCable');
      const cmi = new pc.MeshInstance(cable, this.cableMat);
      this.cableMat.cull = pc.CULLFACE_NONE;
      this.cableMat.update();
      ce.addComponent('render', { meshInstances: [cmi], castShadows: false });
      root.addChild(ce);
    }
    // fireflies: tiny additive glow points, positions updated on the CPU
    this.flyMat = new pc.StandardMaterial();
    this.flyMat.diffuse = new pc.Color(0, 0, 0);
    this.flyMat.emissive = new pc.Color(0.85, 1, 0.45);
    this.flyMat.emissiveIntensity = 6;
    this.flyMat.useLighting = false;
    this.flyMat.blendType = pc.BLEND_ADDITIVE;
    this.flyMat.depthWrite = false;
    this.flyMat.update();
    let seed = 7;
    const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (const [cx, cz, r, n] of SWARMS) {
      for (let i = 0; i < n; i++) {
        const a = rnd() * Math.PI * 2, d = Math.sqrt(rnd()) * r;
        this.flies.push({ cx: cx + Math.cos(a) * d, cz: cz + Math.sin(a) * d, r: 1.5 + rnd() * 3, ph: rnd() * 100, sp: 0.15 + rnd() * 0.35, h: 0.5 + rnd() * 1.8, blink: 0.6 + rnd() * 1.6 });
      }
    }
    this.flyData = new Float32Array(this.flies.length * 16);
    this.flyVb = new pc.VertexBuffer(dev, pc.VertexFormat.getDefaultInstancingFormat(dev), this.flies.length, { data: this.flyData, usage: pc.BUFFER_DYNAMIC });
    const dot = pc.Mesh.fromGeometry(dev, new pc.SphereGeometry({ radius: 0.035, latitudeBands: 4, longitudeBands: 5 }));
    const fmi = new pc.MeshInstance(dot, this.flyMat);
    fmi.setInstancing(this.flyVb);
    fmi.cull = false;
    this.flyEntity = new pc.Entity('fireflies');
    this.flyEntity.addComponent('render', { meshInstances: [fmi], castShadows: false, receiveShadows: false });
    this.flyEntity.enabled = false;
    root.addChild(this.flyEntity);
  }

  private updateFlies(k: number) {
    const e = this.flyEntity, data = this.flyData, vb = this.flyVb;
    if (!e || !data || !vb) return;
    e.enabled = k > 0.3;
    if (!e.enabled) return;
    const t = this.time;
    for (let i = 0; i < this.flies.length; i++) {
      const f = this.flies[i];
      const a = t * f.sp + f.ph;
      const x = f.cx + Math.sin(a) * f.r + Math.sin(a * 2.3 + 1.7) * 0.6;
      const z = f.cz + Math.cos(a * 0.8) * f.r + Math.cos(a * 1.9) * 0.6;
      const y = this.T.heightAt(x, z) + f.h + Math.sin(a * 3.1) * 0.25;
      // blink: mostly dim, brief bright pulses
      const b = Math.pow(Math.max(0, Math.sin(t * f.blink + f.ph * 3)), 6);
      const s = (0.25 + 0.75 * b) * k;
      const o = i * 16;
      data.fill(0, o, o + 16);
      data[o] = s; data[o + 5] = s; data[o + 10] = s; data[o + 15] = 1;
      data[o + 12] = x; data[o + 13] = y; data[o + 14] = z;
    }
    vb.setData(data);
  }

  update(dt: number, night: number) {
    this.time += dt;
    const k = Math.max(0, Math.min(1, (night - 0.15) / 0.6));
    if (Math.abs(k - this.night) > 1e-3) {
      this.bulbMat.emissiveIntensity = 0.2 + k * 5;
      this.bulbMat.update();
    }
    for (const l of this.live) {
      const L = l.e.light!;
      L.enabled = k > 0.01;
      if (!L.enabled) continue;
      let f = 1;
      if (l.def.flicker) {
        const t = this.time * 9 + l.seed;
        f = 0.78 + 0.14 * Math.sin(t) + 0.08 * Math.sin(t * 2.7 + 1.3) + 0.06 * Math.sin(t * 6.1);
      }
      L.intensity = l.def.intensity * k * f;
    }
    if (dt > 0) this.updateFlies(k);
    this.night = k;
  }
}
