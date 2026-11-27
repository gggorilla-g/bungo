# bubblesea.py — クジラの海で、泡が水面ではじけるたびに音が鳴る。音ゲーのように泡が水面へ近づき、カノン進行になる（縦のショート 1080×1920・60コマ）
#   持ち主 11/28：絵の動画（青い海・光のすじ・クジラの影・サンゴの影）の画面を見せて
#     「こういう世界観とこれまでのノウハウで音ゲーっぽくも瞑想ヒーリングっぽくもあるショート動画つくって」
#   まねたのは世界観（青い海・上からの光・クジラの影・サンゴの影）だけ。構図・形・動き・字は自前（海を横から見た断面。クジラは1頭が横切る）
#   音ゲーのところ：8本の筋（レーン）を泡がのぼり、水面（判定の線）に着いた瞬間に鳴る。水面の上に音の名前、上に和音の進み、はじけた数
#   決まり（どれも本物の泡と同じ向き）
#     ・泡は大きいほど低い音（泡が鳴る高さは、半径に反比例する＝ミンナルトの共鳴）。1オクターブ高い泡は半径が半分。だから左のレーンは太く、右は細い
#     ・泡は大きいほど速くのぼる（速さは半径の平方根に比例）。水面に着く時刻が拍に合うように、小さい泡ほど先に出る
#     ・泡は横につぶれ、ゆれながらのぼる（大きいほど大きくゆれる）。はじけると水面に波が立ち、左右へ伝わって消える（1次元の波の式）
#   曲：カノン進行（D A Bm F#m G D G A）を2周。1周めは泡が少しずつふえる（2分→8分→16分）。2周めは金色の泡が旋律（1つの和音に1音）。
#       最後はクジラが泡を8つはく：同時に出るが、大きい泡から先に着くので、低い音から順に鳴る和音になる
#   音：ガラスの響き（kalimba の glass）＋瞑想のような長いエコー＋裏の低い持続音（持ち主 11/28「ガラスっぽい音でいいかも。音階カノンで瞑想エコー」）。
#       出だしに、泡そのものが鳴る短い音を重ねる（同じ高さ・同じ瞬間。水滴がガラスの器を鳴らす水琴窟に近い）。鳴るのは、泡が水面に着いた瞬間だけ
#   python3 tools/bubblesea.py stills ／ zoom ／ all（LANG_OUT=en で英語）→ output/bubblesea1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS = T.W, T.H, T.FPS
BPM = 80.0; BEAT = 60 / BPM; CH = 2 * BEAT; S16 = BEAT / 4; INTRO = .8; NCH = 16
TF = INTRO + NCH * CH                                                   # クジラの泡の、1つめが水面に着く時刻
NL = 8; YS, YV = 520, 1680; WL = 660.0; R0, V0 = 60.0, 420.0           # レーンの数、水面、泡の出口、クジラの体長、レ(D4)の泡の半径、その泡がのぼる速さ
NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]; CHN = ["D", "A", "Bm", "F#m", "G", "D", "G", "A"]
MEL = [78, 76, 74, 73, 71, 69, 71, 73]                                 # 2周めの旋律（1つの和音に1音）
def tones(c): return K.canon_tones(c % 8, 60, 96)[:NL]
def rad(m): return R0 * K.mtof(62) / K.mtof(m)                          # 半径は音の高さに反比例
def speed(r): return V0 * math.sqrt(r / R0)                             # のぼる速さは半径の平方根に比例
RL = [float(np.mean([rad(tones(c)[l]) for c in range(8)])) for l in range(NL)]     # レーンごとの泡の大きさ（8つの和音の平均）
LX = []; _g = (900 - 2 * sum(RL)) / (NL - 1); _x = 50.0                 # レーンの位置：泡どうしのすき間が同じになるように並べる
for _l in range(NL): LX.append(_x + RL[_l]); _x += 2 * RL[_l] + _g

WS = 14.0                                                               # クジラが進む速さ（px/秒）
def whale_y(t): return 1205 + 16 * math.sin(2 * math.pi * t / 7.0)
_r0 = rad(tones(0)[0]); TREL = TF - 1.3                                 # クジラが泡をはく時刻（1つめが TF に着くように）
for _ in range(8): TREL = TF - (whale_y(TREL) - WL * .078 - 14 - (YS + _r0)) / speed(_r0) - .08
XW0 = 540 + WL * .36 + WS * TREL
def whale_xy(t): return XW0 - WS * t, whale_y(t)
def blow_xy(t): x, y = whale_xy(t); return x - WL * .36, y - WL * .078  # 鼻の穴（頭の上）

