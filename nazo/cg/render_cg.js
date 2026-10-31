// nazo/cg/render_cg.js — scene.js の場面を Chromium（GPUなし・ソフト描画）で1コマずつ JPEG に書き出す
// 使い方: node nazo/cg/render_cg.js jobs.json
//   jobs.json = [{scene, p, d(秒), fps, w, h, out(フォルダ)}, ...]  → out/00000.jpg ...
// three.js は nazo/cg/node_modules（npm install）から読む。外部への通信はしない（手元に小さなサーバーを立てて配る）
const fs = require("fs"), path = require("path"), http = require("http");
const { chromium } = require("playwright");
const ROOT = __dirname;

function serve() {
  return new Promise(res => {
    const s = http.createServer((req, rsp) => {
      const f = path.join(ROOT, decodeURIComponent(req.url.split("?")[0]));
      if (!f.startsWith(ROOT) || !fs.existsSync(f)) { rsp.writeHead(404); return rsp.end(); }
      const type = f.endsWith(".js") ? "text/javascript" : "text/html";
      rsp.writeHead(200, { "Content-Type": type }); rsp.end(fs.readFileSync(f));
    }).listen(0, "127.0.0.1", () => res(s));
  });
}

(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const srv = await serve();
  const port = srv.address().port;
  const br = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const T0 = Date.now(); let total = 0;
  for (const j of jobs) {
    const pg = await br.newPage({ viewport: { width: j.w, height: j.h } });
    pg.on("console", m => { if (m.type() === "error") console.error("[page]", m.text()); });
    pg.on("pageerror", e => console.error("[page]", e.message));
    await pg.goto(`http://127.0.0.1:${port}/index.html`);
    await pg.waitForFunction(() => window.ready === true, null, { timeout: 30000 });
    await pg.evaluate(job => window.setup(job), j);
    fs.mkdirSync(j.out, { recursive: true });
    const n = Math.round(j.d * j.fps), t1 = Date.now();
    for (let i = 0; i < n; i++) {
      const b64 = await pg.evaluate(t => { window.frame(t); return document.querySelector("canvas").toDataURL("image/jpeg", 0.92).slice(23); }, i / j.fps);
      fs.writeFileSync(path.join(j.out, String(i).padStart(5, "0") + ".jpg"), Buffer.from(b64, "base64"));
    }
    total += n;
    console.log(`cg ${j.scene} ${n}コマ ${((Date.now() - t1) / 1000).toFixed(1)}秒 (${((Date.now() - t1) / n).toFixed(0)}ms/コマ) → ${j.out}`);
    await pg.close();
  }
  console.log(`cg 合計 ${total}コマ ${((Date.now() - T0) / 1000).toFixed(1)}秒`);
  await br.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
