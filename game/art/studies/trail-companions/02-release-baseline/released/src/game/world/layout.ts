// Hand-authored layout of the "Pine Creek Loop" (松溪环线).
// World units are metres. +X east, +Z south, +Y up. North = -Z.
// Heights (third value) are authored road elevations at control points.

export type SurfaceKind = 'dirt' | 'grass' | 'gravel' | 'rock' | 'mud';

export interface RoadDef {
  id: string;
  name: string;
  /** [x, z, y] control points */
  points: [number, number, number][];
  width: number;
  closed?: boolean;
  surface: SurfaceKind;
  /** vertical bump amplitude of the road surface (m) */
  roughness: number;
  /** max grade in degrees the profile solver may produce */
  maxGrade: number;
  /** whether this road is part of the default loop (used for safe points / autopilot) */
  main?: boolean;
}

export interface SurfaceZone {
  kind: SurfaceKind;
  /** capsule polyline in x/z */
  line: [number, number][];
  radius: number;
  /** extra depression of the terrain (m), used for mud holes */
  sink?: number;
}

export interface LandmarkDef {
  id: 'camp' | 'cabin' | 'creek' | 'ridge' | 'park' | 'canyon' | 'aframe' | 'boathouse';
  name: string;
  subtitle: string;
  /** parking zone */
  x: number;
  z: number;
  radius: number;
  /** the camera shot used for the journal photo */
  shot: { pos: [number, number, number]; target: [number, number, number] };
  isGoal: boolean;
}

export interface AnchorDef {
  id: string;
  x: number;
  z: number;
  kind: 'tree' | 'rock';
}

export interface PropDef {
  model: string;
  x: number;
  z: number;
  /** yaw in degrees, 0 = model front faces north (-Z) */
  yaw: number;
  scale?: number;
  /** height offset relative to terrain */
  dy?: number;
  collider?: 'box' | 'none' | 'cylinder';
  /** half extents for box colliders (model space, metres) */
  half?: [number, number, number];
  /** flatten terrain under the prop within radius */
  flatten?: number;
  /** absolute height (ignores the terrain), e.g. piers over water */
  absY?: number;
  /** extra colliders in model space: boxes [cx, cy, cz, hx, hy, hz] */
  boxes?: [number, number, number, number, number, number][];
}

export const WORLD_SIZE = 640;
export const WORLD_HALF = WORLD_SIZE / 2;
export const LAKE_LEVEL = 0;

export const LAKE = { cx: -22, cz: 112, rx: 86, rz: 50, bed: -3.5 };

/** Stream from the northern ridge into the lake. [x, z, bedHeight, waterDepth] */
export const STREAM: [number, number, number, number][] = [
  [-50, -330, 34, 0.3],
  [-38, -292, 29, 0.32],
  [-52, -250, 24, 0.36],
  [-30, -212, 18, 0.4],
  [-40, -175, 13, 0.42],
  [-22, -140, 9.5, 0.45],
  [-32, -110, 6.4, 0.45],
  [-16, -82, 4.5, 0.48],
  [-24, -52, 2.8, 0.45],
  [-18, -18, 1.55, 0.26], // ford at C
  [-24, 20, 0.6, 0.7],
  [-20, 62, -0.9, 0.9],
];
export const STREAM_WIDTH = 7;

