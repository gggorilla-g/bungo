# lightride.py — 英語の長尺：光の速さで太陽を出て、ボイジャー1号（1光日）まで（オーナー 11/26「トレンドキーワードを調べて…基本3Dで、著作権フリーの画像…長尺」）
#   文脈：2026-11-18 にボイジャー1号が地球から1光日に到達。今月の長尺上位は「宇宙を旅する」型（Astrum のボイジャー回 7日で277万回）。
#   しくみ：旅程（STOPS）を上から順に通る。距離と「光が太陽からそこまでかかる時間」をずっと表示（時間 = 距離 ÷ 光速。どのコマでも正しい）。
#           星は球に地図を貼って陰をつけた3D（地図・写真は assets/maps と assets/planets。すべてパブリックドメイン、meta.json に出どころ）。
#   再現性：STOPS と CRUISE の文を差しかえれば別の旅（プロキシマ、銀河の中心…）になる。
#   python3 tools/lightride.py                 全部（2つに分けて並行に描き、つないで音をのせる）→ output/lightride1_en.mp4
#   python3 tools/lightride.py stills 30,200   確認用の絵（build_lightride/s_*.jpg）
#   python3 tools/lightride.py clip 190 215 out.mp4   一部だけ（音つき）
#   python3 tools/lightride.py thumb           サムネ（output/lightride1_en_thumb.jpg）
import math, os, sys, subprocess, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1920, 1080, 30, 48000
B = "build_lightride"; os.makedirs(B, exist_ok=True)
FB = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"; FM = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
def fnt(sz, bold=True): return ImageFont.truetype(FB if bold else FM, sz)
AU_KM = 149597870.7; C_KMS = 299792.458; AU_LS = AU_KM / C_KMS   # 1AU を光が進む秒（499.005）
FOC = 1500.0; BX, BY = 1.15, -.10   # 星は進む道の右わきにある（星の半径を1として）
LIGHT = np.array([-.42, -.30, -.86]); LIGHT /= np.linalg.norm(LIGHT)

def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)

# ---------- 旅程 ----------
# hold = 止まって見る秒数（文の数から決める）。facts は1行ずつ出る
STOPS = [
 dict(key="sun", name="THE SUN", au=0.00465, facts=["Diameter: 1.39 million km — 109 Earths wide", "Surface temperature: 5,500 °C", "It holds 99.8% of the solar system's mass", "Light leaves the surface. We follow it."]),
 dict(key="mercury", name="MERCURY", au=0.387, facts=["A year here lasts 88 days", "Day side 430 °C — night side −180 °C", "Only 1.4 times wider than our Moon"]),
 dict(key="venus", name="VENUS", au=0.723, facts=["The hottest planet: 465 °C under the clouds", "It spins backwards", "One day (243 Earth days) is longer than its year (225)"], insets=[("venus", "Surface mapped by radar — Magellan", "NASA/JPL")]),
 dict(key="earth", name="EARTH", au=1.0, facts=["Sunlight you see is 8 minutes 19 seconds old", "The only world known to have life", "The Moon is 1.28 light-seconds away", "Every human who ever lived, lived here"]),
 dict(key="mars", name="MARS", au=1.524, facts=["Olympus Mons: 22 km high — 2.5 times Everest", "A day lasts 24 hours 37 minutes", "Radio signals to the rovers take 3 to 22 minutes"]),
 dict(key="ceres", name="CERES", au=2.77, facts=["The largest object in the asteroid belt: 940 km wide", "The belt is almost empty — asteroids are about a million km apart", "All asteroids together weigh less than our Moon"]),
 dict(key="jupiter", name="JUPITER", au=5.203, facts=["11 Earths wide — 318 times Earth's mass", "The Great Red Spot is a storm wider than Earth", "A day lasts under 10 hours", "95 known moons"]),
 dict(key="saturn", name="SATURN", au=9.58, facts=["The rings span 280,000 km", "…yet in places they are only about 10 m thick", "Saturn is less dense than water", "Winds reach 1,800 km/h"], insets=[("saturnphoto", "Saturn at equinox — Cassini, 2009", "NASA/JPL/SSI")]),
 dict(key="uranus", name="URANUS", au=19.19, facts=["Tilted 98° — it orbits the Sun on its side", "Coldest atmosphere of any planet: −224 °C", "One year lasts 84 Earth years", "Visited once: Voyager 2, 1986"], insets=[("uranusphoto", "Uranus — Voyager 2, 1986", "NASA/JPL")]),
 dict(key="neptune", name="NEPTUNE", au=30.07, facts=["Fastest winds in the solar system: 2,000 km/h", "One orbit takes 165 years", "Visited once: Voyager 2, 1989"], insets=[("neptunephoto", "Neptune — Voyager 2, 1989", "NASA/JPL")]),
 dict(key="pluto", name="PLUTO", au=39.48, facts=["Smaller than our Moon: 2,377 km wide", "New Horizons needed 9.5 years to get here", "Sunlight is 1,600 times weaker than on Earth"], insets=[("plutodisc", "Pluto — New Horizons, 2015", "NASA/JHUAPL/SwRI")]),
 dict(key="voyager", name="VOYAGER 1", au=173.1446, facts=["One light-day from Earth — reached on November 18, 2026", "Launched on September 5, 1977", "Speed: 17 km/s. The trip took 49 years.", "Light does it in 24 hours.", "It carries a golden record of Earth's sounds"], insets=[("v1launch", "Launch — September 5, 1977", "NASA"), ("palebluedot", "Earth from 6 billion km — Voyager 1, 1990", "NASA/JPL"), ("record", "The Golden Record", "NASA/JPL")]),
]
# 移動中に出す文（1つの移動に2〜3個）
CRUISE = [
 ["At light speed you would pass a planet in a blink.", "So we slow down at every stop.", "The clock shows how long light really takes."],
 ["Light could circle the Earth 7.5 times in one second.", "Space is still this big."],
 ["Venus is the brightest planet in Earth's sky.", "Next stop: home."],
 ["The Moon is already 1.28 light-seconds behind us.", "Humans have never travelled farther than that."],
 ["Next: the asteroid belt.", "Spacecraft cross it without steering around anything."],
 ["From here, the gaps get much longer.", "Jupiter is three times farther from the Sun than Mars."],
 ["Saturn is almost twice as far out as Jupiter.", "Its light-time passes one hour."],
 ["Uranus is twice as far as Saturn.", "It was unknown until 1781."],
 ["Neptune was found by mathematics in 1846,", "before anyone saw it."],
 ["Beyond Neptune: the Kuiper Belt.", "Thousands of icy worlds, 30 to 50 AU out."],
 ["94 AU — termination shock: the solar wind slows down.", "121 AU — heliopause. Voyager 1 crossed it on August 25, 2012.", "Beyond here: interstellar space."],
]
OUTRO = ["The next star, Proxima Centauri, is 4.24 light-years away.", "Light needs 4 years and 3 months.", "Voyager 1 would need about 75,000 years.", "Thanks for riding along."]
HOLD0, PERFACT, APPR, DEP, INTRO = 10.0, 13.0, 16.0, 5.0, 6.0
CRU = [40, 48, 48, 48, 56, 64, 70, 76, 76, 76, 130]     # 各移動の秒数（離れる5秒・近づく16秒をふくむ）
def build():
    t = INTRO; seg = []
    for i, s in enumerate(STOPS):
        s["hold"] = HOLD0 + PERFACT * len(s["facts"]) + 6; s["t0"] = t; s["t1"] = t + s["hold"]; t = s["t1"]
        if i < len(CRU): t += CRU[i]
    return t
