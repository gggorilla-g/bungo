// nazo/cg/scene.js — 妄想科学ショートの3DCG（四角いブロックだけで作る。色と形は自前・単色）
// render_cg.js が Chromium で開き、window.setup(job) → window.frame(t) を1コマずつ呼んで書き出す。
// 場面（job.scene）と p（台本の cg.p）:
//   land   … ブロックの島。太陽が回る。
//            p: cam / cam_to（カメラの位置名）, sun（1日の秒数。0で止める）, t0（時刻のずらし。ループのつなぎ用）,
//               spin（キャラがくるくる回る）, wind（強風）, blow（キャラが飛ばされる）, night（夜・星）,
//               seasons（雪と猛暑が入れかわる）, ph0（太陽の位置の初期値）
//   flight … 地上→雲→宇宙→月へ飛び、p.burst（0〜1）の時刻で月がブロックに砕けて消える
//   rewind … 地球が逆回り。途中で若い地球（溶岩の色）に変わる
//   spin   … 地球がどんどん速く回る（流れる星の線つき）。p.ring で月の通り道（月はいない）を出す
//   axis   … 地軸（赤い棒）がふらつく
//   space  … 太陽と地球。月の通り道だけあって月はいない
import * as THREE from "./node_modules/three/build/three.module.js";

let R, S, C, CUR, job, upd = () => {};
let seed = 12345;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const ease = x => 1 - Math.pow(1 - Math.min(Math.max(x, 0), 1), 3);
const sstep = x => { x = Math.min(Math.max(x, 0), 1); return x * x * (3 - 2 * x); };
const lerp = (a, b, u) => a + (b - a) * u;
const COL = {
  grass: 0x5cb85c, grass2: 0x4aa64a, dirt: 0x8b5a2b, sand: 0xe8d38a, sea: 0x2f7fd8, sea2: 0x3a8ee6,
  trunk: 0x7a4a24, leaf: 0x2e8b3a, leaf2: 0x3fa34d, snow: 0xf2f2f2, cloud: 0xffffff, sun: 0xffd23a,
  moon: 0xbdbdbd, moon2: 0x9a9a9a, lava: 0xe8552a,
};

// 同じ大きさのブロックを大量に置く（InstancedMesh、色はブロックごと）
function blocks(list, size = 1, mat) {
  const g = new THREE.BoxGeometry(size, size, size);
  const im = new THREE.InstancedMesh(g, mat || new THREE.MeshLambertMaterial(), list.length);
  const o = new THREE.Object3D(), c = new THREE.Color();
  list.forEach((b, i) => {
    o.position.set(b[0], b[1], b[2]); o.updateMatrix(); im.setMatrixAt(i, o.matrix);
    im.setColorAt(i, c.setHex(b[3]));
  });
  im.instanceMatrix.needsUpdate = true; im.instanceColor.needsUpdate = true;
  return im;
}

function shell(r, colorFn) {           // ブロックの球の殻（中身は作らない）
  const list = [];
  for (let x = -r; x <= r; x++) for (let y = -r; y <= r; y++) for (let z = -r; z <= r; z++) {
    const d = Math.sqrt(x * x + y * y + z * z);
    if (d <= r && d > r - 1.8) list.push([x, y, z, colorFn(x / r, y / r, z / r)]);
  }
  return list;
}
const planet = (r, fn, size = 1, mat) => blocks(shell(r, fn), size, mat);

function noise3(x, y, z) {   // 決まった模様のでこぼこ（毎回同じ形）
  return Math.sin(x * 3.1 + Math.sin(y * 2.3)) * 0.5 + Math.sin(y * 2.7 + z * 1.9) * 0.3 + Math.sin(z * 3.7 - x * 1.3) * 0.4;
}
const earthColor = (x, y, z) => {
  if (Math.abs(y) > 0.86) return COL.snow;
  const n = noise3(x, y, z);
  return n > 0.35 ? (n > 0.75 ? COL.dirt : COL.grass) : (n > 0.25 ? COL.sand : (n < -0.4 ? COL.sea : COL.sea2));
};
const moonColor = (x, y, z) => (noise3(x * 2, y * 2, z * 2) > 0.4 ? COL.moon2 : COL.moon);

