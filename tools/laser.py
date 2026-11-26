# laser.py — 光の線が通るたびに、玉が2つに分かれる（縦のショート）
#   オーナー 11/27：参考の録画（光の線が振り子のように上下し、通るたびに玉が倍になる）を送って「これも作っといて」「音こんな感じがいい」。
#   絵は自前：丸い器、金色の細い光の線、玉の色は「何回分かれたか」で変わる。参考の器の形・色・文字の配置はまねない。
#   動き：光の線の高さ = 2つの正弦の和（周期の比が無理数なので同じ形をくり返さない）。速さはだんだん上がる（途中でリズムが変わる）。
#         玉の中心が線をまたいだら、その玉は2つに分かれる（新しい玉は線に沿って少しずれ、横の速さが逆）。2048 個で止まる。
#   音：分かれるたびに澄んだ音（kalimba.bell）。数が増えるほど音が上がる（D のペンタトニック）。16分音符にそろえ、同時は4音まで。
#       下にカノン進行の温かい持続音（kalimba.pad）。残響は小さな部屋を少しだけ。
#   python3 tools/laser.py search      乱数を探す（35〜45 秒で 2048 個、器があふれない）
#   python3 tools/laser.py stills 5,20  確認用の絵
#   python3 tools/laser.py all          → output/laser1_ja.mp4（LANG_OUT=en で英語）
import math, os, sys, subprocess, wave
import numpy as np, cv2, pymunk
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kalimba as K

W, H, FPS, SR = 1080, 1920, 60, 48000
B = "build_laser"; os.makedirs(B, exist_ok=True)
SEED = int(os.environ.get("SEED", 1)); LANG = os.environ.get("LANG_OUT", "ja"); EN = LANG == "en"
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"; FJM = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
def fnt(sz, bold=True): return ImageFont.truetype(FJ if bold else FJM, sz)
CX, CY, RC = W / 2, 1020, 455; R = 8.0; CAP = 2048; GRAV = 700.0
# 光の線は、左右のレール上の台（質量あり）に付いていて、上の留め具からばねでつり下がる（オーナー 11/27「スプリングの慣性とかをもっと精緻に再現してよりリアリティな感じで」）
#   台：m y'' = -k (y - ya(t) - L0) - c y' + m g + 器の上下の止め（硬いばね）。留め具 ya(t) はモーターでゆっくり上下し、その速さがだんだん上がる（共振に近づくと大きく揺れる）。
#   4次のルンゲ＝クッタで 1/960 秒ごとに解く。ばねは画面にコイルで描き、伸び縮みが見える
RAIL = RC + 46; YA0 = CY - RC - 190; KM = 9.0; CM = .45; GM = 700.0; L0 = CY + 170 - YA0 - GM / KM   # つり合いの位置は器の中心より少し下（玉がたまる側をよく通る）
STOP_T, STOP_B = CY - RC + 10, CY + RC - 10
def _anchor(t):
    ph = 1.0 * t + .040 * t * t; return YA0 + 120 * math.sin(ph) * min(1, t / 2.5)
def _acc(t, y, v):
    a = -KM * (y - _anchor(t) - L0 - GM / KM) - CM * v + GM
    if y < STOP_T: a += 900 * (STOP_T - y) - 6 * v
    if y > STOP_B: a -= 900 * (y - STOP_B) + 6 * v
    return a
_LT = {}
def _laser_table(tmax=80.0, h=1 / 960):
    n = int(tmax / h) + 2; ys = np.empty(n); y = YA0 + L0 + GM / KM; v = 0.0; t = 0.0
    for i in range(n):
        ys[i] = y
        k1v = _acc(t, y, v); k1y = v
        k2v = _acc(t + h / 2, y + h / 2 * k1y, v + h / 2 * k1v); k2y = v + h / 2 * k1v
        k3v = _acc(t + h / 2, y + h / 2 * k2y, v + h / 2 * k2v); k3y = v + h / 2 * k2v
        k4v = _acc(t + h, y + h * k3y, v + h * k3v); k4y = v + h * k3v
        y += h / 6 * (k1y + 2 * k2y + 2 * k3y + k4y); v += h / 6 * (k1v + 2 * k2v + 2 * k3v + k4v); t += h
    _LT["y"] = ys; _LT["h"] = h
