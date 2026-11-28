# podfill.py — 枝豆のさやの中で、玉が壁に当たるたびに2つに分かれる。さやがいっぱいになったら、中の豆は何粒？（縦のショート 1080×1920・60コマ）
#   参考（2026-11-28 探す係）：果物の輪郭の中で、壁に当たるたびに2倍 → いっぱいになると玉が絵の色になり、果物の絵が内側から塗られる型
#     KXsEcN_UjZA 7.7万回／1日（登録1.25万人）ほか同じ型3本。docs/trend/2026-11-28.md の I
#   まねたのは しくみ（輪郭の中で倍々 → 満杯で絵になる）だけ。器（枝豆のさや）・問い（輪郭からは豆の数が分からない → 何粒？）・色・文字は自前
#   決まり：玉は重力もまさつもなく、まっすぐ飛ぶ。さやの壁に当たるとはね返り、そのとき2つに分かれる（はね返る向きから左右に少しずつ開く）。8192個（2の13乗）で止める
#           いっぱいになったら、下の先から上へ、玉がその場所の絵の色に変わる → 玉がゆっくり止まり、すき間なく1枚の絵になる
#   音：玉が壁に当たった瞬間だけ（trendkit の Audio。材質は1本ごとに回す＝この動画は竹）。上の方で当たるほど高い音。1個 → 2個 → 4個…で拍が自然に細かくなる。最後は玉が遅くなり、音もまばらになる
#   python3 tools/podfill.py search [数] ／ stills ／ all（LANG_OUT=en で英語、SEED=<数>、MAT=…）→ output/podfill1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T

W, H, FPS = T.W, T.H, T.FPS
SEED = int(os.environ.get("SEED", "11")); MAT = os.environ.get("MAT", "bamboo")
CAPN = 8192; RB = 10.0; SPEED = float(os.environ.get("SPEED", "185")); SUB = 2; DT = 1 / (FPS * SUB)
Y0, Y1 = 300, 1640                                                     # さやの上下の先
REVEAL, SLOW, MELT, HOLD = 2.6, 3.4, 1.4, 2.4                           # 色が変わる波・止まるまで・1枚の絵になる・最後に見せる（秒）
# 色（11/28「配色として綺麗に」）：分かれた回数で色が進む。金・珊瑚・薔薇・すみれ・空・若葉
PAL = [(242, 200, 110), (240, 150, 120), (226, 120, 150), (170, 130, 214), (120, 170, 226), (150, 206, 150)]

# ---------- さやの形 ----------
def center_x(s): return 540 + 70 * (1 - s * s) - 40 * s                   # s＝-1（上の先）〜1（下の先）。少し弓なり
def half_w(s): return 215 * np.clip(1 - np.abs(s) ** 2.4, 0, 1) ** .62
def pod_mask(scale=1):
    yy, xx = np.mgrid[0:H * scale, 0:W * scale].astype(np.float32) / scale
    s = (yy - (Y0 + Y1) / 2) / ((Y1 - Y0) / 2); inside = (np.abs(s) < 1) & (np.abs(xx - center_x(s)) < half_w(s))
    return inside
MASK = pod_mask()
_din = cv2.distanceTransform(MASK.astype(np.uint8), cv2.DIST_L2, 5); _dout = cv2.distanceTransform((~MASK).astype(np.uint8), cv2.DIST_L2, 5)
SDF = cv2.GaussianBlur((_dout - _din).astype(np.float32), (0, 0), 1.5)  # 外が＋、中が－
GY, GX = np.gradient(SDF)
def sample(A, x, y):
    x = np.clip(x, 0, W - 2); y = np.clip(y, 0, H - 2); x0 = x.astype(int); y0 = y.astype(int); fx = x - x0; fy = y - y0
    return A[y0, x0] * (1 - fx) * (1 - fy) + A[y0, x0 + 1] * fx * (1 - fy) + A[y0 + 1, x0] * (1 - fx) * fy + A[y0 + 1, x0 + 1] * fx * fy

# 豆（3粒。輪郭はなめらかなので、外からは数が分からない）
BEANS = [(-.56, 150, 172), (.0, 158, 184), (.55, 150, 170)]             # (s, 横の半径, 縦の半径)