export const ROADS: RoadDef[] = [
  {
    id: 'loop',
    name: '松溪环线',
    closed: true,
    width: 4.6,
    surface: 'dirt',
    roughness: 0.07,
    maxGrade: 17,
    main: true,
    points: [
      [-170, 160, 4.2], // A camp
      [-188, 124, 5.0],
      [-199, 82, 6.0],
      [-197, 40, 7.2],
      [-203, 2, 10.6], // small rocky slope
      [-197, -40, 13.0],
      [-181, -78, 14.2],
      [-160, -99, 14.6], // B cabin clearing
      [-134, -101, 13.6],
      [-110, -88, 11.8],
      [-82, -70, 9.0], // roots
      [-56, -48, 5.6],
      [-36, -28, 3.1],
      [-18, -18, 1.55], // C ford
      [4, -17, 2.5],
      [34, -12, 3.6],
      [64, -8, 4.2], // mud patch
      [95, -12, 5.2],
      [124, -16, 6.4], // D fork
      [101, -44, 8.6], // gravel detour
      [82, -74, 11.4],
      [92, -104, 14.6],
      [119, -114, 17.2],
      [143, -106, 19.5], // J1 (mud shortcut joins)
      [160, -130, 23.8],
      [170, -164, 28.6], // J2 (rock shortcut splits)
      [148, -178, 31.6], // switchback
      [134, -200, 34.8],
      [149, -222, 38.0],
      [174, -210, 40.2], // E ridge lookout
      [201, -204, 39.0],
      [228, -180, 35.6],
      [241, -132, 29.0],
      [234, -72, 22.0],
      [222, -12, 15.0],
      [208, 48, 9.4],
      [180, 104, 5.4],
      [136, 146, 3.2],
      [86, 166, 2.5],
      [40, 170, 2.2], // F lakeshore
      [0, 176, 2.3],
      [-50, 180, 2.6],
      [-100, 184, 3.0],
      [-140, 184, 3.6],
    ],
  },
  {
    id: 'mudShortcut',
    name: '泥坡近路',
    width: 3.3,
    surface: 'mud',
    roughness: 0.09,
    maxGrade: 17,
    points: [
      [124, -16, 6.4],
      [127, -34, 7.4],
      [131, -58, 11.4],
      [136, -82, 15.6],
      [143, -106, 19.5],
    ],
  },
  {
    id: 'rockShortcut',
    name: '岩阶近路',
    width: 3.2,
    surface: 'rock',
    roughness: 0.05,
    maxGrade: 25,
    points: [
      [170, -164, 28.6],
      [171, -176, 31.0],
      [173, -192, 36.2],
      [174, -210, 40.2],
    ],
  },
  {
    id: 'millSpur',
    name: '旧锯木场支路',
    width: 3.4,
    surface: 'dirt',
    roughness: 0.09,
    maxGrade: 14,
    points: [
      [-110, -88, 11.8],
      [-104, -110, 14.0],
      [-99, -132, 16.6],
      [-96, -146, 17.6],
    ],
  },
  {
    id: 'campPad',
    name: '营地',
    width: 9,
    surface: 'dirt',
    roughness: 0.03,
    maxGrade: 6,
    points: [
      [-170, 160, 4.2],
      [-180, 172, 4.3],
    ],
  },
  {
    id: 'creekPad',
    name: '石滩停车处',
    width: 7,
    surface: 'gravel',
    roughness: 0.04,
    maxGrade: 8,
    points: [
      [4, -17, 2.5],
      [8, -27, 2.3],
    ],
  },
  {
    id: 'cabinPad',
    name: '小屋前空地',
    width: 8,
    surface: 'dirt',
    roughness: 0.03,
    maxGrade: 8,
    points: [
      [-160, -99, 14.6],
      [-153, -110, 15.2],
    ],
  },
  {
    id: 'parkSpur',
    name: '训练场支路',
    width: 4.4,
    surface: 'dirt',
    roughness: 0.05,
    maxGrade: 10,
    points: [
      [-156, 178, 3.8],
      [-160, 192, 5.0],
      [-165, 205, 6.4],
    ],
  },
  {
    id: 'park',
    name: '越野训练场',
    closed: true,
    width: 5.2,
    surface: 'dirt',
    roughness: 0.03,
    maxGrade: 24,
    points: [
      [-165, 205, 6.4], // start / finish gate
      [-140, 212, 7.2], // crater field →
      [-100, 216, 8.6],
      [-72, 230, 10.2], // cross-axle moguls →
      [-66, 255, 12.2],
      [-75, 280, 13.4], // steep climb (low range) →
      [-105, 292, 22.4],
      [-135, 290, 22.6], // side slope on the plateau
      [-165, 282, 16.4], // whoops on the descent →
      [-190, 262, 13.6],
      [-196, 235, 10.8], // washboard, then log steps
      [-185, 212, 7.6], // rock garden
    ],
  },
  {
    id: 'canyon',
    name: '赤岩峡谷',
    width: 4.4,
    surface: 'dirt',
    roughness: 0.07,
    maxGrade: 12,
    points: [
      [-160, -99, 14.6],
      [-175, -120, 16.6],
      [-195, -140, 19.4],
      [-215, -165, 22.4],
      [-230, -192, 25.0],
      [-237, -215, 26.2], // plank bridge over the dry gully
      [-246, -240, 27.4],
      [-262, -262, 28.6],
    ],
  },
  {
    id: 'canyonPad',
    name: '峡谷尽头',
    width: 11,
    surface: 'gravel',
    roughness: 0.03,
    maxGrade: 8,
    points: [
      [-262, -262, 28.6],
      [-272, -276, 28.8],
    ],
  },
  {
    id: 'boatPad',
    name: '船屋小径',
    width: 5,
    surface: 'gravel',
    roughness: 0.03,
    maxGrade: 8,
    points: [
      [-72, 182, 2.9],
      [-72, 170, 2.2],
      [-72, 161, 1.7],
    ],
  },
  {
    id: 'ridgePad',
    name: '望台停车处',
    width: 9,
    surface: 'gravel',
    roughness: 0.03,
    maxGrade: 8,
    points: [
      [174, -210, 40.2],
      [180, -218, 40.3],
    ],
  },
];

