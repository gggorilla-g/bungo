# portrait_icon.py — PDの肖像写真を、紺×生成りの2〜3階調ポスター調アイコンにする
import sys
from PIL import Image, ImageOps, ImageFilter, ImageDraw

def make(src, box, out, size=800, levels=(70, 150)):
    im = Image.open(src).convert("L").crop(box)
    im = ImageOps.autocontrast(im, cutoff=2).resize((size, size), Image.LANCZOS)
    im = im.filter(ImageFilter.MedianFilter(7)).filter(ImageFilter.GaussianBlur(1.2))
    dark, mid, light = (13, 31, 60), (23, 51, 94), (242, 238, 228)   # 濃紺 / 紺 / 生成り
    t1, t2 = levels
    px = im.load(); out_im = Image.new("RGB", im.size); op = out_im.load()
    for y in range(size):
        for x in range(size):
            v = px[x, y]
            op[x, y] = dark if v < t1 else (mid if v < t2 else light)
    out_im.save(out)

if __name__ == "__main__":
    make("channel/src_akutagawa.jpg", (0, 0, 619, 619), sys.argv[1] if len(sys.argv) > 1 else "channel/icon_akutagawa.png")
