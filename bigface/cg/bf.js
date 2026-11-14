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

// 看板：木の板に文字（世界の中の文字だけ使う。11/10 ゲンタさん「パン屋とかの文字は使っていい看板とかに」）
function signTex(txt, w, h, bg = "#A9805E", fg = "#F3E8D4", size = 0.62) {
  const cv = document.createElement("canvas"); cv.width = w; cv.height = h; const g = cv.getContext("2d");
  g.fillStyle = bg; g.fillRect(0, 0, w, h);
  g.strokeStyle = "rgba(60,40,20,0.18)"; g.lineWidth = 3; for (let i = 1; i < 4; i++) { g.beginPath(); g.moveTo(0, h * i / 4); g.lineTo(w, h * i / 4 + 4); g.stroke(); }
  g.fillStyle = fg; g.font = `${Math.round(h * size)}px ZenMaru`; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(txt, w / 2, h * 0.54);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
// ---- ビッグフェイス（顔＝全高の約68%）
function bigFace(parent) {
  const root = new THREE.Group(); parent.add(root);
  const body = new THREE.Group(); root.add(body);
  const cloth = toon(0xffffff, { map: grain(PAL.cloth, 128, 128, 3) }), skin = toon(PAL.face), dark = new THREE.MeshBasicMaterial({ color: PAL.ink });
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
  const smile = mesh(new THREE.TorusGeometry(0.085, 0.016, 6, 16, Math.PI * 0.8), dark, face, [0, 0, 0], { rot: [0, 0, Math.PI * 1.1], cast: false }); smile.visible = false;
  const st = { look: [0, 0], blink: 0, mouth: 0, sq: 0, happy: 0 };
  function setFace() {
    eyes.forEach((e, i) => { const x = (i ? 1 : -1) * 0.30 + st.look[0] * 0.10, y = 0.06 + st.look[1] * 0.07; e.position.set(x, y, surf(x, y) - 0.005); e.lookAt(x * 3, y * 3, 3); e.scale.y = 1.15 * (1 - 0.88 * st.blink); });
    const my = -0.26 + st.look[1] * 0.02; mouth.position.set(st.look[0] * 0.04, my, surf(0, my) - 0.004); mouth.scale.y = 1 - 0.35 * st.mouth;
    // うれしい：目が少し細くなり、口が小さく笑う（変化は小さく）
    smile.visible = st.happy > 0.5; mouth.visible = !smile.visible; smile.position.set(st.look[0] * 0.04, my + 0.035, surf(0, my) - 0.004); smile.rotation.set(-0.12, 0, Math.PI * 1.1);
    if (st.happy > 0) eyes.forEach(e => { e.scale.y *= 1 - 0.45 * st.happy; e.position.y += 0.015 * st.happy; });
    if (st.wink) eyes.forEach((e, i) => { e.scale.y *= 1 - 0.8 * (st.wink[i] || 0); });   // 片目だけ細める（雨つぶが当たる側。EP.02）
    // 当たったときの顔の伸び縮み（前後に縮み、横に広がる）
    const depth = 1 - THREE.MathUtils.clamp(st.sq, -0.03, 0.06), lateral = 1 / Math.sqrt(depth);   // 体積を保つ（Codex 案）
    skull.scale.set(1.12 * lateral, lateral, depth); face.scale.set(lateral, lateral, depth);
  }
  return { root, body, neck, head, legs, arms, st, setFace };
}

// ---- 町：パン屋の正面（扉は顔より狭い）と両どなり
function bakery(sc) {
  const wallT = grain(0xEADBC4, 256, 256, 14), woodT = grain(0xA9805E, 256, 256, 22, (g, w, h, r) => { g.strokeStyle = "rgba(60,40,20,0.12)"; for (let i = 0; i < 14; i++) { g.beginPath(); const y = r() * h; g.moveTo(0, y); g.bezierCurveTo(w / 3, y + 6, w * 2 / 3, y - 6, w, y + 2); g.stroke(); } });
  const stoneT = grain(0xCFC1AE, 512, 512, 12, (g, w, h, r) => { g.strokeStyle = "rgba(90,70,50,0.16)"; g.lineWidth = 3; for (let y = 0; y < h; y += 64) for (let x = (y / 64) % 2 * 48; x < w; x += 96) { g.beginPath(); g.roundRect(x + 4, y + 4, 88, 56, 14); g.stroke(); } });
  stoneT.repeat.set(20, 10);
  const wall = toon(0xffffff, { map: wallT }), wood = toon(0xffffff, { map: woodT });
  mesh(new THREE.PlaneGeometry(120, 60), toon(0xffffff, { map: stoneT }), sc, [20, 0, 10], { rot: [-Math.PI / 2, 0, 0], cast: false });
  const DW = 0.7, DH = 2.55, T = 0.28;            // 扉の半幅・高さ・壁の厚み
  const B = (w, h, d, x, y, z, m, o = {}) => mesh(new THREE.BoxGeometry(w, h, d), m, sc, [x, y, z], o);
  B(4.5 - DW, 4.6, T, -(DW + (4.5 - DW) / 2), 2.3, -T / 2, wall);
  // 右の壁（窓 x 1.41〜3.49, y 0.92〜2.38 をあける）
  B(1.41 - DW, 4.6, T, (DW + 1.41) / 2, 2.3, -T / 2, wall); B(4.5 - 3.49, 4.6, T, (3.49 + 4.5) / 2, 2.3, -T / 2, wall);
  B(2.08, 0.92, T, 2.45, 0.46, -T / 2, wall); B(2.08, 4.6 - 2.38, T, 2.45, 2.38 + (4.6 - 2.38) / 2, -T / 2, wall);
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
  // 窓（ガラスごしに中が見える。左右の窓は外へ開く）とパン
  B(2.2, 0.12, 0.36, 2.45, 0.92, 0.06, wood, { line: 0.02 }); B(2.2, 0.12, 0.36, 2.45, 2.38, 0.06, wood, { line: 0.02 });
  B(0.12, 1.58, 0.36, 1.41, 1.65, 0.06, wood, { line: 0.02 }); B(0.12, 1.58, 0.36, 3.49, 1.65, 0.06, wood, { line: 0.02 });
  const glass = new THREE.MeshToonMaterial({ color: 0xDDEEEE, gradientMap: grad, transparent: true, opacity: 0.28 });
  const sash = (hx, dir) => { const g = new THREE.Group(); g.position.set(hx, 1.65, 0.2); sc.add(g);
    const w = 0.96; mesh(new THREE.BoxGeometry(w, 1.34, 0.03), glass, g, [dir * w / 2, 0, 0], { cast: false });
    [[-0.67, 0], [0.67, 0]].forEach(([y]) => mesh(new THREE.BoxGeometry(w, 0.06, 0.06), wood, g, [dir * w / 2, y, 0], { line: 0.03 }));
    [0, w].forEach(x => mesh(new THREE.BoxGeometry(0.06, 1.34, 0.06), wood, g, [dir * x, 0, 0], { line: 0.03 })); return g; };
  const winL = sash(1.47, 1), winR = sash(3.43, -1);
  // 中の窓ぎわの台（パンは置かない。パンは奥の棚から持ってくる。11/10 ゲンタさん「わざわざ奥から持ってくるみたいな感じがいい」）
  B(2.2, 0.9, 0.6, 2.45, 0.45, -0.6, wood, { line: 0.02 });
  // 奥の棚とパン
  B(2.0, 1.3, 0.6, 2.45, 0.65, -4.4, wood, { line: 0.02 }); B(2.0, 0.08, 0.6, 2.45, 1.0, -4.4, wood);
  [[1.8, 1.42, 0xD9A066], [2.3, 1.42, 0xC98A52], [2.8, 1.42, 0xE0B077], [3.2, 1.42, 0xD9A066], [2.0, 1.1, 0xC98A52], [2.6, 1.1, 0xE0B077]].forEach(([x, y, c]) => mesh(new THREE.SphereGeometry(0.18, 12, 8), toon(c), sc, [x, y, -4.35], { scale: [1.3, 0.7, 0.8], line: 0.05 }));
  // 看板（文字なし：小さなパンの形）
  const sign = B(1.5, 0.62, 0.08, 0, 3.2, 0.04, wood, { line: 0.03 });
  mesh(new THREE.PlaneGeometry(1.42, 0.54), new THREE.MeshBasicMaterial({ map: signTex("パン", 512, 196) }), sc, [0, 3.2, 0.085], { cast: false });
  mesh(new THREE.SphereGeometry(0.13, 14, 10), toon(0xD9A066), sc, [0.95, 3.2, 0.12], { scale: [1.4, 0.75, 0.5], line: 0.05 });
  // 植木鉢（左）
  mesh(new THREE.CylinderGeometry(0.26, 0.2, 0.42, 14), toon(0xC9785E), sc, [-1.4, 0.21, 0.35], { line: 0.04 });
  mesh(new THREE.SphereGeometry(0.32, 12, 8), toon(0x7FA07A), sc, [-1.4, 0.62, 0.35], { scale: [1, 0.85, 1], line: 0.04 });
  // 両どなりの家
  const nbR = new THREE.Group(); sc.add(nbR);
  [[-7.3, 0xE3CFC0, 0x8FA5B8, 5.4], [7.2, 0xDDE2CF, 0xB98A72, 4.8]].forEach(([x, c, rc, h]) => {
    const B0 = B; const BB = (...a) => { const m = B0(...a); if (x > 0) { sc.remove(m); nbR.add(m); } return m; };
    BB(5.2, h, 2, x, h / 2, -1.2, toon(0xffffff, { map: grain(c) }));
    BB(5.6, 0.35, 2.4, x, h + 0.1, -1.1, toon(rc), { line: 0.01 });
    [[-1.2, 1.6], [1.2, 1.6], [-1.2, 3.4], [1.2, 3.4]].forEach(([dx, y]) => { if (y < h - 0.6) { BB(0.9, 1.0, 0.1, x + dx, y, -0.15, toon(0x9DB3B8), { line: 0.03 }); } });
  });
  // パン屋の中（第2カット：中から見る）
  const inT = grain(0xE9D6B8);
  B(9, 0.1, 6, 0, 0.0, -3.2, toon(0xffffff, { map: woodT }), { cast: false });
  B(0.2, 4.6, 6, -4.4, 2.3, -3.2, toon(0xffffff, { map: inT })); const inR = B(0.2, 4.6, 6, 4.4, 2.3, -3.2, toon(0xffffff, { map: inT }));
  B(9, 0.2, 6, 0, 3.6, -3.2, toon(0xD8C0A0)); B(9, 4.6, 0.2, 0, 2.3, -6.2, toon(0xffffff, { map: inT }));
  // 中の棚とパン（手前でぼけない程度に）
  B(1.6, 1.0, 0.7, -2.6, 0.5, -1.2, wood, { line: 0.02 });
  [[-3.0, 0xD9A066], [-2.6, 0xC98A52], [-2.2, 0xE0B077]].forEach(([x, c]) => mesh(new THREE.SphereGeometry(0.18, 12, 8), toon(c), sc, [x, 1.1, -1.2], { scale: [1.3, 0.7, 0.8], line: 0.05 }));
  return { DW, DH, winL, winR, nbR, inR, wood, woodT, awn };
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

// ---- ほかの人（ふつうの頭の大きさ。ビッグフェイスとの対比）
function person(parent, o) {
  const root = new THREE.Group(); parent.add(root);
  const body = new THREE.Group(); root.add(body);
  const H = o.h || 1.6, skin = toon(o.skin || 0xF0DCC4), dark = new THREE.MeshBasicMaterial({ color: PAL.ink });
  const legs = [-1, 1].map(s => { const g = new THREE.Group(); g.position.set(s * 0.09 * H, 0.42 * H, 0); body.add(g);
    mesh(new THREE.CapsuleGeometry(0.05 * H, 0.26 * H, 4, 8), toon(o.pants || 0x6B6E73), g, [0, -0.19 * H, 0], { line: 0.1 });
    mesh(new THREE.SphereGeometry(0.06 * H, 10, 8), toon(0x6a5040), g, [0, -0.38 * H, 0.03 * H], { scale: [1, 0.6, 1.4], line: 0.1 }); return g; });
  mesh(new THREE.CapsuleGeometry(0.16 * H, 0.22 * H, 4, 12), toon(o.coat), body, [0, 0.6 * H, 0], { scale: [1, 1, 0.8], line: 0.05 });
  if (o.apron) mesh(new THREE.BoxGeometry(0.26 * H, 0.3 * H, 0.02), toon(0xF6F1E6), body, [0, 0.55 * H, 0.14 * H], { line: 0.05 });
  const arms = [-1, 1].map(s => { const g = new THREE.Group(); g.position.set(s * 0.19 * H, 0.75 * H, 0); body.add(g);
    mesh(new THREE.CapsuleGeometry(0.04 * H, 0.2 * H, 4, 8), toon(o.coat), g, [0, -0.13 * H, 0], { line: 0.12 }); return g; });
  const neck = new THREE.Group(); neck.position.set(0, 0.86 * H, 0); body.add(neck);
  const hr = o.headR || 0.13 * H;
  mesh(new THREE.SphereGeometry(hr, 20, 14), skin, neck, [0, hr * 0.95, 0], { line: 0.04 });
  if (o.hair) mesh(new THREE.SphereGeometry(hr * 1.04, 16, 10, 0, Math.PI * 2, 0, Math.PI * 0.5), toon(o.hair), neck, [0, hr * 1.0, -hr * 0.05], { line: 0.03 });
  if (o.hat === "toque") { mesh(new THREE.CylinderGeometry(hr * 0.8, hr * 0.8, hr * 0.5, 14), toon(0xFAF7F0), neck, [0, hr * 2.0, 0], { line: 0.04 }); mesh(new THREE.SphereGeometry(hr * 0.95, 14, 10), toon(0xFAF7F0), neck, [0, hr * 2.45, 0], { scale: [1, 0.6, 1], line: 0.04 }); }
  if (o.hat === "brim") { mesh(new THREE.CylinderGeometry(hr * 1.5, hr * 1.5, hr * 0.08, 18), toon(o.hatC || 0x7A6A5A), neck, [0, hr * 1.75, 0], { line: 0.04 }); mesh(new THREE.CylinderGeometry(hr * 0.85, hr * 0.9, hr * 0.6, 14), toon(o.hatC || 0x7A6A5A), neck, [0, hr * 2.05, 0], { line: 0.04 }); }
  const eyes = [-1, 1].map(s => mesh(new THREE.SphereGeometry(hr * 0.09, 8, 6), dark, neck, [s * hr * 0.33, hr * 1.02, hr * 0.92], { scale: [1, 1.2, 0.5], cast: false }));
  const st = { blink: 0 };
  return { root, body, neck, legs, arms, eyes, st, H };
}
function walkPose(c, phase, on, amp = 0.5) {
  const weight = Number(on), sw = weight * Math.sin(phase);   // on は 0〜1 の重み（止まるとき徐々に戻る。Codex 案）
  c.legs[0].rotation.x = amp * sw; c.legs[1].rotation.x = -amp * sw;
  c.arms[0].rotation.x = -0.6 * amp * sw; c.arms[1].rotation.x = 0.6 * amp * sw;
  c.body.position.y = weight * 0.025 * (1 - Math.cos(2 * phase)) * 0.5;
}
function bread(parent, pos, sc = 1) {
  const g = new THREE.Group(); g.position.set(...pos); parent.add(g);
  mesh(new THREE.SphereGeometry(0.2 * sc, 16, 10), toon(0xD9A066), g, [0, 0, 0], { scale: [1.35, 0.72, 0.9], line: 0.05 });
  [-0.08, 0.06].forEach(x => mesh(new THREE.BoxGeometry(0.03 * sc, 0.02 * sc, 0.2 * sc), toon(0xF3E1C0), g, [x * sc, 0.135 * sc, 0], { rot: [0, 0.5, 0], cast: false }));
  return g;
}
// ---- 裏の路地（パン屋の裏口。段ボールが積んである）
function backAlley(sc, X) {
  const brT = grain(0xD9C3A8, 256, 256, 12, (g, w, h) => { g.strokeStyle = "rgba(110,80,60,0.16)"; g.lineWidth = 2; for (let y = 0; y < h; y += 22) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); for (let x = (y / 22) % 2 * 24; x < w; x += 48) { g.beginPath(); g.moveTo(x, y); g.lineTo(x, y + 22); g.stroke(); } } });
  brT.repeat.set(3, 2);
  const brick = toon(0xffffff, { map: brT }), wood = toon(0xffffff, { map: grain(0x9A7656) });
  const B = (w, h, d, x, y, z, m, o = {}) => mesh(new THREE.BoxGeometry(w, h, d), m, sc, [X + x, y, z], o);
  B(4, 4.2, 0.3, -2.7, 2.1, -0.15, brick); B(4, 4.2, 0.3, 2.7, 2.1, -0.15, brick); B(1.4, 4.2 - 2.55, 0.3, 0, 2.55 + (4.2 - 2.55) / 2, -0.15, brick);
  B(1.4, 2.55, 0.1, 0, 1.275, -0.3, toon(0x6F5A48));
  B(0.12, 2.65, 0.4, -0.76, 1.32, -0.1, wood, { line: 0.02 }); B(0.12, 2.65, 0.4, 0.76, 1.32, -0.1, wood, { line: 0.02 }); B(1.64, 0.12, 0.42, 0, 2.62, -0.1, wood, { line: 0.02 });
  mesh(new THREE.BoxGeometry(1.3, 0.42, 0.06), wood, sc, [X, 3.75, 0.04], { line: 0.03 });   // 段ボールより上に（11/11 ゲンタさん「うらぐちの文字がダンボールで完全に隠れてる」）
  mesh(new THREE.PlaneGeometry(1.22, 0.35), new THREE.MeshBasicMaterial({ map: signTex("うらぐち", 512, 148, "#9A7656") }), sc, [X, 3.75, 0.075], { cast: false });
  const boxT = grain(0xC8A27A, 128, 128, 18, (g, w, h) => { g.fillStyle = "rgba(170,130,90,0.5)"; g.fillRect(w * 0.42, 0, w * 0.16, h); });
  const box = toon(0xffffff, { map: boxT });
  [[-0.45, 0.4, 0.55, 0.8], [0.42, 0.4, 0.6, 0.8], [-0.4, 1.2, 0.6, 0.8], [0.38, 1.22, 0.65, 0.75], [-0.05, 1.98, 0.7, 0.72], [0.35, 2.65, 0.6, 0.62], [-0.38, 2.68, 0.62, 0.6]].forEach(([x, y, z, s], i) =>
    B(s, s, s, x, y, z, box, { rot: [0, (i % 3 - 1) * 0.08, 0], line: 0.02 }));
  mesh(new THREE.CylinderGeometry(0.32, 0.28, 0.8, 14), toon(0x8C9C94), sc, [X + 2.2, 0.4, 0.5], { line: 0.04 });
  mesh(new THREE.CylinderGeometry(0.06, 0.06, 4.2, 8), toon(0x8A8A86), sc, [X - 1.6, 2.1, 0.05], { line: 0.1 });
  return {};
}

