// WebAudio soundscape: synthesised engine (rpm + load, per-vehicle voice),
// tyre/surface noise, mud, water, wind, creek, birds by day and crickets and
// owls by night, winch and suspension thumps; plus streamed background music
// (free tracks, see docs/CREDITS.md) with day / night / demo playlists and
// crossfades. Everything is mixed into one master that can also be recorded.
import type { Game } from './Game';
import type { InputFrame } from './input';
import { journey } from './boot';
import { clamp, lerp } from './world/noise';

function noiseBuffer(ctx: AudioContext, secs = 2, brown = false): AudioBuffer {
  const buf = ctx.createBuffer(1, ctx.sampleRate * secs, ctx.sampleRate);
  const d = buf.getChannelData(0);
  let last = 0;
  for (let i = 0; i < d.length; i++) {
    const w = Math.random() * 2 - 1;
    if (brown) { last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; } else d[i] = w;
  }
  return buf;
}

interface NoiseVoice { src: AudioBufferSourceNode; filter: BiquadFilterNode; gain: GainNode }

export type MusicMode = 'title' | 'day' | 'night' | 'demo' | 'off';

/** background music: Kevin MacLeod (incompetech.com), CC BY 4.0 — see docs/CREDITS.md */
export const MUSIC: Record<Exclude<MusicMode, 'off'>, { file: string; title: string }[]> = {
  title: [{ file: 'demo_lasting_hope.mp3', title: 'Lasting Hope' }],
  day: [{ file: 'day_wholesome.mp3', title: 'Wholesome' }, { file: 'day_porch_swing.mp3', title: 'Porch Swing Days (slower)' }],
  night: [{ file: 'night_healing.mp3', title: 'Healing' }, { file: 'night_frost_waltz.mp3', title: 'Frost Waltz' }],
  demo: [{ file: 'demo_lasting_hope.mp3', title: 'Lasting Hope' }],
};

class MusicPlayer {
  private els: HTMLAudioElement[] = [];
  private gains: GainNode[] = [];
  private cur = 0;
  mode: MusicMode = 'off';
  private pos: Record<string, number> = {};
  nowPlaying = '';

  constructor(private ctx: AudioContext, out: AudioNode) {
    for (let i = 0; i < 2; i++) {
      const el = new Audio();
      el.preload = 'auto';
      el.crossOrigin = 'anonymous';
      const src = ctx.createMediaElementSource(el);
      const g = ctx.createGain();
      g.gain.value = 0;
      src.connect(g);
      g.connect(out);
      el.addEventListener('ended', () => { if (this.cur === i) this.next(2); });
      this.els.push(el);
      this.gains.push(g);
    }
  }

  setMode(mode: MusicMode, fade = 3, restart = false) {
    if (mode === this.mode && !restart) return;
    this.mode = mode;
    if (mode === 'off') { this.fadeOut(this.cur, fade); this.nowPlaying = ''; return; }
    this.next(fade, restart);
  }

  private next(fade: number, restart = false) {
    if (this.mode === 'off') return;
    const list = MUSIC[this.mode];
    const k = restart ? 0 : (this.pos[this.mode] ?? -1) + 1;
    this.pos[this.mode] = k % list.length;
    const track = list[k % list.length];
    const old = this.cur;
    this.cur = 1 - this.cur;
    const el = this.els[this.cur];
    el.src = `assets/music/${track.file}`;
    el.currentTime = 0;
    void el.play().catch(() => { /* blocked until a gesture */ });
    this.nowPlaying = track.title;
    const t = this.ctx.currentTime;
    const g = this.gains[this.cur].gain;
    g.cancelScheduledValues(t);
    g.setValueAtTime(0, t);
    g.linearRampToValueAtTime(1, t + Math.max(0.05, fade));
    this.fadeOut(old, fade);
  }

  private fadeOut(i: number, fade: number) {
    const t = this.ctx.currentTime;
    const g = this.gains[i].gain;
    g.cancelScheduledValues(t);
    g.setValueAtTime(g.value, t);
    g.linearRampToValueAtTime(0, t + Math.max(0.05, fade));
    const el = this.els[i];
    setTimeout(() => { if (this.cur !== i || this.mode === 'off') el.pause(); }, fade * 1000 + 100);
  }

