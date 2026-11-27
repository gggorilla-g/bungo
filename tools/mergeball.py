# mergeball.py — 円の中の玉は、ぶつかると合体する（面積はそのまま足す）。最後の1個は何色？（縦のショート 1080×1920・60コマ）
#   持ち主 11/27：画面収録（白い背景・太い黒の円・影のないベタ塗りの玉・大きな黒い数字）を送って「色とか雰囲気とか…こっち」、11/28「音はうちが使ってる音でいい」
#   まねたのは雰囲気（明るい背景・ベタ塗り・太い円・大きな数字）。決まりは自前に1つ足した：合体すると、大きい方の色が残る → 最後の1個は何色か、という問い
#   物理：玉は止まらずに飛び続ける（まさつ・重力なし。円の壁ではね返る）。2つが触れたら1つになる：面積の和・重さの比で位置と向き（運動量の向き）。
#         数がへるほど速く動く（v = v0 ×(240/数)^0.5）。画面の下に書く決まり。はじめはゆっくり、終わりに向かって速くなる
#   見本への指摘（11/28）「球がぶつかるときにはぷよぷよっぽいくっつきエフェクトをわかりやすく」→ 触れた2つは、0.16秒かけて、くびれでつながりながら（メタボール）1つに寄り、
#     そのあと、くっついた向きにのびちぢみしてゆれて落ちつく（面積は変えない）。合体の瞬間に、うすい輪が1つ広がる
#   音（大きい玉＝半径30px より大きい玉が円の壁に当たった瞬間にも、小さく1打）：trendkit の Audio（硬い玉が板に当たる音。材質は1本ごとに回す＝この動画は空洞のある木）。合体した瞬間に1打。大きい玉ほど低い。合体の型なのでエコーと裏の低音あり（持ち主 11/27）
#   python3 tools/mergeball.py search [数] ／ stills ／ all（LANG_OUT=en で英語、SEED=<数>、MAT=…）→ output/mergeball1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T

W, H, FPS = T.W, T.H, T.FPS
SEED = int(os.environ.get("SEED", "20")); MAT = os.environ.get("MAT", "glass")    # 持ち主 11/28「ガラスっぽい音でいいかも。音階カノンで瞑想エコー」
CX, CY, RC = 540, 900, 470; N0, R0 = 240, 7.0; VEXP = float(os.environ.get('VEXP', '.6')); SUB = 4; DT = 1 / (FPS * SUB); OUTRO = 3.0
COLS = [("桃", "Pink", (240, 98, 146)), ("緑", "Green", (52, 196, 108)), ("水色", "Cyan", (56, 196, 230)), ("黄", "Yellow", (244, 204, 52)),
        ("紫", "Purple", (146, 96, 222)), ("青", "Blue", (70, 102, 230)), ("橙", "Orange", (246, 146, 52))]
NC = len(COLS)
def cn(i): return COLS[i][1] if T.EN else COLS[i][0]

