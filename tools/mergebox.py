# mergebox.py — 箱の中で、同じ星がぶつかると1つ大きい星になる（オーナー 11/26「これのスイカゲームみたいなしたやつ作って」。mergecol の続き）
#   しくみ：上の口が左右に動いて星を落とす。星は重力で落ち、転がり、積み重なる（物理は pymunk。摩擦あり＝星は転がる）。
#           同じ星どうしが触れると合体して1つ大きい星になる（月→水星→…→木星→太陽）。箱の上の線をこえて積もる前に太陽ができるか。
#           落とす星の種類と位置は乱数で決め（同じ星の真上をねらうことが多い）、たくさんの回の中から太陽までできた回を選ぶ。
#   音：合体の瞬間にだけ石の音が1音。合体するたびにカノンの旋律が1音進む（大きい星の合体ほど低い音が重なる）。
#   python3 tools/mergebox.py [out.mp4]   SEARCH=60 で回をさがす / SEED=n で回を指定 / STILLS=3,9,15 で絵だけ / LANG_OUT=en で英語
import math, os, sys, subprocess, wave, random
import numpy as np
import pymunk

W, H, FPS, SR = 1080, 1920, 60, 48000
LANG = os.environ.get("LANG_OUT", "ja"); EN = LANG == "en"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"output/mergebox1_{LANG}.mp4"
NT = 10
R0 = float(os.environ.get("R0", 26.5)); RAD = [R0 * 1.235 ** k for k in range(9)] + [R0 * 6.8]
MASS = [(r / RAD[0]) ** 2 for r in RAD]
XL, XR, YB = 140.0, 940.0, 1440.0            # 箱の内側（左・右・底）
YWALL, YLIM, YRAIL = 560.0, 690.0, 470.0     # 壁の上の端、あふれの線、口が動くレール
GRAV = 5200.0; SUB = 4; DT = 1.0 / (FPS * SUB)
BEAT = 60 / 112.0
# 落とす間隔：2小節ごとに速くなる（4分 → 8分 → 3連 → 16分）
SCHED = [(0.0, BEAT), (6 * BEAT, BEAT / 2), (22 * BEAT, BEAT / 3), (40 * BEAT, BEAT / 4)]
def interval(t):
    iv = SCHED[0][1]
    for t0, v in SCHED:
        if t >= t0: iv = v
    return iv
TMAX = 34.0; TAIL = 3.4

