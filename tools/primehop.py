# primehop.py — 素数が、自分の数ずつとんでいく。だれも着地しない数が、次の素数（エラトステネスのふるい）。着地の音だけで、素数がわかる（縦のショート 1080×1920・60コマ）
#   持ち主 11/28：数直線から半円の弧がのびていく素数の動画（録画）を見せて「こういうのも作れそう。色と音を組み合わせて美しい。ガラス系の瞑想エコー」
#   見本（100まで・29秒）への持ち主の返事 11/28：「感じとしてはめっちゃいい」「素数はもっと長めにやりたいのと最後はスピードアップして、巻き戻しループ入れたいですね」
#     → 1000 まで続ける（100 までは今までの速さ、そこから12秒で 1000 まで一気に速くなる）。最後は早回しで巻きもどり、頭につながる（tools/loopkit.py）
#   持ち主 11/28：「全体の隠し味で鼓動音的なのを入れてみたい。グルーブではなくて調和」→ 和音の根音で、小さな鼓動を入れる（和音1つに2拍）
#   まねたのは仕組み（素数の倍数を、弧でつないでいく＝エラトステネスのふるい）だけ。絵・色・字・音は自前：
#     ・数直線をまん中に立て、上から下へ進む。弧は左右に開く（ガラスの玉が2つ、左右に分かれて半円を進み、次の倍数でぶつかる）。だから模様は左右対称の輪のつらなりになる
#     ・素数ごとに色と音を決める（2＝金色でいちばん高い音 … 大きい素数ほど低い音）。輪が大きいほど低い音
#     ・音が鳴るのは、玉が数直線の上でぶつかった瞬間だけ。だれも来ない数（＝素数）では音がしない
#       6 は 2 と 3 の音が重なり、30 は 2・3・5 の3つが重なる（数の中身が和音で聞こえる）
#   決まり：素数 p の玉は、p から出て p ずつ進む（2p, 3p, …に着地）。数直線を進む印が整数に着いた時、だれも着地しなければ、その数は素数。そこから新しい玉が出る
#   進み方：100 までは、1秒に 2.3個 → 5.6個。100 から先は、3秒ごとに約2.7倍の速さになる（最後は1秒に約300個）。速い所は全部の着地は鳴らせないので、時刻の順に間引いて鳴らす
#   音：ガラスの響き（kalimba の glass）＋瞑想のような長いエコー＋裏の低い持続音。音の高さはカノン進行（100 までは数10個ごと、そこから先は1.5秒ごとに和音が1つ進む）
#   python3 tools/primehop.py stills ／ zoom ／ all（LANG_OUT=en で英語）→ output/primehop1_<ja|en>.mp4
import colorsys, math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K
import loopkit as L

W, H, FPS = T.W, T.H, T.FPS
N1, N = 100, 1000; R0, R1 = 2.3, 5.6; C = (R1 - R0) / N1; T2 = .15; TAU = 3.0   # 100 までの速さ（個/秒）：R0 → R1。T2＝印が 2 に着く時刻。TAU＝100 から先で速さが e 倍になる秒数
def _t1(n): return T2 + math.log((R0 + C * n) / (R0 + C * 2)) / C
T100 = _t1(N1); D2 = TAU * math.log(1 + (N - N1) / (R1 * TAU)); TEND = T100 + D2
def t_of(n): return _t1(n) if n <= N1 else T100 + TAU * math.log(1 + (n - N1) / (R1 * TAU))
def n_of(t): return ((R0 + C * 2) * math.exp(C * (t - T2)) - R0) / C if t <= T100 else N1 + R1 * TAU * (math.exp((t - T100) / TAU) - 1)
HOLD, TREW = 1.0, 1.6; DUR = TEND + HOLD + TREW; NF = int(round(DUR * FPS))
PR = [p for p in range(2, N + 1) if all(p % q for q in range(2, int(p ** .5) + 1))]; PI = {p: i for i, p in enumerate(PR)}; NP1 = sum(1 for p in PR if p <= N1)
LAND = sorted((t_of(m), m, PI[p]) for p in PR for m in range(2 * p, N + 1, p)); TL = np.array([e[0] for e in LAND])   # 着地（時刻, 数, 素数の番号）
TB = np.array([t_of(p) for p in PR])                                    # 素数が見つかる時刻
SEG = [(0.0 if j == 0 else t_of(10 * j + .5), t_of(10 * j + 10.5) if j < 9 else T100, [0, 1, 2, 3, 4, 5, 6, 7, 0, 0][j]) for j in range(10)]       # 和音の区切り（はじまり, おわり, カノン進行の何番め）
SEG += [(T100 + 1.5 * k, T100 + 1.5 * (k + 1), k) for k in range(int(round(D2 / 1.5)))]; SEG[-1] = (SEG[-1][0], TEND, SEG[-1][2]); SEG.append((TEND, TEND + HOLD, 0))
SB = np.array([s_[0] for s_ in SEG])
def chord_at(t): return SEG[max(0, int(np.searchsorted(SB, t + 1e-9, "right")) - 1)][2]
def factors(m):
    f = []; q = 2
    while m > 1:
        while m % q == 0: f.append(q); m //= q
        q += 1
    return f
