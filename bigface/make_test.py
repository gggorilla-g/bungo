# bigface/make_test.py — 『ビッグフェイスの〇〇』Phase 1 テスト映像（EP.01 冒頭「せまいドア」約8.6秒）の音と文字を付けて書き出す
# 使い方: python3 bigface/make_test.py <CGのコマのフォルダ> <出力mp4>
# 文字：タイトル Zen Maru Gothic Bold、セリフ Zen Kaku Gothic New Medium（どちらも SIL Open Font License、bigface/fonts）
# 音：足音「とて」、顔の接触「ぽふっ」、外の空気・店の中の空気はここで合成（オリジナル）。声は VOICEVOX（仮の声）
import os, sys, glob, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

FR, OUT = sys.argv[1], sys.argv[2]
W, H, FPS, SR = 1080, 1920, 30, 48000
HERE = os.path.dirname(os.path.abspath(__file__))
F_TITLE = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 70)
F_EP = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 34)
F_SUB = ImageFont.truetype(f"{HERE}/fonts/ZenKakuGothicNew-Medium.ttf", 64)
F_CR = ImageFont.truetype(f"{HERE}/fonts/ZenKakuGothicNew-Medium.ttf", 24)
INK = (0x34, 0x3B, 0x3A)
# 時刻は bf.js の T と合わせる
T = dict(walk1=2.4, wind=3.75, hit=4.05, cut=4.6, are=7.15, end=8.6)
VOICE = dict(vvm="0.vvm", style=10, speed=0.82, pitch=-0.05, intonation=0.55)

def alpha(t, a, b, f=0.22):
    if t < a or t > b: return 0.0
    return min(1, (t - a) / f, (b - t) / f)

def text_layer(t):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    a = alpha(t, 0.45, 2.25)                         # タイトルは最初の動きの上に約1.8秒
    if a > 0:
        d.text((W // 2, 118), "EP.01", font=F_EP, fill=INK + (int(200 * a),), anchor="mm")
        d.text((W // 2, 190), "ビッグフェイスのせまいドア", font=F_TITLE, fill=INK + (int(255 * a),), anchor="mm")
    a = alpha(t, T["are"] + 0.05, T["end"] + 1, 0.15)
    if a > 0:                                        # セリフ：白文字＋ひかえめな濃い影。顔にかからないよう、扉の上の壁（上の余白）に置く
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
        ds.text((W // 2 + 3, 236 + 4), "……あれ？", font=F_SUB, fill=(0x20, 0x26, 0x25, int(150 * a)), anchor="mm")
        L = Image.alpha_composite(L, sh.filter(ImageFilter.GaussianBlur(5)))
        ImageDraw.Draw(L).text((W // 2, 236), "……あれ？", font=F_SUB, fill=(255, 255, 255, int(255 * a)), anchor="mm")
    return L

# ---- 音
n = int((T["end"] + 0.2) * SR); mix = np.zeros(n, np.float32)
rng = np.random.default_rng(3)
def put(x, at, g=1.0):
    i = int(at * SR); j = min(n, i + len(x)); mix[i:j] += g * x[: j - i]
def env(L, a, d): t = np.arange(L) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def lp(x, k):                                         # かんたんな低域フィルタ（移動平均を2回）
    c = np.ones(k) / k; return np.convolve(np.convolve(x, c, "same"), c, "same")
def step(pitch=1.0):                                  # とて：小さな木の床をたたく丸い音
    L = int(0.07 * SR); t = np.arange(L) / SR
    x = np.sin(2 * np.pi * 620 * pitch * t) * env(L, 0.002, 0.018) * 0.5 + lp(rng.standard_normal(L), 6) * env(L, 0.001, 0.008) * 0.25
    return x.astype(np.float32)
def pofu():                                           # ぽふっ：弾む低い音＋やわらかい息の音（金属音にしない）
    L = int(0.32 * SR); t = np.arange(L) / SR
    f = 150 * np.exp(-t * 5) + 70
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.004, 0.09)
    air = lp(rng.standard_normal(L), 28) * env(L, 0.006, 0.05) * 1.6
    return (0.9 * body + air).astype(np.float32)
# 外の空気（第1カット）と店の中の空気（第2カット）
amb = lp(rng.standard_normal(n), 120).astype(np.float32); amb /= np.abs(amb).max()
tt = np.arange(n) / SR
mix += amb * np.where(tt < T["cut"], 0.035, 0.018)
for at in [0.7, 1.9, 3.1]:                            # 遠くの小鳥（小さく）
    L = int(0.09 * SR); t = np.arange(L) / SR
    put((np.sin(2 * np.pi * (3200 + 900 * np.sin(t * 90)) * t) * env(L, 0.005, 0.03) * 0.05).astype(np.float32), at)
for k in range(11):                                   # 足音：歩いているあいだ（約4.6歩/秒）
    put(step(1.0 + 0.06 * (k % 2)), 0.12 + k / 4.6, 0.55 * (0.7 + 0.3 * min(1, k / 3)))
put(step(0.92), T["wind"] + 0.12, 0.5)               # ふみこむ一歩
put(pofu(), T["hit"], 1.0)                            # 当たる（映像と同じコマ）
# 声
import render
render.set_voice(VOICE["vvm"], VOICE["style"], VOICE["speed"], VOICE["pitch"], VOICE["intonation"])
render._YOMI["……あれ？"] = "アレ？"
tmp = "/tmp/bf_are.wav"; render.tts("……あれ？", tmp)
with wave.open(tmp) as w: v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; vsr = w.getframerate()
v = np.interp(np.arange(int(len(v) * SR / vsr)) / SR, np.arange(len(v)) / vsr, v).astype(np.float32)
put(v, T["are"] + 0.05, 0.9)
mix = np.clip(mix, -1, 1)
with wave.open("/tmp/bf_mix.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())

# ---- 映像（CGのコマ＋文字）
files = sorted(glob.glob(f"{FR}/*.jpg"))
os.makedirs("/tmp/bf_frames", exist_ok=True)
for i, f in enumerate(files):
    im = Image.open(f).convert("RGBA")
    im = Image.alpha_composite(im, text_layer(i / FPS))
    d = ImageDraw.Draw(im); d.text((24, H - 40), "VOICEVOX:雨晴はう", font=F_CR, fill=(255, 255, 255, 170), anchor="lm")
    im.convert("RGB").save(f"/tmp/bf_frames/{i:05d}.jpg", quality=95)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", "/tmp/bf_frames/%05d.jpg", "-i", "/tmp/bf_mix.wav",
                "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-shortest", OUT], check=True)
print("ok", OUT, len(files), "コマ")