// ==== EP.01『ビッグフェイスのせまいドア』（約43秒）
// ショット（秒）：s1 つっかえる / s2 中から / s3 横にして / s4 斜めにして・行列 / s5 行列を見る・裏口を教わる / s6 裏口に段ボール / s7 帰ろうとする・窓が開く / s8 窓でパンを受けとる / s9 窓の内と外で食べる（左右対称）
export const EP01 = await fetch("ep01_time.json").then(r => r.json());
export const EP02 = await fetch("ep02_time.json").then(r => r.json());
export const EP03 = await fetch("ep03_time.json").then(r => r.json());
export const EP04 = await fetch("ep04_time.json").then(r => r.json());
function ep01(p) {
  const sc = S = new THREE.Scene();
  sc.background = new THREE.Color(0xE6EEE8); sc.fog = new THREE.Fog(0xE6EEE8, 20, 46);
  const hemi = new THREE.HemisphereLight(0xFFF6EA, 0xD8C7B2, 1.15); sc.add(hemi);
  const sun = new THREE.DirectionalLight(0xFFF0DC, 1.6); sun.position.set(6, 10, 8); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 6; sun.shadow.bias = -0.0008; sun.shadow.normalBias = 0.05;
  Object.assign(sun.shadow.camera, { left: -7, right: 7, top: 7, bottom: -5, near: 1, far: 30 }); sc.add(sun); sc.add(sun.target);
  // 接地のうす影（足もとだけ。Codex 案）
  const ccv = document.createElement("canvas"); ccv.width = ccv.height = 128; const cctx = ccv.getContext("2d");
  const cgr = cctx.createRadialGradient(64, 64, 8, 64, 64, 64); cgr.addColorStop(0, "rgba(52,59,58,0.22)"); cgr.addColorStop(1, "rgba(52,59,58,0)"); cctx.fillStyle = cgr; cctx.fillRect(0, 0, 128, 128);
  const ctex = new THREE.CanvasTexture(ccv); ctex.colorSpace = THREE.SRGBColorSpace;
  const contact = mesh(new THREE.PlaneGeometry(1.1, 0.75), new THREE.MeshBasicMaterial({ map: ctex, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 }), sc, [0, 0.012, 0], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false });
  const inside = new THREE.PointLight(0xFFD9A8, 0, 9, 1.5); inside.position.set(0, 2.8, -2.5); sc.add(inside);
  const BK = bakery(sc); const AX = 40; backAlley(sc, AX);
  const bf = bigFace(sc);
  const kid = person(sc, { h: 1.05, coat: 0xD98C74, pants: 0x7C6A5C, apron: true, hat: "toque", hair: 0x6A4A36, headR: 0.17 });
  const folk = [person(sc, { h: 1.75, coat: 0x8FA5B8, pants: 0x55606A, hair: 0x3A3A3A }), person(sc, { h: 1.6, coat: 0xC7A0B4, pants: 0x6A5A60, hair: 0x7A5A3A }), person(sc, { h: 1.5, coat: 0xB9B08A, pants: 0x5A5A50, hat: "brim", hatC: 0x6F7F78 })];
  // アイキャッチの舞台（無地。11/10 ゲンタさん「アイキャッチのようなタイトルを最後に。ザ・ビッグフェイス」）
  const EX = -60, EYEC = 0xF1E4CC;
  mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: EYEC }), sc, [EX, 0.001, 0], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false });
  mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: EYEC }), sc, [EX, 10, -4], { cast: false, recv: false });
  const blob = mesh(new THREE.CircleGeometry(0.75, 32), new THREE.MeshBasicMaterial({ color: 0xC9B79C, transparent: true, opacity: 0.6 }), sc, [EX, 0.01, 0], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false });
  const bf2 = bigFace(sc); bf2.root.position.set(EX, 0, 0);
  const stool = mesh(new THREE.CylinderGeometry(0.25, 0.22, 0.85, 14), BK.wood, sc, [2.45, 0.43, -1.2], { line: 0.03 });
  const fore = [0, 1].map(() => { const g = new THREE.Group(); bf.body.add(g); mesh(new THREE.CapsuleGeometry(0.065, 0.14, 4, 10), toon(PAL.face), g, [0, -0.13, 0], { line: 0.12 });
    const hand = mesh(new THREE.SphereGeometry(0.095, 12, 10), toon(PAL.face), bf.body, [0, 0, 0], { line: 0.1 }); g.visible = false; hand.visible = false; return { g, hand }; });
  const bfBread = bread(sc, [0, -5, 0]), kidBread = bread(sc, [2.45, 1.02, -0.6]), kidBread2 = bread(sc, [0, -5, 0], 0.9);
  const E = EP01;
  // --- ビッグフェイスの道のり（区間ごと。x,z,向き,歩いているか）
  const H_DOOR = Math.PI, ZHIT = 0.8;
  function bfPath(t) {
    if (t < E.s3) { const u = ei(seg(t, 0.22, E.hit1)); return [0, lerp(1.7, ZHIT, u), H_DOOR, t > 0.22 && t < E.hit1]; }
    if (t < E.s4) { // 引いて → 横にして → もう一度
      const back = eo(seg(t, E.s3 + 0.15, E.s3 + 0.7)), fwd = ei(seg(t, E.hit2 - 0.4, E.hit2));
      return [0, lerp(lerp(ZHIT, 1.65, back), ZHIT, fwd), H_DOOR, (t > E.s3 + 0.15 && t < E.s3 + 0.7) || (t > E.hit2 - 0.4 && t < E.hit2)]; }
    if (t < E.s5) {
      const back = eo(seg(t, E.s4 + 0.05, E.s4 + 0.6)), fwd = ei(seg(t, E.hit3 - 0.4, E.hit3)), back2 = eo(seg(t, E.hit3 + 0.7, E.hit3 + 1.3));
      return [0, lerp(lerp(lerp(ZHIT, 1.65, back), ZHIT, fwd), 1.7, back2), H_DOOR, (t > E.s4 + 0.05 && t < E.s4 + 0.6) || (t > E.hit3 - 0.4 && t < E.hit3) || (t > E.hit3 + 0.7 && t < E.hit3 + 1.3)]; }
    if (t < E.s6) { // 行列のほうを見る → 並んでいる人が裏を指さす → その先を見る → 向き直っておじぎ → ゆっくり裏へ（11/11 ゲンタさん「並んでる人の親切で裏口まで回った風に」「ゆっくり目のカット。情感があるように」）
      const P = E.point, a = ease(seg(t, E.s5 + 0.35, E.s5 + 1.1)), b = ease(seg(t, P + 1.0, P + 1.6)), c = ease(seg(t, P + 2.0, P + 2.5)), d = ease(seg(t, P + 3.5, P + 4.2));
      const w = ease(seg(t, P + 3.9, P + 6.6)), m = 1 - w;   // 行列の前を、手前（カメラのほう）へゆっくり回りこむ。画面の右へ向かう（次の裏口のカットで左から入ってくる向きとつながる）
      const px = 2 * w * m * 0.1 + w * w * 3.2, pz = m * m * 1.7 + 2 * w * m * 4.4 + w * w * 5.2;
      return [px, pz, H_DOOR - 2.2 * a + 0.8 * b - 0.8 * c - 0.9 * d, t > P + 3.9]; }
    if (t < E.s7) { // 裏口へ歩く（左から）
      const u = ease(seg(t, E.s6 + 0.1, E.s6 + 2.3));
      const turn = ease(seg(t, E.s6 + 2.3, E.s6 + 2.7));
      return [AX + lerp(-2.4, 1.35, u), 2.1, lerp(Math.PI / 2, H_DOOR + 0.45, turn) - (H_DOOR + 0.15) * ease(seg(t, E.sokka + 0.3, E.sokka + 1.3)), t > E.s6 + 0.1 && t < E.s6 + 2.3]; }   // 「そっか」のあと、ゆっくりふり返る
    if (t < E.s8) { // 店の前を右から左へ、ゆっくり帰る → 窓が開いて止まり、ふり返る
      const stopT = E.kid_say2 + 0.35;
      const u = seg(t, E.s7 + 0.2, stopT), x = lerp(5.6, 0.6, Math.min(1, Math.max(0, u)) - 0.02 * Math.max(0, Math.min(1, u)) * 0);
      const turn = ease(seg(t, stopT + 0.35, stopT + 0.9));
      return [u < 1 ? lerp(5.6, 0.6, Math.max(0, u)) : 0.6, 2.2, lerp(-Math.PI / 2, -Math.PI * 0.15 + 0.0, turn) , t > E.s7 + 0.2 && t < stopT]; }
    if (t < E.s9) { // 窓の前へ戻る
      const u = ease(seg(t, E.s8 + 0.2, E.s8 + 1.9)), turn = ease(seg(t, E.s8 + 1.6, E.s8 + 2.2));
      return [lerp(0.6, 1.95, u), lerp(2.2, 1.2, u), lerp(Math.PI * 0.75, H_DOOR, turn), t > E.s8 + 0.2 && t < E.s8 + 1.9]; }
    if (t >= E.s10) return [1.95, 1.2, H_DOOR, false];   // 最後の顔のアップは窓（子どもの目線）へ正面
    return [1.95, 1.35, H_DOOR - 1.1, false];   // 窓の前：カメラ側へ少し向ける（目が見えるように）
  }
  // かじる動き：0.5秒かけて口元へ → 0.3秒とめる → 0.5秒でもどす（0〜1）
  const biteU = t => Math.max(...[E.bite1, E.bite2].map(tb => ease(seg(t, tb, tb + 0.5)) * (1 - ease(seg(t, tb + 0.8, tb + 1.3)))));
  const kidPos = t => { // 子ども：扉の内側に出てくる → 窓の中（台の上の椅子）
    if (t < E.s6) return [0, -30, 0, 0];   // 裏口を教えるのは行列の人（子どもは出さない）
    if (t >= E.s8 && t < E.s9) {   // 椅子から降りて奥の棚へ → パンを1つ取って戻る → 椅子に上がる（ゆっくり。11/10 ゲンタさん「すごい素早いタイミングで動いてる箇所があるのでやめて」）
      const k = t - E.s8;
      if (k < 0.75) return [2.45, lerp(-1.2, -1.6, ease(seg(k, 0.3, 0.75))), Math.PI * ease(seg(k, 0.2, 0.75)), false];
      if (k < 2.55) return [2.45, lerp(-1.6, -3.85, ease(seg(k, 0.75, 2.55))), Math.PI, true];
      if (k < 3.15) return [2.45, -3.85, Math.PI, false];
      if (k < 4.95) return [2.45, lerp(-3.85, -1.6, ease(seg(k, 3.15, 4.95))), lerp(Math.PI, 0, ease(seg(k, 3.15, 3.6))), true];
      return [2.45, lerp(-1.6, -1.2, ease(seg(k, 4.95, 5.4))), 0, false];
    }
    return [2.45, -1.2, t >= E.s9 ? 1.0 : 0, false];
  };
  const kidY = t => { if (t <= E.s6) return 0; if (t < E.s8 || t >= E.s9) return 0.86; const k = t - E.s8;   // 椅子の上（0.86）／床
    const hop = (a, b, y0, y1) => lerp(y0, y1, ease(seg(k, a, b))) + 0.1 * Math.sin(Math.PI * Math.min(1, Math.max(0, seg(k, a, b))));
    if (k < 0.75) return hop(0.3, 0.75, 0.86, 0); if (k < 4.95) return 0; return hop(4.95, 5.4, 0, 0.86); };
  const head = { x: 0, v: 0 }; let lastT = -1, prevV = 0, phase = 0, gaitW = 0, kphase = 0, fphase = [0, 0, 0];
  const folkSpot = [[1.3, 2.7], [2.2, 3.7], [2.9, 4.6]];
  return (t) => {
    const dt = 1 / 120;   // 固定刻みで0秒から進める（途中の時刻から描いても同じ状態。Codex 案）
    if (lastT < 0 || t < lastT - 1e-6) { lastT = 0; prevV = 0; head.x = head.v = 0; phase = kphase = gaitW = 0; fphase = [0, 0, 0]; }
    while (lastT + dt <= t + 1e-6) {
      const a = bfPath(lastT), b = bfPath(lastT + dt);
      const v = (Math.abs(b[0] - a[0]) > 5 ? 0 : Math.hypot(b[0] - a[0], b[1] - a[1])) / dt, acc = Math.abs(b[0] - a[0]) > 5 ? 0 : (v - prevV) / dt; prevV = v;
      const reloc = Math.abs(b[0] - a[0]) > 5; if (reloc) { head.x = head.v = 0; prevV = 0; }
      const w = 2 * Math.PI * 2.0, z = 0.58, tgt = THREE.MathUtils.clamp(-acc * 0.02, -0.17, 0.17);   // 止まったあとの揺れを早く収める（2.0Hz・減衰0.58、Codex 案）
      if (!reloc) head.v += (-w * w * (head.x - tgt) - 2 * z * w * head.v) * dt; head.x += head.v * dt;
      gaitW += ((a[3] && !reloc ? 1 : 0) - gaitW) * (1 - Math.exp(-dt / 0.065));
      if (a[3] && !reloc) phase += v * dt / 0.36 * Math.PI;   // 足の運びを移動距離に合わせる（一歩0.36）
      kphase += dt * 2 * Math.PI * 2.6; fphase = fphase.map((f, i) => f + dt * 2 * Math.PI * (1.9 + i * 0.15));
      lastT += dt;
    }
    const [x, z, hd, walking] = bfPath(t);
    bf.root.position.set(x, 0, z); bf.root.rotation.y = hd;
    walkPose(bf, phase, gaitW, t > E.s7 && t < E.s8 ? 0.35 : 0.55);
    let pitch = head.x, roll = 0; const st = bf.st; st.look = [0, 0]; st.blink = 0; st.mouth = 0; st.sq = 0; st.happy = 0;
    const bump = (th) => { if (t < th || t > th + 0.6) return; const k = t - th; st.sq = 0.06 * (1 - Math.exp(-k * 70)) * Math.exp(-k * 8) * Math.sin(k * 24 + 0.5); pitch += 0.05 * Math.exp(-k * 6) * Math.sin(k * 20); };   // ゼロからなめらかに縮む（Codex 案）
    bump(E.hit1); bump(E.hit2); bump(E.hit3);
    const blink = (tb) => { if (t > tb && t < tb + 0.14) st.blink = Math.sin(seg(t, tb, tb + 0.14) * Math.PI); };
    // s2：中から。止まって、まばたき、目だけ左右、「……あれ？」で首をかしげる
    if (t > E.s2 && t < E.s3) { blink(E.s2 + 0.8); const lx = -ease(seg(t, E.s2 + 1.2, E.s2 + 1.32)) + 2 * ease(seg(t, E.s2 + 1.6, E.s2 + 1.74)) - ease(seg(t, E.s2 + 2.0, E.s2 + 2.12)); st.look = [lx, 0];
      if (t > E.are) { roll = 0.07 * ease(seg(t, E.are + 0.1, E.are + 0.5)); st.mouth = ease(seg(t, E.are, E.are + 0.2)); } }
    // s3：顔を横にする（首ごと90度）→ 当たる → 戻す
    if (t > E.s3 && t < E.s4) { roll = (Math.PI / 2) * ease(seg(t, E.s3 + 0.75, E.s3 + 1.25)) * (1 - ease(seg(t, E.hit2 + 0.7, E.hit2 + 1.2))); blink(E.hit2 + 0.5); }
    // s4：斜め（45度）→ 当たる → 引く
    if (t > E.s4 && t < E.s5) { roll = -(Math.PI / 4) * ease(seg(t, E.s4 + 0.6, E.s4 + 1.0)) * (1 - ease(seg(t, E.hit3 + 0.8, E.hit3 + 1.3))); blink(E.hit3 + 0.45); }
    // s5：行列に気づく（目→頭→体の順）→ 少しうつむく（はずかしい）→ 子どもの声で顔を上げる
    if (t > E.s5 && t < E.s6) { const P = E.point;   // 目が先に行列へ → うつむく → 指さしで顔を上げる → 指の先を目で追う → おじぎ
      const q = ease(seg(t, E.s5 + 0.15, E.s5 + 0.35)) * (1 - ease(seg(t, E.s5 + 1.0, E.s5 + 1.25))), f = ease(seg(t, P + 1.2, P + 1.5)) * (1 - ease(seg(t, P + 1.9, P + 2.2)));
      st.look = [q - 0.8 * f, 0];
      pitch += 0.16 * ease(seg(t, E.s5 + 1.1, E.s5 + 1.6)) * (1 - ease(seg(t, P + 0.3, P + 0.9)));
      pitch += 0.2 * Math.sin(Math.PI * Math.min(1, Math.max(0, seg(t, P + 2.7, P + 3.5))));
      st.happy = Math.max(st.happy || 0, 0.6 * ease(seg(t, P + 2.4, P + 2.9)));
      blink(E.s5 + 1.9); blink(P + 0.95); blink(P + 3.7); }
    // s6：段ボールを見上げる →「……そっか。」
    if (t > E.s6 && t < E.s7) { const up = ease(seg(t, E.s6 + 2.8, E.s6 + 3.2)) * (1 - ease(seg(t, E.sokka - 0.3, E.sokka + 0.2))); st.look = [0, up]; pitch -= 0.22 * up; blink(E.s6 + 3.5);
      if (t > E.sokka) { pitch += 0.12 * ease(seg(t, E.sokka, E.sokka + 0.8)); st.mouth = 0.6; }
      if (t > E.sokka + 1.8) { const d = ease(seg(t, E.sokka + 1.8, E.sokka + 2.4)); st.look = [0, -0.7 * d]; pitch += 0.06 * d; bf.body.scale.setScalar(1 - 0.03 * d); blink(E.sokka + 1.55); blink(E.sokka + 2.9); } }   // ふり返って、目をふせる（しょんぼり）
    // s7：うつむいて歩く（SAD）→ 窓が開く音で止まる → 見る
    if (t > E.s7 && t < E.s8) { pitch += 0.2 * (1 - ease(seg(t, E.kid_say2 + 0.4, E.kid_say2 + 0.9))); bf.body.scale.setScalar(1 - 0.03 * (1 - ease(seg(t, E.kid_say2 + 0.4, E.kid_say2 + 0.9)))); st.look = [-0.6 * ease(seg(t, E.kid_say2 + 0.3, E.kid_say2 + 0.45)), 0]; blink(E.kid_say2 + 1.4); }
    else bf.body.scale.setScalar(1);
    // s8：パンを受けとる（腕を上げる）→ うれしい（頭が少し上がり、体が小さくはねる）
    let armUp = 0;
    if (t > E.s8 + 2.4 && t < E.give - 0.6) blink(E.s8 + 3.6);   // 待つあいだは動かない（まばたきだけ）
    if (t > E.give + 0.9 && t < E.s9) st.happy = ease(seg(t, E.give + 0.9, E.give + 1.3));   // 受けとって、少し笑う
    if (t > E.s8 && t < E.s9) { armUp = ease(seg(t, E.give - 0.7, E.give)); }
    // s9：食べる（大きな頭がこくんと下がる）→ 最後のひとこと
    if (t >= E.s9) { armUp = t >= E.s10 ? 0.45 : 1; pitch += 0.1 * biteU(t); if (t < E.s10) [E.bite1, E.bite2].forEach(tb => { const c = seg(t, tb + 0.95, tb + 1.75); if (c > 0 && c < 1) st.mouth = 0.5 + 0.5 * Math.sin(c * Math.PI * 4); });   // 食べる：手がのびてパンが口元まで来る → もぐもぐ（11/11 ゲンタさん「手が伸びて口元までパンがくる感じに」） blink(E.s9 + 0.6); blink(E.final + 1.6);
      if (t > E.s10) { blink(E.s10 + 0.7); const h = ease(seg(t, E.smile, E.smile + 0.35)); st.happy = h; pitch -= 0.05 * h; if (t > E.smile + 1.4) blink(E.smile + 1.6); } }   // 最後は顔：ほんの少し笑う（11/10 ゲンタさん「最後はビッグフェイスの表情で終わりたい」）
    bf.arms.forEach((a, i) => { a.rotation.x = -1.9 * armUp + a.rotation.x * (1 - armUp); a.rotation.z = (i ? -1 : 1) * 0.35 * armUp; a.scale.set(1, 1, 1); });
    const bu = biteU(t), HOLD = new THREE.Vector3(0, 0.98, 0.5), MOUTH = new THREE.Vector3(0, 1.6, 1.2), breadL = HOLD.clone().lerp(MOUTH, bu);
    // 腕は「肩 → ひじ → 手」の2本。ひじを顔の前下に出して、顔にめりこまないようにする。手はパンの両わきをにぎる（11/11 ゲンタさん「顔に埋め込まれないようにして腕が」「最後もちゃんとパンを握ってるように」）
    const holding = t >= E.s9 && t < E.eye;
    fore.forEach((f, i) => { f.g.visible = holding; f.hand.visible = holding; });
    if (holding) bf.arms.forEach((a, i) => {
      const sx = i ? 1 : -1, sh = new THREE.Vector3(sx * 0.36, 0.78, 0);
      const el = new THREE.Vector3(sx * 0.44, 0.8, 0.3).lerp(new THREE.Vector3(sx * 0.52, 0.86, 1.12), bu);
      const hd = breadL.clone().add(new THREE.Vector3(sx * 0.2, -0.02, 0));
      const aim = (g, from, to) => { const d = to.clone().sub(from), len = d.length(); g.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), d.normalize()); g.scale.set(1, Math.max(0.6, len / 0.27), 1); };
      aim(a, sh, el); fore[i].g.position.copy(el); aim(fore[i].g, el, hd); fore[i].hand.position.copy(hd); });
    bf.neck.rotation.x = pitch; bf.neck.rotation.z = (t > E.s3 && t < E.s5) ? 0 : roll; bf.head.rotation.z = (t > E.s3 && t < E.s5) ? roll : 0; bf.setFace();
    // --- 子ども
    const [kx, kz, kh, kw] = kidPos(t); kid.root.position.set(kx, 0, kz); kid.root.rotation.y = kh; walkPose(kid, kphase, kw, 0.6);
    kid.root.position.y = kidY(t);            // 窓の中では椅子の上（パンを取りに行くあいだは床）
    stool.visible = t > E.s6;
    kid.arms[1].rotation.x = 0; kid.arms[0].rotation.x = 0; kid.arms[1].rotation.z = 0; kid.neck.rotation.set(0, 0, 0);
    if (t > E.kid_say2 && t < E.s8 + 0.1) { const u = ease(seg(t, E.kid_say2, E.kid_say2 + 0.5)) * (1 - ease(seg(t, E.s8 - 0.6, E.s8 + 0.1))); kid.arms[0].rotation.x = -1.3 * u; }   // 手を一度あげるだけ（ふらない）   // 言葉なし：窓から手招き（11/10 ゲンタさん「言葉なし」）
    if (t > E.s7 && t < E.s9) { kid.neck.rotation.x = 0.1; const k = t - E.s8;
      const reach = Math.sin(Math.PI * Math.min(1, Math.max(0, seg(k, 2.55, 3.15))));   // 棚に手をのばす
      const carry = ease(seg(k, 2.95, 3.25)) * (1 - ease(seg(k, 5.4, 5.6)));          // 右手にパン（左手は空）
      const hand = ease(seg(k, 5.5, 6.1)) * (1 - ease(seg(k, 6.7, 7.3)));             // 窓から差し出す（ゆっくり）
      kid.arms[0].rotation.x = -1.4 * reach; kid.arms[1].rotation.x = Math.min(-1.4 * reach, -0.7 * carry, -1.35 * hand); kid.neck.rotation.x = 0.1 - 0.3 * reach; }
    if (t >= E.s9) { [E.bite1 + 0.3, E.bite2 + 0.3].forEach(tb => { const k = seg(t, tb, tb + 0.9); if (k > 0 && k < 1) kid.neck.rotation.z = 0.12 * Math.sin(k * Math.PI); }); }   // 子どもは食べない。食べるのを見て、首を少しかしげる（11/10 ゲンタさん「店の人もパン食べてるのは意味がわからない」）
    kidBread2.position.set(0, -20, 0); kidBread.visible = false;
    // パン：子どもの右手 → ゆっくり手渡し → ビッグフェイスの手。かじるたびに小さく
    const bites = (t > E.bite1 + 0.7 ? 1 : 0) + (t > E.bite2 + 0.7 ? 1 : 0);
    kid.root.updateMatrixWorld(true); bf.root.updateMatrixWorld(true);
    const khand = new THREE.Vector3(0, -0.26 * kid.H, 0.08); kid.arms[1].localToWorld(khand);
    const bh = (t >= E.s9 ? breadL.clone() : new THREE.Vector3(0, 0.98, 0.42)); bf.root.localToWorld(bh);
    if (t > E.s8 + 3.0 && t < E.give - 0.25) bfBread.position.copy(khand);
    else if (t >= E.give - 0.25 && t < E.give + 0.35) bfBread.position.copy(khand.lerp(bh, ease(seg(t, E.give - 0.25, E.give + 0.35))));
    else if (t >= E.give + 0.35) { bfBread.position.copy(bh); bfBread.rotation.y = bf.root.rotation.y; bfBread.scale.setScalar(1 - 0.22 * bites); }
    else bfBread.position.set(0, -5, 0);
    // --- 窓が開く（外へ）
    const wo = eo(seg(t, E.win, E.win + 0.5)) * (t > E.s7 ? 1 : 0); BK.winL.rotation.y = -1.45 * wo; BK.winR.rotation.y = 1.45 * wo;
    // --- 行列（s4 で右から来て並び、s5 で待つ。ひとりは足先をとんとん）
    folk.forEach((f, i) => {
      const [sx, sz] = folkSpot[i];
      if (t < E.s4 || t >= E.s6) { f.root.position.set(0, -10, 0); return; }
      const u = ease(seg(t, E.s4 + 0.3 + i * 0.5, E.s4 + 2.3 + i * 0.5)); const x0 = 8 + i * 1.2;
      f.root.position.set(lerp(x0, sx, u), 0, lerp(2.2, sz, u)); f.root.rotation.y = u < 1 ? -Math.PI / 2 - 0.2 : -Math.PI * 0.82;
      walkPose(f, fphase[i], u > 0 && u < 1, 0.45);
      if (i === 0 && t > E.s5) {   // 先頭の人：ビッグフェイスのほうへ向き直り → 店の横（裏へ回る道）を腕で指して、そちらを見る → 顔を戻して小さくうなずく
        const P = E.point, arm = ease(seg(t, P, P + 0.7)) * (1 - ease(seg(t, P + 2.1, P + 2.7)));
        f.root.rotation.y = lerp(-Math.PI * 0.82, -2.23, ease(seg(t, P - 0.7, P - 0.1)));
        f.arms[0].rotation.z = -2.3 * arm;   // 頭より上へ。後ろの人に隠れない
        f.neck.rotation.y = -0.7 * ease(seg(t, P + 0.2, P + 0.6)) * (1 - ease(seg(t, P + 1.7, P + 2.1)));
        f.neck.rotation.x = 0.15 * Math.sin(Math.PI * Math.min(1, Math.max(0, seg(t, P + 2.9, P + 3.5)))); }
      if (i === 2 && u >= 1) f.legs[1].rotation.x = -0.25 * Math.max(0, Math.sin(t * 9));                                  // とんとん
    });
    // --- アイキャッチ：上から落ちてきて、ぽふっと着地（顔がつぶれて戻る）→ うれしい顔で少しかしげる
    if (t >= E.eye) {
      const k = t - E.eye, fall = Math.min(1, k / 0.32), y = 3.2 * (1 - fall * fall);
      bf2.root.position.y = y; const land = k - 0.32;
      bf2.st.look = [0, 0]; bf2.st.blink = 0; bf2.st.mouth = 0; bf2.st.happy = 1; bf2.st.sq = 0;
      let p2 = 0, r2 = 0;
      if (land > 0) { bf2.st.sq = Math.max(-0.03, 0.08 * Math.exp(-land * 8) * Math.cos(land * 24)); p2 = 0.06 * Math.exp(-land * 5) * Math.sin(land * 16); bf2.body.scale.set(1 + 0.12 * Math.exp(-land * 12), 1 - 0.12 * Math.exp(-land * 12), 1); }
      r2 = 0.09 * ease(seg(k, 1.0, 1.35)); if (k > 1.6 && k < 1.74) bf2.st.blink = Math.sin(seg(k, 1.6, 1.74) * Math.PI);
      bf2.neck.rotation.x = p2; bf2.neck.rotation.z = r2; bf2.setFace(); blob.scale.setScalar(0.6 + 0.4 * fall);
    }
    if (t >= E.s10) { kid.root.position.y = -20; }
    // --- カメラ（1カット1種類の動き。感情の強い場面は固定）
    const lx = t >= E.eye ? EX : (t >= E.s6 && t < E.s7 ? AX : 0); sun.position.set(lx + 6, 10, 8); sun.target.position.set(lx, 0, 0);   // 影の範囲を場所ごとに（Codex 案）
    contact.position.set(x, t >= E.s2 && t < E.s5 ? 0.058 : 0.012, z); contact.visible = t < E.eye;
    BK.nbR.visible = true; BK.inR.visible = true; BK.awn.visible = true; inside.intensity = 0; hemi.intensity = 1.15; sun.visible = true;
    const cam = (pos, look, fov) => { C.fov = fov; C.position.set(...pos); C.lookAt(...look); };
    if (t < E.s2) cam([0.9, 1.8, 10.2], [-0.2, 2.15, 0.6], 42);
    else if (t < E.s3) { cam([0, 1.55, -4.6], [0, 1.95, 0.4], 34); inside.intensity = 6; hemi.intensity = 1.0; sun.visible = false; }
    else if (t < E.s4) { cam([0, 1.55, -4.6], [0, 1.95, 0.4], 34); inside.intensity = 6; hemi.intensity = 1.0; sun.visible = false; }   // 中から：横になった顔がそのまま押しつけられる
    else if (t < E.s5) { cam([0, 1.55, -4.6], [0, 1.95, 0.4], 34); inside.intensity = 6; hemi.intensity = 1.0; sun.visible = false; }   // 3回目も同じ構図（くり返しの笑い）
    else if (t < E.s6) { const k = ease(seg(t, E.s5, E.s6)); cam([1.7 - 0.3 * k, 2.4 - 0.1 * k, 11.0 - 1.4 * k], [0.2, 1.8, 2.0], 46 - 3 * k); }   // ほぼ正面から：ビッグフェイスの顔と、指さす人の腕が同時に見える。1カットでゆっくり寄る（切らない）
    else if (t < E.s7) cam([AX + 1.0, 1.9, 10.0], [AX + 0.25, 1.9, 0.8], 40);   // 斜め前から：段ボールを見上げる顔と「そっか」が見える（11/10 ゲンタさん「もう少し全体的にビッグフェイスの表情を見たい」）
    else if (t < E.s8) cam([2.2, 2.0, 11.5], [2.0, 2.0, 1.2], 42);
    else if (t < E.s9) { cam([3.75, 2.8, -5.95], [2.25, 1.25, -1.6], 50); BK.winL.rotation.y = -2.95; BK.winR.rotation.y = 2.95; BK.awn.visible = false; inside.intensity = 5; hemi.intensity = 1.15; sun.visible = false; }   // 店の奥からの固定1カット：窓にビッグフェイスの顔、手前で子どもがパンを取って戻り、渡す（11/11 ゲンタさん「カット割りがヘンテコ。忙しない。余計なカットとモーション」）
    else if (t >= E.eye) { cam([EX, 1.4, 9.0], [EX, 0.75, 0], 36); hemi.intensity = 1.2; }
    else if (t >= E.s10) { cam([1.95, 1.62, -3.9], [1.95, 1.72, 1.2], 33); BK.winL.rotation.y = -2.95; BK.winR.rotation.y = 2.95; BK.awn.visible = false; inside.intensity = 5; hemi.intensity = 1.15; sun.visible = false; }   // 窓の中（子どもの肩ごし）から顔：冒頭の「扉いっぱいの顔」と対   // 窓枠が額にかからないよう少し引いて低く（Codex 指摘）
    else { cam([16.0, 1.95, 0.25], [2.2, 1.92, 0.15], 32); BK.winL.rotation.y = -2.95; BK.winR.rotation.y = 2.95; BK.awn.visible = false; BK.nbR.visible = false; BK.inR.visible = false; inside.intensity = 4; }   // 左右対称：壁の真横から。開いた窓は壁にぴったり倒し、顔にかからないように（Codex 指摘）
    // 表情に寄る（アングルはそのまま、要所だけ顔のアップを挟む。11/10 ゲンタさん「裏口空いてなくてその時の表情に寄るとか。さっきのアングルにプラスで表情に寄る」）
    const cu = (yaw = 0.35, dist = 2.6, fov = 30, dy = 0.0) => {
      bf.root.updateMatrixWorld(true); const hp = new THREE.Vector3(); bf.head.getWorldPosition(hp);
      const h = bf.root.rotation.y + yaw, d = new THREE.Vector3(Math.sin(h), 0, Math.cos(h));
      C.fov = fov; C.position.set(hp.x + d.x * dist, hp.y + 0.05 + dy, hp.z + d.z * dist); C.lookAt(hp.x, hp.y - 0.05, hp.z);
      sun.visible = true; inside.intensity = 0; hemi.intensity = 1.15; BK.awn.visible = true; };
    if (t > E.sokka + 1.35 && t < E.s7) cu(0.0, 3.5, 50);                // 裏口があかない：ふり返った顔に寄る

    C.updateProjectionMatrix();
  };
}


