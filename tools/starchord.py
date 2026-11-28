# starchord.py — 円の中ではね返る光の玉。玉の通り道は星の形になる。2つずつ（鏡写しと、1オクターブ上の双子）足していき、10個でひとつの和音になる？（縦のショート）
#   持ち主 11/28：円の中で玉がはね返って星形の軌跡を描く録画（玉が増えるたびに和音が積み上がる）を見せて「これなんかもいいね」
#   まねたのは仕組み（円の中で同じ角度ではね返る → 正しい星形。玉を足すたびに音が重なる）だけ。星の種類・色・音・増やし方は自前
#   しくみ：円の中で玉がはね返ると、入る角度と出る角度が等しいので、はね返るたびに円の中心から見て同じ角度だけ進む。
#     1回に 360°×q/p 進むと、p 回で元の場所にもどり、{p/q} の星になる（5/2 なら五芒星）
#   ペア：1つ目の玉に「鏡写し」（逆回り）を足し、鏡写しの玉は1オクターブ上で鳴る。5組10個。音はD・A・F#・E・B（どの組み合わせでもにごらない）
#   最後だけテンポが上がり（持ち主 11/28「最後だけエスカレーション」）、10個がそろって1つの和音を鳴らして止まる
#   音：ガラスの音とエコー（持ち主 11/27「ガラス系の瞑想エコー」）
#   python3 tools/starchord.py stills ／ all（LANG_OUT=en で英語）→ output/starchord1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS, SR = T.W, T.H, T.FPS, T.SR
BEAT = 60 / 76.0
STARS = [(5, 2, 1.0), (7, 3, .5), (8, 3, 2 / 3), (9, 4, .75), (12, 5, 1 / 3)]          # (p, q, はね返りの間隔［拍］)
NOTE = [62, 69, 66, 76, 71]                                                             # D4 A4 F#4 E5 B4（鏡写しは +12）
STAGE = 6 * BEAT * 1.0; TS = [.4 + STAGE * j for j in range(5)]                         # 組を足す時刻
TALL = TS[4] + STAGE; HOLD = 4 * BEAT; ACC = (48 - 34) / 1.45 * BEAT;   # 止まる瞬間がちょうど48拍目＝全員が円のふちの頂点にいる
 
TEND = TALL + HOLD + ACC; RING = 3.2; DUR = TEND + RING; NF = int(DUR * FPS)
CX, CY, R = W / 2, 960, 470
PAL = [(132, 196, 255), (176, 156, 255), (232, 146, 220), (255, 172, 156), (150, 226, 214)]   # 空色 → むらさき → 桃 → 珊瑚 → ミント（夜明けの色）
def lighten(c, g): return tuple(int(v + (255 - v) * g) for v in c)

def clock(t):
    """音楽の時間（拍）。最後だけ速くなり、TEND で止まる（そこで全員が頂点にいるよう、拍を整数にそろえる）"""
    if t < TALL + HOLD: return (t - .4) / BEAT
    u = min(1.0, (t - TALL - HOLD) / ACC); b0 = (TALL + HOLD - .4) / BEAT
    return b0 + ACC / BEAT * (u + .45 * u * u)                                           # 速さ 1 → 1.9
def beats(t): return clock(min(t, TEND))

class Ball:
    def __init__(s, j, mirror):
        p, q, gap = STARS[j]; s.p, s.q, s.gap = p, q, gap; s.dir = -1 if mirror else 1; s.t0 = TS[j]
        s.a0 = math.pi / 2 + (math.pi / p if mirror else 0) * 0 + j * .21; s.col = lighten(PAL[j], .35 if mirror else 0); s.note = NOTE[j] + (12 if mirror else 0); s.j = j; s.mirror = mirror
        s.b0 = beats(s.t0)
    def vert(s, k): a = s.a0 + s.dir * 2 * math.pi * s.q / s.p * k; return CX + R * math.cos(a), CY - R * math.sin(a)
    def pos(s, t):
        if t < s.t0: return None, -1
        u = (beats(t) - s.b0) / s.gap; k = int(math.floor(u)); f = u - k; (x0, y0), (x1, y1) = s.vert(k), s.vert(k + 1); return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f), k
BALLS = [Ball(j, m) for j in range(5) for m in (False, True)]
def hits():
    ev = []
    for b in BALLS:
        k = 1
        while True:
            bt = b.b0 + k * b.gap
            if bt > beats(TEND) + 1e-6: break
            lo, hi = b.t0, TEND                                                                  # 拍 → 時刻（二分法）
            for _ in range(40):
                m = (lo + hi) / 2
                if beats(m) < bt: lo = m
                else: hi = m
            ev.append((hi, b, k)); k += 1
    return sorted(ev, key=lambda e: e[0])
