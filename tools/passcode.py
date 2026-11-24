# passcode.py — 数字キーを押すたびに1音。押す音そのものが重低音（バスドラムのような低い「ドゥン」）。押す速さが上がっていき、ためのあとに4つ打ちで戻る（オーナー 11/25）
#   11/25 オーナー「重低音のベースよ？バスドラムみたいなやつよ？今爽やかすぎん？」→ エレピ・明るい和音・きらきらした響きをやめ、
#   押す音を 808 ふうの低音（歪ませた正弦波。頭で音程が落ちる「ドゥン」）にした。暗いマイナー（A・F・E）、低い太鼓のロール、うなる低音の残響
#   画面は電話の標準のキー配列（丸いキー＋ABC）。iPhone の画面そのものにはしない：ステータスバー・キャリア名・鍵の印・Apple の文言は入れない
#   python3 tools/passcode.py [out.mp4]     STILLS=1,5,9 で確認用の絵だけ
import math, subprocess, sys, os, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from scipy.signal import butter, sosfilt, fftconvolve

W, H, FPS, SR = 1080, 1920, 30, 48000
BPM = 126; BEAT = 60 / BPM; BAR = 4 * BEAT; S16 = BEAT / 4
OUT = sys.argv[1] if len(sys.argv) > 1 else "output/passcode2_ja.mp4"
FM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
fD = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Light.otf", 104); fK = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 27)
fT = ImageFont.truetype(FJ, 40); fS = ImageFont.truetype(FJ, 28); fL = ImageFont.truetype(FM, 34)

# ---------- 楽譜 ----------
# A 4分で押す（2小節）→ B 8分（2小節）→ C 16分（2小節）→ ため（2小節：低い太鼓が上へのぼり、最後の8分は無音）→ 4つ打ちで戻る（4小節）→ 最後の1打
T0 = .35
ROOT = [33, 33, 29, 28]                                      # 低音：A1・A1・F1・E1（41〜55Hz）
KEYS = "123456789*0#"
tb = lambda bar, six=0: T0 + bar * BAR + six * S16           # 小節と16分の位置 → 秒
def key_of(m, step):                                         # 音の高さ → キーの段（低い音ほど下の段）。列は順にずらす
    row = 2 if m < 36 else 1 if m < 48 else 0; return "123456789"[row * 3 + (step + m) % 3]
presses = []                                                 # (時刻, キー, 音の高さ, 段, 強さ, 種類)
A_N = [[33, 33, 33, 36], [33, 33, 31, 28]]
for bar in (0, 1):
    for q in range(4): m = A_N[bar][q]; presses.append((tb(bar, q * 4), key_of(m, q), m, 0, 1.0, "boom"))
B_ON = [[33, 33, 33, 33], [33, 33, 36, 31]]; B_OFF = [[45, 40, 45, 48], [45, 40, 43, 38]]
for bi, bar in enumerate((2, 3)):
    for q in range(4):
        presses.append((tb(bar, q * 4), key_of(B_ON[bi][q], q), B_ON[bi][q], 1, 1.0, "boom"))
        presses.append((tb(bar, q * 4 + 2), key_of(B_OFF[bi][q], q + 1), B_OFF[bi][q], 1, .8, "mid"))
def rollbar(bar, si):                                        # 16分：拍の頭はバスドラム、あとの3つは転がる低音
    r = ROOT[bar % 4]
    for q in range(4):
        presses.append((tb(bar, q * 4), key_of(r, q), r, si, 1.0, "kick"))
        for p in (1, 2, 3):
            m = r + (12 if (q == 3 and p == 2) else 1 if (bar % 2 == 1 and q == 3 and p == 3) else 0)   # 小節の終わりで1オクターブ上／半音上（不穏に）
            presses.append((tb(bar, q * 4 + p), key_of(m, q + p), m, si, .62 if p != 2 else .78, "roll"))
