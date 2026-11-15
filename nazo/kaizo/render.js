// 使い方: node render4.js [--spec specs/xxx.json] [--fig モデル.vrm] info | stills 0,1,2.5 出力先 | range 0 450 出力先
// scene4.html を手元の小さなHTTPサーバーごしに開く（モデルの読みこみに必要）
const { chromium } = require('playwright'); const path = require('path'); const fs = require('fs'); const http = require('http');
const args = process.argv.slice(2); let figPath = null, specRel = 'specs/jump.json', useGpu = false, page = 'scene4.html'; { const i = args.indexOf('--page'); if (i >= 0) { page = args[i + 1]; args.splice(i, 2); } } { const i = args.indexOf('--gpu'); if (i >= 0) { useGpu = true; args.splice(i, 1); } }
 { const i = args.indexOf('--spec'); if (i >= 0) { specRel = args[i + 1]; args.splice(i, 2); } }
 let _=0; { const i = args.indexOf('--fig'); if (i >= 0) { figPath = path.resolve(args[i + 1]); args.splice(i, 2); } }
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.vrm': 'model/gltf-binary', '.glb': 'model/gltf-binary', '.png': 'image/png', '.jpg': 'image/jpeg', '.json': 'application/json; charset=utf-8', '.woff2': 'font/woff2' };
const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]); let f;
  if (u === '/__fig') f = figPath; else { f = path.join(__dirname, u); if (!f.startsWith(__dirname + path.sep)) f = null; }
  if (!f || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
});
(async () => {
  await new Promise(r => server.listen(0, '127.0.0.1', r)); const port = server.address().port; const mode = args[0];
  // --gpu：通常の Chromium を headless で起動（Mac mini M1 で Metal を使えた設定。2026-11-13 Codex 検証）。既定は GPU なし環境向けの SwiftShader
  const b = useGpu ? await chromium.launch({ channel: 'chromium', headless: true }) : await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  let OW = 1080, OH = 1920; try { const o = JSON.parse(fs.readFileSync(path.join(__dirname, specRel), 'utf8')).output || {}; OW = o.width || OW; OH = o.height || OH } catch (e) {}   // 横長（長尺 1920x1080）にも対応
  const p = await b.newPage({ viewport: { width: OW / 2, height: OH / 2 }, deviceScaleFactor: 2 });
  p.on('pageerror', e => console.log('pageerror:', e.message));
  p.on('console', m => { const t = m.text(); if (!/deprecated|GPU stall|toNonIndexed/.test(t)) console.log('console:', t); });
  const q = new URLSearchParams({ spec: specRel }); if (figPath) q.set('fig', '/__fig');
  await p.goto(`http://127.0.0.1:${port}/${page}?` + q.toString());
  await p.waitForFunction('window.__ready === true', null, { timeout: 120000 });
  console.log('figure:', JSON.stringify(await p.evaluate(() => window.__fig)));
  const renderer = await p.evaluate(() => { const c = document.querySelector('canvas'), gl = c && (c.getContext('webgl2') || c.getContext('webgl')), e = gl && gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : null; });
  console.log('WebGL renderer:', renderer);
  if (useGpu && (!renderer || /SwiftShader/i.test(renderer))) { console.log('NG: GPU で描けていない（--gpu 指定）。止める'); await b.close(); server.close(); process.exit(1); }
  if (mode === 'info') console.log(JSON.stringify(await p.evaluate(() => ({ segs: window.__segs, boxes: window.__boxes }))));
  if (mode === 'stills') { const times = args[1].split(',').map(Number), out = args[2]; fs.mkdirSync(out, { recursive: true });
    for (const t of times) { const t0 = Date.now(); await p.evaluate(tt => window.renderAt(tt), t);
      await p.screenshot({ path: path.join(out, 's_' + t.toFixed(2).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: 88 }); console.log(t.toFixed(2), (Date.now() - t0) + 'ms'); } }
  if (mode === 'range') { const a = +args[1], z = +args[2], out = args[3]; fs.mkdirSync(out, { recursive: true }); const T0 = Date.now();
    for (let i = a; i < z; i++) { await p.evaluate(tt => window.renderAt(tt), i / 30);
      await p.screenshot({ path: path.join(out, 'f' + String(i).padStart(4, '0') + '.jpg'), type: 'jpeg', quality: 95 }); if (i % 60 === 0) console.log('frame', i, ((Date.now() - T0) / 1000).toFixed(0) + 's'); }
    console.log('done', a, z, ((Date.now() - T0) / 1000).toFixed(0) + 's'); }
  await b.close(); server.close();
})();