T_OUT = build(); DUR = T_OUT + 14 + 9 * len(OUTRO)

def state(t):
    """t での場所：(太陽からのAU, 止まっている星の番号 or None, その星までの z, 進む速さ0..1)"""
    if t < STOPS[0]["t0"]: return STOPS[0]["au"], 0, 5.0 + 3.0 * (1 - sstep(0, INTRO, t)) ** 2 * 0 + (STOPS[0]["t0"] - t) * .25, 0.0
    for i, s in enumerate(STOPS):
        if t < s["t1"]: return s["au"], i, 5.0 - .9 * (t - s["t0"]) / s["hold"], 0.0
        if i + 1 == len(STOPS): break
        n = STOPS[i + 1]
        if t < n["t0"]:
            u = (t - s["t1"]) / (n["t0"] - s["t1"]); e = float(sstep(.02, .98, u)); au = s["au"] * (n["au"] / s["au"]) ** e
            sp = float(sstep(0, DEP, t - s["t1"]) * sstep(0, 6, n["t0"] - t))
            if t - s["t1"] < DEP: v = (t - s["t1"]) / DEP; return au, i, 4.1 - 5.2 * v * v, sp
            if n["t0"] - t < APPR: v = 1 - (n["t0"] - t) / APPR; return au, i + 1, 5.0 * math.exp(math.log(700) * (1 - v) ** 1.7), sp
            return au, None, 0.0, sp
    return STOPS[-1]["au"], len(STOPS) - 1, 4.1 - .0 * t, 0.0   # 最後はボイジャーのそば

# ---------- 絵の材料 ----------
def noise(h, w, seed, octs=5, stretch=1.0):
    r = np.random.default_rng(seed); out = np.zeros((h, w), np.float32); a = 1.0; tot = 0
    for o in range(octs):
        gh, gw = max(2, int(h / (64 / 2 ** o))), max(2, int(w / (64 / 2 ** o) / stretch)); g = r.random((gh, gw)).astype(np.float32); g = np.concatenate([g, g[:, :1]], 1)
        out += a * cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC); tot += a; a *= .5
    return out / tot
def bands(cols, seed, wob=.02, fine=.5):
    h, w = 1024, 2048; lat = np.linspace(0, 1, h, dtype=np.float32)[:, None] + (noise(h, w, seed, 4, 6.0) - .5) * wob
    xs = np.linspace(0, 1, len(cols)); c = np.stack([np.interp(lat, xs, [q[k] for q in cols]) for k in range(3)], -1).astype(np.float32)
    return np.clip(c * (1 + (noise(h, w, seed + 1, 6, 10.0)[..., None] - .5) * fine), 0, 255)
def load_map(name, sat=1.0, gain=1.0, tint=None):
    a = np.asarray(Image.open(f"assets/maps/{name}.jpg").convert("RGB").resize((2048, 1024), Image.LANCZOS), np.float32)
    g = a.mean(-1, keepdims=True); a = g + (a - g) * sat
    if tint is not None: a = a * np.asarray(tint, np.float32)
    return np.clip(a * gain, 0, 255)
