// Vehicle and gameplay tuning. All units SI (m, kg, s, N) unless noted.
import type { SurfaceKind } from './world/layout';

export const PHYS_DT = 1 / 60;

export type VehicleId = 'scout' | 'toyota' | 'ranger';

/** chassis collider: cuboid half extents + centre (body space) and friction */
export interface ColliderBox { half: [number, number, number]; at: [number, number, number]; friction?: number }

export interface VehicleSpec {
  id: VehicleId;
  /** display name and one-line character description */
  name: string;
  /** short label for tabs */
  short: string;
  brand: string;
  tagline: string;
  model: string;
  /** reference body length with the fitted bumpers; tuning remains game-specific */
  bodyLength: number;
  suspension: 'coil' | 'leaf';
  /** default paint key and the paint keys offered for this vehicle */
  paint: string;
  paints: string[];
  mass: number;
  /** centre of mass in body space (body origin = mid-axle, static wheel-centre height) */
  com: [number, number, number];
  /** principal inertia about body X (pitch), Y (yaw), Z (roll) */
  inertia: [number, number, number];
  wheelBase: number;
  track: number;
  wheelRadius: number;
  wheelWidth: number;
  wheelMass: number;
  /** suspension hardpoint height above wheel centre at static ride */
  hardpointY: number;
  /** spring free length (hardpoint → wheel centre) */
  restLength: number;
  /** full bump: min length */
  minLength: number;
  springK: number;
  damperBump: number;
  damperRebound: number;
  bumpStopK: number;
  antiRollFront: number;
  antiRollRear: number;
  tyreLatK: number;
  tyreRelax: number;
  tyreLatDamp: number;
  tyreLongK: number;
  rollResist: number;
  highPeak: number;
  highMaxKmh: number;
  lowPeak: number;
  lowMaxKmh: number;
  reverseMaxKmh: number;
  reversePeak: number;
  brakeMax: number;
  engineBrakeLow: number;
  engineBrakeHigh: number;
  spinMu: number;
  mudDrag: number;
  steerMaxLow: number;
  steerMaxHigh: number;
  steerSpeedKmh: number;
  steerRate: number;
  steerReturnRate: number;
  throttleRise: number;
  throttleFall: number;
  waterWarnDepth: number;
  waterFailDepth: number;
  waterFailTime: number;
  colliders: ColliderBox[];
  /** capsule half length / radius for the solid axles */
  axleHalf: number;
  /** body-space winch fairlead (front) and recovery hitch (rear) */
  winchFront: [number, number, number];
  hitchRear: [number, number, number];
  /** engine sound: idle and max rpm, cylinder count (firing order pitch) */
  engine: { idle: number; max: number; cyl: number; tone: number };
  /** 0..1 rating bars on the vehicle select screen */
  ratings: { power: number; speed: number; grip: number; comfort: number; agility: number };
}

