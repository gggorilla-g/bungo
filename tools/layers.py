# layers.py — 重さのちがう液体を6つ重ねたグラスに、しずくを落とす。しずくは自分と同じ重さの層まで沈んで止まり、そこで音が鳴る（縦のショート 1080×1920・60コマ）
#   持ち主 11/28：「鯨で作ってくれた泡が水面で弾ける時の水面のモーションがすごくヒーリング効果高いので、なんか重さの違う液体みたいな感じのコンセプトとで音と組み合わせて一本作りたい」
#   決まり（本物の液体と同じ向き）
#     ・液体の重さ（密度 g/cm3）：アルコール 0.79、油 0.92、水 1.00、台所洗剤 1.06、メープルシロップ 1.33、はちみつ 1.42。軽いものが上にのる（よく使われる「密度の塔」の値。銘柄でずれる）
#     ・しずくは、自分より軽い層を通りぬけ、自分と同じ液体の層の上の面で止まって混ざる
#     ・境目の波は、上と下の重さの差が小さいほど、ゆっくり大きくゆれる（境目を伝わる波の速さは、重さの差÷重さの和 の平方根に比例）。ねばる液体の境目ほど早くおさまる
#     ・しずくが混ざると、その層が少しだけ厚くなる
#   音：しずくが自分の層に着いて混ざった瞬間に1打。重い液体ほど低い音（6つの層＝和音の6つの音）。和音はカノン進行。ガラスの響き＋瞑想のエコー＋裏の低い持続音。
#       いちばん上の面に落ちた瞬間に、小さな水の音（同じ高さ）。最後は、6つの液体のしずくを同時に落とす：軽いものから先に着くので、高い音から順に鳴る
#   python3 tools/layers.py stills ／ all（LANG_OUT=en で英語）→ output/layers1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS = T.W, T.H, T.FPS
NAME = [("アルコール", "Alcohol"), ("油", "Oil"), ("水", "Water"), ("台所洗剤", "Dish soap"), ("シロップ", "Syrup"), ("はちみつ", "Honey")]
RHO = [.79, .92, 1.00, 1.06, 1.33, 1.42]; VISC = [1.2, 50, 1, 300, 2000, 6000]   # 密度、ねばり（水を1とした大まか）
COL = [(246, 231, 196), (242, 196, 140), (234, 150, 122), (198, 108, 142), (126, 92, 168), (62, 78, 140)]   # 配色：上から下へ、明るいクリーム → 夕焼けの橙・紅 → 紫 → 夜の藍（11/28「色合いは配色的に綺麗な見た目になるようにして」）。重いほど暗い
NL = 6; GX0, GX1 = 196.0, 884.0; GTOP, GBOT = 560.0, 1720.0; TH0 = (GBOT - GTOP) / NL - 6   # グラスの内側、はじめの層の厚さ
BPM = 50.0; CH = 2 * 60 / BPM; INTRO = 1.2; NCH = 16; RD = 19.0                 # 和音1つの長さ、しずくの半径
XS = np.arange(GX0, GX1 + 1, 4.0); NX = len(XS)
ATW = [1.0] + [(RHO[k] - RHO[k - 1]) / (RHO[k] + RHO[k - 1]) for k in range(1, NL)]   # 境目 k（k=0 はいちばん上の面）の「重さの差÷重さの和」
CW = [520 * math.sqrt(a) for a in ATW]; CW[0] = 360.0                              # 波の速さ（px/秒）。上の面は見やすい速さに
DAMP = [1.6] + [1.0 + .55 * math.log10(max(VISC[k], VISC[k - 1])) for k in range(1, NL)]
TOP0 = [GTOP + 40 + k * TH0 for k in range(NL)]                                # 境目 k のはじめの高さ（k=0 が上の面）

def travel(k):
    """液体 k のしずくを上の面の 120px 上から落として、層 k の上の面（境目 k）に着くまでの時間と、境目ごとの通過時刻"""
    y, v, t, dt, cross = TOP0[0] - 120, 0.0, 0.0, 1 / 600, []; j = 0
    while True:
        while j <= k and y >= TOP0[j]: cross.append(t); j += 1
        if j > k: return t, cross
        if j == 0: a = 1600.0; v += a * dt
        else:
            vt = 120 + 900 * (RHO[k] - RHO[j - 1]) / (RHO[k]) / (1 + .25 * math.log10(VISC[j - 1] + 1)); v += (vt - v) * dt / .12
        y += v * dt; t += dt