def chart():
    N = []
    def add(t, l, c, kind, vel):
        m = tones(c)[l]; r = rad(m); v = speed(r); y0 = YV - 12.0
        N.append(dict(t=t, l=l, m=m, r=r, v=v, kind=kind, vel=vel, trel=t - (y0 - (YS + r)) / v - .08, xs=LX[l], off=0.0, y0=y0, ph=(len(N) * 2.399) % 6.283))
    for n in range(NCH):
        t0 = INTRO + n * CH; c = n % 8; e = lambda k: t0 + k * BEAT / 2; s = lambda k: t0 + k * S16
        if n < 2: add(e(0), 0, c, "bass", .75); add(e(2), 2, c, "arp", .55)
        elif n < 4:
            for k, l in enumerate((0, 2, 3, 2)): add(e(k), l, c, "bass" if k == 0 else "arp", .72 if k == 0 else .5)
        elif n < 6:
            for k, l in enumerate((0, 2, 3, 4)): add(e(k), l, c, "bass" if k == 0 else "arp", .72 if k == 0 else .5)
            add(s(3), 6, c, "spark", .34); add(s(7), 7, c, "spark", .34)
        elif n < 8:
            add(e(0), 0, c, "bass", .72); add(e(0), 4, c, "arp", .5); add(e(1), 2, c, "arp", .5); add(e(2), 3, c, "arp", .5); add(e(2), 5, c, "arp", .45); add(e(3), 4, c, "arp", .5)
            for k, l in ((1, 6), (3, 7), (5, 6), (7, 7)): add(s(k), l, c, "spark", .32)
        else:
            last = n == NCH - 1                                            # 最後の和音は、後ろ半分を休む（クジラの泡だけがのぼる）
            ml = tones(c).index(MEL[c]); add(e(0), 0, c, "bass", .75); add(e(0), ml, c, "mel", .88); add(e(1), 3, c, "arp", .48); add(s(3), 6, c, "spark", .32)
            if n >= 12: add(s(1), 5, c, "spark", .34)
            if not last:
                add(e(2), 1, c, "bass", .58); add(e(2), 4, c, "arp", .48); add(e(3), 5, c, "arp", .48); add(s(7), 7, c, "spark", .32)
                if n >= 12: add(s(5), 6, c, "spark", .32)
    xb, yb = blow_xy(TREL)                                                 # クジラの泡：同時に出る。大きい泡から先に着く
    for l in range(NL):
        m = tones(0)[l]; r = rad(m); v = speed(r); y0 = yb - 14.0
        N.append(dict(t=TREL + .08 + (y0 - (YS + r)) / v, l=l, m=m, r=r, v=v, kind="ring", vel=.82 - .04 * l, trel=TREL, xs=xb, off=(l - 3.5) * 46.0, y0=y0, ph=l * 1.1))
    return sorted(N, key=lambda q: q["t"])
def bubble_xy(q, t):
    """泡の位置と育ち具合。出口で 0.2 秒ほどふくらんでから離れ、同じ速さでのぼる。ゆれは大きい泡ほど大きい"""
    e = t - q["trel"]; k = q["r"] / 46.0; y = q["y0"] - q["v"] * max(0.0, e - .08)
    x = q["xs"] + q["off"] * (1 - .8 * math.exp(-max(0.0, e) / .30)) + 8 * k * math.sin(2 * math.pi * 1.2 * e + q["ph"]) * min(1.0, e / .6)
    return x, y, min(1.0, max(0.0, e) / .22) ** .7
NOTES = chart()
for _q in NOTES: _q["xa"] = bubble_xy(_q, _q["t"])[0]                      # はじける場所
TA = np.array([q["t"] for q in NOTES]); TLAST = float(TA[-1]); DUR = TLAST + 3.0; NF = int(DUR * FPS)
LT = [np.array([q["t"] for q in NOTES if q["l"] == l and q["kind"] != "ring"]) for l in range(NL)]
def chord_at(t): return min(NCH, max(0, int(math.floor((t - INTRO + 1e-6) / CH))))

