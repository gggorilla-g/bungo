# bheat.py — 青い玉は、壁に当たるたびにふえる。ブラックホールは、触れた玉を飲みこんで大きくなる。最後に勝つのはどっち？ 終わったら早回しで巻きもどり、頭にもどってループする（縦のショート）
#   持ち主 11/28：円の中で青い玉と小さな黒い穴がせめぎ合う動画（録画）を見せて
#     「これも同じループ構造。黒い点も吸収するほどじわじわ大きくなり青と黒のせめぎ合いが面白いしずっと見てられる。一時期青がかなり増殖したが最後は黒が制圧した。その後まきもどしがありループする 音は234」
#   まねたのは仕組み（円の中で、ふえる玉と、飲みこんで育つ穴がせめぎ合う）と流れ（青がふえる → 黒が追いつく → 黒が全部飲む → 巻きもどし → 頭）。絵・色・字・音は自前
#   決まり（この動画の中だけの決まり）
#     ・青い玉は同じ速さで動き、壁と玉どうしで はね返る。壁に当たると、その場所から新しい玉が1つ生まれる（まわりに空きがある時だけ）
#     ・黒い穴は、触れた玉を飲みこむ。飲みこんだ玉の面積のぶんだけ、穴の面積がふえる。重くなるほど ゆっくり動く
#   音：2・3・4（木・竹・空洞のある木。動画ごとに回す）。青い玉が壁に当たった瞬間に1打（高い所ほど高い音）。飲みこまれた瞬間に低い1打。隠し味の鼓動（和音の根音）。カノン進行
#   python3 tools/bheat.py search（種えらび）／ stills ／ all（LANG_OUT=en で英語、MAT=…）→ output/bheat1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K
import loopkit as L

W, H, FPS = T.W, T.H, T.FPS
MAT = os.environ.get("MAT", "wood"); SEED = int(os.environ.get("SEED", "14"))
CX, CY, RC = 540.0, 980.0, 480.0; RB = 30.0; GV = float(os.environ.get("GV", "300")); SUB = 4; KEAT = float(os.environ.get("KEAT", ".10"))   # 円、青い玉の半径、重力、1コマの計算回数、飲みこんだ面積のうち穴がふえる割合
GOAL = int(os.environ.get("GOAL", "60")); CR = float(os.environ.get("CR", "1.0")); VH = float(os.environ.get("VH", "50")); PULL = 260.0; TMAX = 58.0; NMAX = 160            # 青が GOAL 個になったら青の勝ち。穴の速さ（一定・まっすぐ）、穴のそばで玉が引かれる強さ
#   持ち主 11/28 の直し：「黒玉の成長が急すぎる…青玉が小さくて早すぎる。青玉の増殖点は中央で、もっとバウンド的な動き。黒玉はもっと直線的でゆっくりだが青玉の抵抗はさほど受けない。
#     どっちが勝つのかハラハラ感がほしい。あと多少吸い込まれてる感はほんの少し欲しい」
#   → 青い玉は大きく（半径30）、重力で落ちて円の壁で はね返る（エネルギーは減らない）。壁に当たるたびに、まん中から新しい玉が1つ生まれる（まん中が空いている時だけ）
#     黒い穴は一定の速さでまっすぐ進み、壁でだけ向きが変わる（玉を飲んでも曲がらない）。飲んだ面積の2割だけ大きくなる。穴のそばの玉は、少しだけ引き寄せられる
#     青が100個になれば青の勝ち、0個になれば黒の勝ち