def disc_map(path, bg_thr=18):
    """丸く写った写真を、正面の半球に貼った地図にする（裏側は鏡うつしをぼかしたもの）"""
    im = np.asarray(Image.open(path).convert("RGB"), np.float32); g = im.mean(-1); ys, xs = np.where(g > bg_thr); cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2; R = min(xs.max() - xs.min(), ys.max() - ys.min()) / 2 * .97
    h, w = 1024, 2048; lon = (np.arange(w, dtype=np.float32) / w * 2 - 1) * math.pi; lat = (.5 - np.arange(h, dtype=np.float32) / h) * math.pi; LO, LA = np.meshgrid(lon, lat)
    front = np.cos(LO) > 0; lo = np.where(front, LO, np.sign(LO) * math.pi - LO); mx = (cx + R * np.cos(LA) * np.sin(lo)).astype(np.float32); my = (cy - R * np.sin(LA)).astype(np.float32)
    out = cv2.remap(im, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE); back = cv2.GaussianBlur(out, (0, 0), 14); m = sstep(-.12, .12, np.cos(LO))[..., None]; return out * m + back * (1 - m)
TEX = {}
def textures():
    if TEX: return TEX
    TEX["mercury"] = load_map("mercury", .18, 1.05, (1.04, 1.0, .95)); TEX["earth"] = load_map("earth2", 1.0, 1.05); TEX["moon"] = load_map("moon", 1.0, 1.0); TEX["mars"] = load_map("mars2", 1.05, 1.08)
    TEX["jupiter"] = load_map("jupiter", 1.1, 1.05)
    cl = noise(1024, 2048, 31, 6, 5.0); TEX["venus"] = bands([(226, 214, 180), (238, 226, 190), (214, 196, 150), (240, 230, 198), (224, 208, 166), (236, 224, 190), (222, 208, 170)], 32, .06, .16) * (.9 + .2 * cl[..., None])
    TEX["saturn"] = bands([(150, 140, 118), (196, 178, 140), (222, 204, 160), (206, 186, 142), (230, 212, 168), (216, 196, 150), (234, 216, 172), (212, 190, 146), (226, 206, 162), (198, 180, 142), (160, 150, 126)], 41, .012, .10)
    TEX["uranus"] = bands([(150, 206, 214), (170, 222, 228), (176, 228, 232), (172, 224, 230), (160, 214, 222)], 51, .01, .04)
    nep = bands([(40, 70, 170), (52, 92, 204), (66, 112, 222), (58, 100, 212), (70, 118, 226), (50, 88, 198), (38, 66, 166)], 61, .03, .12)
    yy, xx = np.mgrid[0:1024, 0:2048]; spot = np.exp(-(((xx - 900) / 110.0) ** 2 + ((yy - 640) / 46.0) ** 2)); TEX["neptune"] = nep * (1 - .45 * spot[..., None]); TEX["neptune"] += 40 * np.exp(-(((xx - 930) / 80.0) ** 2 + ((yy - 700) / 9.0) ** 2))[..., None]
    TEX["pluto"] = disc_map("assets/maps/plutodisc.jpg") if os.path.exists("assets/maps/plutodisc.jpg") else bands([(170, 140, 110), (200, 176, 150), (180, 150, 120)], 71, .1, .3)
    cer = [p for p in ("assets/maps/ceresdisc.jpg", "assets/maps/ceresdisc2.jpg") if os.path.exists(p)]
    TEX["ceres"] = disc_map(cer[0]) if cer else np.clip(load_map("moon", 0, .8) * .9, 0, 255)
    n1 = cv2.resize(np.random.default_rng(81).random((256, 512)).astype(np.float32), (2048, 1024), interpolation=cv2.INTER_CUBIC) * .55 + noise(1024, 2048, 83, 6, 1.0) * .45; n2 = noise(1024, 2048, 82, 4, 1.0); g = np.clip((n1 - .5) * 2.6 + .70 + (n2 - .5) * 1.1, 0, 1); pol = sstep(.5, .9, np.abs(np.linspace(-1, 1, 1024, dtype=np.float32)))[:, None]; g = (g * (1 - pol) + .66 * pol)[..., None]
    TEX["sun"] = np.array([255, 120, 20], np.float32) * (1 - g) + np.array([255, 232, 150], np.float32) * g
    eh, ew = 1024, 2048; c = noise(eh, ew, 91, 7, 2.0) * .6 + noise(eh, ew, 92, 7, 1.0) * .4; pol = sstep(.6, .95, np.abs(np.linspace(-1, 1, eh, dtype=np.float32)))[:, None]; TEX["clouds"] = (np.clip((c - .535) * 9, 0, 1) * (1 - pol)).astype(np.float32)
    ring = np.zeros((512, 4), np.float32); rr = np.linspace(1.24, 2.27, 512); nz = np.interp(rr, np.linspace(1.24, 2.27, 90), np.random.default_rng(5).random(90))
    al = np.where(rr < 1.52, .22 + .1 * nz, np.where(rr < 1.95, .82 + .16 * nz, np.where(rr < 2.02, .05, .62 + .14 * nz))); al *= sstep(1.24, 1.27, rr) * (1 - sstep(2.24, 2.27, rr))
    ring[:, 0] = 214 + 26 * nz; ring[:, 1] = 196 + 24 * nz; ring[:, 2] = 158 + 22 * nz; ring[:, 3] = al; TEX["ring"] = ring
    for k, f in (("voyager", "voyager"), ("in_record", "record"), ("in_venus", "venus"), ("in_saturnphoto", "saturnphoto"), ("in_uranusphoto", "uranusphoto"), ("in_neptunephoto", "neptunephoto"), ("in_plutodisc", "plutodisc"), ("in_v1launch", "v1launch"), ("in_palebluedot", "palebluedot")):
        if os.path.exists(f"assets/maps/{f}.jpg"): TEX[k] = np.asarray(Image.open(f"assets/maps/{f}.jpg").convert("RGB"), np.float32)
    return TEX