function stars(n, r, size = 2.2) {
  const g = new THREE.BufferGeometry(), p = [];
  for (let i = 0; i < n; i++) {
    const u = rnd() * 2 - 1, a = rnd() * Math.PI * 2, s = Math.sqrt(1 - u * u);
    p.push(r * s * Math.cos(a), r * u, r * s * Math.sin(a));
  }
  g.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({ color: 0xffffff, size, sizeAttenuation: false }));
}

// ブロックのキャラ（緑の髪・白い服・頭の横に豆のブロック。色と形は自前）
function blockChar() {
  const g = new THREE.Group(), body = new THREE.Group(); g.add(body);
  const add = (w, h, d, x, y, z, col) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshLambertMaterial({ color: col }));
    m.position.set(x, y, z); body.add(m); return m;
  };
  add(1.0, 1.1, 0.6, 0, 0.55, 0, 0xf4f4f4);
  add(1.04, 0.16, 0.64, 0, 0.75, 0, 0x6fbf3a);
  add(0.3, 0.6, 0.3, -0.25, -0.3, 0, 0xf4f4f4); add(0.3, 0.6, 0.3, 0.25, -0.3, 0, 0xf4f4f4);
  add(0.28, 0.8, 0.28, -0.68, 0.6, 0, 0xf4f4f4); add(0.28, 0.8, 0.28, 0.68, 0.6, 0, 0xf4f4f4);   // 腕
  add(1.3, 1.2, 1.2, 0, 1.75, 0, 0xffe2c8);
  add(1.4, 0.45, 1.3, 0, 2.45, -0.05, 0x7ccc3c);
  add(1.4, 1.1, 0.3, 0, 1.95, -0.62, 0x7ccc3c);
  add(0.22, 0.32, 0.05, -0.3, 1.8, 0.61, 0x222222); add(0.22, 0.32, 0.05, 0.3, 1.8, 0.61, 0x222222);
  add(0.35, 0.12, 0.05, -0.45, 1.5, 0.61, 0xff9aa6); add(0.35, 0.12, 0.05, 0.45, 1.5, 0.61, 0xff9aa6);
  const ears = [-1, 1].map(sx => {
    const e = new THREE.Group();
    [[0, 0], [0.25, 0.45], [0.5, 0.9]].forEach(([dx, dy]) => {
      const m = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.42, 0.42), new THREE.MeshLambertMaterial({ color: 0x8fd14f }));
      m.position.set(sx * (0.75 + dx), dy, 0); e.add(m);
    });
    e.position.y = 2.0; body.add(e); return e;
  });
  g.userData = { body, ears };
  g.scale.setScalar(1.5);
  return g;
}

