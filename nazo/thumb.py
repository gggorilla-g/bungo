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


def build(main_copy, subject, image_path, out_png, badge="世界の謎を10分で解説"):
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
    _box(d, 0, 30, badge, _font(42), (255, 255, 255), RED, 36, 16)

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
    styles = [((255, 255, 255), (0, 0, 0)), ((0, 0, 0), YELLOW)] if len(lines) > 1 else [((0, 0, 0), YELLOW)]
    for l, (fg_, bg_) in zip(lines, styles):
        _, y2 = _box(d, 0, y, l, f, fg_, bg_, pad, py)
        y = y2 + gap

    # 下：題材名を白い箱に黒文字
    _box(d, 0, sub_top, subject, sf, (0, 0, 0), (255, 255, 255), 30, 16)

    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    im.save(out_png)
    return out_png
