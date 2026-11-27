# pidrop.py — 円周率の数字を順に、玉にして0〜9の筒へ落とす。最初に24個たまるのは、どの数字？（縦のショート 1080×1920・60コマ）
#   持ち主 11/28：画面収録（The Sound of π：円周率の数字ごとに玉が落ち、0〜9の筒にたまって鳴る）を送って「これも作っといて。ビードロ系の音で瞑想エコー」
#   まねたのはしくみ（円周率の数字 → 玉 → 筒）。足した決まり：24個たまったら勝ちの競争。円周率の小数点以下では、8 がずっと先を走り、23個で止まったまま、2 が186けため（小数第186位）で先に24個になる
#   速さ：はじめは1けたに 0.42秒。だんだん速くなる。玉は数字の帯から放物線で筒に落ち、着いた瞬間に1打
#   音：ビードロ（kalimba の vidro。うすいガラスの小びん）。音の高さは、今のカノン進行の和音の音を、数字の順（0 が低い … 9 が高い）。瞑想のような長いエコーと、裏の低い持続音
#   python3 tools/pidrop.py stills ／ all（LANG_OUT=en で英語）→ output/pidrop1_<ja|en>.mp4
import math, os, sys
import numpy as np, mpmath
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS = T.W, T.H, T.FPS
mpmath.mp.dps = 260; DIG = [int(c) for c in mpmath.nstr(mpmath.pi, 250)[2:]]   # 小数点以下（1けため＝1）
GOAL = 24; RAD = 15; TX0, TX1 = 78, 1002; TW = (TX1 - TX0) / 10; TTOP, TBOT = 780, 1540
SY = 470; FLY = .55; G = 2600.0; OUTRO = 3.2
def interval(i): return max(.085, .42 * math.exp(-i / 38.0))
def race():
    rel = []; t = .8; cnt = [0] * 10; land = []
    for i, d in enumerate(DIG):
        rel.append(t); land.append((t + FLY, i, d, cnt[d])); cnt[d] += 1
        if cnt[d] == GOAL: return rel, land, i, d
        t += interval(i)