def simulate(seed, v0=None, record=False):
    rng = np.random.default_rng(seed); v0 = v0 or 34.0 + 4 * (seed % 4)   # はじめの速さ。数がへるほど速くなる：v = v0 × (240/数)^VEXP
    p = []
    while len(p) < N0:                                                  # 重ならないように置く
        a, rr = rng.uniform(0, 2 * math.pi), (RC - R0 - 4) * math.sqrt(rng.uniform(0, 1)); q = np.array([CX + rr * math.cos(a), CY + rr * math.sin(a)])
        if all(np.hypot(*(q - o)) > 2 * R0 + 3 for o in p): p.append(q)
    P = np.array(p); ang = rng.uniform(0, 2 * math.pi, N0); V = v0 * np.stack([np.cos(ang), np.sin(ang)], 1); R = np.full(N0, R0); C = rng.integers(0, NC, N0)
    alive = np.ones(N0, bool); ev = []; wall = []; mg = []; frames = []; t = 0.0; step = 0; t_end = None; born = np.zeros(N0); rfrom = np.full(N0, R0)
    while True:
        P += V * DT; idx = np.flatnonzero(alive)
        d = P[idx] - [CX, CY]; dist = np.hypot(d[:, 0], d[:, 1]); out = dist + R[idx] > RC   # 円の壁
        for k in np.flatnonzero(out):
            i = idx[k]; nrm = d[k] / dist[k]; vn = V[i] @ nrm
            if vn > 0:
                V[i] -= 2 * vn * nrm
                if R[i] > 30: wall.append((t, float(R[i]), float(P[i][0])))     # 大きい玉が壁に当たった瞬間（音）
            P[i] = [CX, CY] + nrm * (RC - R[i])
        merged = True
        while merged:                                                    # 触れた2つを合体（続けて触れれば、続けて合体）
            merged = False; idx = np.flatnonzero(alive)
            if len(idx) < 2: break
            Q = P[idx]; dd = np.hypot(Q[:, None, 0] - Q[None, :, 0], Q[:, None, 1] - Q[None, :, 1]); rs = R[idx][:, None] + R[idx][None, :]
            np.fill_diagonal(dd, 1e9); hit = np.argwhere(np.triu(dd < rs, 1))
            used = set()
            for a, b in hit:
                if a in used or b in used: continue
                i, j = idx[a], idx[b]; used.update((a, b))
                mi, mj = R[i] ** 2, R[j] ** 2; big, small = (i, j) if (mi > mj or (mi == mj and rng.random() < .5)) else (j, i)
                mg.append((t, int(big), int(small), P[big].copy(), P[small].copy(), float(R[big]), float(R[small])))
                rfrom[big] = R[big]; P[big] = (P[i] * mi + P[j] * mj) / (mi + mj); vv = (V[i] * mi + V[j] * mj) / (mi + mj); sp = np.hypot(*vv)
                V[big] = vv / sp * v0 * (N0 / max(1, alive.sum() - 1)) ** VEXP if sp > 1e-6 else V[big]; R[big] = math.sqrt(mi + mj); born[big] = t; alive[small] = False
                dd2 = np.hypot(*(P[big] - [CX, CY]))
                if dd2 + R[big] > RC: P[big] = [CX, CY] + (P[big] - [CX, CY]) / dd2 * (RC - R[big])
                ev.append((t, float(R[big]), float(P[big][0]), int(C[big]), int(alive.sum()))); merged = True
        n = int(alive.sum())
        if merged is False and ev and ev[-1][0] == t:                      # 数がへったら、ぜんぶの玉の速さを v(数) にそろえる
            sp = np.hypot(V[:, 0], V[:, 1]) + 1e-9; V *= (v0 * (N0 / max(1, n)) ** VEXP / sp)[:, None]
        if n == 1 and t_end is None: t_end = t
        if record and step % SUB == 0:
            frames.append(dict(t=t, P=P.copy(), R=R.copy(), C=C.copy(), alive=alive.copy(), born=born.copy(), rfrom=rfrom.copy(), n=n))
        t += DT; step += 1
        if t_end is not None and t > t_end + OUTRO: break
        if t > 70: break
    win = int(C[np.flatnonzero(alive)[0]]) if t_end is not None else -1
    return dict(t_end=t_end, ev=ev, wall=wall, mg=mg, frames=frames, winner=win, dur=(t_end or 70) + OUTRO, v0=v0)

def score(r):
    te = r["t_end"]
    if te is None: return -99
    ns = [e[4] for e in r["ev"]]; t2 = next(e[0] for e in r["ev"] if e[4] == 2); duel = te - t2
    s = -abs(te - 27) - 2 * max(0, 1.5 - duel) - max(0, duel - 6)
    gaps = np.diff([0] + [e[0] for e in r["ev"]]); s -= 2 * max(0, gaps.max() - 4.5)
    return s

# ---------- 絵 ----------
BG = None; SS = 2
def bgimg():
    global BG
    if BG is None:
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]; b = np.array([226, 243, 251], np.float32) * (1 - yy) + np.array([246, 251, 254], np.float32) * yy
        im = Image.fromarray(np.broadcast_to(b, (H, W, 3)).astype(np.uint8)); big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(big)
        d.ellipse([(CX - RC) * SS, (CY - RC) * SS, (CX + RC) * SS, (CY + RC) * SS], fill=(255, 255, 255, 255))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).ellipse([CX - RC, CY - RC + 10, CX + RC, CY + RC + 10], fill=(40, 70, 100, 40))
        from PIL import ImageFilter
        im = Image.alpha_composite(im.convert("RGBA"), sh.filter(ImageFilter.GaussianBlur(18))); im = Image.alpha_composite(im, big.resize((W, H), Image.LANCZOS)); BG = im
    return BG
