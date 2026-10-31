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
  moon: 0xbdbdbd, moon2: 0x9a9a9a, lava: 0xe8552a, ice: 0xdff3ff,
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
      list.push([x, k, z, p.ice ? (k < y ? 0xb8d4e8 : ((x * 7 + z * 3) % 5 ? COL.ice : COL.snow))
                         : (k < y ? COL.dirt : (y <= 0 ? COL.sand : ((x * 7 + z * 3) % 5 ? COL.grass : COL.grass2)))]);
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
  (p.notrees || p.ice ? [] : [[-6, -4], [-3, -9], [5, -6], [8, 3], [-10, 1], [-8, 6], [11, -2], [-13, -6], [3, -12], [-2, 2]]).forEach(([x, z]) => {
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
  const ups = props(sc, p, top);                        // 小道具（家と釘・ひも・車・マッチ・山・空気の柱・ボール）
  // 太陽・光・星（見た目は試作1版のまま。昼夜の切り替えだけゆっくり・なめらかにする）
  // 点滅・急な明暗の切り替えは禁止。明暗の大きな変化は1秒に3回未満（nazo/RULES.md）
  const sun = new THREE.Mesh(new THREE.BoxGeometry(9, 9, 9), new THREE.MeshBasicMaterial({ color: COL.sun }));
  sc.add(sun);
  const amb = new THREE.AmbientLight(0xffffff, 0.55); sc.add(amb);
  const dl = new THREE.DirectionalLight(0xffffff, 1.1); sc.add(dl);
  const st = stars(1400, 500, p.night ? 3 : 2.2); sc.add(st);
  const skyDay = new THREE.Color(0x6ec0ff), skyDusk = new THREE.Color(0xff7a3a), skyNight = new THREE.Color(0x03040c);
  const hot = new THREE.Color(0xff9a3a), snowSky = new THREE.Color(0xc8d8e8);
  const camOf = c => (Array.isArray(c) ? c : LAND_CAMS[c || "hook"]);   // 名前か [[位置],[見る点]]
  const [cp, ct] = camOf(p.cam);
  const [cp2, ct2] = camOf(p.cam_to || p.cam);
  return (t, d) => {
    const u = d ? t / d : 0, tt = t + (p.t0 || 0);
    const ph = (p.sun ? (tt / p.sun) * Math.PI * 2 : 0) + (p.ph0 ?? 0.9);
    let sx = Math.cos(ph) * 160, sy = Math.sin(ph) * 120, sz = -90;
    if (p.polar) { sx = Math.cos(ph) * 150; sz = Math.sin(ph) * 150; sy = 7; }   // 北極：太陽が地平線すれすれをぐるりと回る
    sun.position.set(sx, sy, sz); sun.rotation.set(tt, tt * 0.7, 0);
    dl.position.set(sx, Math.max(sy, -10), sz);
    const el = p.polar ? 0.12 : Math.sin(ph);
    const day = p.night ? 0 : sstep((el + 0.3) / 0.9);          // 昼⇄夜を広い幅でなめらかに（明るさの上限・下限は前のまま）
    const dusk = p.night ? 0 : Math.max(0, 1 - Math.abs(el) * 2.2) ** 2;
    const sky = skyNight.clone().lerp(skyDay, day).lerp(skyDusk, dusk * 0.55);
    if (p.seasons) {                       // 雪⇄猛暑：なめらかに行き来する（1往復 p.season_p 秒）
      const w = 0.5 - 0.5 * Math.cos(2 * Math.PI * tt / (p.season_p || 2.6));   // 0=雪 1=猛暑
      sky.lerp(snowSky, 0.5 * (1 - w)).lerp(hot, 0.55 * w);
      snow.visible = w < 0.98; snow.position.y = -1.05 * w;   // 雪が地面に沈むように溶ける
    } else snow.visible = false;
    sc.background = sky;
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
    act(ch, p, t, tt, cy, CX);                             // キャラの動き（すべる・跳ぶ・息切れ・震える）
    ups.forEach(f => f(t, d, u));
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
      flash.material.opacity = Math.max(0, 0.6 - b * 1.5); flash.scale.setScalar(1 + b * 14);
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
    if (p.untilt !== undefined) {                         // 傾き23.4度 → p.untilt の時刻から0度へ（揺らさない）
      g.rotation.set(0, 0, 0.41 * (1 - sstep((t / d - p.untilt) / 0.06)));
      e.rotation.y = t * 3; const c = ease(Math.min(1, t / d / p.untilt));
      C.position.set(0, 6, lerp(150, 78, c)); C.lookAt(0, 0, 0); C.rotateZ(t / d * 0.25); return;
    }
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


// ---------- 場面：潮のふくらみ（月の引力が海を引っぱり、自転にブレーキがかかる） ----------
// 出典：Wikipedia「Tidal acceleration」— 海は月の側と反対側にふくらむ。自転でふくらみが月より前へ引きずられ、
//       そのずれが地球の自転を遅くする。
//   p.drag   … ふくらみを回転の向きに少しずらし、地球の回転をだんだん遅くする（ブレーキ）
//   p.vanish … 月が消え、ふくらみが引いて、回転が速くなっていく（ブレーキなし）
function tideScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  sc.add(stars(1800, 600, 2.4)); sc.add(new THREE.AmbientLight(0xffffff, 0.45));
  const dl = new THREE.DirectionalLight(0xffffff, 1.2); dl.position.set(-60, 40, 100); sc.add(dl);
  const R0 = 13;
  const eg = new THREE.Group(); sc.add(eg);           // 地球は z 軸（こちら向き）のまわりに回る
  const earth = planet(R0, earthColor); eg.add(earth);
  const moon = planet(5, moonColor); const MP = new THREE.Vector3(0, 38, 0); moon.position.copy(MP); sc.add(moon);
  // 海のふくらみ：球の表面の向きごとに、外へ伸びる水のブロック
  const dirs = shell(R0, () => 0).map(b => new THREE.Vector3(b[0], b[1], b[2]).normalize());
  const water = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshLambertMaterial({ color: 0x3a8ee6 }), dirs.length);
  sc.add(water);
  const o = new THREE.Object3D();
  // 回転の向きを示す赤い矢印ブロックの輪（地球と一緒に回る）
  const ring = new THREE.Group(); sc.add(ring);
  for (let i = 0; i < 6; i++) {                        // 矢印＝長い棒＋先の大きなブロック（反時計回り）
    const a = i / 6 * Math.PI * 2, r = R0 + 8;
    const g = new THREE.Group(); g.rotation.z = a; ring.add(g);
    const mat = new THREE.MeshBasicMaterial({ color: 0xff4a3a });
    for (let k = 0; k < 4; k++) { const b = new THREE.Mesh(new THREE.BoxGeometry(1.1, 1.1, 1.1), mat); const q = k * 0.11; b.position.set(Math.cos(q) * r, Math.sin(q) * r, 0); g.add(b); }
    const tip = new THREE.Mesh(new THREE.BoxGeometry(2.2, 2.2, 1.2), mat); tip.position.set(Math.cos(0.48) * r, Math.sin(0.48) * r, 0); tip.rotation.z = 0.48 + 0.78; g.add(tip);
  }
  // 引力の流れ（地球から月へ向かう小さなブロック）
  const pull = [];
  for (let i = 0; i < 18; i++) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.9, 0.9), new THREE.MeshBasicMaterial({ color: 0xffe14a }));
    m.userData = { x: (i % 3 - 1) * 5, k: i / 18 }; sc.add(m); pull.push(m);
  }
  let ang = 0;
  return (t, d) => {
    const u = t / d;
    let spd = 1.4, bulge = Math.min(1, t / 0.6), lag = 0, gone = 0;
    if (p.drag) { spd = lerp(2.6, 0.5, sstep(u)); bulge = 1; lag = 0.42 * sstep(u / 0.4); }
    if (p.vanish) { gone = sstep((u - 0.1) / 0.35); spd = lerp(0.5, 4.5, sstep((u - 0.2) / 0.8)); bulge = 1 - gone; lag = 0.42 * (1 - gone); }
    ang = spd * t + (p.drag ? -1.2 * t * t / d : 0);
    eg.rotation.z = ang; ring.rotation.z = ang * 0.999;
    
    moon.visible = gone < 0.98; moon.scale.setScalar(Math.max(0.01, 1 - gone)); moon.rotation.y = t * 0.6;
    const axis = new THREE.Vector3(-Math.sin(lag), Math.cos(lag), 0);   // ふくらみの向き（回転の向きへ lag だけずれる）
    dirs.forEach((v, i) => {
      const c = v.dot(axis), h = bulge * 6.5 * Math.max(0, c * c - 0.35) / 0.65;   // ふくらみの所だけ水を盛る（ほかは陸と海が見える）
      o.position.copy(v).multiplyScalar(R0 + h / 2 - 0.5);
      o.lookAt(o.position.clone().multiplyScalar(2)); o.scale.set(h > 0.15 ? 1 : 0.001, h > 0.15 ? 1 : 0.001, Math.max(h, 0.001) + 0.6);
      o.updateMatrix(); water.setMatrixAt(i, o.matrix);
    });
    water.instanceMatrix.needsUpdate = true;
    pull.forEach(m => {
      const q = (m.userData.k + t * 0.9) % 1; m.visible = !p.drag && gone < 0.5;
      m.position.set(m.userData.x * (1 - q) * 0.6, R0 + 7 + q * (MP.y - R0 - 13), 2);
    });
    // 地球は字幕より上・少し右に（左下のずんだもんと下の字幕にかからない位置）
    C.position.set(lerp(-9, -3, u), -6, lerp(122, 116, u)); C.lookAt(lerp(-8, -3, u), -6, 0);
  };
}

