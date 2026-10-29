# nazo/thumb.py — NAZOのサムネイル（型を固定して毎回同じ品質で自動生成する）
#   スマホの小さな表示でも一瞬で読めることを最優先にした、YouTubeらしい強い型:
#   - 実物の画像を画面いっぱいに（コントラスト・彩度を上げて）
#   - 左側を暗く落とし、そこに極太の2行コピー（1行目 白／2行目 黄）を黒フチ＋影で
#   - 左上に赤い札「世界の謎」、下に題材名の黒帯
#   コピーは台本の thumbnail.main_copy（改行 "\n" か「、」で2行に分ける）。
#   事実に反する煽りは書かない（例: アンティキティラ＝「2000年前の / コンピューター」はよく使われる説明として可）
import os, subprocess
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H = 1280, 720
RED, YELLOW = (220, 30, 30), (255, 226, 0)


def _font(size, weight="Black"):
    for name in (f"Noto Sans CJK JP:style={weight}", "Noto Sans CJK JP:style=Bold", "Noto Sans CJK JP"):
        r = subprocess.run(["fc-match", "-f", "%{file}|%{index}", name], capture_output=True, text=True).stdout
        if r and "|" in r:
            path, idx = r.split("|")
            if "CJK" in path:
                return ImageFont.truetype(path, size, index=int(idx or 0))
    return ImageFont.load_default()


def _lines(copy):
    s = copy.replace("\\n", "\n")
    lines = [l.strip() for l in (s.split("\n") if "\n" in s else s.replace("、", "、\n").split("\n")) if l.strip()]
    if len(lines) == 1 and len(lines[0]) > 7:
        h = (len(lines[0]) + 1) // 2; lines = [lines[0][:h], lines[0][h:]]
    return lines[:2]


def _fit(text, max_w, start, weight="Black"):
    size = start
    while size > 40:
        f = _font(size, weight)
        if f.getlength(text) <= max_w:
            return f
        size -= 4
    return _font(size, weight)


def _outlined(d, xy, text, font, fill, stroke):
    x, y = xy
    # 影（右下にずらした黒）→ 黒フチ → 本体
    d.text((x + 8, y + 10), text, font=font, fill=(0, 0, 0), stroke_width=stroke, stroke_fill=(0, 0, 0))
    d.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))


def _box(d, x, y, text, font, fg, bg, padx, pady):
    """文字を四角で囲む（箱の中に文字）。箱の右端を返す"""
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    w, h = r - l, b - t
    d.rectangle([x, y, x + w + padx * 2, y + h + pady * 2], fill=bg)
    d.text((x + padx - l, y + pady - t), text, font=font, fill=fg)
    return x + w + padx * 2, y + h + pady * 2


PALETTE_NAZO = {"badge": ((255, 255, 255), (220, 30, 30)), "l1": ((255, 255, 255), (0, 0, 0)),
                "l2": ((0, 0, 0), (255, 226, 0)), "subj": ((0, 0, 0), (255, 255, 255))}
# BUNGO：紺×金（同じ型で色だけ変える）
PALETTE_BUNGO = {"badge": ((13, 27, 51), (217, 165, 32)), "l1": ((255, 255, 255), (13, 27, 51)),
                 "l2": ((13, 27, 51), (217, 165, 32)), "subj": ((13, 27, 51), (246, 240, 226))}


