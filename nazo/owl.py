# nazo/owl.py — 案内役「フクロウ博士」（オリジナル）をパーツの組み合わせで描く
#   owl(eyes="open"|"half"|"closed", beak="closed"|"open", wing="rest"|"point", size=600) -> RGBA Image
#   4倍の大きさで描いてから縮小し、線をなめらかにする。外部素材は使わない。
from PIL import Image, ImageDraw

INK = (43, 29, 20, 255)          # 輪郭線
BODY = (139, 94, 60, 255)        # 体（茶）
BODY_D = (112, 72, 44, 255)      # 体の影・羽の筋
BELLY = (240, 226, 196, 255)     # お腹
FACE = (222, 190, 146, 255)      # 顔の皿
HAT = (196, 178, 132, 255)       # 探検帽
HAT_D = (150, 133, 92, 255)
BAND = (122, 42, 32, 255)        # 帽子の帯（えんじ）
BEAK = (240, 168, 48, 255)
BEAK_D = (196, 120, 24, 255)
GLASS = (214, 170, 60, 255)      # メガネの縁（金）
WHITE = (255, 255, 255, 255)
PUPIL = (30, 22, 18, 255)
MOUTH = (110, 30, 24, 255)

S = 4  # 描画倍率


def _ell(d, box, fill, w=0):
    x0, y0, x1, y1 = [v * S for v in box]
    if w:
        d.ellipse([x0 - w * S, y0 - w * S, x1 + w * S, y1 + w * S], fill=INK)
    d.ellipse([x0, y0, x1, y1], fill=fill)


def _poly(d, pts, fill, w=0):
    p = [(x * S, y * S) for x, y in pts]
    if w:
        d.polygon(p, fill=fill, outline=INK, width=w * S)
    else:
        d.polygon(p, fill=fill)


