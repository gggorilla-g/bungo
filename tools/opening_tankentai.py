# tools/opening_tankentai.py — 長尺「ずんだもん惑星探査隊」のオープニング（約9.6秒、1920x1080、オリジナル曲つき）
#   アメコミ風：太い黒の輪郭線、網点（ベンデイドット）、コマ割り、ギザギザの吹き出し、斜めの効果音文字。
#   使い方: python tools/opening_tankentai.py [出力mp4]   （assets/enc/parts のずんだもん立ち絵が必要）
import math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1920, 1080, 30
BPM = 150
B = 60 / BPM                      # 1拍 0.4秒
TOTAL = 24 * B                    # 24拍 = 9.6秒
SR = 44100
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
PARTS = "assets/enc/parts"
YEL, RED, CYA, BLK, WHT = (255, 212, 0), (232, 32, 42), (0, 160, 224), (0, 0, 0), (255, 255, 255)
PUR = (52, 30, 90)
_fc = {}


def font(s):
    s = max(8, int(s))
    if s not in _fc:
        _fc[s] = ImageFont.truetype(FONT, s, index=0)
    return _fc[s]


def ease(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def back(x, c=1.9):
    x = min(max(x, 0), 1)
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


_zc = {}


def zunda(face, h, mouth=1):
    k = (face, h, mouth)
    if k not in _zc:
        im = Image.open(f"{PARTS}/{face}_{mouth}_0.png").convert("RGBA")
        _zc[k] = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
    return _zc[k]


def outline(im, px=10):
    """キャラの外側に太い黒フチ（アメコミ風）"""
    a = im.getchannel("A").filter(ImageFilter.MaxFilter(px * 2 + 1))
    base = Image.new("RGBA", (im.width, im.height), BLK + (0,))
    base.putalpha(a)
    base.alpha_composite(im)
    return base


def halftone(size, col, bg, step=26, rmin=2, rmax=11, angle=0, grad=(0, 1)):
    """網点。grad=(左端の濃さ, 右端の濃さ)"""
    w, h = size
    im = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(im)
    for yy in range(-step, h + step, step):
        for xx in range(-step, w + step, step):
            x = xx + (yy // step % 2) * step / 2
            t = grad[0] + (grad[1] - grad[0]) * min(1, max(0, x / w))
            r = rmin + (rmax - rmin) * t
            d.ellipse([x - r, yy - r, x + r, yy + r], fill=col)
    return im


def rays(d, cx, cy, n, rot, cols, R=2400):
    for i in range(n):
        a0 = math.radians(rot + i * 360 / n)
        a1 = math.radians(rot + (i + 0.5) * 360 / n)
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=cols[i % len(cols)])


def burst(d, cx, cy, r, n=14, col=YEL, jag=0.72, rot=0):
    pts = []
    for i in range(n * 2):
        a = math.radians(rot + i * 180 / n)
        rr = r if i % 2 == 0 else r * jag
        pts.append((cx + rr * math.cos(a), cy + rr * 0.8 * math.sin(a)))
    d.polygon(pts, fill=BLK)
    pts2 = [(cx + (x - cx) * 0.93, cy + (y - cy) * 0.93) for x, y in pts]
    d.polygon(pts2, fill=col)


def bubble(img, cx, cy, text, size, s=1.0, kind="round", tail=(0, 1), fg=BLK, bg=WHT):
    """吹き出し。s=ポップの拡大率。kind: round（ふつう）/ jag（ギザギザ、叫び）/ box（四角、GM）"""
    if s <= 0.02:
        return
    lines = text.split("\n")
    f = font(size * s)
    tw = max(f.getbbox(l)[2] for l in lines)
    th = int(size * s * 1.25 * len(lines))
    pw, ph = tw / 2 + 60 * s, th / 2 + 50 * s
    d = ImageDraw.Draw(img)
    tx, ty = cx + tail[0] * pw * 1.2, cy + tail[1] * ph * 1.6
    tri = [(cx - 40 * s, cy + ph * 0.5 * tail[1]), (cx + 40 * s, cy + ph * 0.5 * tail[1]), (tx, ty)]
    if kind == "jag":
        burst(d, cx, cy, max(pw, ph) * 1.25, n=16, col=bg, jag=0.82)
    elif kind == "box":
        d.polygon([(p[0] + 6, p[1]) for p in tri], fill=fg)
        d.rectangle([cx - pw - 8, cy - ph - 8, cx + pw + 8, cy + ph + 8], fill=fg)
        d.polygon(tri, fill=bg)
        d.rectangle([cx - pw, cy - ph, cx + pw, cy + ph], fill=bg)
    else:
        d.polygon([(tri[0][0] - 9, tri[0][1]), (tri[1][0] + 9, tri[1][1]), (tx + 4, ty + 8)], fill=BLK)
        d.ellipse([cx - pw * 1.12 - 9, cy - ph * 1.1 - 9, cx + pw * 1.12 + 9, cy + ph * 1.1 + 9], fill=BLK)
        d.polygon(tri, fill=bg)
        d.ellipse([cx - pw * 1.12, cy - ph * 1.1, cx + pw * 1.12, cy + ph * 1.1], fill=bg)
    for i, l in enumerate(lines):
        y = cy - th / 2 + (i + 0.5) * th / len(lines)
        d.text((cx, y), l, font=f, fill=fg, anchor="mm")


def sfx(img, cx, cy, text, size, s, rot=-10, col=YEL, edge=RED):
    """効果音の文字：黄色に赤フチ＋黒の影、斜め"""
    if s <= 0.02:
        return
    f = font(size * s)
    bb = f.getbbox(text)
    w, h = bb[2] + 80, bb[3] + 80
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.text((w / 2 + 12, h / 2 + 12), text, font=f, fill=BLK, anchor="mm", stroke_width=int(14 * s), stroke_fill=BLK)
    d.text((w / 2, h / 2), text, font=f, fill=col, anchor="mm", stroke_width=int(12 * s), stroke_fill=edge)
    d.text((w / 2, h / 2), text, font=f, fill=col, anchor="mm", stroke_width=int(4 * s), stroke_fill=BLK)
    lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))