def simulate(seed, record=False, P=None):
    P = P or {}
    rnd = random.Random(seed); sp = pymunk.Space(); sp.gravity = (0, GRAV); sp.iterations = 12; sp.damping = P.get("damp", .55)
    for a, b in (((XL, YWALL - 400), (XL, YB)), ((XR, YWALL - 400), (XR, YB)), ((XL, YB), (XR, YB))):
        s = pymunk.Segment(sp.static_body, a, b, 3); s.friction = .6; s.elasticity = .1; sp.add(s)
    B = {}; nid = [0]
    def add(k, x, y, vx=0.0, vy=0.0, ang=0.0, w=0.0, r0=None, t=0.0, fresh=False):
        m = MASS[k]; b = pymunk.Body(m, pymunk.moment_for_circle(m, 0, RAD[k])); b.position = (x, y); b.velocity = (vx, vy); b.angle = ang; b.angular_velocity = w
        s = pymunk.Circle(b, r0 or RAD[k]); s.friction = .5; s.elasticity = P.get("el", .12); sp.add(b, s); nid[0] += 1
        B[nid[0]] = dict(k=k, b=b, s=s, born=t, grow=(r0 is not None), fresh=fresh, pv=(vx, vy), land=(None if fresh else t - 1.0), slow=0.0); return nid[0]
    t = 0.0; best = 0; drops = []; merges = []; toks = []; frames = []; tsun = None; over = 0.0; overflow = False; topmin = YB; nd = 0
    tnext = P.get("t0", .55); held = None; hx = (XL + XR) / 2; hx_from = hx; t_dec = 0.0; mass_dropped = 0
    def choose(tnow):
        md = min(P.get("maxdrop", 4) + (1 if best >= P.get("up1", 5) else 0) + (1 if best >= P.get("up2", 7) else 0), max(0, best - 1)); items = [(v["b"].position.x, v["b"].position.y, RAD[v["k"]], v["k"]) for v in B.values() if not v["fresh"]]
        fly = [(v["b"].position.x, v["k"]) for v in B.values() if v["fresh"]]
        def free(x, k): return not any(kk == k and abs(x - fx) < RAD[k] * 1.2 for fx, kk in fly)
        def hit(x, r):   # x にまっすぐ落としたとき、最初に当たる相手と、そのときの中心の高さ
            bi, by = None, YB - r
            for i, (bx, byy, br, bk) in enumerate(items):
                dx = abs(x - bx)
                if dx < br + r:
                    yh = byy - math.sqrt((br + r) ** 2 - dx * dx)
                    if yh < by: by, bi = yh, i
            return bi, by
        def valley(r):
            lo, hi = XL + r + 4, XR - r - 4; xs = [lo + (hi - lo) * q / 24 for q in range(25)]; hs = [hit(x, r)[1] for x in xs]; m = max(hs); return rnd.choice([x for x, h in zip(xs, hs) if h > m - 30])
        if nd < 2: k = 0
        elif rnd.random() < P.get("small", 0) and not (LONG and top < YLIM + P.get("press", 260)):   # こまかい星（月・水星）をばらまく（オーナー 11/26「こまかいのもっとだしたい。ツキとか」）
            k = 0 if rnd.random() < .78 else 1; r = RAD[k]; return k, rnd.uniform(XL + r + 4, XR - r - 4)
        elif rnd.random() < (1.0 if (LONG and top < YLIM + P.get("press", 260)) else P.get("match", .82)):   # 上があいている星に、同じ星を落とす
            ex = []
            for i, (bx, byy, br, bk) in enumerate(items):
                if bk <= md and XL + br + 4 <= bx <= XR - br - 4 and free(bx, bk) and hit(bx, br)[0] == i:
                    chain = any(kk == bk + 1 and math.hypot(bx - xx, byy - yy) < RAD[bk + 1] + rr + 16 for (xx, yy, rr, kk) in items) if bk + 1 < NT else False
                    ex.append((P.get("wk", 1.6) ** bk * (P.get("wchain", 2.2) if chain else 1.0), bx, bk))
            if ex:
                w_, x, k = rnd.choices(ex, [e[0] for e in ex])[0]; r = RAD[k]; return k, min(XR - r - 4, max(XL + r + 4, x + rnd.uniform(-3, 3)))
            k = rnd.choice(range(min(md, 2) + 1))
        else: k = rnd.choice(range(min(md, P.get("randmax", 3)) + 1))
        r = RAD[k]; lo, hi = XL + r + 4, XR - r - 4
        cands = [(byy, bx) for i, (bx, byy, br, bk) in enumerate(items) if bk == k and lo <= bx <= hi and free(bx, k) and hit(bx, r)[0] == i]
        if cands and rnd.random() < P.get("aim", .8): x = rnd.choice(cands)[1] + rnd.uniform(-3, 3)
        elif rnd.random() < P.get("valley", .7): x = valley(r)
        else: x = rnd.uniform(lo, hi)
        return k, min(hi, max(lo, x))
    held = choose(0.0)
    LONG = P.get("long"); suns = []; top = YB; par = P.setdefault("par", {})
    while t < (LONG or TMAX) and (LONG or tsun is None or t < tsun + TAIL):
        for _ in range(SUB):
            if LONG and t >= tnext and top < YLIM + P.get("hold", 70): tnext = t + P["iv"]   # 長尺：線の近くまで積もったら、合体で下がるまで落とすのを待つ
            if tsun is None and t >= tnext and held is not None:   # 落とす
                k, x = held; add(k, x, YRAIL + 22 + RAD[k], t=t, fresh=True); drops.append((t, k, x)); nd += 1; mass_dropped += 2 ** k
                hx_from = x; t_dec = t; held = choose(t); tnext = t + (P["iv"] if LONG else interval(t))
            for v in B.values(): v["pv"] = (v["b"].velocity.x, v["b"].velocity.y)
            sp.step(DT); t += DT
            for ts_, si in suns:   # 長尺：太陽はしばらく光ってから箱を出ていく
                if si in B and t > ts_ + P.get("sunstay", 3.0): sp.remove(B[si]["b"], B[si]["s"]); del B[si]
            ids = list(B.keys()); n = len(ids)
            if n:
                X = np.array([(B[i]["b"].position.x, B[i]["b"].position.y) for i in ids]); K = np.array([B[i]["k"] for i in ids]); Rr = np.array([B[i]["s"].radius for i in ids])
                for q, i in enumerate(ids):   # 大きくなる途中の星
                    v = B[i]
                    if v["grow"]:
                        f = min(1.0, (t - v["born"]) / .09); r = RAD[v["k"] - 1] + (RAD[v["k"]] - RAD[v["k"] - 1]) * f; v["s"].unsafe_set_radius(r)
                        if f >= 1: v["grow"] = False
                if n > 1:
                    d = X[:, None, :] - X[None, :, :]; dist = np.sqrt((d ** 2).sum(-1)); touch = (dist < Rr[:, None] + Rr[None, :] + 1.2) & (K[:, None] == K[None, :]) & (K[:, None] < NT - 1)
                    if P.get("cool"):   # 合体したての星は少し待ってから次の合体へ（連鎖が1つずつ見えて、音もずれて重なる）
                        ok = np.array([not (B[i]["land"] is not None and B[i].get("mg") and t - B[i]["born"] < P["cool"]) for i in ids]); touch &= ok[:, None] & ok[None, :]
                    ii, jj = np.where(np.triu(touch, 1)); used = set()
                    for a, b in sorted(zip(ii.tolist(), jj.tolist()), key=lambda p: dist[p[0], p[1]]):
                        if a in used or b in used: continue
                        used.add(a); used.add(b); va, vb = B[ids[a]], B[ids[b]]; k = va["k"] + 1
                        pa, pb = va["b"], vb["b"]; x, y = (pa.position.x + pb.position.x) / 2, (pa.position.y + pb.position.y) / 2
                        lowa = pa.position.y > pb.position.y; base = pa if lowa else pb
                        nidx = add(k, x, y, (pa.velocity.x + pb.velocity.x) / 2 * .6, (pa.velocity.y + pb.velocity.y) / 2 * .6, base.angle, (pa.angular_velocity + pb.angular_velocity) / 2, r0=RAD[k - 1], t=t)
                        B[nidx]["mg"] = True; B[nidx]["cd"] = 1 + max([vv.get("cd", 0) for vv in (va, vb) if vv.get("mg") and t - vv["born"] < P.get("chainwin", .8)] + [0]); P.setdefault("chainmap", {})[nidx] = B[nidx]["cd"]
                        par[nidx] = (pa.position.x, pa.position.y, pa.angle, pb.position.x, pb.position.y, pb.angle)
                        for vv, key in ((va, ids[a]), (vb, ids[b])): sp.remove(vv["b"], vv["s"]); del B[key]
                        merges.append((t, k, x, y, nidx, k > best)); best = max(best, k)
                        if k == NT - 1 and LONG: suns.append((t, nidx))
                        elif k == NT - 1 and tsun is None: tsun = t
                # 落とした星が最初に何かに当たった瞬間（小さい「コッ」）
                for i in list(B.keys()):
                    v = B[i]
                    if not v["fresh"]: continue
                    p = v["b"].position; r = v["s"].radius; hitf = p.y >= YB - r - 1.5
                    if not hitf:
                        for j, u in B.items():
                            if j != i and (p.x - u["b"].position.x) ** 2 + (p.y - u["b"].position.y) ** 2 < (r + u["s"].radius + 1.5) ** 2: hitf = True; break
                    if hitf: v["fresh"] = False; v["land"] = t; toks.append((t, v["k"], math.hypot(*v["pv"]), p.x, p.y))
        # あふれ：落ちている途中でない星が線より上にある時間
        for v in B.values(): v["slow"] = v["slow"] + 1 / FPS if (v["b"].velocity.length < 90 and not v["fresh"]) else 0.0
        tops = [v["b"].position.y - v["s"].radius for v in B.values() if v["slow"] >= .25]
        top = min(tops) if tops else YB
        if tsun is None:
            topmin = min(topmin, top); over = over + 1 / FPS if top < YLIM else 0.0
            if over > .35: overflow = True
        # 口の位置：次に落とす所へ、なめらかに
        iv = max(1e-3, tnext - t_dec); f = min(1.0, (t - t_dec) / (iv * .62)); f = f * f * (3 - 2 * f); hx = hx_from + ((held[1] if held else hx_from) - hx_from) * f
        if P.get("on_frame"): P["on_frame"](dict(t=t, bodies=[(i, v["k"], v["b"].position.x, v["b"].position.y, v["b"].angle, v["s"].radius, v["born"]) for i, v in B.items()], hx=hx, held=(held[0] if held else None), nd=nd, top=top, suns=len(suns)))
        elif record:
            frames.append(dict(t=t, bodies=[(i, v["k"], v["b"].position.x, v["b"].position.y, v["b"].angle, v["s"].radius, v["born"]) for i, v in B.items()], hx=hx, held=(held[0] if (held and tsun is None) else None), nd=nd, mass=mass_dropped, best=best, top=top))
        if overflow and not record and not LONG: break
    return dict(seed=seed, tsun=tsun, merges=merges, drops=drops, toks=toks, frames=frames, overflow=overflow, topmin=topmin, best=best, mass=mass_dropped, left=len(B), suns=suns, par=par)

