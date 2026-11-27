# tiles.py — ふむたびに板が1つうすくなる。8色の玉、最後まで跳ねているのはどの色？（縦のショート）
#   もと：docs/trend/2026-11-27.md の A（鍵盤の上で跳ねる玉、鍵盤が落ちていき、最後の1色が勝ち。3日で30万回）。
#   まねたのは「床が減っていく勝ち抜き」というしくみだけ。絵・決まり・音・文字は自前：
#     ・8色の玉が、同じ高さ・同じ間隔で順番に跳ねる（1周で8回）。横にはゆっくり流れ、壁で折り返す
#     ・板は14枚で、厚さが1〜14とぜんぶ違う。ふむたびに1つうすくなり、厚さ0でなくなる。板のない所に下りた玉は落ちる
#       （試した別の決まり：「3回ふむと割れる」は板がほぼ同時に割れて10〜15秒で終わり、最後の一騎打ちが1秒もなかった。厚さを変えると落ちる時刻がばらける）
#     ・1色おちるたびに、はねる高さが 15% 下がる（＝はねる間隔が 8% 短くなる）。高さは点線で見せる。玉がへっても音がまばらにならず、だんだん速くなる
#     ・玉の通った跡は、やわらかい光の線（明るく短い尾＋うすく長い残像）。弧が重なって、画面がさびしくならない（11/23「密度ないとしょーもない」）
#     ・材質（11/27 持ち主「テクスチャと軌跡が安っぽい」で作り直し）：板は木（1枚ずつ木目と色が違い、角が丸い）、玉は飴玉（光が中を通る）。
#       ふまれた板は、ばねにのった重りとしてしずむ（枚数が多いほど重く、ゆっくり・小さく）。はがれた1枚は回りながら落ち、木くずが散る。玉の色が板の上の面に映る
#     ・音：板をふんだ瞬間に、硬い玉が木の板に当たる音が1つ。左の板ほど低く、右ほど高い。1周ごとにカノン進行の和音が1つ進む。落ちた玉のぶん、音が1つ抜ける
#       はねる高さが下がると、当たりは弱くなる（落ちる速さが下がるから）。鳴るのは当たった瞬間だけ：板がなくなる時の追加の音・決着の旋律は入れない
#       （11/27 持ち主「電子音ぽすぎる。もっと物理的な音がいい」「二度うちは違う感じがする。恣意的な感じがする」）
#   使い方：python3 tools/tiles.py search [数] ／ stills ／ all（LANG_OUT=en で英語、SEED=<数>、MAT=wood|bamboo|hollow で音の材質）→ output/tiles1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T

W, H, FPS = T.W, T.H, T.FPS
B = "build_tiles"; os.makedirs(B, exist_ok=True)
SEED = int(os.environ.get("SEED", 232))
XL, XR, FLOOR = 90, 990, 1380; NTILE = 14; TW = (XR - XL) / NTILE; UNIT = 12; RB = 28; NB = 8; MAT = os.environ.get("MAT", "wood")   # 音の材質は1本ごとに回す（nazo/trend/mat_log.txt）。この動画は木
H0, P0, SHR = 850.0, 2.4, .85                   # はじめの高さ・はじめの1周の秒数・1色おちるごとの高さの倍率
G0 = 32 * H0 / P0 ** 2; OUTRO = 2.8

