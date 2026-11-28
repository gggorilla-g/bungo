# lineup.py — ひまわりの種のように並んだ玉。ぜんぶ下のびんにこぼしてばらばらにしても、もとの模様にもどる？（縦のショート・ループ）
#   持ち主 11/28：玉の円盤が中央の穴から流れ出て、また渦の模様に並び直す録画を見せて「基本的にはループ構造ね」「バラバラなものが統一されるのとかも気持ちいいっぽいです」
#   まねたのは仕組み（整った模様 → ばらばら → 並び直す → 最初にもどる）だけ。並び方（黄金角の渦）・色・びん・音・もどり方は自前
#   しくみ：k 番目の玉を、中心からの距離 c√k、角度 k×137.5°（黄金角）に置くと、ひまわりの種の並びになる。
#     k を 8 で割った余りで色を分けると、8本の渦の腕に見える。玉は自分の番地をおぼえていて、腕ごとに、中心から外へ順にもどる
#   ループ：円盤は動画の長さでちょうど1回転する。最後の画面 ＝ 最初の画面
#   音：腕が1本もどるごとに、カノン進行の和音を1つ（隠し味。持ち主 11/28）。玉が番地に収まる瞬間だけ鳴らす。びんに落ちる音は小さく
#   python3 tools/lineup.py stills ／ all（LANG_OUT=en で英語）→ output/lineup1_<ja|en>.mp4
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS, SR = T.W, T.H, T.FPS, T.SR
BPM = 72; BEAT = 60 / BPM
N, RB, CSP = 296, 13.0, 17.2                     # 玉の数・半径・並びの間隔
CX, CY = 540, 760                                  # 円盤の中心（玉は x 230〜850 に収まる）
GA = math.pi * (3 - math.sqrt(5))                  # 黄金角
ARMS = 21                                          # 色の腕の数（21本だと渦がいちばんくっきり見える。数で試した：8・13・21・34）
WAVES = 8                                          # もどる区切り＝カノンの和音8つ
JX0, JX1, JY0, JY1, JRC = 150, 930, 1190, 1660, 120     # びん（左右の壁・口・底・底の角の丸み）
T1 = 2.4                                           # こぼれ始め
TPOUR = 1.8                                        # 下の玉から上の玉へ、こぼれ出す時間
T3 = 9.6                                           # もどり始め
ARM_DT = 2 * BEAT                                  # 腕1本 = 2拍
FLY = .62                                          # 1個がびんから番地へ飛ぶ時間
TALL = T3 + WAVES * ARM_DT                          # 全部そろう
DUR = TALL + 3.4; NF = int(round(DUR * FPS))
OMEGA = 2 * math.pi / DUR                          # 動画の長さでちょうど1回転（ループ）
import colorsys
PAL = [tuple(int(255 * v) for v in colorsys.hls_to_rgb(j / ARMS, .74, .8)) for j in range(ARMS)]   # 腕ごとに色相を少しずつ（虹の渦）

K_ = np.arange(N); RHO = CSP * np.sqrt(K_ + .5); PHI = K_ * GA; ARM = K_ % ARMS
def home(t, idx=slice(None)):
    a = PHI[idx] + OMEGA * t; return np.stack([CX + RHO[idx] * np.cos(a), CY + RHO[idx] * np.sin(a)], -1)

# もどる順：腕 0 → 7、腕の中は中心から外へ
ORDER = sorted(range(N), key=lambda k: (ARM[k], RHO[k]))
LAUNCH = np.zeros(N); SPAN = WAVES * ARM_DT - FLY - .1
for i, k in enumerate(ORDER): LAUNCH[k] = T3 + SPAN * i / (N - 1)                   # 腕を1本ずつ、中心から外へ、一定の速さで
ARRIVE = LAUNCH + FLY