# ---------- 絵：動かない部分 ----------
BY0 = 1420
def build_static():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); rng = np.random.default_rng(3)
    k = np.clip(yy / YS, 0, 1)[..., None]                                   # 空：夜明け前の濃い青。水平線のあたりが明るい
    sky = np.array([6, 12, 36], np.float32) * (1 - k) ** 1.4 + np.array([24, 58, 120], np.float32) * k ** 1.7 + np.array([10, 22, 60], np.float32) * 2 * k * (1 - k)
    sky += (np.exp(-(((xx - 540) / 430) ** 2 + ((yy - YS) / 140) ** 2)) * 78)[..., None] * np.array([.62, .92, 1.1], np.float32)
    stars = []                                                              # 星（3組をゆっくり明るさを入れかえる＝またたき）
    for _ in range(3):
        a = np.zeros((YS, W), np.float32)
        for _ in range(34):
            x, y = int(rng.uniform(8, W - 8)), int(rng.uniform(8, YS - 90)); b = rng.uniform(.25, 1.0) * (1 - y / YS) ** .6; a[y, x] += b; a[y - 1:y + 2, x - 1:x + 2] += b * .28
        stars.append(a)
    d = np.clip((yy - YS) / (YV + 60 - YS), 0, 1)[..., None]                # 海：水面の近くは明るい水色、深い所は紺
    sea = np.array([34, 142, 218], np.float32) * (1 - d) ** 2.2 + np.array([13, 76, 160], np.float32) * 2 * d * (1 - d) + np.array([4, 24, 68], np.float32) * d ** 1.3
    sea += (np.exp(-(((xx - 540) / 340) ** 2 + ((yy - YS) / 540) ** 2)) * 92)[..., None] * np.array([.52, .95, 1.0], np.float32)          # 光が入ってくる所
    sea += (np.exp(-(((xx - 540) / 190) ** 2 + ((yy - YS) / 210) ** 2)) * 40)[..., None] * np.array([.85, 1.0, 1.0], np.float32)
    sea *= (1 - .34 * np.clip(np.abs(xx - 540) / 540, 0, 1) ** 2.2)[..., None]                                                              # 左右はうす暗く
    for l in range(NL):                                                     # レーン：うすい光の筋（太さは泡の大きさに合わせる）
        sea += (np.exp(-((xx - LX[l]) / (1.6 + RL[l] * .03)) ** 2) * np.clip((yy - YS) / 60, 0, 1) * np.clip((YV - yy) / 260, 0, 1) * 13)[..., None]
    rays = []                                                               # 光のすじ（3組をゆっくり入れかえる）
    for _ in range(3):
        im = Image.new("L", (W // 4, H // 4), 0); dr = ImageDraw.Draw(im)
        for _ in range(8):
            x0 = rng.uniform(90, 990); w0 = rng.uniform(8, 40); dx = (x0 - 540) * rng.uniform(.45, .85) + rng.uniform(-50, 50); w1 = w0 * rng.uniform(2.0, 3.4); L_ = rng.uniform(620, 1080)
            dr.polygon([((x0 - w0) / 4, YS / 4), ((x0 + w0) / 4, YS / 4), ((x0 + dx + w1) / 4, (YS + L_) / 4), ((x0 + dx - w1) / 4, (YS + L_) / 4)], fill=int(rng.uniform(80, 175)))
        a = np.asarray(im.filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR), np.float32) / 255
        rays.append((a * np.clip(1 - (yy - YS) / 1240, 0, 1) ** 1.25 * (yy > YS))[YS:YV + 90].astype(np.float32))
    S = 2; bed = Image.new("RGBA", (W * S, (H - BY0) * S), (0, 0, 0, 0)); bd = ImageDraw.Draw(bed); P = lambda x, y: (x * S, (y - BY0) * S)
    def branch(x, y, ang, ln, wd, dep, col):                                # 枝サンゴ（先が丸い）
        x2, y2 = x + ln * math.cos(ang), y + ln * math.sin(ang); bd.line([P(x, y), P(x2, y2)], fill=col, width=int(max(1.5, wd) * S)); q = max(1.5, wd) * .62; bd.ellipse([P(x2 - q, y2 - q), P(x2 + q, y2 + q)], fill=col)
        if dep > 0:
            for da in (rng.uniform(-.72, -.28), rng.uniform(.28, .72)): branch(x2, y2, ang + da, ln * rng.uniform(.62, .80), wd * .74, dep - 1, col)
    FAR, NEAR = (9, 42, 98, 255), (4, 17, 46, 255)
    xs = list(range(-10, W + 20, 10))
    bd.polygon([P(-10, H)] + [P(x, YV + 40 + 20 * math.sin(x / 130 + .6) + 12 * math.sin(x / 57 + 2)) for x in xs] + [P(W + 10, H)], fill=FAR)          # 遠くの岩場（うすい色）
    for x in (212, 495, 730, 880): branch(x, YV + 48, -math.pi / 2 + rng.uniform(-.2, .2), rng.uniform(34, 52), 8, 3, FAR)
    gaps = [(LX[l] + RL[l] + LX[l + 1] - RL[l + 1]) / 2 for l in range(NL - 1)]
    for l in range(NL):                                                     # 泡の出口：筒の太さは、そのレーンの泡の大きさ（太い筒ほど低い音）
        x = LX[l]; hw = RL[l] * .80 + 5
        bd.polygon([P(x - hw * 1.2, YV + 104), P(x - hw, YV), P(x + hw, YV), P(x + hw * 1.2, YV + 104)], fill=(7, 27, 66, 255))
        bd.ellipse([P(x - hw, YV - hw * .24), P(x + hw, YV + hw * .24)], fill=(22, 70, 132, 255)); bd.ellipse([P(x - hw * .80, YV - hw * .15), P(x + hw * .80, YV + hw * .17)], fill=(2, 9, 26, 255))
    bd.polygon([P(-10, H)] + [P(x, YV + 82 + 14 * math.sin(x / 97.0) + 9 * math.sin(x / 41.0 + 1.3) + 5 * math.sin(x / 17.0)) for x in xs] + [P(W + 10, H)], fill=NEAR)   # 手前の海の底
    for x, hgt, wd in ((8, 96, 17), (gaps[1], 50, 11), (gaps[4], 44, 10), (1052, 104, 18), (992, 60, 12)): branch(x, YV + 92, -math.pi / 2 + rng.uniform(-.18, .18), hgt, wd, 4, NEAR)
    for x in (gaps[2], gaps[5]): bd.ellipse([P(x - 30, YV + 60), P(x + 30, YV + 128)], fill=NEAR)                                                                   # 岩
    bed = np.asarray(bed.resize((W, H - BY0), Image.LANCZOS), np.float32) / 255
    return (sky / 255).astype(np.float32), stars, (np.clip(sea, 0, 255) / 255).astype(np.float32), rays, bed, gaps
SKY, STARS, SEA, RAYS, BED, GAPS = build_static()
BASE = np.where((np.arange(H) >= YS)[:, None, None], SEA, SKY).astype(np.float32); YYB = np.arange(YS - 40, YS + 40, dtype=np.float32)[:, None]
_yy, _xx = np.mgrid[0:440, -14:15].astype(np.float32); GL = (np.exp(-(_xx / 4.5) ** 2) * np.exp(-_yy / 150) * np.clip(_yy / 14, 0, 1)).astype(np.float32); GS = T.glow(20)
YSH = np.exp(-np.arange(0, 90, dtype=np.float32) / 26)[:, None]             # 水面のすぐ下の明るい帯
KELP = [(GAPS[0], 230, 0.0), (GAPS[3], 170, 1.9), (GAPS[5], 200, 3.7), (24, 250, 5.1), (1034, 280, 2.6), (1066, 190, 4.4)]

_BS = {}
def bsprite(r, kind=0, ss=3):
    """泡：中はほとんど透明で、ふちが明るい。光は左上から。kind 0＝ふつう、1＝金色（旋律）、2＝クジラの泡（白い）"""
    key = (int(round(r)), kind)
    if key in _BS: return _BS[key]
    r = max(2.0, float(key[0])); R = r * ss; n = int(2 * R + 10 * ss); c = (np.arange(n, dtype=np.float32) + .5 - n / 2) / R; X, Y = np.meshgrid(c, c); d = np.hypot(X, Y)
    a = np.clip((1 - d) * R + .5, 0, 1); face = (-.5 * X - .86 * Y) / np.maximum(d, 1e-3); ang = np.arctan2(Y, X)
    rim = np.exp(-((d - .93) / .055) ** 2) * (.42 + .58 * (face * .5 + .5)); fill = .04 + .10 * d ** 2; dark = np.exp(-((d - .79) / .09) ** 2) * .16
    spec = np.exp(-((X + .36) ** 2 + (Y + .45) ** 2) / .024); core = np.exp(-((X + .40) ** 2 + (Y + .50) ** 2) / .0036)
    cres = np.exp(-((d - .66) / .05) ** 2) * np.exp(-((ang - .9) / .55) ** 2) * .40                                                 # 右下の映りこみ
    col = np.array([(.70, .90, 1.0), (1.0, .86, .58), (.93, .97, 1.0)][kind], np.float32); g = 1.12 if kind else 1.0
    rgb = (col * ((rim * g + fill * .55)[..., None]) + (spec * .50 + core * .90 + cres * .55)[..., None]) * a[..., None]
    al = a * np.clip(fill * .5 + rim * .28 + dark + spec * .35, 0, .9)
    o = np.dstack([rgb, al]).astype(np.float32); k = n // ss; o = o[:k * ss, :k * ss].reshape(k, ss, k, ss, 4).mean((1, 3)); _BS[key] = o; return o
def put(buf, sp, x, y, al=1.0):                                            # 前もって濃さを掛けた絵を重ねる
    h, w = sp.shape[:2]; x0, y0 = int(round(x - w / 2)), int(round(y - h / 2)); xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb <= xa or yb <= ya: return
    s = sp[ya - y0:yb - y0, xa - x0:xb - x0] * al; reg = buf[ya:yb, xa:xb]; reg[:] = reg * (1 - s[..., 3:4]) + s[..., :3]

# ---------- クジラ（横から見た影。背中に上からの光。体の後ろ半分がゆっくり上下にしなる） ----------
TOPE = [(0, .02), (.03, -.035), (.10, -.065), (.22, -.085), (.40, -.095), (.55, -.09), (.585, -.092), (.615, -.114), (.645, -.088), (.70, -.07), (.80, -.045), (.92, -.022), (1.0, -.014)]
BOTE = [(0, .02), (.04, .048), (.12, .088), (.25, .107), (.40, .10), (.55, .08), (.70, .052), (.85, .028), (.95, .016), (1.0, .012)]
FIN = [(.24, .07), (.30, .17), (.38, .27), (.44, .31), (.455, .285), (.41, .20), (.36, .12), (.33, .075)]
FLUKE = [(0, -.012), (.03, -.075), (.075, -.115), (.07, -.07), (.055, -.02), (.062, 0), (.055, .02), (.07, .06), (.075, .10), (.03, .065), (0, .012)]
def whale(buf, t):
    xw, yw = whale_xy(t); ox, oy = xw - WL * .5, yw; x0, y0 = int(ox - 70), int(oy - WL * .30); pw, ph_ = int(WL * 1.2 + 140), int(WL * .72)
    if x0 >= W or x0 + pw <= 0: return
    def bend(u): return .10 * max(0.0, u - .45) ** 2 * math.sin(2 * math.pi * (t / 3.2 - u * .6))
    us = np.linspace(0, 1, 48); te = np.interp(us, [p[0] for p in TOPE], [p[1] for p in TOPE]); be = np.interp(us, [p[0] for p in BOTE], [p[1] for p in BOTE]); bn = np.array([bend(u) for u in us])
    S = 2; P = lambda u, v: ((ox + u * WL - x0) * S, (oy + v * WL - y0) * S)
    im = Image.new("L", (pw * S, ph_ * S), 0); dr = ImageDraw.Draw(im)
    dr.polygon([P(u, te[i] + bn[i]) for i, u in enumerate(us)] + [P(u, be[i] + bn[i]) for i, u in reversed(list(enumerate(us)))], fill=255)
    fa = math.radians(9) * math.sin(2 * math.pi * t / 5.0); rx, ry = .28, .07; ca, sa = math.cos(fa), math.sin(fa)                       # 胸びれ：ゆっくり動く
    dr.polygon([P(rx + (u - rx) * ca - (v - ry) * sa, ry + (u - rx) * sa + (v - ry) * ca) for u, v in FIN], fill=255)
    sl = (bend(1.0) - bend(.97)) / .03; ta = math.atan(sl) * 1.6; ca, sa = math.cos(ta), math.sin(ta); k = .78 + .22 * abs(math.cos(2 * math.pi * (t / 3.2 - .6)))   # 尾びれ：体のしなりに合わせて向きが変わる
    dr.polygon([P(1.0 + u * ca - v * k * sa, bend(1.0) + u * sa + v * k * ca) for u, v in FLUKE], fill=255)
    gr = Image.new("L", (pw * S, ph_ * S), 0); dg = ImageDraw.Draw(gr)                                                                    # のどのひだ（下あごから腹へ、細いすじ）
    for f in (.30, .46, .62, .78, .92): dg.line([P(u, .02 + (be[i] - .02) * f + bn[i]) for i, u in enumerate(us) if .03 <= u <= .46 - .10 * (1 - f)], fill=255, width=int(1.6 * S))
    mo = Image.new("L", (pw * S, ph_ * S), 0); dm = ImageDraw.Draw(mo)                                                                    # 口の線と目
    dm.line([P(u, .020 + .030 * (u / .21) ** 1.7) for u in np.linspace(.004, .21, 12)], fill=255, width=int(2.2 * S)); ex, ey = P(.228, .040); dm.ellipse([ex - 3.2 * S, ey - 3.2 * S, ex + 3.2 * S, ey + 3.2 * S], fill=255)
    mo = np.asarray(mo.filter(ImageFilter.GaussianBlur(.7 * S)).resize((pw, ph_), Image.BILINEAR), np.float32) / 255
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(1.5 * S)).resize((pw, ph_), Image.BILINEAR), np.float32) / 255
    g = np.asarray(gr.filter(ImageFilter.GaussianBlur(.8 * S)).resize((pw, ph_), Image.BILINEAR), np.float32) / 255
    thin = np.zeros_like(a); thin[5:] = a[:-5]; thin = np.clip(a - thin, 0, 1)                                                           # 背中のふち（上から5pxまで）
    broad = np.zeros_like(a); broad[44:] = a[:-44]; broad = cv2.GaussianBlur(np.clip(a - broad, 0, 1), (0, 0), 12) * a                    # 背中の広い明るさ
    X = (np.arange(pw, dtype=np.float32) + x0)[None, :]; caus = 1 + .42 * np.sin(X / 19 + 2.1 * t) * np.sin(X / 33 - 1.3 * t + 1.2)       # 背中でゆれる光の網
    col = np.array([.020, .086, .215], np.float32) + (broad * caus)[..., None] * np.array([.050, .150, .205], np.float32) + thin[..., None] * np.array([.085, .21, .27], np.float32) + (g * a)[..., None] * np.array([.012, .032, .048], np.float32)
    col = col * (1 - .55 * mo[..., None])
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + pw), min(H, y0 + ph_)
    if xb <= xa or yb <= ya: return
    s = (a * .90)[ya - y0:yb - y0, xa - x0:xb - x0, None]; reg = buf[ya:yb, xa:xb]; reg[:] = reg * (1 - s) + col[ya - y0:yb - y0, xa - x0:xb - x0] * s