def simulate(seed, record=False, tmax=90.0):
    rng = np.random.default_rng(seed)
    x = rng.uniform(XL + RB + 10, XR - RB - 10, NB); vx = rng.uniform(70, 190, NB) * rng.choice([-1, 1], NB)
    left = rng.permutation(np.arange(1, NTILE + 1)); thick0 = left.copy()
    alive = np.ones(NB, bool); fall = {}                          # fall[i] = [x, y, vy, 落ちはじめの時刻]
    last_hit = np.full(NTILE, -9.0); last_col = np.zeros(NTILE, int); last_cut = np.full(NTILE, -9.0); last_x = np.zeros(NTILE); subl = []
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
                    gone = False; last_hit[j] = t; last_col[j] = i; last_x[j] = x[i]
                    if t_win is None:                                         # 決着のあとは板をへらさない
                        left[j] -= 1; gone = left[j] == 0; last_cut[j] = t
                        if gone: k += 1
                    ev.append(("hit", t, float(x[i]), i, j, ci, gone, hc))
                else:
                    if t_win is not None: safe = False                        # 終わりの画面で勝者が落ちる乱数は使わない
                    alive[i] = False; fall[i] = [float(x[i]), FLOOR - RB, 4 * hc / P, t]; deaths.append((t, i)); ev.append(("out", t, float(x[i]), i, j, ci, False, hc))
                    if alive.sum() == 1 and t_win is None: t_win = t; winner = int(np.argmax(alive))
        phi = nphi
        for i, f in fall.items(): f[1] += f[2] * dt; f[2] += G0 * dt
        t += dt; step += 1
        if record:
            pos = np.zeros((NB, 3), np.float32)
            for i in range(NB):
                if alive[i]: ph = (phi + i / NB) % 1.0; pos[i] = (x[i], FLOOR - RB - 4 * hc * ph * (1 - ph), 1.0)
                elif i in fall: pos[i] = (fall[i][0], fall[i][1], max(0.0, 1 - (t - fall[i][3]) / .6))
            subl.append(pos)                                                  # 1コマの間の位置（1/240 秒きざみ）。跡と、動きのぶれに使う
            if step % 4 == 0:
                frames.append(dict(t=t, pos=pos, sub=np.array(subl), hc=hc, left=left.copy(), last_hit=last_hit.copy(), last_col=last_col.copy(), last_cut=last_cut.copy(), last_x=last_x.copy(), alive=alive.copy(), k=k)); subl = []
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
PAL = [c for _, _, c in T.PALETTE8]
SPR = [T.sprite(c, RB) for c in PAL]; SPR_S = [T.sprite(c, 19) for c in PAL]; SPR_T = [T.sprite(c, 11) for c in PAL]; RING = [T.ring(c, 17, 2.2) for c in PAL]; CHIP = T.sprite((176, 132, 84), 2.6)
GL_BACK, GL_TOP = T.glow(95), T.glow(30)                                     # 玉が背景を照らす光／板の上に映る光
TWD = int(TW) - 6; GAP = 2
STACK = [T.wood_stack(TWD, UNIT, NTILE, seed=j, gap=GAP) for j in range(NTILE)]   # 板1か所ぶん（14枚がさね）。上から順に残る
LAST = []                                                                    # 最後の1枚：赤みがかる（あと1回でなくなる）
for st in STACK: q = st[:UNIT].copy(); q[..., :3] = np.clip(q[..., :3] * np.array([1.06, .66, .54], np.float32), 0, 1); LAST.append(q)
_BG = {}
def bg():
    if "b" not in _BG:
        b = T.background((W / 2, 930)); yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        band = np.exp(-((yy - (FLOOR + 80)) / 180) ** 2) * np.clip(1 - np.abs(xx - W / 2) / 660, 0, 1) ** .8             # 板の列のうしろの、あたたかい明かり
        b += band[..., None] * np.array([.075, .052, .030], np.float32)
        fade = np.clip((yy - 440) / 520, 0, 1) * np.clip((FLOOR + NTILE * UNIT + 40 - yy) / 70, 0, 1)
        for xw in (XL - 9, XR + 9): b += (np.exp(-((xx - xw) / 1.5) ** 2) * fade)[..., None] * np.array([.20, .22, .33], np.float32)   # 左右の壁：下ほど見える細い光
        _BG["b"] = np.clip(b, 0, 1).astype(np.float32)
    return _BG["b"]

def dip(n, e):
    """ふまれた板のしずみ（ばねにのった重りを、上からたたいた時の動き）。枚数が多いほど重いので、ゆっくり・小さく動く"""
    if not 0 <= e < .7: return 0.0
    m = n + 1.0; return 11.0 / math.sqrt(m) * math.exp(-e / .11) * math.sin(2 * math.pi * 12.5 / math.sqrt(m) * e)
def top_light(buf, j, dy, xh, col, s):
    """板の上の面に、玉の色が映る"""
    if s <= .01: return
    x0 = int(XL + j * TW + 3); ya, yb = int(round(FLOOR + dy)), int(round(FLOOR + dy)) + UNIT - GAP
    g = np.exp(-((np.arange(x0, x0 + TWD) - xh) / 34.0) ** 2) * s; c = np.asarray(col, np.float32) / 255
    reg = buf[ya:yb, x0:x0 + TWD]; reg[:] = 1 - (1 - reg) * (1 - np.clip(g[None, :, None] * c, 0, .9))
