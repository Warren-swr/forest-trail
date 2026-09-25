// Renders a shaded relief map of the generated terrain and prints road grades.
// Usage: npx tsx tools/map-preview.ts [out.png]
import { writeFileSync } from 'node:fs';
import { deflateSync } from 'node:zlib';
import { Terrain } from '../src/game/world/terrain';
import { LANDMARKS, WORLD_HALF } from '../src/game/world/layout';

const t0 = performance.now();
const terrain = new Terrain();
console.log(`terrain built in ${(performance.now() - t0).toFixed(0)} ms`);

const out = process.argv[2] ?? 'map-preview.png';
const N = terrain.n;
const px = new Uint8Array(N * N * 3);
const nrm = { x: 0, y: 0, z: 0 };
const sw = { grass: 0, dirt: 0, mud: 0, gravel: 0, rock: 0 };
let hmin = Infinity, hmax = -Infinity;
for (const h of terrain.heights) { hmin = Math.min(hmin, h); hmax = Math.max(hmax, h); }
for (let iz = 0; iz < N; iz++) for (let ix = 0; ix < N; ix++) {
  const x = ix - WORLD_HALF, z = iz - WORLD_HALF;
  const h = terrain.heights[iz * N + ix];
  terrain.normalAt(x, z, nrm);
  const shade = Math.max(0.25, nrm.x * -0.5 + nrm.y * 0.7 + nrm.z * -0.5);
  terrain.surfaceAt(x, z, sw);
  let r = 70 * sw.grass + 150 * sw.dirt + 90 * sw.mud + 170 * sw.gravel + 130 * sw.rock;
  let g = 110 * sw.grass + 115 * sw.dirt + 65 * sw.mud + 160 * sw.gravel + 128 * sw.rock;
  let b = 55 * sw.grass + 80 * sw.dirt + 40 * sw.mud + 140 * sw.gravel + 125 * sw.rock;
  const band = Math.floor(h / 2) % 2 === 0 ? 1 : 0.94;
  r *= shade * band; g *= shade * band; b *= shade * band;
  const d = terrain.waterDepthAt(x, z);
  if (d > 0.01) {
    const a = Math.min(0.85, 0.35 + d * 0.3);
    r = r * (1 - a) + 40 * a; g = g * (1 - a) + 90 * a; b = b * (1 - a) + 120 * a;
  }
  const k = (iz * N + ix) * 3;
  px[k] = Math.min(255, r); px[k + 1] = Math.min(255, g); px[k + 2] = Math.min(255, b);
}
for (const l of LANDMARKS) {
  for (let a = 0; a < 6.28; a += 0.02) {
    const ix = Math.round(l.x + WORLD_HALF + Math.cos(a) * l.radius), iz = Math.round(l.z + WORLD_HALF + Math.sin(a) * l.radius);
    if (ix < 0 || iz < 0 || ix >= N || iz >= N) continue;
    const k = (iz * N + ix) * 3;
    px[k] = 255; px[k + 1] = 220; px[k + 2] = 60;
  }
}
writeFileSync(out, encodePng(N, N, px));
console.log(`height range ${hmin.toFixed(1)} .. ${hmax.toFixed(1)}; wrote ${out}`);

// grades measured on the final terrain along the centreline (over 4 m)
for (const r of terrain.roads) {
  const S = r.path.samples;
  let maxG = 0, at = 0, sum = 0, cnt = 0, maxBank = 0, bankAt = 0;
  const step = 8; // 4 m
  for (let i = 0; i + step < S.length; i++) {
    const a = S[i], b = S[i + step];
    const g = Math.atan2(Math.abs(terrain.heightAt(b.x, b.z) - terrain.heightAt(a.x, a.z)), 4) * 57.3;
    sum += g; cnt++;
    if (g > maxG) { maxG = g; at = i; }
    // cross slope over the road width
    const hw = r.halfWidth * 0.8;
    const hl = terrain.heightAt(a.x - a.tz * hw, a.z + a.tx * hw), hr = terrain.heightAt(a.x + a.tz * hw, a.z - a.tx * hw);
    const bank = Math.atan2(Math.abs(hl - hr), hw * 2) * 57.3;
    if (bank > maxBank) { maxBank = bank; bankAt = i; }
  }
  const p = S[at], q = S[bankAt];
  console.log(`${r.def.id.padEnd(13)} len ${r.path.length.toFixed(0).padStart(5)} m  maxGrade ${maxG.toFixed(1).padStart(5)}° @(${p.x.toFixed(0)},${p.z.toFixed(0)})  avg ${(sum / Math.max(1, cnt)).toFixed(1)}°  maxBank ${maxBank.toFixed(1)}° @(${q.x.toFixed(0)},${q.z.toFixed(0)})  (limit ${r.def.maxGrade}°)`);
}
for (const l of LANDMARKS) {
  console.log(`${l.id.padEnd(7)} h=${terrain.heightAt(l.x, l.z).toFixed(2)} water=${terrain.waterDepthAt(l.x, l.z).toFixed(2)}`);
}
const ford = terrain.waterDepthAt(-18, -18);
console.log(`ford depth at C ${ford.toFixed(2)} m`);

function encodePng(w: number, h: number, rgb: Uint8Array): Buffer {
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (w * 3 + 1)] = 0;
    Buffer.from(rgb.buffer, rgb.byteOffset + y * w * 3, w * 3).copy(raw, y * (w * 3 + 1) + 1);
  }
  const chunk = (type: string, data: Buffer) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td) >>> 0);
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
function crc32(buf: Buffer): number {
  let c = ~0;
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i];
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
  }
  return ~c;
}
