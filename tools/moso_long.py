# tools/moso_long.py — 長尺「ずんだもん惑星探査隊」（横長1920x1080）を台本データから作る
#   使い方: python tools/moso_long.py nazo/moso_long/solar_v5.json output/moso_long_solar.mp4 [--from 秒 --to 秒]
#   方針: 見やすさと滞在時間を優先（ショートより落ち着いたテンポ）。セリフは全部テロップ。吹き出しや文字でキャラの顔を隠さない。
import json, math, os, re, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, "nazo"); sys.path.insert(0, "src"); sys.path.insert(0, "tools")
import mosofx, se                                   # noqa: E402

W, H, FPS, SR = 1920, 1080, 24, 44100
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FONT_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
PARTS = "assets/enc/parts"
WHT, BLK, YEL, RED = (255, 255, 255), (0, 0, 0), (255, 214, 0), (226, 36, 44)
ZCOL, GCOL = (60, 190, 90), (120, 70, 190)          # 話し手の色（ずんだもん緑、GM紫）
GAP, GM_PRE, SCENE_GAP = 0.5, 0.25, 1.0            # セリフの間（GMは一拍おいて静かに返す）
_fc = {}


def font(s, bold=False):
    k = (int(s), bold)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FONT_B if bold else FONT, max(8, int(s)), index=0)
    return _fc[k]


def ease(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def back(x, c=1.7):
    x = min(max(x, 0), 1)
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


# ── キャラ
_zc = {}


def zunda(face, h, mouth=1, blink=0):
    for f in (face, "通常"):
        for b in ((blink, 0) if blink else (0,)):
            p = f"{PARTS}/{f}_{mouth}_{b}.png"
            k = (p, h)
            if k not in _zc and os.path.exists(p):
                im = Image.open(p).convert("RGBA")
                _zc[k] = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
            if k in _zc:
                return _zc[k]
    raise FileNotFoundError(face)


_dmg = {}


def damaged(im, level):
    """星をまわるたびにボロボロになる（焦げ・ばんそうこう）。目と口にはかけない"""
    if level <= 0:
        return im
    k = (id(im), level)
    if k in _dmg:
        return _dmg[k]
    w, h = im.size
    a = im.getchannel("A")
    rgb = Image.blend(im.convert("RGB"), Image.new("RGB", im.size, (110, 80, 50)), min(0.3, 0.045 * level))
    out = rgb.convert("RGBA"); out.putalpha(a)
    d = ImageDraw.Draw(out)
    # ばんそうこう（頭、おでこの端、ほお、腕）。顔の中心（目と口）は避ける
    spots = [(0.58, 0.29, 20), (0.37, 0.53, -25), (0.31, 0.66, 15), (0.60, 0.66, -10), (0.36, 0.13, -15), (0.56, 0.52, 25), (0.45, 0.90, 10)]
    for i, (fx_, fy_, ang) in enumerate(spots[:level]):
        bw, bh = int(w * 0.11), int(w * 0.045)
        tape = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        td = ImageDraw.Draw(tape)
        td.rounded_rectangle([0, 0, bw - 1, bh - 1], bh // 2, fill=(245, 215, 175), outline=(150, 110, 80), width=max(1, bh // 10))
        td.rectangle([bw * 0.38, 2, bw * 0.62, bh - 3], fill=(250, 235, 210))
        tape = tape.rotate(ang, expand=True, resample=Image.BICUBIC)
        if a.getpixel((int(w * fx_), int(h * fy_))) < 200:      # 体の外には貼らない
            continue
        out.alpha_composite(tape, (int(w * fx_ - tape.width / 2), int(h * fy_ - tape.height / 2)))
    _dmg[k] = out
    return out


def outline(im, px=6):
    a = im.getchannel("A").filter(ImageFilter.MaxFilter(px * 2 + 1))
    base = Image.new("RGBA", im.size, (0, 0, 0, 0)); base.putalpha(a)
    base.alpha_composite(im)
    return base


def gm_figure(w, h, cx, cy, sc, glow, talk=0.0):
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    hw = 260 * sc
    d.polygon([(cx - hw * 0.35, cy - 380 * sc), (cx, cy - 520 * sc), (cx + hw * 0.35, cy - 380 * sc)], fill=BLK)
    d.ellipse([cx - hw * 0.55, cy - 420 * sc, cx + hw * 0.55, cy - 150 * sc], fill=BLK)
    d.polygon([(cx - hw * 0.8, cy - 260 * sc), (cx + hw * 0.8, cy - 260 * sc), (cx + hw * 1.3, cy + 400 * sc), (cx - hw * 1.3, cy + 400 * sc)], fill=BLK)
    g = min(1, glow + talk * 0.4)
    gl = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(gl)
    for ex in (-55, 55):
        gd.ellipse([cx + ex * sc - 36 * sc, cy - 300 * sc - 15 * sc, cx + ex * sc + 36 * sc, cy - 300 * sc + 15 * sc], fill=int(255 * g))
    gl = gl.filter(ImageFilter.GaussianBlur(max(1, 12 * sc)))
    lay.paste(Image.new("RGBA", (w, h), (255, 220, 40, 255)), (0, 0), gl)
    for ex in (-55, 55):
        d.ellipse([cx + ex * sc - 22 * sc, cy - 300 * sc - 8 * sc, cx + ex * sc + 22 * sc, cy - 300 * sc + 8 * sc], fill=(255, 245, 160, int(255 * g)))
    return lay


# ── 背景
PLANET = {  # 色, 影, 帯, 大きさ
    "mercury": ((170, 160, 150), (100, 95, 90), None, 300),
    "venus": ((235, 200, 120), (180, 130, 60), (240, 215, 150), 360),
    "mars": ((210, 100, 60), (140, 55, 35), None, 330),
    "jupiter": ((220, 180, 140), (150, 110, 80), (190, 130, 90), 400),
    "saturn": ((230, 205, 150), (170, 140, 90), (210, 180, 120), 330),
    "uranus": ((150, 220, 225), (90, 160, 175), None, 340),
    "neptune": ((70, 110, 220), (35, 60, 150), (90, 140, 235), 340),
    "earth": ((60, 120, 210), (30, 70, 150), None, 380),
}
_stars = None


def stars(d, t, drift=6):
    global _stars
    if _stars is None:
        rng = np.random.default_rng(4)
        _stars = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 3.2)) for _ in range(170)]
    for x, y, r in _stars:
        x = (x - t * drift * r * 0.4) % W
        a = int(150 + 100 * abs(math.sin(t * 0.6 + x)))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(a, a, min(255, a + 20)))