def caption(img, x, y, text, size, p):
    """黄色いナレーション枠（左上から伸びる）"""
    if p <= 0:
        return
    f = font(size)
    bb = f.getbbox(text)
    w = int((bb[2] + 60) * ease(p))
    d = ImageDraw.Draw(img)
    d.rectangle([x + 8, y + 8, x + w + 8, y + size + 48], fill=BLK)
    d.rectangle([x, y, x + w, y + size + 40], fill=YEL, outline=BLK, width=6)
    if p > 0.5:
        d.text((x + 30, y + 20 + size / 2), text, font=f, fill=BLK, anchor="lm")


def panel(img, box, content, border=12):
    """コマ：box=(x0,y0,x1,y1)。content(im_w,im_h)->RGBA を描いて、黒枠で囲む"""
    x0, y0, x1, y1 = [int(v) for v in box]
    if x1 - x0 < 4 or y1 - y0 < 4:
        return
    c = content(x1 - x0, y1 - y0)
    img.alpha_composite(c, (x0, y0))
    ImageDraw.Draw(img).rectangle([x0, y0, x1, y1], outline=BLK, width=border)


def gm(w, h, cx, cy, sc, glow):
    """謎のゲームマスター（黒いフードの影、目だけ光る）"""
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    hw = 260 * sc
    d.polygon([(cx - hw * 0.35, cy - 380 * sc), (cx, cy - 520 * sc), (cx + hw * 0.35, cy - 380 * sc)], fill=BLK)
    d.ellipse([cx - hw * 0.55, cy - 420 * sc, cx + hw * 0.55, cy - 150 * sc], fill=BLK)
    d.polygon([(cx - hw * 0.8, cy - 260 * sc), (cx + hw * 0.8, cy - 260 * sc), (cx + hw * 1.3, cy + 400 * sc), (cx - hw * 1.3, cy + 400 * sc)], fill=BLK)
    if glow > 0:
        g = Image.new("L", (w, h), 0)
        gd = ImageDraw.Draw(g)
        for ex in (-55, 55):
            gd.ellipse([cx + ex * sc - 34 * sc, cy - 300 * sc - 14 * sc, cx + ex * sc + 34 * sc, cy - 300 * sc + 14 * sc], fill=int(255 * glow))
        g = g.filter(ImageFilter.GaussianBlur(12 * sc))
        lay.paste(Image.new("RGBA", (w, h), (255, 220, 40, 255)), (0, 0), g)
        for ex in (-55, 55):
            d.ellipse([cx + ex * sc - 22 * sc, cy - 300 * sc - 8 * sc, cx + ex * sc + 22 * sc, cy - 300 * sc + 8 * sc], fill=(255, 245, 160, int(255 * glow)))
    return lay


