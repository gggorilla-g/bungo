# mergecol.py — 同じ星が2つ重なると、1つ大きい星になる。月を落とし続けると、太陽になる（オーナー 11/25 の画面収録の型「これは作って」）
#   しくみ：月が上から1個ずつ落ちる。同じ星が2つ重なると合体して1つ大きい星になる（月→水星→火星→…→木星→太陽）。
#           列に残っている星は、落とした数を2進数で書いたものと同じ（上の列の明かり）。512個めで全部が1つになる。
#   音：オーナー「カノンは意識してね」。合体のたびに石の音が1音。1つの和音の間に1回合体する星がパッヘルベルのカノンの旋律、
#       2回の星が次の変奏、4回・8回の星が分散和音、めったに合体しない大きい星が低音（カノンの低音の進行）。
#       落とす速さは1小節ごとに2倍（4分→8分→16分→…）＝リズムが変わっていく。音は合体の瞬間にだけ鳴る。
#   python3 tools/mergecol.py [out.mp4]     STILLS=1,5,9 で確認用の絵だけ（build_mergecol/s_*.jpg）、LANG_OUT=en で英語
import math, os, sys, subprocess, wave
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from scipy.signal import fftconvolve, resample_poly, butter, sosfilt

W, H, FPS, SR = 1080, 1920, 60, 48000
LANG = os.environ.get("LANG_OUT", "ja"); EN = LANG == "en"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"output/mergecol1_{LANG}.mp4"
MAT = os.environ.get("MAT", "")          # 234 の材質（wood・bamboo・hollow）。空なら前の石の音。mergecol2_en（11/28 持ち主「英語版にマイナーチェンジして、音は新しく234に」）は wood
VAR2 = os.environ.get("VAR") == "2"      # マイナーチェンジ版（背景の色みと題名の言い回しを変える）
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"; FI = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"; FIM = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
def fnt(sz, latin=False): return ImageFont.truetype(FI if (latin or EN) else FJ, sz)

# ---------- 星 ----------
NAMES = ["Moon", "Mercury", "Mars", "Venus", "Earth", "Neptune", "Uranus", "Saturn", "Jupiter", "Sun"] if EN else ["月", "水星", "火星", "金星", "地球", "海王星", "天王星", "土星", "木星", "太陽"]
NT = 10
RAD = [20.0 * 1.19 ** k for k in range(9)] + [124.0]          # 列の中の半径（px）
GLOW = [(210, 214, 226), (214, 190, 164), (240, 130, 90), (246, 222, 160), (110, 170, 255), (110, 140, 255), (170, 232, 240), (240, 214, 160), (240, 190, 140), (255, 206, 96)]
TILT = [.2, -.3, .35, .15, .41, .45, 1.35, .32, .08, 0.0]
LX, LY, LZ = (lambda v: v / np.linalg.norm(v))(np.array([-.48, -.58, .66]))

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
    if k == 0:   # 月：明るい灰色に暗い海
        c = mixc((204, 204, 210), (134, 136, 150), sstep(.05, .5, snoise(P, 11, (1.1, 2.3, 4.6)))); return c * (1 + .05 * snoise(P, 12, (7., 13.), (1, .6)))[..., None]
    if k == 1:   # 水星
        c = mixc((180, 158, 136), (126, 108, 94), sstep(-.2, .7, snoise(P, 21)) * .7); return c * (1 + .06 * snoise(P, 22, (8., 15.), (1, .6)))[..., None]
    if k == 2:   # 火星：赤さび色、暗い模様、白い極
        c = mixc((212, 104, 64), (148, 70, 52), sstep(.0, .55, snoise(P, 31))); return mixc(c, (242, 238, 234), sstep(.86, .93, -v))
    if k == 3:   # 金星：うすい黄色の雲の流れ
        return mixc((230, 198, 136), (250, 232, 190), .5 + .5 * np.sin(lat * 7 + 1.6 * snoise(P, 41, (1.2, 2.4))))
    if k == 4:   # 地球：海・陸・雲・極
        c = mixc((40, 92, 196), (62, 124, 220), .5 + .5 * snoise(P, 51, (2., 4.)))
        land = sstep(.10, .20, snoise(P, 52, (1.4, 2.9, 5.8))); c = mixc(c, mixc((60, 142, 80), (164, 144, 96), sstep(.0, .6, snoise(P, 53, (2.5, 5.)))), land)
        c = mixc(c, (246, 248, 252), sstep(.88, .95, np.abs(v))); return mixc(c, (250, 250, 252), sstep(.36, .62, snoise(P, 54, (1.8, 3.7, 7.4))) * .82)
    if k == 5:   # 海王星
        return mixc((60, 96, 224), (42, 68, 182), sstep(.3, 1, np.sin(lat * 6 + .6)) * .55)
    if k == 6:   # 天王星
        return mixc((154, 218, 228), (128, 198, 214), sstep(.2, 1, np.sin(lat * 4 + .3)) * .6)
    if k == 7:   # 土星
        return mixc((230, 202, 148), (194, 164, 114), sstep(-.2, 1, np.sin(lat * 10 + .4) + .5 * np.sin(lat * 23)) * .62)
    if k == 8:   # 木星：しま模様と赤い斑点
        s = np.sin(lat * 12 + .9 * snoise(P, 71, (2., 4.), (1, .5))); c = mixc((238, 216, 184), (176, 120, 84), sstep(-.3, .5, s)); c = mixc(c, (214, 172, 132), sstep(.5, 1, np.sin(lat * 27 + 1)) * .4)
        return mixc(c, (198, 82, 54), 1 - sstep(.75, 1.05, np.hypot((P[..., 0] - .30) / .22, (v - .30) / .115)))
    m = snoise(P, 91, (3., 6., 12.), (1, .7, .45))                 # 太陽：自分で光る
    return mixc(mixc((255, 196, 70), (255, 238, 156), sstep(.15, .8, m)), (244, 146, 36), sstep(.2, .9, -m) * .7)

