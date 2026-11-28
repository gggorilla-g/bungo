# flipcross.py — 1枚の正方形を、4つの辺で裏返してコピーする。それをくり返すと十字の形がどんどん育ち、最後は78,125枚。そのあと早回しで巻きもどって頭にもどる（縦のショート）
#   持ち主 11/28：正方形を辺で裏返してふやしていく動画（録画）を見せて「ガラス石で乾いたマット&エコーで、シャッシャッみたいなこうかおんもあっていい」
#   まねたのは仕組み（形をまるごと辺で裏返してコピーし、くり返すと模様が育つ）と流れ（ふえる → 巻きもどり → 頭）。形は自前：
#     録画は8方向にコピーして真ん中に穴があく形。こちらは上下左右の4方向にだけ裏返すので、真ん中も残って「十字」がくり返す形（ヴィチェック模様）になる。1 → 5 → 25 → … → 78,125枚
#   音：少し空洞のある石の音（kalimba の stone）を乾いた響きで、エコーを少し。裏返って着いた瞬間に1打。裏返っている間は、紙をめくるような「シャッ」（音の高さが上がっていく息の音）
#   python3 tools/flipcross.py stills ／ all（LANG_OUT=en で英語）→ output/flipcross1_<ja|en>.mp4
import colorsys, math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K
import loopkit as L

W, H, FPS = T.W, T.H, T.FPS
NS = 7; CX, CY, FIT = 540.0, 1010.0, 960.0                             # 段階の数（5^7 = 78,125枚）、模様の中心、できあがりの幅
FL = [1.8, 1.55, 1.35, 1.15, .98, .84, .72]; ZM = 1.0;   # 11/28「尺ちょっとずつ長くしてみようか」→ 前より長め
OV = .55               # 段階ごとの1回の裏返しの時間、引く時間、次の裏返しが前に重なる割合
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]                               # 上・右・下・左
SCHED = []; t = .6
for k in range(NS):
    for j in range(4): SCHED.append((k, j, t, t + FL[k])); t += FL[k] * (1 - OV) if j < 3 else FL[k]
    t += ZM
TEND = t + .2; HOLD, TREW = 1.3, 1.7; DUR = TEND + HOLD + TREW; NF = int(round(DUR * FPS))
def stage_start(k): return min(s[2] for s in SCHED if s[0] == k)
def stage_end(k): return max(s[3] for s in SCHED if s[0] == k)

def hue_shift(c, dh, ds=0.0):
    sh0 = c.shape; c = c.reshape(1, -1, 3); hsv = cv2.cvtColor((np.clip(c, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32); hsv[..., 0] = (hsv[..., 0] + dh * 180) % 180; hsv[..., 1] = np.clip(hsv[..., 1] * (1 + ds), 0, 255)
    return (cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32) / 255).reshape(sh0)
SHIFT = [.0, .16, .33, .5, .66]                                       # まん中・上・右・下・左のコピーの色のずらし（段階ごとに少しずつ色が回る）
COLS = [np.array([[[.25, .85, 1.0]]], np.float32)]; MASK = [np.ones((1, 1), bool)]
for k in range(NS):
    c, m = COLS[-1], MASK[-1]; n = c.shape[0]; C2 = np.zeros((3 * n, 3 * n, 3), np.float32); M2 = np.zeros((3 * n, 3 * n), bool)
    for j, (ox, oy) in enumerate([(1, 1), (1, 0), (2, 1), (1, 2), (0, 1)]):
        C2[oy * n:(oy + 1) * n, ox * n:(ox + 1) * n] = hue_shift(c.reshape(-1, 1, 3), SHIFT[j] / (1 + .6 * k), .15).reshape(n, n, 3) if j else c; M2[oy * n:(oy + 1) * n, ox * n:(ox + 1) * n] = m
    COLS.append(C2); MASK.append(M2)

def shape_img(k, s):
    """段階 k の形を、1枚の大きさ s px で描いた絵（RGBA）。s が大きい時は、1枚ずつにすき間とつやをつける"""
    n = 3 ** k; size = max(2, int(round(n * s))); c = np.ones_like(COLS[k]) * .96; m = MASK[k].astype(np.float32)   # 色は場所で決める（ここは白）
    if s >= 1: rgb = cv2.resize(c, (size, size), interpolation=cv2.INTER_NEAREST); a = cv2.resize(m, (size, size), interpolation=cv2.INTER_NEAREST)
    else:                                                                # 1枚が1pxより小さい時：色は平均、濃さは3倍にして、細い線でも暗くならないように
        a0 = cv2.resize(m, (size, size), interpolation=cv2.INTER_AREA); rgb = cv2.resize(c * m[..., None], (size, size), interpolation=cv2.INTER_AREA) / np.maximum(a0[..., None], 1e-4); a = np.clip(a0 * 4.0, 0, 1); rgb = np.clip(rgb * 1.15, 0, 1)
    if s >= 5:                                                           # 1枚ずつのすき間と、左上の明るいふち（ガラスの板のように）
        u = (np.arange(size) % s) / s; g = ((u > .06) & (u < .94)).astype(np.float32); grid = g[None, :] * g[:, None]; hl = (((u < .16)[None, :]) | ((u < .16)[:, None])).astype(np.float32) * .25
        a = a * (.25 + .75 * grid); rgb = np.clip(rgb * (.82 + .18 * grid[..., None]) + hl[..., None] * a[..., None], 0, 1)
    return np.dstack([rgb * a[..., None], a]).astype(np.float32)
def put(buf, img, x0, y0):
    h, w = img.shape[:2]; xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb <= xa or yb <= ya: return
    s = img[ya - y0:yb - y0, xa - x0:xb - x0]; reg = buf[ya:yb, xa:xb]; reg[:] = reg * (1 - s[..., 3:4]) + s[..., :3]
def warp(buf, img, quad):
    h, w = img.shape[:2]; src = np.float32([[0, 0], [w, 0], [w, h], [0, h]]); M = cv2.getPerspectiveTransform(src, np.float32(quad))
    out = cv2.warpPerspective(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT); buf[:] = buf * (1 - out[..., 3:4]) + out[..., :3]

def cam(ts):
    """1枚の大きさ（px）。段階 k の裏返しの間は、できあがり（3^(k+1) 枚）が FIT に収まる大きさ。段階の間に引く"""
    for k in range(NS):
        if ts < stage_start(k): sa = FIT / 3 ** k if k else FIT / 3 * 1.0; sb = FIT / 3 ** (k + 1); u = T.sstep(stage_start(k) - ZM, stage_start(k), ts); return sa + (sb - sa) * u if k else sb
        if ts <= stage_end(k) + 1e-6: return FIT / 3 ** (k + 1)
    return FIT / 3 ** NS
BG = None
def make_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); b = (np.array([9, 8, 24], np.float32) * (1 - yy / H)[..., None] + np.array([3, 3, 12], np.float32) * (yy / H)[..., None]) / 255
    return (b + (np.exp(-(((xx - CX) / 560) ** 2 + ((yy - CY) / 640) ** 2)) * 12 / 255)[..., None] * np.array([.9, .7, 1.4], np.float32)).astype(np.float32)
