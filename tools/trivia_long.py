# tools/trivia_long.py — 雑学の長尺（横長1920x1080）を台本データから作る。tools/moso_long.py の雑学向け派生。
#   使い方: python tools/trivia_long.py nazo/trivia_long/names10.json output/trivia_long_names10.mp4 [--from 秒 --to 秒] [--jobs 2]
#   画面: 右に写真（入れ替わりで動く）、左下にずんだもん（口パク・まばたき）、下にテロップ（全セリフ）、
#         左上に「No.何 名前」、右上に10個の進み具合。ツッコミは顔のアップ（1秒）。
#   BGM は手元で書き出すので moso_long.py と同じ合成BGM（暗号化された曲は CI でしか使えない）。
#   メモリ切れで落ちたことがあるので、画像のためこみ（キャッシュ）にはすべて上限をつける。
import hashlib, json, math, os, re, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, "nazo"); sys.path.insert(0, "src"); sys.path.insert(0, "tools")
import theme, se                                      # noqa: E402

W, H, FPS, SR = 1920, 1080, 24, 44100
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FONT_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
PARTS = "assets/enc/parts"
JINGLE, JINGLE_VOICE = "assets/jingle_letsnotoke.wav", "assets/jingle_letsnotoke_voice.wav"
WHT, BLK, YEL, RED = (255, 255, 255), (0, 0, 0), (255, 214, 0), (226, 36, 44)
PX, PY, PW, PH = 600, 118, 1270, 730                  # 写真の枠
SUB_Y = 872                                           # テロップの帯の上端
ZH = 560                                              # 左下のずんだもんの高さ（胸から上の絵）
GAP, SEC_GAP, UPT = 0.26, 0.45, 1.0                   # セリフの間、章の間、アップの秒数
WORK = "build_trivia_long"
_fc = {}


def font(s, bold=False):
    k = (int(s), bold)
    if k not in _fc:
        if len(_fc) > 200:
            _fc.clear()
        _fc[k] = ImageFont.truetype(FONT_B if bold else FONT, max(8, int(s)), index=0)
    return _fc[k]


def ease(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def back(x, c=1.7):
    x = min(max(x, 0), 1)
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


# ── ずんだもん
_zc = {}


def zunda(face, h, mouth=1, blink=0, flip=False):
    for f in (face, "通常"):
        for b in ((blink, 0) if blink else (0,)):
            p = f"{PARTS}/{f}_{mouth}_{b}.png"
            k = (p, h, flip)
            if k not in _zc and len(_zc) > 90:
                _zc.clear()
            if k not in _zc and os.path.exists(p):
                im = Image.open(p).convert("RGBA")
                im = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
                _zc[k] = im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im
            if k in _zc:
                return _zc[k]
    raise FileNotFoundError(face)


SHAKE = {"泣き": 10, "青ざめ": 12, "焦り": 10, "驚き": 14, "怒り": 18}
DANCE = [("笑顔", False), ("指差し", False), ("ドヤ", True), ("指差し", True), ("笑顔", False), ("驚き", True)]
BEAT = 0.375


# ── 背景（半分の大きさで描いて引きのばす。1/12秒ごとに更新）
_bg = {}


def background(name, t):
    k = (name, int(t * 12))
    if k not in _bg:
        if len(_bg) > 6:
            _bg.clear()
        _bg[k] = theme.background(name, W // 2, H // 2, k[1] / 12).convert("RGB").resize((W, H), Image.BILINEAR)
    return _bg[k].copy()


# ── 写真
_ph = {}


def photo(path):
    if path not in _ph:
        if len(_ph) > 10:
            _ph.pop(next(iter(_ph)))
        im = Image.open(path).convert("RGB")
        s = min(1.0, 1700 / max(im.width, im.height))
        _ph[path] = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS) if s < 1 else im
    return _ph[path]


def cover(src, cx, cy, z, w, h):
    s = max(w / src.width, h / src.height) * z
    cw, ch = w / s, h / s
    x0 = min(max(cx * src.width - cw / 2, 0), max(src.width - cw, 0))
    y0 = min(max(cy * src.height - ch / 2, 0), max(src.height - ch, 0))
    return src.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.BILINEAR)