def simulate(seed, record=False):
    rng = np.random.default_rng(seed); a = rng.uniform(0, 2 * math.pi)
    P = np.zeros((CAPN, 2), np.float32); V = np.zeros((CAPN, 2), np.float32); G = np.zeros(CAPN, np.int16); n = 1
    P[0] = (center_x(-.1) + 110, (Y0 + Y1) / 2 - 140); V[0] = (SPEED * math.cos(a), SPEED * math.sin(a))
    t = 0.0; step = 0; hits = []; frames = []; t_full = None; t_end = None
    while True:
        k = 1.0
        if t_full is not None:                                            # いっぱいになったら、ゆっくり止まる
            k = max(0.0, 1 - T.sstep(t_full + .8, t_full + .8 + SLOW, t))
        P[:n] += V[:n] * DT * k
        d = sample(SDF, P[:n, 0], P[:n, 1]); hit = np.flatnonzero(d > -RB)
        if len(hit):
            gx = sample(GX, P[hit, 0], P[hit, 1]); gy = sample(GY, P[hit, 0], P[hit, 1]); gn = np.hypot(gx, gy) + 1e-6; nx, ny = gx / gn, gy / gn
            dh = d[hit]; vn = V[hit, 0] * nx + V[hit, 1] * ny; go = vn > 0; hit, nx, ny, vn, dh = hit[go], nx[go], ny[go], vn[go], dh[go]
            V[hit, 0] -= 2 * vn * nx; V[hit, 1] -= 2 * vn * ny
            pen = dh + RB; P[hit, 0] -= pen * nx; P[hit, 1] -= pen * ny
            for j, i in enumerate(hit):
                hits.append((t, float(P[i, 0]), float(P[i, 1]), int(G[i]), k))
                jt = rng.normal(0, .16); cj, sj = math.cos(jt), math.sin(jt); vx, vy = float(V[i, 0]), float(V[i, 1])   # 壁は少しでこぼこ（はね返る向きが少しばらける）
                if (cj * vx - sj * vy) * nx[j] + (sj * vx + cj * vy) * ny[j] < 0: V[i] = (cj * vx - sj * vy, sj * vx + cj * vy)
                if n < CAPN:                                              # 2つに分かれる：はね返る向きから左右に開く
                    th = rng.uniform(.25, .85); c, s_ = math.cos(th), math.sin(th); vx, vy = float(V[i, 0]), float(V[i, 1])
                    V[i] = (c * vx - s_ * vy, s_ * vx + c * vy); V[n] = (c * vx + s_ * vy, -s_ * vx + c * vy)
                    P[n] = P[i]; G[i] += 1; G[n] = G[i]; n += 1
                    if n == CAPN and t_full is None: t_full = t
        if record and step % SUB == 0: frames.append((t, n, P[:n].copy(), G[:n].copy(), k))
        t += DT; step += 1
        if t_full is not None and t_end is None and t > t_full + .8 + SLOW: t_end = t
        if t_end is not None and t > t_end + MELT + HOLD: break
        if t > 45: break
    return dict(t_full=t_full, hits=hits, frames=frames, dur=t, first=hits[0][0] if hits else 99)

def score(r):
    if r["t_full"] is None: return -99
    return -abs(r["t_full"] - 19) - 3 * max(0, r["first"] - .9) - 3 * max(0, .35 - r["first"])