// ---------- 場面：ブロックの島 ----------
const LAND_CAMS = {                                      // [位置, 見る点]
  hook: [[16, 11, 33], [0, 6, 0]],      // 冒頭と最後（同じ絵にしてループをつなぐ）
  low: [[5, 4, 15], [0, 7, -6]],        // キャラの足もとから空を見上げる
  wide: [[34, 26, 40], [0, 2, 0]],      // 島の全体
  top: [[2, 48, 12], [0, 0, 0]],        // 真上近く（影が回る）
  side: [[-24, 7, 12], [2, 5, 0]],      // 横から（風で飛ぶのを追う）
  close: [[6, 6.5, 13], [4, 5.5, 4]],   // キャラに寄る
  sky: [[4, 3, 18], [-10, 26, -40]],    // 空を見上げる（星・太陽）
};
function landScene(p) {
  const sc = CUR = new THREE.Scene();
  const N = 22, list = [], top = {};
  const h = (x, z) => {
    const d = Math.sqrt(x * x + z * z) / N;
    return Math.round(3.2 * (1 - d * 1.35) + 1.2 * Math.sin(x * 0.45) * Math.cos(z * 0.38));
  };
  for (let x = -N; x <= N; x++) for (let z = -N; z <= N; z++) {
    const y = h(x, z);
    if (y < 0) continue;
    top[`${x},${z}`] = y;
    for (let k = Math.max(0, y - 2); k <= y; k++)
      list.push([x, k, z, k < y ? COL.dirt : (y <= 0 ? COL.sand : ((x * 7 + z * 3) % 5 ? COL.grass : COL.grass2))]);
  }
  sc.add(blocks(list));
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000), new THREE.MeshLambertMaterial({ color: COL.sea }));
  sea.rotation.x = -Math.PI / 2; sea.position.y = -0.5; sc.add(sea);
  // 雪の層（季節が入れかわる場面用）
  const snowL = [];
  Object.entries(top).forEach(([k, y]) => { const [x, z] = k.split(",").map(Number); if (y > 0) snowL.push([x, y + 0.55, z, COL.snow]); });
  const snow = blocks(snowL, 1); snow.scale.y = 1; snow.visible = false; sc.add(snow);
  // 木
  const trees = [];
  [[-6, -4], [-3, -9], [5, -6], [8, 3], [-10, 1], [-8, 6], [11, -2], [-13, -6], [3, -12], [-2, 2]].forEach(([x, z]) => {
    const y = top[`${x},${z}`]; if (y === undefined || y < 1) return;
    const t = new THREE.Group(); t.position.set(x, y + 0.5, z);
    t.add(blocks([[0, 0, 0, COL.trunk], [0, 1, 0, COL.trunk], [0, 2, 0, COL.trunk]]));
    const lf = [];
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = 0; c <= 1; c++)
      lf.push([a, 3 + c, b, (a + b + c) % 2 ? COL.leaf : COL.leaf2]);
    lf.push([0, 5, 0, COL.leaf]);
    const crown = blocks(lf); t.add(crown); t.userData.crown = crown; sc.add(t); trees.push(t);
  });
  // 雲
  const clouds = new THREE.Group();
  for (let i = 0; i < 12; i++) {
    const cl = [], w = 3 + Math.floor(rnd() * 5);
    for (let a = 0; a < w; a++) for (let b = 0; b < 2; b++) if (rnd() > 0.2) cl.push([a * 1.5, 0, b * 1.5, COL.cloud]);
    const m = blocks(cl, 1.5, new THREE.MeshLambertMaterial({ emissive: 0x555555 }));
    m.position.set(-60 + rnd() * 120, 16 + rnd() * 10, -50 + rnd() * 60); clouds.add(m);
  }
  sc.add(clouds);
  // 風で飛ぶブロック
  const bits = [];
  if (p.wind) for (let i = 0; i < 90; i++) {
    const m = blocks([[0, 0, 0, i % 3 ? COL.leaf2 : COL.sand]], 0.4);
    m.userData = { x: rnd() * 80, y: 1 + rnd() * 14, z: -20 + rnd() * 34, v: 30 + rnd() * 25, s: rnd() * 10 };
    sc.add(m); bits.push(m);
  }
  const CX = 4, ch = blockChar(); const cy = (top[`${CX},6`] ?? 2) + 1.4; ch.position.set(CX, cy, 6); ch.rotation.y = 0.35; sc.add(ch);
  // 太陽・光・星
  const sun = new THREE.Mesh(new THREE.BoxGeometry(9, 9, 9), new THREE.MeshBasicMaterial({ color: COL.sun }));
  sc.add(sun);
  const amb = new THREE.AmbientLight(0xffffff, 0.55); sc.add(amb);
  const dl = new THREE.DirectionalLight(0xffffff, 1.1); sc.add(dl);
  const st = stars(1400, 500, p.night ? 3 : 2.2); sc.add(st);
  const skyDay = new THREE.Color(0x6ec0ff), skyDusk = new THREE.Color(0xff7a3a), skyNight = new THREE.Color(0x03040c);
  const hot = new THREE.Color(0xff9a3a);
  const [cp, ct] = LAND_CAMS[p.cam || "hook"];
  const [cp2, ct2] = LAND_CAMS[p.cam_to || p.cam || "hook"];
  return (t, d) => {
    const u = d ? t / d : 0, tt = t + (p.t0 || 0);
    const ph = (p.sun ? (tt / p.sun) * Math.PI * 2 : 0) + (p.ph0 ?? 0.9);
    const sx = Math.cos(ph) * 160, sy = Math.sin(ph) * 120;
    sun.position.set(sx, sy, -90); sun.rotation.set(tt, tt * 0.7, 0);
    dl.position.set(sx, Math.max(sy, -10), -90);
    const el = Math.sin(ph);
    let day = p.night ? 0 : Math.min(Math.max(el * 2.4 + 0.2, 0), 1);
    const dusk = p.night ? 0 : Math.max(0, 1 - Math.abs(el) * 3.5);
    let season = 0;
    if (p.seasons) season = Math.floor(tt / 0.42) % 2 ? 1 : -1;   // 1=猛暑 -1=雪
    const sky = skyNight.clone().lerp(skyDay, day).lerp(skyDusk, dusk * 0.55);
    if (season === 1) sky.lerp(hot, 0.55);
    if (season === -1) sky.lerp(new THREE.Color(0xc8d8e8), 0.5);
    sc.background = sky;
    snow.visible = season === -1;
    dl.intensity = p.night ? 0 : 0.1 + 1.1 * day; amb.intensity = p.night ? 0.13 : 0.22 + 0.45 * day;
    st.visible = day < 0.55; sun.visible = !p.night;
    clouds.children.forEach(m => {                       // 位置は時刻だけで決める（最後と冒頭の絵をそろえるため）
      if (m.userData.x0 === undefined) m.userData.x0 = m.position.x;
      m.position.x = (((m.userData.x0 + 60 + tt * (p.wind ? 48 : 2.4)) % 120) + 120) % 120 - 60;
    });
    const sway = p.wind ? 0.3 + 0.1 * Math.sin(tt * 13) : 0.02 * Math.sin(tt * 2);
    trees.forEach((tr, i) => { tr.rotation.z = -sway + 0.04 * Math.sin(tt * 11 + i); });
    bits.forEach(b => {
      const q = b.userData; b.position.set(((q.x + t * q.v) % 80) - 40, q.y + Math.sin(t * 6 + q.s), q.z);
      b.rotation.set(t * 7 + q.s, t * 5, 0);
    });
    // キャラ
    const B = ch.userData.body;
    ch.position.set(CX, cy + Math.abs(Math.sin(tt * 8)) * 0.35, 6); ch.rotation.set(0, 0.35, 0);
    ch.userData.ears.forEach((e, i) => { e.rotation.z = (i ? -1 : 1) * 0.2 * Math.sin(tt * 10); });
    if (p.spin) {                         // 高速の昼夜に振り回される
      ch.rotation.y = 0.35 + tt * 9; ch.rotation.z = 0.25 * Math.sin(tt * 6);
      ch.position.y = cy + 0.6 + Math.abs(Math.sin(tt * 6)) * 1.2;
    }
    if (p.wind) {
      ch.rotation.z = -0.35 + 0.08 * Math.sin(t * 15);
      ch.userData.ears.forEach(e => { e.rotation.z = -0.9; });
    }
    if (p.blow) {                          // 飛ばされる
      const b = Math.max(0, t - (p.blow_at ?? 0.25));
      ch.position.set(CX + b * 22, cy + b * 10 - b * b * 2, 6 - b * 4);
      ch.rotation.set(b * 6, 0.35 + b * 4, -0.35 - b * 9);
    }
    const e = sstep(u);
    C.position.set(lerp(cp[0], cp2[0], e), lerp(cp[1], cp2[1], e), lerp(cp[2], cp2[2], e));
    if (p.shake) C.position.x += Math.sin(t * 40) * 0.25;
    C.lookAt(lerp(ct[0], ct2[0], e), lerp(ct[1], ct2[1], e), lerp(ct[2], ct2[2], e));
  };
}