export const SURFACE_ZONES: SurfaceZone[] = [
  // A→B small rocky slope: gravel with embedded rocks
  { kind: 'gravel', line: [[-199, 22], [-201, -18]], radius: 5.5 },
  // B→C roots and stone steps: rocky dirt
  { kind: 'rock', line: [[-90, -76], [-74, -63]], radius: 3.2 },
  // C ford bed
  { kind: 'gravel', line: [[-30, -21], [-4, -17]], radius: 5.2 },
  { kind: 'gravel', line: [[-18, -60], [-19, 40]], radius: 3.6 },
  // C→D first mud patch
  { kind: 'mud', line: [[50, -9], [82, -9]], radius: 4.2, sink: 0.12 },
  // D gravel detour
  { kind: 'gravel', line: [[112, -28], [101, -44], [82, -74], [92, -104], [119, -114], [136, -108]], radius: 3.6 },
  // Mud shortcut body is 'mud' via road surface; wetter core
  { kind: 'mud', line: [[128, -40], [134, -74]], radius: 3.4, sink: 0.1 },
  // Ridge switchback: gravel
  { kind: 'gravel', line: [[160, -168], [148, -178], [134, -200], [149, -222], [165, -214]], radius: 3.6 },
  // Lake shore sand/gravel
  { kind: 'gravel', line: [[20, 172], [60, 169]], radius: 3.5 },
];

/** Terrain relief along a road between two points (nearest arc lengths). */
export type FeatureKind = 'craters' | 'potholes' | 'crossAxle' | 'washboard' | 'whoops' | 'bank';

export interface TerrainFeature {
  kind: FeatureKind;
  road: string;
  from: [number, number];
  to: [number, number];
  /** height scale (m): crater depth, mogul height, ripple amplitude; bank: degrees */
  amp: number;
  /** wavelength / spacing along the road (m) */
  wave?: number;
  /** number of craters / potholes */
  count?: number;
  /** crater radius range (m) */
  r?: [number, number];
  /** autopilot speed limit through the feature (km/h) */
  kmh: number;
  seed?: number;
  /** display name (HUD / map) */
  name: string;
}

export const FEATURES: TerrainFeature[] = [
  // trail park course
  { kind: 'craters', road: 'park', from: [-146, 211], to: [-102, 216], amp: 0.68, count: 11, r: [2.1, 3.3], kmh: 8, seed: 3, name: '炮弹坑群' },
  { kind: 'crossAxle', road: 'park', from: [-73, 232], to: [-67, 262], amp: 0.42, wave: 3.4, kmh: 6, name: '交叉轴' },
  { kind: 'bank', road: 'park', from: [-108, 292], to: [-132, 290], amp: 15, kmh: 7, name: '侧倾坡' },
  { kind: 'whoops', road: 'park', from: [-160, 284], to: [-188, 264], amp: 0.26, wave: 5.2, kmh: 10, name: '连续起伏' },
  { kind: 'washboard', road: 'park', from: [-191, 258], to: [-196, 240], amp: 0.07, wave: 1.5, kmh: 12, name: '搓板路' },
  // main loop and shortcuts
  { kind: 'potholes', road: 'loop', from: [-199, 80], to: [-197, 44], amp: 0.22, count: 9, r: [1.2, 1.8], kmh: 14, seed: 7, name: '坑洼路' },
  { kind: 'washboard', road: 'loop', from: [100, -46], to: [84, -72], amp: 0.05, wave: 1.4, kmh: 16, name: '搓板碎石路' },
  { kind: 'crossAxle', road: 'loop', from: [80, 167], to: [52, 169], amp: 0.18, wave: 3.6, kmh: 10, name: '湖岸车辙' },
  { kind: 'potholes', road: 'canyon', from: [-178, -123], to: [-210, -160], amp: 0.2, count: 7, r: [1.3, 2.0], kmh: 12, seed: 11, name: '峡谷坑洼' },
];

