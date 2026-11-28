# metro3.py — メトロノーム100台。ピンク50台と水色50台が、ちょうど反対向きに振れて打ち消し合う（台は動かない＝そろい 0%）。4台だけ反対にすると？（縦のショート）
#   持ち主 11/28：「50 vs 50. A perfect tie. / In step: 0%」の画面と「これ前作ったやつ（metro2）をもとにもっと激しく、音は心地よく作りなおしましょう」
#   まねたのは仕組み（半分ずつ反対向き → 数台だけ反対にする → ぜんぶそろう）だけ。台・色・字・音は自前（前作 metro2 の白い世界とガラスの台を引きつぐ）
#   法則（蔵本モデル）：1台ずつが「台のゆれ＝みんなの振れの平均」に引きよせられる。50対50で打ち消し合うと平均が0なので、だれも引っぱられない
#     4台を反対にすると 46対54 になり、台が動きはじめる → 引く力が生まれ、そろう台がふえるほど強くなる
#   激しく：振れ幅は大きく（約50度）、台は大きくゆれる。そろったあと、最後だけテンポが上がる（持ち主 11/28「最後だけエスカレーション」）
#   音：カチッではなく、石をたたく音階の音（kalimba "stone"）。ピンクは表、水色は裏で鳴る → はじめから8分の心地よいリズム。そろうと全員で1つの和音
#   python3 tools/metro3.py stills ／ all（LANG_OUT=en で英語）→ output/metro3_<ja|en>.mp4
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS, SR = T.W, T.H, T.FPS, T.SR
NX, NZ = 10, 10; N = NX * NZ; SEED = int(os.environ.get("SEED", 2)); KC = float(os.environ.get("KC", .85)); JIT = .006; EPS = .25
TFLIP = 5.0; HOLD = 2.6; ACC = 4.4; STOP = 1.3; TAILS = 2.2; AMP = .88
rng = np.random.default_rng(SEED); IX = np.arange(N) % NX; PINK = IX < 5; PI_IDX = np.nonzero(PINK)[0]; CY_IDX = np.nonzero(~PINK)[0]
e0 = rng.uniform(-EPS, EPS, 50); om0 = 1 + rng.normal(0, JIT, 50)
FLIP = rng.choice(PI_IDX, 4, replace=False)

def simulate():
    """1コマごとに (位相, 台のゆれ, そろい) を記録。台を放したまま。そろったら少し待って、テンポを上げ、最後に止める"""
    th = np.zeros(N); om = np.zeros(N); th[PI_IDX] = e0; th[CY_IDX] = math.pi + e0; om[PI_IDX] = om0; om[CY_IDX] = om0; om *= 2 * math.pi   # ピンクと水色は、1台ずつ組になって正反対（平均がぴったり0）
    sub = 4; dt = 1 / (FPS * sub); t = 0.0; fr = []; flipped = False; tsync = None; tend = None; ev = []; amp = AMP
    while True:
        if t >= TFLIP and not flipped: th[FLIP] += math.pi; flipped = True
        if tsync is None and flipped and len(fr) > 30:
            if all(f[2] >= .995 for f in fr[-int(.8 * FPS):]): tsync = t; tend = t + HOLD + ACC + STOP
        sp = 1.0
        if tsync is not None:
            u = (t - tsync - HOLD) / ACC; sp = 1 + .95 * T.sstep(0, 1, u)                                   # 最後だけテンポが上がる
            amp = AMP * (1 - T.sstep(0, 1, (t - tsync - HOLD - ACC) / STOP))                                # そして止まる
        for _ in range(sub):
            z = np.exp(1j * th).mean(); r = abs(z); psi = math.atan2(z.imag, z.real)
            th2 = th + (om * sp + KC * r * np.sin(psi - th)) * dt
            cr = np.nonzero(np.floor(th2 / math.pi) != np.floor(th / math.pi))[0]                           # 針がまん中を通る
            if amp > .15:
                for i in cr: ev.append((t, int(i)))
            th = th2; t += dt
        z = np.exp(1j * th).mean(); r = abs(z); psi = math.atan2(z.imag, z.real); dl = np.angle(np.exp(1j * (th - psi)))
        sync = min(1.0, r / .995)   # そろい具合（みんなの振れの向きがどれだけ同じか。蔵本モデルの r）
        fr.append((th.copy(), float(np.mean(np.sin(th))) * amp / AMP, sync, amp, r))
        if tend is not None and t >= tend + TAILS: break
        if t > 80: break
    return fr, ev, tsync, tend
