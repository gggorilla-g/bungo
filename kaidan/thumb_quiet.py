"""怪談のサムネ（静かな型）：暗く沈めた絵＋明朝の縦書きの題名＋朱の「第〇話」。煽り文句は入れない。
  build(題名, "一", 作者, 画像, 出力)"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

W, H = 1280, 720
INK = (242, 238, 230)
SUB = (180, 174, 166)
RED = (142, 20, 20)


def _f(size, w="Black"):
    for name in (w, "Bold", "Regular"):     # 環境によって入っている太さが違う
        try:
            return ImageFont.truetype(f"/usr/share/fonts/opentype/noto/NotoSerifCJK-{name}.ttc", size, index=0)
        except OSError:
            pass
    raise OSError("明朝体（Noto Serif CJK）が見つからない")


def _vertical(d, text, x, y, size, fill):
    for ch in text:
        d.text((x, y + size // 2), ch, font=_f(size), fill=fill, anchor="mm")
        y += size + int(size * 0.07)


def build(title, no_kanji, author, img_path, out):
    im = Image.new("RGB", (W, H), (8, 8, 10))
    if img_path:
        src = Image.open(img_path).convert("RGB")
        # 背景：同じ絵を大きくぼかして暗く
        s = max(W / src.width, H / src.height)
        bg = src.resize((int(src.width * s) + 1, int(src.height * s) + 1))
        bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
        im = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(24))).enhance(0.25)
        # 絵の本体：右側に高さいっぱい（横長の絵は右寄せで幅を抑える）
        fh = H
        fw = int(src.width * fh / src.height)
        if fw > 700:             # 横長の絵は題名にかからない幅に
            fw = 700; fh = int(src.height * fw / src.width)
        fg = ImageEnhance.Brightness(src.resize((fw, fh), Image.LANCZOS)).enhance(0.82)
        m = Image.new("L", fg.size, 255); md = ImageDraw.Draw(m)
        for i in range(60):
            a = int(255 * i / 60)
            md.line([(i, 0), (i, fh)], fill=a); md.line([(fw - 1 - i, 0), (fw - 1 - i, fh)], fill=a)
        im.paste(fg, (W - fw - 40, (H - fh) // 2), m)
    # 周辺を暗く
    v = Image.new("L", (W, H), 0); ImageDraw.Draw(v).ellipse([-300, -250, W + 300, H + 250], fill=255)
    im = Image.composite(im, Image.new("RGB", (W, H), (0, 0, 0)), v.filter(ImageFilter.GaussianBlur(120)))
    d = ImageDraw.Draw(im)
    # 題名：縦書き。長い題名は2列に分ける
    cols = [title] if len(title) <= 7 else [title[: (len(title) + 1) // 2], title[(len(title) + 1) // 2:]]
    n = max(len(c) for c in cols)
    size = min(118, int(600 / (n * 1.07)))
    x = 330 if len(cols) == 1 else 390
    for c in cols:
        _vertical(d, c, x, 60, size, INK)
        x -= int(size * 1.2)
    # 朱の札「第〇話」
    lab = f"第{no_kanji}話"
    fs = 40
    hh = len(lab) * (fs + 20) + 14
    d.rectangle([150, 64, 212, 64 + hh], fill=RED)
    yy = 78
    for ch in lab:
        d.text((181, yy + fs // 2), ch, font=_f(fs, "Bold"), fill=(255, 255, 255), anchor="mm"); yy += fs + 20
    d.text((181, 590), "今晩の", font=_f(26, "Bold"), fill=SUB, anchor="mm")
    d.text((181, 626), "百物語", font=_f(26, "Bold"), fill=SUB, anchor="mm")
    if author:
        d.text((560 if len(cols) == 1 else 600, 662), author, font=_f(28, "Bold"), fill=SUB, anchor="rm")
    im.save(out)
    return out