def simulate(seed, tmax=TMAX, record=True):
    rng = np.random.default_rng(seed); dt = 1 / (FPS * SUB)
    P = np.zeros((NMAX, 2)); Vv = np.zeros((NMAX, 2)); alive = np.zeros(NMAX, bool); born = np.zeros(NMAX)
    P[0] = (CX, CY); Vv[0] = (rng.uniform(-120, 120), 0); alive[0] = True
    a1 = rng.uniform(0, 2 * np.pi); bp = np.array([CX, CY]) + 300 * np.array([math.cos(a1), math.sin(a1)]); a2 = rng.uniform(0, 2 * np.pi); bv = VH * np.array([math.cos(a2), math.sin(a2)]); br = 16.0
    frames = []; ev = []; eaten = []; t = 0.0; nf = int(tmax * FPS); counts = []; done_at = None; winner = None
    for fi in range(nf):
        for _ in range(SUB):
            t += dt; idx = np.where(alive)[0]
            Vv[idx, 1] += GV * dt
            if len(idx):                                                  # 穴のそばの玉は少し引かれる（吸いこまれる感じ）
                rel = bp - P[idx]; dd = np.hypot(rel[:, 0], rel[:, 1]) + 1e-6; near = dd < br * 2.6 + RB
                Vv[idx[near]] += (rel[near] / dd[near, None]) * PULL * dt * (1 - (dd[near] - br) / (br * 1.6 + RB)).clip(0, 1)[:, None]
            P[idx] += Vv[idx] * dt; bp += bv * dt
            d = math.hypot(*(bp - (CX, CY)))
            if d > RC - br:
                nrm = (bp - (CX, CY)) / d; bp -= nrm * (d - (RC - br)); vn = bv @ nrm
                if vn > 0: bv -= 2 * vn * nrm
            if len(idx):
                rel = P[idx] - (CX, CY); dd = np.hypot(rel[:, 0], rel[:, 1]); hit = dd > RC - RB
                for j in np.where(hit)[0]:
                    i = idx[j]; nrm = rel[j] / dd[j]; P[i] -= nrm * (dd[j] - (RC - RB)); vn = Vv[i] @ nrm
                    if vn <= 0: continue
                    Vv[i] -= 2 * vn * nrm; ev.append((t, "wall", float(P[i][1]), i))
                    q = np.array([CX, CY]); free = np.where(~alive)[0]
                    if len(free) and math.hypot(*(q - bp)) > br + RB + 6 and np.all(np.hypot(*(P[alive] - q).T) > CR * RB):   # 壁に当たるたびにふえる（まん中がふさがっている時だけ、ふえない）
                        k = free[0]; P[k] = q; Vv[k] = (rng.uniform(-150, 150), rng.uniform(-260, -60)); alive[k] = True; born[k] = t; ev.append((t, "born", CY, k))
            idx = np.where(alive)[0]
            if len(idx) > 1:
                Q = P[idx]; D = Q[:, None] - Q[None]; R2 = (D ** 2).sum(-1); ii, jj = np.where(np.triu(R2 < (2 * RB) ** 2, 1))
                for a_, b_ in zip(ii, jj):
                    i, j = idx[a_], idx[b_]; dv = P[i] - P[j]; dist = math.hypot(*dv) + 1e-9; nrm = dv / dist; ov = 2 * RB - dist
                    P[i] += nrm * ov / 2; P[j] -= nrm * ov / 2; rv = (Vv[i] - Vv[j]) @ nrm
                    if rv < 0: Vv[i] -= rv * nrm; Vv[j] += rv * nrm
            if len(idx):
                dd = np.hypot(*(P[idx] - bp).T); eat = idx[dd < br + RB * .2]
                for i in eat:
                    alive[i] = False; br = math.sqrt(br * br + KEAT * RB * RB); ev.append((t, "eat", br, i)); eaten.append((t, P[i].copy(), i))
        n = int(alive.sum()); counts.append(n)
        if record: frames.append((P[alive].copy(), born[alive].copy(), bp.copy(), br))
        if winner is None and n >= GOAL: winner, done_at = "blue", t
        if winner is None and n == 0 and fi > FPS * 3: winner, done_at = "black", t
        if done_at is not None and t > done_at + .05: break
    return dict(frames=frames, ev=ev, eaten=eaten, counts=np.array(counts), done=done_at, winner=winner)

def score(r):
    c = r["counts"]
    if r["done"] is None: return -1e9, "終わらない"
    tpk = int(np.argmax(c)) / FPS; close = float((c >= GOAL - 10).mean())                # GOAL のすぐ手前にいる時間が長いほどハラハラ
    return -abs(r["done"] - 48) * 1.0 - (40 if r["winner"] != "black" else 0) - 3 * max(0, GOAL - 3 - c.max()) + 40 * close, f"{r['winner']} の勝ち {r['done']:.1f}s 山 {c.max()} 個 @ {tpk:.1f}s"

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "search":
    res = []
    for s in range(int(sys.argv[2]) if len(sys.argv) > 2 else 0, int(sys.argv[3]) if len(sys.argv) > 3 else 12):
        r = simulate(s, record=False); sc, info = score(r); res.append((sc, s, info)); print(s, info, flush=True)
    print(sorted(res)[-5:]); sys.exit()

