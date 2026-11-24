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

# ---------- 音 ----------
N = int(SR * (DUR + 1)); L = np.zeros(N); R = np.zeros(N)
def put(sig, t, pan=.5, g=1.0):
    i = int(t * SR); j = min(N, i + len(sig)); s = sig[:j - i] * g
    L[i:j] += s * math.cos(pan * math.pi / 2) * 1.41; R[i:j] += s * math.sin(pan * math.pi / 2) * 1.41
f_ = lambda m: 440 * 2 ** ((m - 69) / 12)
def lp(x, a):
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)): s += a * (x[i] - s); y[i] = s
    return y
def pluck(m, dur=.5, bright=.35):
    tt = np.arange(int(SR * dur)) / SR; f = f_(m)
    x = sum(((-1) ** (k + 1)) * np.sin(2 * np.pi * f * k * tt) / k for k in range(1, 9)) * np.exp(-tt * (6 + 10 * bright))
    x += .6 * np.sin(2 * np.pi * f * tt) * np.exp(-tt * 4)
    return x * np.minimum(1, tt / .003) * .25
def kick():
    tt = np.arange(int(SR * .32)) / SR; ph = 2 * np.pi * np.cumsum(48 + 110 * np.exp(-tt * 28)) / SR
    return np.sin(ph) * np.exp(-tt * 9) * .9
rng = np.random.default_rng(3)
def hat(d=.05):
    tt = np.arange(int(SR * d)) / SR; n = rng.normal(0, 1, len(tt)); n = n - lp(n, .35); return n * np.exp(-tt * 70) * .12
def clap():
    tt = np.arange(int(SR * .18)) / SR; n = rng.normal(0, 1, len(tt)); n = lp(n - lp(n, .08), .5)
    env = np.exp(-tt * 22) * (1 + .6 * (np.sin(tt * 2 * np.pi * 90) > 0) * (tt < .03)); return n * env * .25
def saw_chord(ms, dur, g=.12, att=.02):
    tt = np.arange(int(SR * dur)) / SR; x = np.zeros(len(tt))
    for m in ms:
        for dt in (-.11, 0, .11):
            f = f_(m) * 2 ** (dt / 12); x += 2 * ((tt * f + rng.random()) % 1) - 1
    x = lp(x / (3 * len(ms)), .18); env = np.minimum(1, tt / att) * np.minimum(1, (dur - tt) / .25)
    return x * env * g
def bass(m, dur):
    tt = np.arange(int(SR * dur)) / SR; f = f_(m - 24)
    return (np.sin(2 * np.pi * f * tt) + .25 * np.sin(4 * np.pi * f * tt)) * np.minimum(1, tt / .005) * np.exp(-tt * 3) * .35
for t, k, m, si in presses:
    put(pluck(m, .45 if si < 2 else .3, .2 + .15 * si), t, .35 + .3 * ((m % 5) / 4), .55 + .1 * si)
for b in range(8 * 4):          # 拍
    t = T0 + b * BEAT; bar = b // 4
    if bar >= 2: put(kick(), t, .5, .8 if bar < 6 else .9)
    if bar >= 2: put(hat(), t + BEAT / 2, .6)
    if bar >= 4: put(hat(.03), t + BEAT / 4, .4, .7); put(hat(.03), t + 3 * BEAT / 4, .4, .7)
    if bar >= 4 and b % 2 == 1: put(clap(), t, .5)
    if bar >= 4 and b % 4 == 0: put(bass(CH[bar % 4][0], BAR * .9), t)
# ため（最後の2小節）：手拍子の連打が細かくなり、音が上がる
for q in range(32):
    t = T0 + 6 * BAR + q * (2 * BAR / 32)
    if q >= 16 or q % 2 == 0: put(clap(), t, .5, .25 + .6 * q / 32)
tt = np.arange(int(SR * 2 * BAR)) / SR; f = 200 * 2 ** (tt / (2 * BAR) * 2.5)
nz = rng.normal(0, 1, len(tt)); put(lp(nz - lp(nz, .05), .3) * (tt / (2 * BAR)) ** 2 * .10, T0 + 6 * BAR)
put(np.sin(2 * np.pi * np.cumsum(f) / SR) * (tt / (2 * BAR)) ** 2 * .05, T0 + 6 * BAR)
# ほどける：大きな和音と低音、キックの4つ打ち
for bi, ch in enumerate([[57, 60, 64, 69, 72], [53, 57, 60, 65, 69]]):
    t = DROP + bi * BAR; put(saw_chord(ch, BAR, .16, .01), t); put(bass(ch[0], BAR * .95), t, .5, 1.2)
    for q in range(4): put(kick(), t + q * BEAT, .5, 1.0); put(hat(), t + q * BEAT + BEAT / 2, .6, 1.2)
    for q in range(8): put(pluck(ch[(q * 2) % 5] + 12, .35, .5), t + q * BEAT / 2, .2 + .6 * (q % 2), .45)