  resume() {
    const el = this.els[this.cur];
    if (this.mode !== 'off' && el.paused && el.src) void el.play().catch(() => undefined);
  }
}

export class GameAudio {
  ctx: AudioContext | null = null;
  private master!: GainNode;
  private sfx!: GainNode;
  private music!: GainNode;
  private engA!: OscillatorNode;
  private engB!: OscillatorNode;
  private engSub!: OscillatorNode;
  private engFilter!: BiquadFilterNode;
  private engGain!: GainNode;
  private engNoise!: NoiseVoice;
  private roll!: NoiseVoice;
  private gravel!: NoiseVoice;
  private mud!: NoiseVoice;
  private splash!: NoiseVoice;
  private wind!: NoiseVoice;
  private creek!: NoiseVoice;
  private creek2!: NoiseVoice;
  private winchOsc!: OscillatorNode;
  private winchGain!: GainNode;
  private rpm = 800;
  private birdT = 2;
  private creekT = 0;
  private creekDist = 100;
  private creekHint = 0;
  private thumpCd = 0;
  private vols = { master: 0.8, sfx: 0.8, music: 0.5 };
  private pausedState = false;
  music_!: MusicPlayer;
  private recDest: MediaStreamAudioDestinationNode | null = null;
  private comp!: DynamicsCompressorNode;
  private nightT = 3;
  /** requested music mode before the context exists */
  private wantMusic: MusicMode = 'title';

  constructor(private g: Game) {}

  /** switch the background playlist (title / day / night / demo / off) */
  setMusic(mode: MusicMode, fade = 3, restart = false) {
    this.wantMusic = mode;
    this.music_?.setMode(mode, fade, restart);
  }

  get nowPlaying() { return this.music_?.nowPlaying ?? ''; }

  /** the final mix as a MediaStream (for recording the demo) */
  captureStream(): MediaStream | null {
    if (!this.ctx) return null;
    if (!this.recDest) {
      // recordings sit a little hotter than the speakers, behind a limiter
      this.recDest = this.ctx.createMediaStreamDestination();
      const boost = this.ctx.createGain();
      boost.gain.value = 2;
      const limiter = this.ctx.createDynamicsCompressor();
      limiter.threshold.value = -3;
      limiter.ratio.value = 20;
      limiter.attack.value = 0.003;
      limiter.release.value = 0.15;
      this.comp.connect(boost);
      boost.connect(limiter);
      limiter.connect(this.recDest);
    }
    return this.recDest.stream;
  }

