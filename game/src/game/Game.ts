// Game bootstrap and main loop: builds the world, runs fixed-step physics,
// interpolated rendering, camera and gameplay systems.
import * as pc from 'playcanvas';
import { Terrain } from './world/terrain';
import { scatter, TREE_MODELS, UNDER_MODELS, ROCK_MODELS, GRASS_MODELS, HAS_LOD1, type ScatterResult } from './world/scatter';
import { PROPS, WORLD_HALF } from './world/layout';
import { Physics, initRapier } from './physics/physics';
import { Vehicle } from './physics/vehicle';
import { PHYS_DT, VEHICLES, VEHICLE_ORDER, type VehicleId } from './config';
import { Input, type InputFrame } from './input';
import { FollowCamera } from './camera';
import { ModelLibrary } from './render/models';
import { TerrainRender } from './render/terrainRender';
import { InstancedLayer } from './render/forest';
import { Mountains } from './render/sky';
import { Wildlife } from './render/wildlife';
import { Environment } from './render/environment';
import { NightLights } from './render/nightLights';
import { WIND, applyWind, updateWind } from './render/wind';
import { VehicleView, type VehicleInfo } from './render/vehicleView';
import { WaterRender } from './render/water';
import { store } from './store';

export interface GameHooks {
  /** per-frame systems (journey, winch, fx, audio) */
  frame: ((dt: number, inp: InputFrame) => void)[];
  /** per physics step systems */
  step: ((dt: number) => void)[];
}

const nextFrame = () => new Promise((r) => setTimeout(r, 0));

export class Game {
  app!: pc.Application;
  terrain!: Terrain;
  scatter!: ScatterResult;
  phys!: Physics;
  vehicle!: Vehicle;
  view!: VehicleView;
  cam!: FollowCamera;
  input!: Input;
  lib!: ModelLibrary;
  terrainRender!: TerrainRender;
  layers: InstancedLayer[] = [];
  water!: WaterRender;
  hooks: GameHooks = { frame: [], step: [] };
  acc = 0;
  alpha = 0;
  paused = false;
  frameInput: InputFrame = { drive: 0, steer: 0, handbrake: false, digital: true, lookX: 0, lookY: 0, zoom: 0, lookActive: false };
  simTime = 0;
  fpsAcc = 0;
  fpsFrames = 0;
  cameraFrame: pc.CameraFrame | null = null;
  sun!: pc.Entity;
  env!: Environment;
  nightLights!: NightLights;
  mountains!: Mountains;
  wildlife!: Wildlife;
  private time = 0;
  /** set by the debug API to drive the car */
  inputOverride: ((f: InputFrame) => void) | null = null;
  quality: 'low' | 'medium' | 'high' = 'high';
  vehicleId: VehicleId = 'scout';
  vehicleInfos = new Map<VehicleId, VehicleInfo>();
  /** called after the player's vehicle was replaced (winch, lights, audio rebind) */
  onVehicleChanged: (() => void)[] = [];

  constructor(public canvas: HTMLCanvasElement) {}

