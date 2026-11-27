# tiles.py — ふむたびに板が1つうすくなる。8色の玉、最後まで跳ねているのはどの色？（縦のショート）
#   もと：docs/trend/2026-11-27.md の A（鍵盤の上で跳ねる玉、鍵盤が落ちていき、最後の1色が勝ち。3日で30万回）。
#   まねたのは「床が減っていく勝ち抜き」というしくみだけ。絵・決まり・音・文字は自前：
#     ・8色の玉が、同じ高さ・同じ間隔で順番に跳ねる（1周で8回）。横にはゆっくり流れ、壁で折り返す
#     ・板は14枚で、厚さが1〜14とぜんぶ違う。ふむたびに1つうすくなり、厚さ0でなくなる。板のない所に下りた玉は落ちる
#       （試した別の決まり：「3回ふむと割れる」は板がほぼ同時に割れて10〜15秒で終わり、最後の一騎打ちが1秒もなかった。厚さを変えると落ちる時刻がばらける）
#     ・1色おちるたびに、はねる高さが 15% 下がる（＝はねる間隔が 8% 短くなる）。高さは点線で見せる。玉がへっても音がまばらにならず、だんだん速くなる
#     ・玉の通った跡を色の線で残す（2〜3秒で消える）。弧が重なって、画面がさびしくならない（11/23「密度ないとしょーもない」）
#     ・音：板をふんだ瞬間に「カロッ」。左の板ほど低く、右ほど高い。1周ごとにカノン進行の和音が1つ進む。落ちた玉のぶん、音が1つ抜ける
#   使い方：python3 tools/tiles.py search [数] ／ stills ／ all（LANG_OUT=en で英語、SEED=<数>）→ output/tiles1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T

W, H, FPS = T.W, T.H, T.FPS
B = "build_tiles"; os.makedirs(B, exist_ok=True)
SEED = int(os.environ.get("SEED", 232))
XL, XR, FLOOR = 90, 990, 1380; NTILE = 14; TW = (XR - XL) / NTILE; UNIT = 11; RB = 28; NB = 8
H0, P0, SHR = 850.0, 2.4, .85                   # はじめの高さ・はじめの1周の秒数・1色おちるごとの高さの倍率
G0 = 32 * H0 / P0 ** 2; OUTRO = 2.8

