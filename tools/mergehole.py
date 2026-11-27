# mergehole.py — 同じ星が2つ重なると、1つ重い星になる。太陽を落とし続けると、ブラックホールになる（mergecol の続き。縦のショート）
#   持ち主 11/27：mergecol1（月→太陽）が公開35時間で 8,739 回・平均視聴割合 114.7%・直近10本で1位 →「これ系伸びそう」
#   同じなのは、決まり（同じ星が2つ重なると合体）・管・落とす速さ（数が2倍になるたびに速さも2倍）。変えたのは、問い・星・結末：
#     ・落とすのは太陽。重さは 1 → 2 → 4 → 8 → 16 と倍になり、32個めでブラックホールになる
#       実際の星の重さ（太陽＝1。2026-11-27 に確認）：シリウス 2.06、レグルス 4.15、ベラトリックス 8.4、ベテルギウス 10〜20（14 とする資料が多い）。
#       太陽の約20倍より重い星は、一生の最後にブラックホールになることがある（どこから必ずそうなるかは、まだはっきりしていない）
#     ・ブラックホールになったあとは、落ちてきた太陽をぜんぶ飲みこむ。重さ＝落とした数。半径は重さに比例する（シュワルツシルト半径）。512個で半径16倍
#     ・ブラックホールのまわりでは光が曲がるので、うしろの星や管がふちへ引きのばされて見える。飲みこむ量が多いほど、ふちの輪が明るい
#   音：trendkit の Audio（硬い玉が板に当たる音。材質は1本ごとに回す＝この動画は竹）。当たった瞬間に1打ずつ：着地・合体のはじまり・ブラックホールの誕生・飲みこみ。
#       大きい星ほど低い。和音はカノン進行（2拍で1つ）。2段・3段と続けて合体するときは、1段ごとに音がずれて重なる（11/26 持ち主）
#   python3 tools/mergehole.py [out.mp4]   STILLS=1,5,9 で確認用の絵（build_mergehole/s_*.jpg）、INFO=1 で時刻の一覧、LANG_OUT=en で英語、MAT=wood|bamboo|hollow
import math, os, sys, subprocess
from collections import deque
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as TKIT

W, H, FPS, SR = 1080, 1920, 60, 48000
LANG = os.environ.get("LANG_OUT", "ja"); EN = LANG == "en"; MAT = os.environ.get("MAT", "bamboo")
OUT = sys.argv[1] if len(sys.argv) > 1 else f"output/mergehole1_{LANG}.mp4"; B = "build_mergehole"; os.makedirs(B, exist_ok=True)
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"; FI = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
def fnt(sz, latin=False): return ImageFont.truetype(FI if (latin or EN) else FJ, sz)
def fit(s, sz, maxw):
    while sz > 20 and fnt(sz).getlength(s) > maxw: sz -= 2
    return fnt(sz)

# ---------- 星 ----------
NT, NBH, NDROP = 6, 32, 512                                           # 段の数（0〜4 は星、5 はブラックホール）／ブラックホールになる個数／落とす数
LIKE = ["", "about Sirius", "about Regulus", "about Bellatrix", "about Betelgeuse", ""] if EN else ["", "シリウスくらい", "レグルスくらい", "ベラトリックスくらい", "ベテルギウスくらい", ""]
RAD = [22.0, 28.0, 35.0, 44.0, 62.0, 30.0]                             # 列の中の半径（px）。最後はブラックホールのはじめの半径
GLOW = [(255, 206, 96), (226, 234, 255), (176, 200, 255), (140, 172, 255), (255, 140, 84), (255, 206, 160)]
TILT = [0.0, .3, -.2, .4, .15, 0.0]
STAR = [((255, 196, 70), (255, 238, 156), (244, 146, 36), (3., 6., 12.)),      # 太陽：黄
        ((228, 234, 255), (255, 255, 255), (186, 204, 250), (3., 6., 12.)),    # 太陽2個ぶん：白（シリウスくらい）
        ((178, 202, 255), (226, 238, 255), (136, 168, 250), (3., 6., 12.)),    # 4個ぶん：青白（レグルスくらい）
        ((140, 174, 255), (200, 222, 255), (100, 136, 244), (3., 6., 12.)),    # 8個ぶん：青（ベラトリックスくらい）
        ((255, 132, 66), (255, 190, 116), (206, 76, 36), (1.6, 3.2, 6.4))]     # 16個ぶん：赤い超巨星（ベテルギウスくらい）。大きな対流の模様

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
def tex(k, P):
    a, b, c, fr = STAR[k]; m = snoise(P, 91 + k, fr, (1, .7, .45)); return mixc(mixc(a, b, sstep(.15, .8, m)), c, sstep(.2, .9, -m) * .7)

