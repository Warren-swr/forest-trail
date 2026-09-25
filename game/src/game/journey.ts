// Journey rules: safe points and reset, stuck/flip/deep-water help, landmark
// records with a cinematic shot, the optional toolbox + tyre upgrade,
// completion, onboarding hints and saving.
import * as pc from 'playcanvas';
import type { Game } from './Game';
import { GAME } from './config';
import { LANDMARKS, TOOLBOX, type LandmarkDef } from './world/layout';
import { store } from './store';
import { loadSave, storageAvailable, writeSave, type SaveData } from './save';
import { Winch } from './physics/winch';
import { RopeView } from './render/rope';

interface SafePoint { x: number; z: number; yaw: number; road: string }

const GOALS = LANDMARKS.filter((l) => l.isGoal);
const CAMP = LANDMARKS.find((l) => l.id === 'camp')!;

export class Journey {
  save: SaveData;
  safePoints: SafePoint[] = [];
  lastSafe = 0;
  winch: Winch;
  rope: RopeView;
  toolbox: pc.Entity | null = null;
  stuckTime = 0;
  flipTime = 0;
  resetHeld = 0;
  resetPhase: 'none' | 'in' | 'out' = 'none';
  resetT = 0;
  resetReason = '';
  shot: { lm: LandmarkDef; t: number; captured: boolean } | null = null;
  travelled = 0;
  private lastPos = new pc.Vec3();
  private saveTimer = 0;
  private hintUntil = 0;
  private hintKey = '';
  private time = 0;
  private tutorialT = 0;
  private upgradeShown = false;
  private campCheckCooldown = 0;
  fade = 0;

  constructor(private g: Game) {
    const { data, fresh } = loadSave();
    this.save = data;
    this.buildSafePoints();
    this.winch = new Winch(g.phys, g.vehicle, g.scatter.anchors);
    g.onVehicleChanged.push(() => {
      this.winch.detach();
      this.winch.mode = 'off';
      this.winch.v = g.vehicle;
      g.vehicle.mudUpgrade = this.save.upgraded;
    });
    this.rope = new RopeView(g.app, this.winch);
    // toolbox prop
    if (!data.hasToolbox) {
      const tb = g.lib.instantiate('toolbox');
      tb.setPosition(TOOLBOX.x, g.terrain.heightAt(TOOLBOX.x, TOOLBOX.z) + 0.02, TOOLBOX.z);
      tb.setEulerAngles(0, 35, 0);
      for (const r of tb.findComponents('render') as pc.RenderComponent[]) r.castShadows = true;
      g.app.root.addChild(tb);
      this.toolbox = tb;
    }
    g.vehicle.mudUpgrade = data.upgraded;
    g.view.setPaint(data.paint);
    this.upgradeShown = data.upgraded;
    store.set({
      visited: data.visited, hasToolbox: data.hasToolbox, upgraded: data.upgraded, completed: data.completed,
      paint: data.paint, unlockedPaints: data.unlockedPaints, photos: data.photos, settings: data.settings,
      journeyTime: data.journeyTime, firstRun: fresh, tutorialStep: data.tutorialDone ? 99 : 0,
    });
    if (!fresh && data.safePoint > 0 && data.safePoint < this.safePoints.length) {
      this.lastSafe = data.safePoint;
      const sp = this.safePoints[data.safePoint];
      g.teleport(sp.x, sp.z, sp.yaw);
    }
    this.lastPos.set(g.vehicle.pos.x, g.vehicle.pos.y, g.vehicle.pos.z);
    if (!storageAvailable) store.toast('浏览器本地存储不可用：本次进度只保存在当前会话中', 'warn', 8);
    this.updateObjective();
  }

