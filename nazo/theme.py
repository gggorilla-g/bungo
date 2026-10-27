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
    "space":       {"bg": "space", "c": [(8, 10, 40), (20, 30, 90), (70, 60, 160)],
                    "face": (255, 226, 0), "side": (230, 40, 90), "edge": (10, 10, 30), "duo": ((10, 15, 60), (150, 220, 255))},
    "blueprint":   {"bg": "grid", "c": [(18, 70, 150), (30, 95, 185), (140, 190, 240)],
                    "face": (255, 255, 255), "side": (10, 40, 100), "edge": (10, 40, 100), "duo": ((10, 40, 100), (200, 230, 255))},
    "nebula":      {"bg": "nebula", "c": [(30, 10, 60), (110, 30, 140), (240, 90, 170)],
                    "face": (130, 255, 220), "side": (60, 10, 90), "edge": (20, 0, 40), "duo": ((40, 10, 80), (255, 170, 230))},
    "green_red":   {"bg": "stripes", "c": [(30, 90, 40), (226, 72, 40), (246, 208, 128)],
                    "face": (246, 208, 128), "side": (30, 90, 40), "edge": (30, 90, 40), "duo": ((30, 90, 40), (246, 208, 128))},
    # ── 2026-10-27 追加：毎回ちがう見た目にするための配色（雑学はネタに合わせて選ぶ）
    "lemon_dots":  {"bg": "dots", "c": [(250, 214, 40), (255, 232, 110), (255, 246, 190)],
                    "face": (255, 255, 255), "side": (220, 60, 40), "edge": (40, 20, 10), "duo": ((60, 40, 10), (255, 236, 150))},
    "kraft":       {"bg": "kraft", "c": [(150, 110, 70), (190, 150, 105), (225, 200, 160)],
                    "face": (255, 250, 235), "side": (90, 55, 30), "edge": (60, 35, 20), "duo": ((70, 45, 25), (240, 220, 185))},
    "chalk":       {"bg": "chalk", "c": [(22, 58, 44), (34, 78, 60), (230, 235, 220)],
                    "face": (255, 255, 255), "side": (240, 200, 60), "edge": (15, 40, 30), "duo": ((15, 40, 30), (210, 235, 215))},
    "checker":     {"bg": "checker", "c": [(20, 20, 24), (245, 245, 240), (230, 50, 60)],
                    "face": (255, 226, 0), "side": (230, 50, 60), "edge": (20, 20, 24), "duo": ((20, 20, 24), (245, 245, 240))},
    "sky_clouds":  {"bg": "clouds", "c": [(90, 170, 240), (140, 200, 250), (255, 255, 255)],
                    "face": (255, 255, 255), "side": (30, 90, 170), "edge": (20, 60, 130), "duo": ((25, 70, 140), (220, 240, 255))},
    "rail":        {"bg": "rail", "c": [(30, 34, 40), (60, 66, 76), (0, 150, 210)],
                    "face": (255, 255, 255), "side": (0, 110, 170), "edge": (10, 12, 16), "duo": ((15, 25, 40), (200, 225, 240))},
    "tomato":      {"bg": "diag", "c": [(220, 60, 50), (240, 90, 70), (255, 220, 200)],
                    "face": (255, 255, 255), "side": (120, 20, 20), "edge": (60, 10, 10), "duo": ((90, 20, 20), (255, 210, 190))},
    "deep_sea":    {"bg": "bubbles", "c": [(5, 20, 50), (10, 45, 90), (90, 200, 230)],
                    "face": (140, 240, 255), "side": (10, 60, 110), "edge": (0, 10, 30), "duo": ((5, 20, 50), (150, 230, 250))},
    "forest":      {"bg": "leaves", "c": [(40, 90, 50), (70, 130, 70), (190, 225, 150)],
                    "face": (250, 240, 170), "side": (30, 70, 40), "edge": (20, 45, 25), "duo": ((25, 60, 30), (220, 240, 190))},
    "newspaper":   {"bg": "news", "c": [(238, 234, 222), (225, 220, 205), (30, 30, 30)],
                    "face": (20, 20, 20), "side": (200, 40, 40), "edge": (255, 255, 255), "duo": ((25, 25, 25), (240, 236, 225))},
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
    elif kind in ("space", "nebula"):       # 宇宙：濃紺のグラデーションに星がまたたく（星雲は色のもや付き）
        a = np.linspace(0, 1, h)[:, None, None]
        arr = (np.array(c0) * (1 - a) + np.array(c1) * a) * np.ones((1, w, 1))
        im = Image.fromarray(arr.astype(np.uint8))
        d = ImageDraw.Draw(im, "RGBA")
        if kind == "nebula":
            for j in range(5):
                x = (j * 397 % w); y = (j * 613 % h); r = 260 + j * 60
                for q in range(6):
                    rr = r * (1 - q / 6)
                    d.ellipse([x - rr, y - rr * 0.7, x + rr, y + rr * 0.7], fill=c2 + (10,))
        rng = np.random.default_rng(11)
        for x, y, s, ph in zip(rng.integers(0, w, 160), rng.integers(0, h, 160), rng.uniform(1, 4, 160), rng.uniform(0, 6, 160)):
            b = int(160 + 95 * math.sin(t * 3 + ph))
            d.ellipse([x - s, y - s, x + s, y + s], fill=(255, 255, 255, b))
        if h > 1500:                        # 遠くの惑星（全面の背景だけ。絵の帯には出さない）
            d.ellipse([w - 260, int(h * 0.08), w + 120, int(h * 0.08) + 380], fill=c2 + (200,))
            d.arc([w - 380, int(h * 0.08) + 120, w + 240, int(h * 0.08) + 260], 160, 380, fill=(200, 190, 255, 200), width=10)
    elif kind == "grid":                    # 方眼紙（計算ノート）：細い線と太い線、ゆっくり流れる
        im = Image.new("RGB", (w, h), c1)
        d = ImageDraw.Draw(im)
        off = int(t * 20) % 40
        for x in range(-40 + off, w + 40, 40):
            d.line([(x, 0), (x, h)], fill=(60, 125, 210), width=2)
        for y in range(-40 + off, h + 40, 40):
            d.line([(0, y), (w, y)], fill=(60, 125, 210), width=2)
        for x in range(-200 + off * 5 // 5, w + 200, 200):
            d.line([(x, 0), (x, h)], fill=c2, width=3)
        for y in range(-200 + off, h + 200, 200):
            d.line([(0, y), (w, y)], fill=c2, width=3)
    elif kind == "stripes":                 # 太い縦じま（緑と朱）
        im = Image.new("RGB", (w, h), c0)
        d = ImageDraw.Draw(im)
        for x in range(-200, w + 200, 220):
            off = int(30 * math.sin(t * 2))
            d.rectangle([x + off, 0, x + off + 90, h], fill=c1)
    elif kind == "dots":                    # 水玉がゆっくり斜めに流れる
        off = (t * 30) % 120
        for y in range(-120, h + 120, 120):
            for x in range(-120, w + 120, 120):
                xx = x + off + (60 if (y // 120) % 2 else 0); yy = y + off
                d.ellipse([xx - 26, yy - 26, xx + 26, yy + 26], fill=c2)
    elif kind == "kraft":                   # クラフト紙：繊維のすじと、角のマスキングテープ
        rng = np.random.default_rng(3)
        for _ in range(500):
            x, y = int(rng.integers(0, w)), int(rng.integers(0, h)); L = int(rng.integers(20, 90))
            d.line([(x, y), (x + L, y + int(rng.integers(-4, 5)))], fill=c0 if rng.random() < .5 else c2, width=2)
        for (x, y, a) in ((60, 60, -30), (w - 60, h - 60, -30)):
            tp = Image.new("RGBA", (260, 70), (240, 230, 190, 210)); tp = tp.rotate(a, expand=True)
            im.paste(tp, (x - tp.width // 2, y - tp.height // 2), tp)
    elif kind == "chalk":                   # 黒板：ふちの木枠と、うっすら消した跡
        im = Image.new("RGB", (w, h), c1); d = ImageDraw.Draw(im, "RGBA")
        rng = np.random.default_rng(8)
        for _ in range(40):
            x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
            d.ellipse([x - 160, y - 50, x + 160, y + 50], fill=c2 + (8,))
        d.rectangle([0, 0, w - 1, h - 1], outline=(120, 80, 40), width=24)
    elif kind == "checker":                 # 白黒の市松がゆっくり横へ
        im = Image.new("RGB", (w, h), c1); d = ImageDraw.Draw(im)
        S = 135; off = int(t * 25) % (2 * S)
        for y in range(0, h + S, S):
            for x in range(-2 * S, w + S, S):
                if ((x // S) + (y // S)) % 2 == 0:
                    d.rectangle([x + off, y, x + off + S - 1, y + S - 1], fill=c0)
        d.rectangle([0, int(h * .46), w, int(h * .46) + 26], fill=c2)
    elif kind == "clouds":                  # 青空に白い雲が流れる
        a = np.linspace(0, 1, h)[:, None, None]
        arr = (np.array(c0) * (1 - a) + np.array(c1) * a) * np.ones((1, w, 1))
        im = Image.fromarray(arr.astype(np.uint8)); d = ImageDraw.Draw(im)
        for j in range(7):
            cx = (j * 331 + t * (20 + j * 6)) % (w + 500) - 250; cy = (j * 271) % h
            for (dx, dy, r) in ((0, 0, 80), (70, -30, 95), (150, 0, 75), (75, 25, 85)):
                d.ellipse([cx + dx - r, cy + dy - r * .7, cx + dx + r, cy + dy + r * .7], fill=c2)
    elif kind == "rail":                    # 駅のホーム：濃いグレーに路線色の帯と枕木
        im = Image.new("RGB", (w, h), c0); d = ImageDraw.Draw(im)
        off = int(t * 120) % 160
        for x in range(-160 + off, w + 160, 160):
            d.rectangle([x, int(h * .78), x + 70, int(h * .92)], fill=c1)
        d.rectangle([0, int(h * .80), w, int(h * .80) + 10], fill=(170, 170, 175))
        d.rectangle([0, int(h * .88), w, int(h * .88) + 10], fill=(170, 170, 175))
        d.rectangle([0, int(h * .10), w, int(h * .10) + 40], fill=c2)
    elif kind == "diag":                    # 太い斜めじま
        im = Image.new("RGB", (w, h), c0); d = ImageDraw.Draw(im)
        off = int(t * 40) % 200
        for x in range(-h - 200, w + 200, 200):
            d.polygon([(x + off, 0), (x + off + 90, 0), (x + off + 90 + h, h), (x + off + h, h)], fill=c1)
    elif kind == "bubbles":                 # 深海：下から泡がのぼる
        a = np.linspace(0, 1, h)[:, None, None]
        arr = (np.array(c1) * (1 - a) + np.array(c0) * a) * np.ones((1, w, 1))
        im = Image.fromarray(arr.astype(np.uint8)); d = ImageDraw.Draw(im, "RGBA")
        rng = np.random.default_rng(21)
        for x, sp, r, ph in zip(rng.integers(0, w, 40), rng.uniform(60, 160, 40), rng.uniform(6, 22, 40), rng.uniform(0, h, 40)):
            y = h - ((ph + t * sp) % (h + 60))
            d.ellipse([x - r, y - r, x + r, y + r], outline=c2 + (170,), width=3)
    elif kind == "leaves":                  # 葉っぱの形が散らばってゆれる
        rng = np.random.default_rng(13)
        for x, y, r, ph in zip(rng.integers(0, w, 46), rng.integers(0, h, 46), rng.uniform(30, 70, 46), rng.uniform(0, 6, 46)):
            lf = Image.new("RGBA", (int(r * 2.4), int(r * 1.2)), (0, 0, 0, 0))
            ImageDraw.Draw(lf).ellipse([0, 0, lf.width - 1, lf.height - 1], fill=(c0 if ph < 3 else c2) + (255,))
            lf = lf.rotate(ph * 60 + math.sin(t + ph) * 10, expand=True)
            im.paste(lf, (int(x - lf.width / 2), int(y - lf.height / 2)), lf)
    elif kind == "news":                    # 新聞：段組みの灰色の行と、太い罫
        im = Image.new("RGB", (w, h), c0); d = ImageDraw.Draw(im)
        cols = 4; cw = w // cols
        for c in range(cols):
            for y in range(40, h, 26):
                d.line([(c * cw + 24, y), (c * cw + cw - 24 - (40 if (y // 26 + c) % 7 == 0 else 0), y)], fill=(185, 180, 168), width=8)
            d.line([(c * cw, 0), (c * cw, h)], fill=c2, width=3)
        d.rectangle([0, 0, w, 14], fill=c2)
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


def channel_logo(base, cx, cy, sc, t, name=("ずんだもんの", "脳がとける", "雑学"), char=None, logo_theme="pink_grad"):
    """チャンネルのロゴ（立体文字3段＋右下にずんだもん）。sc: 大きさの倍率、t: 出てからの秒"""
    th = THEMES[logo_theme]
    sizes = (70, 150, 210)
    ys = (-200, -60, 140)
    for j, (row, size, dy) in enumerate(zip(name, sizes, ys)):
        p = min(1.0, max(0.0, (t - 0.08 * j) / 0.2))
        if p <= 0:
            continue
        k = 2 - p if p < 1 else 1
        extrude_text(base, int(cx), int(cy + dy * sc), row, size * sc * k, th, angle=(-5 if j % 2 else 4))
    if char is not None and t > 0.25:
        ch = char.resize((int(char.width * sc), int(char.height * sc)))
        base.paste(ch, (int(cx + 130 * sc), int(cy + 20 * sc)), ch)
