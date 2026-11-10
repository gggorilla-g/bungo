# bigface/make_ep01.py — EP.01『ビッグフェイスのせまいドア』（約43秒）の音と文字を付けて書き出す
# 使い方: python3 bigface/make_ep01.py <CGのコマのフォルダ> <出力mp4>
# 時刻は bigface/cg/bf.js の EP01 と合わせる（下の E）
import os, sys, glob, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src")); sys.path.insert(0, HERE)
import music

FR, OUT = sys.argv[1], sys.argv[2]
W, H, FPS, SR = 1080, 1920, 30, 48000
import json
E = json.load(open(f"{HERE}/cg/ep01_time.json"))   # 時刻表は bf.js と同じファイル
F_TITLE = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 70)
F_EP = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 34)
F_SUB = ImageFont.truetype(f"{HERE}/fonts/ZenKakuGothicNew-Medium.ttf", 62)
F_CR = ImageFont.truetype(f"{HERE}/fonts/ZenKakuGothicNew-Medium.ttf", 24)
F_LOGO = ImageFont.truetype(f"{HERE}/fonts/ZenMaruGothic-Bold.ttf", 102)   # 端に余白（Codex 指摘で約13%小さく）
INK = (0x34, 0x3B, 0x3A)

# セリフ（文、読み、声、時刻）。読みはここで決めた片仮名だけを使う（読み間違いを防ぐ）
BF_V = ("0.vvm", 10, 0.82, -0.05, 0.55)      # 仮：雨晴はう（ゆっくり・抑揚ひかえめ）
KID_V = ("0.vvm", 8, 0.98, 0.03, 1.0)        # 仮：春日部つむぎ（パン屋の子）
# 11/10 ゲンタさん「言葉なし」：セリフは使わない（動きだけで見せる）。声を足すときはここに書く
LINES_OFF = [("……あれ？", "アレ？", BF_V, E["are"]),
         ("うらにも、ドアがあるよ", "ウラニモ、ドアガアルヨ", KID_V, E["kid_say"]),
         ("……そっか。", "ソッカ。", BF_V, E["sokka"]),
         ("ここからなら、どうぞ", "ココカラナラ、ドーゾ", KID_V, E["kid_say2"]),
         ("ここも、いい席だね。", "ココモ、イイセキダネ。", BF_V, E["final"])]

import render
voices = []
LINES = []
# タイトルコール（声は語りだけ。物語のセリフは言葉なしのまま。11/10 ゲンタさん「タイトルコールは声欲しいですね」）
NAR_V = ("6.vvm", 31, 0.92, 0.0, 1.0)        # 仮：No.7 読み聞かせ（絵本を読む声）
EYE_V = ("0.vvm", 8, 1.0, 0.04, 1.15)        # 仮：春日部つむぎ（明るく）
CALLS = [("ビッグフェイスの、せまいドア", "ビッグフェイスノ、セマイドア", NAR_V, E["title_in"] + 0.45)]   # アイキャッチは声なし（11/10 ゲンタさん「ザビッグフェイスは声なくていいです」）
CREDIT = "VOICEVOX:No.7"
for i, (txt, yomi, v, at) in enumerate(LINES):
    render.set_voice(*v); render._YOMI[txt] = yomi
    tmp = f"/tmp/bf_l{i}.wav"; render.tts(txt, tmp)
    with wave.open(tmp) as w: x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; vsr = w.getframerate()
    x = np.interp(np.arange(int(len(x) * SR / vsr)) / SR, np.arange(len(x)) / vsr, x).astype(np.float32)
    voices.append((txt, x, at, len(x) / SR))

calls = []
for i, (txt, yomi, v, at) in enumerate(CALLS):
    render.set_voice(*v); render._YOMI[txt] = yomi
    tmp = f"/tmp/bf_c{i}.wav"; render.tts(txt, tmp)
    with wave.open(tmp) as w: x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; vsr = w.getframerate()
    x = np.interp(np.arange(int(len(x) * SR / vsr)) / SR, np.arange(len(x)) / vsr, x).astype(np.float32)
    calls.append((txt, x, at, len(x) / SR))

def alpha(t, a, b, f=0.18):
    if t < a or t > b: return 0.0
    return min(1, (t - a) / f, (b - t) / f)
