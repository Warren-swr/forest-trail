// Driving feedback visuals: dust, mud and water particles (CPU pool drawn as
// one dynamic billboard mesh) and fading tyre tracks.
import * as pc from 'playcanvas';
import type { Game } from '../Game';
import { applyFog } from './shaders';


const MAXP = 420;
const TRACK_SEGS = 900;

interface P { x: number; y: number; z: number; vx: number; vy: number; vz: number; life: number; max: number; size: number; grow: number; r: number; g: number; b: number; a: number; grav: number }

function spriteTexture(device: pc.GraphicsDevice) {
  const n = 64;
  const d = new Uint8Array(n * n * 4);
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    const dx = (x + 0.5) / n * 2 - 1, dy = (y + 0.5) / n * 2 - 1;
    const r = Math.sqrt(dx * dx + dy * dy);
    const a = Math.max(0, 1 - r);
    const k = (y * n + x) * 4;
    d[k] = 255; d[k + 1] = 255; d[k + 2] = 255; d[k + 3] = Math.round(Math.pow(a, 1.6) * 255);
  }
  return new pc.Texture(device, { width: n, height: n, format: pc.PIXELFORMAT_RGBA8, mipmaps: true, levels: [d], addressU: pc.ADDRESS_CLAMP_TO_EDGE, addressV: pc.ADDRESS_CLAMP_TO_EDGE });
}

export class Effects {
  private parts: P[] = [];
  private mesh: pc.Mesh;
  private pos = new Float32Array(MAXP * 4 * 3);
  private uv = new Float32Array(MAXP * 4 * 2);
  private col = new Uint8Array(MAXP * 4 * 4);
  private trackMesh: pc.Mesh;
  private tPos = new Float32Array(TRACK_SEGS * 4 * 3);
  private tCol = new Uint8Array(TRACK_SEGS * 4 * 4);
  private tAge = new Float32Array(TRACK_SEGS).fill(999);
  private tStrength = new Float32Array(TRACK_SEGS);
  private tNext = 0;
  private last: ({ x: number; z: number; y: number } | null)[] = [null, null, null, null];
  private emitAcc = [0, 0, 0, 0];
  private time = 0;
  private rnd = Math.random;

  constructor(private g: Game) {
    const device = g.app.graphicsDevice;
    // particles
    const idx = new Uint16Array(MAXP * 6);
    for (let i = 0; i < MAXP; i++) {
      idx.set([i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3], i * 6);
      this.uv.set([0, 0, 1, 0, 1, 1, 0, 1], i * 8);
    }
    this.mesh = new pc.Mesh(device);
    this.mesh.setPositions(this.pos);
    this.mesh.setNormals(upNormals(MAXP * 4));
    this.mesh.setUvs(0, this.uv);
    this.mesh.setColors32(this.col);
    this.mesh.setIndices(idx);
    this.mesh.update(pc.PRIMITIVE_TRIANGLES, false);
    const mat = new pc.StandardMaterial();
    mat.diffuse = new pc.Color(1, 1, 1);
    mat.diffuseVertexColor = true;
    mat.opacityMap = spriteTexture(device);
    mat.opacityMapChannel = 'a';
    mat.opacityVertexColor = true;
    mat.opacityVertexColorChannel = 'a';
    mat.blendType = pc.BLEND_NORMAL;
    mat.depthWrite = false;
    mat.cull = pc.CULLFACE_NONE;
    mat.useSkybox = false;
    mat.specularityFactor = 0;
    applyFog(mat);
    mat.update();
    const mi = new pc.MeshInstance(this.mesh, mat);
    mi.cull = false;
    mi.castShadow = false;
    const e = new pc.Entity('particles');
    e.addComponent('render', { meshInstances: [mi], castShadows: false, receiveShadows: false });
    g.app.root.addChild(e);

    // tracks
    const tIdx = new Uint16Array(TRACK_SEGS * 6);
    for (let i = 0; i < TRACK_SEGS; i++) tIdx.set([i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3], i * 6);
    this.trackMesh = new pc.Mesh(device);
    this.trackMesh.setPositions(this.tPos);
    this.trackMesh.setNormals(upNormals(TRACK_SEGS * 4));
    this.trackMesh.setColors32(this.tCol);
    this.trackMesh.setIndices(tIdx);
    this.trackMesh.update(pc.PRIMITIVE_TRIANGLES, false);
    const tm = new pc.StandardMaterial();
    tm.diffuse = new pc.Color(1, 1, 1);
    tm.diffuseVertexColor = true;
    tm.opacityVertexColor = true;
    tm.opacityVertexColorChannel = 'a';
    tm.blendType = pc.BLEND_NORMAL;
    tm.depthWrite = false;
    tm.depthBias = -1;
    tm.slopeDepthBias = -2;
    tm.gloss = 0.35;
    tm.cull = pc.CULLFACE_NONE;
    applyFog(tm);
    tm.update();
    const tmi = new pc.MeshInstance(this.trackMesh, tm);
    tmi.cull = false;
    const te = new pc.Entity('tracks');
    te.addComponent('render', { meshInstances: [tmi], castShadows: false, receiveShadows: true });
    g.app.root.addChild(te);
  }

