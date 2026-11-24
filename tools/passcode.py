# passcode.py — 数字キーを押すたびに1音。押す速さが上がっていき、6桁そろうたびに段が上がり、最後にほどける（オーナー 11/25）
#   iPhone の画面の写しではない：キーは角丸の四角、書体は等幅、キャリア名・Face ID の文言・鍵の印は使わない
#   python3 tools/passcode.py [out.mp4]
import math, subprocess, sys, os, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SR = 1080, 1920, 30, 48000
BPM = 128; BEAT = 60 / BPM; BAR = 4 * BEAT
OUT = sys.argv[1] if len(sys.argv) > 1 else "output/passcode1_ja.mp4"
FM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FMB = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
fD = ImageFont.truetype(FMB, 96); fT = ImageFont.truetype(FJ, 40); fS = ImageFont.truetype(FJ, 28); fL = ImageFont.truetype(FM, 26)

# ---------- 楽譜：段ごとに押す間かくが半分になる ----------
# 段1：4分（2小節）、段2：8分（2小節）、段3：16分（2小節）、段4：16分＋和音でため（2小節）→ ほどける（2小節）
STAGES = [(0, 2, 1.0), (2, 4, .5), (4, 6, .25), (6, 8, .25)]   # (開始小節, 終了小節, 拍の長さ)
T0 = .6                                    # 最初の音までの間
CH = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]   # Am F C G（1小節ずつ）
KEYS = "123456789*0#"
# 数字キー → 和音のなかの何番目の音か（キーの場所を音にする：上の段ほど高い）
def key_for(chord, step, stage):
    pat = [0, 1, 2, 1, 2, 0, 1, 2] if stage < 2 else [0, 2, 1, 2, 0, 2, 1, 2, 0, 1, 2, 1, 2, 0, 2, 1]
    i = pat[step % len(pat)]
    oct_ = 1 if stage >= 2 and step % 4 == 3 else 0
    m = chord[i] + 12 + 12 * oct_
    row = 0 if oct_ else (2 - i)           # 高い音ほど上の段
    col = (step * 2 + i) % 3
    k = "123456789"[row * 3 + col]
    return k, m
presses = []
for si, (b0, b1, step_b) in enumerate(STAGES):
    t = T0 + b0 * BAR; n = 0
    while t < T0 + b1 * BAR - 1e-6:
        bar = int((t - T0) / BAR) % 4
        k, m = key_for(CH[bar], n, si); presses.append((t, k, m, si)); t += step_b * BEAT; n += 1
DROP = T0 + 8 * BAR; END = DROP + 2 * BAR + .4; DUR = END

# ---------- 音（11/25 オーナー「とにかく心地よい音を目指したい」：とがった音をやめ、ガラスのマリンバ・ベル・やわらかいパッドと残響で） ----------
from scipy.signal import fftconvolve
N = int(SR * (DUR + 3)); L = np.zeros(N); R = np.zeros(N); DL = np.zeros(N); DR = np.zeros(N)   # D＝残響に送る分
def put(sig, t, pan=.5, g=1.0, wet=.35):
    i = int(t * SR); j = min(N, i + len(sig)); s = sig[:j - i] * g; cl, cr = math.cos(pan * math.pi / 2) * 1.41, math.sin(pan * math.pi / 2) * 1.41
    L[i:j] += s * cl; R[i:j] += s * cr; DL[i:j] += s * cl * wet; DR[i:j] += s * cr * wet
f_ = lambda m: 440 * 2 ** ((m - 69) / 12)
def env(tt, att, dec): return np.minimum(1, tt / att) * np.exp(-tt * dec)
def marimba(m, dur=1.4, soft=0.0):   # ガラスのマリンバ：基音＋4倍音（すぐ消える）＋少しのガラスの倍音
    tt = np.arange(int(SR * dur)) / SR; f = f_(m)
    x = np.sin(2 * np.pi * f * tt) * env(tt, .002, 3.2) + .30 * np.sin(2 * np.pi * f * 3.93 * tt) * env(tt, .001, 14) + .12 * np.sin(2 * np.pi * f * 2.76 * tt) * env(tt, .001, 6) * (1 - soft)
    return x * .28