def score(r):
    """小さいほどよい。線をこえずに太陽までできた回のうち、線ぎりぎりまで積もり、最後に続けて合体する回"""
    if r["tsun"] is None or r["overflow"] or r["topmin"] < YLIM + 6: return None
    last = sum(1 for m in r["merges"] if r["tsun"] - 1.2 <= m[0] <= r["tsun"])
    return abs(r["tsun"] - 22.5) * 10 + max(0.0, r["topmin"] - YLIM - 30) * .8 + max(0, abs(len(r["merges"]) - 88) - 8) * 1.5 - min(last, 5) * 6

if __name__ == "__main__" and os.environ.get("SEARCH"):
    n = int(os.environ["SEARCH"]); s0 = int(os.environ.get("SEED0", 1)); best = None
    for seed in range(s0, s0 + n):
        r = simulate(seed); sc = score(r)
        last = 0 if r["tsun"] is None else sum(1 for m in r["merges"] if r["tsun"] - 1.2 <= m[0] <= r["tsun"])
        print(f"種{seed:4d} 終わりの合体{last} 太陽{'-' if r['tsun'] is None else round(r['tsun'], 1)} 合体{len(r['merges']):3d} 落とした{len(r['drops']):3d} 月{r['mass']:4d} 残り{r['left']:2d} 最高{r['best']} 上の余白{round(r['topmin'] - YLIM)} {'あふれ' if r['overflow'] else ''} 点{'-' if sc is None else round(sc, 1)}")
        if sc is not None and (best is None or sc < best[0]): best = (sc, seed)
    print("選ぶ種:", best); sys.exit()

# ======================================================================================================================
from collections import deque
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from scipy.signal import fftconvolve, resample_poly, butter, sosfilt
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"; FI = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
def fnt(sz, latin=False): return ImageFont.truetype(FI if (latin or EN) else FJ, sz)
NAMES = ["Moon", "Mercury", "Mars", "Venus", "Earth", "Neptune", "Uranus", "Saturn", "Jupiter", "Sun"] if EN else ["月", "水星", "火星", "金星", "地球", "海王星", "天王星", "土星", "木星", "太陽"]
GLOW = [(210, 214, 226), (214, 190, 164), (240, 130, 90), (246, 222, 160), (110, 170, 255), (110, 140, 255), (170, 232, 240), (240, 214, 160), (240, 190, 140), (255, 206, 96)]
TILT = [.2, -.3, .35, .15, .41, .45, 1.35, .32, .08, 0.0]
LX, LY, LZ = (lambda v: v / np.linalg.norm(v))(np.array([-.48, -.58, .66]))

# ---------- 星の絵（mergecol と同じ模様）。模様は星といっしょに回り、光の当たり方は回らない ----------
def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)
def mixc(a, b, t): return np.asarray(a, np.float32) + (np.asarray(b, np.float32) - np.asarray(a, np.float32)) * t[..., None]
def snoise(P, seed, freqs=(1.3, 2.7, 5.5), amps=(1.0, .5, .25)):
    rng = np.random.default_rng(seed); out = np.zeros(P.shape[:-1], np.float32); tot = 0.0
    for f, a in zip(freqs, amps):
        for _ in range(3):
            d = rng.normal(size=3); d /= np.linalg.norm(d); ph = rng.uniform(0, 6.283)
            out += a * np.sin(f * math.pi * (P @ d.astype(np.float32)) + ph); tot += a
    return out / (tot * .75)
def tex(k, lat, u, v, P):
    if k == 0:
        c = mixc((204, 204, 210), (134, 136, 150), sstep(.05, .5, snoise(P, 11, (1.1, 2.3, 4.6)))); return c * (1 + .05 * snoise(P, 12, (7., 13.), (1, .6)))[..., None]
    if k == 1:
        c = mixc((180, 158, 136), (126, 108, 94), sstep(-.2, .7, snoise(P, 21)) * .7); return c * (1 + .06 * snoise(P, 22, (8., 15.), (1, .6)))[..., None]
    if k == 2:
        c = mixc((212, 104, 64), (148, 70, 52), sstep(.0, .55, snoise(P, 31))); return mixc(c, (242, 238, 234), sstep(.86, .93, -v))
    if k == 3: return mixc((230, 198, 136), (250, 232, 190), .5 + .5 * np.sin(lat * 7 + 1.6 * snoise(P, 41, (1.2, 2.4))))
    if k == 4:
        c = mixc((40, 92, 196), (62, 124, 220), .5 + .5 * snoise(P, 51, (2., 4.)))
        land = sstep(.10, .20, snoise(P, 52, (1.4, 2.9, 5.8))); c = mixc(c, mixc((60, 142, 80), (164, 144, 96), sstep(.0, .6, snoise(P, 53, (2.5, 5.)))), land)
        c = mixc(c, (246, 248, 252), sstep(.88, .95, np.abs(v))); return mixc(c, (250, 250, 252), sstep(.36, .62, snoise(P, 54, (1.8, 3.7, 7.4))) * .82)
    if k == 5: return mixc((60, 96, 224), (42, 68, 182), sstep(.3, 1, np.sin(lat * 6 + .6)) * .55)
    if k == 6: return mixc((154, 218, 228), (128, 198, 214), sstep(.2, 1, np.sin(lat * 4 + .3)) * .6)
    if k == 7: return mixc((230, 202, 148), (194, 164, 114), sstep(-.2, 1, np.sin(lat * 10 + .4) + .5 * np.sin(lat * 23)) * .62)
    if k == 8:
        s = np.sin(lat * 12 + .9 * snoise(P, 71, (2., 4.), (1, .5))); c = mixc((238, 216, 184), (176, 120, 84), sstep(-.3, .5, s)); c = mixc(c, (214, 172, 132), sstep(.5, 1, np.sin(lat * 27 + 1)) * .4)
        return mixc(c, (198, 82, 54), 1 - sstep(.75, 1.05, np.hypot((P[..., 0] - .30) / .22, (v - .30) / .115)))
    m = snoise(P, 91, (3., 6., 12.), (1, .7, .45)); return mixc(mixc((255, 196, 70), (255, 238, 156), sstep(.15, .8, m)), (244, 146, 36), sstep(.2, .9, -m) * .7)
