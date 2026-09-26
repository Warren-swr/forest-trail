// Production browser acceptance and unmodified canvas captures.
// Provide PLAYWRIGHT_MODULE / FOREST_CHROMIUM if Playwright is installed outside this project.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');

const root = path.resolve('dist');
const out = path.resolve('docs/vehicle-fidelity');
fs.mkdirSync(out, { recursive: true });
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.wasm': 'application/wasm', '.glb': 'model/gltf-binary', '.png': 'image/png', '.jpg': 'image/jpeg', '.mp3': 'audio/mpeg' };
const server = http.createServer((req, res) => {
  const name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  if (name === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  const file = path.resolve(root, '.' + (name === '/' ? '/index.html' : name));
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404); res.end(); return;
  }
  res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
const report = { capturedAt: new Date().toISOString(), viewport: { width: 1600, height: 1000 },
  method: 'Local production build; real WebGL canvas captures and real 60 Hz physics during the park drive.',
  assets: {}, vehicles: [], screenshots: [], errors: [] };
for (const id of ['scout', 'toyota', 'ranger']) {
  const file = `assets/models/vehicle_${id}.glb`;
  report.assets[id] = { file, sha256: sha(fs.readFileSync(path.join(root, file))) };
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
    await page.goto(`http://127.0.0.1:${server.address().port}/?play`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.__ft?.game?.cameraFrame, undefined, { timeout: 45000 });
    await page.waitForTimeout(1800);
    report.renderer = await page.evaluate(() => {
      const gl = window.__ft.game.app.graphicsDevice.gl;
      return gl.getParameter(gl.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL);
    });
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
    const performance = () => page.evaluate(() => new Promise(resolve => {
      const samples = []; let prev;
      const frame = t => {
        if (prev !== undefined) samples.push(t - prev);
        prev = t;
        if (samples.length < 120) requestAnimationFrame(frame);
        else {
          const sorted = [...samples].sort((a, b) => a - b);
          const mean = samples.reduce((a, b) => a + b, 0) / samples.length;
          resolve({ ...window.__ft.stats(), frames: samples.length, fps: 1000 / mean, meanMs: mean, p95Ms: sorted[114] });
        }
      };
      requestAnimationFrame(frame);
    }));
    for (const id of ['scout', 'toyota', 'ranger']) {
      await page.evaluate(id => {
        const a = window.__ft;
        a.setVehicle(id); a.game.paused = false; a.drive(0, 0, true); a.game.view.dirt = 0;
        a.ui.setPaint(id === 'scout' ? 'ochre' : id === 'toyota' ? 'sand' : 'mint');
        a.setTime(0); a.camRel([4.2, 2.0, -5.4], [0, .68, 0], 44);
      }, id);
      await frames(60);
      await page.evaluate(() => { window.__ft.release(); window.__ft.game.paused = true; });
      const rig = await page.evaluate(() => {
        const g = window.__ft.game, v = g.view;
        const morphs = v.springMorphs.flat();
        const brakes = v.wheels.map(w => w.pivot.children.some(c => c.name.startsWith('Brake')));
        return { fallback: g.lib.models.get(g.vehicle.spec.model).fallback,
          independentSprings: new Set(morphs).size, brakes,
          shocks: v.shocks.length, glassOpacity: v.mats.get('Glass')[0].opacity,
          nearNodes: v.detailNodes.every(n => n.near.enabled && !n.far.enabled) };
      });
      assert.equal(rig.fallback, false); assert.equal(rig.independentSprings, 4);
      assert(rig.brakes.every(Boolean)); assert.equal(rig.shocks, 4);
      assert(rig.glassOpacity < .4); assert(rig.nearNodes);
      await capture(id + '-front');
      await page.evaluate(() => window.__ft.camRel([-4.1, 1.8, 5.4], [0, .65, .2], 45));
      await frames(20); await capture(id + '-rear');
      await page.evaluate(() => window.__ft.camRel([1.95, .50, -2.45], [.65, .20, -1.15], 46));
      await frames(20); await capture(id + '-wheel');
      await page.evaluate(() => window.__ft.camRel([1.70, 1.27, -.60], [0, .86, -.16], 60));
      await frames(20); await capture(id + '-interior');
      await page.evaluate(() => window.__ft.camRel([18, 8, -22], [0, .65, 0], 40));
      await frames(10);
      assert(await page.evaluate(() => window.__ft.game.view.detailNodes.every(n => !n.near.enabled && n.far.enabled)));
      await page.evaluate(() => window.__ft.camRel([4.2, 2, -5.4], [0, .68, 0], 44));
      await frames(10);
      assert(await page.evaluate(() => window.__ft.game.view.detailNodes.every(n => n.near.enabled && !n.far.enabled)));
      const perf = await performance();
      report.vehicles.push({ id, rig, lod: 'near → far → near passed', perf });
      console.log(id, JSON.stringify({ fps: perf.fps, p95Ms: perf.p95Ms, rig }));
    }
    await page.evaluate(() => {
      const a = window.__ft;
      a.setVehicle('toyota'); a.ui.setTimeOfDay('night'); a.camRel([4.2, 1.9, -5.4], [0, .6, 0], 46);
      a.lights().beam = 2;
    });
    await frames(60);
    assert(await page.evaluate(() => window.__ft.game.view.mats.get('Lamp')[0].emissiveIntensity > 0));
    await capture('toyota-night');
    await page.evaluate(() => {
      const a = window.__ft; a.ui.setTimeOfDay('day'); a.game.view.dirt = .8;
    });
    await frames(30); await capture('toyota-mud');
    // Real trail-park run. Camera follows the live vehicle but does not set its pose.
    await page.evaluate(() => {
      const a = window.__ft, g = a.game;
      a.game.view.dirt = .12; a.teleportRoad('park', a.roadS('park', -73, 232) - 2);
      a.ui.resume(); g.paused = false; g.vehicle.gear = 'low'; a.autopilot(5, 'park');
      window.__vehicleProof = { samples: 0, maxAxleDifference: 0, minUprightness: 1, maxSpeedKmh: 0, peakMorph: 0 };
      window.__vehicleProofHook = () => {
        const p = window.__vehicleProof, v = g.vehicle;
        a.camRel([3.3, 1.25, -4.1], [0, .34, 0], 49);
        p.samples++;
        p.maxAxleDifference = Math.max(p.maxAxleDifference, Math.abs(v.wheels[0].length - v.wheels[1].length), Math.abs(v.wheels[2].length - v.wheels[3].length));
        p.minUprightness = Math.min(p.minUprightness, v.uprightness);
        p.maxSpeedKmh = Math.max(p.maxSpeedKmh, v.speed * 3.6);
        p.peakMorph = Math.max(p.peakMorph, ...g.view.springMorphs.flat().map(m => Math.max(m.getWeight(0), m.getWeight(1))));
      };
      g.hooks.frame.push(window.__vehicleProofHook);
      const stream = g.canvas.captureStream(60);
      const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9') ? 'video/webm;codecs=vp9' : 'video/webm';
      const rec = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 6500000 });
      const chunks = [];
      rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      window.__vehicleVideoDone = new Promise(resolve => {
        rec.onstop = () => {
          const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]);
          reader.readAsDataURL(new Blob(chunks, { type: mimeType }));
          stream.getTracks().forEach(t => t.stop());
        };
      });
      window.__vehicleRecorder = rec; rec.start(500);
    });
    await page.waitForTimeout(6000); await capture('toyota-articulation');
    await page.waitForTimeout(6000);
    await page.evaluate(() => window.__vehicleRecorder.stop());
    const video = Buffer.from(await page.evaluate(() => window.__vehicleVideoDone), 'base64');
    fs.writeFileSync(path.join(out, 'suspension.webm'), video);
    report.drive = await page.evaluate(() => {
      const a = window.__ft, g = a.game;
      a.release(); g.paused = true;
      g.hooks.frame.splice(g.hooks.frame.indexOf(window.__vehicleProofHook), 1);
      return window.__vehicleProof;
    });
    assert(report.drive.maxAxleDifference > .10, 'The recorded drive did not exercise axle articulation');
    assert(report.drive.peakMorph > .1);
    assert(report.drive.minUprightness > .5);
    // Near photo inspection keeps its focus, and returning to driving restores camera limits.
    await page.evaluate(() => { const a = window.__ft; a.ui.openPhoto(); a.game.cam.zoomDist = 2.6; });
    await frames(60);
    report.photo = await page.evaluate(() => {
      const g = window.__ft.game;
      return { distance: g.cam.dist, focus: g.cameraFrame.dof.focusDistance, targetDistance: g.cam.entity.getPosition().distance(g.cam.target) };
    });
    assert(Math.abs(report.photo.focus - report.photo.targetDistance) < .04);
    await page.evaluate(() => window.__ft.ui.resume()); await frames(5);
    assert(await page.evaluate(() => window.__ft.game.cam.zoomDist >= 4.5));
    await page.setViewportSize({ width: 844, height: 390 });
    await page.evaluate(() => { window.__ft.ui.pause(); });
    await page.getByRole('button', { name: '车辆与涂装', exact: true }).click();
    await frames(10); await page.screenshot({ path: path.join(out, 'compact-ui.png') });
    report.compact = await page.evaluate(() => ({ width: innerWidth, height: innerHeight,
      horizontalOverflow: document.documentElement.scrollWidth > innerWidth }));
    assert(!report.compact.horizontalOverflow);
    await page.getByRole('button', { name: '近距离检视车辆', exact: true }).click();
    assert(await page.evaluate(() => window.__ft.game.cam.mode === 'photo'));
    assert.equal(report.errors.length, 0, report.errors.join('\n'));
    report.passed = true;
  } finally {
    fs.writeFileSync(path.join(out, 'browser-report.json'), JSON.stringify(report, null, 2) + '\n');
    await browser.close(); server.close();
  }
  console.log('PASS production browser acceptance:', out);
})().catch(error => { console.error(error); process.exitCode = 1; server.close(); });
