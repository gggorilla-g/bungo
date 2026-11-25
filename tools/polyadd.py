# polyadd.py — 図形がV字の谷ではねる。当たるたびに辺が1つふえて、色と名前が変わる。最後は円になる（オーナー 11/25 の画面収録の型。「録画は優先したい」）
#   音：当たるたびにガラスのマリンバが1音（辺の数が多いほど高い）。はねる速さがだんだん上がる＝リズムが速くなる。円になると和音
#   python3 tools/polyadd.py [out.mp4]     STILLS=1,5,9 で確認用の絵だけ
import math, os, sys, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.signal import butter, sosfilt, fftconvolve

W, H, FPS, SR = 1080, 1920, 30, 48000
LANG = os.environ.get("LANG_OUT", "ja"); EN = LANG == "en"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"output/polyadd1_{LANG}.mp4"
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"; FI = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
fName = ImageFont.truetype(FI if EN else FJ, 76); fTop = ImageFont.truetype(FJ, 54); fTop2 = ImageFont.truetype(FJ, 40); fN = ImageFont.truetype(FI, 44)
if EN: fTop = ImageFont.truetype(FI, 54); fTop2 = ImageFont.truetype(FI, 40)

# ---------- 物理 ----------
NMAX = 20                                       # 20角形の次は円
R0, R1 = 330.0, 85.0                            # 11/25「大きくてどんどん小さくなる方がいい」：三角形は半径330px、当たるたびに小さくなり、円で85px
def Rn(n): return R0 * (R1 / R0) ** ((min(n, NMAX + 1) - 3) / (NMAX + 1 - 3))
G = 2600.0                                      # 重力（px/s²）
LEFT = ((0.0, 900.0), (W / 2, 1560.0)); RIGHT = ((W / 2, 1560.0), (float(W), 900.0))
def seg_normal(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy); n = np.array([dy / L, -dx / L])   # 線の上側（y が小さい側）を向く法線
    if n[1] > 0: n = -n
    return n
LINES = [(np.array(LEFT[0]), seg_normal(*LEFT)), (np.array(RIGHT[0]), seg_normal(*RIGHT))]
WALLS = [(np.array([0.0, 0.0]), np.array([1.0, 0.0])), (np.array([float(W), 0.0]), np.array([-1.0, 0.0]))]
def speed_target(t): return 1500 + 40 * t       # はね返りの速さ（だんだん上げる）
def verts(pos, th, n):
    if n > NMAX: return None
    k = np.arange(n); a = th + 2 * np.pi * k / n - np.pi / 2
    return pos + Rn(n) * np.stack([np.cos(a), np.sin(a)], 1)