def rainbow():
    """場所で決まる色：模様の中心のまわりを一周する虹（遠くから見ても色が混ざって灰色にならない）"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); h = (np.arctan2(yy - CY, xx - CX) / (2 * np.pi) + .55) % 1.0; r = np.clip(np.hypot(xx - CX, yy - CY) / 520, 0, 1)
    hsv = np.dstack([h * 179.99, (.55 + .40 * r) * 255, np.full_like(h, 255)]).astype(np.uint8); return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB).astype(np.float32) / 255
RBW = rainbow()
BG = make_bg(); INK = (244, 246, 255, 255); GOLD = (255, 222, 150, 255)

def frame_at(ts, rew=0.0):
    s = cam(ts); buf = np.zeros((H, W, 3), np.float32); k = 0                      # buf にはまず明るさ（白）だけを描き、最後に場所の色をかける
    for kk in range(NS):
        if ts >= stage_start(kk) - ZM: k = kk
    done_k = [j for (kk, j, a, b) in SCHED if kk == k and ts >= b]; active = [(j, (ts - a) / (b - a)) for (kk, j, a, b) in SCHED if kk == k and a <= ts < b]
    if ts >= TEND - .2: k, done_k, active = NS, [], []
    base = shape_img(k, s); n = 3 ** k; L_ = n * s; x0, y0 = CX - L_ / 2, CY - L_ / 2
    for j in done_k:                                                     # 裏返し終わったコピー
        dx, dy = DIRS[j]; put(buf, shape_img_c(k, s, j + 1), int(round(x0 + dx * L_)), int(round(y0 + dy * L_)))
    put(buf, base, int(round(x0)), int(round(y0)))
    for j, u in active:                                                  # 裏返っている途中（辺を軸に、ページをめくるように回る）
        th = math.pi * T.sstep(0, 1, u); c_ = math.cos(th); sp = 1 + .22 * math.sin(th); img = shape_img_c(k, s, j + 1) * np.float32(.62 + .38 * abs(c_)); img[..., 3] /= (.62 + .38 * abs(c_))
        dx, dy = DIRS[j]
        if dy:                                                           # 上下の辺：高さが cos で縮み（はじめは真ん中に重なっていて、最後は外側）、遠い辺が少し広がる（遠近）
            ye = y0 if dy < 0 else y0 + L_; yf = ye + L_ * c_ if dy < 0 else ye - L_ * c_
            q = [[x0, ye], [x0 + L_, ye], [CX + L_ / 2 * sp, yf], [CX - L_ / 2 * sp, yf]]
        else:
            xe = x0 if dx < 0 else x0 + L_; xf = xe + L_ * c_ if dx < 0 else xe - L_ * c_
            q = [[xe, y0], [xe, y0 + L_], [xf, CY + L_ / 2 * sp], [xf, CY - L_ / 2 * sp]]
        warp(buf, img, q)
    A = np.clip(buf.max(-1, keepdims=True) * 1.2, 0, 1); buf = BG * (1 - A) + RBW * buf
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    cnt = 5 ** k * (1 + len(done_k)) if k < NS else 5 ** NS
    T.fit_text(d, (W / 2, 140), T.tr("1枚の正方形を、何度も裏返すと？", "Flip one square over and over"), 60, 1000, INK)
    T.fit_text(d, (W / 2, 214), T.tr("上下左右の辺で裏返して、5倍にふやす", "Flip it over all four edges: five times as many"), 42, 1000, GOLD)
    d.text((W / 2, 318), f"{cnt:,}", font=T.fnt(96), fill=INK, anchor="mm"); d.text((W / 2, 384), T.tr("枚", "squares"), font=T.fnt(30, False), fill=(180, 186, 214, 255), anchor="mm")
    cap = (T.tr("◀◀ 巻きもどし", "◀◀ Rewind"), INK) if rew > 0 else ((T.tr(f"1枚から {5 ** NS:,}枚", f"{5 ** NS:,} squares from one"), (255, 232, 170, 255)) if ts >= TEND - .2 else None)
    if cap: T.fit_text(d, (W / 2, 1640), cap[0], 52, 1000, cap[1])
    return np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=int(ts * FPS))).convert("RGBA"), ov).convert("RGB"))
_CC = {}
def shape_img_c(k, s, j):
    """コピー j（1〜4）の絵：色を少しずらす"""
    key = (k, round(s, 3), j)
    if key not in _CC:
        if len(_CC) > 12: _CC.clear()
        _CC[key] = shape_img(k, s)
    return _CC[key]
def make_frame(fi):
    ts, rew = L.sim_time(fi / FPS, TEND, HOLD, TREW); return frame_at(ts, rew)

def whoosh(dur, sr, rng):
    """紙をめくるような「シャッ」：息のような音の、高さの中心が上がっていく"""
    n = int(sr * dur); x = rng.normal(0, 1, n).astype(np.float32); tt = np.arange(n) / sr; out = np.zeros(n, np.float32); y1 = y2 = 0.0
    fc = 700 * (5.0 ** (tt / dur)); r = .97; xs = x
    from scipy.signal import lfilter
    seg = 256
    for i in range(0, n, seg):                                           # 少しずつ中心をずらす帯の音
        f = fc[i]; th = 2 * math.pi * f / sr; b = [(1 - r * r) / 2, 0, -(1 - r * r) / 2]; a = [1, -2 * r * math.cos(th), r * r]; out[i:i + seg] = lfilter(b, a, xs[i:i + seg])
    env = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 1.6 * (.4 + .6 * tt / dur); return out * env
def audio(path):
    fwd = TEND + HOLD; a = T.Audio(fwd, mat="stone", max_same=3, window=.02); ns = int(T.SR * fwd); under = np.zeros(ns, np.float32); rng = np.random.default_rng(3)
    for idx, (k, j, ta, tb) in enumerate(SCHED):
        tn = K.canon_tones(idx // 2 % 8, 60, 86); a.note(tb, tn[min(len(tn) - 1, (j * 2 + k) % len(tn))], vel=.62 + .03 * k, pan=.5 + .3 * DIRS[j][0])   # 着いた瞬間
        w = whoosh(tb - ta, T.SR, rng); i0 = int(ta * T.SR); w *= .045 / (np.sqrt((w ** 2).mean()) + 1e-9) * (.8 + .05 * k); kk = min(len(w), ns - i0); under[i0:i0 + kk] += w[:kk]
    a.note(TEND - .2, K.CANON[0][0] + 24, vel=.7, pan=.5)
    tmp = path + ".fwd.wav"; a.write(tmp, room=(.20, 1.8), under=under); L.add_rewind(tmp, path, TEND, HOLD, TREW, gain=.55); os.remove(tmp)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_flipcross", exist_ok=True)
    print("長さ", round(DUR, 1), "裏返し", len(SCHED), "最後", 5 ** NS)
    if cmd == "stills": print(T.stills(NF, make_frame, "build_flipcross/s", at=(1.3 / DUR, 3.6 / DUR, 12.0 / DUR, 22.0 / DUR, 31.0 / DUR, (TEND + .3) / DUR))); sys.exit()
    out = f"output/flipcross1_{T.LANG}.mp4"; audio("build_flipcross/a.wav"); T.encode(NF, make_frame, "build_flipcross/a.wav", out); print(out)