for bar in (4, 5): rollbar(bar, 2)
SC = [33, 36, 38, 40, 43, 45, 48, 50, 52, 55, 57, 60]       # ため：Aマイナーの音階を低い太鼓でのぼる
for q in range(16): m = SC[int(q * 11 / 15)]; presses.append((tb(6, q), key_of(m, q), m, 3, .72 + .02 * q, "tom"))
for q in range(8): m = [57, 60, 57, 64][q % 4]; presses.append((tb(7, q), key_of(m, q), m, 3, .9, "tom"))
t_ = tb(7, 8); n_ = 0
while t_ < tb(7, 14) - 1e-6:                                 # 3拍目〜4拍目の前半：32分の連打（最後の8分は無音）
    m = [64, 60][n_ % 2] + (3 if n_ >= 8 else 0); presses.append((t_, key_of(m, n_), m, 3, .6 + .035 * n_, "tom")); t_ += S16 / 2; n_ += 1
GAP0 = tb(7, 14); DROP = tb(8)
for bar in range(8, 12): rollbar(bar, 4)
FIN = tb(12); DUR = FIN + 1.5
PULSE = [(p[0], 1.0 if p[5] == "kick" else .9) for p in presses if p[5] in ("boom", "kick")] + [(tb(6, q * 4), 1.0) for q in range(4)] + [(FIN, 1.0)]
PULSE.sort()                                                 # 低い「ドゥン」が鳴る時刻（キーが光る・ほかの音が引っこむ）
def stage_at(t): return 0 if t < tb(2) else 1 if t < tb(4) else 2 if t < tb(6) else 3 if t < DROP else 4

# ---------- 音：低音が主役。明るい音は使わない ----------
N = int(SR * (DUR + 2.5)); rng = np.random.default_rng(3)
K = np.zeros(N); BS = np.zeros((N, 2)); PAD = np.zeros((N, 2)); PL = np.zeros((N, 2)); PC = np.zeros((N, 2)); SND = np.zeros((N, 2))   # ドゥン／転がる低音／うなり／暗い和音／打楽器／残響へ送る分
f_ = lambda m: 440 * 2 ** ((m - 69) / 12)
def flt(x, kind, fr, order=2): return sosfilt(butter(order, fr, btype=kind, fs=SR, output="sos"), x)
def put(bus, sig, t, pan=.5, g=1.0, wet=0.0):
    i = int(round(t * SR)); j = min(N, i + len(sig))
    if i < 0 or j <= i: return
    s = sig[:j - i] * g; cl, cr = math.cos(pan * math.pi / 2) * 1.414, math.sin(pan * math.pi / 2) * 1.414
    bus[i:j, 0] += s * cl; bus[i:j, 1] += s * cr
    if wet: SND[i:j, 0] += s * cl * wet; SND[i:j, 1] += s * cr * wet
def putk(sig, t, g=1.0):
    i = int(round(t * SR)); j = min(N, i + len(sig)); K[i:j] += sig[:j - i] * g
_c = {}; GRIT = 1.7
def b808(m, dur, dec, punch=1.0, drive=3.0):   # 808 ふうの低音：正弦波を歪ませる（3倍・5倍の倍音が出て、小さいスピーカーでも低音に聞こえる）。頭で音程が落ちて「ドゥン」
    key = (m, round(dur, 4), dec, punch, drive)
    if key not in _c:
        tt = np.arange(int(SR * dur)) / SR; f = f_(m)
        ph = 2 * np.pi * np.cumsum(f * (1 + 2.6 * punch * np.exp(-tt * 38) + .3 * punch * np.exp(-tt * 9))) / SR
        x = np.tanh((np.sin(ph) + .55 * np.sin(2 * ph + .4)) * drive) / np.tanh(drive)
        grit = flt(np.clip((np.sin(ph) + .7 * np.sin(2 * ph + .4) + .4 * np.sin(3 * ph)) * 6, -1, 1), "band", [200, 1300])   # うなり：小さいスピーカーでも聞こえる帯域
        x = flt(x, "low", 1300) * .72 + grit * GRIT
        ck = flt(np.random.default_rng(int(m)).normal(0, 1, len(tt)), "low", 2500) * np.exp(-tt * 500) * .22 * punch
        _c[key] = (x * np.exp(-tt * dec) + ck) * np.minimum(1, tt / .002) * np.minimum(1, (dur - tt) / .025)
    return _c[key]
