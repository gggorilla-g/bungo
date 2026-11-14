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
//   space  … 太陽と地球。月の通り道だけあって月はいない。p.sun_off（0〜1 の時刻）で太陽が消える
//   seafloor … 海の断面（大陸棚・深海平原・海嶺・海溝・海山）。海面が下がって干上がる（11/7〜の回で追加）
// どの場面でも使える p:
//   view / view_to … カメラを [[位置],[見る点]] で上書きする（場面のカメラを回ごとに変えるため。文の長さでなめらかに移る）
//   earth … ブロックの地球の色。"dry"（海が干上がった茶色）/ "snow"（全球凍結の白）
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
let EMODE = "";
const earthColor = (x, y, z) => {
  if (Math.abs(y) > 0.86) return COL.snow;
  const n = noise3(x, y, z);
  if (EMODE === "snow") return n > 0.35 ? COL.snow : (n > -0.4 ? COL.ice : 0xc4dcee);
  if (EMODE === "dry") return n > 0.35 ? (n > 0.75 ? COL.dirt : COL.grass) : (n > 0.25 ? COL.sand : (n < -0.4 ? 0x5e4a3a : 0x7a6450));
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

// ブロックのキャラ（黄緑の髪・枝豆のさやの耳・白いブラウス＋緑のサスペンダースカート。色と形は自前の単色ブロック）
function blockChar() {
  const g = new THREE.Group(), body = new THREE.Group(); g.add(body);
  const add = (w, h, d, x, y, z, col, par = body) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshLambertMaterial({ color: col }));
    m.position.set(x, y, z); par.add(m); return m;
  };
  const HAIR = 0xa6d94a, HAIR2 = 0x8cc63a, SKIN = 0xffe2c8, WHITE = 0xf6f6f6, PINK = 0xf59ab8, GRN = 0x4f9e2c, POD = 0x5aa830, BEAN = 0xb4e46a;
  add(0.3, 0.5, 0.3, -0.25, -0.35, 0, WHITE); add(0.3, 0.5, 0.3, 0.25, -0.35, 0, WHITE);          // 脚
  add(0.34, 0.16, 0.42, -0.25, -0.62, 0.04, GRN); add(0.34, 0.16, 0.42, 0.25, -0.62, 0.04, GRN);   // くつ
  add(1.2, 0.5, 0.78, 0, 0.15, 0, GRN);                          // スカート
  add(1.0, 0.7, 0.6, 0, 0.75, 0, WHITE);                         // ブラウス
  add(0.14, 0.7, 0.64, -0.26, 0.75, 0, GRN); add(0.14, 0.7, 0.64, 0.26, 0.75, 0, GRN);            // サスペンダー
  add(0.7, 0.12, 0.66, 0, 1.12, 0, PINK);                        // 襟
  [-1, 1].forEach(sx => {                                        // 腕（白いそで・ピンクのそで口・手）
    add(0.28, 0.62, 0.28, sx * 0.66, 0.78, 0, WHITE);
    add(0.32, 0.12, 0.32, sx * 0.66, 0.42, 0, PINK);
    add(0.22, 0.18, 0.22, sx * 0.66, 0.27, 0, SKIN);
  });
  add(1.3, 1.2, 1.2, 0, 1.75, 0, SKIN);                          // 顔
  add(1.42, 0.45, 1.32, 0, 2.45, -0.04, HAIR);                   // 髪（上）
  add(1.42, 1.15, 0.32, 0, 1.92, -0.62, HAIR);                   // 髪（後ろ）
  add(1.34, 0.22, 0.14, 0, 2.2, 0.62, HAIR);                     // 前髪
  add(0.3, 0.2, 0.14, -0.3, 2.04, 0.63, HAIR2); add(0.24, 0.16, 0.14, 0.32, 2.06, 0.63, HAIR2);
  add(0.16, 0.85, 0.36, -0.7, 1.72, 0.4, HAIR); add(0.16, 0.85, 0.36, 0.7, 1.72, 0.4, HAIR);     // 横の髪
  [-1, 1].forEach(sx => {                                        // 目（琥珀色＋光）
    add(0.24, 0.34, 0.05, sx * 0.3, 1.8, 0.61, 0xe0a020);
    add(0.12, 0.16, 0.06, sx * 0.3, 1.74, 0.62, 0x8a5410);
    add(0.08, 0.08, 0.07, sx * 0.3 - 0.05, 1.9, 0.625, 0xffffff);
  });
  add(0.35, 0.12, 0.05, -0.45, 1.5, 0.61, 0xff9aa6); add(0.35, 0.12, 0.05, 0.45, 1.5, 0.61, 0xff9aa6);
  add(0.18, 0.06, 0.05, 0, 1.44, 0.61, 0xc8505a);                // 口
  const ears = [-1, 1].map(sx => {                               // 枝豆のさや（緑のさや＋豆のふくらみ）
    const e = new THREE.Group();
    [[0, 0], [0.28, 0.42], [0.56, 0.84]].forEach(([dx, dy], k) => {
      const pod = add(0.4, 0.46, 0.34, sx * (0.78 + dx), dy, 0, POD, e);
      pod.rotation.z = -sx * 0.55;
      const bean = add(0.3, 0.3, 0.2, sx * (0.78 + dx), dy, 0.14, BEAN, e);
      bean.rotation.z = -sx * 0.55;
    });
    add(0.16, 0.22, 0.16, sx * 1.48, 1.18, 0, POD, e);           // さやの先
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
  const seaC = new THREE.Color(p.dry ? 0x9a7a58 : COL.sea), iceC = new THREE.Color(0xdfeef8);   // p.dry：海が干上がった地面 / p.freeze：海が凍る
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000), new THREE.MeshLambertMaterial({ color: seaC.clone() }));
  sea.rotation.x = -Math.PI / 2; sea.position.y = (p.sea_y ?? 0) - 0.5; sc.add(sea);   // p.sea_y：海面を上げる（島の低い所が沈む）
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
  for (let i = 0; i < (p.thick ? 46 : 12); i++) {                     // p.thick：空の大半をおおう雲
    const cl = [], w = 3 + Math.floor(rnd() * 5);
    for (let a = 0; a < w; a++) for (let b = 0; b < 2; b++) if (rnd() > 0.2) cl.push([a * 1.5, 0, b * 1.5, COL.cloud]);
    const m = blocks(cl, 1.5, new THREE.MeshLambertMaterial({ emissive: 0x555555 }));
    m.position.set(-60 + rnd() * 120, 16 + rnd() * 10, -50 + rnd() * 60); clouds.add(m);
  }
  sc.add(clouds); clouds.visible = !p.noclouds && !p.noair;
  // 雨（p.rain）：細い青いブロックが落ちる。位置は時刻だけで決める
  const rain = [];
  const rock = p.rain === "rock";                       // p.rain="rock"：空から小石が斜めに落ちる（空気がない回）
  if (p.rain) for (let i = 0; i < (rock ? 40 : 260); i++) {
    const m = new THREE.Mesh(rock ? new THREE.BoxGeometry(0.7, 0.7, 0.7) : new THREE.BoxGeometry(0.12, 1.1, 0.12),
      rock ? new THREE.MeshLambertMaterial({ color: 0x8a8a8a }) : new THREE.MeshBasicMaterial({ color: 0x9fd2ff }));
    m.userData = { x: -30 + rnd() * 50, z: -24 + rnd() * 40, k: rnd() }; sc.add(m); rain.push(m);
  }
  // 地球の輪（p.ring）：空にかかる帯。南の空を東から西へ（ブロックの帯を数列）
  if (p.ring) {
    const rl = [];
    for (let a = -1.3; a <= 1.3; a += 0.006) for (let w = 0; w < 6; w++) {   // 南の空の高さ約30度まで上がる弓
      if (w === 4) continue;                                     // 帯のすき間
      rl.push([Math.sin(a) * 400, -60 + Math.cos(a) * (220 + w * 7), -150 - Math.cos(a) * (110 + w * 3.5), w < 4 ? 0xeee6d6 : 0xcfc6b4]);
    }
    const ring = blocks(rl, 5, new THREE.MeshBasicMaterial()); sc.add(ring);
  }
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
  sun.scale.setScalar(p.sun_scale || 1); sc.add(sun);                  // p.sun_scale：太陽が大きく見える
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
    const vac = p.noair ? 1 : (p.air_off !== undefined ? sstep((u - p.air_off) / 0.12) : 0);   // 空気がない：昼でも空は黒い
    const off = p.sun_off !== undefined ? sstep((u - p.sun_off) / 0.15) : 0;               // 太陽が消える（ゆっくり暗くなる）
    const sky = skyNight.clone().lerp(skyDay, day * (1 - vac) * (1 - off)).lerp(skyDusk, dusk * 0.55 * (1 - vac) * (1 - off));
    if (p.seasons) {                       // 雪⇄猛暑：なめらかに行き来する（1往復 p.season_p 秒）
      const w = 0.5 - 0.5 * Math.cos(2 * Math.PI * tt / (p.season_p || 2.6));   // 0=雪 1=猛暑
      sky.lerp(snowSky, 0.5 * (1 - w)).lerp(hot, 0.55 * w);
      snow.visible = w < 0.98; snow.position.y = -1.05 * w;   // 雪が地面に沈むように溶ける
    } else if (p.freeze !== undefined || p.frozen) {   // 雪が積もり、海が凍る（p.freeze の時刻から。p.frozen は初めから）
      const w = p.frozen ? 1 : sstep((u - p.freeze) / 0.15);
      sky.lerp(snowSky, 0.6 * w); snow.visible = w > 0.01; snow.position.y = -1.05 * (1 - w);
      sea.material.color.copy(seaC).lerp(iceC, w);
    } else snow.visible = false;
    sc.background = sky;
    dl.intensity = p.night ? 0 : (0.1 + 1.1 * Math.max(day, vac)) * (1 - off); amb.intensity = p.night ? 0.24 : (0.22 + 0.45 * day * (1 - vac)) * (1 - off * 0.6);
    st.visible = day * (1 - vac) * (1 - off) < 0.55; sun.visible = !p.night && off < 0.99; sun.scale.setScalar((p.sun_scale || 1) * (1 - off));
    if (p.cloud_off !== undefined) {                     // 雲が消える（その場で縮んで消える）
      const k = Math.max(0.001, 1 - sstep((u - p.cloud_off) / 0.12)); clouds.children.forEach(m => m.scale.setScalar(k)); clouds.visible = k > 0.01;
    }
    rain.forEach(m => { const q = m.userData, k = (q.k + tt * (rock ? 0.9 : 1.6)) % 1; m.position.set(q.x + (rock ? 20 - k * 20 : -k * 3), 24 - k * 24, q.z); if (rock) m.rotation.set(tt * 5, tt * 3, 0); });
    if (p.air_off !== undefined) clouds.visible = vac < 0.5;
    clouds.children.forEach(m => {                       // 位置は時刻だけで決める（最後と冒頭の絵をそろえるため）
      if (m.userData.x0 === undefined) m.userData.x0 = m.position.x;
      m.position.x = (((m.userData.x0 + 60 + tt * (p.wind && p.wind_off === undefined ? 48 : 2.4)) % 120) + 120) % 120 - 60;
    });
    const wf = p.wind ? (p.wind_off !== undefined ? 1 - sstep((u - p.wind_off) / 0.12) : 1) : 0;   // 11/9 p.wind_off：風がやむ
    const sway = wf * (0.3 + 0.1 * Math.sin(tt * 13)) + (1 - wf) * 0.02 * Math.sin(tt * 2);
    trees.forEach((tr, i) => { tr.rotation.z = -sway + 0.04 * Math.sin(tt * 11 + i) * wf; });
    if (p.trees_off !== undefined) {                     // 11/9 p.trees_off：森が消える（木がその場で縮んで消える）
      const k = Math.max(0.001, 1 - sstep((u - p.trees_off) / 0.12)); trees.forEach(tr => { tr.scale.setScalar(k); tr.visible = k > 0.01; });
    }
    bits.forEach(b => {
      const q = b.userData; b.position.set(((q.x + t * q.v) % 80) - 40, q.y + Math.sin(t * 6 + q.s), q.z); b.visible = wf > 0.3;
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
    if (p.wind && wf > 0.5) {
      ch.rotation.z = -0.35 + 0.08 * Math.sin(t * 15);
      ch.userData.ears.forEach(e => { e.rotation.z = -0.9; });
    }
    if (p.blow) {                          // 飛ばされる
      const b = Math.max(0, t - (p.blow_at ?? 0.25));
      ch.position.set(CX + b * 22, cy + b * 10 - b * b * 2, 6 - b * 4);
      ch.rotation.set(b * 6, 0.35 + b * 4, -0.35 - b * 9);
    }
    act(ch, p, t, tt, cy, CX);                             // キャラの動き（すべる・跳ぶ・息切れ・震える）
    ups.forEach(f => f(tt, d, u));                         // 小道具は t0 込みの時刻で動かす（続きの場面を作れる）
    const e = sstep(u);
    C.position.set(lerp(cp[0], cp2[0], e), lerp(cp[1], cp2[1], e), lerp(cp[2], cp2[2], e));
    if (p.shake) C.position.x += Math.sin(t * 40) * 0.25;
    C.lookAt(lerp(ct[0], ct2[0], e), lerp(ct[1], ct2[1], e), lerp(ct[2], ct2[2], e));
  };
}