// ==== EP.02『ビッグフェイスのかさ』：雨の日、パン屋の前の通り。傘が顔に小さすぎる → カエルに差し出す（腕がにゅーっと伸びる）→ カエルは水たまりへ → 傘を閉じて一緒に歩く
// 11/12 ゲンタさん「少々奇妙な（場合によっては怖い）身体構造の方が面白い」：差し出す腕はゴムのように長く伸びる
function frog(parent) {
  const root = new THREE.Group(); parent.add(root);
  const body = new THREE.Group(); root.add(body);
  const g = toon(0x8DB36A), belly = toon(0xD9E3A6), dark = new THREE.MeshBasicMaterial({ color: PAL.ink });
  mesh(new THREE.SphereGeometry(1, 16, 12), g, body, [0, 0.12, 0], { scale: [0.17, 0.12, 0.19], line: 0.06 });
  mesh(new THREE.SphereGeometry(1, 12, 10), belly, body, [0, 0.09, 0.07], { scale: [0.12, 0.07, 0.12], cast: false });
  const eyes = [-1, 1].map(s => { const e = new THREE.Group(); e.position.set(s * 0.085, 0.22, 0.08); body.add(e);
    mesh(new THREE.SphereGeometry(0.055, 12, 10), g, e, [0, 0, 0], { line: 0.08 });
    const pu = mesh(new THREE.SphereGeometry(0.026, 10, 8), dark, e, [0, 0.005, 0.045], { scale: [1, 1.1, 0.5], cast: false }); return pu; });
  const legs = [-1, 1].map(s => mesh(new THREE.SphereGeometry(1, 10, 8), g, body, [s * 0.15, 0.05, -0.08], { scale: [0.07, 0.05, 0.12], line: 0.08 }));
  return { root, body, eyes, legs };
}
function umbrella(parent, color = 0xE2B85C) {
  const g = new THREE.Group(); parent.add(g);
  const cloth = toon(color, { side: THREE.DoubleSide }), stick = toon(0x6A5240);
  const canopy = mesh(new THREE.ConeGeometry(0.85, 0.34, 10, 1, true), cloth, g, [0, 1.0, 0], { line: 0.02 });
  mesh(new THREE.SphereGeometry(0.035, 8, 6), stick, canopy, [0, 0.19, 0], {});
  const shaft = mesh(new THREE.CylinderGeometry(0.022, 0.022, 1.1, 6), stick, g, [0, 0.5, 0], { line: 0.2 });
  const hook = mesh(new THREE.TorusGeometry(0.07, 0.02, 6, 10, Math.PI), stick, g, [0.07, 0.0, 0], { rot: [0, 0, Math.PI], line: 0.15 });
  return { g, canopy, shaft, hook };
}
function ep02(p) {
  const E = EP02;
  const sc = S = new THREE.Scene();
  const SKY = 0xC6CFD2; sc.background = new THREE.Color(SKY); sc.fog = new THREE.Fog(SKY, 12, 38);
  const hemi = new THREE.HemisphereLight(0xF4F2EC, 0xA09888, 1.7); sc.add(hemi);
  const sun = new THREE.DirectionalLight(0xF2F0EA, 0.6); sun.position.set(3, 12, 6); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 8; sun.shadow.bias = -0.0008; sun.shadow.normalBias = 0.05;
  Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -6, near: 1, far: 30 }); sc.add(sun); sc.add(sun.target);
  const BK = bakery(sc);
  // 水たまり（灰青）と波紋
  const PUD = [[2.6, 5.4, 1.0], [-2.6, 6.1, 0.8], [4.6, 3.6, 0.7], [-5.2, 4.2, 0.9], [6.4, 6.4, 0.8]];
  const pudM = toon(0xA3B3BA);
  PUD.forEach(([x, z, r]) => mesh(new THREE.CircleGeometry(r, 28), pudM, sc, [x, 0.012, z], { rot: [-Math.PI / 2, 0, 0], scale: [1, 0.62, 1], cast: false }));
  const ripples = [];
  PUD.forEach(([x, z, r], pi) => { for (let k = 0; k < 4; k++) { const m = new THREE.MeshBasicMaterial({ color: 0xE6EEF1, transparent: true, opacity: 0, depthWrite: false });
    const rg = mesh(new THREE.RingGeometry(0.9, 1.0, 24), m, sc, [0, 0.016, 0], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false });
    const ang = (k * 2.4 + pi) % 6.28, rr = r * 0.55 * ((k * 0.37 + pi * 0.21) % 1);
    ripples.push({ rg, m, x: x + Math.cos(ang) * rr, z: z + Math.sin(ang) * rr * 0.62, ph: (k * 0.29 + pi * 0.17) % 1, big: 0 }); } });
  const splashRings = [0, 1, 2].map(k => { const m = new THREE.MeshBasicMaterial({ color: 0xF2F6F8, transparent: true, opacity: 0, depthWrite: false });
    return { m, rg: mesh(new THREE.RingGeometry(0.85, 1.0, 28), m, sc, [2.6, 0.018, 5.4], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false }) }; });
  const splashDrops = Array.from({ length: 14 }, (_, i) => mesh(new THREE.SphereGeometry(0.035, 6, 5), new THREE.MeshBasicMaterial({ color: 0xEEF4F7 }), sc, [0, -5, 0], { cast: false }));
  // 雨（細い棒をたくさん。時刻だけで位置が決まる）
  const NR = 1500, rain = new THREE.InstancedMesh(new THREE.BoxGeometry(0.012, 0.42, 0.012), new THREE.MeshBasicMaterial({ color: 0xE3ECF0, transparent: true, opacity: 0.42, depthWrite: false }), NR);
  rain.frustumCulled = false; sc.add(rain);
  const rr = (i, k) => { const x = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return x - Math.floor(x); };
  const dummy = new THREE.Object3D();
  function setRain(t, cx, cz, cy = 3.5, size = 9) {
    for (let i = 0; i < NR; i++) {
      const H = 8, sp = 9.5 + rr(i, 3) * 2, y = cy + H / 2 - ((t * sp + rr(i, 2) * H) % H);
      dummy.position.set(cx + (rr(i, 0) - 0.5) * size, y, cz + (rr(i, 1) - 0.5) * size); if (dummy.position.distanceTo(C.position) < 2.6) dummy.position.y = -60; dummy.rotation.set(0, 0, 0.06); dummy.updateMatrix(); rain.setMatrixAt(i, dummy.matrix); }
    rain.instanceMatrix.needsUpdate = true; }
  // 登場：ビッグフェイス、傘、カエル
  const bf = bigFace(sc), fr = frog(sc), um = umbrella(bf.body);
  const fore = [0, 1].map(() => { const g = new THREE.Group(); bf.body.add(g); mesh(new THREE.CapsuleGeometry(0.065, 0.14, 4, 10), toon(PAL.face), g, [0, -0.13, 0], { line: 0.12 });
    const hand = mesh(new THREE.SphereGeometry(0.095, 12, 10), toon(PAL.face), bf.body, [0, 0, 0], { line: 0.1 }); return { g, hand }; });
  // ほおの雨つぶ（頭の表面をつたって下りる）
  const drops = [0, 1].map(side => Array.from({ length: 4 }, (_, k) => mesh(new THREE.SphereGeometry(0.03, 8, 6), new THREE.MeshBasicMaterial({ color: 0xF4F8FA }), bf.head, [0, 0, 0], { scale: [1, 1.4, 0.6], cast: false })));
  const surf = (x, y) => Math.sqrt(Math.max(0.02, 1 - (x / 1.12) ** 2 - y * y));
  // アイキャッチの舞台（EP.01 と同じ）
  const EX = -60, EYEC = 0xF1E4CC;
  mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: EYEC }), sc, [EX, 0.001, 0], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false });
  mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: EYEC }), sc, [EX, 10, -4], { cast: false, recv: false });
  const blob = mesh(new THREE.CircleGeometry(0.75, 32), new THREE.MeshBasicMaterial({ color: 0xC9B79C, transparent: true, opacity: 0.6 }), sc, [EX, 0.01, 0], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false });
  const bf2 = bigFace(sc); bf2.root.position.set(EX, 0, 0);
  // カエルの場所：歩道のはし → 2回はねて逃げる → 水たまりへ
  const FP = [[0.75, 5.75], [1.35, 6.05], [1.95, 5.95], [2.6, 5.4]];
  function frogPos(t) {
    if (t < E.s4) return [FP[0][0], 0, FP[0][1], 0];
    const hop = (t0, a, b, h = 0.32, d = 0.45) => { const u = seg(t, t0, t0 + d); if (u <= 0) return null; if (u >= 1) return [b[0], 0, b[1], 1];
      return [lerp(a[0], b[0], u), h * Math.sin(Math.PI * u), lerp(a[1], b[1], u), u]; };
    if (t >= E.s9) { const k = t - E.s9, n = Math.floor(k / 0.75), u = (k % 0.75) / 0.42;   // いっしょに歩く：小さくはねながら
      const x0 = 1.3 + n * 0.62, y = u < 1 ? 0.22 * Math.sin(Math.PI * u) : 0, x = u < 1 ? x0 + 0.62 * u : x0 + 0.62; return [x, y, 6.5, Math.min(1, u)]; }
    let r = hop(E.splash - 0.5, FP[2], FP[3], 0.5, 0.5); if (r) return [r[0], r[1] - (r[3] >= 1 ? 0.06 : 0), r[2], r[3]];
    r = hop(E.hop2, FP[1], FP[2]); if (r) return r;
    r = hop(E.hop1, FP[0], FP[1]); if (r) return r;
    return [FP[0][0], 0, FP[0][1], 0];
  }
  // ビッグフェイスの場所（x, z, 向き, 歩いているか）
  function bfPath(t) {
    if (t < E.s2) { const u = ease(seg(t, 0.0, 4.6)); return [lerp(-5.2, -0.8, u), 4.2, lerp(Math.PI / 2, 0, ease(seg(t, 4.2, 5.4))), t < 4.6]; }
    if (t < E.s4) return [-0.8, 4.2, 0, false];
    if (t < E.s5) return [-0.8, 4.2, lerp(0, 0.75, ease(seg(t, E.notice + 0.4, E.notice + 1.3))), false];
    if (t < E.s9) { const u = ease(seg(t, E.s5 + 0.2, E.s5 + 1.2)), u2 = ease(seg(t, E.hop1 + 0.7, E.hop1 + 1.4));
      return [lerp(lerp(-0.8, -0.3, u), 0.15, u2), lerp(lerp(4.2, 4.75, u), 4.95, u2), 0.75 + 0.2 * u2, (t > E.s5 + 0.2 && t < E.s5 + 1.2) || (t > E.hop1 + 0.7 && t < E.hop1 + 1.4)]; }
    if (t < E.s10) { const u = seg(t, E.s9, E.s9 + 7.0); return [lerp(0.6, 5.0, u), 5.6, Math.PI / 2, true]; }
    return [lerp(0.6, 5.0, seg(E.s10, E.s9, E.s9 + 7.0)) + 0.25 * ease(seg(t, E.s10, E.s10 + 0.6)), 5.6, Math.PI / 2 - 0.9 * ease(seg(t, E.s10 + 0.2, E.s10 + 1.1)), t < E.s10 + 0.6];
  }
  const head = { x: 0, v: 0 }; let lastT = -1, prevV = 0, phase = 0, gaitW = 0;
  return (t) => {
    const dt = 1 / 120;
    if (lastT < 0 || t < lastT - 1e-6) { lastT = 0; prevV = 0; head.x = head.v = 0; phase = gaitW = 0; }
    while (lastT + dt <= t + 1e-6) {
      const a = bfPath(lastT), b = bfPath(lastT + dt);
      const v = Math.hypot(b[0] - a[0], b[1] - a[1]) / dt, acc = (v - prevV) / dt; prevV = v;
      const w = 2 * Math.PI * 2.0, z = 0.58, tgt = THREE.MathUtils.clamp(-acc * 0.02, -0.17, 0.17);
      head.v += (-w * w * (head.x - tgt) - 2 * z * w * head.v) * dt; head.x += head.v * dt;
      gaitW += ((a[3] ? 1 : 0) - gaitW) * (1 - Math.exp(-dt / 0.065));
      if (a[3]) phase += v * dt / 0.36 * Math.PI;
      lastT += dt;
    }
    const [x, z, hd] = bfPath(t);
    bf.root.position.set(x, 0, z); bf.root.rotation.y = hd; walkPose(bf, phase, gaitW, 0.45);
    let pitch = head.x, roll = 0; const st = bf.st; st.look = [0, 0]; st.blink = 0; st.mouth = 0; st.sq = 0; st.happy = 0; st.wink = [0, 0];
    const blink = (tb) => { if (t > tb && t < tb + 0.14) st.blink = Math.sin(seg(t, tb, tb + 0.14) * Math.PI); };
    // 傘を持つ位置：sd = +1 右がわ（頭の横）、-1 左がわ。柄はふつうの長さで、腕のほうが伸びて頭の外を回る（11/12 ゲンタさん「傘が貫通しまくってる」「持ち手が長すぎる。腕伸ばして」）
    const uS = ease(seg(t, E.swap, E.swap + 1.3));   // 持ちかえ：頭の上を弧をえがいて反対がわへ（とちゅうは両手）
    let sd = Math.cos(Math.PI * uS), arcY = Math.sin(Math.PI * uS);
    let open = 1, reach = 0, offerW = null, lower = 0;
    // 雨にぬれる側（傘のない側）：0=-x がわ 1=+x がわ
    let wet = [(1 + sd) / 2, (1 - sd) / 2];
    // 顔の演技
    if (t < E.s2) { blink(2.2); }
    if (t >= E.s2 && t < E.s3) { const k = t - E.s2;
      st.look = [0.8 * ease(seg(k, 0.6, 0.8)) * (1 - ease(seg(k, 1.8, 2.0))) - 0.8 * ease(seg(t, E.swap + 1.8, E.swap + 2.0)), 0];
      st.wink = [0.55 * wet[0], 0.55 * wet[1]]; blink(E.swap + 1.4); }
    if (t >= E.s3 && t < E.s4) { pitch += 0.08 * ease(seg(t, E.center + 0.7, E.center + 1.4)); st.wink = [0, 0.5]; st.look = [-0.6, 0]; blink(E.s3 + 2.1); st.mouth = 0.2; }
    if (t >= E.s4 && t < E.s5) { st.look = [0, -0.8 * ease(seg(t, E.notice, E.notice + 0.25))]; pitch += 0.18 * ease(seg(t, E.notice + 0.2, E.notice + 0.8)); blink(E.notice + 1.6); }
    // 差し出す（腕がにゅーっと伸びる）：傘はカエルの真上へ
    if (t >= E.s5 && t < E.s8) {
      const r1 = ease(seg(t, E.offer1, E.offer1 + 0.9)), r2 = ease(seg(t, E.offer2, E.offer2 + 1.0)), back = ease(seg(t, E.hop2 + 0.7, E.s6 + 0.4));
      reach = Math.max(r1, r2) * (1 - back);
      const follow = t > E.offer2 ? frogPos(t) : frogPos(Math.min(t, E.hop1 - 0.05));
      offerW = new THREE.Vector3(follow[0], 1.45, follow[2]);   // 柄の手元はカエルの上 1.45m、布はその 1m 上
      pitch += 0.2 * reach; st.look = [0, -0.7 * reach];
      if (t > E.hop1 && t < E.offer2) { st.look = [0.6 * ease(seg(t, E.hop1, E.hop1 + 0.3)), -0.5]; }
      if (t > E.hop2 && t < E.s6) st.look = [0.6, -0.5];
      wet = [Math.max(wet[0], 0.9 * reach), Math.max(wet[1], 0.9 * reach)]; st.wink = [0.4 * reach, 0.4 * reach]; }
    if (t >= E.s6 && t < E.s7) { roll = 0.1 * ease(seg(t, E.s6 + 0.5, E.s6 + 1.1)); blink(E.s6 + 1.5); st.look = [0.5, -0.3]; st.wink = [0, 0.3]; }
    if (t >= E.s8 && t < E.s9) { st.look = [0.4 * (1 - ease(seg(t, E.smile - 0.4, E.smile))), -0.25];
      st.happy = ease(seg(t, E.smile, E.smile + 0.4)); blink(E.s8 + 0.7); open = 1 - ease(seg(t, E.close, E.close + 0.8));
      lower = ease(seg(t, E.close + 0.6, E.close + 1.6)); wet = [Math.max(wet[0], 0.8 * lower), Math.max(wet[1], 0.8 * lower)]; }
    if (t >= E.s9) { open = 0; lower = 1; st.happy = 1; wet = [0.7, 0.7]; blink(E.s9 + 2.0); blink(E.s9 + 4.4); }
    if (t >= E.s10 && t < E.eye) { const u = ease(seg(t, E.s10 + 0.9, E.s10 + 1.6)); pitch -= 0.14 * u; st.blink = Math.max(st.blink, 0.85 * u); st.happy = 1; }
    bf.neck.rotation.x = pitch; bf.neck.rotation.z = roll; bf.setFace();
    // ---- 傘と腕（すべて体のローカル座標）。頭（だ円）の中に入らないように押し出す
    bf.root.updateMatrixWorld(true);
    const HCw = new THREE.Vector3(); bf.head.getWorldPosition(HCw); const HC = bf.body.worldToLocal(HCw.clone());
    const pushOut = (p, m = 1.22) => { const v = p.clone().sub(HC), d = Math.hypot(v.x / 1.12, v.y, v.z); return d >= m ? p : HC.clone().add(v.multiplyScalar(m / Math.max(d, 1e-3))); };
    const side = (q, ay = 0) => [new THREE.Vector3(q * 1.34, HC.y + 0.9 + 0.75 * ay, 0.12), new THREE.Vector3(-0.5 * q, 0.87, 0).normalize()];
    let [grip, dir] = side(sd, arcY);
    if (reach > 0.001) { const tg = bf.body.worldToLocal(offerW.clone()); grip = pushOut(grip.clone().lerp(tg, reach), 1.3); dir = dir.clone().lerp(new THREE.Vector3(0, 1, 0), reach).normalize(); }
    if (lower > 0) { const hang = new THREE.Vector3(-0.66, 1.2, 0.32), mid = new THREE.Vector3(-1.55, 1.9, 0.3);
      const u = lower, a = grip.clone().lerp(mid, u), b = mid.clone().lerp(hang, u); grip = pushOut(a.lerp(b, u), 1.3);
      dir = dir.clone().lerp(new THREE.Vector3(0.12, -1, 0.15), u).normalize(); }
    const closed = 1 - open;
    um.canopy.scale.set(lerp(1, 0.14, closed), lerp(1, 2.4, closed), lerp(1, 0.14, closed)); um.canopy.position.y = lerp(1.0, 0.62, closed);
    um.g.position.copy(grip); um.g.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    // 持つ手：右がわ（sd>0）は右手、左がわは左手。持ちかえの途中（頭の上）は両手
    const hold = [sd < 0.35 || lower > 0 || reach > 0.001 ? 1 : 0, sd > -0.35 && lower === 0 && reach <= 0.001 ? 1 : 0];
    if (reach > 0.001) { hold[0] = 1; hold[1] = 0; }
    const aim = (g, from, to) => { const d = to.clone().sub(from), len = d.length(); g.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), d.normalize()); g.scale.set(1, Math.max(0.5, len / 0.27), 1); };
    bf.arms.forEach((a, i) => { const sx = i ? 1 : -1;
      a.scale.set(1, 1, 1); a.rotation.set(0, 0, 0); a.quaternion.identity();
      if (!hold[i]) { fore[i].g.visible = false; fore[i].hand.visible = false; a.rotation.z = sx * 0.1; return; }
      fore[i].g.visible = true; fore[i].hand.visible = true;
      const sh = new THREE.Vector3(sx * 0.36, 0.78, 0), hg = grip.clone().add(new THREE.Vector3(sx * 0.03, 0.02, 0));
      const el = pushOut(sh.clone().lerp(hg, 0.5).add(new THREE.Vector3(sx * 0.35, 0, 0.12)), 1.3);
      aim(a, sh, el); fore[i].g.position.copy(el); aim(fore[i].g, el, hg); fore[i].hand.position.copy(hg); });
    // ほおの雨つぶ
    drops.forEach((side, si) => side.forEach((d, k) => { const sx = si ? 1 : -1; const u = ((t * 0.9 + k * 0.27 + si * 0.13) % 1);
      const xx = sx * (0.72 + 0.08 * (k % 2)), yy = 0.25 - 0.85 * u; d.visible = wet[si] > 0.2 + k * 0.15 && t < E.eye;
      d.position.set(xx, yy, surf(xx, yy) + 0.01); }));
    // カエル
    const [fx, fy, fz, fu] = frogPos(t);
    fr.root.position.set(fx, fy, fz); fr.root.rotation.y = t >= E.s9 ? Math.PI / 2 : (t > E.hop1 ? 1.2 : -0.6);
    const air = fy > 0.02; fr.body.scale.set(1, air ? 1.15 : 1, air ? 1.1 : 1); fr.legs.forEach(l => { l.scale.z = air ? 0.22 : 0.12; });
    const inPud = t > E.splash && t < E.s9; if (inPud) { fr.root.position.y = -0.05 + 0.03 * Math.sin(t * 5); fr.root.rotation.y = Math.sin(t * 1.3) * 0.8; }
    const fhappy = inPud || t >= E.s9 ? 1 : 0; fr.eyes.forEach(e => e.scale.y = 1.1 * (1 - 0.7 * fhappy));
    // 水たまりの波紋（雨）＋ 飛びこんだとき
    ripples.forEach(r => { const u = (t * 0.8 + r.ph) % 1; r.rg.position.set(r.x, 0.016, r.z); r.rg.scale.setScalar(0.06 + 0.32 * u); r.m.opacity = 0.55 * (1 - u); });
    splashRings.forEach((s, k) => { const u = seg(t, E.splash + k * 0.25, E.splash + k * 0.25 + 1.2); s.m.opacity = u > 0 && u < 1 ? 0.8 * (1 - u) : 0; s.rg.scale.setScalar(0.1 + 0.9 * Math.max(0, u)); });
    splashDrops.forEach((d, k) => { const u = seg(t, E.splash, E.splash + 0.55); if (u <= 0 || u >= 1) { d.position.set(0, -5, 0); return; }
      const a = k / splashDrops.length * Math.PI * 2, r = 0.5 * u; d.position.set(2.6 + Math.cos(a) * r, 0.5 * Math.sin(Math.PI * u) * (0.6 + 0.4 * (k % 3) / 2), 5.4 + Math.sin(a) * r * 0.7); });
    // アイキャッチ（EP.01 と同じ）
    if (t >= E.eye) {
      const k = t - E.eye, fall = Math.min(1, k / 0.32), y = 3.2 * (1 - fall * fall); bf2.root.position.y = y; const land = k - 0.32;
      bf2.st.look = [0, 0]; bf2.st.blink = 0; bf2.st.mouth = 0; bf2.st.happy = 1; bf2.st.sq = 0; let p2 = 0;
      if (land > 0) { bf2.st.sq = Math.max(-0.03, 0.08 * Math.exp(-land * 8) * Math.cos(land * 24)); p2 = 0.06 * Math.exp(-land * 5) * Math.sin(land * 16); bf2.body.scale.set(1 + 0.12 * Math.exp(-land * 12), 1 - 0.12 * Math.exp(-land * 12), 1); }
      if (k > 1.6 && k < 1.74) bf2.st.blink = Math.sin(seg(k, 1.6, 1.74) * Math.PI);
      bf2.neck.rotation.x = p2; bf2.neck.rotation.z = 0.09 * ease(seg(k, 1.0, 1.35)); bf2.setFace(); blob.scale.setScalar(0.6 + 0.4 * fall);
    }
    // カメラ
    const cam = (pos, look, fov) => { C.fov = fov; C.position.set(...pos); C.lookAt(...look); };
    const cu = (yaw = 0, dist = 3.2, fov = 40, dy = 0.0) => { bf.root.updateMatrixWorld(true); const hp = new THREE.Vector3(); bf.head.getWorldPosition(hp);
      const h = bf.root.rotation.y + yaw, d = new THREE.Vector3(Math.sin(h), 0, Math.cos(h)); C.fov = fov; C.position.set(hp.x + d.x * dist, hp.y + 0.1 + dy, hp.z + d.z * dist); C.lookAt(hp.x, hp.y + dy * 0.5, hp.z); return hp; };
    let rc = [0, 5];
    sun.position.set(6, 12, 8); sun.target.position.set(0, 0, 3); rain.visible = true; hemi.intensity = 1.7;
    if (t < E.s2) { cam([3.2, 2.3, 13.5], [-1.6, 1.9, 3.8], 40); rc = [-1, 7]; }
    else if (t < E.s3) { cam([-0.8, 2.6, 11.4], [-0.8, 2.95, 4.2], 42); rc = [-0.8, 6]; }   // 傘まで入る
    else if (t < E.s4) { const hp = cu(0, 3.6, 46, 0.45); rc = [hp.x, hp.z]; }
    else if (t < E.s5) { cam([1.5, 0.42, 8.9], [0.1, 1.35, 4.8], 44); rc = [0.6, 6.5]; }
    else if (t < E.s6) { cam([0.9, 1.9, 11.6], [0.9, 1.2, 5.3], 38); rc = [0.9, 7]; }
    else if (t < E.s7) { const hp = cu(0, 3.5, 44, 0.3); rc = [hp.x, hp.z]; }
    else if (t < E.s8) { cam([3.0, 0.55, 7.9], [2.55, 0.2, 5.4], 38); rc = [2.6, 6.5]; }
    else if (t < E.s9) { const hp = cu(-0.15, 3.7, 46, 0.35); rc = [hp.x, hp.z]; }
    else if (t < E.s10) { const k = seg(t, E.s9, E.s10); cam([x + 0.7, 1.6, 13.0], [x + 0.7, 1.3, 5.8], 36); rc = [x + 0.7, 8]; }   // 横から並んで歩く（カメラはいっしょに横へ）
    else if (t < E.eye) { const hp = cu(0, 3.7, 44, 0.2); rc = [hp.x, hp.z]; }
    else { cam([EX, 1.4, 9.0], [EX, 0.75, 0], 36); rain.visible = false; hemi.intensity = 1.2; sun.position.set(EX + 6, 10, 8); sun.target.position.set(EX, 0, 0); }
    setRain(t, rc[0], rc[1]);
    C.updateProjectionMatrix();
  };
}