# ---------- 絵 ----------
def picture():
    """答えの絵：ひらいたさやと、中の豆。2倍の大きさで描いて縮める"""
    S = 2; yy, xx = np.mgrid[0:H * S, 0:W * S].astype(np.float32) / S
    s = (yy - (Y0 + Y1) / 2) / ((Y1 - Y0) / 2); cx = center_x(s); hw = half_w(s) + 1e-3; u = (xx - cx) / hw   # u＝-1〜1（さやの左右）
    inside = (np.abs(s) < 1) & (np.abs(u) < 1)
    shell = np.array([.42, .68, .26], np.float32); lining = np.array([.80, .88, .62], np.float32)
    rim = np.clip((np.abs(u) - .80) / .2, 0, 1)                           # ふち：外の皮の緑が見える
    img = lining[None, None] * (1 - rim[..., None]) + shell[None, None] * rim[..., None]
    img *= (1.05 - .18 * np.clip((u + .2), 0, 1) - .10 * (s + 1) / 2)[..., None]                 # 左上から光
    img += (.06 * np.exp(-((u + .55) / .18) ** 2))[..., None]                                     # ふちの内側のつや
    for (sb, rx, ry) in BEANS:                                                                    # 豆
        by = (Y0 + Y1) / 2 + sb * (Y1 - Y0) / 2; bx = center_x(sb) - 4; X = (xx - bx) / rx; Y = (yy - by) / ry; d2 = X * X + Y * Y
        sh = np.exp(-d2 / 1.3) * (d2 < 1.45); img *= (1 - .16 * np.clip(sh - .25, 0, 1))[..., None]          # 豆のまわりのくぼみの影
        nz = np.sqrt(np.clip(1 - d2, 0, 1)); al = np.clip((1 - np.sqrt(d2)) * min(rx, ry) * S * .5 + .5, 0, 1)
        lam = np.clip(-X * .45 - Y * .55 + nz * .70, 0, 1)
        bean = np.array([.56, .80, .30], np.float32)[None, None] * (.62 + .48 * lam)[..., None] + (.30 * np.clip(lam - .82, 0, 1) / .18)[..., None] * .5
        img = img * (1 - al[..., None]) + bean * al[..., None]
    img = np.clip(img, 0, 1); bg = T.background()
    big_bg = cv2.resize(bg, (W * S, H * S)); out = np.where(inside[..., None], img, big_bg)
    return cv2.resize(out, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)
PIC = None; BG = None; WALL = None
def assets():
    global PIC, BG, WALL
    if PIC is None:
        PIC = picture(); BG = T.background()
        edge = np.clip(1 - np.abs(SDF + 1.2) / 2.2, 0, 1).astype(np.float32)                    # さやの壁：細い芯＋うすいにじみ
        halo = cv2.GaussianBlur(edge, (0, 0), 7) * .55
        WALL = np.dstack([edge * .9 + halo, edge * .75 + halo * .8, edge * .55 + halo * .5]).astype(np.float32) * np.array([.86, 1.0, .74], np.float32) * 1.35
        BG = BG * (1 - .25 * MASK[..., None].astype(np.float32))                                # さやの中は少し暗く
    return PIC, BG, WALL

