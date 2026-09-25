// Demo director: a ~126 s scripted showcase (vehicles, detail close-ups, trail
// park moguls, mud, ford, canyon bridge, autumn woods and wildlife, day to
// night, headlights, camp) with smooth camera rigs and captions. It can record
// the canvas plus the game mix with MediaRecorder and download a WebM.
import * as pc from 'playcanvas';
import type { Game } from './Game';
import type { GameAudio } from './audio';
import type { VehicleLights } from './render/vehicleLights';
import { Autopilot } from './autopilot';
import { store } from './store';
import type { VehicleId } from './config';

type V3 = [number, number, number];

interface Ctx { g: Game; lights: VehicleLights; ap: Autopilot | null }

interface Shot {
  dur: number;
  caption?: [string, string?];
  /** caption appears after this many seconds (default 0.6) */
  capAt?: number;
  setup?: (c: Ctx) => void;
  /** camera pose for normalised shot time u (0..1) and seconds t */
  cam: (c: Ctx, u: number, t: number) => { pos: V3; look: V3; fov?: number };
  /** fade from black at the start / to black at the end (seconds) */
  fadeIn?: number;
  fadeOut?: number;
  /** follow rigs are smoothed; world splines are not */
  smooth?: number;
}

const ease = (u: number) => u * u * (3 - 2 * u);
const lerp3 = (a: V3, b: V3, t: number): V3 => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];

/** Catmull-Rom through world points */
function spline(pts: V3[], u: number): V3 {
  const n = pts.length - 1;
  const x = Math.min(n - 1e-6, Math.max(0, u * n));
  const i = Math.floor(x), t = x - i;
  const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(n, i + 2)];
  const out: V3 = [0, 0, 0];
  for (let k = 0; k < 3; k++) {
    out[k] = 0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t * t + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t * t * t);
  }
  return out;
}

export class Director {
  active = false;
  recording = false;
  private shots: Shot[] = [];
  private idx = -1;
  private t = 0;
  private total = 0;
  private elapsed = 0;
  private ctx: Ctx;
  private camPos = new pc.Vec3();
  private camLook = new pc.Vec3();
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  /** the recording is a 2D composite: WebGL frame + letterbox, captions and fades
   * (the DOM overlays are not part of canvas.captureStream) */
  private comp: HTMLCanvasElement | null = null;
  private compCtx: CanvasRenderingContext2D | null = null;
  private capKey = '';
  private capT0 = 0;
  private restore: { vehicle: VehicleId; tod: 'day' | 'night'; beam: number; x: number; z: number; yaw: number; screen: string } | null = null;
  onDone: ((blob: Blob | null) => void) | null = null;
  lastBlob: Blob | null = null;
  private tmp = new pc.Vec3();
  private tmp2 = new pc.Vec3();

  constructor(private g: Game, private audio: GameAudio | null, lights: VehicleLights, private hooks: { setVehicle: (id: VehicleId) => void; setTime: (m: 'day' | 'night', secs: number) => void }) {
    this.ctx = { g, lights, ap: null };
    this.shots = this.buildShots();
    this.total = this.shots.reduce((a, s) => a + s.dur, 0);
  }

  get duration() { return this.total; }