_SPR = {}
def sprite(k, Rp, ss=3):
    """前もって不透明度を掛けた RGBA（float32）。中心は配列のまん中"""
    key = (k, float(round(Rp)) if Rp > 60 else round(Rp * 2) / 2)
    if key in _SPR: return _SPR[key]
    Rp = key[1]; ring, sun = k == 7, k == 9; ss = 2 if Rp > 60 else ss
    half = int(math.ceil(Rp * (1.95 if ring else (1.40 if sun else 1.06)))) + 2; S = 2 * half; n = S * ss
    c = (np.arange(n, dtype=np.float32) + .5) / ss - half; xx, yy = np.meshgrid(c, c)
    rr = np.hypot(xx, yy) / Rp; nx, ny = xx / Rp, yy / Rp; nz = np.sqrt(np.clip(1 - rr * rr, 0, 1))
    ca, sa = math.cos(TILT[k]), math.sin(TILT[k]); u = nx * ca + ny * sa; v = -nx * sa + ny * ca
    P = np.stack([u, v, nz], -1).astype(np.float32); col = tex(k, np.arcsin(np.clip(v, -1, 1)), u, v, P)
    if sun: rgb = col * (.74 + .26 * nz ** .55)[..., None]
    else: rgb = col * ((.30 + .82 * np.clip(nx * LX + ny * LY + nz * LZ, 0, 1) ** .9) * (.80 + .20 * nz ** .4))[..., None]
    al = np.clip((1 - rr) * Rp * ss + .5, 0, 1); o = np.zeros((n, n, 4), np.float32); o[..., :3] = np.clip(rgb, 0, 255) / 255 * al[..., None]; o[..., 3] = al
    if ring:   # 土星の輪：奥の半分は星のうしろ、手前の半分は星の前
        cp, sp_ = math.cos(-.30), math.sin(-.30); xr = xx * cp + yy * sp_; yr = -xx * sp_ + yy * cp; q = np.hypot(xr / Rp, yr / (Rp * .30))
        m = sstep(1.26, 1.31, q) * (1 - sstep(1.80, 1.86, q)); m *= 1 - .8 * sstep(1.580, 1.60, q) * (1 - sstep(1.635, 1.655, q))
        rc = np.asarray((222, 202, 160), np.float32)[None, None] / 255 * (.74 + .26 * np.sin(q * 21))[..., None]; ra = (m * .84)[..., None]
        back, front = (yr <= 0)[..., None], (yr > 0)[..., None]
        o[..., :3] += rc * ra * back * (1 - o[..., 3:4]); o[..., 3:4] += ra * back * (1 - o[..., 3:4])
        o[..., :3] = o[..., :3] * (1 - ra * front) + rc * ra * front; o[..., 3:4] = o[..., 3:4] * (1 - ra * front) + ra * front
    if sun:    # やわらかい光のふち（足し算。光らせすぎない）
        hl = np.exp(-(np.clip(rr - 1, 0, None) / .15) ** 1.25) * .50 * (rr > 1); o[..., :3] += hl[..., None] * np.asarray((255, 176, 70), np.float32) / 255
    o = o.reshape(S, ss, S, ss, 4).mean((1, 3)); _SPR[key] = o; return o
def to_pil(s):   # 前掛けの float → ふつうの RGBA 画像（上の列の小さい絵用）
    a = np.clip(s[..., 3:4], 1e-4, 1); return Image.fromarray((np.clip(np.concatenate([s[..., :3] / a, s[..., 3:4]], -1), 0, 1) * 255).astype(np.uint8), "RGBA")

# ---------- 時間割（カノンの和音1つ＝2拍。t=0 は最初の合体） ----------
BPM = 112.0; BEAT = 60 / BPM; SLOT = 2 * BEAT; NDROP = 512
T = {1: -BEAT}; DI = {1: BEAT}
for n in range(2, 9): T[n] = (n - 2) * BEAT; DI[n] = BEAT             # はじめは4分（1拍に1個）
n0, t0, di = 8, T[8], BEAT / 2
while n0 < 512:                                                      # 数が2倍になるたびに、落とす速さも2倍（1小節ぶん）
    for n in range(n0 + 1, 2 * n0 + 1): T[n] = t0 + (n - n0) * di; DI[n] = di
    t0 = T[2 * n0]; n0 *= 2; di /= 2
