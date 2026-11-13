# bigface/make_ep03.py — EP.03『ビッグフェイスの集合写真』の音と文字を付けて書き出す
# セリフなし。冒頭のタイトルだけ声で読む（11/13 ゲンタさん「タイトル読んでいいです」）。声は VOICEVOX:雨晴はう（クレジットを画面に出す）
# 三脚のカメラから見たカット（s2〜s4、s10）は四すみにファインダーの印。写真（s7、s11）は白いふち付きの1枚に見せる。シャッターで白く光る
import os, sys, glob, subprocess, wave, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "src"))
import music
FR, OUT = sys.argv[1], sys.argv[2]
W, H, FPS, SR = 1080, 1920, 30, 48000
E = json.load(open(f"{HERE}/cg/ep03_time.json"))
F_TITLE = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 70)
F_EP = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 34)
F_LOGO = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 102)
F_CR = ImageFont.truetype(f"{HERE}/fonts/ZenKakuGothicNew-Medium.ttf", 24)
INK = (0x34, 0x3B, 0x3A)
def alpha(t, a, b, f=0.3):
    if t < a or t > b: return 0.0
    return min(1, (t - a) / f, (b - t) / f)
POV = lambda t: (E["s2"] <= t < E["s5"]) or (E["s10"] <= t < E["s11"])
PHOTO = lambda t: (E["s7"] <= t < E["s8"]) or (E["s11"] <= t < E["eye"])
def frame_img(im, t):
    if PHOTO(t):   # 白いふちの写真：背景はその絵をぼかして暗く
        k = E["s7"] if t < E["s8"] else E["s11"]; u = min(1, (t - k) / 0.35)
        bg = im.filter(ImageFilter.GaussianBlur(24)).point(lambda v: int(v * 0.55))
        ph = im.resize((int(W * 0.8), int(H * 0.8))); b = 26
        card = Image.new("RGB", (ph.width + 2 * b, ph.height + 2 * b + 70), (250, 248, 242)); card.paste(ph, (b, b))
        card = card.convert("RGBA").rotate(-2.2 * u + (1 - u) * 0, expand=True, resample=Image.BICUBIC)
        sc = 0.97 + 0.03 * u; card = card.resize((int(card.width * sc), int(card.height * sc)))
        out = bg.convert("RGBA"); out.alpha_composite(card, ((W - card.width) // 2, (H - card.height) // 2 - 20)); return out
    out = im.convert("RGBA")
    if POV(t):     # ファインダーの四すみ
        d = ImageDraw.Draw(out); m, L, w = 70, 90, 6; c = (255, 255, 255, 200)
        for x0, y0, sx, sy in [(m, m + 160, 1, 1), (W - m, m + 160, -1, 1), (m, H - m - 160, 1, -1), (W - m, H - m - 160, -1, -1)]:
            d.line([(x0, y0), (x0 + sx * L, y0)], fill=c, width=w); d.line([(x0, y0), (x0, y0 + sy * L)], fill=c, width=w)
    return out
def text_layer(t):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    a = alpha(t, E["title_in"], E["title_out"])
    if a > 0:
        d.text((W // 2, 118), "EP.03", font=F_EP, fill=INK + (int(200 * a),), anchor="mm")
        d.text((W // 2, 190), "ビッグフェイスの集合写真", font=F_TITLE, fill=INK + (int(255 * a),), anchor="mm")
        d.text((24, H - 40), "VOICEVOX:雨晴はう", font=F_CR, fill=(255, 255, 255, int(190 * a)), anchor="lm")
    k = t - E["eye"] - 0.42
    if k > 0:
        sc_ = 1.0 if k > 0.6 else 1 - 0.35 * np.exp(-k * 11) * np.cos(k * 18)
        lg = Image.new("RGBA", (W, 260), (0, 0, 0, 0)); ImageDraw.Draw(lg).text((W // 2, 130), "ザ・ビッグフェイス", font=F_LOGO, fill=INK + (255,), anchor="mm")
        lg = lg.resize((max(1, int(W * sc_)), max(1, int(260 * sc_)))); L.alpha_composite(lg, (int((W - lg.width) / 2), int(1250 - lg.height / 2)))
    for s in (E["shot1"], E["shot2"]):   # シャッターの光
        f = 1 - (t - s) / 0.25
        if 0 < f <= 1: L.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(235 * f))))
    return L
# ---- 音
n = int((E["end"] + 0.3) * SR); mix = np.zeros(n, np.float32); rng = np.random.default_rng(9); tt = np.arange(n) / SR
def put(x, at, g=1.0):
    i = int(at * SR); j = min(n, i + len(x))
    if 0 <= i < n: mix[i:j] += g * np.asarray(x[: j - i], np.float32)
def env(L, a, d): t = np.arange(L) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def lp(x, k): c = np.ones(k) / k; return np.convolve(np.convolve(x, c, "same"), c, "same")
amb = lp(rng.standard_normal(n), 90).astype(np.float32); amb /= np.abs(amb).max(); mix += amb * np.where(tt < E["eye"], 0.03, 0)
def bird(p=1.0):
    L = int(0.12 * SR); t = np.arange(L) / SR; return np.sin(2 * np.pi * (3000 * p + 700 * np.sin(t * 80)) * t) * env(L, 0.004, 0.03) * 0.06
for at in np.arange(0.5, E["eye"], 2.3): put(bird(0.9 + 0.2 * rng.random()), at + rng.random() * 0.8)
def step(p=1.0):
    L = int(0.07 * SR); t = np.arange(L) / SR
    return np.sin(2 * np.pi * 380 * p * t) * env(L, 0.002, 0.02) * 0.4 + lp(rng.standard_normal(L), 4) * env(L, 0.001, 0.012) * 0.25
for k in range(9): put(step(1 + 0.05 * (k % 2)), 0.5 + k * 0.44, 0.45)
for k in range(3): put(step(), E["s3"] + 0.35 + k * 0.36, 0.45)
for k in range(4): put(step(), E["s4"] + 0.25 + k * 0.36, 0.4)
for k in range(5): put(step(), E["point"] + 0.7 + k * 0.42, 0.45)
for k in range(4): put(step(1.2), E["pull"] - 0.9 + k * 0.22, 0.35)
def stretch():   # 首がのびる「にゅーっ」：上がっていく丸い音
    L = int(1.0 * SR); t = np.arange(L) / SR; f = 180 + 260 * (t / 1.0) ** 1.5
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.1) * np.minimum(1, (1.0 - t) / 0.15) * 0.25
put(stretch(), E["stretch"], 0.9)
def shutter():
    L = int(0.12 * SR); x = lp(rng.standard_normal(L), 2) * env(L, 0.0005, 0.012); y = np.zeros(int(0.06 * SR))
    return np.concatenate([x, y, x * 0.7])
def beep():
    L = int(0.07 * SR); t = np.arange(L) / SR; return np.sin(2 * np.pi * 2100 * t) * np.minimum(1, (0.07 - t) / 0.01).clip(0, 1) * 0.18
put(shutter(), E["shot1"], 0.9); put(shutter(), E["shot2"], 0.9)
k = E["timer"]
while k < E["shot2"] - 0.05: put(beep(), k, 0.9); k += 0.33 if k < E["shot2"] - 0.9 else 0.125
def pofu(p=1.0):
    L = int(0.32 * SR); t = np.arange(L) / SR; f = (150 * np.exp(-t * 5) + 70) * p
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.004, 0.09) + lp(rng.standard_normal(L), 28) * env(L, 0.006, 0.05) * 1.6
# 声：タイトル
import render
render.set_voice("0.vvm", 10, 0.85, -0.03, 0.9)
render._YOMI["ビッグフェイスの集合写真"] = "ビッグフェイスの、シューゴーシャシン"
render.tts("ビッグフェイスの集合写真", "/tmp/bf3_call.wav")
with wave.open("/tmp/bf3_call.wav") as w: v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; vsr = w.getframerate()
v = np.interp(np.arange(int(len(v) * SR / vsr)) / SR, np.arange(len(v)) / vsr, v).astype(np.float32); put(v, E["call"], 0.95)
# BGM：コミカル（s1〜s5）→ 写真と顔のアップは音楽なし → 呼び戻されてからあたたかく
def fade(x, fi, fo):
    L = len(x); e = np.ones(L); a = int(fi * SR); b = int(fo * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if b: e[-b:] = np.linspace(1, 0, b)
    return x * e
m1 = fade(music.bgm02(E["s6"] - 2.4), 0.8, 1.6); i0 = int(2.4 * SR); mix[i0:i0 + len(m1)] += 0.3 * m1[: n - i0]
m2 = fade(music.bgm05(E["eye"] - E["beckon"] + 0.2), 1.0, 0.8); i0 = int(E["beckon"] * SR); mix[i0:i0 + len(m2)] += 0.3 * m2[: n - i0]
put(pofu(1.05), E["eye"] + 0.32, 1.0)
for nn, at in [(76, 0.45), (79, 0.62), (81, 0.79)]: put(music.toypiano(music.hz(nn), 0.6), E["eye"] + at, 0.5)
for nn in (72, 76, 79, 84): put(music.toypiano(music.hz(nn), 1.4), E["eye"] + 1.0, 0.28)
mix = np.clip(mix, -1, 1)
with wave.open("/tmp/bf_ep03.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
# ---- 映像
files = sorted(glob.glob(f"{FR}/*.jpg")); os.makedirs("/tmp/bf_ep03_frames", exist_ok=True)
for i, f in enumerate(files):
    t = i / FPS; im = frame_img(Image.open(f).convert("RGB"), t); im.alpha_composite(text_layer(t))
    im.convert("RGB").save(f"/tmp/bf_ep03_frames/{i:05d}.jpg", quality=95)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", "/tmp/bf_ep03_frames/%05d.jpg", "-i", "/tmp/bf_ep03.wav",
                "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-shortest", OUT], check=True)
print("ok", OUT, len(files), "コマ")