// ---------- 場面：箱庭（動く間違い探し用。2026-11-03〜） ----------
// p.diff：違いの名前の配列（B側だけに入れる）。p.cam_a0 / p.cam_a1：カメラの回り始め・終わりの角度。p.hold：この秒からカメラを止める（答え合わせ用）
// 違いの名前：tree_gone（木が1本ない）/ roof_blue（屋根が青）/ mill_reverse（風車が逆回り）/ hat（ずんだもんが帽子）/ fish（池の魚が跳ぶ）
//            mailbox_blue（ポストが青）/ flower（花が1つ多い）/ bird（鳥が飛んでいる）/ smoke（煙突から煙）/ door_open（ドアが開いている）
//            cloud_pink（雲が1つピンク）/ boat（舟が浮いている）/ fence_gap（柵が1本ない）/ sun_big（太陽が大きい）
const ANCH = {};
function hakoniwa(p) {
  const sc = CUR = new THREE.Scene();
  const D = new Set(p.diff || []);
  sc.background = new THREE.Color(0xa8e0ff);
  sc.add(new THREE.AmbientLight(0xffffff, 0.95));
  const dl = new THREE.DirectionalLight(0xffffff, 1.15); dl.position.set(30, 50, 25); sc.add(dl);
  const N = 8, L = [];
  for (let x = -N; x <= N; x++) for (let z = -N; z <= N; z++) {        // 正方形の島（土の層＋芝）
    const pond = (x - 4) ** 2 + (z - 3) ** 2 <= 3.2;
    for (let k = -2; k <= 0; k++) {
      if (pond && k === 0) continue;
      L.push([x, k, z, k < 0 ? (k === -2 ? 0x6b4422 : COL.dirt) : ((x * 7 + z * 3) % 5 ? COL.grass : COL.grass2)]);
    }
    if (pond) L.push([x, -0.6, z, 0x3a9ee8]);
  }
  sc.add(blocks(L));
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), new THREE.MeshLambertMaterial({ color: COL.sea }));
  sea.material = new THREE.MeshBasicMaterial({ color: 0x6cc4f4 }); sea.rotation.x = -Math.PI / 2; sea.position.y = -2.6; sc.add(sea);   // 11/3「なんか暗い」：海は光の当たり方で暗くならない色に
  const B = (list, sz = 1, pos = [0, 0, 0]) => { const m = blocks(list, sz); m.position.set(...pos); sc.add(m); return m; };
  // 家
  const H = [];
  for (let x = -6; x <= -2; x++) for (let z = -6; z <= -3; z++) for (let y = 1; y <= 3; y++)
    if (x === -6 || x === -2 || z === -6 || z === -3) H.push([x, y, z, 0xf4efe4]);
  B(H);
  const roofC = D.has("roof_blue") ? 0x3a6fd8 : 0xd8463a, R2 = [];
  for (let x = -7; x <= -1; x++) for (let z = -7; z <= -2; z++) R2.push([x, 4, z, roofC]);
  for (let x = -6; x <= -2; x++) for (let z = -6; z <= -3; z++) R2.push([x, 5, z, roofC]);
  for (let x = -5; x <= -3; x++) for (let z = -5; z <= -4; z++) R2.push([x, 6, z, roofC]);
  B(R2); ANCH.roof_blue = [-4, 6, -4.5];
  B([[-3, 6, -6, 0x8a8a8a], [-3, 7, -6, 0x8a8a8a]]);                  // 煙突
  const smoke = []; if (D.has("smoke")) for (let i = 0; i < 5; i++) { const m = B([[0, 0, 0, 0xdddddd]], 0.8); smoke.push(m); }
  ANCH.smoke = [-3, 9, -6];
  const door = B([[0, 0, 0, 0x7a4a24], [0, 1, 0, 0x7a4a24]], 1, [-4, 1, -2.95]); door.scale.z = 0.2; ANCH.door_open = [-4, 1.5, -2.5];
  B([[-5, 2, -2.9, 0x9fd8ff], [-3, 2, -2.9, 0x9fd8ff]]);              // 窓
  // 木（3本。tree_gone は右端の1本がない）
  const trees = [];
  [[2, -6], [6, -2], [-6, 4]].forEach(([x, z], i) => {
    if (D.has("tree_gone") && i === 1) return;
    const lf = [[0, 1, 0, COL.trunk], [0, 2, 0, COL.trunk]];
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = 0; c <= 1; c++) lf.push([a, 3 + c, b, (a + b + c) % 2 ? COL.leaf : COL.leaf2]);
    lf.push([0, 5, 0, COL.leaf]);
    trees.push(B(lf, 1, [x, 0, z]));
  });
  ANCH.tree_gone = [6, 3.5, -2];
  // 風車
  B([[0, 1, 0, 0xe8e0d0], [0, 2, 0, 0xe8e0d0], [0, 3, 0, 0xe8e0d0], [0, 4, 0, 0xe8e0d0], [0, 5, 0, 0xe8e0d0], [0, 6, 0, 0xe8e0d0]], 1, [6, 0, -6]);
  const blades = new THREE.Group(); blades.position.set(6, 6.5, -5.3); sc.add(blades);
  for (let k = 0; k < 4; k++) {
    const bl = blocks([[0, 1, 0, 0xc8503a], [0, 2, 0, 0xf4efe4], [0, 3, 0, 0xc8503a]], 0.7);
    const g = new THREE.Group(); g.add(bl); g.rotation.z = k * Math.PI / 2; blades.add(g);
  }
  ANCH.mill_reverse = [6, 6.5, -5.3];
  // ポスト
  B([[0, 1, 0, 0x7a4a24], [0, 2, 0, D.has("mailbox_blue") ? 0x2f5fd0 : 0xd83a3a]], 0.8, [1, 0, 7]); ANCH.mailbox_blue = [0.8, 1.8, 5.6];
  // 花（flower は1つ多い）
  const fl = [[-2, 6], [-1, 7], [0, 5]]; if (D.has("flower")) fl.push([2, 4]);
  fl.forEach(([x, z], i) => B([[x, 1, z, 0x3fa34d], [x, 1.7, z, [0xff6aa0, 0xffd23a, 0xffffff, 0xb070ff][i]]], 0.6));
  ANCH.flower = [1.2, 1, 2.4];
  // 柵（fence_gap は1本ない）
  for (let x = -8; x <= 8; x += 2) { if (D.has("fence_gap") && x === 4) continue; B([[x, 1, 8, 0xe0c890]], 1); }
  ANCH.fence_gap = [4, 1, 8];
  // 池の魚（fish：ときどき跳ぶ）
  const fish = D.has("fish") ? B([[0, 0, 0, 0xff8a3a], [0.6, 0, 0, 0xff8a3a]], 0.6, [4, -1, 3]) : null; ANCH.fish = [4, 0.8, 3];
  // 舟（boat：沖に浮いている）
  if (D.has("boat")) B([[0, 0, 0, 0x8b5a2b], [1, 0, 0, 0x8b5a2b], [2, 0, 0, 0x8b5a2b], [1, 1, 0, 0xf4efe4], [1, 2, 0, 0xf4efe4]], 1, [10, -2.2, 6]);
  ANCH.boat = [11, -1, 6];
  // 雲
  const clouds = [];
  [[-12, 11, -16], [7, 12, -18], [-2, 14, -24]].forEach((c, i) => {
    const col = D.has("cloud_pink") && i === 1 ? 0xffa8cc : 0xffffff, cl = [];
    for (let a = 0; a < 4; a++) for (let b = 0; b < 2; b++) cl.push([a * 1.4, b * 0.8, 0, col]);
    const m = blocks(cl, 1.4, new THREE.MeshBasicMaterial()); m.position.set(...c); sc.add(m); clouds.push(m);
  });
  ANCH.cloud_pink = [9, 12.5, -18];
  const sun = new THREE.Mesh(new THREE.BoxGeometry(5, 5, 5), new THREE.MeshBasicMaterial({ color: COL.sun }));
  sun.position.set(-16, 16, -34); sun.scale.setScalar(D.has("sun_big") ? 1.7 : 1); sc.add(sun); ANCH.sun_big = [-16, 16, -34];
  // 鳥（bird：島の上を回る）
  const bird = D.has("bird") ? blocks([[0, 0, 0, 0x333333], [-0.7, 0.2, 0, 0x333333], [0.7, 0.2, 0, 0x333333]], 0.6) : null;
  if (bird) sc.add(bird);
  ANCH.bird = [0, 12, 0];
  // ずんだもん
  const ch = blockChar(); ch.scale.setScalar(1.5); ch.position.set(0, 1.5, 1); ch.rotation.y = 0.5; sc.add(ch);
  if (D.has("hat")) { const hc = 0xd83a3a, hl = []; for (let x = -1; x <= 1; x++) for (let z = -1; z <= 1; z++) hl.push([x, 0, z, hc]); hl.push([0, 0, 2, hc], [0, 1, 0, hc], [1, 1, 0, hc], [-1, 1, 0, hc], [0, 1, 1, hc], [0, 1, -1, hc]); const hat = blocks(hl, 0.5); hat.position.set(0, 2.75, 0); ch.userData.body.add(hat); }
  ANCH.hat = [0, 5.9, 1];
  return (t, d) => {
    const hold = p.hold ?? 1e9, tc = Math.min(t, hold);
    const a = lerp(p.cam_a0 ?? -0.35, p.cam_a1 ?? 0.35, sstep(tc / Math.max(0.01, Math.min(hold, d || hold))));
    const r = p.cam_r ?? 21, hgt = p.cam_h ?? 12;
    C.position.set(Math.sin(a) * r, hgt, Math.cos(a) * r); C.lookAt(0, 2.2, 0);
    blades.rotation.z = (D.has("mill_reverse") ? -1 : 1) * t * 1.6;
    ch.position.y = 1.5 + Math.abs(Math.sin(t * 3)) * 0.25;
    ch.userData.ears.forEach((e, i) => { e.rotation.z = (i ? -1 : 1) * 0.15 * Math.sin(t * 6); });
    trees.forEach((tr, i) => { tr.rotation.z = 0.03 * Math.sin(t * 1.5 + i); });
    clouds.forEach((m, i) => { m.position.x += 0; m.position.y = [11, 12, 14][i] + 0.3 * Math.sin(t * 0.8 + i); });
    if (fish) { const k = (t % 2.4) / 2.4, j = k < 0.35 ? Math.sin(k / 0.35 * Math.PI) : 0; fish.position.y = -1 + j * 2.6; fish.rotation.z = (0.5 - k / 0.35) * 1.2 * (k < 0.35); }
    if (bird) { const b = t * 0.9; bird.position.set(Math.cos(b) * 7, 9 + Math.sin(t * 3) * 0.4, Math.sin(b) * 7); bird.rotation.y = -b; bird.children.forEach(m => {}); ANCH.bird = [bird.position.x, bird.position.y, bird.position.z]; }
    smoke.forEach((m, i) => { const k = ((t * 0.5 + i / 5) % 1); m.position.set(-3 + k * 1.5, 8 + k * 4, -6); m.scale.setScalar(0.6 + k); });
    if (D.has("door_open")) door.rotation.y = 1.2;
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
  if (p.ring === "band") {                            // 土星のような輪（赤道の上。p.ring_at の時刻から広がる）
    const rl = [];
    for (let i = 0; i < 360; i++) for (let w = 0; w < 4; w++) { const a = i / 360 * Math.PI * 2, r = 25 + w * 2.2; rl.push([Math.cos(a) * r, 0, Math.sin(a) * r, w === 2 ? 0xbfb6a4 : 0xeee6d6]); }
    ring = blocks(rl, 1.3, new THREE.MeshBasicMaterial()); ring.rotation.set(0.3, 0, 0.41); sc.add(ring);
  } else if (p.ring) {
    const rl = [];
    for (let i = 0; i < 64; i++) if (i % 2) { const a = i / 64 * Math.PI * 2; rl.push([Math.cos(a) * 34, 0, Math.sin(a) * 34, 0x8a8a8a]); }
    ring = blocks(rl, 1.2); ring.rotation.x = 0.3; sc.add(ring);
  }
  return (t, d) => {
    const u = t / d, w = p.slow ? 0.8 : 1.5 + 14 * u;      // 回る速さ（slow：今の地球のゆっくり）
    e.rotation.y = p.slow ? t * 0.8 : t * 1.5 + 7 * u * u * d;
    if (p.rev) {                                        // 11/9 逆回り：p.rev=1 で初めから逆、p.rev_at の時刻から止まって逆へ
      if (p.rev_at === undefined) e.rotation.y = -t * 0.8;
      else { let a = 0; const n = 200; for (let i = 0; i < n; i++) { const tu = (i + 0.5) / n * t; a += 0.8 * (1 - 2 * sstep(((tu / d) - p.rev_at) / 0.12)) * t / n; } e.rotation.y = a; }
    }
    streak.forEach(m => {
      const q = m.userData; m.visible = !p.slow; const a = q.a + t * w * 0.35;
      m.position.set(Math.cos(a) * q.r, q.y, Math.sin(a) * q.r); m.rotation.y = -a;
    });
    if (ring && p.ring === "band") { const k = p.ring_at !== undefined ? sstep((u - p.ring_at) / 0.1) : 1; ring.scale.setScalar(Math.max(0.001, k)); ring.visible = k > 0.01; }
    else if (ring) ring.rotation.y = t * 0.3;
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
  r.visible = !p.noring;                                   // p.noring：月の通り道を出さない
  return (t, d) => {
    const u = t / d;
    if (p.sun_off !== undefined) {                          // 太陽が消える（縮んで消え、光もなめらかに落ちる）
      const k = 1 - sstep((u - p.sun_off) / 0.08); sun.scale.setScalar(Math.max(0.001, k)); sun.visible = k > 0.01;
      pl.intensity = 3 * (1 - sstep((u - p.sun_off - (p.lag || 0)) / 0.1));   // p.lag：光が地球に届くまでの遅れ（割合）
    }
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
      return [-8 + v * 0.6 * s, 5 + v * s - 0.5 * g * s * s, 10];
    };
    ups.push((t, d) => {
      const T1 = d * 0.4, v = 14;
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
  } else if (p.act === "glide") {                        // 一度すべり出すと止まらない（摩擦がない）
    const b = Math.max(0, t - 0.2);
    ch.position.set(CX + b * 7, cy - 0.7, 6 + b * 2.2); ch.rotation.set(-0.9, 0.35 + b * 5, 0);
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
  // p.r（公転の半径。1=今の地球、0.72=今の金星の位置）、p.r_to と p.r_at（その時刻から半径が移る）、p.ghost（今の軌道を点線で残す）
  // p.sun_off（太陽が消える時刻の割合）、p.lag（その何秒あとに光と重力が地球に届く。届いたら暗くなり、まっすぐ飛んでいく）
  const OR0 = 17, mkPath = (R, col) => { const q = []; for (let i = 0; i < 60; i++) if (i % 2) { const a = i / 60 * Math.PI * 2; q.push([Math.cos(a) * R, 0, Math.sin(a) * R, col]); } return blocks(q, 0.8); };
  const r1 = p.r ?? 1, r2 = p.r_to ?? r1;
  sc.add(mkPath(OR0 * r1, 0x555a66)); if (r2 !== r1) sc.add(mkPath(OR0 * r2, 0x8a6a40));
  if (p.ghost) sc.add(mkPath(OR0 * p.ghost, 0x8a6a40));
  return (t, d) => {
    const u = t / d, per = p.per || 3.2;
    const k = r2 !== r1 ? sstep((u - (p.r_at ?? 0.5)) / 0.15) : 0, OR = OR0 * lerp(r1, r2, k);
    const a = t / per * Math.PI * 2 + (p.a0 || 0);
    g.position.set(Math.cos(a) * OR, 0, Math.sin(a) * OR);
    if (p.sun_off !== undefined) {
      const ts = p.sun_off * d, tl = ts + (p.lag || 0);
      const ks = 1 - sstep((t - ts) / 0.25); sun.scale.setScalar(Math.max(0.001, ks)); sun.visible = ks > 0.01;
      pl.intensity = 3.2 * (1 - sstep((t - tl) / 0.3));
      if (t > tl) {                                        // 重力が届いたら、その時の向きのまま接線方向へまっすぐ
        const al = tl / per * Math.PI * 2 + (p.a0 || 0), v = OR * Math.PI * 2 / per, s = t - tl;
        g.position.set(Math.cos(al) * OR - Math.sin(al) * v * s, 0, Math.sin(al) * OR + Math.cos(al) * v * s);
      }
    }
    let tilt = (p.tilt ?? 23.4) * Math.PI / 180;
    if (p.untilt_at !== undefined) tilt *= 1 - sstep((u - p.untilt_at) / 0.12);
    tiltG.rotation.set(0, 0, tilt);                       // 傾きの向きは公転しても変わらない
    e.rotation.y = t * 5; sun.rotation.y = t * 0.3;
    C.position.set(lerp(4, -4, u), 50, lerp(62, 58, u)); C.lookAt(0, -6, 0);   // 公転の円が縦画面に収まる距離
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

// ---------- 場面：海辺のブロックの街（海面が上がる）。1ブロック＝ビル1階分（約3.5m）、海面70m＝20ブロック ----------
//   p.l0 / p.l1（文のはじめ・終わりの海面。ブロック数）、p.cam（位置名か [[位置],[見る点]]）、p.cam_to
//   p.tower（634mの塔。展望台は350mと450m）、p.roof（ずんだもんがビルの屋上で手を振る）、p.ruler（10mごとの目盛りの棒）
function cityScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x7cc4f2);
  sc.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dl = new THREE.DirectionalLight(0xffffff, 0.9); dl.position.set(-60, 120, 80); sc.add(dl);
  const ground = [], blds = [];
  const H = (x, z) => Math.max(0, Math.round(Math.max(0, -z - 20) * 0.55 + Math.max(0, -x - 20) * 0.4));   // 海辺の低地（下町）から、奥・左の台地へ高くなる
  for (let x = -60; x <= 60; x += 2) for (let z = -70; z <= 20; z += 2) {
    const h = H(x, z); if (z > 8 && h < 1) continue;
    ground.push([x, h - 0.5, z, h > 12 ? 0x6a8a4a : 0x8a9a7a]);
  }
  sc.add(blocks(ground, 2));
  const cols = [0xd8d8d8, 0xb8c0c8, 0xe8e0d0, 0xa8b0b8, 0xc8b8a8, 0x9aa4b0];
  const o = new THREE.Object3D(), list = [];
  for (let x = -56; x <= 56; x += 6) for (let z = -64; z <= 4; z += 6) {
    if (rnd() < 0.25) continue;
    const g = H(x, z), hh = 2 + Math.floor(rnd() * rnd() * 34);
    list.push([x, g, z, hh, cols[Math.floor(rnd() * cols.length)]]);
  }
  const bm = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshLambertMaterial(), list.length);
  const c = new THREE.Color();
  list.forEach((b, i) => { o.position.set(b[0], b[1] + b[3] / 2, b[2]); o.scale.set(4, b[3], 4); o.updateMatrix(); bm.setMatrixAt(i, o.matrix); bm.setColorAt(i, c.setHex(b[4])); });
  sc.add(bm);
  // 窓の段（1階ごとの線）：手前のビル1棟だけ
  const fb = new THREE.Group(); fb.position.set(4, H(4, 2), 2); sc.add(fb);
  for (let k = 0; k < 30; k++) { const f = new THREE.Mesh(new THREE.BoxGeometry(5, 0.92, 5), new THREE.MeshLambertMaterial({ color: k % 2 ? 0xe0e4ea : 0xc4ccd6 })); f.position.y = k + 0.5; fb.add(f); }
  const roofY = H(4, 2) + 30;
  let tower = null;
  if (p.tower) {                                          // 634mの塔（約181ブロック）。展望台は350m・450m
    tower = new THREE.Group(); tower.position.set(-20, H(-20, -20), -20); sc.add(tower);
    for (let k = 0; k < 181; k++) { const w = 4 - k / 181 * 3; const m = new THREE.Mesh(new THREE.BoxGeometry(w, 1, w), new THREE.MeshLambertMaterial({ color: k % 2 ? 0xe8eef4 : 0xd0dae4 })); m.position.y = k + 0.5; tower.add(m); }
    [100, 128.6].forEach(y => { const d = new THREE.Mesh(new THREE.BoxGeometry(7, 3, 7), new THREE.MeshLambertMaterial({ color: 0x8aa0b8 })); d.position.y = y; tower.add(d); });
  }
  if (p.ruler) {
    const r = new THREE.Group(); r.position.set(12, 0, 8); sc.add(r);
    for (let k = 0; k < 24; k++) { const m = new THREE.Mesh(new THREE.BoxGeometry(0.8, 1, 0.8), new THREE.MeshBasicMaterial({ color: k % 6 < 3 ? 0xff3b30 : 0xffffff })); m.position.y = k + 0.5; r.add(m); }
    const mark = new THREE.Mesh(new THREE.BoxGeometry(4, 0.6, 0.6), new THREE.MeshBasicMaterial({ color: 0xffd23a })); mark.position.y = 20; r.add(mark);
  }
  const ch = blockChar(); sc.add(ch); ch.visible = !!p.roof; ch.position.set(4, roofY + 1.4, 2);
  const water = new THREE.Mesh(new THREE.BoxGeometry(600, 1, 600), new THREE.MeshLambertMaterial({ color: 0x2f7fd8, transparent: true, opacity: 0.86 }));
  sc.add(water);
  const waves = [];
  for (let i = 0; i < 40; i++) { const m = new THREE.Mesh(new THREE.BoxGeometry(2.5, 0.3, 0.8), new THREE.MeshBasicMaterial({ color: 0xcfe8ff })); m.userData = { x: -60 + rnd() * 120, z: -60 + rnd() * 80, s: rnd() * 6 }; sc.add(m); waves.push(m); }
  const camOf = cc => (Array.isArray(cc) ? cc : CITY_CAMS[cc || "hook"]);
  const [cp, ct] = camOf(p.cam), [cp2, ct2] = camOf(p.cam_to || p.cam);
  return (t, d) => {
    const u = t / d, e = sstep(u);
    const lv = lerp(p.l0 ?? 20, p.l1 ?? (p.l0 ?? 20), sstep(u / 0.85));
    water.position.y = lv - 0.5;
    waves.forEach(m => { const q = m.userData; m.position.set(q.x + Math.sin(t * 1.5 + q.s) * 1.5, lv + 0.1, q.z); });
    if (p.roof) {                                          // 屋上で手を振る（跳ねる）
      ch.position.y = roofY + 1.4 + Math.abs(Math.sin(t * 7)) * 0.6; ch.rotation.set(0, 0.5 + Math.sin(t * 3) * 0.3, Math.sin(t * 9) * 0.15);
    }
    C.position.set(lerp(cp[0], cp2[0], e), lerp(cp[1], cp2[1], e), lerp(cp[2], cp2[2], e));
    C.lookAt(lerp(ct[0], ct2[0], e), lerp(ct[1], ct2[1], e), lerp(ct[2], ct2[2], e));
  };
}
const CITY_CAMS = {
  hook: [[38, 34, 70], [0, 10, -20]],      // 冒頭と最後：海から街を見る
  low: [[10, 22, 40], [0, 18, -10]],
  floor: [[16, 18, 26], [4, 16, 2]],      // 手前のビル（窓の段）に寄る
  roof: [[14, 36, 22], [4, 30, 2]],
  tower: [[30, 30, 70], [-20, 60, -20]],
  high: [[0, 120, 120], [0, 0, -20]],
};

// ---------- 場面：氷床の上を飛ぶ。p.melt（0〜1 の時刻）から氷が沈んで岩と海があらわれる ----------
function icefly(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0xbfdcf2); sc.fog = p.high ? null : new THREE.Fog(0xbfdcf2, 60, 260);
  sc.add(new THREE.AmbientLight(0xffffff, 0.55));
  const dl = new THREE.DirectionalLight(0xffffff, 0.9); dl.position.set(80, 50, 40); sc.add(dl);
  const N = 40, S = 3, cells = [];
  for (let x = -N; x <= N; x++) for (let z = -N * 2; z <= N; z++) {
    const rock = Math.round(14 * noise3(x * 0.13, 0.4, z * 0.13) - 3);   // 岩盤（低い所は海の下。高い所は峰として氷から出る）
    const ice = Math.max(0, Math.round(9 + 2 * noise3(x * 0.07, 1.1, z * 0.07) - Math.max(rock, 0)));
    cells.push([x * S, rock, ice, z * S]);
  }
  const rk = new THREE.InstancedMesh(new THREE.BoxGeometry(S, 1, S), new THREE.MeshLambertMaterial(), cells.length);
  const ic = new THREE.InstancedMesh(new THREE.BoxGeometry(S, 1, S), new THREE.MeshLambertMaterial({ emissive: 0x6a7a8a }), cells.length);
  const o = new THREE.Object3D(), c = new THREE.Color();
  cells.forEach((q, i) => {
    o.position.set(q[0], q[1] - 3, q[3]); o.scale.set(1, 6, 1); o.updateMatrix(); rk.setMatrixAt(i, o.matrix);
    rk.setColorAt(i, c.setHex(q[1] > 2 ? 0x6a5040 : 0x8a6a4a));
    ic.setColorAt(i, c.setHex(q[2] < 4 ? 0xb8d8f0 : ((i * 7) % 5 ? 0xf4f9ff : 0xdcecf8)));
  });
  rk.instanceMatrix.needsUpdate = true; rk.instanceColor.needsUpdate = true; ic.instanceColor.needsUpdate = true;
  sc.add(rk); sc.add(ic);
  const sea = new THREE.Mesh(new THREE.BoxGeometry(1200, 1, 1200), new THREE.MeshLambertMaterial({ color: 0x2a6fc0 })); sc.add(sea);
  const KB = p.melt ?? 2;
  return (t, d) => {
    const u = t / d, m = sstep((u - KB) / Math.max(0.02, (p.melt_len ?? 0.08)));
    cells.forEach((q, i) => {
      const h = q[2] * (1 - m);
      o.position.set(q[0], q[1] + h / 2, q[3]); o.scale.set(1, Math.max(0.001, h), 1); o.updateMatrix(); ic.setMatrixAt(i, o.matrix);
    });
    ic.instanceMatrix.needsUpdate = true;
    sea.position.y = lerp(-4, 1.5, m) - 0.5;
    sc.background.setHex(0xbfdcf2).lerp(new THREE.Color(0x8cc4ee), m); if (sc.fog) sc.fog.color.copy(sc.background);
    if (p.high) { C.position.set(lerp(0, 16, u), 260, lerp(170, 150, u)); C.lookAt(0, 0, -50); return; }
    const z = lerp(110, -130, Math.pow(Math.min(u / Math.max(KB, 0.5), 1), 1.2));
    C.position.set(Math.sin(u * 3) * 10, 44 + Math.sin(u * 5) * 2, z); C.lookAt(0, 0, z - 55); C.rotateZ(Math.sin(u * 4) * 0.08);
  };
}

// ---------- 場面：海に浮かぶ氷が溶ける。目盛りの海面はほぼ変わらない ----------
function seaice(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x9cc8ec);
  sc.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dl = new THREE.DirectionalLight(0xffffff, 0.8); dl.position.set(40, 60, 50); sc.add(dl);
  const sea = new THREE.Mesh(new THREE.BoxGeometry(400, 1, 400), new THREE.MeshLambertMaterial({ color: 0x2a6fc0, transparent: true, opacity: 0.85 })); sea.position.y = -0.5; sc.add(sea);
  const ice = [];
  for (let i = 0; i < 26; i++) {
    const s = 5 + rnd() * 7, m = new THREE.Mesh(new THREE.BoxGeometry(s, s * 0.9, s * 0.8), new THREE.MeshLambertMaterial({ color: i % 3 ? 0xf2f8ff : 0xd4e8f8, emissive: 0x405060 }));
    m.userData = { x: -30 + rnd() * 60, z: -40 + rnd() * 50, s }; sc.add(m); ice.push(m);
  }
  const pole = new THREE.Group(); pole.position.set(6, 0, 14); sc.add(pole);
  for (let k = -6; k < 10; k++) { const b = new THREE.Mesh(new THREE.BoxGeometry(0.8, 1, 0.8), new THREE.MeshBasicMaterial({ color: (k + 6) % 4 < 2 ? 0xff3b30 : 0xffffff })); b.position.y = k + 0.5; pole.add(b); }
  return (t, d) => {
    const u = t / d, m = sstep(u / 0.9);
    ice.forEach((b, i) => {
      const q = b.userData, k = Math.max(0.02, 1 - m * (0.8 + (i % 4) * 0.07));
      b.scale.setScalar(k); b.position.set(q.x + Math.sin(t + i) * 0.4, q.s * 0.9 * k * 0.5 - q.s * 0.9 * k * 0.4, q.z);   // 9割は水の下
    });
    C.position.set(lerp(-4, 4, u), 11, 34); C.lookAt(0, 2, -6);
  };
}

