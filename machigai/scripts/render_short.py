"""間違い探しショート（縦1080x1920）を書き出す。
構成：タイトル1秒 → 探す時間（カウントダウン） → 答えを1つずつ表示 → 余韻"""
import json, sys, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS = 30
W, H = 1080, 1920
SEARCH = 15          # 探す時間（秒）
INTRO = 1.0
REVEAL_GAP = 0.8
HOLD = 2.5
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
BG = (18, 18, 18)
RED = (230, 40, 40)

def font(sz): return ImageFont.truetype(FONT, sz, index=0)  # index0 = JP

def build(base, diff, ans_path, out, search=15, title=None, audio="audio.wav"):
    global SEARCH
    SEARCH = search
    A = Image.open(base).convert("RGB"); B = Image.open(diff).convert("RGB")
    ans = json.load(open(ans_path))["answers"]
    iw = 920; s = iw / A.width; ih = int(A.height * s)
    A = A.resize((iw, ih)); B = B.resize((iw, ih))
    ax, ay = (W - iw)//2, 250
    bx, by = ax, ay + ih + 30
    n = len(ans)
    reveal_start = INTRO + SEARCH
    total = reveal_start + 0.6 + REVEAL_GAP * n + HOLD
    frames = int(total * FPS)

    make_audio(total, n, reveal_start, audio)   # ffmpeg起動前に音を用意
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio,
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                          "-c:a", "aac", "-b:a", "128k", "-shortest", out], stdin=subprocess.PIPE)
    f_title, f_sub, f_num = font(84), font(44), font(120)
    for i in range(frames):
        t = i / FPS
        im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
        im.paste(A, (ax, ay)); im.paste(B, (bx, by))
        d.text((W//2, 120), title or f"間違いは{n}つ", font=f_title, fill=(255, 255, 255), anchor="mm")
        if t < reveal_start:
            left = max(0.0, reveal_start - t) if t >= INTRO else SEARCH
            sub = f"制限時間 {SEARCH}秒"
            d.text((W//2, 200), sub, font=f_sub, fill=(170, 170, 170), anchor="mm")
            # 残り時間バー
            frac = min(1.0, left / SEARCH)
            y0 = by + ih + 70
            d.rectangle((ax, y0, ax + iw, y0 + 24), fill=(60, 60, 60))
            d.rectangle((ax, y0, ax + int(iw * frac), y0 + 24), fill=(255, 255, 255))
            d.text((W//2, y0 + 110), f"{int(np.ceil(left))}", font=f_num, fill=(255, 255, 255), anchor="mm")
        else:
            d.text((W//2, 200), "答え", font=f_sub, fill=(170, 170, 170), anchor="mm")
            k = int((t - reveal_start - 0.6) / REVEAL_GAP) + 1 if t >= reveal_start + 0.6 else 0
            for j, a in enumerate(ans[:max(0, min(k, n))]):
                for ox, oy in ((ax, ay), (bx, by)):
                    cx = ox + (a["x"] + a["w"]/2) * s; cy = oy + (a["y"] + a["h"]/2) * s
                    r = max(a["w"], a["h"]) * s / 2 + 22
                    d.ellipse((cx-r, cy-r, cx+r, cy+r), outline=RED, width=8)
            y0 = by + ih + 70
            kk = min(max(k, 0), n)
            d.text((W//2, y0 + 110), f"{kk} / {n}", font=f_num, fill=(255, 255, 255), anchor="mm")
            if kk:
                d.text((W//2, y0 + 10), f"難易度 {ans[kk-1].get('level', '')}", font=f_sub, fill=(170, 170, 170), anchor="mm")
        p.stdin.write(im.tobytes())
    p.stdin.close(); p.wait()

def tone(freq, dur, sr=44100, vol=0.35):
    t = np.arange(int(sr*dur)) / sr
    env = np.exp(-t * 18)
    return np.sin(2*np.pi*freq*t) * env * vol

def make_audio(total, n, reveal_start, path, sr=44100):
    buf = np.zeros(int(sr * (total + 0.5)))
    def put(at, x):
        i = int(at*sr); buf[i:i+len(x)] += x[:len(buf)-i]
    for k in range(SEARCH):
        put(INTRO + k, tone(1500 if SEARCH - k > 3 else 2000, 0.06, sr, 0.2))
    put(reveal_start, tone(660, 0.5, sr, 0.35))
    for j in range(n):
        put(reveal_start + 0.6 + REVEAL_GAP*j, tone(990, 0.3, sr, 0.35))
    pcm = (np.clip(buf, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

if __name__ == "__main__":
    build(*sys.argv[1:5], search=int(sys.argv[5]) if len(sys.argv) > 5 else 15)