// ---------- 島の小道具（p のキーで出す） ----------
//   house:1  ブロックの家と釘。nails:1 で釘が1本ずつ抜け、板が少しずれる（壊れる表現はしない）
//   rope:1   杭に結んだひも。untie:1 でほどけて落ちる
//   car:"spin"（車輪が空回りして進めない）/ "slide"（ブレーキが効かず滑り続ける）/ "drive"（ふつうに走る）
//   match:1  マッチを箱でこする。火はつかない
//   mountain:1 富士山の形の山（遠景）  air:1 空気の柱（air_half:1 で半分の高さに）  ball:1 ボールの放物線（half_g:1 で2本目が2倍遠く）
function props(sc, p, top) {
  const ups = [], Y = (x, z) => (top[`${x},${z}`] ?? 1) + 0.5;
  const box = (w, h, d, col, basic) => new THREE.Mesh(new THREE.BoxGeometry(w, h, d),
    basic ? new THREE.MeshBasicMaterial({ color: col }) : new THREE.MeshLambertMaterial({ color: col }));
  if (p.house) {
    const g = new THREE.Group(), y0 = Y(-5, 0); g.position.set(-5, y0, 0); sc.add(g);
    const planks = [], nails = [];
    for (let k = 0; k < 5; k++) {                         // 正面の板（横に5枚）
      const pl = box(7, 0.9, 0.5, k % 2 ? 0xb07a45 : 0xa06a38); pl.position.set(0, 0.5 + k, 3); g.add(pl); planks.push(pl);
      [-3, 3].forEach(x => { const n = box(0.35, 0.35, 1.2, 0x9a9a9a); n.position.set(x, 0.5 + k, 3.35); g.add(n); nails.push(n); });
    }
    const back = box(7, 5, 6, 0x8a5a30); back.position.set(0, 2.5, 0); g.add(back);
    const post1 = box(0.8, 5.2, 0.8, 0x6a4020); post1.position.set(-3, 2.6, 3); g.add(post1);
    const post2 = post1.clone(); post2.position.x = 3; g.add(post2);
    const roof = box(8.5, 1, 7.5, 0xb03a2e); roof.position.set(0, 5.5, 0.2); g.add(roof);
    ups.push((t, d) => {
      if (!p.nails) return;
      nails.forEach((n, i) => {                          // 1本ずつ、すーっと抜ける
        const q = Math.max(0, Math.min(1, (t - 0.15 - i * 0.07) / 0.45));
        n.position.z = 3.35 + q * 2.8; n.rotation.x = q * 0.6;
      });
      planks.forEach((pl, k) => {                         // 釘が抜けた板が、少しずつ滑ってずれる
        const q = Math.max(0, t - 0.6 - k * 0.12);
        pl.position.x = Math.min(2.2, q * q * 3) * (k % 2 ? 1 : -1); pl.rotation.z = Math.min(0.25, q * 0.3) * (k % 2 ? -1 : 1);
      });
    });
  }
  if (p.rope) {
    const g = new THREE.Group(), y0 = Y(-1, 2); g.position.set(-1, y0, 2); sc.add(g);
    const post = box(0.9, 4, 0.9, 0x6a4020); post.position.y = 2; g.add(post);
    const segs = [];
    for (let i = 0; i < 26; i++) { const b = box(0.45, 0.45, 0.45, 0xff7a3a); g.add(b); segs.push(b); }
    ups.push((t, d) => {
      const q = p.untie ? sstep((t - 0.3) / 0.9) : 0;
      segs.forEach((b, i) => {
        const a = i / 26 * Math.PI * 4.2;                 // 結び目：杭に2回巻いたひも
        const kx = Math.cos(a) * 0.9, kz = Math.sin(a) * 0.9, ky = 2.6 + i * 0.03;
        const fx = 0.9 + i * 0.32, fy = Math.max(0.3, 2.6 - q * 3 - i * 0.02), fz = 0;   // ほどけて垂れる
        b.position.set(lerp(kx, fx, q), lerp(ky, fy, q), lerp(kz, fz, q) + Math.sin(t * 6 + i) * 0.05 * q);
      });
    });
  }
  if (p.car) {
    const g = new THREE.Group(); sc.add(g);
    const body = box(4.5, 1.4, 2.4, 0xd83a30); body.position.y = 1.2; g.add(body);
    const cab = box(2.4, 1.1, 2.2, 0xf2f2f2); cab.position.set(-0.3, 2.4, 0); g.add(cab);
    const lamp = box(0.2, 0.4, 0.6, 0x552222, true); lamp.position.set(-2.3, 1.4, 0); g.add(lamp);
    const wheels = [];
    [[-1.5, 1.25], [1.5, 1.25], [-1.5, -1.25], [1.5, -1.25]].forEach(([x, z]) => {
      const w = new THREE.Group(); w.position.set(x, 0.55, z); g.add(w); wheels.push(w);
      const tire = box(1.1, 1.1, 0.5, 0x222222); w.add(tire);
      const hub = box(0.5, 0.5, 0.55, 0xcccccc); w.add(hub);
    });
    const x0 = p.car === "slide" ? -9 : 2, z0 = 8, y0 = Y(2, 8) - 0.4;
    g.position.set(x0, y0, z0);
    ups.push((t, d) => {
      if (p.car === "spin") { wheels.forEach(w => (w.rotation.z = -t * 18)); g.position.x = x0 + Math.sin(t * 40) * 0.05; }
      else if (p.car === "slide") {                        // ブレーキを踏んでも止まらない（車輪は止まっている）
        g.position.x = x0 + t * 7; lamp.material.color.setHex(t > 0.3 ? 0xff2a2a : 0x552222); g.rotation.y = Math.sin(t * 2) * 0.12;
      } else { wheels.forEach(w => (w.rotation.z = -t * 8)); g.position.x = x0 + t * 3; }
    });
  }
  if (p.match) {
    const g = new THREE.Group(), y0 = Y(1, 9); g.position.set(1, y0 + 1.6, 9); sc.add(g);
    const mbox = box(3.2, 1.6, 2, 0x2f6fb0); g.add(mbox);
    const strip = box(3.25, 0.5, 0.2, 0x5a3a2a); strip.position.set(0, 0, 1.05); g.add(strip);
    const stick = new THREE.Group(); g.add(stick);
    const wood = box(3.6, 0.3, 0.3, 0xe8c890); wood.position.x = 1.8; stick.add(wood);
    const head = box(0.6, 0.55, 0.55, 0xc8202a); stick.add(head);
    ups.push((t) => { stick.position.set(Math.sin(t * 11) * 1.2, 0, 1.4); stick.rotation.z = 0.1 + Math.sin(t * 11) * 0.05; });
  }
  if (p.mountain) {
    const ml = [];
    for (let y = 0; y < 26; y++) {
      const r = 24 * Math.pow(1 - y / 26, 1.5) + 2.5;     // 富士山のように裾が広がる形
      for (let a = 0; a < 360; a += 360 / Math.max(8, r * 3)) {
        const x = Math.round(Math.cos(a * Math.PI / 180) * r), z = Math.round(Math.sin(a * Math.PI / 180) * r);
        ml.push([x * 1.6, y * 1.6, z * 1.6, y > 19 ? COL.snow : (y > 15 ? 0x8a94b8 : 0x5a6a9a)]);
      }
    }
    const m = blocks(ml, 1.7); m.position.set(-30, -2, -150); sc.add(m);
  }
  if (p.air) {                                            // 空気の柱：上に積んだ空気のブロック
    const g = new THREE.Group(); g.position.set(4, Y(4, 6), 6); sc.add(g);
    const cells = [];
    for (let k = 0; k < 14; k++) { const b = box(2.6, 0.9, 2.6, k % 2 ? 0xbfe6ff : 0x9fd2f5); b.position.y = 4.5 + k; g.add(b); cells.push(b); }
    ups.push((t) => {
      const q = p.air_half ? sstep((t - 0.4) / 0.8) : 0;
      cells.forEach((b, k) => { b.visible = k < 14 - 7 * q + 0.01; b.position.y = 4.5 + k; });
      g.rotation.y = t * 0.3;
    });
  }
  if (p.ball) {
    const mk = col => { const b = box(1.6, 1.6, 1.6, col); sc.add(b); return b; };
    const b1 = mk(0xf2f2f2), b2 = p.half_g ? mk(0xffd23a) : null;
    const dots = [b1, b2].filter(Boolean).map(b => Array.from({ length: 24 }, () => {   // 通った跡の点
      const m = box(0.5, 0.5, 0.5, b.material.color.getHex()); sc.add(m); m.visible = false; return m; }));
    const pos = (k, tt, T1, v) => {                       // 同じ速さ・角度で投げる。重力が半分なら2倍の高さ・2倍の距離
      const g = 2 * v / T1 / k, s = Math.min(tt, T1 * k);
      return [-15 + v * 0.9 * s, 3 + v * s - 0.5 * g * s * s, 4];
    };
    ups.push((t, d) => {
      const T1 = d * 0.42, v = 9;
      [b1, b2].forEach((b, j) => {
        if (!b) return;
        b.position.set(...pos(j + 1, t, T1, v));
        dots[j].forEach((m, i) => { const ti = i * T1 * (j + 1) / 24; m.visible = ti < t; m.position.set(...pos(j + 1, ti, T1, v)); });
      });
    });
  }
  return ups;
}