// ---------- 場面：上から見た南極。白い氷の大陸 → 東は岩の陸地、西は島の連なり（p.melt の時刻から p.melt_len かけて色と高さを移す） ----------
function antarctica(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  sc.add(stars(1600, 700, 2.2)); sc.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dl = new THREE.DirectionalLight(0xffffff, 0.8); dl.position.set(-60, 120, 40); sc.add(dl);
  const sea = new THREE.Mesh(new THREE.BoxGeometry(400, 1, 400), new THREE.MeshLambertMaterial({ color: 0x1f5fae })); sea.position.y = -0.5; sc.add(sea);
  const nz = (x, z) => Math.sin(x * 0.071 + 1.3) * Math.sin(z * 0.053 + 0.7) + 0.5 * Math.sin(x * 0.137 + z * 0.091) + 0.3 * Math.sin(x * 0.29 - z * 0.23 + 2.1) + 0.2 * Math.sin(z * 0.41 + x * 0.05);
  const S = 2, cells = [];
  for (let x = -80; x <= 80; x += S) for (let z = -70; z <= 70; z += S) {
    const ex = x - 14, ez = z + 4, re = Math.sqrt(ex * ex * 0.8 + ez * ez), ae = Math.atan2(ez, ex);
    const east = re < 46 + 6 * Math.sin(ae * 3 + 0.5) + 4 * nz(x, z);                   // 東南極：大きな陸地が残る
    const wx = x + 34, wz = z - 8, rw = Math.sqrt(wx * wx + wz * wz * 1.3);
    const pen = Math.abs((z - 8) - (x + 48) * -0.9) < 5 + 2 * nz(z, x) && x < -40 && x > -78;   // 南極半島
    const west = !east && (rw < 26 + 4 * nz(z, x) || pen);                                   // 西南極：氷の下は大部分が海
    if (!east && !west) continue;
    const dome = east ? 9 - re / 7 : 5 - rw / 8;
    const island = west && nz(x * 1.7, z * 1.7) > 0.3;                                      // 溶けたあとに残る島
    const rockH = east ? 1 + Math.max(0, Math.round(1.5 + 1.5 * nz(x * 1.3, z * 1.3))) : (island ? 1 : 0);
    const rockC = (east ? (nz(x * 2.1, z * 2.1) > 0.2 ? 0x8a7458 : 0x7c7c7c) : 0x8a7458);
    cells.push({ x, z, ice: Math.max(1.5, dome), rockH, rockC, gone: west && !island });
  }
  const im = new THREE.InstancedMesh(new THREE.BoxGeometry(S, 1, S), new THREE.MeshLambertMaterial(), cells.length); sc.add(im);
  const o = new THREE.Object3D(), c = new THREE.Color(), white = new THREE.Color(0xf2f7fc);
  return (t, d) => {
    const u = t / d, m = sstep((u - (p.melt ?? 0.1)) / (p.melt_len ?? 0.5));
    cells.forEach((q, i) => {
      const h = lerp(q.ice, q.gone ? -1.5 : q.rockH, m);
      o.position.set(q.x, h / 2 - 0.5, q.z); o.scale.set(1, Math.max(0.05, Math.abs(h) + 1), 1); o.updateMatrix(); im.setMatrixAt(i, o.matrix);
      im.setColorAt(i, c.copy(white).lerp(new THREE.Color(q.gone ? 0x1f5fae : q.rockC), m));
    });
    im.instanceMatrix.needsUpdate = true; im.instanceColor.needsUpdate = true;
    C.position.set(Math.sin(u * 0.8) * 12, 250, 120); C.lookAt(-8, 0, -4); C.rotateZ(u * 0.12);
  };
}

// ---------- 場面：海の断面（11/7〜の回で追加）。たて1km＝2ブロック（たては横より大きく描く） ----------
//   左から 大陸 → 大陸棚 → 深海平原（約4.5km）と海山（マウナケア：海底から約10.2km、海面上4.2km）→ 海嶺 → 海溝（約10.9km）→ 島
//   p.w0 / p.w1（海面の高さ km。0=今。-12 で干上がる）、p.w_at / p.w_len（下がり始める時刻の割合と長さ）
//   p.everest（海溝の底に 8.85km の目盛りの柱）、p.char（[x, z] にずんだもんを立てる）、p.cam / p.cam_to（SEA_CAMS の名前か [[位置],[見る点]]）
const SEA_CAMS = {                                          // 断面（手前 z=31 の面）を前から見るカメラが基本
  hook: [[30, 40, 110], [10, -12, -10]],
  wide: [[0, 70, 150], [0, -10, -10]],
  trench: [[46, -6, 75], [46, -10, 0]],
  mk: [[-16, 2, 40], [-16, 0, -10]],
  ridge: [[14, 0, 70], [14, -6, 0]],
  low: [[-24, -7, 22], [-16, 5, -10]],
  shelf: [[-46, 2, 62], [-46, -4, 0]],
  top: [[4, 150, 30], [0, -10, 0]],
};
function seafloor(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x7cc4f2);
  sc.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dl = new THREE.DirectionalLight(0xffffff, 0.9); dl.position.set(-40, 90, 70); sc.add(dl);
  const V = 2, S = 2, BOT = -50, cells = [];
  const nz = (x, z) => 0.5 * Math.sin(x * 0.31 + z * 0.17) + 0.3 * Math.sin(z * 0.43 - x * 0.11);
  const depth = (x, z) => {                               // km（マイナスが海面より下）
    if (x < -52) return 0.4 + 0.2 * nz(x, z);
    if (x < -44) return -0.15;
    if (x < -30) return lerp(-0.15, -4.4, sstep((x + 44) / 14));
    let h = -4.5 + 0.15 * nz(x, z);
    const r = Math.sqrt((x + 16) ** 2 + (z + 10) ** 2);   // マウナケア（海山の島）
    if (r < 13) h = Math.max(h, -6 + 10.2 * Math.pow(1 - r / 13, 1.25));
    if (x > 2 && x < 28) h = Math.max(h, -4.5 + 2.1 * Math.exp(-(((x - 14) / 5.5) ** 2)) - (Math.abs(x - 14) < 1.2 ? 0.6 : 0));   // 海嶺（まん中に溝）
    if (x >= 30) h = -5.5;
    if (x > 38 && x < 54) h = Math.min(h, -10.9 + 6.2 * ((x - 46) / 4.2) ** 2);   // 海溝
    if (x >= 52) h = Math.max(h, lerp(-5.5, 0.6, sstep((x - 52) / 8)));
    return h;
  };
  for (let x = -70; x <= 70; x += S) for (let z = -50; z <= 30; z += S) {
    const h = depth(x, z) * V;
    const col = h > 0.3 ? ((x + z) % 4 ? COL.grass : COL.grass2) : (h > -1 ? COL.sand : (h < -16 ? 0x4e3e32 : (x > 2 && x < 28 && h > -7 ? 0x5a4a42 : ((x * 3 + z) % 5 ? 0x7a6450 : 0x6e5a48))));
    cells.push([x, h, z, col]);
  }
  const im = new THREE.InstancedMesh(new THREE.BoxGeometry(S, 1, S), new THREE.MeshLambertMaterial(), cells.length);
  const o = new THREE.Object3D(), c = new THREE.Color();
  cells.forEach((q, i) => { o.position.set(q[0], (q[1] + BOT) / 2, q[2]); o.scale.set(1, q[1] - BOT, 1); o.updateMatrix(); im.setMatrixAt(i, o.matrix); im.setColorAt(i, c.setHex(q[3])); });
  im.instanceMatrix.needsUpdate = true; im.instanceColor.needsUpdate = true; sc.add(im);
  const bed = new THREE.Mesh(new THREE.PlaneGeometry(3000, 3000), new THREE.MeshLambertMaterial({ color: 0x3a2e26 }));   // 断面の下（空が見えないように）
  bed.rotation.x = -Math.PI / 2; bed.position.y = BOT; sc.add(bed);
  const water = new THREE.Mesh(new THREE.BoxGeometry(142, 1, 82), new THREE.MeshLambertMaterial({ color: 0x2f7fd8, transparent: true, opacity: 0.55 }));
  water.position.set(0, 0, -10); sc.add(water);
  if (p.everest) {                                        // エベレスト 8849m を海溝の底から立てる（1kmごとに赤白）
    const g = new THREE.Group(); g.position.set(46, -10.9 * V, 0); sc.add(g);
    for (let k = 0; k < 18; k++) { const m = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1, 1.4), new THREE.MeshBasicMaterial({ color: Math.floor(k / 2) % 2 ? 0xffffff : 0xff3b30 })); m.position.y = k * 0.983 + 0.5; g.add(m); }
    const top = new THREE.Mesh(new THREE.BoxGeometry(3, 0.8, 3), new THREE.MeshBasicMaterial({ color: 0xffd23a })); top.position.y = 8.85 * V; g.add(top);
  }
  const ch = blockChar(); ch.visible = !!p.char; sc.add(ch);
  const [chx, chz] = p.char || [0, 10], chy = depth(chx, chz) * V + 0.5 + 1.4;
  const camOf = cc => (Array.isArray(cc) ? cc : SEA_CAMS[cc || "hook"]);
  const [cp, ct] = camOf(p.cam), [cp2, ct2] = camOf(p.cam_to || p.cam);
  return (t, d) => {
    const u = t / d, e = sstep(u);
    const w = lerp(p.w0 ?? 0, p.w1 ?? (p.w0 ?? 0), sstep((u - (p.w_at ?? 0)) / (p.w_len ?? 0.85)));
    const top = w * V, hgt = Math.max(0.01, top - BOT);
    water.visible = w > -11.9; water.scale.y = hgt; water.position.y = BOT + hgt / 2;
    if (p.char) { ch.position.set(chx, chy + Math.abs(Math.sin(t * 7)) * 0.4, chz); ch.rotation.set(0, 0.4 + Math.sin(t * 2.2) * 0.9, 0); }
    C.position.set(lerp(cp[0], cp2[0], e), lerp(cp[1], cp2[1], e), lerp(cp[2], cp2[2], e));
    C.lookAt(lerp(ct[0], ct2[0], e), lerp(ct[1], ct2[1], e), lerp(ct[2], ct2[2], e));
  };
}