FISH = [(dx, dy, ph, sc) for dx, dy, ph, sc in zip(*[np.random.default_rng(12).uniform(a, b, 13) for a, b in ((-190, 190), (-70, 70), (0, 6.28), (.75, 1.25))])]
def fish(buf, t):
    """遠くを横切る小さな魚の群れ（クジラとは逆向き）"""
    cx = -230 + 50 * t; cy = 880 + 26 * math.sin(t / 3.1); x0, y0 = int(cx - 240), int(cy - 110); pw, ph_ = 480, 220
    if x0 >= W or x0 + pw <= 0: return
    S = 2; im = Image.new("L", (pw * S, ph_ * S), 0); dr = ImageDraw.Draw(im)
    for dx, dy, ph, sc in FISH:
        x = (cx + dx + 7 * math.sin(t * .9 + ph) - x0) * S; y = (cy + dy + 5 * math.sin(t * 1.3 + ph * 2) - y0) * S; L_ = 15 * sc * S; hh = 5.2 * sc * S; wag = 3.2 * sc * S * math.sin(9 * t + ph)
        dr.ellipse([x - L_, y - hh, x + L_, y + hh], fill=255); dr.polygon([(x - L_ * .8, y), (x - L_ * 1.75, y - hh * 1.3 + wag), (x - L_ * 1.75, y + hh * 1.3 + wag)], fill=255)
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(S)).resize((pw, ph_), Image.BILINEAR), np.float32) / 255 * .46
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + pw), min(H, y0 + ph_)
    if xb <= xa or yb <= ya: return
    s = a[ya - y0:yb - y0, xa - x0:xb - x0, None]; reg = buf[ya:yb, xa:xb]; reg[:] = reg * (1 - s) + np.array([.030, .17, .40], np.float32) * s

