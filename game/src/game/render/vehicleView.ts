// Visual vehicle: body, four wheels on solid axles, springs and driveshafts,
// assembled from the GLB parts and the mount sidecar (vehicle_<id>.json);
// interpolated from the physics state. Also owns lamp emission and mud.
import * as pc from 'playcanvas';
import type { Vehicle } from '../physics/vehicle';
import type { ModelLibrary } from './models';
import { slerp, type Q4 } from '../physics/vmath';
import { NOISE_GLSL, applyFog } from './shaders';

interface WheelView {
  pivot: pc.Entity;
  spin: pc.Entity;
}

/** mount sidecar written by art/blender/vehicle_parts.export_vehicle (game coordinates) */
export interface VehicleInfo {
  id: string;
  wheelBase: number;
  trackX: number;
  wheelRadius: number;
  spring: { x: number; top: number; seat: number };
  driveshaft: { tcaseZ: number; tcaseY: number; pinionZ: number; pinionY: number };
  lamps: Partial<Record<'head' | 'fog' | 'bar' | 'indicator' | 'tail' | 'brake' | 'reverse' | 'winch' | 'hitch', [number, number, number][]>>;
  bodyBox?: { min: [number, number, number]; max: [number, number, number] };
}

/** body colours (sRGB), kept at about two thirds of full saturation: ACES and
 * the grading push strong hues further, and bright paint looked toy-like */
export const PAINTS: Record<string, { name: string; body: [number, number, number]; accent?: [number, number, number]; swatch: string }> = {
  ochre: { name: '赭红', body: [0.62, 0.38, 0.31], swatch: '#9e614f' },
  cream: { name: '米白', body: [0.89, 0.87, 0.81], swatch: '#e3decf' },
  pine: { name: '松林绿', body: [0.26, 0.35, 0.31], swatch: '#42594f' },
  trail: { name: '溪蓝', body: [0.24, 0.33, 0.45], swatch: '#3d5473' },
  sand: { name: '沙漠卡其', body: [0.56, 0.53, 0.46], swatch: '#8f8775' }, // already muted: only a light trim
  white: { name: '冰川白', body: [0.9, 0.9, 0.88], swatch: '#e6e6e0' },
  red: { name: '峡谷红', body: [0.52, 0.2, 0.18], swatch: '#85332e' },
  mint: { name: '薄荷绿', body: [0.48, 0.6, 0.58], accent: [0.92, 0.88, 0.78], swatch: '#7a9994' },
  sky: { name: '晴空蓝', body: [0.5, 0.61, 0.72], accent: [0.93, 0.92, 0.88], swatch: '#809cb8' },
};

/** how readily each material collects mud (0 = never) */
const MUD_RECEPTIVITY: Record<string, number> = {
  Paint: 0.85, PaintAccent: 0.6, Trim: 0.9, Rubber: 0.9, Metal: 0.8, Chrome: 0.55, Glass: 0.22, Interior: 0,
  Tire: 1, Rim: 0.95, Canvas: 0.5, Decal: 0.6, Lamp: 0.18, LampAux: 0.18, LampAmber: 0.2, LampRear: 0.2, LampReverse: 0.2,
};

const MUD_DIFFUSE = /* glsl */ `
uniform vec3 material_diffuse;
uniform vec3 ft_vehO;
uniform vec3 ft_vehR;
uniform vec3 ft_vehU;
uniform vec3 ft_vehF;
uniform float ft_dirt;
uniform float ft_mudK;
${NOISE_GLSL}
void getAlbedo() {
  vec3 base = material_diffuse.rgb;
  vec3 d = vPositionW - ft_vehO;
  vec3 lp = vec3(dot(d, ft_vehR), dot(d, ft_vehU), dot(d, ft_vehF));
  float n = ftFbm(lp.xz * 2.7 + vec2(lp.y * 1.9, 0.0));
  float streak = ftNoise(vec2(lp.x * 9.0 + lp.z * 3.0, lp.y * 2.2));
  // mud climbs from the sills and wheel arches; splatter higher up
  float low = 1.0 - smoothstep(-0.25, 0.75 + ft_dirt * 0.35, lp.y + (n - 0.5) * 0.7 - streak * 0.18);
  float spl = smoothstep(0.66, 0.8, ftNoise(lp.xy * 11.0 + lp.zz * 6.0)) * smoothstep(1.6, 0.2, lp.y);
  float m = clamp(ft_dirt * (low * 1.25 + spl * 0.5) - 0.04, 0.0, 1.0) * ft_mudK;
  vec3 wet = ftLin(vec3(0.24, 0.19, 0.14));
  vec3 dry = ftLin(vec3(0.52, 0.45, 0.36));
  vec3 mudC = mix(wet, dry, smoothstep(0.35, 0.75, n));
  dAlbedo = mix(base, mudC, m * 0.92);
}
`;