TSUN = 17 * SLOT                                                      # 太陽ができる時刻（和音が D に戻る頭）
FIN = [.09, .10, .11, .12, .13, .15, .17, .20, .25]                   # 最後の1個：上から下へ、だんだんゆっくり合体していく
T[512] = TSUN - sum(FIN); DI[512] = BEAT
T511 = T[511]; TEND = TSUN + 3.3
def v2(n):
    v = 0
    while n % 2 == 0: n //= 2; v += 1
    return v
def dm(n, j): return FIN[j - 1] if n == 512 else min(BEAT / 8, .3 * (2 ** j) * DI[n])   # 合体にかかる時間（速い星ほど短い）

# ---------- 出来事：落ちる・合体する ----------
ents = []      # [段, 生まれた時刻, 消える時刻, 沈む相手（上の星が下の同じ星に沈んでいく）]
merges = []    # (時刻, できた段, 何個め, その段の初めてか, 1つの和音の間に何回合体する段か)
cur = [None] * NT; seen = set()
for n in range(1, NDROP + 1):
    ents.append([0, T[n], 1e9, None]); casc = len(ents) - 1; tm = T[n]
    for j in range(1, v2(n) + 1):
        tm += dm(n, j); old = cur[j - 1]; ents[old][2] = tm; ents[casc][2] = tm; ents[casc][3] = old; cur[j - 1] = None
        ents.append([j, tm, 1e9, None]); casc = len(ents) - 1
        merges.append((tm, j, n, j not in seen, SLOT / ((2 ** j) * DI[n]))); seen.add(j)
    cur[v2(n)] = casc
EB = np.array([e[1] for e in ents]); order = np.argsort(EB, kind="stable")

# ---------- 置き場所 ----------
CX, YB, YNOZ, HW = 540, 1420, 474, 138                               # 管のまん中、底、口、内側の半分の幅
RX0, RY0, RW, RH = CX - 176, YNOZ, 352, 1446 - YNOZ                   # 星を描く範囲（ここだけ細かい時間で描いてならす）
def stack(t, act):
    """t の時点で列にある星を下から。[(番号, 段, 中心のy)]"""
    a = sorted((i for i in act if ents[i][1] <= t < ents[i][2]), key=lambda i: (-ents[i][0], ents[i][1])); out = []; base = float(YB); pos = {}
    for i in a:
        k, b, d, pt = ents[i]; r = RAD[k]
        if pt is not None and pt in pos:
            f = min(1.0, max(0.0, (t - b) / max(1e-6, d - b))); f = f * f * (3 - 2 * f); y = pos[pt] - 2 * r * (1 - f)   # 下の同じ星へ沈む
        else: y = base - r
        pos[i] = y; base = min(base, y - r); out.append((i, k, y))
    return out, base
class Act:   # 今ある星の番号を、時刻を進めながら持つ
    def __init__(s): s.p = 0; s.a = set()
    def upto(s, t):
        while s.p < len(order) and EB[order[s.p]] <= t: s.a.add(int(order[s.p])); s.p += 1
        for i in [i for i in s.a if ents[i][2] <= t]: s.a.discard(i)
        return s.a
# 落ちてくる月：着く時刻は T[n]（拍の上）。口から初速 v0・重力 g で落ち、ちょうどその時刻に列のてっぺんへ着くように、出る時刻を逆算
G = 5000.0; _a = Act(); V0 = {}; EMIT = {}; YTOP = {}
for n in range(1, NDROP + 1):
    st, base = stack(T[n] - 1e-7, _a.upto(T[n] - 1e-7)); YTOP[n] = base - RAD[0]; D = YTOP[n] - YNOZ
    g = 1800.0 if n == 512 else G; V0[n] = 120.0 if n == 512 else max(300.0, 52.0 / DI[n])
    EMIT[n] = T[n] - (-V0[n] + math.sqrt(V0[n] ** 2 + 2 * g * D)) / g
TN = np.array([T[n] for n in range(1, NDROP + 1)]); LEAD = -(EMIT[1] - .18); DUR = TEND + LEAD; NF = int(DUR * FPS)

# ---------- 音 ----------
def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)
_tc = {}
def stone(m, dec):   # 石を叩く音（石琴ふう。simkit の stone と同じ式）
    if MAT:   # 234：硬い玉が板に当たる音（kalimba.knock）。1打ごとにたたく場所を少し変える
        import kalimba as KB
        _tc["n"] = _tc.get("n", 0) + 1; key = ("k", int(round(m)), _tc["n"] % 7)
        if key not in _tc: _tc[key] = resample_poly(KB.knock(int(round(m)), .85, MAT, _tc["n"] % 7), SR, KB.SR)
        return _tc[key]
    key = (m, round(dec, 1))
    if key not in _tc:
        f = mtof(m); tt = np.arange(int(SR * min(2.4, 7 / dec))) / SR
        s = (np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * f * 1.003 * tt)) * np.exp(-tt * 2.6) + .34 * np.sin(2 * np.pi * f * 2.76 * tt + .7) * np.exp(-tt * 7) \
            + .15 * np.sin(2 * np.pi * f * 5.4 * tt + 1.3) * np.exp(-tt * 15) + .06 * np.sin(2 * np.pi * f * 8.9 * tt) * np.exp(-tt * 28)
        nz = np.random.default_rng(int(m)).normal(0, 1, len(tt)); nz = np.convolve(nz, np.ones(5) / 5, "same") * np.exp(-tt * 700) * .22
        _tc[key] = (s + nz) * np.exp(-tt * max(2.5, dec * .6)) * np.minimum(1, tt / .0008) * np.minimum(1, (tt[-1] - tt) / .02) * (f / 523.25) ** -.3
    return _tc[key]
