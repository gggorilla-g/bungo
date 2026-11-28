# stitch.py — 糸かけ（カーブステッチ）：まっすぐな線だけで、曲線は描ける？ 最後は円になる？（縦のショート）
#   持ち主 11/28：紙の上でジグザグの角に色糸の直線を順にかけ、曲線が浮かび上がる録画を見せた（コメントなし）
#   まねたのは仕組み（角をはさむ2本の辺に等間隔の点をとり、片方は内から、もう片方は外から順に結ぶと、直線の包絡線が放物線になる）だけ。図形・色・音は自前
#   1) ジグザグの3つの角（ゆっくり。1本ずつ）
#   2) 中心から8本の線：となりどうしを結んで、8枚の花びら（だんだん速く）
#   3) 円の上に72個の点。k 番と k+m 番を結ぶ弦だけを引くと、内側に円が浮かぶ（m＝28・20・12 で3重の円。最後だけ速く、最後に止まる）
#   音：線を1本引くたびに、石をたたく音（kalimba "stone"）。線が角から遠いほど低い。和音はカノン進行（隠し味）。うしろに静かな持続音
#   python3 tools/stitch.py stills ／ all（LANG_OUT=en で英語）→ output/stitch1_<ja|en>.mp4
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS, SR = T.W, T.H, T.FPS, T.SR
SS = 2
PAPER = (236, 233, 226); INK = (44, 46, 56)
RED, BLUE = (214, 74, 96), (52, 104, 196)
PAL = [(214, 74, 96), (52, 104, 196), (232, 150, 60), (40, 150, 140), (130, 90, 190), (60, 130, 200), (200, 90, 150), (90, 160, 90)]

def corner(P, A, B, n):
    """角 P をはさむ辺 PA・PB に n 等分の点。A 側の i 番と、B 側の n−i 番を結ぶ（i=1..n−1）"""
    P, A, B = map(np.array, (P, A, B)); out = []
    for i in range(1, n):
        a = P + (A - P) * i / n; b = P + (B - P) * (n - i) / n; out.append((a, b, i / n))
    return out

def build():
    """線の並び：(引き始め時刻, 長さ[秒], 点a, 点b, 色, 音の高さの順番(0..1), 区間)"""
    L = []; t = .6
    zz = [(200, 520), (880, 760), (200, 1000), (880, 1240), (200, 1480)]                    # 1) ジグザグ
    for k in range(1, 4):
        n = 18; ls = corner(zz[k], zz[k - 1], zz[k + 1], n)
        for j, (a, b, u) in enumerate(ls):
            L.append((t, .16, a, b, RED, u, 0)); t += .085
            a2 = a + (np.array(zz[k - 1]) - np.array(zz[k])) * (.5 / n); b2 = b - (np.array(zz[k + 1]) - np.array(zz[k])) * (.5 / n)   # 半分ずらした青い糸
            L.append((t, .16, a2, b2, BLUE, u, 0)); t += .085
    TA = t + .9; t = TA
    C = np.array((540, 1000)); R = 390; sp = [C + R * np.array((math.cos(math.pi / 2 + 2 * math.pi * k / 8), -math.sin(math.pi / 2 + 2 * math.pi * k / 8))) for k in range(8)]
    n = 16; dt = .95                                                                          # 2) 8枚の花びら（8つの角を同時に、だんだん速く）
    for i in range(1, n):
        for k in range(8):
            a = C + (sp[k] - C) * i / n; b = C + (sp[(k + 1) % 8] - C) * (n - i) / n
            L.append((t + k * dt / 8, .22, a, b, PAL[k], i / n, 1))
        t += dt; dt = max(.40, dt * .93)
    TB = t + .9; t = TB
    NP, RC = 72, 405; oc = [C + RC * np.array((math.cos(2 * math.pi * k / NP - math.pi / 2), math.sin(2 * math.pi * k / NP - math.pi / 2))) for k in range(NP)]   # 3) 円のまわりに72個の点。k 番と k+m 番を結ぶ弦だけで、内側に円が浮かぶ（半径 R·cos(πm/72)）
    mid = None; dt = .10
    for m, col in ((28, (214, 74, 96)), (20, (40, 150, 140)), (12, (232, 150, 60))):
        for k in range(NP):
            L.append((t, .16, oc[k], oc[(k + m) % NP], col, k / NP, 2)); t += dt; dt = max(.034, dt * .985)   # だんだん速く
    return L, TA, TB, t, C, sp, oc, mid, zz
LINES, TA, TB, TEND, C0, SPOKES, OCT, MIDS, ZZ = build(); TEND += .3; DUR = TEND + 2.8;   # 最後は白紙にもどり頭につながる（ループ。持ち主 11/28「基本的にはループ構造ね」）
NF = int(DUR * FPS)

def paper():
    rng = np.random.default_rng(3); a = np.full((H * SS, W * SS, 3), PAPER, np.float32)
    a += rng.normal(0, 2.2, (H * SS, W * SS, 1)).astype(np.float32)
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)); return im
PAPER_IM = paper()
def guides(d, sec, fade=1.0):
    """鉛筆の点線（下書き）"""
    c = (150, 150, 158, int(200 * fade))
    def dotted(p, q, n=26):
        for s in np.linspace(0, 1, n):
            x, y = (p + (q - p) * s) * SS; d.ellipse([x - 2.6, y - 2.6, x + 2.6, y + 2.6], fill=c)
    if sec == 0:
        for k in range(4): dotted(np.array(ZZ[k], float), np.array(ZZ[k + 1], float), 30)
    elif sec == 1:
        for p in SPOKES: dotted(C0, p, 16)
    else:
        for p in OCT: x, y = p * SS; d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=c)