REL, LAND, IWIN, WIN = race(); TWIN = LAND[-1][0]; DUR = TWIN + OUTRO; NF = int(DUR * FPS)
LT = np.array([l[0] for l in LAND]); RT = np.array(REL)
def tx(d): return TX0 + (d + .5) * TW
def ystack(k): return TBOT - RAD - 2 * RAD * k - 2
def hue(d):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((.92 + d * .1) % 1, .45, 1.0); return (int(r * 255), int(g * 255), int(b * 255))
SPR = [T.sprite(hue(d), RAD) for d in range(10)]; GL = T.glow(40)
BG = T.background((W / 2, 1100))
CH = ["D", "A", "Bm", "F#m", "G", "D", "G", "A"]
def chord_at(t): return int(t // 2.4) % 8
def pos(l, t):
    """着地前の玉の位置（放物線）"""
    tl, i, d, k = l; t0 = tl - FLY; e = t - t0; x = 540 + (tx(d) - 540) * e / FLY; y1 = ystack(k); v0 = (y1 - SY - .5 * G * FLY * FLY) / FLY
    return x, SY + v0 * e + .5 * G * e * e
def make_frame(fi):
    t = fi / FPS; buf = BG.copy(); nl = int(np.searchsorted(LT, t, "right")); nr = int(np.searchsorted(RT, t, "right"))
    cnt = [0] * 10
    for l in LAND[:nl]: cnt[l[2]] += 1
    lead = max(cnt) if nl else 0
    for l in LAND[:nl]:                                                 # たまった玉
        tl, i, d, k = l; e = t - tl; T.blit(buf, SPR[d], tx(d), ystack(k) + (2.5 * math.exp(-e / .05) * math.sin(e * 60) if e < .2 else 0))
        if e < .5: T.add_glow(buf, GL, tx(d), ystack(k), hue(d), .45 * math.exp(-e / .14))
    for l in LAND[nl:]:                                                 # 飛んでいる玉
        if l[0] - FLY > t: break
        x, y = pos(l, t); T.blit(buf, SPR[l[2]], x, y)
    def draw(d):
        INK = (240, 240, 248, 255)
        T.fit_text(d, (W / 2, 150), T.tr("円周率の数字を、玉にして落とす", "Drop the digits of pi as balls"), 56, 990, INK)
        T.fit_text(d, (W / 2, 232), T.tr(f"最初に {GOAL}個たまるのは、どの数字？", f"Which digit fills {GOAL} first?"), 54, 990, (255, 214, 130, 255))
        # 数字の帯
        cur = max(0, nr - 1); fx = T.fnt(56, False); step = 40
        sc = (t - RT[cur]) / interval(cur) if nr else 0
        for j in range(cur - 13, cur + 14):
            x = 540 + (j - cur - min(1, sc) * 0) * step
            if j < -1: continue
            s_ = "3." if j == -1 else (str(DIG[j]) if j < len(DIG) else "")
            if j > cur: continue
            a = 255 if j == cur else int(150 * max(0, 1 - abs(j - cur) / 14)); d.text((x, 380), s_, font=fx, fill=(230, 230, 240, a), anchor="mm")
        if nr: d.rounded_rectangle([540 - 26, 380 - 36, 540 + 26, 380 + 36], radius=10, outline=(255, 214, 130, 255), width=3); d.text((540, 432), T.tr(f"小数第{cur + 1}位", f"digit {cur + 1}"), font=T.fnt(26, False), fill=(190, 190, 210, 255), anchor="mm")
        for dg in range(10):                                            # ガラスの筒
            x0, x1 = tx(dg) - TW / 2 + 8, tx(dg) + TW / 2 - 8; d.rounded_rectangle([x0, TTOP, x1, TBOT + 4], radius=16, outline=(200, 210, 240, 110), width=3, fill=(160, 180, 255, 14))
            d.line([x0 + 9, TTOP + 30, x0 + 9, TBOT - 30], fill=(255, 255, 255, 34), width=4)
            on = nl and cnt[dg] == lead and lead > 0; d.text((tx(dg), TTOP - 40), str(cnt[dg]), font=T.fnt(38), fill=(255, 214, 130, 255) if on else (200, 204, 222, 255), anchor="mm")
            d.text((tx(dg), TBOT + 52), str(dg), font=T.fnt(46), fill=hue(dg) + (255,), anchor="mm")
        yg = ystack(GOAL - 1) - RAD - 3
        for xs in range(TX0, TX1, 22): d.line([xs, yg, xs + 12, yg], fill=(255, 214, 130, 230), width=3)   # ゴールの線（筒の上に重ねる）
        d.text((W / 2, TTOP - 96), T.tr(f"点線まで（{GOAL}個）たまったら勝ち", f"First to the dotted line ({GOAL}) wins"), font=T.fnt(30, False), fill=(255, 214, 130, 230), anchor="mm")
        if t >= INTRO_T: d.text((W / 2, TBOT + 120), T.tr(f"いまの和音  {CH[chord_at(t)]}", f"Chord: {CH[chord_at(t)]}"), font=T.fnt(30, False), fill=(170, 176, 200, 255), anchor="mm")
        cap = None
        for (ta, tb, s_) in CAPS:
            if ta <= t < tb: cap = (s_, min(1, (t - ta) / .25) * min(1, (tb - t) / .3))
        if cap: T.fit_text(d, (W / 2, 1745), cap[0], 50, 990, (255, 226, 150, int(255 * cap[1])))
        T.fit_text(d, (W / 2, 1840), T.tr("円周率 3.14159… の小数点以下を、1けたずつ", "The digits of pi after 3., one by one"), 28, 990, (150, 156, 184, 255), bold=False)
    out = T.to_frame(buf, draw, grain=fi); g = min(T.sstep(0, .3, t), 1 - T.sstep(DUR - .5, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)
INTRO_T = .8
def caps():
    out = []; cnt = [0] * 10; said20 = False; said23 = False
    for (tl, i, d, k) in LAND:
        cnt[d] += 1
        if not said20 and max(cnt) == 20: ld = cnt.index(20); out.append((tl, tl + 2.2, T.tr(f"{ld} がリード", f"{ld} takes the lead"))); said20 = True
        if not said23 and max(cnt) == 23: ld = cnt.index(23); out.append((tl, tl + 2.4, T.tr(f"{ld} は、あと1個", f"{ld} needs just one more"))); said23 = True
    out.append((TWIN + .15, DUR, T.tr(f"最初に {GOAL}個たまったのは {WIN}", f"{WIN} reached {GOAL} first")))
    return out
CAPS = caps()
def audio(path):
    a = T.Audio(DUR, mat="vidro", max_same=3, window=.02)
    for (tl, i, d, k) in LAND:
        m = K.canon_tones(chord_at(tl), 57, 100)[d]; a.note(tl, m, vel=.7, pan=.15 + .7 * d / 9)
    under = K.pad([(r, r + 12, f5 + 12) for (r, t3, f5) in K.CANON], 2.4, DUR + .5, .045)[: int(T.SR * DUR)]
    return a.write(path, room=(.32, 3.2), under=under)                  # 瞑想のような長いエコー
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_pidrop", exist_ok=True)
    print("長さ", round(DUR, 1), "勝ち", WIN, "けた", IWIN + 1, "字幕", [(round(a, 1), s) for a, b, s in CAPS])
    if cmd == "stills": print(T.stills(NF, make_frame, "build_pidrop/s", at=(.05, .3, .6, .85, .98))); sys.exit()
    out = f"output/pidrop1_{T.LANG}.mp4"; audio("build_pidrop/a.wav"); T.encode(NF, make_frame, "build_pidrop/a.wav", out); print(out)
