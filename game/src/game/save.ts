// Versioned localStorage save with an in-memory fallback.
import { DEFAULT_SETTINGS, type Settings } from './store';
import type { VehicleId } from './config';

export const SAVE_KEY = 'forest-trail/save';
export const SAVE_VERSION = 1;

export interface SaveData {
  version: number;
  visited: string[];
  hasToolbox: boolean;
  upgraded: boolean;
  completed: boolean;
  paint: string;
  unlockedPaints: string[];
  /** safe point index on the safe point list */
  safePoint: number;
  photos: Record<string, string>;
  settings: Settings;
  journeyTime: number;
  tutorialDone: boolean;
  savedAt: number;
  /** selected vehicle and its paint per vehicle */
  vehicle: VehicleId;
  paints: Partial<Record<VehicleId, string>>;
  timeOfDay: 'day' | 'night';
  /** trail park best lap (s) and best section times */
  parkBest: number | null;
  parkSplits: number[];
}

export function defaultSave(): SaveData {
  return {
    version: SAVE_VERSION,
    visited: [],
    hasToolbox: false,
    upgraded: false,
    completed: false,
    paint: 'ochre',
    unlockedPaints: ['ochre', 'cream'],
    safePoint: 0,
    photos: {},
    settings: { ...DEFAULT_SETTINGS },
    journeyTime: 0,
    tutorialDone: false,
    savedAt: 0,
    vehicle: 'scout',
    paints: {},
    timeOfDay: 'day',
    parkBest: null,
    parkSplits: [],
  };
}

let memory: SaveData | null = null;
export let storageAvailable = true;

function probe(): boolean {
  try {
    const k = '__ft_probe';
    localStorage.setItem(k, '1');
    localStorage.removeItem(k);
    return true;
  } catch {
    return false;
  }
}

export function loadSave(): { data: SaveData; fresh: boolean } {
  storageAvailable = probe();
  if (!storageAvailable) return { data: memory ?? defaultSave(), fresh: !memory };
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (!raw) return { data: defaultSave(), fresh: true };
    const parsed = JSON.parse(raw) as Partial<SaveData>;
    if (!parsed || typeof parsed !== 'object' || parsed.version !== SAVE_VERSION) return { data: defaultSave(), fresh: true };
    const d = { ...defaultSave(), ...parsed, settings: { ...DEFAULT_SETTINGS, ...(parsed.settings ?? {}) } };
    return { data: d, fresh: false };
  } catch {
    return { data: defaultSave(), fresh: true };
  }
}

export function writeSave(d: SaveData): boolean {
  d.savedAt = Date.now();
  memory = d;
  if (!storageAvailable) return false;
  try {
    localStorage.setItem(SAVE_KEY, JSON.stringify(d));
    return true;
  } catch {
    // quota: drop photos and retry once
    try {
      localStorage.setItem(SAVE_KEY, JSON.stringify({ ...d, photos: {} }));
      return true;
    } catch {
      storageAvailable = false;
      return false;
    }
  }
}

export function clearSave() {
  memory = null;
  try { localStorage.removeItem(SAVE_KEY); } catch { /* ignore */ }
}