FR, EV, TSYNC, TEND = simulate(); NF = len(FR); DUR = NF / FPS

# ---------- 絵 ----------
SS = 2; WS, HS = W * SS, H * SS; FL = 1750 * SS
cam = np.array([0.0, 5.6, -6.4]); tg = np.array([0.0, .0, 1.75]); fw = tg - cam; fw /= np.linalg.norm(fw); rt = np.cross((0, 1, 0), fw); rt /= np.linalg.norm(rt); up = np.cross(fw, rt); CY0 = .47 * HS
def pj(P, sh=(0, 0)):
    Dv = np.asarray(P, float) - cam; z = Dv @ fw; return (WS / 2 + FL * (Dv @ rt) / z + sh[0], CY0 - FL * (Dv @ up) / z + sh[1]), z
PK, CYN, LAV = np.array((242, 108, 156.)), np.array((56, 186, 228.)), np.array((150, 128, 236.))
def mix(a, b, g): return tuple(int(a[q] * (1 - g) + b[q] * g) for q in range(3))
WHT = (246, 250, 253)
def bgimg():
    im = Image.new("RGB", (WS, HS), WHT); d = ImageDraw.Draw(im)
    for yy in range(0, HS, 4): g_ = yy / HS; d.rectangle([0, yy, WS, yy + 4], fill=mix((236, 241, 248), (212, 222, 236), g_))
    return im
BGI = bgimg()
XS, ZS = 3.9 / (NX - 1), 3.6 / (NZ - 1); BY, BT, RR = .74, .12, .30
CREF = [None]
def color_of(th_i, ref):
    g = (1 - math.cos(th_i - ref)) / 2                                                                     # 水色の組と同じ向き＝水色、反対＝ピンク、そのあいだ＝むらさき
    return tuple(int(v) for v in (CYN * (1 - g) ** 2 + LAV * 2 * g * (1 - g) + PK * g ** 2))
