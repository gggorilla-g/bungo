# dropvote.py — 数式のグラフで鳴らすベースの「ドロップ」を5つ。どれで机がゆれた？（コメントで番号を答えてもらう）（縦のショート）
#   持ち主 11/28：「Drop #4 should actually be illegal / Which drop rattled your desk? (1-4)」の録画を見せて「これけい」
#   まねたのは仕組み（数式のグラフ → ベースの音。番号つきのドロップを並べて、どれが一番かを聞く）だけ。数式・色・字・音は自前（formulabeat の続き）
#   5つとも、うしろのキック・クラップ・ハイハット・和音は同じ。ちがうのはベースだけ（グラフの y がベースの何を動かすか）
#     #1 y = sgn(sin 4πx)                         … 8分で、鳴る／止まる
#     #2 y = ⌊4·mod(x,1)⌋/1.5 − 1                 … 16分の階段で、音の高さが 0・5・7・12 半音と上がる
#     #3 y = sin 3πx                              … こもり具合がうねる（3連のワブル）
#     #4 y = 2e^(−3·mod(x,1)) − 1                 … 拍ごとに1オクターブ上からすべり落ちる（808）
#     #5 y = sgn(sin 4πx)·(2e^(−3·mod(x,1)) − 1)  … #1 と #4 のかけ算。止まりながら、すべり落ちる。いちばん重く、画面もゆれる
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
T0 = [INTRO + BT * NB * i for i in range(ND + 1)]; TEND = T0[ND]; DUR = TEND + 1.9; NF = int(DUR * FPS)
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
TEXI = [tex_img(TEX[i], COL[i]) for i in range(ND)]
GX0, GX1, GY = 60, 1020, 900
def make_bg():
    yy = np.mgrid[0:H, 0:W][0].astype(np.float32); return ((np.array([10, 8, 20], np.float32) * (1 - yy / H)[..., None] + np.array([3, 3, 8], np.float32) * (yy / H)[..., None]) / 255).astype(np.float32)