  async init(progress: (p: number, text: string) => void, vehicleId: VehicleId = 'scout') {
    this.vehicleId = VEHICLES[vehicleId] ? vehicleId : 'scout';
    progress(0.02, '加载物理引擎…');
    await initRapier();
    progress(0.08, '生成地形与道路…');
    await nextFrame();
    this.terrain = new Terrain();
    progress(0.22, '种植森林…');
    await nextFrame();
    this.scatter = scatter(this.terrain);
    this.phys = new Physics(this.terrain);
    this.phys.addCylinders(this.scatter.cylinders);
    this.phys.addBoxes(this.scatter.boxes);
    this.phys.addOriented(this.scatter.areas.oriented);
    this.phys.addCapsules(this.scatter.areas.capsules);
    this.addPropColliders();

    progress(0.3, '启动渲染器…');
    const app = new pc.Application(this.canvas, {
      graphicsDeviceOptions: { antialias: false, powerPreference: 'high-performance', alpha: false },
    });
    this.app = app;
    app.setCanvasFillMode(pc.FILLMODE_FILL_WINDOW);
    app.setCanvasResolution(pc.RESOLUTION_AUTO);
    app.graphicsDevice.maxPixelRatio = Math.min(window.devicePixelRatio, 1.5);
    window.addEventListener('resize', this.onResize);
    // clustered lighting: headlights, campfires and lanterns at night
    const lp = app.scene.lighting;
    lp.shadowsEnabled = true;
    lp.cookiesEnabled = true;
    lp.shadowAtlasResolution = 2048;
    lp.cookieAtlasResolution = 1024;
    lp.maxLightsPerCell = 12;
    lp.cells = new pc.Vec3(16, 6, 16);
    app.start();

    this.env = new Environment(app);
    this.env.prewarm();
    this.sun = this.env.sun;
    this.mountains = new Mountains(app);

    progress(0.36, '加载模型…');
    this.lib = new ModelLibrary(app);
    const names = new Set<string>(VEHICLE_ORDER.map((id) => VEHICLES[id].model));
    await Promise.all(VEHICLE_ORDER.map(async (id) => {
      const spec = VEHICLES[id];
      let info: VehicleInfo | null = null;
      try {
        const res = await fetch(`assets/models/${spec.model}.json`);
        if (res.ok) info = (await res.json()) as VehicleInfo;
      } catch { /* fall back below */ }
      // without the sidecar the running gear uses generic mounts
      this.vehicleInfos.set(id, info ?? {
        id, wheelBase: spec.wheelBase, trackX: spec.track / 2, wheelRadius: spec.wheelRadius,
        spring: { x: spec.track / 2 - 0.27, top: 0.46, seat: 0.06 },
        driveshaft: { tcaseZ: 0.31, tcaseY: 0.1, pinionZ: 0.235, pinionY: 0.03 },
        lamps: { head: [[-0.66, 0.6, -spec.wheelBase / 2 - 0.62], [0.66, 0.6, -spec.wheelBase / 2 - 0.62]] },
      });
    }));
    for (const m of [...TREE_MODELS, ...UNDER_MODELS, ...GRASS_MODELS]) { names.add(m); if (HAS_LOD1.has(m)) names.add(`${m}_lod1`); }
    for (const r of ROCK_MODELS) names.add(r);
    for (const p of PROPS) names.add(p.model);
    for (const p of this.scatter.areas.placed) names.add(p.model);
    names.add('toolbox');
    for (const n of ['deer_stag', 'deer_doe', 'eagle']) names.add(n);
    await this.lib.load([...names], (d, t) => progress(0.36 + (d / t) * 0.4, `加载模型 ${d}/${t}`));

    progress(0.78, '铺设地表…');
    await nextFrame();
    this.terrainRender = new TerrainRender(app, this.terrain);
    this.water = new WaterRender(app, this.terrain);
    progress(0.84, '布置树木…');
    await nextFrame();
    this.applyWind();
    this.buildLayers();
    this.placeProps();
    this.env.glowMats = [...this.lib.glowMats];
    this.nightLights = new NightLights(app, this.scatter.areas, this.terrain);
    this.env.onChange.push(() => {
      this.nightLights.update(0, this.env.night);
      this.mountains.setLight(1 - this.env.night * 0.8);
    });
    this.wildlife = new Wildlife(app, this.lib, this.terrain);

    progress(0.92, '准备车辆…');
    const loop = this.terrain.roads.find((r) => r.def.id === 'loop')!;
    const p0 = loop.path.at(6);
    const yaw0 = Math.atan2(-p0.tx, -p0.tz);
    this.vehicle = new Vehicle(this.phys, p0.x, this.terrain.heightAt(p0.x, p0.z) + 0.45, p0.z, yaw0, VEHICLES[this.vehicleId]);
    this.view = new VehicleView(app, this.lib, this.vehicle, this.vehicleInfos.get(this.vehicleId)!);
    this.cam = new FollowCamera(app, this.phys);
    this.setupCameraFrame();
    this.input = new Input(this.canvas);
    this.cam.snap(this.vehicle, new pc.Vec3(p0.x, this.terrain.heightAt(p0.x, p0.z), p0.z));

    app.on('update', this.update);
    document.addEventListener('visibilitychange', this.onVisibility);
    progress(1, '完成');
  }

  private onResize = () => this.app.resizeCanvas();
  private onVisibility = () => {
    // returning from a hidden tab must not replay the backlog
    this.acc = 0;
    this.input?.clear();
  };

  setupCameraFrame() {
    const cf = new pc.CameraFrame(this.app, this.cam.entity.camera!);
    cf.rendering.toneMapping = pc.TONEMAP_ACES;
    cf.rendering.samples = 4;
    cf.rendering.sharpness = 0.25;
    cf.bloom.intensity = 0.012;
    cf.bloom.blurLevel = 6;
    cf.grading.enabled = true;
    cf.grading.saturation = 1.08;
    cf.grading.contrast = 1.06;
    cf.grading.brightness = 1.02;
    cf.vignette.intensity = 0.28;
    cf.vignette.inner = 0.55;
    cf.vignette.outer = 1.25;
    // MSAA keeps foliage edges crisp while driving; TAA smeared the foreground
    cf.taa.enabled = false;
    // Full-resolution AO avoids magnifying the sampling grid. More taps need
    // a gentler falloff than CameraFrame's default power of 6.
    cf.ssao.type = pc.SSAOTYPE_COMBINE;
    cf.ssao.intensity = 0.4;
    cf.ssao.radius = 1;
    cf.ssao.power = 2;
    cf.ssao.samples = 24;
    cf.ssao.scale = 1;
    cf.update();
    this.cameraFrame = cf;
  }

