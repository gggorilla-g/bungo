# kaidan/kitsune.py — 語り部「狐面の語り部」（オリジナル）をパーツの組み合わせで描く
#   kitsune(lamp=1.0, tilt=0, size=700) -> RGBA Image
#     lamp: 提灯の明るさ（0.4〜1.0。揺らすと炎のゆらぎになる）
#     tilt: 首のかしげ（度）。怖い場面で少し傾ける
#   4倍の大きさで描いてから縮小し、線をなめらかにする。外部素材は使わない。
import math
from PIL import Image, ImageDraw, ImageFilter

INK = (20, 16, 22, 255)
HAIR = (18, 16, 24, 255)
KIMONO = (34, 36, 62, 255)        # 濃紺
KIMONO_D = (24, 25, 44, 255)
OBI = (120, 28, 32, 255)          # 臙脂の帯
COLLAR = (228, 222, 210, 255)     # 襦袢の衿
MASK = (246, 242, 234, 255)       # 狐面（白）
MASK_D = (214, 206, 192, 255)
RED = (196, 36, 36, 255)          # 隈取
GOLD = (210, 160, 60, 255)
LAMP = (232, 92, 40, 255)         # 提灯の紙
LAMP_D = (150, 40, 24, 255)

S = 4


def _p(pts):
    return [(x * S, y * S) for x, y in pts]


def _poly(d, pts, fill, w=0):
    d.polygon(_p(pts), fill=fill, outline=INK if w else None, width=w * S if w else 0)


def _ell(d, box, fill, w=0):
    x0, y0, x1, y1 = [v * S for v in box]
    d.ellipse([x0, y0, x1, y1], fill=fill, outline=INK if w else None, width=w * S if w else 0)


def _head(lamp):
    """頭（髪と狐面）だけを別に描き、首のかしげで回せるようにする。座標は 300x300 の中の頭の領域"""
    im = Image.new("RGBA", (300 * S, 300 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # 後ろ髪（肩までの黒髪）
    _poly(d, [(98, 70), (86, 150), (96, 176), (204, 176), (214, 150), (202, 70), (150, 40)], HAIR)
    _ell(d, (96, 34, 204, 136), HAIR)
    # 狐面：耳
    _poly(d, [(104, 82), (108, 14), (150, 62)], MASK, 3)
    _poly(d, [(196, 82), (192, 14), (150, 62)], MASK, 3)
    _poly(d, [(113, 66), (114, 32), (138, 60)], RED)
    _poly(d, [(187, 66), (186, 32), (162, 60)], RED)
    # 狐面：顔（上が広く、鼻先へすぼまる）
    _poly(d, [(106, 72), (194, 72), (200, 104), (176, 150), (150, 172), (124, 150), (100, 104)], MASK, 3)
    _poly(d, [(150, 172), (138, 158), (162, 158)], MASK_D)
    _ell(d, (144, 160, 156, 170), INK)            # 鼻先
    # 目（細い切れ込み）と隈取
    for sx in (1, -1):
        cx = 150 + sx * 26
        _poly(d, [(cx - sx * 18, 104), (cx + sx * 16, 94), (cx + sx * 12, 100), (cx - sx * 16, 108)], INK)
        _poly(d, [(cx - sx * 20, 112), (cx + sx * 20, 100), (cx + sx * 22, 106), (cx - sx * 16, 118)], RED)
    # 額の印（宝珠）
    _ell(d, (143, 78, 157, 92), RED)
    _ell(d, (147, 82, 153, 88), GOLD)
    # 口の線
    d.arc([138 * S, 140 * S, 162 * S, 160 * S], 20, 160, fill=RED, width=3 * S)
    # 提灯の照り返し（右側だけ少し暖色に）
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([150 * S, 60 * S, 260 * S, 180 * S], fill=(255, 140, 60, int(70 * lamp)))
    glow = glow.filter(ImageFilter.GaussianBlur(20 * S))
    mask_alpha = im.split()[3]
    tinted = Image.alpha_composite(im, Image.composite(glow, Image.new("RGBA", im.size, (0, 0, 0, 0)), mask_alpha))
    return tinted


def kitsune(lamp=1.0, tilt=0.0, size=700):
    W = H = 300
    im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # 提灯の光（背後にぼんやり）
    halo = Image.new("RGBA", im.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    r = 34 + 8 * lamp
    hd.ellipse([(236 - r) * S, (214 - r) * S, (236 + r) * S, (214 + r) * S], fill=(255, 120, 40, int(120 * lamp)))
    halo = halo.filter(ImageFilter.GaussianBlur(14 * S))
    im = Image.alpha_composite(im, halo)
    d = ImageDraw.Draw(im)
    # 着物（肩から下）
    _poly(d, [(60, 300), (74, 210), (104, 176), (196, 176), (226, 210), (240, 300)], KIMONO, 4)
    # 袖のひだ
    d.line(_p([(96, 230), (86, 300)]), fill=KIMONO_D, width=4 * S)
    d.line(_p([(204, 230), (214, 300)]), fill=KIMONO_D, width=4 * S)
    # 衿（白い襦袢の重なり）
    _poly(d, [(122, 176), (150, 246), (178, 176), (166, 176), (150, 220), (134, 176)], COLLAR)
    _poly(d, [(112, 176), (150, 268), (188, 176), (178, 176), (150, 246), (122, 176)], KIMONO_D)
    # 帯
    _poly(d, [(84, 262), (216, 262), (220, 290), (80, 290)], OBI, 3)
    d.line(_p([(84, 276), (216, 276)]), fill=GOLD, width=2 * S)
    # 提灯を持つ手（右）と提灯
    d.line(_p([(204, 214), (236, 168)]), fill=INK, width=3 * S)        # 持ち手の竹
    lt = tuple(int(c * (0.55 + 0.45 * lamp)) for c in LAMP[:3]) + (255,)
    _ell(d, (212, 180, 260, 250), lt, 3)
    for y in (194, 208, 222, 236):
        d.line(_p([(214, y), (258, y)]), fill=LAMP_D, width=2 * S)
    from PIL import ImageFont
    try:
        f = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", 30 * S, index=0)
        d.text((236 * S, 216 * S), "怪", font=f, fill=(40, 12, 8, 230), anchor="mm")
    except OSError:
        pass
    _poly(d, [(220, 176), (252, 176), (250, 184), (222, 184)], INK)
    _poly(d, [(220, 246), (252, 246), (250, 254), (222, 254)], INK)
    _ell(d, (196, 206, 216, 224), COLLAR, 2)                           # 手
    # 頭（首のかしげ）
    head = _head(lamp)
    if tilt:
        head = head.rotate(tilt, resample=Image.BICUBIC, center=(150 * S, 176 * S))
    im = Image.alpha_composite(im, head)
    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "kitsune.png"
    row = Image.new("RGBA", (2100, 700), (12, 10, 16, 255))
    for i, (l, t) in enumerate([(1.0, 0), (0.5, 0), (0.8, -9)]):
        k = kitsune(l, t, 700)
        row.alpha_composite(k, (i * 700, 0))
    row.convert("RGB").save(out)