/** Plank bridge over the dry gully in the canyon (deck follows z = -sag * (1 - (u/half)^2)). */
export const BRIDGE = { road: 'canyon', x: -237, z: -215, half: 13, width: 3.6, sag: 0.25, gullyDepth: 6.5, gullyHalf: 9.5 };

/** Trail park timing gates on the park loop, in driving order; the first is start/finish. */
export const PARK_GATES: [number, number][] = [
  [-160, 207], [-100, 216], [-67, 262], [-105, 292], [-135, 290], [-190, 262], [-196, 236], [-184, 212],
];

/** Shader / scatter zones: red sandstone ground, autumn woods, golden meadows [x, z, radius]. */
export const RED_ZONES: [number, number, number][] = [[-215, -175, 55], [-252, -238, 50], [-190, -140, 32]];
export const AUTUMN_ZONES: [number, number, number][] = [[215, 20, 95], [140, 60, 55], [220, -110, 60], [-120, 250, 80]];
export const MEADOW_ZONES: [number, number, number][] = [[140, 60, 42], [-120, 250, 70], [-22, 10, 26], [-60, 30, 22], [185, 78, 22]];

/** Grazing spots for deer herds [x, z, radius, count]; eagle circles [x, z, radius, height]. */
export const DEER_HERDS: [number, number, number, number][] = [[132, 58, 22, 4], [-30, 22, 14, 3], [-120, 246, 26, 4], [-60, 32, 12, 2], [190, 92, 12, 3]];
export const EAGLES: [number, number, number, number][] = [[-20, 90, 70, 58], [160, -170, 55, 78], [-230, -220, 45, 70]];

export const LANDMARKS: LandmarkDef[] = [
  {
    id: 'camp',
    name: '松溪营地',
    subtitle: '旅程的起点与终点',
    x: -176,
    z: 168,
    radius: 16,
    shot: { pos: [-160, 9, 150], target: [-186, 5, 180] },
    isGoal: false,
  },
  {
    id: 'cabin',
    name: '林窗小屋',
    subtitle: '暖光里的旧木屋',
    x: -155,
    z: -107,
    radius: 15,
    shot: { pos: [-170, 19, -90], target: [-143, 17, -125] },
    isGoal: true,
  },
  {
    id: 'creek',
    name: '浅溪石滩',
    subtitle: '清浅溪水漫过卵石',
    x: 6,
    z: -25,
    radius: 13,
    shot: { pos: [18, 6.5, -40], target: [-18, 2, -6] },
    isGoal: true,
  },
  {
    id: 'ridge',
    name: '山脊望台',
    subtitle: '回望湖谷与来路',
    x: 178,
    z: -214,
    radius: 15,
    shot: { pos: [168, 46, -222], target: [40, 5, 60] },
    isGoal: true,
  },
  {
    id: 'park',
    name: '越野训练场',
    subtitle: '弹坑、交叉轴与原木台阶',
    x: -160,
    z: 207,
    radius: 12,
    shot: { pos: [-128, 30, 300], target: [-120, 12, 232] },
    isGoal: false,
  },
  {
    id: 'canyon',
    name: '赤岩吊桥',
    subtitle: '砂岩峡谷上的木板桥',
    x: -266,
    z: -268,
    radius: 14,
    shot: { pos: [-222, 34, -200], target: [-246, 24, -238] },
    isGoal: false,
  },
  {
    id: 'aframe',
    name: '秋色木屋',
    subtitle: '红枫林里的 A 字屋',
    x: 196,
    z: 72,
    radius: 13,
    shot: { pos: [214, 9, 52], target: [178, 7, 80] },
    isGoal: false,
  },
  {
    id: 'boathouse',
    name: '湖畔船屋',
    subtitle: '长栈桥尽头的高脚小屋',
    x: -72,
    z: 176,
    radius: 13,
    shot: { pos: [-40, 6, 150], target: [-72, 2, 138] },
    isGoal: false,
  },
];

