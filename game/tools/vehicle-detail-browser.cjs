// Compare the frozen input GLBs to current game assets under identical cameras.
// VEHICLE_DETAIL_RUN is a run directory containing baseline/game/public/assets.
// Raw captures always go into a fresh subdirectory; no historical media changes.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

assert(process.env.VEHICLE_DETAIL_RUN, 'Set VEHICLE_DETAIL_RUN to the frozen input run');
const run = path.resolve(process.env.VEHICLE_DETAIL_RUN);
const root = path.resolve('dist');
const out = path.join(run, 'browser', new Date().toISOString().replace(/[:.]/g, '-'));
fs.mkdirSync(out, { recursive: true });
const baseline = path.join(run, 'baseline/game/public/assets/models');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const models = { toyota: 'vehicle_toyota_trail', scout: 'vehicle_scout', ranger: 'vehicle_ranger' };
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json',
  '.css': 'text/css', '.glb': 'model/gltf-binary', '.mp3': 'audio/mpeg' };
const server = http.createServer((req, res) => {
  const name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  if (name === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  const old = name.match(/^\/assets\/models\/(vehicle_(?:toyota_trail|scout|ranger))_before\.(glb|json)$/);
  const file = old ? path.join(baseline, `${old[1]}.${old[2]}`)
    : path.resolve(root, '.' + (name === '/' ? '/index.html' : name));
  if ((!old && !file.startsWith(root + path.sep)) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404); res.end(); return;
  }
  res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
const report = { createdAt: new Date().toISOString(), viewport: { width: 1600, height: 1000 },
  method: 'Production WebGL canvas. Frozen input and current GLBs share the same settled physics body, paint, camera, lighting and environment time.',
  vehicles: [], screenshots: [], errors: [] };

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ headless: true, executablePath: process.env.FOREST_CHROMIUM || undefined,
      args: ['--no-sandbox', '--disable-dev-shm-usage', ...(process.env.SOFTWARE_GL
        ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
        : ['--enable-gpu', '--use-gl=angle', '--use-angle=vulkan', '--enable-features=Vulkan', '--ignore-gpu-blocklist'])] });
    const page = await browser.newPage({ viewport: report.viewport });
    page.setDefaultTimeout(90000);
    page.on('pageerror', e => report.errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') report.errors.push(m.text()); });
    page.on('requestfailed', r => report.errors.push(`${r.url()}: ${r.failure()?.errorText}`));
    page.on('response', r => { if (r.status() >= 400) report.errors.push(`${r.status()} ${r.url()}`); });
    await page.goto(`http://127.0.0.1:${server.address().port}/?play&vehicle=toyota`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.__ft?.game?.cameraFrame);
    const frames = n => page.evaluate(n => new Promise(resolve => {
      let count = 0; const app = window.__ft.game.app;
      const fn = () => { if (++count >= n) { app.off('frameend', fn); resolve(); } };
      app.on('frameend', fn);
    }), n);
    const capture = async name => {
      const data = await page.evaluate(() => new Promise(resolve => {
        const g = window.__ft.game;
        g.app.once('frameend', () => resolve({ png: g.canvas.toDataURL('image/png').split(',')[1],
          jpeg: g.canvas.toDataURL('image/jpeg', .92).split(',')[1] }));
      }));
      const bytes = Buffer.from(data.png, 'base64'), preview = Buffer.from(data.jpeg, 'base64');
      fs.writeFileSync(path.join(out, name + '.png'), bytes);
      fs.writeFileSync(path.join(out, name + '.jpg'), preview);
      report.screenshots.push({ file: name + '.png', sha256: hash(bytes), preview: name + '.jpg', previewSha256: hash(preview) });
    };
    report.renderer = await page.evaluate(() => {
      const gl = window.__ft.game.app.graphicsDevice.gl;
      return gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL);
    });
    const views = [
      { id: 'front', offset: [4.2, 2.05, -5.4], look: [0, .68, 0], fov: 44 },
      { id: 'hood', offset: [2.25, 2.32, -3.25], look: [0, .92, -1.20], fov: 42 },
      { id: 'side', offset: [7.2, 1.25, .1], look: [0, .68, .1], fov: 44 },
      { id: 'rear', offset: [-4.1, 1.8, 5.4], look: [0, .68, .2], fov: 45 },
      { id: 'front-flat', offset: [0, 1.05, -6.5], look: [0, .64, -1.15], fov: 43 },
      { id: 'pillar', offset: [2.30, 1.60, -1.20], look: [.58, 1.10, -.54], fov: 44 },
      { id: 'wheel', offset: [2.35, .67, -2.55], look: [.70, .08, -1.28], fov: 40 },
      { id: 'load', offset: [-2.7, 2.25, 3.8], look: [0, 1.0, 1.0], fov: 44 },
      { id: 'night', offset: [4.2, 1.8, -5.4], look: [0, .66, 0], fov: 44, night: true },
    ];
    for (const id of (process.env.VEHICLES || 'toyota,scout,ranger').split(',')) {
      const model = models[id], alias = model + '_before';
      const row = { id, model, assets: {}, views: [] };
      for (const [variant, file] of [['before', path.join(baseline, model + '.glb')],
        ['after', path.join(root, 'assets/models', model + '.glb')]]) row.assets[variant] = hash(fs.readFileSync(file));
      row.setup = await page.evaluate(async ({ id, alias }) => {
        const a = window.__ft, g = a.game;
        a.release(); a.setVehicle(id); a.setTime(0); a.ui.setTimeOfDay('day');
        g.paused = true; g.app.timeScale = 0; a.lights().beam = 0;
        await g.lib.load([alias]);
        const start = g.terrain.roads.find(r => r.def.id === 'loop').path.at(6);
        a.teleport(start.x, start.z, Math.atan2(-start.tx, -start.tz));
        const neutral = { drive: 0, steer: 0, handbrake: true, digital: true };
        for (let k = 0; k < 180; k++) { g.vehicle.step(neutral); g.phys.step(); g.vehicle.snapshot(); }
        window.__detail = { model: g.vehicle.spec.model, alias, after: g.view.info,
          before: await fetch(`assets/models/${alias}.json`).then(r => r.json()),
          paint: id === 'scout' ? 'ochre' : id === 'toyota' ? 'sand' : 'mint' };
        return { grounded: g.vehicle.groundedCount, position: { ...g.vehicle.pos }, revision: g.view.info.revision };
      }, { id, alias });
      assert.equal(row.setup.grounded, 4);
      const variant = kind => page.evaluate(kind => {
        const a = window.__ft, g = a.game, c = window.__detail, View = g.view.constructor;
        g.view.destroy(); g.vehicle.spec.model = kind === 'before' ? c.alias : c.model;
        g.view = new View(g.app, g.lib, g.vehicle, c[kind]);
        g.view.setPaint(c.paint); g.view.dirt = 0; g.view.update(1);
        for (const hook of g.onVehicleChanged) hook();
        a.lights().attach(g.view);
        return g.lib.models.get(g.vehicle.spec.model).fallback;
      }, kind);
      for (const view of process.env.QUICK ? views.slice(0, 4) : views) {
        await page.evaluate(view => {
          const a = window.__ft;
          a.ui.setTimeOfDay(view.night ? 'night' : 'day'); a.lights().beam = view.night ? 2 : 0;
          a.camRel(view.offset, view.look, view.fov);
        }, view);
        for (const kind of ['before', 'after']) {
          assert.equal(await variant(kind), false);
          await frames(3); await capture(`${id}-${kind}-${view.id}`);
        }
        row.views.push(view);
        console.log('Captured', id, view.id);
      }
      if (!process.env.QUICK) {
        row.lamps = await page.evaluate(() => {
          const v = window.__ft.game.view, states = {};
          for (const [name, beam, brake, reverse] of [['off', 0, 0, false], ['low', 1, 0, false],
            ['high', 2, 0, false], ['brake', 1, 1, false], ['reverse', 1, 0, true]]) {
            v.setLamps({ beam, brake, reverse, night: 1 });
            states[name] = Object.fromEntries(['Lamp', 'LampAux', 'LampRear', 'LampReverse', 'LampPlate']
              .map(k => [k, v.mats.get(k).map(m => m.emissiveIntensity)]));
          }
          return states;
        });
        assert(row.lamps.off.Lamp.every(v => v === 0));
        assert(row.lamps.low.Lamp.every(v => v === 6));
        assert(row.lamps.high.Lamp.every(v => v === 9));
        assert(row.lamps.low.LampAux.every(v => v === 0));
        assert(row.lamps.high.LampAux.every(v => v > 0));
        assert(row.lamps.brake.LampRear.every(v => v === 9));
        assert(row.lamps.reverse.LampReverse.every(v => v === 5));
        assert(row.lamps.low.LampPlate.every(v => v > 0));
        row.rig = await page.evaluate(() => {
          const g = window.__ft.game, v = g.view;
          return { springs: new Set(v.springMorphs.flat()).size, shocks: v.shocks.length,
            glass: v.mats.get('Glass').every(m => m.opacity === 1),
            brakes: v.wheels.every(w => w.pivot.children.some(c => c.name.startsWith('Brake'))) };
        });
        assert.equal(row.rig.springs, 4); assert.equal(row.rig.shocks, 4); assert(row.rig.glass && row.rig.brakes);
        await page.evaluate(() => window.__ft.camRel([18, 8, -22], [0, .65, 0], 40));
        await frames(3);
        assert(await page.evaluate(() => window.__ft.game.view.detailNodes.every(n => !n.near.enabled && n.far.enabled)));
        await capture(`${id}-after-distant`);
        await page.evaluate(() => window.__ft.camRel([4.2, 2.05, -5.4], [0, .68, 0], 44));
        await frames(3);
        assert(await page.evaluate(() => window.__ft.game.view.detailNodes.every(n => n.near.enabled && !n.far.enabled)));
        row.lod = 'near / far / near passed';
        const start = await page.evaluate(() => {
          const a = window.__ft, g = a.game;
          a.ui.setTimeOfDay('day'); a.lights().beam = 0; g.app.timeScale = 1;
          a.release(); a.ui.resume(); g.paused = false;
          a.drive(.65, 0, false);
          return { ...g.vehicle.pos };
        });
        await page.waitForTimeout(6000);
        row.drive = await page.evaluate(start => {
          const a = window.__ft, v = a.game.vehicle;
          a.drive(0, 0, true);
          return { distanceM: Math.hypot(v.pos.x - start.x, v.pos.z - start.z), uprightness: v.uprightness,
            grounded: v.groundedCount, fallback: a.game.lib.models.get(v.spec.model).fallback };
        }, start);
        assert(row.drive.distanceM > 1); assert(row.drive.uprightness > .9); assert.equal(row.drive.fallback, false);
      }
      report.vehicles.push(row);
    }
    assert.equal(report.errors.length, 0, report.errors.join('\n'));
    report.passed = true;
  } catch (error) {
    report.failure = String(error.stack || error);
    throw error;
  } finally {
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2));
    console.log('Output:', out);
    if (browser) await browser.close();
    server.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
