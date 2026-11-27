# mergehole.py — 同じ星が2つ重なると、1つ重い星になる。太陽を落とし続けると、ブラックホールになる（mergecol の続き。縦のショート）
#   持ち主 11/27：mergecol1（月→太陽）が公開35時間で 8,739 回・平均視聴割合 114.7%・直近10本で1位 →「これ系伸びそう」
#   同じなのは、決まり（同じ星が2つ重なると合体）・管・落とす速さ（数が2倍になるたびに速さも2倍）。変えたのは、問い・星・結末：
#     ・落とすのは太陽。重さは 1 → 2 → 4 → 8 → 16 → 32 と倍になり、64個めでブラックホールになる
#       実際の星の重さ（太陽＝1。2026-11-27 に確認）：シリウス 2.06、レグルス 4.15、ベラトリックス 8.4、ベテルギウス 10〜20（14 とする資料が多い）、アルニタク 33±10。
#       太陽の約20倍より重い星は、一生の最後にブラックホールになることがある（どこから必ずそうなるかは、まだはっきりしていない）
#     ・ブラックホールになったあとは、落ちてきた太陽をぜんぶ飲みこむ。重さ＝落とした数。半径は重さに比例する（シュワルツシルト半径）。512個で半径8倍
#   見本への持ち主の指摘（11/27）と、直した所：
#     ・「ブラックホールのリアリティが欲しい」→ 黒い円と輪をやめ、光の道すじを計算して描く（シュワルツシルトの時空で、光が曲がる式 d²u/dφ² = −u + 1.5u² を解く）。
#       まわりを回るガスの円盤を、ほぼ真横（78°）から見た形：手前の帯、穴の上と下に回りこんで見える奥の円盤、ふちの細い光の輪。
#       近づいてくる側（左）は明るく白く、遠ざかる側（右）は暗く赤い（ドップラー効果と、重力で光が赤くなる効果）。内側ほど速く回る。飲みこむ量が多いほど明るい。
#       うしろの星と管は、穴のまわりで外へ引きのばされ、ふちのすぐ外では反対側の景色が裏返って見える。落ちていく太陽は、ふちに近づくほど赤く暗くなって消える
#     ・「星が綺麗なのでもう少し見たい。回転してたりするとなおいい」→ 星を1段ふやし（32個ぶん＝青い超巨星）、大きくし、1つずつ自転させた（重い星ほど・赤い超巨星ほどゆっくり）
#     ・「これ系のやつは心地よい音にエコーたしていい。裏に低音入れてもいい。ベースは2.3.4で」→ 当たる音（木・竹・空洞の順に回す。この動画は竹）にエコーを足し、裏にカノン進行の低い持続音
#   音：当たった瞬間に1打ずつ（着地・合体のはじまり・ブラックホールの誕生・飲みこみ）。大きい星ほど低い。2段・3段と続けて合体するときは、1段ごとに音がずれて重なる（11/26 持ち主）
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
NT, NBH, NDROP = 7, 64, 512                                           # 段の数（0〜5 は星、6 はブラックホール）／ブラックホールになる個数／落とす数
LIKE = ["", "about Sirius", "about Regulus", "about Bellatrix", "about Betelgeuse", "about Alnitak", ""] if EN else ["", "シリウスくらい", "レグルスくらい", "ベラトリックスくらい", "ベテルギウスくらい", "アルニタクくらい", ""]
RAD = [24.0, 31.0, 40.0, 52.0, 70.0, 92.0, 37.5]                       # 列の中の半径（px）。最後はブラックホールの影の、はじめの半径
GLOW = [(255, 206, 96), (226, 234, 255), (176, 200, 255), (140, 172, 255), (255, 140, 84), (150, 168, 255), (255, 206, 160)]
TILT = [0.0, .3, -.2, .4, .15, -.25, 0.0]
PERIOD = [5.0, 4.2, 2.4, 3.4, 9.0, 6.5]                                # 自転の周期（秒）。赤い超巨星はゆっくり
NPH = 40                                                              # 自転の向きを何枚の絵で持つか（となりどうしを混ぜて、なめらかに回す）
STAR = [((255, 196, 70), (255, 238, 156), (244, 146, 36), (3., 6., 12.)),      # 太陽：黄
        ((228, 234, 255), (255, 255, 255), (186, 204, 250), (3., 6., 12.)),    # 太陽2個ぶん：白（シリウスくらい）
        ((178, 202, 255), (226, 238, 255), (136, 168, 250), (3., 6., 12.)),    # 4個ぶん：青白（レグルスくらい）
        ((140, 174, 255), (200, 222, 255), (100, 136, 244), (3., 6., 12.)),    # 8個ぶん：青（ベラトリックスくらい）
        ((255, 132, 66), (255, 190, 116), (206, 76, 36), (1.6, 3.2, 6.4)),     # 16個ぶん：赤い超巨星（ベテルギウスくらい）。大きな対流の模様
        ((118, 146, 255), (196, 212, 255), (78, 100, 232), (2.2, 4.4, 8.8))]   # 32個ぶん：青い超巨星（アルニタクくらい）

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
def sprite(k, Rp, ph=0, ss=3):
    """前もって不透明度を掛けた RGBA（float32）。星は自分で光る（ふちにやわらかい光）。ph＝自転の向き（0〜NPH-1）。k=6 はブラックホールの小さい絵（上の列用）"""
    key = (k, round(Rp * 2) / 2, ph % NPH if k < 6 else 0)
    if key in _SPR: return _SPR[key]
    Rp = key[1]; ss = 2 if Rp > 60 else ss
    half = int(math.ceil(Rp * 1.45)) + 2; S = 2 * half; n = S * ss
    c = (np.arange(n, dtype=np.float32) + .5) / ss - half; xx, yy = np.meshgrid(c, c)
    rr = np.hypot(xx, yy) / Rp; nx, ny = xx / Rp, yy / Rp; nz = np.sqrt(np.clip(1 - rr * rr, 0, 1)); o = np.zeros((n, n, 4), np.float32)
    al = np.clip((1 - rr) * Rp * ss + .5, 0, 1); o[..., 3] = al
    if k == 6:
        band = np.exp(-(ny / .16) ** 2) * (np.abs(nx) < 2.0) * (rr > .9); o[..., :3] += (np.exp(-((rr - 1.07) / .075) ** 2) * .9 + band * .55)[..., None] * np.asarray((255, 214, 170), np.float32) / 255
    else:
        ca, sa = math.cos(TILT[k]), math.sin(TILT[k]); u = nx * ca + ny * sa; v = -nx * sa + ny * ca; a = 2 * math.pi * key[2] / NPH; cr, sr_ = math.cos(a), math.sin(a)
        P = np.stack([u * cr + nz * sr_, v, -u * sr_ + nz * cr], -1).astype(np.float32); rgb = tex(k, P) * (.72 + .28 * nz ** .55)[..., None]   # 軸のまわりに回す。ふちへ行くほど少し暗い
        o[..., :3] = np.clip(rgb, 0, 255) / 255 * al[..., None]
        hl = np.exp(-(np.clip(rr - 1, 0, None) / .15) ** 1.25) * .38 * (rr > 1); o[..., :3] += hl[..., None] * np.asarray(GLOW[k], np.float32) / 255   # やわらかい光のふち（光らせすぎない）
    o = o.reshape(S, ss, S, ss, 4).mean((1, 3)); _SPR[key] = o; return o