def build(main_copy, subject, image_path, out_png, badge="ホー博士の世界の謎10分解説", palette=None):
    pal = palette or PALETTE_NAZO
    # 背景：実物を右寄せで大きく（文字の箱に隠れにくいように）。左の余白は同じ画像をぼかして埋める
    im = Image.new("RGB", (W, H), (8, 8, 8))
    if image_path and os.path.exists(image_path):
        src = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
        src = ImageEnhance.Contrast(src).enhance(1.25)
        src = ImageEnhance.Color(src).enhance(1.3)
        bg = ImageOps.fit(src, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
        im = ImageEnhance.Brightness(bg).enhance(0.55)
        fw = min(int(W * 0.72), int(src.width * H / src.height))
        fg = ImageOps.fit(src, (fw, H), Image.LANCZOS, centering=(0.5, 0.45))
        fg = fg.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=3))
        mask = Image.new("L", (fw, H), 255)
        md = ImageDraw.Draw(mask)
        feather = min(120, fw // 5)
        for x in range(feather):
            md.line([(x, 0), (x, H)], fill=int(255 * x / feather))
        im.paste(fg, (W - fw, 0), mask)
    d = ImageDraw.Draw(im)

    # 左上：赤い箱に白文字
    _box(d, 0, 30, badge, _font(42), pal["badge"][0], pal["badge"][1], 36, 16)

    # 2行コピー：1行目＝黒い箱に白文字、2行目＝黄色い箱に黒文字。どちらも極太で最大の大きさ
    lines = _lines(main_copy)
    pad = 26
    fonts = [_fit(l, 1000 - pad * 2, 168) for l in lines]
    size = min(f.size for f in fonts)
    f = _font(size)
    py = int(size * 0.16)
    gap = 14
    hs = []
    for l in lines:
        t, b = d.textbbox((0, 0), l, font=f)[1::2]
        hs.append(b - t + py * 2)
    block = sum(hs) + gap * (len(lines) - 1)
    sf = _font(50)
    st, sb = d.textbbox((0, 0), subject, font=sf)[1::2]
    sub_top = H - 36 - (sb - st) - 32
    area_top, area_bot = 30 + 90 + 20, sub_top - 20
    y = area_top + max(0, (area_bot - area_top - block) // 2)
    styles = [pal["l1"], pal["l2"]] if len(lines) > 1 else [pal["l2"]]
    for l, (fg_, bg_) in zip(lines, styles):
        _, y2 = _box(d, 0, y, l, f, fg_, bg_, pad, py)
        y = y2 + gap

    # 下：題材名を白い箱に黒文字
    _box(d, 0, sub_top, subject, sf, pal["subj"][0], pal["subj"][1], 30, 16)

    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    im.save(out_png)
    return out_png


def build_v2(main_copy, subject, image_path, out_png, badge="ホー博士の世界の謎", eyes="open"):
    """v2（2026-10-29）：箱をやめ、実物の写真を全面に。極太の縁取り文字2行と、驚くホー博士を大きく。
    1行目 白、2行目 黄。左を暗く落として文字を読ませる。札と題材名は小さく。"""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import owl as owl_mod
    im = Image.new("RGB", (W, H), (8, 8, 8))
    if image_path and os.path.exists(image_path):
        src = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
        src = ImageEnhance.Contrast(src).enhance(1.3)
        src = ImageEnhance.Color(src).enhance(1.25)
        if src.width / src.height >= 1.3:                  # 横長：全面に
            im = ImageOps.fit(src, (W, H), Image.LANCZOS, centering=(0.6, 0.45))
        else:                                             # 縦長（石柱など）：物を右に丸ごと見せ、残りはぼかした同じ写真
            im = ImageEnhance.Brightness(ImageOps.fit(src, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(26))).enhance(0.6)
            fw = int(src.width * H / src.height)
            fg = src.resize((fw, H), Image.LANCZOS)
            m = Image.new("L", (fw, H), 255); md = ImageDraw.Draw(m)
            for x in range(min(90, fw // 4)):
                md.line([(x, 0), (x, H)], fill=int(255 * x / min(90, fw // 4)))
            im.paste(fg, (W - 170 - fw, 0), m)
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=3))
    shade = Image.new("L", (W, H), 0)                      # 左から右へ暗さが抜ける
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(225 * max(0.0, 1 - x / (W * 0.7)) ** 1.1))
    im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, shade)
    d = ImageDraw.Draw(im)
    lines = _lines(main_copy)
    f = _font(min(_fit(l, 740, 190).size for l in lines))
    y = 95 if len(lines) > 1 else 200
    for l, col in zip(lines, [(255, 255, 255), YELLOW] if len(lines) > 1 else [YELLOW]):
        _outlined(d, (44, y), l, f, col, 14)
        t, b = d.textbbox((0, 0), l, font=f)[1::2]
        y += (b - t) + 40
    ow = owl_mod.owl(eyes=eyes, beak="open", wing="rest", size=380)
    im.paste(ow, (W - ow.width + 10, H - ow.height + 30), ow)
    bf = _font(30, "Bold")
    _box(d, 0, 26, badge, bf, (255, 255, 255), RED, 22, 10)
    _outlined(d, (46, H - 84), subject, _font(46), (255, 255, 255), 8)
    im.save(out_png)
    return out_png
