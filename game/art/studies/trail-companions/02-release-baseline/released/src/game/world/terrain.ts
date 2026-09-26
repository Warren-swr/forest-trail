// Terrain synthesis: authored road profiles + relaxed macro field + noise,
// carved by the creek, the lake and the roads. Produces height, surface and
// water grids used by both physics and rendering.

import { ANCHORS, BRIDGE, CLEARINGS, FEATURES, LAKE, LAKE_LEVEL, PROPS, ROADS, STREAM, STREAM_WIDTH, SURFACE_ZONES, WORLD_HALF, WORLD_SIZE, type RoadDef, type SurfaceKind, type TerrainFeature } from './layout';
import { mulberry32 } from './noise';
import { clamp, fbm, lerp, smoothstep, valueNoise } from './noise';
import { Path2 } from './spline';

export const SURFACE_INDEX: Record<SurfaceKind, number> = { grass: -1, dirt: 0, mud: 1, gravel: 2, rock: 3 };

export interface Road {
  def: RoadDef;
  path: Path2;
  /** road surface elevation per path sample */
  profile: Float32Array;
  halfWidth: number;
}

export interface SurfaceWeights {
  grass: number;
  dirt: number;
  mud: number;
  gravel: number;
  rock: number;
}

const NO_WATER = -1000;

/** a terrain feature resolved to arc lengths on its road */
export interface FeatureSpan {
  f: TerrainFeature;
  road: Road;
  s0: number;
  s1: number;
}

export class Terrain {
  readonly size = WORLD_SIZE;
  readonly half = WORLD_HALF;
  readonly res = 1;
  readonly n = WORLD_SIZE + 1;
  readonly heights: Float32Array;
  readonly water: Float32Array;
  /** distance to the nearest road edge in metres (height grid); large when far */
  readonly roadDist: Float32Array;
  /** index of the nearest road (height grid), -1 when none */
  readonly roadId: Int8Array;
  /** material grid (0.5 m): RGBA = dirt, mud, gravel, rock */
  readonly matRes = 0.5;
  readonly mn = WORLD_SIZE * 2 + 1;
  readonly mat: Uint8Array;
  /** aux grid (0.5 m): R = wheel ruts, G = grassy centre strip, B = wetness, A = canopy (filled by scatter) */
  readonly aux: Uint8Array;
  readonly roads: Road[] = [];
  readonly features: FeatureSpan[] = [];
  /** crater / pothole / mogul pit footprints for surface painting (world x, z, radius, depth) */
  readonly pits: { x: number; z: number; r: number; d: number }[] = [];
  /** bridge frame: centre, road tangent, deck height */
  bridge: { x: number; z: number; tx: number; tz: number; y: number } | null = null;
  readonly stream: Path2;
  streamBed!: Float32Array;
  streamDepth!: Float32Array;

  constructor() {
    const n = this.n;
    this.heights = new Float32Array(n * n);
    this.water = new Float32Array(n * n).fill(NO_WATER);
    this.roadDist = new Float32Array(n * n).fill(1e4);
    this.roadId = new Int8Array(n * n).fill(-1);
    this.mat = new Uint8Array(this.mn * this.mn * 4);
    this.aux = new Uint8Array(this.mn * this.mn * 4);
    this.stream = new Path2(STREAM.map((p) => [p[0], p[1]]), 1);
    this.build();
  }

  // ---------------------------------------------------------------- queries

  heightAt(x: number, z: number): number {
    const n = this.n;
    const fx = clamp(x + this.half, 0, this.size - 1e-4);
    const fz = clamp(z + this.half, 0, this.size - 1e-4);
    const ix = Math.floor(fx);
    const iz = Math.floor(fz);
    const tx = fx - ix;
    const tz = fz - iz;
    const h = this.heights;
    const a = h[iz * n + ix];
    const b = h[iz * n + ix + 1];
    const c = h[(iz + 1) * n + ix];
    const d = h[(iz + 1) * n + ix + 1];
    return (a * (1 - tx) + b * tx) * (1 - tz) + (c * (1 - tx) + d * tx) * tz;
  }

  normalAt(x: number, z: number, out: { x: number; y: number; z: number }, e = 0.75) {
    const hl = this.heightAt(x - e, z);
    const hr = this.heightAt(x + e, z);
    const hd = this.heightAt(x, z - e);
    const hu = this.heightAt(x, z + e);
    const nx = hl - hr;
    const nz = hd - hu;
    const ny = 2 * e;
    const l = Math.hypot(nx, ny, nz);
    out.x = nx / l;
    out.y = ny / l;
    out.z = nz / l;
    return out;
  }

  /** Water surface level at a point, or NaN when dry. */
  waterLevelAt(x: number, z: number): number {
    const n = this.n;
    const ix = Math.round(clamp(x + this.half, 0, this.size));
    const iz = Math.round(clamp(z + this.half, 0, this.size));
    const w = this.water[iz * n + ix];
    return w === NO_WATER ? NaN : w;
  }

  waterDepthAt(x: number, z: number): number {
    const lvl = this.waterLevelAt(x, z);
    if (Number.isNaN(lvl)) return 0;
    return Math.max(0, lvl - this.heightAt(x, z));
  }