def make_frame(fi):
    t = fi / FPS; th, sway0, sync, amp, r = FR[fi]; im = BGI.copy(); d = ImageDraw.Draw(im, "RGBA")
    sway = -.62 * sway0                                                                                   # 台は、みんなの振れと逆向きに動く
    acc = abs(sway0 - FR[max(0, fi - 1)][1]) * 60; sh = (0.0, 0.0)
    if TSYNC is not None and t > TSYNC + HOLD: e = T.sstep(0, 1, (t - TSYNC - HOLD) / ACC) * amp / AMP; sh = (14 * SS * e * math.sin(t * 83), 9 * SS * e * math.sin(t * 117 + 1))   # 最後の速い所だけ、画面がゆれる
    P = lambda p: pj(p, sh)[0]
    d.polygon([P((x_, 0, z_)) for x_, z_ in ((-7, -1.6), (7, -1.6), (7, 6), (-7, 6))], fill=(232, 239, 246))
    for gx in np.linspace(-6, 6, 13): d.line([P((gx, 0, -1.6)), P((gx, 0, 6))], fill=(214, 224, 234), width=3)
    d.polygon([P((x_ + sway, 0.001, z_)) for x_, z_ in ((-2.25, -.4), (2.45, -.4), (2.45, 4.25), (-2.25, 4.25))], fill=(204, 214, 228))
    for rx in (-1.45, 1.45):                                                                              # ころ
        xc = rx + sway / 2; ang_ = -(sway / 2) / RR
        d.polygon([P((xc - RR, RR, -.45)), P((xc + RR, RR, -.45)), P((xc + RR, RR, 4.05)), P((xc - RR, RR, 4.05))], fill=(196, 222, 236))
        ce = [P((xc + RR * math.cos(u_), RR + RR * math.sin(u_), -.45)) for u_ in np.linspace(0, 2 * math.pi, 25)]; d.polygon(ce, fill=(214, 236, 246)); d.line(ce, fill=(120, 170, 200), width=5)
        for sk in range(3): u_ = ang_ + sk * 2 * math.pi / 3; d.line([P((xc, RR, -.45)), P((xc + RR * math.cos(u_), RR + RR * math.sin(u_), -.45))], fill=(120, 170, 200), width=4)
    top = [P((x_ + sway, BY, z_)) for x_, z_ in ((-2.3, -.45), (2.3, -.45), (2.3, 4.05), (-2.3, 4.05))]; frn = [P((x_ + sway, BY - BT, -.45)) for x_ in (-2.3, 2.3)]
    d.polygon([top[0], top[1], frn[1], frn[0]], fill=(176, 214, 232)); d.polygon(top, fill=(228, 243, 250))
    for gx in np.linspace(-2.3, 2.3, 11): d.line([P((gx + sway, BY, -.45)), P((gx + sway, BY, 4.05))], fill=(206, 228, 240), width=2)
    d.line(top + [top[0]], fill=(120, 180, 210), width=6); d.line([top[0], top[1]], fill=(255, 255, 255), width=4)
    mk = P((0, 0.002, -.75)); d.line([P((-.6, 0.002, -.75)), P((.6, 0.002, -.75))], fill=(150, 170, 190), width=6); d.line([(mk[0], mk[1] - 16), (mk[0], mk[1] + 16)], fill=(150, 170, 190), width=6)
    mx_ = P((sway, 0.002, -.75)); d.polygon([(mx_[0], mx_[1] - 12), (mx_[0] - 22, mx_[1] - 52), (mx_[0] + 22, mx_[1] - 52)], fill=(240, 110, 130))   # 台の印（ゆれが見える）
    ref = math.pi / 2 + float(th.mean()) - (4 * math.pi / N if t >= TFLIP else 0.0)                       # 色の基準：はじめの水色の組の向き（ピンクと水色のちょうど真ん中＋90度）。どちらにも寄らずにそろえば、むらさきになる
    fu = T.sstep(TFLIP, TFLIP + .5, t)
    for jz in range(NZ - 1, -1, -1):
        for ix in range(NX):
            i = jz * NX + ix; x0 = -1.95 + ix * XS + sway; z0 = jz * ZS; phi = amp * math.sin(th[i]); col = color_of(th[i], ref)
            ph_ = th[i] % math.pi; fl = math.exp(-min(ph_, math.pi - ph_) * 3.2)                             # まん中を通るとき光る
            (bx, by), zb = pj((x0, BY, z0), sh); sc = FL / zb; hgt, wb, L = .40, .11, .74
            apex = P((x0, BY + hgt, z0)); bl = P((x0 - wb, BY, z0)); br_ = P((x0 + wb, BY, z0))
            so = [P((x0 + .16 * math.cos(u_) + .05, BY + .001, z0 + .10 * math.sin(u_))) for u_ in np.linspace(0, 2 * math.pi, 13)]; d.polygon(so, fill=(206, 226, 238))
            d.polygon([bl, br_, apex], fill=mix(WHT, col, .30 + .25 * fl)); d.line([bl, apex, br_, bl], fill=mix(col, (40, 60, 80), .18), width=max(1, int(sc * .009)))
            for gq, back in ((.10, .16), (.20, .08)):                                                       # 振れのあと（激しさ）
                ph2 = amp * math.sin(th[i] - back * 2 * math.pi * (1 + (0 if TSYNC is None else .95 * T.sstep(0, 1, (t - TSYNC - HOLD) / ACC))))
                tp2 = P((x0 + L * .78 * math.sin(ph2), BY + L * .78 * math.cos(ph2), z0)); rb2 = sc * .034
                d.ellipse([tp2[0] - rb2, tp2[1] - rb2, tp2[0] + rb2, tp2[1] + rb2], fill=col + (int(255 * gq),))
            tip = P((x0 + L * math.sin(phi), BY + L * math.cos(phi), z0)); bead = P((x0 + L * .78 * math.sin(phi), BY + L * .78 * math.cos(phi), z0))
            d.line([(bx, by), tip], fill=mix(col, (40, 60, 80), .30), width=max(1, int(sc * .012)))
            rb = sc * (.040 + .016 * fl)
            d.ellipse([bead[0] - rb * 2.0, bead[1] - rb * 2.0, bead[0] + rb * 2.0, bead[1] + rb * 2.0], fill=col + (int(40 + 70 * fl),))
            d.ellipse([bead[0] - rb, bead[1] - rb, bead[0] + rb, bead[1] + rb], fill=mix(col, (255, 255, 255), .08 + .5 * fl), outline=mix(col, (40, 60, 80), .25))
            d.ellipse([bead[0] - rb * .5, bead[1] - rb * .62, bead[0] - rb * .05, bead[1] - rb * .18], fill=(255, 255, 255))
            if i in FLIP and TFLIP - .1 <= t < TFLIP + 1.6:                                                  # 反対にした4台に、輪が広がる
                e_ = max(0.0, t - TFLIP) / 1.6; rr = sc * (.12 + .5 * e_); cx_, cy_ = P((x0, BY + .3, z0)); d.ellipse([cx_ - rr, cy_ - rr, cx_ + rr, cy_ + rr], outline=(255, 255, 255, int(255 * (1 - e_))), width=int(10 * (1 - e_) + 2))
    im = im.resize((W, H), Image.LANCZOS); d = ImageDraw.Draw(im, "RGBA"); ink = (40, 56, 84, 255)
    T.fit_text(d, (W / 2, 150), T.tr("50台と50台が、正反対に振れている", "50 vs 50, swinging exactly opposite"), 54, 1000, ink)
    T.fit_text(d, (W / 2, 232), T.tr("4台だけ反対にすると？", "What if we flip just 4?"), 54, 1000, (214, 70, 120, 255) if t < TFLIP else (40, 120, 170, 255))
    d.text((W / 2, 1480), T.tr(f"そろい {int(round(sync * 100))}%", f"In step {int(round(sync * 100))}%"), font=T.fnt(78), fill=ink, anchor="mm", stroke_width=6, stroke_fill=(250, 252, 254))
    out = np.asarray(im)
    g = min(T.sstep(0, .25, t), 1 - T.sstep(DUR - .8, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)

# ---------- 音 ----------
def audio(path):
    a = T.Audio(DUR, mat="stone", max_same=4, window=.025, chord_len=2.4)
    for t, i in EV:
        ix = i % NX; tn = K.canon_tones(a.chord_index(t), 57, 86); k = ix if ix < 5 else ix - 5
        m = tn[min(len(tn) - 1, k + (0 if PINK[i] else 3))]                                                 # ピンクは低め、水色は高め。左右の位置で高さがかわる
        a.note(t, m, vel=.30, pan=.15 + .7 * ix / (NX - 1))
    if TEND is not None:
        for q, mi in enumerate((50, 57, 62, 66, 69, 74, 78)): a.note(TEND - STOP * .4 + q * .06, mi, vel=.55, pan=.2 + .1 * q)   # 止まる所で、和音
    N_ = int(SR * DUR); tt = np.arange(N_) / SR
    body = K.pad([(r_ - 12, r_, f5) for (r_, t3, f5) in K.CANON], 2.4, DUR, .035)[:N_]
    if TSYNC is not None: body = body * (1 + .8 * np.clip((tt - TSYNC) / 2, 0, 1) * np.clip((TEND - tt) / 1.0, 0, 1))
    return a.write(path, room=(.26, 2.6), under=body.astype(np.float32))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_metro3", exist_ok=True)
    print("長さ", round(DUR, 1), "そろった", None if TSYNC is None else round(TSYNC, 1), "反対にした", sorted(FLIP.tolist()), "打つ音", len(EV))
    if cmd == "sim": sys.exit()
    if cmd == "stills": print(T.stills(NF, make_frame, "build_metro3/s", at=(.02, (TFLIP + .3) / DUR, (TFLIP + 6) / DUR, ((TSYNC or 20) - 2) / DUR, ((TSYNC or 20) + HOLD + ACC * .8) / DUR, .97))); sys.exit()
    if cmd == "audio": audio("build_metro3/a.wav"); sys.exit()
    out = f"output/metro3_{T.LANG}.mp4"; audio("build_metro3/a.wav"); T.encode(NF, make_frame, "build_metro3/a.wav", out); print(out)