  private buildSafePoints() {
    for (const r of this.g.terrain.roads) {
      if (r.def.id.endsWith('Pad')) continue;
      const L = r.path.length;
      for (let s = r.def.closed ? 0 : 4; s < L - 2; s += GAME.safePointSpacing) {
        const p = r.path.at(s);
        // skip points in water or mud
        const T = this.g.terrain;
        if (T.waterDepthAt(p.x, p.z) > 0.05) continue;
        const sw = T.surfaceAt(p.x, p.z, { grass: 0, dirt: 0, mud: 0, gravel: 0, rock: 0 });
        if (sw.mud > 0.2) continue;
        this.safePoints.push({ x: p.x, z: p.z, yaw: Math.atan2(-p.tx, -p.tz), road: r.def.id });
      }
    }
  }

  persist() {
    const s = store.get();
    this.save.settings = s.settings;
    this.save.safePoint = this.lastSafe;
    this.save.journeyTime = s.journeyTime;
    writeSave(this.save);
  }

  hint(key: string, text: string, secs = 6) {
    if (this.hintKey === key && this.time < this.hintUntil) return;
    this.hintKey = key;
    this.hintUntil = this.time + secs;
    store.set({ hint: text });
  }

  private clearHint(key?: string) {
    if (key && this.hintKey !== key) return;
    this.hintUntil = 0;
    if (store.get().hint) store.set({ hint: null });
  }

  requestReset(reason = '') {
    if (this.resetPhase !== 'none') return;
    this.resetPhase = 'in';
    this.resetT = 0;
    this.resetReason = reason;
  }

  private doReset() {
    const v = this.g.vehicle;
    const sp = this.safePoints[this.lastSafe] ?? this.safePoints[0];
    // face the way the car was heading along the road
    const dYaw = Math.atan2(Math.sin(v.yaw - sp.yaw), Math.cos(v.yaw - sp.yaw));
    const yaw = Math.abs(dYaw) > Math.PI / 2 ? sp.yaw + Math.PI : sp.yaw;
    this.winch.detach();
    this.g.teleport(sp.x, sp.z, yaw);
    this.stuckTime = 0;
    this.flipTime = 0;
    v.deepWaterTime = 0;
    this.clearHint();
    store.toast(this.resetReason || '已回到最近的安全点', 'info', 3);
  }

  /** interaction key (F / pad A): record landmark, pick up toolbox */
  interact(): boolean {
    const p = this.prompt;
    if (!p) return false;
    if (p.kind === 'toolbox') {
      this.save.hasToolbox = true;
      this.toolbox?.destroy();
      this.toolbox = null;
      store.set({ hasToolbox: true });
      store.toast('找到旧工具箱！发现任一风景点后回营地，就能装上全地形轮胎', 'good', 6);
      this.persist();
      this.updateObjective();
      return true;
    }
    if (p.kind === 'record' && p.lm) {
      this.startShot(p.lm);
      return true;
    }
    return false;
  }

  prompt: { kind: 'record' | 'toolbox' | 'info'; lm?: LandmarkDef; text: string } | null = null;

  private startShot(lm: LandmarkDef) {
    this.shot = { lm, t: 0, captured: false };
    this.g.input.enabled = false;
    this.g.cam.playShot(lm.shot.pos, lm.shot.target);
    store.set({ cinematic: { title: lm.name, subtitle: lm.subtitle }, prompt: null });
  }