_SPR = {}
def sprite(k, Rp, ss=3):
    """前もって不透明度を掛けた RGBA（float32）。星は自分で光る（ふちにやわらかい光）。k=5 はブラックホールの小さい絵（上の列用）"""
    key = (k, float(round(Rp)) if Rp > 60 else round(Rp * 2) / 2)
    if key in _SPR: return _SPR[key]
    Rp = key[1]; ss = 2 if Rp > 60 else ss
    half = int(math.ceil(Rp * 1.45)) + 2; S = 2 * half; n = S * ss
    c = (np.arange(n, dtype=np.float32) + .5) / ss - half; xx, yy = np.meshgrid(c, c)
    rr = np.hypot(xx, yy) / Rp; nx, ny = xx / Rp, yy / Rp; nz = np.sqrt(np.clip(1 - rr * rr, 0, 1)); o = np.zeros((n, n, 4), np.float32)
    al = np.clip((1 - rr) * Rp * ss + .5, 0, 1); o[..., 3] = al
    if k == 5:
        o[..., :3] += (np.exp(-((rr - 1.07) / .075) ** 2) * .95)[..., None] * np.asarray((255, 222, 180), np.float32) / 255
        o[..., :3] += (np.exp(-np.clip(rr - 1, 0, None) / .16) * .22 * (rr > 1))[..., None] * np.asarray((255, 150, 70), np.float32) / 255
    else:
        ca, sa = math.cos(TILT[k]), math.sin(TILT[k]); u = nx * ca + ny * sa; v = -nx * sa + ny * ca
        P = np.stack([u, v, nz], -1).astype(np.float32); rgb = tex(k, P) * (.72 + .28 * nz ** .55)[..., None]          # ふちへ行くほど少し暗い
        o[..., :3] = np.clip(rgb, 0, 255) / 255 * al[..., None]
        hl = np.exp(-(np.clip(rr - 1, 0, None) / .15) ** 1.25) * .38 * (rr > 1); o[..., :3] += hl[..., None] * np.asarray(GLOW[k], np.float32) / 255   # やわらかい光のふち（光らせすぎない）
    o = o.reshape(S, ss, S, ss, 4).mean((1, 3)); _SPR[key] = o; return o
def to_pil(s):
    a = np.clip(s[..., 3:4], 1e-4, 1); return Image.fromarray((np.clip(np.concatenate([np.clip(s[..., :3] / a, 0, 1) * (s[..., 3:4] > .02) + s[..., :3] * (s[..., 3:4] <= .02), np.maximum(s[..., 3:4], s[..., :3].max(-1, keepdims=True))], -1), 0, 1) * 255).astype(np.uint8), "RGBA")

# ---------- 時間割（和音1つ＝2拍。t=0 は最初の合体。mergecol と同じ：数が2倍になるたびに、落とす速さも2倍） ----------
BPM = 112.0; BEAT = 60 / BPM; SLOT = 2 * BEAT
T = {1: -BEAT}; DI = {1: BEAT}
for n in range(2, 9): T[n] = (n - 2) * BEAT; DI[n] = BEAT             # はじめは1拍に1個
n0, t0, di = 8, T[8], BEAT / 2
while n0 < NDROP:
    for n in range(n0 + 1, 2 * n0 + 1): T[n] = t0 + (n - n0) * di; DI[n] = di
    t0 = T[2 * n0]; n0 *= 2; di /= 2
    if n0 == NBH: t0 += 4 * BEAT                                       # ブラックホールができる間（4拍）は、落とすのを休む