EXT = [1.06] * 7 + [1.95, 1.06, 1.06]
_TEX = {}; _SHD = {}
def tex_img(k, Rp):
    """模様だけの絵（光なし、土星は輪つき）。RGBA の PIL 画像。これを星の角度だけ回して使う"""
    key = (k, int(round(Rp)))
    if key in _TEX: return _TEX[key]
    Rp = float(key[1]); ss = 2 if Rp > 60 else 3; half = int(math.ceil(Rp * EXT[k])) + 2; S = 2 * half; n = S * ss
    c = (np.arange(n, dtype=np.float32) + .5) / ss - half; xx, yy = np.meshgrid(c, c); rr = np.hypot(xx, yy) / Rp; nx, ny = xx / Rp, yy / Rp; nz = np.sqrt(np.clip(1 - rr * rr, 0, 1))
    ca, sa = math.cos(TILT[k]), math.sin(TILT[k]); u = nx * ca + ny * sa; v = -nx * sa + ny * ca
    col = tex(k, np.arcsin(np.clip(v, -1, 1)), u, v, np.stack([u, v, nz], -1).astype(np.float32))
    al = np.clip((1 - rr) * Rp * ss + .5, 0, 1); o = np.zeros((n, n, 4), np.float32); o[..., :3] = np.clip(col, 0, 255) / 255 * al[..., None]; o[..., 3] = al
    if k == 7:
        cp, sp_ = math.cos(-.30), math.sin(-.30); xr = xx * cp + yy * sp_; yr = -xx * sp_ + yy * cp; q = np.hypot(xr / Rp, yr / (Rp * .30))
        m = sstep(1.26, 1.31, q) * (1 - sstep(1.80, 1.86, q)); m *= 1 - .8 * sstep(1.580, 1.60, q) * (1 - sstep(1.635, 1.655, q))
        rc = np.asarray((222, 202, 160), np.float32)[None, None] / 255 * (.74 + .26 * np.sin(q * 21))[..., None] * .86; ra = (m * .84)[..., None]; back, front = (yr <= 0)[..., None], (yr > 0)[..., None]
        o[..., :3] += rc * ra * back * (1 - o[..., 3:4]); o[..., 3:4] += ra * back * (1 - o[..., 3:4])
        o[..., :3] = o[..., :3] * (1 - ra * front) + rc * ra * front; o[..., 3:4] = o[..., 3:4] * (1 - ra * front) + ra * front
    o = o.reshape(S, ss, S, ss, 4).mean((1, 3)); a = np.clip(o[..., 3:4], 1e-4, 1)
    _TEX[key] = Image.fromarray((np.clip(np.concatenate([o[..., :3] / a, o[..., 3:4]], -1), 0, 1) * 255).astype(np.uint8), "RGBA"); return _TEX[key]
def shade(k, Rp):
    """光の当たり方（左上から）。星の円の外（土星の輪）は 1"""
    key = (k, int(round(Rp)))
    if key in _SHD: return _SHD[key]
    Rp = float(key[1]); half = int(math.ceil(Rp * EXT[k])) + 2; S = 2 * half; c = np.arange(S, dtype=np.float32) + .5 - half; xx, yy = np.meshgrid(c, c)
    rr = np.hypot(xx, yy) / Rp; nx, ny = xx / Rp, yy / Rp; nz = np.sqrt(np.clip(1 - rr * rr, 0, 1))
    if k == 9: sh = .74 + .26 * nz ** .55
    else: sh = (.30 + .82 * np.clip(nx * LX + ny * LY + nz * LZ, 0, 1) ** .9) * (.80 + .20 * nz ** .4)
    _SHD[key] = np.where(rr <= 1.0, sh, 1.0).astype(np.float32)[..., None]; return _SHD[key]
_HALO = {}
def halo(Rp):
    key = int(round(Rp))
    if key not in _HALO:
        half = int(key * 1.45) + 2; c = np.arange(2 * half, dtype=np.float32) + .5 - half; xx, yy = np.meshgrid(c, c); rr = np.hypot(xx, yy) / key
        _HALO[key] = (np.exp(-(np.clip(rr - 1, 0, None) / .15) ** 1.25) * .50 * (rr > 1))[..., None] * np.asarray((255, 176, 70), np.float32) / 255
    return _HALO[key]
