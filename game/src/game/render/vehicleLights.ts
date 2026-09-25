// Headlights and lamp glows. One shadow-casting spot light carries the beam
// (low beam: cookie with a sharp cut-off, aimed down, short; high beam: round
// hot spot, long throw), billboard glows sit on every lamp lens, faint
// additive cones show the beams in fog at night, and a small red light
// follows the tail lamps.
import * as pc from 'playcanvas';
import type { VehicleView, VehicleInfo } from './vehicleView';
import type { Vehicle } from '../physics/vehicle';

export type Beam = 0 | 1 | 2;

function canvasTexture(device: pc.GraphicsDevice, size: number, draw: (c: CanvasRenderingContext2D, s: number) => void, name: string) {
  const cv = document.createElement('canvas');
  cv.width = cv.height = size;
  const ctx = cv.getContext('2d')!;
  draw(ctx, size);
  const tex = new pc.Texture(device, {
    name, width: size, height: size, format: pc.PIXELFORMAT_RGBA8, mipmaps: true,
    addressU: pc.ADDRESS_CLAMP_TO_EDGE, addressV: pc.ADDRESS_CLAMP_TO_EDGE,
  });
  tex.setSource(cv);
  return tex;
}

/** spot cookies: the texture maps onto the cone cross-section (top of the image = up) */
function lowBeamCookie(c: CanvasRenderingContext2D, s: number) {
  c.fillStyle = '#000';
  c.fillRect(0, 0, s, s);
  const g = c.createRadialGradient(s * 0.5, s * 0.56, 0, s * 0.5, s * 0.56, s * 0.5);
  g.addColorStop(0, 'rgba(255,250,235,1)');
  g.addColorStop(0.35, 'rgba(235,225,200,0.85)');
  g.addColorStop(0.8, 'rgba(120,110,95,0.25)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  c.fillStyle = g;
  c.fillRect(0, 0, s, s);
  // asymmetric cut-off: flat on the left, 15° kick-up on the right (kerb side)
  c.fillStyle = '#000';
  c.beginPath();
  c.moveTo(0, 0); c.lineTo(s, 0); c.lineTo(s, s * 0.4); c.lineTo(s * 0.56, s * 0.5); c.lineTo(0, s * 0.5);
  c.closePath();
  c.fill();
  // soften the edge
  const e = c.createLinearGradient(0, s * 0.46, 0, s * 0.56);
  e.addColorStop(0, 'rgba(0,0,0,0.9)');
  e.addColorStop(1, 'rgba(0,0,0,0)');
  c.fillStyle = e;
  c.fillRect(0, s * 0.46, s * 0.56, s * 0.1);
  vignette(c, s);
}

function vignette(c: CanvasRenderingContext2D, s: number) {
  c.globalCompositeOperation = 'destination-in';
  const v = c.createRadialGradient(s / 2, s / 2, s * 0.3, s / 2, s / 2, s * 0.49);
  v.addColorStop(0, 'rgba(0,0,0,1)');
  v.addColorStop(1, 'rgba(0,0,0,0)');
  c.fillStyle = v;
  c.fillRect(0, 0, s, s);
  c.globalCompositeOperation = 'destination-over';
  c.fillStyle = '#000';
  c.fillRect(0, 0, s, s);
  c.globalCompositeOperation = 'source-over';
}

function highBeamCookie(c: CanvasRenderingContext2D, s: number) {
  c.fillStyle = '#000';
  c.fillRect(0, 0, s, s);
  const g = c.createRadialGradient(s * 0.5, s * 0.5, 0, s * 0.5, s * 0.5, s * 0.5);
  g.addColorStop(0, 'rgba(255,252,242,1)');
  g.addColorStop(0.22, 'rgba(255,245,225,0.95)');
  g.addColorStop(0.6, 'rgba(170,160,140,0.4)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  c.fillStyle = g;
  c.fillRect(0, 0, s, s);
  vignette(c, s);
}

function glowSprite(c: CanvasRenderingContext2D, s: number) {
  const g = c.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.12, 'rgba(255,255,255,0.85)');
  g.addColorStop(0.35, 'rgba(255,255,255,0.22)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  c.fillStyle = g;
  c.fillRect(0, 0, s, s);
  // thin horizontal streak (anamorphic flare)
  const h = c.createLinearGradient(0, 0, s, 0);
  h.addColorStop(0, 'rgba(255,255,255,0)');
  h.addColorStop(0.5, 'rgba(255,255,255,0.35)');
  h.addColorStop(1, 'rgba(255,255,255,0)');
  c.fillStyle = h;
  c.fillRect(0, s * 0.485, s, s * 0.03);
}

const CONE_VS = /* glsl */ `
attribute vec3 aPosition;
attribute vec2 aUv0;
uniform mat4 matrix_model;
uniform mat4 matrix_viewProjection;
varying vec2 vUv;
varying vec3 vPosW;
varying vec3 vNrm;
void main(void) {
  vUv = aUv0;
  vec4 w = matrix_model * vec4(aPosition, 1.0);
  vPosW = w.xyz;
  // surface normal of the elliptic cone x^2 + (y/0.55)^2 = z^2
  // (the tip vertex sits at the origin: fall back to the axis so no NaN reaches the HDR buffer)
  vec3 n = vec3(aPosition.x, aPosition.y / 0.3025, -aPosition.z);
  if (dot(n, n) < 1e-8) n = vec3(0.0, 0.0, 1.0);
  vNrm = mat3(matrix_model) * n;
  gl_Position = matrix_viewProjection * w;
}`;

const CONE_FS = /* glsl */ `
varying vec2 vUv;
varying vec3 vPosW;
varying vec3 vNrm;
uniform vec3 cone_color;
uniform float cone_alpha;
uniform vec3 view_position;
void main(void) {
  // vUv.y: 0 at the lamp, 1 at the far end; vUv.x around the cone
  float along = vUv.y;
  // clamp: interpolation can overshoot the rim slightly and pow() of a negative base is NaN
  float fall = pow(clamp(1.0 - along, 0.0, 1.0), 2.4) * smoothstep(0.0, 0.08, along);
  float d = length(vPosW - view_position);
  float nearFade = smoothstep(1.5, 5.0, d);
  // silhouettes fade out so the beam reads as a soft volume
  vec3 nn = vNrm / max(length(vNrm), 1e-4);
  float facing = abs(dot(nn, (view_position - vPosW) / max(d, 1e-3)));
  float soft = pow(facing, 2.0);
  gl_FragColor = vec4(cone_color * fall * cone_alpha * nearFade * soft, 1.0);
}`;

/** open cone, tip at the origin, opening along -Z to radius 1 at z = -1; uv.y = 0 at the tip */
function beamConeMesh(device: pc.GraphicsDevice): pc.Mesh {
  const seg = 28, rings = 6;
  const pos: number[] = [], uv: number[] = [], idx: number[] = [];
  for (let r = 0; r <= rings; r++) {
    const t = r / rings;
    for (let i = 0; i <= seg; i++) {
      const a = (i / seg) * Math.PI * 2;
      pos.push(Math.cos(a) * t, Math.sin(a) * t * 0.55, -t);
      uv.push(i / seg, t);
    }
  }
  for (let r = 0; r < rings; r++) for (let i = 0; i < seg; i++) {
    const a = r * (seg + 1) + i, b = a + 1, c = a + seg + 1, d = c + 1;
    idx.push(a, c, b, b, c, d);
  }
  const m = new pc.Mesh(device);
  m.setPositions(pos);
  m.setUvs(0, uv);
  m.setIndices(idx);
  m.update();
  return m;
}

interface Glow { e: pc.Entity; mat: pc.StandardMaterial; kind: string; base: pc.Vec3; dir: number; size: number }

export class VehicleLights {
  beam: Beam = 0;
  private spot: pc.Entity;
  private tail: pc.Entity;
  private glows: Glow[] = [];
  private cones: pc.Entity[] = [];
  private coneMat: pc.ShaderMaterial;
  private lowCookie: pc.Texture;
  private highCookie: pc.Texture;
  private glowTex: pc.Texture;
  private root: pc.Entity | null = null;
  /** follows the vehicle root so the lights survive a vehicle swap */
  private follow: pc.Entity;
  private tmp = new pc.Vec3();
  private tmp2 = new pc.Vec3();
  shadows = true;

  constructor(private app: pc.AppBase) {
    const dev = app.graphicsDevice;
    this.lowCookie = canvasTexture(dev, 128, lowBeamCookie, 'cookieLow');
    this.highCookie = canvasTexture(dev, 128, highBeamCookie, 'cookieHigh');
    this.glowTex = canvasTexture(dev, 128, glowSprite, 'lampGlow');
    this.spot = new pc.Entity('headlight');
    this.spot.addComponent('light', {
      type: 'spot',
      color: new pc.Color(1, 0.94, 0.84),
      intensity: 0,
      range: 45,
      innerConeAngle: 26,
      outerConeAngle: 50,
      // linear falloff gives artistic control over the throw of each beam
      falloffMode: pc.LIGHTFALLOFF_LINEAR,
      castShadows: true,
      shadowResolution: 1024,
      shadowBias: 0.08,
      normalOffsetBias: 0.05,
      cookie: this.lowCookie,
      cookieIntensity: 1,
      enabled: false,
    });
    this.follow = new pc.Entity('vehicleLights');
    app.root.addChild(this.follow);
    this.follow.addChild(this.spot);
    this.tail = new pc.Entity('taillight');
    this.tail.addComponent('light', {
      type: 'omni', color: new pc.Color(1, 0.12, 0.06), intensity: 0, range: 6,
      falloffMode: pc.LIGHTFALLOFF_INVERSESQUARED, castShadows: false, enabled: false,
    });
    this.follow.addChild(this.tail);
    this.coneMat = new pc.ShaderMaterial({
      uniqueName: 'ftBeamCone', vertexGLSL: CONE_VS, fragmentGLSL: CONE_FS,
      attributes: { aPosition: pc.SEMANTIC_POSITION, aUv0: pc.SEMANTIC_TEXCOORD0 },
    });
    this.coneMat.blendType = pc.BLEND_ADDITIVE;
    this.coneMat.depthWrite = false;
    this.coneMat.cull = pc.CULLFACE_NONE;
    this.coneMat.setParameter('cone_color', [1, 0.93, 0.8]);
    this.coneMat.setParameter('cone_alpha', 0);
    this.coneMat.update();
  }

  /** (re)attach to the current vehicle view */
  attach(view: VehicleView) {
    this.root = view.root;
    const info = view.info;
    for (const g of this.glows) g.e.destroy();
    for (const c of this.cones) c.destroy();
    this.glows = [];
    this.cones = [];
    const heads = info.lamps.head ?? [];
    const hc = this.centre(heads, [0, 0.6, -2]);
    // in front of the bumper / winch so the car does not shadow its own beam
    const front = Math.min(hc[2] - 0.3, (info.bodyBox?.min[2] ?? hc[2]) - 0.3);
    this.spot.setLocalPosition(hc[0], hc[1] + 0.28, front);
    const tails = info.lamps.tail ?? [];
    const tc = this.centre(tails, [0, 0.5, 2]);
    this.tail.setLocalPosition(tc[0], tc[1], tc[2] + 0.35);
    const add = (kind: keyof VehicleInfo['lamps'], size: number, dir: number) => {
      for (const p of info.lamps[kind] ?? []) {
        const mat = new pc.StandardMaterial();
        mat.useLighting = false;
        mat.useFog = false;
        mat.diffuse = new pc.Color(0, 0, 0);
        mat.emissiveMap = this.glowTex;
        mat.opacityMap = this.glowTex;
        mat.opacityMapChannel = 'a';
        mat.emissive = new pc.Color(1, 1, 1);
        mat.blendType = pc.BLEND_ADDITIVE;
        mat.depthWrite = false;
        mat.update();
        const e = new pc.Entity(`glow-${kind}`);
        e.addComponent('render', { type: 'plane', castShadows: false, receiveShadows: false });
        e.render!.meshInstances[0].material = mat;
        e.enabled = false;
        this.app.root.addChild(e);
        this.glows.push({ e, mat, kind, base: new pc.Vec3(p[0], p[1], p[2]), dir, size });
      }
    };
    add('head', 0.9, -1);
    add('fog', 0.5, -1);
    add('bar', 0.55, -1);
    add('indicator', 0.28, -1);
    add('tail', 0.42, 1);
    add('reverse', 0.4, 1);
    // beam cones in fog, one per headlight
    const coneMesh = beamConeMesh(this.app.graphicsDevice);
    for (const p of heads) {
      const cone = new pc.Entity('beamCone');
      const mi = new pc.MeshInstance(coneMesh, this.coneMat);
      cone.addComponent('render', { meshInstances: [mi], castShadows: false, receiveShadows: false });
      this.follow.addChild(cone);
      cone.setLocalPosition(p[0], p[1], p[2]);
      cone.enabled = false;
      this.cones.push(cone);
    }
    this.lastKey = '';
  }

  private centre(ps: [number, number, number][], dflt: [number, number, number]): [number, number, number] {
    if (!ps.length) return dflt;
    const c: [number, number, number] = [0, 0, 0];
    for (const p of ps) { c[0] += p[0] / ps.length; c[1] += p[1] / ps.length; c[2] += p[2] / ps.length; }
    return c;
  }

  private lastKey = '';

  update(v: Vehicle, view: VehicleView, cam: pc.Entity, night: number, brake: number, reverse: boolean) {
    if (!this.root) return;
    this.follow.setPosition(view.root.getPosition());
    this.follow.setRotation(view.root.getRotation());
    const beam = this.beam;
    const key = `${beam}|${this.shadows}`;
    const L = this.spot.light!;
    if (key !== this.lastKey) {
      this.lastKey = key;
      L.enabled = beam > 0;
      L.castShadows = this.shadows;
      if (beam === 1) {
        L.range = 42; L.innerConeAngle = 30; L.outerConeAngle = 56; L.cookie = this.lowCookie;
        this.spot.setLocalEulerAngles(83, 0, 0);
      } else if (beam === 2) {
        L.range = 100; L.innerConeAngle = 20; L.outerConeAngle = 44; L.cookie = this.highCookie;
        this.spot.setLocalEulerAngles(87.5, 0, 0);
      }
      for (const c of this.cones) {
        c.enabled = beam > 0;
        const len = beam === 2 ? 24 : 12;
        const rad = beam === 2 ? 2.6 : 3.6;
        c.setLocalEulerAngles(beam === 2 ? -1.5 : -6, 0, 0);
        c.setLocalScale(rad, rad, len);
      }
    }
    L.intensity = beam === 2 ? 4.2 : beam === 1 ? 3.0 : 0;
    this.coneMat.setParameter('cone_alpha', beam > 0 ? 0.03 * (beam === 2 ? 1.25 : 1) * (0.15 + 0.85 * night) : 0);
    const T = this.tail.light!;
    const tailK = (beam > 0 ? 0.05 + night * 0.12 : 0) + brake * (0.15 + night * 0.35);
    T.enabled = tailK > 0.05 && night > 0.2;
    T.intensity = tailK;
    // glows
    const camPos = cam.getPosition();
    const wt = view.root.getWorldTransform();
    const fwd = wt.getZ(this.tmp2).normalize();
    for (const g of this.glows) {
      let k = 0;
      let col: [number, number, number] = [1, 0.95, 0.85];
      switch (g.kind) {
        case 'head': k = beam > 0 ? (beam === 2 ? 1.25 : 0.9) : 0; break;
        case 'fog': case 'bar': k = beam === 2 ? 0.9 : 0; break;
        case 'indicator': k = beam > 0 ? 0.35 : 0; col = [1, 0.55, 0.12]; break;
        case 'tail': k = (beam > 0 ? 0.35 : 0) + brake * 0.9; col = [1, 0.1, 0.05]; break;
        case 'reverse': k = reverse ? 0.7 : 0; break;
      }
      // brighter at night and when looking into the lamp
      wt.transformPoint(g.base, this.tmp);
      const dx = camPos.x - this.tmp.x, dy = camPos.y - this.tmp.y, dz = camPos.z - this.tmp.z;
      const dist = Math.hypot(dx, dy, dz);
      const facing = Math.max(0, (dx * fwd.x + dy * fwd.y + dz * fwd.z) / dist * -g.dir);
      k *= (0.18 + 0.82 * night) * (0.25 + 0.75 * Math.pow(facing, 1.5));
      g.e.enabled = k > 0.01;
      if (!g.e.enabled) continue;
      g.e.setPosition(this.tmp.x + dx / dist * 0.08, this.tmp.y + dy / dist * 0.08, this.tmp.z + dz / dist * 0.08);
      g.e.lookAt(camPos);
      g.e.rotateLocal(90, 0, 0);
      const s = g.size * (0.7 + 0.3 * night) * (1 + Math.min(dist, 60) * 0.012);
      g.e.setLocalScale(s, s, s);
      g.mat.emissive = new pc.Color(col[0] * k * 3, col[1] * k * 3, col[2] * k * 3);
      g.mat.update();
    }
    void v;
  }
}