  surfaceAt(x: number, z: number, out: SurfaceWeights): SurfaceWeights {
    const mn = this.mn;
    const fx = clamp((x + this.half) / this.matRes, 0, mn - 1.001);
    const fz = clamp((z + this.half) / this.matRes, 0, mn - 1.001);
    const ix = Math.floor(fx);
    const iz = Math.floor(fz);
    const tx = fx - ix;
    const tz = fz - iz;
    const m = this.mat;
    const w00 = (1 - tx) * (1 - tz), w10 = tx * (1 - tz), w01 = (1 - tx) * tz, w11 = tx * tz;
    const i00 = (iz * mn + ix) * 4, i10 = i00 + 4, i01 = i00 + mn * 4, i11 = i01 + 4;
    const ch = (c: number) => (m[i00 + c] * w00 + m[i10 + c] * w10 + m[i01 + c] * w01 + m[i11 + c] * w11) / 255;
    out.dirt = ch(0);
    out.mud = ch(1);
    out.gravel = ch(2);
    out.rock = ch(3);
    out.grass = Math.max(0, 1 - out.dirt - out.mud - out.gravel - out.rock);
    return out;
  }

  roadDistAt(x: number, z: number): number {
    const ix = Math.round(clamp(x + this.half, 0, this.size));
    const iz = Math.round(clamp(z + this.half, 0, this.size));
    return this.roadDist[iz * this.n + ix];
  }

  /** Heights in Rapier heightfield layout (column-major, rows along Z). */
  rapierHeights(): Float32Array {
    const n = this.n;
    const out = new Float32Array(n * n);
    for (let iz = 0; iz < n; iz++) for (let ix = 0; ix < n; ix++) out[ix * n + iz] = this.heights[iz * n + ix];
    return out;
  }

  // ------------------------------------------------------------ generation

  protected build() {
    this.buildRoads();
    this.buildMacro();
    this.carveStream();
    this.carveLake();
    this.flattenProps();
    this.carveRoads();
    this.applyFeatures();
    this.carveGully();
    this.applyZones();
    this.buildWater();
    this.buildMaterials();
  }

  private buildRoads() {
    for (const def of ROADS) {
      const pts = def.points.map((p) => [p[0], p[1]] as [number, number]);
      const path = new Path2(pts, 0.5, def.closed);
      // control-point arc lengths
      const cs: number[] = [];
      let hint = 0;
      for (let i = 0; i < def.points.length; i++) {
        const p = def.points[i];
        const r = path.nearest(p[0], p[1], i === 0 ? undefined : hint, 200);
        cs.push(i === 0 ? 0 : r.s);
        hint = r.s;
      }
      const hs = def.points.map((p) => p[2]);
      if (def.closed) {
        cs.push(path.length);
        hs.push(hs[0]);
      }
      const profile = new Float32Array(path.samples.length);
      for (let i = 0; i < path.samples.length; i++) profile[i] = pchip(cs, hs, path.samples[i].s);
      // gentle longitudinal undulation so the suspension always has something to do
      const seed = def.id.length * 13;
      for (let i = 0; i < profile.length; i++) {
        const s = path.samples[i].s;
        const smp = path.samples[i];
        const nearStream = this.stream.nearest(smp.x, smp.z).d;
        const fade = (def.closed ? 1 : smoothstep(0, 6, s) * smoothstep(0, 6, path.length - s)) * smoothstep(5, 16, nearStream);
        profile[i] += (valueNoise(s / 9, 0.5, seed) * 0.22 + valueNoise(s / 3.1, 3.5, seed) * def.roughness) * fade;
      }
      this.roads.push({ def, path, profile, halfWidth: def.width / 2 });
    }
  }