export interface LampState {
  /** 0 off, 1 low beam, 2 high beam */
  beam: number;
  brake: number;
  reverse: boolean;
  /** 0..1 night factor: tail and marker lamps glow brighter at night */
  night: number;
}

export class VehicleView {
  root: pc.Entity;
  body: pc.Entity;
  wheels: WheelView[] = [];
  axles: pc.Entity[] = [];
  springs: pc.Entity[] = [];
  shafts: pc.Entity[] = [];
  paintMats: pc.StandardMaterial[] = [];
  accentMats: pc.StandardMaterial[] = [];
  mats = new Map<string, pc.StandardMaterial[]>();
  renderPos = new pc.Vec3();
  renderRot = new pc.Quat();
  private q: Q4 = { x: 0, y: 0, z: 0, w: 1 };
  /** 0..1 accumulated mud on the car */
  dirt = 0;
  private tmpV = new pc.Vec3();
  private tmpV2 = new pc.Vec3();

  constructor(app: pc.AppBase, lib: ModelLibrary, private v: Vehicle, readonly info: VehicleInfo) {
    this.root = new pc.Entity('vehicle');
    const model = lib.models.get(v.spec.model);
    const ent = model?.container ? model.container.instantiateRenderEntity() : null;
    const find = (name: string) => ent?.findByName(name) as pc.Entity | null;
    this.body = new pc.Entity('bodyRoot');
    this.root.addChild(this.body);
    const bodyNode = find('Body');
    if (bodyNode) {
      bodyNode.reparent(this.body);
      bodyNode.setLocalPosition(0, 0, 0);
    } else {
      const box = new pc.Entity('fbBody');
      box.addComponent('render', { type: 'box' });
      box.setLocalScale(1.8, 0.9, 4.1);
      box.setLocalPosition(0, 0.75, 0);
      const mat = new pc.StandardMaterial();
      mat.name = 'Paint';
      mat.diffuse = new pc.Color(0.72, 0.36, 0.24);
      mat.update();
      box.render!.meshInstances[0].material = mat;
      this.body.addChild(box);
    }
    const C = v.spec;
    const wheelSrc = find('Wheel');
    for (let i = 0; i < 4; i++) {
      const w = v.wheels[i];
      const pivot = new pc.Entity('wheelPivot');
      const spin = new pc.Entity('wheelSpin');
      pivot.addChild(spin);
      let mesh: pc.Entity;
      if (wheelSrc) {
        mesh = wheelSrc.clone() as pc.Entity;
        mesh.setLocalPosition(0, 0, 0);
      } else {
        mesh = new pc.Entity('fbWheel');
        mesh.addComponent('render', { type: 'cylinder' });
        mesh.setLocalScale(C.wheelRadius * 2, C.wheelWidth, C.wheelRadius * 2);
        mesh.setLocalEulerAngles(0, 0, 90);
        const holder = new pc.Entity();
        holder.addChild(mesh);
        mesh = holder;
      }
      if (w.left) mesh.setLocalEulerAngles(0, 180, 0);
      spin.addChild(mesh);
      this.body.addChild(pivot);
      this.wheels.push({ pivot, spin });
    }
    for (const n of ['AxleFront', 'AxleRear']) {
      const src = find(n);
      if (!src) continue;
      const a = src.clone() as pc.Entity;
      this.body.addChild(a);
      this.axles.push(a);
    }
    const shaft = find('Driveshaft');
    if (shaft) {
      for (let i = 0; i < 2; i++) {
        const s = shaft.clone() as pc.Entity;
        this.body.addChild(s);
        this.shafts.push(s);
      }
    }
    const spring = find('Spring');
    if (spring) {
      for (let i = 0; i < 4; i++) {
        const s = spring.clone() as pc.Entity;
        this.body.addChild(s);
        this.springs.push(s);
      }
    }
    ent?.destroy();
    // unique materials per car so paint, lamps and mud are independent
    const cloned = new Map<pc.Material, pc.StandardMaterial>();
    for (const r of this.root.findComponents('render') as pc.RenderComponent[]) {
      r.castShadows = true;
      r.receiveShadows = true;
      for (const mi of r.meshInstances) {
        const src = mi.material as pc.StandardMaterial;
        let m = cloned.get(src);
        if (!m) {
          m = src.clone() as pc.StandardMaterial;
          m.name = src.name;
          const k = MUD_RECEPTIVITY[m.name] ?? 0.5;
          applyFog(m);
          if (k > 0) {
            m.getShaderChunks(pc.SHADERLANGUAGE_GLSL).set('diffusePS', MUD_DIFFUSE);
            m.shaderChunksVersion = '2.8';
            m.setParameter('ft_mudK', k);
          }
          if (m.name.startsWith('Lamp')) m.emissive = new pc.Color(0, 0, 0);
          m.update();
          cloned.set(src, m);
          const list = this.mats.get(m.name) ?? [];
          list.push(m);
          this.mats.set(m.name, list);
        }
        mi.material = m;
      }
    }
    this.paintMats = this.mats.get('Paint') ?? [];
    this.accentMats = this.mats.get('PaintAccent') ?? [];
    app.root.addChild(this.root);
  }

