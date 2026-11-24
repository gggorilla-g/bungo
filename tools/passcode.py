# passcode.py — 数字キーを押すたびに1音。バスドラムの「ドッ、ドッ」でキーが光り、押す速さが上がっていき、ためのあとにほどける（オーナー 11/25）
#   画面は電話の標準のキー配列（丸いキー＋ABC）。iPhone の画面そのものにはしない：ステータスバー・キャリア名・鍵の印・Apple の文言は入れない
#   python3 tools/passcode.py [out.mp4]     STILLS=1,5,9 で確認用の絵だけ
import math, subprocess, sys, os, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from scipy.signal import butter, sosfilt, fftconvolve

W, H, FPS, SR = 1080, 1920, 30, 48000
BPM = 128; BEAT = 60 / BPM; BAR = 4 * BEAT; S16 = BEAT / 4
OUT = sys.argv[1] if len(sys.argv) > 1 else "output/passcode1_ja.mp4"
FM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
fD = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Light.otf", 104); fK = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 27)
fT = ImageFont.truetype(FJ, 40); fS = ImageFont.truetype(FJ, 28); fL = ImageFont.truetype(FM, 34)

# ---------- 楽譜（128BPM）----------
# A 4分で押す（2小節）→ B 8分（2小節）→ C 16分（2小節）→ ため（2小節。最後の8分は無音）→ ほどける（4小節）→ 最後の1打
T0 = .35
CH = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]   # Am F C G（1小節ずつ）
KEYS = "123456789*0#"
tb = lambda bar, six=0: T0 + bar * BAR + six * S16           # 小節と16分の位置 → 秒
def key_of(i, step):                                         # 和音の何番目の音か → キー（高い音ほど上の段）
    return "123456789"[(2 - i % 3) * 3 + (step * 2 + i) % 3]
presses = []                                                 # (時刻, キー, 音の高さ, 段, 強さ)
PAT8 = [0, 1, 2, 1, 2, 0, 1, 2]; PAT16 = [0, 2, 1, 2, 0, 2, 1, 2, 0, 1, 2, 1, 2, 0, 2, 1]
for bar in range(0, 2):
    for q in range(4): i = PAT8[(bar * 4 + q) % 8]; presses.append((tb(bar, q * 4), key_of(i, q), CH[bar % 4][i] + 12, 0, 1.3))
for bar in range(2, 4):
    for q in range(8): i = PAT8[q]; presses.append((tb(bar, q * 2), key_of(i, q), CH[bar % 4][i] + 12, 1, 1.0))
for bar in range(4, 6):
    for q in range(16): i = PAT16[q]; presses.append((tb(bar, q), key_of(i, q), CH[bar % 4][i] + 12 + (12 if q % 4 == 3 else 0), 2, .8))