BODY = dict(sun=dict(tilt=.1, spin=.012, emis=True), mercury=dict(tilt=.03, spin=.02), venus=dict(tilt=.05, spin=-.012, atmo=(255, 236, 190)), earth=dict(tilt=.41, spin=.035, atmo=(120, 170, 255), clouds=True),
            mars=dict(tilt=.44, spin=.034, atmo=(255, 190, 150)), ceres=dict(tilt=.07, spin=.03), jupiter=dict(tilt=.05, spin=.06), saturn=dict(tilt=.47, spin=.055, ring=True), uranus=dict(tilt=1.45, spin=.04, atmo=(170, 230, 236)),
            neptune=dict(tilt=.49, spin=.045, atmo=(90, 130, 255)), pluto=dict(tilt=.3, spin=.008), moon=dict(tilt=.1, spin=.004))

def sphere(buf, key, cx, cy, R, t, lightmul=1.0):
    """buf（H,W,3 float 0..1）に、中心(cx,cy)・半径R の球を描く。地図を貼って、太陽の向きで陰をつける"""
    T = textures(); bd = BODY[key]; pad = R * (2.45 if bd.get("ring") else 2.6 if bd.get("emis") else 1.12) + 4
    x0, x1, y0, y1 = int(max(0, cx - pad)), int(min(W, cx + pad + 1)), int(max(0, cy - pad)), int(min(H, cy + pad + 1))
    if x1 <= x0 or y1 <= y0 or R < .6:
        if R < .6 and 0 <= cx < W and 0 <= cy < H: cv2.circle(buf, (int(cx), int(cy)), 1, (.8 * R / .6,) * 3, -1, cv2.LINE_AA)
        return
    xs = (np.arange(x0, x1, dtype=np.float32) + .5 - cx) / R; ys = (np.arange(y0, y1, dtype=np.float32) + .5 - cy) / R; U, V = np.meshgrid(xs, ys); rr2 = U * U + V * V; ins = rr2 < 1
    Wz = np.sqrt(np.clip(1 - rr2, 0, 1)); nx, ny, nz = U, V, -Wz
    ti = bd["tilt"]; ct, st_ = math.cos(ti), math.sin(ti); ax = .38   # 少し上から見下ろす
    ca, sa = math.cos(ax), math.sin(ax); y2 = ny * ca - nz * sa; z2 = ny * sa + nz * ca; x3 = nx * ct + y2 * st_; y3 = -nx * st_ + y2 * ct
    lon = np.arctan2(x3, -z2) + t * bd["spin"] + 1.0; lat = np.arcsin(np.clip(-y3, -1, 1)); tex = T[key]; th, tw = tex.shape[:2]
    mx = ((lon / (2 * math.pi)) % 1.0 * tw).astype(np.float32); my = ((.5 - lat / math.pi) * (th - 1)).astype(np.float32)
    col = cv2.remap(tex, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP) / 255.0
    aa = np.clip((1 - np.sqrt(rr2)) * R + .5, 0, 1)[..., None]; reg = buf[y0:y1, x0:x1]
    if bd.get("emis"):
        limb = (.55 + .45 * Wz)[..., None]; out = col * limb * 1.15; d = np.sqrt(rr2); glow = ((np.exp(-np.clip(d - 1, 0, None) / .10) * .9 + np.exp(-np.clip(d - 1, 0, None) / .45) * .35) * (1 - sstep(1.9, 2.6, d)))[..., None] * np.array([1.0, .62, .22], np.float32)
        reg[:] = reg + glow * (1 - aa); reg[:] = reg * (1 - aa) + out * aa; return
    lam = nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]; sh = (sstep(-.06, .34, lam) * (.25 + .75 * np.clip(lam, 0, 1)) + .012)[..., None] * lightmul
    if bd.get("clouds"):
        cm = cv2.remap(T["clouds"], ((lon / (2 * math.pi) + t * .0006) % 1.0 * tw).astype(np.float32), my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)[..., None]; col = col * (1 - cm * .85) + cm * .85
    out = col * sh
    if bd.get("atmo"):
        ac = np.asarray(bd["atmo"], np.float32) / 255; rim = ((1 - Wz) ** 2.4)[..., None] * sh * .55; out = out * (1 - rim * .5) + ac * rim
        d = np.sqrt(rr2); halo = (np.exp(-np.clip(d - 1, 0, None) / .022) * sstep(-.2, .5, (U * LIGHT[0] + V * LIGHT[1]) / np.maximum(d, 1e-3)))[..., None] * ac * .5 * lightmul; reg[:] = reg + halo * (1 - aa)
    if bd.get("ring"):
        k = np.array([st_ * ca * 0 + math.sin(ti) * .0 + .0, 0, 0]); kx, ky, kz = -st_, ct * ca, ct * sa * -1.0   # 輪の面の法線（星の自転軸）
        zz = -(kx * U + ky * V) / kz; r = np.sqrt(U * U + V * V + zz * zz); ri = np.clip((r - 1.24) / (2.27 - 1.24) * 511, 0, 511).astype(np.int32); rg = T["ring"][ri]; ra = (rg[..., 3] * ((r > 1.24) & (r < 2.27)))[..., None] * .92
        rc = rg[..., :3] / 255 * lightmul; back = (zz > 0)[..., None]
        reg[:] = reg * (1 - ra * back * (1 - aa)) + rc * ra * back * (1 - aa)   # 奥の輪（星にかくれる）
        reg[:] = reg * (1 - aa) + out * aa
        fr = (~back) * ra; reg[:] = reg * (1 - fr) + rc * fr; return
    reg[:] = reg * (1 - aa) + out * aa