mix = np.stack([L, R], 1); pk = np.max(np.abs(mix)); mix = np.tanh(mix / pk * 1.6) / np.tanh(1.6) * .89
os.makedirs("build_passcode", exist_ok=True)
with wave.open("build_passcode/a.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix[:int(SR * DUR)] * 32767).astype(np.int16).tobytes())

# ---------- 絵 ----------
PAL = [(110, 200, 255), (140, 255, 210), (255, 200, 120), (255, 130, 200)]   # 段ごとの光の色
KW, KG = 230, 44; KX0 = (W - 3 * KW - 2 * KG) // 2; KY0 = 820
kpos = {}
for i, k in enumerate(KEYS):
    r, c = divmod(i, 3); kpos[k] = (KX0 + c * (KW + KG), KY0 + r * (KW + KG - 60))
def bg_base():
    im = Image.new("RGB", (W, H), (6, 8, 16)); d = ImageDraw.Draw(im)
    for y in range(0, H, 4): d.line([0, y, W, y], fill=(6, 8 + y // 160, 16 + y // 90))
    return im
BG = bg_base()
def frame(t):
    im = BG.copy(); glow = Image.new("RGB", (W // 2, H // 2)); g = ImageDraw.Draw(glow); d = ImageDraw.Draw(im)
    si = 0 if t < T0 + 2 * BAR else 1 if t < T0 + 4 * BAR else 2 if t < T0 + 6 * BAR else 3 if t < DROP else 4
    col = PAL[min(si, 3)]
    beat_ph = ((t - T0) / BEAT) % 1 if t > T0 else 1; pulse = math.exp(-beat_ph * 6) if si >= 1 else 0
    # 背景の細い格子（拍で明るくなる）
    a = int(14 + 26 * pulse) if si >= 1 else 12
    for x in range(0, W + 1, 90): d.line([x, 0, x, H], fill=(a // 2, a // 2, a))
    for y in range(0, H + 1, 90): d.line([0, y, W, y], fill=(a // 2, a // 2, a))
    # 押された数（その段のなかで6桁ずつ）
    done = [p for p in presses if p[0] <= t]; n_in = len(done) % 6 if t < DROP else 6
    if done and len(done) % 6 == 0 and t - done[-1][0] < .18 and t < DROP: n_in = 6
    # 上の文字
    d.text((W / 2, 250), "押すたびに、1音", font=fT, fill=(235, 238, 250), anchor="mm")
    d.text((W / 2, 305), "だんだん、速くなる", font=fS, fill=(150, 160, 190), anchor="mm")
    lv = ["x1", "x2", "x4", "x4+", "OPEN"][si]
    d.text((W / 2, 380), lv, font=fL, fill=col, anchor="mm")
    # 6つの枠（ひし形）
    for j in range(6):
        cx = W / 2 + (j - 2.5) * 96; cy = 520; s = 22
        on = j < n_in; pts = [(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)]
        if on:
            d.polygon(pts, fill=col); g.ellipse([cx / 2 - 22, cy / 2 - 22, cx / 2 + 22, cy / 2 + 22], fill=tuple(int(v * .7) for v in col))
        else: d.polygon(pts, outline=(120, 130, 160), width=3)
    # キー
    for k, (x, y) in kpos.items():
        if k in "*#": continue
        hit = [p for p in done if p[1] == k]; e = t - hit[-1][0] if hit else 9
        if t >= DROP: e = min(e, ((t - DROP) * 2 / BEAT + "1234567890".index(k) * .37) % 1 * .5)
        lit = math.exp(-e * 7)
        fill = tuple(int(18 + (c - 18) * lit * .55) for c in col) if lit > .02 else (18, 22, 36)
        rr = [x, y, x + KW, y + KW - 60]
        d.rounded_rectangle(rr, radius=38, fill=fill, outline=tuple(int(70 + (c - 70) * lit) for c in col), width=3)
        if lit > .05: g.rounded_rectangle([v / 2 for v in rr], radius=19, fill=tuple(int(c * lit * .8) for c in col))
        d.text((x + KW / 2, y + (KW - 60) / 2), k, font=fD, fill=(255, 255, 255) if lit > .3 else (200, 206, 225), anchor="mm")
    # ほどけ：光の輪
    if t >= DROP:
        e = t - DROP
        for q in range(4):
            eq = (e - q * BEAT) % (BEAT * 4) if e > q * BEAT else -1
            if 0 <= eq < 1.2:
                r = 60 + 900 * eq; a = 1 - eq / 1.2
                d.ellipse([W / 2 - r, 1150 - r, W / 2 + r, 1150 + r], outline=tuple(int(c * a) for c in PAL[q % 4]), width=4)
    glow = glow.filter(ImageFilter.GaussianBlur(18)).resize((W, H), Image.BILINEAR)
    im = Image.fromarray(np.minimum(255, np.asarray(im, np.int16) + np.asarray(glow, np.int16)).astype(np.uint8))
    return im

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