// ==== 公園（EP.03 の集合写真の場所。11/13 ゲンタさん「パン屋の前にしないで」）
function park(sc) {
  const grassT = grain(0x9CC08A, 512, 512, 18, (g, w, h, r) => { g.fillStyle = "rgba(60,90,40,0.10)"; for (let i = 0; i < 900; i++) g.fillRect(r() * w, r() * h, 2, 6); }); grassT.repeat.set(24, 24);
  mesh(new THREE.PlaneGeometry(140, 140), toon(0xffffff, { map: grassT }), sc, [0, 0, 0], { rot: [-Math.PI / 2, 0, 0], cast: false });
  mesh(new THREE.CircleGeometry(3.6, 40), toon(0xE4D6B8), sc, [0, 0.006, 2.2], { rot: [-Math.PI / 2, 0, 0], scale: [1.6, 1, 1], cast: false });   // 土の広場
  mesh(new THREE.PlaneGeometry(1.8, 30), toon(0xE4D6B8), sc, [0, 0.005, 18], { rot: [-Math.PI / 2, 0, 0], cast: false });                       // 小道
  // 大きな木（集合写真の背景）
  const bark = toon(0x8A6A50), leaf = toon(0x7FA87A), leaf2 = toon(0x6E9A6C);
  mesh(new THREE.CylinderGeometry(0.32, 0.45, 3.6, 12), bark, sc, [0, 1.8, -3.2], { line: 0.03 });
  [[0, 4.6, -3.2, 2.0, leaf], [-1.5, 4.0, -3.0, 1.4, leaf2], [1.5, 4.1, -3.3, 1.5, leaf2], [0.4, 5.6, -3.4, 1.4, leaf], [-0.8, 5.2, -2.6, 1.1, leaf]].forEach(([x, y, z, r, m]) => mesh(new THREE.SphereGeometry(r, 18, 12), m, sc, [x, y, z], { scale: [1, 0.85, 1], line: 0.02 }));
  // ベンチ・花だん・さく・遠くの木と丘
  const wood = toon(0xA9805E);
  [[-4.2, -1.8, 0.4], [4.4, -1.4, -0.4]].forEach(([x, z, r]) => { const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = r; sc.add(g);
    mesh(new THREE.BoxGeometry(1.8, 0.08, 0.45), wood, g, [0, 0.46, 0], { line: 0.03 }); mesh(new THREE.BoxGeometry(1.8, 0.4, 0.06), wood, g, [0, 0.75, -0.2], { line: 0.03 });
    [-0.8, 0.8].forEach(dx => mesh(new THREE.BoxGeometry(0.08, 0.46, 0.4), toon(0x5E5A55), g, [dx, 0.23, 0], { line: 0.05 })); });
  const fl = [0xE7A0A8, 0xF2D27A, 0xF4F0E6, 0xB9A0D8];
  for (let i = 0; i < 26; i++) { const x = -3.2 + (i % 13) * 0.5, z = -1.4 - Math.floor(i / 13) * 0.35; if (Math.abs(x) < 0.9) continue;
    mesh(new THREE.SphereGeometry(0.11, 8, 6), toon(fl[i % 4]), sc, [x, 0.22, z], { line: 0.08 }); mesh(new THREE.SphereGeometry(0.16, 8, 6), toon(0x7FA07A), sc, [x, 0.1, z], { scale: [1, 0.6, 1], cast: false }); }
  for (let x = -14; x <= 14; x += 1.4) { mesh(new THREE.BoxGeometry(0.08, 0.7, 0.08), wood, sc, [x, 0.35, -7.5], { line: 0.05 }); }
  mesh(new THREE.BoxGeometry(28.5, 0.06, 0.06), wood, sc, [0, 0.55, -7.5], {}); mesh(new THREE.BoxGeometry(28.5, 0.06, 0.06), wood, sc, [0, 0.25, -7.5], {});
  [[-7, -9, 1.6], [7.5, -10, 1.9], [-11, -6, 1.4], [11, -7, 1.5], [-4, -12, 1.3], [4, -13, 1.2]].forEach(([x, z, r]) => { mesh(new THREE.CylinderGeometry(0.15, 0.2, 1.6, 8), bark, sc, [x, 0.8, z], {}); mesh(new THREE.SphereGeometry(r, 14, 10), leaf2, sc, [x, 2.2 + r * 0.4, z], { line: 0.02 }); });
  [[-20, -40, 14, 0xA9C4A0], [8, -45, 18, 0x9DB8A6], [30, -38, 12, 0xB2C8A4]].forEach(([x, z, r, c]) => mesh(new THREE.SphereGeometry(r, 24, 12), new THREE.MeshBasicMaterial({ color: c }), sc, [x, -r * 0.55, z], { scale: [1.6, 1, 1], cast: false }));
}
function tripodCam(parent) {
  const g = new THREE.Group(); parent.add(g);
  const m = toon(0x4A4F55), legM = toon(0x6E6A64);
  [0, 2.1, 4.2].forEach(a => { const l = mesh(new THREE.CylinderGeometry(0.02, 0.02, 1.35, 6), legM, g, [Math.sin(a) * 0.22, 0.62, Math.cos(a) * 0.22], { line: 0.2 }); l.rotation.set(Math.cos(a) * 0.32, 0, -Math.sin(a) * 0.32); });
  const body = mesh(new THREE.BoxGeometry(0.34, 0.24, 0.2), m, g, [0, 1.36, 0], { line: 0.04 });
  mesh(new THREE.CylinderGeometry(0.075, 0.08, 0.16, 16), toon(0x2E3338), g, [0, 1.36, -0.17], { rot: [Math.PI / 2, 0, 0], line: 0.06 });
  const lamp = mesh(new THREE.SphereGeometry(0.022, 8, 6), new THREE.MeshBasicMaterial({ color: 0x5A2A2A }), g, [0.12, 1.45, -0.1], {});
  return { g, lamp };
}
function ep03(p) {
  const E = EP03;
  const sc = S = new THREE.Scene();
  const SKY = 0xBFDDEB; sc.background = new THREE.Color(SKY); sc.fog = new THREE.Fog(SKY, 22, 70);
  const hemi = new THREE.HemisphereLight(0xFFF8EC, 0xA8B890, 1.15); sc.add(hemi);
  const sun = new THREE.DirectionalLight(0xFFF2DE, 1.55); sun.position.set(5, 11, 8); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 6; sun.shadow.bias = -0.0008; sun.shadow.normalBias = 0.05;
  Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -6, near: 1, far: 30 }); sc.add(sun); sc.add(sun.target);
  park(sc);
  const tc = tripodCam(sc); tc.g.position.set(0, 0, 6.5);
  // みんな（5人）：横一列。左から
  const ppl = [person(sc, { h: 1.75, coat: 0x8FA5B8, pants: 0x55606A, hair: 0x3A3A3A }), person(sc, { h: 1.6, coat: 0xC7A0B4, pants: 0x6A5A60, hair: 0x7A5A3A }),
    person(sc, { h: 1.05, coat: 0xE3B26A, pants: 0x7C6A5C, hair: 0x5A3A2A, headR: 0.17 }), person(sc, { h: 1.5, coat: 0xB9B08A, pants: 0x5A5A50, hat: "brim", hatC: 0x6F7F78 }),
    person(sc, { h: 1.65, coat: 0x9FB89A, pants: 0x5E5850, hair: 0x2E2E2E })];
  const LINE = [[-1.7, 0.1], [-0.85, 0.0], [0, 0.25], [0.85, 0.0], [1.7, 0.1]];
  // ビッグフェイスと、伸びる首
  const bf = bigFace(sc), skinM = toon(PAL.face);
  const longNeck = mesh(new THREE.CylinderGeometry(0.13, 0.15, 1, 14), skinM, bf.body, [0, 1, 0], { line: 0.1 });
  const fore = [0, 1].map(() => { const g = new THREE.Group(); bf.body.add(g); mesh(new THREE.CapsuleGeometry(0.065, 0.14, 4, 10), skinM, g, [0, -0.13, 0], { line: 0.12 });
    const hand = mesh(new THREE.SphereGeometry(0.095, 12, 10), skinM, bf.body, [0, 0, 0], { line: 0.1 }); g.visible = hand.visible = false; return { g, hand }; });
  // アイキャッチの舞台
  const EX = -60, EYEC = 0xF1E4CC;
  mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: EYEC }), sc, [EX, 0.001, 0], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false });
  mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: EYEC }), sc, [EX, 10, -4], { cast: false, recv: false });
  const blob = mesh(new THREE.CircleGeometry(0.75, 32), new THREE.MeshBasicMaterial({ color: 0xC9B79C, transparent: true, opacity: 0.6 }), sc, [EX, 0.01, 0], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false });
  const bf2 = bigFace(sc); bf2.root.position.set(EX, 0, 0);
  // ビッグフェイスの場所（x, z, 向き, 歩いているか）
  function bfPath(t) {
    if (t < E.s2) { const u = ease(seg(t, 0.4, 4.4)); return [lerp(-4.6, 0, u), lerp(2.6, 1.45, u), lerp(Math.PI / 2, 0, ease(seg(t, 3.6, 4.6))), t > 0.4 && t < 4.4]; }
    if (t < E.s3) return [0, 1.45, 0, false];
    if (t < E.s4) { const u = ease(seg(t, E.s3 + 0.3, E.s3 + 1.4)); return [lerp(0, 1.95, u), lerp(1.45, 1.25, u), lerp(0, 0, u), t > E.s3 + 0.3 && t < E.s3 + 1.4]; }
    if (t < E.s5) { const u = ease(seg(t, E.s4 + 0.2, E.s4 + 1.6)); const x = lerp(1.95, 0, u), z = lerp(1.25, -1.15, u) + Math.sin(Math.PI * u) * 0.0;
      return [u < 0.5 ? lerp(1.95, 2.9, u * 2) : lerp(2.9, 0, (u - 0.5) * 2), u < 0.5 ? lerp(1.25, 0.2, u * 2) : lerp(0.2, -1.15, (u - 0.5) * 2), u < 0.05 ? 0 : lerp(2.4, 4.28, ease(seg(u, 0.4, 0.6))) + (2 * Math.PI - 4.28) * ease(seg(t, E.s4 + 1.5, E.s4 + 2.1)), t > E.s4 + 0.2 && t < E.s4 + 1.6]; }   // 後ろに回って、カメラのほうへ向き直る
    if (t < E.s6) { const u = ease(seg(t, E.point + 0.6, E.s6 + 1.4)); const tgt = [0, 7.6];
      return [lerp(0, 2.6, Math.min(1, u * 2)) * (1 - Math.max(0, u * 2 - 1)) + tgt[0] * Math.max(0, u * 2 - 1), lerp(-1.15, tgt[1], u), u > 0.02 ? (u < 0.98 ? 0.3 : Math.PI) : 0, t > E.point + 0.6]; }
    if (t < E.s9) { const u = ease(seg(t, E.s6, E.s6 + 0.6)); return [0, 7.6, lerp(0.3, Math.PI, Math.max(u, 0.0)), false]; }
    if (t < E.s10) return [0, 7.6, lerp(Math.PI, Math.PI + 0.25, ease(seg(t, E.beckon - 0.2, E.beckon + 0.4))), false];
    return [0, 1.45, 0, false];
  }
  const head = { x: 0, v: 0 }; let lastT = -1, prevV = 0, phase = 0, gaitW = 0;
  return (tIn) => {
    // 写真（止め絵）：シャッターの瞬間の姿のまま
    let t = tIn; if (tIn >= E.s7 && tIn < E.s8) t = E.shot1 + 0.001; if (tIn >= E.s11 && tIn < E.eye) t = E.shot2 - 0.02;
    const dt = 1 / 120;
    if (lastT < 0 || t < lastT - 1e-6) { lastT = 0; prevV = 0; head.x = head.v = 0; phase = gaitW = 0; }
    while (lastT + dt <= t + 1e-6) { const a = bfPath(lastT), b = bfPath(lastT + dt);
      const v = Math.hypot(b[0] - a[0], b[1] - a[1]) / dt, acc = (v - prevV) / dt; prevV = v;
      const w = 2 * Math.PI * 2.0, z = 0.58, tg = THREE.MathUtils.clamp(-acc * 0.02, -0.17, 0.17);
      head.v += (-w * w * (head.x - tg) - 2 * z * w * head.v) * dt; head.x += head.v * dt;
      gaitW += ((a[3] ? 1 : 0) - gaitW) * (1 - Math.exp(-dt / 0.065)); if (a[3]) phase += v * dt / 0.36 * Math.PI; lastT += dt; }
    const [x, z, hd] = bfPath(t);
    bf.root.position.set(x, 0, z); bf.root.rotation.y = hd; walkPose(bf, phase, gaitW, 0.45);
    let pitch = head.x, roll = 0; const st = bf.st; st.look = [0, 0]; st.blink = 0; st.mouth = 0; st.sq = 0; st.happy = 0; st.wink = [0, 0];
    const blink = (tb) => { if (t > tb && t < tb + 0.14) st.blink = Math.sin(seg(t, tb, tb + 0.14) * Math.PI); };
    // 首がのびる（後ろに立ったとき）
    const ns = t >= E.s4 && t < E.s5 + 1.2 ? ease(seg(t, E.stretch, E.stretch + 1.0)) * (1 - ease(seg(t, E.s5 + 0.2, E.s5 + 1.0))) : 0;
    const L = 2.3 * ns;   // 首がにゅーっと長く（少し奇妙なからだ）
    bf.neck.position.y = 0.92 + L; longNeck.visible = L > 0.02; longNeck.position.y = 0.92 + L / 2 + 0.05; longNeck.scale.y = Math.max(0.01, L + 0.1);
    bf.arms.forEach((a, i) => { a.rotation.set(0, 0, 0); a.scale.set(1, 1, 1); a.quaternion.identity(); });
    fore.forEach(f => { f.g.visible = f.hand.visible = false; });
    // 顔
    if (t < E.s2) blink(3.0);
    if (t >= E.s2 && t < E.s3) { blink(E.s2 + 1.2); st.look = [0.5 * ease(seg(t, E.s2 + 2.4, E.s2 + 2.7)) * (1 - ease(seg(t, E.s2 + 3.3, E.s2 + 3.6))), 0]; }
    if (t >= E.s3 && t < E.s4) { st.look = [-0.6 * ease(seg(t, E.s3 + 1.7, E.s3 + 2.0)), 0]; blink(E.s3 + 2.6); }
    if (t >= E.s4 && t < E.s5) { st.look = [0, -0.6 * ease(seg(t, E.stretch + 0.8, E.stretch + 1.2))]; blink(E.stretch + 1.6); }
    if (t >= E.s5 && t < E.s6) { pitch += 0.16 * ease(seg(t, E.s5 + 1.0, E.s5 + 1.5)) * (1 - ease(seg(t, E.point - 0.2, E.point + 0.2))); blink(E.s5 + 1.7);
      const pu = ease(seg(t, E.point, E.point + 0.35)) * (1 - ease(seg(t, E.point + 1.0, E.point + 1.3))); bf.arms[1].rotation.x = -1.4 * pu; }   // カメラを指さす
    if (t >= E.s6 && t < E.s7) { const pr = ease(seg(t, E.shot1 - 0.6, E.shot1 - 0.2)) * (1 - ease(seg(t, E.shot1 + 0.5, E.shot1 + 0.9)));
      const sh = new THREE.Vector3(0.36, 0.78, 0), hg = new THREE.Vector3(0.18, 1.0, 0.5).lerp(new THREE.Vector3(0.12, 1.42, 1.02), pr);   // シャッターボタンへ手をのばす
      const el = sh.clone().lerp(hg, 0.5).add(new THREE.Vector3(0.18, -0.05, 0));
      const aim = (g, from, to) => { const d = to.clone().sub(from), len = d.length(); g.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), d.normalize()); g.scale.set(1, Math.max(0.5, len / 0.27), 1); };
      if (pr > 0.01) { aim(bf.arms[1], sh, el); fore[1].g.visible = fore[1].hand.visible = true; fore[1].g.position.copy(el); aim(fore[1].g, el, hg); fore[1].hand.position.copy(hg); }
      pitch += 0.12; st.look = [0, -0.5]; blink(E.s6 + 0.8); }
    if (t >= E.s8 && t < E.s9) { pitch += 0.22; st.look = [0, -0.9]; blink(E.s8 + 1.4); st.mouth = 0.15; if (t > E.s8 + 2.2) pitch += 0.04 * ease(seg(t, E.s8 + 2.2, E.s8 + 3.0)); }
    if (t >= E.s9 && t < E.s10) { const up = ease(seg(t, E.beckon + 0.3, E.beckon + 0.7)); pitch += 0.2 * (1 - up); st.look = [-0.4 * up, -0.6 * (1 - up)]; blink(E.beckon + 1.2);
      st.happy = ease(seg(t, E.pull + 0.6, E.pull + 1.2)); }
    if (t >= E.s10 && t < E.eye) { st.happy = 1; blink(E.s10 + 1.0); st.look = [0, 0]; }
    bf.neck.rotation.x = pitch; bf.neck.rotation.z = roll; bf.setFace();
    // みんな
    ppl.forEach((pp, i) => { const [px, pz] = LINE[i]; pp.root.position.set(px, 0, pz); pp.root.rotation.set(0, 0, 0); pp.neck.rotation.set(0, 0, 0);
      pp.arms.forEach(a => a.rotation.set(0, 0, 0)); pp.legs.forEach(l => l.rotation.set(0, 0, 0)); pp.body.position.y = 0; pp.st.blink = 0;
      const sx = i < 2 ? -1 : 1;
      if (t < E.s2) { pp.root.rotation.y = lerp(0, -0.5, ease(seg(t, 1.0 + i * 0.2, 2.0 + i * 0.2))) * (1 - ease(seg(t, 3.6, 4.4))); }   // 来る人を見る
      if (t >= E.s2 && t < E.s3 && Math.abs(px) < 1.3) { const w = ease(seg(t, E.s2 + 1.0 + i * 0.15, E.s2 + 1.4 + i * 0.15)); pp.arms[i < 2 ? 0 : 1].rotation.z = (i < 2 ? -1 : 1) * (2.4 + 0.25 * Math.sin(t * 9 + i)) * w; }   // 後ろで手をふる
      if (t >= E.s2 && t < E.s3 && Math.abs(px) >= 1.3) { pp.root.rotation.z = -sx * 0.22 * ease(seg(t, E.s2 + 1.5, E.s2 + 2.0)); }            // のぞきこむ
      if (t >= E.s3 && t < E.s4 && px > 0.5) { pp.root.rotation.z = 0.25 * ease(seg(t, E.s3 + 1.6, E.s3 + 2.1)); }
      if (t >= E.s4 && t < E.s5) { pp.neck.rotation.x = -0.45 * ease(seg(t, E.stretch + 0.4 + i * 0.08, E.stretch + 0.9 + i * 0.08)); }        // 見上げる
      if (t >= E.s5 && t < E.s6) { pp.root.rotation.y = 0.3 * ease(seg(t, E.point + 0.6, E.point + 1.2)); }
      if (t >= E.s9 && t < E.s10) { pp.root.rotation.y = 0; const w = ease(seg(t, E.beckon + i * 0.1, E.beckon + 0.4 + i * 0.1)); pp.arms[sx > 0 ? 1 : 0].rotation.x = -(1.6 + 0.5 * Math.sin(t * 8 + i)) * w;   // 手まねき
        if (i === 2) { const u = ease(seg(t, E.pull - 0.9, E.pull)); pp.root.position.set(lerp(px, 0.75, u), 0, lerp(pz, 6.9, u)); pp.root.rotation.y = lerp(0, Math.PI - 0.3, u);
          walkPose(pp, t * 14, u > 0 && u < 1 ? 1 : 0, 0.6); if (u >= 1) pp.arms[0].rotation.x = -1.1; } }
      if (t >= E.s10 && t < E.eye) {   // 大きな顔のまわりから顔を出す
        const P = [[-1.0, 0.95, 0.36, 0], [1.0, 0.9, -0.36, 0], [0, 0, 0, 1], [1.05, 2.3, 0, 2], [-1.05, 2.35, 0, 2]][i];
        if (P[3] === 0) { pp.root.position.set(P[0], 0, P[1]); pp.root.rotation.z = P[2]; }
        else if (P[3] === 1) { pp.root.position.set(0.05, 2.86, 1.45); pp.legs.forEach(l => l.rotation.x = -1.4); pp.arms[0].rotation.z = -0.9; pp.arms[1].rotation.z = 0.9; }   // 頭の上にすわる
        else { pp.root.position.set(P[0], -0.55, P[1]); pp.legs.forEach(l => l.rotation.x = -1.5); pp.arms[P[0] > 0 ? 1 : 0].rotation.z = (P[0] > 0 ? 1 : -1) * 2.3; }   // 前でしゃがむ
      }
      if (i === 3 && t > 6.0 && t < 6.14) pp.st.blink = 1; });
    // カメラのランプ（タイマー）
    const blinkOn = t > E.timer && t < E.shot2 && Math.floor((t - E.timer) * (t > E.shot2 - 0.8 ? 8 : 3)) % 2 === 0;
    tc.lamp.material.color.setHex(blinkOn ? 0xFF4A3A : 0x5A2A2A);
    // アイキャッチ
    if (tIn >= E.eye) {
      const k = tIn - E.eye, fall = Math.min(1, k / 0.32), y = 3.2 * (1 - fall * fall); bf2.root.position.y = y; const land = k - 0.32;
      bf2.st.look = [0, 0]; bf2.st.blink = 0; bf2.st.mouth = 0; bf2.st.happy = 1; bf2.st.sq = 0; let p2 = 0;
      if (land > 0) { bf2.st.sq = Math.max(-0.03, 0.08 * Math.exp(-land * 8) * Math.cos(land * 24)); p2 = 0.06 * Math.exp(-land * 5) * Math.sin(land * 16); bf2.body.scale.set(1 + 0.12 * Math.exp(-land * 12), 1 - 0.12 * Math.exp(-land * 12), 1); }
      if (k > 1.6 && k < 1.74) bf2.st.blink = Math.sin(seg(k, 1.6, 1.74) * Math.PI);
      bf2.neck.rotation.x = p2; bf2.neck.rotation.z = 0.09 * ease(seg(k, 1.0, 1.35)); bf2.setFace(); blob.scale.setScalar(0.6 + 0.4 * fall);
    }
    // カメラ
    const cam = (pos, look, fov) => { C.fov = fov; C.position.set(...pos); C.lookAt(...look); };
    const cu = (yaw = 0, dist = 3.4, fov = 42, dy = 0.2) => { bf.root.updateMatrixWorld(true); const hp = new THREE.Vector3(); bf.head.getWorldPosition(hp);
      const h = bf.root.rotation.y + yaw, d = new THREE.Vector3(Math.sin(h), 0, Math.cos(h)); C.fov = fov; C.position.set(hp.x + d.x * dist, hp.y + 0.1 + dy, hp.z + d.z * dist); C.lookAt(hp.x, hp.y + dy * 0.5, hp.z); };
    const POV = () => cam([0, 1.36, 6.33], [0, 1.55, 0], 58);   // 三脚のカメラから見た絵
    tc.g.visible = true; sun.target.position.set(0, 0, 2);
    if (tIn < E.s2) cam([6.0, 2.3, 9.8], [-0.4, 1.4, 1.6], 42);
    else if (tIn < E.s5) { POV(); tc.g.visible = false; }
    else if (tIn < E.s6) cam([-6.0, 2.2, 9.6], [0.6, 1.6, 2.6], 50);
    else if (tIn < E.s7) cam([3.0, 1.9, 4.6], [0, 1.55, 7.2], 46);
    else if (tIn < E.s8) { POV(); tc.g.visible = false; }
    else if (tIn < E.s9) { cu(0, 3.3, 44, 0.25); }
    else if (tIn < E.s10) cam([3.4, 2.3, 11.2], [0.2, 1.4, 4.0], 46);   // ビッグフェイスの斜め後ろから、手まねきするみんな
    else if (tIn < E.eye) { POV(); tc.g.visible = false; }
    else { cam([EX, 1.4, 9.0], [EX, 0.75, 0], 36); sun.position.set(EX + 6, 10, 8); sun.target.position.set(EX, 0, 0); }
    if (tIn < E.eye) sun.position.set(5, 11, 8);
    C.updateProjectionMatrix();
  };
}

