// Rapier world setup: terrain heightfield, static obstacles, collision groups.
import RAPIER from '@dimforge/rapier3d-compat';
import type { Terrain } from '../world/terrain';
import { PHYS_DT } from '../config';

export { RAPIER };

/** collision group bits */
export const G_TERRAIN = 0x0001;
export const G_STATIC = 0x0002;
export const G_CHASSIS = 0x0004;
export const G_WALL = 0x0008;

export const groups = (member: number, filter: number) => ((member & 0xffff) << 16) | (filter & 0xffff);

let ready: Promise<void> | null = null;
export function initRapier(): Promise<void> {
  if (!ready) ready = RAPIER.init();
  return ready;
}

export interface StaticCylinder {
  x: number;
  y: number;
  z: number;
  r: number;
  h: number;
}

export interface StaticBox {
  x: number;
  y: number;
  z: number;
  yaw: number;
  hx: number;
  hy: number;
  hz: number;
}

/** box with a full rotation (bridge deck segments) */
export interface OrientedBox {
  x: number;
  y: number;
  z: number;
  q: { x: number; y: number; z: number; w: number };
  hx: number;
  hy: number;
  hz: number;
  friction?: number;
}

/** horizontal capsule (logs): axis along the local X after yaw */
export interface StaticCapsule {
  x: number;
  y: number;
  z: number;
  yaw: number;
  half: number;
  r: number;
}

export class Physics {
  world: RAPIER.World;
  terrainCollider: RAPIER.Collider;
  readonly staticRayGroups = groups(0xffff, G_STATIC | G_WALL);

  constructor(public terrain: Terrain) {
    this.world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
    this.world.timestep = PHYS_DT;
    this.world.integrationParameters.numSolverIterations = 6;
    const n = terrain.n - 1;
    const desc = RAPIER.ColliderDesc.heightfield(n, n, terrain.rapierHeights(), { x: terrain.size, y: 1, z: terrain.size }, RAPIER.HeightFieldFlags.FIX_INTERNAL_EDGES)
      .setFriction(0.7)
      .setRestitution(0)
      .setCollisionGroups(groups(G_TERRAIN, G_CHASSIS));
    this.terrainCollider = this.world.createCollider(desc);
    // invisible boundary walls a little inside the map edge
    const wall = terrain.half - 18;
    const walls: [number, number, number, number][] = [
      [0, -wall - 1, terrain.size, 1],
      [0, wall + 1, terrain.size, 1],
      [-wall - 1, 0, 1, terrain.size],
      [wall + 1, 0, 1, terrain.size],
    ];
    for (const [x, z, hx, hz] of walls) {
      this.world.createCollider(
        RAPIER.ColliderDesc.cuboid(hx, 200, hz).setTranslation(x, 0, z).setCollisionGroups(groups(G_WALL, G_CHASSIS)),
      );
    }
  }

  addCylinders(list: StaticCylinder[]) {
    for (const c of list) {
      this.world.createCollider(
        RAPIER.ColliderDesc.cylinder(c.h / 2, c.r)
          .setTranslation(c.x, c.y + c.h / 2, c.z)
          .setFriction(0.5)
          .setCollisionGroups(groups(G_STATIC, G_CHASSIS)),
      );
    }
  }

  addBoxes(list: StaticBox[]) {
    for (const b of list) {
      const q = { x: 0, y: Math.sin(b.yaw / 2), z: 0, w: Math.cos(b.yaw / 2) };
      this.world.createCollider(
        RAPIER.ColliderDesc.cuboid(b.hx, b.hy, b.hz)
          .setTranslation(b.x, b.y + b.hy, b.z)
          .setRotation(q)
          .setFriction(0.6)
          .setCollisionGroups(groups(G_STATIC, G_CHASSIS)),
      );
    }
  }

  addOriented(list: OrientedBox[]) {
    for (const b of list) {
      this.world.createCollider(
        RAPIER.ColliderDesc.cuboid(b.hx, b.hy, b.hz)
          .setTranslation(b.x, b.y, b.z)
          .setRotation(b.q)
          .setFriction(b.friction ?? 0.7)
          .setCollisionGroups(groups(G_STATIC, G_CHASSIS)),
      );
    }
  }

  addCapsules(list: StaticCapsule[]) {
    for (const c of list) {
      // Rapier capsules run along Y: roll 90° onto X, then yaw
      const qz = { x: 0, y: 0, z: Math.SQRT1_2, w: Math.SQRT1_2 };
      const qy = { x: 0, y: Math.sin(c.yaw / 2), z: 0, w: Math.cos(c.yaw / 2) };
      const q = {
        w: qy.w * qz.w - qy.y * qz.y,
        x: qy.w * qz.x + qy.y * qz.z,
        y: qy.y * qz.w + qy.w * qz.y,
        z: qy.w * qz.z - qy.y * qz.x,
      };
      this.world.createCollider(
        RAPIER.ColliderDesc.capsule(c.half, c.r)
          .setTranslation(c.x, c.y, c.z)
          .setRotation(q)
          .setFriction(0.75)
          .setCollisionGroups(groups(G_STATIC, G_CHASSIS)),
      );
    }
  }

  /** rigid rocks the wheels can climb onto: convex hulls */
  addHull(points: Float32Array, x: number, y: number, z: number, yaw: number) {
    const desc = RAPIER.ColliderDesc.convexHull(points);
    if (!desc) return;
    desc.setTranslation(x, y, z).setRotation({ x: 0, y: Math.sin(yaw / 2), z: 0, w: Math.cos(yaw / 2) })
      .setFriction(0.8)
      .setCollisionGroups(groups(G_STATIC, G_CHASSIS));
    this.world.createCollider(desc);
  }

  private ray = new RAPIER.Ray({ x: 0, y: 0, z: 0 }, { x: 0, y: -1, z: 0 });

  /** Ray against static obstacles (not terrain). Returns toi or -1; writes normal. */
  castStatic(ox: number, oy: number, oz: number, dx: number, dy: number, dz: number, maxToi: number, nOut: { x: number; y: number; z: number }): number {
    this.ray.origin = { x: ox, y: oy, z: oz };
    this.ray.dir = { x: dx, y: dy, z: dz };
    const hit = this.world.castRayAndGetNormal(this.ray, maxToi, true, undefined, this.staticRayGroups);
    if (!hit) return -1;
    nOut.x = hit.normal.x;
    nOut.y = hit.normal.y;
    nOut.z = hit.normal.z;
    return hit.timeOfImpact;
  }

  /** Line of sight test against terrain + static obstacles */
  lineBlocked(ax: number, ay: number, az: number, bx: number, by: number, bz: number): boolean {
    const dx = bx - ax, dy = by - ay, dz = bz - az;
    const len = Math.hypot(dx, dy, dz);
    if (len < 0.01) return false;
    // terrain: march
    for (let t = 0.5; t < len - 0.5; t += 0.5) {
      const f = t / len;
      const x = ax + dx * f, y = ay + dy * f, z = az + dz * f;
      if (y < this.terrain.heightAt(x, z) - 0.05) return true;
    }
    this.ray.origin = { x: ax, y: ay, z: az };
    this.ray.dir = { x: dx / len, y: dy / len, z: dz / len };
    const hit = this.world.castRay(this.ray, len - 1.2, true, undefined, groups(0xffff, G_STATIC));
    return !!hit;
  }

  step() {
    this.world.step();
  }
}
