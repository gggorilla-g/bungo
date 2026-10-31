// nazo/cg/scene.js — 妄想科学ショートの3DCG（四角いブロックだけで作る。色と形は自前）
// render_cg.js が Chromium で開き、window.setup(job) → window.frame(t) を1コマずつ呼んで書き出す。
// 場面（job.scene）:
//   land   … ブロックの島。太陽が回る。p: {cam, sun(1日の秒数), t0, wind, night, snow, hot, zunda}
//   flight … 地上→空→宇宙→月へ飛び、月がブロックに砕けて消える（カウントダウン用）
//   rewind … 月のない地球が逆回りし、星が逆に流れる（45億年前へ巻き戻す）
//   axis   … 地球の地軸がふらつく  p: {amp}
//   space  … 太陽と地球。月があるはずの所に何もない  p: {cam}
import * as THREE from "./node_modules/three/build/three.module.js";

let R, S, C, CUR, job, upd = () => {};
const rnd = (() => { let s = 12345; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
const ease = x => 1 - Math.pow(1 - Math.min(Math.max(x, 0), 1), 3);
const lerp = (a, b, u) => a + (b - a) * u;
const COL = {
  grass: 0x5cb85c, grass2: 0x4aa64a, dirt: 0x8b5a2b, sand: 0xe8d38a, sea: 0x2f7fd8, sea2: 0x3a8ee6,
  trunk: 0x7a4a24, leaf: 0x2e8b3a, leaf2: 0x3fa34d, snow: 0xf2f2f2, cloud: 0xffffff, sun: 0xffd23a,
  moon: 0xbdbdbd, moon2: 0x9a9a9a, rock: 0x8a8a8a, ice: 0xdff3ff, lava: 0xe8552a,
};

function box(geoCache, w, h, d) {
  const k = `${w},${h},${d}`;
  return geoCache[k] || (geoCache[k] = new THREE.BoxGeometry(w, h, d));
}

// 同じ大きさのブロックを大量に置く（InstancedMesh、色はブロックごと）
function blocks(list, size = 1, mat) {
  const g = new THREE.BoxGeometry(size, size, size);
  const m = mat || new THREE.MeshLambertMaterial();
  const im = new THREE.InstancedMesh(g, m, list.length);
  const o = new THREE.Object3D(), c = new THREE.Color();
  list.forEach((b, i) => {
    o.position.set(b[0], b[1], b[2]); o.updateMatrix(); im.setMatrixAt(i, o.matrix);
    im.setColorAt(i, c.setHex(b[3]));
  });
  im.instanceMatrix.needsUpdate = true; im.instanceColor.needsUpdate = true;
  return im;
}

// ブロックの球（地球・月）。殻だけ作る
function voxelPlanet(r, colorFn) {
  const list = [];
  for (let x = -r; x <= r; x++) for (let y = -r; y <= r; y++) for (let z = -r; z <= r; z++) {
    const d = Math.sqrt(x * x + y * y + z * z);
    if (d <= r && d > r - 1.8) list.push([x, y, z, colorFn(x / r, y / r, z / r)]);
  }
  return blocks(list);
}

function noise3(x, y, z) {   // 決まった模様のなめらかなでこぼこ（乱数ではないので毎回同じ形）
  return Math.sin(x * 3.1 + Math.sin(y * 2.3)) * 0.5 + Math.sin(y * 2.7 + z * 1.9) * 0.3 + Math.sin(z * 3.7 - x * 1.3) * 0.4;
}
const earthColor = (x, y, z) => {
  if (Math.abs(y) > 0.86) return COL.snow;
  const n = noise3(x, y, z);
  return n > 0.35 ? (n > 0.75 ? COL.dirt : COL.grass) : (n > 0.25 ? COL.sand : (n < -0.4 ? COL.sea : COL.sea2));
};
const moonColor = (x, y, z) => (noise3(x * 2, y * 2, z * 2) > 0.4 ? COL.moon2 : COL.moon);

function stars(n, r) {
  const g = new THREE.BufferGeometry(), p = [];
  for (let i = 0; i < n; i++) {
    const u = rnd() * 2 - 1, a = rnd() * Math.PI * 2, s = Math.sqrt(1 - u * u);
    p.push(r * s * Math.cos(a), r * u, r * s * Math.sin(a));
  }
  g.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({ color: 0xffffff, size: 2.2, sizeAttenuation: false }));
}

// ブロックのずんだもん風キャラ（色と形は自前。髪は緑、頭に枝豆の形のブロック）
function blockChar() {
  const g = new THREE.Group(), gc = {};
  const add = (w, h, d, x, y, z, col) => {
    const m = new THREE.Mesh(box(gc, w, h, d), new THREE.MeshLambertMaterial({ color: col }));
    m.position.set(x, y, z); g.add(m); return m;
  };
  add(1.0, 1.1, 0.6, 0, 0.55, 0, 0xf4f4f4);                  // 体（白）
  add(1.04, 0.16, 0.64, 0, 0.75, 0, 0x6fbf3a);               // 体の緑の帯
  add(0.3, 0.6, 0.3, -0.25, -0.3, 0, 0xf4f4f4); add(0.3, 0.6, 0.3, 0.25, -0.3, 0, 0xf4f4f4);   // 足
  add(1.3, 1.2, 1.2, 0, 1.75, 0, 0xffe2c8);                  // 顔
  add(1.4, 0.45, 1.3, 0, 2.45, -0.05, 0x7ccc3c);             // 髪（上）
  add(1.4, 1.1, 0.3, 0, 1.95, -0.62, 0x7ccc3c);              // 髪（後ろ）
  add(0.22, 0.32, 0.05, -0.3, 1.8, 0.61, 0x222222); add(0.22, 0.32, 0.05, 0.3, 1.8, 0.61, 0x222222);   // 目
  add(0.35, 0.12, 0.05, -0.45, 1.5, 0.61, 0xff9aa6); add(0.35, 0.12, 0.05, 0.45, 1.5, 0.61, 0xff9aa6); // ほお
  const ear = (sx) => {                                       // 頭の横の枝豆
    const e = new THREE.Group();
    [[0, 0], [0.25, 0.45], [0.5, 0.9]].forEach(([dx, dy]) => {
      const m = new THREE.Mesh(box(gc, 0.42, 0.42, 0.42), new THREE.MeshLambertMaterial({ color: 0x8fd14f }));
      m.position.set(sx * (0.75 + dx), 2.0 + dy, 0); e.add(m);
    });
    g.add(e); return e;
  };
  g.userData.ears = [ear(-1), ear(1)];
  return g;
}

// ---------- 場面：ブロックの島 ----------
function landScene(p) {
  const sc = CUR = new THREE.Scene();
  const N = 22, list = [];
  const h = (x, z) => {
    const d = Math.sqrt(x * x + z * z) / N;
    return Math.round(3.2 * (1 - d * 1.35) + 1.2 * Math.sin(x * 0.45) * Math.cos(z * 0.38));
  };
  const top = {};
  for (let x = -N; x <= N; x++) for (let z = -N; z <= N; z++) {
    const y = h(x, z);
    if (y < 0) { list.push([x, -0.45, z, (x + z) % 2 ? COL.sea : COL.sea2]); continue; }
    top[`${x},${z}`] = y;
    for (let k = Math.max(0, y - 2); k <= y; k++) {
      const col = k < y ? COL.dirt : (y <= 0 ? COL.sand : (p.snow ? COL.snow : ((x * 7 + z * 3) % 5 ? COL.grass : COL.grass2)));
      list.push([x, k, z, col]);
    }
  }
  sc.add(blocks(list));
  // 海を広く（遠くまで）
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(1200, 1200), new THREE.MeshLambertMaterial({ color: COL.sea }));
  sea.rotation.x = -Math.PI / 2; sea.position.y = -0.5; sc.add(sea);
  // 木
  const trees = [];
  const tpos = [[-6, -4], [-3, 5], [5, -6], [8, 3], [-10, 1], [2, 9], [11, -2], [-7, 9], [6, 10], [-12, -6]];
  tpos.forEach(([x, z], i) => {
    const y = top[`${x},${z}`]; if (y === undefined || y < 1) return;
    const t = new THREE.Group(); t.position.set(x, y + 0.5, z);
    const tr = blocks([[0, 0, 0, COL.trunk], [0, 1, 0, COL.trunk], [0, 2, 0, COL.trunk]]);
    const lf = [];
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = 0; c <= 1; c++)
      lf.push([a, 3 + c, b, p.snow ? COL.snow : ((a + b + c) % 2 ? COL.leaf : COL.leaf2)]);
    lf.push([0, 5, 0, p.snow ? COL.snow : COL.leaf]);
    const crown = blocks(lf); t.add(tr); t.add(crown); sc.add(t); trees.push(t);
  });
  // 雲（ブロックの塊）
  const clouds = new THREE.Group();
  for (let i = 0; i < 9; i++) {
    const cl = [], w = 3 + Math.floor(rnd() * 4);
    for (let a = 0; a < w; a++) for (let b = 0; b < 2; b++) if (rnd() > 0.2) cl.push([a, 0, b, COL.cloud]);
    const m = blocks(cl, 1, new THREE.MeshLambertMaterial({ emissive: 0x555555 }));
    m.position.set(-40 + rnd() * 80, 13 + rnd() * 6, -30 + rnd() * 50); clouds.add(m);
  }
  sc.add(clouds);
  // 吹き飛ぶ葉っぱのブロック（風）
  const bits = [];
  if (p.wind) for (let i = 0; i < 60; i++) {
    const m = blocks([[0, 0, 0, i % 3 ? COL.leaf2 : COL.sand]], 0.35);
    m.userData = { x: -30 + rnd() * 60, y: 1 + rnd() * 10, z: -15 + rnd() * 30, v: 18 + rnd() * 14, s: rnd() * 10 };
    sc.add(m); bits.push(m);
  }
  // キャラ
  let ch = null;
  if (p.zunda !== false) {
    ch = blockChar(); const y = top["0,4"] ?? 3; ch.position.set(0, y + 0.8, 4); ch.rotation.y = 0.35; sc.add(ch);
  }
  // 太陽・光
  const sun = new THREE.Mesh(new THREE.BoxGeometry(5, 5, 5), new THREE.MeshBasicMaterial({ color: COL.sun }));
  sc.add(sun);
  const amb = new THREE.AmbientLight(0xffffff, 0.55); sc.add(amb);
  const dl = new THREE.DirectionalLight(0xffffff, 1.1); sc.add(dl);
  const st = stars(900, 400); sc.add(st);
  const skyDay = new THREE.Color(0x7cc8ff), skyDusk = new THREE.Color(0xff8a4a), skyNight = new THREE.Color(0x05060f);
  const hot = new THREE.Color(0xffb36b);
  // カメラ
  const cams = {
    hook: [[14, 9, 22], [0, 3, 0]], low: [[3, 3.5, 12], [0, 4.5, 0]], wide: [[30, 22, 34], [0, 0, 0]],
    top: [[0, 42, 8], [0, 0, 0]], side: [[-20, 6, 8], [0, 4, 0]], sky: [[6, 2.5, 10], [-6, 14, -20]],
  };
  const [cp, ct] = cams[p.cam || "hook"];
  const cpE = cams[p.cam_to || p.cam || "hook"][0];
  return (t, d) => {
    const u = d ? t / d : 0;
    const tt = t + (p.t0 || 0);
    // 太陽：p.sun 秒で1周（1日）。null なら止める
    const ph = p.sun ? (tt / p.sun) * Math.PI * 2 + (p.ph0 || 0) : (p.ph0 ?? 0.9);
    const sx = Math.cos(ph) * 120, sy = Math.sin(ph) * 90;
    sun.position.set(sx, sy, -60); dl.position.set(sx, Math.max(sy, -20), -60);
    const el = Math.sin(ph);                                  // 太陽の高さ（-1〜1）
    const day = p.night ? 0 : Math.min(Math.max(el * 2.2 + 0.25, 0), 1);
    const dusk = p.night ? 0 : Math.max(0, 1 - Math.abs(el) * 4) * 0.8;
    const sky = skyNight.clone().lerp(skyDay, day).lerp(skyDusk, dusk * 0.6);
    if (p.hot) sky.lerp(hot, 0.45);
    sc.background = sky;
    dl.intensity = p.night ? 0.0 : 0.15 + 1.0 * day; amb.intensity = p.night ? 0.12 : 0.25 + 0.4 * day;
    st.material.opacity = 1; st.visible = day < 0.5; sun.visible = !p.night;
    // 雲と風
    clouds.children.forEach((m, i) => { m.position.x = ((m.position.x + 40 + (p.wind ? 0.9 : 0.05)) % 80) - 40; });
    const sway = p.wind ? 0.22 + 0.08 * Math.sin(t * 13) : 0.02 * Math.sin(t * 2);
    trees.forEach((tr, i) => { tr.rotation.z = -sway + 0.03 * Math.sin(t * 9 + i); });
    bits.forEach(b => {
      const q = b.userData; b.position.set(((q.x + t * q.v + 30) % 60) - 30, q.y + Math.sin(t * 6 + q.s) * 0.8, q.z);
      b.rotation.set(t * 7 + q.s, t * 5, 0);
    });
    if (ch) {   // キャラ：小さく跳ねる。風なら傾いて踏ん張る
      ch.position.y = (top["0,4"] ?? 3) + 0.8 + Math.abs(Math.sin(t * 7)) * 0.25;
      ch.rotation.z = p.wind ? -0.25 + 0.06 * Math.sin(t * 15) : 0;
      ch.userData.ears.forEach((e, i) => { e.rotation.z = (i ? -1 : 1) * 0.15 * Math.sin(t * 10) + (p.wind ? -0.5 : 0); });
    }
    const e = ease(u);
    C.position.set(lerp(cp[0], cpE[0], e), lerp(cp[1], cpE[1], e), lerp(cp[2], cpE[2], e));
    C.lookAt(ct[0], ct[1], ct[2]);
  };
}