def star(k, x, pop=1.0):
    """自転している星の絵。x＝回った回数（小数）。pop＝合体した直後のふくらみ"""
    f = (x % 1.0) * NPH; i0 = int(f); w = f - i0; a = sprite(k, RAD[k], i0)
    if w > .02: a = a * (1 - w) + sprite(k, RAD[k], i0 + 1) * w
    if pop > 1.01: n = int(round(a.shape[0] * pop)); a = cv2.resize(a, (n, n), interpolation=cv2.INTER_LINEAR)
    return a
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
FIN = [.11, .13, .15, .18, .22, .2814]                                 # 64個め：下の段へ、だんだんゆっくり合体していく（合わせて2拍）
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
YCB = YB - RAD[5]                                                     # ブラックホールの中心（動かない。最後の2つの星が合体した所）
RX0, RY0, RW, RH = CX - 176, YNOZ, 352, 1446 - YNOZ                   # 星を描く範囲（ここだけ細かい時間で描いてならす）
def Rb(m): return RAD[6] * max(1.0, m / NBH)                          # ブラックホールの影の半径：重さ（＝落とした数）に比例
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
    else: YTOP[n] = YCB - Rb(n - 1) + RAD[0] * .4                     # 影のふちに半分かくれた所で消える
    D = YTOP[n] - YNOZ; V0[n] = max(300.0, 52.0 / DI[n]); EMIT[n] = T[n] - (-V0[n] + math.sqrt(V0[n] ** 2 + 2 * G * D)) / G
