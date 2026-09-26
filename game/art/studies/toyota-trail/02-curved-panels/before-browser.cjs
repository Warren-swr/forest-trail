// Toyota-only study. Compare the exact V2 asset with the refined asset in one
// frozen world, then drive the candidate using the production physics loop.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');

const root = path.resolve('dist');
const study = path.resolve('art/studies/toyota-trail');
const out = path.resolve('docs/toyota-trail');
fs.mkdirSync(out, { recursive: true });
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.glb': 'model/gltf-binary', '.mp3': 'audio/mpeg' };
const server = http.createServer((req, res) => {
  const name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  if (name === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  const legacy = /^\/assets\/models\/vehicle_toyota_legacy\.(glb|json)$/.test(name);
  const file = legacy ? path.join(study, path.basename(name)) : path.resolve(root, '.' + (name === '/' ? '/index.html' : name));
  if ((!legacy && !file.startsWith(root + path.sep)) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404); res.end(); return;
  }
  res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
const report = { capturedAt: new Date().toISOString(), viewport: { width: 1600, height: 1000 },
  method: 'Unmodified production WebGL canvas. Old and new assets share one frozen vehicle pose, environment time, camera and sand paint. Baseline comparison concerns appearance only; the subsequent candidate drive runs real physics.',
  baseline: JSON.parse(fs.readFileSync(path.join(study, 'baseline.json'))),
  assets: {}, views: [], screenshots: [], errors: [] };
for (const [id, file] of Object.entries({ legacy: path.join(study, 'vehicle_toyota_legacy.glb'),
  sample: path.join(root, 'assets/models/vehicle_toyota_trail.glb') })) {
  report.assets[id] = { file: path.relative(process.cwd(), file), sha256: sha(fs.readFileSync(file)) };
}

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.FOREST_CHROMIUM || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-gpu', '--use-gl=angle', '--use-angle=vulkan',
      '--enable-features=Vulkan', '--ignore-gpu-blocklist'] });
  try {
    const page = await browser.newPage({ viewport: report.viewport });
    page.on('pageerror', e => report.errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') report.errors.push(m.text()); });
    page.on('requestfailed', r => report.errors.push(`${r.url()}: ${r.failure()?.errorText}`));
    await page.goto(`http://127.0.0.1:${server.address().port}/?play&vehicle=toyota`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.__ft?.game?.cameraFrame, undefined, { timeout: 45000 });
    const frames = n => page.evaluate(n => new Promise(resolve => {
      let i = 0; const app = window.__ft.game.app;
      const f = () => { if (++i >= n) { app.off('frameend', f); resolve(); } };
      app.on('frameend', f);
    }), n);
    const capture = async name => {
      const data = await page.evaluate(() => new Promise(resolve => {
        const g = window.__ft.game;
        g.app.once('frameend', () => resolve(g.canvas.toDataURL('image/png').split(',')[1]));
      }));
      const b = Buffer.from(data, 'base64');
      fs.writeFileSync(path.join(out, name + '.png'), b);
      report.screenshots.push({ file: name + '.png', sha256: sha(b) });
    };
    await page.evaluate(() => {
      const a = window.__ft;
      a.drive(0, 0, true); a.setTime(0); a.ui.setPaint('sand'); a.game.view.dirt = 0;
    });
    await frames(120);
    report.setup = await page.evaluate(async () => {
      const a = window.__ft, g = a.game;
      a.release(); g.paused = true; g.app.timeScale = 0;
      window.__toyotaSampleInfo = g.view.info;
      window.__toyotaLegacyInfo = await fetch('assets/models/vehicle_toyota_legacy.json').then(r => r.json());
      await g.lib.load(['vehicle_toyota_legacy']);
      const gl = g.app.graphicsDevice.gl;
      return { model: g.vehicle.spec.model, position: g.vehicle.pos, rotation: g.vehicle.body.rotation(),
        environmentTime: g.time, renderer: gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL),
        drivingCamera: { position: g.cam.entity.getPosition().toArray(), target: g.cam.target.toArray(), fov: g.cam.entity.camera.fov } };
    });
    assert.equal(report.setup.model, 'vehicle_toyota_trail');
    const variant = async kind => page.evaluate(kind => {
      const a = window.__ft, g = a.game, View = g.view.constructor;
      g.view.destroy();
      g.vehicle.spec.model = kind === 'sample' ? 'vehicle_toyota_trail' : 'vehicle_toyota_legacy';
      g.view = new View(g.app, g.lib, g.vehicle, kind === 'sample' ? window.__toyotaSampleInfo : window.__toyotaLegacyInfo);
      g.view.setPaint('sand'); g.view.dirt = 0; g.view.update(g.alpha);
      a.lights().attach(g.view);
      return { model: g.vehicle.spec.model, fallback: g.lib.models.get(g.vehicle.spec.model).fallback };
    }, kind);
    const views = [
      { id: 'front', offset: [4.2, 1.8, -5.4], look: [0, .68, 0], fov: 44 },
      { id: 'side', offset: [7.2, 1.25, .1], look: [0, .68, .1], fov: 44 },
      { id: 'rear', offset: [-4.1, 1.8, 5.4], look: [0, .68, .2], fov: 45 },
      { id: 'detail', offset: [2.9, 1.32, -3.6], look: [.23, .66, -1.05], fov: 43 },
      { id: 'driving', ...report.setup.drivingCamera },
      { id: 'night', offset: [4.2, 1.8, -5.4], look: [0, .68, 0], fov: 44, night: true },
    ];
    for (const view of views) {
      await page.evaluate(view => {
        const a = window.__ft;
        a.ui.setTimeOfDay(view.night ? 'night' : 'day');
        if (view.offset) a.camRel(view.offset, view.look, view.fov);
        else a.camAt(view.position, view.target, view.fov);
      }, view);
      for (const kind of ['legacy', 'sample']) {
        assert.equal((await variant(kind)).fallback, false);
        await frames(20);
        await capture(`${kind}-${view.id}`);
      }
      report.views.push(view);
      console.log('Captured pair:', view.id);
    }
    report.rig = await page.evaluate(() => {
      const v = window.__ft.game.view;
      return { independentSprings: new Set(v.springMorphs.flat()).size, shocks: v.shocks.length,
        brakes: v.wheels.map(w => w.pivot.children.some(c => c.name.startsWith('Brake'))),
        glass: v.mats.get('Glass').map(m => ({ opacity: m.opacity, blendType: m.blendType })),
        paint: v.paintMats.map(m => ({ gloss: m.gloss, clearCoat: m.clearCoat })),
        nearNodes: v.detailNodes.every(n => n.near.enabled && !n.far.enabled) };
    });
    assert.equal(report.rig.independentSprings, 4); assert.equal(report.rig.shocks, 4);
    assert(report.rig.brakes.every(Boolean)); assert(report.rig.nearNodes);
    assert(report.rig.glass.every(m => m.opacity === 1));
    assert(report.rig.paint.every(m => m.clearCoat === 0));
    await page.evaluate(() => window.__ft.camRel([18, 8, -22], [0, .65, 0], 40));
    await frames(10);
    assert(await page.evaluate(() => window.__ft.game.view.detailNodes.every(n => !n.near.enabled && n.far.enabled)));
    await page.evaluate(() => window.__ft.camRel([4.2, 1.8, -5.4], [0, .68, 0], 44));
    await frames(10);
    assert(await page.evaluate(() => window.__ft.game.view.detailNodes.every(n => n.near.enabled && !n.far.enabled)));
    report.lod = 'near → far → near passed';
    // Recording follows live articulation, without setting any wheel or body pose.
    await page.evaluate(() => {
      const a = window.__ft, g = a.game;
      a.ui.setTimeOfDay('day'); g.app.timeScale = 1;
      a.teleportRoad('park', a.roadS('park', -73, 232) - 2);
      a.ui.resume(); g.paused = false; g.vehicle.gear = 'low'; a.autopilot(5, 'park');
      window.__toyotaProof = { samples: 0, maxAxleDifference: 0, minUprightness: 1, maxSpeedKmh: 0, peakMorph: 0 };
      window.__toyotaHook = () => {
        const p = window.__toyotaProof, v = g.vehicle;
        a.camRel([3.3, 1.25, -4.1], [0, .34, 0], 49);
        p.samples++;
        p.maxAxleDifference = Math.max(p.maxAxleDifference, Math.abs(v.wheels[0].length - v.wheels[1].length), Math.abs(v.wheels[2].length - v.wheels[3].length));
        p.minUprightness = Math.min(p.minUprightness, v.uprightness);
        p.maxSpeedKmh = Math.max(p.maxSpeedKmh, v.speed * 3.6);
        p.peakMorph = Math.max(p.peakMorph, ...g.view.springMorphs.flat().map(m => Math.max(m.getWeight(0), m.getWeight(1))));
      };
      g.hooks.frame.push(window.__toyotaHook);
      const stream = g.canvas.captureStream(60);
      const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9') ? 'video/webm;codecs=vp9' : 'video/webm';
      const rec = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 6500000 });
      const chunks = [];
      rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      window.__toyotaVideoDone = new Promise(resolve => {
        rec.onstop = () => {
          const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]);
          reader.readAsDataURL(new Blob(chunks, { type: mimeType }));
          stream.getTracks().forEach(t => t.stop());
        };
      });
      window.__toyotaRecorder = rec; rec.start(500);
    });
    await page.waitForTimeout(6000); await capture('sample-articulation');
    await page.waitForTimeout(6000);
    await page.evaluate(() => window.__toyotaRecorder.stop());
    const video = Buffer.from(await page.evaluate(() => window.__toyotaVideoDone), 'base64');
    fs.writeFileSync(path.join(out, 'suspension.webm'), video);
    report.drive = await page.evaluate(() => {
      const a = window.__ft, g = a.game;
      a.release(); g.paused = true;
      g.hooks.frame.splice(g.hooks.frame.indexOf(window.__toyotaHook), 1);
      return window.__toyotaProof;
    });
    assert(report.drive.maxAxleDifference > .1); assert(report.drive.peakMorph > .1);
    assert(report.drive.minUprightness > .5);
    // Shared glass handling still respects the two previously authored transparent cars.
    report.otherCars = [];
    for (const id of ['scout', 'ranger']) {
      await page.evaluate(id => window.__ft.setVehicle(id), id); await frames(10);
      const check = await page.evaluate(() => {
        const g = window.__ft.game;
        return { id: g.vehicleId, fallback: g.lib.models.get(g.vehicle.spec.model).fallback,
          glassOpacity: g.view.mats.get('Glass')[0].opacity };
      });
      assert.equal(check.fallback, false); assert(check.glassOpacity < .4);
      report.otherCars.push(check);
    }
    assert.equal(report.errors.length, 0, report.errors.join('\n'));
    report.passed = true;
  } finally {
    fs.writeFileSync(path.join(out, 'browser-report.json'), JSON.stringify(report, null, 2) + '\n');
    await browser.close(); server.close();
  }
  console.log('PASS Toyota sample browser acceptance:', out);
})().catch(error => { console.error(error); process.exitCode = 1; server.close(); });