def simulate(seed=1, TMAX=40.0):
    rs = np.random.default_rng(seed)
    pos = np.array([W * .5 + rs.uniform(-60, 60), 560.0]); vel = np.array([rs.uniform(-260, 260), 0.0]); th = rs.uniform(0, 1); om = 0.0; n = 3
    dt = 1 / 1200; t = 0.0; hits = []; frames = []; last = -1.0; t_circle = None
    while t < TMAX:
        R = Rn(n); I = .5 * R * R * (.6 if n <= NMAX else 1.0)
        vel[1] += G * dt; pos += vel * dt; th += om * dt
        cand = []
        for a, nn in LINES + WALLS:
            if n <= NMAX:
                V = verts(pos, th, n); d = (V - a) @ nn; i = int(np.argmin(d)); cand.append((d[i], V[i], nn))
            else:
                d = (pos - a) @ nn - R; cand.append((d, pos - nn * R, nn))
        for d, p, nn in cand:
            if d >= 0: continue
            r = p - pos; vp = vel + om * np.array([-r[1], r[0]]); vn = vp @ nn
            pos += nn * (-d)                                              # めりこみを戻す
            if vn >= 0: continue
            rxn = r[0] * nn[1] - r[1] * nn[0]
            j = -(1 + 1.0) * vn / (1 + rxn * rxn / I)
            vel += j * nn; om += j * rxn / I
            tv = vp - vn * nn; tl = np.linalg.norm(tv)                     # まさつ（回転をつける）
            if tl > 1e-6:
                tt_ = tv / tl; rxt = r[0] * tt_[1] - r[1] * tt_[0]; jt = -min(.35 * j, tl / (1 + rxt * rxt / I))
                vel += jt * tt_; om += jt * rxt / I
            is_floor = nn[1] < -.5
            if is_floor and t - last > .12:
                last = t; sp = np.linalg.norm(vel); vel *= speed_target(t) / max(sp, 1)   # 速さをそろえる（だんだん速く）
                om = max(-14, min(14, om))
                if n <= NMAX: n += 1
                hits.append((t, n, p.copy()))
                if n > NMAX and t_circle is None: t_circle = t
        if pos[1] - Rn(n) < 430 and vel[1] < 0: vel[1] = abs(vel[1]) * .9   # 上の文字の下で止める（見えない天井）
        t += dt
        if len(frames) < int(t * FPS): frames.append((pos.copy(), th, n))
        if t_circle is not None and t > t_circle + 3.2: break
    return hits, frames, t_circle
best = None
for seed in range(1, 40):
    hits, frames, tc = simulate(seed)
    if tc is None: continue
    gaps = np.diff([h[0] for h in hits]); ok = gaps.max() < 1.6 and gaps.min() > .14
    if ok and 18 < tc < 30: best = (seed, hits, frames, tc); break
    if best is None or (tc and abs(tc - 24) < abs(best[3] - 24)): best = (seed, hits, frames, tc)
seed, hits, frames, TC = best
DUR = len(frames) / FPS
print("seed", seed, "hits", len(hits), "円になる", round(TC, 2), "長さ", round(DUR, 2))

# ---------- 名前と色 ----------
JA = {3: "三角形", 4: "四角形", 5: "五角形", 6: "六角形", 7: "七角形", 8: "八角形", 9: "九角形", 10: "十角形", 11: "十一角形", 12: "十二角形", 13: "十三角形", 14: "十四角形",
      15: "十五角形", 16: "十六角形", 17: "十七角形", 18: "十八角形", 19: "十九角形", 20: "二十角形", 21: "円"}
ENN = {3: "triangle", 4: "square", 5: "pentagon", 6: "hexagon", 7: "heptagon", 8: "octagon", 9: "nonagon", 10: "decagon", 11: "hendecagon", 12: "dodecagon", 13: "13-gon", 14: "14-gon",
       15: "15-gon", 16: "16-gon", 17: "17-gon", 18: "18-gon", 19: "19-gon", 20: "20-gon", 21: "circle"}
def name(n): return (ENN if EN else JA)[min(n, 21)]
PAL = [(255, 214, 61), (255, 145, 48), (243, 66, 139), (155, 89, 255), (64, 120, 255), (60, 205, 255), (77, 226, 120), (190, 240, 60)]
def color(n): return (255, 255, 255) if n > NMAX else PAL[(n - 3) % len(PAL)]

# ---------- 音 ----------
N = int(SR * (DUR + 3)); L = np.zeros(N); Rr = np.zeros(N); SL = np.zeros(N); SRr = np.zeros(N)
f_ = lambda m: 440 * 2 ** ((m - 69) / 12)
def put(sig, t, pan=.5, g=1.0, wet=.3):
    i = int(t * SR); j = min(N, i + len(sig)); s = sig[:j - i] * g; cl, cr = math.cos(pan * math.pi / 2) * 1.41, math.sin(pan * math.pi / 2) * 1.41
    L[i:j] += s * cl; Rr[i:j] += s * cr; SL[i:j] += s * cl * wet; SRr[i:j] += s * cr * wet