  /** Macro field: relax a coarse grid pinned by roads, lake, creek and borders. */
  private buildMacro() {
    const cell = 8;
    const cn = WORLD_SIZE / cell + 1;
    const f = new Float32Array(cn * cn).fill(NaN);
    const pinW = new Float32Array(cn * cn);
    const pin = new Float32Array(cn * cn);
    const addPin = (x: number, z: number, h: number, w = 1) => {
      const ix = Math.round((x + WORLD_HALF) / cell);
      const iz = Math.round((z + WORLD_HALF) / cell);
      if (ix < 0 || iz < 0 || ix >= cn || iz >= cn) return;
      const k = iz * cn + ix;
      pin[k] = (pin[k] * pinW[k] + h * w) / (pinW[k] + w);
      pinW[k] += w;
    };
    for (const r of this.roads) {
      for (let i = 0; i < r.path.samples.length; i += 8) {
        const s = r.path.samples[i];
        addPin(s.x, s.z, r.profile[i] + 0.4);
      }
    }
    for (let i = 0; i < this.stream.samples.length; i += 6) {
      const s = this.stream.samples[i];
      addPin(s.x, s.z, this.streamBedAt(s.s) + 1.6, 0.6);
    }
    for (let a = 0; a < Math.PI * 2; a += 0.05) {
      addPin(LAKE.cx + Math.cos(a) * LAKE.rx * 0.6, LAKE.cz + Math.sin(a) * LAKE.rz * 0.6, LAKE.bed);
      addPin(LAKE.cx + Math.cos(a) * LAKE.rx * 1.12, LAKE.cz + Math.sin(a) * LAKE.rz * 1.12, 1.6, 0.5);
    }
    // borders: hills all around, high ridge to the north
    for (let t = -WORLD_HALF; t <= WORLD_HALF; t += cell) {
      const north = 78 + fbm(t / 90, 1.3, 3, 5) * 18;
      const south = 26 + fbm(t / 80, 7.1, 3, 6) * 12;
      const west = lerp(70, 30, (t + WORLD_HALF) / WORLD_SIZE) + fbm(t / 70, 3.3, 3, 7) * 10;
      const east = lerp(76, 34, (t + WORLD_HALF) / WORLD_SIZE) + fbm(t / 70, 9.3, 3, 8) * 10;
      addPin(t, -WORLD_HALF, north, 2);
      addPin(t, WORLD_HALF, south, 2);
      addPin(-WORLD_HALF, t, west, 2);
      addPin(WORLD_HALF, t, east, 2);
    }
    // a few authored hills to break up the interior
    const hills: [number, number, number][] = [
      [-120, -180, 34], [-40, -240, 30], [60, -200, 40], [90, -130, 28], [20, -90, 12],
      [-110, 20, 14], [-260, -160, 42], [-270, 60, 26], [280, -250, 70], [150, 30, 12],
      [80, 90, 9], [270, 60, 30], [280, 180, 26], [-260, 250, 24], [100, 260, 18], [-40, 270, 16],
      [210, -270, 60], [110, -270, 58], [-160, -250, 52], [-230, -60, 26], [-140, 60, 9],
    ];
    for (const [x, z, h] of hills) addPin(x, z, h, 1.5);

    for (let k = 0; k < f.length; k++) f[k] = pinW[k] > 0 ? pin[k] : 12;
    const pinned = (k: number) => pinW[k] > 0;
    // initial guess by inverse distance on unpinned cells
    for (let it = 0; it < 2500; it++) {
      for (let iz = 0; iz < cn; iz++) {
        for (let ix = 0; ix < cn; ix++) {
          const k = iz * cn + ix;
          if (pinned(k)) continue;
          let s = 0, c = 0;
          if (ix > 0) { s += f[k - 1]; c++; }
          if (ix < cn - 1) { s += f[k + 1]; c++; }
          if (iz > 0) { s += f[k - cn]; c++; }
          if (iz < cn - 1) { s += f[k + cn]; c++; }
          f[k] = f[k] + (s / c - f[k]) * 1.7;
        }
      }
    }
    // soften pins a bit to avoid cones
    const g = new Float32Array(f);
    for (let pass = 0; pass < 2; pass++) {
      for (let iz = 1; iz < cn - 1; iz++) for (let ix = 1; ix < cn - 1; ix++) {
        const k = iz * cn + ix;
        g[k] = (f[k] * 4 + f[k - 1] + f[k + 1] + f[k - cn] + f[k + cn]) / 8;
      }
      f.set(g);
    }

    // road distance on the height grid (for noise amplitude and tree placement)
    this.rasterRoadDistance();

    const n = this.n;
    for (let iz = 0; iz < n; iz++) {
      for (let ix = 0; ix < n; ix++) {
        const x = ix - WORLD_HALF;
        const z = iz - WORLD_HALF;
        const base = bicubic(f, cn, (x + WORLD_HALF) / cell, (z + WORLD_HALF) / cell);
        const rd = this.roadDist[iz * n + ix];
        const amp = clamp((rd - 6) * 0.12, 0, 5);
        const hills = fbm(x / 70, z / 70, 4, 21) * amp * 1.4;
        const lumps = fbm(x / 13, z / 13, 3, 33) * (0.35 + amp * 0.18);
        this.heights[iz * n + ix] = base + hills + lumps;
      }
    }
  }

  private rasterRoadDistance() {
    const n = this.n;
    const R = 40;
    for (let ri = 0; ri < this.roads.length; ri++) {
      const r = this.roads[ri];
      for (let i = 0; i < r.path.samples.length; i += 2) {
        const s = r.path.samples[i];
        const x0 = Math.max(0, Math.floor(s.x + WORLD_HALF - R));
        const x1 = Math.min(n - 1, Math.ceil(s.x + WORLD_HALF + R));
        const z0 = Math.max(0, Math.floor(s.z + WORLD_HALF - R));
        const z1 = Math.min(n - 1, Math.ceil(s.z + WORLD_HALF + R));
        for (let iz = z0; iz <= z1; iz++) {
          const dz = iz - WORLD_HALF - s.z;
          for (let ix = x0; ix <= x1; ix++) {
            const dx = ix - WORLD_HALF - s.x;
            const d = Math.sqrt(dx * dx + dz * dz) - r.halfWidth;
            const k = iz * n + ix;
            if (d < this.roadDist[k]) {
              this.roadDist[k] = d;
              this.roadId[k] = ri;
            }
          }
        }
      }
    }
  }

  private streamIndex(s: number): number {
    // STREAM control points mapped to arc length proportionally by nearest search
    return s;
  }

  private streamCs?: number[];
  streamBedAt(s: number): number {
    if (!this.streamCs) {
      this.streamCs = STREAM.map((p, i) => (i === 0 ? 0 : this.stream.nearest(p[0], p[1]).s));
      this.streamCs[this.streamCs.length - 1] = this.stream.length;
    }
    return pchip(this.streamCs, STREAM.map((p) => p[2]), this.streamIndex(s));
  }

  streamDepthAt(s: number): number {
    if (!this.streamCs) this.streamBedAt(0);
    return pchip(this.streamCs!, STREAM.map((p) => p[3]), s);
  }