// ---------- 場面：空へ飛ぶ → 月へ → 月が砕けて消える ----------
function flightScene(p) {
  const sc = CUR = new THREE.Scene();
  const st = stars(1600, 900); sc.add(st);
  const amb = new THREE.AmbientLight(0xffffff, 0.45); sc.add(amb);
  const dl = new THREE.DirectionalLight(0xffffff, 1.2); dl.position.set(-200, 80, 100); sc.add(dl);
  // 地上（島の上から見上げる）→ 地球（遠景）
  const earth = voxelPlanet(18, earthColor); earth.scale.setScalar(4); earth.position.set(0, -78, 0); sc.add(earth);
  // 雲の層（通り抜ける）
  const cl = [];
  for (let i = 0; i < 260; i++) cl.push([-60 + rnd() * 120, 0, -60 + rnd() * 120, COL.cloud]);
  const clouds = blocks(cl, 4, new THREE.MeshLambertMaterial({ emissive: 0x666666 })); clouds.position.y = 20; sc.add(clouds);
  // 月：ブロックごとに動かせるよう個別の配列で持つ
  const mr = 9, ml = [];
  for (let x = -mr; x <= mr; x++) for (let y = -mr; y <= mr; y++) for (let z = -mr; z <= mr; z++) {
    const dd = Math.sqrt(x * x + y * y + z * z);
    if (dd <= mr && dd > mr - 1.8) ml.push([x, y, z, moonColor(x / mr, y / mr, z / mr)]);
  }
  const moon = blocks(ml, 1.6); const MZ = 520, MY = 300;
  moon.position.set(0, MY, -MZ); sc.add(moon);
  const vel = ml.map(() => new THREE.Vector3(rnd() - 0.5, rnd() - 0.5, rnd() - 0.5).normalize().multiplyScalar(40 + rnd() * 90));
  const o = new THREE.Object3D();
  const sky = new THREE.Color(0x7cc8ff), black = new THREE.Color(0x000000);
  const flash = new THREE.Mesh(new THREE.SphereGeometry(8, 8, 8), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0 }));
  flash.position.copy(moon.position); sc.add(flash);
  const KB = p.burst ?? 0.78;   // 月が砕ける時刻（場面の長さに対する割合）
  return (t, d) => {
    const u = t / d;
    // カメラの道筋：地上(上を向く) → 雲を抜け → 宇宙 → 月に迫る
    const a = ease(u / KB);
    const camY = lerp(-2, MY - 60, Math.pow(a, 1.6)), camZ = lerp(30, -MZ + 90, Math.pow(a, 2.2));
    C.position.set(Math.sin(u * 3) * 6 * (1 - a), camY, camZ);
    const look = new THREE.Vector3(0, MY, -MZ);
    C.lookAt(look.x, lerp(camY + 40, look.y, Math.min(1, a * 1.5)), lerp(camZ - 30, look.z, Math.min(1, a * 1.3)));
    C.rotateZ(Math.sin(u * 5) * 0.06 + u * 0.5);              // 少しひねって引き込む
    sc.background = sky.clone().lerp(black, Math.min(1, Math.max(0, (camY - 15) / 40)));
    st.visible = camY > 25;
    earth.rotation.y = t * 0.3;
    moon.rotation.y = t * 0.4;
    // 砕ける
    const b = (u - KB) / (1 - KB);
    if (b > 0) {
      for (let i = 0; i < ml.length; i++) {
        const v = vel[i];
        o.position.set(ml[i][0] * 1.6 + v.x * b * 1.6, ml[i][1] * 1.6 + v.y * b * 1.6, ml[i][2] * 1.6 + v.z * b * 1.6);
        const s = Math.max(0.001, 1 - b * 1.25); o.scale.setScalar(s);
        o.rotation.set(b * 9 + i, b * 7, 0); o.updateMatrix(); moon.setMatrixAt(i, o.matrix);
      }
      moon.instanceMatrix.needsUpdate = true;
      flash.material.opacity = Math.max(0, 0.9 - b * 2.2); flash.scale.setScalar(1 + b * 10);
    }
  };
}

