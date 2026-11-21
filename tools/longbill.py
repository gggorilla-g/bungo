# longbill.py — 英語の長尺（横長 1920x1080）：形のちがう部屋で玉を跳ねさせる章を、いくつもつなぐ
#   SIM_LANDSCAPE=1 SIM_S=1 python3 tools/longbill.py spec.json [章の番号]   → output/<id>_c<n>.mp4（章ごと）
#   python3 tools/longbill.py spec.json join   → 章をディゾルブでつないで output/<id>.mp4
#   章ごとに：部屋の形（多角形で近似）・玉の出し方・ふえ方・音色・色・ひねり（途中で起きる予想外のこと）を変える
#   描き方：玉は小さく、軌跡（ストローク）を主役に。軌跡はゆっくり消える。壁に当たった点が光り、枠も軽く光る
import json, os, sys, math, subprocess
import numpy as np
os.environ.setdefault("SIM_LANDSCAPE", "1"); os.environ.setdefault("SIM_S", "1")
sys.path.insert(0, "tools")
from simkit import Sim, FPS, hsv, dim, S, W, H
from PIL import Image, ImageDraw, ImageFilter, ImageChops

SCALES = {"maj": [0, 2, 4, 7, 9], "min": [0, 3, 5, 7, 10], "lyd": [0, 2, 4, 6, 7, 9, 11]}


_CH = {}
ch_get = lambda k, d: _CH.get(k, d)