def planet(d, cx, cy, r, col, dark, ring=False):
    d.ellipse([cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8], fill=BLK)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    step = max(10, int(r / 6))                                   # 影は網点で
    for yy in range(int(cy - r), int(cy + r), step):
        for xx in range(int(cx - r), int(cx + r), step):
            dx, dy = (xx - cx) / r, (yy - cy) / r
            if dx * dx + dy * dy < 0.95:
                t = max(0, (dx * 0.7 + dy * 0.7 + 0.2))
                rr = step * 0.45 * min(1, t)
                if rr > 1:
                    d.ellipse([xx - rr, yy - rr, xx + rr, yy + rr], fill=dark)
    if ring:
        d.arc([cx - r * 1.9, cy - r * 0.45, cx + r * 1.9, cy + r * 0.45], 160, 380, fill=BLK, width=22)
        d.arc([cx - r * 1.9, cy - r * 0.45, cx + r * 1.9, cy + r * 0.45], 160, 380, fill=(240, 200, 120), width=12)


# 背景の網点は先に作っておく
HT_RED = halftone((W, H), (200, 20, 30), RED, step=30, rmin=3, rmax=13, grad=(0.2, 1))
HT_SPACE = halftone((W, H), (20, 60, 150), (10, 20, 70), step=34, rmin=2, rmax=10, grad=(1, 0.1))
HT_PUR = halftone((W, H), (30, 15, 55), PUR, step=28, rmin=2, rmax=11, grad=(0.1, 1))
HT_YEL = halftone((W, H), (255, 180, 0), YEL, step=30, rmin=3, rmax=12, grad=(0.3, 1))


