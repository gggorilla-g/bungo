# trendkit.py — 「伸びている型を自前で作り直す」ときの共通の道具（縦のショート 1080×1920・60コマ）
#   流れと決まりは docs/trend-pipeline.md。新しい型は、このファイルを使って tools/<名前>.py を1つ書く（見本：tools/tiles.py）。
#   ここに入っているもの
#     絵：background() 背景 ／ sprite()・blit()・blit_mb() 飴玉のような玉（動きのぶれつき） ／ glow()・add_glow() やわらかい光
#         Trail 通った跡（やわらかい光の線） ／ wood_stack() 木の板のかさね ／ paste()・paste_rot() 絵をのせる ／ to_frame() 文字をのせて1コマにする ／ PALETTE8 8色
#         持ち主 2026-11-27「テクスチャと軌跡が安っぽい」→ ベタ塗りの四角・細い直線をやめた。物には材質（木目・面取り・ガラスの透け）、跡はぼかした光、ふちは縮小でなめらかに
#     音：Audio … 当たった時刻にそのまま鳴らす（時刻をそろえ直さない）。音色は、硬い玉が板に当たる音（kalimba.knock）。音の高さはカノン進行の和音の音
#         持ち主 2026-11-27「音はもっと乾いたカロっ(飴玉を口で転がすような)音がいい。音階はカノン」
#         同日「電子音ぽすぎるんだよな。もっと物理的な音がいい」「二度うちは違う感じがする。恣意的な感じがする」→ 鳴らすのは、絵の中で物が当たった瞬間だけ。飾りの音を足さない
#         材質は3つ（木・竹・空洞のある木）を、動画1本ごとに順番に回す：聞き比べへの返事 11/27「2.3.4全部いいローテでいい」→ next_mat()
#         11/25「バウンドのタイミングと音が鳴るタイミングは合わせて」／11/27「ブラーエコーもかけすぎない」
#     書き出し：encode() コマを ffmpeg に流して音と合わせる ／ stills() 確認用の絵 ／ pick_seed() 乱数さがし
#   確かめるのは tools/trend/check.py（長さ・音量・高い音・止まって見える時間）と、出だし・真ん中・最後の絵を目で見ること（等倍の切り出しも見る）
import math, os, sys, subprocess, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kalimba as K

W, H, FPS, SR = 1080, 1920, 60, 48000
LANG = os.environ.get("LANG_OUT", "ja"); EN = LANG == "en"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"; FJM = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
_f = {}
def fnt(sz, bold=True):
    k = (sz, bold)
    if k not in _f: _f[k] = ImageFont.truetype(FJ if bold else FJM, sz)
    return _f[k]
def tr(ja, en): return en if EN else ja
def sstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a))) if b != a else float(x >= b); return t * t * (3 - 2 * t)

# 8色（落ち着いた明るさ。白く飛ばさない）
PALETTE8 = [("赤", "Red", (232, 96, 96)), ("橙", "Orange", (240, 150, 74)), ("黄", "Yellow", (236, 214, 96)), ("緑", "Green", (104, 196, 118)),
            ("水色", "Cyan", (92, 198, 226)), ("青", "Blue", (98, 126, 236)), ("紫", "Purple", (170, 110, 222)), ("桃", "Pink", (240, 150, 190))]
def cname(i): return PALETTE8[i][1] if EN else PALETTE8[i][0]

