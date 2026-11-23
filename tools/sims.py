# sims.py — 「数学的に必ずそうなる」を絵と音で見せるショート（simkit を使う）
#   python tools/sims.py <spec.json>       → output/<id>.mp4 と投稿キット
#   STILLS="5,20,30" python tools/sims.py <spec.json>   → その時刻の絵だけ（確認用）
#   spec: id / kind / title（画面の問い2行）/ count_label / yt{title, desc, tags} ＋ 種類ごとの数値
#   種類: parabola（放物線の焦点）/ rings（1周ずつ多く回る輪）/ venus（2つの軌道を線で結ぶ）
import json, sys, os, math
import numpy as np
from PIL import ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):   # spec の "palette" を色の決まりとして先に渡す
    os.environ.setdefault("SIM_PALETTE", json.load(open(sys.argv[1])).get("palette", ""))
from simkit import Sim, PENTA, FPS, S, F, hsv, dim, kit


def lerp(a, b, u): return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def parabola(sp):
    """放物線 y=x²/4f。上の線からまっすぐ落とすと、どのボールも道の長さ Y+f で焦点を通る（同時）。
    焦点を過ぎて反対側の壁で跳ね返ると、まっすぐ上に戻る（道の長さはまた Y+f）。1往復ごとにボールを増やす"""
    f, X, Y, v = 1.0, sp.get("X", 6.0), sp.get("Y", 14.0), sp.get("v", 6.4)
    ST = sp.get("stagger", 0.0)   # ボールごとに速さを変えて、着く時刻をずらす（オーナー 11/22）
    a = 4 * f * f / X; T = (Y + f) / (v * (1 - ST))          # a: 戻ってこられるいちばん内側の x。T: 上の線→焦点の時間（いちばん遅いボールに合わせる）
    ms = sp.get("rounds", [2, 3, 5, 7, 11, 16]) + [sp.get("last", 24)]; intro, tail = .3, sp.get("tail", 1.2)
    sim = Sim(sp, (-X - .15, -.15, X + .15, Y + .15))
    sim.neon([(x, x * x / (4 * f)) for x in np.linspace(-X, X, 241)])
    sim.neon([(-X, Y), (X, Y)], width=5)
    sim.ring((0, f), 13); sim.title()
    rounds = []
    for r, m in enumerate(ms):
        t0 = intro + r * 2 * T; IL = .25 if sp.get("interleave") else 0; balls = []   # interleave：左右の落とす位置を半分ずらす（当たる時刻が1個ずつになる）
        for side in (1, -1):
            for j, x1 in enumerate([a * (X / a) ** ((j + .5 + side * IL) / m) for j in range(m)]):
                x1 = side * x1; y1 = x1 * x1 / (4 * f); x2 = -4 * f * f / x1; y2 = x2 * x2 / (4 * f)
                if sp.get("from_focus"):   # 焦点から打つ：壁で跳ね返ると全部まっすぐ上へ、平行に、同時に上の線へ（道の長さ y1+f + Y-y1 = Y+f）
                    balls.append(dict(pts=[(0, f), (x1, y1), (x1, Y), (x1, y1), (0, f)], cum=[0, y1 + f, Y + f, Y + f + (Y - y1), 2 * (Y + f)],
                                      col=hsv(((j + .5) / m * .5 + (0 if side > 0 else .5)) % 1), done=0)); continue
                balls.append(dict(pts=[(x1, Y), (x1, y1), (0, f), (x2, y2), (x2, Y)], cum=[0, Y - y1, Y + f, Y + 2 * f + y2, 2 * (Y + f)],
                                  col=hsv(((j + .5) / m * .5 + (0 if side > 0 else .5)) % 1), done=0))
        n = len(balls)
        for i, b in enumerate(balls):   # ばらつきはランダムでなく波：横の位置にそって順に着く。回ごとに向きを左右入れかえる（オーナー 11/22）
            u = (b["pts"][1][0] / X + 1) / 2; b["spd"] = 1 - ST * (u if r % 2 == 0 else 1 - u)
        h1 = np.array([b["cum"][1] / b["spd"] for b in balls]); h2 = np.array([b["cum"][3] / b["spd"] for b in balls])
        o1 = np.argsort(np.argsort(h1, kind="stable")); o2 = np.argsort(np.argsort(h2, kind="stable"))
        dec, g = 4 + 3 * math.sqrt(n / 5), .9 / math.sqrt(n)
        sim.chord(t0, [60, 67, 72])
        for i, b in enumerate(balls):   # 壁に当たるたびに1個ずつ。落ちてくるときは当たった順に低→高、戻るときは高→低
            sim.note(t0 + h1[i] / v, PENTA[int(o1[i] / max(1, n - 1) * 15 + .5)], g, .5 + .3 * b["pts"][1][0] / X, dec)
            sim.note(t0 + h2[i] / v, PENTA[int((1 - o2[i] / max(1, n - 1)) * 15 + .5)], g, .5 + .3 * b["pts"][3][0] / X, dec)
        sim.chord(t0 + T, [72, 79, 84])
        rounds.append((t0, balls))
    total = intro + (len(ms) - 1) * 2 * T + T + tail
    sim.notes = [nt for nt in sim.notes if nt[0] < total - .02]
    for fi in range(int(total * FPS)):
        t = fi / FPS; r = min(len(rounds) - 1, max(0, int((t - intro) // (2 * T)))); t0, balls = rounds[r]; s = max(0, t - t0) * v
        segs = []; n = len(balls); lw = max(1.0, 2.0 * min(1, 10 / math.sqrt(n)))
        if r > 0:   # 前の回の残りの線を確定
            for b in rounds[r - 1][1]:
                while b["done"] < 4: segs.append((b["pts"][b["done"]], b["pts"][b["done"] + 1], dim(b["col"], .30))); b["done"] += 1
        live, dots = [], []
        for b in balls:
            cum, pts = b["cum"], b["pts"]; sc = min(s * b.get("spd", 1), cum[-1])
            while b["done"] < 4 and cum[b["done"] + 1] <= sc: segs.append((pts[b["done"]], pts[b["done"] + 1], dim(b["col"], .30))); b["done"] += 1
            k = b["done"]; p = pts[4] if k >= 4 else lerp(pts[k], pts[k + 1], (sc - cum[k]) / (cum[k + 1] - cum[k]))
            if k < 4: live.append((pts[k], p, dim(b["col"], .7), lw))
            dots.append((p, b["col"], 5 if n <= 32 else 4))
        sim.commit(segs, width=lw)
        e = t - (t0 + T); fl = [((0, f), 22 + e * 60, dim((255, 245, 200), 1 - e / .22), 5)] if 0 <= e < .22 and not sp.get("from_focus") else []
        if sp.get("from_focus"):
            e2 = t - t0; fl = [((0, f), 22 + e2 * 60, dim((255, 245, 200), 1 - e2 / .22), 5)] if 0 <= e2 < .22 else []
        sim.frame(t, live, dots, (sp.get("count_label", "ボール："), f"{n:,}"), fl)
    sim.finish(total)


def rings(sp):
    """同じ中心の輪の上を回るボール。外側は T 秒で L0 周、内側へ1つ進むごとに1周多い。
    T は全部の周期の公倍数なので、T 秒後に全部が出発点にそろう（途中 T/2 で縦一列、T/3 で3方向…）"""
    N, L0, T = sp.get("n", 12), sp.get("laps0", 4), sp.get("T", 36.0); intro, tail = .3, sp.get("tail", 1.5)
    rad = [1.0 - i * .75 / (N - 1) for i in range(N)]
    sim = Sim(sp, (-1.05, -1.05, 1.05, 1.05))
    th = np.linspace(0, 2 * np.pi, 241)
    for r in rad: sim.thin([(r * math.sin(x), r * math.cos(x)) for x in th], color=(52, 78, 110), width=1.5)
    sim.thin([(0, rad[-1] - .05), (0, 1.04)], color=(150, 120, 40), width=2)   # そろう線（上）
    sim.title()
    ev = {}
    for i in range(N):
        laps = L0 + i
        for j in range(laps + 1): ev.setdefault(round((intro + j * T / laps) * 1000), []).append(i)
    for ms_, ids in ev.items():   # 上の線を通るたびに1個ずつ。同時に鳴る数が多いときは1個あたりを少し小さく
        for i in ids: sim.note(ms_ / 1000, PENTA[i], .5 * len(ids) ** -.35, .5, 4.5)
    total = intro + T + tail; cols = [hsv(i / N) for i in range(N)]
    cross = [sorted(intro + j * T / (L0 + i) for j in range(L0 + i + 1)) for i in range(N)]
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = max(0, t - intro) / T; live, dots, fl = [], [], []
        for i in range(N):
            ang = 2 * np.pi * (L0 + i) * u; r = rad[i]; p = (r * math.sin(ang), r * math.cos(ang))
            for q in range(10):   # 尾（直前0.6秒、だんだん薄く）
                a0 = 2 * np.pi * (L0 + i) * max(0, u - .6 / T * (q + 1) / 10); a1 = 2 * np.pi * (L0 + i) * max(0, u - .6 / T * q / 10)
                live.append(((r * math.sin(a0), r * math.cos(a0)), (r * math.sin(a1), r * math.cos(a1)), dim(cols[i], .6 * (1 - q / 10)), 4))
            dots.append((p, cols[i], 9))
            e = min((t - c for c in cross[i] if c <= t), default=9)
            if e < .18: fl.append(((0, r), 12 + e * 70, dim(cols[i], 1 - e / .18), 3))
        sim.frame(t, live, dots, (sp.get("count_label", ""), sp.get("time_fmt", "{:.1f}秒").format(max(0, t - intro))), fl)
    sim.finish(total)


def venus(sp):
    """内側が n1 周・外側が n2 周する間、2つを結ぶ線を等間隔に引き続ける。会合が n1−n2 回あるので、その数の花びらが出る"""
    T, n1, n2 = sp.get("T", 40.0), sp.get("n1", 13), sp.get("n2", 8); r1, r2 = sp.get("r1", .723), 1.0
    NL = sp.get("lines", 610); every = sp.get("note_every", 3); intro, tail = .3, sp.get("tail", 2.0)
    sim = Sim(sp, (-1.05, -1.05, 1.05, 1.05)); th = np.linspace(0, 2 * np.pi, 241)
    for r in (r1, r2): sim.thin([(r * math.sin(x), r * math.cos(x)) for x in th], color=(46, 66, 92), width=1.5)
    sim.title()
    pos = lambda u: ((r1 * math.sin(2 * np.pi * n1 * u), r1 * math.cos(2 * np.pi * n1 * u)), (r2 * math.sin(2 * np.pi * n2 * u), r2 * math.cos(2 * np.pi * n2 * u)))
    lines = []
    for k in range(NL + 1):   # 線を引き続ける。every 本に1回、音を1つ（線が長いほど低い）
        u = k / NL; p1, p2 = pos(u); ln = math.dist(p1, p2); idx = int((1 - (ln - (r2 - r1)) / (2 * r1)) * 15 + .5)
        lines.append((intro + u * T, p1, p2, hsv(u % 1, .75, 1.0)))
        if k % every == 0: sim.note(intro + u * T, PENTA[max(0, min(15, idx))], .34, .5 + .3 * (p1[0] + p2[0]) / 2, 6.0)
    total = intro + T + tail; nxt = 0; E, V = sp.get("col_outer", [90, 170, 255]), sp.get("col_inner", [255, 214, 140])
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = max(0, t - intro) / T; segs = []
        while nxt < len(lines) and lines[nxt][0] <= t: segs.append((lines[nxt][1], lines[nxt][2], dim(lines[nxt][3], sp.get("line_gain", .30)))); nxt += 1
        for sg in segs: sim.commit([sg], width=sp.get("line_w", 1.3))   # 1本ずつ足す（交わったところが明るくなる）
        p1, p2 = pos(u)
        sim.frame(t, [(p1, p2, (235, 240, 255), 2)], [((0, 0), (255, 190, 60), 13), (p1, tuple(V), 7), (p2, tuple(E), 8)],
                  (sp.get("count_fmt", "地球 {e}周 ／ 金星 {v}周").format(e=min(n2, int(n2 * u + 1e-9)), v=min(n1, int(n1 * u + 1e-9))), ""))
    sim.finish(total)


def cardioid(sp):
    """円の上に N 個の点。i 番の点から (mult×i を N で割った余り) 番の点へ、1個ずつボールを打つ。
    残った線の重なり（包絡線）が曲線になる。mult=2 ならカージオイド（0番に光源を置いた円の中の反射光と同じ線）"""
    N, mult = sp.get("N", 100), sp.get("mult", 2); gap, fly = sp.get("gap", .3), sp.get("fly", 2.0); intro, tail = .3, sp.get("tail", 1.6)
    P = [(math.sin(2 * np.pi * i / N), math.cos(2 * np.pi * i / N)) for i in range(N)]
    sim = Sim(sp, (-1.17, -1.17, 1.17, 1.17))
    sim.neon(P, closed=True, width=5)
    for i in range(0, N, max(1, N // 10)): sim.text((P[i][0] * 1.11, P[i][1] * 1.11), str(i), size=30)
    sim.title()
    shots = []
    for i in range(1, N):
        j = (mult * i) % N
        if j == i: continue
        t0 = intro + len(shots) * gap; ln = math.dist(P[i], P[j])
        shots.append(dict(i=i, j=j, t0=t0, col=hsv(i / N), done=False))
        sim.note(t0 + fly, PENTA[max(0, min(15, int((1 - ln / 2) * 15 + .5)))], .42, .5 + .3 * P[j][0], 5.0)   # 着いた瞬間に1個ずつ。線が長いほど低い
    total = shots[-1]["t0"] + fly + tail
    for fi in range(int(total * FPS)):
        t = fi / FPS; live, dots, fl, cur = [], [], [], None
        for sh in shots:
            if sh["t0"] > t: break
            cur = sh; u = (t - sh["t0"]) / fly
            if u >= 1:
                if not sh["done"]: sim.commit([(P[sh["i"]], P[sh["j"]], dim(sh["col"], .5))], width=1.6); sh["done"] = True
                e = t - sh["t0"] - fly
                if e < .18: fl.append((P[sh["j"]], 9 + e * 60, dim(sh["col"], 1 - e / .18), 3))
                continue
            p = lerp(P[sh["i"]], P[sh["j"]], u); live.append((P[sh["i"]], p, dim(sh["col"], .7), 1.6)); dots.append((p, sh["col"], 5))
        lab = sp.get("rule_fmt", "{i} → {j}").format(i=cur["i"], j=cur["j"]) if cur else ""
        sim.frame(t, live, dots, ("", lab), fl)
    sim.finish(total)


def mirrors2(sp):
    """2枚の鏡（下：放物線、上：双曲線）。上の線からまっすぐ落とすと、放物線→双曲線と跳ね返って、
    どのボールも道の長さ Y+f+2A で下の点 F2 に着く（同時）。反射望遠鏡（カセグレン式）と同じ並べ方"""
    f, X, Y, d, yv, v = sp.get("f", 6.0), sp.get("X", 4.2), sp.get("Y", 7.5), sp.get("d", 1.6), sp.get("yv", 4.4), sp.get("v", 3.6)
    c = (f - d) / 2; A = yv - c; C = (f + d) / 2; B2 = C * C - A * A; F1, F2 = (0, f), (0, -d)
    xin, hole = sp.get("xin", 1.3), sp.get("hole", .45); ms = sp.get("rounds", [2, 3, 5, 7, 11, 16, 24]); every, intro, tail = sp.get("every", 3.2), .3, sp.get("tail", 1.4)
    Lp = Y + f + 2 * A; sim = Sim(sp, (-X - .15, -d - .35, X + .15, Y + .15))
    for sg in (1, -1): sim.neon([(sg * x, x * x / (4 * f)) for x in np.linspace(hole, X, 80)])
    hw = 1.25; sim.neon([(x, c + A * math.sqrt(1 + x * x / B2)) for x in np.linspace(-hw, hw, 60)], width=6)
    sim.neon([(-X, Y), (-xin + .05, Y)], width=5); sim.neon([(xin - .05, Y), (X, Y)], width=5)
    sim.ring(F2, 13); sim.title()
    waves = []
    for r, m in enumerate(ms):
        t0 = intro + r * every; balls = []
        for side in (1, -1):
            for j in range(m):
                x1 = side * (xin + (X - xin) * (j + .5) / m); y1 = x1 * x1 / (4 * f); L = y1 + f; ux, uy = (0 - x1) / L, (f - y1) / L
                q2 = x1 * x1 + (y1 + d) ** 2; b = x1 * ux + (y1 + d) * uy; s = ((2 * A + L) ** 2 - q2) / (2 * (b + 2 * A + L)); Q = (x1 + s * ux, y1 + s * uy)
                balls.append(dict(pts=[(x1, Y), (x1, y1), Q, F2], cum=[0, Y - y1, Y - y1 + s, Lp], col=hsv(((j + .5) / m * .5 + (0 if side > 0 else .5)) % 1), done=0))
        n = len(balls); dec, g = 4 + 3 * math.sqrt(n / 5), .9 / math.sqrt(n)
        o1 = np.argsort(np.argsort([b["cum"][1] for b in balls], kind="stable")); o2 = np.argsort(np.argsort([b["cum"][2] for b in balls], kind="stable"))
        for i, b in enumerate(balls):   # 鏡に当たるたびに1個ずつ（下の鏡は低い側、上の鏡は高い側の音）
            sim.note(t0 + b["cum"][1] / v, PENTA[int(o1[i] / max(1, n - 1) * 7 + .5)], g, .5 + .3 * b["pts"][1][0] / X, dec)
            sim.note(t0 + b["cum"][2] / v, PENTA[8 + int(o2[i] / max(1, n - 1) * 7 + .5)], g, .5 + .3 * b["pts"][2][0] / X, dec)
        sim.chord(t0 + Lp / v, [72, 79, 84])
        waves.append((t0, balls))
    total = waves[-1][0] + Lp / v + tail; count = 0
    for fi in range(int(total * FPS)):
        t = fi / FPS; live, dots, segs, fl, shown = [], [], [], [], 0
        for t0, balls in waves:
            if t0 > t: break
            s = (t - t0) * v; n = len(balls); lw = max(1.0, 2.0 * min(1, 10 / math.sqrt(n))); shown = n
            for b in balls:
                cum, pts = b["cum"], b["pts"]
                while b["done"] < 3 and cum[b["done"] + 1] <= s: segs.append((pts[b["done"]], pts[b["done"] + 1], dim(b["col"], .30))); b["done"] += 1
                k = b["done"]
                if k < 3:
                    p = lerp(pts[k], pts[k + 1], (s - cum[k]) / (cum[k + 1] - cum[k])); live.append((pts[k], p, dim(b["col"], .7), lw)); dots.append((p, b["col"], 5 if n <= 32 else 4))
            e = t - (t0 + Lp / v)
            if 0 <= e < .22: fl.append((F2, 22 + e * 60, dim((255, 245, 200), 1 - e / .22), 5))
        sim.commit(segs, width=1.6)
        sim.frame(t, live, dots, (sp.get("count_label", "ボール："), f"{shown:,}"), fl)
    sim.finish(total)


def picount(sp):
    """壁・軽い箱（重さ1）・重い箱（重さM）。重い箱をすべらせて、完全に弾むぶつかり方で回数を数える。
    M=1 で3回、100 で31回、10000 で314回（Galperin のビリヤード。円周率の桁が出る）。3段を上から順に見せる"""
    stages = sp.get("stages", [[1, 1.8, 1.6], [100, .9, 1.7], [10000, .8, 1.6]]); intro, tail = .3, sp.get("tail", 2.6); a0, w1 = .6, .34   # [重さ, 速さ（画面の秒あたり）, 重い箱の出発位置]
    XR = 4.2; sim = Sim(sp, (-.2, -3.3, 5.5, 3.3)); lanes = [2.0, 0.0, -2.0][:len(stages)]
    for y in lanes: sim.neon([(0, y), (XR, y)], width=4); sim.neon([(0, y), (0, y + 1.25)], width=6)
    sim.title()
    runs, t0 = [], intro
    for (M, k, b0), y in zip(stages, lanes):
        a, b, v1, v2, t = a0, b0, 0.0, -1.0, 0.0; st = [(0.0, a, b, v1, v2)]; hits = []
        while True:
            tw = a / -v1 if v1 < -1e-15 else math.inf; tb = (b - a) / (v1 - v2) if v1 - v2 > 1e-15 else math.inf
            if not math.isfinite(min(tw, tb)): break
            dt = min(tw, tb); a += v1 * dt; b += v2 * dt; t += dt
            if tw < tb: a, v1 = 0.0, -v1; hits.append((t, "w"))
            else: a = b; v1, v2 = ((1 - M) * v1 + 2 * M * v2) / (1 + M), ((M - 1) * v2 + 2 * v1) / (1 + M); hits.append((t, "b"))
            st.append((t, a, b, v1, v2))
        dur = (t + .8) / k                 # 最後の1回の少しあとで次の段へ（箱はそのまま動き続ける）
        runs.append(dict(M=M, y=y, t0=t0, k=k, st=st, hits=[(t0 + h / k, c) for h, c in hits], w2=.34 + .2 * math.log10(M), col=hsv(.08 + .12 * len(runs))))
        prev = -1
        for h, c in hits:   # ぶつかるたびに1音（壁は高いド、箱どうしはソ）。間が詰まるほど短く小さく
            th = t0 + h / k; gap = th - prev; prev = th
            sim.note(th, 84 if c == "w" else 79, .5 * min(1, gap / .06) ** .5, .25 if c == "w" else .6, 14 if gap > .08 else 40)
        t0 += dur
    total = t0 + tail
    def state(run, t):
        tau = (t - run["t0"]) * run["k"]; st = run["st"]; i = np.searchsorted([q[0] for q in st], tau, side="right") - 1
        if i < 0: return None
        _, a, b, v1, v2 = st[i]; dt = tau - st[i][0]; return a + v1 * dt, b + v2 * dt
    for run in runs: run["times"] = [h for h, _ in run["hits"]]; run["stt"] = np.array([q[0] for q in run["st"]])
    for fi in range(int(total * FPS)):
        t = fi / FPS
        def draw(d, t=t):
            for run in runs:
                if t < run["t0"] and run is not runs[0]: continue
                y = run["y"]; tau = max(0, (t - run["t0"])) * run["k"]; i = max(0, int(np.searchsorted(run["stt"], tau, side="right")) - 1)
                _, a, b, v1, v2 = run["st"][i]; dt = tau - run["st"][i][0]; a, b = a + v1 * dt, b + v2 * dt
                for x0, w, col, lab in ((a, w1, (120, 220, 255), "1"), (b + w1, run["w2"], run["col"], f"{run['M']:,}")):
                    lab += sp.get("unit", "kg")
                    if x0 > XR: continue
                    X0, Y0 = sim.to((x0, y + w)); X1, Y1 = sim.to((min(XR, x0 + w), y)); d.rectangle([X0, Y0, X1, Y1 - 3 * S], fill=dim(col, .85), outline=col, width=2 * S)
                    f = F(34 * S); tw_ = d.textlength(lab, font=f)
                    if x0 + w <= XR: d.text(((X0 + X1) / 2 - tw_ / 2, Y0 - 50 * S), lab, font=f, fill=(215, 222, 235))
                n = int(np.searchsorted(run["times"], t, side="right")); f = F(96 * S); s_ = f"{n}"; tw_ = d.textlength(s_, font=f); X, Y = sim.to((5.45, y + .95))
                d.text((X - tw_, Y), s_, font=f, fill=(255, 210, 70), stroke_width=6 * S, stroke_fill=(0, 0, 0))
        sim.frame(t, draw=draw)
    sim.finish(total)


def sunflower(sp):
    """たねを1個ずつ置く。n 個目は中心から c√n の距離、角度は n×137.5°（黄金角）。
    すきまなく並び、うずまきの本数がフィボナッチ数（21・34・55…）になる（Vogel のモデル）。最初はゆっくり、だんだん速く"""
    N, ang = sp.get("N", 500), sp.get("angle", 137.50776); T, pw = sp.get("T", 30.0), sp.get("pow", .6); intro, tail = .3, sp.get("tail", 2.2)
    fam = sp.get("family", 34); c = 1 / math.sqrt(N); sim = Sim(sp, (-1.06, -1.06, 1.06, 1.06)); sim.title()
    pos = [(c * math.sqrt(n) * math.sin(math.radians(ang * n)), c * math.sqrt(n) * math.cos(math.radians(ang * n))) for n in range(1, N + 1)]
    tt = [intro + T * ((n + 1) / N) ** pw for n in range(N)]; prev = 0
    for n in range(N):   # 置くたびに1音。うずまきの列（n を fam で割った余り）ごとに高さを変える。詰まるほど小さく短く
        gap = tt[n] - prev; prev = tt[n]
        sim.note(tt[n], PENTA[(n % fam) % 16], .5 * min(1, gap / .12) ** .5, .5 + .3 * pos[n][0], 6 if gap > .15 else 14)
    total = tt[-1] + tail; k = 0; rdot = sp.get("dot", 9.5)
    for fi in range(int(total * FPS)):
        t = fi / FPS; fl, live = [], []
        while k < N and tt[k] <= t: sim.dot(pos[k], rdot * (.55 + .45 * math.sqrt((k + 1) / N)), hsv((k % fam) / fam, .8, 1.0)); k += 1
        if 0 < k < N or (k == N and t - tt[-1] < .3):
            p = pos[k - 1]; e = t - tt[k - 1]
            if tt[k - 1] - (tt[k - 2] if k > 1 else 0) > .07: live.append(((0, 0), p, (120, 130, 150), 1.5))   # 置く向きを示す針（速くなったら消す）
            if e < .15: fl.append((p, 9 + e * 60, dim((255, 245, 200), 1 - e / .15), 3))
        sim.frame(t, live, (), (sp.get("count_label", "たね："), f"{k:,}"), fl)
    sim.finish(total)


def ulam(sp):
    """数字を 1 から順に、うずまきに並べる（ウラムのらせん）。素数のマスだけ明るくする。
    素数が斜めの線に並んで見える。最初はゆっくり、だんだん速く"""
    G = sp.get("grid", 29); N = G * G; T, pw = sp.get("T", 30.0), sp.get("pow", .5); intro, tail = .3, sp.get("tail", 2.4)
    sim = Sim(sp, (-G / 2 - .3, -G / 2 - .3, G / 2 + .3, G / 2 + .3)); sim.title()
    xy, x, y, dx, dy, seg, run, turn = [], 0, 0, 1, 0, 1, 0, 0
    for n in range(1, N + 1):   # 1 を中心に、右→上→左→下の順に回る
        xy.append((x, y)); x += dx; y += dy; run += 1
        if run == seg:
            run = 0; dx, dy = -dy, dx; turn += 1
            if turn % 2 == 0: seg += 1
    sieve = bytearray([1]) * (N + 1); sieve[0:2] = b"\0\0"
    for i in range(2, int(N ** .5) + 1):
        if sieve[i]: sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
    tt = [intro + T * ((n + 1) / N) ** pw for n in range(N)]; prev = 0; npr = 0
    for n in range(N):   # 素数のマスで高い音、それ以外は低い小さい音。詰まるほど小さく短く
        gap = tt[n] - prev; prev = tt[n]; g = min(1, gap / .12) ** .5; ring = max(abs(xy[n][0]), abs(xy[n][1]))
        if sieve[n + 1]: sim.note(tt[n], PENTA[5 + ring % 10], .55 * g, .5 + .3 * xy[n][0] / (G / 2), 6 if gap > .15 else 14)
        else: sim.note(tt[n], 60, .12 * g, .5, 20)
    total = tt[-1] + tail; k = 0; pc = 0
    for fi in range(int(total * FPS)):
        t = fi / FPS; dots = []
        while k < N and tt[k] <= t:
            cx_, cy_ = xy[k]; pr = sieve[k + 1]; pc += pr
            sim.cell((cx_ - .42, cy_ - .42), (cx_ + .42, cy_ + .42), (255, 214, 90) if pr else (22, 30, 48)); k += 1
        if 0 < k < N: dots.append((xy[k - 1], (255, 255, 255), 5))
        sim.frame(t, (), dots, (sp.get("count_fmt", "{n} まで　素数 ").format(n=k), f"{pc}"))
    sim.finish(total)


def corner(sp):
    """直角に組んだ2枚の鏡（V字）。上の線からまっすぐ落とすと、2回跳ね返って、来た向きとちょうど逆向きに戻る。
    道の長さはどのボールも 2Y（下り Y−|x|、横 2|x|、上り Y−|x|）なので、同時に上の線に戻る。途中、全部が同時に真ん中の線を横切る"""
    X, Y, v = sp.get("X", 5.0), sp.get("Y", 8.5), sp.get("v", 4.6); ms = sp.get("rounds", [1, 2, 3, 5, 8, 13, 21]); intro, tail = .3, sp.get("tail", 1.2)
    xin, xout = sp.get("xin", .45), X - .25; Tw = 2 * Y / v
    sim = Sim(sp, (-X - .15, -.25, X + .15, Y + .15))
    sim.neon([(-X, X), (0, 0), (X, X)]); sim.neon([(-X, Y), (X, Y)], width=5); sim.title()
    waves = []
    for r, m in enumerate(ms):
        t0 = intro + r * Tw; balls = []
        for side in (1, -1):
            for j in range(m):
                x = side * (xin + (xout - xin) * ((j + .5) / m)); ax = abs(x)
                balls.append(dict(pts=[(x, Y), (x, ax), (-x, ax), (-x, Y)], cum=[0, Y - ax, Y + ax, 2 * Y], col=hsv(((j + .5) / m * .5 + (0 if side > 0 else .5)) % 1), done=0))
        n = len(balls); dec, g = 4 + 3 * math.sqrt(n / 5), .9 / math.sqrt(n)
        o = np.argsort(np.argsort([b["cum"][1] for b in balls], kind="stable"))   # 外側ほど先に当たる
        sim.chord(t0, [60, 67, 72])
        for i, b in enumerate(balls):   # 鏡に当たるたびに1個ずつ。1回目は当たった順に低→高、2回目は高→低
            idx = int(o[i] / max(1, n - 1) * 15 + .5)
            sim.note(t0 + b["cum"][1] / v, PENTA[idx], g, .5 + .3 * b["pts"][1][0] / X, dec)
            sim.note(t0 + b["cum"][2] / v, PENTA[idx], g, .5 + .3 * b["pts"][2][0] / X, dec)
        waves.append((t0, balls))
    total = intro + len(ms) * Tw + tail; sim.chord(intro + len(ms) * Tw, [72, 79, 84])
    for fi in range(int(total * FPS)):
        t = fi / FPS; live, dots, segs, fl, shown = [], [], [], [], 0
        for t0, balls in waves:
            if t0 > t: break
            s = (t - t0) * v; n = len(balls); lw = max(1.0, 2.0 * min(1, 10 / math.sqrt(n)))
            if s <= 2 * Y + 1e-9: shown = n
            for b in balls:
                cum, pts = b["cum"], b["pts"]
                while b["done"] < 3 and cum[b["done"] + 1] <= s: segs.append((pts[b["done"]], pts[b["done"] + 1], dim(b["col"], .30))); b["done"] += 1
                k = b["done"]
                if k < 3:
                    p = lerp(pts[k], pts[k + 1], (s - cum[k]) / (cum[k + 1] - cum[k])); live.append((pts[k], p, dim(b["col"], .7), lw)); dots.append((p, b["col"], 5 if n <= 32 else 4))
            e = t - (t0 + Tw)
            if 0 <= e < .2:
                for b in balls: fl.append((b["pts"][3], 7 + e * 50, dim(b["col"], 1 - e / .2), 2))
        sim.commit(segs, width=1.6)
        sim.frame(t, live, dots, (sp.get("count_label", "ボール："), f"{shown or len(waves[-1][1]):,}"), fl)
    sim.finish(total)


def pendulums(sp):
    """振り子の波を真上から見た形。上の段は T 秒で L0 往復、下の段へ1つ進むごとに1往復多い。
    最初は縦一列、すぐにへび・波・ばらばらに見えて、T 秒でまた一列にそろう（小さい振れ幅の近似）"""
    N, L0, T = sp.get("n", 15), sp.get("laps0", 26), sp.get("T", 36.0); intro, tail = .3, sp.get("tail", 1.5)
    per = [T / (L0 + i) for i in range(N)]; ys = [1.0 - 1.6 * i / (N - 1) for i in range(N)]; A = .82
    sim = Sim(sp, (-1.0, -.7, 1.0, 1.1))
    for y in ys: sim.thin([(-A, y), (A, y)], color=(40, 56, 80), width=1.2)
    sim.thin([(A, 1.06), (A, -.66)], color=(150, 120, 40), width=2); sim.title()
    for i in range(N):   # 右の端（出発点）に戻るたびに1音（下の段ほど高い）
        for j in range(L0 + i + 1):
            tt = intro + j * per[i]
            if tt <= intro + T + .01: sim.note(tt, PENTA[i % 16], .42, .8, 5.0)
    cols = [hsv(i / N) for i in range(N)]; total = intro + T + tail
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = max(0, t - intro); live, dots = [], []
        for i in range(N):
            x = A * math.cos(2 * np.pi * u / per[i]); p = (x, ys[i])
            for q in range(8):
                t0_, t1_ = max(0, u - .035 * (q + 1)), max(0, u - .035 * q)
                live.append(((A * math.cos(2 * np.pi * t0_ / per[i]), ys[i]), (A * math.cos(2 * np.pi * t1_ / per[i]), ys[i]), dim(cols[i], .6 * (1 - q / 8)), 5))
            dots.append((p, cols[i], 9))
        sim.frame(t, live, dots, (sp.get("count_label", ""), sp.get("time_fmt", "{:.1f}秒").format(u)))
    sim.finish(total)


def lissajous(sp):
    """1個のボールが、横は a 回・縦は b 回ゆれる（リサージュ曲線）。軌跡を残すと、T 秒でちょうど閉じる"""
    a, b, ph, T = sp.get("a", 3), sp.get("b", 5), sp.get("phase", .25), sp.get("T", 24.0); intro, tail = .3, sp.get("tail", 2.0)
    sim = Sim(sp, (-1.08, -1.08, 1.08, 1.08)); sim.thin([(-1.05, 0), (1.05, 0)], color=(44, 58, 80)); sim.thin([(0, -1.05), (0, 1.05)], color=(44, 58, 80)); sim.title()
    P = lambda u: (math.sin(2 * np.pi * a * u), math.sin(2 * np.pi * (b * u + ph)))
    steps = 4000; prev = P(0); pp = prev
    for k in range(1, steps + 1):   # 縦の線・横の線をまたぐたびに1音（場所で高さが変わる）
        u = k / steps; p = P(u)
        if (p[0] >= 0) != (prev[0] >= 0): sim.note(intro + u * T, PENTA[int((p[1] + 1) / 2 * 15 + .5)], .45, .5, 5.0)
        if (p[1] >= 0) != (prev[1] >= 0): sim.note(intro + u * T, PENTA[int((p[0] + 1) / 2 * 15 + .5)], .45, .5 + .3 * p[0], 5.0)
        if k >= 2:   # 端で折り返すたびにも1音（横の端は低め、縦の端は高め）
            if (p[0] - prev[0]) * (prev[0] - pp[0]) < 0: sim.note(intro + u * T, PENTA[2 if p[0] < 0 else 4], .38, .5 + .4 * p[0], 6.0)
            if (p[1] - prev[1]) * (prev[1] - pp[1]) < 0: sim.note(intro + u * T, PENTA[11 if p[1] < 0 else 14], .38, .5 + .3 * p[0], 6.0)
        pp = prev; prev = p
    sim.chord(intro + T, [60, 67, 72, 76]); total = intro + T + tail; done = 0
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = min(1, max(0, t - intro) / T); k1 = int(u * steps); segs = []
        while done < k1: segs.append((P(done / steps), P((done + 1) / steps), hsv(done / steps, .75, .9))); done += 1
        sim.commit(segs, width=3.2); p = P(u)
        sim.frame(t, (), [(p, (255, 255, 255), 8)], (sp.get("count_label", ""), sp.get("time_fmt", "{:.1f}秒").format(max(0, t - intro))))
    sim.finish(total)


def koch(sp):
    """三角形のふちをボールが1周するたびに、通った辺の真ん中1/3を外へ折り曲げて、ふちを4/3倍にする（コッホ曲線）。
    6段まで。ふちの長さは 3, 4, 5.33, 7.11 … と増え続けるが、面積は最初の三角形の1.6倍を超えない"""
    steps, T = sp.get("steps", 6), sp.get("lap", [3.0, 3.6, 4.2, 4.8, 5.4, 6.0, 6.6]); intro, tail = .3, sp.get("tail", 2.0)
    R = 1.0; tri = [(R * math.sin(2 * np.pi * k / 3), R * math.cos(2 * np.pi * k / 3)) for k in range(3)]
    def refine(P):
        out = []
        for i in range(len(P)):
            a, b = np.array(P[i]), np.array(P[(i + 1) % len(P)]); d = b - a; p1, p2 = a + d / 3, a + 2 * d / 3
            n = np.array([-d[1], d[0]]) * (math.sqrt(3) / 6); out += [tuple(a), tuple(p1), tuple((a + b) / 2 + n), tuple(p2)]
        return out
    levels = [tri]
    for _ in range(steps): levels.append(refine(levels[-1]))
    sim = Sim(sp, (-1.25, -1.25, 1.25, 1.25)); sim.title()
    side0 = math.dist(tri[0], tri[1]); t0 = intro; laps = []
    for lv in range(steps + 1):
        P = levels[lv]; n = len(P); dur = T[min(lv, len(T) - 1)]; laps.append((t0, dur, P))
        for k in range(n):   # 角を曲がるたびに1音（同じ段の中では1周で音が上がっていく）。角が多いほど小さく短く
            if n <= 800 or k % max(1, n // 800) == 0:
                sim.note(t0 + dur * k / n, PENTA[int(k / n * 15 + .5)], .5 * min(1, 24 / n) ** .35, .5 + .3 * P[k][0], 5 + 6 * math.sqrt(n / 48))
        t0 += dur
    total = t0 + tail; colsL = [hsv(.55 + .07 * i) for i in range(steps + 1)]
    for fi in range(int(total * FPS)):
        t = fi / FPS; lv = 0
        for i, (a_, d_, P) in enumerate(laps):
            if t >= a_: lv = i
        a_, d_, P = laps[lv]; n = len(P); u = min(1, max(0, (t - a_) / d_)); m = u * n; k = int(m)
        live = []
        prevP = laps[lv - 1][2] if lv > 0 else None
        if prevP is not None:   # まだ折り曲げていないところは前の段の形
            for i in range(len(prevP)):
                if i * 4 >= k: live.append((prevP[i], prevP[(i + 1) % len(prevP)], dim(colsL[lv - 1], .9), 3))
        for i in range(min(k, n)): live.append((P[i], P[(i + 1) % n], colsL[lv], 4))
        cur = lerp(P[k % n], P[(k + 1) % n], m - k) if k < n else P[0]
        if k < n: live.append((P[k % n], cur, colsL[lv], 3))
        L = side0 * 3 * (4 / 3) ** lv
        sim.frame(t, live, [(cur, (255, 255, 255), 7)], (sp.get("len_fmt", "ふちの長さ {L:.2f}　段 {s}　").format(L=L / side0, s=lv), ""))
    sim.finish(total)


def cycloid(sp):
    """逆さのサイクロイドの坂。どの高さから転がしても（摩擦なし）、同じ時間で底に着く（等時性）。
    波ごとに数を増やして同時に放す"""
    r = 1.0; T = sp.get("T", 2.6); ms = sp.get("rounds", [3, 5, 8, 13]); intro, tail = .3, sp.get("tail", 1.4)
    X = lambda th: r * (th - math.sin(th)) - r * math.pi; Y = lambda th: r * (1 + math.cos(th))   # th∈[0,2π]、底は th=π（y=0）
    sim = Sim(sp, (-math.pi - .1, -.15, math.pi + .1, 2.15)); sim.neon([(X(th), Y(th)) for th in np.linspace(0, 2 * np.pi, 300)]); sim.ring((0, 0), 12); sim.title()
    # 底からの道のり s で単振動：s(t)=s0 cos(πt/(2T))。s と th の関係： s = 4r cos(th/2) ... 底(th=π)で0
    s_of = lambda th: 4 * r * math.cos(th / 2)
    th_of = lambda s_: 2 * math.acos(max(-1, min(1, s_ / (4 * r))))
    waves = []; t0 = intro
    for w, m in enumerate(ms):
        side = 1 if w % 2 == 0 else -1; balls = []
        for j in range(m):
            th0 = .25 + (math.pi - .45) * (j + .5) / m   # 左の坂の上から底近くまで
            if side < 0: th0 = 2 * np.pi - th0
            balls.append(dict(s0=s_of(th0), col=hsv((j + .5) / m * .8 + .1 * w), tr=[]))
        waves.append((t0, balls)); n = m
        for b in balls: sim.note(t0, PENTA[3 + int(abs(b["s0"]) / 4 * 10)], .3 / math.sqrt(n), .5, 6)
        sim.chord(t0 + T, [72, 79, 84], .45); sim.chord(t0 + 3 * T, [67, 74, 79], .35)
        t0 += 4 * T
    total = t0 + tail
    for fi in range(int(total * FPS)):
        t = fi / FPS; dots, segs, fl = [], [], []
        for i, (a_, balls) in enumerate(waves):
            if t < a_ or (i + 1 < len(waves) and t >= waves[i + 1][0]): continue
            u = t - a_
            for b in balls:
                s_ = b["s0"] * math.cos(math.pi * u / (2 * T)); p = (X(th_of(s_)), Y(th_of(s_)))
                if b["tr"]: segs.append((b["tr"][-1], p, dim(b["col"], .35)))
                b["tr"].append(p); dots.append((p, b["col"], 10))
            e = (u - T) % (2 * T)
            if e < .22: fl.append(((0, 0), 18 + e * 60, dim((255, 245, 200), 1 - e / .22), 4))
        sim.commit(segs, width=1.4)
        n = len([1 for a_, bs in waves if a_ <= t]) and len(next(bs for a_, bs in reversed(waves) if a_ <= t))
        sim.frame(t, (), dots, (sp.get("count_label", "ボール："), f"{n}"), fl)
    sim.finish(total)


def basket(sp):
    """同じ高さから真下に落としたボールが、床で1回跳ねて、全部かごに入る。床の形は「どの位置で跳ねてもかごの中心を
    上から通る」ように、反射の向きを1点ずつ計算してつないだ曲線（数値計算）。数は 1,2,3,5,8,13,21,34"""
    g, H, Tg = sp.get("g", 4.0), sp.get("H", 7.0), tuple(sp.get("target", [-2.2, 4.2])); xa, xb = sp.get("xa", .3), sp.get("xb", 4.2)
    TL = sp.get("tilt", 0.0); Hx = lambda x: H + TL * (x - xa) / (xb - xa)   # 落とす線を傾けると、落ちる時間が自然にずれる（コロコロ）
    vols, gap = sp.get("volleys", [1, 2, 3, 5, 8, 13, 21, 34]), sp.get("gap", 3.0); intro, tail = .3, sp.get("tail", 1.6)
    def outdir(x, y):
        v2 = 2 * g * (Hx(x) - y); dx, dy = Tg[0] - x, Tg[1] - y; A = g * dx * dx / (2 * v2); u = (dx - math.sqrt(dx * dx - 4 * A * (A + dy))) / (2 * A)
        ox, oy = math.copysign(1, dx), u * math.copysign(1, dx); L = math.hypot(ox, oy); return ox / L, oy / L
    def slope(x, y): o = outdir(x, y); return -o[0] / (o[1] + 1)
    xs = np.linspace(xa, xb, 2001); y = 0.0; ys = [y]
    for i in range(len(xs) - 1):
        h = xs[i + 1] - xs[i]; k1 = slope(xs[i], y); k2 = slope(xs[i] + h / 2, y + h / 2 * k1); k3 = slope(xs[i] + h / 2, y + h / 2 * k2); k4 = slope(xs[i + 1], y + h * k3)
        y += h * (k1 + 2 * k2 + 2 * k3 + k4) / 6; ys.append(y)
    ys = np.array(ys)
    sim = Sim(sp, (Tg[0] - .9, -.4, xb + .2, max(H, Hx(xb)) + .2))
    sim.neon(list(zip(xs[::20], ys[::20])) + [(xs[-1], ys[-1])]); sim.neon([(xa - .1, Hx(xa - .1)), (xb + .1, Hx(xb + .1))], width=4)
    rim = .38; sim.neon([(Tg[0] - rim, Tg[1]), (Tg[0] + rim, Tg[1])], color=(255, 170, 70), glow=(255, 120, 30), width=6)
    sim.neon([(Tg[0] - rim - .05, Tg[1] - .1), (Tg[0] - rim - .05, Tg[1] + 1.2)], width=5)
    for k in range(5): sim.thin([(Tg[0] - rim + k * rim / 2, Tg[1]), (Tg[0] - rim * .6 + k * rim * .3, Tg[1] - .7)], color=(150, 150, 165), width=1.2)
    sim.title()
    balls, t0 = [], intro; scored_t = []; WV, HUE0 = sp.get("wave", 0.0), sp.get("hue0", 0.0)
    for w, m in enumerate(vols):
        for j in range(m):
            x0 = xa + .15 + (xb - xa - .3) * ((j + .5) / m); i = int(np.searchsorted(xs, x0)); yf = float(np.interp(x0, xs, ys))
            sl = (ys[min(i + 1, len(xs) - 1)] - ys[max(i - 1, 0)]) / (xs[min(i + 1, len(xs) - 1)] - xs[max(i - 1, 0)]); nrm = np.array([-sl, 1.0]); nrm /= np.linalg.norm(nrm)
            v = math.sqrt(2 * g * (Hx(x0) - yf)); vin = np.array([0, -v]); vo = vin - 2 * np.dot(vin, nrm) * nrm; t1 = math.sqrt(2 * (Hx(x0) - yf) / g); tT = (Tg[0] - x0) / vo[0]
            rank = j / max(1, m - 1)
            td = t0 + WV * (rank if w % 2 == 0 else 1 - rank) * min(1, (m - 1) / 4)   # wave：端から順に落とす（波のズレ。回ごとに向きを入れかえる）
            b = dict(x0=x0, yf=yf, vo=vo, t0=td, t1=t1, tT=tT, col=hsv(((j + .5) / m * .85 + .07 * w + HUE0) % 1), last=None, m=m)
            balls.append(b); scored_t.append(td + t1 + tT)
            g_ = .9 / math.sqrt(m)
            sim.note(td + t1, PENTA[int(rank * 15 + .5)], g_, .5 + .3 * x0 / xb, 4 + 3 * math.sqrt(m / 5))
            sim.note(td + t1 + tT, PENTA[min(15, 10 + int(rank * 5 + .5))], .7 * g_, .3, 5 + 3 * math.sqrt(m / 5), "bell")
        if sp.get("finale", True) and m > 1:   # 最後の1個が入ったら「コロン」：今の和音の根音を高めのベルで鳴らす（和音つき）
            import harmony as _hm; tl = max(scored_t[-m:]) + .12; sim.note(tl, 72 + _hm.pcs(tl)[0], .55, .5, 6, "bell")
        t0 += gap
    total = max(scored_t) + tail; scored_t.sort(); tot = sum(vols)
    def pos(b, t):
        u = t - b["t0"]
        if u < 0: return None
        if u < b["t1"]: return (b["x0"], Hx(b["x0"]) - g * u * u / 2)
        u -= b["t1"]; x = b["x0"] + b["vo"][0] * u; y = b["yf"] + b["vo"][1] * u - g * u * u / 2
        if u > b["tT"]: x = Tg[0] + (x - Tg[0]) * .15   # かごの中はまっすぐ下へ
        return (x, y) if (u <= b["tT"] or y > Tg[1] - 1.1) else None   # 消すのは、かごに入って下に抜けたときだけ（跳ねた直後は必ず見せる）
    for fi in range(int(total * FPS)):
        t = fi / FPS; dots, segs = [], []
        for b in balls:
            p = pos(b, t)
            if p is None: continue
            if b["last"] is not None and t - b["t0"] < b["t1"] + b["tT"]: segs.append((b["last"], p, dim(b["col"], .28)))
            b["last"] = p; dots.append((p, b["col"], 5))
        sim.commit(segs, width=1.3)
        n_in = int(np.searchsorted(scored_t, t, side="right")); n_out = sum(1 for b in balls if b["t0"] <= t)
        fl = []   # 床で跳ねた瞬間に、当たった点が小さく光る（跳ねた感じを見せる）
        for b in balls:
            e = t - b["t0"] - b["t1"]
            if 0 <= e < .28: fl.append(((b["x0"], b["yf"]), 8 + e * 60, dim(b["col"], 1 - e / .28), 2))
        sim.frame(t, (), dots, (sp.get("count_fmt", "入った {a} / {b}　").format(a=n_in, b=n_out), ""), fl)
    sim.finish(total)


def chain(sp):
    """同じ重さの球が、止まっている2球に±45度で同時に当たると、当てた球はぴたりと止まり、2球が速さ 1/√2 で90度に開いて飛ぶ
    （運動量とエネルギーの保存）。飛んだ球がまた次の2球に当たる…をくり返す。道のりも 1/√2 ずつ短くするので、1世代の時間は同じ"""
    G, Tg, L0 = sp.get("gens", 9), sp.get("T", 2.4), sp.get("L0", .62); intro, tail = .5, sp.get("tail", 2.0); r = 1 / math.sqrt(2)
    sim = Sim(sp, (-1.15, -.05, 1.15, 2.05)); sim.title()
    segs = []   # (世代, 始点, 終点, 色)
    def grow(p, d, k, hue):
        L = L0 * r ** k; q = (p[0] + d[0] * L, p[1] + d[1] * L); segs.append((k, p, q, hue))
        if k + 1 < G:
            for sgn in (1, -1):
                c, s_ = math.cos(sgn * math.pi / 4), math.sin(sgn * math.pi / 4); nd = (d[0] * c - d[1] * s_, d[0] * s_ + d[1] * c)
                grow(q, nd, k + 1, (hue + sgn * .5 ** (k + 2)) % 1)
    grow((0, 0), (0, 1), 0, .55)
    byk = [[sg for sg in segs if sg[0] == k] for k in range(G)]
    for k in range(G):   # ぶつかるたびに1音（世代が進むと高く、同時に鳴る数が多いほど1つは小さく）
        if k == 0: continue
        n = len(byk[k - 1])
        for sg in byk[k - 1]: sim.note(intro + k * Tg, PENTA[min(15, 3 + k)], .9 / math.sqrt(n), .5 + .35 * sg[2][0], 4 + 3 * math.sqrt(n / 5))
    total = intro + G * Tg + tail; done = set(); rb = sp.get("ball", 4.5)
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = (t - intro) / Tg; kc = int(math.floor(u)) if u >= 0 else -1; f = u - kc
        add = []
        for k in range(min(kc, G)):
            if k not in done: add += [(sg[1], sg[2], dim(hsv(sg[3], .75, 1), .8)) for sg in byk[k]]; done.add(k)
        sim.commit(add, width=max(1.6, 3.0 * r ** (len(done) / 2)))
        live, dots = [], []
        if 0 <= kc < G:
            for sg in byk[kc]:
                p = lerp(sg[1], sg[2], f); live.append((sg[1], p, dim(hsv(sg[3], .75, 1), .8), 2)); dots.append((p, hsv(sg[3], .7, 1), rb))
                # これから当たる2球（止まっている）
                if kc + 1 < G:
                    for sg2 in byk[kc + 1]:
                        pass
            if kc + 1 < G:
                for sg2 in byk[kc + 1]: dots.append((sg2[1], (200, 205, 220), rb * .8))
        elif u < 0: dots = [((0, 0), hsv(.55, .7, 1), rb)] + [(sg[1], (200, 205, 220), rb * .8) for sg in byk[0][:0]]
        else:
            for sg in byk[G - 1]: dots.append((sg[2], hsv(sg[3], .7, 1), rb))
        n_hit = sum(len(byk[k]) for k in range(min(max(kc, 0), G)))
        sim.frame(t, live, dots, (sp.get("count_label", "動いている球："), f"{len(byk[min(max(kc, 0), G - 1)]) if kc < G else len(byk[G - 1])}"))
    sim.finish(total)


def tusi(sp):
    """半径1の円の内側を、半径1/2の円がすべらずに転がる（トゥースィーの対円）。小さい円のふちの点は、どれも大きい円の直径の上を
    まっすぐ往復する。ふちの位相 φ の点の位置 = cos(θ−φ/2)·(cos(φ/2), sin(φ/2))（θ は小さい円の中心が回った角度）。
    ボールは半周（θ が π 進む）ごとに増える。どのボールも半周に1回、大きい円のふちに届く → そのとき1音"""
    M = sp.get("M", 32); ns = sp.get("ns", [1, 2, 3, 4, 6, 8, 12, 16, 24, 32]); Th = sp.get("half", 2.3); intro, tail = .3, sp.get("tail", 2.6)
    order = sorted(range(M), key=lambda i: int(format(i, f"0{M.bit_length() - 1}b")[::-1], 2))   # 均等に埋まる順（ビット反転）
    sim = Sim(sp, (-1.1, -1.1, 1.1, 1.1)); sim.neon([(math.cos(a), math.sin(a)) for a in np.linspace(0, 2 * np.pi, 241)], closed=True, width=6); sim.title()
    T = Th * len(ns); W_ = np.pi / Th   # θ の速さ
    th = lambda t: W_ * max(0, t - intro) + np.pi / 2 * 0
    spawn = {}
    for r, n in enumerate(ns):
        for i in order[:n]: spawn.setdefault(i, intro + r * Th)
    col = {i: hsv(i / M, .7, 1) for i in range(M)}
    def pos(i, t): a = np.pi * i / M; s = math.cos(th(t) - a); return (s * math.cos(a), s * math.sin(a)), s
    for i, t0 in spawn.items():   # ふちに届く時刻 θ = a + kπ
        a = np.pi * i / M; k = math.ceil((W_ * (t0 - intro) - a) / np.pi - 1e-9)
        while True:
            tt = intro + (a + k * np.pi) / W_
            if tt > intro + T: break
            if tt >= t0: x = math.cos(a) * (1 if k % 2 == 0 else -1); sim.note(tt, PENTA[(i * 5) % 16], .4, .5 + .4 * x, 6.0)
            k += 1
    sim.chord(intro + T, [60, 67, 72, 76]); total = intro + T + tail; cov = {}
    for fi in range(int(total * FPS)):
        t = min(fi / FPS, intro + T); segs = []; balls = []; fl = []
        for i, t0 in spawn.items():
            if fi / FPS < t0: continue
            (p, s) = pos(i, t); a = np.pi * i / M; d = (math.cos(a), math.sin(a))
            if i not in cov: cov[i] = [s, s]; fl.append((p, 16, col[i], 2))
            lo, hi = cov[i]
            if s > hi: segs.append(((d[0] * hi, d[1] * hi), p, dim(col[i], .75))); cov[i][1] = s
            if s < lo: segs.append(((d[0] * lo, d[1] * lo), p, dim(col[i], .75))); cov[i][0] = s
            balls.append((p, (255, 255, 255), 7))
        sim.commit(segs, width=2.6)
        c = (.5 * math.cos(th(t)), .5 * math.sin(th(t)))
        live = [((c[0] + .5 * math.cos(b0), c[1] + .5 * math.sin(b0)), (c[0] + .5 * math.cos(b1), c[1] + .5 * math.sin(b1)), (90, 120, 160), 2)
                for b0, b1 in zip(np.linspace(0, 2 * np.pi, 73)[:-1], np.linspace(0, 2 * np.pi, 73)[1:])]
        n = sum(1 for t0 in spawn.values() if fi / FPS >= t0)
        sim.frame(fi / FPS, live, balls, (sp.get("count_label", "点の数 "), str(n)), fl)
    sim.finish(total)


def throw(sp):
    """同じ高さから、横の速さだけ変えて投げる（0 はただ落とす）。縦の動きは横の速さと関係ないので、全部が同時に床に着き、
    完全に弾んで同時に同じ高さまで戻る。左右の壁でも完全に弾む。ボールは頂点に戻るたびに増える。床に着くたび・壁に当たるたびに1音"""
    Hh, Tb = sp.get("H", 1.5), sp.get("bounce", 2.2); g = 8 * Hh / Tb ** 2; ns = sp.get("ns", [1, 2, 3, 5, 7, 10, 14, 20, 28]); intro, tail = .3, sp.get("tail", 2.6)
    X = 1.0; sim = Sim(sp, (-1.05, -.1, 1.05, Hh + .15)); sim.neon([(-X, Hh + .1), (-X, 0), (X, 0), (X, Hh + .1)], width=6); sim.title()
    vs = [0.0] + [s * (.22 + .19 * k) for k in range(40) for s in (1, -1)]   # 0, ±… の順
    T = Tb * len(ns); spawn = {}
    for r, n in enumerate(ns):
        for i in range(n): spawn.setdefault(i, intro + r * Tb)
    def y_of(t):   # 頂点 (t=0) から始まる弾み。周期 Tb
        m = t % Tb; return Hh - .5 * g * min(m, Tb - m) ** 2
    def x_of(i, t):
        s = vs[i] * t; m = (s + X) % (4 * X); return (m if m <= 2 * X else 4 * X - m) - X
    col = {i: hsv(i * .137 % 1, .7, 1) for i in range(len(vs))}
    for i, t0 in spawn.items():
        k = 0
        while True:   # 床：頂点から Tb/2 後、以後 Tb ごと
            tt = t0 + Tb / 2 + k * Tb
            if tt > intro + T: break
            x = x_of(i, tt - t0); sim.note(tt, PENTA[int((x + 1) / 2 * 15 + .5)], .32, .5 + .4 * x, 5.0); k += 1
        if vs[i]:
            w = 2 * X / abs(vs[i]); tt = t0 + X / abs(vs[i])   # 壁：最初は X、以後 2X ごと
            while tt <= intro + T: sim.note(tt, PENTA[13 if (x_of(i, tt - t0 - 1e-4) > 0) else 10], .2, .5 + .45 * (1 if x_of(i, tt - t0 - 1e-4) > 0 else -1), 7.0); tt += w
    sim.chord(intro + T, [60, 67, 72, 76]); total = intro + T + tail; last = {}
    for fi in range(int(total * FPS)):
        t = min(fi / FPS, intro + T); segs = []; balls = []; fl = []
        for i, t0 in spawn.items():
            if fi / FPS < t0: continue
            p = (x_of(i, t - t0), y_of(t - t0))
            if i in last:
                q = last[i]
                if abs(p[0] - q[0]) < .5: segs.append((q, p, dim(col[i], .42)))
            else: fl.append((p, 16, col[i], 2))
            last[i] = p; balls.append((p, (255, 255, 255), 7))
        sim.commit(segs, width=2.4)
        n = sum(1 for t0 in spawn.values() if fi / FPS >= t0)
        sim.frame(fi / FPS, (), balls, (sp.get("count_label", "ボールの数 "), str(n)), fl)
    sim.finish(total)


def star(sp):
    """円の中を、壁で完全に弾みながら進むボール。弾むたびに円周上を 360°×k/n ずつ進むので、n 回でちょうど元の点に戻り、
    星形 {n/k} を描く。ボールは1周（n 回弾む）ごとに増え、出発点を少しずつずらす。弾むたびに1音（当たった場所で高さが変わる）"""
    n, k = sp.get("n", 7), sp.get("k", 3); tc = sp.get("tc", .45); ms = sp.get("ms", [1, 2, 3, 5, 8]); M = ms[-1]; intro, tail = .3, sp.get("tail", 2.6)
    offs = sorted(range(M), key=lambda i: int(format(i, f"0{max(1, (M - 1).bit_length())}b")[::-1], 2))
    sim = Sim(sp, (-1.1, -1.1, 1.1, 1.1)); sim.neon([(math.cos(a), math.sin(a)) for a in np.linspace(0, 2 * np.pi, 241)], closed=True, width=6); sim.title()
    lap = n * tc; T = lap * len(ms); spawn = {}
    for r, m in enumerate(ms):
        for j in offs[:m]: spawn.setdefault(j, intro + r * lap)
    col = {j: hsv(j / M, .7, 1) for j in range(M)}
    sprd = sp.get("spread", .3)
    A = lambda j, q: np.pi / 2 + 2 * np.pi * (j / M) * sprd / n + 2 * np.pi * k * q / n
    V = lambda j, q: (math.cos(A(j, q)), math.sin(A(j, q)))
    def pos(j, s):   # s: 出発からの時間
        q = int(s // tc); u = (s % tc) / tc; return lerp(V(j, q), V(j, q + 1), u), q
    for j, t0 in spawn.items():
        q = 1
        while t0 + q * tc <= intro + T:
            p = V(j, q); ang = (A(j, q) % (2 * np.pi)) / (2 * np.pi); sim.note(t0 + q * tc, PENTA[int(ang * 15 + .5)], .4, .5 + .4 * p[0], 5.0); q += 1
    sim.chord(intro + T, [60, 67, 72, 76]); total = intro + T + tail; last = {}
    for fi in range(int(total * FPS)):
        t = min(fi / FPS, intro + T); segs = []; balls = []; fl = []
        for j, t0 in spawn.items():
            if fi / FPS < t0: continue
            p, q = pos(j, t - t0)
            if j in last:
                lp, lq = last[j]
                if lq != q: segs.append((lp, V(j, q), dim(col[j], .8))); lp = V(j, q); fl.append((lp, 14, col[j], 2))
                segs.append((lp, p, dim(col[j], .8)))
            else: fl.append((p, 16, col[j], 2))
            last[j] = (p, q); balls.append((p, (255, 255, 255), 7))
        sim.commit(segs, width=2.6)
        c = sum(1 for t0 in spawn.values() if fi / FPS >= t0)
        sim.frame(fi / FPS, (), balls, (sp.get("count_label", "ボールの数 "), str(c)), fl)
    sim.finish(total)


def spiropens(sp):
    """スピログラフ。半径 R の輪の内側を、半径 r の歯車がすべらずに回る。歯車の中心から d の穴にペン。
    位置 = ((R−r)cos t + d cos(kt+φ), (R−r)sin t − d sin(kt+φ))、k=(R−r)/r。t が 2π×r/gcd(R,r) 進むと閉じ、花びらは R/gcd 枚。
    ペンは歯車が1周するたびに増え、穴の向き φ を少しずつずらす。どのペンも花びらの先（いちばん外）に来るたびに1音"""
    Ri, ri = sp.get("R", 96), sp.get("r", 60); g_ = math.gcd(Ri, ri); laps = ri // g_; pet = Ri // g_
    out = sp.get("outer", False); R, r = 1.0, ri / Ri; d = sp.get("d", .8) * r; C = R + r if out else R - r; kk = C / r; sc = 1 / (C + d) if out else 1.0; Tl = sp.get("lap", 2.2); ms = sp.get("ms", [1, 2, 3, 5, 8]); M = ms[-1]; intro, tail = .3, sp.get("tail", 2.6)
    sprd = sp.get("spread", .5); offs = sorted(range(M), key=lambda i: int(format(i, f"0{max(1, (M - 1).bit_length())}b")[::-1], 2))
    sim = Sim(sp, (-1.1, -1.1, 1.1, 1.1)); sim.neon([(sc * math.cos(a), sc * math.sin(a)) for a in np.linspace(0, 2 * np.pi, 241)], closed=True, width=6); sim.title()
    W_ = 2 * np.pi / Tl; spawn = {}
    for j, m in enumerate(ms):
        for i in offs[:m]: spawn.setdefault(i, intro + j * Tl)
    T = (len(ms) - 1 + laps) * Tl; h0, hw = sp.get("hue", .55), sp.get("hue_w", .45); col = {i: hsv((h0 + hw * i / M) % 1, .65, 1) for i in range(M)}
    ph = lambda i: 2 * np.pi * (i / M) * sprd / pet
    def P(i, t):
        u = W_ * t
        if out: return (sc * (C * math.cos(u) - d * math.cos(kk * u + ph(i))), sc * (C * math.sin(u) - d * math.sin(kk * u + ph(i))))
        return (C * math.cos(u) + d * math.cos(kk * u + ph(i)), C * math.sin(u) - d * math.sin(kk * u + ph(i)))
    end = {i: t0 + laps * Tl for i, t0 in spawn.items()}
    for i, t0 in spawn.items():   # 花びらの先：cos((1+k)u+φ)=1 → |p| が最大
        n = 0
        while True:
            u = ((2 * n + 1) * np.pi - ph(i)) / (kk - 1) if out else (2 * np.pi * n - ph(i)) / (1 + kk); n += 1
            if u < 1e-9: continue
            tt = t0 + u / W_
            if tt > end[i] + 1e-6: break
            p = P(i, u / W_); a = (math.atan2(p[1], p[0]) % (2 * np.pi)) / (2 * np.pi); sim.note(tt, PENTA[int(a * 15 + .5)], .36, .5 + .4 * p[0], 5.0)
    sim.chord(intro + T, [60, 67, 72, 76]); total = intro + T + tail; last = {}
    for fi in range(int(total * FPS)):
        tg = fi / FPS; segs = []; balls = []
        for i, t0 in spawn.items():
            if tg < t0: continue
            te = min(tg, end[i]) - t0; a0 = last.get(i, 0.0)
            if te > a0:
                nstep = max(1, int((te - a0) * 60)); us = np.linspace(a0, te, nstep + 1)
                for x0, x1 in zip(us[:-1], us[1:]): segs.append((P(i, x0), P(i, x1), dim(col[i], .7)))
                last[i] = te
            if tg <= end[i]: balls.append((P(i, te), (255, 255, 255), 6))
        sim.commit(segs, width=2.0)
        live = []
        if tg <= intro + T:
            uu = W_ * max(0, tg - intro); c = (sc * C * math.cos(uu), sc * C * math.sin(uu)); rr = sc * r
            cs = np.linspace(0, 2 * np.pi, 61); live = [((c[0] + rr * math.cos(b0), c[1] + rr * math.sin(b0)), (c[0] + rr * math.cos(b1), c[1] + rr * math.sin(b1)), (70, 95, 130), 2) for b0, b1 in zip(cs[:-1], cs[1:])]
        n = sum(1 for t0 in spawn.values() if tg >= t0)
        sim.frame(tg, live, balls, (sp.get("count_label", "ペンの数 "), str(n)))
    sim.finish(total)


def maurer(sp):
    """モーラーのバラ。バラ曲線 r=sin(nθ) の上の点を、角度 d° ずつ進めて順に直線で結ぶ。
    点の数は 360/gcd(360,d) 個で、そこで最初の点に戻って閉じる。ボールが1本ずつ線を引き、点に着くたびに1音（中心から遠いほど高い）"""
    n, dd = sp.get("n", 6), sp.get("d", 58); K = 360 // math.gcd(360, dd); ts = sp.get("seg", 20.0 / K); intro, tail = .3, sp.get("tail", 2.8)
    sim = Sim(sp, (-1.1, -1.1, 1.1, 1.1)); sim.title()
    rose = lambda th: (math.sin(n * th) * math.cos(th), math.sin(n * th) * math.sin(th))
    sim.thin([rose(t) for t in np.linspace(0, 2 * np.pi, 1441)], color=(70, 40, 90), width=2)
    pts = [rose(math.radians(k * dd)) for k in range(K + 1)]; T = K * ts; h0, hw = sp.get("hue", .5), sp.get("hue_w", .5)
    for k in range(sp.get("note_every", 2), K + 1, sp.get("note_every", 2)):   # 線が多いので2本ごとに1音（金星と同じ扱い）
        p = pts[k]; rad = math.hypot(*p); sim.note(intro + k * ts, PENTA[int(rad * 15 + .5)], .3, .5 + .4 * p[0], 6.5)
    sim.chord(intro + T, [60, 67, 72, 76]); total = intro + T + tail; done = 0
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = min(K, max(0, t - intro) / ts); k1 = int(u); segs = []
        while done < k1: segs.append((pts[done], pts[done + 1], hsv((h0 + hw * done / K) % 1, .7, sp.get("v", .85)))); done += 1
        sim.commit(segs, width=1.8); live = []; b = pts[min(k1, K)]
        if k1 < K: f = u - k1; b = lerp(pts[k1], pts[k1 + 1], f); live = [(pts[k1], b, hsv((h0 + hw * k1 / K) % 1, .7, .85), 1.8)]
        sim.frame(t, live, [(b, (255, 255, 255), 7)], (sp.get("count_label", "線の数 "), str(min(K, k1))))
    sim.finish(total)


def harmono(sp):
    """ハーモノグラフ。横と縦に、少しずつ揺れが小さくなる振り子をつなぎ、ペンを動かす。
    x=e^(−au)(A sin(2π f1 u)+B sin(2π f2 u+p1))、y=e^(−au)(A sin(2π f3 u+p2)+B sin(2π f4 u))。周期が少しずれているので、形がゆっくり回りながら内側へ巻いていく。
    横の振れがいちばん外で折り返すたびに1音（揺れが小さくなるほど音も小さく）"""
    f1, f2, f3, f4 = sp.get("f", [2.0, 3.0, 2.01, 3.005]); cyc = sp.get("cycles", 26); a = sp.get("damp", 1.5); A, B = sp.get("amp", [.6, .4]); p1, p2 = sp.get("ph", [1.0, .5])
    T = sp.get("T", 24.0); intro, tail = .3, sp.get("tail", 2.6); h0, hw = sp.get("hue", .5), sp.get("hue_w", .6)
    sim = Sim(sp, (-1.1, -1.1, 1.1, 1.1)); sim.title()
    def P(u):
        w = 2 * np.pi * cyc * u; e = math.exp(-a * u); return (e * (A * math.sin(f1 * w) + B * math.sin(f2 * w + p1)), e * (A * math.sin(f3 * w + p2) + B * math.sin(f4 * w)))
    steps = 9000; prev = P(0); pp = prev
    for k in range(1, steps + 1):
        u = k / steps; p = P(u)
        if k >= 2 and (p[0] - prev[0]) * (prev[0] - pp[0]) < 0 and abs(prev[0]) > .04:
            sim.note(intro + u * T, PENTA[int((prev[1] + 1) / 2 * 15 + .5)], .42 * math.exp(-a * u * .6), .5 + .4 * prev[0], 5.5)
        pp = prev; prev = p
    sim.chord(intro + T, [60, 67, 72, 76], gain=.25); total = intro + T + tail; done = 0
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = min(1, max(0, t - intro) / T); k1 = int(u * steps); segs = []
        while done < k1: segs.append((P(done / steps), P((done + 1) / steps), hsv((h0 + hw * done / steps) % 1, .7, .8))); done += 1
        sim.commit(segs, width=1.6)
        sim.frame(t, (), [(P(u), (255, 255, 255), 7)], (sp.get("count_label", ""), sp.get("time_fmt", "{:.1f}秒").format(max(0, t - intro))))
    sim.finish(total)


def piphase(sp):
    """ぶつかる箱で円周率（Galperin）を、速さの円で見せる。上：壁・軽い箱（1）・重い箱（M）。下：横＝√1·v（軽い箱）、縦＝√M·V（重い箱）の点。
    エネルギーが保たれるので点は円の上にあり、箱どうしの衝突は傾き一定の弦、壁は左右の反転。1回ごとに円を角度 2θ（θ=atan(1/√M)）ずつ進むので、
    半周を超えるまでの回数が π/θ ≒ 円周率の桁になる。段ごとに新しい円に描き、前の段の回数は下に残す"""
    stages = sp.get("stages", [[1, 1.6], [100, .8], [10000, .7]]); intro, tail = .3, sp.get("tail", 3.0); w1 = .34; XR = 4.6
    sim = Sim(sp, (-.3, -3.6, 5.3, 3.0)); ly = 1.75; sim.neon([(0, ly), (XR, ly)], width=4); sim.neon([(0, ly), (0, ly + 1.1)], width=6)
    C, R = (2.5, -.95), 1.5; sim.thin([(C[0] + R * math.cos(a), C[1] + R * math.sin(a)) for a in np.linspace(0, 2 * np.pi, 241)], color=(70, 80, 110), width=2)
    sim.title(); runs, t0 = [], intro
    for si, (M, k) in enumerate(stages):
        a, b, v1, v2, t = .6, 1.7, 0.0, -1.0, 0.0; st = [(0.0, a, b, v1, v2)]; hits = []
        while True:
            tw = a / -v1 if v1 < -1e-15 else math.inf; tb = (b - a) / (v1 - v2) if v1 - v2 > 1e-15 else math.inf
            if not math.isfinite(min(tw, tb)): break
            dt = min(tw, tb); a += v1 * dt; b += v2 * dt; t += dt
            if tw < tb: a, v1 = 0.0, -v1; hits.append((t, "w"))
            else: a = b; v1, v2 = ((1 - M) * v1 + 2 * M * v2) / (1 + M), ((M - 1) * v2 + 2 * v1) / (1 + M); hits.append((t, "b"))
            st.append((t, a, b, v1, v2))
        dur = (t + 1.4) / k
        pts = [(C[0] + R * q[3], C[1] + R * math.sqrt(M) * q[4] / math.sqrt(M)) for q in st]   # 横 v1、縦 √M V2/√M（半径1に正規化）
        pts = [(C[0] + R * q[3] * 1.0, C[1] + R * q[4]) for q in st]
        # 正規化：E = v1² + M V2² = M（最初 V2=-1）→ (v1/√M, V2) が単位円
        pts = [(C[0] + R * q[3] / math.sqrt(M), C[1] + R * q[4]) for q in st]
        runs.append(dict(M=M, t0=t0, k=k, st=st, stt=np.array([q[0] for q in st]), hits=[(t0 + h / k, c) for h, c in hits], pts=pts, w2=.34 + .18 * math.log10(M), col=hsv(.08 + .14 * si)))
        prev = -1
        for h, c in hits:
            th = t0 + h / k; gap = th - prev; prev = th
            sim.note(th, 84 if c == "w" else 79, .5 * min(1, gap / .06) ** .5, .3 if c == "w" else .65, 14 if gap > .08 else 40)
        sim.chord(t0 + dur - .5, [60, 64, 67, 72] if si == len(stages) - 1 else [67, 72], gain=.25)
        t0 += dur
    total = t0 + tail; drawn = {}
    for fi in range(int(total * FPS)):
        t = fi / FPS; cur = max([i for i, r in enumerate(runs) if t >= r["t0"]] or [0]); run = runs[cur]
        if drawn.get("stage") != cur:   # 段が替わったら円の中を消す
            from PIL import Image as _I; sim.acc = _I.new("RGB", sim.acc.size); drawn = {"stage": cur, "n": 0}
        n = int(np.searchsorted([h for h, _ in run["hits"]], t, side="right")); segs = []
        while drawn["n"] < n:
            i = drawn["n"]; segs.append((run["pts"][i], run["pts"][i + 1], hsv(.55 + .45 * i / max(1, len(run["hits"])), .65, min(1, (30 / max(1, len(run["hits"]))) ** .6)))); drawn["n"] += 1
        sim.commit(segs, width=2.2 if len(run["hits"]) < 100 else 1.2)
        tau = max(0, (t - run["t0"])) * run["k"]; i = max(0, int(np.searchsorted(run["stt"], tau, side="right")) - 1)
        _, a, b, v1, v2 = run["st"][i]; dt = tau - run["st"][i][0]; a, b = a + v1 * dt, b + v2 * dt; P = run["pts"][min(i, len(run["pts"]) - 1)]
        def draw(d, run=run, a=a, b=b, n=n, cur=cur):
            for x0, w, col, lab in ((a, w1, (120, 220, 255), "1kg"), (b + w1, run["w2"], run["col"], f"{run['M']:,}kg")):
                if x0 > XR: continue
                X0, Y0 = sim.to((x0, ly + w)); X1, Y1 = sim.to((min(XR, x0 + w), ly)); d.rectangle([X0, Y0, X1, Y1 - 3 * S], fill=dim(col, .8), outline=col, width=2 * S)
                f = F(30 * S); tw_ = d.textlength(lab, font=f)
                if x0 + w <= XR: d.text(((X0 + X1) / 2 - tw_ / 2, Y0 - 44 * S), lab, font=f, fill=(215, 222, 235))
            f = F(34 * S); y = sim.to((0, -2.75))[1]
            for j in range(cur + 1):   # 段ごとの結果を下に並べる
                r = runs[j]; nn = len(r["hits"]) if j < cur else n; s_ = f"{r['M']:,}kg：{nn}回"; tw_ = d.textlength(s_, font=f)
                d.text((sim.to((2.5, 0))[0] - tw_ / 2, y + j * 46 * S), s_, font=f, fill=(255, 210, 70) if j == cur else (190, 196, 210), stroke_width=4 * S, stroke_fill=(0, 0, 0))
        sim.frame(t, (), [(P, (255, 255, 255), 7)], (sp.get("count_label", "ぶつかった回数 "), str(n)), draw=draw)
    sim.finish(total)


def pendswing(sp):
    """振り子の波を横から。ひとつの支点から長さのちがう振り子を吊るし、端で一列にそろえて放す。
    いちばん長い振り子が T 秒で L0 往復、短くなるごとに1往復ずつ多い（小さい振れ幅の近似）。T 秒でまた一列にそろう。
    振り子が端で折り返すたびに1音（はじく音）。上に「いちばん下の玉：◯往復のうち◯」"""
    N, L0, T = sp.get("n", 12), sp.get("laps0", 20), sp.get("T", 40.0); intro, tail = .6, sp.get("tail", 2.0)
    per = [T / (L0 + i) for i in range(N)]; Lmax = 1.55; Ls = [Lmax * (p_ / per[0]) ** 2 for p_ in per]
    th0 = math.radians(sp.get("amp", 38)); piv = (0.0, 1.05)
    sim = Sim(sp, (-1.05, -.75, 1.05, 1.12))
    for sg in (-1, 1):   # 振れる端を示す V 字（支点から）
        sim.neon([piv, (piv[0] + sg * 1.75 * math.sin(th0), piv[1] - 1.75 * math.cos(th0))], color=(150, 220, 255), glow=(30, 120, 220), width=3)
    sim.ring(piv, 6, (160, 200, 240), 3); sim.title()
    for i in range(N):
        for j in range(2 * (L0 + i) + 1):   # 両端で折り返すたびに
            tt = intro + j * per[i] / 2
            if tt <= intro + T + .01: sim.note(tt, PENTA[i % 16] + (0 if j % 2 == 0 else 0), .42, .5 + (.32 if j % 2 == 0 else -.32), 4.0, "pluck")
    cols = [hsv(.0 + .78 * i / (N - 1)) for i in range(N)]; total = intro + T + tail
    def pos(i, u):
        th = th0 * math.cos(2 * np.pi * u / per[i]); return (piv[0] + Ls[i] * math.sin(th), piv[1] - Ls[i] * math.cos(th))
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = min(max(0, t - intro), T); live, dots = [], []
        P = [pos(i, u) for i in range(N)]
        for i in range(N):
            for q in range(10):   # 残像
                a, b = pos(i, max(0, u - .03 * (q + 1))), pos(i, max(0, u - .03 * q))
                live.append((a, b, dim(cols[i], .55 * (1 - q / 10)), 9 - q * .6))
            dots.append((P[i], cols[i], 11 - 5 * i / (N - 1)))
        for a, b in zip(P, P[1:]): live.append((a, b, (70, 80, 110), 1.2))   # 玉どうしを細い線で
        ph = [2 * np.pi * u / per[i] for i in range(N)]; R = abs(sum(np.exp(1j * x) for x in ph)) / N
        R2 = abs(sum(np.exp(2j * x) for x in ph)) / N
        pat = "一列" if R > .97 else "ふたてに分かれた" if R2 > .97 else "波" if R > .55 else "ばらばら"
        k = (L0 + N - 1) * u / T - L0 * u / T   # いちばん短い振り子が、いちばん長い振り子より何往復先か
        sim.frame(t, live, dots, (f"いちばん下の玉：{L0 + N - 1}往復のうち ", f"{int(min(L0 + N - 1, (L0 + N - 1) * u / T))}"),
                  draw=lambda d, pat=pat: _tag(d, f"いまの形：{pat}"))
    sim.finish(total)


def _tag(d, s):
    """下の方に、いまの形の札（枠つき）"""
    from simkit import F, S, W, H
    f = F(44 * S); w = d.textlength(s, font=f); x, y = W * S / 2 - w / 2, H * S * .785
    d.rounded_rectangle([x - 34 * S, y - 14 * S, x + w + 34 * S, y + 62 * S], 38 * S, outline=(150, 170, 200), width=3 * S)
    d.text((x, y), s, font=f, fill=(225, 230, 240))


def golden(sp):
    """黄金比ループ：黄金長方形を正方形に切り続けた図と、その四分円をつないだ黄金らせん。
    らせんの中心へ向けて、1マスで φ 倍ずつ寄りながら90度回ると、もとの絵とぴったり重なる → 継ぎ目なしでどこまでも続く。
    小さな光の玉がらせんをたどり、新しいマスに入るたびに1音"""
    PHI = (1 + 5 ** .5) / 2; steps, per = sp.get("steps", 20), sp.get("per", 2.2); intro, tail = .6, 1.5
    total = intro + steps * per + tail
    # 正方形とらせんを、外側から内側へ（各マスは前の φ 分の1、90度ずつ回る）
    sqs, arcs = [], []; x0, y0, w, h = 0.0, 0.0, PHI, 1.0; d = 0
    for k in range(steps + 14):
        s_ = min(w, h)
        if d == 0: sq = (x0, y0, s_); c = (x0 + s_, y0); a0 = 180; x0 += s_; w -= s_
        elif d == 1: sq = (x0, y0 + h - s_, s_); c = (x0, y0 + h - s_); a0 = 90; h -= s_
        elif d == 2: sq = (x0 + w - s_, y0, s_); c = (x0 + w - s_, y0 + s_); a0 = 0; w -= s_
        else: sq = (x0, y0, s_); c = (x0 + s_, y0 + s_); a0 = 270; y0 += s_; h -= s_
        sqs.append(sq); arcs.append((c, s_, a0)); d = (d + 1) % 4
    # らせんの中心（極限点）
    cx = sum(0 for _ in [0]); cxy = (sqs[-1][0] + sqs[-1][2] / 2, sqs[-1][1] + sqs[-1][2] / 2)
    sim = Sim(sp, (-1.0, -1.0, 1.0, 1.0)); sim.title()
    cols = [hsv((.08 + .11 * k) % 1) for k in range(len(sqs))]
    for k in range(steps):
        sim.note(intro + k * per, PENTA[(k * 2) % 11 + 2], .5, .5, 3.0, "pluck")
        for q in range(1, 4): sim.note(intro + k * per + q * per / 4, PENTA[(k * 2 + [0, 2, 4, 1][q]) % 11 + 2], .22, .3 + .4 * (q % 2), 4.0, "pluck")
    def xf(p, z, rot):   # 中心へ寄せ、z 倍して rot 回す
        x, y = p[0] - cxy[0], p[1] - cxy[1]; c, s2 = math.cos(rot), math.sin(rot); return ((x * c - y * s2) * z, (x * s2 + y * c) * z)
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = max(0, min(steps, (t - intro) / per)); z = sp.get("zoom0", .7) * PHI ** u; rot = math.radians(90) * u * sp.get("turn", 1)
        live, dots = [], []
        kmin = max(0, int(u) - 2)
        for k in range(kmin, min(len(sqs), int(u) + 12)):
            X, Y, S_ = sqs[k]; pts = [xf(p, z, rot) for p in [(X, Y), (X + S_, Y), (X + S_, Y + S_), (X, Y + S_), (X, Y)]]
            if max(abs(c) for p in pts for c in p) > 6: continue
            g = max(.0, min(1, 1.6 - .12 * (k - u)))
            for a, b in zip(pts, pts[1:]): live.append((a, b, dim(cols[k], .22 * g), 12)); live.append((a, b, dim(cols[k], .8 * g), 3))
            (c, r, a0) = arcs[k]; A = [xf((c[0] + r * math.cos(math.radians(a0 - 90 * j / 16)), c[1] + r * math.sin(math.radians(a0 - 90 * j / 16))), z, rot) for j in range(17)]
            for a, b in zip(A, A[1:]): live.append((a, b, dim((255, 200, 90), .25 * g), 16))
            for a, b in zip(A, A[1:]): live.append((a, b, dim((255, 236, 170), g), 5))
        # 光の玉：いまのマスの四分円の上を進む
        k = int(u); f_ = u - k; (c, r, a0) = arcs[k]; ang = math.radians(a0 - 90 * f_)
        dots.append((xf((c[0] + r * math.cos(ang), c[1] + r * math.sin(ang)), z, rot), (255, 245, 210), 12))
        sim.frame(t, live, dots, ("拡大 ", f"{PHI ** u:,.0f}倍" if PHI ** u >= 10 else f"{PHI ** u:.1f}倍"))
    sim.finish(total)


def threebody(sp):
    """ピタゴラスの三体問題：質量3・4・5の星を、辺3・4・5の直角三角形の頂点に止めて置き、重力だけで動かす。
    近づいては離れをくり返し、最後に1つが飛ばされる（決まった初期値なのに先が読めない＝カオス）。
    近づいた瞬間（距離が最小）にガラスの音、数を数える。線は最近の軌跡を明るく、古い軌跡はうすく残す"""
    from scipy.integrate import solve_ivp
    m = np.array(sp.get("m", [3., 4., 5.])); x0 = np.array(sp.get("x0", [[1, 3], [-2, -1], [1, -1]]), float)
    T1, dur, intro, tail = sp.get("T", 66.0), sp.get("dur", 44.0), .8, sp.get("tail", 2.5)
    def f(t, y):
        p = y[:6].reshape(3, 2); a = np.zeros((3, 2))
        for i in range(3):
            for j in range(3):
                if i != j: r = p[j] - p[i]; a[i] += m[j] * r / np.linalg.norm(r) ** 3
        return np.concatenate([y[6:], a.ravel()])
    sol = solve_ivp(f, (0, T1), np.concatenate([x0.ravel(), np.zeros(6)]), rtol=1e-11, atol=1e-12, dense_output=True, method="DOP853")
    k = T1 / dur; total = intro + dur + tail
    P = lambda tt: sol.sol(min(T1, max(0, tt)))[:6].reshape(3, 2)
    sim = Sim(sp, tuple(sp.get("box", (-4.6, -4.2, 4.6, 5.2)))); sim.title()
    cols = [(255, 214, 90), (90, 170, 255), (255, 110, 80)]
    # 近づいた瞬間
    TT = np.linspace(0, T1, int(T1 * 400)); PP = sol.sol(TT)[:6].T.reshape(-1, 3, 2); calls = []
    for pi_, (i, j) in enumerate(((0, 1), (0, 2), (1, 2))):
        dd = np.linalg.norm(PP[:, i] - PP[:, j], axis=1); mn = np.where((dd[1:-1] < dd[:-2]) & (dd[1:-1] < dd[2:]) & (dd[1:-1] < sp.get("close", .45)))[0] + 1
        for q in mn: calls.append((TT[q], i, j, dd[q]))
    calls.sort()
    for n_, (tc, i, j, dd) in enumerate(calls):
        x = PP[int(tc * 400 / T1 * T1 / T1)][i][0] if False else P(tc)[i][0]
        sim.note(intro + tc / k, PENTA[(3 * i + 5 * j + n_ * 2) % 13 + 3], .55 + .3 * (1 - dd / .45), .5 + .08 * x, 3.2, "glass")
    com = lambda p: (p * m[:, None]).sum(0) / m.sum()
    ej = None
    for tt in np.linspace(0, T1, 2000):
        p = P(tt); r = np.linalg.norm(p - com(p), axis=1)
        if r.max() > 7: ej = tt; break
    trail = sp.get("trail", 3.0)   # 明るく見せる最近の軌跡（シミュレーション内の時間）
    last = 0.0
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = min(T1, max(0, (t - intro) * k))
        # 古い軌跡をうすく残す（u-trail までを確定）
        upto = max(0, u - trail)
        if upto > last:
            segs = []; ts_ = np.linspace(last, upto, max(2, int((upto - last) * 60)))
            for i in range(3):
                pts = [P(x)[i] for x in ts_]; segs += [(a, b, dim(cols[i], .22)) for a, b in zip(pts, pts[1:])]
            sim.commit(segs, width=2.2); last = upto
        live = []
        ts_ = np.linspace(max(0, u - trail), u, 90)
        for i in range(3):
            pts = [P(x)[i] for x in ts_]
            for q, (a, b) in enumerate(zip(pts, pts[1:])): live.append((a, b, dim(cols[i], .25 + .75 * q / len(pts)), 2.2 + 2.6 * q / len(pts)))
        p = P(u); balls = [(p[i], cols[i], 6 + 1.6 * m[i]) for i in range(3)]
        n_c = sum(1 for c in calls if c[0] <= u)
        def dr(d, done=ej is not None and u >= ej + 1.5):
            if done and sp.get("end_label", "1つ、飛ばされた"):
                from simkit import F, W as W_, S as S_, H as H_
                msg = sp.get("end_label", "1つ、飛ばされた"); fB = F(70 * S_); w = d.textlength(msg, font=fB)
                d.text((W_ * S_ / 2 - w / 2, H_ * S_ * .80), msg, font=fB, fill=(255, 255, 255), stroke_width=8 * S_, stroke_fill=(30, 60, 140))
        sim.frame(t, live, balls, (sp.get("count_label", "ニアミス："), (f"{n_c}" if sp.get("lang")=="en" or sp["id"].endswith("_en") else f"{n_c}回")), draw=dr)
    sim.finish(total)


def plotter(sp):
    """プリンター：印刷ヘッドが左右に往復して、1行ずつ絵を刷っていく。何の絵かは刷り終わるまでわからない。
    絵はマンデルブロ集合（z→z²+c をくり返して、外へ飛び出すまでの回数で色をつける）。行の端で折り返すたびにガラスの音。
    ヘッドは光る小さな台車、レールも軽く光る。刷ったばかりの行は少し明るく、すぐ落ち着く"""
    from simkit import S as S_, W as W_, H as H_
    from PIL import Image
    rows, dur, intro, tail = sp.get("rows", 96), sp.get("dur", 46.0), .8, sp.get("tail", 3.0)
    cx0, cy0, sc = sp.get("center", [-.6, 0.0]) + [sp.get("scale", 2.6)]
    x0p, x1p = int(.07 * W_ * S_), int(.93 * W_ * S_); wpx = x1p - x0p; hpx = int(wpx * sp.get("aspect", 1.25)); y0p = int(.245 * H_ * S_)
    cols_n = wpx // 3
    # 絵を作る（cols_n × rows）
    xs = cx0 + (np.arange(cols_n) / cols_n - .5) * sc; ys = cy0 + (np.arange(rows) / rows - .5) * sc * hpx / wpx
    C = xs[None, :] + 1j * ys[::-1, None]; Z = np.zeros_like(C); it = np.zeros(C.shape); alive = np.ones(C.shape, bool); MX = sp.get("iters", 90)
    for k in range(MX):
        Z[alive] = Z[alive] ** 2 + C[alive]; esc = alive & (np.abs(Z) > 2); it[esc] = k + 1 - np.log2(np.log2(np.abs(Z[esc]) + 1e-9) + 1e-9); alive &= ~esc
    h0 = sp.get("hue0", .62)
    img = np.zeros(C.shape + (3,), np.uint8)
    for r_ in range(rows):
        for c_ in range(cols_n):
            if alive[r_, c_]: img[r_, c_] = (8, 10, 22)
            else:
                v = it[r_, c_] / MX; img[r_, c_] = hsv((h0 + v * 3.0) % 1, .8, min(1, (v * 5) ** .8))
    rh = hpx / rows
    sim = Sim(sp, (-1, -1, 1, 1)); sim.title()
    per = dur / rows   # 1行の時間
    for r_ in range(rows):   # 折り返しの音：その行の明るさで高さを決める（毎回ずれる）
        br = img[r_].mean() / 255; sim.note(intro + (r_ + 1) * per, PENTA[int(br * 12 + r_ % 3 * 2) % 16] + 12, .5, .25 if r_ % 2 == 0 else .75, 3.0, "glass")
        if (~alive[r_]).any() and alive[r_].any():   # 集合のふちを通るときに小さな音
            edges = np.where(np.diff(alive[r_].astype(int)) != 0)[0]
            for e in edges[:3]:
                fx = (e / cols_n) if r_ % 2 == 0 else 1 - e / cols_n
                sim.note(intro + (r_ + fx) * per, PENTA[(r_ + int(e)) % 10 + 5] + 12, .22, .2 + .6 * (e / cols_n), 5.0, "glass")
    total = intro + dur + tail; printed = 0
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = max(0, (t - intro) / per); r_ = min(rows - 1, int(u)); fx = u - int(u) if u < rows else 1
        # 行を刷る：終わった行は acc へ確定
        while printed < min(rows, int(u)):
            row = Image.fromarray(img[printed][None, :, :]).resize((wpx, max(1, int(rh) + 1)), Image.NEAREST)
            sim.acc.paste(row, (x0p, y0p + int(printed * rh))); printed += 1
        live = []; ttl = None
        def dr(d, r_=r_, fx=fx, done=u >= rows):
            if not done:
                frac = fx if r_ % 2 == 0 else 1 - fx; cc = int(frac * cols_n)
                if cc > 0:
                    part = img[r_, :cc] if r_ % 2 == 0 else img[r_, cols_n - cc:]
                    row = Image.fromarray(np.clip(part.astype(int) * 1.35 + 20, 0, 255).astype(np.uint8)[None]).resize((max(1, int(cc * wpx / cols_n)), max(1, int(rh) + 1)), Image.NEAREST)
                    d._image.paste(row, (x0p if r_ % 2 == 0 else x1p - row.width, y0p + int(r_ * rh)))
                y = y0p + (r_ + .5) * rh; xh = x0p + frac * wpx
                d.line([x0p - 20 * S_, y, x1p + 20 * S_, y], fill=(70, 140, 190), width=3 * S_)          # レール
                d.rounded_rectangle([xh - 26 * S_, y - 14 * S_, xh + 26 * S_, y + 14 * S_], 6 * S_, fill=(30, 40, 60), outline=(150, 235, 255), width=3 * S_)  # ヘッド
                d.ellipse([xh - 5 * S_, y - 5 * S_, xh + 5 * S_, y + 5 * S_], fill=(255, 245, 210))
            d.rectangle([x0p - 4 * S_, y0p - 4 * S_, x1p + 4 * S_, y0p + hpx + 4 * S_], outline=(90, 170, 220), width=3 * S_)   # 紙のふち
        sim.frame(t, live, [], None, draw=dr)
    sim.finish(total)


def lissatable(sp):
    """リサージュの表：上の列の円（速さ1〜N倍）と、左の列の円（速さ1〜N倍）の組み合わせで、全部のマスの曲線を同時に描く。
    はじめは1周で全部が閉じた形になる（予想どおり）。そのあと1列だけ速さがほんの少しずれて形が回りはじめ（ズレ）、
    やがて全部の列と行がずれて、表全体が別の模様に変わっていく。円の点がてっぺんを通るたびにガラスの音（速さの比で重なったりずれたりする）"""
    N = sp.get("n", 7); dur, intro, tail = sp.get("dur", 50.0), .6, sp.get("tail", 2.0)
    TA, TB, TC = sp.get("t_draw", 12.0), sp.get("t_hold", 6.0), sp.get("t_one", 9.0)   # 描く・そのまま・1列だけずれる
    w0 = 2 * np.pi / TA; cell = 1.0; r = .38
    sim = Sim(sp, (-.5, -N - .5, N + .5, .5), area=(.04, .20, .96, .80)); sim.title()
    h0 = sp.get("hue0", 0.0); cols = [hsv((h0 + i / N * .85) % 1, .8, 1) for i in range(N)]
    one = sp.get("one", N // 2)   # 最初にずれる列（0始まり）
    def det(k, t, row=False):   # 速さのずれ（時刻とともに少しずつ）
        u = t - TA - TB
        if u <= 0: return 0.0
        d = 0.0
        if not row and k == one: d += .035 * min(1, u / 3)
        if u > TC: d += .012 * (k - (N - 1) / 2) / ((N - 1) / 2) * min(1, (u - TC) / 6) * (1.3 if row else 1)
        return d
    # 位相（ずれを時間で積分）を前もって数える
    total = intro + dur + tail; dt = 1 / (FPS * 4); TT = np.arange(0, total + 1, dt)
    def phase_arr(k, row):
        f = np.array([(k + 1) + det(k, max(0, t - intro), row) for t in TT]); ph = np.concatenate([[0], np.cumsum(f[:-1] * w0 * dt)]); ph[TT < intro] = 0; return ph
    PC = [phase_arr(k, False) for k in range(N)]; PR = [phase_arr(k, True) for k in range(N)]
    at = lambda arr, t: np.interp(t, TT, arr)
    # 音：上の円・左の円の点がてっぺん（位相が2πの倍数）を通るたび
    for k in range(N):
        for arr, oct_, pan in ((PC[k], 12, .2 + .6 * k / (N - 1)), (PR[k], 0, .5)):
            n_ = np.floor(arr / (2 * np.pi)); idx = np.where(np.diff(n_) > 0)[0]
            for i in idx: sim.note(TT[i], PENTA[(k * 2) % 15] + oct_, .32 if oct_ else .26, pan, 3.4, "glass")
    WIN = 2 * np.pi   # 曲線として見せる長さ（いちばん遅い円の1周ぶん）
    for fi in range(int(total * FPS)):
        t = fi / FPS; live, balls = [], []
        span = min(t - intro, TA) if t < intro + TA else TA   # 描いている途中は伸びていく
        ts = np.linspace(max(0, t - max(.01, span)), t, 90)
        for c in range(N):   # 上の円
            cx, cy = c + 1, 0; th = at(PC[c], t)
            pts = [(cx + r * np.cos(a - np.pi / 2), cy - r * np.sin(a - np.pi / 2)) for a in np.linspace(0, 2 * np.pi, 40)]
            live += [(a, b, dim(cols[c], .5), 2.0) for a, b in zip(pts, pts[1:])]
            balls.append(((cx + r * np.sin(th), cy + r * np.cos(th)), (255, 255, 255), 4))
        for rr in range(N):   # 左の円
            cx, cy = 0, -(rr + 1); th = at(PR[rr], t)
            pts = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 40)]
            live += [(a, b, dim(cols[rr], .5), 2.0) for a, b in zip(pts, pts[1:])]
            balls.append(((cx + r * np.sin(th), cy + r * np.cos(th)), (255, 255, 255), 4))
        if t > intro:
            for c in range(N):
                xs_ = r * np.sin(at(PC[c], ts))
                for rr in range(N):
                    ys_ = r * np.cos(at(PR[rr], ts)); cx, cy = c + 1, -(rr + 1)
                    mix = tuple(int((a + b) / 2) for a, b in zip(cols[c], cols[rr]))
                    P = list(zip(cx + xs_, cy + ys_)); m_ = len(P)
                    live += [(P[i], P[i + 1], dim(mix, .3 + .7 * i / m_), 1.4 + 1.2 * i / m_) for i in range(m_ - 1)]
                    balls.append((P[-1], mix, 2.6))
        sim.frame(t, live, balls)
    sim.finish(total)


def rhythm(sp):
    """リズム譜を、光る玉が跳ねながら読んでいく。玉が音符に着くたびに、その音符が光って1音。
    ページごとに速くなり、最後のページで玉が2つに分かれ、1拍ずらして同じ譜を追いかける（輪唱）。重なったりずれたりする"""
    from simkit import S as S_, W as W_, H as H_, F
    rng = np.random.default_rng(sp.get("seed", 3))
    PAT = [[1], [.5, .5], [.25, .25, .25, .25], [.75, .25], [.5, .25, .25], [.25, .25, .5], [.25, .5, .25]]
    pages = sp.get("pages", [[75, 1], [100, 1], [120, 2]])   # [テンポ, 玉の数]
    rows, beats = 4, 4
    sim = Sim(sp, (0, 0, 1, 1)); sim.title()
    x0, x1 = .08 * W_ * S_, .92 * W_ * S_; ytop = .32 * H_ * S_; dy = .125 * H_ * S_; Z = 1.55
    bw = (x1 - x0) / beats
    t = .8; layout = []   # (開始時刻, テンポ, 玉数, 音符の並び)
    for bpm, nb in pages:
        notes = []   # (行, 拍内の位置(拍), 長さ)
        for r_ in range(rows):
            for b in range(beats):
                pat = PAT[rng.integers(0, len(PAT))] if (r_ + b) else [1]
                pos = 0.0
                for dd in pat: notes.append((r_, b + pos, dd)); pos += dd
        spb = 60 / bpm; lead = 1.2
        layout.append((t, spb, nb, notes, lead)); t += lead + rows * beats * spb + (spb if nb > 1 else 0) + .8
    total = t + sp.get("tail", 1.5)
    hue0 = sp.get("hue0", .55)
    def xy(r_, pos): return (x0 + (pos + .18) * bw * .92, ytop + r_ * dy)
    # 音
    for pi_, (t0, spb, nb, notes, lead) in enumerate(layout):
        for k in range(nb):
            for i, (r_, pos, dd) in enumerate(notes):
                tt = t0 + lead + (r_ * beats + pos) * spb + k * spb
                sim.note(tt, PENTA[(i * 3 + r_ * 2 + k * 4) % 12 + 3] + (12 if k else 0), .42 if not k else .3, .35 + .3 * k, 3.6, "glass")
    if sp.get("beat", True):   # 裏でリズム：拍にやわらかい太鼓、8分の裏にごく小さいシャカ
        for t0, spb, nb, notes, lead in layout:
            nbt = rows * beats + (1 if nb > 1 else 0)
            for b in range(-2, nbt):
                tt = t0 + lead + b * spb
                sim.note(tt, 36, .22 if b % 2 == 0 else .16, .5, 6, "kick"); sim.note(tt + spb / 2, 96, .05, .62, 6, "hat")
    for fi in range(int(total * FPS)):
        tf = fi / FPS
        pi_ = max([i for i, L in enumerate(layout) if tf >= L[0] - .01] or [0]); t0, spb, nb, notes, lead = layout[pi_]
        hue = (hue0 + pi_ * .23) % 1
        def dr(d, t0=t0, spb=spb, nb=nb, notes=notes, lead=lead, hue=hue, pi_=pi_):
            fade = min(1, (tf - t0) / .4)
            for r_ in range(rows):   # 線
                y = ytop + r_ * dy + 14 * Z * S_; d.line([x0, y, x1, y], fill=dim((120, 150, 190), .6 * fade), width=2 * S_)
            # 拍ごとに旗をつなぐ
            groups = {}
            for i, n_ in enumerate(notes): groups.setdefault((n_[0], int(n_[1])), []).append(i)
            stem = 46 * Z * S_
            for (r_, b), idx in groups.items():
                xs_ = []
                for i in idx:
                    rr, pos, dd = notes[i]; x, y = xy(rr, pos)
                    th = t0 + lead + (rr * beats + pos) * spb; age = min([tf - (th + k * spb) for k in range(nb) if tf >= th + k * spb] or [9])
                    glow = max(0, 1 - age / .45)
                    col = tuple(min(255, int(220 * fade + 35 + glow * (c_ - 160))) for c_ in hsv(hue, .7, 1)) if glow > 0 else dim((230, 236, 245), fade)
                    if glow > 0:
                        rg = (14 + 20 * glow) * Z * S_; d.ellipse([x - rg, y - rg * .8, x + rg, y + rg * .8], fill=dim(hsv(hue, .8, 1), .35 * glow))
                    d.ellipse([x - 11 * Z * S_, y - 8 * Z * S_, x + 11 * Z * S_, y + 8 * Z * S_], fill=col)
                    d.line([x + 10 * Z * S_, y, x + 10 * Z * S_, y - stem], fill=col, width=int(3 * Z * S_)); xs_.append((x + 10 * Z * S_, dd))
                    if dd == .75: d.ellipse([x + 18 * Z * S_, y - 3 * Z * S_, x + 24 * Z * S_, y + 3 * Z * S_], fill=col)
                if len(idx) > 1:
                    yb = ytop + r_ * dy - stem; c0 = dim((230, 236, 245), fade)
                    d.line([xs_[0][0], yb, xs_[-1][0], yb], fill=c0, width=int(6 * Z * S_))
                    for (xa, da), (xb, db) in zip(xs_, xs_[1:]):
                        if da == .25 and db == .25: d.line([xa, yb + 11 * Z * S_, xb, yb + 11 * Z * S_], fill=c0, width=int(6 * Z * S_))
                        elif da == .25 or db == .25:
                            xx = xa if da == .25 else xb; d.line([xx - (0 if da == .25 else 16 * Z * S_), yb + 11 * Z * S_, xx + (16 * Z * S_ if da == .25 else 0), yb + 11 * Z * S_], fill=c0, width=int(6 * Z * S_))
            # テンポの表示（小さく）
            fS = F(36 * S_); lab = f"\u2669 = {int(round(60 / spb))}"; d.text((x0, ytop - 120 * S_), lab, font=fS, fill=dim((200, 210, 225), .8 * fade))
            # 玉：音符から音符へ放物線で跳ぶ
            seq = [(t0 + lead + (n_[0] * beats + n_[1]) * spb, xy(n_[0], n_[1])) for n_ in notes]
            for k in range(nb):
                tt = tf - k * spb
                if tt < seq[0][0] - .6: p0 = (seq[0][1][0] - bw * .5, seq[0][1][1] - 120 * S_); a = None
                j = max([i for i, (ts, _) in enumerate(seq) if ts <= tt] or [-1])
                if j < 0:
                    u = min(1, max(0, (tt - (seq[0][0] - .6)) / .6)); A = (seq[0][1][0] - bw * .6, seq[0][1][1] - 140 * S_); B = seq[0][1]
                elif j >= len(seq) - 1:
                    u = min(1, (tt - seq[-1][0]) / .6); A = seq[-1][1]; B = (A[0] + bw * .6, A[1] - 140 * S_)
                else:
                    (ta, A), (tb, B) = seq[j], seq[j + 1]; u = (tt - ta) / (tb - ta)
                h = (40 + 0.35 * abs(B[0] - A[0]) / S_ + (60 if abs(B[1] - A[1]) > 1 else 0)) * S_
                x = A[0] + (B[0] - A[0]) * u; y = A[1] + (B[1] - A[1]) * u - 4 * h * u * (1 - u) - 16 * Z * S_
                c = hsv((hue + .12 * k) % 1, .55, 1)
                for q_, rr_ in ((26, .25), (16, .45)):
                    d.ellipse([x - q_ * S_, y - q_ * S_, x + q_ * S_, y + q_ * S_], fill=dim(c, rr_))
                d.ellipse([x - 9 * S_, y - 9 * S_, x + 9 * S_, y + 9 * S_], fill=c); d.ellipse([x - 5 * S_, y - 6 * S_, x - 1 * S_, y - 2 * S_], fill=(255, 255, 255))
        sim.frame(tf, [], [], None, draw=dr)
    sim.finish(total)


def dragon(sp):
    """ドラゴン曲線：紙のテープを半分に折ることを n 回くり返し、折り目を全部直角に開くと出てくる形。
    開き方：いまの線を、終わりの点を中心に90度回したコピーを足す（これを1段ずつ）。回る途中もそのまま見せる。
    1段ごとに線の数は2倍。段が終わって回りきった瞬間に、中心の点が光って音が鳴る。画面はだんだん引いていく"""
    L, per, intro, tail = sp.get("levels", 12), sp.get("per", 3.2), .8, sp.get("tail", 3.0)
    P = [np.array([0., 0.]), np.array([1., 0.])]; levels = [np.array(P)]
    for k in range(L):
        Q = levels[-1]; piv = Q[-1]; R = Q[:-1][::-1] - piv; R = np.stack([-R[:, 1], R[:, 0]], 1) + piv   # 90度回す
        levels.append(np.concatenate([Q, R]))
    boxes = [(lv.min(0), lv.max(0)) for lv in levels]
    total = intro + L * per + tail
    sim = Sim(sp, (-1, -1, 1, 1)); sim.title()
    h0 = sp.get("hue0", .58)
    for k in range(L):   # 回りきった瞬間：中心が光る、和音のように2音
        tt = intro + (k + 1) * per; base = PENTA[(k * 2) % 10 + 2]
        sim.note(tt, base + 12, .45, .5, 3.0, "glass"); sim.note(tt + .06, base + 19, .25, .62, 3.6, "glass")
        for q in range(3): sim.note(tt - per * (.75 - .2 * q), PENTA[(k * 2 + q * 3) % 12 + 3] + 12, .14, .3 + .2 * q, 4.5, "glass")
    ease = lambda u: u * u * (3 - 2 * u)
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = max(0, (t - intro) / per); k = min(L - 1, int(u)); f = 1.0 if u >= L else ease(min(1, max(0, (u - k - .08) / .7)))
        Q = levels[k]; piv = Q[-1]; th = f * np.pi / 2
        R = Q[:-1][::-1] - piv; c_, s_ = np.cos(th), np.sin(th); R = np.stack([R[:, 0] * c_ - R[:, 1] * s_, R[:, 0] * s_ + R[:, 1] * c_], 1) + piv
        pts = np.concatenate([Q, R])
        # 画面合わせ：この段の始めと終わりの範囲を、回り具合で混ぜる
        (a0, b0), (a1, b1) = boxes[k], boxes[k + 1]; lo = a0 + (a1 - a0) * f; hi = b0 + (b1 - b0) * f
        cen = (lo + hi) / 2; sc = 1.8 / max(hi - lo).max() if np.ndim(hi - lo) else 1.8 / (hi - lo)
        sc = 1.8 / max(hi[0] - lo[0], (hi[1] - lo[1]) * .85, 1e-6)
        M = (pts - cen) * sc; n = len(M); wdt = max(1.2, 4.2 - .3 * k)
        live = []
        for i in range(n - 1):
            col = hsv((h0 + .55 * i / n) % 1, .55, 1)
            live.append((tuple(M[i]), tuple(M[i + 1]), dim(col, .95 if i >= len(Q) - 1 else .75), wdt))
        balls = []
        glow = max(0, 1 - (u - (k + 1)) / .5) if u >= k + .78 and u < L + .5 else 0
        pv = tuple((piv - cen) * sc)
        if 0 < f < 1 or glow > 0: balls.append((pv, (255, 245, 210), 5 + 10 * glow))
        sim.frame(t, live, balls, (sp["count_label"], f"{2 ** (k + 1):,}") if sp.get("count_label") else None)
    sim.finish(total)




def heliostat(sp):
    """たくさんの鏡（ヘリオスタット）。上からまっすぐ来た光を、地面の鏡で塔の上の1点へ。
    鏡までの距離がちがうので、着く時刻は自然にずれる。回ごとに鏡を増やす。塔の点は集まった光の量で明るくなる"""
    X, Y, v = sp.get("X", 6.0), sp.get("Y", 14.0), sp.get("v", 7.0); T = np.array([0.0, sp.get("tower", 6.5)])
    ms = sp.get("rounds", [2, 3, 5, 8, 12, 18]) + [sp.get("last", 26)]; intro, tail = .4, sp.get("tail", 1.6)
    sim = Sim(sp, (-X - .3, -.6, X + .3, Y + .15))
    sim.neon([(-X - .2, -.05), (X + .2, -.05)], width=4)
    sim.neon([(0, -.05), (0, T[1] - .35)], width=3, color=(120, 140, 180), glow=(40, 60, 110))
    sim.neon([(-X, Y), (X, Y)], width=4)
    sim.ring(tuple(T), 13); sim.title()
    maxL = Y + math.hypot(X, T[1]); P = maxL / v + .5
    rounds = []
    for r, m in enumerate(ms):
        t0 = intro + r * P; xs = []
        for j in range(m):   # 左右に m 枚ずつ、内側から外側へ（外ほど間をあける）
            u = (j + .5) / m; x = .8 + (X - .8) * u ** .85; xs += [x, -x]
        balls = []
        for i, x in enumerate(xs):
            M = np.array([x, 0.0]); d2 = T - M; L2 = float(np.hypot(*d2)); nrm = (np.array([0, 1.0]) + d2 / L2); nrm /= np.hypot(*nrm)
            tang = np.array([nrm[1], -nrm[0]]) * .28
            hue = ((abs(x) / X) * .55 + (0 if x > 0 else .5) + r * .07) % 1
            balls.append(dict(M=M, L1=Y, L2=L2, tang=tang, col=hsv(hue), x=x, done=0))
        n = len(balls); dec, g = 4 + 3 * math.sqrt(n / 5), .9 / math.sqrt(n)
        order = np.argsort(np.argsort([abs(b["x"]) for b in balls], kind="stable"))
        for i, b in enumerate(balls):
            frac = order[i] / max(1, n - 1)
            sim.note(t0 + b["L1"] / v, PENTA[int(frac * 9 + .5)], g, .5 + .35 * b["x"] / X, dec)
            sim.note(t0 + (b["L1"] + b["L2"]) / v, PENTA[int(6 + frac * 9 + .5)], g * .8, .5, dec * 1.2)
        rounds.append((t0, balls))
    total = intro + len(ms) * P + tail
    sim.notes = [nt for nt in sim.notes if nt[0] < total - .02]
    energy = 0.0
    for fi in range(int(total * FPS)):
        t = fi / FPS; r = min(len(rounds) - 1, max(0, int((t - intro) // P))); t0, balls = rounds[r]; s = max(0, t - t0) * v
        n = len(balls); lw = max(1.0, 2.0 * min(1, 10 / math.sqrt(n))); segs, live, dots, fl = [], [], [], []
        if r > 0:
            for b in rounds[r - 1][1]:
                if b["done"] < 2: segs.append(((b["x"], Y), tuple(b["M"]), dim(b["col"], .22))); segs.append((tuple(b["M"]), tuple(T), dim(b["col"], .22))); b["done"] = 2
        for b in balls:
            M = b["M"]; p0 = M - b["tang"]; p1 = M + b["tang"]; live.append((tuple(p0), tuple(p1), (200, 225, 255), 3))   # 鏡
            if s < b["L1"]: p = (b["x"], Y - s); live.append(((b["x"], Y), p, dim(b["col"], .7), lw)); dots.append((p, b["col"], 5 if n <= 32 else 4))
            elif s < b["L1"] + b["L2"]:
                if b["done"] < 1: segs.append(((b["x"], Y), tuple(M), dim(b["col"], .22))); b["done"] = 1
                k = (s - b["L1"]) / b["L2"]; p = tuple(M + (T - M) * k); live.append((tuple(M), p, dim(b["col"], .7), lw)); dots.append((p, b["col"], 5 if n <= 32 else 4))
                e = (s - b["L1"]) / v
                if e < .3: fl.append((tuple(M), 10 + e * 50, dim(b["col"], 1 - e / .3), 3))
            else:
                if b["done"] < 2:
                    if b["done"] < 1: segs.append(((b["x"], Y), tuple(M), dim(b["col"], .22)))
                    segs.append((tuple(M), tuple(T), dim(b["col"], .22))); b["done"] = 2; energy += 1
        sim.commit(segs, width=lw)
        energy *= .985
        glow = min(1, energy / 14)
        fl.append((tuple(T), 14 + 26 * glow, dim((255, 240, 190), .35 + .65 * glow), 4))
        sim.frame(t, live, dots, (sp.get("count_label", "鏡："), f"{n:,}"), fl)
    sim.finish(total)



def polyfocus(sp):
    """ポリリズム × 放物線（オーナー 11/22「ポリリズム意識して」）。ボールごとに速さが整数比（k0, k0+1, ...）。
    上の線→壁→焦点→壁→上の線の道の長さはどのボールも同じ 2(Y+f) なので、ボール k は P 秒のあいだに焦点を k 回通る。
    焦点を通るたびに自分の音が鳴り、拍の数がちがうリズムが重なる。P 秒後に全部が同時に上の線にそろう"""
    f, X, Y = 1.0, sp.get("X", 6.0), sp.get("Y", 14.0); P, k0, nb = sp.get("period", 24.0), sp.get("k0", 6), sp.get("balls", 8)
    Lp = 2 * (Y + f); a = 4 * f * f / X; intro, tail = .3, sp.get("tail", 2.2)
    sim = Sim(sp, (-X - .15, -.15, X + .15, Y + .15))
    sim.neon([(x, x * x / (4 * f)) for x in np.linspace(-X, X, 241)]); sim.neon([(-X, Y), (X, Y)], width=5)
    sim.ring((0, f), 13); sim.title()
    balls = []
    for i in range(nb):
        side = 1 if i % 2 == 0 else -1; x1 = side * a * (X / a) ** ((i + .5) / nb); y1 = x1 * x1 / (4 * f); x2 = -4 * f * f / x1; y2 = x2 * x2 / (4 * f)
        k = k0 + i; pts = [(x1, Y), (x1, y1), (0, f), (x2, y2), (x2, Y)]; cum = [0, Y - y1, Y + f, Y + 2 * f + y2, Lp]
        balls.append(dict(pts=pts, cum=cum, k=k, v=k * Lp / P, col=hsv(i / nb * .85), midi=PENTA[int(i / max(1, nb - 1) * 12 + .5)]))
    sim.commit([(b["pts"][j], b["pts"][j + 1], dim(b["col"], .16)) for b in balls for j in range(4)], width=1.4)
    for b in balls:   # 焦点を通るたびに自分の音、上の線に着くたびに1オクターブ下を小さく
        for j in range(b["k"]):
            sim.note(intro + (j + .5) * P / b["k"], b["midi"], .55, .5 + .3 * b["pts"][0][0] / X, 5)
            if j: sim.note(intro + j * P / b["k"], b["midi"] - 12, .22, .5, 4)
    sim.chord(intro, [60, 67, 72]); sim.chord(intro + P, [60, 64, 67, 72], gain=.5, dec=5)
    total = intro + P + tail
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = min(max(0, t - intro), P); live, dots, fl = [], [], []
        for b in balls:
            s = u * b["v"]; q = int(s // Lp); sc = s - q * Lp
            if q % 2: sc = Lp - sc
            if u >= P: sc = Lp if b["k"] % 2 else 0
            cum, pts = b["cum"], b["pts"]; j = min(3, int(np.searchsorted(cum, sc, side="right")) - 1); pnt = lerp(pts[j], pts[j + 1], (sc - cum[j]) / (cum[j + 1] - cum[j]))
            back = max(0, sc - 1.6) if q % 2 == 0 else min(Lp, sc + 1.6); jb = min(3, int(np.searchsorted(cum, back, side="right")) - 1); pb = lerp(pts[jb], pts[jb + 1], (back - cum[jb]) / (cum[jb + 1] - cum[jb]))
            if jb == j: live.append((pb, pnt, dim(b["col"], .8), 2.2))
            else:
                vtx = pts[max(j, jb)]; live.append((pb, vtx, dim(b["col"], .5), 2.2)); live.append((vtx, pnt, dim(b["col"], .8), 2.2))
            dots.append((pnt, b["col"], 7))
            e = ((u - .5 * P / b["k"]) % (P / b["k"])) if u > .5 * P / b["k"] else 9
            if e < .25 and u < P: fl.append(((0, f), 14 + e * 70, dim(b["col"], 1 - e / .25), 3))
        e = t - (intro + P)
        if 0 <= e < .5: fl.append(((0, Y), 20 + e * 220, dim((255, 245, 200), 1 - e / .5), 5))
        sim.frame(t, live, dots, (sp.get("count_label", "そろうまで "), f"{max(0, math.ceil(P - u))}"), fl)
    sim.finish(total)



def sortviz(sp):
    """並べ替えの見える化（ボール以外の題材。オーナー 11/22）。ばらばらの棒を、決まった手順だけで背の順にする。
    入れかえるたびに、動いた棒の高さの音（ドレミ）が鳴る。最後に左から右へ確かめの音が駆け上がる。仕込みなし：手順どおりに動くだけ"""
    import random
    N, algo, D = sp.get("n", 32), sp.get("algo", "insertion"), sp.get("dur", 22.0); rnd = random.Random(sp.get("seed", 3))
    arr = list(range(N)); rnd.shuffle(arr); a = arr[:]; ops = []
    def sw(i, j):
        if i != j: a[i], a[j] = a[j], a[i]; ops.append((i, j))
    if algo == "insertion":
        for i in range(1, N):
            j = i
            while j > 0 and a[j - 1] > a[j]: sw(j - 1, j); j -= 1
    elif algo == "quick":
        def qs(lo, hi):
            if lo >= hi: return
            pv = a[hi]; i = lo
            for j in range(lo, hi):
                if a[j] < pv: sw(i, j); i += 1
            sw(i, hi); qs(lo, i - 1); qs(i + 1, hi)
        qs(0, N - 1)
    elif algo == "shell":
        gap = N // 2
        while gap:
            for i in range(gap, N):
                j = i
                while j >= gap and a[j - gap] > a[j]: sw(j - gap, j); j -= gap
            gap //= 2
    intro, dt = .5, D / len(ops); tS = intro + D + .25; sweep = sp.get("sweep", 1.3); total = tS + sweep + 1.8
    sim = Sim(sp, (-.6, -.5, N + .6, N * 1.25))
    sim.neon([(-.3, -.25), (N + .3, -.25)], width=4); sim.title()
    pit = lambda h: PENTA[int(h / (N - 1) * 15 + .5)]
    cur = arr[:]
    for k, (i, j) in enumerate(ops):
        cur[i], cur[j] = cur[j], cur[i]
        sim.note(intro + (k + 1) * dt, pit(cur[i]), .5, .2 + .6 * i / N, 4)
    for i in range(N): sim.note(tS + sweep * i / N, pit(i), .42, .2 + .6 * i / N, 4)
    sim.chord(tS + sweep + .1, [60, 64, 67, 72], gain=.5, dec=5)
    cur = arr[:]; done = 0
    for fi in range(int(total * FPS)):
        t = fi / FPS; kf = (t - intro) / dt; k = min(len(ops), max(0, int(kf)))
        while done < k: i, j = ops[done]; cur[i], cur[j] = cur[j], cur[i]; done += 1
        xs = {i: float(i) for i in range(N)}; hot = {}
        if 0 < k <= len(ops) and kf - k < 1:   # 直前の入れかえは、すべるように動かす
            i, j = ops[k - 1]; u = min(1, (kf - k) * 1.6 + .2); u = u * u * (3 - 2 * u); xs[i] = j + (i - j) * u; xs[j] = i + (j - i) * u; hot[i] = hot[j] = 1 - (kf - k)
        sw_i = int((t - tS) / sweep * N) if t >= tS else -1
        def draw(d, cur=cur[:], xs=xs, hot=hot, sw_i=sw_i):
            for i in range(N):
                h = cur[i]; c = hsv(h / N * .85); x0, y0 = sim.to((xs[i] + .12, 0)); x1, y1 = sim.to((xs[i] + .88, (h + 1) * 1.2 * N / (N + 1)))
                g = hot.get(i, 0); lit = sw_i >= 0 and i <= sw_i
                if lit: g = max(g, max(0, 1 - (sw_i - i) / 6) * .9, .25)
                if g: gx = (x1 - x0) * .5; d.rounded_rectangle([x0 - gx, min(y0, y1) - gx, x1 + gx, max(y0, y1)], radius=gx * 1.5, fill=dim(c, .25 + .2 * g))
                cc = tuple(int(v + (255 - v) * .6 * g) for v in c) if g else dim(c, .86)
                yt, yb, bw = min(y0, y1), max(y0, y1), x1 - x0; rad = bw * .45
                d.rounded_rectangle([x0, yt, x1, yb], radius=rad, fill=dim(cc, .42))                                   # ふち（暗い）
                d.rounded_rectangle([x0 + bw * .10, yt + bw * .06, x1 - bw * .16, yb], radius=rad * .8, fill=dim(cc, .78))   # 胴
                d.rounded_rectangle([x0 + bw * .18, yt + bw * .14, x0 + bw * .62, yb], radius=rad * .6, fill=cc)             # 明るい面
                hl = tuple(int(v + (255 - v) * .75) for v in cc)
                d.rounded_rectangle([x0 + bw * .24, yt + bw * .30, x0 + bw * .36, yb - bw * .2], radius=bw * .06, fill=hl)   # 細い映りこみ
                d.ellipse([x0 + bw * .2, yt + bw * .1, x0 + bw * .56, yt + bw * .36], fill=hl)                               # 頭のつや
                rh = min((yb - yt) * .22, 60 * S)                                                                           # 床への映りこみ
                for q in range(4): d.rectangle([x0 + bw * .1, yb + 6 * S + rh * q / 4, x1 - bw * .16, yb + 6 * S + rh * (q + 1) / 4], fill=dim(cc, .16 * (1 - q / 4)))
        sim.frame(t, (), (), (sp.get("count_label", "入れかえ："), f"{k:,}"), (), draw)
    sim.finish(total)



def pixels(sp):
    """画素数を限界まで上げる（オーナー参考 11/22「こういうのもいいかも」：段階を上げていき「どれが好き？」と聞く型）。
    同じ絵（マンデルブロ集合。自分で計算）を 4×4 → 8×8 → … → 1024×1024 と細かくしていく。段が上がるたびにドレミが1音上がる"""
    from PIL import Image
    lv = sp.get("levels", [4, 8, 16, 32, 64, 128, 256, 512, 1024]); hold, intro, tail = sp.get("hold", 2.4), .2, 1.6
    cx, cy, R = sp.get("cx", -.6), sp.get("cy", 0.0), sp.get("r", 1.45); amber = os.environ.get("SIM_PALETTE") == "amber"
    def img(n):
        x = np.linspace(cx - R, cx + R, n, endpoint=False) + R / n; y = np.linspace(cy - R, cy + R, n, endpoint=False) + R / n
        c = x[None, :] + 1j * y[:, None]; z = np.zeros_like(c); k = np.zeros(c.shape); alive = np.ones(c.shape, bool)
        for i in range(sp.get("iter", 160)):
            z[alive] = z[alive] ** 2 + c[alive]; esc = alive & (np.abs(z) > 8); k[esc] = i + 1 - np.log2(np.log(np.abs(z[esc])) / math.log(8)); alive &= ~esc
        u = np.clip(k / 40, 0, 1) ** .6; inside = alive
        if amber: r_, g_, b_ = 20 + 235 * u, 8 + 170 * u ** 1.6, 14 + 60 * u ** 3
        else: r_, g_, b_ = 14 + 150 * u ** 2.2, 20 + 215 * u ** 1.1, 40 + 215 * u ** .7
        if sp.get("cyclic"):   # 深く拡大するとき：回数で色が巡る（虹のふち）
            w = k * sp.get("cyclic"); r_, g_, b_ = 135 + 120 * np.cos(w + 0.0), 125 + 120 * np.cos(w + 2.1), 140 + 115 * np.cos(w + 4.2)
        a = np.stack([r_, g_, b_], -1); a[inside] = (6, 8, 16)
        return Image.fromarray(a.clip(0, 255).astype(np.uint8))
    sim = Sim(sp, (0, 0, 1, 1)); sim.title()
    from simkit import W as W_, H as H_
    side = int(W_ * S * .92); x0 = (W_ * S - side) // 2; y0 = int(H_ * S * .30)
    ims = [img(n).resize((side, side), Image.NEAREST) for n in lv]
    for i, n in enumerate(lv): sim.note(intro + i * hold, PENTA[min(15, i * 2 if i < 8 else 15)], .7, .5, 9); sim.note(intro + i * hold + .18, PENTA[min(15, i * 2 if i < 8 else 15)] + 12, .25, .5, 7, "bell")
    pv = sp.get("preview", 1.1)   # 最初にいちばん細かい絵を見せてから、粗い段に落とす（オーナー 11/22）
    sim.notes = [(t + pv, *r) for t, *r in sim.notes]; sim.chord(.05, [72, 76, 79], gain=.4, dec=5)
    total = intro + pv + len(lv) * hold + tail
    for fi in range(int(total * FPS)):
        t = fi / FPS
        if t < intro + pv:
            def draw0(d): d._image.paste(ims[-1], (x0, y0)); d.rounded_rectangle([x0 - 3 * S, y0 - 3 * S, x0 + side + 3 * S, y0 + side + 3 * S], radius=6 * S, outline=(150, 235, 255), width=3 * S)
            sim.frame(t, (), (), (f"{lv[-1]}×{lv[-1]} ＝ ", f"{lv[-1] ** 2:,}" + sp.get("unit", "ピクセル")), (), draw0); continue
        t -= pv; i = min(len(lv) - 1, max(0, int((t - intro) / hold))); e = t - intro - i * hold; t += pv
        def draw(d, i=i, e=e):
            im = ims[i]
            if i and e < .35: im = Image.blend(ims[i - 1], im, max(0, e) / .35)   # 前の段からふわっと切りかえ
            d._image.paste(im, (x0, y0)); d.rounded_rectangle([x0 - 3 * S, y0 - 3 * S, x0 + side + 3 * S, y0 + side + 3 * S], radius=6 * S, outline=(150, 235, 255), width=3 * S)
        n = lv[i]; sim.frame(t, (), (), (f"{n}×{n} ＝ ", f"{n * n:,}" + sp.get("unit", "ピクセル")), (), draw)
    sim.finish(total)



def layers(sp):
    """1個のボール 対 たくさんの層（オーナー参考 11/22）。重力で落ちて床（いちばん上の層）で弾むたびに、層が1枚割れる。
    決まり：同じボールが split 回はねるたびに2つに分かれる（速さは同じ、向きだけ変える → 上下の速さが変わるので、はねる拍が自然にずれる）。
    はね返りで速さは減らない。割れるたびに音（"melody": "canon" ならカノンが1音進む）"""
    L, Wd, g = sp.get("layers", 512), sp.get("width", 4.0), sp.get("g", 30.0); Hs, h0 = sp.get("stack", 6.0), sp.get("drop", 2.6)
    SP, cap, phi = sp.get("split", 4), sp.get("cap", 128), math.radians(sp.get("angle", 24)); th = Hs / L; top = Hs + h0 + 1.2
    sim = Sim(sp, (-Wd / 2 - .5, -.6, Wd / 2 + .5, top), area=(.06, .235, .94, .93))
    sim.neon([(-Wd / 2, top), (-Wd / 2, -.5)], width=5); sim.neon([(Wd / 2, top), (Wd / 2, -.5)], width=5); sim.title()
    intro = .4; dt = 1 / 480; balls = [dict(x=.3, y=Hs + h0, vx=1.3, vy=0.0, n=0, tr=[], on=True)]; broken = 0; t = 0.0; frames = []; flashes = []; t_end = None
    while True:
        for b in [b for b in balls if b["on"]]:
            b["vy"] -= g * dt; b["x"] += b["vx"] * dt; b["y"] += b["vy"] * dt
            if abs(b["x"]) > Wd / 2 - .05: b["x"] = math.copysign(Wd / 2 - .05, b["x"]); b["vx"] = -b["vx"]
            fl = Hs - broken * th
            if broken < L and b["y"] <= fl and b["vy"] < 0:
                b["y"] = fl; b["vy"] = -b["vy"]; broken += 1; b["n"] += 1; flashes.append((t, fl, b["x"]))
                sim.note(intro + t, PENTA[int((1 - broken / L) * 15 + .5)], .5 / math.sqrt(max(1, len(balls) / 3)), .5 + .3 * b["x"] / Wd, 4)
                if broken == L: t_end = t
                if b["n"] % SP == 0 and len(balls) < cap:   # 分かれる：新しい1個は、同じ速さで向きを phi だけ傾けて出る
                    a = phi if len(balls) % 2 else -phi; c, s_ = math.cos(a), math.sin(a)
                    balls.append(dict(x=b["x"], y=b["y"], vx=b["vx"] * c - b["vy"] * s_, vy=abs(b["vx"] * s_ + b["vy"] * c), n=0, tr=[], on=True))
            if b["y"] < -1.5: b["on"] = False
        t += dt
        if int(t * FPS) > len(frames) - 1: frames.append((broken, [(b["x"], b["y"]) for b in balls if b["on"]]))
        if (t_end is not None and t > t_end + 2.0) or t > sp.get("max", 60): break
    if t_end is None: t_end = t
    sim.chord(intro + t_end + .35, [60, 64, 67, 72], gain=.5, dec=5)
    total = intro + len(frames) / FPS; cols = [dim(hsv(.45 + .5 * i / L), .55) for i in range(L)]; trails = {}
    for fi in range(int(total * FPS)):
        tt = fi / FPS; k = min(len(frames) - 1, max(0, int((tt - intro) * FPS))); br, pos = frames[k]
        def draw(d, br=br, tt=tt):
            step = max(1, L // 256); xa, _ = sim.to((-Wd / 2, 0)); xb, _ = sim.to((Wd / 2, 0))
            for i in range(br, L, step):
                _, y = sim.to((0, Hs - i * th)); d.line([xa, y, xb, y], fill=cols[i], width=max(1, int(1.2 * S)))
            if br < L: _, y = sim.to((0, Hs - br * th)); d.line([xa, y, xb, y], fill=(225, 255, 240), width=int(2.5 * S))
            for (tf, yf, xf) in flashes:
                e = tt - intro - tf
                if 0 <= e < .18: x, y = sim.to((xf, yf)); r = (10 + e * 260) * S; d.ellipse([x - r, y - r * .35, x + r, y + r * .35], outline=dim((200, 240, 255), 1 - e / .18), width=int(2 * S))
        live = []; dots = []
        for j, p in enumerate(pos):
            tr = trails.setdefault(j, []); tr.append(p); del tr[:-7]
            for q in range(len(tr) - 1): live.append((tr[q], tr[q + 1], dim((150, 215, 255), .15 + .75 * (q + 1) / len(tr)), 1 + 3.2 * (q + 1) / len(tr)))
            dots.append((p, (235, 248, 255), 6 if len(pos) <= 16 else 4.5))
        sim.frame(tt, live, dots, (sp.get("count_label", "割れた層："), f"{br:,} / {L:,}"), (), draw)
    sim.finish(total)



def zoomsalt(sp):
    """雑学：塩ひと粒を、原子（イオン）が見えるまで少しずつ拡大する（オーナー参考 11/22：徐々にズーム、ASMR とピアノ）。
    事実：食卓塩の粒は約0.3mm のサイコロ形（製品で差）。塩化ナトリウムの結晶は Na と Cl が交互に並び、となりどうしは約0.28nm。絵は模式図"""
    import random
    from PIL import Image
    from simkit import W as W_, H as H_
    rnd = random.Random(5); D, hold0, hold1 = sp.get("dur", 24.0), 1.2, 3.0; w0, w1 = 3e-2, 1.5e-9; total = hold0 + D + hold1
    VW, VH = int(W_ * S * .94), int(H_ * S * .50); VX, VY = (W_ * S - VW) // 2, int(H_ * S * .27); G = 3e-4; A0 = 2.82e-10
    grains = []
    for _ in range(1400):
        x, y = rnd.uniform(-2.2e-2, 2.2e-2), rnd.uniform(-1.6e-2, 1.6e-2); g = rnd.uniform(2.2e-4, 4e-4)
        if abs(x) < 5e-4 and abs(y) < 5e-4: continue
        grains.append((x, y, g, rnd.uniform(0, 1.57), rnd.uniform(.72, 1)))
    steps = {n: [(rnd.uniform(0, 1), rnd.uniform(-.25, .25)) for _ in range(40)] for n in range(-10, -2)}
    caps = [(1e-3, ["塩を、ひとつまみ"]), (1e-4, ["1粒は約0.3mm", "形はサイコロ"]), (5e-6, ["表面は、つるつるに見える"]), (4e-7, ["もっと寄ると", "細かい段々がある"]),
            (2e-8, ["ここから先は", "光の波より小さい"]), (4e-9, ["粒が見えてきた"]), (0, ["ナトリウムと塩素が", "交互にぎっしり"])]
    if sp.get("lang") == "en":
        caps = [(1e-3, ["A pinch of salt"]), (1e-4, ["One grain: about 0.3 mm", "Shaped like a tiny cube"]), (5e-6, ["The surface looks smooth"]), (4e-7, ["Closer in,", "it has tiny steps"]),
                (2e-8, ["From here it is smaller", "than a wave of light"]), (4e-9, ["Dots are showing up"]), (0, ["Sodium and chlorine,", "packed in turns"])]
    last = sp.get("last", ["1粒に、約100京個", "ならんでいるのだ"])
    def fmt(w):
        for u, k in (("cm", 1e-2), ("mm", 1e-3), ("µm", 1e-6), ("nm", 1e-9)):
            if w >= k: v = w / k; return (f"{v:.0f}" if v >= 10 else f"{v:.1f}") + " " + u
        return f"{w / 1e-9:.1f} nm"
    sim = Sim(sp, (0, 0, 1, 1)); sim.title()
    # 音：ピアノ（カノン進行の分散和音をゆっくり）＋ ASMR（塩のさらさら、10倍ごとにガラスの小さな音）
    import harmony as hm
    t = 0.0; k = 0
    while t < total - .5:
        r, q = hm.CANON[int(t / 2.0) % 8]; pcs = [(r + x) % 12 for x in q]; arp = [48 + pcs[0], 60 + pcs[1], 60 + pcs[2], 72 + pcs[0], 60 + pcs[2], 60 + pcs[1], 72 + pcs[1], 60 + pcs[2]]
        sim.note(t, arp[k % 8] if arp[k % 8] >= 55 else arp[k % 8], .42 if k % 8 == 0 else .26, .5 + .12 * math.sin(k), 3, "piano"); t += .25; k += 1
    for i in range(240): tt_ = rnd.uniform(.1, hold0 + D * .22); sim.note(tt_, 80, rnd.uniform(.05, .16) * max(.2, 1 - tt_ / (hold0 + D * .22)), rnd.uniform(.2, .8), 9, "hat")
    for dec in range(1, 8): sim.note(hold0 + D * dec / math.log10(w0 / w1), PENTA[min(15, dec * 2)], .22, .5, 5, "glass")
    fC = F(54 * S); fS = F(34 * S)
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = min(1, max(0, (t - hold0) / D)); u = u * u * (3 - 2 * u) * .35 + u * .65; w = w0 * (w1 / w0) ** u; kpx = VW / w; cx, cy = VW / 2, VH / 2
        def draw(d, w=w, kpx=kpx, t=t):
            im = Image.new("RGB", (VW, VH), (34, 24, 20)); g = ImageDraw.Draw(im)
            if w > 6e-4:   # 塩の山
                for x, y, gs, rot, sh in grains:
                    px, py, hs = cx + x * kpx, cy + y * kpx, gs * kpx / 2
                    if hs < .4 or px < -hs * 2 or px > VW + hs * 2 or py < -hs * 2 or py > VH + hs * 2: continue
                    c_, s_ = math.cos(rot) * hs * 1.41, math.sin(rot) * hs * 1.41; col = tuple(int(v * sh) for v in (236, 240, 248))
                    g.polygon([(px + c_, py + s_), (px - s_, py + c_), (px - c_, py - s_), (px + s_, py - c_)], fill=col)
            hs = G * kpx / 2; dk = min(1, max(0, (math.log10(2e-4) - math.log10(w)) / 3.2)); face = tuple(int(a + (b - a) * dk) for a, b in zip((232, 238, 247), (22, 30, 52)))
            g.rectangle([cx - hs, cy - hs, cx + hs, cy + hs], fill=face)
            if hs < VW * 2: g.rectangle([cx - hs, cy - hs, cx + hs, cy - hs * .93], fill=(250, 252, 255)); g.rectangle([cx + hs * .93, cy - hs, cx + hs, cy + hs], fill=(196, 204, 220))
            for n_, ls in steps.items():   # 段々：いつも画面に数本見えるように、10倍ごとの細かさで描く
                sp_ = 10.0 ** n_ * 3; r_ = sp_ / w
                if not (.03 < r_ < 1.2) or w > 1.5e-4: continue
                al = min(1, (r_ - .03) / .08) * min(1, (1.2 - r_) / .5) * (.9 if w > 3e-8 else max(0, (math.log10(w) + 8.3) * 1.2))
                if al <= 0: continue
                col = tuple(int(f_ + (min(255, f_ + 70) - f_) * al * .6) for f_ in face)
                for (ph, sl) in ls:
                    y = cy + ((ph * 12 - 6) * sp_) * kpx
                    if -50 < y < VH + 50: g.line([0, y - sl * VW * .5, VW, y + sl * VW * .5], fill=col, width=max(1, int(1.5 * S)))
            if w < 1.8e-8:   # 原子（イオン）の並び
                al = min(1, (math.log10(1.8e-8) - math.log10(w)) / .5); a = A0 * kpx; n1 = int(cx / a) + 2; n2 = int(cy / a) + 2
                for i in range(-n1, n1 + 1):
                    for j in range(-n2, n2 + 1):
                        cl = (i + j) % 2 == 0; r = a * (.60 if cl else .34); x, y = cx + i * a, cy + j * a; base = (110, 215, 150) if cl else (255, 176, 84)
                        col = tuple(int(f_ + (b_ - f_) * al) for f_, b_ in zip(face, base)); g.ellipse([x - r, y - r, x + r, y + r], fill=col)
                        if r > 5 * S: g.ellipse([x - r * .5, y - r * .58, x - r * .08, y - r * .2], fill=tuple(min(255, int(v + (255 - v) * .5 * al)) for v in col))
                if w < 3.2e-9 and a > 60 * S:
                    for (i, j, name) in ((0, 0, sp.get("cl", "塩素")), (1, 0, sp.get("na", "ナトリウム"))):
                        g.text((cx + i * a, cy + j * a + (a * .72 if i == 0 else -a * .5)), name, font=fS, fill=(255, 255, 255), anchor="mm", stroke_width=4 * S, stroke_fill=(0, 0, 0))
            unit = 10 ** math.floor(math.log10(w * .35)); bl = unit * kpx   # ものさし
            g.rectangle([24 * S, VH - 34 * S, 24 * S + bl, VH - 28 * S], fill=(255, 255, 255)); g.text((24 * S, VH - 78 * S), fmt(unit).replace(".0", "").replace("1.0", "1"), font=fS, fill=(255, 255, 255), stroke_width=4 * S, stroke_fill=(0, 0, 0))
            d._image.paste(im, (VX, VY)); d.rounded_rectangle([VX - 3 * S, VY - 3 * S, VX + VW + 3 * S, VY + VH + 3 * S], radius=8 * S, outline=(150, 235, 255), width=3 * S)
            lines = last if t > total - hold1 + .3 else next(c for th, c in caps if w > th)
            y = VY + VH + 46 * S
            for li, tx in enumerate(lines):
                d.text((W_ * S / 2, y), tx, font=fC, fill=(255, 214, 80) if li == len(lines) - 1 and len(lines) > 1 else (245, 245, 250), anchor="ma", stroke_width=6 * S, stroke_fill=(0, 0, 0)); y += 70 * S
        sim.frame(t, (), (), (sp.get("count_label", "画面の横幅 "), fmt(w)), (), draw)
    sim.finish(total)



def phyllo(sp):
    """黄金角（オーナー 11/22「リズムと法則が生み出す幾何学的な結末」）。決まりは1つ：前の種から決まった角度だけ回して、少し外に置く。
    角度が 90° や 135° だと線になるだけ。137.5°（黄金角）にすると、ひまわりの種の並びになる。拍に合わせて置き、だんだん速くなる"""
    rounds = sp.get("rounds", [(90.0, [(8, 4.0)]), (135.0, [(8, 4.0)]), (137.5, [(8, 2.0), (16, 2.0), (32, 4.0), (64, 6.0)])])
    K = 120.0 / sp.get("bpm", 120.0)   # bpm：拍の速さ。置くタイミングを全部この拍に合わせる（あとから曲を重ねる用）
    rounds = [(a_, [(r_ / K, d_ * K) for r_, d_ in sg]) for a_, sg in rounds]
    intro, gapr, tail = .5 * K, 1.0 * K, 2.6; plan = []; t = intro
    for ang, segs in rounds:
        ts = []
        for rate, dur in segs: ts += [t + i / rate for i in range(int(rate * dur))]; t += dur
        plan.append((ang, ts, t)); t += gapr
    total = t - gapr + tail; NMAX = max(len(ts) for _, ts, _ in plan)
    sim = Sim(sp, (-1.08, -1.08, 1.08, 1.08)); sim.ring((0, 0), 6); sim.title()
    for ang, ts, te in plan:
        step = max(1, int(round(len(ts) / (te - ts[0]) / 12)))   # 音は多くても毎秒12個くらい
        for n, tn in enumerate(ts):
            if n % step == 0: sim.note(tn, PENTA[[0, 2, 4, 7, 9, 7, 4, 2][(n // step) % 8] + (3 if (n // step) % 16 >= 8 else 0)], .5, .5 + .3 * math.cos(math.radians(ang) * n), 5)
    b = 0.0
    while b < total - 1: sim.note(intro + b, 36, .55, .5, 9, "kick"); sim.note(intro + b + .25 * K, 80, .10, .5, 9, "hat"); b += .5 * K
    sim.chord(plan[-1][2] + .1, [60, 64, 67, 72], gain=.5, dec=5)
    if sp.get("mute"): sim.notes = []   # 無音で書き出す（YouTube アプリで曲を重ねる用）
    for fi in range(int(total * FPS)):
        t = fi / FPS; ri = next((i for i, (_, ts, te) in enumerate(plan) if t < te + gapr), len(plan) - 1); ang, ts, te = plan[ri]
        n = sum(1 for x in ts if x <= t); fade = 1.0 if ri == len(plan) - 1 or t < te + gapr - .45 else max(0, (te + gapr - t) / .45)
        scale = 1.0 / math.sqrt(max(30, n) + 2); dots = []; ga = math.radians(ang)
        for i in range(n):
            r = math.sqrt(i + .5) * scale; a = i * ga; age = t - ts[i]; pop = 1 + .9 * max(0, 1 - age / .18)
            col = hsv((.08 + .5 * (i / NMAX)) % 1); dots.append(((r * math.cos(a), r * math.sin(a)), dim(col, fade), max(2.2, min(9, 150 * scale)) * pop))
        fl = []
        if n and t - ts[n - 1] < .15 and n < 200: i = n - 1; r = math.sqrt(i + .5) * scale; fl.append(((r * math.cos(i * ga), r * math.sin(i * ga)), 10 + (t - ts[i]) * 120, dim((255, 245, 210), 1 - (t - ts[i]) / .15), 2))
        sim.frame(t, (), dots, (sp.get("count_label", "回す角度 "), f"{ang:g}°"), fl)
    sim.finish(total)



def orbits(sp):
    """太陽系（オーナー 11/22）。地球と金星を、数日ごとに線で結び続ける。8年（金星はほぼ13周）で、5枚の花びらの模様になる。
    事実：公転周期 地球365.26日・金星224.70日、軌道の半径 1 と 0.723 天文単位（どちらもほぼ円として描く）"""
    Y, D = sp.get("years", 8.0), sp.get("dur", 21.0); TE, TV, RV = 365.26, 224.70, .723; every = sp.get("every", 4.0); intro, tail = .5, 2.6
    sim = Sim(sp, (-1.1, -1.1, 1.1, 1.1))
    for R_, c_ in ((1.0, (70, 110, 170)), (RV, (150, 120, 70))): sim.thin([(R_ * math.cos(a), R_ * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 181)], color=c_, width=1.4)
    sim.title()
    pos = lambda d: ((math.cos(2 * math.pi * d / TE + 1.57), math.sin(2 * math.pi * d / TE + 1.57)), (RV * math.cos(2 * math.pi * d / TV + 1.57), RV * math.sin(2 * math.pi * d / TV + 1.57)))
    day_at = lambda t: Y * TE * min(1, max(0, (t - intro) / D)) ** 1.5   # だんだん速く
    N = int(Y * TE / every); tl = [intro + D * ((k * every) / (Y * TE)) ** (1 / 1.5) for k in range(N + 1)]; lastn = -9
    for k, tk in enumerate(tl):
        if tk - lastn >= .085:   # 音は毎秒12個まで。2つの星が近いほど高い音
            e, v = pos(k * every); dist = math.hypot(e[0] - v[0], e[1] - v[1]); sim.note(tk, PENTA[int((1 - (dist - .277) / 1.446) * 15 + .5)], .45, .5 + .3 * e[0], 5); lastn = tk
    b = 0.0
    while b < intro + D: sim.note(intro + b, 36, .5, .5, 9, "kick"); sim.note(intro + b + .25, 80, .09, .5, 9, "hat"); b += .5
    sim.chord(intro + D + .1, [60, 64, 67, 72], gain=.5, dec=5)
    total = intro + D + tail; done = 0; allp = [pos(k * every) for k in range(N + 1)]; rnd_ = np.random.default_rng(3); stars = rnd_.uniform(-1.08, 1.08, (70, 2)); sph = rnd_.uniform(0, 6.28, 70)
    for fi in range(int(total * FPS)):
        t = fi / FPS; d = day_at(t); segs = []
        while done <= N and done * every <= d:
            e, v = allp[done]; segs.append((e, v, dim(hsv((.55 + .45 * done / N) % 1), .5))); done += 1
        if segs: sim.commit(segs, width=1.3)
        e, v = pos(d); live = []; dots = []; fl = []
        for q in range(max(0, done - 16), done):   # 引いたばかりの線は明るく、だんだん落ち着く（光が走った跡）
            a_ = (q - (done - 16)) / 16; live.append((allp[q][0], allp[q][1], dim((235, 240, 255), .12 + .6 * a_ * a_), 1 + 1.6 * a_))
        for q in range(done):   # きらめき：もう引いた線の上を、光が順番に流れ続ける（止まって見えないように）
            ph = (q * 7 - t * 140) % 211
            if ph < 3: live.append((allp[q][0], allp[q][1], dim(hsv((.55 + .45 * q / N) % 1), 1.0 - ph * .22), 2.2))
        for (R_, T_, col) in ((1.0, TE, (110, 180, 255)), (RV, TV, (255, 200, 120))):   # 星のうしろに尾
            for q in range(14):
                d0, d1 = d - (q + 1) * T_ * .012, d - q * T_ * .012
                p0 = (R_ * math.cos(2 * math.pi * d0 / T_ + 1.57), R_ * math.sin(2 * math.pi * d0 / T_ + 1.57)); p1 = (R_ * math.cos(2 * math.pi * d1 / T_ + 1.57), R_ * math.sin(2 * math.pi * d1 / T_ + 1.57))
                live.append((p0, p1, dim(col, .9 * (1 - q / 14) ** 1.5), 4.5 * (1 - q / 14) + 1))
        live.append((e, v, (255, 255, 255), 2.4))
        for i_ in range(70): tw = .5 + .5 * math.sin(t * 2.2 + sph[i_]); dots.append(((float(stars[i_][0]), float(stars[i_][1]) * 1.0), dim((170, 190, 255), .10 + .35 * tw), 1.6))
        bt = ((t - intro) % .5) / .5 if t > intro else 1   # 太陽は拍に合わせて脈を打つ
        fl.append(((0, 0), 16 + bt * 46, dim((255, 220, 130), (1 - bt) * .8), 3)); fl.append(((e[0], e[1]), 12 + bt * 16, dim((110, 180, 255), (1 - bt) * .6), 2)); fl.append(((v[0], v[1]), 11 + bt * 14, dim((255, 200, 120), (1 - bt) * .6), 2))
        dots += [((0, 0), (255, 226, 140), 13 + 3 * (1 - bt)), (e, (130, 195, 255), 9), (v, (255, 208, 130), 8)]
        sim.frame(t, live, dots, (sp.get("count_label", "たった時間 "), f"{d / TE:.1f}" + sp.get("unit", "年")), fl)
    sim.finish(total)



def pendwave(sp):
    """振り子の波（派生の土台。オーナー 11/22「振り子は相性がいい」）。長さだけちがう N 本。P 秒のあいだに k0, k0+1, … 回ゆれるので、P 秒後にまたそろう。
    まん中を通るたびに、その振り子の音（石の音色を想定）。玉には光の尾、まん中を通る瞬間に光の輪"""
    N, P, k0, A = sp.get("n", 15), sp.get("period", 24.0), sp.get("k0", 20), math.radians(sp.get("amp", 26)); intro, tail = .6, 2.4; total = intro + P + tail
    Ls = [1.0 * (k0 / (k0 + i)) ** 2 for i in range(N)]; top = 1.12
    sim = Sim(sp, (-.47, -.03, .47, top + .03), area=(.04, .215, .96, .90)); sim.neon([(-.44, top), (.44, top)], width=5); sim.title()
    cols = [hsv(.02 + .8 * i / N) for i in range(N)]
    for i in range(N):
        per = P / (k0 + i)
        for j in range(2 * (k0 + i)):
            tc = intro + (j + .5) * per / 2
            if tc < intro + P: sim.note(tc, PENTA[int(i / (N - 1) * 15 + .5)], .42, .5, 5)
    sim.chord(intro, [60, 67, 72]); sim.chord(intro + P, [60, 64, 67, 72], gain=.55, dec=5)
    hist = [[] for _ in range(N)]
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = min(max(0, t - intro), P); live, dots, fl = [], [], []
        for i in range(N):
            per = P / (k0 + i); th = A * math.cos(2 * math.pi * u / per); L = Ls[i]; pz = (L * math.sin(th), top - L * math.cos(th))
            live.append(((0, top), pz, dim(cols[i], .22), 1.2)); h = hist[i]; h.append(pz); del h[:-9]
            for q in range(len(h) - 1): live.append((h[q], h[q + 1], dim(cols[i], .12 + .7 * (q + 1) / len(h)), 1 + 4 * (q + 1) / len(h)))
            dots.append((pz, cols[i], 9))
            e = (u - per / 4) % (per / 2) if u > per / 4 else 9
            if e < .16 and u < P: fl.append(((0, top - L), 10 + e * 150, dim(cols[i], 1 - e / .16), 2.5))
        e = t - (intro + P)
        if 0 <= e < .6:
            for i in range(N): fl.append(((A * Ls[i] * 0 + Ls[i] * math.sin(A), top - Ls[i] * math.cos(A)), 12 + e * 120, dim((255, 245, 210), 1 - e / .6), 3))
        sim.frame(t, live, dots, (sp.get("count_label", "そろうまで "), f"{max(0, math.ceil(P - u))}"), fl)
    sim.finish(total)



def lens(sp):
    """向かい合った2枚の放物線の鏡（焦点が同じ）。まん中の点から全方向に打つと、1枚目で水平になり、2枚目でまた同じ点に戻る。
    道の長さはどの向きも 4f で同じ。打ち出す系なので、速さを向きにそって波のようにずらす（stagger）"""
    f, v, ST = 1.0, sp.get("v", 2.4), sp.get("stagger", .3); ms = sp.get("rounds", [4, 8, 16, 32]) + [sp.get("last", 64)]; intro, tail = .4, 1.6
    T = 4 * f / (v * (1 - ST)); sim = Sim(sp, (-1.12, -2.08, 1.12, 2.08), area=(.05, .215, .95, .885))   # 下の先がチャンネル名の字（.905）に重ならない高さまで
    ys = np.linspace(-2 * f, 2 * f, 201); sim.neon([(f - y * y / (4 * f), y) for y in ys]); sim.neon([(-(f - y * y / (4 * f)), y) for y in ys]); sim.ring((0, 0), 12); sim.title()
    rounds = []
    for r, m in enumerate(ms):
        t0 = intro + r * T; balls = []
        for i in range(m):
            th = 2 * math.pi * (i + .5) / m + .37 * r; c = math.cos(th); rr = 2 * f / (1 + abs(c)); p1 = (rr * c, rr * math.sin(th)); p2 = (-p1[0], p1[1])
            spd = 1 - ST * (.5 - .5 * math.cos(th - 1.3 * r)); balls.append(dict(pts=[(0, 0), p1, p2, (0, 0)], cum=[0, rr, rr + 2 * abs(p1[0]), 4 * f], spd=spd, col=hsv((i / m + .08 * r) % 1), done=0))
        n = len(balls); g = .9 / math.sqrt(n); dec = 4 + 3 * math.sqrt(n / 5)
        stp = max(1, n // 48)   # 音は1回に48個まで
        for bi_, b in enumerate(balls):
            if bi_ % stp: continue
            for q in (1, 2): sim.note(t0 + b["cum"][q] / (v * b["spd"]), PENTA[int((b["pts"][q][1] / (2 * f) * .5 + .5) * 15 + .5)], g, .5 + .4 * b["pts"][q][0], dec)
        sim.chord(t0, [60, 67, 72]); rounds.append((t0, balls))
    total = intro + len(ms) * T + tail; sim.chord(intro + len(ms) * T, [60, 64, 67, 72], gain=.5, dec=5)
    sim.notes = [nt for nt in sim.notes if nt[0] < total - .02]
    for fi in range(int(total * FPS)):
        t = fi / FPS; r = min(len(rounds) - 1, max(0, int((t - intro) // T))); t0, balls = rounds[r]; s = max(0, t - t0) * v; segs = []; n = len(balls); lw = max(1.0, 2.0 * min(1, 10 / math.sqrt(n)))
        if r > 0:
            for b in rounds[r - 1][1]:
                while b["done"] < 3: segs.append((b["pts"][b["done"]], b["pts"][b["done"] + 1], dim(b["col"], .28 * min(1, 5 / math.sqrt(len(rounds[r - 1][1])))))); b["done"] += 1
        live, dots, fl = [], [], []; arrived = 0
        for b in balls:
            cum, pts = b["cum"], b["pts"]; sc = min(s * b["spd"], cum[-1])
            while b["done"] < 3 and cum[b["done"] + 1] <= sc: segs.append((pts[b["done"]], pts[b["done"] + 1], dim(b["col"], .28 * min(1, 5 / math.sqrt(n))))); b["done"] += 1
            k = b["done"]
            if k >= 3: arrived += 1; continue
            pnt = lerp(pts[k], pts[k + 1], (sc - cum[k]) / (cum[k + 1] - cum[k])); live.append((pts[k], pnt, dim(b["col"], .75 * min(1, 8 / math.sqrt(n))), lw)); dots.append((pnt, b["col"], 5 if n <= 32 else 4 if n <= 256 else 2.6))
            e = (sc - cum[k]) / (v * b["spd"])
            if k in (1, 2) and e < .2 and n <= 128: fl.append((pts[k], 8 + e * 70, dim(b["col"], 1 - e / .2), 2))
        sim.commit(segs, width=lw)
        gl = arrived / n if s > 0 else 0; bt = (t * 2) % 1
        fl.append(((0, 0), 14 + 30 * gl + 6 * (1 - bt), dim((255, 240, 190), .3 + .7 * gl), 4))
        sim.frame(t, live, dots, (sp.get("count_label", "ボール："), f"{n:,}"), fl)
    sim.finish(total)


def koch(sp):
    """コッホ雪片。辺のまん中3分の1に、小さな三角を足す、をくり返す。面積は元の 1.6 倍より大きくならないのに、まわりの長さは毎回 4/3 倍で、どこまでも伸びる。
    光の玉がふちを1周なぞる。角を曲がるたびに1音"""
    stages = sp.get("stages", 5); per = sp.get("per", 4.4); intro, tail = .5, 2.2; R = 1.0
    def poly(n):
        pts = [(R * math.cos(math.radians(90 + 120 * k)), R * math.sin(math.radians(90 + 120 * k))) for k in range(3)]
        for _ in range(n):
            out = []
            for i in range(len(pts)):
                a, b = pts[i], pts[(i + 1) % len(pts)]; dx, dy = (b[0] - a[0]) / 3, (b[1] - a[1]) / 3; p1 = (a[0] + dx, a[1] + dy); p2 = (a[0] + 2 * dx, a[1] + 2 * dy)
                pk = (p1[0] + dx * .5 + dy * .8660254, p1[1] + dy * .5 - dx * .8660254); out += [a, p1, pk, p2]
            pts = out
        return pts
    polys = [poly(n) for n in range(stages + 1)]; side0 = math.dist(polys[0][0], polys[0][1])
    sim = Sim(sp, (-1.22, -1.22, 1.22, 1.22)); sim.neon([(1.2 * math.cos(a), 1.2 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 181)], width=3); sim.title()
    total = intro + (stages + 1) * per + tail
    for n, pts in enumerate(polys):
        t0 = intro + n * per; m = len(pts); step = max(1, m // 48); idx = 7
        for i in range(0, m, step):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % m]; cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]); idx = min(15, max(0, idx + (1 if cr < 0 else -2)))
            sim.note(t0 + (per - .5) * i / m, PENTA[idx], .5, .5 + .4 * b[0], 5)
        sim.chord(t0 + per - .45, [60 + 2 * 0, 67, 72] if n < stages else [60, 64, 67, 72], gain=.4, dec=4)
    fS = F(40 * S)
    for fi in range(int(total * FPS)):
        t = fi / FPS; n = min(stages, max(0, int((t - intro) / per))); u = min(1, max(0, (t - intro - n * per) / (per - .5))); pts = polys[n]; m = len(pts)
        cols = lambda q: hsv(.55 + .25 * q / m); k = int(u * m); live = []
        for i in range(m):
            a, b = pts[i], pts[(i + 1) % m]
            if i < k: live.append((a, b, dim(cols(i), 1.0), 4.2 if m < 400 else 3.0))
            else: live.append((a, b, dim((140, 160, 215), .55), 2.0))
        dots = []; fl = []
        if u < 1:
            a, b = pts[k % m], pts[(k + 1) % m]; fr = u * m - k; pz = lerp(a, b, fr); dots.append((pz, (235, 248, 255), 9)); fl.append((pz, 16, (160, 220, 255), 2))
            for q in range(1, 6):
                kk = (k - q) % m
                if k - q >= 0: live.append((pts[kk], pts[(kk + 1) % m], dim((235, 248, 255), 1 - q / 6), 5 - q * .6))
        peri = 3 * (4 / 3) ** n; area = 1 + .6 * (1 - (4 / 9) ** n)
        def draw(d, area=area, n=n):
            tx = sp.get("area_label", "面積 ") + f"{area:.3f}" + sp.get("area_tail", "（元の三角形＝1）"); w = d.textlength(tx, font=fS); d.text((1080 * S / 2 - w / 2, 1920 * S * .84), tx, font=fS, fill=(200, 215, 240), stroke_width=4 * S, stroke_fill=(0, 0, 0))
        sim.frame(t, live, dots, (sp.get("count_label", "まわりの長さ "), f"{peri:.2f}"), fl, draw)
    sim.finish(total)



def spiro(sp):
    """スピログラフ（オーナー参考 11/22、いいね52万）。歯数 Rt の大きな輪の内側を、歯数 rt の小さな歯車が転がり、穴に差したペンが線を描く。
    歯数の比で、花びらの数と、何周で閉じるかが決まる（花びら＝Rt/gcd、周回＝rt/gcd）。花びらの先を通るたびに1音。だんだん速く"""
    Rt, rt, hole = sp.get("R", 96), sp.get("r", 60), sp.get("hole", .8); g = math.gcd(Rt, rt); petals, laps = Rt // g, rt // g
    R = 1.0; r = R * rt / Rt; d = r * hole; D, intro, tail = sp.get("dur", 22.0), .5, 2.6; total = intro + D + tail
    th_end = 2 * math.pi * laps; th_at = lambda t: th_end * min(1, max(0, (t - intro) / D)) ** 1.6
    holes = sp.get("holes") or [hole]; d = r * holes[0]; H0, HW, HS = sp.get("hue", .62), sp.get("hue_w", .30), sp.get("hue_step", .0)   # holes：同じ歯車に何本もペンを差す。hue_step：ペンごとの色のずれ
    W3 = sp.get("wheel3"); m3 = (1 + W3.get("j", 1) * Rt / rt) if W3 else 0; e3 = (W3.get("e", .1) * R) if W3 else 0; p3 = W3.get("phase", 0.0) if W3 else 0
    def penD(th, dd, full=True):
        x, y = (R - r) * math.cos(th) + dd * math.cos((R - r) / r * th), (R - r) * math.sin(th) - dd * math.sin((R - r) / r * th)
        if W3 and full: x += e3 * math.cos(m3 * th + p3); y += e3 * math.sin(m3 * th + p3)
        return (x, y)
    pen = lambda th: penD(th, d)
    sim = Sim(sp, (-1.15, -1.15, 1.15, 1.15)); sim.neon([(R * math.cos(a), R * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 241)], width=4); sim.title()
    # 花びらの先（中心からいちばん遠い点）を通る時刻に音
    N = 6000; ths = np.linspace(0, th_end, N); rad = np.array([math.hypot(*pen(t_)) for t_ in ths]); last = -9; tips = 0
    inv = lambda th: intro + D * (th / th_end) ** (1 / 1.6)
    for i in range(1, N - 1):
        if rad[i] >= rad[i - 1] and rad[i] > rad[i + 1]:
            tt = inv(ths[i])
            if tt - last > .07: sim.note(tt, PENTA[[0, 2, 4, 7, 9, 12, 9, 7, 4, 2][tips % 10]], .5, .5 + .35 * pen(ths[i])[0], 5); last = tt
            tips += 1
    b = 0.0
    while b < D: sim.note(intro + b, 36, .45, .5, 9, "kick"); b += .5
    sim.chord(intro + D + .1, [60, 64, 67, 72], gain=.55, dec=5)
    prev = 0.0
    for fi in range(int(total * FPS)):
        t = fi / FPS; th = th_at(t); segs = []
        n = max(1, int((th - prev) / .01))
        for k in range(n):
            a0, a1 = prev + (th - prev) * k / n, prev + (th - prev) * (k + 1) / n
            for j, hl in enumerate(holes): segs.append((penD(a0, r * hl), penD(a1, r * hl), dim(hsv((H0 + HS * j + HW * a1 / th_end) % 1), sp.get("line", .85))))
        if th > prev: sim.commit(segs, width=1.6)
        prev = th; c = ((R - r) * math.cos(th), (R - r) * math.sin(th)); p_ = pen(th); live = []
        live += [((c[0] + r * math.cos(a), c[1] + r * math.sin(a)), (c[0] + r * math.cos(a + .1), c[1] + r * math.sin(a + .1)), (120, 140, 190), 2.4) for a in np.arange(0, 2 * math.pi, .1)]
        spin = -(R - r) / r * th
        for k in range(rt // 4):   # 歯車の歯（回転が見えるように）
            a = spin + 2 * math.pi * k / (rt // 4); live.append(((c[0] + r * .93 * math.cos(a), c[1] + r * .93 * math.sin(a)), (c[0] + r * math.cos(a), c[1] + r * math.sin(a)), (150, 170, 215), 2))
        extra = [penD(th, r * hl) for hl in holes[1:]]
        if W3:
            h_ = penD(th, d, False); live.append((c, h_, (200, 210, 240), 1.4)); live.append((h_, p_, (255, 220, 150), 1.6))
            live += [((h_[0] + e3 * math.cos(a_), h_[1] + e3 * math.sin(a_)), (h_[0] + e3 * math.cos(a_ + .2), h_[1] + e3 * math.sin(a_ + .2)), (255, 200, 120), 2.2) for a_ in np.arange(0, 2 * math.pi, .2)]
        else: live.append((c, p_, (200, 210, 240), 1.4))
        fl = [(p_, 10 + 4 * math.sin(t * 12), (255, 240, 200), 2)] if t < intro + D else []
        e = t - intro - D
        if 0 <= e < .7: fl.append(((0, 0), 30 + e * 500, dim((255, 245, 210), 1 - e / .7), 4))
        sim.frame(t, live, [(p_, (255, 250, 235), 6)] + [(q_, (255, 250, 235), 5) for q_ in extra], (sp.get("count_label", "花びら "), f"{petals}"), fl)
    sim.finish(total)



def pendwave3d(sp):
    """振り子の波を、斜め下から見た3D（オーナーの画面収録 11/23 にならう：手前ほど大きく暖色、奥ほど小さく寒色、光る玉と残像、細い糸が棒に集まる）。
    棒は奥へのびる。振り子 i は棒の z_i にぶら下がり、x-y 面でゆれる。P 秒でまたそろう"""
    N, P, k0, A = sp.get("n", 15), sp.get("period", 24.0), sp.get("k0", 20), math.radians(sp.get("amp", 30)); intro, tail = .6, 2.4; total = intro + P + tail
    Ls = [1.0 * (k0 / (k0 + i)) ** 2 for i in range(N)]; zs = [1.0 + i * .55 for i in range(N)]
    ce, cy, tilt, f = np.array([0.0, -1.55, -1.2]), 0, math.radians(sp.get("tilt", 34)), 1.55
    def proj(x, y, z):   # カメラは棒の手前・下から、上向きに見上げる
        X, Y, Z = x - ce[0], y - ce[1], z - ce[2]; ca, sa = math.cos(tilt), math.sin(tilt); y2, z2 = Y * ca - Z * sa, Y * sa + Z * ca
        return (f * X / z2, f * y2 / z2), z2
    sim = Sim(sp, (-.8, -1.0, .8, 1.12), area=(.03, .13, .97, .95)); sim.title()
    cols = [hsv((.53 - .45 * i / (N - 1)) % 1) for i in range(N)]   # 奥（上）＝水色 → 手前（下）＝オレンジ
    for i in range(N):
        per = P / (k0 + i)
        for j in range(2 * (k0 + i)):
            tc = intro + (j + .5) * per / 2
            if tc < intro + P: sim.note(tc, PENTA[int(i / (N - 1) * 15 + .5)], .42, .5, 5)
    sim.chord(intro, [60, 67, 72]); sim.chord(intro + P, [60, 64, 67, 72], gain=.55, dec=5)
    # 画面での見え方（収録にならう）：棒は上から下へ。振り子 i は棒の y_i にぶら下がり、手前（下）ほど大きく、横に大きくふれる
    ys = [.98 - i * .13 for i in range(N)]; ss = [.5 + .5 * i / (N - 1) for i in range(N)]
    def bob(i, th): s_ = ss[i]; return (s_ * .78 * math.sin(th), ys[i] - s_ * .16 * math.cos(th) - .05), s_
    hist = [[] for _ in range(N)]
    for fi in range(int(total * FPS)):
        t = fi / FPS; u = min(max(0, t - intro), P); live = [((0, 1.08), (0, ys[-1] - .02), (240, 200, 120), 3.0)]; dots = []; fl = []
        for i in range(N):
            per = P / (k0 + i); th = A * math.cos(2 * math.pi * u / per); bp, sc = bob(i, th)
            live.append(((0, ys[i]), bp, dim(cols[i], .42), 1.2))
            h = hist[i]; h.append(bp); del h[:-11]
            for q in range(len(h) - 1): live.append((h[q], h[q + 1], dim(cols[i], .08 + .62 * (q + 1) / len(h)), (1 + 8 * (q + 1) / len(h)) * sc))
            dots.append((bp, tuple(min(255, int(c * .5 + 255 * .5)) for c in cols[i]), 15 * sc))
            if 0 < u < P:
                e = (u - per / 4) % (per / 2) if u > per / 4 else 9
                if e < .18: fl.append((bp, (18 + e * 120) * sc, dim(cols[i], 1 - e / .18), 2))
        e = t - (intro + P)
        if 0 <= e < .7: fl.append(((0, .1), 20 + e * 420, dim((255, 240, 210), 1 - e / .7), 4))
        sim.frame(t, live, dots, None, fl)
    sim.finish(total)



def bricks(sp):
    """はねるたびにレンガが1つ増える（オーナー画面収録 11/23 の型）。円の中を玉がまっすぐ飛び、壁に当たった場所に内向きのレンガが積もる。
    積もるほど中がせまくなり、はねる間かくが短くなる＝曲がだんだん速くなる。当たるたびに旋律が1音（melody）"""
    import random
    rnd = random.Random(sp.get("seed", 4)); NB = 360; r0, br, th_add, spread = 1.0, .022, sp.get("brick", .016), sp.get("spread", 5)
    rw = np.full(NB, r0); v = sp.get("v", 1.35); ang = math.radians(sp.get("angle", 63)); p = np.array([0.05, .3]); vel = np.array([math.cos(ang), math.sin(ang)]) * v
    D, intro, tail = sp.get("dur", 30.0), .4, 2.6; dt = 1 / 600; t = 0.0; frames = []; hits = []; bricks_n = 0
    while t < D:
        p = p + vel * dt; t += dt; a = math.atan2(p[1], p[0]); k = int((a % (2 * math.pi)) / (2 * math.pi) * NB) % NB
        if math.hypot(*p) >= rw[k] - br and np.dot(p, vel) > 0:
            n_ = p / math.hypot(*p); kl, kr = rw[(k - 3) % NB], rw[(k + 3) % NB]   # 積もった面の傾きも少しだけ法線に入れる
            tang = np.array([-n_[1], n_[0]]); n_ = n_ + tang * (kl - kr) * 4; n_ /= np.linalg.norm(n_)
            vel = vel - 2 * np.dot(vel, n_) * n_; p = p - n_ * .003; hits.append((t, a)); bricks_n += 1
            for j in range(-spread, spread + 1): rw[(k + j) % NB] = max(.32, rw[(k + j) % NB] - th_add * (1 - abs(j) / (spread + 1)) ** .5)
            vel *= 1.0 + sp.get("speedup", .004)
        if int(t * FPS) >= len(frames): frames.append((p.copy(), rw.copy(), bricks_n))
    sim = Sim(sp, (-1.08, -1.08, 1.08, 1.08)); sim.title()
    for th, a in hits: sim.note(intro + th, 72, .55, .5 + .35 * math.cos(a), 5)
    sim.chord(intro + D + .05, [60, 64, 67, 72], gain=.55, dec=5)
    total = intro + D + tail; tr = []
    angs = np.linspace(0, 2 * math.pi, NB, endpoint=False) + math.pi / NB
    for fi in range(int(total * FPS)):
        t = fi / FPS; k = min(len(frames) - 1, max(0, int((t - intro) * FPS))); pp, rr, nb = frames[k]
        tr.append(tuple(pp)); del tr[:-8]
        def draw(d, rr=rr):
            outer = [sim.to((r0 * math.cos(a), r0 * math.sin(a))) for a in angs]; inner = [sim.to((rr[i] * math.cos(angs[i]), rr[i] * math.sin(angs[i]))) for i in range(NB)]
            for i in range(NB):   # レンガ：外の円と、積もった内側のあいだを塗る。レンガの目地を細い線で
                if rr[i] < r0 - .001:
                    j = (i + 1) % NB; d.polygon([outer[i], outer[j], inner[j], inner[i]], fill=(200, 58, 64))
            for depth in np.arange(r0 - .03, .3, -.03):
                pts = [sim.to((depth * math.cos(angs[i]), depth * math.sin(angs[i]))) if rr[i] < depth - .006 else None for i in range(NB)]
                for i in range(NB):
                    j = (i + 1) % NB
                    if pts[i] and pts[j]: d.line([pts[i], pts[j]], fill=(232, 150, 150), width=1)
            for i in range(0, NB, 6):
                if rr[i] < r0 - .01:
                    off = (int((r0 - rr[i]) / .03) % 2) * 3; a = angs[(i + off) % NB]; d.line([sim.to((r0 * math.cos(a), r0 * math.sin(a))), sim.to((rr[(i + off) % NB] * math.cos(a), rr[(i + off) % NB] * math.sin(a)))], fill=(232, 150, 150), width=1)
            d.line(outer + [outer[0]], fill=(245, 245, 250), width=int(5 * S))
        live = [(tr[q], tr[q + 1], dim((255, 255, 255), .2 + .7 * (q + 1) / len(tr)), 1 + 4 * (q + 1) / len(tr)) for q in range(len(tr) - 1)]
        fl = []
        for th, a in hits:
            e = t - intro - th
            if 0 <= e < .2: fl.append(((math.cos(a) * .97, math.sin(a) * .97), 8 + e * 80, dim((255, 220, 210), 1 - e / .2), 2))
            if e > .3: break
        sim.frame(t, live, [(pp, (255, 255, 255), 6)], (sp.get("count_label", "Bricks: "), f"{nb}"), fl, draw)
    sim.finish(total)



def hearts(sp):
    """心臓の拍で曲を鳴らす（オーナー画面収録 11/23 の型、いいね12万）。生きものごとの心拍（およその安静時）を心電図の線で流し、
    どの生きものの拍も、同じ1曲の「次の1音」を鳴らす（melody）。下に行くほど速い生きもの。最後にクジラ（ゆっくり）"""
    rows = sp.get("rows"); add_every, intro, tail = sp.get("add_every", 3.2), .5, 3.0; win = sp.get("window", 2.4)
    n = len(rows); starts = [intro + i * add_every for i in range(n)]; total = starts[-1] + sp.get("last_hold", 6.0) + tail
    sim = Sim(sp, (0, 0, 1, 1)); sim.title()
    beats = []
    for i, (name, bpm, col) in enumerate(rows):
        per = 60 / bpm; t = starts[i] + .35
        while t < total - tail: beats.append((t, i)); t += per
    beats.sort()
    if sp.get("melody"):
        for t, i in beats: sim.note(t, 72, .5 / math.sqrt(1 + .25 * i), .5, 5)
    else:   # 生きものごとに決まった1音（和音の中の音）。速い生きものほど高く、小さく、短く → 速い拍は「きらきら」に溶ける（オーナー 11/23「音汚い」）
        # 和音を意識（オーナー 11/23）：カノン進行に合わせて、生きものごとに和音の中の役（根音・3度・5度）と高さを持つ。
        # クジラ＝いちばん低い根音、ゾウ＝根音、ヒト＝5度、ネコ＝3度、ウサギ＝5度（上）、ネズミ＝根音（上）、ハチドリ＝3度（上）
        import harmony
        ROLE = sp.get("roles") or [(0, 50), (2, 57), (1, 64), (2, 69), (0, 74), (1, 78), (0, 38)]
        on0 = harmony.ON; harmony.ON = False
        def voice(t, k):
            r, q = harmony.CANON[int(max(0, t) / harmony.BAR) % len(harmony.CANON)]; pc = (r + q[ROLE[k][0]]) % 12; c = ROLE[k][1]
            return min(range(c - 6, c + 7), key=lambda m: (m % 12 != pc) * 99 + abs(m - c))
        for t, i in beats:
            bpm = rows[i][1]; g = .5 * min(1.0, math.sqrt(40 / bpm)) * (1.4 if bpm < 10 else 1); dc = 3 if bpm < 60 else 5 if bpm < 200 else 10 if bpm < 700 else 16
            sim.note(t, voice(t, i), g, .5 + .3 * math.sin(i * 2.1), dc, "mar")
            if bpm < 10: sim.note(t, voice(t, i) - 12, .45, .5, 2, "mar")
        harmony.ON = on0
    ICONS = {}
    if sp.get("icons"):
        from PIL import Image
        for nm in set(sp["icons"]): ICONS[nm] = Image.open(os.path.join(os.path.dirname(__file__), "..", "nazo", "ballsim", "icons", nm + ".png")).convert("RGBA")
    from simkit import W as W_, H as H_
    top, bot = .245, .87; fN, fB = F(38 * S), F(34 * S)
    def ecg(ph):   # 1拍の形（0〜1）：小さな山 → 鋭い山 → 谷 → ゆるい山
        return (.12 * math.exp(-((ph - .18) / .03) ** 2) + 1.0 * math.exp(-((ph - .30) / .008) ** 2) - .28 * math.exp(-((ph - .33) / .01) ** 2) + .22 * math.exp(-((ph - .52) / .05) ** 2))
    def heart(d, x, y, r, c):
        d.ellipse([x - r, y - r * .9, x, y + r * .1], fill=c); d.ellipse([x, y - r * .9, x + r, y + r * .1], fill=c); d.polygon([(x - r * .98, y - r * .25), (x + r * .98, y - r * .25), (x, y + r)], fill=c)
    for fi in range(int(total * FPS)):
        t = fi / FPS; shown = [i for i in range(n) if t >= starts[i]]; m = max(1, len(shown)); rh = min(.16, (bot - top) / m)
        def draw(d, t=t, shown=shown, rh=rh):
            if sp.get("glow"):   # 床のワイヤー（ゆっくり流れる）＋クジラの拍で全体が明るく
                wi = [i for i in shown if rows[i][1] < 10]; wp_ = 0
                for i in wi:
                    per = 60 / rows[i][1]; ag_ = (t - starts[i] - .35) % per if t >= starts[i] + .35 else 9; wp_ = max(wp_, math.exp(-ag_ * 2.2))
                gc = tuple(min(255, int(v * (1 + 1.0 * wp_))) for v in (20, 19, 50))
                for q in range(14):
                    yy = (top + (bot - top) * q / 13) * H_ * S; d.line([(0, yy), (W_ * S, yy)], fill=gc, width=max(1, int(1 * S)))
                off = (t * 40 * S) % (W_ * S / 12)
                for q in range(14):
                    xx = q * W_ * S / 12 - off; d.line([(xx, top * H_ * S), (xx, bot * H_ * S)], fill=gc, width=max(1, int(1 * S)))
            for k, i in enumerate(shown):
                name, bpm, col = rows[i]; per = 60 / bpm; yc = (top + rh * (k + .62)) * H_ * S; x0, x1 = W_ * S * .27, W_ * S * .93; amp = rh * H_ * S * .42
                pts = []; N_ = 260
                for q in range(N_ + 1):
                    tt = t - win * (1 - q / N_); ph = ((tt - starts[i] - .35) / per) % 1 if tt >= starts[i] + .35 else .9
                    pts.append((x0 + (x1 - x0) * q / N_, yc - amp * ecg(ph) * (.55 if per < .12 else .8 if per < .25 else 1)))
                ab = ((t - starts[i] - .35) % per) if t >= starts[i] + .35 else 9
                d.line(pts, fill=dim(col, .30), width=int(10 * S)); d.line(pts, fill=tuple(min(255, int(c * 1.1)) for c in col), width=int(3.5 * S))
                if sp.get("glow") and per >= .2 and ab < .45:   # 右端に光の輪（ヒット）
                    rr = (8 + 40 * ab) * S; al = .55 * (1 - ab / .45); d.ellipse([x1 - rr, pts[-1][1] - rr, x1 + rr, pts[-1][1] + rr], outline=tuple(int(min(255, c * .6 + 100) * al) for c in col), width=max(1, int(4 * S * al + 1)))
                e = ((t - starts[i] - .35) % per) / per if t >= starts[i] + .35 else 1; pr = 1 + .45 * math.exp(-e * 9)
                heart(d, W_ * S * .228, yc - 4 * S, 14 * S * pr, (255, 70, 110)); d.ellipse([x1 - 7 * S, pts[-1][1] - 7 * S, x1 + 7 * S, pts[-1][1] + 7 * S], fill=(255, 255, 255))
                if ICONS:   # アイコン（拍で少しふくらむ）＋名前は線の左上
                    ic = ICONS[sp["icons"][i]]; sz = int(min(rh * H_ * S * .78, 120 * S) * (1 + .12 * math.exp(-e * 9)))
                    ib = .45 * math.exp(-e * per * 6) if per >= .2 else .12
                    tint = Image.new("RGBA", ic.size, tuple(min(255, int(c * (1.0 + .5 * ib) + 90 * ib)) for c in col) + (255,)); tint.putalpha(ic.getchannel("A"))
                    im_ = tint.resize((sz, sz)); d._image.paste(im_, (int(W_ * S * .105 - sz / 2), int(yc - sz / 2)), im_)
                    d.text((x0, yc - amp - 34 * S), name, font=fB, fill=(235, 238, 245), stroke_width=4 * S, stroke_fill=(0, 0, 0))
                else:
                    fz = fN if d.textlength(name, font=fN) < W_ * S * .17 else F(int(38 * S * W_ * S * .17 / d.textlength(name, font=fN)))
                    d.text((W_ * S * .025, yc - 20 * S), name, font=fz, fill=(235, 238, 245), stroke_width=4 * S, stroke_fill=(0, 0, 0))
                tx = f"{bpm:g} " + sp.get("unit", "bpm"); w = d.textlength(tx, font=fB); d.text((x1 - w, yc - amp - 34 * S), tx, font=fB, fill=(255, 255, 255), stroke_width=4 * S, stroke_fill=(0, 0, 0))
        sim.frame(t, (), (), None, (), draw)
    sim.finish(total)



def merge(sp):
    """合体して次の段へ（オーナー画面収録 11/23「Which Planet Reaches Final Form?」の型）。上の口から小さな星を落とす。
    同じ段どうしがふれると合体して次の段（大きな星）になる。合体のたびに光の輪と名前、音は段ごとに高く。最後にどの段まで届くか"""
    import random
    rnd = random.Random(sp.get("seed", 7)); T = sp.get("tiers"); K = len(T); R0, gro = sp.get("r0", .052), sp.get("grow", 1.30); rad = [R0 * gro ** k for k in range(K)]
    RC, gate, g = 1.0, .17, 2.6; D, intro, tail = sp.get("dur", 30.0), .4, 3.0; dt = 1 / 240
    P = np.zeros((0, 2)); V = np.zeros((0, 2)); TI = np.zeros(0, int); born = np.zeros(0); events = []; frames = []; best = 0; t = 0.0; nxt = .2
    while t < D:
        if t >= nxt:   # 落とす間かくは、だんだん短く
            P = np.vstack([P, [rnd.uniform(-gate * .45, gate * .45), RC + .55]]); V = np.vstack([V, [rnd.uniform(-.1, .1), -.4]]); TI = np.append(TI, 0); born = np.append(born, t)
            nxt = t + max(.11, .42 - .3 * t / D)
        V[:, 1] -= g * dt; P += V * dt
        for _ in range(3):
            n = len(P)
            if n > 1:
                d = P[:, None, :] - P[None, :, :]; dist = np.sqrt((d ** 2).sum(-1)) + np.eye(n); rr = np.array([rad[k] for k in TI]); need = rr[:, None] + rr[None, :]
                ii, jj = np.where(np.triu(dist < need, 1))
                merged = set()
                for i, j in zip(ii, jj):
                    if i in merged or j in merged: continue
                    if TI[i] == TI[j] and TI[i] < K - 1:   # 合体
                        k = TI[i] + 1; P[i] = (P[i] + P[j]) / 2; V[i] = (V[i] + V[j]) / 2 * .5; TI[i] = k; born[i] = t; merged.add(j); events.append((t, k, P[i].copy())); best = max(best, k)
                    else:
                        nv = d[i, j] / dist[i, j]; ov = need[i, j] - dist[i, j]; mi, mj = rr[i] ** 2, rr[j] ** 2
                        P[i] += nv * ov * mj / (mi + mj); P[j] -= nv * ov * mi / (mi + mj)
                        rv = np.dot(V[i] - V[j], nv)
                        if rv < 0: im = 1.25 * rv / (mi + mj); V[i] -= im * mj * nv; V[j] += im * mi * nv
                if merged:
                    keep = [q for q in range(n) if q not in merged]; P, V, TI, born = P[keep], V[keep], TI[keep], born[keep]
            for q in range(len(P)):   # 円の壁（上の口だけ開いている）
                x, y = P[q]; r = math.hypot(x, y); rq = rad[TI[q]]
                if abs(x) < gate - rq and y > 0: continue
                if r > RC - rq:
                    nv = np.array([x, y]) / r; P[q] = nv * (RC - rq); vn = np.dot(V[q], nv)
                    if vn > 0: V[q] -= 1.4 * vn * nv
                    V[q] *= .995
            for q in range(len(P)):   # 口の壁
                x, y = P[q]; rq = rad[TI[q]]
                if y > RC * .95 and abs(abs(x) - gate) < rq: P[q, 0] = math.copysign(gate - rq, x) if abs(x) < gate else math.copysign(gate + rq, x); V[q, 0] *= -.3
        V *= .999; t += dt
        if int(t * FPS) >= len(frames): frames.append((P.copy(), TI.copy(), born.copy(), best))
    sim = Sim(sp, (-1.1, -1.12, 1.1, 1.62), area=(.02, .17, .98, .94))
    a0 = math.asin(gate / RC); arc = np.linspace(math.pi / 2 + a0, 2.5 * math.pi - a0, 160)
    for q in range(len(arc) - 1):   # 虹色のネオンの円（上の口だけ開ける）
        u = q / (len(arc) - 1); c = hsv((.75 - u) % 1); sim.neon([(RC * math.cos(arc[q]), RC * math.sin(arc[q])), (RC * math.cos(arc[q + 1]), RC * math.sin(arc[q + 1]))], color=c, glow=dim(c, .7), width=7)
    for sx in (-1, 1): sim.neon([(sx * gate, RC * math.cos(a0)), (sx * gate, RC + .5)], width=5)
    sim.title()
    for tt, k, _ in events: sim.note(intro + tt, PENTA[min(15, k * 2)], .55 + .05 * k, .5, 5 + k)
    sim.chord(intro + D + .1, [60, 64, 67, 72], gain=.55, dec=5)
    total = intro + D + tail; fN = F(40 * S); fL = F(26 * S); from simkit import W as W_, H as H_
    firsts = set(); top_ = 0
    for tt, k, _ in events:
        if k > top_: top_ = k; firsts.add((tt, k))
    def planet(d, x, y, r, k, a=1.0):
        name, base, kind = T[k]; c = tuple(int(v * a) for v in base); d.ellipse([x - r, y - r, x + r, y + r], fill=c)
        if kind == "bands":
            for q in range(-3, 4):
                yy = y + q * r * .26; w = math.sqrt(max(0, 1 - (q * .26) ** 2)) * r; d.line([x - w, yy, x + w, yy], fill=tuple(int(v * .78 * a) for v in base), width=max(1, int(r * .09)))
        if kind == "earth": d.ellipse([x - r * .5, y - r * .45, x + r * .1, y + r * .2], fill=tuple(int(v * a) for v in (70, 160, 90))); d.ellipse([x + r * .1, y + r * .1, x + r * .6, y + r * .55], fill=tuple(int(v * a) for v in (70, 160, 90)))
        if kind == "ring": d.ellipse([x - r * 1.7, y - r * .35, x + r * 1.7, y + r * .35], outline=tuple(int(v * a) for v in (230, 210, 160)), width=max(2, int(r * .12)))
        if kind == "sun":
            for q in range(3): rr_ = r * (1.12 + q * .12); d.ellipse([x - rr_, y - rr_, x + rr_, y + rr_], outline=tuple(int(v * a * (1 - q * .3)) for v in (255, 200, 80)), width=max(2, int(r * .05)))
        d.ellipse([x - r * .55, y - r * .7, x - r * .05, y - r * .25], fill=tuple(min(255, int(v * a + 40)) for v in base))   # つや
    for fi in range(int(total * FPS)):
        t = fi / FPS; k_ = min(len(frames) - 1, max(0, int((t - intro) * FPS))); PP, TT, BB, bst = frames[k_]; tsim = (t - intro)
        def draw(d, PP=PP, TT=TT, BB=BB, bst=bst, tsim=tsim):
            for q in range(len(PP)):
                x, y = sim.to(tuple(PP[q])); r = rad[TT[q]] * sim.k; age = tsim - BB[q]; pop = 1 + .35 * math.exp(-max(0, age) * 9) if TT[q] > 0 else 1
                planet(d, x, y, r * pop, TT[q])
            for tt, k, pos in events:
                e = tsim - tt
                if 0 <= e < .9 and k >= 2 and (tt, k) in firsts:   # 名前は、その段に初めて届いた時だけ（名前どうしが重ならないように）
                    x, y = sim.to(tuple(pos)); nm = T[k][0]; w = d.textlength(nm, font=fN); d.text((x - w / 2, y - rad[k] * sim.k - 60 * S - e * 30 * S), nm, font=fN, fill=(255, 255, 255), stroke_width=5 * S, stroke_fill=(0, 0, 0))
            # 上の段の並び：届いた段は色、まだの段は「？」
            n_ = K; bw = W_ * S * .9 / n_; y0 = max(H_ * S * .145, (getattr(sim, "label_y", 0) + 46) * S)   # 題名が2行のときは、その下へ（題名と重ねない）
            for k in range(K):
                x = W_ * S * .05 + bw * (k + .5)
                if k <= bst: planet(d, x, y0, bw * .32, k)
                else: d.rounded_rectangle([x - bw * .34, y0 - bw * .34, x + bw * .34, y0 + bw * .34], radius=8 * S, fill=(40, 44, 70)); w = d.textlength("?", font=fL); d.text((x - w / 2, y0 - 16 * S), "?", font=fL, fill=(170, 175, 210))
        fl = []
        for tt, k, pos in events:
            e = t - intro - tt
            if 0 <= e < .35: fl.append((tuple(pos), rad[k] * 260 * (1 + e * 3), dim((255, 250, 230), 1 - e / .35), 3))
        sim.frame(t, (), (), None, fl, draw)
    sim.finish(total)



def dominoes(sp):
    """1枚ごとに1.5倍大きいドミノ（オーナー画面収録 11/23「100,000 Dominoes」の型。実在の話：ドミノは自分より約1.5倍大きいドミノまで倒せる）。
    低いカメラが倒れる先を追う。大きいほどゆっくり倒れる（倒れる時間は高さの平方根に比例）→ 音の間かくが自然にのびる。音は大きいほど低い"""
    N, k_ = sp.get("n", 14), sp.get("ratio", 1.5); h0 = .2; H_ = [h0 * k_ ** i for i in range(N)]; z = [0.0]
    for i in range(1, N): z.append(z[-1] + .62 * H_[i - 1] + .12 * H_[i])
    intro, tail = .8, 3.4; Tf = [.42 * math.sqrt(h / h0) ** .9 for h in H_]; st = [intro]
    for i in range(1, N):   # 前のドミノの上の角が届いた瞬間に、次が倒れはじめる
        a = math.asin(min(.98, (z[i] - z[i - 1] - .16 * H_[i - 1]) / H_[i - 1])); u = math.sqrt(a / (math.pi / 2)); st.append(st[-1] + Tf[i - 1] * u)
    total = st[-1] + Tf[-1] + tail
    ang = lambda i, t: 0 if t < st[i] else min(math.pi / 2, math.pi / 2 * ((t - st[i]) / Tf[i]) ** 2)
    def lean(i, bj):   # ドミノ i が、角度 bj のドミノ i+1 の背中にもたれかかる角度（それ以上は倒れられない）（オーナー 11/23「ちゃんとドミノとして倒れ込んで」）
        hi, ti, hj, tj = H_[i], .16 * H_[i], H_[i + 1], .16 * H_[i + 1]; cb, sb = math.cos(bj), math.sin(bj)
        q0 = (tj * sb, z[i + 1] + tj * (1 - cb)); nv = (-sb, cb)   # i+1 の背面の線（y, z）と、前向きの法線
        def gap(a_): cy, cz = hi * math.cos(a_), z[i] + ti + hi * math.sin(a_); return (cy - q0[0]) * nv[0] + (cz - q0[1]) * nv[1]
        if gap(math.pi / 2) <= 0: return math.pi / 2
        lo, hi_ = 0.0, math.pi / 2
        for _ in range(30):
            m = (lo + hi_) / 2
            if gap(m) <= 0: lo = m
            else: hi_ = m
        return lo
    def angles(t):
        A = [ang(i, t) for i in range(N)]
        for i in range(N - 2, -1, -1): A[i] = min(A[i], lean(i, A[i + 1]))
        return A
    slerp = lambda a, b, u: a + (b - a) * u
    sstep = lambda a, b, x: (lambda k: k * k * (3 - 2 * k))(min(1, max(0, (x - a) / (b - a))))
    sim = Sim(sp, (0, 0, 1, 1))
    if sp.get("world"):   # 空と星は背景に先に描く（タイトルはその上）
        from simkit import W as _W, H as _H
        _d = ImageDraw.Draw(sim.bg); hy = _H * S * .60; _r = np.random.default_rng(7)
        for q in range(60):
            y0 = hy * q / 60; u = q / 59; _d.rectangle([0, y0, _W * S, y0 + hy / 60 + 1], fill=(int(6 + 40 * u * u), int(8 + 14 * u * u), int(22 + 60 * u * u)))
        for _ in range(160):
            sx, sy, sb = _r.random(), _r.random() * .55, _r.random(); r_ = (1 + 1.4 * sb) * S; cx, cy = sx * _W * S, sy * hy
            _d.ellipse([cx - r_, cy - r_, cx + r_, cy + r_], fill=(int(120 + 100 * sb), int(130 + 95 * sb), 255))
    sim.title()
    for i in range(N):
        sim.note(st[i], PENTA[max(0, 15 - i)], .55, .5, 5 + i * .4)
        if i >= 6: sim.note(st[i], 36, .3 + .04 * i, .5, 9, "kick")
    sim.note(st[-1] + Tf[-1], 36, .8, .5, 9, "kick"); sim.chord(st[-1] + Tf[-1] + .05, [48, 55, 60, 64, 67], gain=.6, dec=6)
    from simkit import W as W_, H as Hh
    cols = [hsv((.0 + .8 * i / (N - 1)) % 1) for i in range(N)]; fC = F(56 * S)
    WORLD = sp.get("world"); UCM = sp.get("unit_cm", 25.0); OBJ = []; fO = F(26 * S)
    if WORLD:   # 世界ごと作る（オーナー 11/23）：空・地平線・山なみ・星、横に大きさの目安（実寸）を立てる
        from PIL import Image as _Im
        for ob in sp.get("objects", []):
            icn, hcm, near, lab = ob[:4]; dz = ob[4] if len(ob) > 4 else 0; dx = ob[5] if len(ob) > 5 else 0
            im0 = _Im.open(os.path.join(os.path.dirname(__file__), "..", "nazo", "ballsim", "icons", icn + ".png")).convert("RGBA")
            bb = im0.getchannel("A").getbbox(); im0 = im0.crop(bb); hu = hcm / UCM; wu = hu * im0.width / im0.height
            OBJ.append(dict(im=im0, h=hu, w=wu, x=-(H_[near] * .55 + wu / 2 + H_[near] * (.3 + dx)), z=z[near] + H_[near] * (.1 + dz), lab=lab, near=near, col=hsv((.0 + .8 * near / (N - 1)) % 1)))
        rng_ = np.random.default_rng(7); STARS = [(rng_.random(), rng_.random() * .55, rng_.random()) for _ in range(140)]
        HILL = [(q / 60, .5 + .5 * math.sin(q * .37) * math.sin(q * .13 + 1) + .25 * math.sin(q * 1.3)) for q in range(61)]
    def hcm_txt(cm): return (f"{cm / 100:.1f}m" if cm >= 100 else f"{cm:.0f}cm") if sp.get("lang", "ja") == "ja" or True else ""
    for fi in range(int(total * FPS)):
        t = fi / FPS; cur = max([i for i in range(N) if t >= st[i]] or [0]); hc = H_[min(N - 1, cur + 1)]
        e = sstep(0, 1, (t - st[cur]) / max(.2, Tf[cur])) if cur < N - 1 else 1
        tz = slerp(z[cur], z[min(N - 1, cur + 1)], e) if cur < N - 1 else z[-1]; hh = slerp(H_[cur], H_[min(N - 1, cur + 1)], e)
        cam = (hh * 1.15, hh * .38, tz - hh * 2.6); fcl = W_ * S * 1.05
        def P3(x, y, zz):
            X, Y, Z = x - cam[0], y - cam[1], zz - cam[2]
            yaw = -.38; X, Z = X * math.cos(yaw) - Z * math.sin(yaw), X * math.sin(yaw) + Z * math.cos(yaw); Z = max(Z, 1e-3)
            return (W_ * S / 2 + fcl * X / Z, Hh * S * .60 - fcl * Y / Z), Z
        def draw(d, t=t):
            if WORLD:
                hy = Hh * S * .60
                off = (tz * .004) % 1
                for layer, (amp_, colh) in enumerate(((.10, (34, 22, 70)), (.06, (22, 16, 52)))):
                    pts = [(W_ * S * ((u - off * (1 + layer)) % 1.0001), hy - Hh * S * amp_ * v) for u, v in HILL]; pts.sort()
                    d.polygon([(0, hy)] + pts + [(W_ * S, hy)], fill=(8, 8, 22)); d.line(pts, fill=(90, 60, 200) if layer else (150, 90, 255), width=max(1, int((2 if layer else 3) * S)))
                for q in range(30):   # 地面：地平線から手前へ明るく
                    y0 = hy + (Hh * S - hy) * q / 30; u = q / 29; d.rectangle([0, y0, W_ * S, y0 + (Hh * S - hy) / 30 + 1], fill=(int(5 + 4 * u), int(5 + 3 * u), int(14 + 8 * u)))
                d.line([(0, hy), (W_ * S, hy)], fill=(120, 90, 220), width=max(1, int(2 * S)))
            kh = max([k for k in range(1, N) if t >= st[k]] or [0]); ag = t - st[kh] if kh else 9.0; tl = st[-1] + Tf[-1]; agl = t - tl
            pul = math.exp(-ag * 5) * (.5 + .5 * min(1, kh / 6)) + (1.6 * math.exp(-agl * 2.5) if agl >= 0 else 0)
            gc = tuple(min(255, int(v * (1 + 2.2 * pul))) for v in (46, 36, 120)); sp_ = hh * .35
            for q in range(-30, 60):   # 床のワイヤー：横の線（拍で明るく）
                zz = (math.floor((tz - hh * 3) / sp_) + q) * sp_; a, za = P3(-hh * 4, 0, zz); b, zb = P3(hh * 4, 0, zz)
                if za > .01 and zb > .01: d.line([a, b], fill=gc, width=max(1, int(1.5 * S)))
            for q in range(-12, 13):   # 縦のレーン
                xx = q * hh * .35; a, za = P3(xx, 0, tz - hh * 2.4); b, zb = P3(xx, 0, tz + hh * 30)
                if za > .01 and zb > .01: d.line([a, b], fill=gc if q else tuple(min(255, int(v * 1.6)) for v in gc), width=max(1, int((2.5 if q == 0 else 1.2) * S)))
            faces = []; AN = angles(t)
            for i in range(N):
                h = H_[i]; w = h * .5; th = h * .16; a = AN[i]; c, s_ = math.cos(a), math.sin(a)
                def R(x, y, zz): return (x, y * c - (zz - th) * s_, z[i] + th + y * s_ + (zz - th) * c)   # 手前下の辺を軸に、前へ倒れる
                pts = [R(x, y, zz) for x in (-w / 2, w / 2) for y in (0, h) for zz in (0, th)]
                pp = [P3(*p_) for p_ in pts]
                if min(q[1] for q in pp) < .02: continue
                for f_, sh in (((0, 2, 6, 4), .55), ((1, 3, 7, 5), .9), ((2, 3, 7, 6), 1.0), ((0, 1, 3, 2), .7), ((4, 5, 7, 6), .62)):
                    fl_ = math.exp(-(t - st[i]) * 7) if t >= st[i] else 0
                    poly = [pp[k][0] for k in f_]; dep = sum(pp[k][1] for k in f_) / 4; faces.append((dep, poly, (cols[i], sh, fl_)))
            for o in OBJ:
                o["vis"] = min(1, max(0, cur + e + 1.6 - o["near"]))
                if o["vis"] <= 0: continue
                (bx, by), zb_ = P3(o["x"], 0, o["z"]); (tx_, ty_), zt_ = P3(o["x"], o["h"], o["z"])
                if zb_ > .05 and zt_ > .05: faces.append((zb_ + 1e-3, ("img", o, bx, by, by - ty_), None))
            for dep, poly, col in sorted(faces, key=lambda f: -f[0]):
                if isinstance(poly, tuple) and poly and poly[0] == "img":
                    _, o, bx, by, hp = poly
                    if 6 < hp < Hh * S * 3:
                        wp = hp * o["im"].width / o["im"].height; im_ = o["im"].resize((max(1, int(wp)), max(1, int(hp))))
                        A = im_.getchannel("A"); _va = o["vis"]
                        fillc = _Im.new("RGBA", im_.size, tuple(int(v * .22) for v in o["col"]) + (255,)); fillc.putalpha(A.point(lambda v, _va=_va: int(v * .9 * _va)))
                        ed = A.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))   # ワイヤーの線画：ふちだけ光らせる
                        line_ = _Im.new("RGBA", im_.size, tuple(min(255, int(v * 1.1 + 40)) for v in o["col"]) + (255,)); line_.putalpha(ed.point(lambda v, _va=_va: int(min(255, v * 2) * _va)))
                        d._image.paste(fillc, (int(bx - wp / 2), int(by - hp)), fillc); d._image.paste(line_, (int(bx - wp / 2), int(by - hp)), line_)
                        lb = f'{o["lab"]} {hcm_txt(o["h"] * UCM)}'; lw_ = d.textlength(lb, font=fO)
                        if hp > 30 * S and o["vis"] > .6: d.text((min(W_ * S - lw_ - 10 * S, max(10 * S, bx - lw_ / 2)), by - hp - 34 * S), lb, font=fO, fill=(235, 238, 245), stroke_width=3 * S, stroke_fill=(0, 0, 0))
                    continue
                c0, sh, fl_ = col; fillc = tuple(int(v * (.16 * sh + .35 * fl_)) for v in c0)   # ワイヤー：中は暗く透け、ふちが光る
                edge = tuple(min(255, int(v * (1.0 + .6 * fl_) + 120 * fl_)) for v in c0)
                d.polygon(poly, fill=fillc); d.line(poly + [poly[0]], fill=dim(c0, .45), width=max(1, int(6 * S))); d.line(poly + [poly[0]], fill=edge, width=max(1, int(2.4 * S)))
            if kh and ag < .6:   # 当たった瞬間：光の輪と火花（音ゲーのヒット）
                hc_ = math.sqrt(max(0, H_[kh - 1] ** 2 - (z[kh] - z[kh - 1]) ** 2)); (cx, cy), cz = P3(0, hc_, z[kh])
                if cz > .05:
                    ph_ = fcl * H_[kh] / cz; r1 = ph_ * (.08 + .5 * ag / .6); al = 1 - ag / .6; c0 = cols[kh]
                    d.ellipse([cx - r1, cy - r1, cx + r1, cy + r1], outline=tuple(int(min(255, v * .5 + 128) * al) for v in c0), width=max(1, int(5 * S * al + 1)))
                    for j in range(12):
                        an = j * math.pi / 6 + kh; l0, l1 = r1 * .55, r1 * (.9 + .5 * al)
                        d.line([(cx + l0 * math.cos(an), cy + l0 * math.sin(an)), (cx + l1 * math.cos(an), cy + l1 * math.sin(an))], fill=tuple(int(255 * al) for _ in range(3)), width=max(1, int(2.5 * S)))
            if 0 <= agl < 1.6:   # 最後の巨人が倒れきった：地面に広がる光の輪
                al = 1 - agl / 1.6; R_ = H_[-1] * (.3 + 2.2 * agl / 1.6)
                ring = [P3(R_ * math.cos(u), 0, z[-1] + H_[-1] * .9 + R_ * math.sin(u)) for u in np.linspace(0, 2 * math.pi, 90)]
                ring = [p_ for p_, zz_ in ring if zz_ > .05]
                if len(ring) > 3: d.line(ring, fill=tuple(int(min(255, v * .6 + 110) * al) for v in cols[-1]), width=max(1, int(6 * S * al + 1)))
            tx = f"×{k_ ** max(0, cur):.0f}" if cur >= 1 else "×1"
            if WORLD: tx += "   " + hcm_txt(H_[cur] * UCM)
            fC2 = F(int(56 * S * (1 + .22 * math.exp(-min(ag, agl if agl >= 0 else 9) * 9)))); w = d.textlength(tx, font=fC2); d.text((W_ * S / 2 - w / 2, Hh * S * .80 - (fC2.size - fC.size) / 2), tx, font=fC2, fill=(255, 225, 90), stroke_width=6 * S, stroke_fill=(0, 0, 0))
        sim.frame(t, (), (), (sp.get("count_label", "Domino "), f"{cur + 1} / {N}"), (), draw)
    sim.finish(total)

def cupcaustic(sp):
    """丸いお椀（半円の壁）に上からまっすぐ落とす。放物線とちがい、全部は1点に集まらない。
    跳ね返った線が重なって、明るいカーブ（腎臓形 nephroid の一部。コーヒーカップの底の光の模様と同じ）が浮かぶ。
    ばらつきは入れない（自然な道の長さの差だけ）"""
    R, Y, v = 6.0, sp.get("Y", 9.0), sp.get("v", 7.0); XF = R + .15; YB = -R - .15
    ms = sp.get("rounds", [4, 8, 16, 32, 64, 128, 256]); XM = sp.get("xmax", .93); NB = sp.get("bounces", 2)
    intro, tail = .3, sp.get("tail", 2.0)
    sim = Sim(sp, (-XF, YB, XF, Y + .15))
    sim.neon([(R * math.cos(a), R * math.sin(a)) for a in np.linspace(math.pi, 2 * math.pi, 241)])
    sim.neon([(-R, Y), (R, Y)], width=5)
    sim.ring((0, -R / 2), 13); sim.title()
    def path(x):
        P = np.array([x, Y]); d = np.array([0.0, -1.0]); pts = [tuple(P)]
        hit = np.array([x, -math.sqrt(R * R - x * x)]); pts.append(tuple(hit)); P = hit
        for k in range(NB + 1):
            n_ = P / R; d = d - 2 * (d @ n_) * n_; d = d / np.linalg.norm(d)
            tq = -2 * (P @ d); Q = P + tq * d
            if Q[1] <= 1e-6 and k < NB: pts.append(tuple(Q)); P = Q; continue
            ts = [tt for tt in [((Y - P[1]) / d[1]) if d[1] > 1e-9 else None, ((XF - P[0]) / d[0]) if d[0] > 1e-9 else None,
                                ((-XF - P[0]) / d[0]) if d[0] < -1e-9 else None, (tq if Q[1] <= 1e-6 else None)] if tt is not None and tt > 1e-6]
            pts.append(tuple(P + min(ts) * d)); break
        cum = [0.0]
        for a_, b_ in zip(pts, pts[1:]): cum.append(cum[-1] + math.hypot(b_[0] - a_[0], b_[1] - a_[1]))
        return pts, cum
    rounds, t0 = [], intro
    for r, m in enumerate(ms):
        xs = [(-XM + 2 * XM * (j + .5) / m) * R for j in range(m)]; balls = []
        for x in xs:
            pts, cum = path(x); balls.append(dict(pts=pts, cum=cum, col=hsv((.55 + .45 * (x / R + 1) / 2) % 1), done=0))
        n = len(balls); D = max(b["cum"][-1] for b in balls) / v
        hits = sorted([(b["cum"][k] / v, b["pts"][k][0]) for b in balls for k in range(1, len(b["pts"]) - 1)])
        step = max(1, -(-len(hits) // 40)); g = .9 / math.sqrt(min(n, 40)); dec = 4 + 3 * math.sqrt(min(n, 64) / 5)
        sim.chord(t0, [60, 67, 72])
        for th, hx in hits[::step]: sim.note(t0 + th, PENTA[int((hx / R + 1) / 2 * 15 + .5)], g, .5 + .3 * hx / R, dec)
        rounds.append((t0, D, balls)); t0 += D + .15
    total = t0 + tail
    for fi in range(int(total * FPS)):
        t = fi / FPS; r = max([i for i, (a_, _, _) in enumerate(rounds) if t >= a_] or [0]); tr, D, balls = rounds[r]; s = max(0, t - tr) * v
        n = len(balls); lw = max(1.0, 2.0 * min(1, 10 / math.sqrt(n))); al = .34 * min(1, 5 / math.sqrt(n)) + .06
        segs = []
        if r > 0:
            for b in rounds[r - 1][2]:
                while b["done"] < len(b["pts"]) - 1: segs.append((b["pts"][b["done"]], b["pts"][b["done"] + 1], dim(b["col"], b.get("al", al)))); b["done"] += 1
        live, dots = [], []
        for b in balls:
            b["al"] = al; cum, pts = b["cum"], b["pts"]; L = len(pts) - 1; sc = min(s, cum[-1])
            while b["done"] < L and cum[b["done"] + 1] <= sc: segs.append((pts[b["done"]], pts[b["done"] + 1], dim(b["col"], al))); b["done"] += 1
            k = b["done"]; p = pts[-1] if k >= L else lerp(pts[k], pts[k + 1], (sc - cum[k]) / (cum[k + 1] - cum[k]))
            if k < L: live.append((pts[k], p, dim(b["col"], .7), lw))
            if k < L: dots.append((p, b["col"], 5 if n <= 32 else (4 if n <= 128 else 3)))
        sim.commit(segs, width=lw)
        sim.frame(t, live, dots, (sp.get("count_label", "ボール："), f"{n:,}"), [])
    sim.finish(total)


def hearts2(sp):
    """心拍を「2倍ずつの拍」にそろえて重ねる（参考：オーナー画面収録 11/23「Hearts Control the Beat」。作り直し 11/23：リズムと和音をそろえる）。
    ゾウ32・ヒト64・ネコ128・ウサギ256・ネズミ512・ハチドリ1024（回/分。およその値を2倍ずつにそろえた）＝ 1小節に 1・2・4・8・16・32 回。
    1拍ごとに、その小節の和音（C→G→Am→F）の中の1音。最後の行（クジラ、4回/分＝8小節に1回）が低く鳴って、画面が光る"""
    import harmony
    from PIL import Image, ImageChops
    from simkit import W as W_, H as H_
    rows = sp["rows"]; base = sp.get("base", 32); BAR = 60.0 / base; nA = len(rows) - 1
    enter = sp.get("enter", [0, 2, 4, 6, 8, 10])[:nA]; wh_in, wh_beat, end_bar = sp.get("whale_in", 11), sp.get("whale_beat", 12), sp.get("end_bar", 14)
    t0, tail = .12, sp.get("tail", 2.4); T_end = t0 + end_bar * BAR; total = T_end + tail; win = sp.get("window", 2.6)
    PROG = [(0, (0, 4, 7)), (7, (0, 4, 7)), (9, (0, 3, 7)), (5, (0, 4, 7))]   # C → G → Am → F（1小節ずつ）
    near = lambda pc, c: min(range(c - 6, c + 7), key=lambda m: ((m - pc) % 12 != 0) * 99 + abs(m - c))
    def pitch(i, bar, k):   # 行 i の、その小節の k 個目の拍の音（和音の中の音だけ）。大きい生きものほど低い
        r, q = PROG[bar % len(PROG)]
        if i == 0: return near(r, 41)
        if i == 1: return near(r, 52) if k % 2 == 0 else near(r + 7, 55)
        if i == 2: return [near(r + q[1], 64), near(r + q[2], 65), near(r, 69), near(r + q[2], 65)][k % 4]
        b = near(r, 72 if i == 3 else 76); T = [b, b + q[1], b + q[2], b + 12]
        if i == 3: return T[[0, 1, 2, 1, 3, 2, 1, 2][k % 8]]
        if i == 4: return T[[2, 3, 1, 3][k % 4]]
        return [T[3], T[2]][k % 2]
    GAIN = sp.get("gains", [.62, .50, .40, .28, .13, .055]); DEC = [2.0, 2.6, 3.6, 5.5, 10, 16]
    start = [t0 + enter[i] * BAR for i in range(nA)]; per = [BAR / 2 ** i for i in range(nA)]; tw = t0 + wh_beat * BAR; t_wh = t0 + wh_in * BAR
    sim = Sim(sp, (0, 0, 1, 1)); sim.title()
    on0 = harmony.ON; harmony.ON = False
    for i in range(nA):
        nb = int(round((T_end - start[i]) / per[i]))
        for j in range(nb):
            t = start[i] + j * per[i]; bar = int((t - t0) / BAR + 1e-6); k = int(round((t - t0 - bar * BAR) / per[i]))
            sim.note(t, pitch(i, bar, k), GAIN[i], .5 + (.0 if i < 2 else .28 * math.sin(i * 2.1 + k * .9)), DEC[i], "stone")
            if i == 0: sim.note(t, 36, .55, .5, 9, "kick")          # 心臓の「ドクン」：遅い2つだけ、低い太鼓を小さく重ねる
            if i == 1 and k % 2 == 1: sim.note(t, 36, .25, .5, 9, "kick")
    sim.note(tw, 36, 1.0, .5, 9, "kick"); sim.note(tw, 24, .9, .5, 1.0, "stone"); sim.note(tw, 36, .9, .5, 1.0, "stone")   # クジラ：いちばん低い音を長く
    for m in (48, 55, 60, 64, 67): sim.note(tw + .02, m, .22, .5, 1.6, "bell")
    for m in (36, 48, 55, 60, 64, 72): sim.note(T_end, m, .34, .5, 1.6, "bell")                                                # 終わりの和音
    sim.note(T_end, 36, .7, .5, 9, "kick")
    harmony.ON = on0
    ICON = {}
    for nm in set(r_[2] for r_ in rows): ICON[nm] = Image.open(os.path.join(os.path.dirname(__file__), "..", "nazo", "ballsim", "icons", nm + ".png")).convert("RGBA")
    top, bot = sp.get("top", .205), sp.get("bot", .87); fB = F(30 * S); fNm = F(24 * S); GREEN = tuple(sp.get("line_color", (84, 236, 164)))
    sst = lambda x: (lambda u: u * u * (3 - 2 * u))(min(1, max(0, x)))
    def ecg(ph):   # 1拍の形（0〜1）：小さな山 → 鋭い山 → 谷 → ゆるい山
        return (.12 * math.exp(-((ph - .18) / .03) ** 2) + 1.0 * math.exp(-((ph - .30) / .008) ** 2) - .28 * math.exp(-((ph - .33) / .01) ** 2) + .22 * math.exp(-((ph - .52) / .05) ** 2))
    def heart(d, x, y, r, c):
        d.ellipse([x - r, y - r * .9, x, y + r * .1], fill=c); d.ellipse([x, y - r * .9, x + r, y + r * .1], fill=c); d.polygon([(x - r * .98, y - r * .25), (x + r * .98, y - r * .25), (x, y + r)], fill=c)
    def level(i, tt):   # 行 i の、時刻 tt の線の高さ（0〜1）
        if i < nA:
            if tt < start[i] or tt >= T_end: return 0.0
            p_ = per[i]; c_ = (.30 if p_ > .2 else .5) * p_; u = (tt - start[i] + c_) % p_; sg = max(.008 * p_, .010)   # 鋭い山の幅は 0.01 秒より細くしない（速い生きものは、そろった櫛の形になる）
            v = math.exp(-((u - c_) / sg) ** 2)
            if p_ > .2: v += .12 * math.exp(-((u - .18 * p_) / (.03 * p_)) ** 2) - .28 * math.exp(-((u - .33 * p_) / (.01 * p_)) ** 2) + .22 * math.exp(-((u - .52 * p_) / (.05 * p_)) ** 2)
            return v * (.5 if i >= 5 else .62 if i == 4 else .8 if i == 3 else 1)
        e = tt - tw
        return ecg(.30 + e / 2.2) * 1.15 if -.66 < e < 1.5 else 0.0   # クジラ：1回だけ、ゆっくり大きく
    qs = 8; yy_, xx_ = np.mgrid[0:H_ * S // qs, 0:W_ * S // qs]
    for fi in range(int(total * FPS)):
        t = fi / FPS
        def draw(d, t=t):
            A = [sst((t - (start[i] - .30)) / .5) for i in range(nA)] + [sst((t - (t_wh - .30)) / .5)]
            m_eff = max(1.0, sum(A)); rh = min(.150, (bot - top) / m_eff); cum = 0.0; x0, x1 = W_ * S * .265, W_ * S * .935
            ew = t - tw
            for i in range(nA + 1):
                a = A[i]
                if a <= .01: continue
                yc = (top + rh * (cum + .56)) * H_ * S; cum += a; amp = rh * H_ * S * .36
                name, bpm, icn = rows[i][0], rows[i][1], rows[i][2]
                col = GREEN if i < nA or ew < 0 else tuple(int(GREEN[c_] + ((255, 110, 150)[c_] - GREEN[c_]) * math.exp(-ew * .9)) for c_ in range(3))
                pts = [(x0 + (x1 - x0) * q / 520, yc - amp * level(i, t - win * (1 - q / 520))) for q in range(521)]
                d.line(pts, fill=dim(col, .26 * a), width=int(9 * S)); d.line(pts, fill=dim(col, a), width=int(3.2 * S))
                d.ellipse([x1 - 6 * S, pts[-1][1] - 6 * S, x1 + 6 * S, pts[-1][1] + 6 * S], fill=dim((255, 255, 255), a))
                if i < nA: ab = ((t - start[i]) % per[i]) if start[i] <= t < T_end else 9.0; pulse = math.exp(-ab * 9) if per[i] >= .2 else (.25 if start[i] <= t < T_end else 0)
                else: pulse = math.exp(-ew * 2.2) if ew >= 0 else 0
                heart(d, W_ * S * .222, yc - 3 * S, 13 * S * (1 + .45 * pulse), dim((255, 64, 100), a))
                ic = ICON[icn]; sz = min(rh * H_ * S * .56, 124 * S) * (1 + .10 * pulse) * (.6 + .4 * a); iw, ih = int(sz * ic.width / max(ic.size)), int(sz * ic.height / max(ic.size))
                im_ = ic.resize((max(1, iw), max(1, ih)), Image.LANCZOS)
                if a < .999: im_.putalpha(im_.getchannel("A").point(lambda v, a=a: int(v * a)))
                d._image.paste(im_, (int(W_ * S * .105 - iw / 2), int(yc - 6 * S - ih / 2)), im_)
                w = d.textlength(name, font=fNm); d.text((W_ * S * .105 - w / 2, yc - 6 * S + sz / 2 + 2 * S), name, font=fNm, fill=dim((200, 205, 215), a))
                tx = f"{bpm:,} " + sp.get("unit", "bpm"); w = d.textlength(tx, font=fB); d.text((x1 - w, yc - amp - 40 * S), tx, font=fB, fill=dim((255, 255, 255), a), stroke_width=3 * S, stroke_fill=(0, 0, 0))
            if 0 <= ew < 3.0:   # クジラの1拍：心臓から赤い光が広がる
                hx, hy = W_ * S * .222 / qs, (top + rh * (m_eff - 1 + .56)) * H_ * S / qs; rad = W_ * S / qs * (.18 + 1.25 * min(1, ew / .5)); inten = math.exp(-ew * 1.5) * sp.get("flash", .85)
                g = np.clip(1 - np.hypot(xx_ - hx, yy_ - hy) / rad, 0, 1) ** 1.6 * inten
                gi = Image.fromarray((g[:, :, None] * np.array([255, 52, 96])[None, None, :]).astype(np.uint8), "RGB").resize((W_ * S, H_ * S), Image.BILINEAR)
                d._image.paste(ImageChops.add(d._image, gi))
        sim.frame(t, (), (), None, (), draw)
    bar0, can0 = harmony.BAR, harmony.CANON; harmony.BAR, harmony.CANON = BAR, PROG   # 持続音（bed）も同じ小節・同じ和音で
    try: sim.finish(total)
    finally: harmony.BAR, harmony.CANON = bar0, can0


def dominoes2(sp):
    """ドミノの道（参考：オーナー画面収録 11/23「100,000 Dominoes」。作り直し 11/23：たくさんのドミノが曲がる道に並び、少しずつ大きくなる。カメラが低く進む）。
    N 枚、最後が最初の total_ratio 倍（既定 105枚・100倍＝1枚ごとに約1.045倍）。倒れる時間は高さの平方根に比例 → 最初は連打、だんだんゆっくり低く。
    前のドミノは次のドミノの背中にもたれて止まる。世界はネオンのワイヤー（星空・山なみ・道の線）。横に実寸の目安の絵"""
    import bisect
    from PIL import Image
    from simkit import W as W_, H as Hh
    N = sp.get("n", 105); g = sp.get("total_ratio", 100.0) ** (1 / (N - 1)); UCM = sp.get("unit_cm", 5.0); TH, GAP = .16, sp.get("gap", .55)
    Hd = [g ** i for i in range(N + 1)]; amp, perd = sp.get("curve", .34), sp.get("curve_period", 34.0)
    th = [amp * math.sin(2 * math.pi * i / perd) for i in range(N + 2)]; P = [(0.0, 0.0)]; z = [0.0]
    for i in range(N + 1): P.append((P[-1][0] + GAP * Hd[i] * math.sin(th[i]), P[-1][1] + GAP * Hd[i] * math.cos(th[i]))); z.append(z[-1] + GAP * Hd[i])
    a_hit = math.asin(GAP - TH); kf = math.sqrt(a_hit / (math.pi / 2)); Tf0 = sp.get("first", .05) / kf; Tf = [Tf0 * math.sqrt(h) for h in Hd]
    intro, tail = .4, sp.get("tail", 2.6); st = [intro]
    for i in range(N - 1): st.append(st[-1] + Tf[i] * kf)   # 前のドミノの上の角が届いた瞬間に、次が倒れはじめる
    T_last = st[-1] + Tf[N - 1]; total = T_last + tail
    ang = lambda i, t: 0.0 if t < st[i] else min(math.pi / 2, math.pi / 2 * ((t - st[i]) / Tf[i]) ** 2)
    def lean(i, bj):   # ドミノ i が、角度 bj のドミノ i+1 の背中にもたれかかる角度
        hi, ti, tj = Hd[i], TH * Hd[i], TH * Hd[i + 1]; cb, sb = math.cos(bj), math.sin(bj); q0 = (tj * sb, z[i + 1] + tj * (1 - cb)); nv = (-sb, cb)
        def gap(a_): return (hi * math.cos(a_) - q0[0]) * nv[0] + (z[i] + ti + hi * math.sin(a_) - q0[1]) * nv[1]
        if gap(math.pi / 2) <= 0: return math.pi / 2
        lo, hi_ = 0.0, math.pi / 2
        for _ in range(26):
            m = (lo + hi_) / 2
            if gap(m) <= 0: lo = m
            else: hi_ = m
        return lo
    sim = Sim(sp, (0, 0, 1, 1))
    _d = ImageDraw.Draw(sim.bg)
    for q in range(80):   # 空：上が深い紺、下へ向かって紫（題名はこの上に描く）
        y0 = Hh * S * .8 * q / 80; u = min(1, q / 58); _d.rectangle([0, y0, W_ * S, y0 + Hh * S * .8 / 80 + 1], fill=(int(6 + 40 * u * u), int(8 + 14 * u * u), int(22 + 60 * u * u)))
    sim.title()
    import harmony
    on0 = harmony.ON; harmony.ON = False
    PEN = [84, 81, 79, 76, 74, 72, 69, 67, 64, 62, 60, 57, 55, 52, 50, 48, 45, 43, 40, 38, 36]   # 高い音から低い音へ（ドレミソラ）
    for i in range(N):
        u = i / (N - 1); sim.note(st[i], PEN[min(len(PEN) - 1, int(u * len(PEN)))], .20 + .42 * u, .5 + .3 * math.sin(i * .7), 6.5 - 4.0 * u, "stone")
        if u > .5: sim.note(st[i], 36, .15 + .75 * (u - .5) * 2, .5, 9, "kick")
    sim.note(T_last, 36, 1.0, .5, 9, "kick"); sim.note(T_last, 24, .8, .5, 1.2, "stone")
    for m in (36, 48, 55, 60, 64): sim.note(T_last + .03, m, .34, .5, 1.6, "bell")
    harmony.ON = on0
    OBJ = []
    for icn, hcm, lab in sp.get("objects", []):
        im0 = Image.open(os.path.join(os.path.dirname(__file__), "..", "nazo", "ballsim", "icons", icn + ".png")).convert("RGBA"); hu = hcm / UCM
        r_, g_, b_, a_ = im0.split(); im0 = Image.merge("RGBA", (r_.point(lambda v: int(v * .7)), g_.point(lambda v: int(v * .7)), b_.point(lambda v: int(v * .7)), a_))   # 絵は少し暗く（にじみで白く飛ばさない）
        k = min(N - 1, max(0, int(round(math.log(max(hu, 1.0)) / math.log(g))))); wu = hu * im0.width / im0.height
        fx, fz = math.sin(th[k]), math.cos(th[k]); off = (.67 if k >= N - 8 else .5) * Hd[k] + wu / 2   # 同じ高さのドミノのすぐ横に立てる。そのドミノが倒れたら消す（カメラが横を通るときに大きく映りすぎないように）。最後の1つは残す
        OBJ.append(dict(im=im0, h=hu, k=k, pos=(P[k][0] + fz * off, P[k][1] - fx * off), lab=lab, hcm=hcm))
    fC = F(58 * S); fO = F(28 * S); CX, CY, FL = W_ * S / 2, Hh * S * .56, W_ * S * .92; GAM = sp.get("cam_gamma", .82)
    fmt = lambda cm: (f"{cm / 100:.1f}m" if cm >= 100 else f"{cm:.0f}cm")
    rng_ = np.random.default_rng(7); STARS = [(rng_.random(), rng_.random(), rng_.random()) for _ in range(150)]
    prof = lambda a: .55 + .45 * math.sin(a * 7.0) * math.sin(a * 2.3 + 1) + .22 * math.sin(a * 23.0)
    cols = [hsv((i / sp.get("hue_period", 30.0)) % 1) for i in range(N + 1)]
    def path(fi):
        fi = min(max(fi, 0.0), N - 1e-6); i = int(fi); u = fi - i
        return P[i][0] + (P[i + 1][0] - P[i][0]) * u, P[i][1] + (P[i + 1][1] - P[i][1]) * u
    def head(fi):   # 道の向き（前後をならして、カメラがゆれないように）
        def avg(i0): return sum(th[min(N + 1, max(0, i0 + k))] for k in range(-6, 14)) / 20
        fi = min(max(fi, 0.0), N - 1e-6); i = int(fi); u = fi - i; return avg(i) * (1 - u) + avg(i + 1) * u
    for fi_ in range(int(total * FPS)):
        t = fi_ / FPS; cur = max(0, bisect.bisect_right(st, t) - 1); nxt = st[cur + 1] if cur < N - 1 else T_last
        ff = cur + min(1.0, max(0.0, (t - st[cur]) / (nxt - st[cur]))) if t >= st[0] else 0.0
        hf = g ** ff; He = hf ** GAM; ths = head(ff); fw = (math.sin(ths), math.cos(ths)); rt = (math.cos(ths), -math.sin(ths)); px, pz = path(ff)
        kb, kr, ku, ka = 4.4, 1.9, 1.55, 3.0
        C = (px - fw[0] * kb * He + rt[0] * kr * He, ku * He, pz - fw[1] * kb * He + rt[1] * kr * He)
        Tg = (px + fw[0] * ka * hf, .50 * hf, pz + fw[1] * ka * hf)
        ee = (lambda u: u * u * (3 - 2 * u))(min(1.0, max(0.0, (t - st[N - 1] - .2 * Tf[N - 1]) / (Tf[N - 1] + 1.3))))
        if ee > 0:   # 最後の1枚が倒れるあいだに、上をこえて前へ回りこみ、倒れてきた道をふり返る
            hN = Hd[N - 1]; fe = (math.sin(th[N - 1]), math.cos(th[N - 1])); re_ = (fe[1], -fe[0]); kb_ = N - 1 - 34
            C1 = (P[N - 1][0] + fe[0] * 2.3 * hN - re_[0] * .25 * hN, .82 * hN, P[N - 1][1] + fe[1] * 2.3 * hN - re_[1] * .25 * hN)
            T1 = (P[kb_][0] + re_[0] * .9 * hN, .16 * hN, P[kb_][1] + re_[1] * .9 * hN); bump = math.sin(math.pi * ee) * .45 * hN
            C = (C[0] + (C1[0] - C[0]) * ee, C[1] + (C1[1] - C[1]) * ee + bump, C[2] + (C1[2] - C[2]) * ee)
            Tg = tuple(Tg[q] + (T1[q] - Tg[q]) * ee for q in range(3))
        Fv = (Tg[0] - C[0], Tg[1] - C[1], Tg[2] - C[2]); ln = math.sqrt(sum(v * v for v in Fv)); Fv = tuple(v / ln for v in Fv)
        rl = math.hypot(Fv[2], Fv[0]); Rv = (Fv[2] / rl, 0.0, -Fv[0] / rl); Uv = (Fv[1] * Rv[2] - Fv[2] * Rv[1], Fv[2] * Rv[0] - Fv[0] * Rv[2], Fv[0] * Rv[1] - Fv[1] * Rv[0])
        near = .06 * He
        def PJ(x, y, zz, C=C, Fv=Fv, Rv=Rv, Uv=Uv):
            vx, vy, vz = x - C[0], y - C[1], zz - C[2]; zc = vx * Fv[0] + vy * Fv[1] + vz * Fv[2]
            if zc <= near: return None
            return (CX + FL * (vx * Rv[0] + vy * Rv[1] + vz * Rv[2]) / zc, CY - FL * (vx * Uv[0] + vy * Uv[1] + vz * Uv[2]) / zc, zc)
        lo_i, hi_i = max(0, cur - (34 if ee <= 0 else 104)), min(N - 1, cur + 46)
        A = {i: ang(i, t) for i in range(lo_i, min(N, hi_i + 2))}
        for i in range(min(N - 2, hi_i), lo_i - 1, -1):
            if A[i] > 0: A[i] = min(A[i], lean(i, A.get(i + 1, 0.0)))
        age = t - st[cur] if t >= st[0] else 9.0; agl = t - T_last; yaw = math.atan2(Fv[0], Fv[2])
        def draw(d, t=t, cur=cur, A=A, PJ=PJ, hf=hf, He=He, age=age, agl=agl, yaw=yaw, Fv=Fv, C=C, ff=ff):
            hl = math.hypot(Fv[0], Fv[2]); hp = PJ(C[0] + Fv[0] / hl * 1e5 * He, 0.0, C[2] + Fv[2] / hl * 1e5 * He); hy = min(Hh * S * .8, max(Hh * S * .2, hp[1] if hp else CY))
            for sx, sy, sb in STARS:
                tw = .55 + .45 * math.sin(t * (1.5 + sb * 3) + sb * 20); r_ = (1 + 1.4 * sb) * S; cx_, cy_ = ((sx - yaw * .5) % 1) * W_ * S, Hh * S * .20 + sy * max(0, hy - Hh * S * .22)
                d.ellipse([cx_ - r_, cy_ - r_, cx_ + r_, cy_ + r_], fill=tuple(int(v * tw) for v in (210, 220, 255)))
            for layer, (amp_, colf, coll) in enumerate(((.085, (9, 9, 26), (150, 90, 255)), (.05, (7, 7, 20), (90, 60, 200)))):   # 山なみ（ネオンの線）
                pts = [(W_ * S * q / 60, hy - Hh * S * amp_ * prof(yaw * (1 + layer * .3) + (q / 60 - .5) * 1.1 + layer * 2)) for q in range(61)]
                d.polygon([(0, hy)] + pts + [(W_ * S, hy)], fill=colf); d.line(pts, fill=coll, width=max(1, int((3 - layer) * S)))
            for q in range(30):
                y0 = hy + (Hh * S - hy) * q / 30; u = q / 29; d.rectangle([0, y0, W_ * S, y0 + (Hh * S - hy) / 30 + 1], fill=(int(5 + 4 * u), int(5 + 3 * u), int(14 + 8 * u)))
            d.line([(0, hy), (W_ * S, hy)], fill=(120, 90, 220), width=max(1, int(2 * S)))
            pul = math.exp(-age * 6) * (.35 + .65 * cur / N) + (1.6 * math.exp(-agl * 2.5) if agl >= 0 else 0); gc = tuple(min(255, int(v * (1 + 2.0 * pul))) for v in (50, 38, 128))
            LN = (-6.2, -4.3, -2.4, -.62, .62, 2.4, 4.3, 6.2); rails = [[] for _ in LN]
            for i in range(lo_i, hi_i + 2):   # 床のワイヤー：道にそった線（ドミノの両わきと、その外）と、ドミノごとの横の線
                fx, fz = math.sin(th[i]), math.cos(th[i]); hh_ = Hd[min(N, i)]
                for q, m_ in enumerate(LN): rails[q].append(PJ(P[i][0] + fz * m_ * hh_, 0, P[i][1] - fx * m_ * hh_))
                a_, b_ = rails[0][-1], rails[-1][-1]
                if a_ and b_ and (i % 2 == 0 or i > cur - 4): d.line([a_[:2], b_[:2]], fill=gc, width=max(1, int(1.2 * S)))
            for q, rail in enumerate(rails):
                inner = q in (3, 4)
                for a_, b_ in zip(rail[:-1], rail[1:]):
                    if a_ and b_: d.line([a_[:2], b_[:2]], fill=tuple(min(255, int(v * (1.6 if inner else 1.0))) for v in gc), width=max(1, int((2.2 if inner else 1.2) * S)))
            items = []
            for i in range(lo_i, hi_i + 1):
                h = Hd[i]; w = h * .5; tk = h * TH; a = A.get(i, 0.0); c, s_ = math.cos(a), math.sin(a); fx, fz = math.sin(th[i]), math.cos(th[i]); bx, bz = P[i]
                pp = []
                for u_ in (-w / 2, w / 2):
                    for v_ in (0, h):
                        for n_ in (0, tk):
                            vv = v_ * c - (n_ - tk) * s_; nn = tk + v_ * s_ + (n_ - tk) * c; pp.append(PJ(bx + fz * u_ + fx * nn, vv, bz - fx * u_ + fz * nn))
                if any(q is None for q in pp): continue
                fl_ = math.exp(-(t - st[i]) * 7) if t >= st[i] else 0.0; hpx = abs(pp[0][1] - pp[2][1]) + abs(pp[1][1] - pp[3][1])
                for f_, sh in (((0, 2, 6, 4), .55), ((1, 3, 7, 5), .9), ((2, 3, 7, 6), 1.0), ((0, 1, 3, 2), .7), ((4, 5, 7, 6), .62)):
                    items.append((sum(pp[k][2] for k in f_) / 4, 0, [pp[k][:2] for k in f_], (cols[i], sh, fl_, hpx)))
            for o in OBJ:
                vis = min(1.0, max(0.0, (cur + 16 - o["k"]) / 6.0)) * (1.0 if o["k"] >= N - 8 else min(1.0, max(0.0, (o["k"] + 3.5 - ff) / 2.5)))
                if vis <= 0: continue
                b_ = PJ(o["pos"][0], 0, o["pos"][1]); t_ = PJ(o["pos"][0], o["h"], o["pos"][1])
                if b_ and t_: items.append((b_[2], 1, (o, b_, b_[1] - t_[1], vis), None))
            for dep, kind_, geo, col in sorted(items, key=lambda q: -q[0]):
                if kind_ == 1:
                    o, b_, hp, vis = geo
                    if 8 * S < hp < Hh * S * 1.2:
                        wp = hp * o["im"].width / o["im"].height; im_ = o["im"].resize((max(1, int(wp)), max(1, int(hp))), Image.BILINEAR)
                        if vis < .999: im_.putalpha(im_.getchannel("A").point(lambda v, vis=vis: int(v * vis)))
                        d._image.paste(im_, (int(b_[0] - wp / 2), int(b_[1] - hp)), im_)
                        if hp > 46 * S and vis > .6:
                            lb = f'{o["lab"]} {fmt(o["hcm"])}'; lw_ = d.textlength(lb, font=fO); d.text((min(W_ * S - lw_ - 10 * S, max(10 * S, b_[0] - lw_ / 2)), b_[1] - hp - 38 * S), lb, font=fO, fill=(235, 238, 245), stroke_width=3 * S, stroke_fill=(0, 0, 0))
                    continue
                c0, sh, fl_, hpx = col; fillc = tuple(int(v * (.30 * sh + .40 * fl_)) for v in c0)   # 中は暗く透け、ふちが光る
                d.polygon(geo, fill=fillc)
                if hpx > 16 * S:
                    edge = tuple(min(255, int(v * (1.0 + .6 * fl_) + 120 * fl_)) for v in c0)
                    d.line(geo + [geo[0]], fill=dim(c0, .42), width=max(1, int(5 * S))); d.line(geo + [geo[0]], fill=edge, width=max(1, int(2.2 * S)))
                else: d.line(geo + [geo[0]], fill=dim(c0, .8 + .2 * fl_), width=max(1, int(1.2 * S)))
            for i in range(max(1, cur - 1), cur + 1):   # 当たった瞬間：小さな光の輪と火花（連打のあいだは出さない）
                ag = t - st[i]
                if not (0 <= ag < .32) or Tf[i] * kf < .12: continue
                hc_ = Hd[i - 1] * math.cos(a_hit); q = PJ(P[i][0], hc_, P[i][1])
                if not q: continue
                ph_ = FL * Hd[i] / q[2]; r1 = ph_ * (.03 + .13 * ag / .32); al = 1 - ag / .32; c0 = cols[i]
                d.ellipse([q[0] - r1, q[1] - r1, q[0] + r1, q[1] + r1], outline=tuple(int(min(255, v * .5 + 128) * al) for v in c0), width=max(1, int(4 * S * al + 1)))
                for j in range(10):
                    an = j * math.pi / 5 + i; l0, l1 = r1 * .55, r1 * (.9 + .5 * al)
                    d.line([(q[0] + l0 * math.cos(an), q[1] + l0 * math.sin(an)), (q[0] + l1 * math.cos(an), q[1] + l1 * math.sin(an))], fill=tuple(int(255 * al) for _ in range(3)), width=max(1, int(2.2 * S)))
            if 0 <= agl < 1.6:   # 最後の1枚が倒れきった：地面に広がる光の輪
                al = 1 - agl / 1.6; R_ = Hd[N - 1] * (.3 + 2.0 * agl / 1.6); fx, fz = math.sin(th[N - 1]), math.cos(th[N - 1]); cx0, cz0 = P[N - 1][0] + fx * Hd[N - 1] * .7, P[N - 1][1] + fz * Hd[N - 1] * .7
                ring = [PJ(cx0 + R_ * math.cos(u), 0, cz0 + R_ * math.sin(u)) for u in np.linspace(0, 2 * math.pi, 90)]; ring = [q[:2] for q in ring if q]
                if len(ring) > 3: d.line(ring, fill=tuple(int(min(255, v * .6 + 110) * al) for v in cols[N - 1]), width=max(1, int(6 * S * al + 1)))
            tx = sp.get("height_label", "高さ ") + fmt(Hd[cur] * UCM); pop = math.exp(-min(age, agl if agl >= 0 else 9) * 9) if (cur > N * .45 or agl >= 0) else 0
            fC2 = F(int(58 * S * (1 + .2 * pop))); w = d.textlength(tx, font=fC2); d.text((W_ * S / 2 - w / 2, Hh * S * .815 - (fC2.size - fC.size) / 2), tx, font=fC2, fill=(255, 225, 90), stroke_width=6 * S, stroke_fill=(0, 0, 0))
        sim.frame(t, (), (), (sp.get("count_label", "ドミノ "), f"{cur + 1} / {N}"), (), draw)
    sim.finish(total)


def spiralglass(sp):
    """うずまきのガラスを全部割る（参考：オーナー画面収録 11/23「How many balls to break it ALL?」）。
    うずまきの道に、ガラスが 2^rounds − 1 枚（既定 255枚）。毎回、ボールが1個、外から道を流れてくる。入口の点を通ると n 倍にふえる（×1→×2→×4→…→×128）。ふえたボールは1個につき1枚のガラスを割って消える。
    （オーナー 11/23「1個の球が流れてきて、ポイントを通るとn倍になる感じがいい。チェックポイントから発射するのではなくて」→ 入口に戻って待つ作りをやめ、流れ抜ける作りにした）
    割れる間かくは一定（32分音符）なので、1・2・4・8…と長くなる連打になる。音は和音の中の音を上り下り（カロッ）。割れたガラスは破片になって飛ぶ"""
    import harmony
    from simkit import W as W_, H as H_
    RN = sp.get("rounds", 8); NT = 2 ** RN - 1; Rr, bb, r_end = 1.0, sp.get("lane", .17), .07; v = sp.get("v", 10.0); tau = sp.get("tau", .0625); gate = .35
    thmax = 2 * math.pi * (Rr - bb / 2 - r_end) / bb; TH_ = np.linspace(0, thmax, 24000); RC = Rr - bb * TH_ / (2 * math.pi) - bb / 2
    SS = np.cumsum(np.sqrt(RC ** 2 + (bb / (2 * math.pi)) ** 2) * np.gradient(TH_)); Lt = (SS[-1] - gate) / NT
    th_of = lambda s_: float(np.interp(s_, SS, TH_)); pos_th = lambda th_, off=0.0: ((Rr - bb * th_ / (2 * math.pi) - bb / 2 + off) * math.cos(-math.pi / 2 + th_), (Rr - bb * th_ / (2 * math.pi) - bb / 2 + off) * math.sin(-math.pi / 2 + th_))
    th_in = sp.get("entry", -1.25) * math.pi; TE = np.linspace(th_in, 0, 3000); RE = Rr - bb * TE / (2 * math.pi) - bb / 2   # 入口までの道（うずまきを外へ1周ぶん近くのばした所）
    SE = np.cumsum(np.sqrt(RE ** 2 + (bb / (2 * math.pi)) ** 2) * np.gradient(TE)); Le = float(SE[-1]); SE = SE - Le; p_end = pos_th(th_in); p_e2 = pos_th(th_in + .02)
    dl = math.hypot(p_end[0] - p_e2[0], p_end[1] - p_e2[1]); dirb = ((p_end[0] - p_e2[0]) / dl, (p_end[1] - p_e2[1]) / dl); APP = 1.3   # 道の端より前は、まっすぐ外から入ってくる
    def pos_s(s_):
        if s_ >= 0: return pos_th(th_of(s_))
        if s_ >= -Le: return pos_th(float(np.interp(s_, SE, TE)))
        return (p_end[0] + dirb[0] * (-Le - s_), p_end[1] + dirb[1] * (-Le - s_))
    S0 = [gate + n * Lt for n in range(NT + 1)]; TB = [th_of(s_) for s_ in S0]
    # ガラス1枚ずつの形と色（色は向きで決める＝色の輪をうずまきに切った見た目）
    tiles = []
    for n in range(NT):
        ta, tb = TB[n], TB[n + 1]; m = max(2, int(math.ceil((tb - ta) / .045)) + 1); us = [ta + (tb - ta) * q / (m - 1) for q in range(m)]; mg = .016
        outer = [pos_th(u, bb / 2 - mg) for u in us]; inner = [pos_th(u, -bb / 2 + mg) for u in us]; sheen = [pos_th(u, bb / 2 - mg - .03) for u in us]
        tm = (ta + tb) / 2; hue = ((-math.pi / 2 + tm) / (2 * math.pi)) % 1
        tiles.append(dict(poly=outer + inner[::-1], sheen=sheen, col=hsv(hue, .78, 1), c=pos_th(tm), th=tm))
    # 当たる時刻：回ごとに 2^k 個。間かく tau で次のガラスへ。出る時刻は、当たる時刻から道のりぶん戻して決める
    intro, tail = .1, sp.get("tail", 2.6); balls = []; hits = []; rstart = []; leads = []; tprev = intro + (Le + APP) / v
    for k in range(RN):
        n0 = 2 ** k - 1; H0 = tprev + S0[n0] / v; grid = .25 if k < 3 else .5; H0 = math.ceil((H0 - 1e-6) / grid) * grid
        g_ = H0 - S0[n0] / v; rstart.append((g_, 2 ** k)); leads.append(g_)   # g_：流れてきた1個が入口の点を通る時刻
        for j in range(2 ** k):
            n = n0 + j; h = H0 + j * tau; d_ = S0[n]; balls.append(dict(dep=h - d_ / v, hit=h, d=d_, k=k, j=j)); hits.append((h, n, j, k))
        tprev = H0 + (2 ** k - 1) * tau + .18 - S0[min(NT - 1, 2 ** (k + 1) - 1)] / v   # 次の1個は、前の回の最後の1枚が割れるころに着くように流れてくる
        tprev = max(tprev, g_ + .2)
    T_last = hits[-1][0]; total = T_last + tail
    sim = Sim(sp, (-1.22, -1.22, 1.22, 1.22))
    sim.neon([pos_th(u, bb / 2) for u in np.linspace(th_in, thmax + 2 * math.pi * .999, 1000)], width=4); sim.title()   # うずまきの壁（入口までの道も同じ1本の線）
    on0 = harmony.ON; harmony.ON = False
    for h, n, j, k in hits:   # 割れる音：その時の和音の中の音を、上って下りる
        r, q = harmony.CANON[int(h / harmony.BAR) % len(harmony.CANON)]; T = [60 + r, 60 + r + q[1], 60 + r + q[2], 72 + r, 72 + r + q[1], 72 + r + q[2], 84 + r]
        m = T[[0, 1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1][j % 12]]
        while m > 91: m -= 12
        x, y = tiles[n]["c"]; sim.note(h, m, .34 if k < 5 else .28, .5 + .35 * x, 5.0, "karo")
    b = 0.0
    while b < T_last:   # 裏の拍：連打が鳴っている間だけ、やわらかい低い太鼓
        if any(rs + S0[2 ** kk - 1] / v - .01 <= b <= rs + S0[2 ** kk - 1] / v + (cnt - 1) * tau + .01 for kk, (rs, cnt) in enumerate(rstart) if cnt >= 4): sim.note(b, 36, .5, .5, 9, "kick")
        b += .5
    for kk, (rs, cnt) in enumerate(rstart):
        sim.note(rs, 72 + harmony.CANON[int(rs / harmony.BAR) % len(harmony.CANON)][0], .2, .5, 4, "bell")   # 点を通ってふえる合図
    sim.note(T_last + tau, 36, 1.0, .5, 9, "kick")
    for m in (48, 55, 60, 64, 67, 72, 76): sim.note(T_last + tau, m, .30, .5, 1.6, "bell")
    harmony.ON = on0
    rng = np.random.default_rng(sp.get("seed", 5)); shards = []; broke = [None] * NT
    for h, n, j, k in hits: broke[n] = h
    fB = F(38 * S); gx, gy = pos_th(0); WALL_ = [sim.to(pos_th(u, bb / 2)) for u in np.linspace(th_in, thmax + 2 * math.pi * .999, 460)]
    hit_i = 0; hits_sorted = sorted(hits)
    for fi in range(int(total * FPS)):
        t = fi / FPS
        while hit_i < len(hits_sorted) and hits_sorted[hit_i][0] <= t:   # 割れた：破片を飛ばす
            h, n, j, k = hits_sorted[hit_i]; hit_i += 1; tl = tiles[n]; cx, cy = tl["c"]; rad = math.hypot(cx, cy) + 1e-9; ux, uy = cx / rad, cy / rad; tx, ty = -uy, ux
            for _ in range(sp.get("shards", 5)):
                sz = bb * rng.uniform(.12, .30); a0 = rng.uniform(0, 6.28)
                shards.append(dict(t0=h, p=(cx + rng.uniform(-.03, .03), cy + rng.uniform(-.03, .03)), v=(ux * rng.uniform(.1, .9) + tx * rng.uniform(-.2, 1.0) + rng.uniform(-.25, .25), uy * rng.uniform(.1, .9) + ty * rng.uniform(-.2, 1.0) + rng.uniform(.1, .6)),
                                   sz=sz, a=a0, w=rng.uniform(-9, 9), col=tuple(int(c_ * .5 + 255 * .5) for c_ in tl["col"]), life=rng.uniform(.5, .95)))
        shards = [s_ for s_ in shards if t - s_["t0"] < s_["life"]]
        nb = sum(1 for h_ in broke if h_ is not None and h_ <= t)
        rk = max([kk for kk, (rs, cnt) in enumerate(rstart) if t >= rs] or [-1]); rs_age = t - rstart[rk][0] if rk >= 0 else 9.0
        def draw(d, t=t, nb=nb, rk=rk, rs_age=rs_age, shards=list(shards)):
            agl = t - T_last
            if agl > 0:   # 全部割れた：うずまきの壁が虹色に光る
                k_ = min(1.0, agl / .5); 
                for q in range(len(WALL_) - 1):
                    u = q / (len(WALL_) - 1); d.line([WALL_[q], WALL_[q + 1]], fill=dim(hsv((u * 2.5 - t * .25) % 1, .75, 1), k_), width=max(1, int(5 * S)))
            for n in range(NT):   # 残っているガラス
                if broke[n] is not None and broke[n] <= t: continue
                tl = tiles[n]; near_ = (n == nb); c = tl["col"]; P_ = [sim.to(p_) for p_ in tl["poly"]]
                d.polygon(P_, fill=dim(c, (.66 if n % 2 else .58) if not near_ else .85), outline=(8, 10, 24))
                d.line([sim.to(p_) for p_ in tl["sheen"]], fill=tuple(min(255, int(c_ * .8 + 70)) for c_ in c), width=max(1, int(1.6 * S)))
            for s_ in shards:   # 破片：回りながら飛んで、落ちて、消える
                e = t - s_["t0"]; al = max(0.0, 1 - e / s_["life"]); x = s_["p"][0] + s_["v"][0] * e; y = s_["p"][1] + s_["v"][1] * e - .9 * e * e; a = s_["a"] + s_["w"] * e
                k_ = s_["sz"] * (.35 + .65 * al)   # 消えるときは暗くせず、小さくする（にごらせない）
                tri = [sim.to((x + k_ * math.cos(a + q * 2.094) * (1 if q else 1.5), y + k_ * math.sin(a + q * 2.094) * (1 if q else 1.5))) for q in range(3)]
                if min(p_[1] for p_ in tri) < H_ * S * .205: continue   # 題名と数字の上には飛ばさない
                d.polygon(tri, fill=dim(s_["col"], .55 + .45 * al))
            for h, n, j, k in hits_sorted:   # 割れた瞬間の光
                e = t - h
                if e < 0: break
                if e < .14: x, y = sim.to(tiles[n]["c"]); r_ = (10 + 150 * e) * S; d.ellipse([x - r_, y - r_, x + r_, y + r_], outline=dim((255, 250, 235), 1 - e / .14), width=max(1, int(3 * S)))
            for b_ in balls:   # ふえたボール：入口の点から、割るガラスまで（割ったら消える）
                if not (b_["dep"] <= t <= b_["hit"]): continue
                s_ = (t - b_["dep"]) * v
                for q in range(4, -1, -1):   # 尾
                    sq = s_ - q * .035
                    if sq < 0: continue
                    x, y = sim.to(pos_s(sq)); r_ = (7.5 - q * 1.1) * S
                    d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=dim((255, 246, 230) if q == 0 else (255, 150, 110), 1 - q * .2))
            for g_ in leads:   # 流れてくる1個：外から道に入り、入口の点まで（点を通ると、ふえたボールに引きつがれる）
                if not (g_ - (Le + APP) / v <= t < g_): continue
                s_ = -(g_ - t) * v
                for q in range(9, -1, -1):
                    x, y = sim.to(pos_s(s_ - q * .045)); r_ = (11 - q * .95) * S
                    d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=dim((255, 250, 240) if q == 0 else (255, 170, 120), 1 - q * .095))
            rkn = min(RN - 1, rk + 1) if (rk < 0 or (rk + 1 < RN and t >= leads[rk + 1] - (Le + APP) / v)) else rk   # 次の1個が流れてきたら、次の倍率を出しておく
            x, y = sim.to((gx, gy)); pr = 1 + .35 * math.exp(-max(0, rs_age) * 7); r_ = 38 * S * pr; c = hsv((.08 + rkn * .13) % 1, .7, 1)   # 入口の点：ここを通ると何倍になるか
            if 0 <= rs_age < .3: rr_ = (40 + 260 * rs_age) * S; d.ellipse([x - rr_, y - rr_, x + rr_, y + rr_], outline=dim((255, 250, 235), 1 - rs_age / .3), width=max(1, int(4 * S)))
            d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=dim(c, .9), outline=(255, 255, 255), width=max(1, int(2 * S)))
            tx_ = f"×{2 ** rkn}"; fb_ = fB if len(tx_) <= 3 else F(int((30 if len(tx_) == 4 else 25) * S)); w = d.textlength(tx_, font=fb_); d.text((x - w / 2, y - fb_.size * .68), tx_, font=fb_, fill=(20, 16, 30))
        sim.frame(t, (), (), (sp.get("count_label", "割れたガラス "), f"{nb} / {NT}"), (), draw)
    sim.finish(total)


def dots45(sp):
    """2つの点と、たて・よこの格子（参考：オーナー画面収録 11/23「Every dot = 2 balls」。作り直し 11/23）。
    下の放物線（焦点 B）、右の放物線（焦点 A）、ななめ45度の鏡。B から打ったボールは、下の放物線でまっすぐ上へ、鏡で右へ、右の放物線で A に集まる。
    道の長さはどの向きも 2c+4f で同じ＝同時に着く。点に着くたびに2倍。残った線が、たて・よこの格子になる。ばらつきは入れない（当たる順は道の形で決まる）"""
    import harmony
    from simkit import W as W_, H as H_
    from PIL import Image
    f, c = 1.0, sp.get("c", 6.0); U = 2 * math.sqrt(f * f + f * (c + f)) - 2 * f; um, uM = 4 * f * f / U * 1.05, U * .985
    ms = sp.get("rounds", [2 ** k for k in range(12)]); T = sp.get("leg", 1.8); v = (2 * c + 4 * f) / T; intro, tail = .04, sp.get("tail", 2.4)
    Pp = lambda u: (u, u * u / (4 * f) - f); Mp = lambda u: (u, u + c); Qp = lambda u: (c + f - u * u / (4 * f), u + c); B, A = (0.0, 0.0), (c, c)
    STOPS = [(255, 120, 205), (176, 124, 255), (96, 200, 255), (255, 196, 130)]   # ピンク → むらさき → 水色 → もも色（淡い色）
    def colu(u):
        x = (u + U) / (2 * U) * (len(STOPS) - 1); i = min(len(STOPS) - 2, int(x)); k = x - i; return tuple(int(STOPS[i][q] + (STOPS[i + 1][q] - STOPS[i][q]) * k) for q in range(3))
    sim = Sim(sp, (-U - .25, -f - .25, c + f + .25, c + U + .25), area=(.04, .19, .96, .80))
    GOLD, GGL = (255, 214, 150), (110, 76, 30)
    sim.neon([Pp(x) for x in np.linspace(-U, U, 161)], color=GOLD, glow=GGL, width=3); sim.neon([Qp(w) for w in np.linspace(-U, U, 161)], color=GOLD, glow=GGL, width=3)
    sim.neon([(-U, c - U), (U, c + U)], color=GOLD, glow=GGL, width=3); sim.ring(B, 11); sim.ring(A, 11); sim.title()
    bar0 = harmony.BAR; harmony.BAR = T
    try:
        rounds = []
        for r, m in enumerate(ms):
            t0 = intro + r * T; us = [1.9] if m == 1 else [s_ * (um + (uM - um) * (j + .5) / (m // 2)) for s_ in (1, -1) for j in range(m // 2)]; balls = []
            for u in us:
                l1 = u * u / (4 * f) + f; l2 = (u + c) - (u * u / (4 * f) - f); l3 = c + f - u * u / (4 * f) - u; pts = [B, Pp(u), Mp(u), Qp(u), A]; ls = [l1, l2, l3, l1]
                if r % 2: pts = pts[::-1]; ls = ls[::-1]
                cum = [0.0]
                for l_ in ls: cum.append(cum[-1] + l_)
                balls.append(dict(pts=pts, cum=cum, col=colu(u), u=u, done=0))
            n = len(balls); stp = max(1, int(math.ceil(n * 3 / 36)))   # 音は1区間に36個まで
            hitl = sorted((t0 + b["cum"][q] / v, b["pts"][q], b["u"]) for b in balls for q in (1, 2, 3))
            for th_, p_, u_ in hitl[::stp]: sim.note(th_, PENTA[int((u_ + U) / (2 * U) * 15 + .5)], .8 / math.sqrt(min(n * 3, 36)), .5 + .4 * (p_[0] - c / 2) / (c / 2 + U), 4 + 2 * math.sqrt(min(n, 36) / 5), "karo")
            sim.chord(t0, [48, 60, 67], gain=.3); sim.note(t0, 36, .55, .5, 9, "kick"); rounds.append((t0, balls))
        t_end = intro + len(ms) * T; total = t_end + tail
        sim.chord(t_end, [48, 55, 60, 64, 67, 72], gain=.42, dec=2.2, kind="bell"); sim.note(t_end, 36, .9, .5, 9, "kick")
        sim.notes = [nt for nt in sim.notes if nt[0] < total - .02]
        fN = F(150 * S); cxn, cyn = W_ * S / 2, H_ * S * .80; cur_r = -1; FADE = sp.get("fade", .55); band = (uM - um) * sim.k
        ALF = lambda n_, lw_: min(.46, sp.get("line_sum", 52.0) / (255.0 * max(1e-9, (n_ / 2) / band) * max(1, int(lw_ * S))))   # 線1本の明るさ：1区間ぶんを重ねても決まった明るさまで
        for fi in range(int(total * FPS)):
            t = fi / FPS; r = min(len(rounds) - 1, max(0, int((t - intro) // T))); t0, balls = rounds[r]; s = max(0.0, t - t0) * v; segs = []; n = len(balls)
            lw = max(1.0, 1.7 * min(1, 9 / math.sqrt(n))); al = ALF(n, lw)
            if r != cur_r:   # 新しい区間に入るたび、前の線を少し暗くする（重なって白く飛ばないように）
                cur_r = r
                if r > 0: sim.acc = Image.eval(sim.acc, lambda v_: int(v_ * FADE))
            if r > 0:
                pr = rounds[r - 1][1]; alp = ALF(len(pr), max(1.0, 1.7 * min(1, 9 / math.sqrt(len(pr)))))
                for b in pr:
                    while b["done"] < 4: segs.append((b["pts"][b["done"]], b["pts"][b["done"] + 1], dim(b["col"], alp))); b["done"] += 1
            live, dots, fl = [], [], []; ntail = 4 if n <= 64 else 2 if n <= 512 else 0; rad = 5.2 if n <= 32 else 4.2 if n <= 256 else 2.6
            for b in balls:
                cum, pts = b["cum"], b["pts"]; sc = min(s, cum[-1])
                while b["done"] < 4 and cum[b["done"] + 1] <= sc: segs.append((pts[b["done"]], pts[b["done"] + 1], dim(b["col"], al))); b["done"] += 1
                k = b["done"]
                if k >= 4: continue
                pnt = lerp(pts[k], pts[k + 1], (sc - cum[k]) / (cum[k + 1] - cum[k])); live.append((pts[k], pnt, dim(b["col"], .8 * min(1, 7 / math.sqrt(n))), lw))
                for q in range(ntail, 0, -1):   # 尾（ほうき星の形）：来た道を少し戻った所に、小さく暗い玉
                    sq = sc - q * .16
                    if sq <= 0: continue
                    kk = max(i for i in range(4) if cum[i] <= sq); dots.append((lerp(pts[kk], pts[kk + 1], (sq - cum[kk]) / (cum[kk + 1] - cum[kk])), dim(b["col"], 1 - q * .2), rad * (1 - q * .17)))
                dots.append((pnt, tuple(min(255, int(c_ * .5 + 128)) for c_ in b["col"]) if n <= 256 else dim(b["col"], .75), rad if n <= 256 else 1.7))
                e = (sc - cum[k]) / v
                if k in (1, 2, 3) and e < .18 and n <= 64: fl.append((pts[k], 7 + e * 60, dim(b["col"], 1 - e / .18), 2))
            sim.commit(segs, width=lw)
            ag = t - t0 if t < t_end else t - t_end; dot_ = (B, A)[r % 2] if t < t_end else (B, A)[len(ms) % 2]; pulse = math.exp(-ag * 5)
            fl.append((dot_, 12 + 46 * pulse, dim((255, 236, 190), .25 + .75 * pulse), 4))
            cnt = n if t < t_end else n
            def draw(d, cnt=cnt, pulse=pulse):   # 数を、図の下に大きく
                tx = f"{cnt:,}"; fz = F(int(150 * S * (1 + .12 * pulse))); w = d.textlength(tx, font=fz); d.text((cxn - w / 2, cyn - fz.size * .1), tx, font=fz, fill=(255, 255, 255), stroke_width=6 * S, stroke_fill=(0, 0, 0))
            sim.frame(t, live, dots, None, fl, draw)
        sim.finish(total)
    finally: harmony.BAR = bar0


def circlefill(sp):
    """はねるたびに円のふちを1区画ぬり、旋律が1音進む（オーナー画面収録 11/23「WILL IT FILL THE WHOLE CIRCLE?」の型。鍵盤つき）。
    法則：円の中のボールは、はね返るたびに同じ長さの道（弦）を進む＝同じ間かくで当たる。1回で 3/8 周進むので、8回でちょうど1周ぶんの区画がうまる。
    1周ぬり終わるたびにボールが2倍（半拍ずれ・半区画ずれの同じ形の道）。当たる間かくは 4分→8分→16分→32分 と細かくなる。曲はパッヘルベル「カノン」（著作権なし）"""
    T = sp.get("beat", .75); t0 = sp.get("intro", .75); NL = sp.get("layers", 4); th0 = math.pi / 2; tail = sp.get("tail", 2.8)
    FR = [0, .5, .25, .75, .125, .625, .375, .875][:2 ** (NL - 1)]   # ボールごとのずれ（時間は拍の何分の1、場所は区画の何分の1）
    MEL = [[76, 74, 72, 71, 69, 67, 69, 71],
           [72, 76, 79, 77, 76, 72, 76, 74, 72, 69, 72, 79, 77, 81, 79, 77],
           [79, 76, 72, 76, 74, 71, 67, 71, 72, 69, 64, 69, 71, 67, 64, 67, 69, 65, 60, 65, 67, 64, 60, 64, 69, 65, 69, 72, 71, 74, 77, 79],
           [72, 74, 76, 77, 79, 77, 76, 74, 71, 74, 77, 79, 83, 79, 77, 74, 69, 72, 76, 81, 76, 72, 69, 72, 67, 71, 76, 79, 76, 71, 67, 71,
            65, 69, 72, 77, 72, 69, 65, 69, 64, 67, 72, 76, 72, 67, 64, 67, 65, 69, 72, 77, 81, 77, 72, 69, 67, 71, 74, 79, 77, 74, 71, 74]]
    MJ_, MN_ = (0, 4, 7), (0, 3, 7); prog = None
    SONGS = {   # 曲ごとの「骨組み8音・旋律16音・和音8つ」。32音と64音は旋律の各音にとなりの音を足して細かくする（変奏）。どれも著作権の切れた曲
        "twinkle": ([72, 79, 81, 79, 77, 76, 74, 72], [72, 72, 79, 79, 81, 81, 79, 79, 77, 77, 76, 76, 74, 74, 72, 72], [(0, MJ_), (0, MJ_), (5, MJ_), (0, MJ_), (5, MJ_), (0, MJ_), (7, MJ_), (0, MJ_)]),
        "ode": ([76, 77, 79, 76, 72, 74, 76, 74], [76, 76, 77, 79, 79, 77, 76, 74, 72, 72, 74, 76, 76, 74, 74, 74], [(0, MJ_), (0, MJ_), (0, MJ_), (7, MJ_), (0, MJ_), (0, MJ_), (0, MJ_), (7, MJ_)]),
    }
    if sp.get("song") in SONGS:
        sk, ml, prog = SONGS[sp["song"]]; SC = [m for m in range(48, 96) if m % 12 in (0, 2, 4, 5, 7, 9, 11)]; up = lambda m: SC[SC.index(m) + 1]; dn = lambda m: SC[SC.index(m) - 1]
        MEL = [sk, ml, [x for m in ml for x in (m, up(m))], [x for m in ml for x in (up(m), m, dn(m), m)]]
    hs = sp.get("hue_shift", 0.0); HUE = [((h_ + hs) % 1, s_) for h_, s_ in [(.97, .72), (.07, .80), (.13, .78), (.52, .42)]]; wR = sp.get("ring_w", .085)
    ang = lambda b, m: th0 - 2 * math.pi * (3 / 8 * m + FR[b] / 8)
    hp = lambda b, m: (math.cos(ang(b, m)), math.sin(ang(b, m)))
    hits = []   # (時刻, 層, ボール, 何回目の当たり, 音)
    for L in range(NL):
        n = 2 ** L
        for j in range(8 * n):
            b = FR.index((j % n) / n); m = 8 * L + j // n; hits.append((t0 + (m + FR[b]) * T, L, b, m, MEL[L][j]))
    hits.sort(); T_fin = t0 + 8 * NL * T; total = T_fin + tail
    spawn = [0.0] + [0.0] * (len(FR) - 1)
    for b in range(1, len(FR)):
        L = int(math.ceil(math.log2(b + 1))); spawn[b] = t0 + 8 * L * T - T / 2 ** (L - 1)   # 前の層の最後の1区画がうまった時
    def pos(b, t):
        u = (t - t0) / T - FR[b]; m = math.floor(u); f = u - m; a, c = hp(b, m), hp(b, m + 1); return (a[0] + (c[0] - a[0]) * f, a[1] + (c[1] - a[1]) * f)
    import harmony
    bar0 = harmony.BAR; canon0 = harmony.CANON; harmony.BAR = T; harmony.CANON = prog or canon0; sp = dict(sp); sp.setdefault("bed_off", t0)
    try:
        sim = Sim(sp, (-1.40, -1.40, 1.40, 1.40), area=(.08, .232, .92, .708))
        sim.neon([(math.cos(a), math.sin(a)) for a in np.linspace(0, 2 * math.pi, 241)], closed=True, width=5); sim.title()
        tone = sp.get("tone", "karo")
        for th, L, b, m, note in hits:
            a = ang(b, m); pan = .5 + .32 * math.cos(a); ci = int((th - t0) / T + 1e-6) % 8; r, q = harmony.CANON[ci]
            sim.notes.append((th, note, (.62, .5, .42, .34)[L], pan, (5, 6, 7, 9)[L], tone))
            if L == 0 or abs(((th - t0) / T) % 1) < 1e-6:   # 拍の頭：和音の根音を低いピアノで（層が進んでも4分の拍を保つ）
                sim.notes.append((th, 48 + r if r < 8 else 36 + r, .30, .5, 2.2, "piano")); sim.notes.append((th, 60 + (r + q[1]) % 12, .12, .5, 2.6, "piano"))
            if L >= 1 and abs(((th - t0) / T) % 1) < 1e-6: sim.notes.append((th, 36, .34, .5, 9, "kick"))
        for mi in (48, 60, 64, 67, 72, 76): sim.notes.append((T_fin, mi, .34, .5, 1.5, "bell"))
        sim.notes.append((T_fin, 36, .8, .5, 9, "kick"))
        # 鍵盤（下）：鳴った音のキーが光る
        K0, K1 = 60, 84; whites = [m for m in range(K0, K1 + 1) if m % 12 in (0, 2, 4, 5, 7, 9, 11)]; WS, HS = 1080 * S, 1920 * S
        kx0, kx1, ky0, ky1 = .07 * WS, .93 * WS, .722 * HS, .790 * HS; kw = (kx1 - kx0) / len(whites)
        def keyrect(m):
            if m in whites: i = whites.index(m); return (kx0 + i * kw + 1.5 * S, ky0, kx0 + (i + 1) * kw - 1.5 * S, ky1), False
            i = whites.index(m - 1); cx_ = kx0 + (i + 1) * kw; return (cx_ - kw * .30, ky0, cx_ + kw * .30, ky0 + (ky1 - ky0) * .60), True
        fC = F(64 * S); nseg = lambda L: 8 * 2 ** L
        done = set()
        for fi in range(int(total * FPS)):
            t = fi / FPS
            for hi, (th, L, b, m, note) in enumerate(hits):   # 通った道を細い線で残す（重なって星の形になる）
                if th <= t and hi not in done:
                    done.add(hi); h_, s_ = HUE[L]; sim.commit([(hp(b, m - 1), hp(b, m), dim(hsv(h_, s_ * .9, 1), (.30, .22, .16, .11)[L]))], width=1.6)
            nh = sum(1 for h in hits if h[0] <= t)
            def draw(d, t=t):
                cx, cy = sim.to((0, 0)); k = sim.k
                agl = max(0.0, t - T_fin); fin = math.exp(-agl * 2.2) if t >= T_fin else 0
                for th, L, b, m, note in hits:   # ぬった区画
                    if th > t: break
                    e = t - th; h_, s_ = HUE[L]; fl = math.exp(-e * 9); a = ang(b, m); half = 180.0 / nseg(L); gap = .5 if L < 3 else .25
                    r1 = (1 + wR * (L + 1)) * k; r0_ = (1 + wR * L) * k + 3 * S; col = hsv(h_, s_ * (1 - .75 * fl), min(1, .80 + .2 * fl + .2 * fin))
                    d.arc([cx - r1, cy - r1, cx + r1, cy + r1], -math.degrees(a) - half + gap, -math.degrees(a) + half - gap, fill=col, width=int(r1 - r0_))
                    if e < .30:   # 当たった所から外へ光の輪
                        x, y = sim.to((math.cos(a), math.sin(a))); rr = (10 + 150 * e) * S; d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=dim((255, 245, 225), 1 - e / .30), width=max(1, int(3 * S)))
                for b in range(len(FR)):   # ボール（尾つき）
                    if t < spawn[b] or (b == 0 and t < 0): continue
                    ap = min(1, (t - spawn[b]) / .25) if b else 1.0; ap *= max(0, 1 - agl / .5)
                    if ap <= 0: continue
                    for q_ in range(7, -1, -1):
                        x, y = sim.to(pos(b, t - q_ * .011)); r_ = (9 - q_ * .95) * S * (.6 + .4 * ap) * (1 if len(FR) <= 2 or t < spawn[min(len(FR) - 1, 2)] else .86)
                        d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=dim((255, 252, 244) if q_ == 0 else (255, 190, 140), ap * (1 - q_ * .12)))
                for b in range(1, len(FR)):   # ふえた瞬間：輪が広がる
                    e = t - spawn[b]
                    if 0 <= e < .45:
                        x, y = sim.to(pos(b, t)); rr = (12 + 190 * e) * S; d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=dim((255, 240, 200), 1 - e / .45), width=max(1, int(3 * S)))
                for L in range(1, NL):   # 1周ぬり終わった合図：真ん中に「×2」
                    e = t - spawn[2 ** (L - 1)]
                    if 0 <= e < 1.1:
                        g = min(1, e / .12) * max(0, 1 - max(0, e - .7) / .4); tx = sp.get("x2", "ボール ×2"); w_ = d.textlength(tx, font=fC)
                        d.text((cx - w_ / 2, cy - 40 * S), tx, font=fC, fill=dim(hsv(HUE[L][0], .5, 1), g))
                if t >= T_fin and agl < .6:
                    rr = (1 + wR * NL) * k + 420 * agl * S; d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=dim((255, 245, 220), 1 - agl / .6), width=max(1, int(4 * S)))
                lit = {}
                for th, L, b, m, note in hits:
                    if th > t: break
                    e = t - th
                    if e < .42: lit[note] = max(lit.get(note, 0), 1 - e / .42)
                for mi in whites + [m_ for m_ in range(K0, K1 + 1) if m_ not in whites]:   # 白いキー → 黒いキーの順
                    (x0, y0, x1, y1), blk = keyrect(mi); g = lit.get(mi, 0); base = (26, 28, 44) if blk else (214, 220, 232); hc = hsv((mi % 12) / 12.0, .78, 1)
                    col = tuple(int(base[i] * (1 - g) + hc[i] * g) for i in range(3))
                    d.rounded_rectangle([x0, y0, x1, y1], radius=int(5 * S), fill=col)
                    if g > .05 and not blk: d.rounded_rectangle([x0, y1 - 14 * S, x1, y1], radius=int(5 * S), fill=dim((255, 255, 255), .55 * g))
            sim.frame(t, (), (), (sp.get("count_label", "はねた回数 "), f"{nh}"), (), draw)
        sim.finish(total)
    finally: harmony.BAR = bar0; harmony.CANON = canon0

def polywheel(sp):
    """三角形が地面を転がる。1回転するたびに辺が1つふえる（オーナー画面収録 11/23「Can a triangle become a wheel?」の型）。
    法則：一定の速さで回るので、1回転（1小節）の中で n角形は n回着地する＝3連、4つ、5連…と拍が細かくなる。中心の上下は 半径×(1−cos(180°/n)) で、辺がふえるほど平らになる"""
    BAR = sp.get("bar", 1.1); N0, N1 = sp.get("n0", 3), sp.get("n1", 24); R = 1.0; intro = sp.get("intro", .5); tail = sp.get("tail", 2.8); w = 2 * math.pi / BAR
    segs = []; x = 0.0; t = intro   # (開始時刻, n, 支点x, 何番目の着地か)
    lands = []; cxs = 0.0
    for n in range(N0, N1 + 1):
        sd = 2 * R * math.sin(math.pi / n); px = cxs + sd / 2   # 辺を下にして置く。支点は右はし
        for i in range(n):
            segs.append((t, n, px, i)); t += BAR / n; lands.append((t, n, px + sd, i)); px += sd
        cxs = px - sd / 2
    T_end = t; total = T_end + tail
    def state(tt):
        tt = min(max(tt, intro), T_end - 1e-6); k = 0
        lo, hi = 0, len(segs) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if segs[mid][0] <= tt: lo = mid
            else: hi = mid - 1
        ts, n, px, i = segs[lo]; ph = (tt - ts) * w; a = math.pi / 2 + math.pi / n - ph
        c = (px + R * math.cos(a), R * math.sin(a)); base = a + math.pi
        return n, c, [(c[0] + R * math.cos(base + 2 * math.pi * j / n), c[1] + R * math.sin(base + 2 * math.pi * j / n)) for j in range(n)], i
    import harmony
    bar0 = harmony.BAR; harmony.BAR = BAR; sp = dict(sp); sp.setdefault("bed_off", intro)
    try:
        sim = Sim(sp, (-1.75, -0.9, 1.75, 2.9)); sim.title()
        for tl, n, lx, i in lands:
            ci = int((tl - BAR / n - intro) / BAR + 1e-6) % 8; r, q = harmony.CANON[ci]; tones = [m for m in range(57, 86) if (m - r) % 12 in q]
            sim.notes.append((tl, tones[min(len(tones) - 1, (i * len(tones)) // n)], .56 * (3.0 / n) ** .33, .5, 6 + n * .25, sp.get("tone", "karo")))
            if i == n - 1: sim.notes.append((tl, 36, .5, .5, 9, "kick")); sim.notes.append((tl, 48 + harmony.CANON[(ci + 1) % 8][0] % 12, .26, .5, 2.2, "piano"))
        for mi in (48, 60, 64, 67, 72, 76): sim.notes.append((T_end, mi, .3, .5, 1.5, "bell"))
        dtp = 1 / 240.0; path = []; vpath = []; tt = intro
        while tt < T_end: n, c, V, i = state(tt); path.append((tt, c, n)); vpath.append(V); tt += dtp
        fB, fS = F(120 * S), F(40 * S); hue = lambda n: .035 + .105 * (n - N0) / max(1, N1 - N0)
        for fi in range(int(total * FPS)):
            t = fi / FPS; n, c, V, i = state(t); camx = c[0]; done = t >= T_end
            def draw(d, t=t, n=n, c=c, V=V, camx=camx, done=done):
                P = lambda p: sim.to((p[0] - camx, p[1])); WS = 1080 * S
                gy = P((camx, 0))[1]
                for gx in np.arange(math.floor((camx - 2.6) / .5) * .5, camx + 2.6, .5):   # 地面の目もり（流れて速さがわかる）
                    x_, _ = P((gx, 0)); big = abs(gx / 2.0 - round(gx / 2.0)) < 1e-6; d.line([x_, gy, x_, gy + (26 if big else 12) * S], fill=(70, 150, 190) if big else (40, 80, 110), width=max(1, int(2 * S)))
                d.line([0, gy, WS, gy], fill=(30, 90, 120), width=int(9 * S)); d.line([0, gy, WS, gy], fill=(150, 235, 255), width=int(3 * S))
                k0 = int((min(t, T_end) - intro) / dtp); pts = [(P(pc), nn) for (tq, pc, nn) in path[max(0, k0 - 1900):k0 + 1:2] if abs(pc[0] - camx) < 2.7]   # 中心が通った道：でこぼこが平らになっていく
                for a_, b_ in zip(pts, pts[1:]): d.line([a_[0], b_[0]], fill=dim(hsv(hue(a_[1]), .7, 1), .9), width=max(1, int(4 * S)))
                ks = list(range(max(0, k0 - int(1.5 * BAR / dtp)), k0 + 1, 3))   # 角が通った道（1回転半ぶん）：弧が重なってレースもようになる
                for qa, qb in zip(ks, ks[1:]):
                    Va, Vb = vpath[qa], vpath[qb]
                    if len(Va) != len(Vb): continue
                    g = .22 + .50 * (qb - ks[0]) / max(1, len(ks) * 3); cl = dim(hsv(hue(len(Va)) + .5, .55, 1), g)
                    for j in range(len(Va)): d.line([P(Va[j]), P(Vb[j])], fill=cl, width=max(1, int(1.6 * S)))
                h_ = hue(n); col = hsv(h_, .78, 1); poly = [P(v) for v in V]; cc = P(c)
                d.polygon(poly, fill=dim(col, .30))
                for j in range(n): d.line([cc, poly[j]], fill=dim(col, .22), width=max(1, int(1.5 * S)))   # スポーク
                d.line(poly + [poly[0]], fill=dim(col, .5), width=int(10 * S)); d.line(poly + [poly[0]], fill=tuple(min(255, int(v * .55 + 115)) for v in col), width=int(3.5 * S))
                rr = 9 * S; d.ellipse([cc[0] - rr, cc[1] - rr, cc[0] + rr, cc[1] + rr], fill=(255, 250, 235))
                for tl, nn, lx, ii in lands:   # 着地の光：地面にそって広がる
                    e = t - tl
                    if e < 0: break
                    if e < .28:
                        x_, y_ = P((lx, 0)); g = 1 - e / .28; wd = (20 + 240 * e) * S * (1.5 if ii == nn - 1 else 1)
                        d.line([x_ - wd, y_, x_ + wd, y_], fill=dim((255, 240, 205), g), width=int((7 if ii == nn - 1 else 4) * S)); r2 = (6 + 30 * e) * S; d.ellipse([x_ - r2, y_ - r2, x_ + r2, y_ + r2], outline=dim((255, 240, 205), g), width=max(1, int(2 * S)))
                tx = sp.get("fmt", "{n}角形").format(n=n); tw = d.textlength(tx, font=fB); pop = 1 + .18 * math.exp(-max(0, (t - intro) % BAR if not done else 9) * 9)
                d.text((WS / 2 - tw / 2, gy + 70 * S), tx, font=fB, fill=dim(tuple(min(255, int(v * .6 + 100)) for v in col), min(1, .85 * pop)))
                bump = (1 - math.cos(math.pi / n)) * 100; t2 = sp.get("bump", "中心の上下  半径の {b}%").format(b=("%.1f" % bump))
                d.text((WS / 2 - d.textlength(t2, font=fS) / 2, gy + 215 * S), t2, font=fS, fill=(190, 200, 215))
            sim.frame(t, (), (), None, (), draw)
        sim.finish(total)
    finally: harmony.BAR = bar0

def koch2(sp):
    """コッホ雪片：光の玉がふちを1周するたびに、通った辺のまん中に小さな三角が生える（オーナー画面収録 11/23「Can a shape with finite area have an infinite edge?」の型）。
    1周は3小節で一定。生える数は 3、12、48、192、768 と4倍ずつ＝音は細かくなる。ふちの長さは1周ごとに 4/3 倍、面積は 8/5 に近づくだけ"""
    BAR = sp.get("bar", 1.5); G = sp.get("laps", 5); LAP = 3 * BAR; intro = sp.get("intro", .5); tail = sp.get("tail", 3.0); T_end = intro + G * LAP; total = T_end + tail
    base = [np.array([math.cos(math.pi / 2 - 2 * math.pi * k / 3), math.sin(math.pi / 2 - 2 * math.pi * k / 3)]) for k in range(3)]   # 時計回り
    gens = [base]
    for g in range(G):
        P = gens[-1]; Q = []
        for i in range(len(P)):
            a, b = P[i], P[(i + 1) % len(P)]; dv = b - a; nrm = np.array([-dv[1], dv[0]]); Q += [a, a + dv / 3, (a + b) / 2 + nrm * (math.sqrt(3) / 6), a + dv * 2 / 3]
        gens.append(Q)
    side0 = float(np.linalg.norm(base[1] - base[0])); A0 = math.sqrt(3) / 4 * side0 ** 2
    def shape(t):
        """いまの形（点の列）、玉の位置、ふちの長さ（元の1辺=1）、面積（元=1）、何周目か"""
        if t >= T_end: g = G - 1; u = 1.0
        else: g = int(max(0, t - intro) / LAP); u = (max(0, t - intro) - g * LAP) / LAP
        P = gens[g]; N = len(P); x = u * N + (N if t >= T_end else 0); grow = max(.10, min(.45, LAP / N * 1.5)); pts = []; ln = 0.0; ar = 0.0; Lg = side0 / 3 ** g
        for i in range(N):
            a, b = P[i], P[(i + 1) % N]; e = (x - (i + 1)) * (LAP / N) / grow; am = 0.0 if e <= 0 else 1.0 if e >= 1 else e * e * (3 - 2 * e)
            if am <= 0: pts.append(a); ln += Lg; continue
            dv = b - a; nrm = np.array([-dv[1], dv[0]]); h = am * math.sqrt(3) / 6
            pts += [a, a + dv / 3, (a + b) / 2 + nrm * h, a + dv * 2 / 3]; ln += Lg * 2 / 3 + 2 * math.hypot(Lg / 6, h * Lg); ar += .5 * (Lg / 3) * (h * Lg)
        i = min(N - 1, int(u * N)); f = u * N - i; ball = P[i] + (P[(i + 1) % N] - P[i]) * f if t < T_end else None
        area_prev = 1 + sum(3 * 4 ** (k - 1) * (1 / 9.0) ** k for k in range(1, g + 1))
        return pts, ball, ln / side0, area_prev + ar / A0, g, u
    import harmony
    bar0 = harmony.BAR; harmony.BAR = BAR; sp = dict(sp); sp.setdefault("bed_off", intro)
    try:
        sim = Sim(sp, (-1.12, -1.12, 1.12, 1.12), area=(.06, .235, .94, .74))
        sim.neon([(1.07 * math.cos(a), 1.07 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 241)], closed=True, width=4); sim.title()
        ev = []   # 生える時刻
        for g in range(G):
            N = 3 * 4 ** g; st = max(1, N // 48)   # 音は1小節に16個まで
            for i in range(N):
                tb = intro + g * LAP + (i + 1) * LAP / N
                if i % st == st - 1 or N <= 48:
                    bi = int((tb - intro - 1e-6) / BAR); r, q = harmony.CANON[bi % 8]; tones = [m for m in range(60, 85) if (m - r) % 12 in q]
                    k = (i // st) if N > 48 else i; per = max(1, (N // st if N > 48 else N) // 3); j = k % per; up = j if j < len(tones) else (len(tones) - 1 - (j - len(tones)) % len(tones))
                    a_ = gens[g][i]; sim.notes.append((tb, tones[int(up) % len(tones)], (.62, .52, .40, .36, .34)[min(g, 4)], .5 + .3 * a_[0], 5 + g, sp.get("tone", "karo")))
            for b_ in range(3):
                tb = intro + g * LAP + b_ * BAR; r, q = harmony.CANON[(g * 3 + b_) % 8]; sim.notes.append((tb, 48 + r if r < 8 else 36 + r, .28, .5, 2.0, "piano"))
                if g >= 1: sim.notes.append((tb, 36, .40, .5, 9, "kick"))
        for mi in (48, 60, 64, 67, 72, 76): sim.notes.append((T_end, mi, .32, .5, 1.5, "bell"))
        sim.notes.append((T_end, 36, .7, .5, 9, "kick"))
        fS = F(40 * S); hue = lambda v: .52 + .42 * min(1, v / G)
        for fi in range(int(total * FPS)):
            t = fi / FPS; pts, ball, ln, area, g, u = shape(t)
            def draw(d, t=t, pts=pts, ball=ball, area=area, g=g, u=u):
                agl = max(0, t - T_end); pul = math.exp(-agl * 2.5) if t >= T_end else math.exp(-(((t - intro) % BAR) if t > intro else 9) * 6) * .35
                col = hsv(hue(g + u), .72, 1); P_ = [sim.to(p) for p in pts]
                d.polygon(P_, fill=dim(col, .22 + .12 * pul))
                d.line(P_ + [P_[0]], fill=dim(col, .45), width=int((11 if g < 3 else 8) * S), joint="curve"); d.line(P_ + [P_[0]], fill=tuple(min(255, int(v * .6 + 100 + 40 * pul)) for v in col), width=int((4 if g < 3 else 3) * S), joint="curve")
                if ball is not None and t >= intro - .3:
                    N = len(gens[g]); x_ = u * N
                    for q_ in range(9, -1, -1):   # 尾：通ってきた辺をさかのぼる
                        xx = x_ - q_ * N * .0045; ii = int(math.floor(xx)); ff = xx - ii; a, b = gens[g][ii % N], gens[g][(ii + 1) % N]; bx, by = sim.to(a + (b - a) * ff); r_ = (13 - q_ * 1.1) * S
                        d.ellipse([bx - r_, by - r_, bx + r_, by + r_], fill=dim((255, 255, 250) if q_ == 0 else tuple(min(255, int(v * .5 + 120)) for v in col), 1 - q_ * .09))
                if t >= T_end and agl < .7:
                    cx, cy = sim.to((0, 0)); rr = (1.07 * sim.k) + 380 * agl * S; d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=dim((255, 240, 250), 1 - agl / .7), width=max(1, int(4 * S)))
                tx = sp.get("area", "面積 {a}（元＝1）  1.6 はこえない").format(a="%.3f" % area); d.text((1080 * S / 2 - d.textlength(tx, font=fS) / 2, .752 * 1920 * S), tx, font=fS, fill=(190, 200, 215))
            sim.frame(t, (), (), (sp.get("count_label", "ふちの長さ "), "%.2f" % ln), (), draw)
        sim.finish(total)
    finally: harmony.BAR = bar0

def canonstairs(sp):
    """らせん階段を、3つの玉が1周おくれで下りる。1段ごとに旋律が1音。同じ旋律を1周おくれで重ねる＝カノン（オーナー画面収録 11/23「CANON IN D / 3 BALLS. 1 MELODY.」の型）。
    1周8段＝8つの和音。どの玉も同じ時刻に着地するので、ずれた旋律がいつも同じ和音の中で重なる"""
    T = sp.get("beat", .6); t0 = sp.get("intro", .8); NB = sp.get("balls", 3); SPT = 8; tail = sp.get("tail", 3.0)
    PH = [[76, 74, 72, 71, 69, 67, 69, 71], [72, 71, 69, 67, 65, 64, 65, 62], [72, 76, 79, 77, 76, 72, 76, 74], [76, 79, 76, 79, 81, 79, 81, 79], [67, 71, 72, 76, 77, 79, 81, 83]]
    NT = len(PH); NS = NT * SPT; dz = sp.get("dz", .17); tilt = math.radians(sp.get("tilt", 33)); cT, sT = math.cos(tilt), math.sin(tilt)
    T_end = t0 + NS * T; total = T_end + tail; r_in, r_out, rb = .60, 1.0, .80; BC = [(255, 110, 190), (255, 190, 70), (90, 240, 170)]; TONE = [sp.get("tone", "karo"), "stone", "bell"]
    import harmony
    bar0 = harmony.BAR; harmony.BAR = T; sp = dict(sp); sp.setdefault("bed_off", t0)
    try:
        sim = Sim(sp, (-1, -1, 1, 1)); sim.title(); lands = []
        for b in range(NB):
            for i in range(NS - b * SPT):
                tl = t0 + (i + b * SPT) * T; lands.append((tl, b, i)); sim.notes.append((tl, PH[i // SPT][i % SPT], (.58, .46, .30)[b], (.5, .3, .7)[b], (5, 5, 2.5)[b], TONE[b]))
        for i in range(NS):
            r, q = harmony.CANON[i % 8]; sim.notes.append((t0 + i * T, 48 + r if r < 8 else 36 + r, .26, .5, 2.0, "piano"))
            if i >= SPT and i % 2 == 0: sim.notes.append((t0 + i * T, 36, .34, .5, 9, "kick"))
        for mi in (48, 60, 64, 67, 72, 76): sim.notes.append((T_end, mi, .32, .5, 1.5, "bell"))
        lands.sort(); WS, HS = 1080 * S, 1920 * S; K = 318 * S; cx0, cy0 = WS / 2, .50 * HS; fS = F(44 * S)
        phi = lambda i: math.pi / 2 + .5 - i * 2 * math.pi / SPT   # 段 i の向き（手前から始まり、時計回りに下りる）
        def proj(x, y, z, zc, az):
            ca, sa = math.cos(az), math.sin(az); x, y = x * ca - y * sa, x * sa + y * ca
            return (cx0 + x * K, cy0 - ((z - zc) * cT + y * sT) * K), y * cT - (z - zc) * sT   # 画面の位置、奥行き（大きいほど奥）
        NTILE = NS + 10
        for fi in range(int(total * FPS)):
            t = fi / FPS; u0 = (t - t0) / T; zc = -dz * (min(max(u0, -1), NS - 1 + 1.2 * (1 - math.exp(-max(0, t - T_end) * 1.2))) - 6.5); az = .10 * math.sin(t * .33)
            lit = {}   # 段 → (色, 明るさ)
            for tl, b, i in lands:
                if tl > t: break
                e = t - tl; lit[i] = (BC[b], e)
            def draw(d, t=t, u0=u0, zc=zc, az=az, lit=lit):
                objs = []
                for rr_, cw in ((.12, (120, 220, 255)), (r_in - .05, (90, 110, 220))):   # 中心の柱と内側の手すり（らせんの線）
                    ln = []
                    for q in np.arange(-3, NTILE + 1, .25):
                        (x_, y_), _ = proj(rr_ * math.cos(phi(q)), rr_ * math.sin(phi(q)), -dz * q, zc, az); ln.append((x_, y_))
                    for pa, pb in zip(ln, ln[1:]):
                        fg = max(0, min(1, (1 - abs((pa[1] + pb[1]) / 2 - cy0) / (.275 * HS)) * 2.2))
                        if fg > .02: d.line([pa, pb], fill=dim(cw, .5 * fg), width=max(1, int(2.5 * S)))
                for i in range(-2, NTILE):
                    a0, a1 = phi(i) + math.pi / SPT * .88, phi(i) - math.pi / SPT * .88; z = -dz * i
                    arc = [a0 + (a1 - a0) * q / 5 for q in range(6)]
                    top = [proj(r_out * math.cos(a), r_out * math.sin(a), z, zc, az)[0] for a in arc] + [proj(r_in * math.cos(a), r_in * math.sin(a), z, zc, az)[0] for a in reversed(arc)]
                    _, dep = proj(rb * math.cos(phi(i)), rb * math.sin(phi(i)), z, zc, az); objs.append((dep, "t", i, top))
                for b in range(NB):
                    u = u0 - b * SPT
                    if u < -1.2 or t > T_end + 1.2: continue
                    uu = min(u, NS - b * SPT - 1 + 0.0) if t >= T_end else u; i = math.floor(uu); f = uu - i
                    a = phi(i) + (phi(i + 1) - phi(i)) * f; hop = 4 * .34 * f * (1 - f)
                    if t >= T_end: f = 0; hop = .10 * abs(math.sin((t - T_end) * 5)) * math.exp(-(t - T_end) * 1.5); a = phi(i)
                    z = -dz * (i + f) + hop + .07 + (max(0, -u) * 1.6 if u < 0 else 0)
                    p_, dep = proj(rb * math.cos(a), rb * math.sin(a), z, zc, az); objs.append((dep - .02, "b", b, (p_, i, f)))
                objs.sort(key=lambda o: -o[0])
                for dep, kind_, i, dat in objs:
                    if kind_ == "t":
                        yy = dat[0][1]; fog = max(0, min(1, (1 - abs(yy - cy0) / (.275 * HS)) * 2.2))
                        if fog <= .02: continue
                        hcol = hsv(.78 - .16 * ((i % SPT) / SPT), .70, 1); g = .30; col = hcol
                        if i in lit:
                            c_, e = lit[i]; fl = math.exp(-e * 6); col = tuple(int(c_[q] * (1 - fl) + 255 * fl) for q in range(3)); g = .62 + .38 * fl
                        th = .05 * K * cT; side = [(x_, y_ + th) for x_, y_ in dat]
                        d.polygon(side, fill=dim(col, g * .35 * fog)); d.polygon(dat, fill=dim(col, g * fog)); d.line(dat + [dat[0]], fill=dim(tuple(min(255, int(v * .6 + 100)) for v in col), min(1, (g + .25)) * fog), width=max(1, int(2.5 * S)))
                    else:
                        (x, y), i_, f = dat; fgb = max(0, min(1, (1 - abs(y - cy0) / (.275 * HS)) * 2.2)); c_ = dim(BC[i], fgb)   # 題名にかかる高さでは玉も消す
                        if fgb <= .02: continue
                        for rr, gg in ((64, .10), (44, .20), (30, .38)): r_ = rr * S; d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=dim(c_, gg))
                        r_ = 19 * S; d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=tuple(min(255, int(v * .45 + 150)) for v in c_))
                for tl, b, i in lands:   # 着地の光の輪
                    e = t - tl
                    if e < 0: break
                    if e < .32:
                        (x, y), _ = proj(rb * math.cos(phi(i)), rb * math.sin(phi(i)), -dz * i, zc, az); rw = (18 + 190 * e) * S; d.ellipse([x - rw, y - rw * sT, x + rw, y + rw * sT], outline=dim(BC[b], 1 - e / .32), width=max(1, int(3 * S)))
                nb = sum(1 for b in range(NB) if u0 - b * SPT >= -1.2); tx = sp.get("fmt", "玉 {n}こ  ｜  {k}周目").format(n=nb, k=min(NT, max(1, int(max(0, u0) // SPT) + 1)))
                d.text((WS / 2 - d.textlength(tx, font=fS) / 2, .79 * HS), tx, font=fS, fill=(215, 220, 235), stroke_width=int(4 * S), stroke_fill=(0, 0, 0))
            sim.frame(t, (), (), None, (), draw)
        sim.finish(total)
    finally: harmony.BAR = bar0

def chordballs(sp):
    """音の板の上でボールがはねる。はねる回数が1回ずつちがうので、音はばらけて波になり、決まった時刻にまた全部そろって和音になる（オーナー画面収録 11/23「The darkest chord, built by falling balls.」の型）。
    法則：ボール k は周期 D/(n0+k)。高さは周期の2乗に比例（同じ重力）。D 秒後に全員が同時に着地する"""
    NOTES = sp.get("notes", [36, 43, 48, 51, 55, 58, 62, 63, 67, 70]); NAMES = sp.get("names", ["C", "G", "C", "E♭", "G", "B♭", "D", "E♭", "G", "B♭"]); N = len(NOTES)
    D = sp.get("cycle", 18.0); n0 = sp.get("n0", 12); intro = sp.get("intro", .9); tail = sp.get("tail", 3.2); Tk = [D / (n0 + k) for k in range(N)]; HY = 6.6; hk = [HY * (T_ / Tk[0]) ** 2 for T_ in Tk]
    T_end = intro + D; total = T_end + tail
    sim = Sim(sp, (-.55, -1.0, N - .45, 7.3), area=(.04, .235, .96, .765)); sim.title(); lands = []
    for k in range(N):
        for j in range(n0 + k + 1):
            tl = intro + j * Tk[k]; lands.append((tl, k, j)); last = j == n0 + k or j == 0
            sim.notes.append((tl, NOTES[k] + 12, (.5 if last else .40) * (1.15 - .04 * k), .12 + .76 * k / (N - 1), 3.2 if last else 4.5, sp.get("tone", "piano")))
    for mi in NOTES[:3]: sim.notes.append((T_end, mi, .4, .5, 1.2, "bell"))
    lands.sort(); fN, fS = F(34 * S), F(44 * S); col = lambda k: hsv((.93 + .19 * k / (N - 1)) % 1, .78, 1)
    def y_of(k, t):
        if t < intro: return hk[k] * min(1.0, ((intro - t) / (Tk[k] / 2))) ** 2 if False else hk[k] * (1 - (1 - min(1.0, (intro - t) / (Tk[k] / 2))) ** 2)   # 出だし：頂点から落ちてきて、全員同時に着地
        if t >= T_end: e = t - T_end; return .10 * abs(math.sin(e * 6)) * math.exp(-e * 2.2)
        ph = ((t - intro) % Tk[k]) / Tk[k]; return hk[k] * 4 * ph * (1 - ph)
    for fi in range(int(total * FPS)):
        t = fi / FPS; nh = sum(1 for l in lands if l[0] <= t)
        def draw(d, t=t):
            lit = {}
            for tl, k, j in lands:
                if tl > t: break
                lit[k] = t - tl
            agl = t - T_end; allg = math.exp(-max(0, agl) * 1.6) if agl >= 0 else (math.exp(-(t - intro) * 3) if t >= intro else 0)
            for k in range(N):   # 音の板
                c = col(k); e = lit.get(k, 9); fl = math.exp(-e * 7); g = .34 + .66 * max(fl, allg * .9)
                x0, y0 = sim.to((k - .40, 0)); x1, y1 = sim.to((k + .40, -.24)); d.rounded_rectangle([x0, y0, x1, y1], radius=int(8 * S), fill=dim(tuple(int(c[i] * (1 - fl * .6) + 255 * fl * .6) for i in range(3)), g))
                tw = d.textlength(NAMES[k], font=fN); d.text(((x0 + x1) / 2 - tw / 2, y1 + 14 * S), NAMES[k], font=fN, fill=dim((235, 225, 235), .55 + .45 * max(fl, allg)))
                if e < .35:   # 着地の光：上へのびる柱
                    hh = (60 + 520 * e) * S; d.rectangle([x0 + 8 * S, y0 - hh, x1 - 8 * S, y0], fill=dim(c, .22 * (1 - e / .35)))
            for k in range(N):   # 高さの柱：周期が短いボールほど低い（高さは周期の2乗に比例）
                c = col(k); xa, ya = sim.to((k - .33, hk[k] + .42)); xb, yb = sim.to((k + .33, 0)); e = lit.get(k, 9); fl = math.exp(-e * 5)
                d.rectangle([xa, ya, xb, yb], fill=dim(c, .07 + .10 * fl), outline=dim(c, .30 + .3 * fl), width=max(1, int(2 * S)))
            pts = []
            for k in range(N):   # ボール（落ちる速さでのびる）
                y = y_of(k, t); c = col(k); x, yy = sim.to((k, y + .20)); pts.append((x, yy))
                vy = 0 if (t < intro or t >= T_end) else abs(1 - 2 * (((t - intro) % Tk[k]) / Tk[k])); st = 1 + .28 * vy
                for q in range(5, 0, -1):
                    yq = y_of(k, t - q * .014); xq, yyq = sim.to((k, yq + .20)); r_ = (17 - q * 2.2) * S; d.ellipse([xq - r_, yyq - r_, xq + r_, yyq + r_], fill=dim(c, .34 - q * .05))
                r_ = 20 * S; d.ellipse([x - r_ / st, yy - r_ * st, x + r_ / st, yy + r_ * st], fill=tuple(min(255, int(v * .7 + 70)) for v in c))
            d.line(pts, fill=(120, 110, 150), width=max(1, int(2 * S)), joint="curve")   # ボールをつなぐ線：波の形が見える
            if agl >= 0 and agl < .8:
                cx, cy = sim.to(((N - 1) / 2, 0)); rr = (60 + 900 * agl) * S; d.ellipse([cx - rr, cy - rr * .5, cx + rr, cy + rr * .5], outline=dim((255, 230, 240), 1 - agl / .8), width=max(1, int(4 * S)))
            rem = max(0.0, T_end - t); tx = sp.get("fmt", "次にそろうまで {s} 秒").format(s="%.1f" % rem) if rem > 0 else sp.get("done", "全部そろった")
            d.text((1080 * S / 2 - d.textlength(tx, font=fS) / 2, .775 * 1920 * S), tx, font=fS, fill=(225, 215, 230), stroke_width=int(4 * S), stroke_fill=(0, 0, 0))
        sim.frame(t, (), (), (sp.get("count_label", "鳴った音 "), f"{nh}"), (), draw)
    sim.finish(total)

def slinky(sp):
    """虹色のバネ（色が流れ続ける）が階段を下りる。段の高さがどんどん変わる（オーナー 11/23「グラデーションが常に変わり続けるおもちゃが段差をどんどん降りる。段差の高さもどんどん変わる感じ」）。
    法則：1段下りる時間は、段の高さの平方根に比例（落ちる時間と同じ決まり）。高さ 1 : 1/4 : 1/16 の段は、拍の長さ 1 : 1/2 : 1/4 になる＝段の高さでリズムが変わる"""
    BEAT = sp.get("beat", .9); intro = sp.get("intro", .7); tail = sp.get("tail", 3.0); H0 = 1.0; SW = sp.get("step_w", 1.25); R = .43; N = sp.get("coils", 28); th = .021; lag = .46
    SEQ = sp.get("seq", [1] * 4 + [.5] * 8 + [1, .5, .5] * 2 + [.25] * 16 + [.5] * 4 + [.25] * 8 + [2])
    steps = [(0.0, 0.0)]; times = [intro]   # 段の上の面（中心x, 高さy）、着く時刻
    for dbeats in SEQ: x, y = steps[-1]; steps.append((x + SW, y - H0 * dbeats ** 2)); times.append(times[-1] + dbeats * BEAT)
    T_end = times[-1]; total = T_end + tail; NS = len(SEQ)
    ease = lambda v: v * v * (3 - 2 * v)
    def coil(i, k, p):
        """段 k から k+1 へ進む途中（進み具合 p）の、輪 i の中心と向き（道の向き）"""
        (xa, ya), (xb, yb) = steps[k], steps[k + 1]; sv = min(1.0, max(0.0, (p - lag * i / (N - 1)) / (1 - lag))); sv = ease(sv)
        A = (xa, ya + (N - 1 - i) * th + th / 2); B = (xb, yb + i * th + th / 2); arch = .62 + .10 * (ya - yb) ** .5
        def P(v): return (A[0] + (B[0] - A[0]) * v, A[1] + (B[1] - A[1]) * v + arch * math.sin(math.pi * v) + (R * .9) * math.sin(math.pi * v) ** 2)
        c = P(sv)
        if sv <= 0 or sv >= 1: return c, math.pi / 2
        a_, b_ = P(max(0, sv - .01)), P(min(1, sv + .01)); ang = math.atan2(b_[1] - a_[1], b_[0] - a_[0]); w_ = math.sin(math.pi * sv) ** .5
        d_ = ((ang - math.pi / 2 + math.pi) % (2 * math.pi)) - math.pi; return c, math.pi / 2 + d_ * w_
    import harmony
    bar0 = harmony.BAR; harmony.BAR = BEAT; sp = dict(sp); sp.setdefault("bed_off", intro)
    try:
        sim = Sim(sp, (-1, -1, 1, 1)); sim.title()
        for k in range(1, NS + 1):
            tl = times[k]; bi = int((tl - intro) / BEAT - 1e-6); r, q = harmony.CANON[bi % 8]; tones = [m for m in range(55, 86) if (m - r) % 12 in q]; d_ = SEQ[k - 1]
            sim.notes.append((tl, tones[(len(tones) - 1 - (k * 2) % len(tones))], {2: .7, 1: .6, .5: .5, .25: .40}.get(d_, .5), .5, 5 if d_ >= .5 else 8, sp.get("tone", "karo")))
            if abs(((tl - intro) / BEAT) % 1) < 1e-6 or d_ >= 1: sim.notes.append((tl, 48 + r if r < 8 else 36 + r, .26, .5, 2.0, "piano")); sim.notes.append((tl, 36, .36 if d_ < 2 else .8, .5, 9, "kick"))
        for mi in (48, 60, 64, 67, 72, 76): sim.notes.append((T_end, mi, .32, .5, 1.5, "bell"))
        WS, HS = 1080 * S, 1920 * S; K = 268 * S; fS, fB = F(40 * S), F(46 * S); cam = [0.0, 0.3]
        def state(t):
            if t < intro: return 0, 0.0
            if t >= T_end: return NS - 1, 1.0
            k = max(j for j in range(NS) if times[j] <= t); return k, (t - times[k]) / (times[k + 1] - times[k])
        for fi in range(int(total * FPS)):
            t = fi / FPS; k, p = state(t); (xa, ya), (xb, yb) = steps[k], steps[k + 1]; pe = ease(min(1, p * 1.15))
            tx_, ty_ = xa + (xb - xa) * pe, ya + (yb - ya) * pe + .45; cam[0] += (tx_ - cam[0]) * .16; cam[1] += (ty_ - cam[1]) * .16
            def draw(d, t=t, k=k, p=p, cx_=cam[0], cy_=cam[1]):
                Pp = lambda x, y: (WS / 2 + (x - cx_) * K, .50 * HS - (y - cy_) * K)
                ytop, ybot = .215 * HS, .80 * HS
                for gx in np.arange(math.floor(cx_ - 3), cx_ + 3, .5):   # うしろの方眼（流れて、下りる速さがわかる）
                    x_, _ = Pp(gx, 0); d.line([x_, ytop, x_, ybot], fill=(16, 22, 44), width=max(1, int(1.5 * S)))
                for gy in np.arange(math.floor(cy_ - 4), cy_ + 4, .5):
                    _, y_ = Pp(0, gy)
                    if ytop < y_ < ybot: d.line([0, y_, WS, y_], fill=(16, 22, 44), width=max(1, int(1.5 * S)))
                poly = []   # 階段
                for j in range(max(0, k - 6), min(NS + 1, k + 8)):
                    x, y = steps[j]; poly += [Pp(x - SW / 2, y), Pp(x + SW / 2, y)]
                poly = [(x_, min(max(y_, ytop), ybot)) for x_, y_ in poly]
                if len(poly) >= 2:
                    d.polygon([(poly[0][0], ybot)] + poly + [(poly[-1][0], ybot)], fill=(10, 14, 34)); d.line(poly, fill=(40, 110, 150), width=int(9 * S), joint="curve"); d.line(poly, fill=(150, 235, 255), width=int(3 * S), joint="curve")
                for j in range(max(1, k - 6), min(NS + 1, k + 2)):   # ついた段が光る
                    e = t - times[j]
                    if 0 <= e < .5:
                        x, y = steps[j]; (x0, y0), (x1, _) = Pp(x - SW / 2, y), Pp(x + SW / 2, y)
                        if ytop < y0 < ybot: c_ = hsv((j * .07) % 1, .6, 1); g = 1 - e / .5; d.line([x0, y0, x1, y0], fill=dim(c_, g), width=int(8 * S)); d.rectangle([x0, y0 + 5 * S, x1, min(ybot, y0 + (30 + 200 * e) * S)], fill=tuple(int(b_ + c_[q_] * .22 * g) for q_, b_ in enumerate((10, 14, 34))))
                rings = []
                for i in range(N - 1, -1, -1):
                    c, ang = coil(i, k, p); rings.append((i, c, ang))
                for i, c, ang in rings:   # 輪：道に直角な輪を横から見た形（だ円）。色は輪の番号＋時間で流れ続ける
                    col = hsv((i / N * .85 + t * .22) % 1, .82, 1); ca, sa = math.cos(ang), math.sin(ang); pts = []
                    for q in range(25):
                        u = 2 * math.pi * q / 24; lx, ly = R * math.cos(u), R * .26 * math.sin(u)   # 長い軸は道に直角、短い軸は道の向き
                        pts.append(Pp(c[0] + (-sa) * lx + ca * ly, c[1] + ca * lx + sa * ly))
                    if any(y_ < ytop for _, y_ in pts): continue
                    d.line(pts, fill=dim(col, .45), width=int(8 * S), joint="curve"); d.line(pts, fill=tuple(min(255, int(v * .8 + 50)) for v in col), width=int(3.5 * S), joint="curve")
                hh = H0 * SEQ[k] ** 2; tx = sp.get("fmt", "段の高さ {h}  →  下りる時間 {b} 拍").format(h=("%g" % round(hh, 3)), b=("%g" % SEQ[k])) if t < T_end else sp.get("done", "高さが4倍で、時間は2倍")
                d.text((WS / 2 - d.textlength(tx, font=fS) / 2, .812 * HS - 60 * S), tx, font=fS, fill=(215, 222, 238), stroke_width=int(4 * S), stroke_fill=(0, 0, 0))
            nd = sum(1 for j in range(1, NS + 1) if times[j] <= t)
            sim.frame(t, (), (), (sp.get("count_label", "下りた段 "), f"{nd} / {NS}"), (), draw)
        sim.finish(total)
    finally: harmony.BAR = bar0

KINDS = {"slinky": slinky, "chordballs": chordballs, "canonstairs": canonstairs, "koch2": koch2, "polywheel": polywheel, "circlefill": circlefill, "dots45": dots45, "spiralglass": spiralglass, "dominoes2": dominoes2, "hearts2": hearts2, "cupcaustic": cupcaustic, "dominoes": dominoes, "merge": merge, "hearts": hearts, "bricks": bricks, "pendwave3d": pendwave3d, "spiro": spiro, "lens": lens, "koch": koch, "pendwave": pendwave, "orbits": orbits, "phyllo": phyllo, "zoomsalt": zoomsalt, "layers": layers, "pixels": pixels, "sortviz": sortviz, "polyfocus": polyfocus, "heliostat": heliostat, "dragon": dragon, "rhythm": rhythm, "lissatable": lissatable, "plotter": plotter, "threebody": threebody, "pendswing": pendswing, "golden": golden, "piphase": piphase, "maurer": maurer, "harmono": harmono, "spiropens": spiropens, "star": star, "throw": throw, "tusi": tusi, "chain": chain, "basket": basket, "koch": koch, "cycloid": cycloid, "pendulums": pendulums, "lissajous": lissajous, "corner": corner, "sunflower": sunflower, "ulam": ulam, "parabola": parabola, "rings": rings, "venus": venus, "cardioid": cardioid, "mirrors2": mirrors2, "picount": picount}

if __name__ == "__main__":
    sp = json.load(open(sys.argv[1], encoding="utf-8")); KINDS[sp["kind"]](sp); kit(sp)
