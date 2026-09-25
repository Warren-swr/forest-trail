import { useEffect, useRef } from 'react';
import type { HudState } from '../game/store';
import { game } from '../game/boot';
import { LANDMARKS, PARK_GATES, TOOLBOX, WORLD_HALF, WORLD_SIZE } from '../game/world/layout';

let relief: HTMLCanvasElement | null = null;

function buildRelief(): HTMLCanvasElement | null {
  const g = game;
  if (!g) return null;
  const T = g.terrain;
  const N = 640;
  const c = document.createElement('canvas');
  c.width = N; c.height = N;
  const ctx = c.getContext('2d')!;
  const img = ctx.createImageData(N, N);
  const nrm = { x: 0, y: 1, z: 0 };
  const sw = { grass: 0, dirt: 0, mud: 0, gravel: 0, rock: 0 };
  for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
    const x = i - WORLD_HALF + 0.5, z = j - WORLD_HALF + 0.5;
    const h = T.heightAt(x, z);
    T.normalAt(x, z, nrm, 1.5);
    const shade = Math.max(0.35, Math.min(1.2, 0.75 + nrm.x * -0.9 + nrm.z * -0.9));
    T.surfaceAt(x, z, sw);
    // paper map palette
    let r = 196, gg = 196, b = 160;
    const canopy = T.aux[((Math.round((z + WORLD_HALF) * 2)) * T.mn + Math.round((x + WORLD_HALF) * 2)) * 4 + 3] / 255;
    r -= canopy * 70; gg -= canopy * 40; b -= canopy * 70;
    const road = sw.dirt + sw.gravel + sw.mud * 0.8;
    r = r * (1 - road) + (sw.mud > 0.4 ? 120 : 214) * road;
    gg = gg * (1 - road) + (sw.mud > 0.4 ? 96 : 186) * road;
    b = b * (1 - road) + (sw.mud > 0.4 ? 70 : 140) * road;
    r = r * (1 - sw.rock * 0.6) + 150 * sw.rock * 0.6;
    gg = gg * (1 - sw.rock * 0.6) + 146 * sw.rock * 0.6;
    b = b * (1 - sw.rock * 0.6) + 138 * sw.rock * 0.6;
    const band = Math.abs(((h / 5) % 1) - 0.5) < 0.04 ? 0.88 : 1;
    r *= shade * band; gg *= shade * band; b *= shade * band;
    const d = T.waterDepthAt(x, z);
    if (d > 0.02) { const a = Math.min(0.9, 0.45 + d * 0.3); r = r * (1 - a) + 90 * a; gg = gg * (1 - a) + 140 * a; b = b * (1 - a) + 165 * a; }
    const k = (j * N + i) * 4;
    img.data[k] = r; img.data[k + 1] = gg; img.data[k + 2] = b; img.data[k + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  return c;
}

export function MapView({ s }: { s: HudState }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    if (!relief) relief = buildRelief();
    const ctx = cv.getContext('2d')!;
    const S = cv.width;
    const k = S / WORLD_SIZE;
    const P = (x: number, z: number) => [(x + WORLD_HALF) * k, (z + WORLD_HALF) * k] as const;
    ctx.clearRect(0, 0, S, S);
    if (relief) ctx.drawImage(relief, 0, 0, S, S);
    ctx.font = '600 13px "Noto Sans SC", sans-serif';
    ctx.textAlign = 'center';
    for (const l of LANDMARKS) {
      const [px, py] = P(l.x, l.z);
      const done = s.visited.includes(l.id) || (l.id === 'camp') || !!s.photos[l.id];
      ctx.beginPath();
      ctx.arc(px, py, l.isGoal || l.id === 'camp' ? 8 : 6, 0, Math.PI * 2);
      ctx.fillStyle = done ? '#e0a64a' : l.isGoal || l.id === 'camp' ? 'rgba(255,255,255,0.85)' : 'rgba(127,211,196,0.9)';
      ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = '#2b2a22'; ctx.stroke();
      if (s.visited.includes(l.id) || (!l.isGoal && s.photos[l.id])) { ctx.fillStyle = '#2b2a22'; ctx.fillText('✓', px, py + 4.5); }
      ctx.fillStyle = '#1d231d';
      ctx.fillText(l.name, px, py - 14);
    }
    if (!s.hasToolbox) {
      const [tx, ty] = P(TOOLBOX.x, TOOLBOX.z);
      ctx.fillStyle = '#1d231d';
      ctx.font = '500 12px "Noto Sans SC", sans-serif';
      ctx.fillText('旧锯木场 ?', tx, ty - 10);
    }
    // road labels
    ctx.font = 'italic 12px "Noto Sans SC", sans-serif';
    ctx.fillStyle = 'rgba(40,40,30,0.8)';
    const lbl = (t: string, x: number, z: number) => { const [a, b] = P(x, z); ctx.fillText(t, a, b); };
    lbl('泥坡近路', 150, -60); lbl('碎石绕路', 72, -92); lbl('岩阶', 192, -186); lbl('湖', -22, 115); lbl('松溪', -60, -150);
    lbl('训练场环线', -125, 252); lbl('赤岩峡谷', -212, -150); lbl('吊桥', -225, -212); lbl('秋色林', 228, 10);
    // trail park gates
    ctx.fillStyle = '#b75b3d';
    for (const [gx, gz] of PARK_GATES) { const [a, b] = P(gx, gz); ctx.fillRect(a - 2.5, b - 2.5, 5, 5); }
    // player
    const g = game;
    if (g) {
      const v = g.vehicle;
      const [px, py] = P(v.pos.x, v.pos.z);
      const yaw = v.yaw;
      ctx.save();
      ctx.translate(px, py);
      ctx.rotate(-yaw);
      ctx.beginPath();
      ctx.moveTo(0, -11); ctx.lineTo(7, 8); ctx.lineTo(0, 4); ctx.lineTo(-7, 8); ctx.closePath();
      ctx.fillStyle = '#b75b3d'; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = '#fff'; ctx.stroke();
      ctx.restore();
    }
    // compass rose
    ctx.fillStyle = '#1d231d'; ctx.font = '700 14px sans-serif';
    ctx.fillText('N', S - 24, 26);
    ctx.beginPath(); ctx.moveTo(S - 24, 30); ctx.lineTo(S - 29, 44); ctx.lineTo(S - 19, 44); ctx.fill();
  }, [s.visited, s.hasToolbox, s.screen, s.photos]);
  return <canvas ref={ref} width={640} height={640} className="map-canvas" />;
}