FIN = [.13, .15, .19, .25, .3514]                                      # 32個め：下の段へ、だんだんゆっくり合体していく（合わせて2拍）
TEND = T[NDROP] + 2.8
def v2(n):
    v = 0
    while n % 2 == 0: n //= 2; v += 1
    return v
def dm(n, j): return FIN[j - 1] if n == NBH else min(BEAT / 6, .3 * (2 ** j) * DI[n])   # 1段の合体にかかる時間

# ---------- 出来事：落ちる・合体する（32個めまで。そのあとは飲みこまれる） ----------
ents = []      # [段, 生まれた時刻, 消える時刻, 沈む相手]
merges = []    # (合体が終わる時刻, できた段, 何個め, その段の初めてか, 合体がはじまる時刻＝2つが触れた瞬間)
cur = [None] * NT; seen = set()
for n in range(1, NBH + 1):
    ents.append([0, T[n], 1e9, None]); casc = len(ents) - 1; tm = T[n]
    for j in range(1, v2(n) + 1):
        ts = tm; tm += dm(n, j); old = cur[j - 1]; ents[old][2] = tm; ents[casc][2] = tm; ents[casc][3] = old; cur[j - 1] = None
        ents.append([j, tm, 1e9, None]); casc = len(ents) - 1
        merges.append((tm, j, n, j not in seen, ts)); seen.add(j)
    cur[v2(n)] = casc
TBH = merges[-1][0]                                                   # ブラックホールができる時刻
EB = np.array([e[1] for e in ents]); order = np.argsort(EB, kind="stable")

# ---------- 置き場所 ----------
CX, YB, YNOZ, HW = 540, 1420, 474, 138                               # 管のまん中、底、口、内側の半分の幅
YCB = YB - RAD[5]                                                     # ブラックホールの中心（動かない）
RX0, RY0, RW, RH = CX - 176, YNOZ, 352, 1446 - YNOZ                   # 星を描く範囲（ここだけ細かい時間で描いてならす）
def Rb(m): return RAD[5] * max(1.0, m / NBH)                          # ブラックホールの半径：重さ（＝落とした数）に比例
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
# 落ちてくる太陽：着く時刻は T[n]（拍の上）。口から初速 v0・重力 g で落ち、ちょうどその時刻に着くように、出る時刻を逆算
G = 5000.0; _a = Act(); V0 = {}; EMIT = {}; YTOP = {}
for n in range(1, NDROP + 1):
    if n <= NBH: st, base = stack(T[n] - 1e-7, _a.upto(T[n] - 1e-7)); YTOP[n] = base - RAD[0]
    else: YTOP[n] = YCB - Rb(n - 1) + RAD[0] * .4                     # ブラックホールのふちに半分かくれた所で消える
    D = YTOP[n] - YNOZ; V0[n] = max(300.0, 52.0 / DI[n]); EMIT[n] = T[n] - (-V0[n] + math.sqrt(V0[n] ** 2 + 2 * G * D)) / G
TN = np.array([T[n] for n in range(1, NDROP + 1)]); LEAD = -(EMIT[1] - .18); DUR = TEND + LEAD; NF = int(DUR * FPS)
FIRST = {j: tm for tm, j, n, first, ts in merges if first}

