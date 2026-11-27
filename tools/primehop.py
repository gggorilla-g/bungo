# primehop.py — 素数が、自分の数ずつとんでいく。だれも着地しない数が、次の素数（エラトステネスのふるい）。着地の音だけで、素数がわかる（縦のショート 1080×1920・60コマ）
#   持ち主 11/28：数直線から半円の弧がのびていく素数の動画（録画）を見せて「こういうのも作れそう。色と音を組み合わせて美しい。ガラス系の瞑想エコー」
#   まねたのは仕組み（素数の倍数を、弧でつないでいく＝エラトステネスのふるい）だけ。絵・色・字・音は自前：
#     ・数直線をまん中に立て、上から下へ進む。弧は左右に開く（ガラスの玉が2つ、左右に分かれて半円を進み、次の倍数でぶつかる）。だから模様は左右対称の輪のつらなりになる
#     ・素数ごとに色と音を決める（2＝金色でいちばん高い音 … 大きい素数ほど青く、低い音）。輪が大きいほど低い音
#     ・音が鳴るのは、玉が数直線の上でぶつかった瞬間だけ。だれも来ない数（＝素数）では音がしない
#       6 は 2 と 3 の音が重なり、30 は 2・3・5 の3つが重なる（数の中身が和音で聞こえる）
#   決まり：素数 p の玉は、p から出て p ずつ進む（2p, 3p, …に着地）。数直線を進む印が整数に着いた時、だれも着地しなければ、その数は素数。そこから新しい玉が出る
#   進み方：はじめはゆっくり（1秒に2.3個）、カメラが引くにつれて速くなる（最後は1秒に5.6個）
#   音：ガラスの響き（kalimba の glass）＋瞑想のような長いエコー＋裏の低い持続音。音の高さはカノン進行（10個の数ごとに和音が1つ進む：D A Bm F#m G D G A D D）
#   python3 tools/primehop.py stills ／ zoom ／ all（LANG_OUT=en で英語）→ output/primehop1_<ja|en>.mp4
import colorsys, math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS = T.W, T.H, T.FPS
N = 100; R0, R1 = 2.3, 5.6; C = (R1 - R0) / N; T2 = .15                 # 数直線を進む速さ（個/秒）：R0 → R1。T2＝印が 2 に着く時刻
def t_of(n): return T2 + math.log((R0 + C * n) / (R0 + C * 2)) / C
def n_of(t): return ((R0 + C * 2) * math.exp(C * (t - T2)) - R0) / C
TEND = t_of(N); HOLD = 2.9; DUR = TEND + HOLD; NF = int(DUR * FPS)
PR = [p for p in range(2, N + 1) if all(p % q for q in range(2, int(p ** .5) + 1))]; PI = {p: i for i, p in enumerate(PR)}
LAND = sorted((t_of(m), m, PI[p]) for p in PR for m in range(2 * p, N + 1, p)); TL = np.array([e[0] for e in LAND])   # 着地（時刻, 数, 素数の番号）
TB = np.array([t_of(p) for p in PR])                                    # 素数が見つかる時刻
CHS = [0, 1, 2, 3, 4, 5, 6, 7, 0, 0]; CHN = ["D", "A", "Bm", "F#m", "G", "D", "G", "A", "D", "D"]
def chord_of(m): return CHS[min(9, (int(m) - 1) // 10)]
def factors(m):
    f = []; q = 2
    while m > 1:
        while m % q == 0: f.append(q); m //= q
        q += 1
    return f
def color(i):
    """素数ごとの色：2＝金色、3＝橙、5＝紅、7＝桃、11＝紫 … 大きい素数ほど 青 → 水色 → 緑（ガラス玉の色。高い音ほど暖かい色）。はじめの素数ほど、色の差を大きくとる"""
    h = (48 - 27 * i if i <= 4 else 300 - 18 * (i - 4) if i <= 9 else 210 - 6.5 * (i - 9)) % 360; s = .56 - .14 * math.exp(-((h - 245) / 45) ** 2); r, g, b = colorsys.hsv_to_rgb(h / 360, s, 1.0); return (int(r * 255), int(g * 255), int(b * 255))
COL = [color(i) for i in range(len(PR))]

CX, YT, YSW, S0 = 540, 468, 1510, 128.0                                 # 数直線の x、1 の高さ、進む印がとどまる高さ、はじめの大きさ（px/1）
def scale(n): a = YSW - YT; return a / ((max(n, 1.0) - 1) ** 4 + (a / S0) ** 4) ** .25      # はじめは止まっていて、印が下まで来たら引いていく
def cam(t):
    n = min(float(N), n_of(t)); s = scale(n) * (1 - .035 * T.sstep(TEND, DUR, t)); return n, s

def make_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    b = np.array([9, 11, 27], np.float32) * (1 - yy / H)[..., None] + np.array([4, 5, 15], np.float32) * (yy / H)[..., None]
    b += (np.exp(-(((xx - CX) / 520) ** 2 + ((yy - 1000) / 760) ** 2)) * 15)[..., None] * np.array([.75, .85, 1.5], np.float32)
    return (b / 255).astype(np.float32)
BG = make_bg(); RBS = (8, 11, 14)                                      # 玉の半径（カメラが引くと小さくする）
SPR = [[T.sprite(c, rb) for c in COL] for rb in RBS]; GS = T.glow(26); GB = T.glow(40); GD = T.glow(13); ENV = 1 / math.sqrt(8)   # ENV＝模様のふちの傾き（どの素数の最初の輪も、0 を頂点とする同じ2本の直線に接する）
INK = (244, 246, 255, 255); GOLD = (255, 222, 150, 255)

def make_frame(fi):
    t = fi / FPS; n, s = cam(t); buf = BG.copy(); y_of = lambda v: YT + (v - 1) * s; live = t < TEND
    # 1) 弧：できあがった輪と、いま進んでいる半円（大きい素数から描き、小さい素数を上に）
    wth = T.sstep(40, 90, s); cvs = [np.zeros((H, W, 3), np.uint8)] + ([np.zeros((H, W, 3), np.uint8)] if wth > 0 else []); beads = []   # 細い線（2px）と、近い時だけ太い線（4px）
    for i in range(len(PR) - 1, -1, -1):
        p = PR[i]
        if p > n: continue
        r = p / 2 * s; ax = (int(round(r * 16)), int(round(r * 16))); k = 1; dim = float(np.clip(r / 34, .30, 1.0)) ** .8; col = tuple(int(v * dim) for v in COL[i])   # 小さくなった輪は暗めに（まん中が白くつぶれない）
        while k * p <= n:
            cy = y_of((k + .5) * p); ctr = (CX * 16, int(round(cy * 16)))
            for cv, th in zip(cvs, (2, 4)):
                if (k + 1) * p <= n: cv2.ellipse(cv, ctr, ax, 0, 0, 360, col, th, cv2.LINE_AA, 4)
                else:
                    f = (n - k * p) / p
                    if f > 1e-4: cv2.ellipse(cv, ctr, ax, 0, -90, -90 + 180 * f, col, th, cv2.LINE_AA, 4); cv2.ellipse(cv, ctr, ax, 0, 270 - 180 * f, 270, col, th, cv2.LINE_AA, 4)
            if (k + 1) * p > n: ph = math.pi * (n - k * p) / p; beads.append((i, r * math.sin(ph), cy - r * math.cos(ph)))
            k += 1
    c = cvs[0].astype(np.float32) / 255
    if wth > 0: c += (cvs[1].astype(np.float32) / 255 - c) * wth
    g1 = cv2.GaussianBlur(c, (0, 0), 2.4); sm = cv2.resize(c, (W // 4, H // 4), interpolation=cv2.INTER_AREA); g2 = cv2.resize(cv2.GaussianBlur(sm, (0, 0), 4.5), (W, H), interpolation=cv2.INTER_LINEAR)
    buf[:] = 1 - (1 - buf) * (1 - np.clip(c * .95 + g1 * .45 + g2 * .55, 0, 1))
    # 2) 着地の光（ぶつかった瞬間）と、素数が見つかった瞬間の光
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    d.line([(CX, YT - 34), (CX, H if live else min(H, y_of(N) + 60))], fill=(190, 204, 240, 105), width=2)                                                                # 数直線
    nl = int(np.searchsorted(TL, t, "right"))
    for (tl, m, i) in LAND[max(0, nl - 12):nl]:
        e = t - tl
        if e > .5: continue
        y = y_of(m); T.add_glow(buf, GS, CX, y, COL[i], .85 * math.exp(-e / .09)); rr = 12 + (150 + 40 * min(i, 8)) * e ** .75; a = int(190 * (1 - e / .5) ** 1.7)
        if a > 3: d.ellipse([CX - rr, y - rr, CX + rr, y + rr], outline=COL[i] + (a,), width=3)
    nb = int(np.searchsorted(TB, t, "right"))
    for j in range(max(0, nb - 3), nb):
        e = t - TB[j]
        if e < .9: y = y_of(PR[j]); T.add_glow(buf, GB, CX, y, (255, 246, 222), .5 * math.exp(-e / .22)); rr = 16 + 120 * e ** .6; a = int(150 * (1 - e / .9) ** 2); d.ellipse([CX - rr, y - rr, CX + rr, y + rr], outline=(255, 244, 214, a), width=2)
    # 3) 目もり・数字・素数の点
    vmax = int(min(N, n + 16)); a_all = T.sstep(34, 50, s); a5 = T.sstep(13.5, 19, s); fs = int(np.clip(s * .30, 20, 40)); f = T.fnt(fs)
    for v in range(1, vmax + 1):
        y = y_of(v)
        if y > H + 20: break
        passed = v <= n + 1e-9; isp = v in PI
        if not (isp and passed): d.line([(CX - 7, y), (CX + 7, y)], fill=(190, 204, 240, 150 if passed else 70), width=2)
        al = 1.0 if v % 10 == 0 else a5 if v % 5 == 0 else a_all
        if v < n - 3: al *= a_all                                          # 通りすぎた数字は、カメラが引いたら消す（模様にかぶるので）
        if isp and passed: al = max(al, T.sstep(22, 30, s))
        if passed and v % 10 == 0 and a_all < .98:                         # 通りすぎた 10 の倍数は、模様の左のふちに出す
            d.text((CX - ENV * v * s - 14, y), str(v), font=T.fnt(26), fill=(176, 188, 222, int(235 * (1 - a_all) * min(1, (t - t_of(v)) / .4))), anchor="rm")
        if al > .02:
            colr = (COL[PI[v]] if (isp and passed) else (176, 188, 222) if passed else (120, 130, 164)); d.text((CX + 15, y - 5), str(v), font=f, fill=colr + (int(255 * al * (1 if passed else .6)),), anchor="lb", stroke_width=3, stroke_fill=(6, 8, 20, int(230 * al)))
    for j in range(nb):                                                    # 素数の点（見つかった順に残る。最後に、上から順にまたたく）
        p = PR[j]; y = y_of(p); e = t - TB[j]; pop = 1 + .9 * math.exp(-e / .12) * math.cos(e * 22) if e < .6 else 1.0; rd = float(np.clip(s * .085, 4.2, 10)) * pop
        tw = math.exp(-(((t - TEND - .5) * 30 - j) / 2.2) ** 2) if t > TEND else 0.0
        T.add_glow(buf, GD, CX, y, COL[j], .55 + .6 * tw); d.ellipse([CX - rd * (1 + .5 * tw), y - rd * (1 + .5 * tw), CX + rd * (1 + .5 * tw), y + rd * (1 + .5 * tw)], fill=(255, 252, 244, 255))
    # 4) ガラスの玉（左右に1つずつ）
    for (i, dx, y) in beads:
        for sx in (-1, 1): T.add_glow(buf, GD, CX + sx * dx, y, COL[i], .5); T.blit(buf, SPR[2 if s > 80 else 1 if s > 30 else 0][i], CX + sx * dx, y)
    y = y_of(n);                                                           # 進む印（数直線の上の小さな輪）
    if True: d.ellipse([CX - 13, y - 13, CX + 13, y + 13], outline=(255, 255, 255, 235 if live else 120), width=3)
    # 5) 字
    T.fit_text(d, (W / 2, 140), T.tr("だれも着地しない数が、素数", "Numbers nobody lands on are prime"), 58, 990, INK)
    T.fit_text(d, (W / 2, 216), T.tr(f"{N}までに、いくつある？", f"How many are there up to {N}?"), 50, 990, GOLD)
    d.text((W / 2, 296), T.tr(f"見つけた素数 {nb}個", f"Primes found: {nb}"), font=T.fnt(44), fill=(226, 232, 250, 255), anchor="mm")
    m = int(math.floor(n + 1e-9))
    if m >= 2:                                                             # いま着いた数の中身（素数のかけ算）。素数の色で書く
        f2 = T.fnt(40); f2m = T.fnt(40, False)
        if m in PI: parts = [(str(m), COL[PI[m]], f2), (T.tr(" は素数", " is prime"), (255, 240, 200), f2m)]
        else:
            parts = [(str(m), (236, 240, 255), f2), (" = ", (170, 180, 210), f2m)]
            for k, q in enumerate(factors(m)): parts += ([(" × ", (170, 180, 210), f2m)] if k else []) + [(str(q), COL[PI[q]], f2)]
        wsum = sum(d.textlength(s_, font=ff) for s_, _, ff in parts); x = W / 2 - wsum / 2
        for s_, cc, ff in parts: d.text((x, 372), s_, font=ff, fill=cc + (255,), anchor="lm"); x += d.textlength(s_, font=ff)
    for (ta, tb, s_) in CAPS:
        if ta <= t < tb: T.fit_text(d, (W / 2, 1772), s_, 44, 990, (255, 232, 170, int(255 * min(1, (t - ta) / .3) * min(1, (tb - t) / .35))))
    out = np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB"))
    g = min(T.sstep(0, .3, t), 1 - T.sstep(DUR - .6, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)
CAPS = [(t_of(3.6), t_of(8.6), T.tr("素数は、自分の数ずつとんでいく", "Each prime hops by its own size")),
        (t_of(10.6), t_of(17.4), T.tr("だれも来ない数では、音がしない", "Where nobody lands, there is no sound")),
        (t_of(29.6), t_of(36.4), T.tr("30 = 2×3×5：3つの音が重なる", "30 = 2×3×5: three notes ring together")),
        (TEND + .25, DUR, T.tr(f"{N}までの素数は、{len(PR)}個", f"There are {len(PR)} primes up to {N}"))]

def pad_var(segs, n_s, gain=.024):
    """裏の低い持続音。segs＝(和音の MIDI の組, はじまり, おわり)。和音ごとに長さがちがう（だんだん速くなるので）"""
    out = np.zeros(n_s, np.float32); fade = .7
    for ms, t0, t1 in segs:
        a = int((t0 - fade / 2) * T.SR); n1 = int((t1 - t0 + fade) * T.SR); tt = np.arange(n1) / T.SR; env = np.minimum(1, tt / fade) * np.minimum(1, (n1 / T.SR - tt) / fade); sg = np.zeros(n1)
        for q, mm in enumerate(ms):
            f = K.mtof(mm); sg += (np.sin(2 * np.pi * f * tt + q) + .7 * np.sin(2 * np.pi * f * 1.0035 * tt + 2 * q)) * (1.0 if f < 300 else .55) / (1 + .3 * q)
        a0, b0 = max(0, a), min(n_s, a + n1)
        if b0 > a0: out[a0:b0] += (sg * env)[a0 - a:b0 - a].astype(np.float32)
    return K._lp(out, 1400) * gain
def audio(path):
    a = T.Audio(DUR, mat="glass", max_same=4, window=.012)
    for (tl, m, i) in LAND:
        tn = K.canon_tones(chord_of(m), 57, 81)                              # 和音の音を高い方から：2 がいちばん高く、大きい素数ほど低い（いちばん低くてもラ(A3)。スマホでも聞こえる高さ）
        a.note(tl, tn[max(0, len(tn) - 1 - i)], vel=min(.80, .50 + .045 * i) * (1.3 - .3 * T.sstep(2, 14, tl)), pan=.35 + .3 * (i % 4) / 3)   # よく鳴る小さい素数ほどやわらかく。音の少ない出だしは少し強めに
    segs = []
    for j in range(9):
        r, t3, f5 = K.CANON[CHS[j]]; segs.append(((r, r + 12, f5 + 12), 0.0 if j == 0 else t_of(10 * j + .5), DUR if j == 8 else t_of(10 * j + 10.5)))
    under = pad_var(segs, int(T.SR * DUR)); under *= np.clip((DUR - np.arange(len(under)) / T.SR) / 1.5, 0, 1).astype(np.float32)
    return a.write(path, room=(.32, 3.2), under=under)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_primehop", exist_ok=True)
    print("長さ", round(DUR, 1), "素数", len(PR), "着地", len(LAND), "100 に着く", round(TEND, 2), "10ごとの時刻", [round(t_of(v), 1) for v in range(10, 101, 10)])
    if cmd == "stills": print(T.stills(NF, make_frame, "build_primehop/s", at=(t_of(4.4) / DUR, t_of(9.5) / DUR, t_of(30.03) / DUR, t_of(62.5) / DUR, (TEND + 1.2) / DUR))); sys.exit()
    if cmd == "zoom":
        for name, tt_, box in (("a", t_of(6.05), (0, 380, 1080, 1700)), ("b", t_of(30.04), (140, 900, 940, 1700)), ("c", TEND + 1.0, (60, 420, 1020, 1800))):
            Image.fromarray(make_frame(int(tt_ * FPS))).crop(box).save(f"build_primehop/z_{name}.png")
        sys.exit()
    if cmd == "audio": print(audio("build_primehop/a.wav")); sys.exit()
    out = f"output/primehop1_{T.LANG}.mp4"; audio("build_primehop/a.wav"); T.encode(NF, make_frame, "build_primehop/a.wav", out); print(out)