// ==== EP.04『ビッグフェイスのぼうし』：帽子屋 → 植木鉢をかぶって帰る → 雨 → 翌朝、芽が出る → 窓辺に置いて水をやる
function hatShop(sc, ox) {   // 帽子屋の中（ox：x方向にずらして置く）
  const g = new THREE.Group(); g.position.x = ox; sc.add(g);
  const woodT = grain(0xB08A66, 256, 256, 18), wallT = grain(0xEAD9C6, 256, 256, 10);
  mesh(new THREE.PlaneGeometry(14, 24), toon(0xffffff, { map: woodT }), g, [0, 0.012, 6], { rot: [-Math.PI / 2, 0, 0], cast: false });
  mesh(new THREE.PlaneGeometry(14, 6), toon(0xffffff, { map: wallT }), g, [0, 3, -4], { cast: false });
  mesh(new THREE.PlaneGeometry(12, 6), toon(0xffffff, { map: wallT }), g, [-6, 3, 2], { rot: [0, Math.PI / 2, 0], cast: false });
  mesh(new THREE.PlaneGeometry(12, 6), toon(0xffffff, { map: wallT }), g, [6, 3, 2], { rot: [0, -Math.PI / 2, 0], cast: false });
  const wood = toon(0x9A7454), hatC = [0x7C6A5C, 0xC98A6A, 0x8FA5B8, 0xD9C27A, 0x6E8A6A, 0xB98AA8, 0x5E5A55];
  [1.0, 1.9, 2.8].forEach((y, r) => { mesh(new THREE.BoxGeometry(5.6, 0.08, 0.6), wood, g, [0, y, -3.6], { line: 0.03 });
    for (let k = 0; k < 7; k++) { const x = -2.4 + k * 0.8, c = toon(hatC[(k + r * 2) % 7]);
      mesh(new THREE.CylinderGeometry(0.26, 0.26, 0.03, 16), c, g, [x, y + 0.06, -3.55], { line: 0.04 }); mesh(new THREE.CylinderGeometry(0.15, 0.17, 0.2, 14), c, g, [x, y + 0.17, -3.55], { line: 0.05 }); } });
  mesh(new THREE.BoxGeometry(2.4, 1.0, 0.8), wood, g, [3.6, 0.5, -1.6], { line: 0.02 });   // カウンター
  mesh(new THREE.BoxGeometry(1.3, 2.4, 0.08), toon(0x9A7454), g, [-4.6, 1.5, -3.2], { line: 0.03 }); mesh(new THREE.PlaneGeometry(1.1, 2.2), toon(0xD8E2E4), g, [-4.6, 1.5, -3.15], { cast: false });   // 鏡
  // サイズの札（S M L XL）：台の上
  mesh(new THREE.BoxGeometry(2.6, 0.8, 0.6), wood, g, [-2.0, 0.4, 0.4], { line: 0.02 });
  ["S", "M", "L", "XL"].forEach((t, i) => mesh(new THREE.PlaneGeometry(0.42, 0.26), new THREE.MeshBasicMaterial({ map: signTex(t, 168, 104, "#F3E8D4", "#343B3A", 0.7) }), g, [-2.9 + i * 0.6, 0.62, 0.72], { cast: false }));
  return g;
}
function room(sc, ox) {   // ビッグフェイスの部屋（朝）
  const g = new THREE.Group(); g.position.x = ox; sc.add(g);
  const wallT = grain(0xF0E6D6, 256, 256, 8), floorT = grain(0xC8A782, 256, 256, 16);
  mesh(new THREE.PlaneGeometry(14, 20), toon(0xffffff, { map: floorT }), g, [0, 0.012, 6], { rot: [-Math.PI / 2, 0, 0], cast: false });
  const wall = toon(0xffffff, { map: wallT }), wood = toon(0xA9805E);
  // 奥の壁に窓（x -0.9〜0.9, y 1.1〜2.7）
  mesh(new THREE.BoxGeometry(4.6, 5, 0.2), wall, g, [-3.8, 2.5, -3], {}); mesh(new THREE.BoxGeometry(4.6, 5, 0.2), wall, g, [3.8, 2.5, -3], {});   // 大きな窓（x -1.5〜1.5, y 0.3〜3.3）
  mesh(new THREE.BoxGeometry(3.0, 0.3, 0.2), wall, g, [0, 0.15, -3], {}); mesh(new THREE.BoxGeometry(3.0, 1.7, 0.2), wall, g, [0, 4.15, -3], {});
  mesh(new THREE.BoxGeometry(3.2, 0.1, 0.4), wood, g, [0, 0.32, -2.9], { line: 0.03 });
  [[-1.55, 1.8], [1.55, 1.8]].forEach(([x, y]) => mesh(new THREE.BoxGeometry(0.12, 3.1, 0.26), wood, g, [x, y, -2.95], { line: 0.03 }));
  mesh(new THREE.BoxGeometry(3.2, 0.12, 0.26), wood, g, [0, 3.32, -2.95], { line: 0.03 }); mesh(new THREE.BoxGeometry(0.06, 3.0, 0.06), wood, g, [0, 1.8, -2.95], {});
  mesh(new THREE.PlaneGeometry(30, 14), new THREE.MeshBasicMaterial({ color: 0xF6E2C0 }), g, [0, 3, -9], { cast: false });   // 外は朝の光
  [[-2.5, 0.8], [2.8, 1.1], [0.6, 0.6]].forEach(([x, r]) => mesh(new THREE.SphereGeometry(r, 12, 8), new THREE.MeshBasicMaterial({ color: 0xBFD3A8 }), g, [x, 0.9, -8], { cast: false }));
  mesh(new THREE.PlaneGeometry(12, 5), wall, g, [-5.8, 2.5, 2], { rot: [0, Math.PI / 2, 0], cast: false });
  mesh(new THREE.BoxGeometry(2.2, 0.5, 1.2), toon(0xD8CDBE), g, [-3.6, 0.25, -1.6], { line: 0.02 }); mesh(new THREE.BoxGeometry(2.2, 0.2, 1.2), toon(0x9DB3C8), g, [-3.6, 0.6, -1.6], { line: 0.02 });   // ベッド
  return g;
}
function flowerPot(parent) {   // 大きな植木鉢（素焼き）。上下さかさにかぶる
  const g = new THREE.Group(); parent.add(g);
  const terra = toon(0xC9785E, { side: THREE.DoubleSide }), dark = new THREE.MeshBasicMaterial({ color: 0x3A2A22 });
  mesh(new THREE.CylinderGeometry(1.3, 0.95, 1.25, 28, 1, true), terra, g, [0, 0, 0], { line: 0.015 });
  mesh(new THREE.TorusGeometry(1.3, 0.09, 8, 32), terra, g, [0, 0.62, 0], { rot: [Math.PI / 2, 0, 0], line: 0.02 });   // 縁
  const bottom = mesh(new THREE.CircleGeometry(0.95, 28), terra, g, [0, -0.625, 0], { rot: [Math.PI / 2, 0, 0] });
  mesh(new THREE.CircleGeometry(0.11, 14), dark, g, [0, -0.63, 0], { rot: [Math.PI / 2, 0, 0], cast: false });   // 鉢底の穴（外側）
  const soil = mesh(new THREE.CircleGeometry(1.22, 28), toon(0x6A4A36), g, [0, 0.5, 0], { rot: [-Math.PI / 2, 0, 0], cast: false }); soil.visible = false;
  return { g, soil };
}
function sproutM(parent) {
  const g = new THREE.Group(); parent.add(g); const lf = toon(0x8FC27A);
  mesh(new THREE.CylinderGeometry(0.022, 0.026, 0.28, 6), lf, g, [0, 0.14, 0], { line: 0.15 });
  [-1, 1].forEach(s => mesh(new THREE.SphereGeometry(0.09, 10, 8), lf, g, [s * 0.09, 0.3, 0], { scale: [1.3, 0.35, 0.8], rot: [0, 0, s * 0.4], line: 0.08 }));
  return g;
}
function makeRain(sc, n = 1300) {
  const rain = new THREE.InstancedMesh(new THREE.BoxGeometry(0.012, 0.4, 0.012), new THREE.MeshBasicMaterial({ color: 0xE3ECF0, transparent: true, opacity: 0.42, depthWrite: false }), n);
  rain.frustumCulled = false; sc.add(rain);
  const rr = (i, k) => { const x = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return x - Math.floor(x); }, d = new THREE.Object3D();
  return { rain, set(t, cx, cz, amt) { for (let i = 0; i < n; i++) { const Hh = 8, sp = 9.5 + rr(i, 3) * 2, y = 3.5 + Hh / 2 - ((t * sp + rr(i, 2) * Hh) % Hh);
    d.position.set(cx + (rr(i, 0) - 0.5) * 9, y, cz + (rr(i, 1) - 0.5) * 9); if (rr(i, 4) > amt || d.position.distanceTo(C.position) < 2.6) d.position.y = -60;
    d.rotation.set(0, 0, 0.06); d.updateMatrix(); rain.setMatrixAt(i, d.matrix); } rain.instanceMatrix.needsUpdate = true; } };
}
function ep04(p) {
  const E = EP04;
  const sc = S = new THREE.Scene();
  sc.background = new THREE.Color(0xBFDDEB); sc.fog = new THREE.Fog(0xBFDDEB, 22, 70);
  const hemi = new THREE.HemisphereLight(0xFFF8EC, 0xA8B890, 1.15); sc.add(hemi);
  const sun = new THREE.DirectionalLight(0xFFF2DE, 1.5); sun.position.set(5, 11, 8); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 6; sun.shadow.bias = -0.0008; sun.shadow.normalBias = 0.05;
  Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 9, bottom: -6, near: 1, far: 40 }); sc.add(sun); sc.add(sun.target);
  const SHOP = 40, ROOM = 80;   // 帽子屋は x=40、部屋は x=80、帰り道（公園）は x=0
  park(sc); hatShop(sc, SHOP); room(sc, ROOM);
  const rain = makeRain(sc);
  // 店員（脚立の上で帽子をのせる）
  const clerk = person(sc, { h: 1.6, coat: 0x8FA5B8, pants: 0x55606A, apron: true, hair: 0x5A3A2A });
  const ladder = new THREE.Group(); sc.add(ladder); const lw = toon(0xB59A6E);
  [-0.28, 0.28].forEach(x => mesh(new THREE.BoxGeometry(0.06, 1.3, 0.06), lw, ladder, [x, 0.65, 0], { line: 0.05 }));
  [0.35, 0.7, 1.05, 1.28].forEach(y => mesh(new THREE.BoxGeometry(0.62, 0.05, 0.3), lw, ladder, [0, y, 0], { line: 0.05 }));
  const hats = [0.26, 0.33, 0.41, 0.5].map((r, i) => { const g = new THREE.Group(); sc.add(g); const c = toon([0x7C6A5C, 0xC98A6A, 0x8FA5B8, 0x6E8A6A][i]);
    mesh(new THREE.CylinderGeometry(r, r, 0.03, 18), c, g, [0, 0.015, 0], { line: 0.04 }); mesh(new THREE.CylinderGeometry(r * 0.58, r * 0.62, r * 0.75, 16), c, g, [0, r * 0.4, 0], { line: 0.05 });
    mesh(new THREE.CylinderGeometry(r * 0.63, r * 0.63, r * 0.12, 16), toon(0x343B3A), g, [0, r * 0.12, 0], {}); return g; });
  const bf = bigFace(sc), skinM = toon(PAL.face), pot = flowerPot(sc), sp = sproutM(sc), can = new THREE.Group(); sc.add(can);
  mesh(new THREE.CylinderGeometry(0.2, 0.22, 0.34, 16), toon(0x8FA5B8), can, [0, 0, 0], { line: 0.05 }); mesh(new THREE.CylinderGeometry(0.02, 0.035, 0.42, 8), toon(0x8FA5B8), can, [0.26, 0.08, 0], { rot: [0, 0, -0.9], line: 0.1 });
  const stream = mesh(new THREE.CylinderGeometry(0.012, 0.012, 1, 6), new THREE.MeshBasicMaterial({ color: 0xCFE6F2, transparent: true, opacity: 0.8 }), sc, [0, -10, 0], { cast: false });
  const fore = [0, 1].map(() => { const g = new THREE.Group(); bf.body.add(g); mesh(new THREE.CapsuleGeometry(0.065, 0.14, 4, 10), skinM, g, [0, -0.13, 0], { line: 0.12 });
    const hand = mesh(new THREE.SphereGeometry(0.095, 12, 10), skinM, bf.body, [0, 0, 0], { line: 0.1 }); g.visible = hand.visible = false; return { g, hand }; });
  const drops = Array.from({ length: 6 }, () => mesh(new THREE.SphereGeometry(0.02, 8, 6), new THREE.MeshBasicMaterial({ color: 0xF4F8FA }), bf.head, [0, 0, 0], { scale: [1, 1.4, 0.6], cast: false }));
  const surf = (x, y) => Math.sqrt(Math.max(0.02, 1 - (x / 1.12) ** 2 - y * y));
  // アイキャッチ
  const EX = -60, EYEC = 0xF1E4CC;
  mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: EYEC }), sc, [EX, 0.001, 0], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false });
  mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: EYEC }), sc, [EX, 10, -4], { cast: false, recv: false });
  const blob = mesh(new THREE.CircleGeometry(0.75, 32), new THREE.MeshBasicMaterial({ color: 0xC9B79C, transparent: true, opacity: 0.6 }), sc, [EX, 0.01, 0], { rot: [-Math.PI / 2, 0, 0], cast: false, recv: false });
  const bf2 = bigFace(sc); bf2.root.position.set(EX, 0, 0);
  // ビッグフェイスの場所
  function bfPath(t) {
    if (t < E.s4) return [SHOP + 0.4, 0.6, 0, false];
    if (t < E.s6) { const u = seg(t, E.s4, E.s6); return [lerp(-0.4, 0.3, u) + 0.0, lerp(0.5, 9.5, u), 0, true]; }   // 帰り道：こちらへ歩いてくる
    if (t < E.s7) return [ROOM + 0.2, -0.6, 0, false];
    if (t < E.s8) { const u = ease(seg(t, E.lift + 0.2, E.place)); return [ROOM + 0.2, lerp(-0.6, -0.1, u), lerp(0, Math.PI, ease(seg(t, E.lift + 0.6, E.place - 0.3))), false]; }
    if (t < E.s9) return [ROOM + 0.9, -0.3, Math.PI - 0.5, false];
    return [ROOM + 0.9, -0.3, lerp(Math.PI - 0.5, Math.PI + 0.15, ease(seg(t, E.s9, E.s9 + 0.6))), false];
  }
  const head = { x: 0, v: 0 }; let lastT = -1, prevV = 0, phase = 0, gaitW = 0;
  const aim = (g, from, to) => { const d = to.clone().sub(from), len = d.length(); g.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), d.normalize()); g.scale.set(1, Math.max(0.5, len / 0.27), 1); };
  function arm(i, hg) {   // 体ローカルの hg に手をのばす（頭をよける）
    const sx = i ? 1 : -1, sh = new THREE.Vector3(sx * 0.36, 0.78, 0); bf.root.updateMatrixWorld(true);
    const HCw = new THREE.Vector3(); bf.head.getWorldPosition(HCw); const HC = bf.body.worldToLocal(HCw.clone());
    const push = (q, m = 1.3) => { const v = q.clone().sub(HC), dd = Math.hypot(v.x / 1.12, v.y, v.z); return dd >= m ? q : HC.clone().add(v.multiplyScalar(m / Math.max(dd, 1e-3))); };
    const el = push(sh.clone().lerp(hg, 0.5).add(new THREE.Vector3(sx * 0.35, 0, 0.1)));
    aim(bf.arms[i], sh, el); fore[i].g.visible = fore[i].hand.visible = true; fore[i].g.position.copy(el); aim(fore[i].g, el, hg); fore[i].hand.position.copy(hg); }
  return (t) => {
    const dt = 1 / 120;
    if (lastT < 0 || t < lastT - 1e-6) { lastT = 0; prevV = 0; head.x = head.v = 0; phase = gaitW = 0; }
    while (lastT + dt <= t + 1e-6) { const a = bfPath(lastT), b = bfPath(lastT + dt);
      const v = Math.min(3, Math.hypot(b[0] - a[0], b[1] - a[1]) / dt), acc = THREE.MathUtils.clamp((v - prevV) / dt, -20, 20); prevV = v;
      const w = 2 * Math.PI * 2.0, z = 0.58, tg = THREE.MathUtils.clamp(-acc * 0.02, -0.17, 0.17);
      head.v += (-w * w * (head.x - tg) - 2 * z * w * head.v) * dt; head.x += head.v * dt;
      gaitW += ((a[3] ? 1 : 0) - gaitW) * (1 - Math.exp(-dt / 0.065)); if (a[3]) phase += v * dt / 0.36 * Math.PI; lastT += dt; }
    const [x, z, hd] = bfPath(t);
    bf.root.position.set(x, 0, z); bf.root.rotation.y = hd; walkPose(bf, phase, gaitW, 0.45);
    let pitch = head.x, roll = 0; const st = bf.st; st.look = [0, 0]; st.blink = 0; st.mouth = 0; st.sq = 0; st.happy = 0; st.wink = [0, 0];
    const blink = (tb) => { if (t > tb && t < tb + 0.14) st.blink = Math.sin(seg(t, tb, tb + 0.14) * Math.PI); };
    bf.arms.forEach(a => { a.rotation.set(0, 0, 0); a.scale.set(1, 1, 1); a.quaternion.identity(); }); fore.forEach(f => { f.g.visible = f.hand.visible = false; });
    // 帽子：順番に頭のてっぺんへ（小さすぎてちょこんと乗る）→ 店員がもどす
    bf.root.updateMatrixWorld(true); const topW = new THREE.Vector3(); bf.head.getWorldPosition(topW); topW.y += 0.98;
    const CL = new THREE.Vector3(SHOP + 1.55, 0, 0.75); ladder.position.set(CL.x, 0, CL.z); ladder.rotation.y = -0.4;
    clerk.root.position.set(CL.x, 1.3, CL.z); clerk.root.rotation.set(0, -0.9, 0); clerk.arms.forEach(a => a.rotation.set(0, 0, 0)); clerk.legs.forEach(l => l.rotation.set(0, 0, 0)); clerk.neck.rotation.set(0, 0, 0); clerk.st.blink = 0;
    const handW = new THREE.Vector3(CL.x - 0.35, 2.75, CL.z - 0.05);
    hats.forEach((h, i) => { const t0 = [E.h1, E.h2, E.h3, E.h4][i]; const up = ease(seg(t, t0, t0 + 0.6)), down = ease(seg(t, t0 + 1.25, t0 + 1.7));
      if (t < E.s2 || t >= E.s3 || t < t0 - 0.3 || down >= 1) { h.position.set(SHOP - 2.9 + i * 0.6, t < t0 ? 0.82 : -20, 0.3); h.rotation.set(0, 0, 0); return; }
      const on = up * (1 - down), p0 = new THREE.Vector3(SHOP - 2.9 + i * 0.6, 0.82, 0.3).lerp(handW, ease(seg(t, t0 - 0.3, t0)));
      const pos = p0.clone().lerp(topW, on); pos.y += Math.sin(Math.PI * on) * 0.25; h.position.copy(pos); h.rotation.set(0, 0, 0.05 * Math.sin(t * 9) * on);
      if (on > 0.05) clerk.arms[0].rotation.x = -2.6 * Math.min(1, on * 2); });
    // 植木鉢：店員がころがして持ってくる → ビッグフェイスが腕を伸ばして持ちあげ、さかさにかぶる
    let potOn = 0, potWorld = null;
    if (t >= E.s3 && t < E.s4) {
      const r = ease(seg(t, E.roll, E.grab - 0.2)), lift = ease(seg(t, E.grab, E.potOn)), onH = ease(seg(t, E.potOn - 0.25, E.potOn + 0.15));
      if (lift <= 0) { pot.g.position.set(SHOP + lerp(4.8, 1.5, r), 1.3, 1.6); pot.g.rotation.set(0, 0, Math.PI / 2 + (1 - r) * 6); }
      else { const a = new THREE.Vector3(SHOP + 1.5, 1.3, 1.6), b = topW.clone().add(new THREE.Vector3(0, 0.25, 0)), m = new THREE.Vector3(SHOP + 1.4, 4.3, 1.2);
        const pp = a.clone().lerp(m, lift).lerp(m.clone().lerp(b, lift), lift); pot.g.position.copy(pp); pot.g.rotation.set(0, 0, lerp(Math.PI / 2, Math.PI, lift)); potWorld = pp;
        if (lift < 1) { const hl = bf.body.worldToLocal(pp.clone().add(new THREE.Vector3(-1.2, 0, 0))), hr = bf.body.worldToLocal(pp.clone().add(new THREE.Vector3(1.2, 0, 0))); arm(0, hl); arm(1, hr); } }
      potOn = onH;
      clerk.root.position.set(SHOP + lerp(5.6, 2.5, r), 0, 1.6 + 0.7); clerk.root.rotation.y = -Math.PI / 2; walkPose(clerk, t * 12, r > 0 && r < 1 ? 1 : 0, 0.5); clerk.arms[0].rotation.x = clerk.arms[1].rotation.x = -1.2 * (1 - lift);
      ladder.position.y = -20; }
    if (t >= E.s4 && t < E.s7) potOn = 1;
    if (potOn > 0 && !(t >= E.s3 && t < E.potOn)) { pot.g.position.copy(topW).add(new THREE.Vector3(0, 0.08, 0)); pot.g.rotation.set(0, bf.root.rotation.y, Math.PI); }
    if (t < E.s3) pot.g.position.set(SHOP + 9, -20, 0);
    // 顔
    if (t < E.s2) { blink(2.4); st.look = [-0.4, 0.3]; }
    if (t >= E.s2 && t < E.s3) { const k = [E.h1, E.h2, E.h3, E.h4].filter(h => t > h + 0.5).length; st.look = [0, 0.8 * (t % 1.9 < 1.3 && k > 0 ? 1 : 0)]; st.mouth = 0.1 * k; blink(E.h2 + 1.4); blink(E.h4 + 1.4);
      if (t > E.h4 + 0.7) pitch += 0.06; }
    if (t >= E.s3 && t < E.s4) { st.look = [0.6 * ease(seg(t, E.roll + 0.3, E.roll + 0.6)), -0.3]; if (t > E.potOn) { st.happy = ease(seg(t, E.smile, E.smile + 0.4)); st.look = [0, 0.6]; } st.sq = 0.05 * Math.exp(-Math.max(0, t - E.potOn) * 6) * (t > E.potOn ? 1 : 0); }
    if (t >= E.s4 && t < E.s5) { st.happy = 1 - ease(seg(t, E.rain + 0.6, E.rain + 1.2)) * 0.5; if (t > E.rain + 0.8) st.look = [0, 0.7]; blink(E.rain + 1.4); }
    let wet = 0;
    if (t >= E.s5 && t < E.s6) { wet = 1; st.wink = [0.4, 0.4]; st.look = [0, 0.5]; blink(E.drip + 0.5); blink(E.drip + 1.9); st.mouth = 0.2; }
    if (t >= E.s6 && t < E.s7) { st.look = [0, 0.95 * ease(seg(t, E.notice, E.notice + 0.25))]; blink(E.s6 + 0.8); if (t > E.notice + 0.8) st.happy = ease(seg(t, E.notice + 0.8, E.notice + 1.2)); }
    if (t >= E.s7 && t < E.s8) { st.happy = 0.6; st.look = [0, -0.4]; blink(E.place + 0.5); }
    if (t >= E.s8 && t < E.s9) { st.happy = 0.8; st.look = [0, -0.6]; pitch += 0.12; blink(E.water + 1.0); }
    if (t >= E.s9 && t < E.eye) { st.happy = ease(seg(t, E.final, E.final + 0.4)); blink(E.s9 + 0.3); }
    bf.neck.rotation.x = pitch; bf.neck.rotation.z = roll; bf.setFace();
    drops.forEach((d, k) => { const u = (t * 0.8 + k * 0.17) % 1, xx = (k % 2 ? 1 : -1) * (0.2 + 0.12 * k), yy = 0.35 - 0.95 * u; d.visible = wet > 0 && t < E.eye; d.position.set(xx, yy, surf(xx, yy) + 0.01); });
    // 芽：朝、鉢底の穴から出る → 窓辺では土から
    sp.visible = false;
    if (t >= E.s6 && t < E.lift + 0.6) { sp.visible = true; sp.position.copy(pot.g.position).add(new THREE.Vector3(0, 0.63, 0)); sp.scale.setScalar(0.05 + 0.95 * ease(seg(t, E.sprout, E.sprout + 1.4))); }
    // 持ちあげて、ひっくり返して窓辺へ（腕が伸びる）
    if (t >= E.s7 && t < E.eye) {
      const up = ease(seg(t, E.lift, E.lift + 0.6)), flip = ease(seg(t, E.lift + 0.5, E.place - 0.2)), set = ease(seg(t, E.place - 0.4, E.place + 0.2));
      const sill = new THREE.Vector3(ROOM + 0.1, 0.64, -2.05), above = topW.clone().add(new THREE.Vector3(0, 0.2 + 0.6 * up, 0));
      const pp = above.clone().lerp(sill.clone().add(new THREE.Vector3(0, 0.5, 0)), flip).lerp(sill, set); pot.g.position.copy(pp); pot.g.rotation.set(0, 0, Math.PI * (1 - flip));
      pot.soil.visible = flip > 0.5; potOn = 0;
      if (t < E.place + 0.5) { const hl = bf.body.worldToLocal(pp.clone().add(new THREE.Vector3(-1.25, 0, 0))), hr = bf.body.worldToLocal(pp.clone().add(new THREE.Vector3(1.25, 0, 0))); arm(0, hl); arm(1, hr); }
      if (flip > 0.5) { sp.visible = true; sp.position.copy(pp).add(new THREE.Vector3(0, 0.52, 0)); sp.scale.setScalar(1 + 0.25 * ease(seg(t, E.water + 0.6, E.waterEnd + 0.6))); } }
    // じょうろ
    can.position.set(0, -20, 0); stream.position.set(0, -20, 0);
    if (t >= E.s8 && t < E.s9) { const w = ease(seg(t, E.water - 0.6, E.water)) * (1 - ease(seg(t, E.waterEnd, E.waterEnd + 0.5)));
      const cp = new THREE.Vector3(ROOM - 0.25, 1.75 - 0.05 * w, -1.55); can.position.copy(cp); can.rotation.set(0, 0, -0.5 * w);
      arm(1, bf.body.worldToLocal(cp.clone().add(new THREE.Vector3(-0.15, 0.05, 0))));
      if (w > 0.8 && t < E.waterEnd) { stream.position.set(ROOM + 0.08, 1.45, -1.62); stream.scale.y = 0.42; stream.rotation.set(0, 0, 0.35); } }
    // 雨と空
    const rainAmt = t >= E.s4 && t < E.s6 ? ease(seg(t, E.rain, E.rain + 1.4)) : 0;
    rain.rain.visible = rainAmt > 0;
    // アイキャッチ
    if (t >= E.eye) {
      const k = t - E.eye, fall = Math.min(1, k / 0.32), y = 3.2 * (1 - fall * fall); bf2.root.position.y = y; const land = k - 0.32;
      bf2.st.look = [0, 0]; bf2.st.blink = 0; bf2.st.mouth = 0; bf2.st.happy = 1; bf2.st.sq = 0; let p2 = 0;
      if (land > 0) { bf2.st.sq = Math.max(-0.03, 0.08 * Math.exp(-land * 8) * Math.cos(land * 24)); p2 = 0.06 * Math.exp(-land * 5) * Math.sin(land * 16); bf2.body.scale.set(1 + 0.12 * Math.exp(-land * 12), 1 - 0.12 * Math.exp(-land * 12), 1); }
      if (k > 1.6 && k < 1.74) bf2.st.blink = Math.sin(seg(k, 1.6, 1.74) * Math.PI);
      bf2.neck.rotation.x = p2; bf2.neck.rotation.z = 0.09 * ease(seg(k, 1.0, 1.35)); bf2.setFace(); blob.scale.setScalar(0.6 + 0.4 * fall);
    }
    // カメラと光
    const cam = (pos, look, fov) => { C.fov = fov; C.position.set(...pos); C.lookAt(...look); };
    const cu = (yaw = 0, dist = 3.4, fov = 42, dy = 0.2) => { bf.root.updateMatrixWorld(true); const hp = new THREE.Vector3(); bf.head.getWorldPosition(hp);
      const h = bf.root.rotation.y + yaw, d = new THREE.Vector3(Math.sin(h), 0, Math.cos(h)); C.fov = fov; C.position.set(hp.x + d.x * dist, hp.y + 0.1 + dy, hp.z + d.z * dist); C.lookAt(hp.x, hp.y + dy * 0.5, hp.z); return hp; };
    let bg = 0xBFDDEB, hi = 1.15, si = 1.5, sp_ = [5, 11, 8], tg = [0, 0, 2];
    if (t < E.s2) { cam([SHOP + 3.4, 2.6, 7.4], [SHOP - 0.4, 1.6, -0.6], 46); bg = 0xEAD9C6; sp_ = [SHOP + 3, 9, 6]; tg = [SHOP, 0, 0]; }
    else if (t < E.s3) { cam([SHOP + 0.9, 2.3, 7.6], [SHOP + 0.75, 2.2, 0.4], 40); bg = 0xEAD9C6; sp_ = [SHOP + 3, 9, 6]; tg = [SHOP, 0, 0]; }
    else if (t < E.s4) { cam([SHOP + 1.4, 2.6, 9.0], [SHOP + 1.4, 2.3, 0.8], 46); bg = 0xEAD9C6; sp_ = [SHOP + 3, 9, 6]; tg = [SHOP, 0, 0]; }
    else if (t < E.s5) { const k = seg(t, E.s4, E.s5); cam([0.6, 2.2, 14.5], [0, 2.0, 5.0 + 3 * k], 40); const dk = rainAmt; bg = 0xBFDDEB; hi = lerp(1.15, 0.85, dk); si = lerp(1.5, 0.45, dk); rain.set(t, 0, 9, rainAmt); }
    else if (t < E.s6) { cu(0, 4.4, 46, 0.25); hi = 0.85; si = 0.45; rain.set(t, x, z, 1); }
    else if (t < E.s7) { cam([ROOM + 0.2, 3.0, 4.2], [ROOM + 0.2, 3.0, -0.6], 44); bg = 0xF0E6D6; sp_ = [ROOM + 2, 7, 6]; tg = [ROOM, 0, -1]; si = 1.0; hi = 1.5; }
    else if (t < E.s8) { cam([ROOM + 4.4, 2.6, 4.6], [ROOM, 1.8, -1.2], 48); bg = 0xF0E6D6; sp_ = [ROOM + 2, 7, 6]; tg = [ROOM, 0, -1]; si = 1.0; hi = 1.5; }
    else if (t < E.s9) { cam([ROOM + 5.4, 2.0, -0.4], [ROOM + 0.2, 1.5, -1.6], 44); bg = 0xF0E6D6; sp_ = [ROOM + 2, 7, 6]; tg = [ROOM, 0, -1]; si = 1.0; hi = 1.5; }   // 横から：じょうろと鉢
    else if (t < E.eye) { cam([ROOM + 0.1, 1.55, -4.8], [ROOM + 0.75, 1.75, -0.3], 40); bg = 0xF0E6D6; sp_ = [ROOM - 2, 6, -8]; tg = [ROOM, 0, -1]; si = 1.0; hi = 1.5; }   // 窓辺の芽ごしに顔
    else { cam([EX, 1.4, 9.0], [EX, 0.75, 0], 36); bg = 0xF1E4CC; sp_ = [EX + 6, 10, 8]; tg = [EX, 0, 0]; }
    sc.background.setHex(bg); sc.fog.color.setHex(bg); hemi.intensity = hi; sun.intensity = si; sun.position.set(...sp_); sun.target.position.set(...tg);
    C.updateProjectionMatrix();
  };
}