  setPaint(key: string) {
    const p = PAINTS[key] ?? PAINTS.ochre;
    for (const m of this.paintMats) {
      m.diffuse = new pc.Color(p.body[0], p.body[1], p.body[2]);
      m.update();
    }
    if (p.accent) {
      for (const m of this.accentMats) {
        m.diffuse = new pc.Color(p.accent[0], p.accent[1], p.accent[2]);
        m.update();
      }
    }
  }

  private lampKey = '';
  /** lamp lens emission; values are HDR so bloom picks them up at night */
  setLamps(s: LampState) {
    const key = `${s.beam}|${s.brake.toFixed(2)}|${s.reverse}|${s.night.toFixed(2)}`;
    if (key === this.lampKey) return;
    this.lampKey = key;
    const set = (name: string, col: [number, number, number], k: number) => {
      for (const m of this.mats.get(name) ?? []) {
        m.emissive = new pc.Color(col[0], col[1], col[2]);
        m.emissiveIntensity = k;
        m.update();
      }
    };
    const on = s.beam > 0;
    set('Lamp', [1, 0.93, 0.8], on ? (s.beam === 2 ? 9 : 6) : 0);
    set('LampAux', [1, 0.94, 0.82], s.beam === 2 ? 8 : 0);
    set('LampAmber', [1, 0.55, 0.12], on ? 1.2 + s.night * 1.5 : 0);
    const tail = (on ? 1.4 + s.night * 1.6 : 0) + s.brake * 6;
    set('LampRear', [1, 0.09, 0.05], tail);
    set('LampReverse', [1, 0.97, 0.92], s.reverse ? 5 : 0);
  }

  /** world position of a lamp group centre (body space offsets from the sidecar) */
  lampWorld(kind: keyof VehicleInfo['lamps'], i: number, out: pc.Vec3): pc.Vec3 | null {
    const l = this.info.lamps[kind];
    if (!l || !l[i]) return null;
    this.tmpV.set(l[i][0], l[i][1], l[i][2]);
    this.root.getWorldTransform().transformPoint(this.tmpV, out);
    return out;
  }