// ---------- 動く間違い探し 2つめの箱庭：駅のまち（11/4 ゲンタさん「ちがう箱庭も作りたい。いろんな動く間違い探し」） ----------
// 違いの名前：train_car（まん中の車両が赤）/ train_reverse（電車が逆向きに走る）/ signal_red（信号が赤）/ tree_gone（木が1本ない）
//            balloon（風船が浮いている）/ cat（屋根にネコ）/ roof_green（駅の屋根が緑）/ car_red（車が赤）/ flag_gone（旗がない）/ bench_gone（ベンチがない）
function hakoniwaEki(p) {
  const sc = CUR = new THREE.Scene();
  const D = new Set(p.diff || []);
  sc.background = new THREE.Color(0xa8e0ff);
  sc.add(new THREE.AmbientLight(0xffffff, 0.95));
  const dl = new THREE.DirectionalLight(0xffffff, 1.15); dl.position.set(30, 50, 25); sc.add(dl);
  const N = 8, L = [];
  for (let x = -N; x <= N; x++) for (let z = -N; z <= N; z++) for (let k = -2; k <= 0; k++)
    L.push([x, k, z, k < 0 ? (k === -2 ? 0x6b4422 : COL.dirt) : (z >= 7 ? 0x8a8a8a : ((x * 7 + z * 3) % 5 ? COL.grass : COL.grass2))]);
  sc.add(blocks(L));
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), new THREE.MeshBasicMaterial({ color: 0x6cc4f4 }));
  sea.rotation.x = -Math.PI / 2; sea.position.y = -2.6; sc.add(sea);
  const B = (list, sz = 1, pos = [0, 0, 0]) => { const m = blocks(list, sz); m.position.set(...pos); sc.add(m); return m; };
  // 線路（長方形の輪）
  const X0 = -6, X1 = 6, Z0 = -2, Z1 = 5, rail = [];
  for (let x = X0; x <= X1; x++) { rail.push([x, 0.55, Z0, 0x6a5a4a], [x, 0.55, Z1, 0x6a5a4a]); }
  for (let z = Z0 + 1; z < Z1; z++) { rail.push([X0, 0.55, z, 0x6a5a4a], [X1, 0.55, z, 0x6a5a4a]); }
  const rl = B(rail); rl.scale.y = 1; rl.children.forEach(m => { m.scale.y = 0.15; });
  const PER = 2 * ((X1 - X0) + (Z1 - Z0));
  const pt = s => {
    s = ((s % PER) + PER) % PER;
    const w = X1 - X0, h = Z1 - Z0;
    if (s < w) return [X0 + s, Z0, 0];
    if ((s -= w) < h) return [X1, Z0 + s, -Math.PI / 2];
    if ((s -= h) < w) return [X1 - s, Z1, Math.PI];
    s -= w; return [X0, Z1 - s, Math.PI / 2];
  };
  // 電車（3両）
  const cars = [0x2f9e5a, D.has("train_car") ? 0xd83a3a : 0xf2c230, 0x2f9e5a].map((c, i) => {
    const g = new THREE.Group();
    const bl = [];
    for (let u = -1; u <= 1; u++) bl.push([u, 0, 0, c], [u, 0.8, 0, 0x9fd8ff], [u, 1.5, 0, c]);
    const b = blocks(bl, 0.85); b.children.forEach(m => { m.scale.z = 1.0; });
    g.add(b); sc.add(g); return g;
  });
  // 駅（ホーム・建物・屋根・時計・旗）
  const st = [];
  for (let x = -4; x <= 4; x++) st.push([x, 1, -3, 0xc8c0b0]);
  for (let x = -4; x <= 4; x++) for (let z = -7; z <= -4; z++) for (let y = 1; y <= 3; y++)
    if (x === -4 || x === 4 || z === -7 || z === -4) st.push([x, y, z, (y === 2 && z === -4 && x % 2 === 0 && x) ? 0x9fd8ff : 0xf4efe4]);
  B(st);
  const rc = D.has("roof_green") ? 0x3aa65a : 0x3a6fd8, rf = [];
  for (let x = -5; x <= 5; x++) for (let z = -8; z <= -3; z++) rf.push([x, 4, z, rc]);
  for (let x = -3; x <= 3; x++) for (let z = -7; z <= -4; z++) rf.push([x, 5, z, rc]);
  B(rf); ANCH.roof_green = [0, 5, -5.5];
  B([[0, 3, -3.5, 0xffffff]], 0.9);                                         // 時計の文字盤
  const hand = new THREE.Group(); hand.position.set(0, 3, -3.0); sc.add(hand);
  const hm = blocks([[0, 0.25, 0, 0x222222]], 0.12); hm.scale.y = 4; hand.add(hm);
  const flag = new THREE.Group(); flag.position.set(3, 6, -5.5); sc.add(flag);
  if (!D.has("flag_gone")) { flag.add(blocks([[0, 0, 0, 0x888888], [0, 1, 0, 0x888888], [0, 2, 0, 0x888888]], 0.5)); }
  const cloth = D.has("flag_gone") ? null : blocks([[0.5, 1, 0, 0xd83a3a], [1, 1, 0, 0xd83a3a], [0.5, 0.6, 0, 0xd83a3a], [1, 0.6, 0, 0xd83a3a]], 0.5);
  if (cloth) flag.add(cloth);
  ANCH.flag_gone = [3.4, 7, -5.5];
  if (!D.has("bench_gone")) B([[0, 0, 0, 0x8b5a2b], [1, 0, 0, 0x8b5a2b], [0, 0.6, -0.4, 0x8b5a2b], [1, 0.6, -0.4, 0x8b5a2b]], 0.6, [-3, 1.8, -3]);
  ANCH.bench_gone = [-2.7, 2, -3];
  // ネコ（cat：屋根の上）
  const cat = D.has("cat") ? B([[0, 0, 0, 0xf0a040], [0.6, 0, 0, 0xf0a040], [0.9, 0.5, 0, 0xf0a040], [-0.4, 0.4, 0, 0xf0a040]], 0.6, [-2.5, 6, -4.5]) : null;
  ANCH.cat = [-2.3, 6.3, -4.5];
  // 木（2本。tree_gone は右の1本がない）
  [[-7, -7], [7, -6]].forEach(([x, z], i) => {
    if (D.has("tree_gone") && i === 1) return;
    const lf = [[0, 1, 0, COL.trunk], [0, 2, 0, COL.trunk]];
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = 0; c <= 1; c++) lf.push([a, 3 + c, b, (a + b + c) % 2 ? COL.leaf : COL.leaf2]);
    lf.push([0, 5, 0, COL.leaf]); B(lf, 1, [x, 0, z]);
  });
  ANCH.tree_gone = [7, 3.5, -6];
  // 信号（signal_red）
  B([[0, 1, 0, 0x555555], [0, 2, 0, 0x555555], [0, 3, 0, 0x333333]], 0.8, [7.3, 0, 2]);
  B([[0, 0, 0, D.has("signal_red") ? 0xff3a3a : 0x3ad86a]], 0.5, [7.3, 2.45, 2.45]);
  ANCH.signal_red = [7.3, 2.6, 2.5];
  // 道と車（car_red）
  const car = B([[0, 0, 0, D.has("car_red") ? 0xd83a3a : 0x3a6fd8], [1, 0, 0, D.has("car_red") ? 0xd83a3a : 0x3a6fd8], [0.5, 0.8, 0, 0x9fd8ff]], 0.8, [0, 1, 7.5]);
  // 風船（balloon）
  const bal = D.has("balloon") ? B([[0, 0, 0, 0xff4a7a], [0, -0.9, 0, 0xeeeeee]], 0.7, [-5, 8, -1]) : null;
  ANCH.balloon = [-5, 8, -1];
  // 雲と太陽
  const clouds = [];
  [[-12, 11, -16], [7, 12, -18], [-2, 14, -24]].forEach(c => {
    const cl = []; for (let a = 0; a < 4; a++) for (let b = 0; b < 2; b++) cl.push([a * 1.4, b * 0.8, 0, 0xffffff]);
    const m = blocks(cl, 1.4, new THREE.MeshBasicMaterial()); m.position.set(...c); sc.add(m); clouds.push(m);
  });
  const sun = new THREE.Mesh(new THREE.BoxGeometry(5, 5, 5), new THREE.MeshBasicMaterial({ color: COL.sun })); sun.position.set(-16, 16, -34); sc.add(sun);
  // ずんだもん（線路の輪の中で手をふる）
  const ch = blockChar(); ch.scale.setScalar(1.4); ch.position.set(2.6, 1.5, 2); ch.rotation.y = -0.2; sc.add(ch);
  return (t, d) => {
    const hold = p.hold ?? 1e9, tc = Math.min(t, hold);
    const a = lerp(p.cam_a0 ?? -0.35, p.cam_a1 ?? 0.35, sstep(tc / Math.max(0.01, Math.min(hold, d || hold))));
    const r = p.cam_r ?? 21, hgt = p.cam_h ?? 12;
    C.position.set(Math.sin(a) * r, hgt, Math.cos(a) * r); C.lookAt(0, 2.2, 0);
    const dir = D.has("train_reverse") ? -1 : 1, s0 = t * 3.2 * dir;
    cars.forEach((g, i) => { const [x, z, h] = pt(s0 - dir * i * 2.7); g.position.set(x, 0.95, z); g.rotation.y = -h; if (i === 1) ANCH.train_car = [x, 2.2, z]; if (i === 0) ANCH.train_reverse = [x, 2.2, z]; });
    hand.rotation.z = -t * 0.8;
    if (cloth) cloth.rotation.y = 0.25 * Math.sin(t * 4);
    car.position.x = -1 + 6 * Math.sin(t * 0.6); ANCH.car_red = [car.position.x + 0.4, 1.6, 7.5];
    if (bal) { bal.position.y = 8 + 0.4 * Math.sin(t * 1.3); ANCH.balloon = [-5, bal.position.y, -1]; }
    if (cat) cat.rotation.y = 0.3 * Math.sin(t * 1.1);
    ch.position.y = 1.5 + Math.abs(Math.sin(t * 3)) * 0.2;
    ch.userData.ears.forEach((e, i) => { e.rotation.z = (i ? -1 : 1) * 0.15 * Math.sin(t * 6); });
    clouds.forEach((m, i) => { m.position.y = [11, 12, 14][i] + 0.3 * Math.sin(t * 0.8 + i); });
  };
}

// ---------- 動く間違い探し：世界観のある動くステージ「海の中」（11/10 ゲンタさん「回転する箱庭だけではなくて、もっと世界観のある動くステージ」）
// カメラは正面でほぼ固定（ゆっくり左右に揺れるだけ）。ステージの上で、いろいろなものが動き続ける。
// 違い：fish_color（群れの1匹が青）/ bigfish_reverse（大きな魚が逆向き）/ jelly_extra（クラゲが1匹多い）/ octo_purple（タコが紫）
//      chest_open（宝箱が開きっぱなし）/ crab_gone（カニがいない）/ coral_blue（サンゴが1つ青）/ weed_gone（海藻が1本ない）
//      sub_red（潜水艦が赤）/ ship_flag（沈没船に旗）/ star_gone（ヒトデがいない）
function stageSea(p) {
  const sc = CUR = new THREE.Scene();
  const D = new Set(p.diff || []);
  sc.background = new THREE.Color(0x1f6fb8);
  sc.fog = new THREE.Fog(0x1f6fb8, 30, 70);
  sc.add(new THREE.AmbientLight(0xffffff, 0.9));
  const dl = new THREE.DirectionalLight(0xffffff, 1.0); dl.position.set(5, 40, 20); sc.add(dl);
  const B = (list, sz = 1, pos = [0, 0, 0]) => { const m = blocks(list, sz); m.position.set(...pos); sc.add(m); return m; };
  const G = () => { const g = new THREE.Group(); sc.add(g); return g; };
  // 海底（砂）と奥の岩
  const L = [];
  for (let x = -18; x <= 18; x++) for (let z = -10; z <= 5; z++) {
    const h = (Math.sin(x * 0.7) + Math.cos(z * 0.9 + x * 0.3)) > 1.2 ? 1 : 0;
    L.push([x, 0, z, (x + z) % 3 ? 0xe8d38a : 0xdcc57a]);
    if (h) L.push([x, 1, z, 0xd6be72]);
  }
  for (let x = -18; x <= 18; x++) for (let y = 1; y <= 4 + Math.round(2 * Math.sin(x * 0.5)); y++) L.push([x, y, -10, (x + y) % 2 ? 0x5a6f80 : 0x4d6070]);
  B(L);
  // ヒトデ（岩の上）
  if (!D.has("star_gone")) B([[0, 0, 0, 0xff8a3a], [0.5, 0, 0, 0xff8a3a], [-0.5, 0, 0, 0xff8a3a], [0, 0.5, 0, 0xff8a3a], [0, -0.5, 0, 0xff8a3a]], 0.5, [-12, 5.5, -9.4]);
  ANCH.star_gone = [-12, 5.5, -9.4];
  // 沈没船
  const sh = [];
  for (let x = -3; x <= 3; x++) for (let y = 0; y <= 1; y++) sh.push([x, y, 0, 0x7a4a24]);
  for (let x = -2; x <= 2; x++) sh.push([x, -1, 0, 0x6a3e1e]);
  for (let y = 2; y <= 6; y++) sh.push([0, y, 0, 0x5a3418]);
  const ship = B(sh, 1, [-9, 2, -5]); ship.rotation.z = 0.18;
  if (D.has("ship_flag")) B([[0, 0, 0, 0xffffff], [1, 0, 0, 0x222222], [0, -0.8, 0, 0x222222], [1, -0.8, 0, 0xffffff]], 0.8, [-8.2, 8.6, -5]);
  ANCH.ship_flag = [-8.2, 8.3, -5];
  // サンゴ
  [[7, -3, 0xff5a8a], [11, -1, 0xff9a3a], [-13, 1, 0xff5a8a]].forEach(([x, z, c], i) => {
    const col = (D.has("coral_blue") && i === 2) ? 0x3a8aff : c, cl = [];
    for (let y = 1; y <= 3; y++) cl.push([0, y, 0, col]);
    cl.push([-1, 3, 0, col], [1, 2, 0, col], [-1, 4, 0, col], [1, 3, 0, col], [1, 4, 0, col]);
    B(cl, 1, [x, 0, z]);
  });
  ANCH.coral_blue = [-13, 3, 1];
  // 海藻（ゆらゆら）
  const weeds = [];
  [[-5, 1], [-3.5, 2], [13, 2], [3, -6]].forEach(([x, z], i) => {
    if (D.has("weed_gone") && i === 1) return;
    const g = G(); g.position.set(x, 1, z); const w = [];
    for (let y = 0; y < 6; y++) w.push([0, y * 0.8, 0, y % 2 ? 0x2e9b4a : 0x3fb85a]);
    g.add(blocks(w, 0.7)); weeds.push(g);
  });
  ANCH.weed_gone = [-3.5, 3, 2];
  // 宝箱
  B([[0, 0, 0, 0x8b5a2b], [1, 0, 0, 0x8b5a2b]], 1, [-1, 1, 2]);
  const lid = G(); lid.position.set(-1.5, 1.5, 1.5);
  lid.add(blocks([[0.5, 0.25, 0.5, 0x6a3e1e], [1.5, 0.25, 0.5, 0x6a3e1e]], 1));
  B([[0, 0, 0, 0xffd23a], [0.6, 0.1, 0, 0xffd23a]], 0.5, [-0.8, 1.5, 2]);
  ANCH.chest_open = [-0.5, 2.2, 2];
  // タコ
  const octo = G(); octo.position.set(3.5, 1.2, 1.5);
  const oc = D.has("octo_purple") ? 0x9a4adc : 0xe8452a;
  octo.add(blocks([[0, 1.2, 0, oc], [0, 2.1, 0, oc], [-0.9, 1.2, 0, oc], [0.9, 1.2, 0, oc], [-0.9, 2.1, 0, oc], [0.9, 2.1, 0, oc], [0, 3, 0, oc]], 0.9));
  octo.add(blocks([[-0.35, 1.7, 0.5, 0x111111], [0.35, 1.7, 0.5, 0x111111]], 0.3));
  const arms = [];
  for (let k = 0; k < 4; k++) { const a = new THREE.Group(); a.position.set(-0.9 + k * 0.6, 0.6, 0); a.add(blocks([[0, -0.3, 0, oc], [0, -0.8, 0, oc]], 0.45)); octo.add(a); arms.push(a); }
  ANCH.octo_purple = [3.5, 3.2, 1.5];
  // カニ（横歩き）
  const crab = D.has("crab_gone") ? null : B([[0, 0, 0, 0xd8382a], [0.7, 0, 0, 0xd8382a], [-0.5, 0.4, 0, 0xd8382a], [1.2, 0.4, 0, 0xd8382a]], 0.6, [9, 1.4, 3]);
  ANCH.crab_gone = [9.3, 1.6, 3];
  // 魚の群れ（左から右へ）
  const school = [];
  for (let k = 0; k < 6; k++) {
    const c = (D.has("fish_color") && k === 3) ? 0x3a7aff : 0xff9a2a;
    const f = B([[0, 0, 0, c], [0.6, 0, 0, c], [-0.6, 0, 0, 0xffd27a]], 0.6); f.userData = { dx: (k % 3) * 1.4, dy: Math.floor(k / 3) * 1.1 - 0.5 + (k % 2) * 0.3 };
    school.push(f);
  }
  // 大きな魚（右から左へ）
  const big = B([[0, 0, 0, 0xffe04a], [1, 0, 0, 0xffe04a], [-1, 0, 0, 0xffe04a], [0, 1, 0, 0xffe04a], [-2, 0.5, 0, 0xf2c230], [-2, -0.5, 0, 0xf2c230], [1.3, 0.3, 0.5, 0x222222]], 0.9);
  // クラゲ
  const jellies = [[2, 8, -3], [-4, 9.5, -4]].concat(D.has("jelly_extra") ? [[10, 9, -4]] : []).map(([x, y, z], i) => {
    const g = G(); g.position.set(x, y, z); g.userData = { y0: y, ph: i * 1.7 };
    g.add(blocks([[0, 0, 0, 0xffc8f0], [1, 0, 0, 0xffc8f0], [-1, 0, 0, 0xffc8f0], [0, 0.8, 0, 0xffc8f0], [-0.7, -1, 0, 0xffe4f7], [0, -1.3, 0, 0xffe4f7], [0.7, -1, 0, 0xffe4f7]], 0.8));
    return g;
  });
  ANCH.jelly_extra = [10, 9, -4];
  // 潜水艦（奥を左から右へ）
  const subc = D.has("sub_red") ? 0xe8452a : 0x9aa6b4;
  const sub = B([[0, 0, 0, subc], [1, 0, 0, subc], [2, 0, 0, subc], [-1, 0, 0, subc], [0.5, 1, 0, subc], [0.5, 1.8, 0, 0x888888], [1, 0, 0.6, 0x9fd8ff], [-2, 0, 0, 0x555555]], 1.1);
  // 泡（船から）
  const bubbles = [];
  for (let k = 0; k < 8; k++) { const b = B([[0, 0, 0, 0xdff3ff]], 0.35); b.userData = { ph: k / 8 }; bubbles.push(b); }
  // ずんだもん（ダイバー。上下にふわふわ）
  const ch = blockChar(); ch.scale.setScalar(1.3); ch.position.set(6.5, 3, 3); ch.rotation.y = -0.4; sc.add(ch);
  return (t, d) => {
    const sw = p.sway ?? 1;
    C.position.set(Math.sin(t * 0.25) * 1.5 * sw + (p.cam_x || 0), 6.5, 19); C.lookAt(p.cam_x || 0, 6, -1);
    weeds.forEach((g, i) => { g.rotation.z = 0.18 * Math.sin(t * 1.6 + i); });
    const op = D.has("chest_open") ? 1 : Math.max(0, Math.sin(t * 1.3)); lid.rotation.x = -1.1 * op;
    arms.forEach((a, i) => { a.rotation.z = 0.5 * Math.sin(t * 4 + i * 1.2); });
    octo.position.y = 1.2 + 0.3 * Math.abs(Math.sin(t * 2));
    if (crab) { crab.position.x = 9 + 2.2 * Math.sin(t * 0.9); ANCH.crab_gone = [crab.position.x + 0.3, 1.6, 3]; }
    const sx = ((t * 3.2) % 40) - 20;
    school.forEach((f, k) => { f.position.set(sx - f.userData.dx, 8.6 + f.userData.dy + 0.25 * Math.sin(t * 5 + k), 0); if (k === 3) ANCH.fish_color = [f.position.x, f.position.y, 0]; });
    const bd = D.has("bigfish_reverse") ? -1 : 1, bx = 20 - (((t * 2.4) % 40));
    big.position.set(bd * bx, 11.5 + 0.4 * Math.sin(t * 1.5), -3); big.rotation.y = bd > 0 ? Math.PI : 0;
    ANCH.bigfish_reverse = [big.position.x, big.position.y, -3];
    jellies.forEach(g => { g.position.y = g.userData.y0 + 0.8 * Math.sin(t * 1.4 + g.userData.ph); g.scale.y = 1 + 0.12 * Math.sin(t * 2.8 + g.userData.ph); });
    sub.position.set(((t * 1.6) % 50) - 25, 13, -8); ANCH.sub_red = [sub.position.x, 13, -8];
    bubbles.forEach(b => { const u = (t * 0.35 + b.userData.ph) % 1; b.position.set(-8 + 0.4 * Math.sin(u * 12), 3 + u * 11, -5); });
    ch.position.y = 3.5 + 0.6 * Math.sin(t * 1.7);
    ch.userData.ears.forEach((e, i) => { e.rotation.z = (i ? -1 : 1) * 0.2 * Math.sin(t * 6); });
  };
}