  applyQuality(q: 'low' | 'medium' | 'high') {
    this.quality = q;
    const cf = this.cameraFrame;
    const dev = this.app.graphicsDevice;
    dev.maxPixelRatio = q === 'high' ? Math.min(window.devicePixelRatio, 1.5) : q === 'medium' ? 1 : 0.8;
    this.app.resizeCanvas();
    if (cf) {
      cf.ssao.type = q === 'low' ? pc.SSAOTYPE_NONE : pc.SSAOTYPE_COMBINE;
      cf.ssao.samples = q === 'high' ? 24 : 16;
      cf.rendering.samples = q === 'low' ? 1 : 4;
      cf.bloom.intensity = q === 'low' ? 0 : 0.012;
      cf.update();
    }
    const light = this.sun.light!;
    light.shadowResolution = q === 'high' ? 2048 : q === 'medium' ? 1536 : 1024;
    light.numCascades = q === 'low' ? 2 : 3;
    light.shadowDistance = q === 'low' ? 90 : q === 'medium' ? 120 : 150;
    const scale = q === 'high' ? 1 : q === 'medium' ? 0.8 : 0.6;
    for (const l of this.layers) l.setDistanceScale(scale);
  }

  private buildLayers() {
    const app = this.app;
    const sc = this.scatter;
    this.layers.push(
      new InstancedLayer(app, this.lib, sc.trees, {
        chunk: 110,
        dist: [60, 150, 460],
        castShadows: [true, true, false],
        models: TREE_MODELS.map((t) => (HAS_LOD1.has(t) ? [t, `${t}_lod1`, `${t}_lod1`] : [t])),
        heightPad: 22,
      }, 'trees'),
    );
    this.layers.push(
      new InstancedLayer(app, this.lib, sc.under, {
        chunk: 60,
        dist: [40, 110],
        castShadows: [true, false],
        models: UNDER_MODELS.map((t) => (HAS_LOD1.has(t) ? [t, `${t}_lod1`] : [t])),
        heightPad: 2,
      }, 'under'),
    );
    this.layers.push(
      new InstancedLayer(app, this.lib, sc.grass, {
        chunk: 32,
        dist: [40, 75],
        castShadows: [false, false],
        // short tufts drop out at the first threshold; meadow grass keeps a far LOD
        models: GRASS_MODELS.map((t) => (t === 'grass_tall' ? [t, `${t}_lod1`] : [t, '__none'])),
        heightPad: 1.2,
      }, 'grass'),
    );
    this.layers.push(
      new InstancedLayer(app, this.lib, sc.rocks, {
        chunk: 60,
        dist: [260],
        castShadows: [true],
        models: ROCK_MODELS.map((t) => [t]),
        heightPad: 4,
      }, 'rocks'),
    );
  }

  private propEntities: pc.Entity[] = [];
  private placeProps() {
    const put = (model: string, x: number, y: number, z: number, yawDeg: number, sc?: number | [number, number, number]) => {
      const e = this.lib.instantiate(model);
      e.setPosition(x, y, z);
      e.setEulerAngles(0, yawDeg, 0);
      if (typeof sc === 'number') e.setLocalScale(sc, sc, sc);
      else if (sc) e.setLocalScale(sc[0], sc[1], sc[2]);
      for (const r of e.findComponents('render') as pc.RenderComponent[]) { r.castShadows = true; r.receiveShadows = true; }
      this.app.root.addChild(e);
      this.propEntities.push(e);
    };
    for (const p of PROPS) put(p.model, p.x, p.absY ?? this.terrain.heightAt(p.x, p.z) + (p.dy ?? 0), p.z, p.yaw, p.scale);
    for (const p of this.scatter.areas.placed) put(p.model, p.x, p.y, p.z, (p.yaw * 180) / Math.PI, p.sv ?? p.s);
  }

  /** foliage materials sway in the wind (all LODs share the chunk) */
  private applyWind() {
    for (const [name, [amp, h]] of Object.entries(WIND)) {
      for (const n of [name, `${name}_lod1`]) {
        const m = this.lib.models.get(n);
        if (!m) continue;
        for (const part of m.parts) applyWind(part.material as pc.StandardMaterial, amp, h);
      }
    }
  }