def frame(t):
    img = Image.new("RGBA", (W, H), WHT + (255,))
    d = ImageDraw.Draw(img)
    beat = t / B

    if beat < 8:                                                     # ── 1〜2: ずんだもん「大変なのだ！」／GM「地球は、もうダメだ。」
        # 左のコマ：ずんだもん（赤い網点＋集中線）
        p1 = back(beat / 0.9)
        shake = (math.sin(t * 70) * 10 * max(0, 1 - beat / 1.2))

        def left(w, h):
            c = HT_RED.crop((0, 0, w, h)).convert("RGBA")
            cd = ImageDraw.Draw(c)
            rays(cd, w * 0.5, h * 0.55, 18, t * 20, [(255, 90, 60), RED])
            z = outline(zunda("驚き" if beat < 4 else "焦り", int(h * 1.15)), 10)
            c.alpha_composite(z, (int(w / 2 - z.width / 2), int(h * 0.12)))
            return c
        lw = 1840 if beat < 4 else 1840 - (1840 - 900) * ease((beat - 4) / 0.8)   # 最初は全面、GMが来たら半分
        sc = 1.15 - 0.15 * min(1, p1)
        bx = (40 + shake, 40, 40 + min(1840, lw * sc) + shake, 1040)
        panel(img, bx, left)
        if beat >= 4:                                                 # 右のコマ：GM（斜めに差し込む）
            q = ease((beat - 4) / 0.8)
            x0 = 1920 + (1920 * 0.5 - 1920) * q

            def right(w, h):
                c = HT_PUR.crop((0, 0, w, h)).convert("RGBA")
                c.alpha_composite(gm(w, h, w * 0.55, h * 0.72, 1.05, min(1, max(0, (beat - 4.6) / 0.6))))
                return c
            panel(img, (x0, 40, x0 + 960 - 60, 1040), right)
        # 吹き出し・効果音
        bubble(img, 1250 if beat < 4 else 640, 300, "大変なのだ！", 84, back((beat - 0.6) / 0.5), "jag", tail=(-0.4, 1))
        sfx(img, 300, 880, "ドーン！", 150, back(beat / 0.5) * (1 if beat < 3.6 else max(0, 1 - (beat - 3.6) * 3)), rot=-12)
        if beat >= 5.4:
            bubble(img, 1430, 190, "地球は、\nもうダメだ。", 70, back((beat - 5.4) / 0.4), "box", tail=(0.2, 1), fg=WHT, bg=BLK)
        if beat >= 6.6:
            bubble(img, 560, 900, "ええーっ！？", 84, back((beat - 6.6) / 0.35), "round", tail=(0.5, -1))
        caption(img, 70, 70, "ある日――", 50, (beat - 0.2) / 0.6)

    elif beat < 13:                                                   # ── 3: 宇宙へ。星が流れ、ずんだもんが飛ぶ
        u = beat - 8
        img.alpha_composite(HT_SPACE.convert("RGBA"))
        d = ImageDraw.Draw(img)
        for i in range(80):                                            # 星
            x = (i * 397 - u * B * (300 + (i % 5) * 160)) % (W + 40) - 20
            y = (i * 211) % H
            r = 2 + i % 3
            d.ellipse([x - r, y - r, x + r, y + r], fill=WHT)
        planet(d, 1500 - u * 260, 260, 150, (230, 120, 60), (170, 60, 30))                  # 火星っぽい星
        planet(d, 420 - u * 140, 820, 230, (230, 190, 120), (170, 120, 60), ring=True)       # 環のある星
        planet(d, 1750 - u * 420, 900, 90, (110, 200, 230), (40, 120, 170))                  # 青い星
        zx, zy = 300 + 1300 * ease(u / 4.2), 640 - 360 * ease(u / 4.2) + math.sin(u * 4) * 20
        for q in range(9):                                             # スピード線
            yy = zy - 160 + q * 40
            d.line([(zx - 260 - q * 37 % 120, yy), (zx - 700 - q * 53 % 200, yy)], fill=WHT, width=8)
        z = outline(zunda("ドヤ", 520), 8).rotate(-18, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(z, (int(zx - z.width / 2), int(zy - z.height / 2)))
        caption(img, 70, 70, "任務：移住できる星を探せ！", 56, (u - 0.2) / 0.7)
        sfx(img, 1350, 760, "ビューン！", 140, back((u - 0.8) / 0.4) * max(0, min(1, (4.6 - u) * 2)), rot=-8, col=WHT, edge=CYA)
        bubble(img, zx - 420, zy + 40, "宇宙服は！？", 64, back((u - 2.4) / 0.35) * (1 if u < 4.4 else 0), "round", tail=(1, -0.3))

    else:                                                             # ── 4: タイトル
        u = beat - 13
        img.alpha_composite(HT_YEL.convert("RGBA"))
        d = ImageDraw.Draw(img)
        rays(d, W * 0.5, H * 0.46, 24, t * 14, [(255, 150, 0, 255), (255, 212, 0, 0)])
        flash = max(0, 1 - u / 0.25)
        burst(d, W * 0.5, H * 0.43, 620 * back(u / 0.5), n=18, col=RED, jag=0.78, rot=t * 6)
        # タイトル（立体の押し出し）
        s = back((u - 0.15) / 0.45)
        if s > 0.02:
            f1 = font(110 * s)
            f2 = font(250 * s)
            cx, cy = W * 0.5, H * 0.43
            for k in range(14, 0, -1):                                 # 押し出し（黒）
                d.text((cx + k * 2, cy - 150 * s + k * 2), "ずんだもん", font=f1, fill=BLK, anchor="mm")
                d.text((cx + k * 3, cy + 60 * s + k * 3), "惑星探査隊", font=f2, fill=BLK, anchor="mm")
            d.text((cx, cy - 150 * s), "ずんだもん", font=f1, fill=WHT, anchor="mm", stroke_width=int(10 * s), stroke_fill=BLK)
            d.text((cx, cy + 60 * s), "惑星探査隊", font=f2, fill=YEL, anchor="mm", stroke_width=int(14 * s), stroke_fill=BLK)
            d.text((cx, cy + 60 * s), "惑星探査隊", font=f2, fill=YEL, anchor="mm", stroke_width=int(5 * s), stroke_fill=RED)
        # ずんだもんが右下から跳び込む
        j = ease((u - 1.2) / 0.6)
        if j > 0:
            hop = abs(math.sin((u - 1.8) * math.pi / (B * 2.5))) * 26 if u > 1.8 else 0
            z = outline(zunda("笑顔", 470), 10)
            zx, zy = 1690 + (1 - j) * 500, 1080 - z.height + 30 - hop
            img.alpha_composite(z, (int(zx - z.width / 2), int(zy)))
            bubble(img, 1330, 960, "出発なのだ！", 60, back((u - 2.2) / 0.4), "jag", tail=(0.8, -0.2))
        if flash > 0:
            img.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(220 * flash))))
    # 1拍目ごとの全体の小さなズーム（ノリ）
    return img.convert("RGB")