// ---------- ずんだもんはどこ？（11/10 ゲンタさん「ウォーリーを探せはずんだもんでもできるか。うごく3D世界で」「僕は何人いる？」）
// 広場にブロックの人が大勢歩いている。その中にずんだもんがまぎれている（p.zcount 人。ふつうは1）。
// まぎらわしい人（緑の帽子・白い服に緑のスカート）も混ぜる。p.seed で人の並びが変わる。ANCH.zunda0.. に位置。
function crowdPlaza(p) {
  const sc = CUR = new THREE.Scene();
  sc.background = new THREE.Color(0xbfe6ff);
  sc.add(new THREE.AmbientLight(0xffffff, 0.95));
  const dl = new THREE.DirectionalLight(0xffffff, 1.0); dl.position.set(20, 50, 30); sc.add(dl);
  let sd = (p.seed || 1) * 9973;
  const rnd = () => { sd = (sd * 16807) % 2147483647; return sd / 2147483647; };
  const B = (list, sz = 1, pos = [0, 0, 0]) => { const m = blocks(list, sz); m.position.set(...pos); sc.add(m); return m; };
  const XW = 22, ZD = 16;
  // 地面（石だたみ）と芝生のふち
  const L = [];
  for (let x = -XW; x <= XW; x++) for (let z = -ZD; z <= ZD; z++) {
    const edge = Math.abs(x) > XW - 3 || Math.abs(z) > ZD - 2;
    L.push([x, 0, z, edge ? ((x + z) % 2 ? 0x5cb85c : 0x4aa64a) : ((x + z) % 2 ? 0xe8dcc4 : 0xd9ccb0)]);
  }
  B(L);
  // 噴水（まん中）
  const fw = [];
  for (let a = 0; a < 24; a++) { const t = a / 24 * Math.PI * 2; fw.push([Math.round(Math.cos(t) * 3.5), 1, Math.round(Math.sin(t) * 3.5), 0xa0a0a8]); }
  B(fw); B([[0, 1, 0, 0xa0a0a8], [0, 2, 0, 0xa0a0a8]]);
  const water = []; for (let k = 0; k < 6; k++) { const w = B([[0, 0, 0, 0x8fd0ff]], 0.5); water.push(w); }
  // 屋台（奥）
  [[-14, -13, 0xe8452a], [-6, -13, 0x3a7fd8], [2, -13, 0xf2c230], [10, -13, 0x3aa65a], [17, -12, 0xd85aa0]].forEach(([x, z, c]) => {
    const st = [];
    for (let dx = -2; dx <= 2; dx++) { st.push([dx, 1, 0, 0x8b5a2b], [dx, 3.2, 0, (dx % 2) ? c : 0xffffff], [dx, 3.2, 1, (dx % 2) ? c : 0xffffff]); }
    st.push([-2, 2, 0, 0x7a4a24], [2, 2, 0, 0x7a4a24]);
    B(st, 1, [x, 0, z]);
  });
  // 木（左右）
  [[-20, -6], [-20, 6], [20, -6], [20, 6], [-12, 13], [12, 13]].forEach(([x, z]) => {
    const t = [[0, 1, 0, COL.trunk], [0, 2, 0, COL.trunk]];
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = 0; c <= 1; c++) t.push([a, 3 + c, b, (a + b + c) % 2 ? COL.leaf : COL.leaf2]);
    B(t, 1, [x, 0, z]);
  });
  // 風船売り（風船がゆれる）
  const bal = []; [0xff4a7a, 0x4ab0ff, 0xffd23a, 0x6ad86a].forEach((c, k) => { const b = B([[0, 0, 0, c], [0, -0.8, 0, 0xeeeeee]], 0.7); b.userData = { k }; bal.push(b); });
  // 人
  const SH = [0xe8452a, 0x3a7fd8, 0xf2c230, 0x3aa65a, 0xd85aa0, 0xffffff, 0x8a5ad8, 0xff9a3a, 0x444444, 0x2ab8b0];
  const HAIRS = [0x222222, 0x5a3418, 0x8a5a2a, 0xe8c070, 0x777777];
  const person = (decoy) => {
    const g = new THREE.Group(), body = new THREE.Group(); g.add(body);
    const add = (w, h, d, x, y, z, col) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshLambertMaterial({ color: col })); m.position.set(x, y, z); body.add(m); return m; };
    const shirt = decoy === 2 ? 0xf6f6f6 : SH[Math.floor(rnd() * SH.length)];
    const pants = decoy === 2 ? 0x4f9e2c : [0x2a3a6a, 0x333333, 0x6a4a2a, 0x2a5a3a][Math.floor(rnd() * 4)];
    const legs = [add(0.32, 0.9, 0.32, -0.22, 0.45, 0, pants), add(0.32, 0.9, 0.32, 0.22, 0.45, 0, pants)];
    add(0.9, 1.0, 0.55, 0, 1.4, 0, shirt);
    add(0.75, 0.75, 0.75, 0, 2.3, 0, 0xffe2c8);
    add(0.82, 0.25, 0.82, 0, 2.75, 0, decoy === 1 ? 0x8cc63a : HAIRS[Math.floor(rnd() * HAIRS.length)]);
    if (decoy === 1) add(1.1, 0.12, 1.1, 0, 2.86, 0, 0x8cc63a);   // 緑の帽子のつば
    g.userData = { legs };
    g.scale.setScalar(1.25);
    sc.add(g); return g;
  };
  const N = p.n || 95, walkers = [];
  for (let i = 0; i < N; i++) {
    const decoy = i % 9 === 0 ? 1 : (i % 11 === 0 ? 2 : 0);
    const g = person(decoy);
    let x0, z0; do { x0 = (rnd() * 2 - 1) * (XW - 4); z0 = (rnd() * 2 - 1) * (ZD - 3) + 1; } while (Math.hypot(x0, z0) < 5);
    walkers.push({ g, x0, z0, kind: rnd() < 0.5 ? "line" : "circ", a: rnd() * Math.PI * 2, r: 1.5 + rnd() * 4, sp: 0.3 + rnd() * 0.5, ph: rnd() * 6.28 });
  }
  // ずんだもん（p.zcount 人）
  const zs = [];
  for (let k = 0; k < (p.zcount || 1); k++) {
    const ch = blockChar(); ch.scale.setScalar(1.15); sc.add(ch);
    let x0, z0; do { x0 = (rnd() * 2 - 1) * (XW - 5); z0 = (rnd() * 2 - 1) * (ZD - 4) + 1; } while (Math.hypot(x0, z0) < 6);
    zs.push({ g: ch, x0, z0, kind: "line", a: rnd() * Math.PI * 2, r: 2 + rnd() * 2, sp: 0.35, ph: rnd() * 6.28 });
  }
  const place = (w, t) => {
    let x, z, dx, dz;
    if (w.kind === "line") { const u = Math.sin(t * w.sp + w.ph); x = w.x0 + Math.cos(w.a) * w.r * u; z = w.z0 + Math.sin(w.a) * w.r * u; dx = Math.cos(w.a) * Math.cos(t * w.sp + w.ph); dz = Math.sin(w.a) * Math.cos(t * w.sp + w.ph); }
    else { const u = t * w.sp * 0.6 + w.ph; x = w.x0 + Math.cos(u) * w.r; z = w.z0 + Math.sin(u) * w.r; dx = -Math.sin(u); dz = Math.cos(u); }
    x = Math.max(-XW + 2, Math.min(XW - 2, x)); z = Math.max(-ZD + 3, Math.min(ZD - 1.5, z));
    w.g.position.set(x, 0.5, z); w.g.rotation.y = Math.atan2(dx, dz);
    return [x, z];
  };
  return (t, d) => {
    const sw = Math.sin(t * 0.2) * 1.2;
    C.position.set(sw, p.cam_h ?? 30, p.cam_z ?? 19); C.lookAt(sw * 0.3, 0, -0.5);
    walkers.forEach(w => { place(w, t); const s = Math.sin(t * 8 * w.sp + w.ph); if (w.g.userData.legs) { w.g.userData.legs[0].rotation.x = 0.5 * s; w.g.userData.legs[1].rotation.x = -0.5 * s; } w.g.position.y = 0.5 + Math.abs(s) * 0.08; });
    zs.forEach((w, k) => { const [x, z] = place(w, t); w.g.position.y = 1.4 + Math.abs(Math.sin(t * 5)) * 0.1; ANCH["zunda" + k] = [x, 3, z]; });
    water.forEach((w, k) => { const u = (t * 0.8 + k / 6) % 1; const a = k / 6 * Math.PI * 2; w.position.set(Math.cos(a) * u * 2.5, 3 + 3 * u - 4 * u * u, Math.sin(a) * u * 2.5); });
    bal.forEach(b => { b.position.set(15 + b.userData.k * 0.7, 6 + 0.3 * Math.sin(t * 1.5 + b.userData.k), 4); });
  };
}

// ---------- ずんだもんはどこ？ ミニチュアの街（11/10 ゲンタさん「等身が1人だけ違う」「ミニチュアの街みたいな、車とか電車とか観覧車とか動いてる世界で、もう少し小さく」）
// 人もずんだもんも同じ小さな人形の形（ずんだもんは緑の髪・白い服・緑のスカート・小さな枝豆のさや）。まぎらわしい人を多めに混ぜる。
function miniCity(p) {
  const sc = CUR = new THREE.Scene();
  sc.background = new THREE.Color(0xcfeeff);
  sc.add(new THREE.AmbientLight(0xffffff, 0.9));
  const dl = new THREE.DirectionalLight(0xffffff, 1.05); dl.position.set(30, 60, 25); sc.add(dl);
  let sd = (p.seed || 1) * 7919 + 13;
  const rnd = () => { sd = (sd * 16807) % 2147483647; return sd / 2147483647; };
  const B = (list, sz = 1, pos = [0, 0, 0]) => { const m = blocks(list, sz); m.position.set(...pos); sc.add(m); return m; };
  const XW = 22, ZD = 32;
  const ROADX = [-8, 8], ROADZ = [-14, 2, 18];              // 道（縦2本・横2本）
  const isRoad = (x, z) => ROADX.some(r => Math.abs(x - r) <= 1) || ROADZ.some(r => Math.abs(z - r) <= 1);
  // 地面：道・歩道・芝
  const G = [];
  for (let x = -XW; x <= XW; x++) for (let z = -ZD; z <= ZD; z++) {
    let c = (x + z) % 2 ? 0x6cc46c : 0x5cb85c;
    if (isRoad(x, z)) c = 0x5a5a60;
    else if (ROADX.some(r => Math.abs(x - r) === 2) || ROADZ.some(r => Math.abs(z - r) === 2)) c = 0xd9d2c4;
    G.push([x, 0, z, c]);
  }
  B(G);
  // 線路（奥の長方形の輪）
  const RX0 = -20, RX1 = 20, RZ0 = -31, RZ1 = -26;
  const rl = []; for (let x = RX0; x <= RX1; x++) rl.push([x, 0.55, RZ0, 0x6a5a4a], [x, 0.55, RZ1, 0x6a5a4a]);
  for (let z = RZ0; z <= RZ1; z++) rl.push([RX0, 0.55, z, 0x6a5a4a], [RX1, 0.55, z, 0x6a5a4a]);
  const rlm = B(rl); rlm.scale.y = 0.3;
  const PER = 2 * ((RX1 - RX0) + (RZ1 - RZ0));
  const rp = s => { s = ((s % PER) + PER) % PER; const w = RX1 - RX0, h = RZ1 - RZ0;
    if (s < w) return [RX0 + s, RZ0, 0]; if ((s -= w) < h) return [RX1, RZ0 + s, Math.PI / 2];
    if ((s -= h) < w) return [RX1 - s, RZ1, Math.PI]; s -= w; return [RX0, RZ1 - s, -Math.PI / 2]; };
  const cars = [0xd83a3a, 0xf2f2f2, 0xd83a3a, 0xf2f2f2].map(c => { const g = new THREE.Group(); g.add(blocks([[-1, 0, 0, c], [0, 0, 0, c], [1, 0, 0, c], [-1, 0.9, 0, 0x9fd8ff], [0, 0.9, 0, 0x9fd8ff], [1, 0.9, 0, 0x9fd8ff]], 0.9)); sc.add(g); return g; });
  // 建物（区画ごと）
  for (let k = 0; k < 26; k++) {
    let x, z; do { x = Math.round((rnd() * 2 - 1) * (XW - 3)); z = Math.round(-24 + rnd() * 8); } while (isRoad(x, z) || isRoad(x + 1, z + 1));
    const h = 2 + Math.floor(rnd() * 5), c = [0xf2e6d0, 0xe0c8a8, 0xc8d8e8, 0xf0c0b0, 0xd8e8c8, 0xe8e8e8][Math.floor(rnd() * 6)];
    const bl = []; for (let y = 1; y <= h; y++) for (let dx = 0; dx < 2; dx++) for (let dz = 0; dz < 2; dz++) bl.push([dx, y, dz, (y % 2 && dx === 0) ? 0x9fc8e8 : c]);
    bl.push([0, h + 1, 0, 0xb04a3a], [1, h + 1, 0, 0xb04a3a], [0, h + 1, 1, 0xb04a3a], [1, h + 1, 1, 0xb04a3a]);
    B(bl, 1, [x, 0, z]);
  }
  // 観覧車（右手前）
  const FW = new THREE.Group(); FW.position.set(15, 9, 9); sc.add(FW);
  const ring = []; for (let a = 0; a < 32; a++) { const t = a / 32 * Math.PI * 2; ring.push([0, Math.round(Math.cos(t) * 7 * 10) / 10, Math.round(Math.sin(t) * 7 * 10) / 10, 0xf2f2f2]); }
  const wheel = new THREE.Group(); FW.add(wheel); wheel.add(blocks(ring.map(r => [r[2], r[1], 0, r[3]]), 0.6));
  const gond = [0xff4a7a, 0x4ab0ff, 0xffd23a, 0x6ad86a, 0xff9a3a, 0x9a6ad8, 0xff4a7a, 0x4ab0ff].map(c => { const g = blocks([[0, 0, 0, c]], 1.1); FW.add(g); return g; });
  B([[0, 0, 0, 0x888888], [0, 1, 0, 0x888888], [0, 2, 0, 0x888888], [0, 3, 0, 0x888888], [0, 4, 0, 0x888888], [0, 5, 0, 0x888888], [0, 6, 0, 0x888888], [0, 7, 0, 0x888888]], 1, [15, 1, 8]);
  // 木
  for (let k = 0; k < 22; k++) {
    let x, z; do { x = Math.round((rnd() * 2 - 1) * (XW - 2)); z = Math.round((rnd() * 2 - 1) * (ZD - 2)); } while (isRoad(x, z) || (z > -25 && z < -15));
    B([[0, 1, 0, COL.trunk], [0, 2, 0, COL.leaf], [1, 2, 0, COL.leaf2], [-1, 2, 0, COL.leaf2], [0, 2, 1, COL.leaf], [0, 2, -1, COL.leaf2], [0, 3, 0, COL.leaf]], 0.8, [x, 0, z]);
  }
  // 車（道を行き来）
  const autos = [];
  for (let k = 0; k < 10; k++) {
    const c = [0xd83a3a, 0x3a6fd8, 0xf2c230, 0xffffff, 0x333333, 0x3aa65a][k % 6];
    const m = blocks([[0, 0, 0, c], [1, 0, 0, c], [0.5, 0.8, 0, 0x9fd8ff]], 0.8); sc.add(m);
    const vert = k % 2 === 0, lane = vert ? ROADX[k % 4 < 2 ? 0 : 1] : ROADZ[k % 4 < 2 ? 0 : 1];
    autos.push({ m, vert, lane: lane + (k % 3 === 0 ? 0.6 : -0.6), sp: (k % 3 === 0 ? 1 : -1) * (3 + rnd() * 3), ph: rnd() * 60 });
  }
  // 人形（人もずんだもんも同じ形）
  const SH = [0xe8452a, 0x3a7fd8, 0xf2c230, 0x3aa65a, 0xd85aa0, 0xffffff, 0x8a5ad8, 0xff9a3a, 0x444444, 0x2ab8b0];
  const HAIRS = [0x222222, 0x5a3418, 0x8a5a2a, 0xe8c070, 0x777777];
  const doll = (kind) => {   // kind: 0 ふつう, 1 緑の髪, 2 白い服＋緑の下, 3 緑の髪＋白い服（いちばんまぎらわしい）, 9 ずんだもん
    const g = new THREE.Group();
    const add = (w, h, d, x, y, z, col) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshLambertMaterial({ color: col })); m.position.set(x, y, z); g.add(m); return m; };
    const Z = kind === 9;
    const shirt = (Z || kind === 2 || kind === 3) ? 0xf6f6f6 : SH[Math.floor(rnd() * SH.length)];
    const low = (Z || kind === 2) ? 0x4f9e2c : [0x2a3a6a, 0x333333, 0x6a4a2a, 0x2a5a3a][Math.floor(rnd() * 4)];
    const hair = (Z || kind === 1 || kind === 3) ? 0xa6d94a : HAIRS[Math.floor(rnd() * HAIRS.length)];
    const legs = [add(0.3, 0.7, 0.3, -0.18, 0.35, 0, Z ? 0xf6f6f6 : low), add(0.3, 0.7, 0.3, 0.18, 0.35, 0, Z ? 0xf6f6f6 : low)];
    if (Z) add(0.95, 0.4, 0.6, 0, 0.82, 0, 0x4f9e2c);    // スカート
    add(0.8, 0.8, 0.5, 0, 1.2, 0, shirt);
    add(0.7, 0.7, 0.7, 0, 1.95, 0, 0xffe2c8);
    add(0.78, 0.25, 0.78, 0, 2.35, 0, hair);
    add(0.78, 0.55, 0.15, 0, 2.05, -0.36, hair);
    if (Z) { add(0.18, 0.3, 0.18, -0.5, 2.35, 0, 0x5aa830); add(0.18, 0.3, 0.18, 0.5, 2.35, 0, 0x5aa830); }   // 小さな枝豆のさや
    g.userData = { legs }; g.scale.setScalar(p.doll ?? 0.72); sc.add(g); return g;
  };
  const free = () => { let x, z; do { x = (rnd() * 2 - 1) * (XW - 2); z = -12 + rnd() * (ZD + 10); } while (isRoad(x, z) || (x > 10 && x < 20 && z < 13 && z > 5)); return [x, z]; };
  const walkers = [];
  const N = p.n || 170;
  for (let i = 0; i < N; i++) {
    const kind = i % 7 === 0 ? 1 : i % 10 === 0 ? 2 : i % 17 === 0 ? 3 : 0;
    const [x0, z0] = free();
    walkers.push({ g: doll(kind), x0, z0, a: rnd() * Math.PI * 2, r: 1 + rnd() * 3, sp: 0.3 + rnd() * 0.5, ph: rnd() * 6.28 });
  }
  const zs = [];
  for (let k = 0; k < (p.zcount || 1); k++) { const [x0, z0] = free(); zs.push({ g: doll(9), x0, z0, a: rnd() * Math.PI * 2, r: 1.5 + rnd() * 2, sp: 0.4, ph: rnd() * 6.28 }); }
  const place = (w, t) => {
    const u = Math.sin(t * w.sp + w.ph);
    let x = w.x0 + Math.cos(w.a) * w.r * u, z = w.z0 + Math.sin(w.a) * w.r * u;
    x = Math.max(-XW + 1, Math.min(XW - 1, x)); z = Math.max(-ZD + 1, Math.min(ZD - 1, z));
    const dir = Math.cos(t * w.sp + w.ph) >= 0 ? 1 : -1;
    w.g.position.set(x, 0.5, z); w.g.rotation.y = Math.atan2(Math.cos(w.a) * dir, Math.sin(w.a) * dir);
    const s = Math.sin(t * 9 * w.sp + w.ph); w.g.userData.legs[0].rotation.x = 0.5 * s; w.g.userData.legs[1].rotation.x = -0.5 * s;
    return [x, z];
  };
  return (t, d) => {
    const sw = Math.sin(t * 0.18) * 1.5;
    C.position.set(sw, p.cam_h ?? 60, p.cam_z ?? 26); C.lookAt(sw * 0.3, 0, 1);
    walkers.forEach(w => place(w, t));
    zs.forEach((w, k) => { const [x, z] = place(w, t); ANCH["zunda" + k] = [x, 2, z]; });
    cars.forEach((g, i) => { const [x, z, h] = rp(t * 4 - i * 2.8); g.position.set(x, 1, z); g.rotation.y = -h; });
    wheel.rotation.z = t * 0.25;
    gond.forEach((g, i) => { const a = t * 0.25 + i / gond.length * Math.PI * 2; g.position.set(Math.cos(a) * 7, Math.sin(a) * 7 - 0.8, 0.6); });
    autos.forEach(a => { const s = (((t * a.sp + a.ph) % (2 * XW)) + 2 * XW) % (2 * XW) - XW; if (a.vert) { a.m.position.set(a.lane, 1, s * ZD / XW); a.m.rotation.y = Math.PI / 2; } else { a.m.position.set(s, 1, a.lane); a.m.rotation.y = 0; } });
  };
}

