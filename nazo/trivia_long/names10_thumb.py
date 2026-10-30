# nazo/trivia_long/names10_thumb.py — 長尺「名前がひどすぎる生き物10選」のサムネ（1280x720）
#   写真が主役。極太の短い文字（白と黄色、黒フチ）。赤は使わない。タイトル（10選）と同じことは言わない。
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
SRC = "nazo/trivia_long/names10/photos/sloth/sloth_24.jpg"
OUT = sys.argv[1] if len(sys.argv) > 1 else "nazo/manual/trivia_names10/trivia_long_names10_thumb.png"


def cover(im, cx, cy, z, w, h):
    s = max(w / im.width, h / im.height) * z
    cw, ch = w / s, h / s
    x0 = min(max(cx * im.width - cw / 2, 0), im.width - cw)
    y0 = min(max(cy * im.height - ch / 2, 0), im.height - ch)
    return im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.LANCZOS)


src = Image.open(SRC).convert("RGB")
img = cover(src, 0.62, 0.40, 1.05, W, H)
# 文字の下だけ少し暗くして読みやすく（写真は暗くしすぎない）
shade = Image.new("L", (W, H), 0)
d = ImageDraw.Draw(shade)
for x in range(W):
    d.line([(x, 0), (x, H)], fill=int(max(0, 150 * (1 - x / (W * 0.62)))))
img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, shade.filter(ImageFilter.GaussianBlur(20)))
d = ImageDraw.Draw(img)


def text(xy, s, size, fill, sw):
    d.text(xy, s, font=ImageFont.truetype(FONT, size), fill=fill, stroke_width=sw, stroke_fill=(0, 0, 0), anchor="la")


text((40, 60), "名前は", 110, (255, 255, 255), 12)
text((40, 180), "怠け者", 200, (255, 255, 255), 16)
text((40, 470), "息止め40分", 150, (255, 214, 0), 15)
z = "assets/enc/parts/驚き_2_0.png"
if os.path.exists(z):
    zi = Image.open(z).convert("RGBA")
    zi = zi.resize((int(zi.width * 330 / zi.height), 330), Image.LANCZOS)
    img.paste(zi, (W - zi.width + 40, H - zi.height + 20), zi)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
img.save(OUT)
print(OUT)