def draw_body(buf, k, cx, cy, r, ang, pop=1.0, sq=None):
    """buf（float の RGB、0〜1）に星を1つ。模様は ang だけ回す。sq=(横, 縦) で伸び縮み（合体のぷるん）"""
    rr = max(4.0, r * pop); im = tex_img(k, rr)
    if abs(ang) > 1e-4: im = im.rotate(-math.degrees(ang), resample=Image.BICUBIC)
    a = np.asarray(im, np.float32) / 255; sh = shade(k, rr); S = a.shape[0]
    if sq is not None and (abs(sq[0] - 1) > .01 or abs(sq[1] - 1) > .01):
        lit = a.copy(); lit[..., :3] *= sh; im2 = Image.fromarray((np.clip(lit, 0, 1) * 255).astype(np.uint8), "RGBA").resize((max(2, int(round(S * sq[0]))), max(2, int(round(S * sq[1])))), Image.BILINEAR)
        p = np.asarray(im2, np.float32) / 255; h_, w_ = p.shape[:2]; x0 = int(round(cx - w_ / 2)); y0 = int(round(cy - h_ / 2)); xa, ya = max(0, x0), max(0, y0); xb, yb = min(buf.shape[1], x0 + w_), min(buf.shape[0], y0 + h_)
        if xa < xb and ya < yb: q = p[ya - y0:yb - y0, xa - x0:xb - x0]; buf[ya:yb, xa:xb] = buf[ya:yb, xa:xb] * (1 - q[..., 3:4]) + q[..., :3] * q[..., 3:4]
        return
    x0 = int(round(cx - S / 2)); y0 = int(round(cy - S / 2))
    xa, ya = max(0, x0), max(0, y0); xb, yb = min(buf.shape[1], x0 + S), min(buf.shape[0], y0 + S)
    if xa >= xb or ya >= yb: return
    p = a[ya - y0:yb - y0, xa - x0:xb - x0]; al = p[..., 3:4]; buf[ya:yb, xa:xb] = buf[ya:yb, xa:xb] * (1 - al) + p[..., :3] * sh[ya - y0:yb - y0, xa - x0:xb - x0] * al
    if k == 9:
        h = halo(rr); S2 = h.shape[0]; x0 = int(round(cx - S2 / 2)); y0 = int(round(cy - S2 / 2)); xa, ya = max(0, x0), max(0, y0); xb, yb = min(buf.shape[1], x0 + S2), min(buf.shape[0], y0 + S2)
        if xa < xb and ya < yb: buf[ya:yb, xa:xb] += h[ya - y0:yb - y0, xa - x0:xb - x0]
MT = .11   # 合体で2つがくっつくまでの時間
def draw_merge(buf, par, i, k, x, y, ang, r, age, ox, oy, pop=1.0):
    """合体した星：はじめは元の2つが引き合ってつぶれながら1つに重なり（ぷよっとくっつく）、そのあと新しい星がぷるんと揺れて落ち着く"""
    if i in par and age < MT:
        ax, ay, aa, bx, by, ba = par[i]; f = age / MT; f = f * f * (3 - 2 * f); hz = abs(ax - bx) >= abs(ay - by); st = (1 + .22 * f, 1 - .12 * f) if hz else (1 - .12 * f, 1 + .22 * f)
        for px, py, pa in ((ax, ay, aa), (bx, by, ba)): draw_body(buf, k - 1, px + (x - px) * f - ox, py + (y - py) * f - oy, RAD[k - 1] * (1 + .10 * f), pa, sq=st)
        return
    if i in par and age < MT + .7:
        ax, ay, aa, bx, by, ba = par[i]; e = age - MT; w = .26 * math.exp(-e / .17) * math.cos(2 * math.pi * e / .24); hz = abs(ax - bx) >= abs(ay - by)
        draw_body(buf, k, x - ox, y - oy, max(r, RAD[k] * .97), ang, pop, sq=((1 + w, 1 - w * .8) if hz else (1 - w * .8, 1 + w))); return
    draw_body(buf, k, x - ox, y - oy, r, ang, pop)
def icon(k, Rp):
    im = tex_img(k, Rp); a = np.asarray(im, np.float32) / 255; a[..., :3] *= shade(k, Rp); return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGBA")

# ---------- 音：合体するたびに、カノンの旋律が1音進む ----------
def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)
_tc = {}
def stone(m, dec):
    key = (m, round(dec, 1))
    if key not in _tc:
        f = mtof(m); tt = np.arange(int(SR * min(2.4, 7 / dec))) / SR
        s = (np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * f * 1.003 * tt)) * np.exp(-tt * 2.6) + .34 * np.sin(2 * np.pi * f * 2.76 * tt + .7) * np.exp(-tt * 7) \
            + .15 * np.sin(2 * np.pi * f * 5.4 * tt + 1.3) * np.exp(-tt * 15) + .06 * np.sin(2 * np.pi * f * 8.9 * tt) * np.exp(-tt * 28)
        nz = np.random.default_rng(int(m)).normal(0, 1, len(tt)); nz = np.convolve(nz, np.ones(5) / 5, "same") * np.exp(-tt * 700) * .22
        _tc[key] = (s + nz) * np.exp(-tt * max(2.5, dec * .6)) * np.minimum(1, tt / .0008) * np.minimum(1, (tt[-1] - tt) / .02) * (f / 523.25) ** -.3
    return _tc[key]
def tok(pitch=1.0):
    tt = np.arange(int(SR * .05)) / SR; nz = np.random.default_rng(3).normal(0, 1, len(tt)); nz = np.convolve(nz, np.ones(7) / 7, "same")
    return (np.sin(2 * np.pi * 1240 * pitch * tt) * np.exp(-tt * 110) + .5 * np.sin(2 * np.pi * 2480 * pitch * tt) * np.exp(-tt * 190) + nz * np.exp(-tt * 600) * .5) * np.minimum(1, tt / .0005)
PROG = ["D", "A", "Bm", "F#m", "G", "D", "G", "A"]
TRI = {"D": (62, 66, 69), "A": (57, 61, 64), "Bm": (59, 62, 66), "F#m": (54, 57, 61), "G": (55, 59, 62)}
def tones(ch, lo, cnt):
    out = []; m = lo; pcs = [(x - TRI[ch][0]) % 12 for x in TRI[ch]]
    while len(out) < cnt:
        if (m - TRI[ch][0]) % 12 in pcs: out.append(m)
        m += 1
    return out