  private addPropColliders() {
    for (const p of PROPS) {
      const y = p.absY ?? this.terrain.heightAt(p.x, p.z) + (p.dy ?? 0);
      const yaw = (p.yaw * Math.PI) / 180;
      for (const [cx, cy, cz, hx, hy, hz] of p.boxes ?? []) {
        const c = Math.cos(yaw), sn = Math.sin(yaw);
        this.phys.addBoxes([{ x: p.x + cx * c + cz * sn, y: y + cy - hy, z: p.z - cx * sn + cz * c, yaw, hx, hy, hz }]);
      }
      if (!p.half || p.collider === 'none') continue;
      if (p.collider === 'cylinder') this.phys.addCylinders([{ x: p.x, y, z: p.z, r: p.half[0], h: p.half[1] * 2 }]);
      else this.phys.addBoxes([{ x: p.x, y, z: p.z, yaw: (p.yaw * Math.PI) / 180, hx: p.half[0], hy: p.half[1], hz: p.half[2] }]);
    }
  }

  /** fixed-step simulation + interpolated render */
  private update = (dtRaw: number) => {
    const dt = Math.min(dtRaw, 0.1);
    this.fpsAcc += dtRaw;
    this.fpsFrames++;
    if (this.fpsAcc > 0.5) {
      store.set({ fps: Math.round(this.fpsFrames / this.fpsAcc) });
      this.fpsAcc = 0;
      this.fpsFrames = 0;
    }
    const inp = this.input.frame();
    if (this.inputOverride) this.inputOverride(inp);
    this.frameInput = inp;
    if (!this.paused) {
      this.acc += dt;
      let steps = 0;
      while (this.acc >= PHYS_DT && steps < 4) {
        this.vehicle.step(inp, PHYS_DT);
        for (const s of this.hooks.step) s(PHYS_DT);
        this.phys.step();
        this.vehicle.snapshot();
        this.acc -= PHYS_DT;
        this.simTime += PHYS_DT;
        steps++;
      }
      if (steps === 4) this.acc = Math.min(this.acc, PHYS_DT);
      this.alpha = this.acc / PHYS_DT;
    }
    this.view.update(this.alpha);
    this.cam.update(this.vehicle, this.view.renderPos, dt, this.paused && this.cam.mode !== 'photo' ? null : inp);
    const cp = this.cam.entity.getPosition();
    this.terrainRender.update(cp);
    for (const l of this.layers) l.update(cp);
    this.water.update(dt);
    this.env.update(dt, cp);
    this.time += dt;
    updateWind(this.app.graphicsDevice, this.time, 1);
    this.nightLights.update(dt, this.env.night);
    const vp = this.view.renderPos;
    this.wildlife.update(this.paused ? 0 : dt, { x: vp.x, z: vp.z, speed: Math.abs(this.vehicle.forwardSpeed) }, cp);
    for (const f of this.hooks.frame) f(dt, inp);
  };

  /** replace the player's vehicle, keeping its place on the map */
  setVehicle(id: VehicleId) {
    if (id === this.vehicleId && this.vehicle) return;
    const old = this.vehicle;
    const yaw = old.yaw;
    const x = old.pos.x, z = old.pos.z;
    const keep = { mudUpgrade: old.mudUpgrade, fineThrottle: old.fineThrottle };
    const dirt = this.view.dirt;
    this.phys.world.removeRigidBody(old.body);
    this.view.destroy();
    this.vehicleId = id;
    this.vehicle = new Vehicle(this.phys, x, this.terrain.driveHeightAt(x, z) + 0.6, z, yaw, VEHICLES[id]);
    Object.assign(this.vehicle, keep);
    this.view = new VehicleView(this.app, this.lib, this.vehicle, this.vehicleInfos.get(id)!);
    this.view.dirt = dirt * 0.5;
    this.teleport(x, z, yaw);
    for (const f of this.onVehicleChanged) f();
  }

  /** place the car on the ground at x/z facing yaw (0 = -Z) */
  teleport(x: number, z: number, yaw: number) {
    const T = this.terrain;
    const onDeck = T.driveHeightAt(x, z) > T.heightAt(x, z) + 0.05;
    const n = onDeck ? { x: 0, y: 1, z: 0 } : T.normalAt(x, z, { x: 0, y: 1, z: 0 }, 1.5);
    const y = T.driveHeightAt(x, z) + 0.5 / Math.max(0.5, n.y);
    this.vehicle.teleport(x, y, z, yaw, n);
    this.view.update(1);
    this.cam.snap(this.vehicle, this.view.renderPos);
  }

  /** teleport onto a road at arc length s */
  teleportRoad(id: string, s: number, reverse = false) {
    const r = this.terrain.roads.find((q) => q.def.id === id);
    if (!r) return;
    const p = r.path.at(s);
    const yaw = Math.atan2(-p.tx, -p.tz) + (reverse ? Math.PI : 0);
    this.teleport(p.x, p.z, yaw);
  }

  /** world-space bounds for maps */
  get worldHalf() {
    return WORLD_HALF;
  }

  destroy() {
    window.removeEventListener('resize', this.onResize);
    document.removeEventListener('visibilitychange', this.onVisibility);
    this.input?.destroy();
    this.app?.destroy();
  }
}