TN = np.array([T[n] for n in range(1, NDROP + 1)]); LEAD = -(EMIT[1] - .18); DUR = TEND + LEAD; NF = int(DUR * FPS)
FIRST = {j: tm for tm, j, n, first, ts in merges if first}

# ---------- 音：当たった瞬間に1打ずつ。エコーと、裏の低い持続音（合体の型だけ） ----------
def chord_i(t): return int(math.floor((t + 1e-6) / SLOT)) % 8
def audio(path):
    a = TKIT.Audio(DUR, lo=62, hi=90, mat=MAT, max_same=3); K = TKIT.K; N = int(SR * DUR)
    for n in range(1, NBH + 1):
        if n % 2: a.hit(T[n] + LEAD, .97, vel=.36, chord=chord_i(T[n]))                                   # 着いただけ（合体しない）：小さく高い1打
    for tm, j, n, first, ts in merges:
        a.hit(ts + LEAD, .82 - .155 * j if j < 6 else .20, vel=.48 + .075 * j if j < 6 else .80, chord=chord_i(ts))   # 2つが触れた瞬間。大きい星ほど低く、強い
    a.hit(TBH + LEAD, 0.0, vel=1.0, chord=chord_i(TBH))                                                    # ブラックホールの誕生：いちばん低い1打
    for n in range(NBH + 1, NDROP + 1):                                                                    # 飲みこむ1個ごとに1打。重くなるほど低い
        a.hit(T[n] + LEAD, max(0.0, .70 - .22 * math.log2(n / NBH)), vel=max(.2, .40 * (DI[n] / DI[NBH + 1]) ** .22), chord=chord_i(T[n]))
    # 裏の低い持続音：カノン進行の根音（2拍で1つ）。ブラックホールができてからは少し大きく
    off = int(SR * LEAD); under = np.zeros(N, np.float32); pre = K.pad([(50, 62, 69)], LEAD + .6, LEAD + .6, .045); under[: min(N, len(pre))] += pre[:N]
    body = K.pad([(r, r + 12, f5 + 12) for (r, t3, f5) in K.CANON], SLOT, DUR - LEAD + .5, .055); under[off:] += body[: N - off]
    tt = np.arange(N) / SR; under *= (1 + .55 * np.clip((tt - (TBH + LEAD)) / 1.5, 0, 1)) * np.minimum(1, (DUR - tt) / 1.2)
    return a.write(path, room=(.20, 1.5), under=under)

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
IX = [int(W / 2 + (k - 3) * 118) for k in range(NT)]; IY = 356
ICON = [to_pil(sprite(k, 24.0 if k < 6 else 17.0)) for k in range(NT)]
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