def env(tt, a, d): return np.minimum(1, tt / a) * np.exp(-tt * d)
def marimba(m, dur=1.5):
    tt = np.arange(int(SR * dur)) / SR; f = f_(m)
    return (np.sin(2 * np.pi * f * tt) * env(tt, .002, 3.0) + .3 * np.sin(2 * np.pi * f * 3.93 * tt) * env(tt, .001, 13) + .12 * np.sin(2 * np.pi * f * 2.76 * tt) * env(tt, .001, 6)) * .3
def bell(m, dur=2.5):
    tt = np.arange(int(SR * dur)) / SR; f = f_(m); I = 2.0 * np.exp(-tt * 3)
    return np.sin(2 * np.pi * f * tt + I * np.sin(2 * np.pi * f * 3.5 * tt)) * env(tt, .003, 1.5) * .16
def pad(ms, dur, att=.5):
    tt = np.arange(int(SR * dur)) / SR; x = np.zeros(len(tt))
    for m in ms:
        for dt_ in (-.06, .06): fr = f_(m) * 2 ** (dt_ / 12); x += np.sin(2 * np.pi * fr * tt) + .15 * np.sin(4 * np.pi * fr * tt)
    return x / (2 * len(ms)) * np.minimum(1, tt / att) * np.minimum(1, (dur - tt) / .4) * .08
def softkick(g=1.0):
    tt = np.arange(int(SR * .3)) / SR; ph = 2 * np.pi * np.cumsum(50 + 80 * np.exp(-tt * 30)) / SR
    return np.sin(ph) * env(tt, .003, 12) * .4 * g + np.sin(2 * np.pi * np.cumsum(140 + 120 * np.exp(-tt * 40)) / SR) * env(tt, .002, 30) * .18 * g
SCALE = [m for m in range(55, 110) if m % 12 in (0, 2, 4, 7, 9)]          # ド・レ・ミ・ソ・ラ（どの順でも濁らない）
for k, (t, n, p) in enumerate(hits):
    m = SCALE[min(len(SCALE) - 1, n - 3 + 2)]; pan = min(.9, max(.1, p[0] / W))
    if n <= NMAX:
        put(marimba(m), t, pan, .9, .3)
        if n >= 10: put(bell(m + 12), t, pan, .35 + .02 * (n - 10), .5)
        if n >= 8: put(softkick(.6 + .03 * (n - 8)), t, .5, 1.0, 0)
    else:                                                                 # 円になった瞬間：和音
        for q, mi in enumerate((48, 60, 64, 67, 72, 76, 79, 84)): put(bell(mi, 3.0), t + q * .04, .2 + .08 * q, .55, .6)
        put(softkick(1.2), t, .5, 1.0, 0); put(pad([48, 55, 60, 64], 3.2, .05), t, .5, 1.6, .6)
