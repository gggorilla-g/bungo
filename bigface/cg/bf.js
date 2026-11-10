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
  mesh(new THREE.BoxGeometry(1.3, 0.42, 0.06), wood, sc, [X, 3.05, 0.04], { line: 0.03 });
  mesh(new THREE.PlaneGeometry(1.22, 0.35), new THREE.MeshBasicMaterial({ map: signTex("うらぐち", 512, 148, "#9A7656") }), sc, [X, 3.05, 0.075], { cast: false });
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
    if (t < E.s6) { // 行列のほうを見て、少し横へよける
      const side = ease(seg(t, E.s5 + 1.5, E.s5 + 2.3)), turn = ease(seg(t, E.s5 + 0.35, E.s5 + 0.9)) * (1 - ease(seg(t, E.s5 + 1.2, E.s5 + 1.7)));
      const lookKid = ease(seg(t, E.kid_say - 0.2, E.kid_say + 0.2));
      return [lerp(0, -1.5, side), 1.7 + 0.2 * side, H_DOOR - turn * 1.9 + lookKid * 0.6, t > E.s5 + 1.5 && t < E.s5 + 2.3]; }
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
  const kidPos = t => { // 子ども：扉の内側に出てくる → 窓の中（台の上の椅子）
    if (t < E.s5 + 1.6) return [0, -30, 0, 0];
    if (t < E.s6) { const u = ease(seg(t, E.s5 + 1.7, E.s5 + 2.4)); return [0, lerp(-1.6, -0.55, u), 0, u > 0 && u < 1]; }
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
  const folkSpot = [[1.3, 2.7], [1.9, 3.5], [2.5, 4.3]];
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
    if (t > E.s5 && t < E.s6) { st.look = [1 * ease(seg(t, E.s5 + 0.15, E.s5 + 0.3)) * (1 - ease(seg(t, E.s5 + 1.1, E.s5 + 1.3))), 0];
      pitch += 0.16 * ease(seg(t, E.s5 + 0.9, E.s5 + 1.3)) * (1 - ease(seg(t, E.kid_say - 0.1, E.kid_say + 0.3))); blink(E.s5 + 2.2); blink(E.kid_say + 1.0);
      if (t > E.kid_say + 1.3) pitch += 0.08 * Math.sin(seg(t, E.kid_say + 1.3, E.kid_say + 1.6) * Math.PI) * (t < E.kid_say + 1.6 ? 1 : 0); }
    // s6：段ボールを見上げる →「……そっか。」
    if (t > E.s6 && t < E.s7) { const up = ease(seg(t, E.s6 + 2.8, E.s6 + 3.2)) * (1 - ease(seg(t, E.sokka - 0.3, E.sokka + 0.2))); st.look = [0, up]; pitch -= 0.22 * up; blink(E.s6 + 3.5);
      if (t > E.sokka) { pitch += 0.12 * ease(seg(t, E.sokka, E.sokka + 0.8)); st.mouth = 0.6; }
      if (t > E.sokka + 1.8) { const d = ease(seg(t, E.sokka + 1.8, E.sokka + 2.4)); st.look = [0, -0.7 * d]; pitch += 0.06 * d; bf.body.scale.setScalar(1 - 0.03 * d); blink(E.sokka + 1.55); blink(E.sokka + 2.9); } }   // ふり返って、目をふせる（しょんぼり）
    // s7：うつむいて歩く（SAD）→ 窓が開く音で止まる → 見る
    if (t > E.s7 && t < E.s8) { pitch += 0.2 * (1 - ease(seg(t, E.kid_say2 + 0.4, E.kid_say2 + 0.9))); bf.body.scale.setScalar(1 - 0.03 * (1 - ease(seg(t, E.kid_say2 + 0.4, E.kid_say2 + 0.9)))); st.look = [-0.6 * ease(seg(t, E.kid_say2 + 0.3, E.kid_say2 + 0.45)), 0]; blink(E.kid_say2 + 1.4); }
    else bf.body.scale.setScalar(1);
    // s8：パンを受けとる（腕を上げる）→ うれしい（頭が少し上がり、体が小さくはねる）
    let armUp = 0;
    if (t > E.s8 && t < E.give - 0.6) { const k = t - E.s8; st.look = [0.4 * Math.sin(Math.PI * Math.min(1, Math.max(0, seg(k, 3.0, 4.2)))), 0.3 * ease(seg(k, 2.8, 3.1)) * (1 - ease(seg(k, 4.6, 4.9)))]; roll = 0.06 * Math.sin(Math.PI * Math.min(1, Math.max(0, seg(k, 3.1, 4.3)))); blink(E.s8 + 3.7); }   // 待つ：奥をのぞく、少し首をかしげる
    if (t > E.give + 0.6 && t < E.s9) { st.look = [0, -0.6 * ease(seg(t, E.give + 0.6, E.give + 0.8)) * (1 - ease(seg(t, E.give + 1.4, E.give + 1.6))) ]; st.happy = ease(seg(t, E.give + 1.3, E.give + 1.5)); }   // パンを見て、うれしい
    if (t > E.s8 && t < E.s9) { armUp = ease(seg(t, E.give - 0.7, E.give)); const hp = seg(t, E.give + 1.45, E.give + 1.85); if (hp > 0 && hp < 1) { bf.body.position.y += 0.06 * Math.sin(hp * Math.PI); pitch -= 0.08 * Math.sin(hp * Math.PI); } blink(E.give + 1.4); }
    // s9：食べる（大きな頭がこくんと下がる）→ 最後のひとこと
    if (t >= E.s9) { armUp = t >= E.s10 ? 0.45 : 1; [E.bite1, E.bite2].forEach(tb => { const k = seg(t, tb, tb + 0.7); if (k > 0 && k < 1) pitch += 0.42 * Math.sin(k * Math.PI); }); blink(E.s9 + 0.6); blink(E.final + 1.6);
      if (t > E.s10) { blink(E.s10 + 0.7); const h = ease(seg(t, E.smile, E.smile + 0.35)); st.happy = h; pitch -= 0.05 * h; if (t > E.smile + 1.4) blink(E.smile + 1.6); } }   // 最後は顔：ほんの少し笑う（11/10 ゲンタさん「最後はビッグフェイスの表情で終わりたい」）
    bf.arms.forEach((a, i) => { a.rotation.x = -1.9 * armUp + a.rotation.x * (1 - armUp); a.rotation.z = (i ? -1 : 1) * 0.35 * armUp; });
    bf.neck.rotation.x = pitch; bf.neck.rotation.z = (t > E.s3 && t < E.s5) ? 0 : roll; bf.head.rotation.z = (t > E.s3 && t < E.s5) ? roll : 0; bf.setFace();
    // --- 子ども
    const [kx, kz, kh, kw] = kidPos(t); kid.root.position.set(kx, 0, kz); kid.root.rotation.y = kh; walkPose(kid, kphase, kw, 0.6);
    kid.root.position.y = kidY(t);            // 窓の中では椅子の上（パンを取りに行くあいだは床）
    stool.visible = t > E.s6;
    kid.arms[1].rotation.x = 0; kid.arms[0].rotation.x = 0; kid.arms[1].rotation.z = 0; kid.neck.rotation.set(0, 0, 0);
    if (t > E.kid_say && t < E.s6) { const u = ease(seg(t, E.kid_say, E.kid_say + 0.3)) * (1 - ease(seg(t, E.kid_say + 1.6, E.kid_say + 1.9))); kid.arms[0].rotation.z = 1.5 * u; kid.neck.rotation.y = 0.5 * u; }   // 横（裏）を指さす
    if (t > E.kid_say2 && t < E.s8 + 0.1) { const u = ease(seg(t, E.kid_say2, E.kid_say2 + 0.25)) * (1 - ease(seg(t, E.s8 - 0.25, E.s8 + 0.1))); kid.arms[0].rotation.x = -u * (1.3 + 0.45 * Math.sin((t - E.kid_say2) * 11)); }   // 言葉なし：窓から手招き（11/10 ゲンタさん「言葉なし」）
    if (t > E.s7 && t < E.s9) { kid.neck.rotation.x = 0.1; const k = t - E.s8;
      const reach = Math.sin(Math.PI * Math.min(1, Math.max(0, seg(k, 2.55, 3.15))));   // 棚に手をのばす
      const carry = ease(seg(k, 2.95, 3.25)) * (1 - ease(seg(k, 5.4, 5.6)));          // 右手にパン（左手は空）
      const hand = ease(seg(k, 5.5, 6.1)) * (1 - ease(seg(k, 6.7, 7.3)));             // 窓から差し出す（ゆっくり）
      kid.arms[0].rotation.x = -1.4 * reach; kid.arms[1].rotation.x = Math.min(-1.4 * reach, -0.7 * carry, -1.35 * hand); kid.neck.rotation.x = 0.1 - 0.3 * reach; }
    if (t >= E.s9) { [E.bite1 + 0.3, E.bite2 + 0.3].forEach(tb => { const k = seg(t, tb, tb + 0.9); if (k > 0 && k < 1) kid.neck.rotation.z = 0.12 * Math.sin(k * Math.PI); }); }   // 子どもは食べない。食べるのを見て、首を少しかしげる（11/10 ゲンタさん「店の人もパン食べてるのは意味がわからない」）
    kidBread2.position.set(0, -20, 0); kidBread.visible = false;
    // パン：子どもの右手 → ゆっくり手渡し → ビッグフェイスの手。かじるたびに小さく
    const bites = (t > E.bite1 + 0.35 ? 1 : 0) + (t > E.bite2 + 0.35 ? 1 : 0);
    kid.root.updateMatrixWorld(true); bf.root.updateMatrixWorld(true);
    const khand = new THREE.Vector3(0, -0.26 * kid.H, 0.08); kid.arms[1].localToWorld(khand);
    const bh = new THREE.Vector3(0, 0.98, 0.42); bf.root.localToWorld(bh);
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
      if (i === 0 && t > E.s5 + 0.6) f.arms[0].rotation.x = -1.2 * Math.sin(Math.min(1, seg(t, E.s5 + 0.6, E.s5 + 1.0)) * Math.PI / 2) * (1 - ease(seg(t, E.s5 + 2.4, E.s5 + 2.8)));   // 時計を見る
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
    else if (t < E.s6) { const k = ease(seg(t, E.s5, E.s6)); cam([-5.6 + 0.3 * k, 2.5, 10.2 - 0.5 * k], [-0.2, 1.6, 2.4], 48); }   // ゆっくり寄る
    else if (t < E.s7) cam([AX + 1.0, 1.9, 10.0], [AX + 0.25, 1.9, 0.8], 40);   // 斜め前から：段ボールを見上げる顔と「そっか」が見える（11/10 ゲンタさん「もう少し全体的にビッグフェイスの表情を見たい」）
    else if (t < E.s8) cam([2.2, 2.0, 11.5], [2.0, 2.0, 1.2], 42);
    else if (t < E.s9) { const k = t - E.s8;
      if (k > 3.0 && k < 3.95) { cam([1.95, 1.8, -3.6], [1.95, 1.9, 1.2], 36); BK.awn.visible = false; inside.intensity = 5; hemi.intensity = 1.15; sun.visible = false; }   // 待っている顔（窓の中から）
      else if (k > 0.8 && k < 4.95) { cam([4.1, 1.75, -0.45], [2.35, 1.1, -2.9], 60); inside.intensity = 5; hemi.intensity = 1.05; }   // 店の中から：子どもが奥の棚までパンを取りに行って戻る
      else cam([7.2, 2.1, 5.6], [2.3, 1.8, -0.2], 40); }   // 窓の桟が顔にかからないよう外側へ（Codex 指摘）
    else if (t >= E.eye) { cam([EX, 1.4, 9.0], [EX, 0.75, 0], 36); hemi.intensity = 1.2; }
    else if (t >= E.s10) { cam([1.95, 1.78, -3.9], [1.95, 1.88, 1.2], 33); BK.winL.rotation.y = -2.95; BK.winR.rotation.y = 2.95; BK.awn.visible = false; inside.intensity = 5; hemi.intensity = 1.15; sun.visible = false; }   // 窓の中（子どもの肩ごし）から顔：冒頭の「扉いっぱいの顔」と対   // 窓枠が額にかからないよう少し引いて低く（Codex 指摘）
    else { cam([16.0, 1.95, 0.25], [2.2, 1.92, 0.15], 32); BK.winL.rotation.y = -2.95; BK.winR.rotation.y = 2.95; BK.awn.visible = false; BK.nbR.visible = false; BK.inR.visible = false; inside.intensity = 4; }   // 左右対称：壁の真横から。開いた窓は壁にぴったり倒し、顔にかからないように（Codex 指摘）
    // 表情に寄る（アングルはそのまま、要所だけ顔のアップを挟む。11/10 ゲンタさん「裏口空いてなくてその時の表情に寄るとか。さっきのアングルにプラスで表情に寄る」）
    const cu = (yaw = 0.35, dist = 2.6, fov = 30, dy = 0.0) => {
      bf.root.updateMatrixWorld(true); const hp = new THREE.Vector3(); bf.head.getWorldPosition(hp);
      const h = bf.root.rotation.y + yaw, d = new THREE.Vector3(Math.sin(h), 0, Math.cos(h));
      C.fov = fov; C.position.set(hp.x + d.x * dist, hp.y + 0.05 + dy, hp.z + d.z * dist); C.lookAt(hp.x, hp.y - 0.05, hp.z);
      sun.visible = true; inside.intensity = 0; hemi.intensity = 1.15; BK.awn.visible = true; };
    if (t > E.sokka + 1.35 && t < E.s7) cu(0.0, 3.5, 50);                // 裏口があかない：ふり返った顔に寄る
    if (t > E.win - 0.05 && t < E.kid_say2 + 1.0) cu(0.25, 4.3, 54);    // 窓が開く音に気づく
    C.updateProjectionMatrix();
  };
}

const SCENES = { ep01_test: ep01Test, ep01: ep01 };
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