// 画面いっぱいが町（11/10 ゲンタさん「見えてる画面がまるまる町とかステージみたいな世界観」「ギミックとかオブジェクトが多い方が良さそう」）
// 板の端や空が映らないように、地面と建物をカメラの見える範囲より広く敷く。動くもの：電車と踏切、川の船、車とバス、信号、観覧車、メリーゴーランド、噴水、クレーン、ダンプ、池のアヒル、気球、鳥
function townFull(p) {
  const sc = CUR = new THREE.Scene();
  sc.background = new THREE.Color(0x8fbf6a);
  sc.add(new THREE.AmbientLight(0xffffff, 0.9));
  const dl = new THREE.DirectionalLight(0xffffff, 1.05); dl.position.set(30, 60, 25); sc.add(dl);
  let sd = (p.seed || 1) * 7919 + 13;
  const rnd = () => { sd = (sd * 16807) % 2147483647; return sd / 2147483647; };
  const ri = (a, b) => a + Math.floor(rnd() * (b - a + 1));
  const B = (list, sz = 1, pos = [0, 0, 0]) => { const m = blocks(list, sz); m.position.set(...pos); sc.add(m); return m; };
  const X0 = -64, X1 = 64, Z0 = -76, Z1 = 44;
  const ROADX = [-13, 13], ROADZ = [-6, 20];
  const RIV = [-25, -21], RAIL = -34;
  const onRX = x => ROADX.some(r => Math.abs(x - r) <= 1), onRZ = z => ROADZ.some(r => Math.abs(z - r) <= 1);
  const isRoad = (x, z) => onRX(x) || onRZ(z);
  const isRiver = z => z >= RIV[0] && z <= RIV[1];
  const occ = new Set(), key = (x, z) => Math.round(x) + "," + Math.round(z);
  const mark = (x0, z0, w, d, pad = 1) => { for (let x = x0 - pad; x < x0 + w + pad; x++) for (let z = z0 - pad; z < z0 + d + pad; z++) occ.add(key(x, z)); };
  // 地面
  const G = [];
  for (let x = X0; x <= X1; x++) for (let z = Z0; z <= Z1; z++) {
    let c = (x + z) % 2 ? 0x6cc46c : 0x5cb85c, y = 0;
    if (isRiver(z) && !onRX(x)) { c = (x + z) % 2 ? 0x3a8ee6 : 0x2f7fd8; y = -0.3; }
    else if (isRoad(x, z)) c = isRiver(z) ? 0x8a7a6a : 0x5a5a60;
    else if (Math.abs(z - RAIL) <= 1) c = 0x8a7a6a;
    else if (ROADX.some(r => Math.abs(x - r) === 2) || ROADZ.some(r => Math.abs(z - r) === 2) || isRiver(z - 1) || isRiver(z + 1)) c = 0xd9d2c4;
    if (onRZ(z) && Math.abs(z - Math.round(z)) < 0.01 && ROADZ.includes(z) && x % 4 === 0 && !onRX(x)) c = 0xf2f2f2;   // 中央線
    G.push([x, y, z, c]);
  }
  B(G);
  for (let x = X0; x <= X1; x++) occ.add(key(x, RAIL)), occ.add(key(x, RAIL - 1)), occ.add(key(x, RAIL + 1));
  // 橋の欄干
  const rail = []; ROADX.forEach(r => { for (let z = RIV[0] - 1; z <= RIV[1] + 1; z++) rail.push([r - 2, 0.8, z, 0xb04a3a], [r + 2, 0.8, z, 0xb04a3a]); }); B(rail, 0.6);
  // 線路と電車（画面の外から外へ）
  const tr = []; for (let x = X0; x <= X1; x++) tr.push([x, 0.35, RAIL - 0.5, 0x6a5a4a], [x, 0.35, RAIL + 0.5, 0x6a5a4a]); B(tr, 0.5);
  const train = []; for (let i = 0; i < 6; i++) { const c = i === 0 ? 0x2a8a4a : 0xf2f2f2; const g = blocks([[-1, 0, 0, c], [0, 0, 0, c], [1, 0, 0, c], [-1, 1, 0, 0x9fd8ff], [0, 1, 0, c], [1, 1, 0, 0x9fd8ff], [-1, 0, 1, c], [0, 0, 1, 0x2a8a4a], [1, 0, 1, c], [-1, 1, 1, 0x9fd8ff], [0, 1, 1, c], [1, 1, 1, 0x9fd8ff]], 1); sc.add(g); train.push(g); }
  const gates = []; ROADX.forEach(r => [-1, 1].forEach(sx => { const g = new THREE.Group(); g.position.set(r + sx * 2.2, 1.4, RAIL + sx * 2); const bar = blocks([[0, 0, 0, 0xf2f2f2], [1, 0, 0, 0xe03a3a], [2, 0, 0, 0xf2f2f2]], 0.45); bar.position.x = -sx * 0.4; g.add(bar); g.scale.x = -sx; sc.add(g); gates.push(g); B([[0, 0, 0, 0x333333], [0, 1, 0, 0x333333]], 0.6, [r + sx * 2.2, 0.6, RAIL + sx * 2]); }));
  // 遠くの町（画面の上をビルで埋める）
  for (let k = 0; k < 140; k++) {
    let x, z; do { x = ri(X0 + 2, X1 - 4); z = ri(Z0 + 2, RAIL - 4); } while (onRX(x) || onRX(x + 2));
    const h = 3 + Math.floor(rnd() * (6 + (RAIL - z) / 4)), c = [0xf2e6d0, 0xe0c8a8, 0xc8d8e8, 0xf0c0b0, 0xd8e8c8, 0xe8e8e8, 0xb8c8d8][ri(0, 6)];
    const bl = []; for (let y = 1; y <= h; y++) for (let dx = 0; dx < 3; dx++) for (let dz = 0; dz < 3; dz++) if (dx === 1 && dz === 1 && y < h) continue; else bl.push([dx, y, dz, (y % 2 && dz === 2 && dx !== 1) ? 0x9fc8e8 : c]);
    B(bl, 1, [x, 0, z]);
  }
  // 建物（町の中）
  const house = (x, z, w, d, h, c, roof) => {
    const bl = []; for (let y = 1; y <= h; y++) for (let dx = 0; dx < w; dx++) for (let dz = 0; dz < d; dz++) { if (dx > 0 && dx < w - 1 && dz > 0 && dz < d - 1 && y < h) continue; bl.push([dx, y, dz, (y % 2 && dz === d - 1 && dx % 2 === 0) ? 0x9fc8e8 : c]); }
    for (let dx = 0; dx < w; dx++) for (let dz = 0; dz < d; dz++) bl.push([dx, h + 1, dz, roof]);
    B(bl, 1, [x, 0, z]); mark(x, z, w, d);
  };
  const CB = [0xf2e6d0, 0xe0c8a8, 0xc8d8e8, 0xf0c0b0, 0xd8e8c8, 0xe8e8e8], CR = [0xb04a3a, 0x3a6fd8, 0x4a8a3a, 0x8a5a3a, 0x555555];
  const tryHouse = (xa, xb, za, zb, wmax, hmax) => { for (let n = 0; n < 30; n++) { const w = ri(2, wmax), d = ri(2, 3), x = ri(xa, xb - w), z = ri(za, zb - d); let ok = true; for (let a = x - 1; a <= x + w && ok; a++) for (let b = z - 1; b <= z + d; b++) if (occ.has(key(a, b)) || isRoad(a, b) || isRiver(b)) { ok = false; break; } if (ok) { house(x, z, w, d, ri(2, hmax), CB[ri(0, 5)], CR[ri(0, 4)]); return; } } };
  // 風車（左の手前）
  const mills = [[-19, -13], [19, -16], [-6, 24]].map(([x, z]) => { B([[0, 1, 0, 0xf2f2f2], [0, 2, 0, 0xf2f2f2], [0, 3, 0, 0xf2f2f2], [0, 4, 0, 0xf2f2f2], [0, 5, 0, 0xf2f2f2]], 1, [x, 0, z]); const g = new THREE.Group(); g.position.set(x, 5.5, z + 0.7); const bl = []; for (let r = 1; r <= 4; r++) bl.push([r, 0, 0, 0xe8e8e8], [-r, 0, 0, 0xe8e8e8], [0, r, 0, 0xe8e8e8], [0, -r, 0, 0xe8e8e8]); g.add(blocks(bl, 0.7)); sc.add(g); mark(x, z, 1, 1); return g; });
  // 手前：プールと駐車場
  const pool = []; for (let x = 0; x < 8; x++) for (let z = 0; z < 4; z++) pool.push([x, 0.05, z, (x === 0 || x === 7 || z === 0 || z === 3) ? 0xf2f2f2 : 0x5ac8f0]); B(pool, 1, [3, 0, 24]); mark(3, 24, 8, 4, 0);
  const floats = []; for (let i = 0; i < 3; i++) { const m = blocks([[0, 0, 0, [0xff4a7a, 0xf2c230, 0x6ad86a][i]]], 0.7); sc.add(m); floats.push(m); }
  const park = []; for (let x = 0; x < 10; x++) for (let z = 0; z < 5; z++) park.push([x, 0.05, z, x % 2 ? 0x77777c : 0x6a6a70]); B(park, 1, [-18, 0, 24]);
  for (let k = 0; k < 6; k++) { const c = [0xd83a3a, 0x3a6fd8, 0xf2c230, 0xffffff, 0x333333, 0x3aa65a][(k * 7 + (p.seed || 1)) % 6]; B([[0, 0, 0, c], [0, 0, 1, c], [0, 0.8, 0.5, 0x9fd8ff]], 0.8, [-17 + (k % 5) * 2, 1, 24 + (k > 4 ? 3 : 0.5)]); }
  mark(-18, 24, 10, 5, 0);
  // 川と線路のあいだ、両端
  for (let k = 0; k < 34; k++) tryHouse(X0 + 2, X1 - 2, RAIL + 3, RIV[0] - 2, 4, 6);
  // 川の手前の町（左右のブロック）
  for (let k = 0; k < 10; k++) tryHouse(-40, -16, RIV[1] + 3, ROADZ[0] - 3, 4, 7);
  for (let k = 0; k < 10; k++) tryHouse(16, 40, RIV[1] + 3, ROADZ[0] - 3, 4, 7);
  // 手前の家並み（いちばん下）
  for (let k = 0; k < 28; k++) tryHouse(X0 + 2, X1 - 2, ROADZ[1] + 3, Z1 - 1, 3, 3);
  // 中央の広場：噴水と屋台
  const FX = 0, FZ = -14;
  const fb = []; for (let a = 0; a < 20; a++) { const t = a / 20 * Math.PI * 2; fb.push([Math.round(Math.cos(t) * 3), 0.6, Math.round(Math.sin(t) * 3), 0xd9d2c4]); } B(fb, 1, [FX, 0, FZ]);
  const fw = []; for (let x = -2; x <= 2; x++) for (let z = -2; z <= 2; z++) if (x * x + z * z <= 5) fw.push([x, 0.5, z, 0x6ab8f0]); B(fw, 1, [FX, 0, FZ]);
  const jets = []; for (let i = 0; i < 7; i++) { const m = blocks([[0, 0, 0, 0xdff3ff]], 0.6); sc.add(m); jets.push(m); }
  mark(FX - 3, FZ - 3, 7, 7, 0);
  const awn = [0xe03a3a, 0x3a7fd8, 0xf2c230, 0x3aa65a, 0xd85aa0];
  for (let i = 0; i < 5; i++) { const x = -9 + i * 4, z = -19; B([[0, 1, 0, 0xf2e6d0], [1, 1, 0, 0xf2e6d0], [0, 2, 0, awn[i]], [1, 2, 0, awn[i]], [0, 2, 1, awn[i]], [1, 2, 1, awn[i]]], 1, [x, 0, z]); mark(x, z, 2, 1, 0); }
  // 工事現場：クレーン（回る）とダンプ（行き来）
  const CX = -22, CZ = 7;
  const cf = []; for (let x = -6; x <= 6; x++) for (let z = -5; z <= 5; z++) if (Math.abs(x) === 6 || Math.abs(z) === 5) cf.push([x, 0.6, z, (x + z) % 2 ? 0xf2c230 : 0x333333]); B(cf, 0.6, [CX, 0, CZ]);
  const mast = []; for (let y = 1; y <= 14; y++) mast.push([0, y, 0, 0xf2a020]); B(mast, 0.8, [CX, 0, CZ]);
  const jib = new THREE.Group(); jib.position.set(CX, 11.6, CZ); sc.add(jib);
  const jl = []; for (let x = -3; x <= 10; x++) jl.push([x, 0, 0, x < 0 ? 0x888888 : 0xf2a020]); jib.add(blocks(jl, 0.8));
  const hook = blocks([[0, 0, 0, 0x555555], [0, -1, 0, 0x555555], [0, -2, 0, 0x555555], [0, -3, 0, 0x8a5a2a], [0.8, -3, 0, 0x8a5a2a]], 0.6); hook.position.set(6, 0, 0); jib.add(hook);
  B([[0, 1, 0, 0xc8c8c8], [1, 1, 0, 0xc8c8c8], [0, 2, 0, 0xc8c8c8], [1, 2, 0, 0xc8c8c8], [0, 1, 1, 0xc8c8c8], [1, 1, 1, 0xc8c8c8]], 1, [CX + 2, 0, CZ - 3]);
  const dump = blocks([[0, 0, 0, 0xf2c230], [1, 0, 0, 0xf2c230], [2, 0, 0, 0x8a5a2a], [3, 0, 0, 0x8a5a2a], [0, 1, 0, 0x9fd8ff], [2, 1, 0, 0x8a5a2a], [3, 1, 0, 0x8a5a2a]], 0.8); sc.add(dump);
  mark(CX - 6, CZ - 5, 13, 11, 0);
  // 公園：メリーゴーランドと池のアヒル
  const MX = 0, MZ = 7;
  const mg = new THREE.Group(); mg.position.set(MX, 0, MZ); sc.add(mg);
  const disk = []; for (let x = -4; x <= 4; x++) for (let z = -4; z <= 4; z++) if (x * x + z * z <= 17) disk.push([x, 0.6, z, (x + z) % 2 ? 0xf2e6d0 : 0xd85aa0]); mg.add(blocks(disk, 1));
  const top = []; for (let x = -4; x <= 4; x++) for (let z = -4; z <= 4; z++) if (x * x + z * z <= 17) top.push([x, 5.2, z, (Math.atan2(z, x) * 4 / Math.PI | 0) % 2 ? 0xe03a3a : 0xf2f2f2]); mg.add(blocks(top, 1));
  mg.add(blocks([[0, 1.5, 0, 0xf2c230], [0, 2.5, 0, 0xf2c230], [0, 3.5, 0, 0xf2c230], [0, 4.5, 0, 0xf2c230]], 1));
  const horses = []; for (let i = 0; i < 6; i++) { const c = [0xffffff, 0x8a5a2a, 0xf2c230, 0x4ab0ff, 0xff4a7a, 0x333333][i]; const h = blocks([[0, 0, 0, c], [0.8, 0, 0, c], [1.2, 0.7, 0, c]], 0.8); mg.add(h); horses.push(h); }
  mark(MX - 4, MZ - 4, 9, 9, 0);
  const PX = 6, PZ = 14;
  const pond = []; for (let x = -3; x <= 3; x++) for (let z = -2; z <= 2; z++) if (x * x / 9 + z * z / 4 <= 1) pond.push([x, 0.05, z, 0x4aa0e8]); B(pond, 1, [PX, 0, PZ]);
  const ducks = []; for (let i = 0; i < 4; i++) { const d = blocks([[0, 0, 0, i ? 0xffffff : 0xf2c230], [0.5, 0.5, 0, i ? 0xffffff : 0xf2c230]], 0.5); sc.add(d); ducks.push(d); }
  mark(PX - 3, PZ - 2, 7, 5, 0);
  // 観覧車（右）
  const WX = 21, WZ = 10;
  const FW = new THREE.Group(); FW.position.set(WX, 9, WZ); FW.rotation.x = -0.75; sc.add(FW);
  const ring = []; for (let a = 0; a < 36; a++) { const t = a / 36 * Math.PI * 2; ring.push([Math.round(Math.sin(t) * 70) / 10, Math.round(Math.cos(t) * 70) / 10, 0, 0xf2f2f2]); }
  const wheel = new THREE.Group(); FW.add(wheel); wheel.add(blocks(ring, 0.6));
  const spk = []; for (let a = 0; a < 8; a++) for (let r = 1; r < 7; r++) { const t = a / 8 * Math.PI * 2; spk.push([Math.cos(t) * r, Math.sin(t) * r, 0, 0xcccccc]); } wheel.add(blocks(spk, 0.3));
  const gond = [0xff4a7a, 0x4ab0ff, 0xffd23a, 0x6ad86a, 0xff9a3a, 0x9a6ad8, 0xff4a7a, 0x4ab0ff].map(c => { const g = blocks([[0, 0, 0, c]], 1.1); FW.add(g); return g; });
  B([[0, 0, 0, 0x888888], [0, 1, 0, 0x888888], [0, 2, 0, 0x888888], [0, 3, 0, 0x888888], [0, 4, 0, 0x888888], [0, 5, 0, 0x888888], [0, 6, 0, 0x888888], [0, 7, 0, 0x888888]], 1, [WX, 1, WZ - 1]);
  mark(WX - 7, WZ - 2, 15, 4, 0);
  // 木
  for (let k = 0; k < 70; k++) {
    let x, z, n = 0; do { x = ri(X0 + 2, X1 - 2); z = ri(RAIL + 3, Z1 - 1); n++; } while ((isRoad(x, z) || isRiver(z) || occ.has(key(x, z)) || Math.abs(z - RAIL) < 3) && n < 50);
    if (n >= 50) continue;
    B([[0, 1, 0, COL.trunk], [0, 2, 0, COL.leaf], [1, 2, 0, COL.leaf2], [-1, 2, 0, COL.leaf2], [0, 2, 1, COL.leaf], [0, 2, -1, COL.leaf2], [0, 3, 0, COL.leaf]], 0.8, [x, 0, z]); occ.add(key(x, z));
  }
  // 信号（交差点の角。色が変わる）
  const lights = [];
  ROADX.forEach(rx => ROADZ.forEach(rz => { const x = rx + 2.2, z = rz + 2.2; B([[0, 0, 0, 0x333333], [0, 1, 0, 0x333333], [0, 2, 0, 0x333333]], 0.5, [x, 0.4, z]); const l = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.6, 0.6), new THREE.MeshBasicMaterial({ color: 0x3ad83a })); l.position.set(x, 1.9, z); sc.add(l); lights.push(l); }));
  // 船（川を行き来）
  const boats = [0xf2f2f2, 0xe03a3a, 0xf2c230].map((c, i) => { const g = blocks([[-1, 0, 0, c], [0, 0, 0, c], [1, 0, 0, c], [2, 0, 0, c], [0, 1, 0, 0x9fd8ff], [1, 1, 0, c]], 0.8); sc.add(g); return { g, z: RIV[0] + 1 + (i % 2) * 2, sp: (i % 2 ? -1 : 1) * (2 + i), ph: i * 30 }; });
  // 車とバス（道を行き来。画面の外から出入りする）
  const autos = [];
  for (let k = 0; k < 18; k++) {
    const bus = k % 6 === 5, c = bus ? 0x3aa65a : [0xd83a3a, 0x3a6fd8, 0xf2c230, 0xffffff, 0x333333][k % 5];
    const list = bus ? [[0, 0, 0, c], [1, 0, 0, c], [2, 0, 0, c], [3, 0, 0, c], [0, 0.8, 0, 0x9fd8ff], [1, 0.8, 0, 0x9fd8ff], [2, 0.8, 0, 0x9fd8ff], [3, 0.8, 0, 0x9fd8ff]] : [[0, 0, 0, c], [1, 0, 0, c], [0.5, 0.8, 0, 0x9fd8ff]];
    const m = blocks(list, 0.8); sc.add(m);
    const vert = k % 2 === 0, lane = vert ? ROADX[(k >> 1) % 2] : ROADZ[(k >> 1) % 2], dir = (k % 4 < 2) ? 1 : -1;
    autos.push({ m, vert, lane: lane + dir * 0.6, sp: dir * (4 + rnd() * 3), ph: rnd() * 200 });
  }
  // 気球と鳥
  const balloons = [[0xe03a3a, 0xf2f2f2], [0xf2c230, 0x3a7fd8]].map(([a, b], i) => { const bl = []; for (let x = -2; x <= 2; x++) for (let y = -2; y <= 2; y++) for (let z = -2; z <= 2; z++) if (x * x + y * y + z * z <= 5) bl.push([x, y, z, (x + 2) % 2 ? a : b]); bl.push([0, -3.5, 0, 0x8a5a2a]); const m = blocks(bl, 0.8); sc.add(m); return { m, i }; });
  const birds = []; for (let i = 0; i < 7; i++) { const m = blocks([[0, 0, 0, 0xffffff], [-0.6, 0.2, 0, 0xffffff], [0.6, 0.2, 0, 0xffffff]], 0.4); sc.add(m); birds.push(m); }
  // 人形（人もずんだもんも同じ形）
  const SH = [0xe8452a, 0x3a7fd8, 0xf2c230, 0x3aa65a, 0xd85aa0, 0xffffff, 0x8a5ad8, 0xff9a3a, 0x444444, 0x2ab8b0];
  const HAIRS = [0x222222, 0x5a3418, 0x8a5a2a, 0xe8c070, 0x777777];
  const doll = (kind) => {
    const g = new THREE.Group();
    const add = (w, h, d, x, y, z, col) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshLambertMaterial({ color: col })); m.position.set(x, y, z); g.add(m); return m; };
    const Z = kind === 9;
    const shirt = (Z || kind === 2 || kind === 3) ? 0xf6f6f6 : SH[Math.floor(rnd() * SH.length)];
    const low = (Z || kind === 2) ? 0x4f9e2c : [0x2a3a6a, 0x333333, 0x6a4a2a, 0x2a5a3a][Math.floor(rnd() * 4)];
    const hair = (Z || kind === 1 || kind === 3) ? 0xa6d94a : HAIRS[Math.floor(rnd() * HAIRS.length)];
    const legs = [add(0.3, 0.7, 0.3, -0.18, 0.35, 0, Z ? 0xf6f6f6 : low), add(0.3, 0.7, 0.3, 0.18, 0.35, 0, Z ? 0xf6f6f6 : low)];
    if (Z) add(0.95, 0.4, 0.6, 0, 0.82, 0, 0x4f9e2c);
    add(0.8, 0.8, 0.5, 0, 1.2, 0, shirt);
    add(0.7, 0.7, 0.7, 0, 1.95, 0, 0xffe2c8);
    add(0.78, 0.25, 0.78, 0, 2.35, 0, hair);
    add(0.78, 0.55, 0.15, 0, 2.05, -0.36, hair);
    if (Z) { add(0.18, 0.3, 0.18, -0.5, 2.35, 0, 0x5aa830); add(0.18, 0.3, 0.18, 0.5, 2.35, 0, 0x5aa830); }
    g.userData = { legs }; g.scale.setScalar(p.doll ?? 0.72); sc.add(g); return g;
  };
  const bad = (x, z) => isRoad(x, z) || isRiver(z) || occ.has(key(x, z)) || Math.abs(z - RAIL) < 2.5;
  const free = (zmin, zmax, xm) => { for (;;) { const x = (rnd() * 2 - 1) * xm, z = zmin + rnd() * (zmax - zmin), a = rnd() * Math.PI * 2, r = 0.8 + rnd() * 2;
    if (!bad(x, z) && !bad(x + Math.cos(a) * r, z + Math.sin(a) * r) && !bad(x - Math.cos(a) * r, z - Math.sin(a) * r)) return { x0: x, z0: z, a, r }; } };
  const walkers = [];
  const N = p.n || 230;
  for (let i = 0; i < N; i++) {
    const kind = i % 7 === 0 ? 1 : i % 10 === 0 ? 2 : i % 17 === 0 ? 3 : 0;
    walkers.push(Object.assign({ g: doll(kind), sp: 0.3 + rnd() * 0.5, ph: rnd() * 6.28 }, free(-31, 29, 30)));
  }
  const zs = [];
  for (let k = 0; k < (p.zcount || 1); k++) zs.push(Object.assign({ g: doll(9), sp: 0.4, ph: rnd() * 6.28 }, free(p.z_zmin ?? -18, p.z_zmax ?? 24, p.z_xm ?? 22)));
  const place = (w, t) => {
    const u = Math.sin(t * w.sp + w.ph);
    const x = w.x0 + Math.cos(w.a) * w.r * u, z = w.z0 + Math.sin(w.a) * w.r * u;
    const dir = Math.cos(t * w.sp + w.ph) >= 0 ? 1 : -1;
    w.g.position.set(x, 0.5, z); w.g.rotation.y = Math.atan2(Math.cos(w.a) * dir, Math.sin(w.a) * dir);
    const s = Math.sin(t * 9 * w.sp + w.ph); w.g.userData.legs[0].rotation.x = 0.5 * s; w.g.userData.legs[1].rotation.x = -0.5 * s;
    return [x, z];
  };
  const LEN = X1 - X0;
  return (t, d) => {
    const sw = Math.sin(t * 0.18) * 1.5;
    C.position.set(sw, p.cam_h ?? 60, p.cam_z ?? 26); C.lookAt(sw * 0.3, 0, 1);
    walkers.forEach(w => place(w, t));
    zs.forEach((w, k) => { const [x, z] = place(w, t); ANCH["zunda" + k] = [x, 2, z]; });
    // 電車：12秒で画面を横切る。近づくと踏切が下りる
    const hx = ((t * 9 + 20) % (LEN + 40)) + X0 - 20;
    train.forEach((g, i) => g.position.set(hx - i * 3.2, 1, RAIL - 0.5));
    const near = ROADX.some(r => hx + 6 > r && hx - 6 * 3.2 - 6 < r);
    gates.forEach(g => { const tgt = near ? 0 : 1.3; g.rotation.z += (tgt * Math.sign(g.scale.x) - g.rotation.z) * 0.25; });
    // 信号：6秒ごとに 青→黄→赤
    const ph = (t % 6) / 6; lights.forEach((l, i) => l.material.color.setHex(((ph + i * 0.5) % 1) < 0.45 ? 0x3ad83a : ((ph + i * 0.5) % 1) < 0.55 ? 0xf2c230 : 0xe03a3a));
    wheel.rotation.z = t * 0.25;
    gond.forEach((g, i) => { const a = t * 0.25 + i / gond.length * Math.PI * 2; g.position.set(Math.cos(a) * 7, Math.sin(a) * 7 - 0.8, 0.6); });
    mg.rotation.y = t * 0.6;
    horses.forEach((h, i) => { const a = i / horses.length * Math.PI * 2; h.position.set(Math.cos(a) * 3, 1.6 + Math.sin(t * 3 + i) * 0.4, Math.sin(a) * 3); h.rotation.y = -a; });
    jets.forEach((j, i) => { const u = ((t * 1.2 + i / jets.length) % 1); const a = i / jets.length * Math.PI * 2; j.position.set(FX + Math.cos(a) * u * 2, 1 + Math.sin(u * Math.PI) * 4, FZ + Math.sin(a) * u * 2); });
    jib.rotation.y = Math.sin(t * 0.3) * 1.4; hook.position.y = -1 + Math.sin(t * 0.7) * 1.5;
    dump.position.set(CX - 4 + (Math.sin(t * 0.5) + 1) * 4, 1, CZ + 3);
    ducks.forEach((dk, i) => { const a = t * 0.5 + i * 0.5; dk.position.set(PX + Math.cos(a) * 2, 0.5, PZ + Math.sin(a) * 1.2); dk.rotation.y = -a; });
    mills.forEach((m, i) => m.rotation.z = t * (1.2 + i * 0.3));
    floats.forEach((m, i) => m.position.set(5 + i * 2 + Math.sin(t * 0.7 + i) * 1.2, 0.4 + Math.sin(t * 2 + i) * 0.1, 25.5 + Math.cos(t * 0.5 + i * 2) * 0.6));
    boats.forEach(b => { const s = (((t * b.sp + b.ph) % LEN) + LEN) % LEN + X0; b.g.position.set(s, 0.2, b.z); b.g.rotation.y = b.sp > 0 ? 0 : Math.PI; });
    autos.forEach(a => { const s = (((t * a.sp + a.ph) % LEN) + LEN) % LEN; if (a.vert) { a.m.position.set(a.lane, 1, Z0 + s * (Z1 - Z0) / LEN); a.m.rotation.y = a.sp > 0 ? -Math.PI / 2 : Math.PI / 2; } else { a.m.position.set(X0 + s, 1, a.lane); a.m.rotation.y = a.sp > 0 ? 0 : Math.PI; } });
    balloons.forEach(b => b.m.position.set(-30 + b.i * 50 + t * 0.8, 24 + Math.sin(t * 0.5 + b.i) * 1.5, -44 + b.i * 6));
    birds.forEach((m, i) => { const a = t * 0.6 + i * 0.25; m.position.set(Math.cos(a) * 18 + (i % 3), 20 + (i % 2), -10 + Math.sin(a) * 10); m.rotation.y = -a; m.children; });
  };
}