# 下に流れるパッド（4回当たるごとに和音が変わる）
CH = [[48, 52, 55], [45, 48, 52], [41, 45, 48], [43, 47, 50]]
for q in range(0, len(hits), 4):
    if hits[q][1] > NMAX: break
    t0 = hits[q][0]; t1 = hits[min(len(hits) - 1, q + 4)][0]; put(pad([m + 12 for m in CH[(q // 4) % 4]], t1 - t0 + .5), t0, .5, 1.0, .5)
tt = np.arange(int(SR * 2.2)) / SR
def ir(seed): return np.convolve(np.random.default_rng(seed).normal(0, 1, len(tt)) * np.exp(-tt * 2.8), np.ones(20) / 20, "same") * .02
L += fftconvolve(SL, ir(11))[:N]; Rr += fftconvolve(SRr, ir(12))[:N]
mix = np.stack([L, Rr], 1); pk = np.abs(mix).max(); mix = np.tanh(mix / pk * 1.6) / np.tanh(1.6) * .85
e0 = int(SR * DUR); fo = int(SR * .4); mix[e0 - fo:e0] *= np.linspace(1, 0, fo)[:, None]
os.makedirs("build_polyadd", exist_ok=True)
with wave.open("build_polyadd/a.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix[:e0] * 32767).astype(np.int16).tobytes())

# ---------- 絵：平らな色と黒いふち ----------
BG = (64, 214, 204)
def frame(fi):
    t = fi / FPS; pos, th, n = frames[min(fi, len(frames) - 1)]
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.line([LEFT[0], LEFT[1]], fill=(20, 24, 30), width=9); d.line([RIGHT[0], RIGHT[1]], fill=(20, 24, 30), width=9)
    # 上の文字
    d.text((W / 2, 170), "Each hit adds one side" if EN else "当たるたびに、辺が1つふえる", font=fTop, fill=(255, 255, 255), anchor="mm", stroke_width=6, stroke_fill=(20, 24, 30))
    d.text((W / 2, 245), "What comes after 20?" if EN else "20角形の次は？", font=fTop2, fill=(255, 238, 120), anchor="mm", stroke_width=5, stroke_fill=(20, 24, 30))
    lh = [h for h in hits if h[0] <= t]; e = t - lh[-1][0] if lh else 9; R = Rn(n)
    pop = 1 + .14 * math.exp(-e * 12) if lh else 1                      # 当たった瞬間、少しふくらむ
    c = color(n)
    if n <= NMAX:
        V = pos + (verts(pos, th, n) - pos) * pop
        d.polygon([tuple(v) for v in V], fill=c, outline=(20, 24, 30), width=8)
    else:
        rr = R * pop; d.ellipse([pos[0] - rr, pos[1] - rr, pos[0] + rr, pos[1] + rr], fill=c, outline=(20, 24, 30), width=8)
    if lh and e < .18:   # 当たった所に短い線が3本はじける（平らな漫画ふう）
        cx, cy = lh[-1][2]; k_ = e / .18
        for q in range(-1, 2):
            ang = -math.pi / 2 + q * .7 + (.5 if cx < W / 2 else -.5); r0 = 30 + 60 * k_; r1 = r0 + 34 * (1 - k_)
            d.line([cx + r0 * math.cos(ang), cy + r0 * math.sin(ang), cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)], fill=(20, 24, 30), width=7)
    # 名前（図形の上に出て、少し浮かぶ）
    if lh:
        a = min(1, e / .06); y = pos[1] - R * pop - 70 - 30 * min(1, e / .5)
        if y < 330: y = pos[1] + R * pop + 70   # 上の文字とかさなるときは図形の下へ
        big = n > NMAX
        f = ImageFont.truetype(FI if EN else FJ, 120) if big else fName
        d.text((pos[0], y), name(n), font=f, fill=(255, 255, 255) if not big else (255, 238, 120), anchor="mm", stroke_width=8 if big else 6, stroke_fill=(20, 24, 30))
    # 辺の数
    d.text((W / 2, 1720), ("∞" if n > NMAX else str(n)), font=ImageFont.truetype(FI, 96), fill=(255, 255, 255), anchor="mm", stroke_width=7, stroke_fill=(20, 24, 30))
    d.text((W / 2, 1800), "sides" if EN else "辺の数", font=fTop2, fill=(255, 255, 255), anchor="mm", stroke_width=5, stroke_fill=(20, 24, 30))
    return im

if __name__ == "__main__":
    st = os.environ.get("STILLS")
    if st:
        for s in st.split(","): frame(int(float(s) * FPS)).save(f"build_polyadd/s_{float(s):05.2f}.jpg", quality=88)
        sys.exit()
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", "build_polyadd/a.wav",
                          "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", OUT], stdin=subprocess.PIPE)
    for fi in range(len(frames)): p.stdin.write(frame(fi).tobytes())
    p.stdin.close(); p.wait(); print(OUT, round(DUR, 2), "秒")
