// bigface/cg/bf.js — 『ビッグフェイスの〇〇』の3DCG（セルルック・ローポリゴン）
// render.js が Chromium で開き、window.setup(job) → window.frame(t) を1コマずつ呼んで書き出す。
// job.scene: "ep01_test"（Phase 1 のテスト：パン屋のドアに顔がつっかえる）
// 仕様の元：bigface/SPEC.txt（統合マスター仕様書）。色・比率・動きの初期値はそこから
import * as THREE from "./node_modules/three/build/three.module.js";

const PAL = { face: 0xF3E8D4, cloth: 0x7C9D91, town: 0xD8C7B2, accent: 0xD98C74, ink: 0x343B3A };
let R, S, C, job, upd = () => {};

// ---- セルルックの材質（2〜3段）と輪郭線
const grad = (() => { const d = new Uint8Array([175, 225, 255]); const t = new THREE.DataTexture(d, 3, 1, THREE.RedFormat); t.minFilter = t.magFilter = THREE.NearestFilter; t.needsUpdate = true; return t; })();
const toon = (color, extra = {}) => new THREE.MeshToonMaterial(Object.assign({ color, gradientMap: grad }, extra));
const INK = new THREE.MeshBasicMaterial({ color: PAL.ink, side: THREE.BackSide });
function mesh(geo, mat, parent, pos = [0, 0, 0], opt = {}) {
  const m = new THREE.Mesh(geo, mat); m.position.set(...pos);
  if (opt.scale) m.scale.set(...opt.scale);
  if (opt.rot) m.rotation.set(...opt.rot);
  m.castShadow = opt.cast !== false; m.receiveShadow = opt.recv !== false;
  if (opt.line) { const o = new THREE.Mesh(geo, INK); o.scale.setScalar(1 + opt.line); o.castShadow = false; o.receiveShadow = false; m.add(o); }
  parent.add(m); return m;
}
// ほんの少しの色ムラ（木・漆喰・石の質感。弱いノイズ）
function grain(base, w = 256, h = 256, amt = 10, lines = null) {
  const cv = document.createElement("canvas"); cv.width = w; cv.height = h; const g = cv.getContext("2d");
  const c = new THREE.Color(base); g.fillStyle = "#" + c.getHexString(); g.fillRect(0, 0, w, h);
  let s = 7; const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < w * h / 12; i++) { const v = (r() - 0.5) * amt; g.fillStyle = `rgba(${v > 0 ? 255 : 0},${v > 0 ? 250 : 0},${v > 0 ? 240 : 0},${Math.abs(v) / 255})`; g.fillRect(r() * w, r() * h, 2 + r() * 3, 1 + r() * 2); }
  if (lines) lines(g, w, h, r);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
}
const ease = x => { x = Math.min(Math.max(x, 0), 1); return x * x * (3 - 2 * x); };
const eo = x => { x = Math.min(Math.max(x, 0), 1); return 1 - Math.pow(1 - x, 3); };
const ei = x => { x = Math.min(Math.max(x, 0), 1); return x * x * x; };
const lerp = (a, b, u) => a + (b - a) * u;
const seg = (t, a, b) => (t - a) / (b - a);

