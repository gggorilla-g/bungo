# ehon_thumb.py — 絵本の表紙らしいサムネ（1280x720）。Codex の表紙の絵（上3分の1が空いている）に題名を載せる
#   使い方: python3 tools/ehon_thumb.py 表紙の絵.png "題名" 出力.jpg [サブ（例：よみきかせ）]
import sys
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, "tools")
from ballsim import font

def main(src, title, out, sub=""):
    W, H = 1280, 720; im = Image.open(src).convert("RGB")
    r = max(W / im.width, H / im.height); im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H)).convert("RGBA")
    d = ImageDraw.Draw(im); size = 112; f = font(size)
    while d.textlength(title, font=f) > W * .86: size -= 4; f = font(size)
    w = d.textlength(title, font=f); x, y = (W - w) / 2, 70
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.text((x, y), title, font=f, fill=(255, 250, 238, 255), stroke_width=22, stroke_fill=(255, 250, 238, 255))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(im); d.text((x, y), title, font=f, fill=(78, 48, 36), stroke_width=7, stroke_fill=(255, 251, 242))
    if sub:
        fs = font(40); ws = d.textlength(sub, font=fs); d.text(((W - ws) / 2, y + size + 34), sub, font=fs, fill=(90, 62, 48), stroke_width=5, stroke_fill=(255, 251, 242))
    im.convert("RGB").save(out, quality=92); print("サムネ:", out)

if __name__ == "__main__":
    main(*sys.argv[1:5])
