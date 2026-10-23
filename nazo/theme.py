# nazo/theme.py — 雑学ショートの「昭和ポップ」系の見た目（色数をしぼった配色、集中線・波・グラデの背景、
#   2色刷り風の写真、立体の押し出し文字、紙のざらつき）。short3 から使う。
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
_fc = {}


def font(size):
    size = max(8, int(size))
    if size not in _fc:
        _fc[size] = ImageFont.truetype(FONT, size, index=0)
    return _fc[size]


# 色は (暗, 中, 明, 文字の面, 文字の側面, 縁)
THEMES = {
    "orange_rays": {"bg": "rays", "c": [(232, 140, 70), (240, 170, 100), (247, 200, 140)],
                    "face": (160, 216, 232), "side": (31, 78, 121), "edge": (31, 78, 121), "duo": ((31, 78, 121), (247, 214, 170))},
    "blue_waves":  {"bg": "waves", "c": [(28, 78, 140), (79, 163, 209), (169, 220, 235)],
                    "face": (169, 220, 235), "side": (40, 120, 170), "edge": (250, 244, 228), "duo": ((20, 50, 100), (200, 236, 245))},
    "pink_grad":   {"bg": "grad", "c": [(232, 70, 170), (190, 80, 230), (150, 70, 235)],
                    "face": (255, 246, 90), "side": (0, 0, 0), "edge": (0, 0, 0), "duo": ((90, 20, 120), (255, 160, 220))},
    "mint_black":  {"bg": "panels", "c": [(10, 10, 12), (240, 140, 216), (142, 240, 200)],
                    "face": (240, 140, 216), "side": (10, 10, 12), "edge": (142, 240, 200), "duo": ((50, 60, 140), (240, 150, 220))},
    "green_red":   {"bg": "stripes", "c": [(30, 90, 40), (226, 72, 40), (246, 208, 128)],
                    "face": (246, 208, 128), "side": (30, 90, 40), "edge": (30, 90, 40), "duo": ((30, 90, 40), (246, 208, 128))},
}
_grain = {}


def grain(im, amount=18):
    """紙のざらつき（同じ大きさなら同じ模様を使い回す）"""
    key = im.size
    if key not in _grain:
        rng = np.random.default_rng(5)
        _grain[key] = rng.normal(0, amount, (im.size[1], im.size[0], 1)).astype(np.float32)
    a = np.asarray(im, np.float32) + _grain[key]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def background(name, w, h, t):
    th = THEMES[name]
    c0, c1, c2 = th["c"]
    im = Image.new("RGB", (w, h), c1)
    d = ImageDraw.Draw(im)
    kind = th["bg"]
    if kind == "rays":                      # 集中線がゆっくり回る
        cx, cy = w // 2, int(h * 0.42)
        for k in range(0, 360, 12):
            a1, a2 = math.radians(k + t * 12), math.radians(k + 6 + t * 12)
            d.polygon([(cx, cy), (cx + 3000 * math.cos(a1), cy + 3000 * math.sin(a1)),
                       (cx + 3000 * math.cos(a2), cy + 3000 * math.sin(a2))], fill=c2)
    elif kind == "waves":                   # 波の帯がゆっくり流れる
        for band, col in enumerate((c0, c1, c2, c1, c0, c2)):
            pts = []
            base = h * (band / 6) - h * 0.08
            for x in range(0, w + 40, 20):
                pts.append((x, base + 70 * math.sin(x / 120 + t * 1.5 + band)))
            d.polygon(pts + [(w, h), (0, h)], fill=col)
    elif kind == "grad":                    # 縦のグラデーション
        a = np.linspace(0, 1, h)[:, None, None]
        arr = (np.array(c0) * (1 - a) + np.array(c2) * a) * np.ones((1, w, 1))
        im = Image.fromarray(arr.astype(np.uint8))
    elif kind == "panels" and h < 1500:     # 絵の帯の中：飾り枠は写真に隠れるので、黒地に細い縁だけ
        im = Image.new("RGB", (w, h), c0)
        d = ImageDraw.Draw(im)
        d.rectangle([16, 16, w - 17, h - 17], outline=c2, width=6)
        d.rectangle([34, 34, w - 35, h - 35], outline=c1, width=3)
    elif kind == "panels":                  # 黒地にミントとピンクの飾り枠
        im = Image.new("RGB", (w, h), c0)
        d = ImageDraw.Draw(im)
        for (x0, y0, x1, y1, col) in ((40, 40, w - 40, 210, c2), (40, h - 260, w // 2 - 20, h - 40, c1),
                                      (w // 2 + 20, h - 260, w - 40, h - 40, c2)):
            d.rounded_rectangle([x0, y0, x1, y1], 36, fill=col)
            d.rounded_rectangle([x0 + 14, y0 + 14, x1 - 14, y1 - 14], 26, outline=c0, width=4)
    elif kind == "stripes":                 # 太い縦じま（緑と朱）
        im = Image.new("RGB", (w, h), c0)
        d = ImageDraw.Draw(im)
        for x in range(-200, w + 200, 220):
            off = int(30 * math.sin(t * 2))
            d.rectangle([x + off, 0, x + off + 90, h], fill=c1)
    return grain(im, 14)


def duotone(im, dark, light):
    """写真を2色刷り風に"""
    g = np.asarray(im.convert("L"), np.float32)[..., None] / 255.0
    lo, hi = np.percentile(g, 3), np.percentile(g, 97)      # 濃淡を広げてから2色に
    g = np.clip((g - lo) / max(hi - lo, 1e-3), 0, 1) ** 1.15
    arr = np.array(dark, np.float32) * (1 - g) + np.array(light, np.float32) * g
    return Image.fromarray(arr.astype(np.uint8))


def halftone(im, cell=7):
    """網点（白地に濃い点）を重ねる"""
    g = im.convert("L").resize((max(1, im.width // cell), max(1, im.height // cell)))
    dots = Image.new("L", im.size, 255)
    dd = ImageDraw.Draw(dots)
    px = g.load()
    for y in range(g.height):
        for x in range(g.width):
            r = (1 - px[x, y] / 255) * cell * 0.62
            if r > 0.6:
                cx, cy = x * cell + cell / 2, y * cell + cell / 2
                dd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)
    return ImageChops.multiply(im.convert("RGB"), Image.merge("RGB", (dots, dots, dots)).point(lambda v: 150 + v * 105 // 255))


def extrude_text(base, x, y, text, size, th, depth=None, anchor="mm", angle=0):
    """立体の押し出し文字（面の色・側面の色・縁）。base は RGB 画像。"""
    face, side, edge = th["face"], th["side"], th["edge"]
    size = int(size)
    f = font(size)
    depth = depth if depth is not None else max(8, size // 6)
    lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    sw = max(3, size // 22)
    for k in range(depth, 0, -1):          # 右下へ押し出した側面
        ld.text((x + k, y + k), text, font=f, fill=side + (255,), anchor=anchor, stroke_width=sw, stroke_fill=edge + (255,))
    ld.text((x, y), text, font=f, fill=face + (255,), anchor=anchor, stroke_width=sw, stroke_fill=edge + (255,))
    ld.text((x, y), text, font=f, fill=face + (255,), anchor=anchor)
    if angle:
        lay = lay.rotate(angle, center=(x, y), resample=Image.BICUBIC)
    base.paste(lay, (0, 0), lay)