def color(i, deep=0.0):
    """素数ごとの色：2＝金色、3＝橙、5＝紅、7＝桃、11＝紫 … 大きい素数ほど 青 → 水色 → 緑 → …と色の輪を回る（ガラス玉の色）。はじめの素数ほど、色の差を大きくとる。
       deep（0〜1）：線がこみ合ってきたら色を濃くする（うすい色のまま重なると、白っぽくつぶれるので）"""
    h = (48 - 27 * i if i <= 4 else 300 - 18 * (i - 4) if i <= 9 else 210 - 6.5 * (i - 9)) % 360; s = .56 - .14 * math.exp(-((h - 245) / 45) ** 2); s += (.92 - s) * deep; r, g, b = colorsys.hsv_to_rgb(h / 360, s, 1.0 - .12 * deep); return (int(r * 255), int(g * 255), int(b * 255))
COL = [color(i) for i in range(len(PR))]; COLD = [[color(i, k / 4) for i in range(len(PR))] for k in range(5)]

CX, YT, YSW, S0 = 540, 468, 1510, 128.0                                 # 数直線の x、1 の高さ、進む印がとどまる高さ、はじめの大きさ（px/1）
def scale(n): a = YSW - YT; return a / ((max(n, 1.0) - 1) ** 4 + (a / S0) ** 4) ** .25      # はじめは止まっていて、印が下まで来たら引いていく

def make_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    b = np.array([9, 11, 27], np.float32) * (1 - yy / H)[..., None] + np.array([4, 5, 15], np.float32) * (yy / H)[..., None]
    b += (np.exp(-(((xx - CX) / 520) ** 2 + ((yy - 1000) / 760) ** 2)) * 15)[..., None] * np.array([.75, .85, 1.5], np.float32)
    return (b / 255).astype(np.float32)
BG = make_bg(); RBS = (5, 8, 11, 14)                                    # 玉の半径（カメラが引くと小さくする）
_SP = {}
def bead(i, k):
    if (i, k) not in _SP: _SP[(i, k)] = T.sprite(COL[i], RBS[k])
    return _SP[(i, k)]
GS = T.glow(26); GB = T.glow(40); GD = T.glow(13); ENV = 1 / math.sqrt(8)   # ENV＝模様のふちの傾き（どの素数の最初の輪も、0 を頂点とする同じ2本の直線に接する）
INK = (244, 246, 255, 255); GOLD = (255, 222, 150, 255)
def step_th(v, steps):                                                   # きりのいい数ほど、カメラが引いても残す
    th = steps[0][1]
    for st, x in steps:
        if v % st == 0: th = x
    return th
NEAR = ((1, 34.0), (5, 13.5), (10, 6.0), (50, 2.2), (100, 0.0)); EDGE = ((10, 6.0), (50, 2.2), (100, 0.0))

