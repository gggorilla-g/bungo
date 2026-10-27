# nazo/mapfx.py — 地図・湖・看板のモーショングラフィックス（雑学ショートの「写真がない場所」用）
#   地図の元データ：Natural Earth（パブリックドメイン）の州境を間引いたもの（nazo/canada_provinces.json）
import json, math, os
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
_fc, _prov = {}, None


def font(size):
    size = max(8, int(size))
    if size not in _fc:
        _fc[size] = ImageFont.truetype(FONT, size, index=0)
    return _fc[size]


def _ease(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def _back(x):
    x = min(max(x, 0), 1)
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def provinces():
    global _prov
    if _prov is None:
        _prov = json.load(open(os.path.join(os.path.dirname(__file__), "canada_provinces.json"), encoding="utf-8"))
    return _prov


def draw_map(pan, OY, PH, u, spec):
    """カナダの地図。州を光らせ、ピンを落とし、州名の札を出す。
    spec: {province, pin:[lat,lon]（任意）, label}"""
    W = pan.width
    k = math.cos(math.radians(58))
    lon0, lon1, lat0, lat1 = -142, -51, 41, 84
    zoom = 1.0 + 0.08 * _ease(u / 1.2)
    sx = min((W - 60) / ((lon1 - lon0) * k), PH * 0.78 / (lat1 - lat0)) * zoom
    ox = W / 2 - ((lon0 + lon1) / 2 - lon0) * k * sx
    oy = OY + PH * 0.58 - (lat1 - lat0) * sx / 2
    ImageDraw.Draw(pan).rectangle([0, OY, W, OY + PH], fill=(170, 215, 240))   # 海

    def P(lon, lat):
        return (ox + (lon - lon0) * k * sx, oy + (lat1 - lat) * sx)

    lay = Image.new("RGBA", pan.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    hit = spec.get("province")
    flash = 0.5 + 0.5 * math.sin(u * 10) if 0.3 < u < 1.0 else 1.0
    for p in provinces():
        on = p["name"] == hit and u > 0.3
        fill = (255, int(150 + 76 * flash), 0, 255) if on else (245, 240, 230, 255)
        for r in p["rings"]:
            pts = [P(x, y) for x, y in r]
            if len(pts) > 2:
                d.polygon(pts, fill=fill, outline=(40, 40, 50, 255))
    pan.paste(lay, (0, 0), lay)
    d = ImageDraw.Draw(pan)
    if spec.get("pin") and u > 0.6:                    # ピンが上から落ちる
        lat, lon = spec["pin"]
        x, y = P(lon, lat)
        e = _back((u - 0.6) / 0.3)
        y0 = y - 300 * (1 - e)
        d.ellipse([x - 26, y0 - 86, x + 26, y0 - 34], fill=(230, 40, 40), outline=(0, 0, 0), width=5)
        d.polygon([(x - 20, y0 - 50), (x + 20, y0 - 50), (x, y0)], fill=(230, 40, 40), outline=(0, 0, 0))
        d.ellipse([x - 9, y0 - 69, x + 9, y0 - 51], fill=(255, 255, 255))
    if spec.get("label") and u > 0.45:                 # 州名の札
        e = _back((u - 0.45) / 0.25)
        f = font(int(70 * e) or 1)
        tx, ty = W // 2, OY + int(PH * 0.12)
        bb = d.textbbox((tx, ty), spec["label"], font=f, anchor="mm")
        d.rectangle([bb[0] - 24, bb[1] - 14, bb[2] + 24, bb[3] + 14], fill=(0, 0, 0))
        d.text((tx, ty), spec["label"], font=f, fill=(255, 226, 0), anchor="mm")


def _lake(d, cx, cy, rx, ry, u, seed=3):
    """湖（ゆらぐ輪郭＋さざ波）"""
    pts = []
    for i in range(48):
        a = i / 48 * 2 * math.pi
        n = 1 + 0.08 * math.sin(a * 3 + seed) + 0.05 * math.sin(a * 5 + seed * 2)
        pts.append((cx + rx * n * math.cos(a), cy + ry * n * math.sin(a)))
    d.polygon(pts, fill=(60, 140, 210), outline=(20, 60, 110), width=8)
    for j in range(3):                                   # さざ波
        y = cy - ry * 0.3 + j * ry * 0.3
        off = (u * 60 + j * 40) % 80
        for x in range(int(cx - rx * 0.6), int(cx + rx * 0.6), 80):
            d.arc([x + off - 30, y - 10, x + off + 30, y + 10], 200, 340, fill=(200, 230, 255), width=5)


def draw_sign(pan, OY, PH, u, spec):
    """湖のイラストの手前に、カナダの道路案内風の緑の看板が落ちてきて揺れる。
    spec: {text（英語名）, sub（日本語訳）}"""
    W = pan.width
    d = ImageDraw.Draw(pan)
    # 地面と湖
    d.rectangle([0, OY + int(PH * 0.62), W, OY + PH], fill=(90, 150, 70))
    _lake(d, W // 2, OY + int(PH * 0.8), int(W * 0.42), int(PH * 0.13), u)
    for x in (120, 960, 220, 860):                       # 針葉樹
        b = OY + int(PH * 0.66)
        d.polygon([(x, b - 220), (x - 60, b), (x + 60, b)], fill=(30, 90, 50), outline=(10, 40, 20))
    # 看板（上から落ちて、少し揺れて止まる）
    e = _back(u / 0.35)
    sw = min(940, 120 + 46 * len(spec["text"]))
    sh = 340 if spec.get("sub") else 200
    cx = W // 2
    top = OY + int(PH * 0.08) - int(500 * (1 - e))
    ang = 4 * math.sin(u * 9) * math.exp(-u * 2.5) if u > 0.35 else 0
    board = Image.new("RGBA", (sw + 40, sh + 260), (0, 0, 0, 0))
    bd = ImageDraw.Draw(board)
    for px in (sw * 0.25, sw * 0.75):                    # 支柱
        bd.rectangle([20 + px - 12, sh, 20 + px + 12, sh + 250], fill=(150, 150, 160), outline=(60, 60, 70), width=3)
    bd.rounded_rectangle([20, 0, 20 + sw, sh], 28, fill=(0, 112, 60), outline=(255, 255, 255), width=12)
    bd.rounded_rectangle([34, 14, 6 + sw, sh - 14], 20, outline=(255, 255, 255), width=4)
    fs = min(120, int((sw - 80) / max(1, len(spec["text"])) * 1.9))
    bd.text((20 + sw // 2, 110 if spec.get("sub") else sh // 2), spec["text"], font=font(fs), fill=(255, 255, 255), anchor="mm")
    if spec.get("sub") and u > 0.5:
        p = _back((u - 0.5) / 0.25)
        f2 = font(int(104 * p) or 1)
        bb = bd.textbbox((20 + sw // 2, 250), spec["sub"], font=f2, anchor="mm")
        bd.rectangle([bb[0] - 18, bb[1] - 8, bb[2] + 18, bb[3] + 8], fill=(255, 226, 0))
        bd.text((20 + sw // 2, 250), spec["sub"], font=f2, fill=(0, 0, 0), anchor="mm")
    if ang:
        board = board.rotate(ang, center=(board.width // 2, 0), resample=Image.BICUBIC)
    pan.paste(board, (cx - board.width // 2, top), board)


def draw_station(pan, OY, PH, u, spec):
    """駅のホームと、駅名標（白い板に大きな駅名、ふりがな、ローマ字、両どなりの駅）が落ちてきて揺れる。
    spec: {name（漢字）, kana, roma, left, right（となりの駅、任意）, line（線の色 [r,g,b]、任意）, sub（ツッコミの一言、任意）}"""
    W = pan.width
    d = ImageDraw.Draw(pan)
    # ホーム（床と黄色い点字ブロック、線路）
    fy = OY + int(PH * 0.7)
    d.rectangle([0, fy, W, OY + PH], fill=(150, 150, 150))
    d.rectangle([0, fy + 30, W, fy + 70], fill=(250, 210, 0))
    for x in range(0, W, 40):
        d.ellipse([x + 12, fy + 42, x + 26, fy + 56], fill=(220, 180, 0))
    d.rectangle([0, OY + int(PH * 0.9), W, OY + PH], fill=(90, 70, 60))
    for x in range(-40, W, 120):
        d.rectangle([x, OY + int(PH * 0.92), x + 70, OY + int(PH * 0.95)], fill=(60, 45, 40))
    # 駅名標
    e = _back(u / 0.35)
    bw, bh = 980, 420
    line = tuple(spec.get("line", (0, 140, 70)))
    top = OY + int(PH * 0.1) - int(560 * (1 - e))
    ang = 3 * math.sin(u * 9) * math.exp(-u * 2.5) if u > 0.35 else 0
    board = Image.new("RGBA", (bw + 40, bh + 300), (0, 0, 0, 0))
    bd = ImageDraw.Draw(board)
    for px in (bw * 0.2, bw * 0.8):                       # 支柱
        bd.rectangle([20 + px - 14, bh, 20 + px + 14, bh + 290], fill=(120, 120, 130), outline=(50, 50, 60), width=3)
    bd.rectangle([20, 0, 20 + bw, bh], fill=(255, 255, 255), outline=(40, 40, 40), width=8)
    cx = 20 + bw // 2
    if spec.get("kana"):
        bd.text((cx, 62), spec["kana"], font=font(54), fill=(30, 30, 30), anchor="mm")
    name = spec["name"]
    fs = min(200, int(820 / max(1, len(name))))
    bd.text((cx, 180), name, font=font(fs), fill=(0, 0, 0), anchor="mm")
    bd.rectangle([20, 278, 20 + bw, 318], fill=line)              # 線の色の帯
    if spec.get("roma"):
        bd.text((cx, 298), spec["roma"], font=font(30), fill=(255, 255, 255), anchor="mm")
    for side, txt_ in (("left", spec.get("left")), ("right", spec.get("right"))):
        if txt_:
            x = 70 if side == "left" else bw - 30
            bd.text((x, 368), ("← " + txt_) if side == "left" else (txt_ + " →"), font=font(40), fill=(30, 30, 30),
                    anchor="lm" if side == "left" else "rm")
    if spec.get("sub") and u > 0.5:
        p = _back((u - 0.5) / 0.25)
        fs2 = min(84, int((bw - 80) / max(1, len(spec["sub"]))))      # 板の幅に収める
        f2 = font(int(fs2 * p) or 1)
        bb = bd.textbbox((cx, bh + 64), spec["sub"], font=f2, anchor="mm")
        bd.rectangle([bb[0] - 18, bb[1] - 8, bb[2] + 18, bb[3] + 8], fill=(255, 226, 0), outline=(0, 0, 0), width=5)
        bd.text((cx, bh + 64), spec["sub"], font=f2, fill=(0, 0, 0), anchor="mm")
    if ang:
        board = board.rotate(ang, center=(board.width // 2, 0), resample=Image.BICUBIC)
    pan.paste(board, (W // 2 - board.width // 2, top), board)
