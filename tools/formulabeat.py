# formulabeat.py — 数式のグラフを、そのまま音にする。#1〜#7 の数式を1つずつ描き（キック・ベース・ハイハット・クラップ・うねるベース・アルペジオ・和音）、最後の「#∞」で7つの層を重ねてEDMにする（縦のショート）
#   持ち主 11/28：数式のグラフが音になる動画（録画）を見せて「こういうのもチャレンジしてみましょうか　edmっぽい重低音」
#   見本への直し 11/28：「もう少し重低音きかせられる？カノンの和音も電子音っぽいみょーんみたいな音でいい。4回繰り返しが冗長…バリエーションもっと欲しい…全ての音の合体はレイヤーわけしていい」
#     → 1つの数式は8拍（グラフは1回で描き切る）。数式を7つに。和音はずらした鋸波の電子音で、音の頭で高さがすべり落ちる（みょーん）。重低音を太く。#∞ は7つの層を上下に並べて描く
#   持ち主 11/28 の2本目の録画（盛り上げ → 全部が合わさる）を受けて、#7 と #∞ のあいだに「#8 ビルドアップ」（手をたたく位置 x_k = 8 − 16/(k+2) がつまっていく）を入れた
#   まねたのは仕組み（数式 → グラフ → 音。番号つきで次々に出る）だけ。数式・色・字の置き方・音は自前
#   画面の数式が、そのまま音の作り方（x は拍。128 BPM）
#     #1 キック          y = 2e^(−7·mod(x,1)) − 1           … 低い音（高さが落ちるサイン波）の大きさ
#     #2 ベース          y = sgn(sin 2πx) + 0.8·sgn(sin 3πx) … 大きさを音量、正負をオクターブ（カノン進行の根音）
#     #3 ハイハット      y = e^(−30·mod(x+0.5,1))            … 拍の裏の、さーっという音の大きさ
#     #4 クラップ        y = e^(−14·mod(x+1,2))              … 2拍目と4拍目の、手をたたく音の大きさ
#     #5 うねるベース    y = (1 + cos 2πx)/2                  … 鋸波の低い音の、こもり具合（ワブル）
#     #6 アルペジオ      y = ⌊4·mod(x,1)⌋/3                  … 和音の4つの音のどれを鳴らすか（階段）
#     #7 和音（みょーん） y = e^(−4·mod(x,4))                  … 4拍ごとに、音の高さがすべり落ちて和音に着く量
#     #∞ 7つを重ねる（キックのたびに、ほかの音を少し下げる）。最後の8拍は手拍子・光で盛り上げ、和音が A → D に着いて終わる
#   python3 tools/formulabeat.py stills ／ all（LANG_OUT=en で英語）→ output/formulabeat1_<ja|en>.mp4
import math, os, sys, io, wave
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS, SR = T.W, T.H, T.FPS, T.SR
BPM = 128.0; BT = 60 / BPM; NB = 8; NS = 7; NALL = 16                   # 1拍の秒、1つの数式の拍数、数式の数、#∞ の拍数（このあと4拍をテンポ半分）
INTRO = .3; T0 = [INTRO + BT * NB * i for i in range(NS + 2)]; TB1 = T0[NS]; TALL = T0[NS + 1]   # #1〜#7 を1つずつ → #8 ビルドアップ（持ち主 11/28「♾️に入る前のビルドアップも欲しい」）→ #∞
TB = TALL + NALL * BT; TDROP = TB + 8 * BT; TEND = TDROP + 16 * BT; DUR = TEND + 2.6; NF = int(DUR * FPS)
#   #∞ の中で盛り上げる（持ち主 11/28「♾️になってからビルドアップしたくて、最後なんか尻すぼみで終わる感じが嫌」）：
#   #∞（16拍）→ ビルドアップ（8拍。手拍子の位置 x_k = 8 − 16/(k+2) がつまり、さーっと上がる）→ ドロップ（16拍。全部の層＋細かいハイハット・光）
#   → カノン進行の ソ・レ・ソ・ラ から レ に着いた所で、全部がそろって和音を鳴らして終わる。テンポは最後まで同じ
BXK = [0.0]
for k_ in range(1, 60):
    v_ = 8 - 16 / (k_ + 2)
    if v_ - BXK[-1] < .07: break
    BXK.append(v_)
