"""元絵の仮生成（本番ではCodex等のAI画像に置き換える部分）。
外部画像が取得できない環境のため、試作用にフラットなイラストを描く。"""
import random, sys
from PIL import Image, ImageDraw

def scene(seed=7, W=1000, H=750):
    rnd = random.Random(seed)
    im = Image.new("RGB", (W, H), (150, 205, 240))
    d = ImageDraw.Draw(im)
    # 太陽・雲
    d.ellipse((800, 50, 900, 150), fill=(255, 205, 60))
    for cx, cy in [(180, 110), (520, 80)]:
        for dx, dy, r in [(0, 0, 38), (40, -15, 45), (85, 0, 36)]:
            d.ellipse((cx+dx-r, cy+dy-r, cx+dx+r, cy+dy+r), fill=(255, 255, 255))
    # 鳥
    for bx, by in [(330, 170), (370, 150), (640, 190)]:
        d.line((bx-14, by-6, bx, by, bx+14, by-6), fill=(40, 40, 40), width=4)
    # 丘
    d.ellipse((-200, 380, 600, 900), fill=(120, 190, 90))
    d.ellipse((350, 400, 1250, 950), fill=(100, 175, 80))
    d.rectangle((0, 600, W, H), fill=(110, 182, 85))
    # 家
    d.rectangle((380, 360, 640, 590), fill=(245, 225, 190))
    d.polygon([(355, 365), (510, 250), (665, 365)], fill=(200, 70, 60))
    d.rectangle((580, 270, 615, 330), fill=(150, 90, 70))
    d.rectangle((485, 480, 545, 590), fill=(130, 85, 55))
    d.ellipse((530, 530, 540, 540), fill=(240, 200, 60))
    for wx in (405, 570):
        d.rectangle((wx, 400, wx+50, 450), fill=(170, 220, 250))
        d.line((wx+25, 400, wx+25, 450), fill=(255, 255, 255), width=4)
        d.line((wx, 425, wx+50, 425), fill=(255, 255, 255), width=4)
    d.ellipse((490, 300, 530, 340), fill=(170, 220, 250))
    # 木
    for tx, ty, s in [(150, 430, 1.0), (850, 450, 1.1), (270, 500, 0.7)]:
        d.rectangle((tx-12*s, ty, tx+12*s, ty+120*s), fill=(120, 80, 50))
        d.ellipse((tx-70*s, ty-110*s, tx+70*s, ty+30*s), fill=(60, 140, 60))
        for _ in range(4):
            ax = tx + rnd.randint(-45, 45)*s; ay = ty + rnd.randint(-80, 0)*s
            d.ellipse((ax-9, ay-9, ax+9, ay+9), fill=(230, 60, 60))
    # 柵
    for fx in range(20, 340, 40):
        d.rectangle((fx, 620, fx+14, 690), fill=(250, 250, 245))
    d.rectangle((15, 638, 345, 650), fill=(250, 250, 245))
    d.rectangle((15, 668, 345, 680), fill=(250, 250, 245))
    # 花
    for _ in range(9):
        x = rnd.randint(680, 980); y = rnd.randint(640, 730)
        col = rnd.choice([(255, 120, 170), (255, 230, 80), (180, 120, 255)])
        d.line((x, y, x, y+20), fill=(50, 120, 40), width=3)
        for ox, oy in [(-7, 0), (7, 0), (0, -7), (0, 7)]:
            d.ellipse((x+ox-6, y+oy-6, x+ox+6, y+oy+6), fill=col)
        d.ellipse((x-4, y-4, x+4, y+4), fill=(255, 250, 220))
    # 猫
    cx, cy = 430, 640
    d.ellipse((cx-35, cy-20, cx+35, cy+25), fill=(60, 60, 60))
    d.ellipse((cx+20, cy-45, cx+60, cy-5), fill=(60, 60, 60))
    d.polygon([(cx+22, cy-35), (cx+28, cy-60), (cx+38, cy-40)], fill=(60, 60, 60))
    d.polygon([(cx+42, cy-40), (cx+52, cy-60), (cx+58, cy-35)], fill=(60, 60, 60))
    d.line((cx-35, cy, cx-60, cy-30), fill=(60, 60, 60), width=8)
    # 郵便ポスト
    d.rectangle((690, 520, 700, 600), fill=(120, 80, 50))
    d.rectangle((665, 490, 725, 530), fill=(60, 110, 200))
    return im

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "base.png"
    scene().save(out)
    print(out)