// ---------- 場面：地上 → 雲 → 宇宙 → 月へ。月が砕けて消える ----------
function flightScene(p) {
  const sc = CUR = new THREE.Scene();
  const st = stars(2200, 1500, 2.4); sc.add(st);
  sc.add(new THREE.AmbientLight(0xffffff, 0.45));
  const dl = new THREE.DirectionalLight(0xffffff, 1.3); dl.position.set(-300, 200, 200); sc.add(dl);
  // 地上：草と海のブロックの平面、木
  const gl = [];
  for (let x = -40; x <= 40; x++) for (let z = -60; z <= 30; z++) {
    const land = Math.sin(x * 0.2) + Math.cos(z * 0.17) > -0.3;
    gl.push([x, land ? 0 : -0.6, z, land ? ((x + z) % 3 ? COL.grass : COL.grass2) : COL.sea]);
  }
  const ground = blocks(gl); sc.add(ground);
  const ch = blockChar(); ch.position.set(2, 1.2, 22); ch.rotation.y = Math.PI; sc.add(ch);   // 見送るキャラ
  // 雲の層（y=60 あたり。ここを抜けると地面が丸い地球に替わる）
  const cl = [];
  for (let i = 0; i < 170; i++) cl.push([-140 + rnd() * 280, rnd() * 5, -200 + rnd() * 260, COL.cloud]);
  const clouds = blocks(cl, 6, new THREE.MeshLambertMaterial({ emissive: 0x707070 })); clouds.position.y = 60; sc.add(clouds);
  // 宇宙から見る地球
  const earth = planet(18, earthColor); earth.scale.setScalar(16); earth.position.set(0, -250, -450); earth.visible = false; sc.add(earth);
  // 月（ブロックごとに飛び散らせる）
  const mr = 9, MS = 3.4, ml = shell(mr, moonColor).map(b => [b[0] * MS, b[1] * MS, b[2] * MS, b[3]]);
  const moon = blocks(ml, MS); const MP = new THREE.Vector3(0, 215, -760);
  moon.position.copy(MP); sc.add(moon);
  const vel = ml.map(() => new THREE.Vector3(rnd() - 0.5, rnd() - 0.5, rnd() - 0.5).normalize().multiplyScalar(60 + rnd() * 120));
  const o = new THREE.Object3D();
  const flash = new THREE.Mesh(new THREE.BoxGeometry(10, 10, 10), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0 }));
  flash.position.copy(MP); sc.add(flash);
  // カメラの道すじ（なめらかな曲線）
  const path = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 4, 36), new THREE.Vector3(0, 16, 32), new THREE.Vector3(0, 45, 24), new THREE.Vector3(0, 90, 10),
    new THREE.Vector3(0, 140, -80), new THREE.Vector3(0, 185, -330), new THREE.Vector3(0, 210, -600), new THREE.Vector3(0, 214, -655)]);
  const look = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 10, 0), new THREE.Vector3(0, 50, 10), new THREE.Vector3(0, 110, -60), new THREE.Vector3(0, 60, -400),
    new THREE.Vector3(0, 150, -650), MP.clone(), MP.clone(), MP.clone()]);
  const sky = new THREE.Color(0x6ec0ff), black = new THREE.Color(0x000000);
  const KB = p.burst ?? 0.9;
  return (t, d) => {
    const u = t / d;
    const s = Math.min(1, Math.pow(Math.min(u / KB, 1), 1.35) * 0.985 + Math.max(0, u - KB) * 0.15);   // だんだん速く
    const cp = path.getPoint(s), lp = look.getPoint(s);
    C.position.copy(cp); C.lookAt(lp); C.rotateZ(Math.sin(u * 4) * 0.05 + Math.sin(s * Math.PI) * 0.35);
    const above = cp.y > 63;
    ground.visible = ch.visible = !above; earth.visible = above;
    sc.background = sky.clone().lerp(black, sstep((cp.y - 45) / 40));
    st.visible = cp.y > 55;
    earth.rotation.y = t * 0.25;
    moon.rotation.y = t * 0.5; moon.rotation.x = 0.3;
    ch.rotation.z = 0.2 * Math.sin(t * 12);                  // 手をふる代わりに揺れる
    const b = (u - KB) / (1 - KB);
    if (b > 0) {
      for (let i = 0; i < ml.length; i++) {
        const v = vel[i];
        o.position.set(ml[i][0] + v.x * b * 1.5, ml[i][1] + v.y * b * 1.5, ml[i][2] + v.z * b * 1.5);
        o.scale.setScalar(Math.max(0.001, 1 - b * 1.1));
        o.rotation.set(b * 9 + i, b * 7, 0); o.updateMatrix(); moon.setMatrixAt(i, o.matrix);
      }
      moon.instanceMatrix.needsUpdate = true;
      flash.material.opacity = Math.max(0, 1 - b * 2.5); flash.scale.setScalar(1 + b * 14);
      C.position.x += Math.sin(t * 60) * 1.5 * (1 - b);       // 砕けた瞬間に揺れる
    }
  };
}