# ---------- 絵 ----------
def _unit(v): v = np.asarray(v, np.float32); return v / np.linalg.norm(v)
LIGHT = _unit((-.45, -.62, .64))                       # 光は左上の手前から
def sprite(col, r, ss=4):
    """飴玉（ガラス玉）のような玉（RGBA、0..1）。4倍の大きさで描いて縮めるので、ふちがなめらか
       光の入る左上が明るく、反対側（右下）は中を通った光で内側から明るい。小さくはっきりした映りこみが1つ"""
    R = r * ss; s = int(2 * R + 8 * ss); yy, xx = np.mgrid[0:s, 0:s].astype(np.float32); c0 = (s - 1) / 2
    X = (xx - c0) / R; Y = (yy - c0) / R; d2 = X * X + Y * Y; d = np.sqrt(d2); nz = np.sqrt(np.clip(1 - d2, 0, 1)); a = np.clip((1 - d) * R + .5, 0, 1)
    c = np.asarray(col, np.float32) / 255; lxy = math.hypot(LIGHT[0], LIGHT[1])
    wrap = np.clip((X * LIGHT[0] + Y * LIGHT[1] + nz * LIGHT[2] + .60) / 1.60, 0, 1)             # 光は中まで回る（影の境目を作らない）
    body = c * (.46 + .54 * wrap ** 1.15)[..., None]                                           # 本体
    sdir = -(X * LIGHT[0] + Y * LIGHT[1]) / lxy; pdir = (X * LIGHT[1] - Y * LIGHT[0]) / lxy    # 光の向きにそった位置（＋が光の反対側）と、それに直角の位置
    trans = np.exp(-((sdir - .60) / .25) ** 2) * np.exp(-(pdir / .70) ** 2) * nz ** .30          # 中を通って出てくる光（右下の内側が明るい三日月）
    body += (c * 1.05 + .10) * (trans * .62)[..., None]
    body *= (1 - .20 * (1 - nz) ** 3 * np.clip(.5 - sdir, 0, 1))[..., None]                     # 光の側のふちは、ほんの少し暗い
    body += (.10 * (1 - nz) ** 5)[..., None]                                                   # ふちのうすい反射
    hv = _unit(LIGHT + np.array([0, 0, 1], np.float32)); nh = np.clip(X * hv[0] + Y * hv[1] + nz * hv[2], 0, 1)
    body += (nh ** 320 * .95 + nh ** 34 * .07)[..., None]                                      # 映りこみ：小さくはっきり＋ごくうすい広がり
    rgb = np.clip(body, 0, 1) * a[..., None]; k = s // ss
    rgb = cv2.resize(rgb, (k, k), interpolation=cv2.INTER_AREA); a = cv2.resize(a, (k, k), interpolation=cv2.INTER_AREA)
    return np.dstack([rgb / np.maximum(a, 1e-4)[..., None], a]).astype(np.float32)
def ring(col, r, w=2.0, ss=4):
    """細い輪（RGBA、0..1）。ふちがなめらか"""
    R = r * ss; s = int(2 * R + 6 * ss); yy, xx = np.mgrid[0:s, 0:s].astype(np.float32); c0 = (s - 1) / 2; d = np.sqrt((xx - c0) ** 2 + (yy - c0) ** 2)
    a = np.clip(w * ss / 2 + .5 - np.abs(d - R), 0, 1); k = s // ss; a = cv2.resize(a, (k, k), interpolation=cv2.INTER_AREA)
    return np.dstack([np.broadcast_to(np.asarray(col, np.float32) / 255, (k, k, 3)), a]).astype(np.float32)