_photo = {}


def photo(kind, r):
    """NASAの写真（パブリックドメイン, assets/planets）。黒い背景を切り、直径2rに合わせる"""
    k = (kind, r)
    if k in _photo:
        return _photo[k]
    for name in (f"{kind}_hi", kind):
        p = f"assets/planets/{name}.jpg"
        if os.path.exists(p):
            break
    else:
        return None
    im = Image.open(p).convert("RGB")
    g = np.asarray(im.convert("L"))
    ys, xs = np.nonzero(g > 30)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    if kind == "saturn":                       # 環ごと。本体の直径を基準にする（環は本体の約2.3倍の幅）
        body = (x1 - x0) / 2.3
        sc = 2 * r / body
    else:
        sc = 2 * r / max(x1 - x0, y1 - y0)
    im = im.crop((x0, y0, x1 + 1, y1 + 1))
    im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
    _photo[k] = im
    return im


def planet(img, kind, cx, cy, r, t, ring=False, tilt=False):
    ph = photo(kind, r)
    if ph is not None:                          # 写真は「明るい方を残す」重ね方で、黒い背景を宇宙になじませる
        from PIL import ImageChops
        x0, y0 = int(cx - ph.width / 2), int(cy - ph.height / 2)
        box = (max(0, x0), max(0, y0), min(W, x0 + ph.width), min(H, y0 + ph.height))
        reg = img.crop(box).convert("RGB")
        part = ph.crop((box[0] - x0, box[1] - y0, box[2] - x0, box[3] - y0))
        m = part.convert("L").point(lambda v: 255 if v > 28 else v * 9)   # 星が惑星の上に透けないように
        img.paste(Image.composite(part, reg, m), box[:2])
        if tilt:
            d = ImageDraw.Draw(img)
            a = math.radians(98)
            ex, ey = math.sin(a) * r * 1.5, -math.cos(a) * r * 1.5
            d.line([(cx - ex, cy - ey), (cx + ex, cy + ey)], fill=WHT, width=6)
            d.text((cx + ex + 20, cy + ey - 20), "自転軸", font=font(36), fill=WHT, anchor="lm", stroke_width=4, stroke_fill=BLK)
        return
    col, dark, band, _ = PLANET[kind]
    lay = Image.new("RGBA", (2 * r + 40, 2 * r + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    o = r + 20
    d.ellipse([o - r, o - r, o + r, o + r], fill=col + (255,))
    if band:
        for k in range(-4, 5):
            y = o + k * r * 0.2 + math.sin(t * 0.3 + k) * 3
            hh = r * 0.05 * (1 + (k % 2))
            d.ellipse([o - r * 1.2, y - hh, o + r * 1.2, y + hh], fill=band + (255,))
    if kind == "earth":
        for lon, lat, wl, hl in ((-100, 40, 45, 25), (-60, -15, 22, 30), (20, 45, 35, 18), (20, 5, 25, 30), (100, 45, 50, 22), (135, -25, 22, 12)):
            a = math.radians(lon + t * 6)
            if math.cos(a) < 0.05:
                continue
            x = o + r * math.sin(a) * math.cos(math.radians(lat)); y = o - r * math.sin(math.radians(lat))
            w_ = r * math.radians(wl) * math.cos(a) * 0.9; h_ = r * math.radians(hl) * 0.9
            d.ellipse([x - w_, y - h_, x + w_, y + h_], fill=(80, 170, 90, 255))
    if kind == "jupiter":
        d.ellipse([o + r * 0.2, o + r * 0.25, o + r * 0.55, o + r * 0.42], fill=(200, 110, 80, 255))
    mask = Image.new("L", lay.size, 0)
    ImageDraw.Draw(mask).ellipse([o - r, o - r, o + r, o + r], fill=255)
    sh = Image.new("RGBA", lay.size, dark + (0,))
    sm = Image.new("L", lay.size, 0)
    ImageDraw.Draw(sm).ellipse([o - r * 0.55, o - r * 0.75, o + r * 1.7, o + r * 1.6], fill=150)
    sh.putalpha(sm.filter(ImageFilter.GaussianBlur(r * 0.25)))
    lay = Image.alpha_composite(lay, sh)
    lay.putalpha(Image.composite(lay.getchannel("A"), Image.new("L", lay.size, 0), mask))
    if tilt:
        lay = lay.rotate(98 - 90 + t * 0, resample=Image.BICUBIC)
    img.alpha_composite(lay, (int(cx - o), int(cy - o)))
    d = ImageDraw.Draw(img)
    if ring or kind == "saturn":
        for k in range(3):
            rr = r * (1.45 + k * 0.18)
            d.arc([cx - rr, cy - rr * 0.28, cx + rr, cy + rr * 0.28], 160, 380, fill=(235, 215, 170) if k != 1 else (200, 180, 140), width=int(r * 0.07))
    if tilt:  # 横倒しの自転軸
        a = math.radians(98)
        ex, ey = math.sin(a) * r * 1.5, -math.cos(a) * r * 1.5
        d.line([(cx - ex, cy - ey), (cx + ex, cy + ey)], fill=WHT, width=6)
        d.text((cx + ex + 20, cy + ey - 20), "自転軸", font=font(36), fill=WHT, anchor="lm", stroke_width=4, stroke_fill=BLK)


def background(kind, t):
    img = Image.new("RGBA", (W, H), (8, 10, 30, 255))
    d = ImageDraw.Draw(img)
    if kind == "gmroom":
        img.paste((22, 12, 40, 255), (0, 0, W, H))
        for yy in range(0, H, 34):                       # 網点
            for xx in range(0, W, 34):
                r = 2 + 8 * (xx / W)
                d.ellipse([xx + (yy // 34 % 2) * 17 - r, yy - r, xx + (yy // 34 % 2) * 17 + r, yy + r], fill=(34, 20, 60))
        return img
    if kind == "jupiter_fall":
        img.paste((180, 130, 95, 255), (0, 0, W, H))
        for k in range(14):
            y = (k * 110 - t * 160) % (H + 220) - 110
            col = [(205, 160, 120), (160, 110, 80), (225, 190, 150), (185, 125, 90)][k % 4]
            d.rectangle([0, y, W, y + 70 + (k % 3) * 25], fill=col)
        return img
    stars(d, t)
    if kind in PLANET:
        r = PLANET[kind][3]
        if kind == "saturn":
            planet(img, kind, 1290, 470, 250, t)
        else:
            planet(img, kind, 1420, 470, r, t)
    return img


# ── テロップ
def wrap(text, n=21):
    """意味の切れ目（句読点）で2行以内に分ける"""
    if len(text) <= n:
        return [text]
    best = None
    for i in range(len(text) * 2 // 5, len(text) * 3 // 5 + 3):
        if 0 < i < len(text) and text[i - 1] in "、。？！…―":
            if best is None or abs(i - len(text) / 2) < abs(best - len(text) / 2):
                best = i
    if best is None:
        best = (len(text) + 1) // 2
    return [text[:best], text[best:]]


def subtitle(img, who, text):
    d = ImageDraw.Draw(img)
    band = Image.new("RGBA", (W, 190), (0, 0, 0, 170))
    img.alpha_composite(band, (0, H - 190))
    col = ZCOL if who == "z" else GCOL
    name = "ずんだもん" if who == "z" else "マスター"
    f = font(30)
    tw = f.getbbox(name)[2]
    d.rounded_rectangle([60, H - 178, 60 + tw + 40, H - 136], 10, fill=col)
    d.text((80, H - 157), name, font=f, fill=WHT, anchor="lm")
    lines = wrap(text)
    fs = 56 if max(len(l) for l in lines) <= 21 else 50
    for i, l in enumerate(lines):
        y = H - 95 + (i - (len(lines) - 1) / 2) * 68
        d.text((W // 2, y), l, font=font(fs), fill=WHT if who == "z" else (255, 236, 150), anchor="mm", stroke_width=7, stroke_fill=BLK)


def corner_note(img):
    ImageDraw.Draw(img).text((W - 30, 30), "妄想科学｜この物語はフィクションです", font=font(24, True), fill=(220, 220, 230), anchor="ra",
                             stroke_width=3, stroke_fill=BLK)


# ── 演出
def data_card(img, card, u, hl):
    if not card:
        return
    x0 = -520 + 560 * ease(u / 0.8)
    y0 = 30
    RH = 50                                          # 行の高さ（カードはずんだもんの頭にかからない大きさ）
    lay = Image.new("RGBA", (500, 80 + RH * (len(card) - 1)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, 499, lay.height - 1], 18, fill=(10, 14, 40, 225), outline=(120, 170, 255), width=4)
    d.text((26, 40), card[0], font=font(46), fill=YEL, anchor="lm")
    for i, it in enumerate(card[1:], 1):
        y = 40 + RH * i
        if hl == i:
            d.rounded_rectangle([14, y - 23, 485, y + 23], 10, fill=(255, 214, 0, 255))
            d.text((28, y), it, font=font(32), fill=BLK, anchor="lm")
        else:
            d.text((28, y), it, font=font(30, True), fill=WHT, anchor="lm")
    img.alpha_composite(lay, (int(x0), y0))


def chapter_title(img, name, u):
    if u > 2.2 or u < 0:
        return
    a = min(1, u / 0.3, (2.2 - u) / 0.4)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x = W // 2
    d.text((x, 470), name, font=font(170), fill=WHT + (int(255 * a),), anchor="mm", stroke_width=12, stroke_fill=BLK + (int(255 * a),))
    d.text((x, 590), "調査開始", font=font(48), fill=YEL + (int(255 * a),), anchor="mm", stroke_width=6, stroke_fill=BLK + (int(255 * a),))
    img.alpha_composite(lay)


def stamp_judge(img, reason, u):
    s = back(u / 0.3)
    if s <= 0.02:
        return
    lay = Image.new("RGBA", (900, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([20, 20, 880, 400], 30, outline=RED, width=18)
    d.text((450, 160), "移住：×", font=font(150), fill=RED, anchor="mm")
    d.text((450, 310), reason, font=font(56), fill=RED, anchor="mm")
    lay = lay.rotate(-8, expand=True, resample=Image.BICUBIC)
    lay = lay.resize((max(1, int(lay.width * s)), max(1, int(lay.height * s))))
    img.alpha_composite(lay, (int(1190 - lay.width / 2), int(450 - lay.height / 2)))


def bars(img, items, unit, u):
    x0, y0, w0 = 640, 170, 1180
    lay = Image.new("RGBA", (w0, 120 + 130 * len(items)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, w0 - 1, lay.height - 1], 24, fill=(250, 250, 245, 240), outline=BLK, width=5)
    mx = max(v for _, v, _ in items)
    for i, (lab, v, col) in enumerate(items):
        y = 70 + i * 130
        d.text((40, y + 30), lab, font=font(42), fill=BLK, anchor="lm")
        p = ease((u - i * 0.25) / 0.8)
        bw = int((w0 - 520) * max(0.004, v / mx) * p)
        d.rounded_rectangle([340, y, 340 + max(8, bw), y + 60], 10, fill=tuple(col))
        val = v * p
        txt = (f"{val:.2f}" if v < 1 else f"{val:.1f}" if v < 10 else f"{int(round(val)):,}")
        d.text((360 + max(8, bw), y + 30), txt, font=font(42), fill=BLK, anchor="lm")
    d.text((w0 - 30, lay.height - 30), unit, font=font(30, True), fill=(90, 90, 90), anchor="rm")
    img.alpha_composite(lay, (x0, y0))


def count(img, to, unit, label, u):
    p = ease(u / 1.0)
    v = to * p
    lay = Image.new("RGBA", (760, 330), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, 759, 329], 24, fill=(10, 14, 40, 225), outline=(120, 170, 255), width=4)
    d.text((380, 70), label, font=font(44, True), fill=WHT, anchor="mm")
    d.text((380, 200), f"{int(round(v)):,}{unit}", font=font(130), fill=YEL, anchor="mm", stroke_width=8, stroke_fill=BLK)
    img.alpha_composite(lay, (1040, 300))


def solar_map(img, u):
    d = ImageDraw.Draw(img)
    y = 420
    d.ellipse([-330, y - 220, -10, y + 220], fill=(255, 190, 40))
    names = ["水星", "金星", "地球", "火星", "木星", "土星", "天王星", "海王星"]
    cols = [PLANET[k][0] for k in ("mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune")]
    for i, (n, c) in enumerate(zip(names, cols)):
        p = ease((u - i * 0.12) / 0.4)
        if p <= 0:
            continue
        x = 270 + i * 205
        r = [22, 34, 36, 28, 80, 68, 50, 48][i] * p
        d.ellipse([x - r, y - r, x + r, y + r], fill=c, outline=WHT if n != "地球" else (120, 120, 120), width=4)
        d.text((x, y + 110), n, font=font(36), fill=(150, 150, 150) if n == "地球" else WHT, anchor="mm")
        if n != "地球":
            d.ellipse([x - r - 14, y - r - 14, x + r + 14, y + r + 14], outline=YEL, width=5)


def banner(img, text, u):
    s = back(u / 0.4)
    if s <= 0.02:
        return
    d = ImageDraw.Draw(img)
    f = font(60 * s)
    tw = f.getbbox(text)[2]
    d.rounded_rectangle([W // 2 - tw / 2 - 40, 120, W // 2 + tw / 2 + 40, 230], 16, fill=YEL, outline=BLK, width=6)
    d.text((W // 2, 175), text, font=f, fill=BLK, anchor="mm")


def results(img, u, rank=None):
    d = ImageDraw.Draw(img)
    names = ["水星", "金星", "火星", "木星", "土星", "天王星", "海王星"]
    keys = ["mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune"]
    if rank is None:
        for i, (n, k) in enumerate(zip(names, keys)):
            p = ease((u - i * 0.1) / 0.4)
            x = 760 + (i % 4) * 280; y = 230 + (i // 4) * 330
            r = int(90 * p)
            if r < 2:
                continue
            d.ellipse([x - r, y - r, x + r, y + r], fill=PLANET[k][0], outline=WHT, width=4)
            d.text((x, y + 130), n, font=font(40), fill=WHT, anchor="mm")
            if p >= 1:
                d.line([(x - 70, y - 70), (x + 70, y + 70)], fill=RED, width=18); d.line([(x + 70, y - 70), (x - 70, y + 70)], fill=RED, width=18)
        return
    d.rounded_rectangle([700, 90, 1860, 860], 26, fill=(10, 14, 40, 230), outline=YEL, width=5)
    d.text((1280, 160), "もし住むなら ランキング", font=font(56), fill=YEL, anchor="mm")
    d.text((1280, 225), "（どれも、そのままでは住めません）", font=font(28, True), fill=(200, 200, 210), anchor="mm")
    rows = [(3, "金星", "上空50kmは気圧・温度が地球に近い"), (2, "水星", "北極のクレーターの影に氷"), (1, "火星", "1日が約24時間40分・氷がある")]
    for i, (n, nm, why) in enumerate(rows):
        if rank == 0 or n < rank:
            continue
        y = 330 + (3 - n) * 170
        d.text((760, y), f"第{n}位", font=font(60), fill=YEL if n == 1 else WHT, anchor="lm")
        d.text((1000, y - 18), nm, font=font(64), fill=WHT, anchor="lm")
        d.text((1000, y + 46), why, font=font(34, True), fill=(210, 210, 220), anchor="lm")


def earth_points(img, n):
    d = ImageDraw.Draw(img)
    pts = ["呼吸できる空気", "液体の水", "立てる地面"]
    for i in range(n):
        y = 260 + i * 120
        d.rounded_rectangle([600, y - 45, 1000, y + 45], 16, fill=(255, 255, 255, 235), outline=BLK, width=4)
        d.text((630, y), pts[i], font=font(46), fill=BLK, anchor="lm")
        d.line([(940, y), (960, y + 20), (1000, y - 30)], fill=(40, 170, 80), width=12)


# ── 音声
def load_wav(path):
    with wave.open(path) as w:
        sr = w.getframerate(); ch = w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if ch == 2:
        x = x.reshape(-1, 2).mean(1)
    if sr != SR:
        x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x).astype(np.float32)
    return x


_syn = {}
READ_FIX = {"金星": "きんせい", "大赤斑": "だいせきはん", "環": "わ", "170分の1": "ひゃくななじゅうぶんのいち", "天王星": "てんのうせい", "水深": "すいしん", "日陰": "ひかげ", "一等地": "いっとうち"}


def synth(vv, text, out):
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
    A = "vv_assets"
    key = vv["vvm"]
    if key not in _syn:
        ort = Onnxruntime.load_once(filename=f"{A}/voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3")
        s = Synthesizer(ort, OpenJtalk(f"{A}/open_jtalk_dic_utf_8-1.11"))
        with VoiceModelFile.open(f"{A}/{key}") as m:
            s.load_voice_model(m)
        _syn[key] = s
    s = _syn[key]
    for k_, v_ in READ_FIX.items():                     # 読み間違いやすい語（金星→きんぼし 等）
        text = text.replace(k_, v_)
    q = s.create_audio_query(re.sub(r"[「」『』]", "", text), vv["style"])
    q.speed_scale = vv.get("speed", 1.0); q.intonation_scale = vv.get("intonation", 1.0)
    q.pre_phoneme_length = 0.05; q.post_phoneme_length = 0.08
    open(out, "wb").write(s.synthesis(q, vv["style"]))
    if vv.get("echo"):
        tmp = out + ".e.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out, "-af", "aecho=0.8:0.55:60|130:0.28|0.16", tmp], check=True)
        os.replace(tmp, out)


def bgm(total):
    """落ち着いた宇宙っぽいパッド（オリジナル）。声のじゃまをしない小さめの音量"""
    t = np.arange(int(total * SR)) / SR
    chords = [[146.8, 220.0, 277.2, 370.0], [123.5, 185.0, 246.9, 293.7], [98.0, 196.0, 246.9, 293.7], [110.0, 164.8, 220.0, 277.2]]
    y = np.zeros_like(t)
    seg = 6.0
    for i, ch in enumerate(chords * int(total / seg / 4 + 2)):
        a, b = int(i * seg * SR), int((i + 1) * seg * SR + SR)
        if a >= len(t):
            break
        b = min(b, len(t)); tt = t[a:b] - t[a]
        env = np.minimum(1, tt / 1.5) * np.minimum(1, np.maximum(0, (seg + 1 - tt)) / 1.5)
        for f in ch:
            y[a:b] += (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt)) * env * 0.05
    pulse = (np.sin(2 * np.pi * 0.5 * t) > 0.995).astype(np.float32)
    y += np.convolve(pulse, np.exp(-np.arange(int(0.3 * SR)) / SR * 12) * np.sin(2 * np.pi * 880 * np.arange(int(0.3 * SR)) / SR), "same")[:len(y)] * 0.02
    return (y / (np.abs(y).max() + 1e-9) * 0.10).astype(np.float32)


# ── 組み立て
def build(script, out, t_from=None, t_to=None):
    data = json.load(open(script))
    meta, scenes = data["meta"], data["scenes"]
    work = "build_long"; os.makedirs(work, exist_ok=True)
    # 1) 声を作って、タイムラインを決める
    tl = []          # (開始秒, 終了秒, 場面, 行, wavのnumpy, 包絡)
    t = 0.0
    chapters = []
    op_seg = None
    k = 0
    for sc in scenes:
        if sc["bg"] == "opening":
            op = "output/opening_tankentai.mp4"
            if not os.path.exists(op):
                subprocess.run([sys.executable, "tools/opening_tankentai.py", op], check=True)
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", op], capture_output=True, text=True).stdout)
            op_seg = (t, t + dur, op)
            t += dur + 0.3
            continue
        if sc.get("chapter"):
            chapters.append((t, sc["chapter"]))
        sc["_t0"] = t
        for ln in sc["lines"]:
            vv = meta["voices"][ln["who"]]
            import hashlib                                   # セリフと声で名前を決める（行を足しても取り違えない）
            p = f"{work}/v_" + hashlib.md5((ln["who"] + meta["yomi"].get(ln["say"], ln["say"]) + json.dumps(vv, sort_keys=True) + json.dumps(READ_FIX, ensure_ascii=False)).encode()).hexdigest()[:12] + ".wav"
            if not os.path.exists(p):
                synth(vv, meta["yomi"].get(ln["say"], ln["say"]), p)
            x = load_wav(p)
            if ln["who"] == "g":
                t += GM_PRE
            n = len(x) // (SR // FPS) + 1
            env = np.array([np.sqrt(np.mean(x[i * (SR // FPS):(i + 1) * (SR // FPS)] ** 2) + 1e-12) for i in range(n)])
            hold = 0.6 if ln["fx"].get("judge") else 0.0
            tl.append([t, t + len(x) / SR + hold, sc, ln, x, env])
            t += len(x) / SR + hold + GAP
            k += 1
        sc["_t1"] = t
        t += SCENE_GAP
    total = t + 1.5
    print("全体の長さ", round(total, 1), "秒")
    # 2) 音
    mix = np.zeros(int((total + 1) * SR), np.float32)
    se_ev = []
    for t0, t1, sc, ln, x, _ in tl:
        i = int(t0 * SR); mix[i:i + len(x)] += x * 1.0
        fx = ln["fx"]
        if fx.get("judge"):                        # 効果音は控えめに（長尺は耳ざわりのよさ優先）
            se_ev += [("thud", t0 + 0.05, 0.8)]
        if fx.get("bars") or fx.get("count"):
            se_ev += [("pop_lo", t0 + 0.1, 0.6)]
        if fx.get("rank") in (1, 2, 3):
            se_ev += [("chime_a", t0, 0.6)]
    for sc in scenes:
        if sc.get("card") and "_t0" in sc:
            se_ev += [("shimmer", sc["_t0"], 0.7)]
    for name, at, kk in se_ev:
        s = se.sound(name)
        s = np.interp(np.arange(int(len(s) * SR / se.SR)) * se.SR / SR, np.arange(len(s)), s).astype(np.float32)
        i = int(at * SR); mix[i:i + len(s)] += s[:max(0, len(mix) - i)] * kk
    b = bgm(total + 1)
    if op_seg:   # オープニングの間はBGMを止めて、オープニングの音を入れる
        a0, a1 = int(op_seg[0] * SR), int(op_seg[1] * SR)
        b[a0:a1] = 0
        tmpw = f"{work}/op.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", op_seg[2], "-ac", "1", "-ar", str(SR), tmpw], check=True)
        ox = load_wav(tmpw); mix[a0:a0 + len(ox)] += ox * 0.8
    mix += b[:len(mix)]
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.92
    wav_out = f"{work}/mix.wav"
    with wave.open(wav_out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    # 3) 映像
    f0 = int((t_from or 0) * FPS); f1 = int(min(total, t_to or total) * FPS)
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-ss", f"{f0 / FPS:.3f}", "-i", wav_out, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    op_reader = None
    if op_seg:
        op_reader = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", op_seg[2], "-vf", f"fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                     stdout=subprocess.PIPE)
    op_frames_read = 0
    sheet = []
    for fi in range(f1):
        tt = fi / FPS
        if op_seg and op_seg[0] <= tt < op_seg[1]:
            raw = op_reader.stdout.read(W * H * 3)
            op_frames_read += 1
            if fi >= f0 and len(raw) == W * H * 3:
                p.stdin.write(raw)
            continue
        if fi < f0:
            continue
        fr = frame(tt, tl, scenes)
        if fi % (FPS * 8) == 0:
            sheet.append(fr.resize((480, 270)))
        p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait()
    # コマ割りシートとチャプター
    if sheet:
        cols = 6
        sh = Image.new("RGB", (480 * cols, 270 * ((len(sheet) + cols - 1) // cols)))
        for i, s in enumerate(sheet):
            sh.paste(s, ((i % cols) * 480, (i // cols) * 270))
        sh.save(out.replace(".mp4", "_sheet.jpg"), quality=80)
    with open(out.replace(".mp4", "_chapters.txt"), "w") as f:
        f.write("0:00 オープニング\n" if chapters and chapters[0][0] > 0.5 else "")
        for ct, name in chapters:
            f.write(f"{int(ct // 60)}:{int(ct % 60):02d} {name}\n")
    print(out, round(total, 1), "s")


def current(tl, tt):
    """いま話している行（間のあいだは直前の行を表示）"""
    cur = None
    for row in tl:
        if row[0] <= tt:
            cur = row
        else:
            break
    return cur


def frame(tt, tl, scenes):
    row = current(tl, tt)
    if row is None:
        return Image.new("RGB", (W, H))
    t0, t1, sc, ln, x, env = row
    fx = ln["fx"]
    u = tt - t0
    speaking = t0 <= tt < t1
    fi = int((tt - t0) * FPS)
    lv = env[fi] if speaking and fi < len(env) else 0
    mouth = 0 if lv < 0.02 else 1 if lv < 0.07 else 2
    blink = 1 if (int(tt * FPS) % 90) < 3 else 0
    img = background("jupiter_fall" if fx.get("fall") else sc["bg"], tt)
    d = ImageDraw.Draw(img)
    zface = ln["face"] if ln["who"] == "z" else "通常"
    # 直前のずんだもんの表情を保つ（GMが話している間）
    if ln["who"] == "g":
        prev = [r for r in tl if r[0] < t0 and r[2] is sc and r[3]["who"] == "z"]
        zface = prev[-1][3]["face"] if prev else "通常"
    zmouth = mouth if ln["who"] == "z" else 0
    dmg = sum(1 for r in tl if r[3]["fx"].get("judge") and r[1] < tt)        # これまでに受けた判定の数
    if sc["bg"] == "earth" or sc["id"] in ("ending",):
        dmg = min(dmg, 7)
    hide_z = bool(fx.get("fate") or fx.get("empty") or fx.get("fall") or fx.get("blown") or fx.get("jump") or fx.get("ringfall"))
    # 場面ごとの大きな絵
    if sc["bg"] == "gmroom":
        talk = lv * 6 if ln["who"] == "g" else 0
        img.alpha_composite(gm_figure(W, H, 1450, 760, 1.15, 1.0, talk))
    if fx.get("map"):
        solar_map(img, u)
    if fx.get("ring"):
        for q in range(140):                              # 環の粒が回る
            a = q * 0.37 + tt * 0.4
            rr = 250 * (1.6 + (q % 7) * 0.08)
            px, py = 1290 + rr * math.cos(a), 470 + rr * 0.16 * math.sin(a)
            d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(240, 225, 190))
    if fx.get("tilt"):
        img.paste((8, 10, 30, 255), (900, 60, W, 880)); stars(d, tt)
        planet(img, "uranus", 1420, 470, PLANET["uranus"][3], tt, tilt=True)
    if fx.get("results"):
        results(img, u)
    if "rank" in fx:
        results(img, u, fx["rank"])
    if fx.get("earthpt"):
        earth_points(img, fx["earthpt"])
    # ずんだもん（左に立つ。顔は隠さない）
    if fx.get("fate"):
        reg = img.crop((200, 0, 1500, 900)).convert("RGB")
        ch = damaged(zunda(zface if ln["who"] == "z" else "泣き", 460, zmouth, 0), dmg)
        mosofx.draw(reg, 0, 900, u, max(1.5, t1 - t0), {"type": "fate", "mode": fx["fate"], "label": "", "hmax": 0.78,
                                                       "weight": fx.get("weight", "")}, ch)
        img.paste(reg.convert("RGBA"), (200, 0))
    if fx.get("fall"):
        z = outline(zunda("焦り" if ln["who"] == "g" else zface, 520, zmouth, blink)).rotate(math.sin(tt * 0.8) * 10, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(z, (int(W / 2 - z.width / 2), int(420 - z.height / 2 + math.sin(tt * 1.2) * 10)))
        for q in range(6):                                 # 落ちている線（ゆっくり上へ流れる）
            xx = 360 + q * 230; yy = (q * 173 - tt * 300) % H
            d.line([(xx, yy), (xx, yy + 110)], fill=(255, 255, 255), width=4)
        if fx.get("gauge"):
            p_ = min(1, (tt - t0) / 4)
            d.rounded_rectangle([1660, 120, 1780, 820], 20, fill=(20, 20, 30), outline=WHT, width=5)
            hgt = int(660 * (0.2 + 0.8 * p_))
            d.rounded_rectangle([1675, 805 - hgt, 1765, 805], 14, fill=RED)
            d.text((1720, 860), "圧力・温度", font=font(34), fill=WHT, anchor="mm", stroke_width=4, stroke_fill=BLK)
    if fx.get("jump"):
        for i, (lab, hmax) in enumerate((("地球", 120), ("火星", 312))):
            x0 = 760 + i * 520
            hop = abs(math.sin(tt * 2.2)) * hmax
            d.line([(x0 - 160, 800), (x0 + 160, 800)], fill=WHT, width=6)
            z = outline(zunda("笑顔", 300, 1, 0))
            img.alpha_composite(z, (int(x0 - z.width / 2), int(800 - z.height - hop)))
            d.text((x0, 850), lab, font=font(44), fill=WHT, anchor="mm", stroke_width=5, stroke_fill=BLK)
        d.text((1290, 140), "同じ勢いで跳ぶと 約2.6倍", font=font(52), fill=YEL, anchor="mm", stroke_width=6, stroke_fill=BLK)
    if fx.get("ringfall"):
        k_ = min(1, u / 2.2)
        y = 180 + 640 * (k_ ** 2)
        z = outline(damaged(zunda("驚き" if k_ < 0.3 else "泣き", 360, zmouth, 0), dmg)).rotate(k_ * 120, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(z, (int(1180 - z.width / 2), int(y - z.height / 2)))
        for q in range(40):                                   # 手前の粒（ずんだもんの前を通る）
            a = q * 0.61 + tt * 0.5
            rr = 250 * (1.6 + (q % 5) * 0.1)
            px, py = 1290 + rr * math.cos(a), 470 + rr * 0.16 * math.sin(a)
            if math.sin(a) > 0:
                d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(240, 225, 190))
        if k_ > 0.35:
            d.text((1180, 120), "すり抜け", font=font(70), fill=YEL, anchor="mm", stroke_width=8, stroke_fill=BLK)
    if fx.get("blown"):
        k = ease((tt - t0) / 1.2)
        z = outline(zunda("泣き", 560, zmouth, 0)).rotate(k * 400, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(z, (int(360 - z.width / 2 + k * 1900), int(600 - z.height / 2 - k * 200)))
    wind = fx.get("wind", 0)
    if wind:
        for q in range(int(30 * wind)):
            yy = (q * 61) % 860 + 40; xx = (q * 233 + tt * 1100) % (W + 400) - 400
            d.line([(xx, yy), (xx + 260, yy)], fill=(220, 230, 255), width=4)
    if not hide_z:
        if fx.get("up") and ln["who"] == "z":                    # 寄り：ゆっくり近づく（揺らさない。顔は隠さない）
            k_ = ease(u / 0.8)
            hz = int(600 + 500 * k_)
            z = outline(damaged(zunda(zface, hz, zmouth, blink), dmg), 6)
            img.alpha_composite(z, (int(330 + 150 * k_ - z.width / 2), int(890 + 260 * k_ - z.height)))
        else:
            lean = int(wind * 40)
            z = outline(damaged(zunda(zface, 540, zmouth, blink), dmg), 6)
            if wind:
                z = z.rotate(-wind * 12, expand=True, resample=Image.BICUBIC)
            bob = math.sin(tt * 2.4) * 4
            img.alpha_composite(z, (int(330 - z.width / 2 + lean), int(890 - z.height + bob)))
    # GM（惑星の場面では右上の通信窓）
    if ln["who"] == "g" and sc["bg"] != "gmroom":
        wx, wy, ww, wh = 1500, 60, 380, 260
        win = Image.new("RGBA", (ww, wh), (14, 8, 28, 235))
        win.alpha_composite(gm_figure(ww, wh, ww // 2, int(wh * 1.12), 0.42, 1.0, lv * 6))
        ImageDraw.Draw(win).rectangle([0, 0, ww - 1, wh - 1], outline=(170, 120, 255), width=6)
        ImageDraw.Draw(win).text((14, 12), "通信：マスター", font=font(26), fill=(220, 200, 255))
        img.alpha_composite(win, (wx, wy))
    # データカード・数字・判定
    if sc.get("card"):
        data_card(img, sc["card"], tt - sc["_t0"], fx.get("hl"))
        if sc.get("chapter"):
            chapter_title(img, sc["chapter"], tt - sc["_t0"])
    if fx.get("bars"):
        bars(img, fx["bars"], fx.get("unit", ""), u)
    if fx.get("count"):
        c = fx["count"]; count(img, c[0], c[1], c[2], u)
    if fx.get("rule"):
        banner(img, fx["rule"], u)
    if fx.get("next"):
        banner(img, fx["next"], u)
    if fx.get("goal"):                               # 再生数の目標（大きな数字で）
        g_ = fx["goal"]; s_ = back(u / 0.4)
        if s_ > 0.02:
            d.rounded_rectangle([760, 220, 1700, 600], 30, fill=(10, 14, 40, 235), outline=YEL, width=6)
            d.text((1230, 300), g_[0], font=font(int(60 * s_)), fill=WHT, anchor="mm")
            d.text((1230, 460), g_[1], font=font(int(170 * s_)), fill=YEL, anchor="mm", stroke_width=10, stroke_fill=BLK)
    if fx.get("judge"):
        stamp_judge(img, fx["judge"], u)
    if fx.get("logo"):
        d.text((W // 2 + 200, 330), "ずんだもんの", font=font(70), fill=WHT, anchor="mm", stroke_width=8, stroke_fill=BLK)
        d.text((W // 2 + 200, 470), "妄想科学", font=font(170), fill=YEL, anchor="mm", stroke_width=12, stroke_fill=BLK)
    subtitle(img, ln["who"], ln["say"])
    return img.convert("RGB")


if __name__ == "__main__":
    a = sys.argv[1:]
    tf = float(a[a.index("--from") + 1]) if "--from" in a else None
    tt_ = float(a[a.index("--to") + 1]) if "--to" in a else None
    build(a[0], a[1], tf, tt_)