  unlock() {
    if (this.ctx) { void this.ctx.resume(); this.music_?.resume(); return; }
    let ctx: AudioContext;
    try { ctx = new AudioContext(); } catch { return; }
    this.ctx = ctx;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -14; comp.ratio.value = 4;
    comp.connect(ctx.destination);
    this.comp = comp;
    this.master = ctx.createGain();
    this.master.connect(comp);
    this.sfx = ctx.createGain();
    this.sfx.connect(this.master);
    this.music = ctx.createGain();
    this.music.connect(this.master);
    const white = noiseBuffer(ctx, 3), brown = noiseBuffer(ctx, 3, true);
    const nv = (buf: AudioBuffer, type: BiquadFilterType, f: number, q = 0.7): NoiseVoice => {
      const src = ctx.createBufferSource();
      src.buffer = buf; src.loop = true;
      src.playbackRate.value = 0.9 + Math.random() * 0.2;
      const filter = ctx.createBiquadFilter();
      filter.type = type; filter.frequency.value = f; filter.Q.value = q;
      const gain = ctx.createGain();
      gain.gain.value = 0;
      src.connect(filter); filter.connect(gain); gain.connect(this.sfx);
      src.start();
      return { src, filter, gain };
    };
    // engine: two detuned saws + sub through a load-dependent low-pass
    this.engFilter = ctx.createBiquadFilter();
    this.engFilter.type = 'lowpass'; this.engFilter.Q.value = 2.5;
    this.engGain = ctx.createGain(); this.engGain.gain.value = 0;
    const shaper = ctx.createWaveShaper();
    const curve = new Float32Array(1024);
    for (let i = 0; i < 1024; i++) { const x = i / 512 - 1; curve[i] = Math.tanh(x * 2.2); }
    shaper.curve = curve;
    this.engA = ctx.createOscillator(); this.engA.type = 'sawtooth';
    this.engB = ctx.createOscillator(); this.engB.type = 'sawtooth'; this.engB.detune.value = 14;
    this.engSub = ctx.createOscillator(); this.engSub.type = 'square';
    const subG = ctx.createGain(); subG.gain.value = 0.4;
    this.engA.connect(shaper); this.engB.connect(shaper); this.engSub.connect(subG); subG.connect(shaper);
    shaper.connect(this.engFilter); this.engFilter.connect(this.engGain); this.engGain.connect(this.sfx);
    for (const o of [this.engA, this.engB, this.engSub]) o.start();
    this.engNoise = nv(brown, 'lowpass', 180, 1);
    this.roll = nv(brown, 'lowpass', 420, 0.8);
    this.gravel = nv(white, 'bandpass', 2600, 0.9);
    this.mud = nv(brown, 'lowpass', 260, 3);
    this.splash = nv(white, 'bandpass', 900, 0.6);
    this.wind = nv(brown, 'bandpass', 500, 0.5);
    this.creek = nv(white, 'bandpass', 1700, 0.8);
    this.creek2 = nv(brown, 'bandpass', 480, 1.2);
    this.winchOsc = ctx.createOscillator(); this.winchOsc.type = 'sawtooth'; this.winchOsc.frequency.value = 160;
    const wf = ctx.createBiquadFilter(); wf.type = 'bandpass'; wf.frequency.value = 900; wf.Q.value = 2;
    this.winchGain = ctx.createGain(); this.winchGain.gain.value = 0;
    this.winchOsc.connect(wf); wf.connect(this.winchGain); this.winchGain.connect(this.sfx);
    this.winchOsc.start();
    this.music_ = new MusicPlayer(ctx, this.music);
    this.music_.setMode(this.wantMusic, 2);
    this.applyVolumes();
  }

  setVolumes(master: number, sfx: number, music: number) {
    this.vols = { master, sfx, music };
    this.applyVolumes();
  }

  private applyVolumes() {
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    this.master.gain.setTargetAtTime(this.pausedState ? this.vols.master * 0.35 : this.vols.master, t, 0.1);
    this.sfx.gain.setTargetAtTime(this.vols.sfx, t, 0.1);
    this.music.gain.setTargetAtTime(this.vols.music, t, 0.1);
  }

  setPaused(p: boolean) {
    this.pausedState = p;
    this.applyVolumes();
  }

  private set(p: AudioParam, v: number, tc = 0.06) {
    p.setTargetAtTime(v, this.ctx!.currentTime, tc);
  }

