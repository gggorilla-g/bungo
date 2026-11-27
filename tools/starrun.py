# starrun.py — 64個の星を、ジグザグの坂に1つずつ流す。全部、下の丸い器に入る？ 入りきったら早回しで巻きもどり、頭にもどってループする（縦のショート）
#   持ち主 11/28：ジグザグの坂を小さな星が転がり、下の丸い器に入っていく動画（録画）を見せて「これの星バージョンでガラスエコー瞑想」
#   まねたのは仕組み（筒から1つずつ出た玉が、ジグザグの坂を下って器にたまる）だけ。形・色・字・音は自前（夜空の色、光るガラスの星、器は半円）
#   動き：星は重力で坂を転がり（転がった道のりのぶん回る）、星どうし・坂・壁にぶつかる。坂の端から次の坂へ落ちる
#   音：ガラスの響き＋瞑想のエコー＋裏の低い持続音＋隠し味の鼓動。星が坂・器・ほかの星に強く当たった瞬間に1打（高い所ほど高い音）。カノン進行
#   python3 tools/starrun.py stills ／ all（LANG_OUT=en で英語）→ output/starrun1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K
import loopkit as L

W, H, FPS = T.W, T.H, T.FPS
NS, RS, GRAV, SUB = 64, 14.0, 2600.0, 8; DROP = .30                     # 星の数、半径、重力、1コマの計算回数、出す間隔（秒）
TX, TY0, TY1 = 70.0, 330.0, 640.0                                       # 筒（左上）
LEV = [(640, 1), (830, -1), (1020, 1), (1210, -1)]                       # 坂（高さ、向き：1＝右へ下る）。最後の1本は器の上で終わる
XW0, XW1 = 40.0, 1040.0; BX, BY, BR = 640.0, 1625.0, 202.0              # 左右の壁、器（半円）の中心と半径
SEGS = []
for y, s in LEV:
    if s > 0: SEGS.append(((XW0, y), (XW1 - 150, y + 140)))
    else: SEGS.append(((XW1, y), (XW0 + 150, y + 140)))
SEGS.append(((XW0, 1385), (BX - 60, 1530)))                              # 最後の坂：器の上で終わる
SEGS += [((XW0, 300), (XW0, 1420)), ((XW1, 300), (XW1, 1350)), ((TX + 26, 300), (TX + 26, TY1 - 30))]   # 壁と筒の右の板
ARC = [(BX + BR * math.cos(a), BY + BR * math.sin(a)) for a in np.linspace(0, math.pi, 40)]
SEGS += [(ARC[i], ARC[i + 1]) for i in range(len(ARC) - 1)]
SA = np.array([s[0] for s in SEGS], float); SB_ = np.array([s[1] for s in SEGS], float)