const SCOUT: VehicleSpec = {
  id: 'scout',
  name: 'Defender 90 · 林道探险',
  short: 'Defender',
  brand: 'LAND ROVER · 300Tdi',
  tagline: '短轴车身、整体桥螺旋弹簧，在窄林道和交叉轴中从容转向',
  model: 'vehicle_scout',
  bodyLength: 4.24,
  suspension: 'coil',
  paint: 'ochre',
  paints: ['ochre', 'cream', 'trail', 'pine'],
  mass: 1500,
  /** centre of mass in body space (body origin = mid-axle, static wheel-centre height) */
  com: [0, 0.2, 0.05],
  /** principal inertia about body X (pitch), Y (yaw), Z (roll) */
  inertia: [2500, 2700, 700],
  wheelBase: 2.36,
  track: 1.65,
  wheelRadius: 0.38,
  wheelWidth: 0.3,
  wheelMass: 22,
  /** suspension hardpoint height above wheel centre at static ride */
  hardpointY: 0.3,
  /** spring free length (hardpoint → wheel centre) */
  restLength: 0.42,
  /** full bump: min length */
  minLength: 0.12,
  springK: 30000,
  damperBump: 3600,
  damperRebound: 5200,
  bumpStopK: 260000,
  antiRollFront: 9000,
  antiRollRear: 6000,
  /** tyre brush model */
  tyreLatK: 60000,
  tyreRelax: 0.7,
  tyreLatDamp: 1800,
  tyreLongK: 90000,
  rollResist: 0.025,
  /** drive */
  highPeak: 5000,
  highMaxKmh: 31.5,
  lowPeak: 8000,
  lowMaxKmh: 10.5,
  reverseMaxKmh: 8.5,
  reversePeak: 6500,
  brakeMax: 5200,
  engineBrakeLow: 3200,
  engineBrakeHigh: 1000,
  /** wheel-spin: traction falls to this fraction when demand exceeds grip */
  spinMu: 0.8,
  /** speed-proportional suction drag in full mud, per vehicle (N per m/s) */
  mudDrag: 650,
  /** steering */
  steerMaxLow: 32,
  steerMaxHigh: 14,
  steerSpeedKmh: 30,
  steerRate: 95, // deg/s
  steerReturnRate: 140,
  throttleRise: 0.35,
  throttleFall: 0.18,
  /** water */
  waterWarnDepth: 0.55,
  waterFailDepth: 0.78,
  waterFailTime: 3,
  colliders: [
    { half: [0.92, 0.27, 0.8], at: [0, 0.32, 0] }, // belly and sliders between the arches (bottom 0.05)
    { half: [0.95, 0.24, 0.17], at: [0, 0.4, -1.87] }, // front bumper + winch
    { half: [0.94, 0.2, 0.17], at: [0, 0.34, 1.88] }, // rear bumper
    { half: [0.38, 0.38, 0.09], at: [0, 0.7, 2.1] }, // spare wheel
    { half: [0.92, 0.2, 1.7], at: [0, 0.68, 0.05] }, // tub between belt line and sills
    { half: [0.86, 0.34, 1.12], at: [0, 1.30, 0.64], friction: 0.5 }, // cabin
  ],
  axleHalf: 0.5,
  winchFront: [0, 0.324, -2.055],
  hitchRear: [0, 0.17, 2.01],
  engine: { idle: 780, max: 3600, cyl: 4, tone: 1 },
  ratings: { power: 0.55, speed: 0.6, grip: 0.6, comfort: 0.55, agility: 0.8 },
};

const TOYOTA: VehicleSpec = {
  ...SCOUT,
  id: 'toyota',
  name: 'Land Cruiser FJ60 · 远途旅行',
  short: 'Land Cruiser',
  brand: 'TOYOTA · FJ60',
  tagline: '经典四门旅行车，六缸扭矩与前后钢板弹簧，稳稳穿过浅溪和石滩',
  model: 'vehicle_toyota_trail',
  bodyLength: 4.78,
  suspension: 'leaf',
  paint: 'sand',
  paints: ['sand', 'white', 'red', 'pine'],
  mass: 1950,
  com: [0, 0.24, 0.02],
  inertia: [4200, 4400, 1000],
  wheelBase: 2.73,
  track: 1.76,
  wheelRadius: 0.44,
  wheelWidth: 0.3,
  wheelMass: 30,
  hardpointY: 0.32,
  // Extra travel is mostly droop; the larger tyre still needs bump clearance.
  // Static sag gives a lower stance while retaining bump and droop end stops.
  restLength: 0.51,
  minLength: 0.13,
  springK: 20000,
  damperBump: 4200,
  damperRebound: 5900,
  bumpStopK: 300000,
  antiRollFront: 10000,
  antiRollRear: 6500,
  tyreLatK: 72000,
  tyreRelax: 0.75,
  tyreLatDamp: 2100,
  tyreLongK: 105000,
  highPeak: 6300,
  highMaxKmh: 34,
  lowPeak: 10500,
  lowMaxKmh: 11,
  reverseMaxKmh: 8.5,
  reversePeak: 8000,
  brakeMax: 6700,
  engineBrakeLow: 4100,
  engineBrakeHigh: 1300,
  mudDrag: 820,
  steerMaxLow: 30,
  steerMaxHigh: 13,
  steerRate: 85,
  steerReturnRate: 130,
  // the snorkel lets it wade deeper
  waterWarnDepth: 0.7,
  waterFailDepth: 0.95,
  colliders: [
    { half: [0.95, 0.26, 1.35], at: [0, 0.41, 0] }, // belly (bottom 0.15)
    { half: [1.0, 0.34, 0.22], at: [0, 0.53, -2.06] }, // V2 expedition bumper
    { half: [0.95, 0.36, 0.31], at: [0, 0.54, 2.17] }, // bumper and spare
    { half: [0.9, 0.26, 2.05], at: [0, 0.62, 0.07] }, // retained V2 tub
    { half: [0.83, 0.29, 1.38], at: [0, 1.17, 0.72], friction: 0.5 }, // refined greenhouse
    { half: [0.82, 0.14, 1.35], at: [0, 1.6, 0.66] }, // retained roof load
  ],
  axleHalf: 0.53,
  winchFront: [0, 0.33, -2.231],
  hitchRear: [0, 0.225, 2.32],
  engine: { idle: 700, max: 3300, cyl: 6, tone: 0.82 },
  ratings: { power: 0.85, speed: 0.65, grip: 0.7, comfort: 0.85, agility: 0.45 },
};