# ---------- 水面の波（1次元の波の式。泡がはじけた所から左右に伝わって消える） ----------
class Surface:
    def __init__(s): s.n = W // 4 + 1; s.h = np.zeros(s.n); s.v = np.zeros(s.n); s.fi = -1; s.k = 0
    def step_to(s, fi):
        if fi < s.fi: s.__init__()
        while s.fi < fi:
            s.fi += 1; t = s.fi / FPS
            while s.k < len(NOTES) and NOTES[s.k]["t"] <= t:
                q = NOTES[s.k]; xs = np.arange(s.n) * 4.0; s.v += -(60 + q["r"] * 5.0) * np.exp(-((xs - q["xa"]) / (9 + q["r"] * .45)) ** 2); s.k += 1
            for _ in range(4):
                dt = 1 / (FPS * 4); lap = np.zeros(s.n); lap[1:-1] = s.h[2:] - 2 * s.h[1:-1] + s.h[:-2]
                s.v += (420.0 ** 2 * lap / 16.0 - 3.0 * s.v - 5.0 * s.h) * dt; s.h += s.v * dt
    def y(s, t):
        x = np.arange(W, dtype=np.float32); return (YS + 3 * np.sin(2 * math.pi * (x / 420 - t / 3.1)) + 2 * np.sin(2 * math.pi * (x / 190 + t / 2.3)) + np.interp(x, np.arange(s.n) * 4.0, s.h)).astype(np.float32)
