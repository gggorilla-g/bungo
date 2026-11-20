# ehon_thumb.py — 「ほほほブックス」の表紙サムネ（1280x720）
#   表紙の絵（Codex の1枚絵。上3分の1を空けて描く）に、毎回同じ形で載せる：
#     左上＝レーベル「ほほほブックス」／上部＝題名／右下の帯＝「よみきかせ」「◯ふん」
#   使い方: python3 tools/ehon_thumb.py 表紙の絵.png "題名" 出力.jpg 分数
import sys, os
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, "tools")
from ballsim import font

LABEL = "ほほほブックス"
INK = (78, 48, 36); PAPER = (255, 250, 238)


def badge(im, xy, text, size, fill, ink, pad=(26, 14), r=None):
    d = ImageDraw.Draw(im); f = font(size); w = d.textlength(text, font=f); x, y = xy
    box = [x, y, x + w + pad[0] * 2, y + size + pad[1] * 2]
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([box[0] + 4, box[1] + 6, box[2] + 4, box[3] + 6], r or (box[3] - box[1]) // 2, fill=(40, 25, 20, 90))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(im); d.rounded_rectangle(box, r or (box[3] - box[1]) // 2, fill=fill)
    d.text((x + pad[0], y + pad[1] - size * .08), text, font=f, fill=ink); return box


def main(src, title, out, minutes=""):
    W, H = 1280, 720; im = Image.open(src).convert("RGB")
    r = max(W / im.width, H / im.height); im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H)).convert("RGBA")
    # 題名
    d = ImageDraw.Draw(im); size = 116; f = font(size)
    while d.textlength(title, font=f) > W * .84: size -= 4; f = font(size)
    w = d.textlength(title, font=f); x, y = (W - w) / 2, 112
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(glow).text((x, y), title, font=f, fill=PAPER + (255,), stroke_width=24, stroke_fill=PAPER + (255,))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(11)))
    d = ImageDraw.Draw(im); d.text((x, y), title, font=f, fill=INK, stroke_width=7, stroke_fill=PAPER)
    # レーベル（左上）
    lp = "nazo/kaizo/ehon/brand/logo_full.png"
    if os.path.exists(lp):   # レーベルのロゴ（フクロウと本）。読めるよう、うしろに淡い紙色のにじみ
        lg = Image.open(lp).convert("RGBA"); lg.thumbnail((330, 110)); pad = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(pad).rounded_rectangle([20, 16, 20 + lg.width + 28, 16 + lg.height + 20], 30, fill=PAPER + (215,)); im.alpha_composite(pad.filter(ImageFilter.GaussianBlur(4)))
        im.alpha_composite(lg, (34, 26))
    else: badge(im, (34, 28), LABEL, 34, (122, 74, 52), PAPER, pad=(24, 12))
    # 帯（右下）：よみきかせ／◯ふん
    tag = "よみきかせ" + (f"  {minutes}ふん" if minutes else "")
    f2 = font(40); w2 = ImageDraw.Draw(im).textlength(tag, font=f2)
    badge(im, (W - w2 - 26 * 2 - 30, H - 40 - 14 * 2 - 30), tag, 40, PAPER, INK, pad=(26, 14))
    im.convert("RGB").save(out, quality=92); print("サムネ:", out)


if __name__ == "__main__":
    main(*sys.argv[1:5])
