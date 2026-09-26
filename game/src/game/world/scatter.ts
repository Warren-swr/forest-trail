// Deterministic placement of trees, undergrowth, rocks and anchors, plus the
// matching static colliders. Pure data so it can run in node for checks.
import { ANCHORS, AUTUMN_ZONES, CLEARINGS, LAKE, LANDMARKS, MEADOW_ZONES, PROPS, RED_ZONES, VIEW_CONES, WORLD_HALF } from './layout';
import { BIG_ROCK_HALF, buildAreas, type AreaResult } from './areas';
import { clamp, fbm, mulberry32, smoothstep, valueNoise } from './noise';
import type { Terrain } from './terrain';
import type { StaticBox, StaticCylinder } from '../physics/physics';

export const TREE_MODELS = ['pine_tall_a', 'pine_tall_b', 'pine_mid', 'pine_young', 'aspen_gold', 'snag', 'maple_red', 'maple_orange', 'birch', 'larch_gold'] as const;
export const UNDER_MODELS = ['bush_a', 'bush_b', 'fern', 'grass_tuft'] as const;
/** dense ground cover layer: short tufts, golden meadow grass, wildflowers */
export const GRASS_MODELS = ['grass_tuft', 'grass_tall', 'flowers_a', 'flowers_b'] as const;
/** models that ship a *_lod1 file */
export const HAS_LOD1 = new Set<string>([...TREE_MODELS, 'bush_a', 'bush_b', 'fern', 'grass_tuft', 'grass_tall']);
export const ROCK_MODELS = ['rock_a', 'rock_b', 'rock_c', 'rock_slab', 'rock_post', 'pebbles', 'log', 'stump', 'boulder_a', 'boulder_b', 'boulder_c', 'sandstone_a', 'sandstone_b', 'sandstone_c'] as const;
export const ROCK_LOD1 = new Set<string>(ROCK_MODELS.slice(0, 8));

export interface Instance {
  kind: number;
  x: number;
  y: number;
  z: number;
  yaw: number;
  s: number;
  /** anchor id when used as a winch anchor */
  anchor?: string;
}

export interface WinchAnchor {
  id: string;
  x: number;
  y: number;
  z: number;
  /** attach height above ground */
  h: number;
  kind: 'tree' | 'rock';
}

export interface ScatterResult {
  trees: Instance[];
  /** dense near-camera grass tufts */
  grass: Instance[];
  under: Instance[];
  rocks: Instance[];
  cylinders: StaticCylinder[];
  boxes: StaticBox[];
  anchors: WinchAnchor[];
  areas: AreaResult;
}

/** trunk radius at the base for scale 1 */
const TRUNK_R = [0.32, 0.3, 0.24, 0.1, 0.16, 0.22, 0.2, 0.2, 0.17, 0.28];
/** rock half extents for scale 1 (x, y, z) */
const ROCK_HALF: [number, number, number][] = [
  [0.9, 0.7, 0.8], [0.7, 0.55, 0.65], [1.1, 0.6, 0.9], [1.2, 0.25, 0.8], [0.4, 0.8, 0.4], [0, 0, 0], [3, 0.25, 0.25], [0.3, 0.3, 0.3],
];

const zone = (zs: [number, number, number][], x: number, z: number, soft = 0.35) => {
  let f = 0;
  for (const [cx, cz, r] of zs) f = Math.max(f, 1 - smoothstep(r * (1 - soft), r, Math.hypot(x - cx, z - cz)));
  return f;
};

