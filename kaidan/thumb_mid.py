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
    _shadow_text(im, (64, 44), "今晩の百物語", _f(46), INK)
    # 話の中の一言：大きく
    if copy:
        lines = copy.split("\n")
        n = max(len(l) for l in lines)
        size = min(132, int(620 / max(n, 1)))
        _shadow_text(im, (60, 150), copy, _f(size), INK, spacing=int(size * 0.18))
        bb = ImageDraw.Draw(im).multiline_textbbox((60, 150), copy, font=_f(size), spacing=int(size * 0.18))
        y_tag = bb[3] + 40
    else:
        y_tag = 300
    # 朱の札：第〇話　題名
    d = ImageDraw.Draw(im)
    lab = f"第{no_kanji}話"
    f1, f2 = _f(40, "Bold"), _f(72)
    w1 = d.textlength(lab, font=f1)
    w2 = d.textlength(title, font=f2)
    d.rectangle([64, y_tag, 64 + w1 + 36, y_tag + 64], fill=RED)
    d.text((64 + 18, y_tag + 32), lab, font=f1, fill=(255, 255, 255), anchor="lm")
    _shadow_text(im, (64 + w1 + 60, y_tag + 32), title, f2, INK, anchor="lm")
    if author:
        _shadow_text(im, (66, y_tag + 104), author, _f(30, "Bold"), SUB)
    im.save(out)
    return out