// ---- ビッグフェイス（顔＝全高の約68%）
function bigFace(parent) {
  const root = new THREE.Group(); parent.add(root);
  const body = new THREE.Group(); root.add(body);
  const cloth = toon(PAL.cloth), skin = toon(PAL.face), dark = new THREE.MeshBasicMaterial({ color: PAL.ink });
  mesh(new THREE.SphereGeometry(1, 20, 14), cloth, body, [0, 0.66, 0], { scale: [0.40, 0.34, 0.34], line: 0.06 });
  const legs = [-1, 1].map(s => { const g = new THREE.Group(); g.position.set(s * 0.15, 0.40, 0); body.add(g);
    mesh(new THREE.CapsuleGeometry(0.085, 0.16, 4, 10), skin, g, [0, -0.16, 0], { line: 0.12 });
    mesh(new THREE.SphereGeometry(0.11, 12, 8), toon(0x8a6a58), g, [0, -0.30, 0.04], { scale: [1, 0.6, 1.35], line: 0.1 }); return g; });
  const arms = [-1, 1].map(s => { const g = new THREE.Group(); g.position.set(s * 0.36, 0.78, 0); body.add(g);
    mesh(new THREE.CapsuleGeometry(0.07, 0.14, 4, 10), skin, g, [s * 0.03, -0.13, 0], { rot: [0, 0, s * 0.25], line: 0.12 }); return g; });
  const neck = new THREE.Group(); neck.position.set(0, 0.92, 0); body.add(neck);
  const head = new THREE.Group(); head.position.set(0, 1.0, 0); neck.add(head);
  const skull = mesh(new THREE.SphereGeometry(1, 40, 28), skin, head, [0, 0, 0], { scale: [1.12, 1.0, 1.0], line: 0.018 });
  const face = new THREE.Group(); head.add(face);
  const surf = (x, y) => Math.sqrt(Math.max(0.02, 1 - (x / 1.12) ** 2 - y * y));
  const eyes = [-1, 1].map(s => mesh(new THREE.SphereGeometry(0.062, 14, 10), dark, face, [0, 0, 0], { scale: [1, 1.15, 0.45], cast: false }));
  const mouth = mesh(new THREE.CapsuleGeometry(0.016, 0.15, 3, 8), dark, face, [0, 0, 0], { rot: [0, 0, Math.PI / 2], cast: false });
  const st = { look: [0, 0], blink: 0, mouth: 0, sq: 0 };
  function setFace() {
    eyes.forEach((e, i) => { const x = (i ? 1 : -1) * 0.30 + st.look[0] * 0.10, y = 0.06 + st.look[1] * 0.07; e.position.set(x, y, surf(x, y) - 0.005); e.lookAt(x * 3, y * 3, 3); e.scale.y = 1.15 * (1 - 0.88 * st.blink); });
    const my = -0.26 + st.look[1] * 0.02; mouth.position.set(st.look[0] * 0.04, my, surf(0, my) - 0.004); mouth.scale.y = 1 - 0.35 * st.mouth;
    // 当たったときの顔の伸び縮み（前後に縮み、横に広がる）
    skull.scale.set(1.12 * (1 + 0.5 * st.sq), 1.0 * (1 + 0.3 * st.sq), 1.0 * (1 - st.sq));
    face.scale.set(1 + 0.5 * st.sq, 1 + 0.3 * st.sq, 1 - st.sq);
  }
  return { root, body, neck, head, legs, arms, st, setFace };
}