  // ---------------------------------------------------------------- helpers
  private H(x: number, z: number) { return this.g.terrain.heightAt(x, z); }
  private road(id: string) { return this.g.terrain.roads.find((r) => r.def.id === id)!; }
  /** put the car on a road at the point nearest (x, z) and start the autopilot */
  private drive(id: string, x: number, z: number, kmh: number, offset = 0) {
    const r = this.road(id);
    const s = (r.path.nearest(x, z).s + offset + r.path.length) % r.path.length;
    this.g.teleportRoad(id, s);
    const ap = new Autopilot(r.path, !!r.def.closed);
    ap.targetKmh = kmh;
    ap.autoGear = true;
    ap.limit = (q) => this.g.terrain.featureLimit(id, q);
    ap.grade = (q) => {
      const a = r.path.at(Math.max(0, Math.min(r.path.length, q))), b = r.path.at(Math.max(0, Math.min(r.path.length, q + 4)));
      return (Math.atan2(this.H(b.x, b.z) - this.H(a.x, a.z), 4) * 180) / Math.PI;
    };
    ap.reset(this.g.vehicle.pos.x, this.g.vehicle.pos.z);
    this.ctx.ap = ap;
    this.g.inputOverride = (f) => { this.ctx.ap?.update(this.g.vehicle, f); };
  }
  private park(x: number, z: number, yaw: number) {
    this.g.teleport(x, z, yaw);
    this.ctx.ap = null;
    this.g.inputOverride = (f) => { f.drive = 0; f.steer = 0; f.handbrake = true; f.digital = true; };
  }
  /** point in the car's body space (x right, y up, z back) to world */
  private rel(off: V3): V3 {
    const wt = this.g.view.root.getWorldTransform();
    wt.transformPoint(this.tmp.set(off[0], off[1], off[2]), this.tmp2);
    return [this.tmp2.x, this.tmp2.y, this.tmp2.z];
  }
  /** vehicle-relative camera blending between two offsets over the shot */
  private follow(a: V3, b: V3, lookA: V3 = [0, 0.9, 0], lookB = lookA, fov = 50) {
    return (_c: Ctx, u: number) => {
      const e = ease(u);
      const pos = this.rel(lerp3(a, b, e));
      const gy = this.H(pos[0], pos[2]) + 0.5;
      if (pos[1] < gy) pos[1] = gy;
      return { pos, look: this.rel(lerp3(lookA, lookB, e)), fov };
    };
  }
  private orbit(radius: number, height: number, a0: number, a1: number, look: V3 = [0, 0.8, 0], fov = 40) {
    return (_c: Ctx, u: number) => {
      const a = a0 + (a1 - a0) * ease(u);
      const pos = this.rel([Math.sin(a) * radius, height, Math.cos(a) * radius]);
      const gy = this.H(pos[0], pos[2]) + 0.4;
      if (pos[1] < gy) pos[1] = gy;
      return { pos, look: this.rel(look), fov };
    };
  }
  /** fixed world camera that pans to keep the car framed */
  private tracker(pos: V3, lookOff: V3 = [0, 0.8, 0], fov = 45) {
    return () => ({ pos, look: this.rel(lookOff), fov });
  }
  /** moving world camera that keeps the car framed */
  private pathOnCar(pts: V3[], lookOff: V3 = [0, 0.8, 0], fov = 50) {
    return (_c: Ctx, u: number) => ({ pos: spline(pts, ease(u)), look: this.rel(lookOff), fov });
  }
  private path(pts: V3[], looks: V3[], fov = 55) {
    return (_c: Ctx, u: number) => ({ pos: spline(pts, ease(u)), look: spline(looks, ease(u)), fov });
  }
  private caption(title: string | null, sub?: string) {
    const d = store.get().demo;
    if (!d) return;
    store.set({ demo: { ...d, caption: title, sub: sub ?? null } });
  }