# ---------- ブラックホール：光の道すじを計算して描く（長さの単位はシュワルツシルト半径 rs＝1） ----------
INC, ROLL = math.radians(78.0), math.radians(-7.0)                    # 円盤を見る角度（0°＝真上から）、画面の中での傾き
RIN, ROUT = 3.0, 6.4                                                  # 円盤の内側（いちばん内側の安定な軌道＝3rs）と外側
BCRIT = 1.5 * math.sqrt(3.0)                                          # 影のふち（これより内側を通る光は飲みこまれる）＝2.598rs
EXT = ROUT + .35; OMEGA0 = 2 * math.pi / 1.9                          # 絵にする範囲／内側のふちが1周する速さ
def geodesics(dphi=.002):
    """光の道すじ u(φ)＝1/r を、中心からのずれ b ごとに解く：d²u/dφ² = −u + 1.5u²（u=0, du/dφ=1/b から）。u>=1 で飲みこまれ、u<0 で遠くへ去る"""
    b = np.concatenate([BCRIT - np.geomspace(2.45, 1e-4, 260), BCRIT + np.geomspace(1e-4, 13.0, 560)]); n = int((3 * math.pi + .3) / dphi)
    u = np.zeros_like(b); w = 1 / b; U = np.empty((len(b), n), np.float32); stt = np.zeros(len(b), np.int8)
    f = lambda u_, w_: (w_, -u_ + 1.5 * u_ * u_)
    for q in range(n):
        U[:, q] = np.where(stt == 0, u, np.where(stt == 1, 2.0, -1.0))
        k1 = f(u, w); k2 = f(u + .5 * dphi * k1[0], w + .5 * dphi * k1[1]); k3 = f(u + .5 * dphi * k2[0], w + .5 * dphi * k2[1]); k4 = f(u + dphi * k3[0], w + dphi * k3[1])
        go = stt == 0; u = np.where(go, u + dphi / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]), u); w = np.where(go, w + dphi / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]), w)
        stt = np.where(go & (u >= 1.0), 1, stt); stt = np.where(go & (u < 0) & (q > 2), 2, stt).astype(np.int8)
    return b, dphi, U
GB, GDPHI, GU = geodesics()
def look(b, phi):
    """ずれ b の光が、角度 φ まで進んだ時の 1/r。飲みこまれた後・去った後は ok=False"""
    bi = np.interp(b, GB, np.arange(len(GB))); i0 = np.clip(bi.astype(np.int32), 0, len(GB) - 2); fb = (bi - i0).astype(np.float32)
    pj = phi / GDPHI; j0 = np.clip(pj.astype(np.int32), 0, GU.shape[1] - 2); fp = (pj - j0).astype(np.float32)
    a00, a01, a10, a11 = GU[i0, j0], GU[i0, j0 + 1], GU[i0 + 1, j0], GU[i0 + 1, j0 + 1]
    ok = (a00 > 0) & (a00 < 1) & (a01 > 0) & (a01 < 1) & (a10 > 0) & (a10 < 1) & (a11 > 0) & (a11 < 1)
    return a00 * (1 - fb) * (1 - fp) + a01 * (1 - fb) * fp + a10 * fb * (1 - fp) + a11 * fb * fp, ok
NRAD, NPSI = 128, 2048
def disk_texture():
    """円盤の濃淡：回る向きに長くのびた筋"""
    from scipy.ndimage import gaussian_filter
    rng = np.random.default_rng(8); x = rng.normal(0, 1, (NRAD, NPSI)).astype(np.float32)
    t = gaussian_filter(x, (1.8, 26), mode=("nearest", "wrap")) * 5 + gaussian_filter(x, (.8, 7), mode=("nearest", "wrap")) * 1.3
    t = (t - t.min()) / (t.max() - t.min()); return (t ** 1.5).astype(np.float32)