// ---- 町：パン屋の正面（扉は顔より狭い）と両どなり
function bakery(sc) {
  const wallT = grain(0xEADBC4, 256, 256, 14), woodT = grain(0xA9805E, 256, 256, 22, (g, w, h, r) => { g.strokeStyle = "rgba(60,40,20,0.12)"; for (let i = 0; i < 14; i++) { g.beginPath(); const y = r() * h; g.moveTo(0, y); g.bezierCurveTo(w / 3, y + 6, w * 2 / 3, y - 6, w, y + 2); g.stroke(); } });
  const stoneT = grain(0xCFC1AE, 512, 512, 12, (g, w, h, r) => { g.strokeStyle = "rgba(90,70,50,0.16)"; g.lineWidth = 3; for (let y = 0; y < h; y += 64) for (let x = (y / 64) % 2 * 48; x < w; x += 96) { g.beginPath(); g.roundRect(x + 4, y + 4, 88, 56, 14); g.stroke(); } });
  stoneT.repeat.set(10, 10);
  const wall = toon(0xffffff, { map: wallT }), wood = toon(0xffffff, { map: woodT });
  mesh(new THREE.PlaneGeometry(60, 60), toon(0xffffff, { map: stoneT }), sc, [0, 0, 10], { rot: [-Math.PI / 2, 0, 0], cast: false });
  const DW = 0.7, DH = 2.55, T = 0.28;            // 扉の半幅・高さ・壁の厚み
  const B = (w, h, d, x, y, z, m, o = {}) => mesh(new THREE.BoxGeometry(w, h, d), m, sc, [x, y, z], o);
  B(4.5 - DW, 4.6, T, -(DW + (4.5 - DW) / 2), 2.3, -T / 2, wall);
  B(4.5 - DW, 4.6, T, (DW + (4.5 - DW) / 2), 2.3, -T / 2, wall);
  B(2 * DW, 4.6 - DH, T, 0, DH + (4.6 - DH) / 2, -T / 2, wall);
  // 扉の枠（木）と、内側へ開いた扉
  B(0.14, DH + 0.14, T + 0.08, -DW - 0.07, DH / 2, -T / 2, wood, { line: 0.02 });
  B(0.14, DH + 0.14, T + 0.08, DW + 0.07, DH / 2, -T / 2, wood, { line: 0.02 });
  B(2 * DW + 0.28, 0.16, T + 0.1, 0, DH + 0.07, -T / 2, wood, { line: 0.02 });
  const door = new THREE.Group(); door.position.set(-DW, 0, -T); sc.add(door);
  mesh(new THREE.BoxGeometry(2 * DW - 0.04, DH - 0.04, 0.07), wood, door, [DW, DH / 2, -0.04], { line: 0.015 }); door.rotation.y = Math.PI - 0.12;   // 扉は内側の壁にぴったり開いておく（中からの絵で顔にかからない）
  // 屋根の縁と日よけ（縞）
  B(9.4, 0.3, 0.7, 0, 4.75, 0.1, toon(0x9a6a54), { line: 0.01 });
  const awnT = (() => { const cv = document.createElement("canvas"); cv.width = 256; cv.height = 16; const g = cv.getContext("2d"); for (let i = 0; i < 8; i++) { g.fillStyle = i % 2 ? "#F3E8D4" : "#D98C74"; g.fillRect(i * 32, 0, 32, 16); } const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; return t; })();
  const awn = mesh(new THREE.BoxGeometry(2.6, 0.06, 1.0), toon(0xffffff, { map: awnT }), sc, [2.45, 2.85, 0.42], { rot: [0.42, 0, 0], line: 0.01 });
  // 窓とパン
  B(2.2, 0.12, 0.36, 2.45, 0.92, 0.06, wood, { line: 0.02 }); B(2.2, 0.12, 0.36, 2.45, 2.38, 0.06, wood, { line: 0.02 });
  B(0.12, 1.58, 0.36, 1.41, 1.65, 0.06, wood, { line: 0.02 }); B(0.12, 1.58, 0.36, 3.49, 1.65, 0.06, wood, { line: 0.02 });
  mesh(new THREE.PlaneGeometry(1.96, 1.34), toon(0xF4E2B8), sc, [2.45, 1.65, -0.02], { cast: false });
  [[1.85, 1.2, 0xD9A066], [2.35, 1.18, 0xC98A52], [2.9, 1.2, 0xE0B077], [2.1, 1.75, 0xD9A066], [2.75, 1.78, 0xC98A52]].forEach(([x, y, c]) => mesh(new THREE.SphereGeometry(0.22, 14, 10), toon(c), sc, [x, y, 0.0], { scale: [1.3, 0.7, 0.6], line: 0.05 }));
  // 看板（文字なし：小さなパンの形）
  const sign = B(1.1, 0.5, 0.08, 0, 3.15, 0.04, wood, { line: 0.03 });
  mesh(new THREE.SphereGeometry(0.16, 14, 10), toon(0xD9A066), sc, [0, 3.15, 0.1], { scale: [1.4, 0.75, 0.5] });
  // 植木鉢（左）
  mesh(new THREE.CylinderGeometry(0.26, 0.2, 0.42, 14), toon(0xC9785E), sc, [-1.4, 0.21, 0.35], { line: 0.04 });
  mesh(new THREE.SphereGeometry(0.32, 12, 8), toon(0x7FA07A), sc, [-1.4, 0.62, 0.35], { scale: [1, 0.85, 1], line: 0.04 });
  // 両どなりの家
  [[-7.3, 0xE3CFC0, 0x8FA5B8, 5.4], [7.2, 0xDDE2CF, 0xB98A72, 4.8]].forEach(([x, c, rc, h]) => {
    B(5.2, h, 2, x, h / 2, -1.2, toon(0xffffff, { map: grain(c) }));
    B(5.6, 0.35, 2.4, x, h + 0.1, -1.1, toon(rc), { line: 0.01 });
    [[-1.2, 1.6], [1.2, 1.6], [-1.2, 3.4], [1.2, 3.4]].forEach(([dx, y]) => { if (y < h - 0.6) { B(0.9, 1.0, 0.1, x + dx, y, -0.15, toon(0x9DB3B8), { line: 0.03 }); } });
  });
  // パン屋の中（第2カット：中から見る）
  const inT = grain(0xE9D6B8);
  B(9, 0.1, 6, 0, 0.0, -3.2, toon(0xffffff, { map: woodT }), { cast: false });
  B(0.2, 4.6, 6, -4.4, 2.3, -3.2, toon(0xffffff, { map: inT })); B(0.2, 4.6, 6, 4.4, 2.3, -3.2, toon(0xffffff, { map: inT }));
  B(9, 0.2, 6, 0, 3.6, -3.2, toon(0xD8C0A0)); B(9, 4.6, 0.2, 0, 2.3, -6.2, toon(0xffffff, { map: inT }));
  // 中の棚とパン（手前でぼけない程度に）
  B(1.6, 1.0, 0.7, -2.6, 0.5, -1.2, wood, { line: 0.02 });
  [[-3.0, 0xD9A066], [-2.6, 0xC98A52], [-2.2, 0xE0B077]].forEach(([x, c]) => mesh(new THREE.SphereGeometry(0.18, 12, 8), toon(c), sc, [x, 1.1, -1.2], { scale: [1.3, 0.7, 0.8], line: 0.05 }));
  B(1.6, 1.0, 0.7, 2.6, 0.5, -1.2, wood, { line: 0.02 });
  [[2.2, 0xC98A52], [2.6, 0xD9A066], [3.0, 0xC98A52]].forEach(([x, c]) => mesh(new THREE.SphereGeometry(0.18, 12, 8), toon(c), sc, [x, 1.1, -1.2], { scale: [1.3, 0.7, 0.8], line: 0.05 }));
  return { DW, DH };
}

