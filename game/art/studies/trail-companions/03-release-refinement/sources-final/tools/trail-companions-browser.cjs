// Fixed-camera before/after captures, live articulation and production UI checks.
// Use TRAIL_STUDY_OUT for a NEW directory; PLAYWRIGHT_MODULE / FOREST_CHROMIUM
// allow using an existing browser installation without adding game dependencies.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');

const root = path.resolve('dist');
const study = path.resolve('art/studies/trail-companions/02-release-baseline');
const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
const out = path.resolve(process.env.TRAIL_STUDY_OUT || path.join('docs/trail-companions', stamp));
assert(!fs.existsSync(out), 'Use a new directory; existing captures are preserved');
fs.mkdirSync(out, { recursive: true });
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.glb': 'model/gltf-binary', '.mp3': 'audio/mpeg' };
const server = http.createServer((req, res) => {
  const name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  if (name === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  const match = name.match(/^\/assets\/models\/vehicle_(scout|ranger)_before\.(glb|json)$/);
  const file = match ? path.join(study, match[1], 'before.' + match[2])
    : path.resolve(root, '.' + (name === '/' ? '/index.html' : name));
  if ((!match && !file.startsWith(root + path.sep)) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404); res.end(); return;
  }
  res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
const report = { capturedAt: new Date().toISOString(), viewport: { width: 1600, height: 1000 },
  method: 'Previous published models and their original specifications versus current models/specifications in the same current WebGL scene and compatibility renderer. Each pair shares fixed world cameras, paint and environment; each variant creates a fresh rigid body and settles for 3 seconds with the current physics. Historical physics is compared separately in the suspension study. Driving videos use the real current 60 Hz simulation.',
  baseline: JSON.parse(fs.readFileSync(path.join(study, 'baseline.json'))),
  assets: {}, vehicles: [], screenshots: [], errors: [] };
assert.equal(report.baseline.kind, 'published-release');
for (const asset of report.baseline.publishedAssets) {
  const file = path.join(study, asset.id, 'before' + path.extname(asset.path));
  assert.equal(sha(fs.readFileSync(file)), asset.sha256, 'Published baseline no longer matches its live-site receipt');
}
for (const id of ['scout', 'ranger']) {
  report.assets[id] = {};
  for (const [kind, file] of [['before', path.join(study, id, 'before.glb')],
    ['after', path.join(root, 'assets/models/vehicle_' + id + '.glb')]]) {
    report.assets[id][kind] = { file: path.relative(process.cwd(), file), sha256: sha(fs.readFileSync(file)) };
  }
}

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true, executablePath: process.env.FOREST_CHROMIUM || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-gpu', '--use-gl=angle', '--use-angle=vulkan',
      '--enable-features=Vulkan', '--ignore-gpu-blocklist'] });
  try {
    const page = await browser.newPage({ viewport: report.viewport });
    page.on('pageerror', e => report.errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') report.errors.push(m.text()); });
    page.on('requestfailed', r => report.errors.push(r.url() + ': ' + r.failure()?.errorText));
    await page.goto('http://127.0.0.1:' + server.address().port + '/?play', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.__ft?.game?.cameraFrame, undefined, { timeout: 45000 });
    const frames = n => page.evaluate(n => new Promise(resolve => {
      let i = 0;
      const app = window.__ft.game.app;
      const f = () => { if (++i >= n) { app.off('frameend', f); resolve(); } };
      app.on('frameend', f);
    }), n);
    const capture = async name => {
      const data = await page.evaluate(() => new Promise(resolve => {
        const g = window.__ft.game;
        g.app.once('frameend', () => resolve(g.canvas.toDataURL('image/png').split(',')[1]));
      }));
      const bytes = Buffer.from(data, 'base64');
      fs.writeFileSync(path.join(out, name + '.png'), bytes);
      report.screenshots.push({ file: name + '.png', sha256: sha(bytes) });
    };
    await frames(60);
    report.renderer = await page.evaluate(() => {
      const gl = window.__ft.game.app.graphicsDevice.gl;
      return gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL);
    });
    for (const id of ['scout', 'ranger']) {
      const beforeSpec = JSON.parse(fs.readFileSync(path.join(study, id, 'before-spec.json')));
      await page.evaluate(async ({ id, beforeSpec }) => {
        const a = window.__ft, g = a.game;
        a.release(); a.setVehicle(id); g.paused = true; g.app.timeScale = 0;
        a.setTime(0); a.lights().beam = 0;
        const alias = 'vehicle_' + id + '_before';
        await g.lib.load([alias]);
        const start = g.terrain.roads.find(r => r.def.id === 'loop').path.at(6);
        window.__companion = { id, paint: id === 'scout' ? 'ochre' : 'mint',
          beforeSpec, afterSpec: structuredClone(g.vehicle.spec),
          beforeInfo: await fetch('assets/models/' + alias + '.json').then(r => r.json()),
          afterInfo: g.view.info, spawn: { x: start.x, z: start.z, yaw: Math.atan2(-start.tx, -start.tz) } };
      }, { id, beforeSpec });
      const variant = kind => page.evaluate(kind => {
        const a = window.__ft, g = a.game, c = window.__companion;
        const View = g.view.constructor, Vehicle = g.vehicle.constructor;
        g.phys.world.removeRigidBody(g.vehicle.body); g.view.destroy();
        const spec = structuredClone(kind === 'before' ? c.beforeSpec : c.afterSpec);
        if (kind === 'before') spec.model = 'vehicle_' + c.id + '_before';
        const p = c.spawn;
        g.vehicle = new Vehicle(g.phys, p.x, g.terrain.heightAt(p.x, p.z) + .65, p.z, p.yaw, spec);
        const neutral = { drive: 0, steer: 0, handbrake: true, digital: true };
        for (let i = 0; i < 180; i++) { g.vehicle.step(neutral); g.phys.step(); g.vehicle.snapshot(); }
        g.view = new View(g.app, g.lib, g.vehicle, kind === 'before' ? c.beforeInfo : c.afterInfo);
        g.view.setPaint(c.paint); g.view.dirt = 0; g.view.update(1);
        for (const hook of g.onVehicleChanged) hook();
        a.lights().attach(g.view);
        return { model: spec.model, fallback: g.lib.models.get(spec.model).fallback,
          position: { ...g.vehicle.pos }, wheelLengths: g.vehicle.wheels.map(w => w.length),
          grounded: g.vehicle.groundedCount, radius: spec.wheelRadius };
      }, kind);
      const row = { id, views: [], variants: {} };
      const views = [
        { id: 'front', offset: [4.2, 2.05, -5.4], look: [0, .68, 0], fov: 44 },
        { id: 'side', offset: [7.2, 1.1, .1], look: [0, .65, .1], fov: 44 },
        { id: 'rear', offset: [-4.1, 1.8, 5.4], look: [0, .66, .2], fov: 45 },
        { id: 'front-flat', offset: [0, 1.04, -6.5], look: [0, .65, -1.15], fov: 43 },
        { id: 'rear-flat', offset: [0, 1.1, 6.5], look: [0, .66, 1.65], fov: 43 },
        { id: 'hood', offset: [2.3, 2.3, -3.1], look: [0, .93, -1.12], fov: 43 },
        { id: 'wheel', offset: [2.4, .64, -2.5], look: [.7, .12, -1.2], fov: 42 },
        { id: 'detail', offset: [2.4, 1.55, -.6], look: [.5, 1.04, -.25], fov: 43 },
        { id: 'load', offset: [-2.7, 2.25, 3.8], look: [0, 1.0, 1.0], fov: 44 },
        { id: 'night', offset: [4.2, 1.8, -5.4], look: [0, .66, 0], fov: 44, night: true },
      ];
      for (const view of views) {
        await variant('after');
        await page.evaluate(view => {
          const a = window.__ft;
          a.ui.setTimeOfDay(view.night ? 'night' : 'day');
          a.lights().beam = view.night ? 2 : 0;
          a.camRel(view.offset, view.look, view.fov);
        }, view);
        for (const kind of ['before', 'after']) {
          const state = await variant(kind);
          assert.equal(state.fallback, false); assert.equal(state.grounded, 4);
          row.variants[kind] = state;
          await frames(12); await capture(id + '-' + kind + '-' + view.id);
        }
        row.views.push(view);
        console.log('Captured', id, view.id);
      }
      row.rig = await page.evaluate(() => {
        const g = window.__ft.game, v = g.view;
        return { model: g.vehicle.spec.model, independentSprings: new Set(v.springMorphs.flat()).size,
          shocks: v.shocks.length, opaqueGlass: v.mats.get('Glass').every(m => m.opacity === 1),
          brakes: v.wheels.every(w => w.pivot.children.some(c => c.name.startsWith('Brake'))),
          barrelScales: v.shocks.map(s => s.barrel.getLocalScale().toArray()) };
      });
      assert.equal(row.rig.independentSprings, 4); assert.equal(row.rig.shocks, 4);
      assert(row.rig.opaqueGlass && row.rig.brakes);
      assert(row.rig.barrelScales.every(s => s.every(v => v === 1)));
      await page.evaluate(() => window.__ft.camRel([18, 8, -22], [0, .65, 0], 40));
      await frames(12);
      assert(await page.evaluate(() => window.__ft.game.view.detailNodes.every(n => !n.near.enabled && n.far.enabled)));
      await capture(id + '-after-distant');
      await page.evaluate(() => window.__ft.camRel([4.2, 2.05, -5.4], [0, .68, 0], 44));
      await frames(12);
      assert(await page.evaluate(() => window.__ft.game.view.detailNodes.every(n => n.near.enabled && !n.far.enabled)));
      row.lod = 'near → far → near passed';
      row.lamps = await page.evaluate(() => {
        const v = window.__ft.game.view;
        const result = {};
        for (const [name, beam, brake, reverse] of [['off', 0, 0, false], ['low', 1, 0, false],
          ['high', 2, 0, false], ['brake', 1, 1, false], ['reverse', 1, 0, true]]) {
          v.setLamps({ beam, brake, reverse, night: 1 });
          result[name] = Object.fromEntries(['Lamp', 'LampAux', 'LampRear', 'LampReverse', 'LampPlate']
            .map(k => [k, v.mats.get(k).map(m => m.emissiveIntensity)]));
        }
        return result;
      });
      assert(row.lamps.off.Lamp.every(v => v === 0));
      assert(row.lamps.low.Lamp.every(v => v === 6));
      assert(row.lamps.high.Lamp.every(v => v === 9));
      assert(row.lamps.low.LampAux.every(v => v === 0));
      assert(row.lamps.high.LampAux.every(v => v > 0));
      assert(row.lamps.brake.LampRear.every(v => v === 9));
      assert(row.lamps.reverse.LampReverse.every(v => v === 5));
      assert(row.lamps.low.LampPlate.every(v => v > 0));
      await page.evaluate(() => {
        const a = window.__ft, g = a.game;
        a.ui.setTimeOfDay('day'); a.lights().beam = 0; g.app.timeScale = 1;
        a.teleportRoad('park', a.roadS('park', -73, 232) - 2);
        a.ui.resume(); g.paused = false; g.vehicle.gear = 'low'; a.autopilot(5, 'park');
        window.__trailProof = { samples: 0, maxAxleDifference: 0, minUprightness: 1, maxSpeedKmh: 0,
          peakMorph: 0, barrelScaleError: 0, maxFrameMs: 0 };
        window.__trailHook = dt => {
          const p = window.__trailProof, v = g.vehicle;
          a.camRel([3.8, 1.12, -4.3], [0, .35, 0], 48);
          p.samples++; p.maxFrameMs = Math.max(p.maxFrameMs, dt * 1000);
          p.maxAxleDifference = Math.max(p.maxAxleDifference, Math.abs(v.wheels[0].length - v.wheels[1].length),
            Math.abs(v.wheels[2].length - v.wheels[3].length));
          p.minUprightness = Math.min(p.minUprightness, v.uprightness);
          p.maxSpeedKmh = Math.max(p.maxSpeedKmh, v.speed * 3.6);
          p.peakMorph = Math.max(p.peakMorph, ...g.view.springMorphs.flat().map(m => Math.max(m.getWeight(0), m.getWeight(1))));
          p.barrelScaleError = Math.max(p.barrelScaleError, ...g.view.shocks.flatMap(s =>
            s.barrel.getLocalScale().toArray().map(x => Math.abs(x - 1))));
        };
        g.hooks.frame.push(window.__trailHook);
        const stream = g.canvas.captureStream(60);
        const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9') ? 'video/webm;codecs=vp9' : 'video/webm';
        const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 6500000 });
        const chunks = [];
        recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
        window.__trailVideo = new Promise(resolve => {
          recorder.onstop = () => {
            const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]);
            reader.readAsDataURL(new Blob(chunks, { type: mimeType }));
            stream.getTracks().forEach(t => t.stop());
          };
        });
        window.__trailRecorder = recorder; recorder.start(500);
      });
      await page.waitForTimeout(6000); await capture(id + '-after-articulation');
      await page.waitForTimeout(6000);
      await page.evaluate(() => window.__trailRecorder.stop());
      fs.writeFileSync(path.join(out, id + '-suspension.webm'),
        Buffer.from(await page.evaluate(() => window.__trailVideo), 'base64'));
      row.drive = await page.evaluate(() => {
        const a = window.__ft, g = a.game;
        a.release(); g.paused = true; g.app.timeScale = 0;
        g.hooks.frame.splice(g.hooks.frame.indexOf(window.__trailHook), 1);
        return window.__trailProof;
      });
      assert(row.drive.maxAxleDifference > .1); assert(row.drive.peakMorph > .1);
      assert(row.drive.minUprightness > .85); assert.equal(row.drive.barrelScaleError, 0);
      report.vehicles.push(row);
      console.log('Verified', id, JSON.stringify(row.drive));
    }
    // The approved Toyota is a style reference under the same fixed world
    // lighting and cameras; it is never used as the companions' old baseline.
    await page.evaluate(() => {
      const a = window.__ft, g = a.game;
      a.release(); a.setVehicle('toyota'); a.teleportRoad('loop', 6);
      g.paused = true; g.app.timeScale = 0; a.setTime(0); a.ui.setTimeOfDay('day');
      const neutral = { drive: 0, steer: 0, handbrake: true, digital: true };
      for (let i = 0; i < 180; i++) { g.vehicle.step(neutral); g.phys.step(); g.vehicle.snapshot(); }
      g.view.setPaint('sand'); g.view.dirt = 0; g.view.update(1); a.lights().beam = 0;
    });
    report.toyotaReference = { sha256: sha(fs.readFileSync(path.join(root, 'assets/models/vehicle_toyota_trail.glb'))), views: [] };
    for (const view of [
      { id: 'front', offset: [4.2, 2.05, -5.4], look: [0, .68, 0], fov: 44 },
      { id: 'side', offset: [7.2, 1.1, .1], look: [0, .65, .1], fov: 44 },
      { id: 'load', offset: [-2.7, 2.25, 3.8], look: [0, 1.0, 1.0], fov: 44 },
    ]) {
      await page.evaluate(v => window.__ft.camRel(v.offset, v.look, v.fov), view);
      await frames(12); await capture('toyota-reference-' + view.id);
      report.toyotaReference.views.push(view);
    }
    // All three cars still switch correctly with the existing saves and paint UI.
    report.switching = [];
    for (const id of ['toyota', 'scout', 'ranger', 'toyota']) {
      await page.evaluate(id => window.__ft.setVehicle(id), id); await frames(12);
      const state = await page.evaluate(() => {
        const g = window.__ft.game;
        return { id: g.vehicleId, model: g.vehicle.spec.model, fallback: g.lib.models.get(g.vehicle.spec.model).fallback,
          opaqueGlass: g.view.mats.get('Glass').every(m => m.opacity === 1) };
      });
      assert.equal(state.id, id); assert(!state.fallback && state.opaqueGlass);
      report.switching.push(state);
    }
    await page.evaluate(() => { const a = window.__ft; a.setVehicle('scout'); a.ui.setPaint('pine'); a.key('Escape'); });
    await frames(15);
    await page.screenshot({ path: path.join(out, 'desktop-ui.png') });
    await page.setViewportSize({ width: 860, height: 640 });
    await frames(15);
    await page.screenshot({ path: path.join(out, 'compact-ui.png') });
    report.compactUI = await page.evaluate(() => ({
      width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      canvasWidth: window.__ft.game.canvas.width, canvasHeight: window.__ft.game.canvas.height,
    }));
    assert(report.compactUI.scrollWidth <= report.compactUI.width);
    assert.deepEqual(report.errors, []);
    report.passed = true;
  } catch (error) {
    report.failure = error.stack;
    throw error;
  } finally {
    fs.writeFileSync(path.join(out, 'browser-report.json'), JSON.stringify(report, null, 2) + '\n');
    await browser.close(); server.close();
    console.log('Saved', out);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