def laser_y(t):
    if "y" not in _LT: _laser_table()
    i = t / _LT["h"]; j = int(i); f = i - j; ys = _LT["y"]; j = min(j, len(ys) - 2); return float(ys[j] * (1 - f) + ys[j + 1] * f)

def simulate(seed, record=False, tmax=60.0):
    rng = np.random.default_rng(seed); sp = pymunk.Space(); sp.gravity = (0, GRAV); sp.iterations = 12
    n = 160; pts = [(CX + (RC + 16) * math.cos(2 * math.pi * k / n), CY + (RC + 16) * math.sin(2 * math.pi * k / n)) for k in range(n)]   # 壁は厚く（玉が押されてもすり抜けない）
    for k in range(n): s = pymunk.Segment(sp.static_body, pts[k], pts[(k + 1) % n], 16); s.elasticity = .94; s.friction = .1; sp.add(s)
    balls = []
    def add(x, y, vx, vy, gen):
        b = pymunk.Body(1, pymunk.moment_for_circle(1, 0, R)); b.position = (x, y); b.velocity = (vx, vy); c = pymunk.Circle(b, R); c.elasticity = .94; c.friction = .1; c.gen = gen; sp.add(b, c); balls.append(c); return c
    add(CX + rng.uniform(-60, 60), CY - 200, rng.uniform(-160, 160), 0, 0)
    dt = 1 / 240; t = 0.0; frames = []; events = []; side = {}; full_t = None
    while t < tmax:
        ly = laser_y(t)
        for c in list(balls):
            s = 1 if c.body.position.y > ly else -1; o = side.get(id(c))
            side[id(c)] = s
            if o is not None and o != s and len(balls) < CAP:
                p = c.body.position; v = c.body.velocity; d = 1 if rng.random() < .5 else -1
                c.body.position = (p.x - d * R * .55, p.y); c2 = add(p.x + d * R * .55, p.y, -v.x + rng.normal(0, 30), v.y * .96, c.gen + 1); c.gen += 1; side[id(c2)] = s
                events.append((t, p.x, len(balls)))
                if len(balls) >= CAP and full_t is None: full_t = t
        for _ in range(4): sp.step(dt); t += dt
        if record and abs(t * FPS - round(t * FPS)) < 1e-6 or (record and len(frames) < int(t * FPS)):
            frames.append((t, laser_y(t), np.array([[c.body.position.x, c.body.position.y, c.gen] for c in balls], np.float32)))
        if full_t is not None and t > full_t + 6: break
    top = min(c.body.position.y for c in balls); return dict(frames=frames, events=events, full=full_t, top=top, n=len(balls))

def search(n=20):
    out = []
    for sd in range(n):
        r = simulate(sd); ok = r["full"] is not None; sc = (-abs(r["full"] - 40) if ok else -99) - (20 if r["top"] < CY - RC + 40 else 0)
        out.append((round(sc, 1), sd, r["full"] and round(r["full"], 1), round(r["top"]))); print(out[-1], flush=True)
    out.sort(reverse=True); print("上位", out[:4])

# ---------- 絵 ----------
def hue(g):
    pal = [(255, 214, 140), (255, 176, 150), (246, 150, 186), (208, 150, 230), (156, 166, 246), (120, 196, 240), (110, 220, 210), (150, 226, 160), (214, 230, 140), (250, 206, 120), (255, 170, 130), (240, 150, 200)]
    return pal[g % len(pal)]
def sprite(col, r):
    s = int(r * 2 + 8); yy, xx = np.mgrid[0:s, 0:s].astype(np.float32); c0 = s / 2; d = np.sqrt((xx - c0) ** 2 + (yy - c0) ** 2) / r
    a = np.clip((1 - d) * r + .5, 0, 1); nz = np.sqrt(np.clip(1 - d * d, 0, 1)); lam = np.clip(-(xx - c0) / r * .4 - (yy - c0) / r * .5 + nz * .75, 0, 1)
    c = np.asarray(col, np.float32) / 255; rgb = c * (.5 + .6 * lam)[..., None] + np.exp(-(((xx - c0 + r * .35) ** 2 + (yy - c0 + r * .38) ** 2) / (r * .3) ** 2))[..., None] * .35
    return np.dstack([np.clip(rgb, 0, 1), a]).astype(np.float32)