_sp = {}
def spr(col):
    """色ごとの飴玉（色をまるめて、作った絵を使い回す）。半画素ずつずらした4つ"""
    key = tuple(int(c) // 6 * 6 for c in col)
    if key not in _sp:
        sp = T.sprite(key, RB); h, w = sp.shape[:2]; pm = np.dstack([sp[..., :3] * sp[..., 3:4], sp[..., 3:4]]).astype(np.float32); vs = []
        for oy in (0, .5):
            for ox in (0, .5):
                vs.append(cv2.warpAffine(pm, np.float32([[1, 0, ox], [0, 1, oy]]), (w + 1, h + 1), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0))
        _sp[key] = vs
    return _sp[key]
def stamp(buf, col, x, y):
    vs = spr(col); h, w = vs[0].shape[:2]; fx, fy = x - (w - 1) / 2, y - (h - 1) / 2; x0, y0 = int(math.floor(fx)), int(math.floor(fy))
    pm = vs[(2 if fy - y0 >= .25 and fy - y0 < .75 else 0) + (1 if fx - x0 >= .25 and fx - x0 < .75 else 0)]
    if fy - y0 >= .75: y0 += 1
    if fx - x0 >= .75: x0 += 1
    reg = buf[y0:y0 + h, x0:x0 + w]; s = pm[:reg.shape[0], :reg.shape[1]]; reg *= 1 - s[..., 3:4]; reg += s[..., :3]

def wave_pos(r, t):
    """色が変わる波の位置（s：1＝下の先 → -1＝上の先）。まだなら 2"""
    tf = r["t_full"]
    if tf is None or t < tf + .4: return 2.0
    return 1.15 - 2.3 * T.sstep(tf + .4, tf + .4 + REVEAL, t)

def melt_pre(r, t):
    return 0.0 if r["t_full"] is None else T.sstep(r["t_full"] + .8 + SLOW - .4, r["t_full"] + .8 + SLOW + MELT, t)
TR = None
def make_frame(r, i):
    global TR
    pic, bg, wall = assets(); fr = r["frames"]; t, n, P, G, k = fr[min(i, len(fr) - 1)]
    buf = bg.copy()
    if TR is None: TR = T.Trail(0, H, half=.9)
    tf = r["t_full"]; wp = wave_pos(r, t)
    # 玉の色：分かれた回数で進む色 → 波が通ったら、その場所の絵の色
    s = (P[:, 1] - (Y0 + Y1) / 2) / ((Y1 - Y0) / 2)
    xi = np.clip(P[:, 0].astype(int), 0, W - 1); yi = np.clip(P[:, 1].astype(int), 0, H - 1); pc = pic[yi, xi] * 255
    base = np.array([PAL[g % len(PAL)] for g in G], np.float32) if n < 600 else np.asarray(PAL, np.float32)[G % len(PAL)]
    m = np.clip((s - wp) / .12, 0, 1)[:, None]                                                    # 波より下（s が大きい）ほど絵の色
    cols = base * (1 - m) + pc * m
    # 跡（玉が少ないうちだけ。多くなると消す）
    tg = 1.0 if n <= 16 else max(0.0, 1 - math.log2(n / 16) / 4)
    if i > 0 and tg > 0:
        tp, _, PP, _, _ = fr[i - 1]; segs = [(float(PP[j, 0]), float(PP[j, 1]), float(P[j, 0]), float(P[j, 1]), tuple(cols[j]), SPEED) for j in range(min(len(PP), 64))]
        TR.step(segs)
    elif i > 0: TR.step([])
    if tg > 0: TR.gain = tg; TR.render(buf)
    buf = 1 - (1 - buf) * (1 - wall * (.55 + .25 * (1 - k)))
    # 当たった所が少し光る（壁に、当たった玉の色が映る）
    import bisect
    if "ht" not in r: r["ht"] = [h[0] for h in r["hits"]]
    a0, a1 = bisect.bisect_left(r["ht"], t - .35), bisect.bisect_right(r["ht"], t)
    if a1 - a0 <= 48 and melt_pre(r, t) < 1:
        gg = T.glow(14)
        for (th, hx, hy, g, kk) in r["hits"][a0:a1]:
            e = (t - th) / .35; T.add_glow(buf, gg, hx, hy, PAL[(g - 1) % len(PAL)], .55 * (1 - e) ** 2)
    melt = melt_pre(r, t)
    if melt < .999:
        for j in range(n): stamp(buf, cols[j], float(P[j, 0]), float(P[j, 1]))
    if melt > 0:                                                                                  # すき間なく1枚の絵になる
        mk = MASK[..., None].astype(np.float32); buf = buf * (1 - mk * melt) + pic * mk * melt
    def draw(d):
        INK = (236, 238, 230, 255)
        T.fit_text(d, (W / 2, 128), T.tr("壁に当たるたびに、2つに分かれる", "Every bounce splits the ball in two"), 52, 980, (200, 206, 196, 255), bold=False)
        T.fit_text(d, (W / 2, 210), T.tr("さやがいっぱいになったら、豆は何粒？", "When the pod is full... how many beans?"), 60, 1000, INK)
        d.text((W / 2, 1790), f"{n:,}", font=T.fnt(110), fill=(236, 238, 230, 255), anchor="mm")
    return T.to_frame(buf, draw, grain=i)

def audio(r, path):
    a = T.Audio(r["dur"], lo=62, hi=88, mat=MAT, max_same=2, window=.04)
    for (t, x, y, g, k) in r["hits"]:
        u = 1 - (y - Y0) / (Y1 - Y0); a.hit(t, .04 + .92 * u, vel=(.42 + .45 * k) * min(1.0, .55 + .45 * 16 / max(16, 2 ** min(g, 12))))
    return a.write(path)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_podfill", exist_ok=True)
    if cmd == "search":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        def quick(sd):
            r = simulate(sd); print(sd, "最初の当たり", round(r["first"], 2), "満杯", r["t_full"] and round(r["t_full"], 1), "長さ", round(r["dur"], 1)); return r
        T.pick_seed(quick, score, range(n)); sys.exit()
    r = simulate(SEED, record=True); nf = len(r["frames"])
    print("長さ", round(r["dur"], 1), "秒 最初の当たり", round(r["first"], 2), "満杯", round(r["t_full"], 1), "当たり", len(r["hits"]))
    if cmd == "stills": print(T.stills(nf, lambda i: make_frame(r, i), "build_podfill/s", at=(.01, .3, .6, .8, .88, .93, .99))); sys.exit()
    out = f"output/podfill1_{T.LANG}.mp4"; wav = "build_podfill/a.wav"; audio(r, wav); T.encode(nf, lambda i: make_frame(r, i), wav, out); print(out)
