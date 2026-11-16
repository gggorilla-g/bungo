# bigface/make_ep06.py — EP.06『ビッグフェイスのバス』の音と文字を付けて書き出す（セリフなし。冒頭のタイトルだけ声。VOICEVOX:雨晴はう）
import os, sys, glob, subprocess, wave, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "src"))
import music
FR, OUT = sys.argv[1], sys.argv[2]
W, H, FPS, SR = 1080, 1920, 30, 48000
E = json.load(open(f"{HERE}/cg/ep06_time.json"))
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
        d.text((W // 2, 118), "EP.06", font=F_EP, fill=INK + (int(200 * a),), anchor="mm")
        d.text((W // 2, 190), "ビッグフェイスのバス", font=F_TITLE, fill=INK + (int(255 * a),), anchor="mm")
        d.text((24, H - 40), "VOICEVOX:雨晴はう", font=F_CR, fill=(255, 255, 255, int(190 * a)), anchor="lm")
    k = t - E["eye"] - 0.42
    if k > 0:
        sc_ = 1.0 if k > 0.6 else 1 - 0.35 * np.exp(-k * 11) * np.cos(k * 18)
        lg = Image.new("RGBA", (W, 260), (0, 0, 0, 0)); ImageDraw.Draw(lg).text((W // 2, 130), "ザ・ビッグフェイス", font=F_LOGO, fill=INK + (255,), anchor="mm")
        lg = lg.resize((max(1, int(W * sc_)), max(1, int(260 * sc_)))); L.alpha_composite(lg, (int((W - lg.width) / 2), int(1250 - lg.height / 2)))
    return L
n = int((E["end"] + 0.3) * SR); mix = np.zeros(n, np.float32); rng = np.random.default_rng(16); tt = np.arange(n) / SR
def put(x, at, g=1.0):
    i = int(at * SR); j = min(n, i + len(x))
    if 0 <= i < n: mix[i:j] += g * np.asarray(x[: j - i], np.float32)
def env(L, a, d): t = np.arange(L) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def lp(x, k): c = np.ones(k) / k; return np.convolve(np.convolve(x, c, "same"), c, "same")
def hp(x, k): return x - lp(x, k)
# 町の空気 → バスのエンジン（低いうなり。止まっている時は小さく）
amb = lp(rng.standard_normal(n), 120).astype(np.float32); amb /= np.abs(amb).max()
mix += amb * np.where(tt < E["eye"], 0.018, 0)
moving = np.clip((tt - E["door"] - 1.2) / 1.0, 0, 1) * (tt < E["eye"])
moving = moving * np.where((tt > E["stop"]) & (tt < E["enter1"] + 0.6), 0.35, 1.0)
eng = (np.sin(2 * np.pi * 46 * tt) * 0.6 + np.sin(2 * np.pi * 92 * tt) * 0.25) * (1 + 0.15 * np.sin(2 * np.pi * 7 * tt)) + lp(rng.standard_normal(n), 30) * 0.5
inside = (tt >= E["s4"]) & (tt < E["s10"])
mix += (eng * moving * np.where(inside, 0.05, 0.035)).astype(np.float32)
arr = np.clip(1 - (tt - E["arrive0"]) / (E["arrive1"] - E["arrive0"]), 0, 1) * (tt >= E["arrive0"]) * (tt < E["arrive1"] + 0.2)
mix += (eng * arr * 0.05).astype(np.float32)
def step(p=1.0):
    L = int(0.07 * SR); t = np.arange(L) / SR
    return np.sin(2 * np.pi * 380 * p * t) * env(L, 0.002, 0.02) * 0.4 + lp(rng.standard_normal(L), 4) * env(L, 0.001, 0.012) * 0.25
def steps(a, b, gap=0.42, p=1.0, g=0.4):
    k = a
    while k < b: put(step(p + 0.05 * rng.random()), k, g); k += gap
def door(sec=0.7):   # 扉の「プシュー」
    L = int(sec * SR); t = np.arange(L) / SR; x = hp(rng.standard_normal(L), 4) * np.minimum(1, t / 0.03) * np.exp(-t / (sec * 0.45)); return x / np.abs(x).max() * 0.12
def squeak(sec):     # 顔が扉でぎゅっとなる（ゴムがこすれる音）
    L = int(sec * SR); t = np.arange(L) / SR; f = 600 + 180 * np.sin(t * 9)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sin(t * 40)) * np.minimum(1, t / 0.05) * np.minimum(1, (sec - t) / 0.1) * 0.06
def bonk():          # 天井にゴツン（小さめの木の音）
    L = int(0.25 * SR); t = np.arange(L) / SR; return (np.sin(2 * np.pi * 180 * t) * 0.6 + np.sin(2 * np.pi * 410 * t) * 0.3) * env(L, 0.001, 0.06)
def bell():          # 降車ベルではなく、発車の小さな合図
    return music.toypiano(music.hz(88), 0.5) * 0.4
def brake(sec=1.0):  # ブレーキの「キキー」（高すぎない）
    L = int(sec * SR); t = np.arange(L) / SR; f = 1500 - 250 * t / sec
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.05) * np.minimum(1, (sec - t) / 0.3) * 0.05
def tap():           # 席をとんとん
    L = int(0.05 * SR); t = np.arange(L) / SR; return lp(rng.standard_normal(L), 3) * env(L, 0.001, 0.012) * 0.5
def zip_bag():       # かばんのチャック
    L = int(0.35 * SR); t = np.arange(L) / SR; x = hp(rng.standard_normal(L), 2) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 60 * t))) * np.sin(np.pi * t / 0.35); return x / np.abs(x).max() * 0.05
def sticky():        # 湿布をぺたっ
    L = int(0.08 * SR); t = np.arange(L) / SR; return lp(rng.standard_normal(L), 6) * env(L, 0.002, 0.02) * 0.6
steps(0.3, E["arrive1"] - 0.3, 0.5, 1.0, 0.25)
put(door(), E["door"], 1.0); put(squeak(1.2), E["s2"] + 1.6, 1.0); put(door(0.6), E["s3"] - 0.6, 0.8)
put(bell(), E["s3"] + 0.4, 0.5)
steps(E["stand"] + 0.4, E["bonk"] - 0.1, 0.3, 1.1, 0.25); put(bonk(), E["bonk"], 0.6)
for nn, at in [(76, 0.0), (72, 0.18)]: put(music.pizz(music.hz(nn), 0.4), E["bonk"] + 0.35 + at, 0.3)
steps(E["bonk"] + 0.6, E["floor"] - 0.3, 0.32, 1.1, 0.22)
put(door(), E["stop"] + 0.3, 0.9); steps(E["enter0"], E["look"], 0.45, 1.5, 0.2); put(door(0.6), E["sit"] + 0.4, 0.7)
for k in range(3): put(tap(), E["pat"] + 0.1 + k * 0.14, 0.6)
for nn, at in [(79, 0.0), (84, 0.22)]: put(music.toypiano(music.hz(nn), 0.8), E["sit"] + 0.2 + at, 0.35)   # すわれた
for nn in (72, 76, 79): put(music.feltpiano(music.hz(nn), 1.8), E["lean"], 0.2)                             # ほほがまくら
put(brake(1.0), E["brake"] - 0.2, 1.0); put(bonk(), E["bump"], 0.45)
put(zip_bag(), E["bag"] + 0.1, 1.0); put(sticky(), E["stick"], 0.8)
for nn, at in [(84, 0.0), (88, 0.2)]: put(music.toypiano(music.hz(nn), 0.8), E["stick"] + 0.3 + at, 0.35)
import render
render.set_voice("0.vvm", 10, 0.85, -0.03, 0.9)
render._YOMI["ビッグフェイスのバス"] = "ビッグフェイスの、バス"
render.tts("ビッグフェイスのバス", "/tmp/bf6_call.wav")
with wave.open("/tmp/bf6_call.wav") as w: v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; vsr = w.getframerate()
v = np.interp(np.arange(int(len(v) * SR / vsr)) / SR, np.arange(len(v)) / vsr, v).astype(np.float32); put(v, E["call"], 0.95)
def fade(x, fi, fo):
    L = len(x); e = np.ones(L); a = int(fi * SR); b = int(fo * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if b: e[-b:] = np.linspace(1, 0, b)
    return x * e
def lay(x, at, g):
    i0 = int(at * SR); mix[i0:i0 + len(x)] += g * x[: n - i0]
lay(fade(music.bgm02(E["s4"] - 2.4 + 0.5), 0.8, 1.4), 2.4, 0.24)                 # 乗るまで
lay(fade(music.bgm04(E["s6"] - E["s4"]), 0.6, 1.0), E["s4"], 0.22)              # せまい車内・おばあさん
lay(fade(music.bgm05(E["brake"] - 0.3 - E["s6"]), 1.0, 0.4), E["s6"], 0.24)     # まくら（ブレーキの手前で切る）
lay(fade(music.bgm05(E["eye"] - E["wake"]), 1.0, 1.0), E["wake"], 0.24)         # 湿布〜走っていく
# アイキャッチ（ボフン系の音は使わない。11/15 ゲンタさん「ボフンみたいなSEは全撤廃」）
for nn, at in [(76, 0.45), (79, 0.62), (81, 0.79)]: put(music.toypiano(music.hz(nn), 0.6), E["eye"] + at, 0.5)
for nn in (72, 76, 79, 84): put(music.toypiano(music.hz(nn), 1.4), E["eye"] + 1.0, 0.28)
mix = np.clip(mix, -1, 1)
with wave.open("/tmp/bf_ep06.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
files = sorted(glob.glob(f"{FR}/*.jpg")); os.makedirs("/tmp/bf_ep06_frames", exist_ok=True)
for i, f in enumerate(files):
    im = Image.open(f).convert("RGBA"); im.alpha_composite(text_layer(i / FPS)); im.convert("RGB").save(f"/tmp/bf_ep06_frames/{i:05d}.jpg", quality=95)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", "/tmp/bf_ep06_frames/%05d.jpg", "-i", "/tmp/bf_ep06.wav",
                "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-shortest", OUT], check=True)
print("ok", OUT, len(files), "コマ")