// ---------- 動く間違い探し：ドライブ（11/14 ゲンタさん「道の両端と背景が動いていくドライブ」「カット割ってもいい」）
// ずんだもんの車が道を走り続ける。A と B は同じカメラ。探す時間（hold まで）を3つのカットに分ける：
//   1) 運転席から前を見る  2) 横から並走（左の道ばたが流れる）  3) 前から車をふり返る（通りすぎた物が遠ざかる）
// 違い：sign_arrow（標識の矢印が逆）/ mill_reverse（風車が逆に回る）/ house_roof（家の屋根が青）
//      cow_gone（牛が1頭いない）/ mail_blue（ポストが青）/ balloon（空に風船）/ car_red（対向車が赤）
function driveScene(p) {
  const sc = CUR = new THREE.Scene();
  const D = new Set(p.diff || []);
  sc.background = new THREE.Color(0xa8e0ff); sc.fog = new THREE.Fog(0xa8e0ff, 70, 190);
  sc.add(new THREE.AmbientLight(0xffffff, 0.95));
  const dl = new THREE.DirectionalLight(0xffffff, 1.1); dl.position.set(30, 50, 25); sc.add(dl);
  let sd = 4242; const rr = () => { sd = (sd * 16807) % 2147483647; return sd / 2147483647; };
  const B = (list, sz = 1, pos = [0, 0, 0]) => { const m = blocks(list, sz); m.position.set(...pos); sc.add(m); return m; };
  const Bs = (list, sz, pos = [0, 0, 0]) => B(list.map(([x, y, z, c]) => [x * sz, y * sz, z * sz, c]), sz, pos);   // ブロックをすき間なく並べる
  const V = 7, HOLD = p.hold ?? 17, L = V * HOLD, LANE = -1.6;
  const zAt = f => -L * f;                         // 車が f（0〜1、探す時間の割合）のときにいる z
  const plane = (w, d, col, x, y, z) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshLambertMaterial({ color: col })); m.rotation.x = -Math.PI / 2; m.position.set(x, y, z); sc.add(m); return m; };
  const ZN = 30, ZF = -L - 160, ZM = (ZN + ZF) / 2, ZL = ZN - ZF;
  plane(400, ZL, 0x5cb85c, 0, 0, ZM); plane(7.2, ZL, 0x5a5a60, 0, 0.02, ZM);
  plane(0.5, ZL, 0xd9d2c4, -3.85, 0.025, ZM); plane(0.5, ZL, 0xd9d2c4, 3.85, 0.025, ZM);
  const dash = []; for (let z = ZN; z > ZF; z -= 4) dash.push([0, 0.04, z, 0xffffff]);
  const dm = B(dash, 1); dm.scale.set(0.18, 0.05, 2);
  // 山（遠く）
  for (let k = 0; k < 14; k++) { const x = (k % 2 ? 1 : -1) * (60 + rr() * 80), z = -60 - rr() * (L + 120), h = 12 + rr() * 18, col = k % 3 ? 0x6fae7a : 0x86bf8c;
    const m = new THREE.Mesh(new THREE.ConeGeometry(h * 1.2, h, 4), new THREE.MeshLambertMaterial({ color: col, flatShading: true })); m.position.set(x, h / 2, z); m.rotation.y = Math.PI / 4; sc.add(m); }
  const tree = (x, z, s = 1) => { const lf = [[0, 0.5, 0, COL.trunk], [0, 1.5, 0, COL.trunk]];
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = 0; c <= 1; c++) lf.push([a, 2.5 + c, b, (a + b + c) % 2 ? COL.leaf : COL.leaf2]);
    lf.push([0, 4.5, 0, COL.leaf]); const m = B(lf, 0.8 * s, [x, 0, z]); m.scale.setScalar(1); return m; };
  const pole = (x, z) => Bs([[0, 0, 0, 0x8a7a6a], [0, 1, 0, 0x8a7a6a], [0, 2, 0, 0x8a7a6a], [0, 3, 0, 0x8a7a6a], [0, 4, 0, 0x8a7a6a], [0, 4.2, 0.6, 0x555555], [0, 4.2, -0.6, 0x555555]], 0.4, [x, 0.2, z]);
  const house = (x, z, wall, roof, face = 1) => { const L2 = [];
    for (let a = -2; a <= 2; a++) for (let b = -2; b <= 2; b++) for (let y = 0; y <= 2; y++) if (Math.abs(a) === 2 || Math.abs(b) === 2) L2.push([a, y + 0.5, b, (y === 1 && Math.abs(a) === 2 && b === 0) ? 0x9fd8ff : wall]);
    for (let a = -3; a <= 3; a++) for (let b = -3; b <= 3; b++) L2.push([a, 3.5, b, roof]);
    for (let a = -2; a <= 2; a++) for (let b = -2; b <= 2; b++) L2.push([a, 4.5, b, roof]);
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) L2.push([a, 5.5, b, roof]);
    return B(L2, 0.9, [x, 0, z]); };
  const flowers = (x, z) => { const fl = []; for (let k = 0; k < 6; k++) fl.push([rr() * 3 - 1.5, 0.15, rr() * 3 - 1.5, [0xff6a8a, 0xffd23a, 0xffffff, 0xb36aff][k % 4]]); B(fl, 0.3, [x, 0, z]); };
  // 違いの物の場所（車がそこを通る時刻の割合）
  const DZ = { sign_arrow: zAt(0.2) - 4, mill_reverse: zAt(0.25), house_roof: zAt(0.45), cow_gone: zAt(0.58), mail_blue: zAt(0.8) };
  const near = (z, side) => Object.entries(DZ).some(([k, dz]) => Math.abs(dz - z) < (k === "mill_reverse" ? 4 : 9) && (k === "mill_reverse" ? side > 0 : side < 0));
  // 道ばた（左右）
  for (const side of [-1, 1]) for (let z = ZN; z > ZF; z -= 5) {
    if (near(z, side)) continue;
    const x = side * (5.5 + rr() * 2.5), u = rr();
    if (u < 0.5) tree(x, z + rr() * 2); else if (u < 0.62) pole(side * 4.6, z); else if (u < 0.72) house(side * (11 + rr() * 6), z, [0xf4efe4, 0xffe3b0, 0xdde8f4][Math.floor(rr() * 3)], [0xd85a3a, 0x7a5a3a, 0x3a8a5a][Math.floor(rr() * 3)]); else if (u < 0.85) flowers(x, z);
    if (rr() < 0.35) tree(side * (16 + rr() * 14), z + 2, 1.2);
  }
  // 1) 標識（左）：矢印。B は逆向き
  Bs([[0, 0, 0, 0x888888], [0, 1, 0, 0x888888], [0, 2, 0, 0x888888], [0, 3, 0, 0x888888]], 0.35, [-4.6, 0.2, DZ.sign_arrow]);
  const brd = []; for (let a = -3; a <= 3; a++) for (let b = -2; b <= 2; b++) brd.push([a, b, 0, 0x2f6fd8]);
  const signB = Bs(brd, 0.28, [-4.6, 1.75, DZ.sign_arrow + 0.08]);
  const dirA = D.has("sign_arrow") ? -1 : 1, arr = [];
  for (let a = -2; a <= 1; a++) arr.push([a * dirA, 0, 0, 0xffffff]); arr.push([1 * dirA, 1, 0, 0xffffff], [1 * dirA, -1, 0, 0xffffff], [2 * dirA, 0, 0, 0xffffff]);
  Bs(arr, 0.22, [-4.6, 1.75, DZ.sign_arrow + 0.25]);
  ANCH.sign_arrow = [-4.6, 1.75, DZ.sign_arrow];
  // 2) 風車（右の丘）
  const MX = 16, mill = []; for (let y = 0; y <= 7; y++) mill.push([0, y, 0, 0xf4efe4]); mill.push([0, 8, 0, 0xd85a3a]);
  B(mill, 1, [MX, 0.5, DZ.mill_reverse]);
  const blades = new THREE.Group(); blades.position.set(MX, 8.5, DZ.mill_reverse + 0.9); sc.add(blades);
  for (let k = 0; k < 4; k++) { const bl = blocks([[0, 0.7, 0, 0xffffff], [0, 1.4, 0, 0xffffff], [0, 2.1, 0, 0xffffff], [0, 2.8, 0, 0xffffff], [0.6, 2.4, 0, 0xffffff], [0.6, 1.7, 0, 0xffffff]], 0.7); bl.rotation.z = k * Math.PI / 2; blades.add(bl); }
  ANCH.mill_reverse = [MX, 8.5, DZ.mill_reverse];
  // 3) 家（左、道の近く）
  house(-10, DZ.house_roof, 0xfff4dc, D.has("house_roof") ? 0x3a6fd8 : 0xd83a3a); ANCH.house_roof = [-10, 4.5, DZ.house_roof];
  // 4) 牛（左の牧場、3頭。B は真ん中がいない）
  const fence = []; for (let z = -8; z <= 8; z++) fence.push([0, 0.5, z, 0xc8a878]); for (let z = -8; z <= 8; z += 2) fence.push([0, 1.1, z, 0xc8a878]);
  B(fence, 0.6, [-5.6, 0, DZ.cow_gone]);
  const cows = [];
  [-3, 0, 3].forEach((dz, i) => { if (D.has("cow_gone") && i === 1) return;
    const c = [[0, 0, 0, 0xffffff], [1, 0, 0, 0x222222], [-1, 0, 0, 0xffffff], [0, 0, 1, 0x222222], [1, 0, 1, 0xffffff], [-1, 0, 1, 0xffffff], [2, 0.6, 0.5, 0xffffff], [2.6, 0.6, 0.5, 0xf5b8c0],
      [-1, -1, 0, 0xeeeeee], [1, -1, 0, 0xeeeeee], [-1, -1, 1, 0xeeeeee], [1, -1, 1, 0xeeeeee]];
    const m = Bs(c, 0.6, [-9 - (i % 2) * 2, 1.0, DZ.cow_gone + dz * 1.6]); m.rotation.y = Math.PI / 2 + (i - 1) * 0.5; cows.push(m); });
  ANCH.cow_gone = [-9, 1.2, DZ.cow_gone];
  // 5) ポスト（左の歩道）
  Bs([[0, 0, 0, 0x555555], [0, 1, 0, D.has("mail_blue") ? 0x2f6fd8 : 0xd83a3a], [0, 1.6, 0, D.has("mail_blue") ? 0x2f6fd8 : 0xd83a3a]], 0.6, [-4.5, 0.3, DZ.mail_blue]);
  ANCH.mail_blue = [-4.5, 1.2, DZ.mail_blue];
  // 道ばたで手をふるずんだもん（1人）
  const wv = blockChar(); wv.scale.setScalar(1.2); wv.position.set(-5.2, 1.0, zAt(0.68)); wv.rotation.y = Math.PI / 2; sc.add(wv);
  // 風船（balloon：空の高いところ。車について来る）
  const bal = D.has("balloon") ? B([[0, 0, 0, 0xff4a7a], [0, -0.9, 0, 0xeeeeee]], 0.8) : null;
  // 雲
  const clouds = []; for (let k = 0; k < 9; k++) { const cl = []; for (let a = 0; a < 4; a++) for (let b = 0; b < 2; b++) cl.push([a * 1.4, b * 0.8, 0, 0xffffff]);
    const m = blocks(cl, 1.6, new THREE.MeshBasicMaterial()); m.position.set((rr() * 2 - 1) * 50, 18 + rr() * 8, -20 - k * (L + 100) / 9); sc.add(m); clouds.push(m); }
  // ずんだもんの車
  const mkCar = (col) => { const g = new THREE.Group(), cb = [];
    for (let a = -1; a <= 1; a++) for (let b = -2; b <= 2; b++) cb.push([a, 0, b, col]);
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 0; b++) cb.push([a, 1, b, (b === -1 || Math.abs(a) === 1) ? 0x9fd8ff : col]);
    [[-1.2, -1.4], [1.2, -1.4], [-1.2, 1.4], [1.2, 1.4]].forEach(([a, b]) => cb.push([a, -0.5, b, 0x222222]));
    cb.push([-0.7, 0, -2.6, 0xfff2a0], [0.7, 0, -2.6, 0xfff2a0]);
    const m = blocks(cb.map(([x, y, z, c]) => [x * 0.62, y * 0.62, z * 0.62, c]), 0.62); m.position.y = 0.72; g.add(m); sc.add(g); return g; };
  const car = mkCar(0x5aa830);
  const hood = new THREE.Group(); sc.add(hood);   // 運転席から見えるボンネットとハンドル（カット1だけ）
  { const hb = []; for (let a = -2; a <= 2; a++) for (let b = 0; b <= 2; b++) hb.push([a, 0, -b, 0x5aa830]);
    const hm = blocks(hb.map(([x, y, z, c]) => [x * 0.42, y * 0.42, z * 0.42, c]), 0.42); hood.add(hm);
  }
  const drv = blockChar(); drv.scale.setScalar(0.62); drv.position.set(0, 1.25, 0.1); drv.rotation.y = Math.PI; car.add(drv);
  // 対向車（2台。car_red は2台目が赤）
  const onc = [0xf2f2f2, D.has("car_red") ? 0xd83a3a : 0xf2c230].map(c => { const g = mkCar(c); g.rotation.y = Math.PI; return g; });
  ANCH.car_red = [1.6, 1.2, 0]; ANCH.balloon = [0, 14, 0];
  return (t) => {
    const tc = Math.min(t, HOLD), stopE = 1.2;
    const dist = tc < HOLD - stopE ? V * tc : V * (HOLD - stopE) + V * stopE * (1 - Math.pow(1 - (tc - HOLD + stopE) / stopE, 2)) / 2;   // 最後の1.2秒でとまる
    const cz = -dist, f = tc / HOLD, bob = 0.03 * Math.sin(t * 13) * (t < HOLD ? 1 : 0);
    car.position.set(LANE, bob, cz);
    drv.userData.ears && drv.userData.ears.forEach((e, i) => { e.rotation.z = (i ? -1 : 1) * 0.15 * Math.sin(t * 6); });
    // 対向車：f=0.15 と f=0.72 ごろにすれちがう
    [[0.15, 0], [0.72, 1]].forEach(([fp, i]) => { const meet = HOLD * fp, z = -V * meet + (t - meet) * V; onc[i].position.set(-LANE, 0, z); if (i === 1) ANCH.car_red = [-LANE, 1.2, z]; });
    blades.rotation.z = (D.has("mill_reverse") ? -1 : 1) * t * 1.6;
    cows.forEach((m, i) => { m.rotation.z = 0.06 * Math.sin(t * 2 + i); });
    wv.userData.arms && wv.userData.arms[1] && (wv.userData.arms[1].rotation.z = 2.4 + 0.5 * Math.sin(t * 8));
    wv.position.y = 1.0 + Math.abs(Math.sin(t * 4)) * 0.15;
    if (bal) { bal.position.set(-6, 13 + 0.5 * Math.sin(t * 1.3), cz - 22); ANCH.balloon = [-6, bal.position.y, cz - 22]; }
    // カメラ（3カット）
    const k = f < 0.34 ? 0 : (f < 0.67 ? 1 : 2);
    car.visible = k !== 0; hood.visible = k === 0; hood.position.set(LANE, 0.78 + bob, cz - 1.9);
    if (k === 0) { C.position.set(LANE, 1.75 + bob, cz + 0.2); C.lookAt(LANE + 0.3, 1.6, cz - 30); }
    else if (k === 1) { C.position.set(LANE + 6.5, 2.4, cz - 1.5); C.lookAt(LANE - 3, 1.6, cz - 1.0); }
    else { C.position.set(LANE + 1.0, 3.0, cz - 8); C.lookAt(LANE, 1.3, cz + 3); }
  };
}