def blit(buf, sp, x, y, al=1.0):
    """buf（H,W,3 の 0..1）に絵（RGBA）を置く。中心が (x, y)。小数の位置もそのまま置く（1画素ずつカクカク動かない）。画面の外は切る"""
    h, w = sp.shape[:2]; fx, fy = x - w / 2, y - h / 2; x0, y0 = int(math.floor(fx)), int(math.floor(fy)); dx, dy = fx - x0, fy - y0
    if al <= 0 or x0 >= buf.shape[1] or y0 >= buf.shape[0] or x0 + w + 1 <= 0 or y0 + h + 1 <= 0: return
    pm = np.dstack([sp[..., :3] * sp[..., 3:4], sp[..., 3:4]])
    if dx > .02 or dy > .02: pm = cv2.warpAffine(pm, np.float32([[1, 0, dx], [0, 1, dy]]), (w + 1, h + 1), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    _over(buf, pm, x0, y0, al)
def _over(buf, pm, x0, y0, al=1.0):
    """色に濃さをかけ済みの絵（pm）を、左上 (x0, y0) にのせる"""
    Hh, Ww = buf.shape[:2]; h, w = pm.shape[:2]; xa, ya, xb, yb = max(0, x0), max(0, y0), min(Ww, x0 + w), min(Hh, y0 + h)
    if xb <= xa or yb <= ya: return
    s = pm[ya - y0:yb - y0, xa - x0:xb - x0]; reg = buf[ya:yb, xa:xb]; reg[:] = reg * (1 - s[..., 3:4] * al) + s[..., :3] * al
def blit_mb(buf, sp, pts, al=1.0):
    """動いている玉：1コマの間に通った位置を何点か受けとり、その平均でのせる（速いほど流れて見える。止まっていればくっきり）"""
    if len(pts) == 1 or max(abs(pts[0][0] - pts[-1][0]), abs(pts[0][1] - pts[-1][1])) < 1.2: return blit(buf, sp, pts[-1][0], pts[-1][1], al)
    h, w = sp.shape[:2]; xs = [p[0] - w / 2 for p in pts]; ys = [p[1] - h / 2 for p in pts]; x0, y0 = int(math.floor(min(xs))), int(math.floor(min(ys)))
    ww, hh = int(math.ceil(max(xs))) - x0 + w + 2, int(math.ceil(max(ys))) - y0 + h + 2; acc = np.zeros((hh, ww, 4), np.float32); pm = np.dstack([sp[..., :3] * sp[..., 3:4], sp[..., 3:4]])
    for fx, fy in zip(xs, ys): acc += cv2.warpAffine(pm, np.float32([[1, 0, fx - x0], [0, 1, fy - y0]]), (ww, hh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    _over(buf, acc / len(pts), x0, y0, al)
def paste(buf, rgba, x0, y0, al=1.0):
    """絵（RGBA）を、左上 (x0, y0)（整数）にのせる"""
    _over(buf, np.dstack([rgba[..., :3] * rgba[..., 3:4], rgba[..., 3:4]]), int(x0), int(y0), al)
def paste_rot(buf, rgba, cx, cy, ang, al=1.0):
    """絵（RGBA）を、中心 (cx, cy)・角度 ang（ラジアン）でのせる"""
    h, w = rgba.shape[:2]; D = int(math.hypot(w, h)) + 4; pm = np.dstack([rgba[..., :3] * rgba[..., 3:4], rgba[..., 3:4]])
    x0, y0 = int(math.floor(cx - D / 2)), int(math.floor(cy - D / 2)); M = cv2.getRotationMatrix2D((w / 2, h / 2), -math.degrees(ang), 1.0); M[0, 2] += cx - x0 - w / 2; M[1, 2] += cy - y0 - h / 2
    _over(buf, cv2.warpAffine(pm, M, (D, D), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0), x0, y0, al)
_g = {}
def glow(sigma):
    """やわらかい光の形（まん中が1、まわりへなだらかに消える）"""
    if sigma not in _g:
        n = int(sigma * 3.2); yy, xx = np.mgrid[-n:n + 1, -n:n + 1].astype(np.float32); g = np.exp(-(xx * xx + yy * yy) / (2 * sigma * sigma)); _g[sigma] = (g - g[0, n]).clip(0, 1).astype(np.float32)
    return _g[sigma]
def add_glow(buf, g, x, y, col, gain=1.0):
    """光を足す（重なっても白く飛ばないよう、明るい所ほど足しにくくする）。col は 0..255"""
    Hh, Ww = buf.shape[:2]; h, w = g.shape; x0, y0 = int(round(x - w / 2)), int(round(y - h / 2)); xa, ya, xb, yb = max(0, x0), max(0, y0), min(Ww, x0 + w), min(Hh, y0 + h)
    if xb <= xa or yb <= ya or gain <= 0: return
    s = g[ya - y0:yb - y0, xa - x0:xb - x0, None] * (np.asarray(col, np.float32) / 255 * gain); reg = buf[ya:yb, xa:xb]; reg[:] = 1 - (1 - reg) * (1 - np.clip(s, 0, 1))
def background(center=(W / 2, 1000)):
    """暗い紺の背景。上から下へほんの少し色が変わり、まん中がわずかに明るく、四すみは落ちる（ベタ塗りにしない）"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); d = np.sqrt((xx - center[0]) ** 2 + ((yy - center[1]) * .8) ** 2); v = (yy / H)[..., None]
    b = np.array([.026, .030, .060], np.float32) * (1 - v) + np.array([.040, .032, .052], np.float32) * v
    b = b + (np.exp(-(d / 760) ** 2) * .040)[..., None] * np.array([.75, .85, 1.25], np.float32)
    b *= (1 - .35 * np.clip((np.sqrt(((xx - W / 2) / (W * .72)) ** 2 + ((yy - H / 2) / (H * .72)) ** 2) - .55) / .6, 0, 1) ** 2)[..., None]
    return np.clip(b, 0, 1).astype(np.float32)

class Trail:
    """玉の通った跡を、光で残す（ペンで引いたような、同じ太さ・同じ明るさの線にしない）。2段で描く：
       1) 残像：細くやわらかい線が、ゆっくり消える。明るさは「そこにいた時間」に比例させる（長時間露光の写真と同じ。弧のてっぺんは遅いので明るく、床の近くは速いのでうすい）
          → step() に、このコマで進んだ線分と速さを渡す
       2) 尾：玉のすぐ後ろの、太く短い光。先へ行くほど細く・うすくなる → render() の wakes に、玉ごとの最近の位置（新しい順）を渡す
       half：残像の明るさが半分になるまでの秒数"""
    def __init__(self, y0, y1, half=1.1, gain=1.0):
        self.y0, self.y1, self.gain = y0, y1, gain; self.long = np.zeros((y1 - y0, W, 3), np.float32); self.wk = np.zeros_like(self.long); self.dl = .5 ** (1 / (half * FPS))
    def clear(self): self.long[:] = 0
    def _p(self, x, y): return (int(round(x * 16)), int(round((y - self.y0) * 16)))
    def step(self, segs):
        """segs：[(x0, y0, x1, y1, (r,g,b) 0..255, 速さ px/秒), …]"""
        self.long *= self.dl
        for (xa, ya, xb, yb, col, speed) in segs:
            w = min(1.0, max(.15, 260.0 / (speed + 120.0))); c = np.asarray(col, np.float32) / 255 * (.62 * w)
            cv2.line(self.long, self._p(xa, ya), self._p(xb, yb), tuple(float(v) for v in c), 2, cv2.LINE_AA, 4)
    def render(self, buf, wakes=(), wake_gain=.42):
        h = self.y1 - self.y0; wk = self.wk; wk[:] = 0
        for pts, col, w0 in wakes:
            n = len(pts); c = np.asarray(col, np.float32) / 255
            for k in range(n - 1, 0, -1):                                                         # 古い方から描く（新しく太い方が上にのる）
                a = k / n; cv2.line(wk, self._p(*pts[k]), self._p(*pts[k - 1]), tuple(float(v) for v in c * (1 - a) ** 1.7), max(1, int(round(2 + (w0 - 2) * (1 - a) ** 2.0))), cv2.LINE_AA, 4)
        small = cv2.resize(self.long, (W // 4, h // 4), interpolation=cv2.INTER_AREA); halo = cv2.resize(cv2.GaussianBlur(small, (0, 0), 3.2), (W, h), interpolation=cv2.INTER_LINEAR)
        g = cv2.GaussianBlur(self.long, (0, 0), 1.25) + halo * .65                                # 残像：芯をほんの少しぼかし、まわりに光のにじみ
        if wakes: g += cv2.GaussianBlur(wk, (0, 0), 4.5) * wake_gain                              # 尾：大きくぼかす
        reg = buf[self.y0:self.y1]; reg[:] = 1 - (1 - reg) * (1 - np.clip(g * self.gain, 0, .92))

WOOD = (np.array([.90, .73, .50], np.float32), np.array([.72, .52, .33], np.float32))            # 明るい木・濃い木
def wood_stack(w, unit, n, seed=0, gap=2, ss=3, tones=WOOD):
    """木の板を n 枚かさねた絵（RGBA 0..1、幅 w・高さ n*unit）。上から 0,1,2… 枚め。1枚ごとに色と木目が少し違い、角は丸く、上の面取りが明るい"""
    rng = np.random.default_rng(1000 + seed); out = np.zeros((n * unit, w, 4), np.float32); hh = unit - gap; Ws, Hs = w * ss, hh * ss
    yy, xx = np.mgrid[0:Hs, 0:Ws].astype(np.float32); rad = 3.2 * ss
    qx = np.abs(xx - (Ws - 1) / 2) - ((Ws - 1) / 2 - rad); qy = np.abs(yy - (Hs - 1) / 2) - ((Hs - 1) / 2 - rad)
    sd = np.sqrt(np.clip(qx, 0, None) ** 2 + np.clip(qy, 0, None) ** 2) + np.minimum(np.maximum(qx, qy), 0) - rad; al = np.clip(.5 - sd, 0, 1)   # 角の丸い四角
    v = yy / (Hs - 1); u = xx / (Ws - 1)
    for q in range(n):
        t = rng.uniform(0, 1) * .75 + (.25 if q % 2 else 0); base = tones[0] * (1 - t) + tones[1] * t
        nz = rng.normal(0, 1, (Hs // 2 + 2, 6)).astype(np.float32); grain = cv2.resize(nz, (Ws, Hs), interpolation=cv2.INTER_CUBIC)                     # 横に長くのびた木目
        ph = rng.uniform(0, 6.28); lines = .5 + .5 * np.sin(v * rng.uniform(5, 9) + grain * 1.4 + ph + u * rng.uniform(-1.5, 1.5)); lines = lines ** 6
        shade = 1 + .050 * grain - .13 * lines                                                 # 木目のむらと、濃い筋
        shade *= 1.10 - .22 * v ** 1.6                                                          # 上が明るく、下が暗い（上から光）
        shade *= 1.03 - .07 * u                                                                 # 左がほんの少し明るい
        shade += .16 * np.exp(-(yy / (1.1 * ss)) ** 2)                                          # 上の面取りのハイライト
        shade -= .12 * np.exp(-((Hs - 1 - yy) / (1.2 * ss)) ** 2)                               # 下のふちの影
        rgb = np.clip(base[None, None, :] * shade[..., None], 0, 1) * al[..., None]
        rgb = cv2.resize(rgb, (w, hh), interpolation=cv2.INTER_AREA); a2 = cv2.resize(al, (w, hh), interpolation=cv2.INTER_AREA)
        out[q * unit:q * unit + hh, :, :3] = rgb / np.maximum(a2, 1e-4)[..., None]; out[q * unit:q * unit + hh, :, 3] = a2
    return out

_GR = None
def to_frame(buf, draw=None, grain=None):
    """0..1 の絵を1コマ（uint8）にする。draw(d) で文字や線をのせる（d は RGBA の ImageDraw。色の4つめで濃さを指定できる）
       grain にコマ番号を渡すと、ごく細かい粒子をまぜる（なだらかな色の段々＝バンディングが出ない）"""
    global _GR
    x = np.clip(buf, 0, 1) * 255
    if grain is not None:
        if _GR is None: _GR = [np.random.default_rng(40 + k).normal(0, .9, (H, W, 1)).astype(np.float32) for k in range(5)]
        x = np.clip(x + _GR[int(grain) % 5], 0, 255)
    im = Image.fromarray((x + .5).astype(np.uint8))
    if draw is None: return np.asarray(im)
    im = im.convert("RGBA"); ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); draw(ImageDraw.Draw(ov)); return np.asarray(Image.alpha_composite(im, ov).convert("RGB"))
def fit_text(d, xy, s, size, maxw, fill, anchor="mm", bold=True, minsize=22):
    """幅 maxw におさまる大きさに下げて書く（はみ出し防止）"""
    while size > minsize and d.textlength(s, font=fnt(size, bold)) > maxw: size -= 2
    d.text(xy, s, font=fnt(size, bold), fill=fill, anchor=anchor); return size

# ---------- 音 ----------
MATS = ("wood", "bamboo", "hollow")                      # 木の板 → 竹の板 → 空洞のある木。動画1本ごとに順番に回す
MAT_LOG = os.path.join(ROOT, "nazo", "trend", "mat_log.txt")   # 1行 = "<動画の名前> <材質>"（作った順）
def next_mat():
    """次の動画に使う材質。mat_log.txt の最後の行の、次の材質を返す。
       新しい動画を作る時：python3 tools/trendkit.py nextmat で材質を見て、スクリプトの MAT の既定値に書き、mat_log.txt に1行足す
       （日本語版と英語版は同じ材質。作り直しても変わらないよう、スクリプトに書いておく）"""
    last = None
    if os.path.exists(MAT_LOG):
        for l in open(MAT_LOG, encoding="utf-8"):
            w = l.split()
            if len(w) >= 2 and w[1] in MATS: last = w[1]
    return MATS[0] if last is None else MATS[(MATS.index(last) + 1) % len(MATS)]

class Audio:
    """当たった出来事を集めて、最後に1本の音にする。鳴らすのは、絵の中で物が当たった瞬間だけ（飾りの音・二度打ち・締めの旋律を足さない）
       hit(t, u)：時刻 t に、u（0＝低い … 1＝高い）の高さで1打。音は、その時のカノン進行の和音の音から選ぶので、重なっても濁らない
       note(t, midi)：高さを直接指定
       mat：物の材質（kalimba.MATERIALS。"wood" 木の板 ／ "bamboo" 竹 ／ "hollow" 空洞のある木）。"karo" は前の作り方（波を足した音）
       同じ瞬間（window 秒以内）に鳴るのは max_same 音まで（強いものを残す）"""
    def __init__(self, dur, lo=69, hi=91, mat="wood", chord_len=2.4, max_same=3, window=.03):
        self.dur, self.lo, self.hi, self.mat, self.chord_len, self.max_same, self.window = dur, lo, hi, mat, chord_len, max_same, window; self.ev = []
    def chord_index(self, t): return int(t // self.chord_len) % 8
    def hit(self, t, u, vel=.8, chord=None, octave=0):
        tones = K.canon_tones(self.chord_index(t) if chord is None else chord, self.lo, self.hi); m = tones[int(min(.999, max(0, u)) * len(tones))] + 12 * octave
        self.ev.append((float(t), int(m), float(vel), .2 + .6 * float(min(1, max(0, u))))); return m
    def note(self, t, midi, vel=.8, pan=.5): self.ev.append((float(t), int(midi), float(vel), float(pan)))
    def write(self, path, target_rms=.15, room=(.03, .25), under=None):
        """room＝(足す量, 響きの長さ秒)。ふだんは (.03, .25)＝ほとんど足さない（乾いた音）。
           合体の型（mergecol・mergehole）だけは、エコーを足してよい・裏に低音を入れてよい（持ち主 11/27「これ系のやつは心地よい音にエコーたしていい。裏に低音入れてもいい。ベースは2.3.4で」）
           under＝裏に流す音（長さ N のモノラル。kalimba.pad で作る低い持続音など）"""
        N = int(SR * self.dur); st = np.zeros((N, 2), np.float32); ev = sorted(self.ev); kept = []; i = 0
        while i < len(ev):   # 同時に鳴りすぎないように間引く
            j = i
            while j < len(ev) and ev[j][0] - ev[i][0] < self.window: j += 1
            kept += sorted(ev[i:j], key=lambda e: -e[2])[:self.max_same]; i = j
        for n, (t, m, vel, pan) in enumerate(kept):
            x = K.karo(m, vel, False, .8) if self.mat == "karo" else K.knock(m, vel, self.mat, n % 7)   # 1打ごとに、たたく場所が少し違う
            a = int(t * SR)
            if a < 0 or a >= N: continue
            k = min(len(x), N - a); st[a:a + k, 0] += x[:k] * math.cos(pan * math.pi / 2) * vel; st[a:a + k, 1] += x[:k] * math.sin(pan * math.pi / 2) * vel
        if under is not None: st[: len(under)] += np.asarray(under, np.float32)[:N, None]
        st = K.room(st, room[0], room[1])
        tt = np.arange(N) / SR; st *= (np.minimum(1, tt / .05) * np.minimum(1, (self.dur - tt) / .4))[:, None]
        act = np.abs(st).max(1) > 1e-4; rms = float(np.sqrt((st[act] ** 2).mean())) if act.any() else 1.0
        st = np.tanh(st / rms * target_rms * 1.2) / 1.2             # 聞こえる大きさでそろえ、短い山はやわらかく丸める
        with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())
        return len(kept)

# ---------- 書き出し ----------
def encode(n, frame_fn, wav, out, crf=18):
    """frame_fn(i) → (H,W,3) uint8 を n コマ流し、音（wav）と合わせて mp4 にする"""
    tmp = f"{out}.{os.getpid()}.v.mp4"                     # 同じ動画を2つ同時に作っても、途中のファイルがぶつからない
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for i in range(n): p.stdin.write(np.ascontiguousarray(frame_fn(i)).tobytes())
    p.stdin.close(); p.wait()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True); os.remove(tmp)
def stills(n, frame_fn, prefix, at=(.02, .5, .96)):
    """出だし・真ん中・最後の絵を書き出す（目で見る用）。横に並べた1枚も作る"""
    ims = [Image.fromarray(frame_fn(int(n * a))) for a in at]; sheet = Image.new("RGB", (W * len(ims) // 2, H // 2))
    for k, im in enumerate(ims): im.save(f"{prefix}_{k}.jpg", quality=88); sheet.paste(im.resize((W // 2, H // 2)), (k * W // 2, 0))
    sheet.save(f"{prefix}_sheet.jpg", quality=85); return f"{prefix}_sheet.jpg"
def pick_seed(simulate, score, seeds, show=5):
    """乱数をいくつも試し、score（大きいほど良い）で並べる。simulate(seed) の結果を score に渡す"""
    out = []
    for sd in seeds:
        r = simulate(sd); out.append((round(float(score(r)), 2), sd)); print(out[-1], flush=True)
    out.sort(reverse=True); print("上位", out[:show]); return out[0][1]

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "nextmat": print(next_mat())