SURF = Surface()
SNOW = np.random.default_rng(9).uniform(0, 1, (110, 4))                   # 水の中のこまかい粒
XF = np.arange(W, dtype=np.float32)

INK = (244, 248, 255, 255); GOLD = (255, 222, 150, 255); SOFT = (214, 232, 250, 255)
def make_frame(fi):
    t = fi / FPS; SURF.step_to(fi); ys = SURF.y(t); buf = BASE.copy()
    w = [.5 + .5 * math.sin(2 * math.pi * t / p + q) for p, q in ((9, 0), (7, 2.1), (11, 4.0))]                                          # 星のまたたき
    buf[:YS] += (STARS[0] * w[0] + STARS[1] * w[1] + STARS[2] * w[2])[..., None] * np.array([.80, .90, 1.0], np.float32)
    m = np.clip(YYB - ys[None, :] + .5, 0, 1)[..., None]; buf[YS - 40:YS + 40] = buf[YS - 40:YS + 40] * (1 - m) + SEA[YS - 40:YS + 40] * m    # 波うつ水面で、空と海を分ける
    w = [.55 + .45 * math.sin(2 * math.pi * t / p + q) for p, q in ((11, 0), (8, 2.1), (14, 4.0))]
    buf[YS:YV + 90] += (RAYS[0] * w[0] + RAYS[1] * w[1] + RAYS[2] * w[2])[..., None] * np.array([.12, .24, .26], np.float32)                  # 光のすじ
    sh = .5 + .5 * np.sin(XF / 37 + 1.9 * t) * np.sin(XF / 61 - 1.2 * t + .7) + .35 * np.sin(XF / 13 - 2.6 * t)                            # 水面の裏のきらめき
    buf[YS + 8:YS + 98] += (YSH * np.clip(sh, 0, 1.4)[None, :])[..., None] * np.array([.05, .10, .11], np.float32)
    fish(buf, t); whale(buf, t)
    reg = buf[BY0:]; reg[:] = reg * (1 - BED[..., 3:4]) + BED[..., :3] * BED[..., 3:4]
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for x0, hgt, ph in KELP:                                                # 海草：根もとは動かず、先ほど大きくゆれる
        pts = [(x0 + 15 * (s / 12) ** 1.6 * math.sin(1.25 * t + ph - 2.4 * s / 12), YV + 104 - hgt * s / 12) for s in range(13)]
        for s in range(12): d.line([pts[s], pts[s + 1]], fill=(5, 24, 58, 255), width=int(round(11 - 7 * s / 12)))
        for s in range(2, 12, 2): sd = 1 if (s // 2) % 2 else -1; d.line([pts[s], (pts[s][0] + sd * (20 - s), pts[s][1] - 18)], fill=(5, 24, 58, 255), width=5)
    for sn in SNOW:                                                         # 粒：ゆっくり流れる
        x = (sn[0] * W + 12 * math.sin(t * .5 + sn[2] * 6.3)) % W; y = YS + 30 + ((sn[1] * 1130 - t * (6 + 10 * sn[3])) % 1130); d.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(200, 230, 255, int(36 + 60 * sn[3])))
    npop = int(np.searchsorted(TA, t, "right"))
    for q in NOTES:                                                         # のぼっている泡
        if q["trel"] > t or q["t"] <= t: continue
        x, y, grow = bubble_xy(q, t); r = q["r"]; k = r / 46.0; e = t - q["trel"]; asp = 1 + (.085 * k + .055 * k * math.sin(2 * math.pi * 2.6 * e + q["ph"] * 1.7)) * grow
        sp = bsprite(max(2.0, r * grow), {"mel": 1, "ring": 2}.get(q["kind"], 0)); hh, ww = sp.shape[:2]
        put(buf, cv2.resize(sp, (max(2, int(round(ww * asp))), max(2, int(round(hh / asp)))), interpolation=cv2.INTER_LINEAR), x, y)
    for q in NOTES[max(0, npop - 48):npop]:                                 # はじけた瞬間：水面の光、レーンの光、水の中へ広がる音の輪、しぶき
        e = t - q["t"]
        if e > .9: continue
        x = q["xa"]; r = q["r"]; yq = float(ys[int(min(W - 1, max(0, x)))]); kind = q["kind"]; c = (255, 226, 170) if kind == "mel" else (200, 240, 255)
        if e < .5:
            T.add_glow(buf, GS, x, yq, c, (.55 + .35 * r / R0) * math.exp(-e / .07))
            if kind != "ring": T.add_glow(buf, GL, LX[q["l"]], yq + 220, c, (.34 + .30 * r / R0) * math.exp(-e / .16))
        if e < .6:
            rr = r * .9 + (300 + 4 * r) * e ** .8; al = int((120 + 60 * r / R0) * (1 - e / .6) ** 1.8)
            if al > 3: d.arc([x - rr, yq - rr, x + rr, yq + rr], 8, 172, fill=c + (al,), width=2 if r < 30 else 3)
        rng = np.random.default_rng(int(q["t"] * 1000) + q["l"] * 7)
        for _ in range(4 + int(r / 14)):                                    # しぶき（水面の上へとんで、落ちる）
            vx, vy = rng.uniform(-80, 80), rng.uniform(-330, -150) * (.55 + .45 * r / R0); px, py = x + vx * e, yq + vy * e + 500 * e * e; sz = rng.uniform(1.6, 2.4 + r / 40)
            if py < yq - 1 and e < .8: d.ellipse([px - sz, py - sz, px + sz, py + sz], fill=(226, 246, 255, int(235 * (1 - e / .8))))
    pts = [(x, float(ys[x])) for x in range(0, W, 6)] + [(W - 1, float(ys[-1]))]                                                            # 水面の線（判定の線）
    d.line(pts, fill=(170, 226, 255, 64), width=7); d.line(pts, fill=(226, 246, 255, 235), width=3)
    c = chord_at(t); fin = c >= NCH; cc = 0 if fin else c % 8; tn = tones(cc)
    for l in range(NL):                                                     # レーンの受け皿（幅＝そのレーンの泡の大きさ）と、音の名前。はじけた瞬間に光る
        x = LX[l]; rr = rad(tn[l]) * .92; k = int(np.searchsorted(LT[l], t, "right")); fl = math.exp(-(t - LT[l][k - 1]) / .16) if k else 0.0
        seg = [(xx_, float(ys[int(min(W - 1, max(0, xx_)))])) for xx_ in np.linspace(x - rr, x + rr, 7)]
        d.line(seg, fill=(255, 255, 255, int(205 + 50 * fl)), width=int(round(6 + 4 * fl)), joint="curve")
        for ex in (seg[0], seg[-1]): d.ellipse([ex[0] - 3.5, ex[1] - 3.5, ex[0] + 3.5, ex[1] + 3.5], fill=(255, 255, 255, 230))
        f = T.fnt(int(round(30 + 8 * fl))); d.text((x, YS - 50 - 3 * fl), NOTE[tn[l] % 12], font=f, fill=(int(190 + 65 * fl), int(214 + 34 * fl), int(240 - 60 * fl), int(170 + 85 * fl)), anchor="mm")
    for q in NOTES[max(0, npop - 8):npop]:                                  # クジラの泡は、はじけた場所に音の名前が出る
        e = t - q["t"]
        if q["kind"] == "ring" and e < 1.1: d.text((q["xa"], YS - 94 - 12 * e), NOTE[q["m"] % 12], font=T.fnt(32), fill=(255, 236, 190, int(255 * min(1, (1.1 - e) / .5))), anchor="mm")
    T.fit_text(d, (W / 2, 140), T.tr("泡は、大きいほど低い音がする", "Bigger bubbles make lower sounds"), 56, 990, INK)
    T.fit_text(d, (W / 2, 214), T.tr("最後に、クジラが和音を鳴らす", "At the end, the whale plays a chord"), 48, 990, GOLD)
    for k in range(8):                                                      # 和音の進み（カノン進行の8つ）
        x0 = 96 + k * 112; on = t >= INTRO and ((not fin and cc == k) or (fin and k == 0)); done = t >= INTRO and (c >= 8 or k < cc)
        d.rounded_rectangle([x0, 268, x0 + 104, 314], radius=12, fill=(255, 220, 140, 240) if on else (70, 124, 188, 165 if done else 80))
        d.text((x0 + 52, 290), CHN[k], font=T.fnt(28), fill=(20, 40, 80, 255) if on else (220, 236, 252, 235 if done else 150), anchor="mm")
    cap = 0.0
    for (ta, tb, s_) in CAPS:
        if ta <= t < tb:
            cap = min(1, (t - ta) / .5) * min(1, (tb - t) / .5)                # 数が消えてから字幕が出る（重ねない）
            if cap > .5: T.fit_text(d, (W / 2, 372), s_, 38, 990, (255, 236, 190, int(255 * (2 * cap - 1))), bold=False)
    if cap < .5: d.text((W / 2, 372), T.tr(f"はじけた泡 {npop}", f"Bubbles popped: {npop}"), font=T.fnt(38), fill=SOFT[:3] + (int(255 * (1 - 2 * cap)),), anchor="mm")
    out = np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB"))
    g = min(T.sstep(0, .35, t), 1 - T.sstep(DUR - .6, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)
CAPS = [(INTRO + 4 * CH - .2, INTRO + 6 * CH - .1, T.tr("小さい泡は遅いので、先に出る", "Small bubbles rise slower, so they leave first")),
        (INTRO + 8 * CH - .2, INTRO + 10 * CH - .1, T.tr("2周め：金色の泡が旋律", "Round two: the golden bubbles are the melody")),
        (TREL - .2, TF + .25, T.tr("クジラの泡：同時に出て、大きい泡から着く", "The whale's bubbles leave together. Big ones land first")),
        (TLAST + .5, DUR, T.tr(f"{len(NOTES)}個の泡で、カノン進行でした", f"{len(NOTES)} bubbles played the Canon progression"))]

def drop_layer(N):
    """泡そのものが鳴る音（水滴の「ぽちゃん」の正体）。泡は大きさで決まる高さで短く鳴り、鳴りながら少し上がる（ミンナルトの共鳴。van den Doel 2005 の式）
       ガラスの響きの出だしに、同じ高さ・同じ瞬間で小さく重ねる（1つの出来事に1つの音のまま）"""
    out = np.zeros(N, np.float32)
    for q in NOTES:
        f = K.mtof(q["m"]); dmp = .043 * f + .0014 * f ** 1.5; n = int(T.SR * min(.4, 8 / dmp)); tt = np.arange(n) / T.SR; vel = q["vel"]
        x = np.sin(2 * math.pi * f * (1 + .1 * dmp * tt) * tt) * np.exp(-dmp * tt) * np.minimum(1, tt / .0012)
        a = int(q["t"] * T.SR); k = min(n, N - a)
        if k > 0: out[a:a + k] += (x[:k] * .42 * .9 * (f / 700) ** -.28 * (.70 + .30 * vel) * vel * .707).astype(np.float32)
    return out
def audio(path):
    a = T.Audio(DUR, mat="glass", max_same=4, window=.012)
    for q in NOTES: a.note(q["t"], q["m"], vel=q["vel"], pan=.15 + .7 * (q["xa"] - 50) / 900)
    N = int(T.SR * DUR); under = drop_layer(N); body = K.pad([(r, r + 12, f5 + 12) for (r, t3, f5) in K.CANON], CH, NCH * CH + 4.5, .05); off = int(T.SR * INTRO); k = min(len(body), N - off)
    under[off:off + k] += body[:k]; under *= np.clip((DUR - np.arange(N) / T.SR) / 1.5, 0, 1).astype(np.float32)
    return a.write(path, room=(.32, 3.2), under=under)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_bubblesea", exist_ok=True)
    print("長さ", round(DUR, 1), "泡", len(NOTES), "クジラが泡をはく", round(TREL, 2), "1つめが着く", round(TF, 2), "最後", round(TLAST, 2), "レーン", [round(x) for x in LX], "泡の半径", [round(r) for r in RL])
    if cmd == "stills": print(T.stills(NF, make_frame, "build_bubblesea/s", at=(.012, .3, .62, (TREL + .55) / DUR, (TLAST + .8) / DUR))); sys.exit()
    if cmd == "zoom":                                                      # 近くで見る：泡、はじけた瞬間、クジラ
        for name, tt_, box in (("pop", INTRO + 13 * CH + .03, (0, 380, 1080, 1000)), ("whale", TREL + .3, (200, 880, 1080, 1480)), ("bed", 12.0, (0, 1300, 1080, 1920)), ("end", TLAST + 1.2, (0, 0, 1080, 700))):
            Image.fromarray(make_frame(int(tt_ * FPS))).crop(box).save(f"build_bubblesea/z_{name}.png")
        sys.exit()
    if cmd == "audio": print(audio("build_bubblesea/a.wav")); sys.exit()
    out = f"output/bubblesea1_{T.LANG}.mp4"; audio("build_bubblesea/a.wav"); T.encode(NF, make_frame, "build_bubblesea/a.wav", out); print(out)