def kick():   # クラブのバスドラム：長くのびる低い胴（約47Hz）＋頭の「ドッ」＋「コツ」
    tt = np.arange(int(SR * .46)) / SR; ph = 2 * np.pi * np.cumsum(47 + 150 * np.exp(-tt * 40) + 30 * np.exp(-tt * 9)) / SR
    body = np.tanh(np.sin(ph) * 2.6) / np.tanh(2.6) * np.exp(-tt * 5.0) * np.minimum(1, tt / .0015) * np.minimum(1, (.46 - tt) / .04)
    knock = np.sin(2 * np.pi * np.cumsum(120 + 190 * np.exp(-tt * 40)) / SR) * np.exp(-tt * 22) * 1.15   # 100〜300Hz の「ドッ」を強く
    ck = flt(rng.normal(0, 1, len(tt)), "band", [700, 3200]) * np.exp(-tt * 420) * .55
    return body * 1.0 + knock + ck
KICK = kick()
def stab(ms, dur=.34, cut=1500):     # 暗い和音の一打（丸めたノコギリ波、高い所は切る）
    tt = np.arange(int(SR * dur)) / SR; x = np.zeros(len(tt))
    for m in ms:
        for det in (-9, 0, 9):
            fd = f_(m) * 2 ** (det / 1200)
            for k in range(1, 9):
                if fd * k > cut: break
                x += np.sin(2 * np.pi * fd * k * tt + det + k) / k * np.exp(-tt * (6 + 1.6 * k))
    return x / len(ms) * np.minimum(1, tt / .004) * np.minimum(1, (dur - tt) / .03) * .15
def drone(ms, dur, att=.8):          # 低いうなり（ゆっくり揺れる）
    tt = np.arange(int(SR * dur)) / SR; x = np.zeros(len(tt))
    for m in ms:
        for det in (-9, 9): f = f_(m) * 2 ** (det / 1200); x += np.sin(2 * np.pi * f * tt) + .25 * np.sin(4 * np.pi * f * tt) + .12 * np.sin(6 * np.pi * f * tt)
    return x / (2 * len(ms)) * np.minimum(1, tt / att) * np.minimum(1, (dur - tt) / .2) * (1 + .15 * np.sin(2 * np.pi * .7 * tt))
def hat(open_=False):                # 暗めのハット
    d = .11 if open_ else .045; tt = np.arange(int(SR * d)) / SR
    return flt(rng.normal(0, 1, len(tt)), "band", [5500, 10500]) * np.exp(-tt * (30 if open_ else 100)) * np.minimum(1, tt / .001) * np.minimum(1, (d - tt) / .01)
def clap():                          # 暗い手拍子
    tt = np.arange(int(SR * .26)) / SR; n = flt(rng.normal(0, 1, len(tt)), "band", [550, 2300])
    e = sum(np.where(tt >= d0, np.exp(-(tt - d0) * 260), 0) for d0 in (0, .011, .022)) * .6 + np.where(tt >= .022, np.exp(-(tt - .022) * 24), 0)
    return n * e
