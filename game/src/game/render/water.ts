// Lake and creek surfaces: vertex-tinted translucent water with two
// scrolling procedural normal maps and sky reflections.
import * as pc from 'playcanvas';
import type { Terrain } from '../world/terrain';
import { LAKE, LAKE_LEVEL, STREAM_WIDTH } from '../world/layout';
import { clamp } from '../world/noise';
import { applyFog } from './shaders';

function makeNormalMap(device: pc.GraphicsDevice, size = 256, seed = 1): pc.Texture {
  // tileable height from a sum of periodic sines, converted to normals
  const h = new Float32Array(size * size);
  const waves: [number, number, number, number][] = [];
  let s = seed;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 24; i++) {
    const kx = Math.round((rnd() - 0.5) * 16), kz = Math.round((rnd() - 0.5) * 16);
    waves.push([kx, kz, rnd() * 6.28, 1 / (1 + Math.hypot(kx, kz))]);
  }
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    let v = 0;
    for (const [kx, kz, ph, a] of waves) v += Math.sin(((kx * x + kz * y) / size) * Math.PI * 2 + ph) * a;
    h[y * size + x] = v;
  }
  const data = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const hx = h[y * size + ((x + 1) % size)] - h[y * size + ((x - 1 + size) % size)];
    const hy = h[((y + 1) % size) * size + x] - h[((y - 1 + size) % size) * size + x];
    const nx = -hx * 1.6, ny = -hy * 1.6, nz = 1;
    const l = Math.hypot(nx, ny, nz);
    const k = (y * size + x) * 4;
    data[k] = ((nx / l) * 0.5 + 0.5) * 255;
    data[k + 1] = ((ny / l) * 0.5 + 0.5) * 255;
    data[k + 2] = ((nz / l) * 0.5 + 0.5) * 255;
    data[k + 3] = 255;
  }
  return new pc.Texture(device, {
    name: 'waterNormal', width: size, height: size, format: pc.PIXELFORMAT_RGBA8, mipmaps: true,
    addressU: pc.ADDRESS_REPEAT, addressV: pc.ADDRESS_REPEAT, levels: [data],
    minFilter: pc.FILTER_LINEAR_MIPMAP_LINEAR, magFilter: pc.FILTER_LINEAR,
  });
}

export class WaterRender {
  material: pc.StandardMaterial;
  private t = 0;

  constructor(app: pc.AppBase, private T: Terrain) {
    const device = app.graphicsDevice;
    const mat = new pc.StandardMaterial();
    mat.name = 'water';
    mat.diffuse = new pc.Color(1, 1, 1);
    mat.diffuseVertexColor = true;
    mat.diffuseVertexColorChannel = 'rgb';
    mat.opacityVertexColor = true;
    mat.opacityVertexColorChannel = 'a';
    mat.blendType = pc.BLEND_NORMAL;
    mat.depthWrite = false;
    mat.cull = pc.CULLFACE_NONE;
    mat.useMetalness = true;
    mat.metalness = 0;
    mat.gloss = 0.9;
    mat.specularityFactor = 0.7;
    mat.normalMap = makeNormalMap(device, 256, 7);
    mat.normalMapTiling = new pc.Vec2(0.09, 0.09);
    mat.bumpiness = 0.35;
    mat.normalDetailMap = makeNormalMap(device, 256, 99);
    mat.normalDetailMapTiling = new pc.Vec2(0.31, 0.31);
    mat.normalDetailMapBumpiness = 0.6;
    mat.useFog = true;
    applyFog(mat);
    mat.update();
    this.material = mat;

    const root = new pc.Entity('water');
    const lake = this.buildLake(device);
    const creek = this.buildCreek(device);
    for (const mesh of [lake, creek]) {
      const mi = new pc.MeshInstance(mesh, mat);
      mi.castShadow = false;
      const e = new pc.Entity();
      e.addComponent('render', { meshInstances: [mi], castShadows: false, receiveShadows: true });
      root.addChild(e);
    }
    app.root.addChild(root);
  }

  private tint(depth: number, flow: number, out: number[]) {
    const d = clamp(depth, 0, 4);
    const shallow = [0.26, 0.42, 0.4], deep = [0.04, 0.13, 0.16];
    const t = clamp(d / 2.2, 0, 1);
    out[0] = shallow[0] + (deep[0] - shallow[0]) * t;
    out[1] = shallow[1] + (deep[1] - shallow[1]) * t;
    out[2] = shallow[2] + (deep[2] - shallow[2]) * t;
    // foam at the very edge and on fast shallow water
    const foam = clamp(1 - d / 0.08, 0, 1) * 0.5 + flow * clamp(1 - d / 0.4, 0, 1) * 0.25;
    out[0] += foam * 0.4; out[1] += foam * 0.4; out[2] += foam * 0.4;
    out[3] = clamp(0.12 + d * 0.6 + foam * 0.35, 0.0, 0.94) * clamp(d / 0.04, 0, 1);
  }