def draw_tiles(buf, f, t):
    for j in range(NTILE):
        n = int(f["left"][j]); e = t - f["last_hit"][j]; ec = t - f["last_cut"][j]; x0 = int(XL + j * TW + 3); dy = dip(n, e)
        if n > 0:
            T.blit(buf, LAST[j] if n == 1 else STACK[j][:n * UNIT], x0 + TWD / 2, FLOOR + dy + (UNIT if n == 1 else n * UNIT) / 2)
            if 0 <= e < .5:
                c2 = PAL[int(f["last_col"][j])]; sv = math.exp(-e / .11); top_light(buf, j, dy, f["last_x"][j], c2, sv * .60); T.add_glow(buf, GL_TOP, f["last_x"][j], FLOOR + dy - 3, c2, sv * .42)
        if 0 <= ec < .42:                                                      # はがれた1枚：回りながら落ちる。木くずが散る
            rng = np.random.default_rng(j * 1000 + int(f["last_cut"][j] * 240)); om = rng.uniform(1.5, 4.0) * rng.choice([-1, 1]); vx = rng.uniform(-30, 30); al = 1 - T.sstep(.14, .42, ec)
            for _ in range(7):
                px, vx2, vy2 = rng.uniform(4, TWD - 4), rng.uniform(-150, 150), rng.uniform(-40, 170)
                T.blit(buf, CHIP, x0 + px + vx2 * ec, FLOOR + (n + 1) * UNIT + vy2 * ec + 1000 * ec * ec, al * .9 * T.sstep(.02, .08, ec))
            T.paste_rot(buf, STACK[j][n * UNIT:(n + 1) * UNIT], x0 + TWD / 2 + vx * ec, FLOOR + n * UNIT + UNIT / 2 + 30 * ec + 1000 * ec * ec, om * ec, al)

TY0, TY1 = 440, FLOOR + 4; TR = T.Trail(TY0, TY1); _TRI = [-9]
def trail_to(r, i):
    """玉の通った跡（残像）を i コマめまで進める。順番に呼ばれた時は1コマぶんだけ足す。とんだ時は手前 400 コマから作り直す"""
    fr = r["frames"]
    if i != _TRI[0] + 1: TR.clear(); a = max(1, i - 400)
    else: a = i
    for q in range(a, i + 1):
        segs = []
        if 1 <= q < len(fr):
            prev = fr[q - 1]["sub"][-1]
            for sub in fr[q]["sub"]:
                for bi in range(NB):
                    if sub[bi, 2] >= 1 and prev[bi, 2] >= 1: segs.append((prev[bi, 0], prev[bi, 1], sub[bi, 0], sub[bi, 1], PAL[bi], math.hypot(sub[bi, 0] - prev[bi, 0], sub[bi, 1] - prev[bi, 1]) * 240))
                prev = sub
        TR.step(segs)
    _TRI[0] = i
def wakes(r, i, back=11):
    """玉ごとの、最近 0.18 秒の位置（新しい順）。床で折り返した手前は入れない（尾は、今の向きの後ろにだけのびる）"""
    fr = r["frames"]; out = []
    for bi in range(NB):
        if fr[i]["pos"][bi, 2] < 1: continue
        pts = []
        for q in range(i, max(0, i - back), -1):
            for sub in fr[q]["sub"][::-1]:
                if sub[bi, 2] < 1: break
                if len(pts) >= 2 and (pts[-1][1] - pts[-2][1]) * (sub[bi, 1] - pts[-1][1]) < 0 and pts[-1][1] > FLOOR - RB - 30: break
                pts.append((float(sub[bi, 0]), float(sub[bi, 1])))
            else: continue
            break
        if len(pts) >= 3: out.append((pts, PAL[bi], RB * 1.25))
    return out