# ---------- 音：当たった瞬間に1打ずつ ----------
def chord_i(t): return int(math.floor((t + 1e-6) / SLOT)) % 8
def audio(path):
    a = TKIT.Audio(DUR, lo=62, hi=90, mat=MAT, max_same=3)
    for n in range(1, NBH + 1):
        if n % 2: a.hit(T[n] + LEAD, .97, vel=.36, chord=chord_i(T[n]))                                   # 着いただけ（合体しない）：小さく高い1打
    for tm, j, n, first, ts in merges:
        a.hit(ts + LEAD, .82 - .19 * j if j < 5 else .25, vel=.50 + .09 * j if j < 5 else .80, chord=chord_i(ts))   # 2つが触れた瞬間。大きい星ほど低く、強い
    a.hit(TBH + LEAD, 0.0, vel=1.0, chord=chord_i(TBH))                                                    # ブラックホールの誕生：いちばん低い1打
    for n in range(NBH + 1, NDROP + 1):                                                                    # 飲みこむ1個ごとに1打。重くなるほど低い
        a.hit(T[n] + LEAD, max(0.0, .70 - .165 * math.log2(n / NBH)), vel=max(.2, .40 * (DI[n] / DI[NBH + 1]) ** .22), chord=chord_i(T[n]))
    return a.write(path)

