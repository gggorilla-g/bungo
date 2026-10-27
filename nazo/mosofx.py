# nazo/mosofx.py — 「ずんだもんの妄想科学」用のモーショングラフィックス（写真を使わず図で見せる）
#   globe : 回る地球が急に止まり、人や家が東へ吹っ飛ぶ
#   orbit : ずんだもんが光の速さで地球のまわりを周回し、周回数が上がる
#   beans : 地球から月まで枝豆が並んでいき、本数が上がる
#   hole  : 地球の断面のトンネルをずんだもんが落ちていき、経過時間が上がる
#   dash  : コースをずんだもんが一瞬で走り抜け、時間が出る
#   fate  : ずんだもんがひどい目にあう（roast 焼き枝豆／squash ぺしゃんこ／stretch ずんだ麺／fade 赤くなって消える）
#   bh    : ブラックホールに向かってずんだもんが落ちていく
#   left  : 地球が去っていき、ずんだもんだけ宇宙に取り残される（タイムマシン）
#   fate faint : 宇宙空間でゆっくり回りながら気を失う
#   fate freeze / fossil : 凍る／化石になる
#   moongone : 夜空の月がぽんと消え、見上げるずんだもんが取り残される
import math
from PIL import Image, ImageDraw, ImageFont

TYPES = ("globe", "orbit", "beans", "hole", "dash", "fate", "bh", "left", "moongone")

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
_fc = {}
YEL, WHT, BLK, RED = (255, 226, 0), (255, 255, 255), (0, 0, 0), (230, 40, 40)
OCEAN, LAND, LAND2 = (40, 110, 200), (90, 180, 90), (60, 140, 70)
# 大陸のかたまり（経度, 緯度, 横幅, 縦幅）：ざっくりした見た目用
CONT = [(-100, 45, 50, 30), (-60, -15, 25, 35), (20, 50, 40, 20), (20, 5, 30, 35), (90, 45, 60, 25),
        (135, -25, 25, 15), (-40, 72, 18, 10), (100, 15, 20, 15)]


def font(size):
    size = max(8, int(size))
    if size not in _fc:
        _fc[size] = ImageFont.truetype(FONT, size, index=0)
    return _fc[size]