def melody():
    """(音, 和音の番号) の列。カノンの旋律 → 次の旋律 → 2音ずつの変奏 → 分散和音"""
    P1 = [78, 76, 74, 73, 71, 69, 71, 73]; P2 = [74, 73, 71, 69, 67, 66, 67, 64]
    P3 = [(74, 78), (81, 79), (78, 74), (78, 76), (74, 71), (74, 81), (79, 83), (81, 79)]; P4 = [(78, 74), (76, 85), (86, 90), (93, 81), (83, 79), (81, 78), (74, 86), (86, 85)]
    seq = [(n, c) for c, n in enumerate(P1)] + [(n, c) for c, n in enumerate(P2)] + [(n, c) for c, ab in enumerate(P3) for n in ab] + [(n, c) for c, ab in enumerate(P4) for n in ab]
    for pat in ((0, 2, 1, 3), (3, 1, 2, 0), (0, 1, 2, 3), (3, 2, 1, 2), (0, 2, 1, 3), (1, 3, 2, 0)):
        for c in range(8): tl = tones(PROG[c], 74, 4); seq += [(tl[i], c) for i in pat]
    return seq
def make_audio(res, lead, dur, path):
    N = int(SR * (dur + 2.6)); AL = np.zeros(N); AR = np.zeros(N); SL = np.zeros(N); SRv = np.zeros(N)
    def put(x, t, pan=.5, g=1.0, send=.35):
        i = int(round((t + lead) * SR))
        if i < 0 or i >= N: return
        k = min(len(x), N - i); l, r = math.cos(pan * math.pi / 2) * g, math.sin(pan * math.pi / 2) * g
        AL[i:i + k] += x[:k] * l; AR[i:i + k] += x[:k] * r; SL[i:i + k] += x[:k] * l * send; SRv[i:i + k] += x[:k] * r * send
    def pad(ms, d, g):
        tt = np.arange(int(SR * d)) / SR; s = np.zeros(len(tt))
        for q, m_ in enumerate(ms):
            f = mtof(m_); s += (np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * f * 1.004 * tt + q) + .22 * np.sin(4 * np.pi * f * tt + 2 * q)) / (1 + .25 * q)
        return s * np.minimum(1, tt / .25) * np.minimum(1, (d - tt) / .7) * g
    seq = melody(); mi = -1; last_t = -9; last_note = None; chord = None; log = []
    for t, k, x, y, nid, first in res["merges"]:
        pan = .5 + .34 * (x - (XL + XR) / 2) / (XR - XL)
        if k == NT - 1:   # 太陽：D の和音で決着
            for m_, g_ in ((38, .9), (45, .7), (50, .9), (57, .6), (62, .8), (66, .6), (69, .6), (74, .7), (78, .5)): put(stone(m_, 2.2), t, .5 + .2 * math.sin(m_), g_ * .62, .7)
            put(pad([50, 62, 66, 69], 3.4, .034), t - .03, .5, 1.0, .6); log.append((t, 62, k)); continue
        if t - last_t < .09 and last_note is not None:   # 続けて起きた合体：旋律は進めず、今の和音の下の音を重ねる
            tl = [m for m in tones(chord, 50, 12) if m < last_note]; m = tl[-1] if tl else last_note - 12; last_note = m; g = .50
        else:
            mi += 1; m, ci = seq[mi % len(seq)]; g = .80 + .02 * k
            if PROG[ci] != chord or t - last_t > 2.0:
                chord = PROG[ci]; r_, t_, f_ = TRI[chord]; put(pad([r_, t_, f_, r_ + 12], 2.6, .020), t - .02, .5, 1.0, .6)
            last_note = m
        last_t = t; put(stone(m, 3.2 if k < 5 else 2.8), t, pan, g, .45); log.append((t, m, k)); r_ = TRI[chord][0]
        if k >= 4: put(stone(r_ - 12, 2.8), t, pan, .30 + .05 * (k - 4), .5)                      # 大きい星の合体ほど、低い音が重なる
        if k >= 6: put(stone(r_ - 24, 2.4), t, .5, .50, .5); put(stone(TRI[chord][2] - 12, 2.8), t, pan, .26, .5)
        if k >= 8: put(stone(TRI[chord][1], 2.8), t + .012, pan, .30, .5)
    TK = [tok(1.0 - .045 * k) for k in range(NT)]
    for t, k, spd, x, y in res["toks"]:   # 落とした星が最初に当たった「コッ」。速く当たるほど少し大きい
        if any(abs(t - m[0]) < .02 for m in res["merges"]): continue
        put(TK[k], t, .5 + .34 * (x - (XL + XR) / 2) / (XR - XL), min(.26, .05 + spd / 9000) * (.7 + .08 * k), .2)
    tt_ = np.arange(int(SR * 2.4)) / SR
    def ir(seed): return np.convolve(np.random.default_rng(seed).normal(0, 1, len(tt_)) * np.exp(-tt_ * 2.4), np.ones(24) / 24, "same") * .02
    AL += fftconvolve(SL, ir(11))[:N]; AR += fftconvolve(SRv, ir(12))[:N]
    mix = np.stack([AL, AR], 1); pk = np.abs(mix).max(); mix = np.tanh(mix / pk * 1.5) / np.tanh(1.5)
    sos = butter(4, 15000, "low", fs=SR, output="sos"); mix = np.stack([sosfilt(sos, mix[:, 0]), sosfilt(sos, mix[:, 1])], 1)
    e0 = int(SR * dur); fo = int(SR * .5); mix[e0 - fo:e0] *= np.linspace(1, 0, fo)[:, None]; mix = mix[:e0]
    tp = max(np.abs(resample_poly(mix[:, 0], 4, 1)).max(), np.abs(resample_poly(mix[:, 1], 4, 1)).max()); mix *= .84 / tp
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    return log

