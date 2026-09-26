// Distant mountains outside the playable map: three rings of lit, fogged
// relief with forested flanks, rock and snow caps, plus animated waterfall
// ribbons on the northern range facing the valley.
import * as pc from 'playcanvas';
import { fbm, mulberry32 } from '../world/noise';
import { LATTICE_HASH, applyFog } from './shaders';

interface Ring { r: number; depth: number; h: number; seed: number; snow: number }

const RINGS: Ring[] = [
  { r: 470, depth: 160, h: 95, seed: 1, snow: 0.72 },
  { r: 700, depth: 230, h: 170, seed: 2, snow: 0.55 },
  { r: 1000, depth: 260, h: 250, seed: 3, snow: 0.45 },
];

/** mountain height at angle a (radians) and radial position u (0 inner edge .. 1 outer edge) */
function heightAt(R: Ring, a: number, u: number): number {
  const ca = Math.cos(a) * 3, sa = Math.sin(a) * 3;
  const ridge = 1 - Math.abs(fbm(ca + R.seed * 7, sa, 4, R.seed) );
  const base = fbm(ca * 0.6 + 11, sa * 0.6, 3, R.seed + 10) * 0.5 + 0.5;
  // the north range (towards -Z) is the tallest, like a ridge behind the lake
  const north = 0.75 + 0.45 * Math.max(0, -Math.sin(a));
  const peak = R.h * (0.35 + base * 0.55 + ridge * ridge * 0.45) * north;
  const bell = Math.sin(Math.min(1, u * 1.15) * Math.PI) ** 0.8;
  const detail = fbm(Math.cos(a) * 40 + u * 5, Math.sin(a) * 40, 3, R.seed + 20) * R.h * 0.06;
  return -25 + (peak + detail) * bell;
}

const FALL_VS = /* glsl */ `
attribute vec3 aPosition;
attribute vec2 aUv0;
uniform mat4 matrix_model;
uniform mat4 matrix_viewProjection;
varying vec2 vUv;
varying vec3 vPosW;
void main(void) {
  vUv = aUv0;
  vec4 w = matrix_model * vec4(aPosition, 1.0);
  vPosW = w.xyz;
  gl_Position = matrix_viewProjection * w;
}`;

const FALL_FS = /* glsl */ `
varying vec2 vUv;
varying vec3 vPosW;
uniform float ft_time;
uniform vec3 fog_color;
uniform float fog_start;
uniform float fog_end;
uniform vec3 view_position;
uniform float fall_light;
${LATTICE_HASH}
float h21(vec2 p) { return ftLat(p); }
float vn(vec2 p) { vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), u.x), mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), u.x), u.y); }
void main(void) {
  float streak = vn(vec2(vUv.x * 9.0, vUv.y * 3.0 + ft_time * 1.6)) * 0.6 + vn(vec2(vUv.x * 23.0, vUv.y * 7.0 + ft_time * 2.6)) * 0.4;
  float edge = smoothstep(0.0, 0.22, vUv.x) * smoothstep(1.0, 0.78, vUv.x);
  float a = clamp(streak * 1.4 - 0.25, 0.0, 1.0) * edge;
  vec3 c = mix(vec3(0.55, 0.68, 0.74), vec3(0.95, 0.97, 1.0), streak) * fall_light;
  float d = length(vPosW - view_position);
  float f = clamp((d - fog_start) / (fog_end - fog_start), 0.0, 1.0);
  f = 1.0 - exp(-f * f * 1.7 * 0.6);
  c = mix(c, fog_color, f);
  gl_FragColor = vec4(c, a * (1.0 - f * 0.6));
}`;

export class Mountains {
  root: pc.Entity;
  private fallMat: pc.ShaderMaterial;