export const TOOLBOX = { x: -95, z: -143 };

export const ANCHORS: AnchorDef[] = [
  // C→D mud patch
  { id: 'mudA1', x: 48, z: -17, kind: 'tree' },
  { id: 'mudA2', x: 88, z: -2, kind: 'tree' },
  { id: 'mudA3', x: 72, z: -18, kind: 'rock' },
  // mud shortcut
  { id: 'mudS1', x: 121, z: -44, kind: 'tree' },
  { id: 'mudS2', x: 142, z: -66, kind: 'rock' },
  { id: 'mudS3', x: 145, z: -93, kind: 'tree' },
  { id: 'mudS4', x: 130, z: -99, kind: 'tree' },
  // rock steps
  { id: 'rock1', x: 179, z: -181, kind: 'rock' },
  { id: 'rock2', x: 166, z: -199, kind: 'tree' },
  { id: 'rock3', x: 181, z: -203, kind: 'tree' },
  // creek ford
  { id: 'ford1', x: -8, z: -8, kind: 'tree' },
  { id: 'ford2', x: -30, z: -34, kind: 'tree' },
  // roots section
  { id: 'root1', x: -90, z: -64, kind: 'tree' },
  { id: 'root2', x: -70, z: -74, kind: 'tree' },
  // rocky slope A→B
  { id: 'slope1', x: -208, z: -24, kind: 'tree' },
  { id: 'slope2', x: -192, z: 10, kind: 'tree' },
  // trail park: steep climb and crater field
  { id: 'park1', x: -82, z: 292, kind: 'rock' },
  { id: 'park2', x: -112, z: 300, kind: 'tree' },
  { id: 'park3', x: -122, z: 222, kind: 'tree' },
  // canyon
  { id: 'can1', x: -205, z: -145, kind: 'rock' },
  { id: 'can2', x: -259, z: -245, kind: 'rock' },
  // switchback
  { id: 'sw1', x: 128, z: -190, kind: 'tree' },
  { id: 'sw2', x: 158, z: -230, kind: 'rock' },
];

/** Clearings keep trees away (x, z, radius). */
export const CLEARINGS: [number, number, number][] = [
  [-182, 176, 34], // camp
  [-150, -112, 30], // cabin
  [4, -26, 20], // creek beach
  [-18, -30, 22], // ford valley
  [-22, 10, 18], // lower creek meadow
  [180, -216, 26], // lookout
  [-98, -146, 14], // sawmill
  [30, 165, 16], // lakeshore opening
  // open the lake side of the return road so the water stays in view
  [-95, 170, 18], [-50, 166, 22], [-5, 162, 22], [45, 158, 20], [90, 150, 20], [125, 135, 16],
  [-60, 30, 24], // meadow north of lake
  [120, 60, 30], // east meadow
  [-120, 100, 22],
  [200, -60, 18],
  // trail park field, canyon floor, autumn meadow, boathouse shore
  [-120, 248, 46], [-165, 225, 20], [-85, 265, 18], [-150, 285, 16],
  [-240, -225, 16], [-262, -266, 18],
  [180, 76, 18], [140, 60, 36],
  [-72, 168, 14],
];

/** View corridors from landmarks: [x, z, dirX, dirZ, halfAngleDeg, length, eyeHeight].
 * Trees whose tops would rise above the sight line are not planted. */
export const VIEW_CONES: [number, number, number, number, number, number, number][] = [
  [178, -214, -0.523, 0.852, 24, 340, 5], // ridge → lake valley
  [-155, -107, 0.45, -0.89, 34, 45, 3], // cabin frontage
  [6, -25, -0.9, 0.2, 40, 45, 2.5], // creek beach → ford
  [-176, 168, 0.55, -0.83, 30, 60, 3], // camp → first bend
];