// ---- 動き：歩く・止まる・見る・当たる（頭は体より遅れてついてくる）
function ep01Test(p) {
  const sc = S = new THREE.Scene();
  sc.background = new THREE.Color(0xE6EEE8);
  sc.fog = new THREE.Fog(0xE6EEE8, 18, 40);
  const hemi = new THREE.HemisphereLight(0xFFF6EA, 0xD8C7B2, 1.15); sc.add(hemi);
  const sun = new THREE.DirectionalLight(0xFFF0DC, 1.6); sun.position.set(6, 10, 8); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 6; sun.shadow.bias = -0.0008; sun.shadow.normalBias = 0.05;
  Object.assign(sun.shadow.camera, { left: -8, right: 8, top: 8, bottom: -4, near: 1, far: 30 }); sc.add(sun);
  const inside = new THREE.PointLight(0xFFD9A8, 0, 9, 1.5); inside.position.set(0, 2.8, -2.5); sc.add(inside);
  const { DW } = bakery(sc);
  const bf = bigFace(sc);
  // 道のり：左手前から扉の前へ（2.4秒）→ 止まる → 扉を見上げる → 一歩ふみこむ → 当たる
  const P0 = [-3.3, 1.8], P1 = [-0.02, 1.8], ZHIT = 0.80;
  const T = { walk1: 2.4, turn: 2.75, look: 3.05, up: 3.55, wind: 3.75, hit: 4.05, cut: 4.6, blink: 5.5, l1: 6.0, l2: 6.45, l3: 6.95, are: 7.15, end: 8.6 };
  const head = { x: 0, v: 0, r: 0, rv: 0 }; let lastT = -1, prevV = 0, phase = 0;
  const pathAt = t => {
    if (t <= T.walk1) { const u = ease(t / T.walk1 * 0.85 + 0.15) ; const k = Math.min(1, t / T.walk1); const uu = k < 0.15 ? k * k / 0.3 : (k > 0.85 ? 1 - (1 - k) * (1 - k) / 0.3 : k - 0.075); const n = uu / 0.925; return [lerp(P0[0], P1[0], n), lerp(P0[1], P1[1], n), Math.atan2(P1[0] - P0[0], P1[1] - P0[1]), 1]; }
    const h0 = Math.atan2(P1[0] - P0[0], P1[1] - P0[1]);
    if (t <= T.wind) { const u = ease(seg(t, T.walk1 + 0.15, T.turn + 0.15)); return [P1[0], P1[1], lerp(h0, Math.PI, u), 0]; }
    // ためて、ふみこむ（等速にしない：最初ゆっくり→最後に加速）
    const u = ei(seg(t, T.wind, T.hit)); return [P1[0], lerp(P1[1], ZHIT, u), Math.PI, u < 1 && t < T.hit ? 1 : 0];
  };
  return (t) => {
    // 頭の遅れ（ばねとダンパー）。体の加速度で頭の傾きの目標が決まる
    const dt = 1 / 60;
    if (lastT < 0) lastT = t;
    while (lastT < t - 1e-6) {
      const a = pathAt(lastT), b = pathAt(lastT + dt);
      const v = Math.hypot(b[0] - a[0], b[1] - a[1]) / dt, acc = (v - prevV) / dt; prevV = v;
      const w = 2 * Math.PI * 2.4, z = 0.32;
      const tgt = THREE.MathUtils.clamp(-acc * 0.018, -0.16, 0.16) + (lastT > T.hit ? 0 : 0);
      head.v += (-w * w * (head.x - tgt) - 2 * z * w * head.v) * dt; head.x += head.v * dt;
      if (a[3]) phase += dt * 2.3 * 2 * Math.PI * Math.min(1, v / 1.2 + 0.25);
      lastT += dt;
    }
    const [x, z, hd, walking] = pathAt(t);
    bf.root.position.set(x, 0, z); bf.root.rotation.y = hd;
    // 小刻みな歩き：脚を振る、体が上下にはねる（足が着くたびに少し沈む）
    const sw = walking ? Math.sin(phase) : 0, bob = walking ? Math.abs(Math.cos(phase)) : 1;
    bf.legs[0].rotation.x = 0.55 * sw; bf.legs[1].rotation.x = -0.55 * sw;
    bf.arms[0].rotation.x = -0.4 * sw; bf.arms[1].rotation.x = 0.4 * sw;
    bf.body.position.y = walking ? 0.035 * bob : 0;
    // 頭：前後の遅れ（head.x）＋見上げる・首をかしげる
    let pitch = head.x, roll = 0;
    const st = bf.st; st.look = [0, 0]; st.blink = 0; st.mouth = 0; st.sq = 0;
    if (t > T.turn && t < T.up + 0.5) { const u = ease(seg(t, T.look, T.look + 0.18)) * (1 - ease(seg(t, T.up, T.up + 0.3))); st.look = [0, 1.0 * u]; pitch -= 0.20 * ease(seg(t, T.look + 0.12, T.look + 0.42)) * (1 - ease(seg(t, T.up, T.up + 0.25))); }
    if (t > T.up && t < T.hit) { pitch -= 0.10 * ease(seg(t, T.up, T.wind)) * (1 - ease(seg(t, T.wind, T.wind + 0.12))); }   // ため：少し後ろへ
    // 当たる：顔が縮み、体は0.06秒遅れて止まる。首がわずかに押し戻される
    if (t >= T.hit) {
      const k = t - T.hit; st.sq = 0.055 * Math.exp(-k * 9) * Math.cos(k * 28) + (k < 0.04 ? 0.055 * k / 0.04 : 0);
      st.sq = Math.max(-0.02, st.sq);
      bf.body.position.z = -0.06 * Math.max(0, 1 - k / 0.12) * (k < 0.06 ? k / 0.06 : 1);
      pitch += 0.05 * Math.exp(-k * 6) * Math.sin(k * 20);
    } else bf.body.position.z = 0;
    // 第2カット（中から）：止まったまま → まばたき → 目だけ左右 → 首をかしげる
    if (t > T.cut) {
      if (t > T.blink && t < T.blink + 0.14) st.blink = Math.sin(seg(t, T.blink, T.blink + 0.14) * Math.PI);
      const lx = ease(seg(t, T.l1, T.l1 + 0.12)) * -1 + ease(seg(t, T.l2, T.l2 + 0.14)) * 2 - ease(seg(t, T.l3, T.l3 + 0.12));
      st.look = [lx, 0];
      if (t > T.are) { roll = 0.07 * ease(seg(t, T.are + 0.15, T.are + 0.6)); st.mouth = ease(seg(t, T.are, T.are + 0.2)); }
      if (t > T.are + 1.0 && t < T.are + 1.14) st.blink = Math.sin(seg(t, T.are + 1.0, T.are + 1.14) * Math.PI);
    }
    bf.neck.rotation.x = pitch; bf.neck.rotation.z = roll;
    bf.setFace();
    // カメラ：第1カットは固定の斜め（MS〜WS）、第2カットは店の中から固定
    if (t < T.cut) { C.fov = 42; C.position.set(0.9, 1.8, 10.2); C.lookAt(-0.5, 2.15, 0.6); inside.intensity = 0; hemi.intensity = 1.15; }
    else { C.fov = 34; C.position.set(0.0, 1.55, -4.6); C.lookAt(0, 1.95, 0.4); inside.intensity = 6; hemi.intensity = 0.9; }
    C.updateProjectionMatrix();
  };
}

const SCENES = { ep01_test: ep01Test };
window.setup = (j) => {
  job = j;
  if (!R) {
    R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    R.shadowMap.enabled = true; R.shadowMap.type = THREE.PCFSoftShadowMap;
    R.outputColorSpace = THREE.SRGBColorSpace; R.toneMapping = THREE.NoToneMapping;
    document.body.appendChild(R.domElement);
  }
  R.setPixelRatio(1); R.setSize(j.w, j.h);
  C = new THREE.PerspectiveCamera(40, j.w / j.h, 0.1, 200);
  upd = SCENES[j.scene](j.p || {});
  return true;
};
window.frame = (t) => { upd(t); R.render(S, C); return true; };
window.probe = () => [];
window.ready = true;