  private updateShot(dt: number) {
    const s = this.shot!;
    s.t += dt;
    if (!s.captured && s.t > 2.1) {
      s.captured = true;
      this.g.app.once('frameend', () => {
        try {
          const src = this.g.canvas;
          const c = document.createElement('canvas');
          c.width = 480; c.height = 270;
          const ctx = c.getContext('2d')!;
          const ar = src.width / src.height, tr = 480 / 270;
          let sw = src.width, sh = src.height, sx = 0, sy = 0;
          if (ar > tr) { sw = src.height * tr; sx = (src.width - sw) / 2; } else { sh = src.width / tr; sy = (src.height - sh) / 2; }
          ctx.drawImage(src, sx, sy, sw, sh, 0, 0, 480, 270);
          const url = c.toDataURL('image/jpeg', 0.72);
          this.save.photos = { ...this.save.photos, [s.lm.id]: url };
          store.set({ photos: this.save.photos });
          this.persist();
        } catch (e) {
          console.warn('photo capture failed', e);
        }
      });
    }
    if (s.t > 4.2) {
      this.shot = null;
      this.g.cam.endShot();
      this.g.input.enabled = true;
      this.g.input.clear();
      store.set({ cinematic: null });
      const lm = s.lm;
      if (lm.isGoal && !this.save.visited.includes(lm.id)) {
        this.save.visited = [...this.save.visited, lm.id];
        store.set({ visited: this.save.visited });
        const n = this.save.visited.length;
        store.toast(`已记录：${lm.name}（${n}/${GOALS.length}）`, 'good', 5);
        if (n === GOALS.length) store.toast('三处风景都已记录，返回松溪营地完成旅程', 'good', 7);
      } else if (lm.id === 'camp') {
        this.finishJourney();
      } else if (!lm.isGoal) {
        const extra = LANDMARKS.filter((l) => !l.isGoal && l.id !== 'camp');
        const got = extra.filter((l) => l.id === lm.id || this.save.photos[l.id]).length;
        store.toast(`已收录探索点「${lm.name}」（${got}/${extra.length}）`, 'good', 5);
      }
      this.persist();
      this.updateObjective();
    }
  }

  private finishJourney() {
    if (this.save.completed) return;
    this.save.completed = true;
    if (!this.save.unlockedPaints.includes('pine')) this.save.unlockedPaints = [...this.save.unlockedPaints, 'pine'];
    store.set({ completed: true, unlockedPaints: this.save.unlockedPaints, screen: 'journal' });
    this.g.paused = true;
    store.toast('旅程完成！解锁纪念车漆「松林绿」，可在暂停菜单更换', 'good', 8);
    this.persist();
  }

  updateObjective() {
    const s = this.save;
    const left = GOALS.filter((l) => !s.visited.includes(l.id));
    let objective: string;
    if (s.completed) objective = '旅程已完成 · 自由探索';
    else if (left.length) objective = `记录风景点 ${s.visited.length}/${GOALS.length}：${left.map((l) => l.name).join('、')}`;
    else objective = '返回松溪营地，记录旅程终点';
    store.set({ objective });
  }

  private nearestTarget(): LandmarkDef {
    const v = this.g.vehicle;
    const left = GOALS.filter((l) => !this.save.visited.includes(l.id));
    const list = left.length && !this.save.completed ? left : [CAMP];
    let best = list[0], bd = Infinity;
    for (const l of list) {
      const d = Math.hypot(l.x - v.pos.x, l.z - v.pos.z);
      if (d < bd) { bd = d; best = l; }
    }
    return best;
  }