R = simulate(SEED); FR = R["frames"]; EAT = R["eaten"]; ET = np.array([e[0] for e in EAT] + [1e9]); TEND = len(FR) / FPS; HOLD, TREW = 1.0, 1.6; DUR = TEND + HOLD + TREW; NF = int(round(DUR * FPS)); CNT = R["counts"]

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); DR = np.hypot(xx - CX, yy - CY)
def make_bg():
    b = np.array([6, 9, 22], np.float32) * np.ones((H, W, 1), np.float32) / 255 + (np.exp(-(DR / 560) ** 2) * 14 / 255)[..., None] * np.array([.6, .8, 1.5], np.float32)
    rng = np.random.default_rng(5)
    for _ in range(140):                                                    # うしろの星
        x, y = int(rng.uniform(0, W)), int(rng.uniform(0, H)); b[y, x] += rng.uniform(.15, .55)
    rim = np.exp(-((DR - RC) / 2.0) ** 2) * .9 + np.exp(-((DR - RC) / 14) ** 2) * .16
    return np.clip(1 - (1 - b) * (1 - rim[..., None] * np.array([.86, .93, 1.0], np.float32)), 0, 1).astype(np.float32)
BG = make_bg(); SPB = T.sprite((84, 156, 255), RB); GS = T.glow(22); GH = T.glow(48)
INK = (244, 246, 255, 255); GOLD = (255, 222, 150, 255); BLUE = (120, 180, 255, 255)
_hole = {}
def hole(br):
    """ブラックホール：まっ黒な影、そのふちの細い光の輪、外へやわらかく広がる光"""
    k = int(round(br * 2))
    if k not in _hole:
        if len(_hole) > 6: _hole.clear()                                    # 大きい絵をためこまない（メモリ）
        r = k / 2; hl = min(60.0, max(4, r * .45)); n = int(2 * r + 10 * hl + 40); c = np.arange(n, dtype=np.float32) - n / 2 + .5; X, Y = np.meshgrid(c, c); d = np.hypot(X, Y)
        ring = np.exp(-((d - r * 1.06) / max(1.2, r * .035)) ** 2); halo = np.exp(-np.clip(d - r, 0, None) / hl) * (d > r) * .55
        rgb = (ring[..., None] * np.array([1.0, .86, .62]) + halo[..., None] * np.array([1.0, .55, .25]) * .55).astype(np.float32)
        shadow = np.clip(r + .5 - d, 0, 1); _hole[k] = (rgb, shadow.astype(np.float32))
    return _hole[k]