def panel(img, th, path, mode, k, z, appear, tt):
    """写真を枠の中に置く。mode: contain（全体を縁つきで）/ cover（寄ってゆっくり動く）。appear: 出てからの秒"""
    src = photo(path)
    if z:                                                 # 台本で寄りを指定
        cx, cy, z0, z1 = z
        pim = cover(src, cx, cy, z0 + (z1 - z0) * ease(k), PW, PH)
    elif mode == "cover":
        import zlib
        d = 1 if (zlib.crc32(path.encode()) % 2) else -1
        pim = cover(src, 0.5 + 0.08 * d * (k - 0.5), 0.5, 1.06 + 0.1 * k, PW, PH)
    else:
        s = min(PW * 0.94 / src.width, PH * 0.94 / src.height) * (1.0 + 0.05 * k)
        im = src.resize((max(1, int(src.width * s)), max(1, int(src.height * s))), Image.BILINEAR)
        pim = None
    lay = Image.new("RGBA", (PW + 40, PH + 40), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    if pim is not None:
        ld.rectangle([18, 18, PW + 18, PH + 18], fill=th["side"] + (255,))
        ld.rectangle([0, 0, PW + 8, PH + 8], fill=th["edge"] + (255,))
        lay.paste(pim, (4, 4))
        ox, oy = PX - 4, PY - 4
    else:
        x0, y0 = (PW - im.width) // 2, (PH - im.height) // 2
        ld.rectangle([x0 + 14, y0 + 14, x0 + im.width + 22, y0 + im.height + 22], fill=th["side"] + (255,))
        ld.rectangle([x0 - 8, y0 - 8, x0 + im.width + 8, y0 + im.height + 8], fill=th["edge"] + (255,))
        lay.paste(im, (x0, y0))
        ox, oy = PX, PY
    if appear < 0.32:                                     # 写真が替わった瞬間：少し小さく横から入ってポンと止まる
        p = back(appear / 0.32)
        sc = 0.86 + 0.14 * p
        lay = lay.resize((max(1, int(lay.width * sc)), max(1, int(lay.height * sc))), Image.BILINEAR)
        ox += int((PW - lay.width + 40) / 2 + (1 - min(1, p)) * 120)
        oy += int((PH - lay.height + 40) / 2)
        lay = lay.rotate(-3 * (1 - min(1, p)), expand=True, resample=Image.BILINEAR)
    img.alpha_composite(lay, (ox, oy))


# ── テロップ・見出し
def wrap(text, n=24):
    if len(text) <= n:
        return [text]
    best = None
    for i in range(len(text) * 3 // 10, len(text) * 7 // 10 + 2):
        if 0 < i < len(text) and text[i - 1] in "、。？！…」":
            if best is None or abs(i - len(text) / 2) < abs(best - len(text) / 2):
                best = i
    if best is None:
        best = (len(text) + 1) // 2
    return [text[:best], text[best:]]


def subtitle(img, text):
    band = Image.new("RGBA", (W, H - SUB_Y), (0, 0, 0, 185))
    img.alpha_composite(band, (0, SUB_Y))
    d = ImageDraw.Draw(img)
    lines = wrap(text)
    if len(lines) > 2:
        lines = [lines[0], "".join(lines[1:])]
    fs = 66 if max(len(l) for l in lines) <= 24 else int(66 * 24 / max(len(l) for l in lines))
    for i, l in enumerate(lines):
        y = SUB_Y + (H - SUB_Y) / 2 + (i - (len(lines) - 1) / 2) * (fs + 16)
        d.text((W // 2 + 120, y), l, font=font(fs), fill=WHT, anchor="mm", stroke_width=7, stroke_fill=BLK)
    d.text((W - 16, H - 10), "VOICEVOX:ずんだもん", font=font(20, True), fill=(190, 190, 190), anchor="rd")


def box(d, x, y, text, f, fg, bg, padx=22, pady=10):
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    w, h = r - l + padx * 2, b - t + pady * 2
    d.rectangle([x, y, x + w, y + h], fill=bg, outline=BLK, width=4)
    d.text((x + padx - l, y + pady - t), text, font=f, fill=fg)
    return w, h


def header(img, no, name, cur, n_all):
    d = ImageDraw.Draw(img)
    w, h = box(d, 34, 26, f"No.{no}", font(56), WHT, RED)
    box(d, 34 + w + 10, 26, name, font(56), BLK, YEL)
    gx = W - 40 - n_all * 52                              # いま何種目か（最後まで見たくなるように）
    for q in range(n_all):
        on = q < cur
        d.rounded_rectangle([gx + q * 52, 44, gx + q * 52 + 40, 64], 8, fill=YEL if on else WHT, outline=BLK, width=3)


def stamp(img, f, u, th):
    s = 1.6 - 0.6 * back(u / 0.25)
    t2 = dict(th)
    if f.get("color"):
        t2["face"] = tuple(f["color"]); t2["edge"] = BLK; t2["side"] = (40, 40, 40)
    else:
        t2["face"] = WHT; t2["edge"] = BLK; t2["side"] = th["side"]
    sh = int(12 * math.sin(u * 80)) if u < 0.3 else 0
    theme.extrude_text(img, int(PX + PW * f.get("x", 0.5)) + sh, int(PY + PH * f.get("y", 0.5)), f["text"], f.get("size", 150) * s,
                       t2, angle=f.get("tilt", 5))


def count(img, f, u):
    p = ease(u / 0.9)
    v = f["to"] * p
    dec = f.get("dec", 0)
    txt = (f"{v:.{dec}f}" if dec else f"{int(round(v)):,}") + f["unit"]
    lay = Image.new("RGBA", (880, 330), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, 879, 329], 28, fill=(10, 12, 30, 225), outline=YEL, width=6)
    d.text((440, 70), f["label"], font=font(40, True), fill=WHT, anchor="mm")
    fs = 150 if len(txt) <= 6 else int(150 * 6 / len(txt)) + 20
    d.text((440, 205), txt, font=font(fs), fill=YEL, anchor="mm", stroke_width=8, stroke_fill=BLK)
    sc = back(min(1, u / 0.25))
    if sc < 1:
        lay = lay.resize((max(1, int(lay.width * sc)), max(1, int(lay.height * sc))))
    img.alpha_composite(lay, (int(PX + PW / 2 - lay.width / 2), int(PY + PH * 0.55 - lay.height / 2)))


def bars(img, f, u):
    items = f["items"]
    w0 = 1040
    lay = Image.new("RGBA", (w0, 110 + 120 * len(items)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, w0 - 1, lay.height - 1], 24, fill=(250, 250, 245, 240), outline=BLK, width=5)
    mx = max(v for _, v, _ in items)
    lw = max(font(38).getbbox(lab)[2] for lab, _, _ in items) + 60
    for i, (lab, v, col) in enumerate(items):
        y = 60 + i * 120
        d.text((30, y + 28), lab, font=font(38), fill=BLK, anchor="lm")
        p = ease((u - i * 0.3) / 0.8)
        bw = int((w0 - lw - 200) * max(0.01, v / mx) * p)
        d.rounded_rectangle([lw, y, lw + max(8, bw), y + 56], 10, fill=tuple(col), outline=BLK, width=3)
        val = v * p
        txt = f"{val:.2f}".rstrip("0").rstrip(".") if v < 10 and v != int(v) else f"{int(round(val)):,}"
        d.text((lw + max(8, bw) + 16, y + 28), txt, font=font(40), fill=BLK, anchor="lm")
    d.text((w0 - 26, lay.height - 24), f["unit"], font=font(28, True), fill=(80, 80, 80), anchor="rm")
    img.alpha_composite(lay, (int(PX + PW / 2 - w0 / 2), int(PY + PH - lay.height - 30)))


def thermo(img, f, u):
    d = ImageDraw.Draw(img)
    x, y0, y1 = PX + PW - 170, PY + 90, PY + PH - 150
    d.rounded_rectangle([x - 34, y0 - 10, x + 34, y1 + 30], 34, fill=WHT, outline=BLK, width=6)
    d.ellipse([x - 70, y1 - 20, x + 70, y1 + 120], fill=RED, outline=BLK, width=6)
    p = ease(u / 1.2)
    top = y1 - (y1 - y0 - 20) * p
    d.rectangle([x - 18, top, x + 18, y1 + 30], fill=RED)
    d.text((x - 110, top), f"{int(round(f['to'] * p))}℃", font=font(110), fill=YEL, anchor="rm", stroke_width=8, stroke_fill=BLK)
    if p > 0.95:
        d.text((x - 110, top + 110), "以上", font=font(60), fill=WHT, anchor="rm", stroke_width=6, stroke_fill=BLK)


def spray(img, f, u, tt):
    d = ImageDraw.Draw(img, "RGBA")
    bx, by = PX + PW * 0.30, PY + PH * 0.62
    for q in range(14):                                   # お尻から白いガスがぷしゅーっと広がる
        a = (q * 0.37 + u * 2) % 1.0
        ang = (math.radians(200 + (q % 5) * 8) if not f.get("aim") else math.radians(200 + 140 * (int(u / 0.8) % 2) + (q % 5) * 8))
        r = 20 + 300 * a
        cx, cy = bx + math.cos(ang) * r, by + math.sin(ang) * r * 0.6
        rr = 18 + 60 * a
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(250, 250, 235, int(170 * (1 - a))))
    if int(u * 3) % 2 == 0:
        d.text((bx - 120, by - 170), "ぷしゅー", font=font(80), fill=YEL, anchor="mm", stroke_width=7, stroke_fill=BLK)


def pit(img, f, u, tt):
    """アリジゴクの巣の断面：すり鉢の斜面を砂がすべり、アリが底へ落ちる"""
    cw, chh = 620, 380
    lay = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, cw - 1, chh - 1], 24, fill=(255, 248, 230, 240), outline=BLK, width=5)
    d.polygon([(20, 120), (cw / 2 - 30, 330), (cw / 2 + 30, 330), (cw - 20, 120), (cw - 20, chh - 20), (20, chh - 20)], fill=(222, 190, 130))
    d.line([(20, 120), (cw / 2 - 30, 330), (cw / 2 + 30, 330), (cw - 20, 120)], fill=(150, 110, 60), width=6)
    for q in range(16):                                   # 砂つぶがすべり落ちる
        a = (q * 0.13 + tt * 0.5) % 1.0
        side = -1 if q % 2 else 1
        x = cw / 2 + side * (cw / 2 - 40) * (1 - a); y = 120 + 210 * a - 8
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(160, 120, 70))
    jaw = 8 * math.sin(tt * 8)                            # 底の大あご
    d.arc([cw / 2 - 60 - jaw, 300, cw / 2 - 4, 360], 270, 360, fill=(90, 50, 20), width=8)
    d.arc([cw / 2 + 4, 300, cw / 2 + 60 + jaw, 360], 180, 270, fill=(90, 50, 20), width=8)
    if f.get("ant"):
        a = min(1, max(0, (u - 0.3) / 1.6))
        x = 60 + (cw / 2 - 70) * ease(a); y = 112 + 205 * ease(a) - 10
        for k_ in range(3):
            d.ellipse([x - 12 + k_ * 12, y - 8, x + 2 + k_ * 12, y + 6], fill=BLK)
        if a > 0.2:
            d.text((x + 70, y - 40), "ずるっ", font=font(44), fill=RED, anchor="mm", stroke_width=5, stroke_fill=WHT)
    d.text((cw / 2, 50), "アリジゴクの巣（断面）", font=font(36), fill=BLK, anchor="mm")
    sc = back(min(1, u / 0.3))
    if sc < 1:
        lay = lay.resize((max(1, int(cw * sc)), max(1, int(chh * sc))))
    img.alpha_composite(lay, (int(PX + PW - 30 - lay.width), int(PY + PH - 30 - lay.height)))