  // ---------------------------------------------------------------- shot list
  private buildShots(): Shot[] {
    const H = (x: number, z: number) => this.H(x, z);
    const setup = (fn: (c: Ctx) => void) => fn;
    return [
      // 0 · opening: over the lake valley towards the northern range
      {
        dur: 8, fadeIn: 1.2, caption: ['#Forest Trail', '松 溪 环 线'], capAt: 1.2,
        setup: setup((c) => { this.hooks.setTime('day', 0); c.lights.beam = 0; this.hooks.setVehicle('scout'); this.park(-40, 190, Math.PI); }),
        cam: this.path([[-60, 34, 215], [-40, 30, 175], [-15, 26, 130]], [[-20, 8, 110], [-10, 14, 60], [0, 30, -200]], 55),
      },
      // 1 · Scout on the forest road
      {
        dur: 9, caption: ['Scout 短轴四驱', '老松工坊 · 灵活均衡的第一台车'],
        setup: setup((c) => { this.hooks.setVehicle('scout'); c.lights.beam = 0; this.drive('loop', -199, 70, 20); }),
        cam: this.follow([-6, 1.3, -1], [-4, 2.4, 7.5], [0, 0.9, 0], [0, 1, -4], 48), smooth: 6,
      },
      // 2 · Scout details, slow orbit
      {
        dur: 8, caption: ['细节', '圆灯铬圈 · 绞盘与 D 形环 · 脱困板与车顶行李 · 灯排'],
        setup: setup((c) => { c.lights.beam = 0; this.park(-176, 150, 0.6); }),
        cam: this.orbit(5.4, 1.1, 2.3, 4.0, [0, 0.85, -0.6], 36), smooth: 10,
      },
      // 3 · under the car: solid axles articulating on the moguls
      {
        dur: 9, fadeIn: 0.5, caption: ['越野训练场 · 交叉轴', '整体桥随地形扭转，对角车轮悬空'],
        setup: setup(() => { this.hooks.setVehicle('toyota'); this.drive('park', -72, 232, 6, -2); }),
        cam: this.follow([3.6, 0.55, -2.2], [3.4, 0.7, 2.4], [0, 0.35, 0], [0, 0.4, -1], 52), smooth: 8,
      },
      // 4 · crater field
      {
        dur: 7, caption: ['炮弹坑群', '低档慢行，悬挂吃下每一个坑'],
        setup: setup(() => { this.drive('park', -146, 211, 8, 2); }),
        cam: this.tracker([-118, H(-118, 222) + 2.3, 222], [0, 0.6, 0], 42),
      },
      // 5 · TOYOTA hero
      {
        dur: 9, caption: ['TOYOTA Land Cruiser 60', '圆灯 · 格栅字标 · 钢保险杠绞盘与雾灯 · 通气管'],
        setup: setup((c) => { c.lights.beam = 1; this.park(-30, 178, -Math.PI / 2); }),
        cam: this.follow([-2.8, 0.7, -5.8], [2.0, 0.9, -5.4], [0, 0.85, -0.6], [0, 0.95, -0.3], 34), smooth: 10,
      },
      // 6 · Kestrel in the mud
      {
        dur: 8, fadeIn: 0.5, caption: ['Kestrel 小皮卡 · 泥地', '驱动超出抓地会打滑，松一点油门反而爬得上去'],
        setup: setup((c) => { c.lights.beam = 0; this.hooks.setVehicle('ranger'); this.drive('loop', 46, -10, 16); }),
        cam: this.follow([4.2, 0.8, -3], [4.6, 1.2, 3.5], [0, 0.6, -1], [0, 0.7, -3], 46), smooth: 6,
      },
      // 7 · creek ford
      {
        dur: 7, caption: ['浅溪涉水', '水花、湿泥与车身上的泥点'],
        setup: setup(() => { this.drive('loop', -33, -27, 10); }),
        cam: this.follow([3.8, 0.55, -4.5], [4.4, 0.8, 2.5], [0, 0.5, -1], [0, 0.6, -2], 46), smooth: 7,
      },
      // 8 · canyon bridge from the gully floor
      {
        dur: 10, fadeIn: 0.6, caption: ['赤岩峡谷 · 木板吊桥', '层叠砂岩与干沟，桥面随车轻微下沉'],
        setup: setup(() => {
          this.hooks.setVehicle('toyota');
          const b = this.g.terrain.bridge!;
          this.drive('canyon', b.x - b.tx * 15, b.z - b.tz * 15, 8);
        }),
        cam: (c, u) => {
          const b = this.g.terrain.bridge!;
          // from the gully floor beside the trestles up to the far abutment, looking back at the car
          const side: V3 = [b.x - b.tz * 9, b.y - 4.2, b.z + b.tx * 9];
          const high: V3 = [b.x + b.tx * 17 - b.tz * 3.5, b.y + 2.8, b.z + b.tz * 17 + b.tx * 3.5];
          const pos = lerp3(side, high, ease(u));
          pos[1] = Math.max(pos[1], this.H(pos[0], pos[2]) + 0.6);
          return { pos, look: this.rel([0, 0.8, 0]), fov: 52 };
        },
        smooth: 4,
      },
      // 9 · autumn woods, A-frame and deer
      {
        dur: 9, caption: ['秋色林', '红枫、白桦、落叶松，鹿群被引擎声惊起'],
        setup: setup((c) => { this.g.env.setTime(0.3, 0); c.lights.beam = 0; this.hooks.setVehicle('scout'); this.drive('loop', 204, 40, 18); }),
        cam: this.pathOnCar([[221, H(221, 28) + 6, 28], [218, H(218, 60) + 6.5, 60], [211, H(211, 92) + 7, 92]], [0, 0.8, 0], 50),
      },
      // 10 · day to night over the lake
      {
        dur: 14, caption: ['昼夜交替', '夕阳、蓝调时刻，然后是星空与月光'], capAt: 1,
        setup: setup((c) => { c.lights.beam = 0; this.park(-90, 183, -Math.PI / 2); this.g.env.setTime(0.3, 0); this.g.env.setTime(1, 12.5); }),
        cam: this.path([[-70, 12, 172], [-45, 14, 160], [-20, 16, 150]], [[-40, 12, 100], [-10, 22, 60], [20, 40, -60]], 58),
      },
      // 11 · night drive: low beam, then high beam
      {
        dur: 12, caption: ['车灯 · 近光与远光', '近光截止线压低光斑，远光和灯排照亮林间'],
        setup: setup((c) => { this.hooks.setTime('night', 0); c.lights.beam = 1; this.hooks.setVehicle('scout'); this.drive('loop', -199, 70, 18); }),
        cam: (c, u, t) => {
          if (t > 5.5) c.lights.beam = 2;
          return this.follow([-2.4, 1.3, -9], [2.6, 1.7, -8], [0, 0.8, 0], [0, 0.9, 1], 46)(c, u);
        },
        smooth: 6,
      },
      // 12 · camp at night
      {
        dur: 9, caption: ['松溪营地', '串灯、篝火和露营拖车'],
        setup: setup((c) => { c.lights.beam = 1; this.park(-172, 166, 2.5); }),
        cam: this.path([[-160, H(-160, 196) + 3.2, 196], [-170, H(-170, 192) + 2.6, 190]], [[-192, 6, 176], [-190, 5, 180]], 52),
      },
      // 13 · ending card over the night sky
      {
        dur: 7, fadeOut: 2, caption: ['#Forest Trail', '驾 驶 · 探 索 · 记 录'], capAt: 0.8,
        setup: setup((c) => { c.lights.beam = 1; }),
        cam: this.path([[-180, 14, 200], [-176, 22, 206]], [[-150, 30, 120], [-130, 50, 60]], 55),
      },
    ];
  }