def shape_pts(kind, n=240, a=1.0, b=.62):
    if kind == "circle": th = np.linspace(0, 2 * np.pi, n, endpoint=False); return np.c_[np.cos(th), np.sin(th)]
    if kind == "ellipse": th = np.linspace(0, 2 * np.pi, n, endpoint=False); return np.c_[a * np.cos(th), b * np.sin(th)]
    if kind.startswith("poly"):   # poly6 など正多角形
        k = int(kind[4:]); th = np.linspace(0, 2 * np.pi, k, endpoint=False) + np.pi / 2 + (np.pi / k if k % 2 == 0 else 0); return np.c_[np.cos(th), np.sin(th)]
    if kind == "square": return np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], float) * .82
    if kind == "stadium":   # 長方形の両端に半円
        r, L = .62, .55; pts = []
        for th in np.linspace(-np.pi / 2, np.pi / 2, n // 2): pts.append([L + r * np.cos(th), r * np.sin(th)])
        for th in np.linspace(np.pi / 2, 3 * np.pi / 2, n // 2): pts.append([-L + r * np.cos(th), r * np.sin(th)])
        return np.array(pts)
    if kind == "mushroom":   # キノコ形（半円のかさ＋細い柄）。かさの中に閉じこめられる玉と、さまよう玉が分かれる
        sw, sl = ch_get("stem_w", .32), ch_get("stem_l", 1.15); pts = []
        for th in np.linspace(0, np.pi, n): pts.append([np.cos(th), .35 + np.sin(th)])
        pts += [[-sw, .35], [-sw, .35 - sl], [sw, .35 - sl], [sw, .35]]
        return np.array(pts)
    if kind.startswith("star"):   # star5 など。へこんだ星形
        k = int(kind[4:]); r2 = ch_get("inner", .45); pts = []
        for i in range(2 * k):
            th = np.pi / 2 + i * np.pi / k; r = 1 if i % 2 == 0 else r2; pts.append([r * np.cos(th), r * np.sin(th)])
        return np.array(pts)
    if kind == "dshape":   # 円を弦で切ったD形
        c = ch_get("cut", .45); a0 = np.arcsin(c); th = np.linspace(np.pi - a0, 2 * np.pi + a0, n); return np.c_[np.cos(th), np.sin(th)]
    raise ValueError(kind)


class Table:
    def __init__(self, P):
        self.P = P; self.A = P; self.B = np.roll(P, -1, 0); E = self.B - self.A
        self.E = E; N = np.c_[E[:, 1], -E[:, 0]]; N /= np.linalg.norm(N, axis=1)[:, None]
        area = .5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
        self.N = N * (-1 if area > 0 else 1)   # 内向き（向きで決める。へこんだ形でも正しい）

    def hit(self, p, v):
        """p,v: (m,2)。最初に当たる辺までの時間と辺の番号"""
        A, E = self.A[None], self.E[None]; P_ = p[:, None]; V = v[:, None]
        den = V[..., 0] * E[..., 1] - V[..., 1] * E[..., 0]
        AP = A - P_
        t = (AP[..., 0] * E[..., 1] - AP[..., 1] * E[..., 0]) / np.where(np.abs(den) < 1e-12, np.nan, den)
        u = (AP[..., 0] * V[..., 1] - AP[..., 1] * V[..., 0]) / np.where(np.abs(den) < 1e-12, np.nan, den)
        ok = (t > 1e-9) & (u >= -1e-9) & (u <= 1 + 1e-9)
        t = np.where(ok, t, np.inf); j = np.argmin(t, 1); return t[np.arange(len(p)), j], j


def run_chapter(sp, ci):
    ch = sp["chapters"][ci]; cid = f'{sp["id"]}_c{ci}'
    rng = np.random.default_rng(ch.get("seed", ci + 1))
    _CH.clear(); _CH.update(ch)
    P = shape_pts(ch["shape"], a=ch.get("a", 1.0), b=ch.get("b", .62)); T = Table(P)
    dur = ch.get("dur", 100.0); total = dur
    mn, mx = P.min(0), P.max(0); pad = .1 * (mx - mn).max(); box = (mn[0] - pad, mn[1] - pad, mx[0] + pad, mx[1] + pad)
    sim = Sim(dict(id=cid, bloom=ch.get("bloom", .55)), box, area=(.03, .05, .97, .95))
    hue0 = ch.get("hue", .55); frame_col = hsv(hue0, .45, 1)
    sim.neon(list(map(tuple, P)), closed=True, color=dim(frame_col, .8), glow=dim(frame_col, .35), width=3)
    # 玉の出し方
    def fan(origin, n, a0=0, a1=2 * np.pi, speed=.5):
        th = np.linspace(a0, a1, n, endpoint=(a1 - a0 < 2 * np.pi - 1e-6)); return np.tile(origin, (n, 1)).astype(float), np.c_[np.cos(th), np.sin(th)] * speed
    p, v = fan(np.array(ch.get("origin", [0, 0])), ch.get("n", 12), *ch.get("arc", [0, 2 * np.pi]), speed=ch.get("speed", .45))
    if ch.get("twin"):   # ほとんど同じ2つの玉（ずれが育つ）
        p = np.array([ch["origin"], ch["origin"]], float); a = ch.get("angle", .7); v = np.array([[np.cos(a), np.sin(a)], [np.cos(a + ch["twin"]), np.sin(a + ch["twin"])]]) * ch.get("speed", .45)
    if ch.get("start_angles"):
        a = np.array(ch["start_angles"]); p = np.tile(ch.get("origin", [0, 0]), (len(a), 1)).astype(float); v = np.c_[np.cos(a), np.sin(a)] * ch.get("speed", .45)
    cols = [hsv((hue0 + ch.get("hue_span", .35) * i / max(1, len(p) - 1)) % 1, .55, 1) for i in range(len(p))]
    gen = np.zeros(len(p), int)
    scale = SCALES[ch.get("scale", "maj")]; root = ch.get("root", 60); kind = ch.get("sound", "glass")
    pitch = lambda x: root + scale[int(x * len(scale) * 2) % len(scale)] + 12 * (int(x * len(scale) * 2) // len(scale))
    decay = ch.get("fade", .985)   # 軌跡が消える速さ（1フレームごとに掛ける）
    hits = []   # (時刻, 位置, 色)
    cp = ch.get("checkpoint"); cap = ch.get("cap", 400); mult = ch.get("mult", 2)
    sub = 4; dt = 1 / FPS / sub; last_pos = p.copy(); nudge_t = ch.get("nudge_t")
    for fi in range(int(total * FPS)):
        t = fi / FPS; segs = []
        for _ in range(sub):
            rem = np.full(len(p), dt); q0 = p.copy()
            for _k in range(6):
                th, j = T.hit(p, v); go = np.minimum(th, rem); p = p + v * go[:, None]
                idx = np.where(th <= rem + 1e-12)[0]; rem = rem - go
                for i in idx:
                    n_ = T.N[j[i]]; v[i] = v[i] - 2 * (v[i] @ n_) * n_; p[i] += n_ * 1e-7
                    hits.append((t, p[i].copy(), cols[i % len(cols)], j[i] / len(T.P)))
                if len(idx) == 0 or (rem < 1e-12).all(): break
            for i in range(len(p)): segs.append((tuple(q0[i]), tuple(p[i]), cols[i % len(cols)]))
            # チェックポイント：点を通ったらふえる（上限つき）
            if cp and len(p) < cap:
                c_ = np.array(cp[:2]); r_ = cp[2]
                d0 = np.linalg.norm(q0 - c_, axis=1); d1 = np.linalg.norm(p - c_, axis=1)
                crossed = np.where((d1 < r_) & (d0 >= r_))[0]
                if len(crossed):
                    newp, newv, newc = [], [], []
                    for i in crossed:
                        for k in range(mult - 1):
                            a = (k + 1) * ch.get("split_angle", .5) * (1 if k % 2 == 0 else -1); ca, sa = math.cos(a), math.sin(a)
                            newp.append(p[i].copy()); newv.append([v[i][0] * ca - v[i][1] * sa, v[i][0] * sa + v[i][1] * ca]); newc.append(hsv((hue0 + .08 * (gen[i] + 1)) % 1, .55, 1))
                    room = cap - len(p); newp, newv, newc = newp[:room], newv[:room], newc[:room]
                    if newp:
                        p = np.vstack([p, newp]); v = np.vstack([v, newv]); cols = cols + newc; gen = np.concatenate([gen, gen[crossed[:1]].repeat(len(newp)) + 1])
            if nudge_t is not None and abs(t - nudge_t) < dt / 2 + 1e-9:   # ひねり：ほんの少し向きを変える
                a = ch.get("nudge", .004); ca, sa = math.cos(a), math.sin(a); v[0] = [v[0][0] * ca - v[0][1] * sa, v[0][0] * sa + v[0][1] * ca]
        # 軌跡を焼く（ゆっくり消える）
        sim.acc = Image.eval(sim.acc, lambda x, k=decay: int(x * k))
        dr = ImageDraw.Draw(sim.acc); lw = ch.get("line", 2)
        for a, b, c in segs: dr.line([*sim.to(a), *sim.to(b)], fill=dim(c, ch.get("line_gain", .55)), width=lw)
        # 光：当たった点と枠
        recent = [h for h in hits if 0 <= t - h[0] < .35]
        def draw_fx(d, recent=recent):
            for th_, pp, c, _ in recent[-160:]:
                al = 1 - (t - th_) / .35; x, y = sim.to(pp); r = (3 + 10 * al) * S
                d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(min(255, int(cc * al + 120 * al)) for cc in c))
            pw = min(1, len([h for h in hits if 0 <= t - h[0] < .25]) / max(3, len(p) ** .5))
            if pw > .05: d.line([sim.to(q) for q in list(map(tuple, P)) + [tuple(P[0])]], fill=dim(frame_col, .4 + .6 * pw), width=max(1, int((2 + 3 * pw) * S)))
            if ch.get("label"):
                from simkit import F
                f_ = F(int(22 * S)); d.text((40 * S, H * S - 60 * S), ch["label"], font=f_, fill=(120, 132, 150))
                f2 = F(int(22 * S)); s2 = f"balls {len(p)}"; w2 = d.textlength(s2, font=f2); d.text((W * S - 40 * S - w2, H * S - 60 * S), s2, font=f2, fill=(120, 132, 150))
        balls = [(tuple(p[i]), cols[i % len(cols)], ch.get("ball", 2.6)) for i in range(len(p))]
        sim.frame(t, [], balls, None, draw=draw_fx)
    # 音：当たった時刻ごと。密なときは音量を下げ、同じ瞬間の重なりを間引く
    hits.sort(key=lambda h: h[0]); last = {}
    for th_, pp, c, frac in hits:
        key = round(th_ * 40)
        last[key] = last.get(key, 0) + 1
        if last[key] > ch.get("poly", 4): continue
        g = ch.get("gain", .32) / math.sqrt(last[key])
        sim.note(th_, pitch(frac), g, .5 + .45 * float(pp[0]) / 1.2, ch.get("dec", 3.2), kind)
    sim.finish(total)
    return f"output/{cid}.mp4"


def join(sp):
    n = len(sp["chapters"]); xf = sp.get("xfade", 2.0)
    files = [f'output/{sp["id"]}_c{i}.mp4' for i in range(n)]
    durs = [float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout) for f in files]
    args = ["ffmpeg", "-v", "error", "-y"]
    for f in files: args += ["-i", f]
    fv, fa = [], []; off = 0; lv, la = "[0:v]", "[0:a]"
    for i in range(1, n):
        off += durs[i - 1] - xf
        fv.append(f"{lv}[{i}:v]xfade=transition=fade:duration={xf}:offset={off:.3f}[v{i}]"); lv = f"[v{i}]"
        fa.append(f"{la}[{i}:a]acrossfade=d={xf}[a{i}]"); la = f"[a{i}]"
        off -= 0
    args += ["-filter_complex", ";".join(fv + fa), "-map", lv, "-map", la, "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", f'output/{sp["id"]}.mp4']
    subprocess.run(args, check=True); print("書き出し:", f'output/{sp["id"]}.mp4', round(sum(durs) - xf * (n - 1), 1), "秒")


if __name__ == "__main__":
    sp = json.load(open(sys.argv[1]))
    if len(sys.argv) > 2 and sys.argv[2] == "join": join(sp)
    else:
        for ci in ([int(sys.argv[2])] if len(sys.argv) > 2 else range(len(sp["chapters"]))): print(run_chapter(sp, ci))
