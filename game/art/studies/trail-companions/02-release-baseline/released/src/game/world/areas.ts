// Derived placements for the second-wave areas: plank bridge, canyon rocks and
// arch, boulder slopes, trail park course dressing, log steps, rock garden,
// camp string lights and night light sources. Pure data (no rendering) so the
// same colliders exist in node tests and in the game.
import { BRIDGE, FEATURES, PARK_GATES, PROPS } from './layout';
import { mulberry32 } from './noise';
import type { Road, Terrain } from './terrain';
import type { Instance } from './scatter';
import type { OrientedBox, StaticBox, StaticCapsule, StaticCylinder } from '../physics/physics';

/** a non-instanced prop placed by code (yaw in radians, 0 = model front faces -Z) */
export interface Placed {
  model: string;
  x: number;
  y: number;
  z: number;
  yaw: number;
  s?: number;
  /** non-uniform scale */
  sv?: [number, number, number];
}

export interface LightDef {
  x: number;
  y: number;
  z: number;
  color: [number, number, number];
  range: number;
  intensity: number;
  /** campfire flicker */
  flicker?: boolean;
}

export interface AreaResult {
  placed: Placed[];
  /** extra instances for the rock layer, using the scatter ROCK_MODELS kinds */
  rocks: Instance[];
  boxes: StaticBox[];
  oriented: OrientedBox[];
  capsules: StaticCapsule[];
  cylinders: StaticCylinder[];
  lights: LightDef[];
  /** string light spans between pole hooks */
  strings: { a: [number, number, number]; b: [number, number, number] }[];
}

/** rock layer kinds added in scatter.ts (after the first-version rocks) */
export const K_BOULDER = [8, 9, 10];
export const K_SANDSTONE = [11, 12, 13];
/** collider half extents (x, height, z) for the kinds above at scale 1 */
export const BIG_ROCK_HALF: Record<number, [number, number, number]> = {
  8: [1.32, 0.95, 1.11], 9: [1.85, 1.34, 1.27], 10: [0.95, 0.66, 0.81],
  11: [6.0, 4.9, 4.25], 12: [2.47, 7.04, 2.38], 13: [4.78, 2.05, 3.26],
};

const WARM: [number, number, number] = [1, 0.66, 0.34];
const FIRE: [number, number, number] = [1, 0.5, 0.18];

function yawOf(tx: number, tz: number) {
  return Math.atan2(-tx, -tz);
}

function quatYawPitch(yaw: number, pitch: number) {
  const cy = Math.cos(yaw / 2), sy = Math.sin(yaw / 2), cp = Math.cos(pitch / 2), sp = Math.sin(pitch / 2);
  // q = qYaw(Y) * qPitch(X)
  return { w: cy * cp, x: cy * sp, y: sy * cp, z: -sy * sp };
}

/** rotate a model-space offset (x right, z back) by yaw and add to a base point */
function offset(x: number, z: number, yaw: number, ox: number, oz: number): [number, number] {
  const c = Math.cos(yaw), s = Math.sin(yaw);
  return [x + ox * c + oz * s, z - ox * s + oz * c];
}