// ---------- 場面：巻き戻し ----------
function rewindScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  const st = stars(2000, 600, 2.4); sc.add(st);
  sc.add(new THREE.AmbientLight(0xffffff, 0.35));
  const dl = new THREE.DirectionalLight(0xffffff, 1.3); dl.position.set(-100, 30, 60); sc.add(dl);
  const young = planet(18, (x, y, z) => { const n = noise3(x, y, z); return n > 0.3 ? COL.lava : (n > -0.2 ? 0x6a2a14 : 0x2a1a14); });
  const now = planet(18, earthColor);
  sc.add(young); sc.add(now);
  return (t, d) => {
    const u = t / d;
    const ang = -(t * 2 + 30 * Math.pow(u, 2.2));             // だんだん速く逆回り
    young.rotation.set(0, ang, 0.41); now.rotation.set(0, ang, 0.41);
    now.visible = u < (p.swap ?? 0.55); young.visible = !now.visible;
    st.rotation.y = ang * 0.08; st.rotation.x = ang * 0.02;
    C.position.set(0, 6, lerp(92, 70, ease(u))); C.lookAt(0, 0, 0); C.rotateZ(-u * 0.8);
  };
}

// ---------- 場面：地球がどんどん速く回る ----------
function spinScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  sc.add(stars(1800, 600, 2.4)); sc.add(new THREE.AmbientLight(0xffffff, 0.4));
  const dl = new THREE.DirectionalLight(0xffffff, 1.3); dl.position.set(-100, 40, 80); sc.add(dl);
  const e = planet(18, earthColor); e.rotation.z = 0.41; sc.add(e);
  const streak = [];                                  // 回転の速さを見せる流れる線（細長いブロック）
  for (let i = 0; i < 40; i++) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 6 + rnd() * 10), new THREE.MeshBasicMaterial({ color: 0xbfe6ff }));
    m.userData = { a: rnd() * Math.PI * 2, y: -18 + rnd() * 36, r: 23 + rnd() * 6 }; sc.add(m); streak.push(m);
  }
  let ring = null;
  if (p.ring) {
    const rl = [];
    for (let i = 0; i < 64; i++) if (i % 2) { const a = i / 64 * Math.PI * 2; rl.push([Math.cos(a) * 34, 0, Math.sin(a) * 34, 0x8a8a8a]); }
    ring = blocks(rl, 1.2); ring.rotation.x = 0.3; sc.add(ring);
  }
  return (t, d) => {
    const u = t / d, w = p.slow ? 0.8 : 1.5 + 14 * u;      // 回る速さ（slow：今の地球のゆっくり）
    e.rotation.y = p.slow ? t * 0.8 : t * 1.5 + 7 * u * u * d;
    streak.forEach(m => {
      const q = m.userData; m.visible = !p.slow; const a = q.a + t * w * 0.35;
      m.position.set(Math.cos(a) * q.r, q.y, Math.sin(a) * q.r); m.rotation.y = -a;
    });
    if (ring) ring.rotation.y = t * 0.3;
    C.position.set(lerp(-10, 10, u), 10, lerp(80, 70, u)); C.lookAt(0, 0, 0);
  };
}