def tok():           # 月が着く小さい「コッ」
    tt = np.arange(int(SR * .05)) / SR; nz = np.random.default_rng(3).normal(0, 1, len(tt)); nz = np.convolve(nz, np.ones(7) / 7, "same")
    return (np.sin(2 * np.pi * 1240 * tt) * np.exp(-tt * 110) + .5 * np.sin(2 * np.pi * 2480 * tt) * np.exp(-tt * 190) + nz * np.exp(-tt * 600) * .5) * np.minimum(1, tt / .0005)
CHORDS = ["D", "A", "Bm", "F#m", "G", "D", "G", "A"]
TRI = {"D": (62, 66, 69), "A": (57, 61, 64), "Bm": (59, 62, 66), "F#m": (54, 57, 61), "G": (55, 59, 62)}
LINE1 = [78, 76, 74, 73, 71, 69, 71, 73]; LINE2 = [74, 73, 71, 69, 67, 66, 67, 64]                      # カノンの旋律（和音1つに1音）
PH3 = [(74, 78), (81, 79), (78, 74), (78, 76), (74, 71), (74, 81), (79, 83), (81, 79)]                    # 次の変奏（和音1つに2音）
PH4 = [(78, 74), (76, 85), (86, 90), (93, 81), (83, 79), (81, 78), (74, 86), (86, 85)]
FINP = [88, 85, 81, 79, 76, 73, 69, 67]                                                                    # 最後：A7 を上から下りて D へ
def tones(ch, lo, cnt):   # 和音の音を lo 以上から順に
    out = []; m = lo
    while len(out) < cnt:
        if (m - TRI[ch][0]) % 12 in [(x - TRI[ch][0]) % 12 for x in TRI[ch]]: out.append(m)
        m += 1
    return out
def chord_at(t):
    s = int(math.floor((t + 1e-6) / SLOT));
    if s >= 17: return "D", s
    if s >= 15: return "A", s
    return CHORDS[s % 8], s
N = int(SR * (DUR + 2.6)); AL = np.zeros(N); AR = np.zeros(N); SL = np.zeros(N); SRv = np.zeros(N)
def put(x, t, pan=.5, g=1.0, send=.35):
    i = int(round((t + LEAD) * SR))
    if i < 0 or i >= N: return
    k = min(len(x), N - i); l, r = math.cos(pan * math.pi / 2) * g, math.sin(pan * math.pi / 2) * g
    AL[i:i + k] += x[:k] * l; AR[i:i + k] += x[:k] * r; SL[i:i + k] += x[:k] * l * send; SRv[i:i + k] += x[:k] * r * send
cnt = {}; notes_log = []
for tm, j, n, first, cls in merges:
    ch, s = chord_at(tm - min(.25, dm(n, 1) * j)); s8 = s % 8; cyc2 = (s // 8) % 2 == 1; key = (j, s); q = cnt.get(key, 0); cnt[key] = q + 1
    pan = .5 + .16 * math.sin(j * 2.1)
    if n == 512:
        if j < 9: put(stone(FINP[j - 1], 3.2), tm, pan, .50 + .05 * j, .5); notes_log.append((tm, FINP[j - 1], j))
        else:
            for m_, g_ in (((50, .9), (62, .8), (69, .6), (74, .7)) if MAT else ((38, .9), (45, .7), (50, .9), (57, .6), (62, .8), (66, .6), (69, .6), (74, .7), (78, .5))): put(stone(m_, 2.2), tm, .5 + .2 * math.sin(m_), g_ * .62, .7)
            notes_log.append((tm, 62, j))
        continue
    if cls <= .26:   m, g, dc, sd = TRI[ch][0] - 24 + (12 if MAT else 0), .78, 2.4, .5; MAT or put(stone(m + 12, 2.8), tm, .5, .34, .5)   # いちばん大きい星：低音（1オクターブ上を重ねて小さいスピーカーでも聞こえるように）
    elif cls <= .51: m, g, dc, sd = TRI[ch][0] - 12, .70, 2.6, .5; MAT or put(stone(m + 12, 3.0), tm, .5, .26, .5)
    elif cls <= 1.01: m, g, dc, sd = (LINE2 if cyc2 else LINE1)[s8], 1.0, 3.0, .55                              # カノンの旋律
    elif cls <= 2.01: m, g, dc, sd = (PH4 if cyc2 else PH3)[s8][q % 2], .74, 4.0, .45
    elif cls <= 4.01: tl = tones(ch, 76, 3); m, g, dc, sd = tl[(0, 1, 2, 1)[q % 4]], .46, 6.0, .4               # 分散和音
    elif cls <= 8.01: tl = tones(ch, 81, 4); m, g, dc, sd = tl[(0, 1, 2, 3, 2, 1, 0, 1)[q % 8]], .27, 10.0, .35
    elif cls <= 16.01: tl = tones(ch, 86, 3); m, g, dc, sd = tl[(0, 2, 1, 2)[q % 4]], .12, 18.0, .3              # 速すぎる星は、小さくきらめくだけ
    elif cls <= 32.01: tl = tones(ch, 86, 2); m, g, dc, sd = tl[q % 2], .045, 26.0, .25
    else: continue
    put(stone(m, dc), tm, pan, g, sd); notes_log.append((tm, m, j))
TK = stone(86, 20) if MAT else tok()
for n in range(1, NDROP + 1):   # 着く音：ゆっくりの間だけ聞こえる
    g = .30 * min(1.0, (DI[n] / .13)) ** 1.5
    if g > .012: put(TK, T[n], .5, g, .2)
# 下に流れるうすい和音（カノンの進行。合体の音のじゃまをしない大きさ）
def pad(ms, dur, g):
    tt = np.arange(int(SR * dur)) / SR; s = np.zeros(len(tt))
    for q, m_ in enumerate(ms):
        f = mtof(m_); s += (np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * f * 1.004 * tt + q) + .22 * np.sin(4 * np.pi * f * tt + 2 * q)) / (1 + .25 * q)
    return s * np.minimum(1, tt / .30) * np.minimum(1, (dur - tt) / .45) * g