SPR = [sprite(hue(g), R) for g in range(12)]
_BG = {}
def bg():
    if "b" in _BG: return _BG["b"]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); d = np.sqrt((xx - CX) ** 2 + (yy - CY) ** 2)
    b = np.zeros((H, W, 3), np.float32) + np.array([.030, .032, .060], np.float32); b += (np.exp(-d / 900) * .03)[..., None] * np.array([.8, .8, 1.2], np.float32)
    inside = d < RC; b[inside] += np.array([.010, .012, .022], np.float32)
    rim = np.exp(-((d - RC - 6) / 3.0) ** 2); b += rim[..., None] * np.array([.42, .44, .56], np.float32); b += np.exp(-((d - RC - 6) / 14.0) ** 2)[..., None] * np.array([.05, .05, .08], np.float32)
    _BG["b"] = np.clip(b, 0, 1); _BG["d"] = d; return _BG["b"]
F = dict(n=fnt(150), lab=fnt(40, False), t=fnt(56), s=fnt(34, False))
def frame(r, i):
    t, ly, pos = r["frames"][min(i, len(r["frames"]) - 1)]; buf = bg().copy()
    for x, y, g in pos:
        sp_ = SPR[int(g) % 12]; h, w = sp_.shape[:2]; x0, y0 = int(x - w / 2), int(y - h / 2)
        if 0 <= x0 and 0 <= y0 and x0 + w <= W and y0 + h <= H: a = sp_[..., 3:4]; reg = buf[y0:y0 + h, x0:x0 + w]; reg[:] = reg * (1 - a) + sp_[..., :3] * a
    # レール・ばね・台（ばねの伸び縮みが見えるように）
    ya = _anchor(t); y = int(round(ly))
    for sx in (-1, 1):
        xr = int(CX + sx * RAIL)
        cv2.line(buf, (xr, int(YA0 - 120)), (xr, int(CY + RC + 30)), (.20, .21, .28), 2, cv2.LINE_AA)
        cv2.rectangle(buf, (xr - 22, int(ya) - 10), (xr + 22, int(ya)), (.55, .56, .64), -1, cv2.LINE_AA)
        nt = 22; y0c, y1c = ya + 4, ly - 14; pts = [(xr, int(ya))]
        for q in range(1, nt * 2):
            yy_ = y0c + (y1c - y0c) * q / (nt * 2); pts.append((xr + (11 if q % 2 else -11), int(yy_)))
        pts.append((xr, int(ly - 10))); cv2.polylines(buf, [np.array(pts, np.int32)], False, (.62, .64, .72), 2, cv2.LINE_AA)
        cv2.rectangle(buf, (xr - 16, y - 10), (xr + 16, y + 10), (.70, .66, .58), -1, cv2.LINE_AA); cv2.rectangle(buf, (xr - 16, y - 10), (xr + 16, y + 10), (.9, .86, .74), 1, cv2.LINE_AA)
    # 光の線（台から台へ。器の中は明るく、外は弱く）
    x0, x1 = int(CX - RAIL + 16), int(CX + RAIL - 16); dy = ly - CY
    for wdt, g in ((7, .035), (3, .12), (1, .55)):
        ys = slice(max(0, y - wdt), min(H, y + wdt + 1)); buf[ys, x0:x1] += np.array([1.0, .82, .46], np.float32) * g * .45
    if abs(dy) < RC:
        hw = math.sqrt(RC * RC - dy * dy); xa, xb = int(CX - hw), int(CX + hw)
        for wdt, g in ((9, .05), (4, .14), (1, .7)):
            ys = slice(max(0, y - wdt), min(H, y + wdt + 1)); buf[ys, xa:xb] += np.array([1.0, .82, .46], np.float32) * g
    im = Image.fromarray((np.clip(buf, 0, 1) * 255).astype(np.uint8)); d = ImageDraw.Draw(im); n = len(pos)
    d.text((W / 2, 300), f"{n:,}", font=F["n"], fill=(250, 246, 236), anchor="mm"); d.text((W / 2, 400), ("marbles" if EN else "個"), font=F["lab"], fill=(200, 196, 214), anchor="mm")
    top = ("The light splits every marble it crosses" if EN else "光の線が通るたび、玉は2つに分かれる")
    d.text((W / 2, 160), top, font=F["s"], fill=(220, 214, 230), anchor="mm")
    if r["full"] and t > r["full"]:
        a = min(1, (t - r["full"]) / 1.2); d.text((W / 2, 1640), ("2048 reached" if EN else "2048個に到達"), font=F["t"], fill=(255, 226, 150, ), anchor="mm")
    else: d.text((W / 2, 1640), ("Will it reach 2048?" if EN else "2048個になるまで"), font=F["s"], fill=(200, 196, 214), anchor="mm")
    return np.asarray(im)

