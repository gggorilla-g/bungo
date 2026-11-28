# formulabeat.py — 数式のグラフを、そのまま音にする。#1 から順に、キック・ベース・ハイハット・和音の数式を1つずつ描き、最後の「#∞」で全部が重なってEDMの曲になる（縦のショート）
#   持ち主 11/28：数式のグラフを点が描き、その形が音になる動画（録画）を見せて「こういうのもチャレンジしてみましょうか　edmっぽい重低音」
#   まねたのは仕組み（数式 → グラフ → 音。番号つきで次々に出る）だけ。数式・色・字の置き方・音は自前
#   決まり：画面の数式が、そのまま音の作り方になっている（x は拍。1拍＝0.469秒、128 BPM）
#     #1 キック    y = 2e^(−7·mod(x,1)) − 1        … 1拍ごとに y が跳ね上がって下がる。これを、低い音（高さが落ちていくサイン波）の大きさにする
#     #2 ベース    y = sgn(sin 2πx) + 0.8·sgn(sin 3πx) … y の大きさを音量、y の正負をオクターブにする。和音の根音（カノン進行）で鳴らす
#     #3 ハイハット y = e^(−30·mod(x+0.5, 1))       … 拍の裏で、さーっという息の音を鳴らす大きさ
#     #4 和音      y = sin(2πx·f + 2.5 sin(2πx·3f))·e^(−3·mod(x,2)) … f は和音の音。周波数を変調した明るい音（FM）
#     #∞ 全部を重ねる。キックが鳴るたびに、ほかの音を少し下げる（サイドチェイン）。最後の小節だけテンポを半分に落とす（持ち主 11/28「動画の最後だけ…リズムテンポ変える」）
#   python3 tools/formulabeat.py stills ／ all（LANG_OUT=en で英語）→ output/formulabeat1_<ja|en>.mp4
import math, os, sys, io, wave
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS, SR = T.W, T.H, T.FPS, T.SR
BPM = 128.0; BT = 60 / BPM; NB = 16                                     # 1拍の秒、1つの数式の拍数
INTRO = .6; SEC = [("kick", 0), ("bass", 1), ("hat", 2), ("chord", 3), ("all", 4)]
LEN = [NB, NB, NB, NB, 24]; T0 = [INTRO + BT * sum(LEN[:i]) for i in range(5)]; TALL = T0[4]; TSLOW = T0[4] + 20 * BT   # #∞ の最後の4拍は半分の速さ
DUR = TSLOW + 4 * BT * 2 + 2.6; NF = int(DUR * FPS)
COL = [(246, 196, 108), (236, 120, 110), (120, 200, 210), (170, 140, 230), (255, 236, 200)]   # 琥珀・珊瑚・青緑・すみれ・白金
def beat_x(t):
    """動画の時刻 → 拍（x）。最後の4拍だけ、半分の速さで進む"""
    if t <= TSLOW: return (t - INTRO) / BT
    return (TSLOW - INTRO) / BT + (t - TSLOW) / (2 * BT)
