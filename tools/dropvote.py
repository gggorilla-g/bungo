# dropvote.py — 数式のグラフで鳴らすベースの「ドロップ」を5つ。どれで机がゆれた？（コメントで番号を答えてもらう）（縦のショート）
#   持ち主 11/28：「Drop #4 should actually be illegal / Which drop rattled your desk? (1-4)」の録画を見せて「これけい」
#   まねたのは仕組み（数式のグラフ → ベースの音。番号つきのドロップを並べて、どれが一番かを聞く）だけ。数式・色・字・音は自前（formulabeat の続き）
#   5つとも、うしろのキック・クラップ・ハイハット・和音は同じ。ちがうのはベースだけ（グラフの y がベースの何を動かすか）
#     #1 y = sgn(sin 4πx)                         … 8分で、鳴る／止まる
#     #2 y = ⌊4·mod(x,1)⌋/1.5 − 1                 … 16分の階段で、音の高さが 0・5・7・12 半音と上がる
#     #3 y = sin 3πx                              … こもり具合がうねる（3連のワブル）
#     #4 y = 2e^(−3·mod(x,1)) − 1                 … 拍ごとに1オクターブ上からすべり落ちる（808）
#     #5 y = sgn(sin 4πx)·(2e^(−3·mod(x,1)) − 1)  … #1 と #4 のかけ算。止まりながら、すべり落ちる。いちばん重く、画面もゆれる
#   最初から #∞ で重ねる前提の編曲：5つのベースは音域とリズムを分けておく（#1 低めの8分・#2 高い16分・#3 まん中のうねり・#4 重低音・#5 まん中の刻み）
#   #5 のあと、ビルドアップ（手をたたく位置 x_k = 8 − 16/(k+2)）→ #∞。#∞ は左右に分ける（#1・#3 は左、#2・#5 は右、#4 はまん中）
#   和音は Dm・B♭・F・C（2拍ずつ）。140 BPM。x は拍
#   python3 tools/dropvote.py stills ／ all（LANG_OUT=en で英語）→ output/dropvote1_<ja|en>.mp4
import math, os, sys, io, wave
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS, SR = T.W, T.H, T.FPS, T.SR
BPM = 140.0; BT = 60 / BPM; NB = 8; ND = 5; INTRO = .15
T0 = [INTRO + BT * NB * i for i in range(ND + 1)]; TB = T0[ND]; TALL = TB + 8 * BT; TEND = TALL + 16 * BT; DUR = TEND + 1.9;   # #5 のあとにビルドアップ（8拍）→ #∞   # 最後に #∞：5つのベースを、高さをずらして重ねて一緒に鳴らす（持ち主 11/28「最後レイヤーで一緒に演奏するの好き」）
NF = int(DUR * FPS)
COL = [(150, 140, 255), (120, 190, 255), (110, 230, 200), (255, 170, 120), (255, 96, 150)]
def f1(x): return np.sign(np.sin(4 * np.pi * x))
def f2(x): return np.floor(4 * np.mod(x, 1)) / 1.5 - 1
def f3(x): return np.sin(3 * np.pi * x)
def f4(x): return 2 * np.exp(-3 * np.mod(x, 1)) - 1
def f5(x): return f1(x) * f4(x)
FN = [f1, f2, f3, f4, f5]
TEX = [r"$y=\mathrm{sgn}(\sin 4\pi x)$", r"$y=\frac{\lfloor 4\,\mathrm{mod}(x,1)\rfloor}{1.5}-1$", r"$y=\sin 3\pi x$", r"$y=2e^{-3\,\mathrm{mod}(x,1)}-1$",
       r"$y=\mathrm{sgn}(\sin 4\pi x)\cdot(2e^{-3\,\mathrm{mod}(x,1)}-1)$"]
def tex_img(s, col):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    matplotlib.rcParams["mathtext.fontset"] = "cm"; fig = plt.figure(figsize=(11, 1.6), dpi=100); fig.patch.set_alpha(0)
    fig.text(.5, .5, s, ha="center", va="center", fontsize=34, color=np.array(col) / 255); buf = io.BytesIO(); fig.savefig(buf, format="png", transparent=True, dpi=100); plt.close(fig)
    im = Image.open(buf).convert("RGBA"); bb = im.getbbox(); return im.crop(bb) if bb else im