def inflate(img, f, u, tt):
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = PX + PW - 230, PY + PH - 230
    p = ease(u / 1.4)
    r = 60 + 90 * p
    d.ellipse([cx - 175, cy - 175, cx + 175, cy + 175], fill=(255, 255, 255, 215), outline=BLK, width=5)
    for q in range(28):                                   # 寝ていた針が立つ
        a = q / 28 * 2 * math.pi
        ln = 12 + 40 * p
        tilt = (1 - p) * 1.2
        x0, y0 = cx + r * math.cos(a), cy + r * math.sin(a)
        x1, y1 = cx + (r + ln) * math.cos(a + tilt), cy + (r + ln) * math.sin(a + tilt)
        d.line([(x0, y0), (x1, y1)], fill=(120, 90, 50), width=5)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(230, 200, 140), outline=(120, 90, 50), width=5)
    d.ellipse([cx + r * 0.35, cy - r * 0.35, cx + r * 0.6, cy - r * 0.1], fill=BLK)
    if p > 0.6:
        d.text((cx, cy - 210), "ぷくーっ", font=font(60), fill=YEL, anchor="mm", stroke_width=7, stroke_fill=BLK)


def swim(img, f, u, tt):
    d = ImageDraw.Draw(img, "RGBA")
    for q in range(4):                                    # 水をかく波紋
        a = (u * 0.8 + q / 4) % 1
        cx, cy = PX + PW * 0.5, PY + PH * 0.55
        r = 60 + 420 * a
        d.ellipse([cx - r, cy - r * 0.35, cx + r, cy + r * 0.35], outline=(255, 255, 255, int(200 * (1 - a))), width=6)
    if int(u * 2.5) % 2 == 0:
        d.text((PX + PW * 0.5, PY + 90), "すいすい", font=font(84), fill=YEL, anchor="mm", stroke_width=8, stroke_fill=BLK)