# 押す音
for t, k, m, si, g, kind in presses:
    pan = .5
    if kind == "boom": putk(b808(m, BEAT * (.98 if si == 0 else .49), 3.6 if si == 0 else 5.5, 1.0, 3.2), t, .95 * g); putk(b808(m + 12, BEAT * .45, 7.0, .8, 3.0), t, .40 * g)   # 1オクターブ上を重ねる（小さいスピーカーでも「ドゥン」が聞こえる）
    elif kind == "kick": putk(KICK, t, 1.0 * g)
    elif kind == "mid": put(BS, b808(m, 2 * S16 * .95, 7, .6, 2.8), t, pan, .85 * g, .05)
    elif kind == "roll": gg = g * (1.25 if si == 4 else 1.0); put(BS, b808(m, S16 * .97, 6, .35, 3.0), t, pan, 1.0 * gg); put(BS, b808(m + 12, S16 * .9, 9, .3, 3.0), t, pan, .72 * gg)
    elif kind == "tom": put(BS, b808(m, S16 * (1.6 if si == 3 and t < tb(7, 8) else .9), 11, .7, 2.2), t, .35 + .3 * ((m % 5) / 4), .30 * g, .25)
for q in range(4): putk(KICK, tb(6, q * 4), .95)            # ため1小節目は下でバスドラムが続く
# 低いうなり（最初から小さく。だんだん大きく）
for bar in range(0, 7):
    r = ROOT[bar % 4]; put(PAD, drone([r + 12, r + 19], BAR + .25, .5 if bar else .05), tb(bar), .5, .10 if bar < 2 else .14 if bar < 4 else .18, .3)
for bar in range(1, 7):
    for q in range(4):
        t = tb(bar, q * 4)
        put(PC, hat(), t + 2 * S16, .58, .5 if bar < 2 else .65)                          # 裏拍のハット
        if bar >= 4:
            for p, v in ((1, 1.0), (3, .8)): put(PC, hat(), t + p * S16, .44, .38 * v)
            put(PC, hat(True), t + 2 * S16, .6, .6, .06)
        if bar in (4, 5) and q % 2 == 1: put(PC, clap(), t, .5, 1.5, .35)
    if bar in (4, 5): put(PL, stab([57, 60, 64]), tb(bar, 6), .45, 4.0, .5); put(PL, stab([57, 60, 64]), tb(bar, 14), .55, 3.2, .5)
# ため：上がっていく暗い「サー」と手拍子の連打。最後の8分は無音
c = [ROOT[3] + 12, ROOT[3] + 19, ROOT[3] + 24]; put(PAD, drone(c, GAP0 - tb(7), att=1.4), tb(7), .5, .20, .4)
roll = [tb(7, q * 2) for q in range(4)] + [tb(7, 8 + q) for q in range(4)] + [tb(7, 12) + q * S16 / 2 for q in range(4)]
for n, t in enumerate(roll): u = n / (len(roll) - 1); put(PC, clap(), t, .5, (.15 + .6 * u) * (1 if n >= 4 else .6), .3); put(PC, hat(), t, .5, .25 + .35 * u)
tt = np.arange(int(SR * (GAP0 - tb(6)))) / SR; u = tt / tt[-1]; nz = rng.normal(0, 1, len(tt)); ris = np.zeros(len(tt))
for bi, fc in enumerate([250, 500, 1000, 2000, 3600]):
    wgt = np.clip(1 - np.abs(u * 4 - bi), 0, 1); ris += flt(nz, "band", [fc * .7, fc * 1.4]) * wgt
put(PC, ris * u ** 2.5 * np.minimum(1, (tt[-1] - tt) / .01), tb(6), .5, .5, .3)
# 4つ打ちで戻る：バスドラム＋転がる低音（押す音）に、下でのび続ける低音、暗い和音、ハット、手拍子
for bar in range(8, 12):
    r = ROOT[bar % 4]
    put(BS, b808(r, BAR * .985, .7, 0, 2.2), tb(bar), .5, .38)                              # 下でのび続ける低音（ドゥンのたびに引っこんで、ふくらむ）
    put(PAD, drone([r + 12, r + 19], BAR + .25, .3), tb(bar), .5, .22, .3)
    for q in range(4):
        t = tb(bar, q * 4)
        put(PC, hat(True), t + 2 * S16, .6, .9, .06)
        for p, v in ((1, 1.0), (3, .8)): put(PC, hat(), t + p * S16, .44, .45 * v)
        if q % 2 == 1: put(PC, clap(), t, .5, 1.9, .4)
    ch = [57, 60, 64] if bar % 4 < 2 else [53, 57, 60] if bar % 4 == 2 else [52, 56, 59]    # Am・Am・F・E（最後は長三和音のミ＝不穏な終止）
    put(PL, stab(ch), tb(bar, 6), .45, 5.5, .5); put(PL, stab(ch), tb(bar, 9), .55, 2.6, .5); put(PL, stab(ch), tb(bar, 14), .5, 4.4, .5)