  update(dt: number, _inp: InputFrame) {
    if (!this.ctx) return;
    const g = this.g;
    const v = g.vehicle;
    const paused = g.paused;
    const speed = paused ? 0 : Math.abs(v.forwardSpeed);
    // ---- engine rpm proxy from wheel speed, gear and wheel spin
    let omega = 0, grounded = 0, spin = 0, mud = 0, gravel = 0, water = 0, rock = 0;
    for (const w of v.wheels) {
      omega += Math.abs(w.omega) / 4;
      if (w.grounded) {
        grounded++;
        if (w.spinning) spin += 0.25;
        mud += w.mud / 4; gravel += w.gravel / 4;
        if (w.surface === 'rock') rock += 0.25;
      }
      water = Math.max(water, w.water);
    }
    const E = v.spec.engine;
    const ratio = (v.dir < 0 ? 210 : v.gear === 'low' ? 250 : 88) * (E.max / 3600);
    const targetRpm = clamp(E.idle + 20 + omega * ratio + v.throttle * 700, E.idle, E.max + 700);
    this.rpm = lerp(this.rpm, paused ? E.idle : targetRpm, Math.min(1, dt * (targetRpm > this.rpm ? 5 : 3)));
    const load = paused ? 0 : clamp(v.throttle * (0.5 + v.engineLoad * 0.5) + spin * 0.3, 0, 1);
    // firing frequency: rpm / 60 * cylinders / 2, shaded by the vehicle's tone
    const f = (this.rpm / 60) * (E.cyl / 2) * E.tone;
    this.set(this.engA.frequency, f);
    this.set(this.engB.frequency, f * 1.005);
    this.set(this.engSub.frequency, f * 0.5);
    this.set(this.engFilter.frequency, 220 + load * 1300 + this.rpm * 0.18);
    this.set(this.engGain.gain, 0.05 + load * 0.08 + (this.rpm - E.idle) / 3500 * 0.03);
    this.set(this.engNoise.gain.gain, 0.05 + load * 0.12);
    this.set(this.engNoise.filter.frequency, 120 + this.rpm * 0.08);
    // ---- tyres and surfaces
    const onGround = grounded / 4;
    const sp = clamp(speed / 8, 0, 1);
    this.set(this.roll.gain.gain, onGround * sp * 0.22 * (1 - mud * 0.6));
    this.set(this.roll.filter.frequency, 250 + speed * 40);
    const crunch = onGround * clamp(speed / 5, 0, 1) * (gravel * 0.3 + rock * 0.12) * (0.8 + Math.random() * 0.4);
    this.set(this.gravel.gain.gain, crunch, 0.03);
    const squelch = onGround * mud * (clamp(speed / 4, 0, 1) * 0.25 + spin * 0.5) * (0.6 + 0.4 * Math.sin(g.simTime * 9));
    this.set(this.mud.gain.gain, squelch, 0.04);
    this.set(this.mud.filter.frequency, 200 + spin * 300);
    this.set(this.splash.gain.gain, clamp(water * 3, 0, 1) * clamp(speed / 3, 0, 1) * 0.35);
    // ---- ambience
    const pos = v.pos;
    const altitude = clamp((pos.y - 5) / 40, 0, 1);
    this.set(this.wind.gain.gain, 0.03 + altitude * 0.05 + sp * 0.04 + Math.sin(g.simTime * 0.3) * 0.01, 0.4);
    this.creekT -= dt;
    if (this.creekT <= 0) {
      this.creekT = 0.3;
      const n = g.terrain.stream.nearest(pos.x, pos.z, this.creekHint, 80);
      this.creekHint = n.s;
      if (n.d > 70) { const m = g.terrain.stream.nearest(pos.x, pos.z); this.creekHint = m.s; this.creekDist = m.d; } else this.creekDist = n.d;
    }
    const creekVol = clamp(1 - this.creekDist / 70, 0, 1);
    this.set(this.creek.gain.gain, creekVol * creekVol * 0.16, 0.3);
    this.set(this.creek2.gain.gain, creekVol * creekVol * 0.12, 0.3);
    // ---- winch
    const w = journey?.winch;
    const reeling = !!w && w.mode === 'attached' && w.reeling && !paused;
    this.set(this.winchGain.gain, reeling ? 0.06 + (w!.tension / 11000) * 0.05 : 0, 0.05);
    if (w) this.set(this.winchOsc.frequency, 190 - (w.tension / 11000) * 60);
    // ---- suspension thumps
    this.thumpCd -= dt;
    if (!paused && v.impact > 0.25 && this.thumpCd <= 0) { this.thump(v.impact); this.thumpCd = 0.25; }
    // ---- birds by day, crickets and owls by night
    const night = g.env.night;
    this.birdT -= dt;
    if (this.birdT <= 0) { this.birdT = 2.5 + Math.random() * 6; if ((!paused || Math.random() < 0.5) && Math.random() > night) this.bird(); }
    this.nightT -= dt;
    if (this.nightT <= 0 && night > 0.5) {
      this.nightT = 0.6 + Math.random() * 1.6;
      if (Math.random() < 0.07) this.owl(); else this.cricket(night);
    }
  }

