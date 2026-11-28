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
#     #∞ 7つを重ねる（キックのたびに、ほかの音を少し下げる）。最後の8拍はテンポが上がり、一撃で終わる
#   python3 tools/formulabeat.py stills ／ all（LANG_OUT=en で英語）→ output/formulabeat1_<ja|en>.mp4
import math, os, sys, io, wave
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS, SR = T.W, T.H, T.FPS, T.SR
BPM = 128.0; BT = 60 / BPM; NB = 8; NS = 7; NALL = 16                   # 1拍の秒、1つの数式の拍数、数式の数、#∞ の拍数（このあと4拍をテンポ半分）
INTRO = .3; T0 = [INTRO + BT * NB * i for i in range(NS + 2)]; TB = T0[NS]; TALL = T0[NS + 1];   # #8 ビルドアップ（持ち主 11/28 の2本目の録画：盛り上げてから全部が合わさる）
BXK = [0.0]
for k_ in range(1, 60):
    v_ = 8 - 16 / (k_ + 2)
    if v_ - BXK[-1] < .07: break
    BXK.append(v_)
BXK = np.array(BXK)                                                     # 手をたたく位置 x_k = 8 − 16/(k+2)：だんだん間がつまって、8に近づく
TESC = TALL + NALL * BT; NE = 8; DE = NE * BT / 1.25; TEND = TESC + DE; DUR = TEND + 3.6; NF = int(DUR * FPS)   # 最後の8拍はテンポが1.5倍まで上がり（持ち主 11/28「最後勿体なさすぎる。エスカレーションして終わって」）、和音は A → D に着いて、流れたまま消える（持ち主 11/28「音楽として綺麗に終わらせたい。コードを繋いで。エスカレーションはビート感とか発光感とかエフェクトで」）
TSLOW = TESC
COL = [(246, 196, 108), (236, 128, 108), (120, 200, 210), (240, 160, 180), (150, 210, 140), (130, 160, 240), (186, 140, 230), (255, 236, 200)]
def beat_x(t):
    if t <= TESC: return (t - INTRO) / BT
    xe = (TESC - INTRO) / BT
    if t <= TEND: u = (t - TESC) / DE; return xe + DE / BT * (u + .25 * u * u)
    return xe + NE + (t - TEND) * 1.5 / BT                                  # 終わったあとも同じ速さで進む（線は音と一緒に平らになっていく）
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
        xb = x - (TB - INTRO) / BT; c = COL[7]; d.line([(GX0, 1100), (GX1, 1100)], fill=(80, 84, 110, 150), width=2)
        for k in range(1, NB + 1): xx_ = GX0 + (GX1 - GX0) * k / NB; d.line([(xx_, 1092), (xx_, 1108)], fill=(80, 84, 110, 150), width=2)
        for k, v in enumerate(BXK):
            if v > xb: break
            px = GX0 + v / NB * (GX1 - GX0); hh = 60 + 520 * (k / (len(BXK) - 1)) ** 1.3; fresh = math.exp(-(xb - v) * 6)
            d.line([(px, 1100), (px, 1100 - hh)], fill=c + (int(120 + 135 * fresh),), width=6); T.add_glow(buf, GS, px, 1100 - hh, c, .25 + .5 * fresh)
        d.text((W / 2, 300), "#8", font=T.fnt(110), fill=c + (255,), anchor="mm"); d.text((W / 2, 400), T.tr("ビルドアップ", "Build-up"), font=T.fnt(44), fill=(220, 224, 240, 255), anchor="mm")
        im = TEXB; sc_ = min(2.2, 940 / im.width, 150 / im.height); im2 = im.resize((int(im.width * sc_), int(im.height * sc_)), Image.LANCZOS); ov.alpha_composite(im2, (int(W / 2 - im2.width / 2), 1260))
    else:                                                                # #∞：7つの層を上下に並べる
        x0 = math.floor((x - 1e-6) / NB) * NB; x0 = min(x0, x); ue = min(1.0, max(0.0, (t - TESC) / DE)); hitf = 1.0 if t >= TEND else 0.0
        d.text((W / 2, 290), "#∞", font=T.fnt(int(110 * (1 + .18 * ue * (1 - hitf) + .18 * hitf))), fill=COL[7] + (255,), anchor="mm")
        for j in range(NS):
            yc = 470 + j * 150; d.line([(GX0, yc), (GX1, yc)], fill=(70, 74, 100, 110), width=1); plot(d, buf, j, x0, x, yc, (52 + 16 * ue) * (math.exp(-(t - TEND) * .9) if t >= TEND else 1.0), 3 + int(2 * ue))
            d.text((GX0, yc - 58), f"#{j + 1} " + T.tr(NAME[j][0], NAME[j][1]), font=T.fnt(24, False), fill=COL[j] + (230,), anchor="lm")
    if TESC <= t < TEND: ue_ = (t - TESC) / DE; buf = buf + np.float32(.10 * ue_ * math.exp(-((x % 1)) * 5))      # 加速中は、拍ごとに画面が光る（だんだん強く）
    if t >= TEND: buf = buf + np.float32(.12 * math.exp(-(t - TEND) * 1.2))                                   # 着いた所で、やわらかく光って消えていく
    out = np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB"))
    g = min(T.sstep(0, .25, t), 1 - T.sstep(DUR - 1.0, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)

def saw(ph): return 2 * (np.mod(ph, 1.0)) - 1
def synth(path):
    N = int(SR * DUR); tt = np.arange(N) / SR; X = np.interp(tt, tt[::64], np.array([beat_x(v) for v in tt[::64]])); live = (tt >= INTRO) & (tt < TEND)
    X = np.where(tt > TEND, (TESC - INTRO) / BT + NE + (tt - TEND) * 1.5 / BT, X)                                   # 終わったあとも、音の拍は同じ速さで進む（和音・アルペジオが流れたまま消える）
    sec = np.clip(np.searchsorted(np.array(T0), tt, "right") - 1, 0, NS + 1); al = sec == NS + 1; bd = (sec == NS) & live; on = lambda k: ((sec == k) | al) & live
    ci = np.where(tt > TEND, 0, (X // 4).astype(int) % 8); roots = np.array([K.mtof(K.CANON[c][0] - 12) for c in range(8)])[ci]
    def lp(x, fc): return K._lp(x.astype(np.float32), fc)
    ph = np.mod(X, 1); env = np.clip((f_kick(X) + 1) / 2, 0, 1) ** 1.2; fk = 46 + 120 * np.exp(-ph * 24); kick = np.sin(2 * np.pi * np.cumsum(fk) / SR) * env; kick = np.tanh(kick * 1.6)
    kick += .18 * np.random.default_rng(1).normal(0, 1, N) * np.exp(-ph * 140)
    yb = f_bass(X); fr = roots * np.where(yb > 0, 2.0, 1.0); bass = np.tanh(np.sin(2 * np.pi * np.cumsum(fr) / SR) * 2.4) * (np.abs(yb) / 1.8); bass = lp(bass, 700)
    n = np.random.default_rng(2).normal(0, 1, N).astype(np.float32); hat = lp(lp(n - lp(n, 2600), 4600), 4600) * f_hat(X)
    clap = lp(lp(n - lp(n, 900), 3000), 3000) * f_clap(X)
    from scipy.signal import lfilter
    pw = np.cumsum(roots) / SR; wsaw = saw(pw) * .6 + saw(pw * 1.007) * .4; cut = 150 + 1400 * f_wob(X); wob = np.zeros(N, np.float32); zi = np.zeros(1)   # うねるベース：こもり具合をまわす
    for k in range(0, N, 256):
        c = math.exp(-2 * math.pi * cut[k] / SR); o, zi = lfilter([1 - c], [1, -c], wsaw[k:k + 256], zi=zi); wob[k:k + 256] = o
    wob = np.tanh(wob * 2.5)
    tones = [np.array([K.mtof(K.canon_tones(c, 62, 88)[q]) for c in range(8)])[ci] for q in range(4)]; idx = np.clip(np.floor(4 * np.mod(X, 1)).astype(int), 0, 3)
    fa = np.choose(idx, tones); arp = saw(np.cumsum(fa) / SR) * np.exp(-np.mod(X * 4, 1) * 5); arp = lp(arp, 2600)
    bend = 2 ** (-np.where(tt > TEND + 4 * BT / 1.5, 0.0, f_glide(X)) * 7 / 12); chord = np.zeros(N, np.float32)                                              # みょーん：4拍ごとに、少し高い所からすべり落ちる。ずらした鋸波を3本ずつ
    for q in range(3):
        fq = tones[q] / 2 * (2 ** (7 / 12)) * bend
        for det in (-.012, 0, .011): chord += saw(np.cumsum(fq * (1 + det)) / SR) / 9
    chord = lp(chord, 2200)
    duck = 1 - .7 * np.exp(-np.mod(X, 1) * 8) * al
    G = {"bass": np.where(al, .30, .38), "hat": np.where(al, .45, 3.4), "clap": np.where(al, .5, 4.0), "wob": np.where(al, .28, .40), "arp": np.where(al, .22, 1.0), "chord": np.where(al, .55, 1.1)}   # 1つずつの区間は、聞こえの大きさをそろえる
    mix = kick * on(0) + (bass * G["bass"] * on(1) + hat * G["hat"] * on(2) + clap * G["clap"] * on(3) + wob * G["wob"] * on(4) + arp * G["arp"] * on(5) + chord * G["chord"] * on(6)) * duck
    sub = np.sin(2 * np.pi * np.cumsum(roots / 2) / SR); sub = (sub + .3 * np.sin(2 * np.pi * np.cumsum(roots) / SR)) * .55 * (on(1) * .7 + al * .5) * duck   # 重低音（基音の1オクターブ下）。小さいスピーカーでも聞こえるよう、倍音を少し
    xb = X - (TB - INTRO) / BT; roll = np.zeros(N, np.float32)                                                        # ビルドアップ：x_k ごとに手をたたく音。だんだん高く、強く。下で鋸波の和音がこもりから開いていく
    for k, v in enumerate(BXK):
        a0 = int((TB + v * BT) * SR); seg = min(N - a0, int(.18 * SR)); u = k / (len(BXK) - 1)
        if seg <= 0: continue
        e = np.exp(-np.arange(seg) / SR * 30); roll[a0:a0 + seg] += (n[a0:a0 + seg] - lp(n[a0:a0 + seg], 700 + 1600 * u)) * e * (.5 + .9 * u)
    roll = lp(lp(roll, 3800), 3800) * 2.6
    rise = (n - lp(n, 400)) * np.clip(xb / 8, 0, 1) ** 2 * .35; rise = lp(lp(rise, 2600), 2600)
    padb = np.zeros(N, np.float32)
    for q in range(3):
        fq = tones[q] / 2 * (2 ** (np.clip(xb, 0, 8) / 8 * 2 / 12))
        for det in (-.01, .009): padb += saw(np.cumsum(fq * (1 + det)) / SR) / 6
    opn = np.zeros(N, np.float32); m_ = bd.astype(np.float32); cutb = 300 + 2600 * np.clip(xb / 8, 0, 1) ** 2; zi = np.zeros(1)
    for k in range(0, N, 256):
        if not bd[k:k + 256].any(): continue
        c = math.exp(-2 * math.pi * cutb[k] / SR); o, zi = lfilter([1 - c], [1, -c], padb[k:k + 256], zi=zi); opn[k:k + 256] = o
    mix = mix + ((roll + rise + opn * .9) * m_).astype(np.float32) + (sub * 0 + np.sin(2 * np.pi * np.cumsum(roots / 2) / SR) * .3 * m_ * (1 - np.clip(xb / 8, 0, 1))).astype(np.float32)
    es = ((tt >= TESC) & (tt < TEND)).astype(np.float32); ue = np.clip((tt - TESC) / DE, 0, 1)                   # 最後の8拍：8分 → 16分の手拍子が速まり、さーっという音が上がる
    mrate = np.where(ue < .5, 2.0, 4.0); clr = lp(lp(n - lp(n, 1100), 3200), 3200) * np.exp(-26 * np.mod(X * mrate, 1)) * (.4 + 1.1 * ue) * 1.6
    rise2 = lp(lp((n - lp(n, 500)) * ue ** 2 * .5, 2400), 2400)
    mix = mix + ((clr + rise2) * es).astype(np.float32)
    tl = (tt >= TEND).astype(np.float32); sub = sub * (1 - tl); te = np.maximum(tt - TEND, 0); envT = np.exp(-te * .9) * tl                # 終わり：テンポの上がった流れのまま、和音が A → D に着いて（カノン進行の最後と最初）、ゆっくり消える
    kz = np.tanh(np.sin(2 * np.pi * np.cumsum(44 + 100 * np.exp(-te * 22)) / SR) * 1.6) * np.exp(-te * 6) * tl * .9    # 着いた所で、やわらかいキック1つ
    crash = lp(lp(n - lp(n, 1200), 3400), 3400) * np.exp(-te * 2.2) * tl * .5                                       # さーっと広がって消える音
    tailmix = chord * 1.0 * envT + arp * .35 * np.exp(-te * 1.4) * tl + sub * 0 + np.sin(2 * np.pi * np.cumsum(roots / 2) / SR) * .55 * envT
    mix = ((mix + sub) * (.80 + .20 * ue) + tailmix + kz + crash).astype(np.float32) * np.clip((DUR - tt) / .6, 0, 1)   # 加速する8拍で、全体の大きさも少しずつ上がる
    st = np.stack([mix + chord * .05 * on(6), mix - chord * .05 * on(6)], 1); st = np.tanh(st * 1.3) / 1.3; st *= .55 / (np.abs(st).max() + 1e-9)
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_formulabeat", exist_ok=True)
    print("長さ", round(DUR, 1), "区切り", [round(v, 2) for v in T0], "加速", round(TESC, 2), "終わり", round(TEND, 2))
    if cmd == "stills": print(T.stills(NF, make_frame, "build_formulabeat/s", at=[(T0[i] + 2.6) / DUR for i in (0, 4, 6)] + [(TB + 3.5) / DUR] + [(TALL + 4) / DUR, (TESC + DE * .8) / DUR, (TEND + .15) / DUR])); sys.exit()
    if cmd == "audio": synth("build_formulabeat/a.wav"); sys.exit()
    out = f"output/formulabeat1_{T.LANG}.mp4"; synth("build_formulabeat/a.wav"); T.encode(NF, make_frame, "build_formulabeat/a.wav", out); print(out)