export function buildAreas(T: Terrain): AreaResult {
  const rnd = mulberry32(4242);
  const out: AreaResult = { placed: [], rocks: [], boxes: [], oriented: [], capsules: [], cylinders: [], lights: [], strings: [] };
  const road = (id: string) => T.roads.find((r) => r.def.id === id) as Road | undefined;
  const side = (p: { x: number; z: number; tx: number; tz: number }, lat: number): [number, number] => [p.x + -p.tz * lat, p.z + p.tx * lat];
  const addBigRock = (kind: number, x: number, z: number, s: number, yaw: number, sink: number, collide = true) => {
    // never let a boulder or cliff block any road (e.g. where two roads meet)
    const hb = BIG_ROCK_HALF[kind];
    if (T.roadDistAt(x, z) < Math.hypot(hb[0], hb[2]) * s * 0.88 + 0.4) return;
    const y = T.heightAt(x, z) - sink;
    out.rocks.push({ kind, x, y, z, yaw, s });
    if (!collide) return;
    const h = BIG_ROCK_HALF[kind];
    out.boxes.push({ x, y: y - h[1] * s * 0.2, z, yaw, hx: h[0] * s * 0.88, hy: h[1] * s, hz: h[2] * s * 0.88 });
  };

  // ------------------------------------------------------------ plank bridge
  const b = T.bridge;
  if (b) {
    const yaw = yawOf(b.tx, b.tz);
    out.placed.push({ model: 'plank_bridge', x: b.x, y: b.y, z: b.z, yaw });
    const segs = 12, L = BRIDGE.half * 2, seg = L / segs;
    for (let i = 0; i < segs; i++) {
      const u = -BRIDGE.half + (i + 0.5) * seg;
      const top = -BRIDGE.sag * (1 - (u / BRIDGE.half) ** 2);
      const slope = (2 * BRIDGE.sag * u) / (BRIDGE.half * BRIDGE.half);
      out.oriented.push({
        x: b.x + b.tx * u, y: b.y + top - 0.1, z: b.z + b.tz * u,
        q: quatYawPitch(yaw, Math.atan(slope)), hx: BRIDGE.width / 2, hy: 0.1, hz: seg / 2 + 0.06, friction: 0.8,
      });
    }
    // rope rails keep the car on the deck
    for (const s of [-1, 1]) {
      const [x, z] = side(b, s * (BRIDGE.width / 2 + 0.12));
      out.oriented.push({ x, y: b.y + 0.45, z, q: quatYawPitch(yaw, 0), hx: 0.06, hy: 0.55, hz: BRIDGE.half, friction: 0.2 });
    }
  }

  // ------------------------------------------------------------ canyon walls and arch
  const cn = road('canyon');
  if (cn) {
    const L = cn.path.length;
    const sb = b ? cn.path.nearest(b.x, b.z).s : -100;
    let flip = 1;
    for (let s = 26; s < L - 14; s += 11 + rnd() * 5) {
      if (Math.abs(s - sb) < 19) continue;
      const p = cn.path.at(s);
      flip = rnd() < 0.7 ? -flip : flip;
      for (const sd of [flip, rnd() < 0.45 ? -flip : 0]) {
        if (!sd) continue;
        const kind = K_SANDSTONE[rnd() < 0.45 ? 0 : rnd() < 0.5 ? 1 : 2];
        const sc = 0.75 + rnd() * 0.5;
        const foot = Math.max(BIG_ROCK_HALF[kind][0], BIG_ROCK_HALF[kind][2]) * sc;
        const lat = sd * (cn.halfWidth + 3.5 + foot + rnd() * 6);
        const [x, z] = side(p, lat);
        if (T.roadDistAt(x, z) < foot * 0.6) continue;
        addBigRock(kind, x, z, sc, rnd() * Math.PI * 2, 0.8 + rnd() * 1.2, Math.abs(lat) < 30);
      }
    }
    // a natural arch the road passes through near the end
    const pa = cn.path.at(L - 24);
    const ay = yawOf(pa.tx, pa.tz);
    const hy = T.heightAt(pa.x, pa.z) - 0.3;
    out.placed.push({ model: 'sandstone_arch', x: pa.x, y: hy, z: pa.z, yaw: ay });
    for (const [ox, oy, oz, hx, hh, hz] of [[-5.3, 2.7, 0, 1.9, 2.7, 1.9], [5.3, 2.7, 0, 1.9, 2.7, 1.9], [0, 7.05, 0, 6.9, 1.85, 1.9]]) {
      const [x, z] = offset(pa.x, pa.z, ay, ox, oz);
      out.boxes.push({ x, y: hy + oy - hh, z, yaw: ay, hx, hy: hh, hz });
    }
    // loose boulders on the canyon floor
    for (let i = 0; i < 10; i++) {
      const s = 20 + rnd() * (L - 40);
      if (Math.abs(s - sb) < 16) continue;
      const p = cn.path.at(s);
      const [x, z] = side(p, (rnd() < 0.5 ? -1 : 1) * (cn.halfWidth + 1.8 + rnd() * 3));
      addBigRock(K_BOULDER[Math.floor(rnd() * 3)], x, z, 0.45 + rnd() * 0.4, rnd() * 6.28, 0.25);
    }
  }

  // ------------------------------------------------------------ boulder slopes by the rock steps and the lookout
  const rs = road('rockShortcut');
  if (rs) {
    for (let s = 2; s < rs.path.length - 2; s += 5.5 + rnd() * 3) {
      const p = rs.path.at(s);
      for (const sd of [-1, 1]) {
        if (rnd() < 0.3) continue;
        const [x, z] = side(p, sd * (rs.halfWidth + 2.2 + rnd() * 4));
        addBigRock(K_BOULDER[Math.floor(rnd() * 3)], x, z, 0.7 + rnd() * 0.55, rnd() * 6.28, 0.3);
      }
    }
  }
  for (const [x, z, s] of [[196, -232, 1.2], [168, -236, 0.9], [160, -208, 1.1], [193, -200, 0.8], [202, -218, 1.3]] as const) {
    addBigRock(K_BOULDER[Math.floor(rnd() * 3)], x, z, s, rnd() * 6.28, 0.3);
  }

  // ------------------------------------------------------------ trail park
  const pk = road('park');
  if (pk) {
    const hw = pk.halfWidth;
    const at = (x: number, z: number) => pk.path.at(pk.path.nearest(x, z).s);
    // start / finish arch
    const g0 = at(PARK_GATES[0][0], PARK_GATES[0][1]);
    const gy = yawOf(g0.tx, g0.tz);
    out.placed.push({ model: 'gate_arch', x: g0.x, y: T.heightAt(g0.x, g0.z) - 0.05, z: g0.z, yaw: gy });
    for (const sd of [-1, 1]) {
      const [x, z] = offset(g0.x, g0.z, gy, sd * 4, 0);
      out.cylinders.push({ x, y: T.heightAt(x, z) - 0.3, z, r: 0.28, h: 5 });
    }
    // checkpoint flags
    for (let i = 1; i < PARK_GATES.length; i++) {
      const g = at(PARK_GATES[i][0], PARK_GATES[i][1]);
      for (const sd of [-1, 1]) {
        const [x, z] = side(g, sd * (hw + 0.9));
        out.placed.push({ model: 'flag_marker', x, y: T.heightAt(x, z) - 0.05, z, yaw: yawOf(g.tx, g.tz) + (sd < 0 ? Math.PI : 0) });
      }
    }
    // cones along the crater field and the moguls, sign boards at each section
    for (const f of T.features) {
      if (f.road !== pk) continue;
      const p0 = pk.path.at(Math.max(0, f.s0 - 4));
      const [sx, sz] = side(p0, -(hw + 1.6));
      out.placed.push({ model: 'sign_board', x: sx, y: T.heightAt(sx, sz) - 0.05, z: sz, yaw: yawOf(p0.tx, p0.tz) + Math.PI / 2 });
      if (f.f.kind === 'craters' || f.f.kind === 'crossAxle') {
        for (let s = f.s0; s < f.s1; s += 5) {
          const p = pk.path.at(s);
          for (const sd of [-1, 1]) {
            const [x, z] = side(p, sd * (hw + 0.7));
            out.placed.push({ model: 'cone', x, y: T.heightAt(x, z) - 0.02, z, yaw: rnd() * 6.28 });
          }
        }
      }
      if (f.f.kind === 'bank') {
        // safety barriers on the low side of the side slope
        for (let s = f.s0 + 3; s < f.s1 - 2; s += 3.4) {
          const p = pk.path.at(s);
          const [x, z] = side(p, -(hw + 1.5));
          const yaw = yawOf(p.tx, p.tz) + Math.PI / 2;
          const y = T.heightAt(x, z) - 0.02;
          out.placed.push({ model: 'barrier', x, y, z, yaw });
          out.boxes.push({ x, y, z, yaw, hx: 1.5, hy: 0.5, hz: 0.3 });
        }
      }
      if (f.f.kind === 'craters') {
        // tyre walls on the outside of the crater field
        for (let s = f.s0 + 4; s < f.s1; s += 9) {
          const p = pk.path.at(s);
          const [x, z] = side(p, hw + 2.6);
          const yaw = yawOf(p.tx, p.tz) + Math.PI / 2;
          const y = T.heightAt(x, z) - 0.05;
          out.placed.push({ model: 'tyre_wall', x, y, z, yaw });
          out.boxes.push({ x, y, z, yaw, hx: 1.8, hy: 0.28, hz: 0.2 });
        }
      }
    }
    // tyre stacks on the corners
    for (const [x, z] of [[-60, 238], [-80, 296], [-176, 290], [-203, 250], [-176, 202]] as const) {
      out.placed.push({ model: 'tyre_stack', x, y: T.heightAt(x, z), z, yaw: rnd() * 6.28 });
      out.cylinders.push({ x, y: T.heightAt(x, z) - 0.2, z, r: 0.45, h: 1.05 });
    }
    // log steps between the washboard and the rock garden
    const sA = pk.path.nearest(-195.5, 233).s;
    for (let i = 0; i < 4; i++) {
      const p = pk.path.at(sA + i * 5.5);
      const yaw = yawOf(p.tx, p.tz) + (i % 2 ? 0.12 : -0.1);
      const r = 0.2 + (i % 2) * 0.03;
      const k = r / 0.35;
      const y = T.heightAt(p.x, p.z);
      out.placed.push({ model: 'log_step', x: p.x, y: y - 0.07, z: p.z, yaw, sv: [1, k, k] });
      out.capsules.push({ x: p.x, y: y - 0.07 + r, z: p.z, yaw, half: 3 - r, r });
    }
    // rock garden: half-buried rocks and slabs on the track, with gaps to pick a line
    const sR0 = pk.path.nearest(-184, 211).s, sR1 = pk.path.nearest(-168, 206).s;
    const g1 = Math.min(sR0, sR1), g2 = Math.max(sR0, sR1);
    const L = pk.path.length;
    const inRange = (s: number) => (g1 < g2 && g2 - g1 < L / 2 ? s >= g1 && s <= g2 : s >= g2 || s <= g1);
    for (let s = g1 + 1; inRange(s % L) && s < g1 + 40; s += 2.3) {
      const p = pk.path.at(s % L);
      const lat = (rnd() - 0.5) * 2 * (hw - 0.6);
      const [x, z] = side(p, lat);
      const slab = rnd() < 0.3;
      const kind = slab ? 3 : Math.floor(rnd() * 3);
      const sc = slab ? 0.5 + rnd() * 0.2 : 0.3 + rnd() * 0.16;
      const hh = [0.7, 0.55, 0.6, 0.25][kind] * sc;
      const y = T.heightAt(x, z) - hh * (slab ? 0.6 : 1.05);
      const yaw = rnd() * 6.28;
      out.rocks.push({ kind, x, y, z, yaw, s: sc });
      const hx = [0.9, 0.7, 1.1, 1.2][kind] * sc * 0.8, hz = [0.8, 0.65, 0.9, 0.8][kind] * sc * 0.8;
      out.boxes.push({ x, y, z, yaw, hx, hy: hh, hz });
    }
  }

  // ------------------------------------------------------------ camp string lights and night lights
  const poles = PROPS.filter((p) => p.model === 'string_pole');
  const hook = (p: { x: number; z: number }): [number, number, number] => [p.x, T.heightAt(p.x, p.z) + 2.52, p.z - 0.08];
  for (let i = 0; i < poles.length; i++) out.strings.push({ a: hook(poles[i]), b: hook(poles[(i + 1) % poles.length]) });
  const h = (x: number, z: number) => T.heightAt(x, z);
  for (const p of PROPS) {
    const y = (p.absY ?? h(p.x, p.z) + (p.dy ?? 0));
    const yaw = (p.yaw * Math.PI) / 180;
    const put = (ox: number, oy: number, oz: number, color: [number, number, number], range: number, intensity: number, flicker = false) => {
      const [x, z] = offset(p.x, p.z, yaw, ox, oz);
      out.lights.push({ x, y: y + oy, z, color, range, intensity, flicker });
    };
    switch (p.model) {
      case 'campfire': put(0, 0.7, 0, FIRE, 15, 3.2, true); break;
      case 'lantern': put(0, 0.3, 0, WARM, 6, 0.6); break;
      case 'lamp_post': put(0, 2.45, -0.55, WARM, 12, 1.4); break;
      case 'boathouse': put(0, 2.3, -19.8, WARM, 12, 1.2); put(0, 2.6, -9, WARM, 9, 0.8); break;
      case 'aframe_cabin': put(0, 2.2, -3.2, WARM, 10, 1.2); break;
      case 'cabin': put(0, 2.3, -3.6, WARM, 10, 1.2); break;
      case 'shed': put(0, 2.3, -2.4, WARM, 8, 0.9); break;
      case 'lookout': put(0, 3.2, 0, WARM, 10, 0.9); break;
      case 'camper': put(0.9, 1.4, 0, WARM, 7, 0.7); break;
    }
  }
  // over the camp table, under the string lights
  out.lights.push({ x: -188, y: h(-188, 179) + 2.2, z: 179, color: WARM, range: 14, intensity: 0.7 });
  // boathouse pier deck and hut are solid
  const bh = PROPS.find((p) => p.model === 'boathouse');
  if (bh && bh.absY !== undefined) {
    const yaw = (bh.yaw * Math.PI) / 180;
    for (const [ox, oz, hx, hz] of [[0, -8, 1.5, 8], [0, -19.5, 3.5, 3.5]]) {
      const [x, z] = offset(bh.x, bh.z, yaw, ox, oz);
      out.boxes.push({ x, y: bh.absY - 0.3, z, yaw, hx, hy: 0.15, hz });
    }
    const [x, z] = offset(bh.x, bh.z, yaw, 0, -19.8);
    out.boxes.push({ x, y: bh.absY, z, yaw, hx: 2.0, hy: 1.85, hz: 2.5 });
  }
  void FEATURES;
  return out;
}