for q in range(16):                                          # ため1小節目：16分で上へのぼる
    i = q % 3; presses.append((tb(6, q), key_of(i, q), CH[2][i] + 12 + 12 * (q // 6), 3, .7 + .02 * q))
for q in range(8):                                           # ため2小節目：16分 → 32分の連打
    i = q % 3; presses.append((tb(7, q), key_of(i, q), CH[3][i] + 24, 3, .85))
t_ = tb(7, 8); n_ = 0
while t_ < tb(7, 14) - 1e-6:                                 # 3拍目〜4拍目の前半：32分（最後の8分は無音）
    i = n_ % 2 * 2; presses.append((t_, key_of(i + n_ // 4, n_), CH[3][i] + 24 + (12 if n_ >= 8 else 0), 3, .6 + .03 * n_)); t_ += S16 / 2; n_ += 1
GAP0 = tb(7, 14); DROP = tb(8); LEAD = [0, 3, 6, 8, 11, 14]; LIDX = [3, 2, 4, 3, 1, 2]   # ほどけ：3-3-2 のリズム
for bar in range(8, 12):
    c = CH[bar % 4]; tones = [c[0] + 12, c[1] + 12, c[2] + 12, c[0] + 24, c[1] + 24]
    for h, six in enumerate(LEAD): presses.append((tb(bar, six), key_of(LIDX[h], h + bar), tones[LIDX[h]], 4, 1.4))
FIN = tb(12); DUR = FIN + 1.0
KICKS = [(tb(b, q * 4), .9) for b in range(0, 2) for q in range(4)] + [(tb(b, q * 4), 1.0) for b in range(2, 7) for q in range(4)] + [(tb(7), 1.0)] \
      + [(tb(b, q * 4), 1.0) for b in range(8, 12) for q in range(4)] + [(FIN, 1.0)]
def stage_at(t): return 0 if t < tb(2) else 1 if t < tb(4) else 2 if t < tb(6) else 3 if t < DROP else 4

# ---------- 音：EDM の骨組み（4つ打ち・サイドチェイン・ため・ほどけ）を、耳にやさしい音色で ----------
N = int(SR * (DUR + 2.5)); rng = np.random.default_rng(3)
K = np.zeros(N); PAD = np.zeros((N, 2)); PL = np.zeros((N, 2)); PC = np.zeros((N, 2)); SND = np.zeros((N, 2))   # バスドラム／パッドと低音／はじく音／打楽器／残響へ送る分
f_ = lambda m: 440 * 2 ** ((m - 69) / 12)
def flt(x, kind, fr, order=2): return sosfilt(butter(order, fr, btype=kind, fs=SR, output="sos"), x)
def put(bus, sig, t, pan=.5, g=1.0, wet=0.0):
    i = int(round(t * SR)); j = min(N, i + len(sig))
    if i < 0 or j <= i: return
    s = sig[:j - i] * g; cl, cr = math.cos(pan * math.pi / 2) * 1.414, math.sin(pan * math.pi / 2) * 1.414
    bus[i:j, 0] += s * cl; bus[i:j, 1] += s * cr
    if wet: SND[i:j, 0] += s * cl * wet; SND[i:j, 1] += s * cr * wet
def kick():   # 頭の「ドッ」（高い所からすばやく下がる）＋太い胴。スマホのスピーカーでも聞こえるよう、下がりはじめを高めに
    tt = np.arange(int(SR * .42)) / SR; ph = 2 * np.pi * np.cumsum(46 + 175 * np.exp(-tt * 55) + 45 * np.exp(-tt * 11)) / SR
    body = np.tanh(np.sin(ph) * 1.7) / np.tanh(1.7) * np.exp(-tt * 6.5) * np.minimum(1, tt / .0015) * np.minimum(1, (.42 - tt) / .03)
    ck = flt(rng.normal(0, 1, len(tt)), "low", 5000) * np.exp(-tt * 700) * .4
    knock = np.sin(2 * np.pi * np.cumsum(120 + 160 * np.exp(-tt * 45)) / SR) * np.exp(-tt * 26) * .55   # 小さいスピーカーでも聞こえる「コツ」
    return body * .8 + knock + ck
KICK = kick()
_pc = {}
def pluck(m, dur=.9, bright=1.0):   # はじく音：倍音は 1/k、高い倍音ほど早く消える（フィルターが閉じる感じ）。2声を少しずらす
    key = (m, dur, bright)
    if key not in _pc:
        tt = np.arange(int(SR * dur)) / SR; x = np.zeros(len(tt))
        for det in (-5, 5):
            fd = f_(m) * 2 ** (det / 1200)
            for k in range(1, 12):
                if fd * k > 8500: break
                x += np.sin(2 * np.pi * fd * k * tt + k * .7) / k ** .85 * np.exp(-tt * (3.2 + 1.7 * k / bright))
        _pc[key] = x * np.minimum(1, tt / .002) * np.minimum(1, (dur - tt) / .02) * .15
    return _pc[key]
def stab(ms, dur=.42):              # 和音の短い一打（やわらかいノコギリ波を3声、高い所は丸める）
    tt = np.arange(int(SR * dur)) / SR; x = np.zeros(len(tt))
    for m in ms:
        for det in (-9, 0, 9):
            fd = f_(m) * 2 ** (det / 1200)
            for k in range(1, 10):
                if fd * k > 6500: break
                x += np.sin(2 * np.pi * fd * k * tt + det + k) / k * np.exp(-tt * (4 + 1.1 * k))
    return x / len(ms) * np.minimum(1, tt / .004) * np.minimum(1, (dur - tt) / .03) * .16
def pad(ms, dur, att=.12):          # パッド：少しずらしたやわらかい波（奇数倍音を少し）
    tt = np.arange(int(SR * dur)) / SR; x = np.zeros(len(tt))
    for m in ms:
        for det in (-7, 7): f = f_(m) * 2 ** (det / 1200); x += np.sin(2 * np.pi * f * tt) + .11 * np.sin(6 * np.pi * f * tt) + .2 * np.sin(4 * np.pi * f * tt)
    return x / (2 * len(ms)) * np.minimum(1, tt / att) * np.minimum(1, (dur - tt) / .12)
def bass(m, dur):                   # 低音：スマホでも聞こえるよう2・3倍音を足す
    tt = np.arange(int(SR * dur)) / SR; f = f_(m)
    x = np.sin(2 * np.pi * f * tt) + .8 * np.sin(4 * np.pi * f * tt) + .5 * np.sin(6 * np.pi * f * tt) + .25 * np.sin(8 * np.pi * f * tt) + .35 * np.sin(np.pi * f * tt)
    return np.tanh(x * .7) * np.minimum(1, tt / .008) * np.exp(-tt * 2.2) * np.minimum(1, (dur - tt) / .03)
def hat(open_=False):
    d = .2 if open_ else .05; tt = np.arange(int(SR * d)) / SR
    return flt(rng.normal(0, 1, len(tt)), "high", 7000 if not open_ else 6000) * np.exp(-tt * (17 if open_ else 95)) * np.minimum(1, tt / .001)
def clap():
    tt = np.arange(int(SR * .26)) / SR; n = flt(rng.normal(0, 1, len(tt)), "band", [900, 3800])
    e = sum(np.where(tt >= d0, np.exp(-(tt - d0) * 260), 0) for d0 in (0, .011, .022)) * .6 + np.where(tt >= .022, np.exp(-(tt - .022) * 26), 0)
    return n * e
def snare(pit=190):
    tt = np.arange(int(SR * .13)) / SR
    return flt(rng.normal(0, 1, len(tt)), "band", [1500, 6000]) * np.exp(-tt * 42) * .8 + np.sin(2 * np.pi * pit * tt) * np.exp(-tt * 34) * .6
# バスドラム
for t, g in KICKS:
    i = int(round(t * SR)); K[i:i + len(KICK)] += KICK * g
# 押す音（＋付点8分のこだまを左右に）
for t, k, m, si, g in presses:
    pan = .32 + .36 * (("123456789".index(k) % 3) / 2); br = [.8, .9, 1.0, 1.15, 1.2][si]; s = pluck(m, .9 if si < 2 else .6, br)
    put(PL, s, t, pan, 1.9 * g, .22)
    if si != 3: put(PL, s, t + 3 * S16, 1 - pan, .6 * g, .3); put(PL, s, t + 6 * S16, pan, .26 * g, .3)
# A〜C：だんだん増える
for bar in range(0, 6):
    c = CH[bar % 4]
    for q in range(4):
        t = tb(bar, q * 4)
        if bar >= 2: put(PC, hat(), t + 2 * S16, .6, .20)                                   # 裏拍のハット
        if bar >= 2: put(PAD, bass(c[0] - 12, 2 * S16 * .95), t + 2 * S16, .5, .42)          # 裏拍の低音（ドッ・ン・ドッ・ン）
        if bar >= 4: put(PC, hat(), t + S16, .4, .10); put(PC, hat(), t + 3 * S16, .42, .10)
        if bar >= 4 and q % 2 == 1: put(PC, clap(), t, .5, .50, .35)
    if bar >= 2: put(PAD, pad([c[0], c[1], c[2], c[0] + 12], BAR), tb(bar), .5, .15 if bar < 4 else .22, .3)
# ため：スネアの連打（4分 → 8分 → 16分 → 32分）、パッドのふくらみ、上がっていく音。最後の8分は無音
c = CH[2]; put(PAD, pad([c[0], c[1], c[2], c[0] + 12], BAR), tb(6), .5, .22, .3)
for q in range(4): put(PAD, bass(c[0] - 12, 2 * S16 * .95), tb(6, q * 4 + 2), .5, .42); put(PC, hat(), tb(6, q * 4 + 2), .6, .20)
roll = [tb(6, q * 4) for q in range(4)] + [tb(7, q * 2) for q in range(4)] + [tb(7, 8 + q) for q in range(4)] + [tb(7, 12) + q * S16 / 2 for q in range(4)]
for n, t in enumerate(roll): u = n / (len(roll) - 1); put(PC, snare(180 + 120 * u), t, .5, .18 + .34 * u, .25)
tt = np.arange(int(SR * (GAP0 - tb(6)))) / SR; u = tt / tt[-1]; nz = rng.normal(0, 1, len(tt)); ris = np.zeros(len(tt))
for bi, fc in enumerate([500, 1000, 2000, 4000, 7500]):    # 上がっていく「サー」：帯域を下から上へ受け渡す（やわらかめ）
    wgt = np.clip(1 - np.abs(u * 4 - bi), 0, 1); ris += flt(nz, "band", [fc * .7, fc * 1.4]) * wgt
put(PC, ris * u ** 2 * np.minimum(1, (tt[-1] - tt) / .01), tb(6), .5, .30, .3)
put(PL, np.sin(2 * np.pi * np.cumsum(330 * 2 ** (u * 2)) / SR) * u ** 2 * np.minimum(1, (tt[-1] - tt) / .01), tb(6), .5, .05, .4)
c = CH[3]; pd = pad([c[0], c[1], c[2], c[0] + 12, c[1] + 12], GAP0 - tb(7), att=1.2); put(PAD, pd, tb(7), .5, .26, .4)
# ほどける：4つ打ち、裏拍の低音、2・4拍の手拍子、開いたハット、3-3-2 の和音とリード
for bar in range(8, 12):
    c = CH[bar % 4]
    for q in range(4):
        t = tb(bar, q * 4)
        put(PAD, bass(c[0] - 12, 2 * S16 * .95), t + 2 * S16, .5, .78)
        put(PC, hat(True), t + 2 * S16, .62, .16, .1); put(PC, hat(), t + S16, .4, .10); put(PC, hat(), t + 3 * S16, .42, .10)
        if q % 2 == 1: put(PC, clap(), t, .5, .60, .4)
    put(PAD, pad([c[0], c[1], c[2], c[0] + 12], BAR), tb(bar), .5, .40, .3)
    for six in LEAD: put(PL, stab([c[0], c[1], c[2], c[0] + 12]), tb(bar, six), .5, 1.7, .3)
    for q in range(16): put(PL, pluck(c[PAT16[q]] + 12 + (12 if q % 4 == 3 else 0), .6, 1.0), tb(bar, q), .25 + .5 * (q % 2), .55, .2)   # 下で16分の分散和音が回りつづける
tt = np.arange(int(SR * 1.8)) / SR; put(PC, flt(rng.normal(0, 1, len(tt)), "high", 4500) * np.exp(-tt * 2.4), DROP, .5, .14, .5)   # 入りのシンバル（小さく）
c = CH[0]; put(PAD, pad([c[0], c[1], c[2], c[0] + 12, c[2] + 12], 1.6, att=.01) * np.exp(-np.arange(int(SR * 1.6)) / SR * 2.2), FIN, .5, .34, .6)   # 最後の1打
put(PL, pluck(c[0] + 24, .9, 1.2), FIN, .5, .9, .5)
# サイドチェイン：バスドラムのたびに、ほかの音を下げて戻す（EDM の「ウワッ、ウワッ」）
duck = np.zeros(N); dl = int(SR * .5); sh = np.exp(-np.arange(dl) / SR / .15)
for t, g in KICKS:
    i = int(round(t * SR)); duck[i:i + dl] = np.maximum(duck[i:i + dl], sh[:max(0, min(dl, N - i))] * g)
# 残響（1.8秒、低い所と高い所を切ったやわらかい部屋）
tt = np.arange(int(SR * 1.8)) / SR
def ir(seed): return flt(flt(np.random.default_rng(seed).normal(0, 1, len(tt)), "low", 5200), "high", 320) * np.exp(-tt * 3.4) * .018
REV = np.stack([fftconvolve(SND[:, 0], ir(11))[:N], fftconvolve(SND[:, 1], ir(12))[:N]], 1)
gap = np.ones(N); i0, i1 = int(GAP0 * SR), int(DROP * SR); gap[i0:i1] = .12 + .88 * np.maximum(0, 1 - np.arange(i1 - i0) / (SR * .03))   # ため直前の無音（残響だけ少し残す）
mix = (PAD * (1 - .8 * duck)[:, None] + PL * (1 - .45 * duck)[:, None] + PC + REV * (1 - .5 * duck)[:, None]) * gap[:, None]
mix[:, 0] += K * .62; mix[:, 1] += K * .62
mix = np.stack([flt(mix[:, 0], "high", 28), flt(mix[:, 1], "high", 28)], 1)
pk = np.max(np.abs(mix)); mix = np.tanh(mix / pk * 2.0) / np.tanh(2.0) * .89   # 頭打ちをやわらかく丸めて、全体の音量をかせぐ
fo = int(SR * .25); e0 = int(SR * DUR); mix[e0 - fo:e0] *= np.linspace(1, 0, fo)[:, None]
os.makedirs("build_passcode", exist_ok=True)
with wave.open("build_passcode/a.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix[:e0] * 32767).astype(np.int16).tobytes())

# ---------- 絵：マットにぼかした背景＋すりガラスの丸いキー。バスドラムのたびにキーが光る ----------
# 段ごとの背景（だんだん暗くして、光を目立たせる）
TINT = [((92, 86, 80), (150, 140, 128), (112, 104, 96)), ((62, 70, 82), (112, 128, 150), (80, 90, 108)),
        ((66, 52, 72), (128, 96, 132), (88, 68, 96)), ((70, 56, 44), (140, 108, 78), (92, 72, 56)), ((22, 22, 34), (56, 46, 86), (30, 34, 58))]
GLOW = [(255, 240, 220), (110, 215, 255), (255, 120, 215), (255, 205, 110)]          # A・B・C・ため の光の色
DROPC = [(110, 215, 255), (255, 120, 215), (255, 205, 110), (170, 140, 255)]        # ほどけ：1拍ごとに色が回る
def blobs(cols, seed):   # 大きくぼかした色の雲
    rs = np.random.default_rng(seed); im = Image.new("RGB", (W // 4, H // 4), cols[0]); d = ImageDraw.Draw(im)
    for q in range(7):
        x, y, r = rs.uniform(0, W // 4), rs.uniform(0, H // 4), rs.uniform(60, 150); d.ellipse([x - r, y - r, x + r, y + r], fill=cols[1 + q % 2])
    return im.filter(ImageFilter.GaussianBlur(60)).resize((W + 240, H + 240), Image.BICUBIC)
BGS = [np.asarray(blobs(c, 5 + i), np.float32) for i, c in enumerate(TINT)]
grain = (np.random.default_rng(9).normal(0, 1, (H, W, 1)) * 3.0).astype(np.float32)   # マットに見せる細かい粒
KD = 216; KSX = 296; KSY = 258; KY0 = 930
LET = {"2": "ABC", "3": "DEF", "4": "GHI", "5": "JKL", "6": "MNO", "7": "PQRS", "8": "TUV", "9": "WXYZ"}
kpos = {}
for i, k in enumerate(KEYS):
    r, c = divmod(i, 3); kpos[k] = (W / 2 + (c - 1) * KSX, KY0 + r * KSY)   # キーの中心
EDGES = [tb(2), tb(4), tb(6), DROP]
def frame(t):
    si = stage_at(t); prev = max(0, si - 1); u = min(1, (t - EDGES[si - 1]) / (.5 if si < 4 else .12)) if si > 0 else 1
    kp = 0.0; ki = -1
    for n, (tk, g) in enumerate(KICKS):
        if tk <= t + 1e-6: kp = math.exp(-(t - tk) * 8.5) * g; ki = n
        else: break
    ingap = GAP0 <= t < DROP
    col = GLOW[min(si, 3)] if si < 4 else DROPC[ki % 4]
    ox, oy = int(120 + 60 * math.sin(t * .23)), int(120 + 80 * math.cos(t * .17))   # 背景はゆっくり漂う
    bg = BGS[prev][oy:oy + H, ox:ox + W] * (1 - u) + BGS[si][oy:oy + H, ox:ox + W] * u
    bg = bg * ((.55 if ingap else 1) + (.10 if si < 4 else .30) * kp) + grain
    if si == 4: bg = bg + np.array(col, np.float32)[None, None, :] * (.10 * kp)   # ほどけ：背景にも色がにじむ
    base = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))
    glow = Image.new("RGB", (W // 2, H // 2)); g = ImageDraw.Draw(glow)             # 足し算で重ねる光（ぼかす）
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    done = [p for p in presses if p[0] <= t + 1e-6]; n_in = len(done) % 6
    if done and len(done) % 6 == 0 and t - done[-1][0] < .12: n_in = 6
    if si == 4 or ingap or (si == 3 and t >= tb(7, 8)): n_in = 6
    d.text((W / 2, 430), "押すたびに、1音", font=fT, fill=(255, 255, 255, 240), anchor="mm")
    d.text((W / 2, 488), "だんだん、速くなる", font=fS, fill=(255, 255, 255, 190), anchor="mm")
    d.text((W / 2, 300), ["x1", "x2", "x4", "x8", "OPEN"][si], font=fL, fill=(255, 255, 255, 210), anchor="mm")
    for j in range(6):   # 入力の丸6つ（バスドラムで少しふくらむ）
        cx = W / 2 + (j - 2.5) * 96; cy = 600; s = 16 * (1 + .25 * kp)
        if j < n_in:
            d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=(255, 255, 255, 245)); gr = 16 + 12 * kp
            g.ellipse([cx / 2 - gr, cy / 2 - gr, cx / 2 + gr, cy / 2 + gr], fill=tuple(int(v * (.15 + .35 * kp)) for v in col))
        else: d.ellipse([cx - s, cy - s, cx + s, cy + s], outline=(255, 255, 255, 220), width=3)
    for k, (x, y) in kpos.items():
        if k in "*#": continue
        hit = [p for p in done if p[1] == k]; e = t - hit[-1][0] if hit else 9; lit = math.exp(-e * 7) * (hit[-1][4] if hit else 0)
        kk = kp * (1.0 if k == "0" else (.38 if si < 4 else .72))        # 「0」はバスドラムのキー。ほどけたら全部のキーが打つ
        if ingap: kk = 0; lit *= .3
        a = max(lit, kk); rad = KD / 2 * (1 + .05 * a)
        rr = [x - rad, y - rad, x + rad, y + rad]
        hr = rad / 2 * (1.06 + .32 * a)                                  # キーのまわりににじむ光
        if a > .02: g.ellipse([x / 2 - hr, y / 2 - hr, x / 2 + hr, y / 2 + hr], fill=tuple(int(v * min(.62, .62 * a)) for v in col))
        d.ellipse(rr, fill=(255, 255, 255, int(38 + 70 * kk + 150 * lit)))   # すりガラスの丸：白をうすく重ねる。押すと明るい
        if a > .08: d.ellipse(rr, outline=col + (int(230 * a),), width=5)
        dy = -14 if k in LET else 0
        wq = max(0, min(1, (max(lit, kk if k == "0" else 0) - .35) / .3)); tc = tuple(int(255 + (38 - 255) * wq) for _ in range(3))   # 白く光っている間は、数字を暗い色に
        d.text((x, y + dy), k, font=fD, fill=tc + (250,), anchor="mm")
        if k in LET: d.text((x, y + 50), " ".join(LET[k]), font=fK, fill=tc + (235,), anchor="mm")
    if si == 4 and kp > .02:   # ほどけ：バスドラムのたびに、キーの列から光の輪がひろがる
        e = -math.log(max(kp, 1e-6)) / 8.5; r = (260 + 1500 * e) / 2
        g.ellipse([W / 4 - r, 1320 / 2 - r, W / 4 + r, 1320 / 2 + r], outline=tuple(int(v * .55 * kp) for v in col), width=10)
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
                          "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", OUT], stdin=subprocess.PIPE)
    for i in range(nf):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait(); print(OUT, round(DUR, 2), "秒")