def simulate():
    """びんの中の玉（位置で解く簡単な物理）。こぼれる前と、飛びたったあとの玉は動かさない"""
    rng = np.random.default_rng(5); SUB = 8; dt = 1 / (FPS * SUB); g = 2600.0
    P = home(0.0).copy(); Q = P.copy(); y0 = home(T1 + TPOUR / 2)[:, 1]                   # こぼれる頃の向きで、下にある玉から
    REL = T1 + TPOUR * (1 - (y0 - y0.min()) / (y0.max() - y0.min())) ** 1.0 + rng.uniform(0, .08, N)   # 下の玉から順にこぼれる
    state = np.zeros(N, int)                                                   # 0 円盤の上  1 落ちている／びんの中  2 飛んで帰った
    POS = np.zeros((NF, N, 2), np.float32); HITS = []
    lastv = np.zeros(N)
    for fi in range(NF):
        t0 = fi / FPS
        for s in range(SUB):
            t = t0 + s * dt
            st0 = state == 0; P[st0] = home(t, st0); Q[st0] = home(t - dt, st0)       # 円盤といっしょに回る
            nw = (state == 0) & (t >= REL); state[nw] = 1
            Q[nw] = P[nw] - (home(t, nw) - home(t - dt, nw)) + rng.normal(0, .02, (nw.sum(), 2))   # 回っていた速さのまま放す
            gone = (state == 1) & (t >= LAUNCH); state[gone] = 2
            act = state == 1
            if not act.any(): continue
            ia = np.nonzero(act)[0]
            gx = 260 * math.sin(2 * math.pi * (t - 6.4) / 3.2) * T.sstep(6.2, 7.0, t) * (1 - T.sstep(8.6, 9.4, t))   # びんを少しゆらす
            V = (P[ia] - Q[ia]) * .9995; vm = np.linalg.norm(V, axis=1, keepdims=True); V *= np.minimum(1, 1400 * dt / (vm + 1e-9)); Q[ia] = P[ia]; P[ia] = P[ia] + V + np.array([gx, g]) * dt * dt   # 速さに上限（押し合いで弾け飛ばない）
            for it in range(3):
                X = P[ia]; D = X[:, None, :] - X[None, :, :]; L = np.sqrt((D ** 2).sum(-1)) + 1e-6
                ov = np.clip(2 * RB - L, 0, None); np.fill_diagonal(ov, 0)
                P[ia] += (D / L[..., None] * ov[..., None] * .5).sum(1) * .9
                X = P[ia]
                inj = X[:, 1] > JY0 - RB                                           # びんの中だけ壁がある（上から落ちてくる間は素通り）
                X[:, 0] = np.where(inj, np.clip(X[:, 0], JX0 + RB, JX1 - RB), X[:, 0]); X[:, 1] = np.minimum(X[:, 1], JY1 - RB)
                for cx_ in (JX0 + JRC, JX1 - JRC):                                 # 底の角の丸み
                    cy_ = JY1 - JRC; dx = X[:, 0] - cx_; dy = X[:, 1] - cy_
                    m = (dy > 0) & (np.sign(dx) == np.sign(cx_ - W / 2)) ; r = np.sqrt(dx * dx + dy * dy) + 1e-6
                    out = m & (r > JRC - RB); X[out, 0] = cx_ + dx[out] / r[out] * (JRC - RB); X[out, 1] = cy_ + dy[out] / r[out] * (JRC - RB)
                P[ia] = X
        sp = np.linalg.norm(P - Q, axis=1) * FPS * SUB                                   # ぶつかって急に止まった玉（落ちる音の候補）
        drop = (state == 1) & (lastv - sp > 700); HITS += [(t0, k, float(P[k, 0])) for k in np.nonzero(drop)[0]]
        lastv = np.where(state == 1, sp, 0)
        POS[fi] = P
    return POS, HITS, REL
POS, HITS, REL = simulate()

def ball_pos(fi):
    t = fi / FPS; P = POS[fi].copy()
    fl = (t >= LAUNCH) & (t < ARRIVE)                                                 # 飛んでいる玉：びんの中の最後の位置から、番地へ弧を描いて
    if fl.any():
        idx = np.nonzero(fl)[0]; f0 = np.clip(np.round(LAUNCH[idx] * FPS).astype(int) - 1, 0, NF - 1)
        A = POS[f0, idx]; B = home(t, idx); u = (t - LAUNCH[idx]) / FLY; e = u * u * (3 - 2 * u)
        Cn = (A + B) / 2 + np.stack([np.zeros(len(idx)), -np.full(len(idx), 240.0)], -1)
        P[idx] = ((1 - e) ** 2)[:, None] * A + (2 * (1 - e) * e)[:, None] * Cn + (e * e)[:, None] * B
    hm = t >= ARRIVE; P[hm] = home(t, hm)
    return P, fl

SS = 2; BGC = np.array([18, 20, 34], np.float32)
def bg_image():
    y = np.linspace(0, 1, H)[:, None, None]; c0 = np.array([24, 26, 44]); c1 = np.array([12, 14, 26])
    a = (c0 * (1 - y) + c1 * y) * np.ones((1, W, 1)); return Image.fromarray(a.astype(np.uint8)).resize((W * SS, H * SS)).convert("RGBA")
BG = bg_image()
SPR = {}
def sprite(col, glow=False):
    key = (col, glow)
    if key not in SPR:
        s = int(RB * SS * 2 + 6); im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = s / 2; r = RB * SS
        d.ellipse([c - r, c - r, c + r, c + r], fill=col + (255,))
        hl = tuple(int(v + (255 - v) * .55) for v in col); d.ellipse([c - r * .55, c - r * .62, c - r * .02, c - r * .1], fill=hl + (200,))
        SPR[key] = im
    return SPR[key]