  update(dt: number, resetKey: boolean, reelKey: boolean) {
    const g = this.g;
    const v = g.vehicle;
    this.time += dt;
    if (g.paused) return;
    const st = store.get();
    if (!this.shot) store.set({ journeyTime: st.journeyTime + dt });
    const kmh = Math.abs(v.forwardSpeed) * 3.6;

    // ---- reset fade
    if (this.resetPhase === 'in') {
      this.resetT += dt / 0.35;
      if (this.resetT >= 1) { this.doReset(); this.resetPhase = 'out'; this.resetT = 1; }
    } else if (this.resetPhase === 'out') {
      this.resetT -= dt / 0.45;
      if (this.resetT <= 0) { this.resetPhase = 'none'; this.resetT = 0; }
    }
    this.fade = this.resetT;
    if (Math.abs(store.get().fade - this.fade) > 0.01 || (this.fade === 0 && store.get().fade !== 0)) store.set({ fade: this.fade });

    if (this.shot) { this.updateShot(dt); return; }

    // ---- hold R to reset
    if (resetKey && this.resetPhase === 'none') {
      this.resetHeld += dt;
      if (this.resetHeld >= GAME.resetHold) { this.resetHeld = 0; this.requestReset(); }
    } else this.resetHeld = 0;
    store.set({ resetHold: this.resetHeld / GAME.resetHold });

    // ---- travelled distance
    const d = Math.hypot(v.pos.x - this.lastPos.x, v.pos.z - this.lastPos.z);
    if (d < 5) this.travelled += d;
    this.lastPos.set(v.pos.x, v.pos.y, v.pos.z);

    // ---- safe points (only in a clean, stable state)
    const T = g.terrain;
    const stable = v.groundedCount === 4 && v.uprightness > 0.9 && T.waterDepthAt(v.pos.x, v.pos.z) < 0.05 && v.wheels.every((w) => w.mud < 0.3);
    if (stable) {
      for (let i = 0; i < this.safePoints.length; i++) {
        const sp = this.safePoints[i];
        if (Math.abs(sp.x - v.pos.x) > 6 || Math.abs(sp.z - v.pos.z) > 6) continue;
        if (Math.hypot(sp.x - v.pos.x, sp.z - v.pos.z) < 5.5 && i !== this.lastSafe) this.lastSafe = i;
      }
    }

    // ---- stuck, flipped, deep water
    const trying = v.throttle > 0.3;
    if (trying && kmh < 0.8) this.stuckTime += dt;
    else if (kmh > 2.5) this.stuckTime = 0;
    if (v.uprightness < 0.45) this.flipTime += dt; else this.flipTime = 0;
    const depth = T.waterDepthAt(v.pos.x, v.pos.z);
    const warn = depth > v.spec.waterWarnDepth;
    if (warn !== st.waterWarn) store.set({ waterWarn: warn });
    if (v.deepWaterTime > v.spec.waterFailTime) {
      v.deepWaterTime = 0;
      this.requestReset('水太深，车辆已被拖回安全点');
    } else if (this.flipTime > 1.5) {
      this.hint('flip', '车辆倾覆了：按住 R 一秒回到最近的安全点', 5);
    } else if (this.stuckTime > GAME.stuckResetHint) {
      this.hint('stuck2', '按住 R 一秒，免费回到最近的安全点', 6);
    } else if (this.stuckTime > GAME.stuckToolsHint) {
      const mud = v.wheels.some((w) => w.mud > 0.3);
      this.hint('stuck1', mud
        ? '泥里打滑：松油后轻踩、按 Q 换低档，或按 E 用绞盘拉出来'
        : '被卡住了？试试 Q 换低档、倒车换条线，或按 E 使用绞盘', 7);
    } else if (warn) {
      this.hint('water', '水太深了！倒车退回浅处', 3);
    }

    // ---- winch
    if (this.winch.mode === 'select') {
      const f = g.cam.entity.forward;
      this.winch.refresh({ x: f.x, z: f.z });
      if (kmh > 3) this.winch.mode = 'off';
    }
    if (this.winch.message) { store.toast(this.winch.message, 'warn'); this.winch.message = null; }
    this.rope.update(dt);
    const w = this.winch;
    const sel = w.selected;
    store.set({
      winch: {
        mode: w.mode,
        tension: w.tension,
        length: w.length,
        target: w.mode === 'select' ? (sel ? `${sel.anchor.kind === 'tree' ? '树干' : '岩桩'} · ${sel.dist.toFixed(0)} m · ${sel.front ? '车头' : '车尾'}` : null) : null,
        message: w.mode === 'select' && !sel ? (w.candidates[0]?.reason ?? '附近没有可用锚点') : null,
      },
    });
    this.reel = reelKey;

    // ---- prompts: landmarks and toolbox
    let prompt: Journey['prompt'] = null;
    const slow = kmh < GAME.recordSpeedKmh;
    for (const lm of LANDMARKS) {
      const dist = Math.hypot(lm.x - v.pos.x, lm.z - v.pos.z);
      if (dist > lm.radius) continue;
      if (lm.id === 'camp') {
        this.campLogic(slow, dt);
        const all = GOALS.every((l) => this.save.visited.includes(l.id));
        if (all && !this.save.completed) prompt = slow ? { kind: 'record', lm, text: '按 F 记录旅程终点' } : { kind: 'info', text: '停稳车辆，记录旅程终点' };
        continue;
      }
      const done = this.save.visited.includes(lm.id);
      if (slow) prompt = { kind: 'record', lm, text: done ? `按 F 再次拍摄「${lm.name}」` : `按 F 记录「${lm.name}」` };
      else if (!done) prompt = { kind: 'info', text: `减速停稳，记录「${lm.name}」` };
    }
    if (this.toolbox && Math.hypot(TOOLBOX.x - v.pos.x, TOOLBOX.z - v.pos.z) < 6) {
      prompt = slow ? { kind: 'toolbox', text: '按 F 拾取工具箱' } : { kind: 'info', text: '停下来看看这个工具箱' };
    }
    this.prompt = prompt;
    if ((st.prompt ?? null) !== (prompt?.text ?? null)) store.set({ prompt: prompt?.text ?? null });

    // ---- compass target
    const tgt = this.nearestTarget();
    const bearing = Math.atan2(tgt.x - v.pos.x, -(tgt.z - v.pos.z));
    store.set({ nearestLandmark: { name: tgt.name, dist: Math.hypot(tgt.x - v.pos.x, tgt.z - v.pos.z), bearing } });

    this.tutorial(dt);
    if (this.time > this.hintUntil && st.hint) store.set({ hint: null });

    this.saveTimer += dt;
    if (this.saveTimer > 20) { this.saveTimer = 0; this.persist(); }
  }