BXK = np.array(BXK)                                                     # 手をたたく位置 x_k = 8 − 16/(k+2)：だんだん間がつまって、8に近づく（#8）
R2 = np.array([k * .5 for k in range(8)] + [4 + k * .25 for k in range(16)])   # #∞ の中のビルドアップ：8分 → 16分
COL = [(246, 196, 108), (236, 128, 108), (120, 200, 210), (240, 160, 180), (150, 210, 140), (130, 160, 240), (186, 140, 230), (255, 236, 200)]
def beat_x(t): return (min(t, TEND) - INTRO) / BT                    # 終わった所で止まる
def f_kick(x): return 2 * np.exp(-7 * np.mod(x, 1)) - 1
def f_bass(x): return np.sign(np.sin(2 * np.pi * x)) + .8 * np.sign(np.sin(3 * np.pi * x))
def f_hat(x): return np.exp(-30 * np.mod(x + .5, 1))
def f_clap(x): return np.exp(-14 * np.mod(x + 1, 2))
def f_wob(x): return (1 + np.cos(2 * np.pi * x)) / 2
def f_arp(x): return np.floor(4 * np.mod(x, 1)) / 3
def f_glide(x): return np.exp(-4 * np.mod(x, 4))
FN = [f_kick, f_bass, f_hat, f_clap, f_wob, f_arp, f_glide]
RNG = [(-1, 1), (-1.8, 1.8), (0, 1), (0, 1), (0, 1), (0, 1), (0, 1)]    # グラフの縦の範囲
TEX = [r"$y=2e^{-7\,\mathrm{mod}(x,1)}-1$", r"$y=\mathrm{sgn}(\sin 2\pi x)+0.8\,\mathrm{sgn}(\sin 3\pi x)$", r"$y=e^{-30\,\mathrm{mod}(x+0.5,\,1)}$", r"$y=e^{-14\,\mathrm{mod}(x+1,\,2)}$",
       r"$y=\frac{1+\cos 2\pi x}{2}$", r"$y=\frac{\lfloor 4\,\mathrm{mod}(x,1)\rfloor}{3}$", r"$y=e^{-4\,\mathrm{mod}(x,4)}$"]
NAME = [("キック", "Kick"), ("ベース", "Bass"), ("ハイハット", "Hi-hat"), ("クラップ", "Clap"), ("うねるベース", "Wobble bass"), ("アルペジオ", "Arpeggio"), ("和音", "Chords")]
def tex_img(s, col):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    matplotlib.rcParams["mathtext.fontset"] = "cm"; fig = plt.figure(figsize=(10, 1.6), dpi=100); fig.patch.set_alpha(0)
    fig.text(.5, .5, s, ha="center", va="center", fontsize=34, color=np.array(col) / 255); buf = io.BytesIO(); fig.savefig(buf, format="png", transparent=True, dpi=100); plt.close(fig)
    im = Image.open(buf).convert("RGBA"); bb = im.getbbox(); return im.crop(bb) if bb else im
TEXI = [tex_img(TEX[i], COL[i]) for i in range(NS)]; TEXB = tex_img(r"$x_k=8-\frac{16}{k+2}\ \longrightarrow\ 8$", COL[7])

GX0, GX1 = 70, 1010
def make_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); return ((np.array([10, 10, 20], np.float32) * (1 - yy / H)[..., None] + np.array([4, 4, 10], np.float32) * (yy / H)[..., None]) / 255).astype(np.float32)
BG = make_bg(); GS = T.glow(16); INK = (244, 246, 255, 255)
def sec_at(t):
    for i in range(NS + 1, -1, -1):
        if t >= T0[i]: return i
    return 0