RING = None
def ring():
    global RING
    if RING is None:
        big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); ImageDraw.Draw(big).ellipse([(CX - RC - 6) * SS, (CY - RC - 6) * SS, (CX + RC + 6) * SS, (CY + RC + 6) * SS], outline=(24, 28, 38, 255), width=12 * SS)
        RING = big.resize((W, H), Image.LANCZOS)
    return RING

JOIN, WOB = .16, .55                                                   # くっつく時間／ゆれる時間
def _patch(buf, x0, y0, al, col):
    h, w = al.shape; xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb <= xa or yb <= ya: return
    a = al[ya - y0:yb - y0, xa - x0:xb - x0, None]; reg = buf[ya:yb, xa:xb]; reg[:] = reg * (1 - a) + np.asarray(col, np.float32) / 255 * a
def disc(buf, x, y, r, col, A=0.0, ax=(1.0, 0.0)):
    """円（A≠0 なら、ax の向きに 1+A 倍のび、直角に 1/(1+A) 倍ちぢむ。面積はそのまま）"""
    e = r * (1 + abs(A)) + 2; x0, y0 = int(x - e), int(y - e); n = int(2 * e) + 2
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32); dx, dy = xx + x0 + .5 - x, yy + y0 + .5 - y
    if abs(A) > 1e-3:
        u = dx * ax[0] + dy * ax[1]; v = -dx * ax[1] + dy * ax[0]; q = np.sqrt((u / (1 + A)) ** 2 + (v * (1 + A)) ** 2)
        al = np.clip((r - q) * min(1 + A, 1 / (1 + A)) + .5, 0, 1)
    else: al = np.clip(r - np.sqrt(dx * dx + dy * dy) + .5, 0, 1)
    _patch(buf, x0, y0, al, col)
def blob(buf, p1, r1, p2, r2, col):
    """2つの円が、くびれでつながった形（メタボール：r1²/d1² + r2²/d2² ≥ 1）"""
    e = max(r1, r2) * 1.3 + 3; x0 = int(min(p1[0], p2[0]) - e); y0 = int(min(p1[1], p2[1]) - e); x1 = int(max(p1[0], p2[0]) + e); y1 = int(max(p1[1], p2[1]) + e)
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32) + .5
    g = r1 * r1 / ((xx - p1[0]) ** 2 + (yy - p1[1]) ** 2 + 1e-3) + r2 * r2 / ((xx - p2[0]) ** 2 + (yy - p2[1]) ** 2 + 1e-3)
    al = np.clip((np.sqrt(g) - 1) * max(r1, r2) + .5, 0, 1); _patch(buf, x0, y0, al, col)
