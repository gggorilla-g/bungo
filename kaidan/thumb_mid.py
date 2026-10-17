"""怪談のサムネ（ほどよいインパクトの型）：
  絵を画面いっぱいに大きく、明るめに → 左に暗がりを作って、話の中の一言（copy）を太い明朝で大きく →
  朱の札に「第〇話」と題名、左上にチャンネル名。罫線・煽り文句（閲覧注意など）は使わない。
  build(題名, "二", 作者, 画像, 出力, copy="話したら、\n殺す。", focus=(0.6, 0.35))
  focus は絵のどこを中心に切り抜くか（横・縦の割合）"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

W, H = 1280, 720
INK = (246, 242, 234)
SUB = (196, 190, 182)
RED = (150, 18, 18)


def _f(size, w="Black"):
    for name in (w, "Bold", "Regular"):
        try:
            return ImageFont.truetype(f"/usr/share/fonts/opentype/noto/NotoSerifCJK-{name}.ttc", size, index=0)
        except OSError:
            pass
    raise OSError("明朝体（Noto Serif CJK）が見つからない")


def _cover(src, w, h, focus):
    s = max(w / src.width, h / src.height) * 1.08          # 少し寄る
    r = src.resize((int(src.width * s) + 1, int(src.height * s) + 1), Image.LANCZOS)
    x = int(min(max(r.width * focus[0] - w / 2, 0), r.width - w))
    y = int(min(max(r.height * focus[1] - h / 2, 0), r.height - h))
    return r.crop((x, y, x + w, y + h))


def _shadow_text(im, xy, text, font, fill, anchor="la", spacing=0):
    sh = Image.new("L", im.size, 0)
    ImageDraw.Draw(sh).multiline_text(xy, text, font=font, fill=255, anchor=anchor, spacing=spacing)
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    im.paste((0, 0, 0), (0, 0), sh.point(lambda v: min(255, int(v * 1.6))))
    ImageDraw.Draw(im).multiline_text(xy, text, font=font, fill=fill, anchor=anchor, spacing=spacing)


BLOOD = (214, 30, 30)


def _rich_text(im, xy, text, font, spacing):
    """［］で囲んだ言葉だけ赤くする（例「誰もいない［墓］の前で、」）"""
    import re
    x0, y = xy
    lh = font.getbbox("あ")[3] + spacing
    for line in text.split("\n"):
        segs = [(t, i % 2 == 1) for i, t in enumerate(re.split(r"[［］]", line)) if t]
        plain = "".join(t for t, _ in segs)
        sh = Image.new("L", im.size, 0)
        ImageDraw.Draw(sh).text((x0, y), plain, font=font, fill=255)
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        im.paste((0, 0, 0), (0, 0), sh.point(lambda v: min(255, int(v * 1.6))))
        d = ImageDraw.Draw(im)
        x = x0
        for t, red in segs:
            if red:   # 明るい絵の上でも沈まないよう、赤い字には暗い縁
                d.text((x, y), t, font=font, fill=BLOOD, stroke_width=4, stroke_fill=(20, 0, 0))
            else:
                d.text((x, y), t, font=font, fill=INK)
            x += d.textlength(t, font=font)
        y += lh
    return y


def build(title, no_kanji, author, img_path, out, copy="", focus=(0.6, 0.4)):
    im = Image.new("RGB", (W, H), (10, 10, 12))
    if img_path:
        src = Image.open(img_path).convert("RGB")
        # 絵は右寄りに大きく。左側は暗がりにして文字を置く
        fw = 900
        fg = ImageEnhance.Contrast(ImageEnhance.Brightness(_cover(src, fw, H, focus)).enhance(0.92)).enhance(1.08)
        bg = ImageEnhance.Brightness(_cover(src, W, H, focus).filter(ImageFilter.GaussianBlur(28))).enhance(0.3)
        im = bg
        m = Image.new("L", (fw, H), 255)
        md = ImageDraw.Draw(m)
        for i in range(260):                                # 左端をなだらかに暗がりへ溶かす（線は引かない）
            md.line([(i, 0), (i, H)], fill=int(255 * (i / 260) ** 1.4))
        im.paste(fg, (W - fw, 0), m)
    # 下と左を少し沈めて、文字と再生時間の表示を読みやすく
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(170 * max(0, 1 - x / 640) ** 1.2))
    im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, shade)
    d = ImageDraw.Draw(im)
    # チャンネル名（左上）
    _shadow_text(im, (64, 40), "今晩の百物語", _f(54), INK)
    # 札と作者 → 題名（いちばん大きく） → 話の中の一言 の順に並べる
    d = ImageDraw.Draw(im)
    lab = f"第{no_kanji}話"
    f1 = _f(46, "Bold")
    w1 = d.textlength(lab, font=f1)
    d.rectangle([64, 116, 64 + w1 + 36, 182], fill=RED)
    d.text((64 + 18, 149), lab, font=f1, fill=(255, 255, 255), anchor="lm")
    if author:
        _shadow_text(im, (64 + w1 + 60, 149), author, _f(34, "Bold"), SUB, anchor="lm")
    ts = min(160, int(720 / max(len(title), 1)))
    glow = Image.new("L", im.size, 0)                 # 題名の背後に、にじむような暗い赤
    ImageDraw.Draw(glow).text((56, 196), title, font=_f(ts), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(22)).point(lambda v: min(255, int(v * 1.3)))
    im.paste((120, 0, 0), (0, 0), glow)
    _shadow_text(im, (56, 196), title, _f(ts), INK)
    bb = ImageDraw.Draw(im).textbbox((56, 196), title, font=_f(ts))
    if copy:
        n = max(len(l.replace("［", "").replace("］", "")) for l in copy.split("\n"))
        size = min(92, int(800 / max(n, 1)))   # 長い一言は小さく（左の暗がりの幅に収める）
        _rich_text(im, (60, bb[3] + 40), copy, _f(size, "Black"), int(size * 0.2))
    im.save(out)
    return out