// ---------- 場面：巻き戻し（月のない地球が逆回り） ----------
function rewindScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  const st = stars(1600, 600); sc.add(st);
  sc.add(new THREE.AmbientLight(0xffffff, 0.35));
  const dl = new THREE.DirectionalLight(0xffffff, 1.3); dl.position.set(-100, 30, 60); sc.add(dl);
  const earth = voxelPlanet(18, (x, y, z) => {   // 後半は若い地球（溶岩の色）に変わっていく見立て
    const n = noise3(x, y, z); return n > 0.3 ? COL.lava : (n > -0.2 ? 0x5a2a1a : 0x2a1a14);
  });
  const earthNow = voxelPlanet(18, earthColor);
  sc.add(earth); sc.add(earthNow); earth.visible = false;
  return (t, d) => {
    const u = t / d;
    const sp = -(2 + 22 * ease(u));               // だんだん速く逆回り
    earth.rotation.y = earthNow.rotation.y = sp * t * 0.6;
    earth.rotation.z = earthNow.rotation.z = 0.41;
    earthNow.visible = u < 0.62; earth.visible = !earthNow.visible;
    st.rotation.y = sp * t * 0.05;
    C.position.set(0, 4, lerp(70, 46, ease(u))); C.lookAt(0, 0, 0);
    C.rotateZ(-u * 0.6);
  };
}