_BG = {}
def background():
    if "bg" in _BG: return _BG["bg"]
    r = np.random.default_rng(3); yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]; bg = np.zeros((H, W, 3), np.float32) + np.array([.012, .013, .028], np.float32) * (1 + .5 * yy)
    mw = noise(H, W, 7, 6, 1.0); X, Y = np.meshgrid(np.linspace(-1, 1, W, dtype=np.float32), np.linspace(-1, 1, H, dtype=np.float32)); band = np.exp(-((Y * .9 + X * .42 - .1) / .34) ** 2) * (.35 + mw)
    bg += band[..., None] * np.array([.045, .04, .06], np.float32)
    for _ in range(1500):
        x, y = int(r.uniform(0, W)), int(r.uniform(0, H)); b = r.uniform(.10, .75) ** 1.6; c = np.array([1, 1, 1], np.float32) * b * np.array([r.uniform(.85, 1), r.uniform(.88, 1), 1.0]); bg[y, x] += c
        if b > .28 and 0 < x < W - 1 and 0 < y < H - 1: bg[y - 1:y + 2, x - 1:x + 2] += c * .32
    _BG["bg"] = np.clip(bg, 0, 1); return _BG["bg"]
_D = {}
def dust(buf, t, sp):
    """進んでいる感じ：手前へ流れる細かい粒（速さ sp に比例。止まっている間は出ない）"""
    if sp <= .01: return
    if "p" not in _D:
        r = np.random.default_rng(11); _D["p"] = np.stack([r.uniform(-1, 1, 420), r.uniform(-1, 1, 420), r.uniform(0, 1, 420)], 1); fr = np.arange(int(DUR * FPS) + 2) / FPS; _D["z"] = np.cumsum([state(x)[3] for x in fr]) / FPS * .32
    Z = _D["z"][min(len(_D["z"]) - 1, int(t * FPS))]; p = _D["p"]; z = (p[:, 2] - Z) % 1.0 + .03; z2 = z + .012 * sp
    for (x, y), a, b in zip(p[:, :2], z, z2):
        xa, ya, xb, yb = W / 2 + x * 520 / a, H / 2 + y * 520 / a, W / 2 + x * 520 / b, H / 2 + y * 520 / b
        if -50 < xa < W + 50 and -50 < ya < H + 50: g = float(min(1, .09 / a) * sp * .9 * sstep(.03, .09, a)); cv2.line(buf, (int(xb), int(yb)), (int(xa), int(ya)), (g * .8, g * .88, g), 1, cv2.LINE_AA)

def fmt_time(sec):
    sec = int(round(sec)); d, r = divmod(sec, 86400); h, r = divmod(r, 3600); m, s = divmod(r, 60); return (f"{d}d " if d else "") + f"{h:02d}:{m:02d}:{s:02d}"
def fmt_km(km):
    if km >= 1e9: return f"{km / 1e9:,.2f} billion km"
    if km >= 1e6: return f"{km / 1e6:,.1f} million km"
    return f"{km:,.0f} km"
F = dict(lab=fnt(22, False), big=fnt(58), mid=fnt(34), name=fnt(86), fact=fnt(36, False), cru=fnt(44, False), small=fnt(20, False), tick=fnt(18, False), cap=fnt(22, False), title=fnt(92), sub=fnt(40, False))
def mono(d, xy, s, font, fill, adv):
    x, y = xy
    for ch in s:
        if ch.isdigit(): w = d.textlength(ch, font=font); d.text((x + (adv - w) / 2, y), ch, font=font, fill=fill); x += adv
        else: d.text((x, y), ch, font=font, fill=fill); x += d.textlength(ch, font=font)
def fade(t, a, b, fi=.8, fo=.8): return float(min(sstep(a, a + fi, t), 1 - sstep(b - fo, b, t)))
LOGA, LOGB = math.log10(.3), math.log10(190)
def barx(au): return 150 + (W - 300) * (math.log10(max(au, .3)) - LOGA) / (LOGB - LOGA)