// ---------- ブロックのキャラの動き（p.act） ----------
//   slip（足がすべって尻もち、立てずにくるくる）/ jump（p.jump_h の高さまで跳ぶ。半分の重力ではゆっくり高く）
//   pant（ぜーぜー：速く上下し、口から白い息のブロック）/ shiver（ぶるぶる震える）
function act(ch, p, t, tt, cy, CX) {
  if (!p.act) return;
  const B = ch.userData.body;
  if (p.act === "slip") {
    const q = Math.min(1, t / 0.5);
    ch.position.set(CX + Math.sin(t * 5) * 1.5, cy - 0.9 * sstep((t - 0.3) / 0.3) + Math.abs(Math.sin(t * 9)) * 0.2, 6);
    ch.rotation.set(-0.9 * sstep((t - 0.3) / 0.3), t * 3, Math.sin(t * 12) * 0.25 * q);
  } else if (p.act === "jump") {
    const per = p.jump_p || 1.2, k = (t % per) / per, H = p.jump_h || 3;
    ch.position.set(CX, cy + 4 * H * k * (1 - k), 6); ch.rotation.set(0, 0.35 + k * 0.4, 0);
    ch.userData.ears.forEach((e, i) => { e.rotation.z = (i ? -1 : 1) * (0.5 - k) * 0.8; });
  } else if (p.act === "pant") {
    t = tt;                                               // ループのつなぎ用に時刻（t0 込み）で動かす
    ch.position.set(CX, cy + Math.abs(Math.sin(t * 14)) * 0.3, 6); ch.rotation.set(0.15 + 0.1 * Math.sin(t * 14), 0.35, 0);
    if (!ch.userData.puffs) {
      ch.userData.puffs = [0, 1, 2, 3].map(() => { const m = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.5), new THREE.MeshBasicMaterial({ color: 0xffffff })); ch.parent.add(m); return m; });
    }
    ch.userData.puffs.forEach((m, i) => {
      const q = (((t * 1.6 + i / 4) % 1) + 1) % 1;
      m.position.set(CX + 0.9 + q * 2.4, cy + 2.4 + q * 1.4, 7.4 + q); m.scale.setScalar(0.4 + q * 0.7); m.visible = q < 0.85;
    });
  } else if (p.act === "shiver") {
    ch.position.set(CX + Math.sin(t * 60) * 0.12, cy, 6); ch.rotation.set(0, 0.35, Math.sin(t * 50) * 0.05);
  }
}