  private carveStream() {
    const n = this.n;
    const hw = STREAM_WIDTH / 2;
    const S = this.stream.samples;
    this.streamBed = new Float32Array(S.length);
    this.streamDepth = new Float32Array(S.length);
    for (let i = 0; i < S.length; i++) {
      this.streamBed[i] = this.streamBedAt(S[i].s);
      this.streamDepth[i] = this.streamDepthAt(S[i].s);
    }
    const R = 26;
    const best = new Float32Array(n * n).fill(1e4);
    const bestI = new Int32Array(n * n).fill(-1);
    for (let i = 0; i < S.length; i++) {
      const s = S[i];
      const x0 = Math.max(0, Math.floor(s.x + WORLD_HALF - R)), x1 = Math.min(n - 1, Math.ceil(s.x + WORLD_HALF + R));
      const z0 = Math.max(0, Math.floor(s.z + WORLD_HALF - R)), z1 = Math.min(n - 1, Math.ceil(s.z + WORLD_HALF + R));
      for (let iz = z0; iz <= z1; iz++) for (let ix = x0; ix <= x1; ix++) {
        const d = Math.hypot(ix - WORLD_HALF - s.x, iz - WORLD_HALF - s.z);
        const k = iz * n + ix;
        if (d < best[k]) { best[k] = d; bestI[k] = i; }
      }
    }
    for (let k = 0; k < n * n; k++) {
      const i = bestI[k];
      if (i < 0) continue;
      const x = (k % n) - WORLD_HALF, z = Math.floor(k / n) - WORLD_HALF;
      const wob = valueNoise(x / 6, z / 6, 77) * 0.8;
      const d = Math.max(0, best[k] + wob);
      const bed = this.streamBed[i];
      const depth = this.streamDepth[i];
      const bank = depth + 0.55;
      let target: number;
      if (d < hw) {
        const t = d / hw;
        target = bed + Math.pow(t, 2.2) * bank + valueNoise(x / 1.7, z / 1.7, 91) * 0.06;
      } else {
        target = bed + bank + (d - hw) * 0.42;
      }
      const h = this.heights[k];
      this.heights[k] = Math.min(h, target);
    }
  }

  private carveLake() {
    const n = this.n;
    for (let iz = 0; iz < n; iz++) for (let ix = 0; ix < n; ix++) {
      const x = ix - WORLD_HALF, z = iz - WORLD_HALF;
      const ang = Math.atan2(z - LAKE.cz, x - LAKE.cx);
      const wob = 1 + valueNoise(Math.cos(ang) * 2 + 3, Math.sin(ang) * 2 + 3, 55) * 0.12;
      const e = Math.hypot((x - LAKE.cx) / (LAKE.rx * wob), (z - LAKE.cz) / (LAKE.rz * wob));
      if (e > 1.6) continue;
      const shore = lerp(LAKE.bed, 1.3, smoothstep(0.45, 1.04, e));
      const target = e < 1.04 ? shore : 1.3 + (e - 1.04) * 26;
      const k = iz * n + ix;
      this.heights[k] = Math.min(this.heights[k], target);
    }
  }

  private carveRoads() {
    const n = this.n;
    for (let ri = 0; ri < this.roads.length; ri++) {
      const r = this.roads[ri];
      const S = r.path.samples;
      const R = r.halfWidth + 16;
      const best = new Map<number, [number, number, number]>(); // k -> [dist, sampleIdx, lateral]
      for (let i = 0; i < S.length; i++) {
        const s = S[i];
        const x0 = Math.max(0, Math.floor(s.x + WORLD_HALF - R)), x1 = Math.min(n - 1, Math.ceil(s.x + WORLD_HALF + R));
        const z0 = Math.max(0, Math.floor(s.z + WORLD_HALF - R)), z1 = Math.min(n - 1, Math.ceil(s.z + WORLD_HALF + R));
        for (let iz = z0; iz <= z1; iz++) for (let ix = x0; ix <= x1; ix++) {
          const dx = ix - WORLD_HALF - s.x, dz = iz - WORLD_HALF - s.z;
          const d = Math.sqrt(dx * dx + dz * dz);
          if (d > R) continue;
          const k = iz * n + ix;
          const cur = best.get(k);
          if (!cur || d < cur[0]) best.set(k, [d, i, dx * -s.tz + dz * s.tx]);
        }
      }
      for (const [k, [d, i, lat]] of best) {
        const x = (k % n) - WORLD_HALF, z = Math.floor(k / n) - WORLD_HALF;
        const crown = -Math.pow(clamp(Math.abs(lat) / r.halfWidth, 0, 1), 2) * 0.06;
        const rut = valueNoise(x / 1.3, z / 1.3, 12 + ri) * r.def.roughness * 0.6;
        const roadH = r.profile[i] + crown + rut;
        const h = this.heights[k];
        const dh = Math.abs(roadH - h);
        const shoulder = 2.2 + dh * 1.35;
        const edge = r.halfWidth + 0.6;
        const w = d <= edge ? 1 : 1 - smoothstep(edge, edge + shoulder, d);
        if (w <= 0) continue;
        this.heights[k] = lerp(h, roadH, w);
      }
    }
  }

  /** Target height for a pad: blend of the nearest road profile and the local ground. */
  private padHeight(x: number, z: number): number {
    let best = Infinity, h = this.heightAt(x, z);
    for (const r of this.roads) {
      const q = r.path.nearest(x, z, undefined, 1e4);
      if (q.d < best) {
        best = q.d;
        const i = Math.min(r.profile.length - 1, Math.round(q.s / r.path.step));
        h = lerp(r.profile[i], this.heightAt(x, z), smoothstep(10, 30, q.d));
      }
    }
    return h;
  }