def simulate(seed, record=False, tmax=90.0):
    rng = np.random.default_rng(seed)
    x = rng.uniform(XL + RB + 10, XR - RB - 10, NB); vx = rng.uniform(70, 190, NB) * rng.choice([-1, 1], NB)
    left = rng.permutation(np.arange(1, NTILE + 1)); thick0 = left.copy()
    alive = np.ones(NB, bool); fall = {}                          # fall[i] = [x, y, vy, 落ちはじめの時刻]
    last_hit = np.full(NTILE, -9.0); last_col = np.zeros(NTILE, int)
    phi = 0.0; hc = H0; k = 0; t = 0.0; dt = 1 / 240; ev = []; frames = []; deaths = []; t_win = None; winner = -1; step = 0; safe = True
    while t < tmax:
        ht = H0 * SHR ** len(deaths); hc += (ht - hc) * (1 - math.exp(-dt / .25)); P = P0 * math.sqrt(hc / H0); nphi = phi + dt / P
        for i in range(NB):
            if not alive[i]: continue
            x[i] += vx[i] * dt
            if x[i] < XL + RB: x[i] = 2 * (XL + RB) - x[i]; vx[i] = -vx[i]
            if x[i] > XR - RB: x[i] = 2 * (XR - RB) - x[i]; vx[i] = -vx[i]
            if math.floor(nphi + i / NB) > math.floor(phi + i / NB):        # 床に着いた
                j = int(min(NTILE - 1, max(0, (x[i] - XL) // TW))); ci = int(math.floor(nphi + i / NB)) - 1
                if left[j] > 0:
                    gone = False; last_hit[j] = t; last_col[j] = i
                    if t_win is None:                                         # 決着のあとは板をへらさない
                        left[j] -= 1; gone = left[j] == 0
                        if gone: k += 1
                    ev.append(("hit", t, float(x[i]), i, j, ci, gone))
                else:
                    if t_win is not None: safe = False                        # 終わりの画面で勝者が落ちる乱数は使わない
                    alive[i] = False; fall[i] = [float(x[i]), FLOOR - RB, 4 * hc / P, t]; deaths.append((t, i)); ev.append(("out", t, float(x[i]), i, j, ci, False))
                    if alive.sum() == 1 and t_win is None: t_win = t; winner = int(np.argmax(alive))
        phi = nphi
        for i, f in fall.items(): f[1] += f[2] * dt; f[2] += G0 * dt
        t += dt; step += 1
        if record and step % 4 == 0:
            pos = np.zeros((NB, 3), np.float32)
            for i in range(NB):
                if alive[i]: ph = (phi + i / NB) % 1.0; pos[i] = (x[i], FLOOR - RB - 4 * hc * ph * (1 - ph), 1.0)
                elif i in fall: pos[i] = (fall[i][0], fall[i][1], max(0.0, 1 - (t - fall[i][3]) / .6))
            frames.append(dict(t=t, pos=pos, hc=hc, left=left.copy(), last_hit=last_hit.copy(), last_col=last_col.copy(), alive=alive.copy(), k=k))
        if t_win is not None and t > t_win + OUTRO: break
    return dict(ev=ev, frames=frames, deaths=deaths, t_win=t_win, winner=winner, safe=safe, k=k, dur=t, thick0=thick0)

def score(r):
    if r["t_win"] is None or not r["safe"]: return -99
    d = [a for a, _ in r["deaths"]]; gaps = np.diff(d); duel = d[-1] - d[-2]; s = -abs(r["t_win"] - 26) / 3
    if not 4 <= d[0] <= 10: s -= 4
    if gaps.min() < .6: s -= 3
    s += 3 if 3 <= duel <= 9 else -abs(duel - 6) / 2
    if not 20 <= r["t_win"] <= 32: s -= 6
    if gaps.max() > 7: s -= 2                                              # 長く何も起きない時間がある
    return s

# ---------- 絵 ----------
SPR = [T.sprite(c, RB) for _, _, c in T.PALETTE8]
_BG = {}
def bg():
    if "b" not in _BG:
        b = T.background((W / 2, 1000))
        for xw in (XL - 8, XR + 8): cv2.line(b, (int(xw), 470), (int(xw), FLOOR + NTILE * UNIT + 10), (.20, .21, .30), 3, cv2.LINE_AA)
        _BG["b"] = b
    return _BG["b"]
IVORY = np.array([.86, .82, .73], np.float32); THIN = np.array([.90, .62, .50], np.float32)
def draw_tile(buf, j, f, t):
    x0, x1 = int(XL + j * TW + 3), int(XL + (j + 1) * TW - 3); n = int(f["left"][j]); e = t - f["last_hit"][j]
    col = IVORY if n > 1 else THIN; dy = 0.0
    if 0 <= e < .30:
        c2 = np.array(T.PALETTE8[int(f["last_col"][j])][2], np.float32) / 255; col = col + (c2 - col) * .65 * (1 - e / .30); dy = 4 * math.exp(-e / .06) * math.cos(e * 40)
    if n > 0:
        y0, y1 = int(FLOOR + dy), int(FLOOR + n * UNIT + dy); cv2.rectangle(buf, (x0, y0), (x1, y1), tuple(float(v) for v in col), -1, cv2.LINE_AA)
        for q in range(1, n): cv2.line(buf, (x0 + 2, y0 + q * UNIT), (x1 - 2, y0 + q * UNIT), tuple(float(v) for v in col * .80), 1)   # 層の線
    if 0 <= e < .30:                                                           # はがれた1層が落ちる
        al = 1 - e / .30; ys = int(FLOOR + n * UNIT + .5 * 2400 * e * e); ya, yb = max(0, ys), min(H, ys + UNIT)
        if yb > ya: reg = buf[ya:yb, x0:x1]; reg[:] = reg * (1 - al * .8) + col * al * .8

TY0, TY1 = 440, FLOOR + 4; _TR = dict(i=-9, layer=np.zeros((TY1 - TY0, W, 3), np.float32))
def trail_to(r, i):
    """玉の通った跡を i コマめまで進める。順番に呼ばれた時は1コマぶんだけ足す。とんだ時は手前 360 コマから作り直す"""
    fr = r["frames"]; st = _TR
    if i != st["i"] + 1: st["layer"][:] = 0; a = max(1, i - 360)
    else: a = i
    for q in range(a, i + 1):
        st["layer"] *= .990
        if q < 1 or q >= len(fr): continue
        p0, p1 = fr[q - 1]["pos"], fr[q]["pos"]
        for bi in range(NB):
            if p1[bi, 2] < 1 or p0[bi, 2] < 1 or p1[bi, 1] > FLOOR - RB + 1: continue
            c = np.array(T.PALETTE8[bi][2], np.float32) / 255 * .74
            cv2.line(st["layer"], (int(p0[bi, 0]), int(p0[bi, 1] - TY0)), (int(p1[bi, 0]), int(p1[bi, 1] - TY0)), tuple(float(v) for v in c), 4, cv2.LINE_AA)
    st["i"] = i; return st["layer"]

def make_frame(r, i):
    i = min(i, len(r["frames"]) - 1); f = r["frames"][i]; t = f["t"]; buf = bg().copy()
    buf[TY0:TY1] = np.maximum(buf[TY0:TY1], trail_to(r, i))
    yl = int(FLOOR - 2 * RB - f["hc"])                                       # はねる高さの点線
    for xs in range(XL, XR, 26): cv2.line(buf, (xs, yl), (xs + 12, yl), (.34, .36, .50), 2, cv2.LINE_AA)
    for j in range(NTILE): draw_tile(buf, j, f, t)
    for bi in np.argsort(f["pos"][:, 1]):
        x, y, a = f["pos"][bi]
        if a > 0: T.blit(buf, SPR[bi], x, y, float(a))
    n_alive = int(f["alive"].sum()); deaths = [d for d in r["deaths"] if d[0] <= t]
    def draw(d):
        T.fit_text(d, (W / 2, 150), T.tr("ふむたびに、板が1つうすくなる", "Every bounce makes the tile thinner"), 54, 960, (240, 240, 246, 255))
        T.fit_text(d, (W / 2, 226), T.tr("最後まで跳ねているのはどの色？", "Which color is still bouncing at the end?"), 42, 960, (255, 222, 150, 255), bold=False)
        for q in range(NB):                                                  # 残っている色
            cx = W / 2 + (q - (NB - 1) / 2) * 74; c = T.PALETTE8[q][2]; on = bool(f["alive"][q])
            d.ellipse([cx - 20, 320 - 20, cx + 20, 320 + 20], fill=c + (255,) if on else (60, 62, 78, 255))
            if not on: d.line([cx - 14, 320 + 14, cx + 14, 320 - 14], fill=(130, 134, 156, 255), width=3)
        d.text((W / 2, 392), T.tr(f"残り {n_alive}色", f"{n_alive} left"), font=T.fnt(36, False), fill=(200, 204, 222, 255), anchor="mm")
        d.text((XR + 4, yl - 22), T.tr("はねる高さ", "bounce height"), font=T.fnt(22, False), fill=(120, 126, 160, 255), anchor="rm")
        cap = None
        if r["t_win"] is not None and t >= r["t_win"] + .25:
            w = r["winner"]; a = T.sstep(r["t_win"] + .25, r["t_win"] + .7, t); cap = (T.tr(f"最後まで跳ねたのは {T.cname(w)}", f"{T.cname(w)} is the last one bouncing"), T.PALETTE8[w][2], a, 56)
        elif deaths and t - deaths[-1][0] < 1.5:
            td, w = deaths[-1]; a = min(T.sstep(td, td + .15, t), 1 - T.sstep(td + 1.1, td + 1.5, t))
            two = n_alive == 2; cap = (T.tr(f"{T.cname(w)} おちた" + ("　一騎打ち" if two else ""), f"{T.cname(w)} fell" + (" — last two" if two else "")), T.PALETTE8[w][2], a, 50)
        if cap: T.fit_text(d, (W / 2, 1640), cap[0], cap[3], 960, cap[1] + (int(255 * cap[2]),))
        T.fit_text(d, (W / 2, 1790), T.tr("1色おちるたびに、はねる高さが下がって速くなる", "Each fall lowers the bounce, so the rest speed up"), 30, 980, (150, 156, 184, 255), bold=False)
    out = T.to_frame(buf, draw).astype(np.float32); g = min(T.sstep(0, .3, t), 1 - T.sstep(r["dur"] - .4, r["dur"], t)); return (out * g).astype(np.uint8)

def audio(r, path):
    a = T.Audio(r["dur"], lo=69, hi=91, hard=.8, roll=True, max_same=3)
    for (kind, t, x, i, j, ci, gone) in r["ev"]:
        if kind != "hit": continue                                           # 落ちた玉は鳴らない（音が1つ抜ける）
        m = a.hit(t, (x - XL) / (XR - XL), vel=.8, chord=ci)
        if gone: a.note(t + .06, m - 12, .85, .5, roll=True, hard=.5)        # なくなった板：1オクターブ下が続けて鳴る
    if r["t_win"] is not None:
        tones = T.K.canon_tones(int(r["ev"][-1][5]) if r["ev"] else 0, 69, 93)
        for q, m in enumerate(tones[::2][:6]): a.note(r["t_win"] + .45 + q * .11, m, .7, .3 + .08 * q, roll=False)
    return a.write(path)

if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "all"
    if m == "search": T.pick_seed(simulate, score, range(int(sys.argv[2]) if len(sys.argv) > 2 else 400)); sys.exit()
    r = simulate(SEED, record=True); n = len(r["frames"])
    print(f"長さ {r['dur']:.1f}秒 決着 {r['t_win']:.1f}秒 勝ち {T.cname(r['winner'])} なくなった板 {r['k']}枚 落ちた時刻 {[round(d[0], 1) for d in r['deaths']]}", flush=True)
    if m == "stills": print(T.stills(n, lambda i: make_frame(r, i), f"{B}/s", at=(.03, .35, .7, .97)))
    else:
        out = sys.argv[2] if len(sys.argv) > 2 else f"output/tiles1_{T.LANG}.mp4"; nn = audio(r, f"{B}/a.wav"); T.encode(n, lambda i: make_frame(r, i), f"{B}/a.wav", out); print(out, "音", nn, "個")