// ---------- 場面：太陽のまわりを回る地球（傾きの棒つき） ----------
//   p.tilt（度。23.4 か 0）、p.per（1周の秒数）、p.untilt_at（この割合の時刻から傾きが0へ）
function orbitScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  sc.add(stars(1800, 800, 2.4)); sc.add(new THREE.AmbientLight(0xffffff, 0.22));
  const sun = planet(6, (x, y, z) => (noise3(x * 2, y * 2, z * 2) > 0.3 ? 0xffb020 : COL.sun), 1, new THREE.MeshBasicMaterial()); sc.add(sun);
  const pl = new THREE.PointLight(0xffffff, 3.2, 0, 0); sc.add(pl);
  const g = new THREE.Group(); sc.add(g);
  const tiltG = new THREE.Group(); g.add(tiltG);
  const e = planet(4, earthColor); tiltG.add(e);
  tiltG.add(new THREE.Mesh(new THREE.BoxGeometry(0.5, 15, 0.5), new THREE.MeshBasicMaterial({ color: 0xff3b30 })));
  const eq = [];                                           // 赤道の線（黄色）
  for (let i = 0; i < 32; i++) { const a = i / 32 * Math.PI * 2; eq.push([Math.cos(a) * 4.6, 0, Math.sin(a) * 4.6, 0xffe14a]); }
  tiltG.add(blocks(eq, 0.4));
  const OR = 17, path = [];
  for (let i = 0; i < 60; i++) if (i % 2) { const a = i / 60 * Math.PI * 2; path.push([Math.cos(a) * OR, 0, Math.sin(a) * OR, 0x555a66]); }
  sc.add(blocks(path, 0.8));
  return (t, d) => {
    const u = t / d, per = p.per || 3.2, a = t / per * Math.PI * 2 + (p.a0 || 0);
    g.position.set(Math.cos(a) * OR, 0, Math.sin(a) * OR);
    let tilt = (p.tilt ?? 23.4) * Math.PI / 180;
    if (p.untilt_at !== undefined) tilt *= 1 - sstep((u - p.untilt_at) / 0.12);
    tiltG.rotation.set(0, 0, tilt);                       // 傾きの向きは公転しても変わらない
    e.rotation.y = t * 5; sun.rotation.y = t * 0.3;
    C.position.set(lerp(5, -5, u), 40, lerp(44, 40, u)); C.lookAt(0, -2, 0);
  };
}