  private spawn(p: Partial<P> & { x: number; y: number; z: number }) {
    if (this.parts.length >= MAXP) this.parts.shift();
    this.parts.push({ vx: 0, vy: 0, vz: 0, life: 0, max: 1, size: 0.3, grow: 0.5, r: 0.6, g: 0.55, b: 0.45, a: 0.5, grav: 0, ...p });
  }

  update(dt: number) {
    const g = this.g;
    if (g.paused) { this.upload(); return; }
    this.time += dt;
    const v = g.vehicle;
    const T = g.terrain;
    const q = v.rot;
    const speed = Math.abs(v.forwardSpeed);
    const rv = { x: 0, y: 0, z: 0 };
    for (let i = 0; i < 4; i++) {
      const w = v.wheels[i];
      if (!w.grounded) { this.last[i] = null; continue; }
      const cx = w.contact.x, cz = w.contact.z;
      const water = T.waterDepthAt(cx, cz);
      const slipV = w.spinning ? 6 : w.sliding ? 3 : 0;
      const intensity = speed + slipV;
      // --- particles
      let rate = 0;
      let col: [number, number, number, number] = [0.62, 0.55, 0.44, 0.35];
      let kind: 'dust' | 'mud' | 'water' = 'dust';
      if (water > 0.04) { kind = 'water'; rate = speed > 0.8 ? speed * 9 * Math.min(1, water * 4) : 0; col = [0.82, 0.88, 0.88, 0.55]; }
      else if (w.mud > 0.4) { kind = 'mud'; rate = (w.spinning ? 30 : 0) + speed * 3; col = [0.26, 0.21, 0.16, 0.9]; }
      else if (w.surface === 'dirt' || w.surface === 'gravel') { rate = speed > 2.5 ? (speed - 2.5) * 4.5 + slipV * 3 : 0; if (w.surface === 'gravel') col = [0.64, 0.61, 0.55, 0.3]; }
      else if (w.surface === 'grass') rate = w.spinning ? 6 : 0;
      this.emitAcc[i] += rate * dt;
      while (this.emitAcc[i] >= 1) {
        this.emitAcc[i] -= 1;
        // behind the wheel, thrown back and up
        const back = { x: 0, y: 0, z: 0 };
        const dirSign = v.forwardSpeed >= 0 ? 1 : -1;
        rotateVec(back, q, (this.rnd() - 0.5) * 0.6, 0, dirSign * (0.3 + this.rnd() * 0.3));
        const base = { x: cx + back.x, y: w.contact.y + 0.08, z: cz + back.z };
        rotateVec(rv, q, (this.rnd() - 0.5) * 1.2, 0, dirSign * (0.8 + intensity * 0.15));
        if (kind === 'dust') {
          this.spawn({ ...base, vx: rv.x * 0.6, vy: 0.4 + this.rnd() * 0.5, vz: rv.z * 0.6, max: 1.6 + this.rnd(), size: 0.35, grow: 1.4, r: col[0], g: col[1], b: col[2], a: col[3] * (0.6 + this.rnd() * 0.4), grav: -0.1 });
        } else if (kind === 'mud') {
          this.spawn({ ...base, vx: rv.x * (1 + this.rnd()), vy: 1.2 + this.rnd() * 2.2 * (w.spinning ? 1.4 : 0.6), vz: rv.z * (1 + this.rnd()), max: 0.9, size: 0.09 + this.rnd() * 0.07, grow: 0, r: col[0], g: col[1], b: col[2], a: col[3], grav: 9 });
        } else {
          this.spawn({ ...base, y: w.contact.y + water, vx: rv.x * 0.7 + (this.rnd() - 0.5), vy: 1.4 + this.rnd() * 1.8 * Math.min(1, speed / 3), vz: rv.z * 0.7 + (this.rnd() - 0.5), max: 0.8, size: 0.16 + this.rnd() * 0.12, grow: 0.5, r: col[0], g: col[1], b: col[2], a: col[3], grav: 8 });
        }
      }
      // --- tracks
      const soft = water < 0.05 && (w.mud > 0.2 || w.surface === 'dirt' || w.surface === 'grass' || w.surface === 'gravel');
      const last = this.last[i];
      if (!soft) { this.last[i] = null; continue; }
      if (!last) { this.last[i] = { x: cx, z: cz, y: w.contact.y }; continue; }
      const dx = cx - last.x, dz = cz - last.z;
      const d = Math.hypot(dx, dz);
      if (d < 0.4) continue;
      if (d > 2) { this.last[i] = { x: cx, z: cz, y: w.contact.y }; continue; }
      const strength = w.mud > 0.2 ? 0.75 : w.surface === 'grass' ? 0.25 : w.surface === 'gravel' ? 0.18 : 0.32;
      this.addTrack(last.x, last.z, cx, cz, this.g.vehicle.spec.wheelWidth * 0.9, strength + (w.spinning ? 0.2 : 0));
      this.last[i] = { x: cx, z: cz, y: w.contact.y };
    }
    // --- simulate particles
    const out: P[] = [];
    for (const p of this.parts) {
      p.life += dt;
      if (p.life >= p.max) continue;
      p.vy -= p.grav * dt;
      p.vx *= 1 - dt * 1.2; p.vz *= 1 - dt * 1.2;
      p.x += p.vx * dt; p.y += p.vy * dt; p.z += p.vz * dt;
      const gh = T.heightAt(p.x, p.z);
      if (p.y < gh + 0.02 && p.grav > 0) { p.y = gh + 0.02; p.vx *= 0.3; p.vz *= 0.3; p.vy = 0; }
      out.push(p);
    }
    this.parts = out;
    for (let i = 0; i < TRACK_SEGS; i++) this.tAge[i] += dt;
    this.upload();
  }