def frame_at(ts, rew=0.0):
    """ts＝中の時刻（0〜TEND）。進む時も巻きもどす時も、同じ絵になる"""
    n = min(float(N), n_of(ts)); s = scale(n); buf = BG.copy(); y_of = lambda v: YT + (v - 1) * s
    crowd = T.sstep(3, 14, s); LC = COLD[int(round(4 * (1 - crowd)))]; rate = (R0 + C * n) if ts <= T100 else R1 * math.exp((ts - T100) / TAU); calm = min(1.0, 9.0 / rate)   # crowd＝線のこみぐあい（1＝すいている）、calm＝速くなるほど、着地の光をひかえる
    # 1) 弧：できあがった輪と、いま進んでいる半円（大きい素数から描き、小さい素数を上に）
    wth = T.sstep(40, 90, s); cvs = [np.zeros((H, W, 3), np.uint8)] + ([np.zeros((H, W, 3), np.uint8)] if wth > 0 else []); beads = []   # 細い線（2px）と、近い時だけ太い線（4px）
    for i in range(len(PR) - 1, -1, -1):
        p = PR[i]
        if p > n: continue
        r = p / 2 * s
        if r < 1.0: continue                                               # 小さすぎて見えない輪は描かない
        ax = (int(round(r * 16)), int(round(r * 16))); k = 1; dim = float(np.clip(r / 34, .30, 1.0)) ** .8; col = tuple(int(v * dim) for v in LC[i])   # 小さくなった輪は暗めに（まん中が白くつぶれない）
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
    gk = .22 + .78 * crowd; buf[:] = 1 - (1 - buf) * (1 - np.clip(c * .95 + g1 * .45 * gk + g2 * .55 * gk, 0, 1))
    # 2) 着地の光（ぶつかった瞬間）と、素数が見つかった瞬間の光
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); done = ts >= TEND - 1e-6
    d.line([(CX, YT - 34), (CX, min(H, y_of(N) + 60) if n > N - 60 else H)], fill=(190, 204, 240, 105), width=2)                          # 数直線
    nl = int(np.searchsorted(TL, ts, "right"))
    for (tl, m, i) in LAND[max(0, nl - 12):nl]:
        e = ts - tl
        if e > .5: continue
        y = y_of(m); T.add_glow(buf, GS, CX, y, COL[i], .85 * calm * math.exp(-e / .09)); rr = 12 + (150 + 40 * min(i, 8)) * e ** .75; a = int(190 * calm * (1 - e / .5) ** 1.7)
        if a > 3: d.ellipse([CX - rr, y - rr, CX + rr, y + rr], outline=COL[i] + (a,), width=3)
    nb = int(np.searchsorted(TB, ts, "right"))
    for j in range(max(0, nb - 3), nb):
        e = ts - TB[j]
        if e < .9: y = y_of(PR[j]); T.add_glow(buf, GB, CX, y, (255, 246, 222), .5 * calm * math.exp(-e / .22)); rr = 16 + 120 * e ** .6; a = int(150 * calm * (1 - e / .9) ** 2); d.ellipse([CX - rr, y - rr, CX + rr, y + rr], outline=(255, 244, 214, a), width=2)
    # 3) 目もり・数字・素数の点
    vmax = int(min(N, n + 16)); a_all = T.sstep(34, 50, s); fs = int(np.clip(s * .30, 20, 40)); f = T.fnt(fs); v0 = 1 if s >= 22 else max(1, int(n) - 4)
    for v in range(v0, vmax + 1):                                           # 線のそばの数字（これから来る数と、通ったばかりの数）
        y = y_of(v)
        if y > H + 20: break
        passed = v <= n + 1e-9; isp = v in PI
        if s >= 5 and not (isp and passed): d.line([(CX - 7, y), (CX + 7, y)], fill=(190, 204, 240, 150 if passed else 70), width=2)
        th = step_th(v, NEAR); al = 1.0 if th <= 0 else T.sstep(th, th * 1.45, s)
        if v < n - 3: al *= a_all                                          # 通りすぎた数字は、カメラが引いたら消す（模様にかぶるので）
        if isp and passed: al = max(al, T.sstep(22, 30, s))
        if al > .02:
            colr = (COL[PI[v]] if (isp and passed) else (176, 188, 222) if passed else (120, 130, 164)); d.text((CX + 15, y - 5), f"{v:,}", font=f, fill=colr + (int(255 * al * (1 if passed else .6)),), anchor="lb", stroke_width=3, stroke_fill=(6, 8, 20, int(230 * al)))
    if a_all < .98:                                                        # 通りすぎた きりのいい数は、模様の左のふちに出す
        for v in range(10, int(n) + 1, 10):
            th = step_th(v, EDGE); al = (1.0 if th <= 0 else T.sstep(th, th * 1.45, s)) * (1 - a_all) * min(1, max(0, ts - t_of(v)) / .4)
            if al > .02: d.text((CX - ENV * v * s - 14, y_of(v)), f"{v:,}", font=T.fnt(26), fill=(176, 188, 222, int(235 * al)), anchor="rm")
    rd = float(np.clip(s * .085, 1.3, 10)); gg = min(1.0, s / 14)
    for j in range(nb):                                                    # 素数の点（見つかった順に残る）
        p = PR[j]; y = y_of(p); e = ts - TB[j]; pop = 1 + .9 * math.exp(-e / .12) * math.cos(e * 22) if e < .6 else 1.0
        if gg > .08: T.add_glow(buf, GD, CX, y, COL[j], .55 * gg)
        d.ellipse([CX - rd * pop, y - rd * pop, CX + rd * pop, y + rd * pop], fill=(255, 252, 244, int(255 * min(1, max(.3, s / 6)))))
    # 4) ガラスの玉（左右に1つずつ）
    kb = 3 if s > 80 else 2 if s > 30 else 1 if s > 8 else 0
    for (i, dx, y) in beads:
        for sx in (-1, 1):
            if kb: T.add_glow(buf, GD, CX + sx * dx, y, COL[i], .5)
            T.blit(buf, bead(i, kb), CX + sx * dx, y)
    y = y_of(n); d.ellipse([CX - 13, y - 13, CX + 13, y + 13], outline=(255, 255, 255, 120 if done else 235), width=3)                    # 進む印（数直線の上の小さな輪）
    # 5) 字
    T.fit_text(d, (W / 2, 140), T.tr("だれも着地しない数が、素数", "Numbers nobody lands on are prime"), 58, 990, INK)
    T.fit_text(d, (W / 2, 216), T.tr(f"{N:,}までに、いくつある？", f"How many are there up to {N:,}?"), 50, 990, GOLD)
    d.text((W / 2, 296), T.tr(f"見つけた素数 {nb}個", f"Primes found: {nb}"), font=T.fnt(44), fill=(226, 232, 250, 255), anchor="mm")
    m = int(math.floor(n + 1e-9))
    if m >= 2:                                                             # いま着いた数の中身（素数のかけ算）。素数の色で書く
        f2 = T.fnt(40); f2m = T.fnt(40, False)
        if m in PI: parts = [(f"{m:,}", COL[PI[m]], f2), (T.tr(" は素数", " is prime"), (255, 240, 200), f2m)]
        else:
            parts = [(f"{m:,}", (236, 240, 255), f2), (" = ", (170, 180, 210), f2m)]
            for k, q in enumerate(factors(m)): parts += ([(" × ", (170, 180, 210), f2m)] if k else []) + [(str(q), COL[PI[q]], f2)]
        wsum = sum(d.textlength(s_, font=ff) for s_, _, ff in parts); x = W / 2 - wsum / 2
        for s_, cc, ff in parts: d.text((x, 372), s_, font=ff, fill=cc + (255,), anchor="lm"); x += d.textlength(s_, font=ff)
    cap = None
    if rew > 0: cap = (T.tr("◀◀ 巻きもどし", "◀◀ Rewind"), 1.0, INK)
    elif done: cap = (T.tr(f"{N:,}までの素数は、{len(PR)}個", f"There are {len(PR)} primes up to {N:,}"), 1.0, (255, 232, 170, 255))
    else:
        for (ta, tb, s_) in CAPS:
            if ta <= ts < tb: cap = (s_, min(1, (ts - ta) / .3) * min(1, (tb - ts) / .35), (255, 232, 170, 255))
    if cap: T.fit_text(d, (W / 2, 1772), cap[0], 44, 990, cap[2][:3] + (int(255 * cap[1]),))
    return np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=int(ts * FPS))).convert("RGBA"), ov).convert("RGB"))