# ── 音楽（オリジナル）。ニ長調、D - Bm - G - A を4小節、最後にDでジャーン
def note(n):
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    nm, oc = n[:-1], int(n[-1])
    return 440 * 2 ** ((names[nm] + 12 * (oc + 1) - 69) / 12)


def osc(f, dur, kind="saw", vol=0.2, a=0.005, dec=4.0, vib=0.0):
    t = np.arange(int(dur * SR)) / SR
    ph = 2 * np.pi * np.cumsum(f * (1 + vib * np.sin(2 * np.pi * 5.5 * t))) / SR
    if kind == "saw":
        y = sum(np.sin(k * ph) / k for k in range(1, 9)) * 0.55
    elif kind == "square":
        y = sum(np.sin(k * ph) / k for k in range(1, 12, 2)) * 0.9
    else:
        y = np.sin(ph)
    env = np.minimum(1, t / a) * np.exp(-t * dec)
    rel = np.minimum(1, (dur - t) / 0.02)
    return y * env * rel * vol


def noise(dur, dec, vol, seed=0):
    t = np.arange(int(dur * SR)) / SR
    return np.random.default_rng(seed).normal(0, 1, len(t)) * np.exp(-t * dec) * vol


def kick():
    t = np.arange(int(0.3 * SR)) / SR
    f = 140 * np.exp(-t * 20) + 48
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11) * 0.9


def snare():
    t = np.arange(int(0.22 * SR)) / SR
    return (np.random.default_rng(5).normal(0, 1, len(t)) * 0.6 + np.sin(2 * np.pi * 190 * t) * 0.5) * np.exp(-t * 20) * 0.45


def add(buf, x, at, gain=1.0):
    i = int(at * SR)
    if i >= len(buf):
        return
    n = min(len(x), len(buf) - i)
    buf[i:i + n] += x[:n] * gain