# ---------- 絵 ----------
RX0, RY0, RW, RH = 60, 430, 960, 1040          # 星を描く範囲
IX = [90 + 100 * k for k in range(NT)]; IY = 330
def build_static():
    rs = np.random.default_rng(5); yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    bg = np.zeros((H, W, 3), np.float32); bg[..., 0] = 8 + 7 * yy; bg[..., 1] = 9 + 2 * yy; bg[..., 2] = 22 + 12 * yy
    im = Image.fromarray(bg.astype(np.uint8)); glow = Image.new("RGB", (W, H), (0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse([80, 600, 1000, 1500], fill=(14, 12, 34)); gd.ellipse([-200, 1300, 500, 2100], fill=(10, 16, 30)); im = ImageChops.add(im, glow.filter(ImageFilter.GaussianBlur(170)))
    d = ImageDraw.Draw(im)
    for _ in range(170):
        x, y = rs.uniform(0, W), rs.uniform(0, H); b = int(rs.uniform(40, 150)); r = rs.choice([1, 1, 1, 2]); d.ellipse([x - r, y - r, x + r, y + r], fill=(b, b, min(255, b + 20)))
    tint = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(tint).rectangle([XL, YWALL, XR, YB], fill=(150, 170, 255, 9)); im = Image.alpha_composite(im.convert("RGBA"), tint).convert("RGB")
    S = 2; fr = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); f = ImageDraw.Draw(fr); col = (176, 190, 226, 175); o = 5
    f.line([((XL - o) * S, YWALL * S), ((XL - o) * S, (YB + o) * S), ((XR + o) * S, (YB + o) * S), ((XR + o) * S, YWALL * S)], fill=col, width=4 * S, joint="curve")   # ガラスの箱（上はあいている）
    for sx in (XL - o, XR + o): f.ellipse([(sx - 5) * S, (YWALL - 5) * S, (sx + 5) * S, (YWALL + 5) * S], fill=col)
    hi = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); h = ImageDraw.Draw(hi)
    h.rounded_rectangle([(XL + 12) * S, (YWALL + 60) * S, (XL + 24) * S, (YB - 40) * S], radius=6 * S, fill=(255, 255, 255, 30)); h.rounded_rectangle([(XR - 18) * S, (YWALL + 160) * S, (XR - 13) * S, (YB - 120) * S], radius=3 * S, fill=(255, 255, 255, 16))
    fr = Image.alpha_composite(fr, hi.filter(ImageFilter.GaussianBlur(5 * S))); f = ImageDraw.Draw(fr)
    f.line([((XL - 26) * S, YRAIL * S), ((XR + 26) * S, YRAIL * S)], fill=(150, 166, 210, 120), width=2 * S)                                                        # 口が動くレール
    fr = fr.resize((W, H), Image.LANCZOS); f = ImageDraw.Draw(fr)
    l1 = "Two of the same merge into a bigger one" if EN else "同じ星がぶつかると、1つ大きい星になる"; l2 = "Can it make a Sun before it overflows?" if EN else "線をこえる前に、太陽はできる？"
    f.text((W / 2, 160), l1, font=fnt(46 if EN else 47), fill=(244, 244, 250, 255), anchor="mm", stroke_width=5, stroke_fill=(6, 6, 16, 255))
    f.text((W / 2, 232), l2, font=fnt(50 if EN else 54), fill=(255, 226, 122, 255), anchor="mm", stroke_width=5, stroke_fill=(6, 6, 16, 255))
    wg = np.zeros((H, W), np.float32); wg[int(YWALL):int(YB), int(XL):int(XR)] = 1.0
    return im, fr, wg
def nozzle_img():
    S = 2; im = Image.new("RGBA", (130 * S, 60 * S), (0, 0, 0, 0)); f = ImageDraw.Draw(im)
    f.rounded_rectangle([8 * S, 8 * S, 122 * S, 46 * S], radius=12 * S, fill=(22, 24, 42, 255), outline=(176, 190, 226, 210), width=2 * S)
    f.ellipse([43 * S, 38 * S, 87 * S, 54 * S], fill=(6, 6, 14, 255), outline=(150, 166, 210, 220), width=2 * S)
    for q in (28, 102): f.ellipse([(q - 3) * S, 24 * S, (q + 3) * S, 30 * S], fill=(176, 190, 226, 200))
    return im.resize((130, 60), Image.LANCZOS)