def text_layer(t):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    a = alpha(t, E["title_in"], E["title_out"], 0.3)       # タイトル：最初の事件から中の顔のカットまで約5秒（11/10 ゲンタさん「タイトルもっと長く見せたい」）
    if a > 0:
        d.text((W // 2, 118), "EP.01", font=F_EP, fill=INK + (int(200 * a),), anchor="mm")
        d.text((W // 2, 190), "ビッグフェイスのせまいドア", font=F_TITLE, fill=INK + (int(255 * a),), anchor="mm")
    k = t - E["eye"] - 0.42                                 # アイキャッチのロゴ：ぽんと出て、少しはねて止まる
    if k > 0:
        sc_ = 1 - 0.35 * np.exp(-k * 11) * np.cos(k * 18)   # 小さく出て一度はね、0.4秒ほどで止まる（11/10 ゲンタさん「最後に不自然に文字が大きくなる」）
        if k > 0.6: sc_ = 1.0
        lg = Image.new("RGBA", (W, 260), (0, 0, 0, 0)); ImageDraw.Draw(lg).text((W // 2, 130), "ザ・ビッグフェイス", font=F_LOGO, fill=INK + (255,), anchor="mm")
        lg = lg.resize((max(1, int(W * sc_)), max(1, int(260 * sc_))))
        L.alpha_composite(lg, (int((W - lg.width) / 2), int(1250 - lg.height / 2)))
    for txt, x, at, dur in voices:                          # セリフ：上の余白に1行、白文字＋ひかえめな影
        a = alpha(t, at, at + dur + 0.7, 0.12)
        if a <= 0: continue
        bx = ImageDraw.Draw(L).textbbox((W // 2, 300), txt, font=F_SUB, anchor="mm")            # 明るい背景でも読めるよう、薄い板を敷く
        ImageDraw.Draw(L).rounded_rectangle((bx[0] - 30, bx[1] - 18, bx[2] + 30, bx[3] + 18), radius=22, fill=(0x34, 0x3B, 0x3A, int(110 * a)))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((W // 2 + 3, 300 + 4), txt, font=F_SUB, fill=(0x20, 0x26, 0x25, int(160 * a)), anchor="mm")
        L = Image.alpha_composite(L, sh.filter(ImageFilter.GaussianBlur(5)))
        ImageDraw.Draw(L).text((W // 2, 300), txt, font=F_SUB, fill=(255, 255, 255, int(255 * a)), anchor="mm")
    return L

# ---- 音
n = int((E["end"] + 0.3) * SR); fx = np.zeros(n, np.float32); bgm = np.zeros(n, np.float32); vo = np.zeros(n, np.float32)
rng = np.random.default_rng(3)
def put(buf, x, at, g=1.0):
    i = int(at * SR); j = min(n, i + len(x))
    if 0 <= i < n: buf[i:j] += g * np.asarray(x[: j - i], np.float32)
def env(L, a, d): t = np.arange(L) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def lp(x, k): c = np.ones(k) / k; return np.convolve(np.convolve(x, c, "same"), c, "same")
def step(p=1.0, heel=False):
    L = int(0.07 * SR); t = np.arange(L) / SR
    f = (900 if heel else 620) * p
    return np.sin(2 * np.pi * f * t) * env(L, 0.002, 0.012 if heel else 0.018) * 0.5 + lp(rng.standard_normal(L), 6) * env(L, 0.001, 0.008) * 0.25
def pofu(p=1.0):
    L = int(0.32 * SR); t = np.arange(L) / SR; f = (150 * np.exp(-t * 5) + 70) * p
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.004, 0.09) + lp(rng.standard_normal(L), 28) * env(L, 0.006, 0.05) * 1.6
def pop():                                               # はずれる「ぽこ」
    L = int(0.12 * SR); t = np.arange(L) / SR; f = 260 + 500 * t / 0.12
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, 0.003, 0.03) * 0.5
def creak():                                             # 窓の木がきしむ（やわらかく）
    L = int(0.45 * SR); t = np.arange(L) / SR; f = 420 + 120 * np.sin(t * 22)
    return lp(np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * env(L, 0.03, 0.15), 18) * 0.25
def rustle():                                            # 紙袋・パンを受けとる
    L = int(0.35 * SR); return lp(rng.standard_normal(L), 3) * env(L, 0.02, 0.09) * 0.18
def munch():                                             # もぐ
    L = int(0.16 * SR); t = np.arange(L) / SR
    return (lp(rng.standard_normal(L), 14) * env(L, 0.01, 0.04) * 0.9 + np.sin(2 * np.pi * 180 * t) * env(L, 0.005, 0.03) * 0.2)
tt = np.arange(n) / SR
amb = lp(rng.standard_normal(n), 120).astype(np.float32); amb /= np.abs(amb).max()
inside = ((tt >= E["s2"]) & (tt < E["s5"])) | (tt >= E["s9"])
alley = (tt >= E["s6"]) & (tt < E["s7"])
fx += amb * np.where(inside, 0.018, np.where(alley, 0.028, 0.035))
for at in [1.0, 13.8, 24.5, 30.2, 41.0]:                 # 遠くの小鳥
    L = int(0.09 * SR); t = np.arange(L) / SR
    put(fx, np.sin(2 * np.pi * (3200 + 900 * np.sin(t * 90)) * t) * env(L, 0.005, 0.03) * 0.05, at)
# 足音・接触
put(fx, step(), 0.3, 0.5); put(fx, pofu(), E["hit1"])
put(fx, pop(), E["s3"] + 0.18); put(fx, step(), E["s3"] + 0.4, 0.4); put(fx, step(0.95), E["hit2"] - 0.2, 0.45); put(fx, pofu(1.12), E["hit2"])
put(fx, pop(), E["s4"] + 0.12); put(fx, step(0.95), E["hit3"] - 0.18, 0.45); put(fx, pofu(0.94), E["hit3"]); put(fx, pop(), E["hit3"] + 0.72)
for i in range(3):                                       # 行列の人が来る
    for k in range(7): put(fx, step(1.1 + 0.05 * i, True), E["s4"] + 0.35 + i * 0.5 + k / 3.6, 0.22)
for k in range(3): put(fx, step(), E["s5"] + 1.35 + k * 0.2, 0.4)
for k in range(9): put(fx, step(1 + 0.05 * (k % 2)), E["s6"] + 0.15 + k / 4.2, 0.45)
for k in range(15): put(fx, step(0.9 + 0.04 * (k % 2)), E["s7"] + 0.25 + k / 3.2, 0.3)   # ゆっくり帰る
put(fx, creak(), E["win"])
for k in range(6): put(fx, step(), E["s8"] + 0.15 + k / 4.6, 0.4)
for k in range(6): put(fx, step(1.35, True), E["s8"] + 0.45 + k * 0.18, 0.18)          # 子どもが奥へ（小さな足音）
put(fx, rustle(), E["s8"] + 1.6, 0.8)                                                    # 棚からパンを取る
for k in range(6): put(fx, step(1.35, True), E["s8"] + 1.95 + k * 0.18, 0.18)          # 戻ってくる
put(fx, rustle(), E["give"] - 0.1)
for b in (E["bite1"], E["bite2"]): put(fx, munch(), b + 0.33, 0.6); put(fx, munch(), b + 0.8, 0.35)
# BGM：冒頭は無音 → なんだかへんだ → （止める）→ ひとりぼっち → （窓の音で止める）→ そういうことか
def fade(x, fi, fo):
    L = len(x); e = np.ones(L); a = int(fi * SR); b = int(fo * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if b: e[-b:] = np.linspace(1, 0, b)
    return x * e
m02 = fade(music.bgm02(E["s6"] - E["s3"] - 0.1), 0.4, 0.6); put(bgm, m02, E["s3"], 0.38)   # 序盤のBGMは小さく（11/10 ゲンタさん「序盤の音楽がうるさい」）
m04 = fade(music.bgm04(E["win"] - E["s6"] - 1.0), 1.0, 1.2); put(bgm, m04, E["s6"] + 1.0, 0.9)
m05 = fade(music.bgm05(E["eye"] - E["s8"] - 0.4), 0.8, 0.5); put(bgm, m05, E["s8"] + 0.4, 0.85)
# アイキャッチ：着地のぽふっ＋トイピアノの短いジングル（メインテーマの頭3音＋和音）
put(fx, pofu(1.05), E["eye"] + 0.32, 1.0)
for j, (nn, at) in enumerate([(76, 0.45), (79, 0.62), (81, 0.79)]): put(bgm, music.toypiano(music.hz(nn), 0.6), E["eye"] + at, 0.5)
for nn in (72, 76, 79, 84): put(bgm, music.toypiano(music.hz(nn), 1.4), E["eye"] + 1.0, 0.28)
for txt, x, at, dur in voices: put(vo, x, at + 0.02, 0.95)
for txt, x, at, dur in calls: put(vo, x, at, 0.95)
# セリフの間はBGMを下げる
duck = np.ones(n, np.float32)
for txt, x, at, dur in voices + calls:
    i, j = int((at - 0.15) * SR), int((at + dur + 0.25) * SR); duck[max(0, i):min(n, j)] = 0.45
duck = lp(duck, 2400).astype(np.float32)
mix = np.clip(fx + bgm * duck * 0.9 + vo, -1, 1)
with wave.open("/tmp/bf_ep01.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())

# ---- 映像
files = sorted(glob.glob(f"{FR}/*.jpg"))
os.makedirs("/tmp/bf_ep01_frames", exist_ok=True)
for i, f in enumerate(files):
    im = Image.alpha_composite(Image.open(f).convert("RGBA"), text_layer(i / FPS))
    ImageDraw.Draw(im).text((24, H - 40), CREDIT, font=F_CR, fill=(0x34, 0x3B, 0x3A, 150), anchor="lm")
    im.convert("RGB").save(f"/tmp/bf_ep01_frames/{i:05d}.jpg", quality=95)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", "/tmp/bf_ep01_frames/%05d.jpg", "-i", "/tmp/bf_ep01.wav",
                "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-shortest", OUT], check=True)
print("ok", OUT, len(files), "コマ")
