# bigface/make_ep04.py — EP.04『ビッグフェイスのぼうし』の音と文字を付けて書き出す（セリフなし。冒頭のタイトルだけ声。VOICEVOX:雨晴はう）
import os, sys, glob, subprocess, wave, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "src"))
import music
FR, OUT = sys.argv[1], sys.argv[2]
W, H, FPS, SR = 1080, 1920, 30, 48000
E = json.load(open(f"{HERE}/cg/ep04_time.json"))
F_TITLE = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 70)
F_EP = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 34)
F_LOGO = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 102)
F_CR = ImageFont.truetype(f"{HERE}/fonts/ZenKakuGothicNew-Medium.ttf", 24)
INK = (0x34, 0x3B, 0x3A)
def alpha(t, a, b, f=0.3):
    if t < a or t > b: return 0.0
    return min(1, (t - a) / f, (b - t) / f)
def text_layer(t):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    a = alpha(t, E["title_in"], E["title_out"])
    if a > 0:
        d.text((W // 2, 118), "EP.04", font=F_EP, fill=INK + (int(200 * a),), anchor="mm")
        d.text((W // 2, 190), "ビッグフェイスのぼうし", font=F_TITLE, fill=INK + (int(255 * a),), anchor="mm")
        d.text((24, H - 40), "VOICEVOX:雨晴はう", font=F_CR, fill=(255, 255, 255, int(190 * a)), anchor="lm")
    k = t - E["eye"] - 0.42
    if k > 0:
        sc_ = 1.0 if k > 0.6 else 1 - 0.35 * np.exp(-k * 11) * np.cos(k * 18)
        lg = Image.new("RGBA", (W, 260), (0, 0, 0, 0)); ImageDraw.Draw(lg).text((W // 2, 130), "ザ・ビッグフェイス", font=F_LOGO, fill=INK + (255,), anchor="mm")
        lg = lg.resize((max(1, int(W * sc_)), max(1, int(260 * sc_)))); L.alpha_composite(lg, (int((W - lg.width) / 2), int(1250 - lg.height / 2)))
    return L
n = int((E["end"] + 0.3) * SR); mix = np.zeros(n, np.float32); rng = np.random.default_rng(11); tt = np.arange(n) / SR
def put(x, at, g=1.0):
    i = int(at * SR); j = min(n, i + len(x))
    if 0 <= i < n: mix[i:j] += g * np.asarray(x[: j - i], np.float32)
def env(L, a, d): t = np.arange(L) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def lp(x, k): c = np.ones(k) / k; return np.convolve(np.convolve(x, c, "same"), c, "same")
def hp(x, k): return x - lp(x, k)
amb = lp(rng.standard_normal(n), 120).astype(np.float32); amb /= np.abs(amb).max()
mix += amb * np.where(tt < E["s4"], 0.02, np.where(tt < E["s6"], 0.03, np.where(tt < E["eye"], 0.015, 0)))
def pop(p=1.0):   # 帽子がちょこんと乗る「ぽこ」
    L = int(0.12 * SR); t = np.arange(L) / SR; f = (700 * p) * np.exp(-t * 18) + 250
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.002, 0.03) * 0.5
for i, h in enumerate([E["h1"], E["h2"], E["h3"], E["h4"]]): put(pop(1.25 - 0.12 * i), h + 0.55, 0.7)
def rumble(sec):  # 鉢がころがる「ごろごろ」
    L = int(sec * SR); t = np.arange(L) / SR; x = lp(rng.standard_normal(L), 60) * (0.6 + 0.4 * np.sin(2 * np.pi * 7 * t)); return x / np.abs(x).max() * 0.35 * np.minimum(1, t / 0.2) * np.minimum(1, (sec - t) / 0.2)
put(rumble(E["grab"] - 0.2 - E["roll"]), E["roll"], 0.8)
def stretchS():
    L = int(0.9 * SR); t = np.arange(L) / SR; f = 200 + 240 * (t / 0.9) ** 1.5
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.1) * np.minimum(1, (0.9 - t) / 0.15) * 0.22
put(stretchS(), E["grab"], 0.9); put(stretchS(), E["lift"], 0.8)
def thunk():      # 鉢をかぶる「ごぽっ」（中が空洞の音）
    L = int(0.4 * SR); t = np.arange(L) / SR; f = 160 * np.exp(-t * 6) + 90
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.003, 0.12); x += 0.3 * np.sin(2 * np.pi * np.cumsum(f * 2.1) / SR) * env(L, 0.003, 0.06); return x * 0.8
put(thunk(), E["potOn"], 1.0); put(thunk() * 0.6, E["place"] + 0.15, 0.8)
def step(p=1.0):
    L = int(0.07 * SR); t = np.arange(L) / SR
    return np.sin(2 * np.pi * 380 * p * t) * env(L, 0.002, 0.02) * 0.4 + lp(rng.standard_normal(L), 4) * env(L, 0.001, 0.012) * 0.25
for k in range(int((E["s6"] - E["s4"]) / 0.42)): put(step(1 + 0.05 * (k % 2)), E["s4"] + 0.1 + k * 0.42, 0.4)
# 雨（帰り道）と、鉢の中のしずく「ぽちゃん」（鉢の中で響く）
rn = hp(lp(rng.standard_normal(n), 3), 40).astype(np.float32); rn /= np.abs(rn).max()
ra = np.clip((tt - E["rain"]) / 1.4, 0, 1) * (tt < E["s6"]); mix += rn * ra * 0.1
def tick():
    L = int(0.03 * SR); t = np.arange(L) / SR; return (np.sin(2 * np.pi * 1300 * t) * 0.4 + hp(rng.standard_normal(L), 4) * 0.4) * env(L, 0.0005, 0.008)
k = E["rain"] + 0.5
while k < E["s6"]: put(tick(), k, 0.25); k += 0.05 + 0.08 * rng.random()   # 鉢に当たる雨
def plink(p=1.0):
    L = int(0.35 * SR); t = np.arange(L) / SR; f = (1100 + 600 * np.exp(-t * 40)) * p
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.001, 0.05); echo = np.zeros(L); d = int(0.07 * SR); echo[d:] = x[:-d] * 0.45; return (x + echo) * 0.5
for at in np.arange(E["drip"], E["s6"] - 0.2, 0.7): put(plink(0.9 + 0.2 * rng.random()), at, 0.8)
# 朝：小鳥、芽「ぴょこ」、水
def bird(p=1.0):
    L = int(0.12 * SR); t = np.arange(L) / SR; return np.sin(2 * np.pi * (3000 * p + 700 * np.sin(t * 80)) * t) * env(L, 0.004, 0.03) * 0.06
for at in np.arange(E["s6"] + 0.3, E["eye"], 1.9): put(bird(0.9 + 0.2 * rng.random()), at + rng.random() * 0.6)
def sproutS():
    L = int(0.25 * SR); t = np.arange(L) / SR; f = 600 + 1400 * t / 0.25; return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.003, 0.09) * 0.35
put(sproutS(), E["sprout"] + 0.9, 0.9)
wl = int((E["waterEnd"] - E["water"]) * SR); wx = lp(rng.standard_normal(wl), 3); wx = wx / np.abs(wx).max() * np.minimum(1, np.arange(wl) / SR / 0.15) * np.minimum(1, (wl / SR - np.arange(wl) / SR) / 0.2)
put(wx * 0.18, E["water"], 1.0)
def pofu(p=1.0):
    L = int(0.32 * SR); t = np.arange(L) / SR; f = (150 * np.exp(-t * 5) + 70) * p
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.004, 0.09) + lp(rng.standard_normal(L), 28) * env(L, 0.006, 0.05) * 1.6
import render
render.set_voice("0.vvm", 10, 0.85, -0.03, 0.9)
render._YOMI["ビッグフェイスのぼうし"] = "ビッグフェイスの、ボーシ"
render.tts("ビッグフェイスのぼうし", "/tmp/bf4_call.wav")
with wave.open("/tmp/bf4_call.wav") as w: v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; vsr = w.getframerate()
v = np.interp(np.arange(int(len(v) * SR / vsr)) / SR, np.arange(len(v)) / vsr, v).astype(np.float32); put(v, E["call"], 0.95)
def fade(x, fi, fo):
    L = len(x); e = np.ones(L); a = int(fi * SR); b = int(fo * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if b: e[-b:] = np.linspace(1, 0, b)
    return x * e
m1 = fade(music.bgm02(E["rain"] + 1.0 - 2.4), 0.8, 1.8); i0 = int(2.4 * SR); mix[i0:i0 + len(m1)] += 0.28 * m1[: n - i0]   # 店〜帰り道（雨で消える）
m2 = fade(music.bgm05(E["eye"] - E["s6"] - 0.4), 1.5, 0.8); i0 = int((E["s6"] + 0.4) * SR); mix[i0:i0 + len(m2)] += 0.28 * m2[: n - i0]   # 朝
put(pofu(1.05), E["eye"] + 0.32, 1.0)
for nn, at in [(76, 0.45), (79, 0.62), (81, 0.79)]: put(music.toypiano(music.hz(nn), 0.6), E["eye"] + at, 0.5)
for nn in (72, 76, 79, 84): put(music.toypiano(music.hz(nn), 1.4), E["eye"] + 1.0, 0.28)
mix = np.clip(mix, -1, 1)
with wave.open("/tmp/bf_ep04.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
files = sorted(glob.glob(f"{FR}/*.jpg")); os.makedirs("/tmp/bf_ep04_frames", exist_ok=True)
for i, f in enumerate(files):
    im = Image.open(f).convert("RGBA"); im.alpha_composite(text_layer(i / FPS)); im.convert("RGB").save(f"/tmp/bf_ep04_frames/{i:05d}.jpg", quality=95)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", "/tmp/bf_ep04_frames/%05d.jpg", "-i", "/tmp/bf_ep04.wav",
                "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-shortest", OUT], check=True)
print("ok", OUT, len(files), "コマ")
