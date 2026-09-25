// Winch rope (segmented cylinders with sag) and anchor markers.
import * as pc from 'playcanvas';
import type { Winch } from '../physics/winch';
import { applyFog } from './shaders';

const SEGS = 18;

function emissiveMat(r: number, g: number, b: number, opacity = 1) {
  const m = new pc.StandardMaterial();
  m.diffuse = new pc.Color(0, 0, 0);
  m.emissive = new pc.Color(r, g, b);
  m.emissiveIntensity = 1.5;
  m.useLighting = false;
  if (opacity < 1) {
    m.opacity = opacity;
    m.blendType = pc.BLEND_ADDITIVEALPHA;
    m.depthWrite = false;
  }
  m.update();
  return m;
}

export class RopeView {
  root = new pc.Entity('winchFx');
  segs: pc.Entity[] = [];
  markers: pc.Entity[] = [];
  matValid = emissiveMat(0.45, 0.95, 0.5, 0.55);
  matSelected = emissiveMat(1.0, 0.8, 0.35, 0.8);
  matInvalid = emissiveMat(0.9, 0.35, 0.3, 0.35);
  private time = 0;
  private a = new pc.Vec3();
  private b = new pc.Vec3();

  constructor(app: pc.AppBase, private winch: Winch) {
    const ropeMat = new pc.StandardMaterial();
    ropeMat.diffuse = new pc.Color(0.16, 0.15, 0.13);
    ropeMat.gloss = 0.3;
    applyFog(ropeMat);
    ropeMat.update();
    for (let i = 0; i < SEGS; i++) {
      const e = new pc.Entity('rope');
      e.addComponent('render', { type: 'cylinder', material: ropeMat, castShadows: true });
      e.enabled = false;
      this.root.addChild(e);
      this.segs.push(e);
    }
    for (let i = 0; i < 12; i++) {
      const m = new pc.Entity('marker');
      const ring = new pc.Entity('ring');
      ring.addComponent('render', { type: 'torus', material: this.matValid, castShadows: false });
      ring.setLocalScale(1.4, 0.35, 1.4);
      const beam = new pc.Entity('beam');
      beam.addComponent('render', { type: 'cylinder', material: this.matValid, castShadows: false });
      beam.setLocalScale(0.12, 5, 0.12);
      beam.setLocalPosition(0, 2.5, 0);
      m.addChild(ring);
      m.addChild(beam);
      m.enabled = false;
      this.root.addChild(m);
      this.markers.push(m);
    }
    app.root.addChild(this.root);
  }

  update(dt: number) {
    this.time += dt;
    const w = this.winch;
    // markers during selection
    const showMarkers = w.mode === 'select';
    for (let i = 0; i < this.markers.length; i++) {
      const m = this.markers[i];
      const c = showMarkers ? w.candidates[i] : undefined;
      if (!c) { m.enabled = false; continue; }
      m.enabled = true;
      const sel = w.selected === c;
      const mat = sel ? this.matSelected : c.valid ? this.matValid : this.matInvalid;
      for (const ch of m.children as pc.Entity[]) if (ch.render) ch.render.material = mat;
      const pulse = sel ? 1 + Math.sin(this.time * 6) * 0.12 : 1;
      m.setPosition(c.anchor.x, c.anchor.y + c.anchor.h, c.anchor.z);
      m.setLocalScale(pulse, 1, pulse);
    }
    // rope
    const attached = w.mode === 'attached' && w.anchor;
    for (const s of this.segs) s.enabled = !!attached;
    if (!attached) return;
    const p = w.attachWorld, q = w.anchorWorld;
    const dist = Math.hypot(q.x - p.x, q.y - p.y, q.z - p.z);
    const slack = Math.max(0, w.length - dist);
    const sag = Math.min(1.2, slack * 0.8 + (w.tension < 200 ? 0.15 : 0.02));
    const pt = (t: number, out: pc.Vec3) => {
      out.set(p.x + (q.x - p.x) * t, p.y + (q.y - p.y) * t - Math.sin(t * Math.PI) * sag, p.z + (q.z - p.z) * t);
      return out;
    };
    for (let i = 0; i < SEGS; i++) {
      pt(i / SEGS, this.a);
      pt((i + 1) / SEGS, this.b);
      const e = this.segs[i];
      const len = this.a.distance(this.b);
      e.setPosition((this.a.x + this.b.x) / 2, (this.a.y + this.b.y) / 2, (this.a.z + this.b.z) / 2);
      e.lookAt(this.b);
      e.rotateLocal(90, 0, 0);
      e.setLocalScale(0.05, len + 0.01, 0.05);
    }
  }
}