def simulate():
    P = np.zeros((NS, 2)); V = np.zeros((NS, 2)); act = np.zeros(NS, bool); rot = np.zeros(NS); dt = 1 / (FPS * SUB)
    for i in range(NS): P[i] = (TX, -100.0)                               # 出る前は画面の外
    gate = 0; frames = []; ev = []; t = 0.0; inbowl = np.zeros(NS, bool); still = 0
    for fi in range(int(60 * FPS)):
        for _ in range(SUB):
            t += dt
            if gate < NS and t >= .4 + gate * DROP:                       # 筒の口をあけて1つ出す（右へ少し押す）
                act[gate] = True; P[gate] = (TX, TY0); V[gate] = (0.0, 200.0); gate += 1   # 筒の上から1つずつ落とす
            idx = np.where(act)[0]
            # 筒の中で待っている星は、口が空くまで止まって見える（下へ詰める）
            V[idx, 1] += GRAV * dt; P[idx] += V[idx] * dt
            for _ in range(2):
                # 板と当たる
                for k in range(len(SEGS)):
                    a, b = SA[k], SB_[k]; ab = b - a; L2 = ab @ ab; q = P[idx] - a; u = np.clip(q @ ab / L2, 0, 1); c = a + u[:, None] * ab; d = P[idx] - c; dist = np.hypot(d[:, 0], d[:, 1]) + 1e-9
                    hit = dist < RS + 2
                    for j in np.where(hit)[0]:
                        i = idx[j]; nrm = d[j] / dist[j]; P[i] += nrm * (RS + 2 - dist[j]); vn = V[i] @ nrm
                        if vn < 0:
                            if -vn > 150: ev.append((t, float(P[i][1]), -vn))
                            tang = V[i] - vn * nrm; V[i] = tang - .25 * vn * nrm
                # 星どうし
                Q = P[idx]; D = Q[:, None] - Q[None]; R2 = (D ** 2).sum(-1); ii, jj = np.where(np.triu(R2 < (2 * RS) ** 2, 1))
                for a_, b_ in zip(ii, jj):
                    i, j = idx[a_], idx[b_]; dv = P[i] - P[j]; dist = math.hypot(*dv) + 1e-9; nrm = dv / dist; ov = 2 * RS - dist; P[i] += nrm * ov / 2; P[j] -= nrm * ov / 2
                    rv = (V[i] - V[j]) @ nrm
                    if rv < 0:
                        if -rv > 220: ev.append((t, float(P[i][1]), -rv * .7))
                        V[i] -= .62 * rv * nrm; V[j] += .62 * rv * nrm
            sp = np.hypot(V[idx, 0], V[idx, 1]); rot[idx] += np.sign(V[idx, 0]) * sp * dt / RS
            inbowl[idx] = np.hypot(P[idx, 0] - BX, P[idx, 1] - BY) < BR + 2
            V[idx] *= .99995
        frames.append((P.copy(), rot.copy(), int(inbowl.sum())))
        if (inbowl.all() and t > .4 + (NS - 1) * DROP + 1.5) or t > .4 + (NS - 1) * DROP + 11.0: break   # 全部入ったら（入らなくても最後の星から9秒で）終わり
    return frames, ev

FR, EV = simulate(); TEND = len(FR) / FPS; HOLD, TREW = 1.2, 1.6; DUR = TEND + HOLD + TREW; NF = int(round(DUR * FPS))
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
def make_bg():
    b = (np.array([8, 10, 30], np.float32) * (1 - yy / H)[..., None] + np.array([3, 4, 14], np.float32) * (yy / H)[..., None]) / 255
    rng = np.random.default_rng(11)
    for _ in range(220):
        x, y = int(rng.uniform(0, W)), int(rng.uniform(0, H)); b[y, x] += rng.uniform(.1, .5) * np.array([.85, .9, 1.0])
    m = np.zeros((H, W), np.uint8)
    for (a, c) in SEGS: cv2.line(m, (int(a[0] * 8), int(a[1] * 8)), (int(c[0] * 8), int(c[1] * 8)), 255, 5, cv2.LINE_AA, 3)
    
    f = m.astype(np.float32) / 255; g = cv2.GaussianBlur(f, (0, 0), 6) * .5
    return np.clip(1 - (1 - b) * (1 - np.clip(f * .92 + g, 0, 1)[..., None] * np.array([.88, .94, 1.0], np.float32)), 0, 1).astype(np.float32)
BG = make_bg(); GS = T.glow(14)
def star_sprite(r, ang, ss=4):
    """5つの角の星（ガラスの星：まん中が明るく、角へ行くほど金色が濃い）"""
    n = int(r * 2 * ss + 8 * ss); im = Image.new("L", (n, n), 0); dr = ImageDraw.Draw(im); c0 = n / 2
    pts = [(c0 + r * ss * (1.0 if k % 2 == 0 else .48) * math.cos(ang - math.pi / 2 + k * math.pi / 5), c0 + r * ss * (1.0 if k % 2 == 0 else .48) * math.sin(ang - math.pi / 2 + k * math.pi / 5)) for k in range(10)]
    dr.polygon(pts, fill=255); a = np.asarray(im, np.float32) / 255; c = (np.arange(n) + .5 - n / 2) / (r * ss); X, Y = np.meshgrid(c, c); d = np.hypot(X, Y)
    shade = np.clip(1.25 - .6 * d + .2 * (-X - Y), .55, 1.3); col = np.array([1.0, .84, .44]); rgb = col * shade[..., None] * a[..., None]
    o = np.dstack([rgb, a]).astype(np.float32); k_ = n // ss; return o[:k_ * ss, :k_ * ss].reshape(k_, ss, k_, ss, 4).mean((1, 3))