EV = hits()

BG = T.background((CX, CY)) * .55; GS = T.glow(14); GB = T.glow(40)
def make_frame(fi):
    t = fi / FPS; buf = BG.copy(); ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    fin = max(0.0, t - TEND); fade = math.exp(-fin * .9) if fin > 0 else 1.0
    d.ellipse([CX - R - 6, CY - R - 6, CX + R + 6, CY + R + 6], outline=(150, 160, 210, 120), width=3)
    nb = 0; live = []
    for b in BALLS:
        P, k = b.pos(min(t, TEND))
        if P is None: continue
        nb += 1; live.append((b, P, k)); n_lines = min(k + 1, b.p)                                     # 1周したら星は完成（それ以上は重ねない）
        age = beats(min(t, TEND)) - b.b0; al = min(1.0, .25 + .75 * min(1, age / (b.gap * b.p)))
        pts = [b.vert(i) for i in range(max(0, k - b.p + 1), k + 1)] + [P]
        w = 3 if b.mirror else 4
        d.line(pts, fill=b.col + (int(70 * al * fade),), width=w + 6, joint="curve"); d.line(pts, fill=b.col + (int(235 * al * fade),), width=w, joint="curve")
    for b, P, k in live:                                                                            # 玉と、壁に当たった所の光
        T.add_glow(buf, GS, P[0], P[1], b.col, .9 * fade); r = 9 if not b.mirror else 7; d.ellipse([P[0] - r, P[1] - r, P[0] + r, P[1] + r], fill=(255, 255, 255, int(255 * fade)))
    for te, b, k in EV:
        if te > t: break
        e = t - te
        if e < .7: vx, vy = b.vert(k); T.add_glow(buf, GB, vx, vy, b.col, .55 * math.exp(-e * 5)); rr = 12 + 50 * e; d.ellipse([vx - rr, vy - rr, vx + rr, vy + rr], outline=b.col + (int(200 * (1 - e / .7)),), width=3)
    if fin > 0: T.add_glow(buf, GB, CX, CY, (220, 210, 255), .5 * math.exp(-fin * 1.6))
    T.fit_text(d, (W / 2, 190), T.tr("円の中ではね返る玉。10個で、ひとつの和音になる？", "Balls bouncing in a circle. Can 10 make one chord?"), 54, 1000, (240, 242, 255, 255))
    d.text((W / 2, 1580), str(nb), font=T.fnt(130), fill=(244, 244, 255, 255), anchor="mm"); d.text((W / 2, 1680), T.tr("個", "BALLS" if nb != 1 else "BALL"), font=T.fnt(40), fill=(190, 196, 236, 255), anchor="mm")
    out = np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB"))
    g = min(T.sstep(0, .3, t), 1 - T.sstep(DUR - .9, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)

def audio(path):
    a = T.Audio(DUR, mat="glass", max_same=6, window=.02, chord_len=2.4)
    for te, b, k in EV:
        if te >= TEND - 1e-3: continue
        a.note(te, b.note, vel=.30 if b.mirror else .36, pan=float(np.clip((b.vert(k)[0] - CX) / R * .4 + .5, .1, .9)))
    for q, b in enumerate(BALLS): a.note(TEND + q * .035, b.note, vel=.5, pan=.15 + .07 * q)        # 止まる所で、10個が1つの和音
    for m in (38, 50): a.note(TEND, m, vel=.45, pan=.5)
    N_ = int(SR * DUR); tt = np.arange(N_) / SR
    body = K.pad([(50, 57, 62)] * 8, 2.4, DUR, .03)[:N_] * np.clip((tt - .4) / 3, 0, 1)                # D の上で、ずっと静かな持続音
    return a.write(path, room=(.34, 3.4), under=body.astype(np.float32))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_starchord", exist_ok=True)
    print("長さ", round(DUR, 1), "全員", round(TALL, 1), "止まる", round(TEND, 1), "音", len(EV))
    if cmd == "stills": print(T.stills(NF, make_frame, "build_starchord/s", at=(.03, (TS[1] + 2) / DUR, (TS[3] + 2) / DUR, (TALL + 1) / DUR, (TEND - .5) / DUR, (TEND + 1) / DUR))); sys.exit()
    if cmd == "audio": audio("build_starchord/a.wav"); sys.exit()
    out = f"output/starchord1_{T.LANG}.mp4"; audio("build_starchord/a.wav"); T.encode(NF, make_frame, "build_starchord/a.wav", out); print(out)