TR = [travel(k) for k in range(NL)]

def chart():
    D = []; rng = np.random.default_rng(4)
    pat = [[0], [3], [0, 4], [2, 5], [0, 2, 4], [1, 3, 5], [0, 2, 3, 5], [1, 2, 4, 5]]
    for n in range(NCH):
        t0 = INTRO + n * CH; lv = min(7, n // 2); ks = pat[lv]; nb = len(ks); st = CH / nb
        for q, k in enumerate(ks):
            tm = t0 + q * st; x = float(rng.uniform(GX0 + 70, GX1 - 70)); D.append(dict(k=k, tm=tm, tr=tm - TR[k][0], x=x, ch=n % 8, vel=.62 if q == 0 else .48, fin=False))
    tf = INTRO + NCH * CH + .2                                                     # 最後：6つ同時に落とす（軽いものから着く）
    for k in range(NL): D.append(dict(k=k, tm=tf + TR[k][0], tr=tf, x=GX0 + 90 + k * (GX1 - GX0 - 180) / 5, ch=0, vel=.7, fin=True))
    return sorted(D, key=lambda d: d["tm"])
DROPS = chart(); TLAST = max(d["tm"] for d in DROPS); DUR = TLAST + 3.2; NF = int(DUR * FPS)
for d in DROPS: d["cross"] = [d["tr"] + c for c in TR[d["k"]][1]]

class Waves:
    """境目ごとの1次元の波。しずくが通った所・止まった所を押しこむ"""
    def __init__(s):
        s.h = np.zeros((NL, NX)); s.v = np.zeros((NL, NX)); s.fi = -1; s.ev = sorted([(c, j, d) for d in DROPS for j, c in enumerate(d["cross"])], key=lambda e: e[0]); s.k = 0; s.th = np.zeros(NL)
    def step_to(s, fi):
        if fi < s.fi: s.__init__()
        while s.fi < fi:
            s.fi += 1; t = s.fi / FPS
            while s.k < len(s.ev) and s.ev[s.k][0] <= t:
                c, j, d = s.ev[s.k]; s.k += 1; last = j == d["k"]; amp = (260 if j == 0 else 110 / math.sqrt(max(ATW[j], .02))) * (1.3 if last else .6)
                s.v[j] += amp * np.exp(-((XS - d["x"]) / (14 + RD)) ** 2)
                if last:
                    for i in range(1, d["k"] + 1): s.th[i] += math.pi * RD * RD / (GX1 - GX0) * .0          # 層の厚さ（下の層が厚くなると、上の境目が上がる）
                    s.th[:d["k"] + 1] -= math.pi * RD * RD / (GX1 - GX0)
            for _ in range(4):
                dt = 1 / (FPS * 4); lap = np.zeros((NL, NX)); lap[:, 1:-1] = s.h[:, 2:] - 2 * s.h[:, 1:-1] + s.h[:, :-2]; lap[:, 0] = s.h[:, 1] - s.h[:, 0]; lap[:, -1] = s.h[:, -2] - s.h[:, -1]
                cc = np.array(CW)[:, None] ** 2 / 16.0; s.v += (cc * lap - np.array(DAMP)[:, None] * s.v - 4.0 * s.h) * dt; s.h += s.v * dt
    def y(s, t):
        base = np.array(TOP0)[:, None] + s.th[:, None] * 0; tilt = np.zeros((NL, NX)); tilt[0] = 2.5 * np.sin(2 * np.pi * (XS / 380 - t / 3.3)); tilt[1:] = 1.5 * np.sin(2 * np.pi * (XS[None] / 520 + t / 6.1 + np.arange(1, NL)[:, None]))
        return base + np.cumsum(np.r_[[0], s.th[1:]])[:, None] * 0 + s.h + tilt + s.th[:, None]
WV = Waves()

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
def make_bg():
    b = (np.array([10, 13, 30], np.float32) * (1 - yy / H)[..., None] + np.array([4, 5, 14], np.float32) * (yy / H)[..., None]) / 255
    b += (np.exp(-(((xx - 540) / 520) ** 2 + ((yy - 1100) / 700) ** 2)) * 16 / 255)[..., None] * np.array([.8, .9, 1.4], np.float32)
    return b.astype(np.float32)
RAY = (1.0 + .16 * np.sin(xx / 47 + 1.3) * np.sin(xx / 113) + .10 * np.sin(xx / 23 + 2.1)).astype(np.float32)   # 光のすじ（縦）
BG = make_bg(); INSIDE = ((xx >= GX0) & (xx <= GX1) & (yy <= GBOT)).astype(np.float32)
GS = T.glow(16)
def glass_layer():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.line([(GX0 - 6, GTOP - 80), (GX0 - 6, GBOT + 8)], fill=(220, 232, 255, 150), width=4); d.line([(GX1 + 6, GTOP - 80), (GX1 + 6, GBOT + 8)], fill=(220, 232, 255, 150), width=4)
    d.line([(GX0 - 8, GBOT + 8), (GX1 + 8, GBOT + 8)], fill=(220, 232, 255, 150), width=5); d.line([(GX0 + 14, GTOP - 60), (GX0 + 14, GBOT - 30)], fill=(255, 255, 255, 40), width=8)
    return im
GLASS = glass_layer()

def make_frame(fi):
    t = fi / FPS; WV.step_to(fi); Y = WV.y(t); buf = BG.copy()
    yi = np.interp(np.arange(W), XS, np.arange(NX)).astype(np.float32)
    lay = np.full((H, W), -1, np.int16)                                             # 画素ごとに、どの層か
    for k in range(NL):
        yk = np.interp(np.arange(W), XS, Y[k]); lay[(yy >= yk[None, :]) & (INSIDE > 0)] = k
    for k in range(NL):
        m = (lay == k).astype(np.float32)
        if not m.any(): continue
        yk = np.interp(np.arange(W), XS, Y[k])[None, :]; depth = np.clip((yy - yk) / TH0, 0, 1.5)
        c = np.array(COL[k], np.float32) / 255 * .92                                                            # 層の中はベタ塗り（11/28「縦縞感がきついのでベタでいいかもな思い切って。動きで見せる系の」）
        buf = buf * (1 - m[..., None]) + c * m[..., None]
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for k in range(NL):                                                             # 境目の光る線
        pts = [(float(x), float(y)) for x, y in zip(XS, Y[k])]; d.line(pts, fill=(255, 255, 255, 210 if k == 0 else 120), width=3 if k == 0 else 2)
    for dr in DROPS:                                                                # しずく
        if not (dr["tr"] <= t < dr["tm"] + .25): continue
        e = t - dr["tr"]; y, v = TOP0[0] - 120, 0.0; j = 0; dt = 1 / 240; tt = 0.0
        while tt < min(e, dr["tm"] - dr["tr"]):
            while j <= dr["k"] and y >= TOP0[j]: j += 1
            if j == 0: v += 1600 * dt
            else: vt = 120 + 900 * (RHO[dr["k"]] - RHO[j - 1]) / RHO[dr["k"]] / (1 + .25 * math.log10(VISC[j - 1] + 1)); v += (vt - v) * dt / .12
            y += v * dt; tt += dt
        y += Y[dr["k"]][int(np.clip((dr["x"] - GX0) / 4, 0, NX - 1))] - TOP0[dr["k"]] if t >= dr["tm"] else 0
        g = 1.0 if t < dr["tm"] else max(0.0, 1 - (t - dr["tm"]) / .25); rr = RD * (.55 + .45 * g); el = 1 + min(.35, v / 2500)
        c = COL[dr["k"]]; d.ellipse([dr["x"] - rr / el, y - rr * el, dr["x"] + rr / el, y + rr * el], fill=tuple(min(255, int(v * 1.08)) for v in c) + (int(255 * g),), outline=(255, 255, 255, int(220 * g)), width=2)
        d.ellipse([dr["x"] - rr * .45 / el, y - rr * .62 * el, dr["x"] - rr * .05 / el, y - rr * .25 * el], fill=(255, 255, 255, int(170 * g)))   # しずくの光
    for dr in DROPS:                                                                # 混ざった瞬間：小さな光
        e = t - dr["tm"]
        if 0 <= e < .35: T.add_glow(buf, GS, dr["x"], float(Y[dr["k"]][int(np.clip((dr["x"] - GX0) / 4, 0, NX - 1))]), COL[dr["k"]], .5 * math.exp(-e / .1))
    f = T.fnt(30)
    for k in range(NL):                                                             # 層の名前と重さ
        ym = (float(Y[k].mean()) + (float(Y[k + 1].mean()) if k < NL - 1 else GBOT)) / 2
        d.text((GX1 + 26, ym - 18), T.tr(NAME[k][0], NAME[k][1]), font=f, fill=tuple(int(v + (255 - v) * .45) for v in COL[k]) + (255,), anchor="lm")   # 名前は少し明るく（暗い層の色でも読める）; d.text((GX1 + 26, ym + 18), f"{RHO[k]:.2f}", font=T.fnt(28, False), fill=(200, 208, 228, 255), anchor="lm")
    d.text((GX0 - 24, 1745), T.tr("重さ g/cm³", "Density g/cm³"), font=T.fnt(24, False), fill=(170, 180, 205, 255), anchor="lm") if False else None
    T.fit_text(d, (W / 2, 140), T.tr("重さのちがう液体に、しずくを落とすと？", "Drop by drop into six liquids of different weights"), 56, 1000, (244, 246, 255, 255))
    T.fit_text(d, (W / 2, 214), T.tr("しずくは、自分と同じ液体の層で止まって鳴る", "Each drop sinks to its own layer and rings there"), 42, 1000, (255, 222, 150, 255))
    T.fit_text(d, (W / 2, 288), T.tr("重い液体ほど、低い音", "Heavier liquids, lower notes"), 38, 1000, (200, 210, 235, 255), bold=False)
    if t > TLAST - TR[5][0] - .2: T.fit_text(d, (W / 2, 1810), T.tr("最後は6つ同時に。軽いものから着く", "Finally all six at once. The lightest lands first"), 40, 1000, (255, 232, 170, 255))
    out = np.asarray(Image.alpha_composite(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov), GLASS).convert("RGB"))
    gg = min(T.sstep(0, .35, t), 1 - T.sstep(DUR - .7, DUR, t))
    return out if gg >= .999 else (out.astype(np.float32) * gg).astype(np.uint8)