export function scatter(T: Terrain): ScatterResult {
  const rnd = mulberry32(1337);
  const areas = buildAreas(T);
  /** footprints of big rocks and placed props that trees must avoid */
  const blockers: [number, number, number][] = areas.rocks.filter((r) => r.kind >= 8).map((r) => {
    const h = BIG_ROCK_HALF[r.kind];
    return [r.x, r.z, Math.max(h[0], h[2]) * r.s + 1.5];
  });
  for (const p of areas.placed) blockers.push([p.x, p.z, p.model === 'plank_bridge' ? 16 : p.model === 'sandstone_arch' ? 10 : 3]);
  const blocked = (x: number, z: number) => blockers.some(([bx, bz, r]) => Math.abs(x - bx) < r && Math.abs(z - bz) < r && Math.hypot(x - bx, z - bz) < r);
  const trees: Instance[] = [];
  const under: Instance[] = [];
  const rocks: Instance[] = [];
  const cylinders: StaticCylinder[] = [];
  const boxes: StaticBox[] = [];
  const anchors: WinchAnchor[] = [];
  const occupied = new Set<number>();
  const key = (x: number, z: number) => (Math.floor(x + WORLD_HALF) >> 1) * 1000 + (Math.floor(z + WORLD_HALF) >> 1);
  const nrm = { x: 0, y: 1, z: 0 };

  const clearingFactor = (x: number, z: number) => {
    let f = 1;
    for (const [cx, cz, r] of CLEARINGS) {
      const d = Math.hypot(x - cx, z - cz) + valueNoise(x / 6, z / 6, 101) * 5;
      f = Math.min(f, smoothstep(r * 0.75, r * 1.1, d));
    }
    for (const p of PROPS) {
      if (!p.flatten) continue;
      f = Math.min(f, smoothstep(p.flatten, p.flatten + 3, Math.hypot(x - p.x, z - p.z)));
    }

    const le = Math.hypot((x - LAKE.cx) / LAKE.rx, (z - LAKE.cz) / LAKE.rz);
    f = Math.min(f, smoothstep(1.12, 1.35, le));
    return f;
  };

  const cones = VIEW_CONES.map(([cx, cz, dx, dz, half, len, eye]) => {
    const ey = T.heightAt(cx, cz) + eye;
    const tx = cx + dx * len, tz = cz + dz * len;
    return { cx, cz, dx, dz, cosHalf: Math.cos((half * Math.PI) / 180), len, ey, ty: T.heightAt(tx, tz) };
  });
  // every landmark's journal shot gets a clear sight line too
  for (const lm of LANDMARKS) {
    const [px, py, pz] = lm.shot.pos, [tx, ty, tz] = lm.shot.target;
    const len = Math.min(340, Math.hypot(tx - px, tz - pz));
    const dx = (tx - px) / Math.hypot(tx - px, tz - pz), dz = (tz - pz) / Math.hypot(tx - px, tz - pz);
    const full = Math.hypot(tx - px, tz - pz);
    cones.push({ cx: px, cz: pz, dx, dz, cosHalf: Math.cos((42 * Math.PI) / 180), len, ey: py, ty: py + (ty - py) * (len / full) });
  }
  /** true when a tree of this top height at x/z would block a landmark view */
  const blocksView = (x: number, z: number, top: number) => {
    for (const c of cones) {
      const vx = x - c.cx, vz = z - c.cz;
      const along = vx * c.dx + vz * c.dz;
      if (along < 0.5 || along > c.len) continue;
      const dist = Math.hypot(vx, vz);
      if (along / dist < c.cosHalf) continue;
      const lineY = c.ey + (c.ty - c.ey) * (along / c.len);
      if (top > lineY - 1.5) return true;
    }
    return false;
  };
  const TREE_H = [18, 18.5, 11, 4.5, 10, 9, 8.5, 8.4, 11.7, 14];

  // ---- anchors first (guaranteed, with colliders)
  for (const a of ANCHORS) {
    const y = T.heightAt(a.x, a.z);
    if (T.roadDistAt(a.x, a.z) < 1.2) console.warn(`[scatter] anchor ${a.id} sits on a road`);
    if (a.kind === 'tree') {
      const s = 1.05 + rnd() * 0.15;
      trees.push({ kind: rnd() < 0.5 ? 0 : 1, x: a.x, y: y - 0.1, z: a.z, yaw: rnd() * 6.28, s, anchor: a.id });
      cylinders.push({ x: a.x, y: y - 0.5, z: a.z, r: TRUNK_R[0] * s, h: 6 });
      anchors.push({ id: a.id, x: a.x, y, z: a.z, h: 0.9, kind: 'tree' });
    } else {
      const s = 1.1;
      rocks.push({ kind: 4, x: a.x, y: y - 0.15, z: a.z, yaw: rnd() * 6.28, s, anchor: a.id });
      cylinders.push({ x: a.x, y: y - 0.3, z: a.z, r: 0.42 * s, h: 2 });
      anchors.push({ id: a.id, x: a.x, y, z: a.z, h: 0.8, kind: 'rock' });
    }
    occupied.add(key(a.x, a.z));
  }

  // ---- trees: jittered grid
  const cell = 3.9;
  for (let gz = -WORLD_HALF + 2; gz < WORLD_HALF - 2; gz += cell) {
    for (let gx = -WORLD_HALF + 2; gx < WORLD_HALF - 2; gx += cell) {
      const x = gx + rnd() * cell, z = gz + rnd() * cell;
      const rd = T.roadDistAt(x, z);
      if (rd < 2.4) continue;
      if (T.waterDepthAt(x, z) > 0 || T.waterDepthAt(x + 2, z) > 0 || T.waterDepthAt(x - 2, z) > 0) continue;
      T.normalAt(x, z, nrm, 1.5);
      if (nrm.y < 0.8) continue;
      const stand = fbm(x / 55, z / 55, 3, 202) * 0.5 + 0.5;
      const edge = rd < 9 ? 0.55 + 0.45 * smoothstep(2.4, 9, rd) : 1;
      const dist = Math.max(Math.abs(x), Math.abs(z));
      const outer = smoothstep(250, 300, dist);
      let cf = clearingFactor(x, z);
      if (z > -120 && z < 60 && Math.abs(x + 20) < 40) {
        // keep the creek valley open around the ford
        const sd = T.stream.nearest(x, z).d;
        cf *= smoothstep(6, 16, sd + valueNoise(x / 8, z / 8, 404) * 3);
      }
      const red = zone(RED_ZONES, x, z);
      let p = (0.3 + stand * 0.62) * edge * cf * (1 - red * 0.75);
      p = Math.max(p, outer * 0.9);
      if (rnd() > p) continue;
      if (blocked(x, z)) continue;
      const k = key(x, z);
      if (occupied.has(k)) continue;
      occupied.add(k);
      // species
      const aspen = fbm(x / 40 + 9, z / 40, 2, 303);
      const r = rnd();
      let kind: number;
      const clearingEdge = cf > 0.05 && cf < 0.85 && dist < 250;
      const autumn = zone(AUTUMN_ZONES, x, z, 0.5);
      if (autumn > 0 && rnd() < autumn * 0.82) {
        const q = rnd();
        kind = q < 0.3 ? 6 : q < 0.52 ? 7 : q < 0.78 ? 8 : 9;
      } else if (red > 0.3) kind = r < 0.5 ? 9 : r < 0.8 ? 2 : 3;
      else if ((aspen > 0.5 || (clearingEdge && r < 0.4)) && rd > 3.5) kind = 4;
      else if (r < 0.03) kind = 5;
      else if (r < 0.18 || (rd < 6 && r < 0.3)) kind = 3;
      else if (r < 0.45) kind = 2;
      else kind = r < 0.72 ? 0 : 1;
      let s = kind === 3 ? 0.8 + rnd() * 0.5 : kind >= 6 ? 0.8 + rnd() * 0.45 : 0.82 + rnd() * 0.38 + stand * 0.12;
      const y = T.heightAt(x, z) - 0.15;
      if (blocksView(x, z, y + TREE_H[kind] * s)) {
        // try a young pine instead, otherwise leave the gap
        if (rnd() > 0.3) continue;
        kind = 3; s = 0.7 + rnd() * 0.35;
        if (blocksView(x, z, y + TREE_H[3] * s)) continue;
      }
      trees.push({ kind, x, y, z, yaw: rnd() * Math.PI * 2, s });
      if (rd < 40) cylinders.push({ x, y: y - 0.5, z, r: TRUNK_R[kind] * s, h: kind === 3 ? 3 : 6 });
    }
  }

  // ---- undergrowth: road edges and forest floor
  for (let i = 0; i < 26000; i++) {
    const x = (rnd() * 2 - 1) * (WORLD_HALF - 20), z = (rnd() * 2 - 1) * (WORLD_HALF - 20);
    const rd = T.roadDistAt(x, z);
    if (rd < 0.9) continue;
    if (T.waterDepthAt(x, z) > 0.02) continue;
    const near = (rd < 14 ? 1 : 0.25) * (1 - zone(RED_ZONES, x, z) * 0.8);
    if (rnd() > near) continue;
    const r = rnd();
    let kind: number;
    if (rd < 3) kind = r < 0.7 ? 3 : 2;
    else if (rd < 8) kind = r < 0.35 ? 0 : r < 0.55 ? 1 : r < 0.8 ? 2 : 3;
    else kind = r < 0.25 ? 0 : r < 0.4 ? 1 : 2;
    const s = 0.7 + rnd() * 0.7;
    under.push({ kind, x, y: T.heightAt(x, z) - 0.05, z, yaw: rnd() * 6.28, s });
  }

  // ---- rocks: scattered boulders off-road, plus authored challenge rocks
  for (let i = 0; i < 900; i++) {
    const x = (rnd() * 2 - 1) * (WORLD_HALF - 15), z = (rnd() * 2 - 1) * (WORLD_HALF - 15);
    const rd = T.roadDistAt(x, z);
    if (rd < 3.2) continue;
    T.normalAt(x, z, nrm, 1.5);
    const steep = 1 - nrm.y;
    if (rnd() > 0.25 + steep * 4) continue;
    if (blocked(x, z)) continue;
    const kind = rnd() < 0.12 ? 7 : rnd() < 0.18 ? 6 : Math.floor(rnd() * 3);
    const s = kind >= 6 ? 0.8 + rnd() * 0.4 : 0.6 + rnd() * 1.1;
    const y = T.heightAt(x, z) - 0.25 * s;
    const yaw = rnd() * 6.28;
    rocks.push({ kind, x, y, z, yaw, s });
    if (rd < 30) addRockCollider(kind, x, y, z, yaw, s);
  }
  // pebbles along road shoulders
  for (let i = 0; i < 3000; i++) {
    const x = (rnd() * 2 - 1) * (WORLD_HALF - 20), z = (rnd() * 2 - 1) * (WORLD_HALF - 20);
    const rd = T.roadDistAt(x, z);
    if (rd < -0.6 || rd > 2.5) continue;
    rocks.push({ kind: 5, x, y: T.heightAt(x, z) - 0.02, z, yaw: rnd() * 6.28, s: 0.7 + rnd() * 0.6 });
  }

  function addRockCollider(kind: number, x: number, y: number, z: number, yaw: number, s: number) {
    const h = ROCK_HALF[kind];
    if (h[0] === 0) return;
    if (kind === 6) {
      boxes.push({ x, y: y + 0.0, z, yaw, hx: h[0] * s, hy: h[1] * s, hz: h[2] * s });
      return;
    }
    if (kind === 7 || kind === 4) {
      cylinders.push({ x, y, z, r: h[0] * s, h: h[1] * 2 * s });
      return;
    }
    boxes.push({ x, y, z, yaw, hx: h[0] * s * 0.85, hy: h[1] * s * 0.9, hz: h[2] * s * 0.85 });
  }

  // rock steps on the rock shortcut and the roots section: low slabs across the track
  const rockRoad = T.roads.find((r) => r.def.id === 'rockShortcut');
  if (rockRoad) {
    const L = rockRoad.path.length;
    for (let s = 8; s < L - 6; s += 5.5) {
      const p = rockRoad.path.at(s);
      const yaw = Math.atan2(-p.tx, -p.tz) + (rnd() - 0.5) * 0.5;
      for (const side of [-1, 1]) {
        if (rnd() < 0.25) continue;
        const off = side * (0.5 + rnd() * 0.6);
        const x = p.x + -p.tz * off, z = p.z + p.tx * off;
        const sc = 0.55 + rnd() * 0.25;
        const y = T.heightAt(x, z) - 0.22 * sc * 2 + 0.16 + rnd() * 0.12;
        rocks.push({ kind: 3, x, y, z, yaw, s: sc });
        boxes.push({ x, y, z, yaw, hx: 1.2 * sc, hy: 0.25 * sc, hz: 0.8 * sc });
      }
    }
  }
  const loop = T.roads.find((r) => r.def.id === 'loop')!;
  {
    // roots / stone steps on B→C near (-90,-76)..(-74,-63)
    const a = loop.path.nearest(-90, -76).s, b = loop.path.nearest(-74, -63).s;
    for (let s = Math.min(a, b); s < Math.max(a, b); s += 3.2) {
      const p = loop.path.at(s);
      const off = (rnd() - 0.5) * 2.4;
      const x = p.x + -p.tz * off, z = p.z + p.tx * off;
      const sc = 0.45 + rnd() * 0.2;
      const yaw = Math.atan2(-p.tx, -p.tz) + (rnd() - 0.5) * 0.8;
      const y = T.heightAt(x, z) - 0.1;
      if (rnd() < 0.5) {
        rocks.push({ kind: 3, x, y: y - 0.05, z, yaw, s: sc });
        boxes.push({ x, y: y - 0.05, z, yaw, hx: 1.2 * sc, hy: 0.25 * sc, hz: 0.8 * sc });
      } else {
        // exposed root: a thin log across part of the track
        rocks.push({ kind: 6, x, y: y - 0.12, z, yaw: yaw + Math.PI / 2, s: 0.35 });
        boxes.push({ x, y: y - 0.12, z, yaw: yaw + Math.PI / 2, hx: 3 * 0.35, hy: 0.25 * 0.35 * 1.2, hz: 0.25 * 0.35 });
      }
    }
    // embedded rocks on the small rocky slope A→B
    const c = loop.path.nearest(-199, 22).s, d = loop.path.nearest(-201, -18).s;
    for (let s = Math.min(c, d); s < Math.max(c, d); s += 2.6) {
      const p = loop.path.at(s);
      const off = (rnd() - 0.5) * 3.2;
      const x = p.x + -p.tz * off, z = p.z + p.tx * off;
      const sc = 0.22 + rnd() * 0.16;
      const kind = Math.floor(rnd() * 3);
      const y = T.heightAt(x, z) - ROCK_HALF[kind][1] * sc * 1.2;
      rocks.push({ kind, x, y, z, yaw: rnd() * 6.28, s: sc });
      boxes.push({ x, y, z, yaw: 0, hx: ROCK_HALF[kind][0] * sc * 0.8, hy: ROCK_HALF[kind][1] * sc, hz: ROCK_HALF[kind][2] * sc * 0.8 });
    }
  }

  // ---- dense grass: jittered grid, weighted by the grass surface, thinner under canopy
  const grass: Instance[] = [];
  const sw = { grass: 0, dirt: 0, mud: 0, gravel: 0, rock: 0 };
  const gcell = 1.25;
  for (let gz = -WORLD_HALF + 20; gz < WORLD_HALF - 20; gz += gcell) {
    for (let gx = -WORLD_HALF + 20; gx < WORLD_HALF - 20; gx += gcell) {
      const x = gx + rnd() * gcell, z = gz + rnd() * gcell;
      T.surfaceAt(x, z, sw);
      const rd = T.roadDistAt(x, z);
      let p = sw.grass * (0.35 + 0.65 * smoothstep(-0.2, 0.5, fbm(x / 18, z / 18, 2, 505)));
      if (rd < 0.6) p *= 0.15;
      p *= 1 - zone(RED_ZONES, x, z) * 0.7;
      const meadow = zone(MEADOW_ZONES, x, z, 0.45) * (rd > 1.2 ? 1 : 0.2);
      p = Math.max(p, meadow * sw.grass * 0.95);
      if (p < 0.08 || rnd() > p) continue;
      if (T.waterDepthAt(x, z) > 0) continue;
      let gk = 0;
      if (meadow > 0.1 && rnd() < 0.3 + meadow * 0.62) gk = rnd() < 0.07 ? (rnd() < 0.5 ? 2 : 3) : 1;
      else if (rd > 2 && rnd() < 0.012) gk = rnd() < 0.6 ? 2 : 3;
      grass.push({ kind: gk, x, y: T.heightAt(x, z) - 0.03, z, yaw: rnd() * 6.28, s: gk === 1 ? 0.8 + rnd() * 0.5 : 0.65 + rnd() * 0.7 });
    }
  }

  // canopy density into the terrain aux alpha channel (forest floor tint)
  const mn = T.mn, res = T.matRes;
  const canopy = new Float32Array(mn * mn);
  for (const t of trees) {
    if (t.kind === 5) continue;
    const R = t.kind === 3 ? 2 : 4.5;
    const x0 = Math.max(0, Math.floor((t.x + WORLD_HALF - R) / res)), x1 = Math.min(mn - 1, Math.ceil((t.x + WORLD_HALF + R) / res));
    const z0 = Math.max(0, Math.floor((t.z + WORLD_HALF - R) / res)), z1 = Math.min(mn - 1, Math.ceil((t.z + WORLD_HALF + R) / res));
    for (let iz = z0; iz <= z1; iz++) for (let ix = x0; ix <= x1; ix++) {
      const d = Math.hypot(ix * res - WORLD_HALF - t.x, iz * res - WORLD_HALF - t.z);
      if (d < R) canopy[iz * mn + ix] += (1 - d / R) * 0.6;
    }
  }
  for (let k = 0; k < mn * mn; k++) T.aux[k * 4 + 3] = Math.round(clamp(canopy[k], 0, 1) * 255);

  // second-wave areas: big rocks, course dressing, bridge
  rocks.push(...areas.rocks);
  boxes.push(...areas.boxes);
  cylinders.push(...areas.cylinders);
  return { trees, grass, under, rocks, cylinders, boxes, anchors, areas };
}