def make_frame(fi):
    t = fi / FPS; im = BG.copy(); d = ImageDraw.Draw(im, "RGBA")
    rr = (CSP * math.sqrt(N) + RB + 14) * SS                                             # 円盤のふち（うすく）
    d.ellipse([CX * SS - rr, CY * SS - rr, CX * SS + rr, CY * SS + rr], outline=(150, 156, 210, 70), width=3 * SS // 2)
    jl = [(JX0, JY0 - 30), (JX0, JY1 - JRC)]; d.line([(x * SS, y * SS) for x, y in jl], fill=(170, 180, 220, 110), width=3 * SS)  # びん
    d.line([(JX1 * SS, (JY0 - 30) * SS), (JX1 * SS, (JY1 - JRC) * SS)], fill=(170, 180, 220, 110), width=3 * SS)
    d.arc([JX0 * SS, (JY1 - 2 * JRC) * SS, (JX0 + 2 * JRC) * SS, JY1 * SS], 90, 180, fill=(170, 180, 220, 110), width=3 * SS)
    d.arc([(JX1 - 2 * JRC) * SS, (JY1 - 2 * JRC) * SS, JX1 * SS, JY1 * SS], 0, 90, fill=(170, 180, 220, 110), width=3 * SS)
    d.line([((JX0 + JRC) * SS, JY1 * SS), ((JX1 - JRC) * SS, JY1 * SS)], fill=(170, 180, 220, 110), width=3 * SS)
    P, fl = ball_pos(fi)
    order = np.argsort(fl.astype(int), kind="stable")                                     # 飛んでいる玉を手前に
    for k in order:
        x, y = P[k]; sp = sprite(PAL[ARM[k]]); s = sp.size[0]
        im.alpha_composite(sp, (int(x * SS - s / 2), int(y * SS - s / 2)))
    out = im.resize((W, H), Image.LANCZOS)
    arr = np.asarray(out.convert("RGB")).astype(np.float32)
    for k in np.nonzero((t >= ARRIVE) & (t < ARRIVE + .45))[0]:                         # 番地に収まった瞬間、小さく光る
        e = (t - ARRIVE[k]) / .45; x, y = home(t, [k])[0]; T.add_glow(arr, GL, x, y, PAL[ARM[k]], .35 * (1 - e))
    if t > TALL: e = t - TALL; T.add_glow(arr, GB, CX, CY, (210, 214, 255), .45 * math.exp(-e * 1.4) * T.sstep(0, .15, e))
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)); d3 = ImageDraw.Draw(out, "RGBA")
    T.fit_text(d3, (W / 2, 175), T.tr("ばらばらにしても、もとの模様にもどる？", "Scatter them all. Will the pattern come back?"), 56, 840, (238, 240, 255, 255))
    return np.asarray(out)
GL = T.glow(10); GB = T.glow(60)

def audio(path):
    a = T.Audio(DUR, mat="glass", max_same=5, window=.03, chord_len=ARM_DT)
    for j in range(ARMS):                                                                 # 腕の玉が中心から外へ収まるたび、そのときのカノンの和音を下から上へ
        ks = sorted([k for k in range(N) if ARM[k] == j], key=lambda k: ARRIVE[k])
        for i, k in enumerate(ks):
            if i % 2: continue
            tones = K.canon_tones(min(7, int((ARRIVE[k] - T3) // ARM_DT)), 62, 88)
            m = tones[min(len(tones) - 1, i // 2)]; x = home(ARRIVE[k], [k])[0, 0]
            a.note(ARRIVE[k], m, vel=.26 + .10 * (i == 0), pan=float(np.clip(.5 + (x - CX) / 700, .15, .85)))
    for q, m in enumerate(K.canon_tones(0, 62, 81)): a.note(TALL + .1 + q * .05, m, vel=.38, pan=.2 + .1 * q)   # そろったら、最初の和音（D）
    for m in (38, 50): a.note(TALL + .1, m, vel=.42, pan=.5)
    rng = np.random.default_rng(3); last = -1
    for t, k, x in sorted(HITS):                                                           # びんに落ちる音：小さく、まばらに
        if t - last < .07 or t > T3: continue
        last = t; a.note(t, int(rng.choice([74, 76, 78, 81, 83, 86])), vel=.12, pan=float(np.clip(.5 + (x - W / 2) / 900, .1, .9)), mat="stone")
    N_ = int(SR * DUR); tt = np.arange(N_) / SR
    pad = K.pad([K.CANON[min(7, max(0, int((x - T3) // ARM_DT)))] if x >= T3 else K.CANON[0] for x in np.arange(0, DUR + 4, ARM_DT)], ARM_DT, DUR, .028)[:N_]
    return a.write(path, room=(.32, 3.0), under=pad.astype(np.float32))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_lineup", exist_ok=True)
    print("長さ", round(DUR, 1), "そろう", round(TALL, 1), "落ちる音の候補", len(HITS), "はみ出し x", round(float(POS[:, :, 0].min()), 1), round(float(POS[:, :, 0].max()), 1), "最大 y", round(float(POS[:, :, 1].max()), 1))
    if cmd == "stills": print(T.stills(NF, make_frame, "build_lineup/s", at=(.0, 4 / DUR, 9 / DUR, (T3 + 3) / DUR, (T3 + 9) / DUR, (TALL + .5) / DUR, .999))); sys.exit()
    if cmd == "audio": audio("build_lineup/a.wav"); sys.exit()
    out = f"output/lineup1_{T.LANG}.mp4"; audio("build_lineup/a.wav"); T.encode(NF, make_frame, "build_lineup/a.wav", out); print(out)