  reel = false;

  private campLogic(slow: boolean, dt: number) {
    this.campCheckCooldown -= dt;
    if (!slow || this.campCheckCooldown > 0) return;
    this.campCheckCooldown = 1;
    // stopping at camp makes camp the respawn point (loop safe point 0 sits at the camp entrance)
    if (this.lastSafe !== 0) { this.lastSafe = 0; this.persist(); }
    if (this.save.hasToolbox && !this.save.upgraded && this.save.visited.length > 0) {
      this.save.upgraded = true;
      this.g.vehicle.mudUpgrade = true;
      store.set({ upgraded: true });
      if (!this.upgradeShown) {
        this.upgradeShown = true;
        store.toast('在营地换上了全地形轮胎：泥地和碎石上抓地更稳', 'good', 7);
      }
      this.persist();
    }
  }

  private tutorial(dt: number) {
    const st = store.get();
    if (this.save.tutorialDone) return;
    // help hints (stuck, flipped, water) take priority over onboarding
    if (this.time < this.hintUntil && !this.hintKey.startsWith('t')) return;
    const v = this.g.vehicle;
    const step = st.tutorialStep;
    this.tutorialT += dt;
    const near = (x: number, z: number, r: number) => Math.hypot(v.pos.x - x, v.pos.z - z) < r;
    if (step === 0) {
      this.hint('t0', 'W / ↑ 油门　S / ↓ 制动，停稳后倒车　A / D 转向', 2);
      if (this.travelled > 45) { store.set({ tutorialStep: 1 }); this.tutorialT = 0; this.clearHint('t0'); }
    } else if (step === 1) {
      this.hint('t1', '按住鼠标右键拖动可环视，C 回正镜头；M 打开地图', 2);
      if (this.tutorialT > 7) { store.set({ tutorialStep: 2 }); this.clearHint('t1'); }
    } else if (step === 2) {
      if (near(-200, 10, 34)) {
        this.hint('t2', '前方碎石坡：按 Q 切换低档，慢一点更稳', 2);
        if (v.gear === 'low' || near(-199, -30, 8)) { store.set({ tutorialStep: 3 }); this.clearHint('t2'); }
      } else if (this.save.visited.length > 0) store.set({ tutorialStep: 3 });
    } else if (step === 3) {
      if (near(60, -9, 30)) {
        this.hint('t3', '泥地抓地差：稳住小油门、少打方向；陷住了就按 E 用绞盘', 2);
      } else if (near(95, -12, 8) || near(124, -16, 10)) {
        store.set({ tutorialStep: 99 });
        this.save.tutorialDone = true;
        this.clearHint('t3');
        this.persist();
      }
    }
  }
}