// ---------- 場面：地軸がふらつく ----------
function axisScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  sc.add(stars(1400, 600)); sc.add(new THREE.AmbientLight(0xffffff, 0.4));
  const dl = new THREE.DirectionalLight(0xffffff, 1.3); dl.position.set(-100, 40, 80); sc.add(dl);
  const g = new THREE.Group(); sc.add(g);
  const e = voxelPlanet(18, earthColor); g.add(e);
  const rod = new THREE.Mesh(new THREE.BoxGeometry(1.4, 56, 1.4), new THREE.MeshBasicMaterial({ color: 0xff3b30 })); g.add(rod);
  return (t, d) => {
    const amp = p.amp ?? 1;
    g.rotation.z = 0.41 + amp * (0.55 * Math.sin(t * 3.1) + 0.25 * Math.sin(t * 7.3));
    g.rotation.x = amp * 0.35 * Math.sin(t * 4.3 + 1);
    e.rotation.y = t * 4;
    C.position.set(lerp(-8, 8, t / d), 6, 62); C.lookAt(0, 0, 0);
  };
}

// ---------- 場面：太陽と地球。月がいない ----------
function spaceScene(p) {
  const sc = CUR = new THREE.Scene(); sc.background = new THREE.Color(0x02030a);
  sc.add(stars(1400, 700)); sc.add(new THREE.AmbientLight(0xffffff, 0.25));
  const sun = voxelPlanet(14, (x, y, z) => (noise3(x * 2, y * 2, z * 2) > 0.3 ? 0xffb020 : COL.sun));
  sun.material = new THREE.MeshBasicMaterial(); sun.position.set(-70, 10, -40); sc.add(sun);
  const pl = new THREE.PointLight(0xffffff, 3, 0, 0); pl.position.copy(sun.position); sc.add(pl);
  const e = voxelPlanet(10, earthColor); e.position.set(25, -6, 10); sc.add(e);
  // 月の通り道（点線のブロック）だけあって、月はいない
  const ring = [];
  for (let i = 0; i < 48; i++) if (i % 2) { const a = i / 48 * Math.PI * 2; ring.push([Math.cos(a) * 26, 0, Math.sin(a) * 26, 0x777777]); }
  const r = blocks(ring, 0.9); r.position.copy(e.position); r.rotation.x = 0.25; sc.add(r);
  return (t, d) => {
    e.rotation.y = t * 3; sun.rotation.y = t * 0.3; r.rotation.y = t * 0.2;
    const u = t / d;
    C.position.set(lerp(50, 62, u), lerp(14, 8, u), lerp(70, 58, u)); C.lookAt(10, 0, 0);
  };
}

const SCENES = { land: landScene, flight: flightScene, rewind: rewindScene, axis: axisScene, space: spaceScene };

window.setup = (j) => {
  job = j;
  if (!R) {
    R = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    document.body.appendChild(R.domElement);
  }
  R.setPixelRatio(1); R.setSize(j.w, j.h);
  C = new THREE.PerspectiveCamera(j.fov || 55, j.w / j.h, 0.1, 3000);
  upd = SCENES[j.scene](j.p || {});
  S = CUR;
  return true;
};
window.frame = (t) => {
  upd(t, job.d);
  R.render(S, C);
  return true;
};
window.ready = true;