def audio(path):
    a = T.Audio(DUR, mat="glass", max_same=4, window=.012); N = int(T.SR * DUR); under = np.zeros(N, np.float32)
    for dr in DROPS:
        tn = K.canon_tones(dr["ch"], 57, 88); m = tn[max(0, len(tn) - 1 - 2 * dr["k"])] if len(tn) > 2 * dr["k"] else tn[0]   # 軽いほど高い音（和音の音を1つおきに）
        a.note(dr["tm"], m, vel=dr["vel"], pan=.2 + .6 * (dr["x"] - GX0) / (GX1 - GX0))
        f = K.mtof(m + 12); dmp = .043 * f + .0014 * f ** 1.5; n = int(T.SR * min(.3, 8 / dmp)); tt = np.arange(n) / T.SR; i0 = int(dr["cross"][0] * T.SR)   # 上の面に落ちた瞬間の小さな水の音
        x = np.sin(2 * math.pi * f * (1 + .1 * dmp * tt) * tt) * np.exp(-dmp * tt) * np.minimum(1, tt / .0012) * .10
        if 0 <= i0 < N: k2 = min(n, N - i0); under[i0:i0 + k2] += x[:k2]
    body = K.pad([(r, r + 12, f5 + 12) for (r, t3, f5) in K.CANON], CH, NCH * CH + 5, .045); off = int(T.SR * INTRO); k2 = min(len(body), N - off); under[off:off + k2] += body[:k2]
    under *= np.clip((DUR - np.arange(N) / T.SR) / 1.5, 0, 1).astype(np.float32)
    return a.write(path, room=(.32, 3.2), under=under)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_layers", exist_ok=True)
    print("長さ", round(DUR, 1), "しずく", len(DROPS), "落ちる時間", [round(t[0], 2) for t in TR], "波の速さ", [round(c) for c in CW])
    if cmd == "stills": print(T.stills(NF, make_frame, "build_layers/s", at=(.05, .25, .5, .75, (TLAST - .8) / DUR, (TLAST + .5) / DUR))); sys.exit()
    out = f"output/layers1_{T.LANG}.mp4"; audio("build_layers/a.wav"); T.encode(NF, make_frame, "build_layers/a.wav", out); print(out)