DTEX = disk_texture()
_tc = np.array([.30, .50, .80, 1.05, 1.35], np.float32); _cc = np.array([(.80, .22, .06), (.96, .40, .11), (1.0, .66, .30), (1.0, .90, .74), (.92, .95, 1.0)], np.float32)
_rr = np.linspace(RIN, ROUT, 400); I0MAX = float(((RIN / _rr) ** 3 * (1 - np.sqrt(RIN * .93 / _rr))).max())
def bh_maps(N):
    """絵の1点1点について、そこに届く光が円盤のどこから来たかを前もって求める（手前から順に3回まで：じかに見える円盤、穴を回りこんだ円盤、もう1周した光の輪）"""
    ax = ((np.arange(N, dtype=np.float32) + .5) / N * 2 - 1) * EXT; X, Y = np.meshgrid(ax, -ax); cr, sr_ = math.cos(ROLL), math.sin(ROLL)
    Xr = X * cr + Y * sr_; Yr = -X * sr_ + Y * cr; b = np.hypot(Xr, Yr) + 1e-6; ex, ey = Xr / b, Yr / b; ci, si = math.cos(INC), math.sin(INC)
    phi0 = np.arctan2(ey * si, ci) + math.pi / 2; ks = []
    for k in range(3):
        ph = phi0 + k * math.pi; u, ok = look(b, ph); r = 1 / np.maximum(u, 1e-6); a = (sstep(RIN - .02, RIN + .22, r) * (1 - sstep(ROUT - 1.5, ROUT, r)) * ok).ravel()
        idx = np.flatnonzero(a > .003); r_ = r.ravel()[idx]; sp, cp = np.sin(ph).ravel()[idx], np.cos(ph).ravel()[idx]; ex_, ey_ = ex.ravel()[idx], ey.ravel()[idx]
        psi = np.arctan2(sp * ey_ * r_ * ci - cp * r_ * si, sp * ex_ * r_)                                # 円盤の上での向き
        beta = np.sqrt(.5 / (r_ - 1)); g = np.sqrt(1 - beta ** 2) / (1 - beta * (-si * sp * ex_)) * np.sqrt(1 - 1 / r_)   # 回る速さによるドップラー効果 × 重力で光が赤くなる効果
        I0 = (RIN / r_) ** 3 * (1 - np.sqrt(RIN * .93 / r_)) / I0MAX; tcol = I0 ** .25 * g
        col = np.stack([np.interp(tcol, _tc, _cc[:, q]) for q in range(3)], -1).astype(np.float32)
        ks.append(dict(idx=idx, a=a[idx].astype(np.float32), E=((I0 * g ** 2.0) ** .8).astype(np.float32), col=col, om=(OMEGA0 * (RIN / r_) ** 1.5).astype(np.float32), psi=psi.astype(np.float32),
                       ri=np.clip(((r_ - RIN) / (ROUT - RIN) * (NRAD - 1)).astype(np.int32), 0, NRAD - 1)))
    return dict(N=N, k=ks, cap=(b < BCRIT).ravel())
_MAPS = {}
def bh_image(size, t, lum):
    """ブラックホールと円盤の絵（一辺 size px。色は前もって濃さを掛けたもの＋濃さ）"""
    N = next((n for n in (200, 390, 780, 1560) if n >= size), 1560)
    if N not in _MAPS: _MAPS[N] = bh_maps(N)
    M = _MAPS[N]; rgb = np.zeros((N * N, 3), np.float32); tr = np.ones(N * N, np.float32)
    for k in M["k"]:
        tx = DTEX[k["ri"], (((k["psi"] - k["om"] * t) / (2 * math.pi)) % 1.0 * NPSI).astype(np.int32) % NPSI]
        w = tr[k["idx"]] * k["a"]; rgb[k["idx"]] += k["col"] * (k["E"] * (.38 + 1.05 * tx) * lum * w)[:, None]; tr[k["idx"]] *= 1 - k["a"]
    al = 1 - tr; al[M["cap"]] = 1.0; rgb = 1 - np.exp(-1.5 * rgb); out = np.dstack([rgb.reshape(N, N, 3), al.reshape(N, N)])
    return out if N == size else cv2.resize(out, (size, size), interpolation=cv2.INTER_AREA)