def frame(t):
    T = textures(); au, bi, z, sp = state(t); buf = background().copy(); dust(buf, t, sp)
    if bi is not None:
        s = STOPS[bi]; key = s["key"]
        if z > .28:
            Rr = FOC / math.sqrt(z * z + BX * BX + BY * BY); cx, cy = W / 2 + FOC * BX / z + 1.0, H / 2 + FOC * BY / z + 30
            sc = dict(sun=1.12, jupiter=1.0, saturn=.62, ceres=.55, pluto=.7, mercury=.8, mars=.85, moon=.5).get(key, .92); Rr *= sc
            if key == "voyager":
                if "voyager" in T:
                    im = T["voyager"]; hh = Rr * 2.1; ww = hh * im.shape[1] / im.shape[0]; ang = 8 * math.sin(t * .05)
                    M = cv2.getRotationMatrix2D((im.shape[1] / 2, im.shape[0] / 2), ang, hh / im.shape[0]); M[0, 2] += cx - im.shape[1] / 2; M[1, 2] += cy - im.shape[0] / 2
                    wv = cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_AREA if hh < im.shape[0] else cv2.INTER_LINEAR) / 255.0; a = np.clip(wv.max(-1, keepdims=True) * 6, 0, 1); buf[:] = buf * (1 - a) + wv * .9 * a
            else:
                if key == "earth" and t >= s["t0"] - 2:   # 月（1.28光秒）
                    ma = fade(t, s["t0"] + 2, s["t1"] + 2); mx_, my_ = cx - Rr * 2.25, cy - Rr * .72
                    if ma > 0: tmp = buf.copy(); sphere(tmp, "moon", mx_, my_, Rr * .27, t); buf[:] = buf * (1 - ma) + tmp * ma
                sphere(buf, key, cx, cy, Rr, t)
    img = Image.fromarray((np.clip(buf, 0, 1) * 255).astype(np.uint8)).convert("RGBA"); ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    hud = float(sstep(1.0, 3.0, t) * (1 - sstep(T_OUT + 10, T_OUT + 13, t))); A = lambda v, a=1.0: int(255 * v * a * hud)
    if hud > 0:
        km = au * AU_KM
        d.text((92, 70), "DISTANCE FROM THE SUN", font=F["lab"], fill=(150, 170, 210, A(1)))
        mono(d, (90, 98), fmt_km(km), F["big"], (244, 246, 252, A(1)), 36); mono(d, (92, 170), f"{au:,.3f} AU" if au < 100 else f"{au:,.2f} AU", F["mid"], (190, 200, 226, A(1)), 21)
        d.text((92, 240), "LIGHT TRAVEL TIME FROM THE SUN", font=F["lab"], fill=(255, 214, 130, A(1))); mono(d, (90, 268), fmt_time(au * AU_LS), F["big"], (255, 226, 150, A(1)), 36)
        d.text((W - 92, 70), "SPEED", font=F["lab"], fill=(150, 170, 210, A(1)), anchor="ra"); d.text((W - 92, 98), "299,792 km/s", font=F["mid"], fill=(244, 246, 252, A(1)), anchor="ra"); d.text((W - 92, 142), "the speed of light", font=F["small"], fill=(150, 170, 210, A(1)), anchor="ra")
        # 下：道のり（対数目盛り）
        y = H - 70; d.line([(150, y), (W - 150, y)], fill=(120, 136, 180, A(.6)), width=2); xn = barx(au)
        d.line([(150, y), (xn, y)], fill=(255, 220, 140, A(.95)), width=4)
        for q, s_ in enumerate(STOPS[1:]):
            x = barx(s_["au"]); passed = au >= s_["au"] * .999; d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 226, 150, A(1)) if passed else (120, 136, 180, A(.9)))
            d.text((x, y + (16 if q % 2 == 0 else -40)), s_["name"].title(), font=F["tick"], fill=(230, 234, 246, A(1 if passed else .6)), anchor="ma")
        d.ellipse([xn - 9, y - 9, xn + 9, y + 9], fill=(255, 255, 255, A(1)))
        # 左下：ここから見た太陽（地球から見た大きさを基準に、同じ縮尺）
        if au > .05:
            bx_, by_ = 190, 856; d.text((92, 744), "THE SUN FROM HERE", font=F["lab"], fill=(150, 170, 210, A(1))); rs = 26.0 / au
            if rs > 1.2: rs2 = min(rs, 92); d.ellipse([bx_ - rs2, by_ - rs2, bx_ + rs2, by_ + rs2], fill=(255, 236, 170, A(1)))
            else: d.ellipse([bx_ - 2, by_ - 2, bx_ + 2, by_ + 2], fill=(255, 244, 210, A(min(1, .45 + rs * .5))))
            br = 100 / au ** 2; d.text((320, 826), "Sunlight", font=F["small"], fill=(150, 170, 210, A(1))); d.text((320, 852), (f"{br:,.0f}%" if br >= 10 else f"{br:.1f}%" if br >= .1 else f"{br:.3f}%") + " of Earth's", font=F["cap"], fill=(236, 238, 246, A(1)))
    # 止まっている星の名前と文
    for s in STOPS:
        if s["t0"] - 3 < t < s["t1"] + 1.5:
            a = fade(t, s["t0"] - 2.5, s["t1"] + 1.2); d.text((90, 392), s["name"], font=F["name"], fill=(255, 255, 255, int(255 * a)))
            for j, f in enumerate(s["facts"]):
                tf = s["t0"] + HOLD0 * .45 + PERFACT * j; af = fade(t, tf, s["t1"] + 1.0, .9)
                if af > 0: d.text((94, 510 + 46 * j), f, font=F["fact"] if len(f) < 50 else fnt(31, False), fill=(226, 232, 246, int(255 * af)))
            ins = s.get("insets", [])
            for q, (ik, cap, cred) in enumerate(ins):
                k = "in_" + ik
                if k not in T: continue
                i0 = s["t0"] + s["hold"] * .30; per = (s["t1"] - i0) / len(ins); ai = fade(t, i0 + per * q, i0 + per * (q + 1) + (.5 if q == len(ins) - 1 else -.2), 1.2)
                if ai > 0:
                    im = Image.fromarray(T[k].astype(np.uint8)); im.thumbnail((380, 190)); im.putalpha(int(255 * ai)); px, py = 520, 760; ov.alpha_composite(im, (px, py)); d.rectangle([px - 2, py - 2, px + im.width + 1, py + im.height + 1], outline=(200, 210, 236, int(200 * ai)), width=2)
                    d.text((px + im.width + 18, py + 6), cap, font=F["cap"], fill=(236, 238, 246, int(255 * ai))); d.text((px + im.width + 18, py + 38), "Image: " + cred, font=F["small"], fill=(150, 170, 210, int(255 * ai))); d.text((px + im.width + 18, py + 64), "public domain", font=F["small"], fill=(150, 170, 210, int(255 * ai)))
            if s["key"] == "earth":
                am = fade(t, s["t0"] + HOLD0 * .45 + PERFACT * 2, s["t1"] + 1.0)
                if am > 0 and z > .3:
                    Rr = FOC / math.sqrt(z * z + BX * BX + BY * BY) * .92; cx, cy = W / 2 + FOC * BX / z + 1.0, H / 2 + FOC * BY / z + 30; d.text((cx - Rr * 2.25, cy - Rr * .72 - Rr * .27 - 34), "Moon (not to scale)", font=F["cap"], fill=(236, 238, 246, int(255 * am)), anchor="ma")
    # 移動中の文
    for i, lines in enumerate(CRUISE):
        a0 = STOPS[i]["t1"] + DEP + 1.5; a1 = STOPS[i + 1]["t0"] - APPR * .55; n = len(lines); per = (a1 - a0) / n
        for j, ln in enumerate(lines):
            al = fade(t, a0 + per * j, a0 + per * (j + 1) - .3, 1.0, 1.0)
            if al > 0: d.text((W / 2 + 120, H / 2 + 40), ln, font=F["cru"] if len(ln) < 52 else fnt(38, False), fill=(240, 242, 250, int(255 * al)), anchor="mm")
    if t < INTRO + 1:   # 題
        a = fade(t, .3, INTRO - .2, 1.0, 1.2); d.text((W / 2, H / 2 - 60), "LEAVING THE SUN AT THE SPEED OF LIGHT", font=fnt(70), fill=(255, 255, 255, int(255 * a)), anchor="mm"); d.text((W / 2, H / 2 + 30), "A real-distance journey to Voyager 1 — one light-day away", font=F["sub"], fill=(255, 226, 150, int(255 * a)), anchor="mm")
    for j, ln in enumerate(OUTRO):
        a0 = T_OUT + 13 + 9 * j; al = fade(t, a0, a0 + 8.6, 1.0, 1.0)
        if al > 0: d.text((W / 2, H / 2), ln, font=F["cru"], fill=(240, 242, 250, int(255 * al)), anchor="mm")
    out = np.asarray(Image.alpha_composite(img, ov).convert("RGB"), np.float32) / 255
    if t > T_OUT + 10 and bi is not None: pass
    g = float(sstep(0, 1.5, t) * (1 - sstep(DUR - 3, DUR, t))); return (np.clip(out * g, 0, 1) * 255).astype(np.uint8)