def owl(eyes="open", beak="closed", wing="rest", size=600, look=(0, 0)):
    W = H = 300  # 設計上の座標（300x300）
    im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    # 足
    for fx in (122, 162):
        _ell(d, (fx, 268, fx + 22, 284), BEAK_D, 3)

    # 左の翼（画面左、常に下ろす）
    _poly(d, [(70, 150), (50, 205), (64, 258), (100, 250), (98, 160)], BODY_D, 4)

    if wing != "point":
        _poly(d, [(214, 150), (234, 205), (220, 258), (186, 250), (188, 160)], BODY_D, 4)
    # 体
    _ell(d, (64, 92, 220, 278), BODY, 5)
    # お腹とうろこ模様
    _ell(d, (94, 168, 190, 272), BELLY, 0)
    for row, y in enumerate(range(186, 262, 16)):
        off = 8 if row % 2 else 0
        for x in range(100 + off, 186, 18):
            d.arc([x * S, y * S, (x + 14) * S, (y + 12) * S], 20, 160, fill=(200, 172, 128, 255), width=3 * S)

    # 右の翼（画面右）：rest=下ろす / point=指し示す（斜め上へ）
    if wing == "point":
        _poly(d, [(196, 160), (250, 120), (286, 96), (276, 128), (232, 176), (206, 196)], BODY_D, 4)
        for i in range(3):  # 羽先の筋
            x = 252 + i * 10; y = 118 - i * 7
            d.line([((x - 22) * S, (y + 22) * S), (x * S, y * S)], fill=INK, width=3 * S)

    # 耳の羽（帽子の下からのぞく）
    _poly(d, [(84, 92), (70, 58), (106, 80)], BODY_D, 4)
    _poly(d, [(200, 92), (214, 58), (178, 80)], BODY_D, 4)

    # 顔の皿（ハート寄りの横長）
    _ell(d, (78, 86, 146, 156), FACE, 4)
    _ell(d, (138, 86, 206, 156), FACE, 4)
    _ell(d, (100, 120, 184, 170), FACE, 0)

    # 目（白目→瞳→ハイライト）。half/closedはまぶた
    lx, ly = look
    for cx in (112, 172):
        _ell(d, (cx - 24, 98, cx + 24, 146), WHITE, 0)
        if eyes == "jito":
            # ジト目：上まぶたが水平に下り、瞳は下の方で横目
            _ell(d, (cx - 10 + 6, 120, cx + 12 + 6, 142), PUPIL, 0)
            d.rectangle([(cx - 25) * S, 96 * S, (cx + 25) * S, 121 * S], fill=FACE)
            d.line([(cx - 24) * S, 121 * S, (cx + 24) * S, 121 * S], fill=INK, width=5 * S)
        elif eyes == "uruuru":
            # うるうる：大きな瞳に光をたくさん、下に涙の水たまり
            _ell(d, (cx - 17, 104, cx + 17, 140), PUPIL, 0)
            _ell(d, (cx - 11, 108, cx - 1, 118), WHITE, 0)
            _ell(d, (cx + 4, 124, cx + 9, 129), WHITE, 0)
            _ell(d, (cx - 8, 129, cx - 4, 133), WHITE, 0)
            d.chord([(cx - 23) * S, 118 * S, (cx + 23) * S, 148 * S], 0, 180, fill=(150, 205, 240, 255))
            d.arc([(cx - 23) * S, 118 * S, (cx + 23) * S, 148 * S], 0, 180, fill=(90, 160, 220, 255), width=2 * S)
        elif eyes == "closed":
            d.rectangle([(cx - 25) * S, 97 * S, (cx + 25) * S, 147 * S], fill=FACE)
            d.arc([(cx - 18) * S, 112 * S, (cx + 18) * S, 134 * S], 20, 160, fill=INK, width=5 * S)
        else:
            _ell(d, (cx - 12 + lx, 110 + ly, cx + 12 + lx, 134 + ly), PUPIL, 0)
            _ell(d, (cx - 6 + lx, 113 + ly, cx + 1 + lx, 120 + ly), WHITE, 0)
            if eyes == "half":
                d.rectangle([(cx - 25) * S, 96 * S, (cx + 25) * S, 120 * S], fill=FACE)
                d.line([(cx - 22) * S, 120 * S, (cx + 22) * S, 120 * S], fill=INK, width=4 * S)
        # メガネの縁（丸メガネ）
        d.ellipse([(cx - 28) * S, 94 * S, (cx + 28) * S, 150 * S], outline=GLASS, width=6 * S)
    d.line([136 * S, 118 * S, 148 * S, 118 * S], fill=GLASS, width=6 * S)  # ブリッジ
    if eyes == "uruuru":
        _poly(d, [(196, 148), (190, 162), (202, 162)], (150, 205, 240, 255), 0)
        _ell(d, (189, 157, 203, 171), (150, 205, 240, 255), 0)

    # くちばし（closed=三角 / open=上下に開く）
    if beak == "open":
        _ell(d, (128, 150, 156, 182), MOUTH, 3)                       # 開いた口
        _poly(d, [(126, 144), (158, 144), (142, 160)], BEAK, 3)       # 上くちばし
        _poly(d, [(132, 176), (152, 176), (142, 188)], BEAK_D, 3)     # 下くちばし
    else:
        _poly(d, [(130, 146), (154, 146), (142, 170)], BEAK, 3)

    # 探検帽（つば＋山＋帯）
    _ell(d, (60, 62, 224, 92), HAT_D, 4)
    _poly(d, [(92, 78), (100, 28), (184, 28), (192, 78)], HAT, 4)
    _ell(d, (98, 18, 186, 40), HAT, 4)
    d.rectangle([94 * S, 60 * S, 190 * S, 74 * S], fill=BAND)

    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "build/owl_sheet.png"
    poses = [("open", "closed", "rest"), ("open", "open", "rest"), ("jito", "closed", "rest"),
             ("uruuru", "closed", "rest"), ("closed", "closed", "rest")]
    sheet = Image.new("RGBA", (300 * len(poses), 300), (40, 40, 40, 255))
    for i, p in enumerate(poses):
        o = owl(*p, size=300)
        sheet.alpha_composite(o, (i * 300, 0))
    sheet.save(out)
    print(out)