  // ---------------------------------------------------------------- run
  start(record: boolean) {
    if (this.active) return;
    const g = this.g;
    const v = g.vehicle;
    this.restore = { vehicle: g.vehicleId, tod: store.get().timeOfDay, beam: this.ctx.lights.beam, x: v.pos.x, z: v.pos.z, yaw: v.yaw, screen: store.get().screen };
    this.active = true;
    this.recording = record;
    this.idx = -1;
    this.t = 0;
    this.elapsed = 0;
    g.cam.mode = 'free';
    g.paused = false;
    store.set({ demo: { active: true, recording: record, caption: null, sub: null, progress: 0 }, screen: 'playing', fade: 1 });
    this.audio?.unlock();
    this.audio?.setMusic('demo', 0.5, true);
    this.chunks = [];
    this.lastBlob = null;
    if (record) this.startRecorder();
    this.next();
  }

  private startRecorder() {
    const gl = this.g.canvas;
    const comp = document.createElement('canvas') as HTMLCanvasElement & { captureStream(fps?: number): MediaStream };
    comp.width = gl.width;
    comp.height = gl.height;
    this.comp = comp;
    this.compCtx = comp.getContext('2d');
    this.g.app.on('frameend', this.drawComposite);
    const video = comp.captureStream(60);
    const tracks = [...video.getVideoTracks()];
    const a = this.audio?.captureStream();
    if (a) tracks.push(...a.getAudioTracks());
    const stream = new MediaStream(tracks);
    const types = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];
    const mimeType = types.find((t) => MediaRecorder.isTypeSupported(t)) ?? '';
    try {
      this.recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 10_000_000, audioBitsPerSecond: 160_000 });
    } catch (e) {
      console.warn('MediaRecorder unavailable', e);
      this.recorder = null;
      this.recording = false;
      return;
    }
    this.recorder.ondataavailable = (e) => { if (e.data.size) this.chunks.push(e.data); };
    this.recorder.start(1000);
  }

  /** runs right after the engine rendered a frame, while the WebGL back buffer is valid */
  private drawComposite = () => {
    const c = this.comp, x = this.compCtx;
    if (!c || !x) return;
    const gl = this.g.canvas;
    if (c.width !== gl.width || c.height !== gl.height) { c.width = gl.width; c.height = gl.height; }
    const W = c.width, H = c.height, k = H / 1080;
    x.globalAlpha = 1;
    x.drawImage(gl, 0, 0, W, H);
    // letterbox
    const bar = Math.round(H * 0.075);
    x.fillStyle = '#000';
    x.fillRect(0, 0, W, bar);
    x.fillRect(0, H - bar, W, bar);
    // captions
    const d = store.get().demo;
    const cap = d?.caption ?? null;
    const key = `${cap}|${d?.sub ?? ''}`;
    if (key !== this.capKey) { this.capKey = key; this.capT0 = performance.now(); }
    if (cap) {
      const a = Math.min(1, (performance.now() - this.capT0) / 900);
      const e = 1 - Math.pow(1 - a, 3);
      const sans = '"Inter", "HarmonyOS Sans SC", "PingFang SC", "Noto Sans CJK SC", "Noto Sans SC", "Microsoft YaHei", sans-serif';
      x.save();
      x.globalAlpha = e;
      x.shadowColor = 'rgba(0,0,0,0.5)';
      x.shadowBlur = 24 * k;
      x.shadowOffsetY = 4 * k;
      x.fillStyle = '#f6f2e9';
      if (cap.startsWith('#')) {
        x.textAlign = 'center';
        x.font = `900 ${Math.round(96 * k)}px ${sans}`;
        x.fillText(cap.slice(1), W / 2, H / 2 + (1 - e) * 16 * k);
        if (d?.sub) {
          x.fillStyle = '#f2b24c';
          x.font = `700 ${Math.round(24 * k)}px ${sans}`;
          x.fillText(d.sub, W / 2, H / 2 + 52 * k);
        }
      } else {
        x.textAlign = 'left';
        const left = W * 0.06, base = H - H * 0.13 - 30 * k + (1 - e) * 16 * k;
        x.font = `850 ${Math.round(46 * k)}px ${sans}`;
        x.fillText(cap, left, base);
        if (d?.sub) {
          x.shadowBlur = 12 * k;
          x.fillStyle = 'rgba(246,242,233,0.78)';
          x.font = `500 ${Math.round(21 * k)}px ${sans}`;
          x.fillText(d.sub, left, base + 40 * k);
        }
      }
      x.restore();
    }
    // fade to / from black
    const f = store.get().fade;
    if (f > 0.001) {
      x.globalAlpha = f;
      x.fillStyle = '#0a0f0d';
      x.fillRect(0, 0, W, H);
      x.globalAlpha = 1;
    }
  };

  private next() {
    this.idx++;
    if (this.idx >= this.shots.length) { this.finish(); return; }
    const s = this.shots[this.idx];
    this.t = 0;
    this.caption(null);
    s.setup?.(this.ctx);
    const pose = s.cam(this.ctx, 0, 0);
    this.camPos.set(pose.pos[0], pose.pos[1], pose.pos[2]);
    this.camLook.set(pose.look[0], pose.look[1], pose.look[2]);
  }

  update(dt: number) {
    if (!this.active) return;
    const s = this.shots[this.idx];
    if (!s) return;
    this.t += dt;
    this.elapsed += dt;
    const u = Math.min(1, this.t / s.dur);
    const pose = s.cam(this.ctx, u, this.t);
    const k = s.smooth ? 1 - Math.exp(-s.smooth * dt) : 1;
    this.camPos.lerp(this.camPos, this.tmp.set(pose.pos[0], pose.pos[1], pose.pos[2]), k);
    this.camLook.lerp(this.camLook, this.tmp.set(pose.look[0], pose.look[1], pose.look[2]), s.smooth ? 1 - Math.exp(-s.smooth * 1.5 * dt) : 1);
    const cam = this.g.cam.entity;
    cam.setPosition(this.camPos);
    cam.lookAt(this.camLook);
    cam.camera!.fov = pose.fov ?? 50;
    // fades and captions
    let fade = 0;
    if (s.fadeIn) fade = Math.max(fade, 1 - this.t / s.fadeIn);
    if (s.fadeOut) fade = Math.max(fade, 1 - (s.dur - this.t) / s.fadeOut);
    // short dip between shots that swap cars
    const nextShot = this.shots[this.idx + 1];
    if (nextShot?.fadeIn) fade = Math.max(fade, 1 - (s.dur - this.t) / 0.4);
    const d = store.get().demo!;
    const capOn = s.caption && this.t > (s.capAt ?? 0.6) && this.t < s.dur - 0.5;
    const want = capOn ? s.caption![0] : null;
    store.set({
      fade: Math.max(0, Math.min(1, fade)),
      demo: { ...d, caption: want, sub: capOn ? s.caption![1] ?? null : null, progress: Math.min(1, this.elapsed / this.total) },
    });
    if (this.t >= s.dur) this.next();
  }

  stop() {
    if (!this.active) return;
    this.finish(true);
  }

  private finish(aborted = false) {
    this.active = false;
    const g = this.g;
    g.inputOverride = null;
    this.ctx.ap = null;
    g.cam.entity.camera!.fov = 55;
    const r = this.restore;
    const done = (blob: Blob | null) => {
      if (r) {
        this.hooks.setVehicle(r.vehicle);
        this.hooks.setTime(r.tod, 0);
        this.ctx.lights.beam = r.beam as 0 | 1 | 2;
        g.teleport(r.x, r.z, r.yaw);
      }
      g.cam.mode = r?.screen === 'title' ? 'title' : 'follow';
      store.set({ demo: null, fade: 0, screen: (r?.screen as 'title' | 'playing') ?? 'title' });
      g.paused = store.get().screen !== 'playing';
      this.audio?.setMusic(store.get().screen === 'title' ? 'title' : store.get().timeOfDay, 2);
      this.onDone?.(blob);
    };
    if (this.comp) {
      g.app.off('frameend', this.drawComposite);
    }
    if (this.recorder && this.recorder.state !== 'inactive') {
      const rec = this.recorder;
      rec.onstop = () => {
        this.comp = null;
        this.compCtx = null;
        const blob = new Blob(this.chunks, { type: rec.mimeType || 'video/webm' });
        this.lastBlob = blob;
        if (!aborted || blob.size > 0) {
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = `forest-trail-demo-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.webm`;
          document.body.appendChild(a);
          a.click();
          setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
        }
        store.toast(`演示视频已导出（${(blob.size / 1e6).toFixed(1)} MB，WebM）`, 'good', 6);
        done(blob);
      };
      rec.stop();
      this.recorder = null;
    } else {
      done(null);
    }
  }
}
