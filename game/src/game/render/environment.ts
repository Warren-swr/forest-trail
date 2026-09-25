// Time of day: a GPU sky dome (gradient, sun/moon, clouds, stars), the sun or
// moon light, fog, exposure and image based lighting. `t` runs 0 (afternoon)
// → 0.33 (golden hour) → 0.66 (blue hour) → 1 (night); gameplay uses 0 and 1,
// the demo sweeps through the stages.
import * as pc from 'playcanvas';
import { fbm } from '../world/noise';
import { LATTICE_HASH } from './shaders';

type RGB = [number, number, number];

interface Stage {
  sunDir: RGB;
  lightColor: RGB;
  lightIntensity: number;
  zenith: RGB;
  horizon: RGB;
  /** warm scattering around the sun/moon */
  glow: RGB;
  cloudLit: RGB;
  cloudShade: RGB;
  fog: RGB;
  fogSun: RGB;
  fogStart: number;
  fogEnd: number;
  exposure: number;
  stars: number;
  /** sun disc (0) or moon disc (1) */
  moon: number;
  bloom: number;
  /** IBL intensity */
  env: number;
  /** sun / moon disc, glow and light strength: dips to 0 while the sun hands over to the moon */
  disc: number;
}

const norm = (v: RGB): RGB => {
  const l = Math.hypot(v[0], v[1], v[2]);
  return [v[0] / l, v[1] / l, v[2] / l];
};

export const STAGES: Stage[] = [
  {
    sunDir: norm([-0.72, 0.46, 0.52]), lightColor: [1.0, 0.9, 0.76], lightIntensity: 2.4,
    zenith: [0.2, 0.36, 0.62], horizon: [0.72, 0.76, 0.74], glow: [0.55, 0.35, 0.1],
    cloudLit: [0.95, 0.92, 0.88], cloudShade: [0.66, 0.7, 0.74],
    fog: [0.58, 0.66, 0.66], fogSun: [0.95, 0.8, 0.6], fogStart: 45, fogEnd: 640,
    exposure: 1, stars: 0, moon: 0, bloom: 0.012, env: 1, disc: 1,
  },
  {
    sunDir: norm([-0.8, 0.2, 0.56]), lightColor: [1.0, 0.68, 0.42], lightIntensity: 2.1,
    zenith: [0.22, 0.3, 0.55], horizon: [0.96, 0.7, 0.5], glow: [0.9, 0.42, 0.12],
    cloudLit: [1.0, 0.72, 0.52], cloudShade: [0.55, 0.48, 0.55],
    fog: [0.78, 0.64, 0.54], fogSun: [1.0, 0.66, 0.38], fogStart: 40, fogEnd: 600,
    exposure: 1.05, stars: 0, moon: 0, bloom: 0.018, env: 0.9, disc: 1,
  },
  {
    sunDir: norm([-0.84, -0.04, 0.54]), lightColor: [0.62, 0.55, 0.85], lightIntensity: 0.55,
    zenith: [0.06, 0.09, 0.24], horizon: [0.52, 0.36, 0.44], glow: [0.6, 0.24, 0.16],
    cloudLit: [0.62, 0.42, 0.5], cloudShade: [0.2, 0.2, 0.3],
    fog: [0.3, 0.29, 0.4], fogSun: [0.7, 0.4, 0.35], fogStart: 35, fogEnd: 520,
    exposure: 1.25, stars: 0.35, moon: 0, bloom: 0.03, env: 1.4, disc: 1,
  },
  {
    sunDir: norm([0.38, 0.62, -0.68]), lightColor: [0.6, 0.7, 1.0], lightIntensity: 0.85,
    zenith: [0.009, 0.018, 0.048], horizon: [0.045, 0.085, 0.11], glow: [0.05, 0.08, 0.12],
    cloudLit: [0.11, 0.14, 0.2], cloudShade: [0.025, 0.035, 0.055],
    fog: [0.04, 0.068, 0.095], fogSun: [0.1, 0.14, 0.2], fogStart: 30, fogEnd: 470,
    exposure: 1.45, stars: 1, moon: 1, bloom: 0.045, env: 3.4, disc: 1,
  },
];

