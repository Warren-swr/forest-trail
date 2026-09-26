// Minimal allocation-free vector helpers for the physics code.
export interface V3 { x: number; y: number; z: number }
export interface Q4 { x: number; y: number; z: number; w: number }

export const v3 = (x = 0, y = 0, z = 0): V3 => ({ x, y, z });
export const set = (o: V3, x: number, y: number, z: number) => { o.x = x; o.y = y; o.z = z; return o; };
export const copy = (o: V3, a: V3) => { o.x = a.x; o.y = a.y; o.z = a.z; return o; };
export const dot = (a: V3, b: V3) => a.x * b.x + a.y * b.y + a.z * b.z;
export const len = (a: V3) => Math.hypot(a.x, a.y, a.z);
export const cross = (o: V3, a: V3, b: V3) => set(o, a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
export const normalize = (o: V3) => {
  const l = Math.hypot(o.x, o.y, o.z) || 1;
  o.x /= l; o.y /= l; o.z /= l;
  return o;
};
/** o = a + b * s */
export const addScaled = (o: V3, a: V3, b: V3, s: number) => set(o, a.x + b.x * s, a.y + b.y * s, a.z + b.z * s);

/** rotate vector v by unit quaternion q */
export function rotate(o: V3, q: Q4, vx: number, vy: number, vz: number): V3 {
  const { x: qx, y: qy, z: qz, w: qw } = q;
  const ix = qw * vx + qy * vz - qz * vy;
  const iy = qw * vy + qz * vx - qx * vz;
  const iz = qw * vz + qx * vy - qy * vx;
  const iw = -qx * vx - qy * vy - qz * vz;
  return set(o, ix * qw + iw * -qx + iy * -qz - iz * -qy, iy * qw + iw * -qy + iz * -qx - ix * -qz, iz * qw + iw * -qz + ix * -qy - iy * -qx);
}

export function quatFromYaw(yaw: number): Q4 {
  return { x: 0, y: Math.sin(yaw / 2), z: 0, w: Math.cos(yaw / 2) };
}

/** yaw of a heading vector where yaw 0 faces -Z */
export const yawOf = (dx: number, dz: number) => Math.atan2(-dx, -dz);

export function slerp(o: Q4, a: Q4, b: Q4, t: number): Q4 {
  let bx = b.x, by = b.y, bz = b.z, bw = b.w;
  let c = a.x * bx + a.y * by + a.z * bz + a.w * bw;
  if (c < 0) { c = -c; bx = -bx; by = -by; bz = -bz; bw = -bw; }
  let s0 = 1 - t, s1 = t;
  if (c < 0.9995) {
    const th = Math.acos(c), sn = Math.sin(th);
    s0 = Math.sin((1 - t) * th) / sn;
    s1 = Math.sin(t * th) / sn;
  }
  o.x = a.x * s0 + bx * s1; o.y = a.y * s0 + by * s1; o.z = a.z * s0 + bz * s1; o.w = a.w * s0 + bw * s1;
  const l = Math.hypot(o.x, o.y, o.z, o.w);
  o.x /= l; o.y /= l; o.z /= l; o.w /= l;
  return o;
}