  update(alpha: number) {
    const v = this.v;
    const C = v.spec;
    const I = this.info;
    this.renderPos.lerp(this.tmpV.set(v.prevPos.x, v.prevPos.y, v.prevPos.z), this.tmpV2.set(v.pos.x, v.pos.y, v.pos.z), alpha);
    slerp(this.q, v.prevRot, v.rot, alpha);
    this.renderRot.set(this.q.x, this.q.y, this.q.z, this.q.w);
    this.root.setPosition(this.renderPos);
    this.root.setRotation(this.renderRot);
    const ys: number[] = [];
    for (let i = 0; i < 4; i++) {
      const w = v.wheels[i];
      const L = w.prevLength + (w.length - w.prevLength) * alpha;
      const y = w.hp.y - Math.max(L, C.minLength - 0.04);
      ys.push(y);
      const wv = this.wheels[i];
      wv.pivot.setLocalPosition(w.hp.x, y, w.hp.z);
      wv.pivot.setLocalEulerAngles(0, (-w.steer * 180) / Math.PI, 0);
      wv.spin.setLocalEulerAngles((-w.spin * 180) / Math.PI, 0, 0);
    }
    // solid axles follow the two wheel centres
    for (let a = 0; a < this.axles.length; a++) {
      const yl = ys[a * 2], yr = ys[a * 2 + 1];
      const z = a === 0 ? -C.wheelBase / 2 : C.wheelBase / 2;
      this.axles[a].setLocalPosition(0, (yl + yr) / 2, z);
      this.axles[a].setLocalEulerAngles(0, 0, (Math.atan2(yr - yl, C.track) * 180) / Math.PI);
    }
    // coil springs between the body mounts and the axle seats
    for (let i = 0; i < this.springs.length; i++) {
      const w = v.wheels[i];
      const a = i < 2 ? 0 : 1;
      const yl = ys[a * 2], yr = ys[a * 2 + 1];
      const x = w.left ? -I.spring.x : I.spring.x;
      const axleY = yl + (yr - yl) * ((x + C.track / 2) / C.track);
      const bottom = axleY + I.spring.seat;
      this.springs[i].setLocalPosition(x, bottom, w.hp.z);
      this.springs[i].setLocalScale(1, Math.max(0.05, I.spring.top - bottom), 1);
    }
    // driveshafts from the transfer case to each axle's pinion
    const D = I.driveshaft;
    for (let a = 0; a < this.shafts.length; a++) {
      const front = a === 0;
      const z0 = front ? -D.tcaseZ : D.tcaseZ;
      const axleY = (ys[a * 2] + ys[a * 2 + 1]) / 2;
      const z1 = front ? -C.wheelBase / 2 + D.pinionZ : C.wheelBase / 2 - D.pinionZ;
      const y1 = axleY + D.pinionY;
      const sh = this.shafts[a];
      sh.setLocalPosition(0, D.tcaseY, z0);
      const dy = y1 - D.tcaseY, dz = z1 - z0;
      const len = Math.hypot(dy, dz);
      // model points along -Z; pitch it towards the axle end
      const pitch = Math.atan2(dy, Math.abs(dz)) * (180 / Math.PI);
      sh.setLocalEulerAngles(pitch, front ? 0 : 180, 0);
      sh.setLocalScale(1, 1, len);
    }
    this.updateMudUniforms();
  }

  private updateMudUniforms() {
    const wt = this.root.getWorldTransform();
    const o = this.root.getPosition();
    const r = wt.getX(this.tmpV).normalize();
    const vals = { o: [o.x, o.y, o.z], r: [r.x, r.y, r.z], u: [0, 0, 0], f: [0, 0, 0] };
    const u = wt.getY(this.tmpV).normalize();
    vals.u = [u.x, u.y, u.z];
    const f = wt.getZ(this.tmpV).normalize();
    vals.f = [f.x, f.y, f.z];
    for (const list of this.mats.values()) {
      for (const m of list) {
        m.setParameter('ft_vehO', vals.o);
        m.setParameter('ft_vehR', vals.r);
        m.setParameter('ft_vehU', vals.u);
        m.setParameter('ft_vehF', vals.f);
        m.setParameter('ft_dirt', this.dirt);
      }
    }
  }

  destroy() {
    this.root.destroy();
    for (const list of this.mats.values()) for (const m of list) m.destroy();
  }
}