  private flattenProps() {
    const n = this.n;
    for (const p of PROPS) {
      if (!p.flatten) continue;
      const target = this.padHeight(p.x, p.z) + 0.15;
      forCellsNearPolyline([[p.x, p.z]], p.flatten + 12, n, (k, d) => {
        const w = 1 - smoothstep(p.flatten!, p.flatten! + 12, d);
        this.heights[k] = lerp(this.heights[k], target, w);
      });
    }
  }

  private applyZones() {
    const n = this.n;
    for (const zone of SURFACE_ZONES) {
      if (!zone.sink) continue;
      forCellsNearPolyline(zone.line, zone.radius + 2, n, (k, d) => {
        const w = 1 - smoothstep(zone.radius * 0.5, zone.radius + 1, d);
        this.heights[k] -= zone.sink! * w;
      });
    }
    void ANCHORS;
    void CLEARINGS;
  }

  // ------------------------------------------------------------- features

  private applyFeatures() {
    const n = this.n;
    for (const f of FEATURES) {
      const road = this.roads.find((r) => r.def.id === f.road);
      if (!road) continue;
      const a = road.path.nearest(f.from[0], f.from[1], undefined, 1e4).s;
      const b = road.path.nearest(f.to[0], f.to[1], undefined, 1e4).s;
      const s0 = Math.min(a, b), s1 = Math.max(a, b);
      this.features.push({ f, road, s0, s1 });
      const hw = road.halfWidth;
      const rnd = mulberry32(f.seed ?? 1);
      // pits placed along the span (craters, potholes)
      const pits: { s: number; l: number; r: number; d: number }[] = [];
      if (f.kind === 'craters' || f.kind === 'potholes') {
        const cnt = f.count ?? 6;
        for (let i = 0; i < cnt; i++) {
          const t = (i + 0.5) / cnt + (rnd() - 0.5) * 0.6 / cnt;
          const r = f.r ? f.r[0] + rnd() * (f.r[1] - f.r[0]) : 2;
          pits.push({ s: s0 + 2 + t * (s1 - s0 - 4), l: (rnd() - 0.5) * 2 * Math.max(0, hw - r * 0.35), r, d: f.amp * (0.7 + rnd() * 0.45) });
        }
        for (const p of pits) {
          const q = road.path.at(p.s);
          this.pits.push({ x: q.x + -q.tz * p.l, z: q.z + q.tx * p.l, r: p.r, d: p.d });
        }
      }
      if (f.kind === 'crossAxle') {
        const wave = f.wave ?? 3.4;
        for (let j = 0; s0 + j * wave < s1; j++) {
          const q = road.path.at(s0 + j * wave);
          const l = -(j % 2 === 0 ? 1 : -1) * 0.9;
          this.pits.push({ x: q.x + -q.tz * l, z: q.z + q.tx * l, r: 1.5, d: f.amp * 0.75 });
        }
      }
      const S = road.path.samples;
      const i0 = Math.max(0, Math.floor(s0 / road.path.step) - 8), i1 = Math.min(S.length - 1, Math.ceil(s1 / road.path.step) + 8);
      const R = hw + 4;
      const best = new Map<number, [number, number]>(); // k -> [s, lat]
      const bestD = new Map<number, number>();
      for (let i = i0; i <= i1; i++) {
        const sm = S[i];
        const x0 = Math.max(0, Math.floor(sm.x + WORLD_HALF - R)), x1 = Math.min(n - 1, Math.ceil(sm.x + WORLD_HALF + R));
        const z0 = Math.max(0, Math.floor(sm.z + WORLD_HALF - R)), z1 = Math.min(n - 1, Math.ceil(sm.z + WORLD_HALF + R));
        for (let iz = z0; iz <= z1; iz++) for (let ix = x0; ix <= x1; ix++) {
          const dx = ix - WORLD_HALF - sm.x, dz = iz - WORLD_HALF - sm.z;
          const d = dx * dx + dz * dz;
          const k = iz * n + ix;
          const cur = bestD.get(k);
          if (cur === undefined || d < cur) {
            bestD.set(k, d);
            // lateral: positive to the right of the driving direction
            best.set(k, [sm.s + (dx * sm.tx + dz * sm.tz), dx * -sm.tz + dz * sm.tx]);
          }
        }
      }
      const g = (d2: number, sig: number) => Math.exp(-d2 / (2 * sig * sig));
      for (const [k, [sa, lat]] of best) {
        if (sa < s0 - 1 || sa > s1 + 1) continue;
        const ends = smoothstep(s0 - 1, s0 + 3, sa) * (1 - smoothstep(s1 - 3, s1 + 1, sa));
        const side = 1 - smoothstep(hw + 0.3, hw + 3.2, Math.abs(lat));
        const w = ends * side;
        if (w <= 0) continue;
        let dh = 0;
        switch (f.kind) {
          case 'craters':
          case 'potholes':
            for (const p of pits) {
              const d = Math.hypot(sa - p.s, lat - p.l) / p.r;
              if (d < 1) dh -= p.d * 0.5 * (1 + Math.cos(d * Math.PI));
              if (f.kind === 'craters') dh += p.d * 0.28 * Math.exp(-Math.pow((d - 1.12) / 0.22, 2));
            }
            break;
          case 'crossAxle': {
            const wave = f.wave ?? 3.4;
            const kk = Math.round((sa - s0) / wave);
            for (let j = kk - 1; j <= kk + 1; j++) {
              const sc = s0 + j * wave;
              const sideJ = j % 2 === 0 ? 1 : -1;
              const du = sa - sc;
              dh += f.amp * g(du * du + (lat - sideJ * 0.9) ** 2, 0.85);
              dh -= f.amp * 0.75 * g(du * du + (lat + sideJ * 0.9) ** 2, 0.85);
            }
            break;
          }
          case 'washboard':
          case 'whoops': {
            const wave = f.wave ?? 1.5;
            dh = f.amp * Math.sin(((sa - s0) / wave) * Math.PI * 2 + lat * 0.08);
            break;
          }
          case 'bank': {
            const t = Math.tan((f.amp * Math.PI) / 180);
            const ll = clamp(lat, -hw - 1, hw + 1);
            dh = ll * t;
            break;
          }
        }
        // banks keep the shoulders attached; bumps fade into them
        this.heights[k] += dh * (f.kind === 'bank' ? ends * (1 - smoothstep(hw + 2, hw + 7, Math.abs(lat))) : w);
      }
    }
  }