def walk(img, f, u, tt):
    d = ImageDraw.Draw(img)
    n = int(u / 0.35) + 1
    for q in range(min(n, 7)):                            # 足あとが順に増える
        x = PX + 120 + q * 160; y = PY + PH - 90 - (30 if q % 2 else 0)
        d.ellipse([x - 26, y - 16, x + 26, y + 16], fill=YEL, outline=BLK, width=4)
    d.text((PX + PW - 200, PY + PH - 170), "てくてく", font=font(70), fill=WHT, anchor="mm", stroke_width=7, stroke_fill=BLK)


def lure(img, f, u, tt):
    d = ImageDraw.Draw(img)
    dy = 14 * math.sin(tt * 14)
    d.text((PX + PW * 0.72, PY + 140 + dy), "ピクピク", font=font(90), fill=YEL, anchor="mm", stroke_width=8, stroke_fill=BLK)


def dig(img, f, u, tt):
    d = ImageDraw.Draw(img)
    for q in range(22):                                   # 土がとぶ
        a = (q * 0.21 + u * 1.6) % 1
        x = PX + PW * 0.45 + (q % 7 - 3) * 40 * a * 3; y = PY + PH - 60 - 360 * a + 300 * a * a
        d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(110, 75, 40), outline=BLK)
    if int(u * 3) % 2 == 0:
        d.text((PX + PW * 0.75, PY + 120), "ザクザク", font=font(84), fill=YEL, anchor="mm", stroke_width=8, stroke_fill=BLK)


def notes(img, f, u, tt):
    d = ImageDraw.Draw(img)
    for q in range(5):
        a = (u * 0.5 + q / 5) % 1
        x = PX + PW * 0.6 + q * 60 + 30 * math.sin(tt * 3 + q); y = PY + PH * 0.7 - 380 * a
        d.text((x, y), "♪", font=font(80), fill=WHT, anchor="mm", stroke_width=6, stroke_fill=BLK)


