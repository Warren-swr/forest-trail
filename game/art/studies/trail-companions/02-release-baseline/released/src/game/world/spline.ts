// Planar Catmull-Rom path with arc-length sampling (x/z plane).

export interface PathSample {
  x: number;
  z: number;
  /** unit tangent */
  tx: number;
  tz: number;
  s: number;
}

export class Path2 {
  readonly samples: PathSample[] = [];
  readonly length: number;
  readonly step: number;

  constructor(points: [number, number][], step = 1, public readonly closed = false) {
    this.step = step;
    const pts = points.slice();
    const dense: [number, number][] = [];
    const n = pts.length;
    const get = (i: number) => {
      if (closed) return pts[(i + n) % n];
      return pts[Math.max(0, Math.min(n - 1, i))];
    };
    const segs = closed ? n : n - 1;
    for (let i = 0; i < segs; i++) {
      const p0 = get(i - 1), p1 = get(i), p2 = get(i + 1), p3 = get(i + 2);
      const segLen = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
      const sub = Math.max(4, Math.ceil(segLen / 0.5));
      for (let k = 0; k < sub; k++) {
        const t = k / sub;
        dense.push(catmull(p0, p1, p2, p3, t));
      }
    }
    dense.push(closed ? pts[0] : pts[n - 1]);
    // cumulative length
    const cum = [0];
    for (let i = 1; i < dense.length; i++) {
      cum.push(cum[i - 1] + Math.hypot(dense[i][0] - dense[i - 1][0], dense[i][1] - dense[i - 1][1]));
    }
    this.length = cum[cum.length - 1];
    let j = 0;
    const count = Math.max(2, Math.round(this.length / step) + 1);
    const realStep = this.length / (count - 1);
    this.step = realStep;
    for (let i = 0; i < count; i++) {
      const s = i * realStep;
      while (j < cum.length - 2 && cum[j + 1] < s) j++;
      const segL = cum[j + 1] - cum[j] || 1;
      const t = (s - cum[j]) / segL;
      const x = dense[j][0] + (dense[j + 1][0] - dense[j][0]) * t;
      const z = dense[j][1] + (dense[j + 1][1] - dense[j][1]) * t;
      this.samples.push({ x, z, tx: 0, tz: 0, s });
    }
    for (let i = 0; i < this.samples.length; i++) {
      const a = this.samples[Math.max(0, i - 1)];
      const b = this.samples[Math.min(this.samples.length - 1, i + 1)];
      const l = Math.hypot(b.x - a.x, b.z - a.z) || 1;
      this.samples[i].tx = (b.x - a.x) / l;
      this.samples[i].tz = (b.z - a.z) / l;
    }
  }

  at(s: number): PathSample {
    if (this.closed) s = ((s % this.length) + this.length) % this.length;
    const f = Math.max(0, Math.min(this.samples.length - 1, s / this.step));
    const i = Math.floor(f);
    const t = f - i;
    const a = this.samples[i];
    const b = this.samples[Math.min(this.samples.length - 1, i + 1)];
    const tx = a.tx + (b.tx - a.tx) * t;
    const tz = a.tz + (b.tz - a.tz) * t;
    const l = Math.hypot(tx, tz) || 1;
    return { x: a.x + (b.x - a.x) * t, z: a.z + (b.z - a.z) * t, tx: tx / l, tz: tz / l, s };
  }

  /** Nearest sample (coarse then refine). Returns arc length and signed lateral distance (+ = right of travel). */
  nearest(x: number, z: number, hintS?: number, window = 40): { s: number; d: number; lateral: number } {
    let best = Infinity;
    let bi = 0;
    const n = this.samples.length;
    let lo = 0, hi = n - 1;
    if (hintS !== undefined) {
      lo = Math.floor((hintS - window) / this.step);
      hi = Math.ceil((hintS + window) / this.step);
      if (!this.closed) { lo = Math.max(0, lo); hi = Math.min(n - 1, hi); }
    }
    for (let j = lo; j <= hi; j++) {
      const i = ((j % n) + n) % n;
      const p = this.samples[i];
      const d = (p.x - x) * (p.x - x) + (p.z - z) * (p.z - z);
      if (d < best) { best = d; bi = i; }
    }
    const p = this.samples[bi];
    // right vector of travel in x/z with y up: right = (-tz, tx)? forward (tx,tz), right = (-tz, tx) when z is south.
    const lateral = (x - p.x) * -p.tz + (z - p.z) * p.tx;
    return { s: p.s, d: Math.sqrt(best), lateral };
  }
}

function catmull(p0: [number, number], p1: [number, number], p2: [number, number], p3: [number, number], t: number): [number, number] {
  // centripetal catmull-rom (alpha = 0.5)
  const alpha = 0.5;
  const tj = (ti: number, a: [number, number], b: [number, number]) => ti + Math.pow(Math.hypot(b[0] - a[0], b[1] - a[1]) || 1e-4, alpha);
  const t0 = 0;
  const t1 = tj(t0, p0, p1);
  const t2 = tj(t1, p1, p2);
  const t3 = tj(t2, p2, p3);
  const tt = t1 + (t2 - t1) * t;
  const lerp2 = (a: [number, number], b: [number, number], ta: number, tb: number): [number, number] => {
    const w = (tt - ta) / (tb - ta || 1e-6);
    return [a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w];
  };
  const A1 = lerp2(p0, p1, t0, t1);
  const A2 = lerp2(p1, p2, t1, t2);
  const A3 = lerp2(p2, p3, t2, t3);
  const B1 = lerp2(A1, A2, t0, t2);
  const B2 = lerp2(A2, A3, t1, t3);
  return lerp2(B1, B2, t1, t2);
}