def render(res, out, stills=None):
    BG, FRONT, WARM = build_static(); BGROI = np.asarray(BG, np.float32)[RY0:RY0 + RH, RX0:RX0 + RW] / 255; NOZ = nozzle_img()
    ICON = [icon(k, 24.0 if k != 7 else 19.0) for k in range(NT)]
    ICON_DIM = [Image.merge("RGBA", (*[c.point(lambda v: int(v * .26)) for c in im_.split()[:3]], im_.split()[3])) for im_ in ICON]
    fW = ImageFont.truetype(FI, 22); fQ = ImageFont.truetype(FI, 26); fCnt = ImageFont.truetype(FI, 46); fUnit = fnt(30); fName = fnt(54); fSub = fnt(31); fBig = fnt(128); fBig2 = fnt(56)
    frames = res["frames"]; merges = res["merges"]; tsun = res["tsun"]; FIRST = {k: (t, x, y, nid) for t, k, x, y, nid, first in merges if first}
    lead = .45; NF = len(frames) + int(lead * FPS); dur = NF / FPS; pres = np.zeros(NT); danger = 0.0
    os.makedirs("build_mergebox", exist_ok=True)
    if stills is None:
        log = make_audio(res, lead, dur, "build_mergebox/a.wav")
        proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", "build_mergebox/a.wav",
                              "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    want = None if stills is None else {int(round((s + 0) * FPS)) for s in stills}
    for fi in range(NF):
        F = frames[max(0, fi - int(lead * FPS))]; t = F["t"] if fi >= int(lead * FPS) else 0.0; bodies = F["bodies"] if fi >= int(lead * FPS) else []
        for k in range(NT): pres[k] += ((1.0 if any(b[1] == k for b in bodies) else 0.0) - pres[k]) * (1 - math.exp(-1 / FPS / .07))
        margin = F["top"] - YLIM; danger += ((0.0 if tsun is not None and t >= tsun else min(1.0, max(0.0, 1 - margin / 170))) - danger) * .12
        if want is not None and fi not in want: continue
        roi = BGROI.copy(); pos = {}
        for i, k, x, y, ang, r, born in sorted(bodies, key=lambda b: (-b[1], b[0])):
            age = t - born; pop = 1 + (.016 * math.sin(max(0, age) * 2.4) if k == 9 else 0)
            draw_merge(roi, res["par"], i, k, x, y, ang, r, age, RX0, RY0, pop); pos[i] = (x, y, r, k)
        hk = F["held"]
        if hk is not None and fi >= int(lead * FPS):   # 口の下にぶらさがっている、次に落とす星
            last_drop = max((d[0] for d in res["drops"] if d[0] <= t), default=-1.0); g = min(1.0, (t - last_drop) / .09) if last_drop >= 0 else min(1.0, t / .2)
            draw_body(roi, hk, F["hx"] - RX0, YRAIL + 22 + RAD[hk] * g - RY0, RAD[hk] * max(.2, g), 0.0)
        im = BG.copy(); im.paste(Image.fromarray((np.clip(roi, 0, 1) * 255).astype(np.uint8)), (RX0, RY0)); im = Image.alpha_composite(im.convert("RGBA"), FRONT)
        add = Image.new("RGB", (W, H), (0, 0, 0)); ad = ImageDraw.Draw(add); ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        ov.alpha_composite(NOZ, (int(round(F["hx"] - 65)), int(YRAIL - 28)))
        # あふれの線（点線）。積もった星が近づくほど明るく、赤みが出る
        a_ = int(70 + 150 * danger); lc = (255, int(214 - 70 * danger), int(150 - 70 * danger), a_)
        for x in range(int(XL) + 6, int(XR) - 6, 28): d.line([x, YLIM, x + 15, YLIM], fill=lc, width=3)
        # 合体の光の輪（合体の瞬間から広がる）
        for tm, k, x, y, nid, first in merges:
            if tm > t: break
            life = 1.5 if k == 9 else (.55 if first else .34)
            if t - tm > life: continue
            p = (t - tm) / life; bx, by, br, bk = pos.get(nid, (x, y, RAD[k], k)); R = RAD[k]; c = GLOW[k]; a = (1 - p) ** 1.6 * (.9 if first else .62)
            for w_, r1 in ((max(2, int(R * .07)), R * (1.05 + (2.2 if k == 9 else (1.4 if first else .9)) * p)),) + (((2, R * (1.05 + 2.5 * p)),) if first or k == 9 else ()):
                ad.ellipse([bx - r1, by - r1, bx + r1, by + r1], outline=tuple(int(v * a) for v in c), width=w_)
        # 上の列：今ある星が明るい。まだできていない星は「？」
        for k in range(NT):
            x = IX[k]; known = k == 0 or (k in FIRST and FIRST[k][0] <= t)
            if not known:
                d.ellipse([x - 25, IY - 25, x + 25, IY + 25], outline=(120, 130, 170, 150), width=2); d.text((x, IY), "?", font=fQ, fill=(130, 140, 180, 200), anchor="mm"); continue
            b = float(min(1, pres[k])); ic = ICON[k]; ov.alpha_composite(ICON_DIM[k], (x - ic.width // 2, IY - ic.height // 2))
            if b > .02: ov.paste(ic, (x - ic.width // 2, IY - ic.height // 2), ic.split()[3].point(lambda v, b=b: int(v * b)))
            e = t - FIRST[k][0] if k in FIRST else 9
            if 0 <= e < .6: r1 = 27 + 16 * e / .6; a = (1 - e / .6); ad.ellipse([x - r1, IY - r1, x + r1, IY + r1], outline=tuple(int(v * a * .9) for v in GLOW[k]), width=3)
        d.text((XR - 96, 418), "Dropped" if EN else "落とした星", font=fUnit, fill=(196, 202, 224, 255), anchor="rm", stroke_width=3, stroke_fill=(6, 6, 16, 255))
        d.text((XR, 416), str(F["nd"] if fi >= int(lead * FPS) else 0), font=fCnt, fill=(244, 244, 250, 255), anchor="rm", stroke_width=4, stroke_fill=(6, 6, 16, 255))
        # 初めての星の名前（その星のすぐ上）
        for k, (tm, x, y, nid) in FIRST.items():
            e = t - tm
            if k == 9 or e < 0 or e > 1.6: continue
            a = min(1, e / .08) * min(1, (1.6 - e) / .3); A = int(255 * a); bx, by, br, bk = pos.get(nid, (x, y, RAD[k], k))
            lx = min(W - 150, max(150, bx)); ly = max(YLIM - 40, by - RAD[k] - 74 - 10 * min(1, e / .5))
            d.text((lx, ly), NAMES[k], font=fName, fill=(248, 248, 252, A), anchor="mm", stroke_width=5, stroke_fill=(6, 6, 16, A))
        if tsun is not None and t >= tsun:
            e = t - tsun; a = min(1, e / .25); A = int(255 * a); sx, sy, sr, sk = next(((x, y, r, k) for (x, y, r, k) in pos.values() if k == 9), (W / 2, YB - RAD[9], RAD[9], 9))
            lx = min(W - 240, max(240, sx)); ly = max(YLIM + 90, sy - RAD[9] - 170) - 14 * min(1, e / .6)
            d.text((lx, ly), NAMES[9], font=fBig if not EN else fnt(120), fill=(255, 226, 122, A), anchor="mm", stroke_width=8, stroke_fill=(6, 6, 16, A))
        im = Image.alpha_composite(im, ov).convert("RGB")
        if tsun is not None and t >= tsun:
            e = min(1, (t - tsun) / .8); wl = (WARM * (e * .07))[..., None] * np.array([255, 150, 60], np.float32); add = ImageChops.add(add, Image.fromarray(np.clip(wl, 0, 255).astype(np.uint8)))
        im = ImageChops.add(im, add)
        src = add.copy(); src.paste(Image.fromarray((np.clip((roi - .60) * 1.3, 0, 1) * 255).astype(np.uint8)), (RX0, RY0))
        im = ImageChops.add(im, src.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(7)).resize((W, H), Image.BILINEAR))
        if stills is None: proc.stdin.write(im.tobytes())
        else: im.save(f"build_mergebox/s_{fi / FPS:05.2f}.jpg", quality=90)
    if stills is None: proc.stdin.close(); proc.wait(); print(out, round(dur, 2), "秒 / 太陽", round(tsun + lead, 2), "秒 / 合体", len(merges), "回 / 落とした星", len(res["drops"]), "個")

MERGED = set()
if __name__ == "__main__":
    seed = int(os.environ.get("SEED", 59)); res = simulate(seed, record=True); MERGED.update(m[4] for m in res["merges"])
    print("種", seed, "太陽", res["tsun"], "合体", len(res["merges"]), "落とした", len(res["drops"]), "上の余白", round(res["topmin"] - YLIM), "あふれ", res["overflow"])
    st = os.environ.get("STILLS"); render(res, OUT, [float(x) for x in st.split(",")] if st else None)
