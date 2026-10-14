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


def build(main_copy, subject, image_path, out_png, badge="世界の謎を10分で解説"):
    # 背景：実物の画像を右側に大きく（右の約2/3）。左は黒で、境目はなめらかに溶かす
    IX = 420
    im = Image.new("RGB", (W, H), (8, 8, 8))
    if image_path and os.path.exists(image_path):
        src = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
        src = ImageOps.fit(src, (W - IX, H), Image.LANCZOS, centering=(0.5, 0.45))
        src = ImageEnhance.Contrast(src).enhance(1.25)
        src = ImageEnhance.Color(src).enhance(1.3)
        src = src.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=3))
        mask = Image.new("L", (W - IX, H), 255)
        md = ImageDraw.Draw(mask)
        for x in range(220):
            md.line([(x, 0), (x, H)], fill=int(255 * (x / 220) ** 1.3))
        im.paste(src, (IX, 0), mask)
    d = ImageDraw.Draw(im)

    # 左上の赤い札
    bf = _font(40)
    bw = int(bf.getlength(badge))
    d.rectangle([0, 36, bw + 76, 36 + 78], fill=RED)
    d.text((40, 36 + 8), badge, font=bf, fill=(255, 255, 255))

    # 2行コピー：画面の横幅の約65%まで、行ごとに最大の大きさで
    lines = _lines(main_copy)
    max_w = 820
    fonts = [_fit(l, max_w, 170) for l in lines]
    size = min(f.size for f in fonts)              # 2行の大きさをそろえる（小さいほうに合わせる）
    fonts = [_font(size) for _ in lines]
    lh = int(size * 1.22)
    top = 150 + max(0, (2 - len(lines)) * lh // 2) + (170 - size) // 2
    for i, (l, f) in enumerate(zip(lines, fonts)):
        _outlined(d, (44, top + i * lh), l, f, (255, 255, 255) if i == 0 and len(lines) > 1 else YELLOW,
                  stroke=max(6, size // 13))

    # 下の題材名
    sf = _font(48, "Bold")
    tw = int(sf.getlength(subject))
    d.rectangle([0, H - 118, tw + 90, H - 40], fill=(0, 0, 0))
    d.rectangle([0, H - 118, 14, H - 40], fill=YELLOW)
    d.text((44, H - 112), subject, font=sf, fill=(255, 255, 255))

    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    im.save(out_png)
    return out_png