  /** dry gully under the plank bridge, perpendicular to the canyon road */
  private carveGully() {
    const road = this.roads.find((r) => r.def.id === BRIDGE.road);
    if (!road) return;
    const q = road.path.nearest(BRIDGE.x, BRIDGE.z, undefined, 1e4);
    const p = road.path.at(q.s);
    const i = Math.min(road.profile.length - 1, Math.round(q.s / road.path.step));
    this.bridge = { x: p.x, z: p.z, tx: p.tx, tz: p.tz, y: road.profile[i] };
    const n = this.n;
    const R = 34;
    for (let iz = Math.floor(p.z + WORLD_HALF - R); iz <= Math.ceil(p.z + WORLD_HALF + R); iz++) {
      for (let ix = Math.floor(p.x + WORLD_HALF - R); ix <= Math.ceil(p.x + WORLD_HALF + R); ix++) {
        if (ix < 0 || iz < 0 || ix >= n || iz >= n) continue;
        const dx = ix - WORLD_HALF - p.x, dz = iz - WORLD_HALF - p.z;
        const u = dx * p.tx + dz * p.tz; // along the road
        const v = dx * -p.tz + dz * p.tx; // across
        const wob = valueNoise((ix - WORLD_HALF) / 5, (iz - WORLD_HALF) / 5, 919) * 1.6;
        const inside = 1 - smoothstep(BRIDGE.gullyHalf - 3, BRIDGE.gullyHalf + 1.5, Math.abs(u) + wob);
        const len = 1 - smoothstep(20, 30, Math.abs(v));
        if (inside * len <= 0) continue;
        const k = iz * n + ix;
        const floor = this.bridge.y - BRIDGE.gullyDepth + valueNoise(v / 4, u / 4, 920) * 0.6 - v * 0.04;
        this.heights[k] = Math.min(this.heights[k], lerp(this.heights[k], floor, inside * len));
      }
    }
  }

  /** height of what a car drives on: the plank bridge deck over the gully, else the ground */
  driveHeightAt(x: number, z: number): number {
    const b = this.bridge;
    if (b) {
      const dx = x - b.x, dz = z - b.z;
      const u = dx * b.tx + dz * b.tz, v = dx * -b.tz + dz * b.tx;
      if (Math.abs(u) <= BRIDGE.half && Math.abs(v) <= BRIDGE.width / 2 + 0.3) {
        return Math.max(this.heightAt(x, z), b.y - BRIDGE.sag * (1 - (u / BRIDGE.half) ** 2));
      }
    }
    return this.heightAt(x, z);
  }

  /** true inside the gully footprint (no road surface is painted there) */
  inGully(x: number, z: number): boolean {
    const b = this.bridge;
    if (!b) return false;
    const dx = x - b.x, dz = z - b.z;
    return Math.abs(dx * b.tx + dz * b.tz) < BRIDGE.gullyHalf + 0.5 && Math.abs(dx * -b.tz + dz * b.tx) < 24;
  }

  /** autopilot speed limit on a road at arc length s (km/h), Infinity when free */
  featureLimit(roadId: string, s: number): number {
    let lim = Infinity;
    for (const fs of this.features) {
      if (fs.road.def.id !== roadId) continue;
      if (s > fs.s0 - 12 && s < fs.s1 + 2) lim = Math.min(lim, fs.f.kmh);
    }
    return lim;
  }

  private buildWater() {
    const n = this.n;
    // lake
    for (let iz = 0; iz < n; iz++) for (let ix = 0; ix < n; ix++) {
      const x = ix - WORLD_HALF, z = iz - WORLD_HALF;
      const e = Math.hypot((x - LAKE.cx) / LAKE.rx, (z - LAKE.cz) / LAKE.rz);
      const k = iz * n + ix;
      if (e < 1.45 && this.heights[k] < LAKE_LEVEL + 0.05) this.water[k] = LAKE_LEVEL;
    }
    // creek: level follows the bed along the stream path
    const S = this.stream.samples;
    const hw = STREAM_WIDTH / 2 + 2;
    const bestD = new Float32Array(n * n).fill(1e4);
    for (let i = 0; i < S.length; i++) {
      const s = S[i];
      const level = this.streamBed[i] + this.streamDepth[i];
      const x0 = Math.max(0, Math.floor(s.x + WORLD_HALF - hw)), x1 = Math.min(n - 1, Math.ceil(s.x + WORLD_HALF + hw));
      const z0 = Math.max(0, Math.floor(s.z + WORLD_HALF - hw)), z1 = Math.min(n - 1, Math.ceil(s.z + WORLD_HALF + hw));
      for (let iz = z0; iz <= z1; iz++) for (let ix = x0; ix <= x1; ix++) {
        const d = Math.hypot(ix - WORLD_HALF - s.x, iz - WORLD_HALF - s.z);
        if (d > hw) continue;
        const k = iz * n + ix;
        if (d >= bestD[k]) continue;
        bestD[k] = d;
        if (this.heights[k] < level + 0.05) this.water[k] = Math.max(LAKE_LEVEL, level);
        else if (this.water[k] !== LAKE_LEVEL) this.water[k] = NO_WATER;
      }
    }
  }