def ease(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def back(x):
    x = min(max(x, 0), 1)
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def txt(d, x, y, s, size, fg=YEL, stroke=10, anchor="mm"):
    d.text((x, y), s, font=font(size), fill=fg, stroke_width=stroke, stroke_fill=BLK, anchor=anchor)


def earth(base, cx, cy, r, rot):
    """横から見た地球（rot: 自転の角度・度）。大陸は手前の面だけ描く"""
    lay = Image.new("RGBA", (2 * r + 20, 2 * r + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    o = r + 10
    d.ellipse([o - r, o - r, o + r, o + r], fill=OCEAN + (255,))
    for lon, lat, wl, hl in CONT:
        a = math.radians(lon + rot)
        if math.cos(a) < 0.05:
            continue
        x = o + r * math.sin(a) * math.cos(math.radians(lat))
        y = o - r * math.sin(math.radians(lat))
        w = r * math.radians(wl) * math.cos(a) * 0.9
        h = r * math.radians(hl) * 0.9
        for ox, oy, sc in ((0, 0, 1.0), (0.5, -0.4, 0.6), (-0.45, 0.5, 0.55), (0.3, 0.6, 0.45)):
            ww, hh = w * sc, h * sc
            d.ellipse([x + ox * w - ww, y + oy * h - hh, x + ox * w + ww, y + oy * h + hh], fill=LAND + (255,))
        d.ellipse([x - w * 0.25, y - h * 0.2, x + w * 0.15, y + h * 0.25], fill=LAND2 + (255,))
    mask = Image.new("L", lay.size, 0)
    ImageDraw.Draw(mask).ellipse([o - r, o - r, o + r, o + r], fill=255)
    sh = Image.new("RGBA", lay.size, (0, 0, 40, 0))       # 右下に影
    sd = ImageDraw.Draw(sh)
    for k in range(12):
        sd.ellipse([o - r + r * 0.5 + k * 6, o - r + r * 0.3 + k * 5, o + r + r * 0.9, o + r + r * 0.9], fill=(0, 0, 40, 10))
    lay = Image.alpha_composite(lay, sh)
    lay.putalpha(Image.composite(lay.getchannel("A"), Image.new("L", lay.size, 0), mask))
    ImageDraw.Draw(lay).ellipse([o - r, o - r, o + r, o + r], outline=(10, 30, 70, 255), width=8)
    base.paste(lay, (int(cx - o), int(cy - o)), lay)


def moon(base, cx, cy, r):
    d = ImageDraw.Draw(base)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(225, 225, 215), outline=(60, 60, 70), width=6)
    for dx, dy, rr in ((-0.3, -0.2, 0.22), (0.25, 0.1, 0.16), (-0.05, 0.4, 0.12), (0.35, -0.35, 0.1)):
        d.ellipse([cx + dx * r - rr * r, cy + dy * r - rr * r, cx + dx * r + rr * r, cy + dy * r + rr * r], fill=(190, 190, 180))


def bean(d, x, y, ang, s=1.0):
    """枝豆のさや1本"""
    ca, sa = math.cos(ang), math.sin(ang)
    for k in (-1, 0, 1):
        px, py = x + ca * k * 9 * s, y + sa * k * 9 * s
        d.ellipse([px - 7 * s, py - 7 * s, px + 7 * s, py + 7 * s], fill=(120, 190, 60), outline=(40, 90, 30), width=max(1, int(2 * s)))


def tint(c, col, a):
    """キャラ画像を col の色に a(0〜1) だけ寄せる（透明部分はそのまま）"""
    rgb = Image.blend(c.convert("RGB"), Image.new("RGB", c.size, col), max(0.0, min(1.0, a)))
    rgb.putalpha(c.getchannel("A"))
    return rgb


def fade(c, a):
    c = c.copy()
    c.putalpha(c.getchannel("A").point(lambda v: int(v * max(0.0, min(1.0, a)))))
    return c


def blackhole(d, cx, cy, r, u):
    """降着円盤つきのブラックホール（横から見た図）"""
    for q in range(6, 0, -1):                       # 外側ほど暗い光の輪
        rr = r * (1 + q * 0.35)
        col = (255, 120 + q * 15, 20 + q * 10)
        d.ellipse([cx - rr, cy - rr * 0.22, cx + rr, cy + rr * 0.22], outline=col, width=10)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BLK, outline=(255, 200, 80), width=6)
    for q in range(5):                               # 吸い込まれる線
        a = u * 2.5 + q * 1.26
        x0, y0 = cx + math.cos(a) * r * 2.6, cy + math.sin(a) * r * 1.6
        d.line([(x0, y0), (cx + math.cos(a) * r * 1.2, cy + math.sin(a) * r * 1.05)], fill=WHT, width=4)


def stars(d, W, OY, PH):
    for q in range(60):
        x = (q * 397) % W
        y = OY + (q * 631) % PH
        r = 2 + q % 3
        d.ellipse([x - r, y - r, x + r, y + r], fill=WHT)


def counter(d, W, OY, PH, val, unit, label, y=0.86, size=120, x=None):
    x = W // 2 if x is None else x
    if label:
        txt(d, x, OY + int(PH * (y - 0.1)), label, 54, WHT, 7)
    txt(d, x, OY + int(PH * y), val + unit, size, YEL, 12)


def fmt(v, to):
    return f"{int(round(v)):,}" if to >= 10 else f"{v:.1f}".rstrip("0").rstrip(".")


def draw(pan, OY, PH, u, dur, fx, char=None):
    W = pan.width
    k = fx["type"]
    d = ImageDraw.Draw(pan)
    if k == "globe":
        cx, cy, r = W // 2, OY + int(PH * 0.47), int(PH * 0.3)
        stop = fx.get("stop", 0.6)                  # この秒で急に止まる
        rot = u * 160 if u < stop else stop * 160
        if u >= stop:                               # 止まった瞬間に少し揺れる
            cx += int(14 * math.sin((u - stop) * 60) * math.exp(-(u - stop) * 6))
        earth(pan, cx, cy, r, rot)
        if u < stop:                                # 回っている矢印
            d.arc([cx - r - 40, cy - r - 40, cx + r + 40, cy + r + 40], 200, 330, fill=WHT, width=12)
            ax, ay = cx + (r + 40) * math.cos(math.radians(330)), cy + (r + 40) * math.sin(math.radians(330))
            d.polygon([(ax + 30, ay + 10), (ax - 20, ay - 30), (ax - 18, ay + 22)], fill=WHT)
            txt(d, W // 2, OY + int(PH * 0.08), fx.get("spin_label", "回ってる"), 70, WHT, 8)
        else:                                       # 東（右）へ吹っ飛ぶ
            p = (u - stop)
            txt(d, W // 2, OY + int(PH * 0.08), fx.get("stop_label", "急停止"), 90, RED, 10)
            for j, (sy, kind) in enumerate(((-0.55, "house"), (-0.1, "char"), (0.3, "house"), (0.65, "tree"))):
                x0 = cx + r * math.sqrt(max(0, 1 - sy * sy)) - 30
                x = x0 + p * (360 + j * 70)
                y = cy + sy * r - p * 120 * (j - 1.5)
                for q in range(1, 6):                # 動きの線
                    d.line([(x - q * 60, y + (q % 2) * 20 - 10), (x - q * 60 - 50, y + (q % 2) * 20 - 10)], fill=WHT, width=6)
                if kind == "char" and char is not None:
                    c = char.resize((char.width * 4 // 5, char.height * 4 // 5)).rotate(-p * 540, expand=True)
                    pan.paste(c, (int(x - c.width / 2), int(y - c.height / 2)), c)
                elif kind == "house":
                    d.rectangle([x - 40, y - 20, x + 40, y + 40], fill=(240, 220, 180), outline=BLK, width=4)
                    d.polygon([(x - 52, y - 20), (x, y - 62), (x + 52, y - 20)], fill=RED, outline=BLK)
                else:
                    d.rectangle([x - 8, y, x + 8, y + 50], fill=(120, 80, 40))
                    d.ellipse([x - 40, y - 60, x + 40, y + 10], fill=LAND2, outline=BLK, width=4)
    elif k == "orbit":
        cx, cy, r = W // 2, OY + int(PH * 0.42), int(PH * 0.26)
        earth(pan, cx, cy, r, u * 20)
        R = r + 70
        laps = fx.get("to", 7.5) * ease(u / max(0.6, dur * 0.8))
        ang = laps * 2 * math.pi - math.pi / 2
        for q in range(40):                         # 光の尾
            a = ang - q * 0.07
            x, y = cx + R * math.cos(a), cy + R * 0.38 * math.sin(a)
            w = max(2, 22 - q // 2)
            d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=(255, 255, 160 + min(95, q * 3)))
        x, y = cx + R * math.cos(ang), cy + R * 0.38 * math.sin(ang)
        if char is not None:
            c = char.resize((char.width * 3 // 4, char.height * 3 // 4))
            pan.paste(c, (int(x - c.width / 2), int(y - c.height * 0.8)), c)
        counter(d, W, OY, PH, fmt(laps, fx.get("to", 7.5)), fx.get("unit", "周"), fx.get("label", ""))
    elif k == "beans":
        ex, ey, er = int(W * 0.2), OY + int(PH * 0.78), int(PH * 0.15)
        mx, my, mr = int(W * 0.82), OY + int(PH * 0.2), int(PH * 0.08)
        earth(pan, ex, ey, er, 30)
        moon(pan, mx, my, mr)
        p = ease(u / max(0.6, dur * 0.8))
        sx, sy = ex + er * 0.7, ey - er * 0.7
        tx, ty = mx - mr * 0.7, my + mr * 0.7
        ang = math.atan2(ty - sy, tx - sx)
        L = math.hypot(tx - sx, ty - sy)
        n = int(L / 26)
        for i in range(int(n * p)):
            bean(d, sx + math.cos(ang) * i * 26, sy + math.sin(ang) * i * 26, ang, 0.9)
        if p >= 1:
            txt(d, (sx + tx) // 2 + 80, (sy + ty) // 2 + 40, "到着", 80, RED, 9)
        counter(d, W, OY, PH, fmt(fx.get("to", 77) * p, fx.get("to", 77)), fx.get("unit", "億本"), fx.get("label", ""), y=0.24, size=130, x=int(W * 0.33))
    elif k == "hole":
        cx, cy, r = W // 2, OY + int(PH * 0.5), int(PH * 0.42)
        for rr, col in ((1.0, (90, 160, 80)), (0.97, (200, 110, 50)), (0.55, (240, 160, 40)), (0.2, (255, 230, 120))):
            d.ellipse([cx - r * rr, cy - r * rr, cx + r * rr, cy + r * rr], fill=col, outline=BLK, width=4)
        d.rectangle([cx - 26, cy - r - 10, cx + 26, cy + r + 10], fill=(30, 20, 20))
        p = ease(u / max(0.6, dur * 0.85)) if fx.get("ease", True) else min(1, u / max(0.6, dur * 0.85))
        y = cy - r + 2 * r * (0.5 - 0.5 * math.cos(math.pi * min(1, u / max(0.6, dur * 0.85))))   # 真ん中で一番速い
        if char is not None:
            c = char.resize((char.width * 3 // 5, char.height * 3 // 5))
            if fx.get("heat"):                      # 深いほど焦げる
                c = tint(c, (120, 60, 15), 0.7 * min(1, (y - (cy - r)) / r))
            c = c.rotate(u * 400, expand=True)
            pan.paste(c, (int(cx - c.width / 2), int(y - c.height / 2)), c)
        for lab, yy in (("日本", cy - r - 40), (fx.get("bottom", "地球の裏"), cy + r + 40)):
            txt(d, cx + 200, yy, lab, 52, WHT, 7)
        mins = fx.get("to", 38) * min(1, u / max(0.6, dur * 0.85))
        txt(d, cx - 300, cy, f"{int(mins)}分", 110, YEL, 12)
    elif k == "dash":
        y = OY + int(PH * 0.55)
        d.rectangle([40, y + 50, W - 40, y + 70], fill=WHT)
        txt(d, 90, y + 120, "スタート", 44, WHT, 6)
        txt(d, W - 110, y + 120, "ゴール", 44, WHT, 6)
        p = min(1, u / 0.12)                       # ほぼ一瞬
        x = 80 + (W - 160) * p
        if 0 < p < 1 or u < 0.3:
            for q in range(0, int(x) - 80, 30):
                d.line([(80 + q, y - 20 + (q // 30 % 3) * 20), (80 + q + 20, y - 20 + (q // 30 % 3) * 20)], fill=YEL, width=6)
        if char is not None:
            c = char.resize((char.width * 7 // 10, char.height * 7 // 10))
            pan.paste(c, (int(x - c.width / 2), y + 50 - c.height), c)
        if u > 0.2:
            txt(d, W // 2, OY + int(PH * 0.2), fx.get("time", ""), 130, YEL, 12)
            txt(d, W // 2, OY + int(PH * 0.33), fx.get("label", ""), 60, WHT, 8)
    elif k == "fate":
        mode = fx.get("mode", "roast")
        p = ease(u / max(0.5, dur * fx.get("speed", 0.7)))
        cx, cy = W // 2, OY + int(PH * 0.5)
        if char is not None:
            h0 = min(char.height * 3 // 2, int(PH * fx.get("hmax", 0.5)))   # 画面の高さに収める
            c = char.resize((max(1, char.width * h0 // char.height), h0))
            if mode == "roast":                      # だんだん焦げ色に、炎と湯気
                c = tint(c, (120, 60, 15), 0.62 * p)
                for q in range(9):
                    fx_ = cx - 300 + q * 75
                    h = 160 + 110 * abs(math.sin(u * 9 + q))
                    base_y = cy + c.height // 2 - 10
                    d.polygon([(fx_ - 46, base_y), (fx_ + 46, base_y), (fx_, base_y - h)], fill=(255, 120 + (q % 3) * 40, 0))
                    d.polygon([(fx_ - 16, base_y), (fx_ + 16, base_y), (fx_, base_y - h * 0.55)], fill=YEL)
                pan.paste(c, (int(cx - c.width / 2), int(cy - c.height / 2 + math.sin(u * 30) * 4)), c)
                if p > 0.3:
                    for q in range(3):               # 湯気
                        x = cx - 120 + q * 120
                        y = cy - c.height // 2 - 40 - (u * 120 + q * 40) % 140
                        d.arc([x - 30, y - 30, x + 30, y + 30], 200, 340, fill=WHT, width=8)
            elif mode == "squash":                   # 上からつぶされてぺしゃんこ
                sy = 1 - 0.72 * p
                sx = 1 + 0.6 * p
                c = c.resize((max(1, int(c.width * sx)), max(1, int(c.height * sy))))
                floor = cy + int(PH * 0.18)
                d.rectangle([0, floor, W, floor + 16], fill=WHT)
                top = floor - c.height
                d.rectangle([cx - 340, OY, cx + 340, top], fill=(110, 110, 125), outline=BLK, width=6)
                txt(d, cx, max(OY + 80, top - 90), fx.get("weight", ""), 90, WHT, 10)
                pan.paste(c, (int(cx - c.width / 2), top), c)
            elif mode == "stretch":                  # 縦にびよーん
                bcy = OY + int(PH * 0.86)
                blackhole(d, cx, bcy, int(PH * 0.09), u)
                sy = 1 + (PH * 0.8 / c.height - 1) * p      # 上端まで伸びて切れないように
                sx = 1 - 0.68 * p
                c = c.resize((max(1, int(c.width * sx)), max(1, int(c.height * sy))))
                c = tint(c, (255, 200, 120), 0.2 * p)
                pan.paste(c, (int(cx - c.width / 2), bcy - c.height + int(PH * 0.03 * p)), c)
            elif mode == "faint":                    # 宇宙でゆっくり回って気を失う
                stars(d, W, OY, PH)
                c = tint(c.resize((c.width * 3 // 4, c.height * 3 // 4)), (60, 90, 200), 0.35 * p).rotate(u * 25, expand=True)
                pan.paste(c, (int(cx - c.width / 2), int(cy - c.height / 2 + math.sin(u * 2) * 20)), c)
                if p > 0.4:
                    for q in range(3):
                        txt(d, cx + 150 + q * 50, cy - 260 - q * 50 - (u * 40) % 30, "z", 60 + q * 15, WHT, 6)
            elif mode == "freeze":                   # だんだん青白くなり、氷の結晶がつく
                c = tint(c, (170, 220, 255), 0.6 * p)
                pan.paste(c, (int(cx - c.width / 2 + (math.sin(u * 50) * 6 if p < 0.8 else 0)), int(cy - c.height / 2)), c)
                for q in range(int(14 * p)):
                    x = cx - c.width // 2 + (q * 173) % c.width
                    y = cy - c.height // 2 + (q * 251) % c.height
                    for a in range(3):
                        dx, dy = 26 * math.cos(a * math.pi / 3), 26 * math.sin(a * math.pi / 3)
                        d.line([(x - dx, y - dy), (x + dx, y + dy)], fill=(230, 245, 255), width=6)
                for q in range(20):                  # 雪
                    x = (q * 211 + u * 60) % W
                    y = OY + (q * 137 + u * 220) % PH
                    d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=WHT)
            elif mode == "fossil":                   # 灰色の石になり、ひびが入る
                g = c.convert("L").convert("RGB")
                g = Image.blend(c.convert("RGB"), g, min(1, p * 1.3))
                g = Image.blend(g, Image.new("RGB", c.size, (150, 140, 120)), 0.35 * p)
                g.putalpha(c.getchannel("A"))
                pan.paste(g, (int(cx - c.width / 2), int(cy - c.height / 2)), g)
                if p > 0.6:
                    x0, y0 = cx - 60, cy - c.height // 2 + 80
                    pts = [(x0, y0), (x0 + 40, y0 + 90), (x0 - 10, y0 + 170), (x0 + 50, y0 + 280), (x0 + 10, y0 + 380)]
                    d.line(pts, fill=(60, 50, 40), width=7)
                d.rectangle([0, cy + c.height // 2 - 20, W, OY + PH], fill=(120, 95, 70))
            elif mode == "fade":                     # 外から見ると、赤くなって止まって消える
                blackhole(d, cx, OY + int(PH * 0.74), int(PH * 0.11), u * 0.3)
                slow = 1 - (1 - min(1, u / max(1.5, dur * 0.9))) ** 3
                c = c.resize((c.width * 2 // 3, c.height * 2 // 3))
                c = fade(tint(c, (200, 0, 0), 0.8 * slow), 1 - 0.92 * slow)
                y = OY + int(PH * 0.3) + int(PH * 0.22 * slow)
                pan.paste(c, (int(cx - c.width / 2), y), c)
        lab = fx.get("label", "")
        if lab and p > 0.55:
            s_ = back(min(1, (p - 0.55) / 0.3))
            ly = fx.get("label_y", 0.1 if mode in ("stretch", "fade") else 0.86)
            txt(d, cx, OY + int(PH * ly), lab, int(150 * max(0.3, s_)), RED, 14)
    elif k == "bh":                                  # 遠くからブラックホールへ落ちていく
        cx, cy, r = W // 2, OY + int(PH * 0.6), int(PH * 0.13)
        blackhole(d, cx, cy, r, u)
        p = ease(u / max(0.5, dur * 0.85))
        if char is not None:
            sc = 0.8 - 0.35 * p
            c = char.resize((max(1, int(char.width * sc)), max(1, int(char.height * sc * (1 + 0.8 * p))))).rotate(u * 90, expand=True)
            x = cx - W * 0.35 * (1 - p)
            y = OY + PH * 0.12 + (cy - r * 1.6 - OY - PH * 0.12) * p
            pan.paste(c, (int(x - c.width / 2), int(y - c.height / 2)), c)
        if fx.get("label"):
            txt(d, W // 2, OY + int(PH * 0.08), fx["label"], 70, WHT, 8)
    elif k == "left":                               # 地球が去っていき、ずんだもんだけ取り残される
        stars(d, W, OY, PH)
        p = ease(u / max(0.5, dur * 0.8))
        r = int(PH * 0.2 * (1 - 0.7 * p))
        ex = W // 2 + int(W * 0.38 * p)
        ey = OY + int(PH * 0.55) - int(PH * 0.15 * p)
        earth(pan, ex, ey, max(10, r), u * 30)
        if p > 0.05:
            for q in range(1, 6):
                d.line([(ex - r - q * 50, ey + (q % 2) * 24 - 12), (ex - r - q * 50 - 34, ey + (q % 2) * 24 - 12)], fill=WHT, width=6)
        if char is not None:
            c = char.resize((char.width * 9 // 10, char.height * 9 // 10)).rotate(math.sin(u * 2) * 12, expand=True)
            pan.paste(c, (int(W * 0.3 - c.width / 2), int(OY + PH * 0.45 - c.height / 2)), c)
        if fx.get("label") and p > 0.5:
            txt(d, W // 2, OY + int(PH * 0.1), fx["label"], 110, RED, 12)
    elif k == "moongone":                           # 月がぽんと消える
        stars(d, W, OY, PH)
        gone = fx.get("gone", 0.5)
        mx, my, mr = int(W * 0.7), OY + int(PH * 0.22), int(PH * 0.1)
        if u < gone:
            moon(pan, mx, my, mr)
        else:
            q = min(1, (u - gone) / 0.35)
            for j in range(10):                     # ぽんと散る
                a = j * math.pi / 5
                rr = mr * (0.5 + 1.6 * q)
                x, y = mx + rr * math.cos(a), my + rr * math.sin(a)
                w = max(2, int(22 * (1 - q)))
                d.ellipse([x - w, y - w, x + w, y + w], fill=(225, 225, 215))
            if q >= 1:
                txt(d, mx, my, "？", 160, WHT, 10)
        d.rectangle([0, OY + int(PH * 0.82), W, OY + PH], fill=(30, 40, 30))
        if char is not None:
            c = char.resize((char.width * 9 // 10, char.height * 9 // 10))
            pan.paste(c, (int(W * 0.3 - c.width / 2), OY + int(PH * 0.82) - c.height), c)
        if fx.get("label") and u > gone + 0.3:
            txt(d, W // 2, OY + int(PH * 0.42), fx["label"], 110, RED, 12)
