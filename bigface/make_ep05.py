# bigface/make_ep05.py — EP.05『ビッグフェイスのかくれんぼ』の音と文字を付けて書き出す（セリフなし。冒頭のタイトルだけ声。VOICEVOX:雨晴はう）
import os, sys, glob, subprocess, wave, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "src"))
import music
FR, OUT = sys.argv[1], sys.argv[2]
W, H, FPS, SR = 1080, 1920, 30, 48000
E = json.load(open(f"{HERE}/cg/ep05_time.json"))
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
        d.text((W // 2, 118), "EP.05", font=F_EP, fill=INK + (int(200 * a),), anchor="mm")
        d.text((W // 2, 190), "ビッグフェイスのかくれんぼ", font=F_TITLE, fill=INK + (int(255 * a),), anchor="mm")
        d.text((24, H - 40), "VOICEVOX:雨晴はう", font=F_CR, fill=(255, 255, 255, int(190 * a)), anchor="lm")
    k = t - E["eye"] - 0.42
    if k > 0:
        sc_ = 1.0 if k > 0.6 else 1 - 0.35 * np.exp(-k * 11) * np.cos(k * 18)
        lg = Image.new("RGBA", (W, 260), (0, 0, 0, 0)); ImageDraw.Draw(lg).text((W // 2, 130), "ザ・ビッグフェイス", font=F_LOGO, fill=INK + (255,), anchor="mm")
        lg = lg.resize((max(1, int(W * sc_)), max(1, int(260 * sc_)))); L.alpha_composite(lg, (int((W - lg.width) / 2), int(1250 - lg.height / 2)))
    return L
n = int((E["end"] + 0.3) * SR); mix = np.zeros(n, np.float32); rng = np.random.default_rng(15); tt = np.arange(n) / SR
def put(x, at, g=1.0):
    i = int(at * SR); j = min(n, i + len(x))
    if 0 <= i < n: mix[i:j] += g * np.asarray(x[: j - i], np.float32)
def env(L, a, d): t = np.arange(L) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def lp(x, k): c = np.ones(k) / k; return np.convolve(np.convolve(x, c, "same"), c, "same")
def hp(x, k): return x - lp(x, k)
# 公園の空気（昼）→ 夕方は少し静かに。林の中はさらに静か
amb = lp(rng.standard_normal(n), 120).astype(np.float32); amb /= np.abs(amb).max()
mix += amb * np.where(tt < E["s5"], 0.022, np.where(tt < E["eye"], 0.014, 0))
def bird(p=1.0):
    L = int(0.12 * SR); t = np.arange(L) / SR; return np.sin(2 * np.pi * (3000 * p + 700 * np.sin(t * 80)) * t) * env(L, 0.004, 0.03) * 0.06
for at in np.arange(0.3, E["s5"] - 0.5, 2.3): put(bird(0.9 + 0.2 * rng.random()), at + rng.random() * 0.8)
def cricket():   # 夕方の虫（小さく）
    L = int(0.5 * SR); t = np.arange(L) / SR; return np.sin(2 * np.pi * 4200 * t) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 28 * t))) * env(L, 0.02, 0.25) * 0.02
for at in np.arange(E["s5"] + 0.5, E["eye"] - 0.5, 1.3): put(cricket(), at + rng.random() * 0.4)
def step(p=1.0):
    L = int(0.07 * SR); t = np.arange(L) / SR
    return np.sin(2 * np.pi * 380 * p * t) * env(L, 0.002, 0.02) * 0.4 + lp(rng.standard_normal(L), 4) * env(L, 0.001, 0.012) * 0.25
def steps(a, b, gap=0.42, p=1.0, g=0.4):
    k = a
    while k < b: put(step(p + 0.05 * rng.random()), k, g); k += gap
steps(0.5, 2.6)                                                    # ビッグフェイスが来る
steps(E["s2"] + 0.7, E["find1"] - 0.2, 0.28, 1.4, 0.3)             # オニが探しに来る（小さい足音）
steps(E["s3"] + 0.6, E["find2"] - 0.2, 0.28, 1.4, 0.3)
steps(E["s4"] + 0.6, E["find3"] - 0.2, 0.28, 1.4, 0.3)
steps(E["s4"] + 0.2, E["s5"] - 0.4, 0.3, 1.6, 0.15)                # 小さい子が林へ
steps(E["go"], E["s9"] + 0.2, 0.26, 1.6, 0.25); steps(E["s9"] + 0.3, E["hug"], 0.24, 1.6, 0.3)
def found():     # 見つかった「ぴこっ」と、しょんぼり（下がる2音）
    a = music.toypiano(music.hz(84), 0.25) * 0.6; return a
for f in (E["find1"], E["find2"], E["find3"]):
    put(found(), f, 0.6)
    put(music.pizz(music.hz(67), 0.4), f + 0.55, 0.35); put(music.pizz(music.hz(62), 0.6), f + 0.8, 0.35)
def kotsu():     # ふたが頭の上でかたかた
    L = int(0.06 * SR); t = np.arange(L) / SR; return (np.sin(2 * np.pi * 520 * t) * 0.5 + lp(rng.standard_normal(L), 3) * 0.4) * env(L, 0.001, 0.015)
for k in range(4): put(kotsu(), E["s3"] + 0.5 + k * 0.9 + rng.random() * 0.2, 0.35)
def count(i):    # 人数を数える指（小さな「ぽん」）。4つめは鳴らない（ひとり足りない）
    return music.softpluck(music.hz(72 + 2 * i), 0.3)
for i, c in enumerate([E["c1"], E["c2"], E["c3"]]): put(count(i), c + 0.1, 0.5)
def stretchS(sec):   # 首がのびる（ゆっくり上がる音）
    L = int(sec * SR); t = np.arange(L) / SR; f = 160 + 420 * (t / sec) ** 1.4
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.2) * np.minimum(1, (sec - t) / 0.3) * 0.18
put(stretchS(E["stretchEnd"] - E["stretch"]), E["stretch"], 0.9)
def shrinkS(sec):
    L = int(sec * SR); t = np.arange(L) / SR; f = 520 - 340 * (t / sec) ** 0.8
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.1) * np.minimum(1, (sec - t) / 0.2) * 0.14
put(shrinkS(1.4), E["retract"], 0.8)
for nn, at in [(79, 0.0), (84, 0.25)]: put(music.toypiano(music.hz(nn), 0.8), E["see"] + 0.3 + at, 0.4)   # 林の子が顔に気づく
for nn in (72, 76, 79): put(music.feltpiano(music.hz(nn), 1.6), E["hug"], 0.22)                          # だきつく
def sniff():      # すすり泣き（息を吸う短い音。声ではない）
    L = int(0.22 * SR); t = np.arange(L) / SR; x = hp(rng.standard_normal(L), 3) * np.sin(np.pi * t / 0.22) ** 2; return x / np.abs(x).max() * 0.08
for at in list(np.arange(E["s6"] + 0.4, E["s7"] - 0.3, 0.9)) + list(np.arange(E["s8"] + 0.2, E["see"] - 0.2, 0.9)): put(sniff(), at + 0.1 * rng.random(), 0.8)
import render
render.set_voice("0.vvm", 10, 0.85, -0.03, 0.9)
render._YOMI["ビッグフェイスのかくれんぼ"] = "ビッグフェイスの、カクレンボ"
render.tts("ビッグフェイスのかくれんぼ", "/tmp/bf5_call.wav")
with wave.open("/tmp/bf5_call.wav") as w: v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; vsr = w.getframerate()
v = np.interp(np.arange(int(len(v) * SR / vsr)) / SR, np.arange(len(v)) / vsr, v).astype(np.float32); put(v, E["call"], 0.95)
def fade(x, fi, fo):
    L = len(x); e = np.ones(L); a = int(fi * SR); b = int(fo * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if b: e[-b:] = np.linspace(1, 0, b)
    return x * e
def lay(x, at, g):
    i0 = int(at * SR); mix[i0:i0 + len(x)] += g * x[: n - i0]
lay(fade(music.bgm02(E["s5"] - 2.4), 0.8, 1.2), 2.4, 0.26)                 # かくれんぼ
lay(fade(music.bgm04(E["stretch"] - E["s5"]), 0.6, 1.2), E["s5"], 0.26)     # ひとり足りない・林の中
lay(fade(music.bgm05(E["eye"] - E["stretch"] - 0.2), 1.5, 1.0), E["stretch"] + 0.2, 0.28)   # 目印になる
# アイキャッチ（ボフン系の音は使わない。11/15 ゲンタさん「ボフンみたいなSEは全撤廃」）
for nn, at in [(76, 0.45), (79, 0.62), (81, 0.79)]: put(music.toypiano(music.hz(nn), 0.6), E["eye"] + at, 0.5)
for nn in (72, 76, 79, 84): put(music.toypiano(music.hz(nn), 1.4), E["eye"] + 1.0, 0.28)
mix = np.clip(mix, -1, 1)
with wave.open("/tmp/bf_ep05.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
files = sorted(glob.glob(f"{FR}/*.jpg")); os.makedirs("/tmp/bf_ep05_frames", exist_ok=True)
for i, f in enumerate(files):
    im = Image.open(f).convert("RGBA"); im.alpha_composite(text_layer(i / FPS)); im.convert("RGB").save(f"/tmp/bf_ep05_frames/{i:05d}.jpg", quality=95)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", "/tmp/bf_ep05_frames/%05d.jpg", "-i", "/tmp/bf_ep05.wav",
                "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-shortest", OUT], check=True)
print("ok", OUT, len(files), "コマ")