def shoot(img, f, u, tt):
    d = ImageDraw.Draw(img)
    p = ease(u / 0.35)
    x0, y0 = PX + 120, PY + PH * 0.7
    x1 = x0 + (PW - 300) * p
    d.line([(x0, y0), (x1, y0 - 60 * math.sin(p * 3))], fill=(240, 120, 160), width=16)
    d.text((PX + PW * 0.75, PY + 120), "ビュッ", font=font(100), fill=YEL, anchor="mm", stroke_width=8, stroke_fill=BLK)


FX = {"thermo": thermo, "spray": spray, "pit": pit, "inflate": inflate, "swim": swim, "walk": walk, "lure": lure,
      "dig": dig, "notes": notes, "shoot": shoot}


def chapter_card(img, no, name, u, th):
    if u > 2.0:
        return
    a = min(1, u / 0.15, (2.0 - u) / 0.35)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rectangle([PX, PY + PH * 0.30, PX + PW, PY + PH * 0.70], fill=(0, 0, 0, int(150 * a)))
    img.alpha_composite(lay)
    p = back(u / 0.3)
    x = PX + PW / 2 + (1 - min(1, p)) * 500
    d = ImageDraw.Draw(img)
    f = font(64)
    tw = f.getbbox(f"No.{no}")[2]
    if a > 0.3:
        d.rectangle([x - tw / 2 - 20, PY + PH * 0.30 - 50, x + tw / 2 + 20, PY + PH * 0.30 + 40], fill=RED, outline=BLK, width=4)
        d.text((x, PY + PH * 0.30 - 5), f"No.{no}", font=f, fill=WHT, anchor="mm")
        sz = 170 if len(name) <= 6 else int(170 * 6 / len(name)) + 10
        th2 = dict(th); th2["face"] = YEL; th2["edge"] = BLK; th2["side"] = (40, 40, 40)
        theme.extrude_text(img, int(x), int(PY + PH * 0.53), name, sz * (0.9 + 0.1 * min(1, p)), th2, angle=-3)