# ---------- 絵：動かない部分 ----------
def build_static():
    rs = np.random.default_rng(5); yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    bg = np.zeros((H, W, 3), np.float32); bg[..., 0] = 8 + 7 * yy; bg[..., 1] = 9 + 2 * yy; bg[..., 2] = 22 + 12 * yy
    im = Image.fromarray(bg.astype(np.uint8)); glow = Image.new("RGB", (W, H), (0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse([120, 520, 960, 1500], fill=(14, 12, 34)); gd.ellipse([-200, 1300, 500, 2100], fill=(10, 16, 30)); im = ImageChops.add(im, glow.filter(ImageFilter.GaussianBlur(170)))
    d = ImageDraw.Draw(im)
    for _ in range(260):                                               # うしろの星（ブラックホールのまわりで、ゆがんで見える）
        x, y = rs.uniform(0, W), rs.uniform(0, H); b = int(rs.uniform(40, 170)); r = rs.choice([1, 1, 1, 2]); d.ellipse([x - r, y - r, x + r, y + r], fill=(b, b, min(255, b + 20)))
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
    f = ImageDraw.Draw(fr)   # 上の口（太陽が出てくる所）
    f.rounded_rectangle([(CX - 66) * S, 424 * S, (CX + 66) * S, 470 * S], radius=12 * S, fill=(22, 24, 42, 255), outline=(176, 190, 226, 200), width=2 * S)
    f.ellipse([(CX - 26) * S, 462 * S, (CX + 26) * S, 478 * S], fill=(6, 6, 14, 255), outline=(150, 166, 210, 220), width=2 * S)
    for q in (-44, 44): f.ellipse([(CX + q - 3) * S, 444 * S, (CX + q + 3) * S, 450 * S], fill=(176, 190, 226, 200))
    fr = fr.resize((W, H), Image.LANCZOS); f = ImageDraw.Draw(fr)
    l1 = "Two same stars merge into a heavier one" if EN else "同じ星が2つ重なると、1つ重い星になる"
    l2 = "How many Suns make a black hole?" if EN else "太陽を何個落とすと、ブラックホールになる？"
    f.text((W / 2, 176), l1, font=fit(l1, 48, 1010), fill=(244, 244, 250, 255), anchor="mm", stroke_width=5, stroke_fill=(6, 6, 16, 255))
    f.text((W / 2, 248), l2, font=fit(l2, 54, 1010), fill=(255, 226, 122, 255), anchor="mm", stroke_width=5, stroke_fill=(6, 6, 16, 255))
    return im, fr
BG, FRONT = build_static(); BGROI = np.asarray(BG, np.float32)[RY0:RY0 + RH, RX0:RX0 + RW] / 255
IX = [int(W / 2 + (k - 2.5) * 118) for k in range(NT)]; IY = 356
ICON = [to_pil(sprite(k, 24.0 if k < 5 else 19.0)) for k in range(NT)]
ICON_DIM = [Image.merge("RGBA", (*[c.point(lambda v: int(v * .26)) for c in im_.split()[:3]], im_.split()[3])) for im_ in ICON]
fW = ImageFont.truetype(FI, 24); fQ = ImageFont.truetype(FI, 26); fCnt = ImageFont.truetype(FI, 84); fUnit = fnt(34 if not EN else 30); fSmall = fnt(28 if not EN else 26)
INK = (6, 6, 16)

def blit4(buf, s, cx, cy):   # 前掛けの RGBA どうしを重ねる
    sh, sw = s.shape[:2]; x0 = int(round(cx - sw / 2)); y0 = int(round(cy - sh / 2)); xa, ya = max(0, x0), max(0, y0); xb, yb = min(buf.shape[1], x0 + sw), min(buf.shape[0], y0 + sh)
    if xa >= xb or ya >= yb: return
    p = s[ya - y0:yb - y0, xa - x0:xb - x0]; buf[ya:yb, xa:xb] = buf[ya:yb, xa:xb] * (1 - p[..., 3:4]) + p
def blit(buf, s, cx, cy):
    sh, sw = s.shape[:2]; x0 = int(round(cx - sw / 2)); y0 = int(round(cy - sh / 2)); xa, ya = max(0, x0), max(0, y0); xb, yb = min(buf.shape[1], x0 + sw), min(buf.shape[0], y0 + sh)
    if xa >= xb or ya >= yb: return
    p = s[ya - y0:yb - y0, xa - x0:xb - x0]; buf[ya:yb, xa:xb] = buf[ya:yb, xa:xb] * (1 - p[..., 3:4]) + p[..., :3]

def draw_bh(a, R, hot, t):
    """a：(H,W,3) uint8 の絵に、ブラックホールを描きこむ。
       まわりの景色は、ふちに近いほど外へ引きのばす（光が曲がる）。ふちに細い光の輪、その外にうすい光。飲みこむ量（hot）が多いほど明るい。中は黒"""
    ext = int(1.85 * R + 24); x0, x1 = max(0, CX - ext), min(W, CX + ext); y0, y1 = max(500, int(YCB - ext)), min(H, int(YCB + ext))
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32); dx, dy = xx - CX, yy - YCB; r = np.sqrt(dx * dx + dy * dy) + 1e-3
    w = np.clip((1.8 * R - r) / (.8 * R), 0, 1) ** 2; rs = r - .40 * R * (R / np.maximum(r, .7 * R)) ** 2 * w
    src = cv2.remap(a, CX + dx / r * rs, YCB + dy / r * rs, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    spot = .5 + .5 * np.cos(np.arctan2(dy, dx) - 2 * math.pi * t / 1.7)                                    # ふちを回る明るい所（まわりの光は回っている）
    ring = np.exp(-((r - R - max(2.0, min(9.0, .035 * R))) / max(1.8, min(5.5, .030 * R))) ** 2) * (.42 + .26 * hot + .22 * spot)   # 輪は、大きくなっても太くしない
    halo = np.exp(-np.clip(r - R, 0, None) / (min(.20 * R, 46.0) + 6)) * (r > R) * (.08 + .11 * hot) * (.7 + .3 * spot)
    src += ring[..., None] * np.array([255, 226, 190], np.float32) + halo[..., None] * np.array([255, 150, 70], np.float32)
    src *= 1 - np.clip((R - r) / 1.5 + .5, 0, 1)[..., None]; a[y0:y1, x0:x1] = np.clip(src, 0, 255).astype(np.uint8)

class Renderer:
    def __init__(s): s.act = Act(); s.yv = {}; s.q = deque(); s.pres = np.zeros(NT); s.lastt = None; s.rbh = None
    def sub(s, t, dt):
        """ある瞬間の星の絵（描く範囲だけ）。位置はなめらかに追いつかせる"""
        buf = np.zeros((RH, RW, 4), np.float32)
        st, base = stack(t, s.act.upto(t)); kk = 1 - math.exp(-dt / .028) if dt > 0 else 1.0; live = set()
        for i, k, y in st:
            live.add(i); yv = s.yv.get(i, y); yv += (y - yv) * kk; s.yv[i] = yv; age = t - ents[i][1]
            if k == 5: continue                                                                             # ブラックホールは、あとで全体の絵に描く
            pop = 1 + (.24 * math.exp(-age / .075) if (k > 0 and (ents[i][2] - ents[i][1]) > .12) else 0)
            blit4(buf, sprite(k, RAD[k] * pop), CX - RX0, yv - RY0)
        for i in [i for i in s.yv if i not in live]: del s.yv[i]
        return buf, st
    def frame(s, fi):
        t = fi / FPS - LEAD; dt_f = 1 / FPS
        if s.lastt is None or abs((t - dt_f) - s.lastt) > 1e-6: s.q.clear(); s.yv.clear(); s.act = Act(); s.rbh = None   # 途中から描くとき
        s.lastt = t; nd = int(np.searchsorted(TN, t, "right")); di = DI[max(1, min(NDROP, nd if nd else 1))] if t < T[NDROP] + .02 else 1.0
        if TBH - 1.2 < t < T[NBH + 1] - .1: di = 1.0
        K = 1 if di > .1 else (3 if di > .03 else 6); win = 1 if di > .07 else (2 if di > .04 else (3 if di > .02 else 4))
        acc = np.zeros((RH, RW, 4), np.float32); st = []; pr = np.zeros(NT)
        for q in range(K):                                                                                 # 1コマを細かい時間に分けて描き、ならす（速いほど流れて見える）
            ts = t - dt_f + (q + 1) * dt_f / K; b, st = s.sub(ts, dt_f / K); lo = int(np.searchsorted(TN, ts, "right"))
            for n in range(lo + 1, min(NDROP, lo + 80) + 1):                                               # まだ着いていない太陽（空中）
                tau = ts - EMIT[n]
                if tau >= 0: blit4(b, sprite(0, RAD[0]), CX - RX0, YNOZ + V0[n] * tau + .5 * G * tau * tau - RY0)
            acc += b
            for i, k, y in st: pr[k] += 1.0 / K
        s.q.append(acc / K)
        while len(s.q) > win: s.q.popleft()
        lay = sum(s.q) / len(s.q); roi = BGROI * (1 - lay[..., 3:4]) + lay[..., :3]; s.pres += (np.minimum(pr, 1) - s.pres) * (1 - math.exp(-dt_f / .07))
        im = BG.copy(); im.paste(Image.fromarray((np.clip(roi, 0, 1) * 255).astype(np.uint8)), (RX0, RY0)); im = Image.alpha_composite(im.convert("RGBA"), FRONT)
        if t >= TBH:                                                                                        # ブラックホール：重さに比例する半径。なめらかに追いつかせる
            tgt = Rb(max(NBH, nd)); s.rbh = tgt if s.rbh is None else s.rbh + (tgt - s.rbh) * (1 - math.exp(-dt_f / .06))
            hot = min(1.0, (nd - int(np.searchsorted(TN, t - .15, "right"))) / 6.0) if nd > NBH else max(0.0, 1 - (t - TBH) / .5)
            arr = np.asarray(im.convert("RGB")).copy(); draw_bh(arr, s.rbh, hot, t); im = Image.fromarray(arr).convert("RGBA")
            if t - TBH < .24:                                                                               # つぶれる瞬間：赤い星が、穴の中へちぢんで消える
                sp = to_pil(sprite(4, max(3.0, RAD[4] * (1 - (t - TBH) / .24) ** 1.6))); im.alpha_composite(sp, (int(CX - sp.width / 2), int(YCB - sp.height / 2)))
        add = Image.new("RGB", (W, H), (0, 0, 0)); ad = ImageDraw.Draw(add); ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        ypos = {k: y for i, k, y in st}
        for tm, j, n, first, ts in merges:                                                                 # 合体の光の輪（合体が終わった瞬間から広がる）
            if tm > t: break
            life = 1.3 if j == 5 else (.55 if first else .36)
            if t - tm > life: continue
            p = (t - tm) / life; y = YCB if j == 5 else ypos.get(j, None)
            if y is None: continue
            R = RAD[j] if j < 5 else 46.0; c = GLOW[j]; a = (1 - p) ** 1.6 * (.9 if first else .62)
            for w_, r1 in ((max(2, int(R * .075)), R * (1.05 + (2.6 if j == 5 else (1.5 if first else .95)) * p)),) + (((2, R * (1.05 + 3.0 * p)),) if first else ()):
                ad.ellipse([CX - r1, y - r1, CX + r1, y + r1], outline=tuple(int(v * a) for v in c), width=w_)
        if 1 <= nd <= NBH and DI[nd] > .05 and t - T[nd] < .16:                                            # 太陽が着いた小さい輪（ゆっくりの間だけ）
            p = (t - T[nd]) / .16; r1 = RAD[0] * (1.0 + .9 * p); a = (1 - p) * .5; ad.ellipse([CX - r1, YTOP[nd] - r1, CX + r1, YTOP[nd] + r1], outline=tuple(int(v * a) for v in GLOW[0]), width=2)
        for k in range(NT):                                                                                # 上の列：今ある星が明るい。まだできていない星は「？」
            x = IX[k]; known = k == 0 or (k in FIRST and FIRST[k] <= t)
            if not known:
                d.ellipse([x - 25, IY - 25, x + 25, IY + 25], outline=(120, 130, 170, 150), width=2); d.text((x, IY), "?", font=fQ, fill=(130, 140, 180, 200), anchor="mm"); continue
            b = float(min(1, s.pres[k])); ic = ICON[k]; ov.alpha_composite(ICON_DIM[k], (x - ic.width // 2, IY - ic.height // 2))
            if b > .02: ov.paste(ic, (x - ic.width // 2, IY - ic.height // 2), ic.split()[3].point(lambda v, b=b: int(v * b)))
            e = t - FIRST.get(k, -9)
            if 0 <= e < .6: r1 = 27 + 16 * e / .6; a = (1 - e / .6); ad.ellipse([x - r1, IY - r1, x + r1, IY + r1], outline=tuple(int(v * a * .9) for v in GLOW[k]), width=3)
            g_ = int(120 + 135 * b); d.text((x, IY + 46), str(2 ** k), font=fW, fill=(g_, g_, min(255, g_ + 10), 255), anchor="mm")
        d.text((862, 560), "Suns dropped" if EN else "落とした太陽", font=fUnit, fill=(196, 202, 224, 255), anchor="mm", stroke_width=3, stroke_fill=INK + (255,))
        d.text((862, 632), str(nd), font=fCnt, fill=(244, 244, 250, 255), anchor="mm", stroke_width=4, stroke_fill=INK + (255,))
        if nd > NBH:                                                                                       # ブラックホールの半径（重さに比例）
            m = min(nd, NDROP); d.text((862, 724), "Black hole radius" if EN else "ブラックホールの半径", font=fSmall, fill=(196, 202, 224, 255), anchor="mm", stroke_width=3, stroke_fill=INK + (255,))
            d.text((862, 782), f"×{m / NBH:.1f}", font=ImageFont.truetype(FI, 56), fill=(255, 226, 122, 255), anchor="mm", stroke_width=4, stroke_fill=INK + (255,))
        for j, tm in FIRST.items():                                                                        # 初めての星：重さと、同じくらいの実際の星（管の左）
            e = t - tm
            if j == 5 or e < 0 or e > 1.7: continue
            a = min(1, e / .08) * min(1, (1.7 - e) / .3); y = min(1370, max(600, ypos.get(j, YB - RAD[j]))) - 14 * min(1, e / .5); A = int(255 * a)
            s1 = f"= {2 ** j} Suns" if EN else f"太陽 {2 ** j}個ぶん"
            d.text((198, y), s1, font=fit(s1, 56, 360), fill=(255, 226, 122, A), anchor="mm", stroke_width=5, stroke_fill=INK + (A,))
            d.text((198, y + 60), LIKE[j], font=fit(LIKE[j], 38, 360), fill=(248, 248, 252, A), anchor="mm", stroke_width=4, stroke_fill=INK + (A,))
        if TBH <= t < T[NBH + 1] + .25:                                                                    # ブラックホールの誕生
            e = t - TBH; a = min(1, e / .2) * min(1, (T[NBH + 1] + .25 - t) / .25); A = int(255 * a); s1 = "Black hole" if EN else "ブラックホール"; s2 = "= 32 Suns" if EN else "太陽 32個ぶん"
            d.text((W / 2, 1010 - 16 * min(1, e / .6)), s1, font=fit(s1, 120, 980), fill=(255, 226, 122, A), anchor="mm", stroke_width=8, stroke_fill=INK + (A,))
            d.text((W / 2, 1118 - 16 * min(1, e / .6)), s2, font=fnt(56), fill=(248, 248, 252, A), anchor="mm", stroke_width=6, stroke_fill=INK + (A,))
        def two(lines, ta, tb):                                                                            # 下の2行
            if not ta <= t < tb: return
            A = int(255 * min(1, (t - ta) / .25) * min(1, (tb - t) / .3))
            for q, sx in enumerate(lines): d.text((W / 2, 1640 + 52 * q), sx, font=fit(sx, 36, 900), fill=(226, 230, 246, A), anchor="mm", stroke_width=4, stroke_fill=INK + (A,))
        two(("Stars heavier than about 20 Suns", "can end as black holes") if EN else ("太陽の約20倍より重い星は、", "最後にブラックホールになることがある"), TBH + .25, TBH + 4.3)
        two(("Every star it swallows adds mass.", "Its radius grows in proportion to mass") if EN else ("飲みこむたびに、重くなる。", "半径は、重さに比例して大きくなる"), TBH + 4.5, T[NDROP] + .1)
        if t >= T[NDROP] + .15:                                                                            # おわり：黒い穴の中に、結果
            e = t - T[NDROP] - .15; A = int(255 * min(1, e / .3)); s1 = "512 Suns" if EN else "太陽 512個ぶん"; s2 = "16× the radius" if EN else "半径は 16倍"
            d.text((W / 2, YCB - 60), s1, font=fit(s1, 84, 760), fill=(248, 248, 252, A), anchor="mm"); d.text((W / 2, YCB + 44), s2, font=fit(s2, 60, 760), fill=(255, 226, 122, A), anchor="mm")
        im = Image.alpha_composite(im, ov).convert("RGB"); im = ImageChops.add(im, add)
        src = add.copy(); src.paste(Image.fromarray((np.clip((roi - .62) * 1.2, 0, 1) * 255).astype(np.uint8)), (RX0, RY0))                # にじみ：星の明るい所と光の輪だけ、ひかえめ（文字は光らせない）
        bl = src.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(7)).resize((W, H), Image.BILINEAR)
        im = ImageChops.add(im, bl); g = min(1.0, (t + LEAD) / .3, (DUR - t - LEAD) / .4)
        return im if g >= .999 else Image.fromarray((np.asarray(im, np.float32) * max(0.0, g)).astype(np.uint8))

if __name__ == "__main__":
    st = os.environ.get("STILLS"); R_ = Renderer()
    if os.environ.get("INFO"):
        print("長さ", round(DUR, 2), "秒 / 先頭の余白", round(LEAD, 3), "/ ブラックホール", round(TBH + LEAD, 2), "秒 / 流れの再開", round(T[NBH + 1] + LEAD, 2), "秒 / 512個め", round(T[NDROP] + LEAD, 2), "秒")
        for j, tm in sorted(FIRST.items()): print("  初めての段", j, "（太陽", 2 ** j, "個ぶん）映像の", round(tm + LEAD, 3), "秒")
        sys.exit()
    if st:
        for x in st.split(","):
            f0 = int(float(x) * FPS); im = None
            for fi in range(max(0, f0 - 8), f0 + 1): im = R_.frame(fi)
            im.save(f"{B}/s_{float(x):05.2f}.jpg", quality=90)
        sys.exit()
    nn = audio(f"{B}/a.wav")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", f"{B}/a.wav",
                          "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    for fi in range(NF): p.stdin.write(R_.frame(fi).tobytes())
    p.stdin.close(); p.wait(); print(OUT, round(DUR, 2), "秒 音", nn, "個")