# ---------- 音 ----------
PROG = [(38, 50, 54, 57), (33, 45, 49, 52), (35, 47, 50, 54), (30, 42, 45, 49), (31, 43, 47, 50), (26, 38, 42, 45), (31, 43, 47, 50), (33, 45, 49, 52)]   # D A Bm F#m G D G A（カノン進行）
PENTA = [62, 64, 66, 69, 71]   # D E F# A B
def audio(r, dur, path):
    N = int(SR * dur); st = np.zeros((N, 2), np.float32); BPM = 96; S16 = 60 / BPM / 4; CH = 60 / BPM * 4
    def put(x, t, pan, g):
        i = int(t * SR)
        if 0 <= i < N: k = min(len(x), N - i); st[i:i + k, 0] += x[:k] * math.cos(pan * math.pi / 2) * g; st[i:i + k, 1] += x[:k] * math.sin(pan * math.pi / 2) * g
    slots = {}
    for (t, x, n) in r["events"]: slots.setdefault(round(t / S16), []).append((n, x))
    for q, lst in sorted(slots.items()):
        lst = lst[-4:]; t = q * S16
        for j, (n, x) in enumerate(lst):
            step = int(math.log2(max(1, n)) * 2.2) + j; m = PENTA[step % 5] + 12 * (step // 5); m = min(m, 98)
            put(K.bell(m, .8), t + j * .012, .25 + .5 * (x - CX + RC) / (2 * RC), .30 / (1 + .35 * j) * (1 if len(lst) < 3 else .8))
    pd = K.pad([c for c in PROG], CH, dur, .07); st += pd[:, None]
    if r["full"]:
        for j, m in enumerate([74, 78, 81, 86, 90, 93]): put(K.bell(m, 1), r["full"] + .1 + j * S16 * 2, .3 + .08 * j, .34)
    st = K.room(st, .14, 1.0); tt = np.arange(N) / SR; st *= (np.minimum(1, tt / .3) * np.minimum(1, (dur - tt) / 1.5))[:, None]
    pk = float(np.abs(st).max()) or 1; st = st / pk * .7
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "all"
    if m == "search": search(int(sys.argv[2]) if len(sys.argv) > 2 else 20); sys.exit()
    r = simulate(SEED, record=True); n = len(r["frames"]); print("2048個", r["full"], "秒 コマ", n, flush=True)
    if m == "stills":
        for x in sys.argv[2].split(","): Image.fromarray(frame(r, int(float(x) * FPS))).save(f"{B}/s_{float(x):05.1f}.jpg", quality=90)
    else:
        out = sys.argv[2] if len(sys.argv) > 2 else f"output/laser1_{LANG}.mp4"
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", f"{B}/v.mp4"], stdin=subprocess.PIPE)
        for i in range(n): p.stdin.write(frame(r, i).tobytes())
        p.stdin.close(); p.wait(); audio(r, n / FPS, f"{B}/a.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{B}/v.mp4", "-i", f"{B}/a.wav", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True); print(out)