  private buildMaterials() {
    const mn = this.mn;
    const res = this.matRes;
    const W = new Float32Array(mn * mn * 4);
    const set = (k: number, idx: number, w: number) => {
      const b = k * 4;
      // blend towards the new surface with weight w
      for (let c = 0; c < 4; c++) W[b + c] *= 1 - w;
      if (idx >= 0) W[b + idx] += w;
    };
    // roads
    for (const r of this.roads) {
      const idx = SURFACE_INDEX[r.def.surface];
      const S = r.path.samples;
      const R = r.halfWidth + 1.6;
      const cover = new Float32Array(0);
      void cover;
      const best = new Map<number, number>();
      for (let i = 0; i < S.length; i++) {
        const s = S[i];
        const x0 = Math.max(0, Math.floor((s.x + WORLD_HALF - R) / res)), x1 = Math.min(mn - 1, Math.ceil((s.x + WORLD_HALF + R) / res));
        const z0 = Math.max(0, Math.floor((s.z + WORLD_HALF - R) / res)), z1 = Math.min(mn - 1, Math.ceil((s.z + WORLD_HALF + R) / res));
        for (let iz = z0; iz <= z1; iz++) for (let ix = x0; ix <= x1; ix++) {
          const d = Math.hypot(ix * res - WORLD_HALF - s.x, iz * res - WORLD_HALF - s.z);
          if (d > R) continue;
          const k = iz * mn + ix;
          const cur = best.get(k);
          if (cur === undefined || d < cur) best.set(k, d);
        }
      }
      const twoTrack = r.def.width < 5.5;
      for (const [k, d] of best) {
        const x = (k % mn) * res - WORLD_HALF, z = Math.floor(k / mn) * res - WORLD_HALF;
        if (r.def.id === BRIDGE.road && this.inGully(x, z)) { set(k, SURFACE_INDEX.rock, 0.8); continue; }
        const edgeNoise = valueNoise(x / 2.3, z / 2.3, 5) * 0.45 + valueNoise(x / 0.7, z / 0.7, 6) * 0.15;
        const w = 1 - smoothstep(r.halfWidth - 0.7, r.halfWidth + 0.5, d + edgeNoise);
        if (w > 0) set(k, idx, w);
        if (twoTrack) {
          const wob = valueNoise(x / 7, z / 7, 17) * 0.12;
          const rut = (1 - smoothstep(0.16, 0.42, Math.abs(d + wob - 0.82))) * (0.7 + 0.3 * valueNoise(x / 3, z / 3, 18));
          const strip = (1 - smoothstep(0.2, 0.46, d + wob * 0.5)) * smoothstep(-0.3, 0.4, valueNoise(x / 9, z / 9, 19));
          const b4 = k * 4;
          this.aux[b4] = Math.max(this.aux[b4], Math.round(clamp(rut, 0, 1) * 255));
          if (r.def.surface === 'dirt') this.aux[b4 + 1] = Math.max(this.aux[b4 + 1], Math.round(clamp(strip, 0, 1) * 255));
        }
      }
    }
    // explicit zones
    for (const zone of SURFACE_ZONES) {
      const idx = SURFACE_INDEX[zone.kind];
      forCellsNearPolyline(zone.line, zone.radius + 1.5, mn, (k, d) => {
        const x = (k % mn) * res - WORLD_HALF, z = Math.floor(k / mn) * res - WORLD_HALF;
        const noise = valueNoise(x / 1.9, z / 1.9, 44) * 0.9;
        const w = 1 - smoothstep(zone.radius - 1.2, zone.radius + 0.6, d + noise);
        if (w > 0) set(k, idx, w);
      }, res);
    }
    // creek bed and banks, lake shore, steep slopes
    const tmpN = { x: 0, y: 0, z: 0 };
    for (let iz = 0; iz < mn; iz++) for (let ix = 0; ix < mn; ix++) {
      const x = ix * res - WORLD_HALF, z = iz * res - WORLD_HALF;
      const k = iz * mn + ix;
      const depth = this.waterDepthAt(x, z);
      const lvl = this.waterLevelAt(x, z);
      const h = this.heightAt(x, z);
      if (!Number.isNaN(lvl) || (h < 1.9 && Math.hypot((x - LAKE.cx) / LAKE.rx, (z - LAKE.cz) / LAKE.rz) < 1.22)) {
        const shoreW = Number.isNaN(lvl) ? smoothstep(1.9, 1.2, h) : 1;
        const sandy = valueNoise(x / 4, z / 4, 3) > -0.2 ? 1 : 0.6;
        set(k, SURFACE_INDEX.gravel, shoreW * sandy * (depth > 1.5 ? 0.5 : 1));
      }
      let wet = 0;
      if (!Number.isNaN(lvl)) wet = 1;
      else if (Math.hypot((x - LAKE.cx) / LAKE.rx, (z - LAKE.cz) / LAKE.rz) < 1.3) wet = smoothstep(1.6, 0.4, h - LAKE_LEVEL);
      else {
        for (const [ox, oz] of [[1.8, 0], [-1.8, 0], [0, 1.8], [0, -1.8]]) {
          const l2 = this.waterLevelAt(x + ox, z + oz);
          if (!Number.isNaN(l2)) wet = Math.max(wet, smoothstep(1.0, 0.1, h - l2));
        }
      }
      this.aux[k * 4 + 2] = Math.round(wet * 255);
      this.normalAt(x, z, tmpN, 1);
      const slope = Math.acos(clamp(tmpN.y, -1, 1)) * 57.3;
      const rockW = smoothstep(29, 38, slope + valueNoise(x / 5, z / 5, 8) * 5);
      if (rockW > 0) set(k, SURFACE_INDEX.rock, rockW);
    }
    // crater and pit floors: churned damp soil, loose spoil on the rims
    for (const p of this.pits) {
      forCellsNearPolyline([[p.x, p.z]], p.r * 1.35, mn, (k, d) => {
        const t = d / p.r;
        const b4 = k * 4;
        if (t < 0.85) {
          set(k, SURFACE_INDEX.dirt, 0.9);
          this.aux[b4 + 2] = Math.max(this.aux[b4 + 2], Math.round((1 - t / 0.85) * 150 * Math.min(1, p.d / 0.4)));
          this.aux[b4 + 1] = 0;
        } else if (t < 1.3) {
          set(k, SURFACE_INDEX.gravel, 0.35 * (1 - Math.abs(t - 1.07) / 0.25));
        }
      }, res);
    }
    for (let i = 0; i < W.length; i++) this.mat[i] = Math.round(clamp(W[i], 0, 1) * 255);
    // mud reads as wet
    for (let k = 0; k < mn * mn; k++) this.aux[k * 4 + 2] = Math.max(this.aux[k * 4 + 2], this.mat[k * 4 + 1]);
  }
}