def plot(d, buf, i, x0, x, yc, ga, w=4):
    """数式 i のグラフを、x0 から x まで（8拍で横いっぱい）"""
    xs = np.linspace(x0, max(x0 + 1e-3, x), max(2, int((x - x0) * 160))); lo, hi = RNG[i]; ys = (np.clip(FN[i](xs), lo, hi) - (lo + hi) / 2) / ((hi - lo) / 2)
    px = GX0 + (xs - x0) / NB * (GX1 - GX0); py = yc - ys * ga; pts = list(zip(px.tolist(), py.tolist())); c = COL[i]
    if len(pts) > 1: d.line(pts, fill=c + (80,), width=w + 5, joint="curve"); d.line(pts, fill=c + (255,), width=w, joint="curve")
    T.add_glow(buf, GS, pts[-1][0], pts[-1][1], c, .55); r = 4 + w; d.ellipse([pts[-1][0] - r, pts[-1][1] - r, pts[-1][0] + r, pts[-1][1] + r], fill=(255, 255, 255, 255))
def make_frame(fi):
    t = fi / FPS; buf = BG.copy(); i = sec_at(t); x = beat_x(t); ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    T.fit_text(d, (W / 2, 140), T.tr("数式のグラフを、そのまま音にすると？", "What if a formula's graph were the sound?"), 58, 1000, INK)
    if i < NS:                                                           # 1つずつ：大きなグラフ1つ、8拍で描き切る
        x0 = (T0[i] - INTRO) / BT; d.line([(GX0, 900), (GX1, 900)], fill=(80, 84, 110, 150), width=2)
        for k in range(1, NB): xx_ = GX0 + (GX1 - GX0) * k / NB; d.line([(xx_, 892), (xx_, 908)], fill=(80, 84, 110, 150), width=2)
        if t >= INTRO: plot(d, buf, i, x0, x, 900, 230)
        d.text((W / 2, 300), f"#{i + 1}", font=T.fnt(110), fill=COL[i] + (255,), anchor="mm"); d.text((W / 2, 400), T.tr(NAME[i][0], NAME[i][1]), font=T.fnt(44), fill=(220, 224, 240, 255), anchor="mm")
        im = TEXI[i]; sc_ = min(2.2, 940 / im.width, 150 / im.height); im2 = im.resize((int(im.width * sc_), int(im.height * sc_)), Image.LANCZOS); ov.alpha_composite(im2, (int(W / 2 - im2.width / 2), 1260))
    elif i == NS:                                                        # #8 ビルドアップ：手をたたく位置が、だんだんつまって8に近づく
        xb = x - (TB1 - INTRO) / BT; c = COL[7]; d.line([(GX0, 1100), (GX1, 1100)], fill=(80, 84, 110, 150), width=2)
        for k in range(1, NB + 1): xx_ = GX0 + (GX1 - GX0) * k / NB; d.line([(xx_, 1092), (xx_, 1108)], fill=(80, 84, 110, 150), width=2)
        for k, v in enumerate(BXK):
            if v > xb: break
            px = GX0 + v / NB * (GX1 - GX0); hh = 60 + 520 * (k / (len(BXK) - 1)) ** 1.3; fresh = math.exp(-(xb - v) * 6)
            d.line([(px, 1100), (px, 1100 - hh)], fill=c + (int(120 + 135 * fresh),), width=6); T.add_glow(buf, GS, px, 1100 - hh, c, .25 + .5 * fresh)
        d.text((W / 2, 300), "#8", font=T.fnt(110), fill=c + (255,), anchor="mm"); d.text((W / 2, 400), T.tr("ビルドアップ", "Build-up"), font=T.fnt(44), fill=(220, 224, 240, 255), anchor="mm")
        im = TEXB; sc_ = min(2.2, 940 / im.width, 150 / im.height); im2 = im.resize((int(im.width * sc_), int(im.height * sc_)), Image.LANCZOS); ov.alpha_composite(im2, (int(W / 2 - im2.width / 2), 1260))
        buf = buf + np.float32(.05 * min(1.0, xb / 8) ** 2)
    else:                                                                # #∞：7つの層を上下に並べる。途中でビルドアップ → ドロップ
        x0 = math.floor((x - 1e-6) / NB) * NB; x0 = min(x0, x); dp = TDROP <= t; fin = t >= TEND
        pulse = math.exp(-(x % 1) * 5) if (dp and not fin) else 0.0; ub = min(1.0, max(0.0, (t - TB) / (8 * BT)))
        sz = 110 * (1 + .10 * ub * (t < TDROP) + (.18 + .06 * pulse) * dp)
        d.text((W / 2, 290), "#∞", font=T.fnt(int(sz)), fill=COL[7] + (255,), anchor="mm")
        for j in range(NS):
            mute = TB <= t < TDROP and j in (1, 3, 4, 6)                    # ビルドアップの間は、ベース・クラップ・うねるベース・和音がいったん抜ける
            yc = 470 + j * 150; d.line([(GX0, yc), (GX1, yc)], fill=(70, 74, 100, 110), width=1)
            ga = ((8 if mute else 52) + (14 + 8 * pulse) * dp) * (math.exp(-(t - TEND) * 1.4) if fin else 1.0); plot(d, buf, j, x0, x, yc, ga, 3 + 2 * dp)
            d.text((GX0, yc - 58), f"#{j + 1} " + T.tr(NAME[j][0], NAME[j][1]), font=T.fnt(24, False), fill=COL[j] + ((90 if mute else 230),), anchor="lm")
        if TB <= t < TDROP:                                              # 2回目のビルドアップ：手拍子が8分 → 16分につまっていく（下の棒）
            xb = x - (TB - INTRO) / BT; c = COL[7]; yb0 = 1640; d.line([(GX0, yb0), (GX1, yb0)], fill=(80, 84, 110, 150), width=2)
            for k, v in enumerate(R2):
                if v > xb: break
                px = GX0 + v / NB * (GX1 - GX0); hh = 20 + 170 * (k / (len(R2) - 1)) ** 1.3; fresh = math.exp(-(xb - v) * 6)
                d.line([(px, yb0), (px, yb0 - hh)], fill=c + (int(120 + 135 * fresh),), width=5); T.add_glow(buf, GS, px, yb0 - hh, c, .2 + .45 * fresh)
            buf = buf + np.float32(.05 * ub * ub)
    if TDROP <= t < TEND: buf = buf + np.float32(.09 * math.exp(-(x % 1) * 5))                            # ドロップの間は、拍ごとに画面が光る
    if t >= TEND: buf = buf + np.float32(.07 * math.exp(-(t - TEND) * 2.0))                                # 着いた所で、少しだけ光って静かに消える
    out = np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB"))
    g = min(T.sstep(0, .25, t), 1 - T.sstep(DUR - 1.0, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)

def saw(ph): return 2 * (np.mod(ph, 1.0)) - 1
def synth(path):
    N = int(SR * DUR); tt = np.arange(N) / SR; X = (np.minimum(tt, TEND) - INTRO) / BT; live = (tt >= INTRO) & (tt < TEND)
    sec = np.clip(np.searchsorted(np.array(T0), tt, "right") - 1, 0, NS + 1); inf = (sec == NS + 1) & live; bd1 = (sec == NS) & live; xb1 = X - (TB1 - INTRO) / BT
    bd = (tt >= TB) & (tt < TDROP); dpm = ((tt >= TDROP) & (tt < TEND)).astype(np.float32); xb = X - (TB - INTRO) / BT
    out_b = bd.astype(np.float32)                                                                                  # ビルドアップで抜ける層
    on = lambda k: ((sec == k) | inf) & live
    ci = (X // 4).astype(int) % 8; roots = np.array([K.mtof(K.CANON[c][0] - 12) for c in range(8)])[ci]
    def lp(x, fc): return K._lp(x.astype(np.float32), fc)
    ph = np.mod(X, 1); env = np.clip((f_kick(X) + 1) / 2, 0, 1) ** 1.2; fk = 46 + 120 * np.exp(-ph * 24); kick = np.sin(2 * np.pi * np.cumsum(fk) / SR) * env; kick = np.tanh(kick * 1.6)
    kick += .18 * np.random.default_rng(1).normal(0, 1, N) * np.exp(-ph * 140)
    kick = kick * (1 - out_b * (xb >= 6))                                                                          # ビルドアップの最後の2拍は、キックも止める（ためる）
    yb = f_bass(X); fr = roots * np.where(yb > 0, 2.0, 1.0); bass = np.tanh(np.sin(2 * np.pi * np.cumsum(fr) / SR) * 2.4) * (np.abs(yb) / 1.8); bass = lp(bass, 700)
    n = np.random.default_rng(2).normal(0, 1, N).astype(np.float32); hn = lp(lp(n - lp(n, 2600), 4600), 4600); hat = hn * f_hat(X)
    cn = lp(lp(n - lp(n, 900), 3000), 3000); clap = cn * f_clap(X)
    from scipy.signal import lfilter
    pw = np.cumsum(roots) / SR; wsaw = saw(pw) * .6 + saw(pw * 1.007) * .4; cut = 150 + 1400 * f_wob(X); wob = np.zeros(N, np.float32); zi = np.zeros(1)   # うねるベース：こもり具合をまわす
    for k in range(0, N, 256):
        c = math.exp(-2 * math.pi * cut[k] / SR); o, zi = lfilter([1 - c], [1, -c], wsaw[k:k + 256], zi=zi); wob[k:k + 256] = o
    wob = np.tanh(wob * 2.5)
    tones = [np.array([K.mtof(K.canon_tones(c, 62, 88)[q]) for c in range(8)])[ci] for q in range(4)]; idx = np.clip(np.floor(4 * np.mod(X, 1)).astype(int), 0, 3)
    fa = np.choose(idx, tones); arp = saw(np.cumsum(fa) / SR) * np.exp(-np.mod(X * 4, 1) * 5); arp = lp(arp, 2600)
    bend = 2 ** (-f_glide(X) * 7 / 12); chord = np.zeros(N, np.float32)                                              # みょーん：4拍ごとに、少し高い所からすべり落ちる。ずらした鋸波を3本ずつ
    for q in range(3):
        fq = tones[q] / 2 * (2 ** (7 / 12)) * bend
        for det in (-.012, 0, .011): chord += saw(np.cumsum(fq * (1 + det)) / SR) / 9
    chord_b = lp(chord, 3200); chord = lp(chord, 2200)
    duck = 1 - .7 * np.exp(-np.mod(X, 1) * 8) * inf
    G = {"bass": np.where(inf, .30, .38), "hat": np.where(inf, .45, 3.4), "clap": np.where(inf, .5, 4.0), "wob": np.where(inf, .28, .40), "arp": np.where(inf, .22, 1.0), "chord": np.where(inf, .55, 1.1)}   # 1つずつの区間は、聞こえの大きさをそろえる
    keep = 1 - out_b
    mix = kick * on(0) + (bass * G["bass"] * on(1) * keep + hat * G["hat"] * on(2) + clap * G["clap"] * on(3) * keep + wob * G["wob"] * on(4) * keep + arp * G["arp"] * on(5) * (1 + .6 * out_b) + (chord * (1 - dpm) + chord_b * dpm * 1.25) * G["chord"] * on(6) * keep) * duck
    sub = np.sin(2 * np.pi * np.cumsum(roots / 2) / SR); sub = (sub + .3 * np.sin(2 * np.pi * np.cumsum(roots) / SR)) * .55 * (on(1) * .7 + inf * .5 * (1 + .3 * dpm)) * keep * duck   # 重低音（基音の1オクターブ下）
    def build(t0, pos, mask, xb_):                                                                                   # ビルドアップ：決まった位置で手をたたく音（だんだん高く、強く）、さーっと上がる音、鋸波の和音がこもりから開いていく
        roll = np.zeros(N, np.float32)
        for k, v in enumerate(pos):
            a0 = int((t0 + v * BT) * SR); seg = min(N - a0, int(.18 * SR)); u = k / (len(pos) - 1)
            if seg <= 0: continue
            e = np.exp(-np.arange(seg) / SR * 30); roll[a0:a0 + seg] += (n[a0:a0 + seg] - lp(n[a0:a0 + seg], 700 + 1600 * u)) * e * (.5 + .9 * u)
        roll = lp(lp(roll, 3800), 3800) * 2.6
        rise = (n - lp(n, 400)) * np.clip(xb_ / 8, 0, 1) ** 2 * .35; rise = lp(lp(rise, 2600), 2600)
        padb = np.zeros(N, np.float32)
        for q in range(3):
            fq = tones[q] / 2 * (2 ** (np.clip(xb_, 0, 8) / 8 * 2 / 12))
            for det in (-.01, .009): padb += saw(np.cumsum(fq * (1 + det)) / SR) / 6
        opn = np.zeros(N, np.float32); cutb = 300 + 2600 * np.clip(xb_ / 8, 0, 1) ** 2; zi = np.zeros(1)
        for k in range(0, N, 256):
            if not mask[k:k + 256].any(): continue
            c = math.exp(-2 * math.pi * cutb[k] / SR); o, zi = lfilter([1 - c], [1, -c], padb[k:k + 256], zi=zi); opn[k:k + 256] = o
        return ((roll + rise + opn * .9) * mask).astype(np.float32)
    mix = mix + build(TB1, BXK, bd1.astype(np.float32), xb1) + build(TB, R2, out_b, xb)
    mix = mix + (np.sin(2 * np.pi * np.cumsum(roots / 2) / SR) * .3 * bd1 * (1 - np.clip(xb1 / 8, 0, 1))).astype(np.float32)
    xd = X - (TDROP - INTRO) / BT                                                                                    # ドロップ：16分のハイハットと、入った瞬間のシャーン。最後の2拍は手拍子が16分で駆け上がる
    h16 = hn * np.exp(-34 * np.mod(X * 4, 1)) * .55 * dpm
    te0 = np.maximum(tt - TDROP, 0); crash0 = cn * np.exp(-te0 * 2.4) * (tt >= TDROP) * .9
    fill = cn * np.exp(-24 * np.mod(X * 4, 1)) * np.clip((xd - 14) / 2, 0, 1) * 2.2 * dpm
    mix = mix + (h16 + crash0 * (tt < TEND) + fill).astype(np.float32)
    tl = (tt >= TEND).astype(np.float32); te = np.maximum(tt - TEND, 0)                                              # 終わり（持ち主 11/28「最後のじゃーんがダサすぎる。もっと渋い感じで」）：レに着いた所で、ほかの音はすっと止まり、
    r0 = K.mtof(K.CANON[0][0] - 12)                                                                                  #   低いキック1つと、重低音のレ、こもった和音が小さく残って消える
    kz = np.tanh(np.sin(2 * np.pi * np.cumsum(42 + 60 * np.exp(-te * 30)) / SR) * 1.4) * np.exp(-te * 5) * tl * .8
    stab = np.zeros(N, np.float32)
    for m in K.canon_tones(0, 50, 70)[:3]:
        for det in (-.006, .006): stab += saw(np.cumsum(np.full(N, K.mtof(m) * (1 + det))) / SR) / 8
    stab = lp(lp(stab, 700), 700) * np.exp(-te * 1.3) * np.minimum(1, te / .03) * tl * .9
    subz = np.sin(2 * np.pi * r0 / 2 * te) * np.exp(-te * 1.1) * tl * .9
    crash = 0.0
    gain = .80 + .20 * dpm
    mix = ((mix + sub) * gain + kz + stab + subz + crash).astype(np.float32) * np.clip((DUR - tt) / .5, 0, 1)
    st = np.stack([mix + chord * .05 * on(6), mix - chord * .05 * on(6)], 1); st = np.tanh(st * 1.3) / 1.3; st *= .55 / (np.abs(st).max() + 1e-9)
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_formulabeat", exist_ok=True)
    print("長さ", round(DUR, 1), "区切り", [round(v, 2) for v in T0], "ビルドアップ", round(TB1, 2), round(TB, 2), "ドロップ", round(TDROP, 2), "終わり", round(TEND, 2))
    if cmd == "stills": print(T.stills(NF, make_frame, "build_formulabeat/s", at=[(T0[i] + 2.6) / DUR for i in (0, 6)] + [(TB1 + 3.4) / DUR, (TALL + 4) / DUR, (TB + 3.2) / DUR, (TDROP + 2.0) / DUR, (TEND + .3) / DUR])); sys.exit()
    if cmd == "audio": synth("build_formulabeat/a.wav"); sys.exit()
    out = f"output/formulabeat1_{T.LANG}.mp4"; synth("build_formulabeat/a.wav"); T.encode(NF, make_frame, "build_formulabeat/a.wav", out); print(out)
