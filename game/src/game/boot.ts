import * as pc from 'playcanvas';
// Creates the game, wires gameplay systems, screen flow, controls and the
// debug API (window.__ft).
import { Game } from './Game';
import { store, type Screen, type Settings } from './store';
import { Journey } from './journey';
import { Autopilot } from './autopilot';
import { GameAudio } from './audio';
import { Effects } from './render/effects';
import { clearSave, loadSave } from './save';
import { VehicleLights } from './render/vehicleLights';
import { VEHICLES, type VehicleId } from './config';
import { TrailPark } from './park';
import { Director } from './director';
import { renderCover } from './cover';
import { PAINTS } from './render/vehicleView';

export let game: Game | null = null;
export let journey: Journey | null = null;
export let audio: GameAudio | null = null;
export let lights: VehicleLights | null = null;
export let director: Director | null = null;

function setScreen(screen: Screen) {
  const g = game!;
  const prev = store.get().screen;
  if (prev === screen) return;
  g.paused = screen !== 'playing';
  if (screen === 'photo') {
    g.cam.mode = 'photo';
    g.cameraFrame!.dof.enabled = true;
    g.cameraFrame!.dof.focusDistance = g.cam.dist;
    g.cameraFrame!.dof.focusRange = 6;
    g.cameraFrame!.dof.blurRadius = 3;
    g.cameraFrame!.update();
  } else if (prev === 'photo') {
    g.cam.mode = 'follow';
    g.cameraFrame!.dof.enabled = false;
    g.cameraFrame!.update();
  }
  if (screen === 'title') g.cam.mode = 'title';
  else if (prev === 'title') g.cam.mode = 'follow';
  if (screen === 'playing') { g.input.clear(); g.acc = 0; }
  audio?.setPaused(screen !== 'playing' && screen !== 'photo');
  store.set({ screen });
}