def render_part(a, b, path):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    import time; t0 = time.time()
    for i in range(a, b):
        p.stdin.write(frame(i / FPS).tobytes())
        if (i - a) % 900 == 0: print(f"  {path} {i - a}/{b - a} コマ {time.time() - t0:.0f}秒", flush=True)
    p.stdin.close(); p.wait()

# ---------- 音：瞑想の系統（長い余韻の音、ゆっくりした和音、低い持続音）。着いた時と、文が出るたびに1音 ----------
def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)
PROG = [(50, 54, 57), (57, 61, 64), (59, 62, 66), (54, 57, 61), (55, 59, 62), (50, 54, 57), (55, 59, 62), (57, 61, 64)]   # D A Bm F#m G D G A（カノンの進行）
def audio(path, a=0.0, b=None):
    b = b or DUR; N = int(SR * (b - a)); dry = np.zeros((N, 2), np.float32); snd = np.zeros((N, 2), np.float32); bc = {}
    def bowl(m):
        if m not in bc:
            f = mtof(m); tt = np.arange(int(SR * 9.0)) / SR; x = (np.sin(2 * np.pi * f * tt) + .8 * np.sin(2 * np.pi * (f + .55) * tt)) * np.exp(-tt / 3.2) + .30 * np.sin(2 * np.pi * f * 2.71 * tt + 1) * np.exp(-tt / 1.5) + .10 * np.sin(2 * np.pi * f * 5.2 * tt + 2) * np.exp(-tt / .6)
            bc[m] = (x * np.minimum(1, tt / .035) * np.minimum(1, (9.0 - tt) / 1.0) * (f / 261.6) ** -.35).astype(np.float32)
        return bc[m]
    def put(x, t, pan=.5, g=1.0, send=.5):
        i = int(round((t - a) * SR))
        if i >= N or i + len(x) <= 0: return
        if i < 0: x = x[-i:]; i = 0
        k = min(len(x), N - i); l, r = math.cos(pan * math.pi / 2) * g, math.sin(pan * math.pi / 2) * g; dry[i:i + k, 0] += x[:k] * l; dry[i:i + k, 1] += x[:k] * r; snd[i:i + k, 0] += x[:k] * l * send; snd[i:i + k, 1] += x[:k] * r * send
    CH = 8.0; pc = {}
    def pad(ms, d_):
        key = tuple(ms)
        if key not in pc:
            tt = np.arange(int(SR * d_)) / SR; s = np.zeros(len(tt))
            for q, m_ in enumerate(ms): f = mtof(m_); s += (np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * f * 1.004 * tt + q) + .2 * np.sin(4 * np.pi * f * tt + 2 * q)) / (1 + .25 * q)
            pc[key] = (s * np.minimum(1, tt / 2.6) * np.minimum(1, (d_ - tt) / 2.6)).astype(np.float32)
        return pc[key]
    for sl in range(int(a // CH) - 1, int(b // CH) + 1):
        r_, t3, f5 = PROG[sl % 8]; put(pad([r_ - 12, r_, f5, t3 + 12], CH + 2.8) * .020, sl * CH - 1.4, .5, 1.0, .8)
    rg = np.random.default_rng(4)
    def chord_at(t): return PROG[int(t // CH) % 8]
    for i, s in enumerate(STOPS):
        r_, t3, f5 = chord_at(s["t0"]);
        for m_, g_, dt in ((r_ - 12, .5, 0), (r_, .4, .0), (f5, .3, .5), (t3 + 12, .28, 1.0), (r_ + 24, .2, 1.6)): put(bowl(m_), s["t0"] - 1.0 + dt, .5 + .25 * math.sin(m_), g_ * .55, .9)   # 着いた
        for j in range(len(s["facts"])):
            tf = s["t0"] + HOLD0 * .45 + PERFACT * j; c_ = chord_at(tf); m_ = (c_[j % 3] + 12 + (12 if j % 2 else 0)); put(bowl(m_), tf, .35 + .3 * rg.random(), .26, .9)
    for i, lines in enumerate(CRUISE):
        a0 = STOPS[i]["t1"] + DEP + 1.5; a1 = STOPS[i + 1]["t0"] - APPR * .55; per = (a1 - a0) / len(lines)
        for j in range(len(lines)): tf = a0 + per * j; c_ = chord_at(tf); put(bowl(c_[(j + 1) % 3] + 12), tf, .6, .2, .9)
        tq = a0
        while tq < a1:   # 移動中：ぽつぽつと高い音
            c_ = chord_at(tq); put(bowl(c_[int(rg.integers(0, 3))] + 24), tq, .2 + .6 * rg.random(), .09, .95); tq += float(rg.uniform(3.5, 7.5))
    for j in range(len(OUTRO)): tf = T_OUT + 13 + 9 * j; c_ = chord_at(tf); put(bowl(c_[j % 3] + 12), tf, .5, .26, .9)
    tt_ = np.arange(int(SR * 2.6)) / SR; out = dry.copy()
    for c in (0, 1):
        ir = (np.convolve(np.random.default_rng(11 + c).normal(0, 1, len(tt_)) * np.exp(-tt_ * 1.2), np.ones(60) / 60, "same") * .02).astype(np.float32)
        from scipy.signal import fftconvolve
        for q in range(0, N, SR * 60):
            y = fftconvolve(snd[q:q + SR * 60, c], ir); k = min(len(y), N - q); out[q:q + k, c] += y[:k]
    tq = a + np.arange(N) / SR; dr = (.007 * (1 + .35 * np.sin(2 * np.pi * tq / 23)) * (np.sin(2 * np.pi * 73.42 * tq) + .7 * np.sin(2 * np.pi * 110.0 * tq) + .5 * np.sin(2 * np.pi * 146.83 * tq + .5 * np.sin(2 * np.pi * tq / 17)))).astype(np.float32); out += dr[:, None]
    env = (sstep(0, 3, tq) * (1 - sstep(DUR - 5, DUR, tq))).astype(np.float32); out *= env[:, None]; pk = float(np.abs(out).max()) or 1.0; out = np.tanh(out / pk * 1.6) / math.tanh(1.6) * .5
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32767).astype(np.int16).tobytes())

def thumb(path):
    buf = background().copy(); sphere(buf, "saturn", 1500, 560, 300, 40.0); sphere(buf, "sun", -260, 540, 620, 3.0); sphere(buf, "earth", 760, 800, 120, 30.0)
    im = Image.fromarray((np.clip(buf, 0, 1) * 255).astype(np.uint8)); d = ImageDraw.Draw(im)
    d.line([(380, 540), (1900, 300)], fill=(255, 240, 190), width=8)
    d.text((70, 60), "1 LIGHT-DAY", font=fnt(190), fill=(255, 226, 120), stroke_width=12, stroke_fill=(6, 6, 16)); d.text((80, 270), "AT LIGHT SPEED", font=fnt(104), fill=(255, 255, 255), stroke_width=10, stroke_fill=(6, 6, 16))
    d.text((80, 900), "SUN → VOYAGER 1", font=fnt(96), fill=(255, 255, 255), stroke_width=10, stroke_fill=(6, 6, 16))
    im.resize((1280, 720), Image.LANCZOS).save(path, quality=92)

if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "all"
    if m == "info":
        print("長さ", round(DUR / 60, 2), "分"); [print(f"  {s['t0']:7.1f}〜{s['t1']:7.1f}  {s['name']:10s} {fmt_time(s['au'] * AU_LS)}  {fmt_km(s['au'] * AU_KM)}") for s in STOPS]
    elif m == "stills":
        for x in sys.argv[2].split(","): Image.fromarray(frame(float(x))).save(f"{B}/s_{float(x):07.1f}.jpg", quality=90)
    elif m == "part": render_part(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    elif m == "thumb": thumb(sys.argv[2] if len(sys.argv) > 2 else "output/lightride1_en_thumb.jpg")
    elif m == "clip":
        a, b, out = float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]; render_part(int(a * FPS), int(b * FPS), f"{B}/c.mp4"); audio(f"{B}/c.wav", a, b)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{B}/c.mp4", "-i", f"{B}/c.wav", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out], check=True)
    else:
        out = sys.argv[2] if len(sys.argv) > 2 else "output/lightride1_en.mp4"; n = int(DUR * FPS); h = n // 2
        ps = [subprocess.Popen([sys.executable, __file__, "part", str(a), str(b), f"{B}/p{q}.mp4"]) for q, (a, b) in enumerate(((0, h), (h, n)))]; audio(f"{B}/a.wav"); [p.wait() for p in ps]
        open(f"{B}/list.txt", "w").write("file 'p0.mp4'\nfile 'p1.mp4'\n")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{B}/list.txt", "-i", f"{B}/a.wav", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True); print(out, round(DUR / 60, 1), "分")
