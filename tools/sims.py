# sims.py — 「数学的に必ずそうなる」を絵と音で見せるショート（simkit を使う）
#   python tools/sims.py <spec.json>       → output/<id>.mp4 と投稿キット
#   STILLS="5,20,30" python tools/sims.py <spec.json>   → その時刻の絵だけ（確認用）
#   spec: id / kind / title（画面の問い2行）/ count_label / yt{title, desc, tags} ＋ 種類ごとの数値
#   種類: parabola（放物線の焦点）/ rings（1周ずつ多く回る輪）/ venus（2つの軌道を線で結ぶ）
import json, sys, os, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simkit import Sim, PENTA, FPS, S, F, hsv, dim, kit


def lerp(a, b, u): return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def parabola(sp):
    """放物線 y=x²/4f。上の線からまっすぐ落とすと、どのボールも道の長さ Y+f で焦点を通る（同時）。
    焦点を過ぎて反対側の壁で跳ね返ると、まっすぐ上に戻る（道の長さはまた Y+f）。1往復ごとにボールを増やす"""
    f, X, Y, v = 1.0, sp.get("X", 6.0), sp.get("Y", 14.0), sp.get("v", 6.4)
    a = 4 * f * f / X; T = (Y + f) / v          # a: 戻ってこられるいちばん内側の x。T: 上の線→焦点の時間
    ms = sp.get("rounds", [2, 3, 5, 7, 11, 16]) + [sp.get("last", 24)]; intro, tail = .3, sp.get("tail", 1.2)
    sim = Sim(sp, (-X - .15, -.15, X + .15, Y + .15))
    sim.neon([(x, x * x / (4 * f)) for x in np.linspace(-X, X, 241)])
    sim.neon([(-X, Y), (X, Y)], width=5)
    sim.ring((0, f), 13); sim.title()
    rounds = []
    for r, m in enumerate(ms):
        t0 = intro + r * 2 * T; xr = [a * (X / a) ** ((j + .5) / m) for j in range(m)]; balls = []
        for side in (1, -1):
            for j, x1 in enumerate(xr):
                x1 = side * x1; y1 = x1 * x1 / (4 * f); x2 = -4 * f * f / x1; y2 = x2 * x2 / (4 * f)
                balls.append(dict(pts=[(x1, Y), (x1, y1), (0, f), (x2, y2), (x2, Y)], cum=[0, Y - y1, Y + f, Y + 2 * f + y2, 2 * (Y + f)],
                                  col=hsv(((j + .5) / m * .5 + (0 if side > 0 else .5)) % 1), done=0))
        n = len(balls); h1 = np.array([b["cum"][1] for b in balls]); h2 = np.array([b["cum"][3] for b in balls])
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
            cum, pts = b["cum"], b["pts"]; sc = min(s, cum[-1])
            while b["done"] < 4 and cum[b["done"] + 1] <= sc: segs.append((pts[b["done"]], pts[b["done"] + 1], dim(b["col"], .30))); b["done"] += 1
            k = b["done"]; p = pts[4] if k >= 4 else lerp(pts[k], pts[k + 1], (sc - cum[k]) / (cum[k + 1] - cum[k]))
            if k < 4: live.append((pts[k], p, dim(b["col"], .7), lw))
            dots.append((p, b["col"], 5 if n <= 32 else 4))
        sim.commit(segs, width=lw)
        e = t - (t0 + T); fl = [((0, f), 22 + e * 60, dim((255, 245, 200), 1 - e / .22), 5)] if 0 <= e < .22 else []
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
    vols, gap = sp.get("volleys", [1, 2, 3, 5, 8, 13, 21, 34]), sp.get("gap", 3.0); intro, tail = .3, sp.get("tail", 1.6)
    def outdir(x, y):
        v2 = 2 * g * (H - y); dx, dy = Tg[0] - x, Tg[1] - y; A = g * dx * dx / (2 * v2); u = (dx - math.sqrt(dx * dx - 4 * A * (A + dy))) / (2 * A)
        ox, oy = math.copysign(1, dx), u * math.copysign(1, dx); L = math.hypot(ox, oy); return ox / L, oy / L
    def slope(x, y): o = outdir(x, y); return -o[0] / (o[1] + 1)
    xs = np.linspace(xa, xb, 2001); y = 0.0; ys = [y]
    for i in range(len(xs) - 1):
        h = xs[i + 1] - xs[i]; k1 = slope(xs[i], y); k2 = slope(xs[i] + h / 2, y + h / 2 * k1); k3 = slope(xs[i] + h / 2, y + h / 2 * k2); k4 = slope(xs[i + 1], y + h * k3)
        y += h * (k1 + 2 * k2 + 2 * k3 + k4) / 6; ys.append(y)
    ys = np.array(ys)
    sim = Sim(sp, (Tg[0] - .9, -.4, xb + .2, H + .2))
    sim.neon(list(zip(xs[::20], ys[::20])) + [(xs[-1], ys[-1])]); sim.neon([(xa - .1, H), (xb + .1, H)], width=4)
    rim = .38; sim.neon([(Tg[0] - rim, Tg[1]), (Tg[0] + rim, Tg[1])], color=(255, 170, 70), glow=(255, 120, 30), width=6)
    sim.neon([(Tg[0] - rim - .05, Tg[1] - .1), (Tg[0] - rim - .05, Tg[1] + 1.2)], width=5)
    for k in range(5): sim.thin([(Tg[0] - rim + k * rim / 2, Tg[1]), (Tg[0] - rim * .6 + k * rim * .3, Tg[1] - .7)], color=(150, 150, 165), width=1.2)
    sim.title()
    balls, t0 = [], intro; scored_t = []
    for w, m in enumerate(vols):
        for j in range(m):
            x0 = xa + .15 + (xb - xa - .3) * ((j + .5) / m); i = int(np.searchsorted(xs, x0)); yf = float(np.interp(x0, xs, ys))
            sl = (ys[min(i + 1, len(xs) - 1)] - ys[max(i - 1, 0)]) / (xs[min(i + 1, len(xs) - 1)] - xs[max(i - 1, 0)]); nrm = np.array([-sl, 1.0]); nrm /= np.linalg.norm(nrm)
            v = math.sqrt(2 * g * (H - yf)); vin = np.array([0, -v]); vo = vin - 2 * np.dot(vin, nrm) * nrm; t1 = math.sqrt(2 * (H - yf) / g); tT = (Tg[0] - x0) / vo[0]
            b = dict(x0=x0, yf=yf, vo=vo, t0=t0, t1=t1, tT=tT, col=hsv((j + .5) / m * .85 + .07 * w), last=None, m=m)
            balls.append(b); scored_t.append(t0 + t1 + tT)
            g_ = .9 / math.sqrt(m); rank = j / max(1, m - 1)
            sim.note(t0 + t1, PENTA[int(rank * 15 + .5)], g_, .5 + .3 * x0 / xb, 4 + 3 * math.sqrt(m / 5))
            sim.note(t0 + t1 + tT, PENTA[min(15, 10 + int(rank * 5 + .5))], .7 * g_, .3, 5 + 3 * math.sqrt(m / 5), "bell")
        t0 += gap
    total = max(scored_t) + tail; scored_t.sort(); tot = sum(vols)
    def pos(b, t):
        u = t - b["t0"]
        if u < 0: return None
        if u < b["t1"]: return (b["x0"], H - g * u * u / 2)
        u -= b["t1"]; x = b["x0"] + b["vo"][0] * u; y = b["yf"] + b["vo"][1] * u - g * u * u / 2
        if u > b["tT"]: x = Tg[0] + (x - Tg[0]) * .15   # かごの中はまっすぐ下へ
        return (x, y) if y > Tg[1] - 1.1 else None
    for fi in range(int(total * FPS)):
        t = fi / FPS; dots, segs = [], []
        for b in balls:
            p = pos(b, t)
            if p is None: continue
            if b["last"] is not None and t - b["t0"] < b["t1"] + b["tT"]: segs.append((b["last"], p, dim(b["col"], .28)))
            b["last"] = p; dots.append((p, b["col"], 5))
        sim.commit(segs, width=1.3)
        n_in = int(np.searchsorted(scored_t, t, side="right")); n_out = sum(1 for b in balls if b["t0"] <= t)
        sim.frame(t, (), dots, (sp.get("count_fmt", "入った {a} / {b}　").format(a=n_in, b=n_out), ""))
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


KINDS = {"chain": chain, "basket": basket, "koch": koch, "cycloid": cycloid, "pendulums": pendulums, "lissajous": lissajous, "corner": corner, "sunflower": sunflower, "ulam": ulam, "parabola": parabola, "rings": rings, "venus": venus, "cardioid": cardioid, "mirrors2": mirrors2, "picount": picount}

if __name__ == "__main__":
    sp = json.load(open(sys.argv[1], encoding="utf-8")); KINDS[sp["kind"]](sp); kit(sp)
