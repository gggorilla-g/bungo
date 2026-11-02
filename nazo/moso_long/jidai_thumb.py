# 長尺 第2回のサムネ（1280x720）。左に時代の絵を4枚並べて×、右にずんだもん。文字は短く
#   使い方: python nazo/moso_long/jidai_thumb.py output/jidai_thumb.png
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
f = lambda s: ImageFont.truetype(FONT, s, index=0)
RED, YEL, WHT, BLK = (226, 36, 44), (255, 214, 0), (255, 255, 255), (0, 0, 0)


def tile(name, w, h, crop=None):
    im = Image.open(f"assets/eras/{name}.jpg").convert("RGB")
    if crop:
        im = im.crop((int(im.width * crop[0]), int(im.height * crop[1]), int(im.width * crop[2]), int(im.height * crop[3])))
    sc = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def main(out):
    img = Image.new("RGB", (W, H), (12, 12, 20))
    tiles = [("cretaceous2", None, "恐竜時代"), ("iceage", None, "氷河期"), ("edo", [0.03, 0.04, 0.97, 0.96], "江戸時代"), ("carbon", None, "5億年前")]
    tw, th = 400, 300
    d = ImageDraw.Draw(img)
    for i, (n, c, lab) in enumerate(tiles):
        x, y = 20 + (i % 2) * (tw + 12), 100 + (i // 2) * (th + 12)
        img.paste(tile(n, tw, th, c), (x, y))
        d.rectangle([x, y, x + tw - 1, y + th - 1], outline=WHT, width=4)
        d.text((x + 14, y + th - 14), lab, font=f(40), fill=WHT, anchor="ld", stroke_width=6, stroke_fill=BLK)
        d.line([(x + 110, y + 60), (x + tw - 110, y + th - 60)], fill=RED, width=22)
        d.line([(x + tw - 110, y + 60), (x + 110, y + th - 60)], fill=RED, width=22)
    z = Image.open("assets/enc/parts/泣き_1_0.png").convert("RGBA")
    zh = 640
    z = z.resize((int(z.width * zh / z.height), zh), Image.LANCZOS)
    a = z.getchannel("A").point(lambda v: 255 if v > 10 else 0)
    from PIL import ImageFilter
    ol = Image.new("RGBA", z.size, (255, 255, 255, 0)); ol.putalpha(a.filter(ImageFilter.MaxFilter(15)))
    ol.alpha_composite(z)
    img.paste(ol, (W - ol.width + 30, H - ol.height + 20), ol)
    d.rectangle([0, 0, W, 92], fill=BLK)
    d.text((20, 46), "7つの時代に移住してみた", font=f(64), fill=YEL, anchor="lm")
    d.text((1080, 520), "全部", font=f(84), fill=WHT, anchor="mm", stroke_width=10, stroke_fill=BLK)
    d.text((1080, 620), "ムリ", font=f(110), fill=RED, anchor="mm", stroke_width=12, stroke_fill=WHT)
    img.save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "output/jidai_thumb.png")