// ==== チャンネルの絵（ヘッダー 2560x1440／アイコン 800x800）。p.kind = "banner" | "icon"
function art(p) {
  const sc = S = new THREE.Scene();
  const bg = p.kind === "icon" ? 0xF1E4CC : 0xE6EEE8; sc.background = new THREE.Color(bg);
  const hemi = new THREE.HemisphereLight(0xFFF6EA, 0xD8C7B2, 1.15); sc.add(hemi);
  const sun = new THREE.DirectionalLight(0xFFF0DC, 1.6); sun.position.set(6, 10, 8); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 6; sun.shadow.bias = -0.0008; sun.shadow.normalBias = 0.05;
  Object.assign(sun.shadow.camera, { left: -9, right: 9, top: 7, bottom: -5, near: 1, far: 30 }); sc.add(sun); sc.add(sun.target);
  if (p.kind !== "icon") bakery(sc);
  const bf = bigFace(sc); bf.root.position.set(0, 0, 1.7); bf.st.happy = 1; bf.st.look = [0, 0]; bf.setFace();
  return () => {
    C.fov = p.fov; C.position.set(...p.cam); C.lookAt(...p.look); C.updateProjectionMatrix();
  };
}
const SCENES = { ep01_test: ep01Test, ep01: ep01, ep02, ep03, ep04, art };
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
// 看板の文字（Zen Maru Gothic Bold）を読みこんでから始める
{ const buf = await fetch("fonts/ZenMaruGothic-Bold.ttf").then(r => r.arrayBuffer()); const ff = new FontFace("ZenMaru", buf); await ff.load(); document.fonts.add(ff); }
window.ready = true;