def chord_of(x): return int(x // 4) % 8                                  # 4拍で和音が1つ進む（カノン進行）

def f_kick(x): return 2 * np.exp(-7 * np.mod(x, 1)) - 1
def f_bass(x): return np.sign(np.sin(2 * np.pi * x)) + .8 * np.sign(np.sin(3 * np.pi * x))
def f_hat(x): return np.exp(-30 * np.mod(x + .5, 1))
def f_chord(x, fr=3.0): return np.sin(2 * np.pi * x * fr + 2.5 * np.sin(2 * np.pi * x * 3 * fr)) * np.exp(-3 * np.mod(x, 2))
def f_all(x): return (f_kick(x) * .9 + f_bass(x) * .35 + f_hat(x) * .3 + f_chord(x) * .4) / 1.4
FN = [f_kick, f_bass, f_hat, f_chord, f_all]
TEX = [r"$y=2e^{-7\,\mathrm{mod}(x,1)}-1$", r"$y=\mathrm{sgn}(\sin 2\pi x)+0.8\,\mathrm{sgn}(\sin 3\pi x)$", r"$y=e^{-30\,\mathrm{mod}(x+0.5,\,1)}$",
       r"$y=\sin(2\pi f x+2.5\sin 6\pi f x)\,e^{-3\,\mathrm{mod}(x,2)}$", r"$y=$" + "#1 + #2 + #3 + #4"]
NAME = [("キック", "Kick"), ("ベース", "Bass"), ("ハイハット", "Hi-hat"), ("和音", "Chords"), ("ぜんぶ", "All of them")]
def tex_img(s, col):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    matplotlib.rcParams["mathtext.fontset"] = "cm"; fig = plt.figure(figsize=(10, 1.2), dpi=100); fig.patch.set_alpha(0)
    fig.text(.5, .5, s, ha="center", va="center", fontsize=34, color=np.array(col) / 255); buf = io.BytesIO(); fig.savefig(buf, format="png", transparent=True, dpi=100); plt.close(fig)
    im = Image.open(buf).convert("RGBA"); bb = im.getbbox(); return im.crop(bb) if bb else im
TEXI = [tex_img(TEX[i], COL[i]) for i in range(5)]

GX0, GX1, GYC, GA = 70, 1010, 960, 230                                  # グラフの左右、まん中の高さ、振れ幅
def make_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); b = (np.array([10, 10, 20], np.float32) * (1 - yy / H)[..., None] + np.array([4, 4, 10], np.float32) * (yy / H)[..., None]) / 255
    return b.astype(np.float32)
BG = make_bg(); GS = T.glow(18)
INK = (244, 246, 255, 255)

def sec_at(t):
    for i in range(4, -1, -1):
        if t >= T0[i]: return i
    return 0