def bell(m, dur=2.4):                 # FM のベル（澄んだ長い余韻）
    tt = np.arange(int(SR * dur)) / SR; f = f_(m); I = 2.2 * np.exp(-tt * 3)
    return np.sin(2 * np.pi * f * tt + I * np.sin(2 * np.pi * f * 3.5 * tt)) * env(tt, .003, 1.6) * .16
def pad(ms, dur, g=.10, att=.6):      # やわらかいパッド：少しずらしたサイン波
    tt = np.arange(int(SR * dur)) / SR; x = np.zeros(len(tt))
    for m in ms:
        for dt in (-.06, .06): f = f_(m) * 2 ** (dt / 12); x += np.sin(2 * np.pi * f * tt) + .18 * np.sin(4 * np.pi * f * tt)
    return x / (2 * len(ms)) * np.minimum(1, tt / att) * np.minimum(1, (dur - tt) / .4) * g
def kick(g=1.0):                      # 丸いキック（心臓の鼓動くらい）
    tt = np.arange(int(SR * .3)) / SR; ph = 2 * np.pi * np.cumsum(46 + 60 * np.exp(-tt * 30)) / SR
    return np.sin(ph) * env(tt, .004, 11) * .55 * g
rng = np.random.default_rng(3)
def shaker(d=.06):                    # シェイカー：高い音だけのやわらかい「サッ」
    tt = np.arange(int(SR * d)) / SR; n = rng.normal(0, 1, len(tt)); n = n - np.convolve(n, np.ones(6) / 6, "same")
    return n * np.minimum(1, tt / .008) * np.exp(-tt * 55) * .035
def wood(m=79):                       # 木の「コッ」（手拍子の代わり）
    tt = np.arange(int(SR * .12)) / SR; f = f_(m)
    return (np.sin(2 * np.pi * f * tt) + .4 * np.sin(2 * np.pi * f * 2.3 * tt)) * env(tt, .001, 40) * .10
def sub(m, dur):                      # やわらかい低音
    tt = np.arange(int(SR * dur)) / SR; f = f_(m - 24)
    return np.sin(2 * np.pi * f * tt) * np.minimum(1, tt / .03) * np.minimum(1, (dur - tt) / .2) * .22
for t, k, m, si in presses:
    put(marimba(m, 1.4 if si < 2 else 1.0, soft=.5 * (si >= 2)), t, .3 + .4 * ((m % 7) / 6), .62 - .06 * si, .30 + .05 * si)
for b in range(8 * 4):
    t = T0 + b * BEAT; bar = b // 4
    if bar >= 2: put(kick(.8 if bar < 4 else 1.0), t, .5, 1.0, .05)
    if bar >= 2: put(shaker(), t + BEAT / 2, .62, 1.0, .1)
    if bar >= 4: put(shaker(.04), t + BEAT / 4, .38, .7, .1); put(shaker(.04), t + 3 * BEAT / 4, .38, .7, .1)
    if bar >= 4 and b % 2 == 1: put(wood(), t, .45, 1.0, .4)
    if b % 4 == 0: put(pad(CH[bar % 4], BAR, .07 + .02 * (bar >= 4)), t, .5, 1.0, .6)
    if bar >= 4 and b % 4 == 0: put(sub(CH[bar % 4][0], BAR * .95), t, .5, 1.0, 0)