const SCENES = { drive: driveScene, town_full: townFull, hakoniwa: hakoniwa, hakoniwa_eki: hakoniwaEki, stage_sea: stageSea, crowd_plaza: crowdPlaza, mini_city: miniCity, seafloor: seafloor, antarctica: antarctica, city: cityScene, icefly: icefly, seaice: seaice, orbit: orbitScene, gravity: gravityScene, surface: surfaceScene, tide: tideScene, land: landScene, flight: flightScene, rewind: rewindScene, spin: spinScene, axis: axisScene, space: spaceScene };

window.setup = (j) => {
  job = j; seed = 12345;
  if (!R) {
    R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    document.body.appendChild(R.domElement);
  }
  R.setPixelRatio(1); R.setSize(j.w, j.h);
  C = new THREE.PerspectiveCamera(j.fov || 55, j.w / j.h, 0.1, 5000);
  EMODE = (j.p || {}).earth || "";
  upd = SCENES[j.scene](j.p || {});
  S = CUR;
  return true;
};
function viewOver(t) {                                   // p.view / p.view_to：どの場面でもカメラを上書き
  const p = job.p || {}; if (!p.view) return;
  const [a, la] = p.view, [b, lb] = p.view_to || p.view, e = sstep(job.d ? t / job.d : 0);
  C.position.set(lerp(a[0], b[0], e), lerp(a[1], b[1], e), lerp(a[2], b[2], e));
  C.up.set(0, 1, 0); C.lookAt(lerp(la[0], lb[0], e), lerp(la[1], lb[1], e), lerp(la[2], lb[2], e));
}
const _dir = new THREE.Vector3();
function pushCam(t) {                                    // p.push：0秒から一定の速さで前へ寄る（距離の割合/秒）。p.push_end：最後の時刻で寄りゼロ（ループの終わりを冒頭の絵に合わせる）
  const p = job.p || {}; if (!p.push) return;
  C.getWorldDirection(_dir);
  C.position.addScaledVector(_dir, p.push * C.position.length() * (p.push_end ? t - (job.d || 0) : t));
}
window.frame = (t) => { upd(t, job.d); viewOver(t); pushCam(t); R.render(S, C); return true; };
window.probe = (t, names) => {                          // 違いの場所を画面の座標（0〜1）で返す（答え合わせの丸の位置）
  upd(t, job.d); viewOver(t); C.updateMatrixWorld();
  const v = new THREE.Vector3();
  return names.map(n => { const a = ANCH[n]; if (!a) return null; v.set(...a).project(C); return [(v.x + 1) / 2, (1 - v.y) / 2]; });
};
window.ready = true;
