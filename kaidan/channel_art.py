"""今晩の百物語：チャンネルのアイコン（800x800）とヘッダー（2560x1440）。黒×朱、明朝、狐面の宵狐"""
import sys
from PIL import Image, ImageDraw
sys.path.insert(0, "kaidan")
import kitsune, thumb_quiet

BG, RED, INK = (8, 8, 10), (142, 20, 20), (238, 234, 226)


def icon():
    im = Image.new("RGB", (800, 800), (20, 14, 16))
    d = ImageDraw.Draw(im)
    d.ellipse([60, 60, 740, 740], fill=(52, 14, 16))          # 提灯の明かりのような朱の円
    k = kitsune.kitsune(0.9, 0, 1300)
    im.paste(k, ((800 - k.width) // 2 - 10, 10), k)
    im.save("kaidan/channel/icon.png")


def banner():
    W, H = 2560, 1440
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    k = kitsune.kitsune(0.9, 0, 470)
    im.paste(k, (700, (H - 470) // 2 + 20), k)
    f = thumb_quiet._f
    d.text((1230, 650), "今晩の百物語", font=f(132), fill=INK, anchor="lm")
    d.rectangle([1236, 760, 1236 + 560, 812], fill=RED)
    d.text((1236 + 280, 786), "古典怪談の朗読　原作は青空文庫", font=f(34, "Bold"), fill=(255, 255, 255), anchor="mm")
    im.save("kaidan/channel/banner.png")


icon(); banner()