SPR = [star_sprite(RS * 1.35, 2 * math.pi * k / 30) for k in range(30)]   # 回る向き（5つの角で 72° ごとに同じ形）
INK = (244, 246, 255, 255); GOLD = (255, 222, 150, 255)

def frame_at(ts, rew=0.0):
    fi = int(min(len(FR) - 1, max(0, round(ts * FPS)))); P, rot, nb = FR[fi]; buf = BG.copy()
    for i in range(NS):
        x, y = P[i]
        if y < 0: continue
        T.add_glow(buf, GS, x, y, (255, 214, 130), .32); k = int(round((rot[i] % (2 * math.pi / 5)) / (2 * math.pi / 5) * 30)) % 30
        sp = SPR[k]; h, w = sp.shape[:2]; x0, y0 = int(round(x - w / 2)), int(round(y - h / 2)); reg = buf[y0:y0 + h, x0:x0 + w]
        if reg.shape[:2] == (h, w): reg[:] = reg * (1 - sp[..., 3:4]) + sp[..., :3]
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); done = ts >= TEND - 1e-6
    T.fit_text(d, (W / 2, 132), T.tr(f"{NS}個の星は、全部 器に入る？", f"Will all {NS} stars land in the bowl?"), 60, 1000, INK)
    T.fit_text(d, (W / 2, 206), T.tr("ジグザグの坂を、1つずつ転がす", "One by one, down the zigzag slopes"), 42, 1000, GOLD)
    d.text((W - 60, 280), T.tr(f"器の中 {nb} / {NS}", f"In the bowl: {nb} / {NS}"), font=T.fnt(44), fill=INK, anchor="rm")
    cap = (T.tr("◀◀ 巻きもどし", "◀◀ Rewind"), INK) if rew > 0 else ((T.tr("全部入った", "All of them made it") if nb == NS else T.tr(f"{nb}個入った。{NS - nb}個はこぼれた", f"{nb} made it. {NS - nb} spilled out"), (255, 232, 170, 255)) if done else None)
    if cap: T.fit_text(d, (W / 2, 1850), cap[0], 46, 1000, cap[1])
    return np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB"))
def make_frame(fi):
    ts, rew = L.sim_time(fi / FPS, TEND, HOLD, TREW); return frame_at(ts, rew)

def audio(path):
    fwd = TEND + HOLD; a = T.Audio(fwd, lo=64, hi=93, mat="glass", max_same=3, window=.05, chord_len=2.4); last = -1
    for t, y, v in EV:
        if t - last < 1 / 9: continue
        last = t; a.hit(t, float(np.clip((1700 - y) / 1400, 0, .999)), vel=float(np.clip(.25 + v / 900, .25, .75)))
    ns = int(T.SR * fwd); under = K.pad([(r, r + 12, f5 + 12) for (r, t3, f5) in K.CANON], 2.4, fwd + 1, .03)[:ns]
    under += L.heartbeat([(c * 2.4 + h * 1.2, K.CANON[c % 8][0]) for c in range(int(fwd / 2.4) + 1) for h in (0, 1)], ns, T.SR, .085)
    tmp = path + ".fwd.wav"; a.write(tmp, room=(.32, 3.2), under=under); L.add_rewind(tmp, path, TEND, HOLD, TREW, gain=.55); os.remove(tmp)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_starrun", exist_ok=True)
    print("長さ", round(DUR, 1), "当たり", len(EV), "器の中", FR[-1][2])
    if cmd == "stills": print(T.stills(NF, make_frame, "build_starrun/s", at=(.05, .2, .4, .6, (TEND - .2) / DUR))); sys.exit()
    out = f"output/starrun1_{T.LANG}.mp4"; audio("build_starrun/a.wav"); T.encode(NF, make_frame, "build_starrun/a.wav", out); print(out)
