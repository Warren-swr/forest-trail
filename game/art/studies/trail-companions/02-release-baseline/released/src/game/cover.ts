// Game cover (3:2 portrait, 1200 x 1800): renders a golden-hour shot of the
// Land Cruiser in the red canyon in front of the sandstone arch, at the
// portrait resolution, then lays the title over it on a 2D canvas.
import * as pc from 'playcanvas';
import type { Game } from './Game';
import type { VehicleLights } from './render/vehicleLights';
import type { VehicleId } from './config';

export const COVER_W = 1200;
export const COVER_H = 1800;

const frame = (app: pc.AppBase) => new Promise<void>((r) => app.once('frameend', () => r()));

export async function renderCover(g: Game, lights: VehicleLights, setVehicle: (id: VehicleId) => void): Promise<string> {
  const app = g.app;
  const dev = app.graphicsDevice;
  const keep = { vehicle: g.vehicleId, t: g.env.t, beam: lights.beam, x: g.vehicle.pos.x, z: g.vehicle.pos.z, yaw: g.vehicle.yaw, mode: g.cam.mode, fov: g.cam.entity.camera!.fov, paused: g.paused, ratio: dev.maxPixelRatio, dirt: 0 };
  // shot: Land Cruiser at golden hour, headlights on
  setVehicle('toyota');
  keep.dirt = g.view.dirt;
  g.view.dirt = 0.35;
  g.env.setTime(0.33, 0);
  lights.beam = 1;
  // in the red canyon, parked in front of the sandstone arch and facing away from it:
  // the camera stands ahead of the car and looks back at it, arch and sky behind
  const road = g.terrain.roads.find((r) => r.def.id === 'canyon')!;
  const p = road.path.at(road.path.length - 37);
  g.teleport(p.x, p.z, Math.atan2(-p.tx, -p.tz) + Math.PI);
  g.inputOverride = (f) => { f.drive = 0; f.steer = 0; f.handbrake = true; };
  g.paused = false;
  // let the suspension settle
  for (let i = 0; i < 40; i++) await frame(app);
  g.cam.mode = 'free';
  const wt = g.view.root.getWorldTransform();
  const cp = new pc.Vec3(), lk = new pc.Vec3();
  wt.transformPoint(new pc.Vec3(-2.4, 0.5, -6.4), cp);
  wt.transformPoint(new pc.Vec3(0.3, 2.3, 0), lk);
  cp.y = Math.max(cp.y, g.terrain.heightAt(cp.x, cp.z) + 0.45);
  g.cam.entity.setPosition(cp);
  g.cam.entity.lookAt(lk);
  g.cam.entity.camera!.fov = 58;
  dev.maxPixelRatio = 1;
  app.setCanvasFillMode(pc.FILLMODE_NONE, COVER_W, COVER_H);
  app.resizeCanvas(COVER_W, COVER_H);
  for (let i = 0; i < 12; i++) await frame(app);
  const shot = await new Promise<string>((r) => app.once('frameend', () => r(g.canvas.toDataURL('image/png'))));
  // restore the live view
  app.setCanvasFillMode(pc.FILLMODE_FILL_WINDOW);
  dev.maxPixelRatio = keep.ratio;
  app.resizeCanvas();
  setVehicle(keep.vehicle);
  g.view.dirt = keep.dirt;
  g.env.setTime(keep.t, 0);
  lights.beam = keep.beam as 0 | 1 | 2;
  g.teleport(keep.x, keep.z, keep.yaw);
  g.inputOverride = null;
  g.cam.mode = keep.mode;
  g.cam.entity.camera!.fov = keep.fov;
  g.paused = keep.paused;
  return compose(shot);
}

function compose(shotUrl: string): Promise<string> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = COVER_W; c.height = COVER_H;
      const x = c.getContext('2d')!;
      x.drawImage(img, 0, 0, COVER_W, COVER_H);
      // legibility gradients
      let g = x.createLinearGradient(0, 0, 0, 760);
      g.addColorStop(0, 'rgba(10,14,12,0.72)');
      g.addColorStop(0.55, 'rgba(10,14,12,0.28)');
      g.addColorStop(1, 'rgba(10,14,12,0)');
      x.fillStyle = g; x.fillRect(0, 0, COVER_W, 760);
      g = x.createLinearGradient(0, COVER_H - 520, 0, COVER_H);
      g.addColorStop(0, 'rgba(10,14,12,0)');
      g.addColorStop(1, 'rgba(10,14,12,0.82)');
      x.fillStyle = g; x.fillRect(0, COVER_H - 520, COVER_W, 520);
      const sans = '"Inter", "HarmonyOS Sans SC", "PingFang SC", "Noto Sans CJK SC", "Noto Sans SC", "Microsoft YaHei", sans-serif';
      x.textAlign = 'center';
      x.fillStyle = 'rgba(246,242,233,0.75)';
      x.font = `600 26px ${sans}`;
      spaced(x, 'AN  OFF-ROAD  JOURNEY  THROUGH  THE  PINES', COVER_W / 2, 150, 4);
      x.shadowColor = 'rgba(0,0,0,0.45)'; x.shadowBlur = 30; x.shadowOffsetY = 6;
      x.fillStyle = '#f6f2e9';
      x.font = `900 168px ${sans}`;
      x.fillText('Forest', COVER_W / 2, 340);
      x.fillText('Trail', COVER_W / 2, 505);
      x.shadowBlur = 16;
      x.fillStyle = '#f2b24c';
      x.font = `700 54px ${sans}`;
      spaced(x, '松溪环线', COVER_W / 2, 600, 36);
      x.shadowBlur = 0; x.shadowOffsetY = 0;
      // accent rule
      x.fillStyle = '#7fd3c4';
      x.fillRect(COVER_W / 2 - 60, 640, 120, 4);
      // bottom lines
      x.fillStyle = '#f6f2e9';
      x.font = `800 46px ${sans}`;
      spaced(x, '驾驶 · 探索 · 记录', COVER_W / 2, COVER_H - 230, 10);
      x.fillStyle = 'rgba(246,242,233,0.72)';
      x.font = `600 26px ${sans}`;
      spaced(x, 'SCOUT  ·  LAND CRUISER 60  ·  KESTREL', COVER_W / 2, COVER_H - 162, 3);
      x.font = `500 22px ${sans}`;
      x.fillStyle = 'rgba(246,242,233,0.5)';
      x.fillText('昼夜切换 · 远近光车灯 · 越野训练场 · 赤岩峡谷', COVER_W / 2, COVER_H - 108);
      resolve(c.toDataURL('image/png'));
    };
    img.src = shotUrl;
  });
}

/** letter-spaced centred text */
function spaced(x: CanvasRenderingContext2D, text: string, cx: number, y: number, gap: number) {
  const chars = [...text];
  const widths = chars.map((ch) => x.measureText(ch).width);
  const total = widths.reduce((a, b) => a + b, 0) + gap * (chars.length - 1);
  let px = cx - total / 2;
  const align = x.textAlign;
  x.textAlign = 'left';
  chars.forEach((ch, i) => { x.fillText(ch, px, y); px += widths[i] + gap; });
  x.textAlign = align;
}