for s in range(0, 20):
    ch = "D" if s >= 17 else ("A" if s >= 15 else CHORDS[s % 8]); r_, t_, f_ = TRI[ch]; ms = [r_, t_, f_, r_ + 12] + ([r_ + 10] if s == 16 else [])
    if s * SLOT < TEND: put(pad(ms, SLOT + .5 if s < 19 else 1.6, .022 if s < 17 else .032), s * SLOT - .05, .5, 1.0, .6)
put(pad([50, 62, 66, 69], 1.5 * BEAT + .5, .022), -1.5 * BEAT, .5, 1.0, .6)   # 最初の合体の前：D のうすい和音
tt_ = np.arange(int(SR * 2.4)) / SR
def ir(seed): return np.convolve(np.random.default_rng(seed).normal(0, 1, len(tt_)) * np.exp(-tt_ * 2.4), np.ones(24) / 24, "same") * .02
AL += fftconvolve(SL, ir(11))[:N]; AR += fftconvolve(SRv, ir(12))[:N]
mix = np.stack([AL, AR], 1); pk = np.abs(mix).max(); mix = np.tanh(mix / pk * 1.5) / np.tanh(1.5)
sos = butter(4, 15000, "low", fs=SR, output="sos"); mix = np.stack([sosfilt(sos, mix[:, 0]), sosfilt(sos, mix[:, 1])], 1)
e0 = int(SR * DUR); fo = int(SR * .5); mix[e0 - fo:e0] *= np.linspace(1, 0, fo)[:, None]; mix = mix[:e0]
tp = max(np.abs(resample_poly(mix[:, 0], 4, 1)).max(), np.abs(resample_poly(mix[:, 1], 4, 1)).max()); mix *= .84 / tp   # 圧縮したあとに山がはみ出さないよう、細かく見た山で合わせる
os.makedirs("build_mergecol", exist_ok=True)
with wave.open("build_mergecol/a.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())

# ---------- 絵：動かない部分 ----------
def build_static():
    rs = np.random.default_rng(5); yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    bg = np.zeros((H, W, 3), np.float32); bg[..., 0] = 8 + 7 * yy; bg[..., 1] = 9 + 2 * yy; bg[..., 2] = 22 + 12 * yy
    if VAR2: bg[..., 0] = 5 + 4 * yy; bg[..., 1] = 12 + 9 * yy; bg[..., 2] = 20 + 12 * yy   # 青緑寄りの夜空
    im = Image.fromarray(bg.astype(np.uint8)); glow = Image.new("RGB", (W, H), (0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse([120, 520, 960, 1500], fill=(8, 22, 30) if VAR2 else (14, 12, 34)); gd.ellipse([-200, 1300, 500, 2100], fill=(18, 10, 30) if VAR2 else (10, 16, 30)); im = ImageChops.add(im, glow.filter(ImageFilter.GaussianBlur(170)))
    d = ImageDraw.Draw(im)
    for _ in range(170):
        x, y = rs.uniform(0, W), rs.uniform(0, H); b = int(rs.uniform(40, 150)); r = rs.choice([1, 1, 1, 2]); d.ellipse([x - r, y - r, x + r, y + r], fill=(b, b, min(255, b + 20)))
    S = 2; fr = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); f = ImageDraw.Draw(fr); o = HW + 6; yc = YB + 6 - o; yt = 492
    tint = Image.new("RGBA", (W, H), (0, 0, 0, 0)); td = ImageDraw.Draw(tint); td.rectangle([CX - HW, yt, CX + HW, yc], fill=(150, 170, 255, 9)); td.pieslice([CX - HW, yc - HW, CX + HW, yc + HW], 0, 180, fill=(150, 170, 255, 9))
    im = Image.alpha_composite(im.convert("RGBA"), tint).convert("RGB")
    col = (176, 190, 226, 170)   # ガラスの管（手前に重ねる）
    f.line([(CX - o) * S, yt * S, (CX - o) * S, yc * S], fill=col, width=3 * S); f.line([(CX + o) * S, yt * S, (CX + o) * S, yc * S], fill=col, width=3 * S)
    f.arc([(CX - o) * S, (yc - o) * S, (CX + o) * S, (yc + o) * S], 0, 180, fill=col, width=3 * S)
    f.ellipse([(CX - o - 12) * S, (yt - 9) * S, (CX + o + 12) * S, (yt + 9) * S], outline=(176, 190, 226, 150), width=3 * S)
    hi = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); h = ImageDraw.Draw(hi)
    h.rounded_rectangle([(CX - HW + 14) * S, (yt + 40) * S, (CX - HW + 26) * S, (yc - 10) * S], radius=6 * S, fill=(255, 255, 255, 34)); h.rounded_rectangle([(CX + HW - 20) * S, (yt + 120) * S, (CX + HW - 15) * S, (yc - 60) * S], radius=3 * S, fill=(255, 255, 255, 18))
    fr = Image.alpha_composite(fr, hi.filter(ImageFilter.GaussianBlur(5 * S)))
    f = ImageDraw.Draw(fr)   # 上の口（月が出てくる所）
    f.rounded_rectangle([(CX - 66) * S, 424 * S, (CX + 66) * S, 470 * S], radius=12 * S, fill=(22, 24, 42, 255), outline=(176, 190, 226, 200), width=2 * S)
    f.ellipse([(CX - 26) * S, 462 * S, (CX + 26) * S, 478 * S], fill=(6, 6, 14, 255), outline=(150, 166, 210, 220), width=2 * S)
    for q in (-44, 44): f.ellipse([(CX + q - 3) * S, 444 * S, (CX + q + 3) * S, 450 * S], fill=(176, 190, 226, 200))
    fr = fr.resize((W, H), Image.LANCZOS); f = ImageDraw.Draw(fr)
    l1 = ("Two matching stars become one bigger star" if VAR2 else "Two of the same merge into a bigger one") if EN else "同じ星が2つ重なると、1つ大きい星になる"
    l2 = ("How many Moons make one Sun?" if VAR2 else "Keep dropping Moons. Get a Sun?") if EN else "月を何個落とすと、太陽になる？"
    f.text((W / 2, 176), l1, font=fnt(48 if EN else 47), fill=(244, 244, 250, 255), anchor="mm", stroke_width=5, stroke_fill=(6, 6, 16, 255))
    f.text((W / 2, 248), l2, font=fnt(54 if EN else 52), fill=(255, 226, 122, 255), anchor="mm", stroke_width=5, stroke_fill=(6, 6, 16, 255))
    warm = Image.new("L", (W, H), 0); wd = ImageDraw.Draw(warm); wd.rectangle([CX - HW, yt, CX + HW, yc], fill=255); wd.pieslice([CX - HW, yc - HW, CX + HW, yc + HW], 0, 180, fill=255)
    wg = np.asarray(warm, np.float32) / 255 * np.clip((np.arange(H, dtype=np.float32)[:, None] - 700) / 720, 0, 1) ** 1.6
    return im, fr, wg
BG, FRONT, WARM = build_static(); BGROI = np.asarray(BG, np.float32)[RY0:RY0 + RH, RX0:RX0 + RW] / 255
IX = [90 + 100 * k for k in range(NT)]; IY = 356
ICON = [to_pil(sprite(k, 24.0 if k != 7 else 19.0)) for k in range(NT)]
ICON_DIM = [Image.merge("RGBA", (*[c.point(lambda v: int(v * .26)) for c in im_.split()[:3]], im_.split()[3])) for im_ in ICON]
fW = ImageFont.truetype(FI, 24); fQ = ImageFont.truetype(FI, 26); fCnt = ImageFont.truetype(FI, 84); fUnit = fnt(34); fName = fnt(66); fSub = fnt(38); fBig = fnt(128); fBig2 = fnt(56); fOne = fnt(62)
FIRST = {j: tm for tm, j, n, first, cls in merges if first}

def blit4(buf, s, cx, cy):   # 前掛けの RGBA どうしを重ねる
    sh, sw = s.shape[:2]; x0 = int(round(cx - sw / 2)); y0 = int(round(cy - sh / 2)); xa, ya = max(0, x0), max(0, y0); xb, yb = min(buf.shape[1], x0 + sw), min(buf.shape[0], y0 + sh)
    if xa >= xb or ya >= yb: return
    p = s[ya - y0:yb - y0, xa - x0:xb - x0]; buf[ya:yb, xa:xb] = buf[ya:yb, xa:xb] * (1 - p[..., 3:4]) + p
def blit(buf, s, cx, cy):
    sh, sw = s.shape[:2]; x0 = int(round(cx - sw / 2)); y0 = int(round(cy - sh / 2)); xa, ya = max(0, x0), max(0, y0); xb, yb = min(buf.shape[1], x0 + sw), min(buf.shape[0], y0 + sh)
    if xa >= xb or ya >= yb: return
    p = s[ya - y0:yb - y0, xa - x0:xb - x0]; buf[ya:yb, xa:xb] = buf[ya:yb, xa:xb] * (1 - p[..., 3:4]) + p[..., :3]

class Renderer:
    def __init__(s): s.act = Act(); s.yv = {}; s.q = deque(); s.pres = np.zeros(NT); s.lastt = None; s.ysun = None
    def sub(s, t, dt):
        """ある瞬間の星の絵（描く範囲だけ）。位置はなめらかに追いつかせる"""
        buf = np.zeros((RH, RW, 4), np.float32)
        st, base = stack(t, s.act.upto(t)); kk = 1 - math.exp(-dt / .028) if dt > 0 else 1.0; live = set()
        for i, k, y in st:
            live.add(i); yv = s.yv.get(i, y); yv += (y - yv) * kk; s.yv[i] = yv; age = t - ents[i][1]
            pop = 1 + (.24 * math.exp(-age / .075) if (k > 0 and (ents[i][2] - ents[i][1]) > .12) else 0)
            if k == 9: pop *= 1 + .018 * math.sin(max(0, age) * 2.4)   # 太陽はゆっくり息をする
            blit4(buf, sprite(k, RAD[k] * pop), CX - RX0, yv - RY0)
            if k == 9: s.ysun = yv
        for i in [i for i in s.yv if i not in live]: del s.yv[i]
        return buf, st
    def frame(s, fi):
        t = fi / FPS - LEAD; dt_f = 1 / FPS
        if s.lastt is None or abs((t - dt_f) - s.lastt) > 1e-6: s.q.clear(); s.yv.clear(); s.act = Act()       # 途中から描くとき
        s.lastt = t; nd = int(np.searchsorted(TN, t, "right")); di = DI[max(1, min(NDROP, nd if nd else 1))] if t < T511 + .02 else 1.0
        K = 1 if di > .1 else (3 if di > .03 else 6); win = 1 if di > .07 else (2 if di > .04 else (3 if di > .02 else 4))
        acc = np.zeros((RH, RW, 4), np.float32); st = []; pr = np.zeros(NT)
        for q in range(K):
            ts = t - dt_f + (q + 1) * dt_f / K; b, st = s.sub(ts, dt_f / K); acc += b
            for i, k, y in st: pr[k] += 1.0 / K
        s.q.append(acc / K)
        while len(s.q) > win: s.q.popleft()
        lay = sum(s.q) / len(s.q); roi = BGROI.copy()
        lo = int(np.searchsorted(TN, t, "right"))                    # まだ着いていない月（空中）。列のうしろに、くっきり
        for n in range(lo + 1, min(NDROP, lo + 80) + 1):
            tau = t - EMIT[n]
            if tau < 0: continue
            g = 1800.0 if n == 512 else G; blit(roi, sprite(0, RAD[0]), CX - RX0, YNOZ + V0[n] * tau + .5 * g * tau * tau - RY0)
        roi = roi * (1 - lay[..., 3:4]) + lay[..., :3]; s.pres += (np.minimum(pr, 1) - s.pres) * (1 - math.exp(-dt_f / .07))
        im = BG.copy(); im.paste(Image.fromarray((np.clip(roi, 0, 1) * 255).astype(np.uint8)), (RX0, RY0)); im = Image.alpha_composite(im.convert("RGBA"), FRONT)
        add = Image.new("RGB", (W, H), (0, 0, 0)); ad = ImageDraw.Draw(add); ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        ypos = {k: y for i, k, y in st}
        # 合体の光の輪（音が鳴る合体だけ。合体の瞬間から広がる）
        for tm, j, n, first, cls in merges:
            if tm > t: break
            life = (1.5 if j == 9 else (.55 if first else min(.36, .55 * SLOT / max(cls, 1e-6))))
            if t - tm > life or (cls > 16.01 and not first): continue
            p = (t - tm) / life; y = ypos.get(j, None)
            if y is None: continue
            R = RAD[j]; c = GLOW[j]; a = (1 - p) ** 1.6 * (.9 if first else .62) * (1.0 if cls <= 8.01 else .5)
            for w_, r1 in ((max(2, int(R * .075)), R * (1.05 + (2.3 if j == 9 else (1.5 if first else .95)) * p)),) + (((2, R * (1.05 + 2.6 * p)),) if first or j == 9 else ()):
                ad.ellipse([CX - r1, y - r1, CX + r1, y + r1], outline=tuple(int(v * a) for v in c), width=w_)
        # 月が着いた小さい輪（ゆっくりの間だけ）
        if nd >= 1 and DI[nd] > .05 and t - T[nd] < .16:
            p = (t - T[nd]) / .16; r1 = RAD[0] * (1.0 + .9 * p); a = (1 - p) * .5; ad.ellipse([CX - r1, YTOP[nd] - r1, CX + r1, YTOP[nd] + r1], outline=tuple(int(v * a) for v in GLOW[0]), width=2)
        # 上の列：今ある星が明るい（落とした数の2進数）。まだできていない星は「？」
        for k in range(NT):
            x = IX[k]; known = k == 0 or (k in FIRST and FIRST[k] <= t)
            if not known:
                d.ellipse([x - 25, IY - 25, x + 25, IY + 25], outline=(120, 130, 170, 150), width=2); d.text((x, IY), "?", font=fQ, fill=(130, 140, 180, 200), anchor="mm"); continue
            b = float(min(1, s.pres[k])); ic = ICON[k]; ov.alpha_composite(ICON_DIM[k], (x - ic.width // 2, IY - ic.height // 2))
            if b > .02: ov.paste(ic, (x - ic.width // 2, IY - ic.height // 2), ic.split()[3].point(lambda v, b=b: int(v * b)))
            e = t - FIRST.get(k, -9)
            if 0 <= e < .6: r1 = 27 + 16 * e / .6; a = (1 - e / .6); ad.ellipse([x - r1, IY - r1, x + r1, IY + r1], outline=tuple(int(v * a * .9) for v in GLOW[k]), width=3)
            if not EN: g_ = int(120 + 135 * b); d.text((x, IY + 46), str(2 ** k), font=fW, fill=(g_, g_, min(255, g_ + 10), 255), anchor="mm")
        # 数
        d.text((862, 560), "Moons dropped" if EN else "落とした月", font=fUnit if not EN else fnt(30), fill=(196, 202, 224, 255), anchor="mm", stroke_width=3, stroke_fill=(6, 6, 16, 255))
        d.text((862, 632), str(nd), font=fCnt, fill=(244, 244, 250, 255), anchor="mm", stroke_width=4, stroke_fill=(6, 6, 16, 255))
        # 初めての星の名前（管の左）
        for j, tm in FIRST.items():
            e = t - tm
            if j == 9 or e < 0 or e > 1.7: continue
            a = min(1, e / .08) * min(1, (1.7 - e) / .3); y = min(1370, max(600, ypos.get(j, YB - RAD[j]))) - 14 * min(1, e / .5); A = int(255 * a)
            d.text((196, y), NAMES[j], font=fName if not EN else fnt(54), fill=(248, 248, 252, A), anchor="mm", stroke_width=5, stroke_fill=(6, 6, 16, A))
            if not EN: d.text((196, y + 58), (f"= {2 ** j} moons" if EN else f"月 {2 ** j}個ぶん"), font=fSub if not EN else fnt(32), fill=(255, 226, 122, A), anchor="mm", stroke_width=4, stroke_fill=(6, 6, 16, A))
        if T511 + .12 < t < T[512]:   # 最後の1個の前
            a = min(1, (t - T511 - .12) / .15); A = int(255 * a); d.text((196, 560), "One more" if EN else "あと1個", font=fOne, fill=(255, 226, 122, A), anchor="mm", stroke_width=5, stroke_fill=(6, 6, 16, A))
        if t >= TSUN:                 # 決着
            e = t - TSUN; a = min(1, e / .25); A = int(255 * a); ys = (s.ysun or (YB - RAD[9]))
            d.text((W / 2, ys - 330 - 16 * min(1, e / .6)), NAMES[9], font=fBig if not EN else fnt(120), fill=(255, 226, 122, A), anchor="mm", stroke_width=8, stroke_fill=(6, 6, 16, A))
            if not EN: d.text((W / 2, ys - 226 - 16 * min(1, e / .6)), ("= 512 Moons" if EN else "月 512個ぶん"), font=fBig2, fill=(248, 248, 252, A), anchor="mm", stroke_width=6, stroke_fill=(6, 6, 16, A))
        im = Image.alpha_composite(im, ov).convert("RGB")
        if t >= TSUN:                 # 太陽の明かりで管の中がうっすら暖かくなる
            e = min(1, (t - TSUN) / .8); wl = (WARM * (e * .16))[..., None] * np.array([255, 150, 60], np.float32); add = ImageChops.add(add, Image.fromarray(np.clip(wl, 0, 255).astype(np.uint8)))
        im = ImageChops.add(im, add)
        src = add.copy(); src.paste(Image.fromarray((np.clip((roi - .60) * 1.3, 0, 1) * 255).astype(np.uint8)), (RX0, RY0))                # にじみ：星の明るい所と光の輪だけ、ひかえめ（文字は光らせない）
        bl = src.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(7)).resize((W, H), Image.BILINEAR)
        return ImageChops.add(im, bl)

if __name__ == "__main__":
    st = os.environ.get("STILLS"); R_ = Renderer()
    if os.environ.get("INFO"):
        print("長さ", round(DUR, 2), "秒 / 先頭の余白", round(LEAD, 3), "/ 太陽", round(TSUN + LEAD, 2), "秒 / 合体", len(merges), "回 / 鳴らす音", len(notes_log))
        for j, tm in sorted(FIRST.items()): print("  初めての", NAMES[j], "映像の", round(tm + LEAD, 3), "秒")
        sys.exit()
    if st:
        for x in st.split(","):
            f0 = int(float(x) * FPS); im = None
            for fi in range(max(0, f0 - 8), f0 + 1): im = R_.frame(fi)
            im.save(f"build_mergecol/s_{float(x):05.2f}.jpg", quality=90)
        sys.exit()
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", "build_mergecol/a.wav",
                          "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    for fi in range(NF): p.stdin.write(R_.frame(fi).tobytes())
    p.stdin.close(); p.wait(); print(OUT, round(DUR, 2), "秒")