def make_frame(r, i):
    i = min(i, len(r["frames"]) - 1); f = r["frames"][i]; t = f["t"]; buf = bg().copy(); pos = f["pos"]; sub = f["sub"]
    for bi in range(NB):
        if pos[bi, 2] > 0: T.add_glow(buf, GL_BACK, pos[bi, 0], pos[bi, 1], PAL[bi], .060 * float(pos[bi, 2]))        # 玉が背景をほんのり照らす
    trail_to(r, i); TR.render(buf, wakes(r, i))
    draw_tiles(buf, f, t)
    for bi in range(NB):                                                     # 下りてくる玉の色が、板の上に映る
        if pos[bi, 2] >= 1:
            j = int(min(NTILE - 1, max(0, (pos[bi, 0] - XL) // TW))); n = int(f["left"][j])
            if n > 0: top_light(buf, j, dip(n, t - f["last_hit"][j]), pos[bi, 0], PAL[bi], .34 * math.exp(-(FLOOR - RB - pos[bi, 1]) / 120))
    for bi in np.argsort(pos[:, 1]):
        x, y, a = pos[bi]
        if a >= 1 and len(sub) >= 2 and sub[-2][bi, 2] >= 1: T.blit_mb(buf, SPR[bi], [sub[-2][bi, :2], sub[-1][bi, :2]])   # 1コマの後ろ半分の動きを平均する（速いほど流れる）
        elif a > 0: T.blit(buf, SPR[bi], x, y, float(a))
    for q in range(NB):                                                      # 残っている色（上の列）。落ちた色は輪だけ
        T.blit(buf, SPR_S[q] if f["alive"][q] else RING[q], W / 2 + (q - (NB - 1) / 2) * 74, 320, 1.0 if f["alive"][q] else .45)
    n_alive = int(f["alive"].sum()); deaths = [d for d in r["deaths"] if d[0] <= t]; yl = int(FLOOR - 2 * RB - f["hc"])
    for kd, (td, w) in enumerate(deaths):                                    # これまでの高さの線の右はしに、その高さで落ちた色を小さく残す（落ちた順に上から並ぶ）
        T.blit(buf, SPR_T[w], XR - 14, FLOOR - 2 * RB - H0 * SHR ** kd, .70 * T.sstep(td + .1, td + .6, t))
    def draw(d):
        T.fit_text(d, (W / 2, 150), T.tr("ふむたびに、板が1つうすくなる", "Every bounce makes the tile thinner"), 54, 960, (240, 240, 246, 255))
        T.fit_text(d, (W / 2, 226), T.tr("最後まで跳ねているのはどの色？", "Which color is still bouncing at the end?"), 42, 960, (255, 222, 150, 255), bold=False)
        for kd, (td, w) in enumerate(deaths):                                # これまでの高さ（うすい点線）
            yk = int(FLOOR - 2 * RB - H0 * SHR ** kd); al = int(60 * T.sstep(td + .1, td + .6, t))
            for xs in range(XL, XR - 40, 26): d.line([xs, yk, xs + 11, yk], fill=(150, 158, 210, al), width=1)
        d.text((W / 2, 392), T.tr(f"残り {n_alive}色", f"{n_alive} left"), font=T.fnt(36, False), fill=(200, 204, 222, 255), anchor="mm")
        for xs in range(XL, XR, 26): d.line([xs, yl, xs + 11, yl], fill=(150, 158, 210, 120), width=2)                 # はねる高さの点線
        d.text((XL + 2, yl - 22), T.tr("はねる高さ", "bounce height"), font=T.fnt(22, False), fill=(130, 136, 172, 255), anchor="lm")
        cap = None
        if r["t_win"] is not None and t >= r["t_win"] + .25:
            w = r["winner"]; a = T.sstep(r["t_win"] + .25, r["t_win"] + .7, t); cap = (T.tr(f"最後まで跳ねたのは {T.cname(w)}", f"{T.cname(w)} is the last one bouncing"), T.PALETTE8[w][2], a, 56)
        elif deaths and t - deaths[-1][0] < 1.5:
            td, w = deaths[-1]; a = min(T.sstep(td, td + .15, t), 1 - T.sstep(td + 1.1, td + 1.5, t))
            two = n_alive == 2; cap = (T.tr(f"{T.cname(w)} おちた" + ("　一騎打ち" if two else ""), f"{T.cname(w)} fell" + (" — last two" if two else "")), T.PALETTE8[w][2], a, 50)
        if cap: T.fit_text(d, (W / 2, 1640), cap[0], cap[3], 960, cap[1] + (int(255 * cap[2]),))
        T.fit_text(d, (W / 2, 1790), T.tr("1色おちるたびに、はねる高さが下がって速くなる", "Each fall lowers the bounce, so the rest speed up"), 30, 980, (150, 156, 184, 255), bold=False)
    out = T.to_frame(buf, draw, grain=i); g = min(T.sstep(0, .3, t), 1 - T.sstep(r["dur"] - .4, r["dur"], t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)

def audio(r, path):
    a = T.Audio(r["dur"], lo=69, hi=91, mat=MAT, max_same=3)
    for (kind, t, x, i, j, ci, gone, hc) in r["ev"]:
        if kind != "hit": continue                                           # 落ちた玉は鳴らない（音が1つ抜ける）
        a.hit(t, (x - XL) / (XR - XL), vel=.55 + .40 * math.sqrt(hc / H0), chord=ci)   # はねる高さが下がると、当たりは弱くなる
    return a.write(path)

if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "all"
    if m == "search": T.pick_seed(simulate, score, range(int(sys.argv[2]) if len(sys.argv) > 2 else 400)); sys.exit()
    r = simulate(SEED, record=True); n = len(r["frames"])
    print(f"長さ {r['dur']:.1f}秒 決着 {r['t_win']:.1f}秒 勝ち {T.cname(r['winner'])} なくなった板 {r['k']}枚 落ちた時刻 {[round(d[0], 1) for d in r['deaths']]}", flush=True)
    if m == "stills": print(T.stills(n, lambda i: make_frame(r, i), f"{B}/s", at=(.03, .35, .7, .97)))
    else:
        out = sys.argv[2] if len(sys.argv) > 2 else f"output/tiles1_{T.LANG}.mp4"; nn = audio(r, f"{B}/a.wav"); T.encode(n, lambda i: make_frame(r, i), f"{B}/a.wav", out); print(out, "音", nn, "個")