tt = np.arange(int(SR * 1.2)) / SR; put(PC, flt(rng.normal(0, 1, len(tt)), "band", [2500, 9000]) * np.exp(-tt * 3.5), DROP, .5, .6, .4)   # 入りのシンバル（暗く短く）
putk(KICK, FIN, 1.0); putk(b808(33, 1.45, 1.5, 1.0, 3.2), FIN, .9); put(PL, stab([57, 60, 64], .8, 1200), FIN, .5, 6.0, .8)   # 最後の1打
# うなる残響：ドゥンの音に短い残響をかけ、低い所だけ残す（クラブの床が鳴る感じ）。ドゥンの瞬間は引っこめる
duck = np.zeros(N); dl = int(SR * .5); sh = np.exp(-np.arange(dl) / SR / .12)
for t, g in PULSE:
    i = int(round(t * SR)); duck[i:i + dl] = np.maximum(duck[i:i + dl], sh[:max(0, min(dl, N - i))] * g)
tr = np.arange(int(SR * .7)) / SR; irr = np.random.default_rng(21).normal(0, 1, len(tr)) * np.exp(-tr * 6)
rum = flt(fftconvolve(K, irr)[:N], "low", 115, 4); rum = rum / (np.abs(rum).max() + 1e-9)
rg = np.zeros(N); rg[int(tb(4) * SR):int(tb(7) * SR)] = .35; rg[int(DROP * SR):int((FIN + 1.2) * SR)] = .55
# 残響（1.6秒、暗い部屋）
tt = np.arange(int(SR * 1.6)) / SR
def ir(seed): return flt(flt(np.random.default_rng(seed).normal(0, 1, len(tt)), "low", 3000), "high", 300) * np.exp(-tt * 3.6) * .024
REV = np.stack([fftconvolve(SND[:, 0], ir(11))[:N], fftconvolve(SND[:, 1], ir(12))[:N]], 1)
gap = np.ones(N); i0, i1 = int(GAP0 * SR), int(DROP * SR); gap[i0:i1] = .08 + .92 * np.maximum(0, 1 - np.arange(i1 - i0) / (SR * .03))   # 直前の無音（残響だけ少し残す）
mix = (BS * (1 - .75 * duck)[:, None] + PAD * (1 - .85 * duck)[:, None] + PL * (1 - .35 * duck)[:, None] + PC + REV * (1 - .4 * duck)[:, None]) * gap[:, None]
low = K * .95 + rum * rg * (1 - .9 * duck) * gap
mix[:, 0] += low; mix[:, 1] += low
mix = np.stack([flt(mix[:, 0], "high", 26), flt(mix[:, 1], "high", 26)], 1)
pk = np.max(np.abs(mix)); mix = np.tanh(mix / pk * 3.2) / np.tanh(3.2) * .78   # 頭打ちをやわらかく丸めて、全体の音量をかせぐ
fo = int(SR * .35); e0 = int(SR * DUR); mix[e0 - fo:e0] *= np.linspace(1, 0, fo)[:, None]
os.makedirs("build_passcode", exist_ok=True)
with wave.open("build_passcode/a.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix[:e0] * 32767).astype(np.int16).tobytes())

# ---------- 絵：暗くぼかした背景＋すりガラスの丸いキー。低い「ドゥン」のたびにキーが光り、キー全体がわずかにふくらむ ----------
TINT = [((34, 32, 31), (78, 72, 66), (50, 46, 44)), ((24, 27, 34), (60, 68, 86), (36, 42, 54)),
        ((30, 22, 34), (74, 52, 84), (44, 32, 52)), ((26, 16, 14), (70, 38, 30), (40, 24, 20)), ((8, 8, 12), (34, 30, 56), (16, 18, 30))]
GLOW = [(255, 244, 230), (190, 222, 255), (224, 192, 255), (255, 196, 170)]          # A・B・C・ため の光の色（白に寄せてくすませる）
DROPC = [(255, 255, 255), (186, 214, 255), (255, 255, 255), (214, 190, 255)]        # 戻ったあと：白・青・白・紫
def blobs(cols, seed):   # 大きくぼかした色の雲
    rs = np.random.default_rng(seed); im = Image.new("RGB", (W // 4, H // 4), cols[0]); d = ImageDraw.Draw(im)
    for q in range(7):
        x, y, r = rs.uniform(0, W // 4), rs.uniform(0, H // 4), rs.uniform(60, 150); d.ellipse([x - r, y - r, x + r, y + r], fill=cols[1 + q % 2])
    return im.filter(ImageFilter.GaussianBlur(60)).resize((W + 240, H + 240), Image.BICUBIC)
BGS = [np.asarray(blobs(c, 5 + i), np.float32) for i, c in enumerate(TINT)]
grain = (np.random.default_rng(9).normal(0, 1, (H, W, 1)) * 2.6).astype(np.float32)   # マットに見せる細かい粒
KD = 216; KSX = 296; KSY = 258; KY0 = 930; KCY = KY0 + 1.5 * KSY
LET = {"2": "ABC", "3": "DEF", "4": "GHI", "5": "JKL", "6": "MNO", "7": "PQRS", "8": "TUV", "9": "WXYZ"}
kpos = {}
for i, k in enumerate(KEYS):
    r, c = divmod(i, 3); kpos[k] = (W / 2 + (c - 1) * KSX, KY0 + r * KSY)   # キーの中心
EDGES = [tb(2), tb(4), tb(6), DROP]
def frame(t):
    si = stage_at(t); prev = max(0, si - 1); u = min(1, (t - EDGES[si - 1]) / (.5 if si < 4 else .12)) if si > 0 else 1
    kp = 0.0; ki = -1
    for n, (tk, g) in enumerate(PULSE):
        if tk <= t + 1e-6: kp = math.exp(-(t - tk) * 8.5) * g; ki = n
        else: break
    brk = tb(7) <= t < DROP; ingap = GAP0 <= t < DROP
    if brk: kp = 0.0
    col = GLOW[min(si, 3)] if si < 4 else DROPC[ki % 4]
    ox, oy = int(120 + 60 * math.sin(t * .23)), int(120 + 80 * math.cos(t * .17))   # 背景はゆっくり漂う
    bg = BGS[prev][oy:oy + H, ox:ox + W] * (1 - u) + BGS[si][oy:oy + H, ox:ox + W] * u
    bg = bg * ((.5 if ingap else 1) + (.22 if si < 4 else .5) * kp) + grain
    if si == 4: bg = bg + np.array(col, np.float32)[None, None, :] * (.07 * kp)   # 戻ったら、背景にも光がにじむ
    base = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))
    glow = Image.new("RGB", (W // 2, H // 2)); g = ImageDraw.Draw(glow)             # 足し算で重ねる光（ぼかす）
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    done = [p for p in presses if p[0] <= t + 1e-6]; n_in = len(done) % 6
    if done and len(done) % 6 == 0 and t - done[-1][0] < .12: n_in = 6
    if si == 4 or ingap or (si == 3 and t >= tb(7, 8)): n_in = 6
    d.text((W / 2, 430), "押すたびに、1音", font=fT, fill=(255, 255, 255, 240), anchor="mm")
    d.text((W / 2, 488), "だんだん、速くなる", font=fS, fill=(255, 255, 255, 180), anchor="mm")
    d.text((W / 2, 300), ["x1", "x2", "x4", "x8", "OPEN"][si], font=fL, fill=(255, 255, 255, 200), anchor="mm")
    for j in range(6):   # 入力の丸6つ（ドゥンで少しふくらむ）
        cx = W / 2 + (j - 2.5) * 96; cy = 600; s = 16 * (1 + .25 * kp)
        if j < n_in:
            d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=(255, 255, 255, 245)); gr = 16 + 12 * kp
            g.ellipse([cx / 2 - gr, cy / 2 - gr, cx / 2 + gr, cy / 2 + gr], fill=tuple(int(v * (.12 + .3 * kp)) for v in col))
        else: d.ellipse([cx - s, cy - s, cx + s, cy + s], outline=(255, 255, 255, 220), width=3)
    zs = 1 + .022 * kp                                                   # ドゥンのたびに、キー全体がわずかに前へ出る
    for k, (x0, y0) in kpos.items():
        if k in "*#": continue
        x = W / 2 + (x0 - W / 2) * zs; y = KCY + (y0 - KCY) * zs
        hit = [p for p in done if p[1] == k]; e = t - hit[-1][0] if hit else 9; lit = math.exp(-e * 7) * (min(1, hit[-1][4] * 1.2) if hit else 0)
        kk = kp * (1.0 if k == "0" else (.36 if si < 4 else .7))        # 「0」は拍のキー。戻ったら全部のキーが打つ
        if ingap: kk = 0; lit *= .3
        a = max(lit, kk); rad = KD / 2 * zs * (1 + .05 * a)
        rr = [x - rad, y - rad, x + rad, y + rad]
        hr = rad / 2 * (1.06 + .30 * a)                                 # キーのまわりににじむ光
        if a > .02: g.ellipse([x / 2 - hr, y / 2 - hr, x / 2 + hr, y / 2 + hr], fill=tuple(int(v * min(.55, .55 * a)) for v in col))
        d.ellipse(rr, fill=(255, 255, 255, int(28 + 70 * kk + 165 * lit)))   # すりガラスの丸：白をうすく重ねる。押すと明るい
        if a > .08: d.ellipse(rr, outline=col + (int(220 * a),), width=4)
        dy = -14 if k in LET else 0
        wq = 1 if max(lit, kk if k == "0" else 0) > .6 else 0; tc = tuple(int(255 + (30 - 255) * wq) for _ in range(3))   # 白く光っている間だけ、数字を暗い色に
        d.text((x, y + dy), k, font=fD, fill=tc + (250,), anchor="mm")
        if k in LET: d.text((x, y + 50), " ".join(LET[k]), font=fK, fill=tc + (235,), anchor="mm")
    if si == 4 and kp > .02:   # 戻ったら：ドゥンのたびに、キーの列から細い光の輪がひろがる
        e = -math.log(max(kp, 1e-6)) / 8.5; r = (260 + 1500 * e) / 2
        g.ellipse([W / 4 - r, 1320 / 2 - r, W / 4 + r, 1320 / 2 + r], outline=tuple(int(v * .4 * kp) for v in col), width=8)
    glow = glow.filter(ImageFilter.GaussianBlur(20)).resize((W, H), Image.BILINEAR)
    im = ImageChops.add(base, glow).convert("RGBA")
    return Image.alpha_composite(im, ov).convert("RGB")

if __name__ == "__main__":
    still = os.environ.get("STILLS")
    if still:
        for s in still.split(","): frame(float(s)).save(f"build_passcode/s_{float(s):06.3f}.jpg", quality=88)
        sys.exit()
    nf = int(DUR * FPS)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", "build_passcode/a.wav",
                          "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", OUT], stdin=subprocess.PIPE)
    for i in range(nf):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait(); print(OUT, round(DUR, 2), "秒")
