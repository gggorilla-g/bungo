# thumb_puzzle.py — サムネの文字を「長体・詰め・ふち文字の重ね」で作る（整えすぎない）
#   使い方（Python から）: from thumb_puzzle import big_text
#   big_text(img, xy, "700倍", size=220, fill="#ffe14a", rims=[("#000",34),("#fff",22),("#000",8)], cond=.72, track=-.06, rot=-3)
#   rims は外側から順に (色, 太さ px)。cond は横の縮め（長体）、track は字間（em、マイナスで詰め）
from PIL import Image, ImageDraw, ImageFont
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"


def _layer(text, size, fill, rims, track):
    f = ImageFont.truetype(FONT, size, index=0)
    pad = max([w for _, w in rims] + [0]) + 10
    adv = [f.getlength(ch) for ch in text]
    W = int(sum(adv) + track * size * (len(text) - 1) + pad * 2); H = int(size * 1.35 + pad * 2)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for col, w in rims + [(fill, 0)]:             # 外のふちから順に重ねる
        d = ImageDraw.Draw(im); x = pad
        for ch, a in zip(text, adv):
            d.text((x, pad), ch, font=f, fill=col, stroke_width=w, stroke_fill=col)
            x += a + track * size
    return im


def big_text(img, xy, text, size=160, fill="#ffffff", rims=(("#000", 26), ("#fff", 16), ("#000", 6)), cond=.74, track=-.06, rot=0):
    L = _layer(text, size, fill, list(rims), track)
    L = L.resize((max(1, int(L.width * cond)), L.height), Image.LANCZOS)
    if rot: L = L.rotate(rot, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(L, (int(xy[0]), int(xy[1])))
    return L.size
