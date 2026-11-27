# chordwood.py — カノン進行を、落ちるボールで鳴らすと？ 18秒後に、全部がまた同時に着地する（縦のショート 1080×1920・60コマ）
#   持ち主 11/28：妄想 chord1（いちばん切ない和音を、落ちるボールで鳴らすと？）の画面を見せて「これの234verカノン。木っぽいテクスチャで質感は少し柔らかいエフェクトで」
#   決まりは chord1 と同じ：10個のボールが、それぞれの板の上ではね続ける。18秒の間に、左から 12, 13, …, 21 回はねる（周期 18/12 … 18/21 秒）。
#     はねる高さは周期の2乗に比例（同じ重力で落ちるから）。だから少しずつずれて波になり、9秒で1つおきにそろい、18秒で全部そろう
#   変えたところ：
#     ・音の高さ：カノン進行（D A Bm F#m G D G A）。和音は 18/8 秒ごとに1つ進み、板の音は「今の和音の音」を低い方から順に。18秒で1周して、最初の D にもどる所で全部そろう
#     ・音色：2・3・4（木・竹・空洞のある木）を、板ごとに順に（左から 木・竹・空洞・木…）。当たった瞬間に1打だけ
#     ・絵：木の板と、木目の柱（うしろの柱＝はねる高さ）。暗い木の背景。ボールはやわらかい色。着地でボールが少しつぶれ、板が少ししずみ、板にやわらかい光が広がる
#   python3 tools/chordwood.py stills ／ all（LANG_OUT=en で英語）→ output/chordwood1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS = T.W, T.H, T.FPS
NB, CYC, INTRO, OUTRO = 10, 18.0, .9, 2.8
DUR = INTRO + CYC + OUTRO; NF = int(DUR * FPS)
PER = [CYC / (12 + i) for i in range(NB)]; HMAX = 760.0; G = 8 * HMAX / PER[0] ** 2; HT = [G * p * p / 8 for p in PER]
XL, XR, PADY = 72, 1008, 1330; DX = (XR - XL) / NB; RB = 25; MATS3 = ("wood", "bamboo", "hollow")
CHL = CYC / 8                                                          # 和音1つの長さ（18秒で8つ＝1周）
NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def chord_at(t): return int(math.floor((t - INTRO + 1e-6) / CHL)) % 8 if t >= INTRO - 1e-6 else 0
def tones(ci): return K.canon_tones(ci, 52, 110)[:NB]          # 低い方から10音（およそ E3〜F#6）
def col(i):                                                            # やわらかい色：桃 → 橙 → 黄
    u = i / (NB - 1); a, b, c = np.array([238, 128, 150.]), np.array([246, 170, 104.]), np.array([240, 214, 112.])
    return tuple(int(v) for v in (a + (b - a) * min(1, u * 2) if u < .5 else b + (c - b) * (u * 2 - 1)))
def ypos(i, t):
    """板の上からの高さ。t=INTRO で全員が着地。その前は、上から落ちてくる"""
    if t < INTRO: tau = PER[i] / 2 - (INTRO - t); return max(0.0, HT[i] - .5 * G * (tau + PER[i] / 2 - PER[i] / 2) ** 2) if tau >= 0 else HT[i]
    ph = ((t - INTRO) % PER[i]); return .5 * G * ph * (PER[i] - ph)
def landings():
    ev = []
    for i in range(NB):
        k = 0
        while True:
            t = INTRO + k * PER[i]
            if t > DUR - .3: break
            ev.append((t, i)); k += 1
    return sorted(ev)
EV = landings(); TE = np.array([e[0] for e in EV])

# ---------- 絵 ----------
def board(w, h, seed, tones_=T.WOOD, vertical=False):
    if vertical: b = T.wood_stack(h, w, 1, seed=seed, gap=0, tones=tones_); return np.ascontiguousarray(np.rot90(b))
    return T.wood_stack(w, h, 1, seed=seed, gap=0, tones=tones_)
DARK = (np.array([.30, .20, .13], np.float32), np.array([.22, .14, .09], np.float32))
def make_bg():
    b = np.zeros((H, W, 3), np.float32)
    panel = T.wood_stack(W, 160, 12, seed=77, gap=3, tones=DARK)       # 暗い木の壁（横板）
    b[:panel.shape[0]] = panel[..., :3] * panel[..., 3:4]; b[panel.shape[0]:] = panel[-1:, :, :3] * .6
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    b *= (1 - .55 * np.clip(np.hypot((xx - W / 2) / W, (yy - 1000) / H) * 1.6 - .2, 0, 1) ** 1.5)[..., None]   # まわりを落とす
    b *= .62; b += (np.exp(-((yy - 900) / 700) ** 2) * .05)[..., None] * np.array([1, .8, .6], np.float32)
    return np.clip(b, 0, 1).astype(np.float32)