CAPS = [(t_of(3.6), t_of(8.6), T.tr("素数は、自分の数ずつとんでいく", "Each prime hops by its own size")),
        (t_of(10.6), t_of(17.4), T.tr("だれも来ない数では、音がしない", "Where nobody lands, there is no sound")),
        (t_of(29.6), t_of(36.4), T.tr("30 = 2×3×5：3つの音が重なる", "30 = 2×3×5: three notes ring together")),
        (T100 - .2, T100 + 3.2, T.tr(f"{N1}までの素数は{NP1}個。ここから速くなる", f"{NP1} primes up to {N1}. Now it speeds up"))]
def make_frame(fi):
    ts, rew = L.sim_time(fi / FPS, TEND, HOLD, TREW); return frame_at(ts, rew)

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
def voice(t, i): tn = K.canon_tones(chord_at(t), 57, 81); return tn[max(0, len(tn) - 1 - i)]   # 和音の音を高い方から：2 がいちばん高く、大きい素数ほど低い（いちばん低くてもラ(A3)。スマホでも聞こえる高さ）
def audio(path):
    fwd = TEND + HOLD; a = T.Audio(fwd, mat="glass", max_same=4, window=.012); nn = 0
    for (tl, m, i) in LAND:                                                # 100 まで：全部の着地を鳴らす。よく鳴る小さい素数ほどやわらかく。音の少ない出だしは少し強めに
        if m <= N1: a.note(tl, voice(tl, i), vel=min(.80, .50 + .045 * i) * (1.3 - .3 * T.sstep(2, 14, tl)), pan=.35 + .3 * (i % 4) / 3); nn += 1
    t = T100; used = set()                                                 # 100 から先：速すぎて全部は鳴らせない。時刻の順に間引き（1秒に 14 → 26 打まで）、その数のいちばん小さい素数と、いちばん大きい素数の音を鳴らす
    while t < TEND - 1e-6:
        rate = min(R1 * math.exp((t - T100) / TAU), 14 + 12 * (t - T100) / D2); t += 1 / rate; m = int(round(n_of(t)))
        while m in PI or m in used: m += 1
        if m > N: break
        used.add(m); fs_ = sorted(set(factors(m))); tm = t_of(m); last = m == N
        for q, v_ in ((fs_[0], .40), (fs_[-1], .48)) if len(fs_) > 1 else ((fs_[0], .44),): a.note(tm, voice(tm, PI[q]), vel=.8 if last else v_, pan=.35 + .3 * (PI[q] % 4) / 3); nn += 1
    if N not in used:
        for q in sorted(set(factors(N))): a.note(TEND, voice(TEND, PI[q]), vel=.8, pan=.5); nn += 1
    ns = int(T.SR * fwd); under = pad_var([((K.CANON[ci][0], K.CANON[ci][0] + 12, K.CANON[ci][2] + 12), t0, t1) for (t0, t1, ci) in SEG], ns)
    under += L.heartbeat([(tb_, K.CANON[ci][0]) for (t0, t1, ci) in SEG for tb_ in ((t0, (t0 + t1) / 2) if t1 - t0 > 1.2 else (t0,))], ns, T.SR, .085)   # 鼓動：和音1つに2拍（根音）
    under *= np.clip((fwd - np.arange(ns) / T.SR) / .8, 0, 1).astype(np.float32); tmp = path + ".fwd.wav"; a.write(tmp, room=(.32, 3.2), under=under)
    L.add_rewind(tmp, path, TEND, HOLD, TREW, gain=.55); os.remove(tmp); return nn

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_primehop", exist_ok=True)
    print("長さ", round(DUR, 1), "素数", len(PR), f"（{N1}までに{NP1}）", "着地", len(LAND), f"{N1} に着く", round(T100, 2), f"{N} に着く", round(TEND, 2))
    if cmd == "stills": print(T.stills(NF, make_frame, "build_primehop/s", at=(0.0, t_of(9.5) / DUR, t_of(62.5) / DUR, (T100 + 5.0) / DUR, (T100 + 10.0) / DUR, (TEND + .5) / DUR, (TEND + HOLD + .5 * TREW) / DUR))); sys.exit()
    if cmd == "zoom":
        for name, tt_, box in (("a", T100 + 7.0, (60, 420, 1020, 1800)), ("c", TEND + .5, (60, 420, 1020, 1800))): Image.fromarray(make_frame(int(tt_ * FPS))).crop(box).save(f"build_primehop/z_{name}.png")
        sys.exit()
    if cmd == "audio": print(audio("build_primehop/a.wav")); sys.exit()
    out = f"output/primehop1_{T.LANG}.mp4"; audio("build_primehop/a.wav"); T.encode(NF, make_frame, "build_primehop/a.wav", out); print(out)