export const PROPS: PropDef[] = [
  // camp
  { model: 'tent', x: -190, z: 184, yaw: 150, collider: 'box', half: [1.3, 0.8, 1.6], flatten: 4 },
  { model: 'campfire', x: -181, z: 185, yaw: 0, collider: 'cylinder', half: [0.8, 0.3, 0.8], flatten: 3 },
  { model: 'bench_log', x: -178, z: 188, yaw: 80, collider: 'none' },
  { model: 'bench_log', x: -184, z: 189, yaw: 20, collider: 'none' },
  { model: 'picnic_table', x: -195, z: 172, yaw: 30, collider: 'box', half: [0.9, 0.4, 1.0], flatten: 3 },
  { model: 'signpost', x: -164, z: 150, yaw: 200, collider: 'cylinder', half: [0.15, 1.2, 0.15] },
  // cabin
  { model: 'cabin', x: -143, z: -124, yaw: 210, collider: 'box', half: [3.6, 3, 4.6], flatten: 9 },
  { model: 'fence', x: -134, z: -113, yaw: 120, collider: 'none' },
  { model: 'fence', x: -131, z: -116, yaw: 120, collider: 'none' },
  // creek
  { model: 'signpost', x: 12, z: -12, yaw: 90, collider: 'cylinder', half: [0.15, 1.2, 0.15] },
  // ridge lookout
  { model: 'lookout', x: 184, z: -226, yaw: 200, collider: 'box', half: [4.5, 1.5, 3.5], flatten: 8 },
  { model: 'signpost', x: 166, z: -168, yaw: 160, collider: 'cylinder', half: [0.15, 1.2, 0.15] },
  // D fork
  { model: 'signpost', x: 119, z: -8, yaw: 60, collider: 'cylinder', half: [0.15, 1.2, 0.15] },
  // sawmill
  { model: 'shed', x: -100, z: -153, yaw: 190, collider: 'box', half: [3.2, 2, 2.4], flatten: 7 },
  // lake dock
  { model: 'dock', x: 24, z: 157, yaw: 0, collider: 'none', dy: -0.45 },
  // camp at night: camper, firewood, lanterns and string light poles (strings in areas.ts)
  { model: 'camper', x: -201, z: 160, yaw: 120, collider: 'box', half: [1.1, 1.25, 2.1], flatten: 4 },
  { model: 'firewood', x: -185, z: 190, yaw: 25, collider: 'none' },
  { model: 'crate_stack', x: -204, z: 172, yaw: 10, collider: 'box', half: [0.8, 0.6, 0.6] },
  { model: 'canoe_rack', x: -207, z: 180, yaw: 70, collider: 'box', half: [2.1, 0.7, 0.9] },
  { model: 'lantern', x: -189.6, z: 181.2, yaw: 0, collider: 'none' },
  { model: 'lantern', x: -178.2, z: 186.6, yaw: 40, collider: 'none' },
  { model: 'string_pole', x: -200, z: 166, yaw: 0, collider: 'cylinder', half: [0.08, 1.3, 0.08] },
  { model: 'string_pole', x: -201, z: 189, yaw: 0, collider: 'cylinder', half: [0.08, 1.3, 0.08] },
  { model: 'string_pole', x: -176, z: 195, yaw: 0, collider: 'cylinder', half: [0.08, 1.3, 0.08] },
  { model: 'string_pole', x: -172, z: 179, yaw: 0, collider: 'cylinder', half: [0.08, 1.3, 0.08] },
  // lakeside boathouse on its pier, rowboat, canoes
  { model: 'boathouse', x: -72, z: 158, yaw: 0, collider: 'none', absY: 1.45 },
  { model: 'rowboat', x: -63, z: 142, yaw: 28, collider: 'none', absY: 0.02 },
  { model: 'lamp_post', x: -77, z: 166, yaw: 0, collider: 'cylinder', half: [0.12, 1.5, 0.12] },
  { model: 'canoe_rack', x: -64, z: 168, yaw: 10, collider: 'box', half: [2.1, 0.7, 0.9] },
  // autumn A-frame cabin facing the east road
  { model: 'aframe_cabin', x: 178, z: 76, yaw: -78, collider: 'none', flatten: 10, boxes: [[0, 3.6, 1.35, 3.4, 3.6, 3.3]] },
  { model: 'lamp_post', x: 186, z: 70, yaw: -78, collider: 'cylinder', half: [0.12, 1.5, 0.12] },
  { model: 'firewood', x: 176, z: 84, yaw: 12, collider: 'none' },
  { model: 'signpost', x: 198, z: 62, yaw: -80, collider: 'cylinder', half: [0.15, 1.2, 0.15] },
  // trail park entrance
  { model: 'signpost', x: -152, z: 196, yaw: 20, collider: 'cylinder', half: [0.15, 1.2, 0.15] },
];
