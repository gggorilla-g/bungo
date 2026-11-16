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
# 町の空気 → バスのエンジン（低いうなり。止まっている間は小さく）
amb = lp(rng.standard_normal(n), 120).astype(np.float32); amb /= np.abs(amb).max()
mix += amb * np.where(tt < E["eye"], 0.018, 0)
eng = (np.sin(2 * np.pi * 46 * tt) * 0.6 + np.sin(2 * np.pi * 92 * tt) * 0.25) * (1 + 0.15 * np.sin(2 * np.pi * 7 * tt)) + lp(rng.standard_normal(n), 30) * 0.5
run = np.where((tt > E["stopA"]) & (tt < E["stopB"]), 0.3, 1.0) * (tt < E["eye"])
mix += (eng * run * np.where(tt < E["s2"], 0.035, 0.045)).astype(np.float32)
def step(p=1.0):
    L = int(0.07 * SR); t = np.arange(L) / SR
    return np.sin(2 * np.pi * 380 * p * t) * env(L, 0.002, 0.02) * 0.4 + lp(rng.standard_normal(L), 4) * env(L, 0.001, 0.012) * 0.25
def steps(a, b, gap=0.42, p=1.0, g=0.4):
    k = a
    while k < b: put(step(p + 0.05 * rng.random()), k, g); k += gap
def door(sec=0.7):   # 扉の「プシュー」
    L = int(sec * SR); t = np.arange(L) / SR; x = hp(rng.standard_normal(L), 4) * np.minimum(1, t / 0.03) * np.exp(-t / (sec * 0.45)); return x / np.abs(x).max() * 0.12
def stretchS(sec):   # 首がのびる（ゆっくり上がる音）
    L = int(sec * SR); t = np.arange(L) / SR; f = 160 + 420 * (t / sec) ** 1.4
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.2) * np.minimum(1, (sec - t) / 0.3) * 0.16
def soft():          # ほほがそっとふれる
    L = int(0.25 * SR); t = np.arange(L) / SR; return lp(rng.standard_normal(L), 20) * np.sin(np.pi * t / 0.25) ** 2 * 0.25
steps(E["manIn"], E["manStop"], 0.4, 1.0, 0.28); steps(E["manGo"], E["manGo"] + 1.6, 0.4, 1.0, 0.28)
for nn, at in [(67, 0.0), (64, 0.3)]: put(music.pizz(music.hz(nn), 0.5), E["manGo"] + 0.2 + at, 0.3)   # やめて行ってしまう（下がる2音）
put(door(), E["stopA"] + 0.2, 0.9); steps(E["ladyIn"], E["ladyStop"], 0.5, 1.4, 0.2); steps(E["ladyLook"] + 1.4, E["toSeat"], 0.5, 1.4, 0.2); put(door(0.6), E["stopB"] - 0.5, 0.7)
put(stretchS(1.6), E["rise"], 0.9)
for nn, at in [(79, 0.0), (84, 0.22)]: put(music.toypiano(music.hz(nn), 0.8), E["rise"] + 1.7 + at, 0.35)   # 席が空く
for nn in (72, 76, 79): put(music.feltpiano(music.hz(nn), 1.8), E["sit"] + 0.8, 0.2)                        # すわれた
put(soft(), E["lower"] + 1.5, 1.0)
for nn in (67, 72, 76, 79): put(music.feltpiano(music.hz(nn), 2.2), E["lower"] + 1.6, 0.16)                 # ほほがまくら
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
lay(fade(music.bgm02(E["manGo"] + 0.2 - 2.4), 0.8, 1.2), 2.4, 0.22)              # 走るバス（人が行ってしまうところで消える）
lay(fade(music.bgm05(E["eye"] - E["rise"] - 1.5), 1.5, 1.0), E["rise"] + 1.5, 0.24)   # 席が空いてから
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