CACHE = {"fi": -1, "im": None, "sec": -1, "done": 0}
def sec_at(t): return 0 if t < TA else (1 if t < TB else 2)
def base_for(sec):
    im = PAPER_IM.copy(); d = ImageDraw.Draw(im, "RGBA"); guides(d, sec); return im
def make_frame(fi):
    t = fi / FPS; sec = sec_at(t)
    if CACHE["fi"] > fi or CACHE["sec"] != sec or CACHE["im"] is None:                         # 区間が変わったら、新しい紙に（線は区間ごと）
        CACHE.update(im=base_for(sec), sec=sec, done=0)
    im = CACHE["im"]; d = ImageDraw.Draw(im, "RGBA")
    while CACHE["done"] < len(LINES):                                                          # 引き終わった線を紙に描きこむ
        ts, ln, a, b, col, u, s = LINES[CACHE["done"]]
        if ts + ln > t: break
        if s == sec: d.line([tuple(a * SS), tuple(b * SS)], fill=col + (235,), width=3)
        CACHE["done"] += 1
    CACHE["fi"] = fi
    fr = im.copy(); d2 = ImageDraw.Draw(fr, "RGBA"); live = 0
    for k in range(CACHE["done"], min(len(LINES), CACHE["done"] + 40)):                         # 引いている途中の線（ペン先が走る）
        ts, ln, a, b, col, u, s = LINES[k]
        if ts > t: break
        if s != sec: continue
        f = (t - ts) / ln; e = a + (b - a) * f; d2.line([tuple(a * SS), tuple(e * SS)], fill=col + (235,), width=3)
        d2.ellipse([e[0] * SS - 7, e[1] * SS - 7, e[0] * SS + 7, e[1] * SS + 7], fill=col + (255,)); live += 1
    out = fr.resize((W, H), Image.LANCZOS); d3 = ImageDraw.Draw(out, "RGBA")
    nlines = sum(1 for L_ in LINES if L_[0] + L_[1] <= t)
    q = [T.tr("まっすぐな線だけで、曲線は描ける？", "Can straight lines draw a curve?"), T.tr("まっすぐな線だけで、花は描ける？", "Can straight lines draw a flower?"), T.tr("まっすぐな線だけで、円は描ける？", "Can straight lines draw a circle?")][sec]
    T.fit_text(d3, (W / 2, 175), q, 56, 840, (40, 42, 52, 255))
    d3.text((W / 2, 1720), T.tr(f"線 {nlines} 本", f"{nlines} lines"), font=T.fnt(48), fill=(70, 72, 84, 255), anchor="mm")
    arr = np.asarray(out).astype(np.float32)
    for tb in (TA, TB):                                                                         # 区間の変わり目：紙がふわっと替わる
        if tb - .35 < t < tb + .35: arr = arr * (.55 + .45 * abs(t - tb) / .35) + PAPER[0] * (1 - (.55 + .45 * abs(t - tb) / .35))
    if t > TEND: g = .10 * math.exp(-(t - TEND) * 1.5); arr = arr * (1 - g) + 255 * g
    if t > DUR - 1.1:                                                                            # 最後の1.1秒で、最初の画面（白紙・線0本）にもどる
        e = T.sstep(DUR - 1.1, DUR - .05, t); arr = arr * (1 - e) + first_frame() * e
    return np.clip(arr, 0, 255).astype(np.uint8)
FIRST = []
def first_frame():
    if not FIRST:
        b = base_for(0).resize((W, H), Image.LANCZOS); d4 = ImageDraw.Draw(b, "RGBA")
        T.fit_text(d4, (W / 2, 175), T.tr("まっすぐな線だけで、曲線は描ける？", "Can straight lines draw a curve?"), 56, 840, (40, 42, 52, 255))
        d4.text((W / 2, 1720), T.tr("線 0 本", "0 lines"), font=T.fnt(48), fill=(70, 72, 84, 255), anchor="mm"); FIRST.append(np.asarray(b).astype(np.float32))
    return FIRST[0]

def audio(path):
    a = T.Audio(DUR, mat="stone", max_same=3, window=.03, chord_len=2.4)
    last = -1
    for ts, ln, aa, bb, col, u, s in LINES:
        if s >= 1 and ts - last < .045: continue                                                # 速いところは間引く
        last = ts; tn = K.canon_tones(a.chord_index(ts), 60, 88); m = tn[min(len(tn) - 1, int((1 - u) * (len(tn) - 1) + .5))]   # 角に近い線ほど高い
        a.note(ts + ln * .5, m, vel=.30 if s == 0 else .24, pan=float(np.clip((aa[0] + bb[0]) / 2 / W, .15, .85)))
    for q, m in enumerate((50, 57, 62, 66, 69, 74)): a.note(TEND + q * .05, m, vel=.38, pan=.3 + .08 * q)   # 最後の和音
    N_ = int(SR * DUR); tt = np.arange(N_) / SR
    body = K.pad([(r - 12, r, f5) for (r, t3, f5) in K.CANON], 2.4, DUR, .03)[:N_] * np.clip(tt / 2, 0, 1)
    return a.write(path, room=(.24, 2.2), under=body.astype(np.float32))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_stitch", exist_ok=True)
    print("長さ", round(DUR, 1), "区切り", round(TA, 1), round(TB, 1), round(TEND, 1), "線", len(LINES))
    if cmd == "stills": print(T.stills(NF, make_frame, "build_stitch/s", at=(.05, (TA - .5) / DUR, (TB - .5) / DUR, (TB + 3) / DUR, (TEND + 1) / DUR))); sys.exit()
    if cmd == "audio": audio("build_stitch/a.wav"); sys.exit()
    out = f"output/stitch1_{T.LANG}.mp4"; audio("build_stitch/a.wav"); T.encode(NF, make_frame, "build_stitch/a.wav", out); print(out)