// ---------- 場面：地軸がふらつく ----------
function axisScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  sc.add(stars(1800, 600, 2.4)); sc.add(new THREE.AmbientLight(0xffffff, 0.4));
  const dl = new THREE.DirectionalLight(0xffffff, 1.3); dl.position.set(-100, 40, 80); sc.add(dl);
  const g = new THREE.Group(); sc.add(g);
  const e = planet(18, earthColor); g.add(e);
  g.add(new THREE.Mesh(new THREE.BoxGeometry(1.6, 60, 1.6), new THREE.MeshBasicMaterial({ color: 0xff3b30 })));
  return (t, d) => {
    const a = p.amp ?? 1;
    g.rotation.z = 0.41 + a * (0.6 * Math.sin(t * 3.4) + 0.3 * Math.sin(t * 8.1));
    g.rotation.x = a * 0.4 * Math.sin(t * 4.7 + 1);
    e.rotation.y = t * 4;
    C.position.set(lerp(-12, 12, t / d), 8, 84); C.lookAt(0, 0, 0);
  };
}

// ---------- 場面：太陽と地球。月がいない ----------
function spaceScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  sc.add(stars(1800, 800, 2.4)); sc.add(new THREE.AmbientLight(0xffffff, 0.25));
  const sun = planet(14, (x, y, z) => (noise3(x * 2, y * 2, z * 2) > 0.3 ? 0xffb020 : COL.sun), 1, new THREE.MeshBasicMaterial());
  sun.position.set(-6, 56, -40); sc.add(sun);
  const pl = new THREE.PointLight(0xffffff, 3, 0, 0); pl.position.copy(sun.position); sc.add(pl);
  const e = planet(10, earthColor); e.position.set(2, 0, 10); sc.add(e);
  const rl = [];
  for (let i = 0; i < 48; i++) if (i % 2) { const a = i / 48 * Math.PI * 2; rl.push([Math.cos(a) * 24, 0, Math.sin(a) * 24, 0x8a8a8a]); }
  const r = blocks(rl, 1); r.position.copy(e.position); r.rotation.x = 0.3; sc.add(r);
  return (t, d) => {
    const u = t / d;
    e.rotation.y = t * 3; sun.rotation.y = t * 0.4; r.rotation.y = t * 0.6;
    C.position.set(lerp(18, 28, u), lerp(-2, 4, u), lerp(120, 108, u)); C.lookAt(0, 4, 0);
  };
}

const SCENES = { land: landScene, flight: flightScene, rewind: rewindScene, spin: spinScene, axis: axisScene, space: spaceScene };

window.setup = (j) => {
  job = j; seed = 12345;
  if (!R) {
    R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    document.body.appendChild(R.domElement);
  }
  R.setPixelRatio(1); R.setSize(j.w, j.h);
  C = new THREE.PerspectiveCamera(j.fov || 55, j.w / j.h, 0.1, 5000);
  upd = SCENES[j.scene](j.p || {});
  S = CUR;
  return true;
};
window.frame = (t) => { upd(t, job.d); R.render(S, C); return true; };
window.ready = true;