  constructor(app: pc.AppBase) {
    const device = app.graphicsDevice;
    this.root = new pc.Entity('mountains');
    const mat = new pc.StandardMaterial();
    mat.diffuse = new pc.Color(1, 1, 1);
    mat.diffuseVertexColor = true;
    mat.gloss = 0.12;
    mat.useMetalness = true;
    mat.metalness = 0;
    applyFog(mat, 0.8);
    mat.update();
    const rnd = mulberry32(99);
    const falls: [number, number][] = [];
    for (const R of RINGS) {
      const seg = 360, rows = 9;
      const pos: number[] = [], col: number[] = [], idx: number[] = [];
      for (let i = 0; i <= seg; i++) {
        const a = (i / seg) * Math.PI * 2;
        for (let j = 0; j <= rows; j++) {
          const u = j / rows;
          const rr = R.r + u * R.depth + fbm(Math.cos(a) * 9, Math.sin(a) * 9, 2, R.seed + 30) * 20;
          const h = heightAt(R, a, u);
          pos.push(Math.cos(a) * rr, h, Math.sin(a) * rr);
        }
      }
      for (let i = 0; i < seg; i++) for (let j = 0; j < rows; j++) {
        const a = i * (rows + 1) + j, b = a + 1, c = a + rows + 1, d = c + 1;
        idx.push(a, b, c, b, d, c);
      }
      // colours from height and slope: forest, scree, rock, snow
      const nor = pc.calculateNormals(pos, idx);
      for (let k = 0; k < pos.length / 3; k++) {
        const y = pos[k * 3 + 1];
        const ny = nor[k * 3 + 1];
        const x = pos[k * 3], z = pos[k * 3 + 2];
        const n = fbm(x / 60, z / 60, 3, R.seed + 40) * 0.5 + 0.5;
        const t = (y + 25) / (R.h * 1.4);
        const forest: [number, number, number] = [0.13 + n * 0.05, 0.22 + n * 0.06, 0.16];
        const rock: [number, number, number] = [0.36 + n * 0.08, 0.35 + n * 0.07, 0.34 + n * 0.06];
        const snow: [number, number, number] = [0.9, 0.93, 0.97];
        let c = forest;
        const rockK = Math.min(1, Math.max(0, (t - 0.25 + (1 - ny) * 0.6) * 2.2));
        c = [c[0] + (rock[0] - c[0]) * rockK, c[1] + (rock[1] - c[1]) * rockK, c[2] + (rock[2] - c[2]) * rockK];
        const snowK = Math.min(1, Math.max(0, (t - R.snow + n * 0.18) * 5)) * Math.min(1, Math.max(0, (ny - 0.45) * 3));
        c = [c[0] + (snow[0] - c[0]) * snowK, c[1] + (snow[1] - c[1]) * snowK, c[2] + (snow[2] - c[2]) * snowK];
        col.push(c[0], c[1], c[2], 1);
      }
      const mesh = new pc.Mesh(device);
      mesh.setPositions(pos);
      mesh.setNormals(nor);
      mesh.setColors(col);
      mesh.setIndices(idx);
      mesh.update();
      const mi = new pc.MeshInstance(mesh, mat);
      mi.castShadow = false;
      mi.cull = false;
      const e = new pc.Entity('mountainRing');
      e.addComponent('render', { meshInstances: [mi], castShadows: false, receiveShadows: false });
      this.root.addChild(e);
      if (R === RINGS[0]) {
        // two falls on the north range, facing the lake
        for (const a of [-Math.PI / 2 - 0.22 - rnd() * 0.05, -Math.PI / 2 + 0.3]) falls.push([a, R.r]);
      }
    }
    this.fallMat = new pc.ShaderMaterial({
      uniqueName: 'ftWaterfall', vertexGLSL: FALL_VS, fragmentGLSL: FALL_FS,
      attributes: { aPosition: pc.SEMANTIC_POSITION, aUv0: pc.SEMANTIC_TEXCOORD0 },
    });
    this.fallMat.blendType = pc.BLEND_NORMAL;
    this.fallMat.depthWrite = false;
    this.fallMat.cull = pc.CULLFACE_NONE;
    this.fallMat.setParameter('fall_light', 1);
    this.fallMat.update();
    for (const [a] of falls) this.addFall(device, RINGS[0], a);
    app.root.addChild(this.root);
  }

  /** ribbon hugging the mountain face along the radial line at angle a */
  private addFall(device: pc.GraphicsDevice, R: Ring, a: number) {
    const pos: number[] = [], uv: number[] = [], idx: number[] = [];
    const rows = 24, width = 7;
    const ca = Math.cos(a), sa = Math.sin(a);
    const px = -sa, pz = ca; // across the fall
    for (let j = 0; j <= rows; j++) {
      const u = 0.06 + (j / rows) * 0.36; // from the foot up to near the crest
      const rr = R.r + u * R.depth;
      const h = heightAt(R, a, u) + 1.5;
      for (const s of [-1, 1]) {
        const w = (width * (0.6 + 0.4 * (1 - j / rows))) / 2;
        pos.push(ca * rr + px * w * s, h, sa * rr + pz * w * s);
        uv.push(s < 0 ? 0 : 1, j / 4);
      }
      if (j > 0) {
        const k = (j - 1) * 2;
        idx.push(k, k + 2, k + 1, k + 1, k + 2, k + 3);
      }
    }
    const mesh = new pc.Mesh(device);
    mesh.setPositions(pos);
    mesh.setUvs(0, uv);
    mesh.setIndices(idx);
    mesh.update();
    const mi = new pc.MeshInstance(mesh, this.fallMat);
    mi.cull = false;
    const e = new pc.Entity('waterfall');
    e.addComponent('render', { meshInstances: [mi], castShadows: false, receiveShadows: false });
    this.root.addChild(e);
  }

  /** dimmer falls at night */
  setLight(k: number) {
    this.fallMat.setParameter('fall_light', k);
  }
}