def draw_bh(a, R, t, lum):
    """a：(H,W,3) uint8 の絵に、ブラックホールを描きこむ。R＝影の半径（px）。戻り値：円盤の絵と置いた場所（にじみ用）
       1) うしろの景色（星・管）：穴のまわりで外へ引きのばす。ふちのすぐ外（アインシュタインの輪の内側）では、反対側の景色が裏返って見える
       2) その上に、光の道すじから求めた円盤と影をのせる"""
    RE = 1.4 * R; ext = int(2.6 * R + 8); x0, x1 = max(0, CX - ext), min(W, CX + ext); y0, y1 = max(500, int(YCB - ext)), min(H, int(YCB + ext))
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32); dx, dy = xx - CX, yy - YCB; r = np.sqrt(dx * dx + dy * dy) + 1e-3
    rs = r - np.clip((2.6 * R - r) / (.9 * R), 0, 1) ** 2 * RE * RE / r
    a[y0:y1, x0:x1] = cv2.remap(a, CX + dx / r * rs, YCB + dy / r * rs, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    size = int(round(2 * EXT * R / BCRIT)); im = bh_image(size, t, lum); bx, by = int(round(CX - size / 2)), int(round(YCB - size / 2))
    xa, ya, xb, yb = max(0, bx), max(0, by), min(W, bx + size), min(H, by + size); sp = im[ya - by:yb - by, xa - bx:xb - bx]
    a[ya:yb, xa:xb] = np.clip(a[ya:yb, xa:xb] * (1 - sp[..., 3:4]) + sp[..., :3] * 255, 0, 255).astype(np.uint8)
    return sp[..., :3], (xa, ya)
_yy, _xx = np.mgrid[RY0:RY0 + RH, RX0:RX0 + RW].astype(np.float32); DROI = np.hypot(_xx - CX, _yy - YCB)   # 星を描く範囲の各点から、ブラックホールの中心までの距離

class Renderer:
    def __init__(s): s.act = Act(); s.yv = {}; s.q = deque(); s.pres = np.zeros(NT); s.lastt = None; s.rbh = None; s.hot = 0.0
    def sub(s, t, dt):
        """ある瞬間の星の絵（描く範囲だけ）。位置はなめらかに追いつかせる。星は1つずつ自転している"""
        buf = np.zeros((RH, RW, 4), np.float32)
        st, base = stack(t, s.act.upto(t)); kk = 1 - math.exp(-dt / .028) if dt > 0 else 1.0; live = set()
        for i, k, y in st:
            live.add(i); yv = s.yv.get(i, y); yv += (y - yv) * kk; s.yv[i] = yv; age = t - ents[i][1]
            if k == 6: continue                                                                             # ブラックホールは、あとで全体の絵に描く
            pop = 1 + (.24 * math.exp(-age / .075) if (k > 0 and (ents[i][2] - ents[i][1]) > .12) else 0)
            blit4(buf, star(k, t / PERIOD[k] + i * .37, pop), CX - RX0, yv - RY0)
        for i in [i for i in s.yv if i not in live]: del s.yv[i]
        lo = int(np.searchsorted(TN, t, "right"))
        for n in range(lo + 1, min(NDROP, lo + 80) + 1):                                                   # まだ着いていない太陽（空中）
            tau = t - EMIT[n]
            if tau >= 0: blit4(buf, star(0, t / PERIOD[0] + n * .37), CX - RX0, YNOZ + V0[n] * tau + .5 * G * tau * tau - RY0)
        return buf, st
    def frame(s, fi):
        t = fi / FPS - LEAD; dt_f = 1 / FPS
        if s.lastt is None or abs((t - dt_f) - s.lastt) > 1e-6: s.q.clear(); s.yv.clear(); s.act = Act(); s.rbh = None; s.hot = 0.0   # 途中から描くとき
        s.lastt = t; nd = int(np.searchsorted(TN, t, "right")); di = DI[max(1, min(NDROP, nd if nd else 1))] if t < T[NDROP] + .02 else 1.0
        if TBH - 1.2 < t < T[NBH + 1] - .1: di = 1.0
        K = 1 if di > .1 else (3 if di > .03 else 6); win = 1 if di > .07 else (2 if di > .04 else (3 if di > .02 else 4))
        acc = np.zeros((RH, RW, 4), np.float32); st = []; pr = np.zeros(NT)
        for q in range(K):                                                                                 # 1コマを細かい時間に分けて描き、ならす（速いほど流れて見える）
            b, st = s.sub(t - dt_f + (q + 1) * dt_f / K, dt_f / K); acc += b
            for i, k, y in st: pr[k] += 1.0 / K
        s.q.append(acc / K)
        while len(s.q) > win: s.q.popleft()
        lay = sum(s.q) / len(s.q); s.pres += (np.minimum(pr, 1) - s.pres) * (1 - math.exp(-dt_f / .07)); bh = t >= TBH
        roi = BGROI.copy() if bh else BGROI * (1 - lay[..., 3:4]) + lay[..., :3]                            # ブラックホールができたあとの太陽は、穴の絵の上に、あとで重ねる
        im = BG.copy(); im.paste(Image.fromarray((np.clip(roi, 0, 1) * 255).astype(np.uint8)), (RX0, RY0)); im = Image.alpha_composite(im.convert("RGBA"), FRONT)
        src = Image.new("RGB", (W, H), (0, 0, 0))                                                          # にじみのもと
        if bh:
            tgt = Rb(max(NBH, nd)); s.rbh = tgt if s.rbh is None else s.rbh + (tgt - s.rbh) * (1 - math.exp(-dt_f / .06))   # 半径は重さに比例。なめらかに追いつかせる
            rate = min(1.0, (nd - int(np.searchsorted(TN, t - .15, "right"))) / 6.0) if nd > NBH else max(0.0, 1 - (t - TBH) / .9)
            s.hot += (rate - s.hot) * (1 - math.exp(-dt_f / (.12 if rate > s.hot else .7)))                # 飲みこむ量が多いほど、円盤が明るい。止まると、ゆっくり暗くなる
            arr = np.asarray(im.convert("RGB")).copy(); disk, (bx, by) = draw_bh(arr, s.rbh, t, .58 + .42 * s.hot)
            z = np.clip((DROI - s.rbh) / (s.rbh + 24), 0, 1)[..., None]; fade = z ** .8                      # 落ちていく太陽：影のふちに近づくほど赤く、暗くなって消える（重力で光が赤くなる）
            sun = lay * fade; sun[..., 1] *= (.30 + .70 * z[..., 0]); sun[..., 2] *= (.10 + .90 * z[..., 0])
            reg = arr[RY0:RY0 + RH, RX0:RX0 + RW]; reg[:] = np.clip(reg * (1 - sun[..., 3:4]) + sun[..., :3] * 255, 0, 255).astype(np.uint8)
            if t - TBH < .24:                                                                               # つぶれる瞬間：青い超巨星が、穴の中へちぢんで消える
                sp = to_pil(star(5, t / PERIOD[5], max(.04, (1 - (t - TBH) / .24) ** 1.6))) if False else to_pil(cv2.resize(sprite(5, RAD[5]), None, fx=max(.04, (1 - (t - TBH) / .24) ** 1.6), fy=max(.04, (1 - (t - TBH) / .24) ** 1.6), interpolation=cv2.INTER_AREA))
                im2 = Image.fromarray(arr).convert("RGBA"); im2.alpha_composite(sp, (int(CX - sp.width / 2), int(YCB - sp.height / 2))); arr = np.asarray(im2.convert("RGB")).copy()
            im = Image.fromarray(arr).convert("RGBA")
            src.paste(Image.fromarray((np.clip((disk - .55) * 1.0, 0, 1) * 255).astype(np.uint8)), (bx, by)); roi = np.clip(sun[..., :3], 0, 1)
        add = Image.new("RGB", (W, H), (0, 0, 0)); ad = ImageDraw.Draw(add); ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        ypos = {k: y for i, k, y in st}
        for tm, j, n, first, ts in merges:                                                                 # 合体の光の輪（合体が終わった瞬間から広がる）
            if tm > t: break
            life = 1.3 if j == 6 else (.55 if first else .36)
            if t - tm > life: continue
            p = (t - tm) / life; y = YCB if j == 6 else ypos.get(j, None)
            if y is None: continue
            R = RAD[j] if j < 6 else 60.0; c = GLOW[j]; a = (1 - p) ** 1.6 * (.9 if first else .62)
            for w_, r1 in ((max(2, int(R * .075)), R * (1.05 + (2.6 if j == 6 else (1.5 if first else .95)) * p)),) + (((2, R * (1.05 + 3.0 * p)),) if first else ()):
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
            if j == 6 or e < 0 or e > 1.7: continue
            a = min(1, e / .08) * min(1, (1.7 - e) / .3); y = min(1370, max(600, ypos.get(j, YB - RAD[j]))) - 14 * min(1, e / .5); A = int(255 * a)
            s1 = f"= {2 ** j} Suns" if EN else f"太陽 {2 ** j}個ぶん"
            d.text((198, y), s1, font=fit(s1, 56, 360), fill=(255, 226, 122, A), anchor="mm", stroke_width=5, stroke_fill=INK + (A,))
            d.text((198, y + 60), LIKE[j], font=fit(LIKE[j], 38, 360), fill=(248, 248, 252, A), anchor="mm", stroke_width=4, stroke_fill=INK + (A,))
        if TBH <= t < T[NBH + 1] + .25:                                                                    # ブラックホールの誕生
            e = t - TBH; a = min(1, e / .2) * min(1, (T[NBH + 1] + .25 - t) / .25); A = int(255 * a); s1 = "Black hole" if EN else "ブラックホール"; s2 = f"= {NBH} Suns" if EN else f"太陽 {NBH}個ぶん"
            d.text((W / 2, 940 - 16 * min(1, e / .6)), s1, font=fit(s1, 120, 980), fill=(255, 226, 122, A), anchor="mm", stroke_width=8, stroke_fill=INK + (A,))
            d.text((W / 2, 1048 - 16 * min(1, e / .6)), s2, font=fnt(56), fill=(248, 248, 252, A), anchor="mm", stroke_width=6, stroke_fill=INK + (A,))
        def two(lines, ta, tb):                                                                            # 下の2行
            if not ta <= t < tb: return
            A = int(255 * min(1, (t - ta) / .25) * min(1, (tb - t) / .3))
            for q, sx in enumerate(lines): d.text((W / 2, 1570 + 52 * q), sx, font=fit(sx, 36, 900), fill=(232, 236, 250, A), anchor="mm", stroke_width=5, stroke_fill=INK + (A,))
        two(("Stars heavier than about 20 Suns", "can end as black holes") if EN else ("太陽の約20倍より重い星は、", "最後にブラックホールになることがある"), TBH + .25, TBH + 3.4)
        two(("Every star it swallows adds mass.", "Its radius grows in proportion to mass") if EN else ("飲みこむたびに、重くなる。", "半径は、重さに比例して大きくなる"), TBH + 3.6, T[NDROP] + .1)
        if t >= T[NDROP] + .15:                                                                            # おわり：影の上半分に、結果
            e = t - T[NDROP] - .15; A = int(255 * min(1, e / .3)); s1 = f"{NDROP} Suns" if EN else f"太陽 {NDROP}個ぶん"; s2 = f"{NDROP // NBH}× the radius" if EN else f"半径は {NDROP // NBH}倍"
            d.text((W / 2, YCB - 150), s1, font=fit(s1, 70, 460), fill=(248, 248, 252, A), anchor="mm"); d.text((W / 2, YCB - 64), s2, font=fit(s2, 52, 460), fill=(255, 226, 122, A), anchor="mm")
        im = Image.alpha_composite(im, ov).convert("RGB"); im = ImageChops.add(im, add)
        src = ImageChops.add(src, add); pr_ = Image.fromarray((np.clip((roi - .62) * 1.2, 0, 1) * 255).astype(np.uint8)); box = Image.new("RGB", (W, H), (0, 0, 0)); box.paste(pr_, (RX0, RY0)); src = ImageChops.add(src, box)   # にじみ：星・円盤の明るい所と光の輪だけ、ひかえめ（文字は光らせない）
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