# ため（最後の2小節）：ベルの分散和音が上へ、だんだん細かく。パッドがふくらむ
q = 0; t = T0 + 6 * BAR
while t < DROP - .02:
    u = (t - (T0 + 6 * BAR)) / (2 * BAR); ch = CH[3] if u > .5 else CH[2]
    put(bell(ch[q % 3] + 12 * (1 + q // 3 % 3)), t, .2 + .6 * (q % 2), .35 + .5 * u, .6); q += 1
    t += BEAT / 2 if u < .5 else BEAT / 4
put(pad([55, 59, 62, 67], 2 * BAR, .13, att=2 * BAR * .9), T0 + 6 * BAR, .5, 1.0, .6)
# ほどける：大きな和音（パッド＋ベル）、鼓動のキックと低音
for bi, ch in enumerate([[57, 60, 64, 69, 72], [53, 57, 60, 65, 69]]):
    t = DROP + bi * BAR; put(pad(ch, BAR + .6, .16, .05), t, .5, 1.0, .6); put(sub(ch[0], BAR * .95), t, .5, 1.1, 0)
    put(bell(ch[-1] + 12), t, .5, .9, .7)
    for qq in range(4): put(kick(1.0), t + qq * BEAT, .5, 1.0, .05); put(shaker(), t + qq * BEAT + BEAT / 2, .62, 1.0, .1)
    for qq in range(8): put(marimba(ch[(qq * 2) % 5] + 12, 1.2), t + qq * BEAT / 2, .2 + .6 * (qq % 2), .5, .5)
# 残響（2.4秒のやわらかい部屋）
tt = np.arange(int(SR * 2.4)) / SR
def ir(seed):
    n = np.random.default_rng(seed).normal(0, 1, len(tt)) * np.exp(-tt * 2.6); return np.convolve(n, np.ones(24) / 24, "same") * .02
L += fftconvolve(DL, ir(11))[:N]; R += fftconvolve(DR, ir(12))[:N]
mix = np.stack([L, R], 1); pk = np.max(np.abs(mix)); mix = np.tanh(mix / pk * 1.3) / np.tanh(1.3) * .89
os.makedirs("build_passcode", exist_ok=True)
with wave.open("build_passcode/a.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix[:int(SR * DUR)] * 32767).astype(np.int16).tobytes())

# ---------- 絵（11/25 オーナー「マットなんだけど程よくブラーも効いてる」：ネオンの発光をやめ、ぼかした色の背景にすりガラスのキー） ----------
# 段ごとの背景の色（くすんだ色）：夕方の青灰 → セージ → 砂 → ばら → ほどけ（明るい乳白）
TINT = [((70, 78, 96), (120, 128, 150), (95, 90, 110)), ((70, 86, 80), (130, 150, 138), (98, 108, 96)),
        ((96, 84, 70), (165, 148, 120), (120, 104, 92)), ((98, 76, 84), (170, 136, 148), (122, 96, 108)), ((130, 120, 118), (205, 192, 186), (160, 148, 150))]
def blobs(cols, seed):   # 大きくぼかした色の雲（背景）
    rs = np.random.default_rng(seed); im = Image.new("RGB", (W // 4, H // 4), cols[0]); d = ImageDraw.Draw(im)
    for q in range(7):
        x, y, r = rs.uniform(0, W // 4), rs.uniform(0, H // 4), rs.uniform(60, 150); c = cols[1 + q % 2]
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    return im.filter(ImageFilter.GaussianBlur(60)).resize((W + 240, H + 240), Image.BICUBIC)
BGS = [np.asarray(blobs(c, 5 + i), np.float32) for i, c in enumerate(TINT)]
grain = (np.random.default_rng(9).normal(0, 1, (H, W, 1)) * 3.0).astype(np.float32)   # マットに見せる細かい粒
KW, KG = 232, 40; KX0 = (W - 3 * KW - 2 * KG) // 2; KY0 = 800; KH = 196
kpos = {}
for i, k in enumerate(KEYS):
    r, c = divmod(i, 3); kpos[k] = (KX0 + c * (KW + KG), KY0 + r * (KH + 36))
def stage_at(t): return 0 if t < T0 + 2 * BAR else 1 if t < T0 + 4 * BAR else 2 if t < T0 + 6 * BAR else 3 if t < DROP else 4
def frame(t):
    si = stage_at(t); prev = max(0, si - 1); edges = [T0 + 2 * BAR, T0 + 4 * BAR, T0 + 6 * BAR, DROP]
    u = min(1, (t - edges[si - 1]) / .8) if si > 0 else 1      # 段が変わったら .8秒で色を移す
    beat_ph = ((t - T0) / BEAT) % 1 if t > T0 else 1; pulse = math.exp(-beat_ph * 5) if si >= 1 else 0
    ox, oy = int(120 + 60 * math.sin(t * .23)), int(120 + 80 * math.cos(t * .17))   # 背景はゆっくり漂う
    bg = BGS[prev][oy:oy + H, ox:ox + W] * (1 - u) + BGS[si][oy:oy + H, ox:ox + W] * u
    bg = bg * (1 + .05 * pulse) + grain
    im = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    soft = Image.new("RGBA", (W // 2, H // 2), (0, 0, 0, 0)); g = ImageDraw.Draw(soft)   # ぼかして重ねる光（ほんのり）
    done = [p for p in presses if p[0] <= t]; n_in = len(done) % 6 if t < DROP else 6
    if done and len(done) % 6 == 0 and t - done[-1][0] < .18 and t < DROP: n_in = 6
    d.text((W / 2, 260), "押すたびに、1音", font=fT, fill=(255, 255, 255, 235), anchor="mm")
    d.text((W / 2, 316), "だんだん、速くなる", font=fS, fill=(255, 255, 255, 170), anchor="mm")
    d.text((W / 2, 392), ["x1", "x2", "x4", "x4+", "OPEN"][si], font=fL, fill=(255, 255, 255, 190), anchor="mm")
    for j in range(6):
        cx = W / 2 + (j - 2.5) * 90; cy = 520; s = 18; pts = [(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)]
        if j < n_in: d.polygon(pts, fill=(255, 255, 255, 235))
        else: d.polygon(pts, outline=(255, 255, 255, 170), width=3)
    for k, (x, y) in kpos.items():
        if k in "*#": continue
        hit = [p for p in done if p[1] == k]; e = t - hit[-1][0] if hit else 9
        if t >= DROP: e = min(e, ((t - DROP) * 2 / BEAT + "1234567890".index(k) * .37) % 1 * .6)
        lit = math.exp(-e * 6)
        rr = [x, y, x + KW, y + KH]
        d.rounded_rectangle(rr, radius=44, fill=(255, 255, 255, int(34 + 120 * lit)))   # すりガラス：白をうすく重ねる
        if lit > .05: g.rounded_rectangle([v / 2 for v in rr], radius=22, fill=(255, 250, 240, int(110 * lit)))
        d.text((x + KW / 2, y + KH / 2), k, font=fD, fill=(255, 255, 255, 245), anchor="mm")
    if t >= DROP:   # ほどけ：ぼんやりした光の輪
        e = t - DROP
        for q in range(4):
            eq = (e - q * BEAT) % (BEAT * 4) if e > q * BEAT else -1
            if 0 <= eq < 1.4:
                r = 80 + 500 * eq; a = int(120 * (1 - eq / 1.4))
                g.ellipse([W / 4 - r / 2, 575 - r / 2, W / 4 + r / 2, 575 + r / 2], outline=(255, 252, 245, a), width=6)
    soft = soft.filter(ImageFilter.GaussianBlur(14)).resize((W, H), Image.BILINEAR)
    im = Image.alpha_composite(Image.alpha_composite(im, soft), ov)
    return im.convert("RGB")

if __name__ == "__main__":
    still = os.environ.get("STILLS")
    if still:
        for s in still.split(","): frame(float(s)).save(f"build_passcode/s_{float(s):05.2f}.jpg", quality=88)
        sys.exit()
    nf = int(DUR * FPS)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", "build_passcode/a.wav",
                          "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", OUT], stdin=subprocess.PIPE)
    for i in range(nf):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait(); print(OUT, round(DUR, 2), "秒")