// ---------- 場面：重力の矢印（地球へ向かう矢印が、0.00 で半分の長さに） ----------
function gravityScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  sc.add(stars(1800, 600, 2.4)); sc.add(new THREE.AmbientLight(0xffffff, 0.4));
  const dl = new THREE.DirectionalLight(0xffffff, 1.3); dl.position.set(-100, 40, 80); sc.add(dl);
  const e = planet(14, earthColor); sc.add(e);
  const arrows = [];
  for (let i = 0; i < 12; i++) {
    const a = i / 12 * Math.PI * 2, g = new THREE.Group(); g.rotation.z = a; sc.add(g);
    const shaft = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0x5ad1ff })); g.add(shaft);
    const tip = new THREE.Mesh(new THREE.BoxGeometry(2.2, 2.2, 1), new THREE.MeshBasicMaterial({ color: 0x5ad1ff })); tip.rotation.z = Math.PI / 4; g.add(tip);
    arrows.push({ g, shaft, tip });
  }
  const KB = p.burst ?? 0.9;
  return (t, d) => {
    const u = t / d, L = 12 * (1 - 0.5 * sstep((u - KB) / 0.06));   // 矢印の長さ＝重力の強さ
    arrows.forEach(({ shaft, tip }, i) => {
      const r0 = 17, flow = ((t * 1.5 + i * 0.13) % 1) * 0.6;
      shaft.scale.set(1, L, 1); shaft.position.set(0, r0 + L / 2 + 1.5 - flow, 0); tip.position.set(0, r0 + 0.6 - flow, 0);
    });
    e.rotation.y = t * 0.8;
    const c = ease(Math.min(1, u / KB));
    C.position.set(Math.sin(u * 2) * 8, 4, lerp(140, 82, c)); C.lookAt(0, 0, 0); C.rotateZ(u * 0.3);
  };
}