def music(out_wav):
    buf = np.zeros(int((TOTAL + 0.3) * SR), np.float32)
    # 0〜3拍：スネアの連打で盛り上げ＋上がっていく音
    for q in range(12):
        add(buf, snare(), q * B / 4 + 1.0 * B, 0.3 + q * 0.06)
    t = np.arange(int(4 * B * SR)) / SR
    add(buf, np.sin(2 * np.pi * np.cumsum(200 + 600 * (t / t[-1]) ** 2) / SR) * 0.06 * (t / t[-1]), 0)
    add(buf, noise(0.6, 4, 0.25, 1), 0)                                 # ドーン
    add(buf, kick(), 0, 1.2)
    # 4〜19拍：本編（4小節）
    chords = [["D3", "F#3", "A3", "D4"], ["B2", "D3", "F#3", "B3"], ["G2", "B2", "D3", "G3"], ["A2", "C#3", "E3", "A3"]]
    bass = ["D2", "B1", "G1", "A1"]
    mel = [  # (拍, 音, 長さ拍) 小節ごと
        [(0, "A4", .5), (.5, "D5", .5), (1, "F#5", .5), (1.5, "A5", 1), (2.5, "F#5", .5), (3, "D5", 1)],
        [(0, "B4", .5), (.5, "D5", .5), (1, "F#5", .5), (1.5, "B5", 1), (2.5, "A5", .5), (3, "F#5", 1)],
        [(0, "G4", .5), (.5, "B4", .5), (1, "D5", .5), (1.5, "G5", .5), (2, "F#5", .5), (2.5, "E5", .5), (3, "D5", .5), (3.5, "B4", .5)],
        [(0, "A4", .5), (.5, "C#5", .5), (1, "E5", .5), (1.5, "A5", 1.5), (3, "G5", .5), (3.5, "E5", .5)],
    ]
    for bar in range(4):
        b0 = (4 + bar * 4) * B
        for bt in range(4):
            add(buf, kick(), b0 + bt * B, 1.0)
            if bt % 2:
                add(buf, snare(), b0 + bt * B)
            for h in (0, 0.5):
                add(buf, noise(0.05, 80, 0.08, 7), b0 + (bt + h) * B)
                add(buf, osc(note(bass[bar]), B * 0.45, "square", 0.22, dec=5), b0 + (bt + h) * B)
        for st in (0.5, 1.5, 2.5, 3.5):                                 # ブラス風の裏打ち
            for n in chords[bar]:
                add(buf, osc(note(n) * 2, B * 0.35, "saw", 0.045, dec=7), b0 + st * B)
        for st, n, ln in mel[bar]:                                      # メロディ
            add(buf, osc(note(n), ln * B * 0.95, "saw", 0.11, a=0.01, dec=1.5, vib=0.004), b0 + st * B)
            add(buf, osc(note(n) * 2, ln * B * 0.95, "square", 0.03, a=0.01, dec=2), b0 + st * B)
    # 8拍目（ダメだ）・12拍目（宇宙へ）に合わせて小さなアクセント
    add(buf, noise(0.4, 6, 0.18, 2), 8 * B)
    # 20拍目：Dでジャーン（タイトル）
    end = 20 * B
    for n in ("D3", "A3", "D4", "F#4", "A4", "D5"):
        add(buf, osc(note(n), 1.7, "saw", 0.07, dec=1.6), end)
    add(buf, noise(1.6, 2.5, 0.22, 3), end)
    add(buf, kick(), end, 1.4)
    # タイトルの入りの前（13拍目＝5.2秒）にも一発
    add(buf, noise(0.5, 5, 0.25, 4), 13 * B); add(buf, kick(), 13 * B, 1.3)
    # 効果音：ビューン（8.9拍あたり）
    t2 = np.arange(int(0.6 * SR)) / SR
    add(buf, np.sin(2 * np.pi * np.cumsum(1200 - 900 * t2 / t2[-1]) / SR) * np.exp(-t2 * 3) * 0.08, 8.8 * B)
    buf = np.tanh(buf * 1.4) / np.tanh(1.4)
    buf = buf / max(1e-6, np.abs(buf).max()) * 0.9
    fade = np.ones_like(buf); n = int(0.3 * SR); fade[-n:] = np.linspace(1, 0, n)
    buf *= fade
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((buf * 32767).astype(np.int16).tobytes())


def main(out="output/opening_tankentai.mp4"):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    wav = out.replace(".mp4", ".wav")
    music(wav)
    n = int(TOTAL * FPS)
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
                          "-shortest", out], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait()
    print(out, f"{TOTAL:.1f}s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--stills":
        for tt in (0.5, 1.2, 2.3, 3.0, 3.8, 4.4, 5.6, 6.6, 7.6, 9.0):
            frame(tt).save(f"{sys.argv[2]}/op_{tt:.1f}.jpg", quality=85)
    else:
        main(*sys.argv[1:])
