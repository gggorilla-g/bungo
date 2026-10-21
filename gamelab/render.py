"""学習の記録（history.json）から、世代ごとの群れの映像を描く部品。
draw_gen(gen_entry, ...) で、その世代の上位の挑戦をまとめて再生したフレームを返す。"""
import math
from PIL import Image, ImageDraw, ImageFont
import game

W, H = 1280, 720
T = game.T
BG = (24, 26, 44)
GROUND = (58, 52, 86)
GROUND_TOP = (110, 98, 160)
SPIKE = (235, 235, 245)
CRUMBLE = (150, 110, 70)
ZUNDA = (120, 200, 90)
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
_fc = {}


def font(size):
    if size not in _fc:
        _fc[size] = ImageFont.truetype(FONT, size, index=0)
    return _fc[size]


def simulate(genomes):
    """上位の遺伝子をまとめて動かし、tickごとの位置と状態を記録する"""
    agents = [game.Agent() for _ in genomes]
    frames = []
    for t in range(game.MAXT):
        row = []
        live = False
        for a, g in zip(agents, genomes):
            if a.alive and not a.won:
                a.step(g[min(t // game.STEP, len(g) - 1)], t)
                live = live or (a.alive and not a.won)
            row.append((a.x, a.y, a.alive, a.won, a.trig, frozenset(a.gone), a.cause if not a.alive else None))
        frames.append(row)
        if not live:
            break
    return frames + [frames[-1]] * 90     # 終わったあとも少し映す（ゴールの余韻）


def leader(row):
    """群れの先頭（生きている中でいちばん右。全滅なら最後に死んだ中でいちばん右）"""
    alive = [r for r in row if r[2]]
    pool = alive or row
    return max(pool, key=lambda r: r[0])


def draw_level(d, cam, t, lead):
    c0, c1 = int(cam // T) - 1, int((cam + W) // T) + 2
    for r in range(game.ROWS):
        for c in range(max(0, c0), min(len(game.LEVEL[0]), c1)):
            v = game.LEVEL[r][c]
            x, y = c * T - cam, r * T
            if v == 1:
                d.rectangle([x, y, x + T - 1, y + T - 1], fill=GROUND)
                if r == 0 or game.LEVEL[r - 1][c] != 1:
                    d.rectangle([x, y, x + T - 1, y + 5], fill=GROUND_TOP)
            elif v == 5 and (r, c) not in lead[5]:
                d.rectangle([x, y, x + T - 1, y + T - 1], fill=CRUMBLE)
                d.line([x + 8, y + 6, x + 20, y + 22, x + 30, y + 12], fill=(90, 60, 30), width=3)
            elif v == 2:
                for k in range(2):
                    bx = x + k * T / 2
                    d.polygon([(bx, y + T), (bx + T / 4, y + T / 2 - 4), (bx + T / 2, y + T)], fill=SPIKE)
            elif v == 3:
                for k in range(2):
                    bx = x + k * T / 2
                    d.polygon([(bx, y), (bx + T / 4, y + T / 2 + 4), (bx + T / 2, y)], fill=SPIKE)
    # 隠しトゲ：先頭が近づいたら出る
    lx = lead[0]
    for hx, hy in game.HIDDEN:
        if abs(lx - hx) < 70 or lx > hx:
            x = hx - cam
            for k in range(2):
                bx = x + k * T / 2
                d.polygon([(bx, hy + T), (bx + T / 4, hy + 4), (bx + T / 2, hy + T)], fill=(255, 90, 90))
    # 偽ゴールと本物のゴール
    for fx in (game.FAKE_GOAL_X, game.FAKE_GOAL2_X, game.GOAL_X):
        x = fx - cam
        if -60 < x < W + 60:
            d.rectangle([x + 18, 15 * T - 160, x + 22, 15 * T], fill=(230, 230, 230))
            d.polygon([(x + 22, 15 * T - 160), (x + 90, 15 * T - 135), (x + 22, 15 * T - 110)], fill=(240, 200, 40))
            d.text((x + 28, 15 * T - 148), "GOAL", font=font(16), fill=(30, 30, 30))
    # 落ちる天井
    ty = game.thwomp_y(lead[4], t)
    x = game.THWOMP_X - cam
    if -100 < x < W + 100:
        d.rectangle([x, ty, x + 2 * T - 1, ty + 2 * T - 1], fill=(120, 120, 140))
        d.rectangle([x, ty + 2 * T - 8, x + 2 * T - 1, ty + 2 * T - 1], fill=(200, 60, 60))
        d.line([x + 14, ty + 26, x + 32, ty + 34], fill=(30, 30, 30), width=5)
        d.line([x + 66, ty + 26, x + 48, ty + 34], fill=(30, 30, 30), width=5)
    # ノコギリ
    for sx, sy, rad in game.saws(t):
        x = sx - cam
        if -50 < x < W + 50:
            pts = []
            for k in range(24):
                a = k * math.pi / 12 + t / 6
                rr = rad + (7 if k % 2 == 0 else 0)
                pts.append((x + rr * math.cos(a), sy + rr * math.sin(a)))
            d.polygon(pts, fill=(200, 205, 215))
            d.ellipse([x - 6, sy - 6, x + 6, sy + 6], fill=(80, 80, 90))


def draw_frame(row, t, cam, graves, alpha_layer=True):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    lead = leader(row)
    draw_level(d, cam, t, lead)
    for gx, gy in graves:                       # これまでに死んだ場所の印
        x = gx - cam
        if -10 < x < W + 10:
            d.line([x - 6, gy - 6, x + 6, gy + 6], fill=(200, 60, 60), width=3)
            d.line([x - 6, gy + 6, x + 6, gy - 6], fill=(200, 60, 60), width=3)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    for r in row:
        if not r[2] or r is lead:
            continue
        x, y = r[0] - cam, r[1]
        ld.ellipse([x, y, x + game.AW, y + game.AH], fill=ZUNDA + (90,))
    im.paste(lay, (0, 0), lay)
    if lead[2] or lead[3]:
        x, y = lead[0] - cam, lead[1]
        d.ellipse([x - 2, y - 2, x + game.AW + 2, y + game.AH + 2], fill=(20, 40, 20))
        d.ellipse([x, y, x + game.AW, y + game.AH], fill=ZUNDA)
        d.ellipse([x + 13, y + 7, x + 17, y + 12], fill=(20, 20, 20))
        d.ellipse([x + 18, y + 7, x + 22, y + 12], fill=(20, 20, 20))
    return im, d, lead


def hud(im, d, gen, deaths, best_x, lead_x):
    d.text((28, 20), f"GEN {gen}", font=font(44), fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    d.text((28, 74), f"DEATHS {deaths:,}", font=font(36), fill=(255, 110, 110), stroke_width=4, stroke_fill=(0, 0, 0))
    # 進み具合の棒
    x0, x1, y = 340, W - 40, 40
    d.rectangle([x0, y - 6, x1, y + 6], fill=(60, 60, 80))
    p = lambda v: x0 + (x1 - x0) * min(1, v / game.GOAL_X)
    d.rectangle([x0, y - 6, p(best_x), y + 6], fill=(90, 140, 80))
    d.ellipse([p(lead_x) - 10, y - 10, p(lead_x) + 10, y + 10], fill=ZUNDA, outline=(0, 0, 0), width=3)
    d.text((x1, y + 14), "GOAL", font=font(18), fill=(240, 200, 40), anchor="ra")