def up_panel(img, face, mouth, blink, u, thn):
    """ツッコミ：ずんだもんの顔が画面いっぱいにドンと寄る。集中線、驚き系は揺れる"""
    pan = background(thn, u).convert("RGBA")
    dr = ImageDraw.Draw(pan, "RGBA")
    cx, cy = W // 2, 420
    for a in range(0, 360, 5):
        r = math.radians(a + (int(u * 15) % 2) * 2)
        w = 4 + (a * 7 % 5) * 3
        r0 = 380 + (a * 13 % 7) * 25
        dr.polygon([(cx + r0 * math.cos(r - 0.005 * w), cy + r0 * math.sin(r - 0.005 * w)),
                    (cx + 1800 * math.cos(r), cy + 1800 * math.sin(r)),
                    (cx + r0 * math.cos(r + 0.005 * w), cy + r0 * math.sin(r + 0.005 * w))], fill=(255, 255, 255, 170))
    z = 1.0 + 0.25 * (1 - ease(min(1, u / 0.15)))
    h = int(1450 * z)
    im = zunda(face, h, mouth, blink)
    amp = SHAKE.get(face, 0) * math.exp(-u * 3)
    sx, sy = int(amp * math.sin(u * 70)), int(amp * 0.6 * math.cos(u * 55))
    pan.alpha_composite(im, ((W - im.width) // 2 + sx, max(-2000, cy - int(h * 0.36) + sy)))
    img.paste(pan.crop((0, 0, W, SUB_Y)), (0, 0))


def dance_frame(img, u, mouth, line, first_photo):
    """冒頭0秒：ずんだもんが踊りながらキラーワード。右に写真、大きな数字"""
    k = int(u / BEAT) % len(DANCE); v = (u % BEAT) / BEAT
    face, flip = DANCE[k]
    im = zunda(face, 900, mouth, 0, flip)
    hop = abs(math.sin(math.pi * v)) * 26
    im = im.rotate(5 * math.sin(2 * math.pi * u / (BEAT * 2)), expand=True, resample=Image.BICUBIC)
    if first_photo:
        src = photo(first_photo)
        p = back(min(1, max(0, (u - 0.15) / 0.3)))
        if p > 0.02:
            ph = cover(src, 0.5, 0.42, 1.1, 820, 600)
            fr = Image.new("RGBA", (860, 640), BLK + (255,)); fr.paste(ph, (20, 20))
            fr = fr.resize((max(1, int(860 * p)), max(1, int(640 * p)))).rotate(-4, expand=True, resample=Image.BICUBIC)
            img.alpha_composite(fr, (int(1380 - fr.width / 2), int(420 - fr.height / 2)))
    img.alpha_composite(im, (int(420 - im.width / 2), int(SUB_Y + 40 - im.height - hop)))


# ── 音
_syn = {}


def synth(vv, text, out):
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
    A = "vv_assets"
    if "s" not in _syn:
        ort = Onnxruntime.load_once(filename=f"{A}/voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3")
        s = Synthesizer(ort, OpenJtalk(f"{A}/open_jtalk_dic_utf_8-1.11"))
        with VoiceModelFile.open(f"{A}/{vv['vvm']}") as m:
            s.load_voice_model(m)
        _syn["s"] = s
    s = _syn["s"]
    q = s.create_audio_query(re.sub(r"[「」『』]", "", text), vv["style"])
    q.speed_scale = vv.get("speed", 1.0); q.intonation_scale = vv.get("intonation", 1.0)
    q.pre_phoneme_length = 0.04; q.post_phoneme_length = 0.06
    open(out + ".tmp", "wb").write(s.synthesis(q, vv["style"]))
    os.replace(out + ".tmp", out)
    return q.kana


def load_wav(path):
    with wave.open(path) as w:
        sr = w.getframerate(); ch = w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if ch == 2:
        x = x.reshape(-1, 2).mean(1)
    if sr != SR:
        x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x).astype(np.float32)
    return x


def env_of(x):
    n = len(x) // (SR // FPS) + 1
    return np.array([np.sqrt(np.mean(x[i * (SR // FPS):(i + 1) * (SR // FPS)] ** 2) + 1e-12) for i in range(n)])


# ── 組み立て
def timeline(data):
    meta, secs = data["meta"], data["sections"]
    os.makedirs(WORK, exist_ok=True)
    rows, chapters, kana = [], [], []
    t = 0.0
    no = 0
    for si, sc in enumerate(secs):
        if not sc.get("ending"):
            no += 1
            chapters.append((t, f"{sc['name']}"))
        else:
            chapters.append((t, "まとめ"))
        sc["_no"] = no
        img = None
        for li, ln in enumerate(sc["lines"]):
            if ln.get("img"):
                img = ln["img"]
            ln["_img"] = img
            if ln.get("logo") and os.path.exists(JINGLE):
                x = load_wav(JINGLE)
                ev = load_wav(JINGLE_VOICE) if os.path.exists(JINGLE_VOICE) else x
                kana.append(f"{ln['say']}\n  → （ジングル）")
            else:
                say = meta.get("yomi", {}).get(ln["say"], ln["say"])
                for k_, v_ in meta.get("yomi_words", {}).items():     # 読み間違えやすい語（日本→にっぽん 等）
                    say = say.replace(k_, v_)
                vv = meta["voice"]
                p = f"{WORK}/v_" + hashlib.md5((say + json.dumps(vv, sort_keys=True)).encode()).hexdigest()[:12] + ".wav"
                kp = p + ".kana"
                if not os.path.exists(p) or not os.path.exists(kp):
                    open(kp, "w").write(synth(vv, say, p))
                kana.append(f"{ln['say']}\n  → {open(kp).read()}")
                x = load_wav(p); ev = x
            hold = ln.get("hold", 0.0) + (0.5 if ln.get("logo") else 0)
            if ln.get("up"):
                hold += 0.1
            rows.append([t, t + len(x) / SR + hold, si, li, x, env_of(ev)])
            t += len(x) / SR + hold + GAP
        t += SEC_GAP
    return rows, chapters, kana, t + 0.8


def audio(data, rows, total, out_wav):
    secs = data["sections"]
    import moso_long
    mix = np.zeros(int((total + 1) * SR), np.float32)
    ev = []
    for t0, t1, si, li, x, _ in rows:
        ln = secs[si]["lines"][li]
        i = int(t0 * SR); mix[i:i + len(x)] += x
        if ln.get("logo"):
            continue
        if ln.get("chapter"):
            ev += [("whoosh_l", t0, 0.5), ("boom", t0 + 0.3, 0.45)]
        if ln.get("up"):
            ev += [("boom", t0, 0.45)]
        if ln.get("dance"):
            ev += [("boing", t0 + 0.1, 0.7), ("kira", t0 + 0.4, 0.6)]
        if ln.get("digest") and li == 0:
            ev += [("pop_mid", t0 + 0.05 + q * 0.12, 0.5) for q in range(10)]
        for f in ln.get("fx", []):
            at = t0 + f.get("at", 0.2)
            ty = f["type"]
            ev += {"stamp": [("pop_big", at, 0.6)], "count": [("drumroll", at, 0.55), ("ding", at + 0.9, 0.6)],
                   "bars": [("pop_lo", at, 0.6)], "thermo": [("zip_long", at, 0.6)], "spray": [("whoosh_s", at, 0.6)],
                   "pit": [("slide_dn", at, 0.5)], "inflate": [("boing", at + 0.2, 0.6)], "walk": [("tick", at + q * 0.35, 0.4) for q in range(5)],
                   "dig": [("paper", at + q * 0.3, 0.5) for q in range(4)], "shoot": [("zip_up", at, 0.6)],
                   "swim": [("bubble", at + q * 0.4, 0.5) for q in range(3)], "lure": [("pop_hi", at, 0.4)],
                   "notes": [("chime_a", at, 0.35)]}.get(ty, [])
    for name, at, k in ev:
        s = se.sound(name)
        s = np.interp(np.arange(int(len(s) * SR / se.SR)) * se.SR / SR, np.arange(len(s)), s).astype(np.float32)
        i = int(at * SR); mix[i:i + len(s)] += s[:max(0, len(mix) - i)] * k
    marks = []
    for t0, t1, si, li, x, _ in rows:
        if li == 0:
            marks.append((t0, secs[si].get("mood", "comic")))
    b = moso_long.bgm(total + 1, marks) * 0.9
    for t0, t1, si, li, x, _ in rows:                   # ジングルの間はBGMを止める
        if secs[si]["lines"][li].get("logo"):
            a0 = int((t0 - 0.3) * SR); b[a0:] *= np.clip(1 - np.arange(len(b) - a0) / (0.3 * SR), 0, 1)
    mix += b[:len(mix)]
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.92
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


def frame(tt, data, rows, starts):
    secs = data["sections"]
    i = max(0, np.searchsorted(starts, tt, side="right") - 1)
    t0, t1, si, li, x, env = rows[i]
    sc = secs[si]; ln = sc["lines"][li]
    u = tt - t0
    th = theme.THEMES[sc["theme"]]
    speaking = t0 <= tt < t1
    fi = int(u * FPS)
    lv = env[fi] if speaking and fi < len(env) else 0
    mouth = 0 if lv < 0.02 else 1 if lv < 0.07 else 2
    blink = 1 if (int(tt * FPS) % 90) < 3 else 0
    img = background(sc["theme"], tt).convert("RGBA")
    n_all = sum(1 for s in secs if not s.get("ending"))
    if ln.get("dance"):
        dance_frame(img, u, mouth, ln, ln.get("_img"))
        for f in ln.get("fx", []):
            if f["type"] == "stamp" and u >= f.get("at", 0):
                g = dict(f, x=(1380 - PX) / PW, y=(820 - PY) / PH, size=210)
                stamp(img, g, u - f.get("at", 0), th)
                if u > 0.5:
                    stamp(img, dict(g, text="息を止められる", y=(970 - PY) / PH - 0.06, size=88, color=[255, 255, 255], tilt=-3), u - 0.5, th)
        subtitle(img, ln["say"])
        return img.convert("RGB")
    if ln.get("logo"):
        lp = background("pink_grad", u).convert("RGB")
        theme.channel_logo(lp, 760, 430, 1.25, u, logo_theme="pink_grad")
        img = lp.convert("RGBA")
        if u > BEAT:
            k = int((u - BEAT) / BEAT) % len(DANCE); v = ((u - BEAT) % BEAT) / BEAT
            face, flip = DANCE[k]
            zz = zunda(face, 640, mouth, 0, flip).rotate(5 * math.sin(2 * math.pi * u / (BEAT * 2)), expand=True, resample=Image.BICUBIC)
            img.alpha_composite(zz, (int(1450 - zz.width / 2), int(SUB_Y + 30 - zz.height - abs(math.sin(math.pi * v)) * 20)))
        subtitle(img, "レッツ！脳とけ！")
        return img.convert("RGB")
    if ln.get("digest"):                                  # まとめ：10種の写真がぽんぽん並ぶ
        firsts = [(s["name"], next(l["_img"] for l in s["lines"] if l.get("_img"))) for s in secs if not s.get("ending")]
        d0 = next(r[0] for r in rows if r[2] == si)
        uu = tt - d0
        cw, chh = 330, 250
        d = ImageDraw.Draw(img)
        for q, (nm, pth) in enumerate(firsts):
            p = back((uu - 0.05 - q * 0.12) / 0.2)
            if p <= 0.02:
                continue
            tile = cover(photo(pth), 0.5, 0.45, 1.0, cw, chh)
            fr = Image.new("RGBA", (cw + 16, chh + 16), WHT + (255,)); fr.paste(tile, (8, 8))
            fr = fr.resize((max(1, int(fr.width * p)), max(1, int(fr.height * p))))
            x = PX - 30 + (q % 5) * 255 + 128 - fr.width // 2; y = 250 + (q // 5) * 330 - fr.height // 2
            img.alpha_composite(fr.rotate((q % 3 - 1) * 3, expand=True, resample=Image.BICUBIC), (x, y))
            if p > 0.9:
                fs = 36 if len(nm) <= 6 else 30
                box(d, x + 6, y + fr.height - 30, nm, font(fs), BLK, YEL, 10, 4)
    else:
        # 写真の枠
        if ln.get("_img"):
            run0, k_ = t0, 0.0                            # 同じ写真が何秒続いているか（ゆっくり寄りの進み具合）
            j = i
            while j > 0 and secs[rows[j - 1][2]]["lines"][rows[j - 1][3]].get("_img") == ln["_img"] and rows[j - 1][2] == si:
                j -= 1
            run0 = rows[j][0]
            j2 = i
            while j2 + 1 < len(rows) and rows[j2 + 1][2] == si and secs[si]["lines"][rows[j2 + 1][3]].get("_img") == ln["_img"]:
                j2 += 1
            run1 = rows[j2][1]
            k_ = (tt - run0) / max(0.5, run1 - run0)
            mode = "cover" if (sum(1 for q in range(j) if rows[q][2] == si) % 2) else "contain"
            if ln.get("z"):                               # 台本で寄りを指定した行は、その行の中で寄る
                k_ = u / max(0.5, t1 - t0)
            panel(img, th, ln["_img"], mode, k_, ln.get("z"), tt - run0, tt)
            if tt - run0 < 2 / FPS:
                img.alpha_composite(Image.new("RGBA", (PW, PH), (255, 255, 255, 70)), (PX, PY))
        for f in ln.get("fx", []):
            fu = u - f.get("at", 0.2)
            if fu < 0:
                continue
            ty = f["type"]
            if ty == "stamp":
                stamp(img, f, fu, th)
            elif ty == "count":
                count(img, f, fu)
            elif ty == "bars":
                bars(img, f, fu)
            elif ty in FX:
                FX[ty](img, f, fu, tt)
        if ln.get("chapter"):
            chapter_card(img, sc["_no"], sc["name"], u, th)
        header(img, sc["_no"], sc["name"], sc["_no"], n_all)
    # ずんだもん（左下）。ツッコミの行は最初の1秒だけ顔のアップ
    if ln.get("up") and u < UPT:
        up_panel(img, ln.get("face", "驚き"), mouth, blink, u, sc["theme"])
    else:
        hop = int(10 * math.sin(math.pi * u / 0.25)) if u < 0.25 else 0
        bob = math.sin(tt * 2.6) * 4
        z = zunda(ln.get("face", "通常"), ZH, mouth, blink)
        img.alpha_composite(z, (int(300 - z.width / 2), int(SUB_Y + 30 - z.height - hop + bob)))
    subtitle(img, ln["say"])
    return img.convert("RGB")


def render_part(args):
    a, b, out, data_path, rows_pk = args
    import pickle
    data, rows = pickle.load(open(rows_pk, "rb"))
    starts = np.array([r[0] for r in rows])
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(a, b):
        p.stdin.write(frame(fi / FPS, data, rows, starts).tobytes())
        if (fi - a) % (FPS * 60) == 0:
            print(f"  {out}: {(fi - a) / FPS / 60:.0f}分 / {(b - a) / FPS / 60:.1f}分", flush=True)
    p.stdin.close(); p.wait()
    return out


def build(script, out, t_from=None, t_to=None, jobs=2):
    data = json.load(open(script, encoding="utf-8"))
    rows, chapters, kana, total = timeline(data)
    print("全体の長さ", round(total, 1), "秒", f"({int(total // 60)}分{int(total % 60)}秒)")
    open(f"{WORK}/yomi.txt", "w", encoding="utf-8").write("\n".join(kana) + "\n")
    wav = f"{WORK}/mix.wav"
    audio(data, rows, total, wav)
    import pickle
    pk = f"{WORK}/rows.pkl"
    pickle.dump((data, rows), open(pk, "wb"))
    f0 = int((t_from or 0) * FPS); f1 = int(min(total, t_to or total) * FPS)
    cuts = [f0 + (f1 - f0) * q // jobs for q in range(jobs + 1)]
    parts = [(cuts[q], cuts[q + 1], f"{WORK}/part{q}.mp4", script, pk) for q in range(jobs)]
    from multiprocessing import Pool
    with Pool(jobs) as pool:
        outs = pool.map(render_part, parts)
    open(f"{WORK}/parts.txt", "w").write("\n".join(f"file '{os.path.basename(o)}'" for o in outs))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", "parts.txt", "-c", "copy", "video.mp4"], check=True, cwd=WORK)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", f"{WORK}/video.mp4", "-ss", f"{f0 / FPS:.3f}", "-t", f"{(f1 - f0) / FPS:.3f}", "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", out], check=True)
    with open(out.replace(".mp4", "_chapters.txt"), "w", encoding="utf-8") as f:
        for ct, name in chapters:
            f.write(f"{int(ct // 60)}:{int(ct % 60):02d} {name}\n")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out, "-vf", "fps=1/10,scale=320:-1,tile=8x14", "-frames:v", "1",
                    out.replace(".mp4", "_sheet.jpg")])
    print(out, round(total, 1), "s")


if __name__ == "__main__":
    a = sys.argv[1:]
    tf = float(a[a.index("--from") + 1]) if "--from" in a else None
    tt_ = float(a[a.index("--to") + 1]) if "--to" in a else None
    jb = int(a[a.index("--jobs") + 1]) if "--jobs" in a else 2
    build(a[0], a[1], tf, tt_, jb)