BG = make_bg()
PILLAR = [board(int(DX) - 30, int(HT[i]), 40 + i, (np.array([.80, .62, .42], np.float32), np.array([.64, .45, .28], np.float32)), vertical=True) for i in range(NB)]
PAD = [board(int(DX) - 14, 34, 60 + i) for i in range(NB)]
SPR = [T.sprite(col(i), RB) for i in range(NB)]; GL = T.glow(46); GLS = T.glow(22)
f_note = T.fnt(40); f_cnt = T.fnt(64)
def squash(sp, k):
    """ボールを縦に k 倍（面積はそのまま）。下はしをそろえる"""
    h, w = sp.shape[:2]; nh, nw = max(2, int(round(h * k))), max(2, int(round(w / math.sqrt(k))))
    return cv2.resize(sp, (nw, nh), interpolation=cv2.INTER_LINEAR)

def make_frame(fi):
    t = fi / FPS; buf = BG.copy(); ci = chord_at(t); tn = tones(ci)
    for i in range(NB):                                                # 柱（はねる高さ）
        x = XL + (i + .5) * DX; pl = PILLAR[i]; T.paste(buf, pl, int(x - pl.shape[1] / 2), int(PADY - pl.shape[0]), .26)
    nland = int(np.searchsorted(TE, t, "right"))
    for i in range(NB):
        x = XL + (i + .5) * DX; ks = [e[0] for e in EV if e[1] == i and e[0] <= t]; e_ = t - ks[-1] if ks else 9.0
        dip = 6 * math.exp(-e_ / .07) * math.sin(math.pi * min(1, e_ / .14)) if e_ < .4 else 0.0
        if e_ < .6: T.add_glow(buf, GL, x, PADY + 6 + dip, col(i), .55 * math.exp(-e_ / .16))      # 板にやわらかい光
        T.paste(buf, PAD[i], int(x - PAD[i].shape[1] / 2), int(PADY + dip))
        y = ypos(i, t); k = 1 - .16 * math.exp(-e_ / .045) if e_ < .25 else 1.0                       # 着地で少しつぶれる
        sp = SPR[i] if k > .995 else squash(SPR[i], k); yc = PADY + dip - y - sp.shape[0] / 2 + 4
        T.add_glow(buf, GLS, x, PADY + dip - y - RB, col(i), .10)
        T.blit(buf, sp, x, yc)
    def draw(d):
        INK = (246, 238, 226, 255)
        T.fit_text(d, (W / 2, 168), T.tr("カノン進行を", "Pachelbel's Canon chords,"), 66, 980, (255, 214, 128, 255))
        T.fit_text(d, (W / 2, 252), T.tr("落ちるボールで鳴らすと？", "played by falling balls?"), 66, 980, INK)
        d.text((W / 2, 344), T.tr(f"鳴った音 {nland}", f"Notes played {nland}"), font=T.fnt(44), fill=(232, 224, 210, 255), anchor="mm")
        for i in range(NB):
            x = XL + (i + .5) * DX; d.text((x, PADY + 80), NOTE[tn[i] % 12], font=f_note, fill=(236, 226, 210, 255), anchor="mm")
        names = ["D", "A", "Bm", "F#m", "G", "D", "G", "A"]
        if t >= INTRO: d.text((W / 2, PADY + 156), T.tr(f"いまの和音  {names[ci]}", f"Now: {names[ci]}"), font=T.fnt(38, False), fill=(214, 200, 180, 255), anchor="mm")
        cap = None; tc = t - INTRO
        if 8.7 <= tc < 10.4: cap = T.tr("1つおきに、そろった", "Every other ball lines up")
        if tc >= CYC - .15: cap = T.tr("18秒後、全部そろった", "18 seconds later, all together again")
        if cap:
            a0 = (INTRO + 8.7) if tc < 12 else (INTRO + CYC - .15); a = int(255 * min(1, (t - a0) / .25))
            T.fit_text(d, (W / 2, 1640), cap, 54, 980, (255, 226, 150, a))
        T.fit_text(d, (W / 2, 1790), T.tr("左から 12回、13回 … 21回。18秒でちょうど整数回はねる", "From left: 12, 13 … 21 bounces in exactly 18 s"), 32, 980, (190, 178, 160, 255), bold=False)
    out = T.to_frame(buf, draw, grain=fi); g = min(T.sstep(0, .3, t), 1 - T.sstep(DUR - .5, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)

def audio(path):
    a = T.Audio(DUR, mat="wood", max_same=6, window=.012)
    for (t, i) in EV:
        m = tones(chord_at(t))[i]; a.note(t, m, vel=.62 + .25 * (1 - i / NB), pan=.15 + .7 * i / (NB - 1), mat=MATS3[i % 3])
    under = K.pad([(r, r + 12, f5 + 12) for (r, t3, f5) in K.CANON], CHL, DUR + .5, .035)
    under = np.concatenate([np.zeros(int(T.SR * INTRO), np.float32), under])[: int(T.SR * DUR)]
    return a.write(path, room=(.14, 1.1), under=under)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_chordwood", exist_ok=True)
    print("長さ", round(DUR, 2), "着地", len(EV))
    if cmd == "stills": print(T.stills(NF, make_frame, "build_chordwood/s", at=(.03, .2, (INTRO + 9.0) / DUR, .6, (INTRO + CYC + .2) / DUR))); sys.exit()
    out = f"output/chordwood1_{T.LANG}.mp4"; audio("build_chordwood/a.wav"); T.encode(NF, make_frame, "build_chordwood/a.wav", out); print(out)