export const ui = {
  start() {
    audio?.unlock();
    setScreen('playing');
    audio?.setMusic(store.get().timeOfDay, 3);
    game?.canvas.focus();
  },
  resume() { setScreen('playing'); game?.canvas.focus(); },
  pause() { if (store.get().screen === 'playing') setScreen('paused'); },
  openMap() { setScreen('map'); },
  openPhoto() { setScreen('photo'); },
  closeJournal() { setScreen('playing'); },
  returnToCamp() {
    if (!journey) return;
    journey.lastSafe = 0;
    setScreen('playing');
    journey.requestReset('已回到松溪营地');
  },
  setPaint(key: string) {
    if (!journey || !game) return;
    journey.save.paint = key;
    journey.save.paints = { ...journey.save.paints, [game.vehicleId]: key };
    game.view.setPaint(key);
    store.set({ paint: key, paints: journey.save.paints });
    journey.persist();
  },
  setVehicle(id: VehicleId) {
    const g = game, j = journey;
    if (!g || !j || !VEHICLES[id]) return;
    g.setVehicle(id);
    j.save.vehicle = id;
    const paint = j.save.paints[id] ?? VEHICLES[id].paint;
    j.save.paint = paint;
    g.view.setPaint(paint);
    store.set({ vehicle: id, paint });
    j.persist();
  },
  setTimeOfDay(mode: 'day' | 'night', secs = 0) {
    const g = game, j = journey;
    if (!g) return;
    g.env.setTime(mode === 'night' ? 1 : 0, secs);
    if (j) { j.save.timeOfDay = mode; j.persist(); }
    // headlights come on by themselves after dark, off in daylight
    if (lights) { lights.beam = mode === 'night' ? Math.max(1, lights.beam) as 1 | 2 : 0; store.set({ beam: lights.beam }); }
    store.set({ timeOfDay: mode });
    const scr = store.get().screen;
    if (scr !== 'title' && scr !== 'loading' && !store.get().demo) audio?.setMusic(mode, 4);
  },
  toggleLights() {
    if (!lights) return;
    lights.beam = lights.beam > 0 ? 0 : 1;
    store.set({ beam: lights.beam });
    store.toast(lights.beam ? '大灯已打开（近光）· B 切换远 / 近光' : '大灯已关闭', 'info', 2);
  },
  toggleBeam() {
    if (!lights) return;
    lights.beam = lights.beam === 2 ? 1 : 2;
    store.set({ beam: lights.beam });
    store.toast(lights.beam === 2 ? '远光：照得更远，适合开阔路段' : '近光：光斑压低，林间和会车时使用', 'info', 2);
  },
  setSettings(patch: Partial<Settings>) {
    const s = { ...store.get().settings, ...patch };
    store.set({ settings: s });
    if (patch.quality && game) game.applyQuality(patch.quality);
    if (game) { game.cam.shakeEnabled = s.shake; game.vehicle.fineThrottle = s.fineThrottle; }
    audio?.setVolumes(s.master, s.effects, s.music);
    journey?.persist();
  },
  resetProgress() {
    clearSave();
    location.reload();
  },
  /** scripted ~2 min showcase; with record = true the canvas and game audio are recorded to a WebM download */
  startDemo(record: boolean) {
    if (!director || director.active) return;
    director.start(record);
  },
  stopDemo() { director?.stop(); },
  /** 1200 x 1800 cover image; downloads a PNG and resolves to its data URL */
  async makeCover(download = true): Promise<string | null> {
    const g = game;
    if (!g || !lights) return null;
    store.toast('正在渲染封面…', 'info', 2);
    const url = await renderCover(g, lights, (id) => ui.setVehicle(id));
    if (download) {
      const a = document.createElement('a');
      a.download = 'forest-trail-cover.png';
      a.href = url;
      a.click();
    }
    store.toast('封面已生成（1200 × 1800 PNG）', 'good', 4);
    return url;
  },
  savePhoto() {
    const g = game;
    if (!g) return;
    g.app.once('frameend', () => {
      const a = document.createElement('a');
      a.download = `forest-trail-${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
      a.href = g.canvas.toDataURL('image/png');
      a.click();
    });
  },
};

function onKey(code: string) {
  const g = game!, j = journey!;
  const scr = store.get().screen;
  if (scr === 'loading') return;
  if (store.get().demo) {
    if (code === 'Escape') ui.stopDemo();
    return;
  }
  if (scr === 'title') {
    if (code === 'Enter' || code === 'Space') ui.start();
    return;
  }
  if (code === 'Escape') {
    if (scr === 'playing') {
      if (j.winch.mode === 'select') { j.winch.mode = 'off'; return; }
      setScreen('paused');
    } else if (scr === 'journal') ui.closeJournal();
    else setScreen('playing');
    return;
  }
  if (code === 'KeyM') { setScreen(scr === 'map' ? 'playing' : scr === 'playing' ? 'map' : scr); return; }
  if (code === 'KeyP') { setScreen(scr === 'photo' ? 'playing' : scr === 'playing' || scr === 'paused' ? 'photo' : scr); return; }
  if (scr !== 'playing' || j.shot) return;
  if (code === 'KeyQ') {
    g.vehicle.gear = g.vehicle.gear === 'high' ? 'low' : 'high';
    store.toast(g.vehicle.gear === 'low' ? '低档：扭矩大、速度慢，适合爬坡和下坡控速' : '高档：常规行驶', 'info', 2.5);
  } else if (code === 'KeyC') g.cam.recenter();
  else if (code === 'KeyL') ui.toggleLights();
  else if (code === 'KeyB') ui.toggleBeam();
  else if (code === 'KeyN') ui.setTimeOfDay(store.get().timeOfDay === 'day' ? 'night' : 'day', 8);
  else if (code === 'KeyE') {
    const msg = j.winch.toggle();
    if (msg) store.toast(msg, j.winch.mode === 'off' && msg.includes('断开') ? 'info' : 'warn', 3);
    g.cam.winchView = j.winch.mode === 'select';
  } else if (code === 'KeyF' || code === 'Enter') {
    if (j.winch.mode === 'select') {
      const msg = j.winch.connect();
      if (msg) store.toast(msg, (j.winch.mode as string) === 'attached' ? 'good' : 'warn', 4);
      g.cam.winchView = false;
    } else if (j.winch.mode !== 'attached') j.interact();
  }
}

export async function startGame(canvas: HTMLCanvasElement) {
  const g = new Game(canvas);
  game = g;
  try {
    const saved = loadSave().data;
    const requested = new URLSearchParams(location.search).get('vehicle');
    const vehicle = requested && Object.hasOwn(VEHICLES, requested) ? requested as VehicleId : saved.vehicle;
    await g.init((p, text) => store.set({ loading: p, loadingText: text }), vehicle);
  } catch (e) {
    console.error(e);
    store.set({ loadingText: `启动失败：${(e as Error).message}` });
    return;
  }
  const j = new Journey(g);
  journey = j;
  audio = new GameAudio(g);
  const fx = new Effects(g);
  const park = new TrailPark(g, j);

  const vl = new VehicleLights(g.app);
  lights = vl;
  vl.attach(g.view);
  g.onVehicleChanged.push(() => vl.attach(g.view));
  director = new Director(g, audio, vl, {
    setVehicle: (id) => ui.setVehicle(id),
    setTime: (m, secs) => ui.setTimeOfDay(m, secs),
  });
  g.hooks.frame.push((dt) => director?.update(dt));
  {
    const sv = j.save;
    sv.vehicle = g.vehicleId;
    const paint = sv.paints[g.vehicleId] ?? (VEHICLES[g.vehicleId].paints.includes(sv.paint) ? sv.paint : VEHICLES[g.vehicleId].paint);
    sv.paint = paint;
    g.view.setPaint(paint);
    store.set({ vehicle: g.vehicleId, paint, paints: sv.paints });
    ui.setTimeOfDay(sv.timeOfDay ?? 'day');
  }
  const s0 = store.get().settings;
  g.applyQuality(s0.quality);
  g.cam.shakeEnabled = s0.shake;
  g.vehicle.fineThrottle = s0.fineThrottle;
  audio.setVolumes(s0.master, s0.effects, s0.music);
  g.input.onKey.push(onKey);
  // the first click or key on the title screen unlocks audio and starts the title theme
  const firstGesture = () => {
    audio?.unlock();
    if (store.get().screen === 'title') audio?.setMusic('title', 2);
    window.removeEventListener('pointerdown', firstGesture);
    window.removeEventListener('keydown', firstGesture);
  };
  window.addEventListener('pointerdown', firstGesture);
  window.addEventListener('keydown', firstGesture);
  store.subscribe(() => {
    const st = store.get();
    document.body.dataset.screen = st.cinematic ? 'cinematic' : st.screen;
  });

  g.hooks.step.push((dt) => j.winch.step(dt, j.reel));
  let hudT = 0;
  const holds = { reel: false, reset: false };
  g.hooks.frame.push((dt, inp) => {
    const input = g.input;
    const pad = input.gamepad();
    // gamepad buttons
    if (pad) {
      if (input.padPressed(9)) onKey('Escape');
      if (input.padPressed(8)) onKey('KeyM');
      if (input.padPressed(2)) onKey('KeyQ');
      if (input.padPressed(3)) onKey('KeyE');
      if (input.padPressed(0)) onKey('KeyF');
      if (input.padPressed(11)) onKey('KeyC');
      if (input.padPressed(12)) onKey('KeyL');
      if (input.padPressed(15)) onKey('KeyB');
    }
    if (store.get().screen === 'playing' && j.winch.mode === 'select' && input.takeClick()) onKey('KeyF');
    input.takeClick();
    const resetKey = holds.reset || input.down('KeyR') || !!(pad && pad.buttons[4]?.pressed && pad.buttons[5]?.pressed);
    const reelKey = holds.reel || input.down('KeyF') || input.lmb || !!pad?.buttons[0]?.pressed;
    j.update(dt, resetKey && store.get().screen === 'playing', reelKey && j.winch.mode === 'attached');
    fx.update(dt);
    if (j.resetPhase !== 'none') park.cancel('车辆复位，本次计时取消');
    if (store.get().screen === 'playing' && !store.get().demo) park.update(dt);
    audio!.update(dt, inp);
    // lamps and mud
    {
      const v = g.vehicle;
      const reversing = v.dir < 0 && (v.throttle > 0.02 || v.forwardSpeed < -0.3);
      const braking = Math.max(v.brake, v.handbrake ? 0.4 : 0);
      g.view.setLamps({ beam: vl.beam, brake: braking, reverse: reversing, night: g.env.night });
      vl.update(v, g.view, g.cam.entity, g.env.night, braking, reversing);
      let dd = 0;
      for (const w of v.wheels) {
        if (!w.grounded) continue;
        const sp = Math.abs(w.omega * v.spec.wheelRadius);
        dd += (w.mud * 0.012 + (w.surface === 'dirt' || w.surface === 'gravel' ? 0.0006 : 0)) * Math.min(sp, 8) * (w.spinning ? 2.2 : 1);
        if (w.water > 0.15) dd -= 0.02 * w.water * (0.3 + Math.min(Math.abs(v.forwardSpeed), 4) * 0.3);
      }
      g.view.dirt = Math.max(0, Math.min(1, g.view.dirt + dd * dt));
    }
    hudT += dt;
    if (hudT > 1 / 20) {
      hudT = 0;
      const v = g.vehicle;
      const counts: Record<string, number> = {};
      for (const w of v.wheels) if (w.grounded) counts[w.surface] = (counts[w.surface] ?? 0) + 1;
      const surface = (Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'dirt') as typeof store.state.surface;
      const f = g.cam.entity.forward;
      store.set({
        speedKmh: v.forwardSpeed * 3.6,
        gear: v.gear,
        reverse: v.dir < 0,
        heading: Math.atan2(f.x, -f.z),
        surface,
        water: g.terrain.waterDepthAt(v.pos.x, v.pos.z),
        dirt: g.view.dirt,
        lowRange: v.gear === 'low',
        debug: debugOn ? telemetry() : null,
      });
    }
  });

  let debugOn = new URLSearchParams(location.search).has('debug');
  const telemetry = () => {
    const v = g.vehicle;
    return [
      `v ${(v.forwardSpeed * 3.6).toFixed(1)} km/h thr ${v.throttle.toFixed(2)} brk ${v.brake.toFixed(2)} dir ${v.dir} gear ${v.gear}`,
      `steer ${((v.steerAngle * 180) / Math.PI).toFixed(1)}° grounded ${v.groundedCount} up ${v.uprightness.toFixed(3)}`,
      `len ${v.wheels.map((w) => w.length.toFixed(2)).join(' ')}`,
      `load ${v.wheels.map((w) => (w.load / 1000).toFixed(1)).join(' ')} kN`,
      `surf ${v.wheels.map((w) => w.surface).join(' ')} spin ${v.wheels.map((w) => (w.spinning ? 'S' : w.sliding ? 's' : '-')).join('')}`,
      `water ${g.terrain.waterDepthAt(v.pos.x, v.pos.z).toFixed(2)} pos ${v.pos.x.toFixed(1)} ${v.pos.y.toFixed(1)} ${v.pos.z.toFixed(1)}`,
      `safe ${j.lastSafe} stuck ${j.stuckTime.toFixed(1)} winch ${j.winch.mode} ${(j.winch.tension / 1000).toFixed(1)} kN`,
      `draws ${g.app.stats.drawCalls.total} tris ${(g.app.stats.frame.triangles / 1e6).toFixed(2)}M`,
    ].join('\n');
  };

  // ---- debug / test API
  const loop = g.terrain.roads.find((r) => r.def.id === 'loop')!;
  let ap: Autopilot | null = null;
  const api = {
    game: g, journey: j, store, ui, audio,
    audioState: () => audio?.ctx?.state ?? 'locked',
    debug(on = true) { debugOn = on; },
    teleport: (x: number, z: number, yaw = 0) => g.teleport(x, z, yaw),
    teleportRoad: (id: string, s: number, rev = false) => g.teleportRoad(id, s, rev),
    roadS: (id: string, x: number, z: number) => g.terrain.roads.find((r) => r.def.id === id)?.path.nearest(x, z).s,
    drive(drive: number, steer = 0, handbrake = false) {
      g.inputOverride = (f) => { f.drive = drive; f.steer = steer; f.handbrake = handbrake; f.digital = true; };
    },
    release() { g.inputOverride = null; ap = null; },
    autopilot(kmh = 20, roadId = 'loop') {
      const road = g.terrain.roads.find((r) => r.def.id === roadId) ?? loop;
      ap = new Autopilot(road.path, !!road.def.closed);
      ap.targetKmh = kmh;
      ap.reset(g.vehicle.pos.x, g.vehicle.pos.z);
      g.inputOverride = (f) => { ap?.update(g.vehicle, f); };
      return ap;
    },
    key: (code: string) => onKey(code),
    lights: () => vl,
    park: () => park,
    director: () => director,
    cover: () => ui.makeCover(false),
    /** park the camera at a fixed pose (free mode); call with no args to return to follow */
    camAt(p?: [number, number, number], t?: [number, number, number], fov = 55) {
      if (!p || !t) { g.cam.mode = 'follow'; g.cam.entity.camera!.fov = 55; return; }
      g.cam.mode = 'free';
      g.cam.entity.setPosition(p[0], p[1], p[2]);
      g.cam.entity.lookAt(t[0], t[1], t[2]);
      g.cam.entity.camera!.fov = fov;
    },
    /** camera relative to the vehicle: offset in body space (x right, y up, z back) looking at a body-space point */
    camRel(off: [number, number, number], look: [number, number, number] = [0, 0.8, 0], fov = 45) {
      const wt = g.view.root.getWorldTransform();
      const a = new pc.Vec3(), b = new pc.Vec3();
      wt.transformPoint(new pc.Vec3(off[0], off[1], off[2]), a);
      wt.transformPoint(new pc.Vec3(look[0], look[1], look[2]), b);
      api.camAt([a.x, a.y, a.z], [b.x, b.y, b.z], fov);
    },
    setVehicle: (id: VehicleId) => ui.setVehicle(id),
    setTime: (t: number, secs = 0) => g.env.setTime(t, secs),
    paints: () => Object.keys(PAINTS),
    hold(which: 'reel' | 'reset', on: boolean) { holds[which] = on; },
    state: () => ({ ...store.get(), photos: Object.keys(store.get().photos) }),
    telemetry,
    stats: () => ({ fps: store.get().fps, draws: g.app.stats.drawCalls.total, tris: g.app.stats.frame.triangles, frameMs: g.app.stats.frame.ms }),
  };
  (window as unknown as { __ft: unknown }).__ft = api;
  const skipTitle = new URLSearchParams(location.search).has('play');
  setScreen(skipTitle ? 'playing' : 'title');
  if (skipTitle) store.set({ screen: 'playing' });
}