TEXI = [tex_img(TEX[i], COL[i]) for i in range(ND)]; TEXBI = tex_img(r"$x_k=8-\frac{16}{k+2}\ \longrightarrow\ 8$", (255, 236, 210))
GX0, GX1, GY = 60, 1020, 900; TALL_X = (TALL - INTRO) / BT
def make_bg():
    yy = np.mgrid[0:H, 0:W][0].astype(np.float32); return ((np.array([10, 8, 20], np.float32) * (1 - yy / H)[..., None] + np.array([3, 3, 8], np.float32) * (yy / H)[..., None]) / 255).astype(np.float32)
BG = make_bg(); GS = T.glow(18); INK = (244, 246, 255, 255)
BXK = [0.0]
for k_ in range(1, 60):
    v_ = 8 - 16 / (k_ + 2)
    if v_ - BXK[-1] < .07: break
    BXK.append(v_)
BXK = np.array(BXK)                                                     # ビルドアップで手をたたく位置 x_k = 8 − 16/(k+2)
TEXB = None
def sec_at(t): return ND + 1 if t >= TALL else (ND if t >= TB else int(min(ND - 1, max(0, (t - INTRO) // (BT * NB)))))
def shake(t):
    """#4 と #5 は、キックのたびに画面がゆれる（#5 は大きく）"""
    i = sec_at(t); x = (min(t, TEND) - INTRO) / BT; e = math.exp(-(x % 1) * 7) if t < TEND else math.exp(-(t - TEND) * 6)
    a = {3: 5, 4: 14, 6: 10}.get(i, 0) * e; return a * math.sin(t * 91), a * .7 * math.sin(t * 127 + 1)
def make_frame(fi):
    t = fi / FPS; buf = BG.copy(); i = sec_at(t); x = (min(t, TEND) - INTRO) / BT; ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    pulse = math.exp(-(x % 1) * 5) if t < TEND else 0.0
    T.fit_text(d, (W / 2, 150), T.tr("どのドロップで、机がゆれた？（1〜5）", "Which drop rattled your desk? (1-5)"), 58, 1000, INK)
    if i == ND:                                                          # ビルドアップ：手をたたく位置がつまっていく
        xb = x - (TB - INTRO) / BT; c = (255, 236, 210); d.line([(GX0, 1100), (GX1, 1100)], fill=(80, 84, 110, 150), width=2)
        for k, v in enumerate(BXK):
            if v > xb: break
            px = GX0 + v / NB * (GX1 - GX0); hh = 60 + 520 * (k / (len(BXK) - 1)) ** 1.3; fresh = math.exp(-(xb - v) * 6)
            d.line([(px, 1100), (px, 1100 - hh)], fill=c + (int(120 + 135 * fresh),), width=6); T.add_glow(buf, GS, px, 1100 - hh, c, .25 + .5 * fresh)
        d.text((W / 2, 330), T.tr("ビルドアップ", "Build-up"), font=T.fnt(90), fill=c + (255,), anchor="mm")
        im = TEXBI; sc_ = min(2.0, 900 / im.width, 130 / im.height); im2 = im.resize((int(im.width * sc_), int(im.height * sc_)), Image.LANCZOS); ov.alpha_composite(im2, (int(W / 2 - im2.width / 2), 1330))
        buf = buf + np.float32(.06 * min(1.0, xb / 8) ** 2)
        return finish(buf, ov, fi, t)
    if i == ND + 1:                                                      # #∞：5つの層を上下に並べる
        x0 = min(x, TALL_X + math.floor((x - TALL_X - 1e-6) / NB) * NB)
        d.text((W / 2, 320), "#∞", font=T.fnt(int(140 * (1 + .06 * pulse))), fill=(255, 236, 210, 255), anchor="mm")
        for j in range(ND):
            yc = 560 + j * 210; c = COL[j]; d.line([(GX0, yc), (GX1, yc)], fill=(70, 70, 100, 110), width=1)
            xs = np.linspace(x0, max(x0 + 1e-3, x), max(2, int((x - x0) * 220))); ys = np.clip(FN[j](xs), -1.05, 1.05)
            pts = list(zip((GX0 + (xs - x0) / NB * (GX1 - GX0)).tolist(), (yc - ys * 78).tolist()))
            if len(pts) > 1: d.line(pts, fill=c + (70,), width=11, joint="curve"); d.line(pts, fill=c + (255,), width=4, joint="curve")
            T.add_glow(buf, GS, pts[-1][0], pts[-1][1], c, .5 + .3 * pulse); d.ellipse([pts[-1][0] - 8, pts[-1][1] - 8, pts[-1][0] + 8, pts[-1][1] + 8], fill=(255, 255, 255, 255))
            d.text((GX0, yc - 96), f"#{j + 1}  " + [T.tr("左", "L"), T.tr("右", "R"), T.tr("左", "L"), T.tr("まん中", "C"), T.tr("右", "R")][j], font=T.fnt(30), fill=c + (230,), anchor="lm")   # どちらの耳から聞こえるか
        buf = buf + np.float32(.08 * pulse)
        if t >= TEND: buf = buf + np.float32(.06 * math.exp(-(t - TEND) * 2.5))
        return finish(buf, ov, fi, t)
    x0 = i * NB; c = COL[i]
    d.text((W / 2, 330), f"#{i + 1}", font=T.fnt(int(150 * (1 + .06 * pulse))), fill=c + (255,), anchor="mm")
    d.line([(GX0, GY), (GX1, GY)], fill=(70, 70, 100, 140), width=2)
    xs = np.linspace(x0, max(x0 + 1e-3, x), max(2, int((x - x0) * 220))); ys = np.clip(FN[i](xs), -1.05, 1.05)
    px = GX0 + (xs - x0) / NB * (GX1 - GX0); py = GY - ys * 260; pts = list(zip(px.tolist(), py.tolist()))
    w = 5 + i
    if len(pts) > 1: d.line(pts, fill=c + (70,), width=w + 10, joint="curve"); d.line(pts, fill=c + (255,), width=w, joint="curve")
    T.add_glow(buf, GS, pts[-1][0], pts[-1][1], c, .7 + .4 * pulse); r = 7 + w; d.ellipse([pts[-1][0] - r, pts[-1][1] - r, pts[-1][0] + r, pts[-1][1] + r], fill=(255, 255, 255, 255))
    im = TEXI[i]; sc_ = min(2.0, 960 / im.width, 140 / im.height); im2 = im.resize((int(im.width * sc_), int(im.height * sc_)), Image.LANCZOS); ov.alpha_composite(im2, (int(W / 2 - im2.width / 2), 1330))
    for k in range(ND):                                                  # 下に、5つの番号（いま鳴っているのが光る）
        cx = W / 2 + (k - 2) * 150; on = k == i; cc = COL[k] + ((255 if on else 90),)
        d.ellipse([cx - 46, 1640 - 46, cx + 46, 1640 + 46], outline=cc, width=4 if on else 2); d.text((cx, 1640), str(k + 1), font=T.fnt(46), fill=cc, anchor="mm")
    buf = buf + np.float32((.03 + .03 * i) * pulse)
    return finish(buf, ov, fi, t)
def finish(buf, ov, fi, t):
    out = Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB")
    sx, sy = shake(t)
    if abs(sx) + abs(sy) > .5: out = Image.fromarray(cv2.warpAffine(np.asarray(out), np.float32([[1.02, 0, sx - W * .01], [0, 1.02, sy - H * .01]]), (W, H), borderMode=cv2.BORDER_REFLECT))
    out = np.asarray(out); g = min(T.sstep(0, .12, t), 1 - T.sstep(DUR - .7, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)

def saw(ph): return 2 * np.mod(ph, 1.0) - 1
def synth(path):
    """最初から #∞ で重ねる前提の編曲（持ち主 11/28「♾️がやっぱ音同士が強すぎて、最初から♾️に行く前提のリミックスにして」）
    5つのベースは、高さ（音域）とリズムのすきまを分けておく。1つずつ鳴らすときも、#∞ で重ねるときも同じ音域
      #1 低め（根音の1オクターブ上）の8分のポンプ  #2 高い（2オクターブ上）16分のはじく音  #3 まん中（1オクターブ上）のうねり
      #4 重低音（根音そのまま、808）              #5 まん中の短い刻み
    1つずつのときは、#4 以外は下に静かな重低音（土台）をしく。#∞ では土台は #4 がつとめる"""
    N = int(SR * DUR); tt = np.arange(N) / SR; X = (np.minimum(tt, TEND) - INTRO) / BT; live = ((tt >= INTRO) & (tt < TEND)).astype(np.float32)
    sec = np.where(tt >= TALL, ND + 1, np.where(tt >= TB, ND, np.clip(((tt - INTRO) // (BT * NB)).astype(int), 0, ND - 1)))
    inf = (sec == ND + 1).astype(np.float32); bd = (sec == ND).astype(np.float32); xb = X - (TB - INTRO) / BT
    def lp(x, fc): return K._lp(x.astype(np.float32), fc)
    def hp(x, fc): return x - lp(lp(x, fc), fc)
    from scipy.signal import lfilter
    def vcf(src, cut, mask):
        o = np.zeros(N, np.float32); zi = np.zeros(1)
        for k in range(0, N, 256):
            if not mask[k:k + 256].any(): continue
            c = math.exp(-2 * math.pi * cut[k] / SR); oo, zi = lfilter([1 - c], [1, -c], src[k:k + 256], zi=zi); o[k:k + 256] = oo
        return o
    CH = [(38, 50, 53, 57), (34, 46, 50, 53), (41, 53, 57, 60), (36, 48, 52, 55)]                                  # Dm B♭ F C（2拍ずつ）
    ci = (X // 2).astype(int) % 4; root = np.array([K.mtof(c[0]) for c in CH])[ci]
    ph = np.mod(X, 1); env = np.exp(-ph * 9); fk = 44 + 110 * np.exp(-ph * 26); kick = np.tanh(np.sin(2 * np.pi * np.cumsum(fk) / SR) * 2.2) * env
    kick = kick * (1 - bd * (xb >= 6))                                                                              # ビルドアップの最後の2拍はキックを止める
    n = np.random.default_rng(2).normal(0, 1, N).astype(np.float32); cn = lp(lp(n - lp(n, 900), 3000), 3000)
    clap = cn * np.exp(-14 * np.mod(X + 1, 2)) * .9 * (1 - bd)
    hat = lp(lp(n - lp(n, 2600), 4600), 4600) * np.exp(-30 * np.mod(X + .5, 1)) * .45
    pad = np.zeros(N, np.float32)
    for q in range(1, 4):
        f = np.array([K.mtof(c[q] + 12) for c in CH])[ci]
        for det in (-.008, .008): pad += saw(np.cumsum(f * (1 + det)) / SR) / 9
    pad = lp(lp(pad, 1500), 1500) * .5
    y = [FN[i](X) for i in range(ND)]; on = lambda i: ((sec == i).astype(np.float32) + inf)
    any_m = lambda i: (on(i) > 0)
    p1 = saw(np.cumsum(root * 2) / SR); L1 = np.tanh(vcf(p1, np.full(N, 800.0), any_m(0)) * 2.0) * (y[0] > 0) * np.exp(-np.mod(X * 2, 1) * 2.5)
    st2 = np.array([0, 5, 7, 12])[np.clip(np.round((y[1] + 1) * 1.5).astype(int), 0, 3)]; f2_ = root * 4 * 2 ** (st2 / 12)
    L2 = lp(saw(np.cumsum(f2_) / SR) * .6 + np.sin(2 * np.pi * np.cumsum(f2_) / SR) * .4, 3200) * np.exp(-np.mod(X * 4, 1) * 7)
    p3 = np.cumsum(root * 2) / SR; L3 = np.tanh(vcf(saw(p3) * .6 + saw(p3 * 1.006) * .4, 160 + 1700 * (y[2] + 1) / 2, any_m(2)) * 1.6)
    f4_ = root * 2 ** ((y[3] + 1) / 2); L4 = np.tanh(np.sin(2 * np.pi * np.cumsum(f4_) / SR) * 1.6) * np.exp(-np.mod(X, 1) * .7)
    f5_ = root * 2 * 2 ** ((np.abs(y[4]) + 1) / 2 - .5); L5 = np.tanh(vcf(saw(np.cumsum(f5_) / SR), 300 + 1500 * np.abs(y[4]), any_m(4)) * 2.2) * (np.sign(np.sin(4 * np.pi * X)) > 0) * np.exp(-np.mod(X * 2, 1) * 4)
    LAY = [hp(L1, 90), hp(L2, 400), hp(L3, 160), L4, hp(L5, 180)]
    SOLO = [.95, .80, .85, 1.10, 1.0]; INF = [.55, .38, .45, .95, .40]; PAN = [-.5, .55, -.3, 0.0, .35]
    found = np.sin(2 * np.pi * np.cumsum(root / 2) / SR) * .55 * np.exp(-np.mod(X, 1) * .5)                        # 1つずつのときの土台（#4 のときはなし）
    fmask = sum((sec == i).astype(np.float32) for i in (0, 1, 2, 4))
    duck = 1 - .6 * np.exp(-np.mod(X, 1) * 9); duck2 = 1 - .75 * np.exp(-np.mod(X, 1) * 7)
    L = np.zeros(N, np.float32); R = np.zeros(N, np.float32)
    for i in range(ND):
        sol = LAY[i] * (sec == i) * SOLO[i] * duck; inl = LAY[i] * inf * INF[i] * duck2
        gL, gR = math.sqrt((1 - PAN[i]) / 2) * 1.414, math.sqrt((1 + PAN[i]) / 2) * 1.414
        L += sol + inl * gL; R += sol + inl * gR
    roll = np.zeros(N, np.float32)                                                                                   # ビルドアップ：x_k ごとに手をたたく音、さーっと上がる音、和音のこもりが開く
    for k, v in enumerate(BXK):
        a0 = int((TB + v * BT) * SR); seg = min(N - a0, int(.18 * SR)); u = k / (len(BXK) - 1)
        if seg <= 0: continue
        e = np.exp(-np.arange(seg) / SR * 30); roll[a0:a0 + seg] += (n[a0:a0 + seg] - lp(n[a0:a0 + seg], 700 + 1600 * u)) * e * (.5 + .9 * u)
    roll = lp(lp(roll, 3800), 3800) * 2.4; rise = lp(lp((n - lp(n, 400)) * np.clip(xb / 8, 0, 1) ** 2 * .35, 2600), 2600)
    padb = vcf(pad * 2.0, 300 + 2600 * np.clip(xb / 8, 0, 1) ** 2, bd > 0)
    build = (roll + rise + padb * .8) * bd + found * bd * (1 - np.clip(xb / 6, 0, 1))
    mid = (kick + clap + hat + pad * (1 - .5 * inf) * (1 - bd) + lp(found, 200) * fmask * duck + build) * live
    te = np.maximum(tt - TEND, 0); tl = (tt >= TEND).astype(np.float32)                                            # 終わり：キックと重低音のレがひとつだけ、短く
    mid += (np.tanh(np.sin(2 * np.pi * np.cumsum(42 + 80 * np.exp(-te * 26)) / SR) * 1.8) * np.exp(-te * 4) + np.sin(2 * np.pi * K.mtof(26) * te) * np.exp(-te * 2.2) * .6) * tl
    L = (mid + L * live); R = (mid + R * live); fade = np.clip((DUR - tt) / .4, 0, 1)
    st = np.stack([L * fade, R * fade], 1); st = np.tanh(st * 1.2) / 1.2; st *= .36 / (np.abs(st).max() + 1e-9)
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_dropvote", exist_ok=True)
    print("長さ", round(DUR, 1), "区切り", [round(v, 2) for v in T0])
    if cmd == "stills": print(T.stills(NF, make_frame, "build_dropvote/s", at=[(T0[i] + 2.8) / DUR for i in (0, 4)] + [(TB + 2.8) / DUR, (TALL + 6) / DUR, (TEND + .2) / DUR])); sys.exit()
    if cmd == "audio": synth("build_dropvote/a.wav"); sys.exit()
    out = f"output/dropvote1_{T.LANG}.mp4"; synth("build_dropvote/a.wav"); T.encode(NF, make_frame, "build_dropvote/a.wav", out); print(out)