  private buildLake(device: pc.GraphicsDevice): pc.Mesh {
    const T = this.T;
    const cell = 2;
    const x0 = LAKE.cx - LAKE.rx * 1.35, x1 = LAKE.cx + LAKE.rx * 1.35;
    const z0 = LAKE.cz - LAKE.rz * 1.45, z1 = LAKE.cz + LAKE.rz * 1.35;
    const nx = Math.ceil((x1 - x0) / cell) + 1, nz = Math.ceil((z1 - z0) / cell) + 1;
    const pos: number[] = [], col: number[] = [], nor: number[] = [], uv: number[] = [];
    const index = new Int32Array(nx * nz).fill(-1);
    const c = [0, 0, 0, 0];
    const wet = (x: number, z: number) => T.heightAt(x, z) < LAKE_LEVEL + 0.25;
    for (let j = 0; j < nz; j++) for (let i = 0; i < nx; i++) {
      const x = x0 + i * cell, z = z0 + j * cell;
      if (!(wet(x, z) || wet(x + cell, z) || wet(x, z + cell) || wet(x - cell, z) || wet(x, z - cell))) continue;
      index[j * nx + i] = pos.length / 3;
      pos.push(x, LAKE_LEVEL, z);
      nor.push(0, 1, 0);
      uv.push(x, z);
      this.tint(LAKE_LEVEL - T.heightAt(x, z), 0, c);
      col.push(Math.round(c[0] * 255), Math.round(c[1] * 255), Math.round(c[2] * 255), Math.round(c[3] * 255));
    }
    const idx: number[] = [];
    for (let j = 0; j < nz - 1; j++) for (let i = 0; i < nx - 1; i++) {
      const a = index[j * nx + i], b = index[j * nx + i + 1], cc = index[(j + 1) * nx + i], d = index[(j + 1) * nx + i + 1];
      if (a < 0 || b < 0 || cc < 0 || d < 0) continue;
      idx.push(a, cc, b, b, cc, d);
    }
    return this.mesh(device, pos, nor, uv, col, idx);
  }

  private buildCreek(device: pc.GraphicsDevice): pc.Mesh {
    const T = this.T;
    const S = T.stream.samples;
    const pos: number[] = [], col: number[] = [], nor: number[] = [], uv: number[] = [];
    const idx: number[] = [];
    const across = 9;
    const hw = STREAM_WIDTH / 2 + 1.8;
    const c = [0, 0, 0, 0];
    let rows = 0;
    for (let i = 0; i < S.length; i += 2) {
      const s = S[i];
      const level = Math.max(LAKE_LEVEL + 0.01, T.streamBed[i] + T.streamDepth[i]);
      if (level <= LAKE_LEVEL + 0.02 && Math.hypot((s.x - LAKE.cx) / LAKE.rx, (s.z - LAKE.cz) / LAKE.rz) < 1.0) break;
      const slope = i > 2 ? Math.max(0, T.streamBed[i - 2] - T.streamBed[i]) : 0;
      for (let k = 0; k < across; k++) {
        const t = (k / (across - 1)) * 2 - 1;
        const x = s.x + -s.tz * t * hw, z = s.z + s.tx * t * hw;
        pos.push(x, level, z);
        nor.push(0, 1, 0);
        // uv flows downstream
        uv.push(t * hw, -s.s);
        this.tint(level - T.heightAt(x, z), clamp(slope * 6, 0, 1), c);
        col.push(Math.round(c[0] * 255), Math.round(c[1] * 255), Math.round(c[2] * 255), Math.round(c[3] * 255));
      }
      if (rows > 0) {
        const base = rows * across;
        for (let k = 0; k < across - 1; k++) {
          const a = base - across + k, b = a + 1, cc = base + k, d = cc + 1;
          idx.push(a, cc, b, b, cc, d);
        }
      }
      rows++;
    }
    return this.mesh(device, pos, nor, uv, col, idx);
  }

  private mesh(device: pc.GraphicsDevice, pos: number[], nor: number[], uv: number[], col: number[], idx: number[]) {
    const m = new pc.Mesh(device);
    m.setPositions(pos);
    m.setNormals(nor);
    m.setUvs(0, uv);
    m.setColors32(col);
    m.setIndices(pos.length / 3 > 65535 ? new Uint32Array(idx) : new Uint16Array(idx));
    m.update();
    return m;
  }

  update(dt: number) {
    this.t += dt;
    const m = this.material;
    m.normalMapOffset = new pc.Vec2(this.t * 0.004, this.t * 0.011);
    m.normalDetailMapOffset = new pc.Vec2(-this.t * 0.013, this.t * 0.02);
    m.update();
  }
}
