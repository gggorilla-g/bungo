"""ホー博士のチャンネル用アイコン（800x800）とヘッダー（2560x1440）。
サムネと同じ型：黒地、文字はすべて箱、赤・黒・黄。"""
from PIL import Image, ImageDraw
import owl
from thumb import _font, _box

SP = "channel"
YEL, RED, BLK, WHT = (255, 226, 0), (220, 30, 30), (0, 0, 0), (255, 255, 255)


def icon():
    im = Image.new("RGB", (800, 800), YEL)
    o = owl.owl("open", "closed", "rest", size=1150)
    # 顔と帽子が丸い切り抜きの中に収まるよう、上半身を大きく
    im.paste(o, ((800 - o.width) // 2, 40), o)
    im.save(f"{SP}/icon.png")


def banner():
    W, H = 2560, 1440
    im = Image.new("RGB", (W, H), BLK)
    d = ImageDraw.Draw(im)
    # スマホでも切れない中央の帯（1546x423）にすべて収める
    o = owl.owl("open", "closed", "point", size=420)
    ox = 640
    im.paste(o, (ox, (H - o.height) // 2), o)
    x = ox + 430
    f1, f2 = _font(84), _font(120)
    _, y2 = _box(d, x, 560, "ホー博士の", f1, WHT, RED, 26, 14)
    _box(d, x, y2 + 16, "世界の謎10分解説", f2, BLK, YEL, 30, 16)
    im.save(f"{SP}/banner.png")


if __name__ == "__main__":
    icon(); banner()