  private cricket(k: number) {
    const ctx = this.ctx!;
    const t0 = ctx.currentTime;
    const o = ctx.createOscillator();
    o.type = 'sine';
    o.frequency.value = 4200 + Math.random() * 900;
    const gg = ctx.createGain();
    gg.gain.value = 0;
    const pan = ctx.createStereoPanner();
    pan.pan.value = Math.random() * 1.8 - 0.9;
    o.connect(gg); gg.connect(pan); pan.connect(this.sfx);
    const pulses = 3 + Math.floor(Math.random() * 4);
    for (let i = 0; i < pulses; i++) {
      const t = t0 + i * 0.055;
      gg.gain.setValueAtTime(0, t);
      gg.gain.linearRampToValueAtTime(0.012 * k, t + 0.01);
      gg.gain.linearRampToValueAtTime(0, t + 0.04);
    }
    o.start(t0);
    o.stop(t0 + pulses * 0.055 + 0.05);
  }

  private owl() {
    const ctx = this.ctx!;
    const t0 = ctx.currentTime;
    const o = ctx.createOscillator();
    o.type = 'sine';
    const gg = ctx.createGain();
    gg.gain.value = 0;
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass'; lp.frequency.value = 900;
    o.connect(gg); gg.connect(lp); lp.connect(this.sfx);
    const hoots: [number, number, number][] = [[0, 0.35, 420], [0.55, 0.18, 400], [0.8, 0.5, 380]];
    for (const [dt, d, f] of hoots) {
      const t = t0 + dt;
      o.frequency.setValueAtTime(f, t);
      o.frequency.linearRampToValueAtTime(f * 0.92, t + d);
      gg.gain.setValueAtTime(0, t);
      gg.gain.linearRampToValueAtTime(0.04, t + 0.06);
      gg.gain.linearRampToValueAtTime(0, t + d);
    }
    o.start(t0);
    o.stop(t0 + 1.5);
  }

  private thump(k: number) {
    const ctx = this.ctx!;
    const t = ctx.currentTime;
    const o = ctx.createOscillator();
    o.type = 'sine';
    o.frequency.setValueAtTime(90, t);
    o.frequency.exponentialRampToValueAtTime(40, t + 0.18);
    const gg = ctx.createGain();
    gg.gain.setValueAtTime(0.0001, t);
    gg.gain.exponentialRampToValueAtTime(0.25 * k + 0.05, t + 0.01);
    gg.gain.exponentialRampToValueAtTime(0.0001, t + 0.25);
    o.connect(gg); gg.connect(this.sfx);
    o.start(t); o.stop(t + 0.3);
  }

  private bird() {
    const ctx = this.ctx!;
    const t0 = ctx.currentTime;
    const pan = ctx.createStereoPanner();
    pan.pan.value = Math.random() * 1.6 - 0.8;
    const gg = ctx.createGain();
    gg.gain.value = 0;
    pan.connect(this.sfx);
    gg.connect(pan);
    const o = ctx.createOscillator();
    o.type = 'sine';
    o.connect(gg);
    const base = 2200 + Math.random() * 1800;
    const notes = 2 + Math.floor(Math.random() * 4);
    let t = t0;
    for (let i = 0; i < notes; i++) {
      const d = 0.06 + Math.random() * 0.1;
      o.frequency.setValueAtTime(base * (0.9 + Math.random() * 0.3), t);
      o.frequency.exponentialRampToValueAtTime(base * (1.1 + Math.random() * 0.5), t + d);
      gg.gain.setValueAtTime(0, t);
      gg.gain.linearRampToValueAtTime(0.025 + Math.random() * 0.02, t + 0.015);
      gg.gain.linearRampToValueAtTime(0, t + d);
      t += d + 0.04 + Math.random() * 0.08;
    }
    o.start(t0);
    o.stop(t + 0.1);
  }
}