BG = make_bg(); GS = T.glow(18); INK = (244, 246, 255, 255)
def sec_at(t): return int(min(ND - 1, max(0, (t - INTRO) // (BT * NB))))
def shake(t):
    """#4 と #5 は、キックのたびに画面がゆれる（#5 は大きく）"""
    i = sec_at(t); x = (min(t, TEND) - INTRO) / BT; e = math.exp(-(x % 1) * 7) if t < TEND else math.exp(-(t - TEND) * 6)
    a = {3: 5, 4: 14}.get(i, 0) * e; return a * math.sin(t * 91), a * .7 * math.sin(t * 127 + 1)
def make_frame(fi):
    t = fi / FPS; buf = BG.copy(); i = sec_at(t); x = (min(t, TEND) - INTRO) / BT; ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    x0 = i * NB; c = COL[i]; pulse = math.exp(-(x % 1) * 5) if t < TEND else 0.0
    T.fit_text(d, (W / 2, 150), T.tr("どのドロップで、机がゆれた？（1〜5）", "Which drop rattled your desk? (1-5)"), 58, 1000, INK)
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
    if t >= TEND: buf = buf + np.float32(.10 * math.exp(-(t - TEND) * 2.5))
    out = Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB")
    sx, sy = shake(t)
    if abs(sx) + abs(sy) > .5: out = Image.fromarray(cv2.warpAffine(np.asarray(out), np.float32([[1.02, 0, sx - W * .01], [0, 1.02, sy - H * .01]]), (W, H), borderMode=cv2.BORDER_REFLECT))
    out = np.asarray(out); g = min(T.sstep(0, .12, t), 1 - T.sstep(DUR - .7, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)

def saw(ph): return 2 * np.mod(ph, 1.0) - 1
def synth(path):
    N = int(SR * DUR); tt = np.arange(N) / SR; X = (np.minimum(tt, TEND) - INTRO) / BT; live = ((tt >= INTRO) & (tt < TEND)).astype(np.float32)
    sec = np.clip(((tt - INTRO) // (BT * NB)).astype(int), 0, ND - 1); y = np.zeros(N)
    for i in range(ND): m = sec == i; y[m] = FN[i](X[m])
    def lp(x, fc): return K._lp(x.astype(np.float32), fc)
    from scipy.signal import lfilter
    CH = [(38, 50, 53, 57), (34, 46, 50, 53), (41, 53, 57, 60), (36, 48, 52, 55)]                                  # Dm B♭ F C（2拍ずつ）
    ci = (X // 2).astype(int) % 4; root = np.array([K.mtof(c[0]) for c in CH])[ci]
    ph = np.mod(X, 1); env = np.exp(-ph * 9); fk = 44 + 110 * np.exp(-ph * 26); kick = np.tanh(np.sin(2 * np.pi * np.cumsum(fk) / SR) * 2.2) * env
    n = np.random.default_rng(2).normal(0, 1, N).astype(np.float32)
    clap = lp(lp(n - lp(n, 900), 3000), 3000) * np.exp(-14 * np.mod(X + 1, 2)) * .9
    hat = lp(lp(n - lp(n, 2600), 4600), 4600) * np.exp(-30 * np.mod(X + .5, 1)) * .45
    pad = np.zeros(N, np.float32)
    for q in range(1, 4):
        f = np.array([K.mtof(c[q] + 12) for c in CH])[ci]
        for det in (-.008, .008): pad += saw(np.cumsum(f * (1 + det)) / SR) / 9
    pad = lp(lp(pad, 1500), 1500) * .5
    bass = np.zeros(N, np.float32); sub = np.zeros(N, np.float32)
    for i in range(ND):                                                                                             # グラフの y が、ベースの何を動かすか
        m = (sec == i).astype(np.float32)
        if i == 0: fr = root; amp = (y > 0).astype(np.float32); cut = np.full(N, 900.0)
        elif i == 1: fr = root * 2 ** (np.array([0, 5, 7, 12])[np.clip(np.round((y + 1) * 1.5).astype(int), 0, 3)] / 12); amp = np.ones(N, np.float32); cut = np.full(N, 1100.0)
        elif i == 2: fr = root; amp = np.ones(N, np.float32); cut = 90 + 1900 * (y + 1) / 2
        elif i == 3: fr = root * 2 ** ((y + 1) / 2); amp = np.ones(N, np.float32) * np.exp(-np.mod(X, 1) * .8); cut = np.full(N, 700.0)
        else: fr = root * 2 ** ((np.abs(y) + 1) / 2 - .5); amp = (np.abs(y) > .05).astype(np.float32) * (np.sign(np.sin(4 * np.pi * X)) > 0); cut = 300 + 1400 * np.abs(y)
        ph_ = np.cumsum(fr) / SR; src = saw(ph_) * .6 + saw(ph_ * 1.006) * .4
        o = np.zeros(N, np.float32); zi = np.zeros(1)
        for k in range(0, N, 256):
            if not m[k:k + 256].any(): continue
            c = math.exp(-2 * math.pi * cut[k] / SR); oo, zi = lfilter([1 - c], [1, -c], src[k:k + 256], zi=zi); o[k:k + 256] = oo
        drive = 2.0 + .8 * i
        bass += np.tanh(o * drive) * amp * m * (.7 + .06 * i) * [.80, .86, .92, 1.0, 1.12][i]
        gi = [.80, .86, .92, 1.0, 1.12][i]; bass_amp = amp if i < 4 else np.ones(N, np.float32) * np.exp(-np.mod(X, 1) * .6)   # #5 の重低音は止めずに鳴らしつづける（いちばん重く）
        sub += np.sin(2 * np.pi * np.cumsum(fr / 2) / SR) * bass_amp * m * (.45 + .10 * i) * gi
    duck = 1 - .6 * np.exp(-np.mod(X, 1) * 9)
    mix = (kick * 1.0 + (clap + hat) + (pad + lp(bass, 4000) * 1.0 + lp(sub, 200) * 1.0) * duck) * live
    te = np.maximum(tt - TEND, 0); tl = (tt >= TEND).astype(np.float32)                                            # 終わり：キックと重低音のレがひとつだけ、短く
    mix += (np.tanh(np.sin(2 * np.pi * np.cumsum(42 + 80 * np.exp(-te * 26)) / SR) * 1.8) * np.exp(-te * 4) + np.sin(2 * np.pi * K.mtof(26) * te) * np.exp(-te * 2.2) * .6) * tl
    mix = mix * np.clip((DUR - tt) / .4, 0, 1)
    st = np.stack([mix + pad * .06 * live, mix - pad * .06 * live], 1); st = np.tanh(st * 1.2) / 1.2; st *= .36 / (np.abs(st).max() + 1e-9)
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_dropvote", exist_ok=True)
    print("長さ", round(DUR, 1), "区切り", [round(v, 2) for v in T0])
    if cmd == "stills": print(T.stills(NF, make_frame, "build_dropvote/s", at=[(T0[i] + 2.8) / DUR for i in range(ND)] + [(TEND + .2) / DUR])); sys.exit()
    if cmd == "audio": synth("build_dropvote/a.wav"); sys.exit()
    out = f"output/dropvote1_{T.LANG}.mp4"; synth("build_dropvote/a.wav"); T.encode(NF, make_frame, "build_dropvote/a.wav", out); print(out)