const RANGER: VehicleSpec = {
  ...SCOUT,
  id: 'ranger',
  name: 'Hilux RN46 · 溪谷轻骑',
  short: 'Hilux',
  brand: 'TOYOTA · 1979 4WD',
  tagline: '轻巧单排皮卡，独立货斗与钢板弹簧，油门轻快、起伏反馈清晰',
  model: 'vehicle_ranger',
  bodyLength: 5.00,
  suspension: 'leaf',
  paint: 'mint',
  paints: ['mint', 'cream', 'red', 'sky'],
  mass: 1320,
  com: [0, 0.22, -0.08],
  inertia: [2550, 2550, 600],
  wheelBase: 2.80,
  track: 1.58,
  wheelRadius: 0.36,
  wheelWidth: 0.27,
  wheelMass: 20,
  hardpointY: 0.3,
  restLength: 0.43,
  minLength: 0.13,
  springK: 25000,
  damperBump: 2900,
  damperRebound: 4200,
  bumpStopK: 240000,
  antiRollFront: 7000,
  antiRollRear: 4000,
  tyreLatK: 52000,
  tyreRelax: 0.65,
  tyreLatDamp: 1500,
  tyreLongK: 80000,
  rollResist: 0.022,
  highPeak: 4600,
  highMaxKmh: 38,
  lowPeak: 6700,
  lowMaxKmh: 10,
  reverseMaxKmh: 9,
  reversePeak: 5500,
  brakeMax: 4700,
  engineBrakeLow: 2600,
  engineBrakeHigh: 900,
  spinMu: 0.76,
  mudDrag: 600,
  steerMaxLow: 33,
  steerMaxHigh: 15,
  steerRate: 105,
  steerReturnRate: 150,
  waterWarnDepth: 0.48,
  waterFailDepth: 0.7,
  colliders: [
    { half: [0.82, 0.33, 0.86], at: [0, 0.45, 0] }, // belly between the arches (bottom 0.12)
    { half: [0.85, 0.27, 0.16], at: [0, 0.49, -2.11] }, // front overhang
    { half: [0.84, 0.24, 0.17], at: [0, 0.475, 2.46] }, // rear bumper
    { half: [0.78, 0.29, 0.62], at: [0, 1.11, -0.14], friction: 0.5 }, // cab
    { half: [0.83, 0.20, 0.97], at: [0, 0.64, 1.51] }, // bed
  ],
  axleHalf: 0.48,
  winchFront: [0, 0.324, -2.295],
  hitchRear: [0, 0.17, 2.70],
  engine: { idle: 850, max: 4600, cyl: 4, tone: 1.22 },
  ratings: { power: 0.45, speed: 0.9, grip: 0.5, comfort: 0.4, agility: 0.9 },
};

export const VEHICLES: Record<VehicleId, VehicleSpec> = { scout: SCOUT, toyota: TOYOTA, ranger: RANGER };
export const VEHICLE_ORDER: VehicleId[] = ['scout', 'toyota', 'ranger'];
/** default vehicle (the first-version car) */
export const VEHICLE = SCOUT;

export interface SurfaceParams {
  mu: number;
  roll: number;
  /** how far the tyre sinks into the surface (m) */
  sink: number;
  /** relative tyre vibration / bumpiness used by audio & camera */
  rough: number;
}

export const SURFACES: Record<SurfaceKind, SurfaceParams> = {
  dirt: { mu: 1.0, roll: 1.0, sink: 0, rough: 0.3 },
  grass: { mu: 0.86, roll: 1.35, sink: 0.01, rough: 0.2 },
  gravel: { mu: 0.84, roll: 1.25, sink: 0.01, rough: 0.8 },
  rock: { mu: 1.02, roll: 0.8, sink: 0, rough: 1.0 },
  mud: { mu: 0.42, roll: 4.5, sink: 0.07, rough: 0.1 },
};

/** all-terrain tyre upgrade */
export const UPGRADE_MUD_MU = 1.14;
export const UPGRADE_ALL_MU = 1.05;

export const WINCH = {
  range: 18,
  reelSpeed: 0.75,
  maxForce: 11000,
  ropeK: 42000,
  ropeDamp: 2500,
  minLength: 3.5,
};

export const GAME = {
  stuckToolsHint: 8,
  stuckResetHint: 20,
  resetHold: 1.0,
  recordSpeedKmh: 1.2,
  safePointSpacing: 35,
};