function lerp3(a: RGB, b: RGB, t: number): RGB {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

/** interpolated stage for continuous t in [0, 1] */
export function stageAt(t: number): Stage {
  const x = Math.max(0, Math.min(1, t)) * (STAGES.length - 1);
  const i = Math.min(STAGES.length - 2, Math.floor(x));
  const f = x - i;
  const a = STAGES[i], b = STAGES[i + 1];
  const out = {} as Stage;
  // colours and light levels blend geometrically: dusk is 10-30x brighter than
  // night, and a linear blend stays bright until the very end, then drops
  const geo = (x: number, y: number) => (x > 1e-5 && y > 1e-5 ? Math.exp(Math.log(x) + (Math.log(y) - Math.log(x)) * f) : x + (y - x) * f);
  for (const k of Object.keys(a) as (keyof Stage)[]) {
    const va = a[k], vb = b[k];
    if (Array.isArray(va)) {
      const A = va as RGB, B = vb as RGB;
      (out[k] as RGB) = k === 'sunDir' ? lerp3(A, B, f) : [geo(A[0], B[0]), geo(A[1], B[1]), geo(A[2], B[2])];
    } else if (k === 'lightIntensity' || k === 'env') (out[k] as number) = geo(va as number, vb as number);
    else (out[k] as number) = (va as number) + ((vb as number) - (va as number)) * f;
  }
  // sun path: swing between the day and night directions through the horizon.
  // The sun sets and the moon rises in a different part of the sky, so the
  // direction swaps halfway through blue hour; the light, the discs, the glow
  // and the sun tint in the fog fade out and back in around the swap instead
  // of jumping (shadows would snap to a new direction otherwise).
  if (i < 2) out.sunDir = norm(out.sunDir);
  else {
    out.sunDir = f < 0.5 ? a.sunDir : b.sunDir;
    const k = Math.min(1, Math.abs(f - 0.5) / 0.32);
    out.disc = k * k * (3 - 2 * k);
    out.lightIntensity *= out.disc;
    out.fogSun = lerp3(out.fog, out.fogSun, out.disc);
  }
  return out;
}

// ------------------------------------------------------------------ CPU sky for IBL

function skyColor(S: Stage, dx: number, dy: number, dz: number, out: number[]) {
  const s = S.sunDir;
  const cosSun = Math.max(0, dx * s[0] + dy * s[1] + dz * s[2]);
  const t = Math.pow(Math.max(0, dy), 0.55);
  let r = S.horizon[0] + (S.zenith[0] - S.horizon[0]) * t;
  let g = S.horizon[1] + (S.zenith[1] - S.horizon[1]) * t;
  let b = S.horizon[2] + (S.zenith[2] - S.horizon[2]) * t;
  const haze = Math.pow(cosSun, 4) * (1 - t) * 1.6 * S.disc;
  r += haze * S.glow[0]; g += haze * S.glow[1]; b += haze * S.glow[2];
  const glow = (Math.pow(cosSun, 64) * 3 + Math.pow(cosSun, 12) * 0.35) * (S.moon > 0.5 ? 0.08 : 1) * S.disc;
  r += glow * S.lightColor[0]; g += glow * S.lightColor[1]; b += glow * S.lightColor[2];
  if (dy > 0.02) {
    const px = dx / (dy + 0.12), pz = dz / (dy + 0.12);
    const c = fbm(px * 1.1 + 3, pz * 1.1, 5, 77);
    const cov = Math.max(0, Math.min(1, (c - 0.02) * 2.2)) * Math.min(1, dy * 6);
    const lit = 0.85 + Math.pow(cosSun, 3) * 0.6 * S.disc;
    r = r * (1 - cov) + (S.cloudShade[0] + (S.cloudLit[0] - S.cloudShade[0]) * lit * 0.8) * cov;
    g = g * (1 - cov) + (S.cloudShade[1] + (S.cloudLit[1] - S.cloudShade[1]) * lit * 0.8) * cov;
    b = b * (1 - cov) + (S.cloudShade[2] + (S.cloudLit[2] - S.cloudShade[2]) * lit * 0.8) * cov;
  }
  if (dy < 0) {
    const k = Math.min(1, -dy * 4);
    const gr = S.fog;
    r = r * (1 - k) + gr[0] * 0.55 * k; g = g * (1 - k) + gr[1] * 0.6 * k; b = b * (1 - k) + gr[2] * 0.55 * k;
  }
  out[0] = r * S.env; out[1] = g * S.env; out[2] = b * S.env;
}

/** mean sky radiance seen by an upward-facing surface (cosine weighted), used
 * to keep the ambient light continuous between the pre-built IBL samples */
const LUM_DIRS: [number, number, number, number][] = [];
for (let j = 0; j < 4; j++) for (let i = 0; i < 12; i++) {
  const el = ((j + 0.5) / 4) * (Math.PI / 2), az = (i / 12) * Math.PI * 2 + j * 0.4;
  LUM_DIRS.push([Math.cos(el) * Math.cos(az), Math.sin(el), Math.cos(el) * Math.sin(az), Math.sin(el)]);
}
function skyLum(S: Stage): number {
  const c = [0, 0, 0];
  let sum = 0, w = 0;
  for (const [x, y, z, k] of LUM_DIRS) {
    skyColor(S, x, y, z, c);
    sum += (c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722) * k;
    w += k;
  }
  return sum / w;
}

function toHalf(v: number): number {
  const f = new Float32Array(1);
  const u = new Uint32Array(f.buffer);
  f[0] = v;
  const x = u[0];
  const sign = (x >> 16) & 0x8000;
  const e = ((x >> 23) & 0xff) - 127 + 15;
  const m = x & 0x7fffff;
  if (e <= 0) return sign;
  if (e >= 31) return sign | 0x7c00;
  return sign | (e << 10) | (m >> 13);
}

function buildEnvAtlas(device: pc.GraphicsDevice, S: Stage): pc.Texture {
  const size = 64;
  const faces: Uint16Array[] = [];
  const c = [0, 0, 0];
  for (let f = 0; f < 6; f++) {
    const data = new Uint16Array(size * size * 4);
    for (let j = 0; j < size; j++) for (let i = 0; i < size; i++) {
      const u = ((i + 0.5) / size) * 2 - 1, v = ((j + 0.5) / size) * 2 - 1;
      let x = 0, y = 0, z = 0;
      switch (f) {
        case 0: x = 1; y = -v; z = -u; break;
        case 1: x = -1; y = -v; z = u; break;
        case 2: x = u; y = 1; z = v; break;
        case 3: x = u; y = -1; z = -v; break;
        case 4: x = u; y = -v; z = 1; break;
        default: x = -u; y = -v; z = -1; break;
      }
      const l = Math.hypot(x, y, z);
      skyColor(S, x / l, y / l, z / l, c);
      const k = (j * size + i) * 4;
      data[k] = toHalf(c[0]); data[k + 1] = toHalf(c[1]); data[k + 2] = toHalf(c[2]); data[k + 3] = toHalf(1);
    }
    faces.push(data);
  }
  const cube = new pc.Texture(device, {
    name: 'skyIbl', cubemap: true, width: size, height: size, format: pc.PIXELFORMAT_RGBA16F, mipmaps: false,
    minFilter: pc.FILTER_LINEAR, magFilter: pc.FILTER_LINEAR,
    addressU: pc.ADDRESS_CLAMP_TO_EDGE, addressV: pc.ADDRESS_CLAMP_TO_EDGE,
    levels: [faces as unknown as Uint8Array[]],
  });
  const lighting = pc.EnvLighting.generateLightingSource(cube);
  const atlas = pc.EnvLighting.generateAtlas(lighting);
  lighting.destroy();
  cube.destroy();
  return atlas;
}

// ------------------------------------------------------------------ GPU sky dome

const DOME_VS = /* glsl */ `
attribute vec3 aPosition;
uniform mat4 matrix_model;
uniform mat4 matrix_viewProjection;
varying vec3 vDir;
void main(void) {
  vDir = aPosition;
  vec4 p = matrix_viewProjection * (matrix_model * vec4(aPosition, 1.0));
  gl_Position = p.xyww;
  gl_Position.z = gl_Position.w * 0.99999;
}`;

const DOME_FS = /* glsl */ `
varying vec3 vDir;
uniform vec3 sky_sun;
uniform vec3 sky_zenith;
uniform vec3 sky_horizon;
uniform vec3 sky_glow;
uniform vec3 sky_light;
uniform vec3 sky_cloudLit;
uniform vec3 sky_cloudShade;
uniform vec3 sky_ground;
uniform float sky_stars;
uniform float sky_moon;
uniform float sky_disc;
uniform float sky_time;
${LATTICE_HASH}
float h21(vec2 p) { return ftLat(p); }
float vn(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), u.x), mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm4(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * vn(p); p = mat2(0.8, -0.6, 0.6, 0.8) * p * 2.03 + 11.7; a *= 0.5; }
  return v;
}
void main(void) {
  vec3 d = normalize(vDir);
  float cosSun = max(dot(d, sky_sun), 0.0);
  float t = pow(max(d.y, 0.0), 0.55);
  vec3 col = mix(sky_horizon, sky_zenith, t);
  float haze = pow(cosSun, 4.0) * (1.0 - t) * 1.6 * sky_disc;
  col += haze * sky_glow;
  // teal night-glow low on the horizon (away from the moon)
  col += vec3(0.0, 0.03, 0.035) * sky_moon * pow(1.0 - abs(d.y), 8.0);
  float glowK = mix(1.0, 0.08, sky_moon) * sky_disc;
  col += (pow(cosSun, 64.0) * 3.0 + pow(cosSun, 12.0) * 0.35) * sky_light * glowK;
  // disc: sun (bright, soft edge) or moon (cool, with maria)
  float disc = smoothstep(0.99955, 0.99975, cosSun);
  vec3 moonC = vec3(2.2, 2.3, 2.5) * (0.82 + 0.18 * vn(d.xz * 900.0));
  col += disc * mix(sky_light * 38.0, moonC, sky_moon) * sky_disc;
  col += smoothstep(0.996, 1.0, cosSun) * sky_moon * sky_disc * vec3(0.05, 0.07, 0.1);
  // clouds on a virtual plane
  if (d.y > 0.0) {
    vec2 pp = d.xz / (d.y + 0.12);
    float c = fbm4(pp * 1.4 + vec2(sky_time * 0.004, 0.0) + 3.0);
    float cov = clamp((c - 0.47) * 3.2, 0.0, 1.0) * clamp(d.y * 6.0, 0.0, 1.0);
    float lit = 0.8 + pow(cosSun, 3.0) * 0.6 * sky_disc;
    vec3 cc = mix(sky_cloudShade, sky_cloudLit, clamp(lit * 0.75 + (c - 0.5), 0.0, 1.2));
    col = mix(col, cc, cov * 0.92);
    // stars: one per grid cell, twinkling, hidden by clouds and near the horizon
    if (sky_stars > 0.001) {
      vec2 cell = floor(vec2(atan(d.z, d.x) * 180.0 / 1.6, asin(d.y) * 180.0 / 1.6));
      float r = h21(cell);
      vec2 f = fract(vec2(atan(d.z, d.x) * 180.0 / 1.6, asin(d.y) * 180.0 / 1.6)) - vec2(h21(cell + 3.1), h21(cell + 7.7)) * 0.8 - 0.1;
      float star = step(0.86, r) * smoothstep(0.09, 0.0, length(f)) * (0.6 + 2.8 * pow(h21(cell + 1.3), 6.0));
      star *= 0.7 + 0.3 * sin(sky_time * (1.5 + r * 3.0) + r * 40.0);
      // milky band
      float bk = dot(d, normalize(vec3(0.5, 0.3, 0.8))) * 3.2;
      float band = exp(-bk * bk) * fbm4(d.xz * 8.0) * 0.05;
      col += (vec3(star) * vec3(0.9, 0.95, 1.0) + vec3(0.6, 0.7, 0.9) * band) * sky_stars * (1.0 - cov) * smoothstep(0.02, 0.2, d.y);
    }
  } else {
    col = mix(col, sky_ground, clamp(-d.y * 4.0, 0.0, 1.0));
  }
  gl_FragColor = vec4(col, 1.0);
}`;

const IBL_STEPS = 13;

export class Environment {
  t = 0;
  sun: pc.Entity;
  dome: pc.Entity;
  private domeMat: pc.ShaderMaterial;
  /** image based lighting sampled at IBL_STEPS evenly spaced times of day */
  private atlases: (pc.Texture | null)[] = new Array(IBL_STEPS).fill(null);
  private atlasLum: number[] = new Array(IBL_STEPS).fill(0);
  private atlasIndex = -1;
  /** 0 day … 1 night: drives lamps, windows, fireflies */
  night = 0;
  current: Stage = STAGES[0];
  /** materials that light up at night (window panes, bulbs) */
  glowMats: pc.StandardMaterial[] = [];
  onChange: ((t: number) => void)[] = [];
  private time = 0;
  private targetT = 0;
  private speed = 0;

  constructor(private app: pc.AppBase) {
    const scene = app.scene;
    scene.fog.type = pc.FOG_LINEAR;
    scene.ambientLight = new pc.Color(0, 0, 0);
    scene.skyboxIntensity = 1;
    this.sun = new pc.Entity('sun');
    this.sun.addComponent('light', {
      type: 'directional',
      color: new pc.Color(1.0, 0.9, 0.76),
      intensity: 2.4,
      castShadows: true,
      shadowType: pc.SHADOW_PCF3_32F,
      shadowResolution: 2048,
      numCascades: 3,
      cascadeDistribution: 0.62,
      shadowDistance: 150,
      shadowBias: 0.25,
      normalOffsetBias: 0.6,
    });
    app.root.addChild(this.sun);
    // sky dome
    this.domeMat = new pc.ShaderMaterial({
      uniqueName: 'ftSkyDome',
      vertexGLSL: DOME_VS,
      fragmentGLSL: DOME_FS,
      attributes: { aPosition: pc.SEMANTIC_POSITION },
    });
    this.domeMat.cull = pc.CULLFACE_FRONT;
    this.domeMat.depthWrite = false;
    this.domeMat.update();
    const mesh = pc.Mesh.fromGeometry(app.graphicsDevice, new pc.SphereGeometry({ radius: 1, latitudeBands: 32, longitudeBands: 48 }));
    const mi = new pc.MeshInstance(mesh, this.domeMat);
    mi.cull = false;
    this.dome = new pc.Entity('skyDome');
    this.dome.addComponent('render', { meshInstances: [mi], castShadows: false, receiveShadows: false });
    this.dome.setLocalScale(1200, 1200, 1200);
    app.root.addChild(this.dome);
    const device = app.graphicsDevice;
    app.on('prerender', () => {
      const S = this.current;
      device.scope.resolve('ft_fogSun').setValue(S.fogSun);
      device.scope.resolve('ft_sunDir').setValue(S.sunDir);
    });
    this.apply(0, true);
  }

  private atlas(i: number): pc.Texture {
    if (!this.atlases[i]) {
      const S = stageAt(i / (IBL_STEPS - 1));
      this.atlases[i] = buildEnvAtlas(this.app.graphicsDevice, S);
      this.atlasLum[i] = skyLum(S);
    }
    return this.atlases[i]!;
  }

  /** build the IBL samples ahead of time (called while loading) */
  prewarm() {
    for (let i = 0; i < IBL_STEPS; i++) this.atlas(i);
  }

  /** jump (speed 0) or sweep towards a time of day */
  setTime(target: number, secs = 0) {
    this.targetT = Math.max(0, Math.min(1, target));
    if (secs <= 0) { this.speed = 0; this.apply(this.targetT); }
    else this.speed = Math.abs(this.targetT - this.t) / secs;
  }

  get transitioning() { return this.speed > 0 && Math.abs(this.targetT - this.t) > 1e-4; }

  private apply(t: number, force = false) {
    this.t = t;
    const S = stageAt(t);
    this.current = S;
    this.night = Math.max(0, Math.min(1, (t - 0.45) / 0.45));
    const scene = this.app.scene;
    scene.fog.color = new pc.Color(S.fog[0], S.fog[1], S.fog[2]);
    scene.fog.start = S.fogStart;
    scene.fog.end = S.fogEnd;
    scene.exposure = S.exposure;
    const l = this.sun.light!;
    l.color = new pc.Color(S.lightColor[0], S.lightColor[1], S.lightColor[2]);
    l.intensity = S.lightIntensity;
    // light points along -Y of the entity: aim it along -sunDir
    this.sun.setEulerAngles(0, 0, 0);
    this.sun.lookAt(-S.sunDir[0], -S.sunDir[1], -S.sunDir[2]);
    this.sun.rotateLocal(-90, 0, 0);
    const m = this.domeMat;
    m.setParameter('sky_sun', S.sunDir);
    m.setParameter('sky_zenith', S.zenith);
    m.setParameter('sky_horizon', S.horizon);
    m.setParameter('sky_glow', S.glow);
    m.setParameter('sky_light', S.lightColor);
    m.setParameter('sky_cloudLit', S.cloudLit);
    m.setParameter('sky_cloudShade', S.cloudShade);
    m.setParameter('sky_ground', [S.fog[0] * 0.55, S.fog[1] * 0.6, S.fog[2] * 0.55]);
    m.setParameter('sky_stars', S.stars);
    m.setParameter('sky_moon', S.moon);
    m.setParameter('sky_disc', S.disc);
    // image based lighting: the nearest pre-built sample, rescaled so the
    // ambient brightness follows t continuously instead of stepping
    const idx = Math.round(Math.max(0, Math.min(1, t)) * (IBL_STEPS - 1));
    if (idx !== this.atlasIndex || force) {
      this.atlasIndex = idx;
      scene.envAtlas = this.atlas(idx);
    }
    const ref = this.atlasLum[idx];
    const k = ref > 1e-6 ? Math.max(0.5, Math.min(2, skyLum(S) / ref)) : 1;
    // write the backing field: the public setter also flags every material for a
    // shader rebuild, which is only needed when env lighting is switched on or off
    (scene as unknown as { _skyboxIntensity: number })._skyboxIntensity = k;
    for (const gm of this.glowMats) {
      gm.emissive = new pc.Color(1, 0.72, 0.38);
      gm.emissiveIntensity = this.night * 3.2;
      gm.update();
    }
    for (const f of this.onChange) f(t);
  }

  update(dt: number, camPos: pc.Vec3) {
    this.time += dt;
    this.domeMat.setParameter('sky_time', this.time);
    this.dome.setPosition(camPos);
    if (this.speed > 0 && Math.abs(this.targetT - this.t) > 1e-4) {
      const step = Math.sign(this.targetT - this.t) * Math.min(Math.abs(this.targetT - this.t), this.speed * dt);
      this.apply(this.t + step);
    }
  }
}