def make_frame(fi):
    t = fi / FPS; buf = BG.copy(); i = sec_at(t); x = beat_x(t); x0 = math.floor(x / 4) * 4 if i < 4 else math.floor(x / 4) * 4   # 4拍ごとに描き直す
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    d.line([(GX0, GYC), (GX1, GYC)], fill=(80, 84, 110, 160), width=2); d.line([(GX0, GYC - GA - 30), (GX0, GYC + GA + 30)], fill=(80, 84, 110, 120), width=2)
    for k in range(1, 4): xx_ = GX0 + (GX1 - GX0) * k / 4; d.line([(xx_, GYC - 8), (xx_, GYC + 8)], fill=(80, 84, 110, 160), width=2)
    if t >= INTRO:
        xs = np.linspace(x0, max(x0 + 1e-3, x), max(2, int((x - x0) * 220))); f = FN[i]; ys = f(xs); ys = np.clip(ys, -2, 2)
        sc = GA / (1.0 if i in (0, 3) else 1.8 if i == 1 else 1.0 if i == 2 else 1.1)
        px = GX0 + (xs - x0) / 4 * (GX1 - GX0); py = GYC - ys * sc * (1 if i != 2 else 1.6) + (GA * .8 if i == 2 else 0)
        pts = list(zip(px.tolist(), py.tolist())); c = COL[i]
        if len(pts) > 1: d.line(pts, fill=c + (90,), width=9, joint="curve"); d.line(pts, fill=c + (255,), width=4, joint="curve")
        T.add_glow(buf, GS, pts[-1][0], pts[-1][1], c, .7); d.ellipse([pts[-1][0] - 9, pts[-1][1] - 9, pts[-1][0] + 9, pts[-1][1] + 9], fill=(255, 255, 255, 255))
    T.fit_text(d, (W / 2, 140), T.tr("数式のグラフを、そのまま音にすると？", "What if a formula's graph were the sound?"), 58, 1000, INK)
    T.fit_text(d, (W / 2, 212), T.tr("最後の #∞ で、全部が重なる", "At #∞, they all play together"), 42, 1000, (255, 222, 150, 255))
    lab = "#∞" if i == 4 else f"#{i + 1}"; d.text((W / 2, 340), lab, font=T.fnt(110), fill=COL[i] + (255,), anchor="mm")
    d.text((W / 2, 440), T.tr(NAME[i][0], NAME[i][1]), font=T.fnt(44), fill=(220, 224, 240, 255), anchor="mm")
    im = TEXI[i]; sc_ = min(2.2, 940 / im.width); im2 = im.resize((int(im.width * sc_), int(im.height * sc_)), Image.LANCZOS); ov.alpha_composite(im2, (int(W / 2 - im2.width / 2), 1330))
    if t >= TSLOW: T.fit_text(d, (W / 2, 1560), T.tr("最後だけ、テンポ半分", "Half tempo for the last bar"), 42, 1000, (255, 232, 170, 255))
    out = np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB"))
    g = min(T.sstep(0, .3, t), 1 - T.sstep(DUR - .8, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)

def synth(path):
    N = int(SR * DUR); tt = np.arange(N) / SR; X = np.array([beat_x(v) for v in tt[::64]]); X = np.interp(tt, tt[::64], X); live = tt >= INTRO
    sec = np.searchsorted(np.array(T0), tt, "right") - 1; on = lambda k: ((sec == k) | (sec == 4)) & live & (tt < DUR - 2.4)
    roots = np.array([K.mtof(K.CANON[c][0] - 12) for c in range(8)])
    # キック：#1 の y を大きさに（0〜1）、高さは 150→48Hz に落ちる
    ph = np.mod(X, 1); env = np.clip((f_kick(X) + 1) / 2, 0, 1) ** 1.2; fk = 48 + 110 * np.exp(-ph * 26); kick = np.sin(2 * np.pi * np.cumsum(fk) / SR) * env
    kick += .25 * np.random.default_rng(1).normal(0, 1, N) * np.exp(-ph * 120)            # 当たりのカチッ
    # ベース：#2 の |y| を音量、正負でオクターブ。音はカノン進行の根音
    yb = f_bass(X); fr = roots[(X // 4).astype(int) % 8] * np.where(yb > 0, 2.0, 1.0); bass = np.sin(2 * np.pi * np.cumsum(fr) / SR); bass = np.tanh(bass * 2.2) * (np.abs(yb) / 1.8)
    bass = K._lp(bass.astype(np.float32), 900)
    # ハイハット：#3 の y を大きさに、白い雑音の高い所だけ
    n = np.random.default_rng(2).normal(0, 1, N).astype(np.float32); hat = (n - K._lp(n, 7000)) * f_hat(X)
    # 和音：#4。和音の3つの音で、FM の明るい音
    ch = np.zeros(N, np.float32); env4 = np.exp(-3 * np.mod(X, 2))
    for q in range(3):
        fq = np.array([K.mtof(K.canon_tones(c, 62, 86)[q]) for c in range(8)])[(X // 4).astype(int) % 8]; p = 2 * np.pi * np.cumsum(fq) / SR; ch += np.sin(p + 2.5 * np.sin(3 * p) * env4) * env4 / 3
    duck = 1 - .75 * np.exp(-np.mod(X, 1) * 9) * (sec == 4)                                # サイドチェイン（#∞ のときだけ）
    al = (sec == 4); gk, gb, gh, gc = .95, np.where(al, .24, .30), np.where(al, .8, 1.6), np.where(al, .5, .9)   # 1つずつ鳴る時と、全部の時で、音量をそろえる
    mix = kick * gk * on(0) + bass * gb * on(1) * duck + hat * gh * on(2) * duck + ch * gc * on(3) * duck
    sub = np.sin(2 * np.pi * np.cumsum(roots[(X // 4).astype(int) % 8] / 2) / SR) * .35 * (sec == 4) * duck * live * (tt < DUR - 2.4)   # #∞ の重低音
    mix = (mix + sub).astype(np.float32); mix *= np.clip((DUR - tt) / 1.0, 0, 1)
    st = np.stack([mix, mix], 1); st[:, 0] += hat * .06 * on(2); st = np.tanh(st * 1.4) / 1.4; st *= .9 / (np.abs(st).max() + 1e-9)
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_formulabeat", exist_ok=True)
    print("長さ", round(DUR, 1), "区切り", [round(v, 2) for v in T0], "テンポ半分から", round(TSLOW, 2))
    if cmd == "stills": print(T.stills(NF, make_frame, "build_formulabeat/s", at=[(T0[i] + 2.6) / DUR for i in range(5)] + [(TSLOW + 1.5) / DUR])); sys.exit()
    out = f"output/formulabeat1_{T.LANG}.mp4"; synth("build_formulabeat/a.wav"); T.encode(NF, make_frame, "build_formulabeat/a.wav", out); print(out)