def frame_at(ts, rew=0.0):
    fi = int(min(len(FR) - 1, max(0, round(ts * FPS)))); P, born, bp, br = FR[fi]; buf = BG.copy()
    for (x, y), b in zip(P, born):
        g = min(1.0, (ts - b) / .18) if ts >= b else 1.0
        sp = SPB if g >= .999 else cv2.resize(SPB, (max(2, int(SPB.shape[1] * g)), max(2, int(SPB.shape[0] * g))))
        T.blit(buf, sp, x, y)
    for te, pe, i in EAT[max(0, int(np.searchsorted(ET, ts - .4))):int(np.searchsorted(ET, ts, "right"))]:   # 飲まれた玉：0.4秒かけて、縮みながら穴の中心へ吸いこまれる
        u = (ts - te) / .4; c = pe + (bp - pe) * u ** 1.6; g = (1 - u) ** 1.3
        if g > .05: T.blit(buf, cv2.resize(SPB, (max(2, int(SPB.shape[1] * g)), max(2, int(SPB.shape[0] * g)))), c[0], c[1])
    rgb, sh = hole(br); h, w = sh.shape; x0, y0 = int(round(bp[0] - w / 2)), int(round(bp[1] - h / 2)); xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    reg = buf[ya:yb, xa:xb]; s_ = sh[ya - y0:yb - y0, xa - x0:xb - x0, None]; reg[:] = reg * (1 - s_); inside = np.clip(RC + 3 - DR[ya:yb, xa:xb], 0, 1)[..., None]   # 光は円の内側だけ
    reg[:] = 1 - (1 - reg) * (1 - np.clip(rgb[ya - y0:yb - y0, xa - x0:xb - x0], 0, 1) * inside)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); n = len(P); done = ts >= TEND - 1e-6
    T.fit_text(d, (W / 2, 132), T.tr(f"青が{GOAL}個になる前に、ブラックホールは食べきれる？", f"Can the black hole eat them all before blue reaches {GOAL}?"), 52, 1010, INK)
    T.fit_text(d, (W / 2, 204), T.tr("青い玉は、壁に当たるたびに まん中からふえる", "Every wall bounce adds a new blue ball at the centre"), 40, 1010, GOLD)
    d.text((W / 2, 290), T.tr(f"青い玉 {n} / {GOAL}", f"Blue balls: {n} / {GOAL}"), font=T.fnt(54), fill=BLUE, anchor="mm")
    bx0, bx1 = 240, 840; d.rounded_rectangle([bx0, 330, bx1, 346], radius=8, fill=(40, 52, 84, 255)); d.rounded_rectangle([bx0, 330, bx0 + (bx1 - bx0) * min(1, n / GOAL), 346], radius=8, fill=BLUE)   # 青の勝ちまでの残り
    gx0, gx1, gy0, gy1 = 120, 960, 1530, 1690; d.rectangle([gx0, gy0, gx1, gy1], outline=(90, 104, 140, 160), width=2)   # 青い玉の数のグラフ（ここまでの分）
    top = GOAL; d.line([(gx0, gy0), (gx1, gy0)], fill=(120, 180, 255, 120), width=1); k = fi + 1; xs = np.linspace(gx0, gx1, len(CNT))[:k]; ys = gy1 - (gy1 - gy0) * CNT[:k] / top
    if k > 1: d.line(list(zip(xs[::2].tolist(), ys[::2].tolist())) + [(float(xs[-1]), float(ys[-1]))], fill=BLUE, width=3)
    d.text((gx0, gy0 - 12), T.tr("青い玉の数", "Blue balls over time"), font=T.fnt(28, False), fill=(176, 186, 214, 255), anchor="lb")
    cap = None
    if rew > 0: cap = (T.tr("◀◀ 巻きもどし", "◀◀ Rewind"), INK)
    elif done: cap = ((T.tr(f"黒の勝ち。青はいちばん多い時で {CNT.max()}個", f"Black wins. Blue peaked at {CNT.max()}") if R["winner"] == "black" else T.tr(f"青の勝ち。{GOAL}個になった", f"Blue wins: it reached {GOAL}")), (255, 232, 170, 255))
    if cap: T.fit_text(d, (W / 2, 1780), cap[0], 46, 1000, cap[1])
    return np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB"))
def make_frame(fi):
    ts, rew = L.sim_time(fi / FPS, TEND, HOLD, TREW); return frame_at(ts, rew)

def audio(path):
    fwd = TEND + HOLD; a = T.Audio(fwd, lo=62, hi=88, mat=MAT, max_same=3, window=.03, chord_len=2.4); last = -1
    walls = [e for e in R["ev"] if e[1] == "wall"]; eats = [e for e in R["ev"] if e[1] == "eat"]
    for t, kind, y, i in walls:
        if t - last < 1 / 22: continue                                    # 多すぎる時は間引く（1秒に22打まで）
        last = t; a.hit(t, float(np.clip((CY + RC - y) / (2 * RC), 0, .999)), vel=.55)
    le = -1
    for t, kind, br, i in eats:
        if t - le < .09: continue
        le = t; a.note(t, K.canon_tones(a.chord_index(t), 45, 64)[0], vel=.62, pan=.5)
    ns = int(T.SR * fwd); under = K.pad([(r, r + 12, f5 + 12) for (r, t3, f5) in K.CANON], 2.4, fwd + 1, .022)[:ns]
    # 鼓動は入れない（持ち主 11/28「鼓動はいらないかも」）
    if False: under += L.heartbeat([(c * 2.4 + h * 1.2, K.CANON[c % 8][0]) for c in range(int(fwd / 2.4) + 1) for h in (0, 1)], ns, T.SR, .085)
    tmp = path + ".fwd.wav"; a.write(tmp, room=(.05, .4), under=under); L.add_rewind(tmp, path, TEND, HOLD, TREW, gain=.55); os.remove(tmp)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_bheat", exist_ok=True)
    print("長さ", round(DUR, 1), score(R)[1], "材質", MAT)
    if cmd == "stills": print(T.stills(NF, make_frame, "build_bheat/s", at=(.02, .2, .4, .6, (TEND - .3) / DUR, (TEND + HOLD + .5 * TREW) / DUR))); sys.exit()
    out = f"output/bheat1_{T.LANG}.mp4"; audio("build_bheat/a.wav"); T.encode(NF, make_frame, "build_bheat/a.wav", out); print(out)