  private addTrack(x0: number, z0: number, x1: number, z1: number, width: number, strength: number) {
    const T = this.g.terrain;
    const i = this.tNext;
    this.tNext = (this.tNext + 1) % TRACK_SEGS;
    const dx = x1 - x0, dz = z1 - z0;
    const l = Math.hypot(dx, dz) || 1;
    const nx = (-dz / l) * width * 0.5, nz = (dx / l) * width * 0.5;
    const pts = [[x0 - nx, z0 - nz], [x0 + nx, z0 + nz], [x1 + nx, z1 + nz], [x1 - nx, z1 - nz]];
    for (let k = 0; k < 4; k++) {
      const [x, z] = pts[k];
      this.tPos.set([x, T.heightAt(x, z) + 0.03, z], (i * 4 + k) * 3);
    }
    this.tAge[i] = 0;
    this.tStrength[i] = strength;
  }

  private upload() {
    const cam = this.g.cam.entity;
    const right = cam.right, up = cam.up;
    const pos = this.pos, col = this.col;
    pos.fill(0);
    col.fill(0);
    let n = 0;
    for (const p of this.parts) {
      const t = p.life / p.max;
      const s = p.size * (1 + p.grow * t);
      const a = p.a * (1 - t) * Math.min(1, p.life * 8);
      const rx = right.x * s, ry = right.y * s, rz = right.z * s;
      const ux = up.x * s, uy = up.y * s, uz = up.z * s;
      const b = n * 12;
      pos[b] = p.x - rx - ux; pos[b + 1] = p.y - ry - uy; pos[b + 2] = p.z - rz - uz;
      pos[b + 3] = p.x + rx - ux; pos[b + 4] = p.y + ry - uy; pos[b + 5] = p.z + rz - uz;
      pos[b + 6] = p.x + rx + ux; pos[b + 7] = p.y + ry + uy; pos[b + 8] = p.z + rz + uz;
      pos[b + 9] = p.x - rx + ux; pos[b + 10] = p.y - ry + uy; pos[b + 11] = p.z - rz + uz;
      for (let k = 0; k < 4; k++) {
        const c = (n * 4 + k) * 4;
        col[c] = p.r * 255; col[c + 1] = p.g * 255; col[c + 2] = p.b * 255; col[c + 3] = a * 255;
      }
      n++;
    }
    this.mesh.setPositions(pos);
    this.mesh.setColors32(col);
    this.mesh.update(pc.PRIMITIVE_TRIANGLES, false);
    // tracks fade over ~40 s
    const tc = this.tCol;
    for (let i = 0; i < TRACK_SEGS; i++) {
      const age = this.tAge[i];
      const a = age > 60 ? 0 : this.tStrength[i] * Math.max(0, 1 - age / 60);
      for (let k = 0; k < 4; k++) {
        const c = (i * 4 + k) * 4;
        tc[c] = 40; tc[c + 1] = 32; tc[c + 2] = 24; tc[c + 3] = a * 255;
      }
    }
    this.trackMesh.setPositions(this.tPos);
    this.trackMesh.setColors32(tc);
    this.trackMesh.update(pc.PRIMITIVE_TRIANGLES, false);
  }
}

function upNormals(n: number) {
  const a = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) a[i * 3 + 1] = 1;
  return a;
}

function rotateVec(o: { x: number; y: number; z: number }, q: { x: number; y: number; z: number; w: number }, vx: number, vy: number, vz: number) {
  const { x: qx, y: qy, z: qz, w: qw } = q;
  const ix = qw * vx + qy * vz - qz * vy;
  const iy = qw * vy + qz * vx - qx * vz;
  const iz = qw * vz + qx * vy - qy * vx;
  const iw = -qx * vx - qy * vy - qz * vz;
  o.x = ix * qw + iw * -qx + iy * -qz - iz * -qy;
  o.y = iy * qw + iw * -qy + iz * -qx - ix * -qz;
  o.z = iz * qw + iw * -qz + ix * -qy - iy * -qx;
}