function forCellsNearPolyline(line: [number, number][], R: number, gridN: number, fn: (k: number, d: number) => void, res = 1) {
  const minX = Math.min(...line.map((p) => p[0])) - R, maxX = Math.max(...line.map((p) => p[0])) + R;
  const minZ = Math.min(...line.map((p) => p[1])) - R, maxZ = Math.max(...line.map((p) => p[1])) + R;
  const x0 = Math.max(0, Math.floor((minX + WORLD_HALF) / res)), x1 = Math.min(gridN - 1, Math.ceil((maxX + WORLD_HALF) / res));
  const z0 = Math.max(0, Math.floor((minZ + WORLD_HALF) / res)), z1 = Math.min(gridN - 1, Math.ceil((maxZ + WORLD_HALF) / res));
  for (let iz = z0; iz <= z1; iz++) for (let ix = x0; ix <= x1; ix++) {
    const x = ix * res - WORLD_HALF, z = iz * res - WORLD_HALF;
    let d = Infinity;
    for (let i = 0; i < line.length - 1 || i === 0; i++) {
      const a = line[i], b = line[Math.min(i + 1, line.length - 1)];
      d = Math.min(d, distToSeg(x, z, a[0], a[1], b[0], b[1]));
      if (line.length === 1) break;
    }
    if (d <= R) fn(iz * gridN + ix, d);
  }
}

export function distToSeg(px: number, pz: number, ax: number, az: number, bx: number, bz: number): number {
  const vx = bx - ax, vz = bz - az;
  const l2 = vx * vx + vz * vz;
  const t = l2 > 0 ? clamp(((px - ax) * vx + (pz - az) * vz) / l2, 0, 1) : 0;
  return Math.hypot(px - (ax + vx * t), pz - (az + vz * t));
}

/** Monotone piecewise cubic interpolation. */
export function pchip(xs: number[], ys: number[], x: number): number {
  const n = xs.length;
  if (x <= xs[0]) return ys[0];
  if (x >= xs[n - 1]) return ys[n - 1];
  let i = 0;
  while (i < n - 2 && xs[i + 1] < x) i++;
  const h = (k: number) => xs[k + 1] - xs[k];
  const del = (k: number) => (ys[k + 1] - ys[k]) / (h(k) || 1e-6);
  const slope = (k: number) => {
    if (k === 0) return del(0);
    if (k === n - 1) return del(n - 2);
    const d0 = del(k - 1), d1 = del(k);
    if (d0 * d1 <= 0) return 0;
    const w1 = 2 * h(k) + h(k - 1), w2 = h(k) + 2 * h(k - 1);
    return (w1 + w2) / (w1 / d0 + w2 / d1);
  };
  const t = (x - xs[i]) / (h(i) || 1e-6);
  const m0 = slope(i) * h(i), m1 = slope(i + 1) * h(i);
  const t2 = t * t, t3 = t2 * t;
  return (2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * m1;
}

function bicubic(f: Float32Array, n: number, fx: number, fz: number): number {
  const ix = Math.floor(fx), iz = Math.floor(fz);
  const tx = fx - ix, tz = fz - iz;
  const get = (x: number, z: number) => f[clamp(z, 0, n - 1) * n + clamp(x, 0, n - 1)];
  const cr = (p0: number, p1: number, p2: number, p3: number, t: number) =>
    p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3 + t * (3 * (p1 - p2) + p3 - p0)));
  const rows: number[] = [];
  for (let j = -1; j <= 2; j++) rows.push(cr(get(ix - 1, iz + j), get(ix, iz + j), get(ix + 1, iz + j), get(ix + 2, iz + j), tx));
  return cr(rows[0], rows[1], rows[2], rows[3], tz);
}
