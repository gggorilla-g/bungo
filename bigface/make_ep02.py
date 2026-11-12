# bigface/make_ep02.py — EP.02『ビッグフェイスのかさ』の音と文字を付けて書き出す（言葉なし。雨音は左右で動かす）
# 使い方: python3 bigface/make_ep02.py <CGのコマのフォルダ> <出力mp4>
# 時刻は bigface/cg/ep02_time.json（bf.js と同じファイル）
import os, sys, glob, subprocess, wave, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import music
FR, OUT = sys.argv[1], sys.argv[2]
W, H, FPS, SR = 1080, 1920, 30, 48000
E = json.load(open(f"{HERE}/cg/ep02_time.json"))
F_TITLE = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 70)
F_EP = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 34)
F_LOGO = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 102)
INK = (0x34, 0x3B, 0x3A)

def alpha(t, a, b, f=0.3):
    if t < a or t > b: return 0.0
    return min(1, (t - a) / f, (b - t) / f)
def text_layer(t):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    a = alpha(t, E["title_in"], E["title_out"])
    if a > 0:
        d.text((W // 2, 118), "EP.02", font=F_EP, fill=INK + (int(200 * a),), anchor="mm")
        d.text((W // 2, 190), "ビッグフェイスのかさ", font=F_TITLE, fill=INK + (int(255 * a),), anchor="mm")
    k = t - E["eye"] - 0.42
    if k > 0:
        sc_ = 1.0 if k > 0.6 else 1 - 0.35 * np.exp(-k * 11) * np.cos(k * 18)
        lg = Image.new("RGBA", (W, 260), (0, 0, 0, 0)); ImageDraw.Draw(lg).text((W // 2, 130), "ザ・ビッグフェイス", font=F_LOGO, fill=INK + (255,), anchor="mm")
        lg = lg.resize((max(1, int(W * sc_)), max(1, int(260 * sc_))))
        L.alpha_composite(lg, (int((W - lg.width) / 2), int(1250 - lg.height / 2)))
    return L

# ---- 音（ステレオ）
n = int((E["end"] + 0.3) * SR); Lc = np.zeros(n, np.float32); Rc = np.zeros(n, np.float32); bgm = np.zeros(n, np.float32)
rng = np.random.default_rng(7); tt = np.arange(n) / SR
def put(x, at, g=1.0, pan=0.0):           # pan: -1 左 〜 +1 右
    i = int(at * SR); j = min(n, i + len(x))
    if 0 <= i < n:
        x = np.asarray(x[: j - i], np.float32) * g
        Lc[i:j] += x * np.sqrt((1 - pan) / 2) * 1.414; Rc[i:j] += x * np.sqrt((1 + pan) / 2) * 1.414
def env(L, a, d): t = np.arange(L) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def lp(x, k): c = np.ones(k) / k; return np.convolve(np.convolve(x, c, "same"), c, "same")
def hp(x, k): return x - lp(x, k)
# 雨：左右で別のざあざあ（少しずつ揺らす）
for ch, seed in ((Lc, 11), (Rc, 12)):
    r = np.random.default_rng(seed); x = hp(lp(r.standard_normal(n), 3), 40).astype(np.float32); x /= np.abs(x).max()
    lvl = np.where(tt < E["eye"], 0.11, 0.0) * (1 + 0.15 * np.sin(tt * 0.7 + seed))
    ch += x * lvl
def tick(p=1.0):                          # 傘に当たる雨つぶ「ぱた」
    L = int(0.03 * SR); t = np.arange(L) / SR
    return (np.sin(2 * np.pi * 1800 * p * t) * 0.3 + hp(rng.standard_normal(L), 4) * 0.5) * env(L, 0.0005, 0.006)
def drip(p=1.0):                          # ほおに当たる「ぴと」
    L = int(0.06 * SR); t = np.arange(L) / SR; f = (900 + 700 * np.exp(-t * 60)) * p
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.001, 0.012) * 0.6
def wstep(p=1.0):                         # ぬれた足音「ぴちゃ」
    L = int(0.12 * SR); t = np.arange(L) / SR
    return (np.sin(2 * np.pi * 480 * p * t) * env(L, 0.002, 0.02) * 0.35 + hp(rng.standard_normal(L), 3) * env(L, 0.003, 0.04) * 0.4)
def hopS():                               # カエルがはねる「ぴょ」
    L = int(0.12 * SR); t = np.arange(L) / SR; f = 500 + 900 * t / 0.12
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.003, 0.04) * 0.35
def splash():
    L = int(0.7 * SR); x = lp(rng.standard_normal(L), 2) * env(L, 0.004, 0.16); t = np.arange(L) / SR
    return x * 0.8 + np.sin(2 * np.pi * (220 * np.exp(-t * 4) + 90) * t) * env(L, 0.004, 0.1) * 0.4
def close_umb():                          # 傘を閉じる「ばさ、かちっ」
    L = int(0.4 * SR); x = lp(rng.standard_normal(L), 6) * env(L, 0.02, 0.1) * 0.5
    c = np.zeros(int(0.05 * SR)); t = np.arange(len(c)) / SR; c = np.sin(2 * np.pi * 2400 * t) * env(len(c), 0.0005, 0.005) * 0.4
    return np.concatenate([x, c])
def pofu(p=1.0):
    L = int(0.32 * SR); t = np.arange(L) / SR; f = (150 * np.exp(-t * 5) + 70) * p
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.004, 0.09) + lp(rng.standard_normal(L), 28) * env(L, 0.006, 0.05) * 1.6
# 傘の雨音：傘がある側から（s1〜s4、s5 は差し出した先）。s8 で閉じるまで
umb_pan = lambda t: (-0.6 if t < E["swap"] else 0.6) if t < E["s3"] else 0.0
k = 0.0
while k < E["close"]:
    if not (E["s6"] <= k < E["s8"] and False):
        put(tick(0.9 + 0.3 * rng.random()), k, 0.22 if k < E["s5"] else 0.14, umb_pan(k))
    k += 0.045 + 0.06 * rng.random()
# ほおの「ぴと」：ぬれている側から（s2）
for at in np.arange(E["s2"] + 0.3, E["s3"], 0.38):
    pan = 0.7 if at < E["swap"] + 0.5 else -0.7
    put(drip(0.9 + 0.2 * rng.random()), at, 0.35, pan)
for at in np.arange(E["s5"] + 1.0, E["s7"], 0.5): put(drip(0.95 + 0.1 * rng.random()), at, 0.18, rng.uniform(-0.4, 0.4))
# 足音
for i in range(11): put(wstep(1 + 0.05 * (i % 2)), 0.25 + i * 0.42, 0.4, -0.5 + i * 0.05)
for i in range(3): put(wstep(), E["s5"] + 0.3 + i * 0.35, 0.4)
for i in range(2): put(wstep(), E["hop1"] + 0.8 + i * 0.35, 0.4)
for i in range(16): put(wstep(1 + 0.05 * (i % 2)), E["s9"] + 0.2 + i * 0.36, 0.38)
for i in range(8): put(hopS(), E["s9"] + 0.1 + i * 0.75, 0.25, 0.2)
put(hopS(), E["hop1"], 0.5, 0.2); put(hopS(), E["hop2"], 0.5, 0.3); put(hopS(), E["splash"] - 0.5, 0.5, 0.2)
put(splash(), E["splash"], 0.9, 0.1)
put(close_umb(), E["close"], 0.8)
# BGM：序盤だけ（日常）。カエルに会うところで消える。あとは雨と足音だけ（仕様書）
def fade(x, fi, fo):
    L = len(x); e = np.ones(L); a = int(fi * SR); b = int(fo * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if b: e[-b:] = np.linspace(1, 0, b)
    return x * e
m = fade(music.bgm05(E["notice"] + 0.8), 0.6, 2.0); bgm[: len(m)] += 0.32 * m[: n]
# アイキャッチ（EP.01 と同じ）
put(pofu(1.05), E["eye"] + 0.32, 1.0)
for nn, at in [(76, 0.45), (79, 0.62), (81, 0.79)]: i = int((E["eye"] + at) * SR); x = music.toypiano(music.hz(nn), 0.6); bgm[i:i + len(x)] += 0.5 * x[: n - i]
for nn in (72, 76, 79, 84): i = int((E["eye"] + 1.0) * SR); x = music.toypiano(music.hz(nn), 1.4); bgm[i:i + len(x)] += 0.28 * x[: n - i]
Lc += bgm * 0.9; Rc += bgm * 0.9
st = np.clip(np.stack([Lc, Rc], 1), -1, 1)
with wave.open("/tmp/bf_ep02.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())
# ---- 映像
files = sorted(glob.glob(f"{FR}/*.jpg")); os.makedirs("/tmp/bf_ep02_frames", exist_ok=True)
for i, f in enumerate(files):
    Image.alpha_composite(Image.open(f).convert("RGBA"), text_layer(i / FPS)).convert("RGB").save(f"/tmp/bf_ep02_frames/{i:05d}.jpg", quality=95)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", "/tmp/bf_ep02_frames/%05d.jpg", "-i", "/tmp/bf_ep02.wav",
                "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-shortest", OUT], check=True)
print("ok", OUT, len(files), "コマ")