def make_frame(r, i):
    fr = r["frames"]; f = fr[min(i, len(fr) - 1)]; t = f["t"]; te = r["t_end"]
    buf = np.asarray(bgimg().convert("RGB"), np.float32) / 255; buf = buf.copy()
    last = {}                                                            # 玉ごとの、いちばん新しい合体
    for m in r["mg"]:
        if m[0] > t: break
        if t - m[0] < WOB + JOIN: last[m[1]] = m
    rings = []
    for k in np.flatnonzero(f["alive"]):
        x, y = f["P"][k]; col = COLS[f["C"][k]][2]; m = last.get(k)
        if m is None: disc(buf, x, y, f["R"][k], col); continue
        tm, big, small, pb, ps, rb, rs = m; e = t - tm; pm = (pb * rb * rb + ps * rs * rs) / (rb * rb + rs * rs)
        dvec = ps - pb; dn = np.hypot(*dvec) + 1e-6; ax = (dvec[0] / dn, dvec[1] / dn)
        if e < JOIN:                                                     # くっつく：2つが、くびれでつながりながら寄る
            sft = T.sstep(0, JOIN, e) ** .8; cur = np.array([x, y])
            p1 = cur + (pb - pm) * (1 - sft); p2 = cur + (ps - pm) * (1 - sft); blob(buf, p1, rb, p2, rs, col)
        else:                                                            # ゆれる：くっついた向きにのびちぢみして落ちつく
            w_ = e - JOIN; A = .26 * math.cos(2 * math.pi * w_ / .2) * math.exp(-w_ / .13) * min(1.0, rs / rb * 2.5)
            disc(buf, x, y, f["R"][k], col, A, ax)
        if e < .45 and f["R"][k] > 9: rings.append((x, y, f["R"][k], col, e))
    im = Image.fromarray((np.clip(buf, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    if rings:                                                            # 合体の瞬間の、うすい輪
        rb_ = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(rb_)
        for (x, y, rr, col, e) in rings:
            p = e / .45; R_ = rr * (1.08 + .7 * p); a = int(120 * (1 - p) ** 1.5); d.ellipse([(x - R_) * SS, (y - R_) * SS, (x + R_) * SS, (y + R_) * SS], outline=col + (a,), width=int(3 * SS))
        im = Image.alpha_composite(im, rb_.resize((W, H), Image.LANCZOS))
    im = Image.alpha_composite(im, ring())
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(ov); INK = (24, 28, 38, 255)
    T.fit_text(dd, (W / 2, 170), T.tr("ぶつかると、合体する", "Balls merge when they touch"), 60, 980, INK)
    T.fit_text(dd, (W / 2, 254), T.tr("最後に残るのは、何色？", "Which color is left at the end?"), 54, 980, (226, 70, 120, 255))
    n = f["n"]; ncol = (24, 28, 38, 255) if n > 1 else COLS[r["winner"]][2] + (255,)
    dd.text((W / 2, 1530), str(n), font=T.fnt(190), fill=ncol, anchor="mm")
    cnt = np.bincount(f["C"][f["alive"]], minlength=NC)
    for c in range(NC):
        x = W / 2 + (c - (NC - 1) / 2) * 128; y = 1712; col = COLS[c][2]
        if cnt[c]: dd.ellipse([x - 20, y - 20, x + 20, y + 20], fill=col + (255,)); dd.text((x, y + 48), str(int(cnt[c])), font=T.fnt(30), fill=(60, 66, 80, 255), anchor="mm")
        else: dd.ellipse([x - 20, y - 20, x + 20, y + 20], outline=col + (140,), width=3)
    if te is not None and t >= te + .3:
        a = int(255 * T.sstep(te + .3, te + .8, t)); w = r["winner"]
        T.fit_text(dd, (W / 2, 1830), T.tr(f"最後に残ったのは {cn(w)}", f"{cn(w)} is the last one left"), 52, 980, COLS[w][2] + (a,))
    im = Image.alpha_composite(im, ov).convert("RGB"); out = np.asarray(im)
    g = min(T.sstep(0, .3, t), 1 - T.sstep(r["dur"] - .4, r["dur"], t))
    return out if g >= .999 else (out.astype(np.float32) * g + 255 * (1 - g)).astype(np.uint8)

def audio(r, path):
    a = T.Audio(r["dur"], lo=60, hi=86, mat=MAT, max_same=3, chord_len=2.4); rmax = R0 * math.sqrt(N0); K = T.K
    for (t, rr, x, c, n) in r["ev"]:
        u = 1 - math.log(rr / R0) / math.log(rmax / R0)                   # 大きい玉ほど低い
        a.hit(t, .05 + .9 * u, vel=.45 + .5 * (1 - u))
    for (t, rr, x) in r["wall"]:                                         # 大きい玉が壁に当たった瞬間：小さく1打（同じ音程の帯の、少し下）
        if r["t_end"] is None or t < r["t_end"] + .2:
            u = 1 - math.log(rr / R0) / math.log(rmax / R0); a.hit(t, max(0, .9 * u - .05), vel=.30)
    N = int(T.SR * r["dur"]); under = K.pad([(r_, r_ + 12, f5 + 12) for (r_, t3, f5) in K.CANON], 2.4, r["dur"] + .5, .05)[:N]
    under = under * np.minimum(1, (r["dur"] - np.arange(len(under)) / T.SR) / 1.2).clip(0, 1)
    return a.write(path, room=(.32, 3.2), under=under)                  # 瞑想のような長いエコー（持ち主 11/28）

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_mergeball", exist_ok=True)
    if cmd == "search":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 30; T.pick_seed(simulate, score, range(n)); sys.exit()
    r = simulate(SEED, record=True); nf = int(r["dur"] * FPS)
    t2 = next(e[0] for e in r["ev"] if e[4] == 2)
    print("長さ", round(r["dur"], 1), "秒 1個になる", round(r["t_end"], 1), "一騎打ち", round(t2, 1), "勝ち", cn(r["winner"]), "合体", len(r["ev"]))
    if cmd == "stills": print(T.stills(nf, lambda i: make_frame(r, i), "build_mergeball/s", at=(.03, .2, .5, .8, .99))); sys.exit()
    out = f"output/mergeball1_{T.LANG}.mp4"; wav = "build_mergeball/a.wav"; audio(r, wav); T.encode(nf, lambda i: make_frame(r, i), wav, out); print(out)
