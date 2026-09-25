// Tiny observable store shared by the game loop and React UI.
import type { Gear } from './physics/vehicle';
import type { SurfaceKind } from './world/layout';
import type { VehicleId } from './config';

export type Screen = 'loading' | 'title' | 'playing' | 'paused' | 'map' | 'photo' | 'journal';

export interface Toast {
  id: number;
  text: string;
  kind: 'info' | 'good' | 'warn';
  until: number;
}

export interface HudState {
  screen: Screen;
  loading: number;
  loadingText: string;
  speedKmh: number;
  gear: Gear;
  reverse: boolean;
  heading: number;
  surface: SurfaceKind;
  water: number;
  waterWarn: boolean;
  resetHold: number;
  hint: string | null;
  prompt: string | null;
  winch: { mode: 'off' | 'select' | 'attached'; tension: number; length: number; target: string | null; message: string | null };
  visited: string[];
  hasToolbox: boolean;
  upgraded: boolean;
  completed: boolean;
  paint: string;
  unlockedPaints: string[];
  journeyTime: number;
  toasts: Toast[];
  objective: string;
  nearestLandmark: { name: string; dist: number; bearing: number } | null;
  fps: number;
  debug: string | null;
  firstRun: boolean;
  tutorialStep: number;
  photos: Record<string, string>;
  settings: Settings;
  cinematic: { title: string; subtitle: string } | null;
  fade: number;
  vehicle: VehicleId;
  /** per-vehicle chosen paint */
  paints: Partial<Record<VehicleId, string>>;
  timeOfDay: 'day' | 'night';
  /** 0 off, 1 low beam, 2 high beam */
  beam: number;
  lowRange: boolean;
  dirt: number;
  /** demo director caption and state */
  demo: { active: boolean; recording: boolean; caption: string | null; sub: string | null; progress: number } | null;
  park: { running: boolean; time: number; split: number; gate: number; gates: number; best: number | null; last: number | null; splits: number[] } | null;
}

export interface Settings {
  quality: 'low' | 'medium' | 'high';
  master: number;
  music: number;
  effects: number;
  shake: boolean;
  fineThrottle: boolean;
  showFps: boolean;
  invertY: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  quality: 'high',
  master: 0.8,
  music: 0.5,
  effects: 0.8,
  shake: true,
  fineThrottle: false,
  showFps: false,
  invertY: false,
};

type Listener = () => void;

class Store {
  state: HudState = {
    screen: 'loading',
    loading: 0,
    loadingText: '正在准备森林…',
    speedKmh: 0,
    gear: 'high',
    reverse: false,
    heading: 0,
    surface: 'dirt',
    water: 0,
    waterWarn: false,
    resetHold: 0,
    hint: null,
    prompt: null,
    winch: { mode: 'off', tension: 0, length: 0, target: null, message: null },
    visited: [],
    hasToolbox: false,
    upgraded: false,
    completed: false,
    paint: 'ochre',
    unlockedPaints: ['ochre', 'cream'],
    journeyTime: 0,
    toasts: [],
    objective: '',
    nearestLandmark: null,
    fps: 0,
    debug: null,
    firstRun: true,
    tutorialStep: 0,
    photos: {},
    settings: { ...DEFAULT_SETTINGS },
    cinematic: null,
    fade: 0,
    vehicle: 'scout',
    paints: {},
    timeOfDay: 'day',
    beam: 0,
    lowRange: false,
    dirt: 0,
    demo: null,
    park: null,
  };
  private listeners = new Set<Listener>();
  private toastId = 1;

  subscribe = (l: Listener) => {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  };
  get = () => this.state;
  private scheduled = false;
  set(patch: Partial<HudState>) {
    let changed = false;
    for (const k in patch) {
      if ((this.state as unknown as Record<string, unknown>)[k] !== (patch as Record<string, unknown>)[k]) { changed = true; break; }
    }
    if (!changed) return;
    this.state = { ...this.state, ...patch };
    // notify at most once per animation frame
    if (!this.scheduled) {
      this.scheduled = true;
      requestAnimationFrame(() => {
        this.scheduled = false;
        for (const l of this.listeners) l();
      });
    }
  }
  toast(text: string, kind: Toast['kind'] = 'info', secs = 4) {
    const now = performance.now();
    const toasts = this.state.toasts.filter((t) => t.until > now).concat({ id: this.toastId++, text, kind, until: now + secs * 1000 });
    this.set({ toasts: toasts.slice(-4) });
  }
}

export const store = new Store();