// ---------- 場面：表面のでこぼこ（摩擦のもと）。0.00 でつるつるになる ----------
function surfaceScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x1a1f2a);
  sc.add(new THREE.AmbientLight(0xffffff, 0.55));
  const dl = new THREE.DirectionalLight(0xffffff, 1.0); dl.position.set(30, 60, 40); sc.add(dl);
  const N = 22, list = [], hs = [];
  for (let x = -N; x <= N; x++) for (let z = -N; z <= N; z++) {
    const h = Math.max(0, Math.round(1.6 * noise3(x * 0.6, 0.3, z * 0.6) + rnd() * 1.4));
    hs.push(h); list.push([x, 0, z, (x + z) % 2 ? 0xa06a38 : 0x8a5a30]);
  }
  const floor = blocks(list); sc.add(floor);
  const top = new THREE.Group(); sc.add(top);              // 上にのった木の箱（でこぼこが引っかかる）
  const crate = new THREE.Mesh(new THREE.BoxGeometry(10, 6, 10), new THREE.MeshLambertMaterial({ color: 0xc8904a })); top.add(crate);
  const o = new THREE.Object3D(), KB = p.burst ?? 0.9;
  return (t, d) => {
    const u = t / d, flat = sstep((u - KB) / 0.08);
    let i = 0;
    for (let x = -N; x <= N; x++) for (let z = -N; z <= N; z++, i++) {
      const h = 1 + hs[i] * (1 - flat);
      o.position.set(x, h / 2, z); o.scale.set(1, h, 1); o.updateMatrix(); floor.setMatrixAt(i, o.matrix);
    }
    floor.instanceMatrix.needsUpdate = true;
    const hmax = 1 + 3 * (1 - flat);
    top.position.set(Math.sin(t * 9) * 0.3 * (1 - flat) + flat * (u - KB) * 60, hmax + 3, 0);   // つるつるになると滑っていく
    const c = ease(Math.min(1, u / KB));
    C.position.set(lerp(40, 14, c), lerp(36, 9, c), lerp(46, 22, c)); C.lookAt(0, 2, 0);
  };
}

const SCENES = { orbit: orbitScene, gravity: gravityScene, surface: surfaceScene, tide: tideScene, land: landScene, flight: flightScene, rewind: rewindScene, spin: spinScene, axis: axisScene, space: spaceScene };

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
