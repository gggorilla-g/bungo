# race.py — 倍々サバイバル玉レース（横長の長尺、15分以内）
#   文脈（11/27 調べ）：MIKAN「The Doubling - Team Elimination Marble Race」14分で734万回。レース再生リスト262本＝コースと決まりを変えて出し続ける型。
#   オーナー 11/27「それで。瞑想ヒーリングっぽく」「音がキンキン…カリンバっぽい心地よい音色」「ブラーエコーもかけすぎない」「モロカノンというよりカノン進行」
#   決まり：16色の玉が上から落ち、くぎの間を転がって、下の箱に入る。箱は「×2」（次の段で2倍）「そのまま」「OUT」。
#           段の終わりに、玉がいちばん少ない色が脱落（9色以上のうちは下位2色）。同じ数なら、最後の玉が箱に入るのが遅かった色が脱落。最後の1色が勝ち（11段）。
#           段ごとに箱の並びが変わる。玉が増えすぎないよう、玉が多いほど OUT が増える（画面に出す）。
#   音：くぎに当たった玉が、カノン進行（D A Bm F#m G D G A）の和音の音を鳴らす。左ほど低く右ほど高い。8分音符にそろえ、同時は3音まで。音色は tools/kalimba.py。
#   再現性：SEED を変えると別のレース。SEARCH=1 で「12〜14分で決着し、最後が一騎打ち」になる乱数を探す。
#   python3 tools/race.py search            乱数を探す
#   python3 tools/race.py stills 30,200      確認用の絵
#   python3 tools/race.py clip 0 90 out.mp4  一部（音つき）
#   python3 tools/race.py all                全部 → output/race1_ja.mp4
import math, os, sys, json, subprocess, wave
import numpy as np, cv2, pymunk
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kalimba as K

W, H, FPS, SR = 1920, 1080, 30, 48000
B = "build_race"; os.makedirs(B, exist_ok=True)
SEED = int(os.environ.get("SEED", 7)); LANG = os.environ.get("LANG_OUT", "ja"); EN = LANG == "en"
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"; FJM = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
def fnt(sz, bold=True): return ImageFont.truetype(FJ if bold else FJM, sz)

# 16色（落ち着いた明るさ。光らせすぎない）
TEAMS = [("赤", "Red", (236, 92, 92)), ("橙", "Orange", (240, 146, 70)), ("山吹", "Amber", (240, 192, 72)), ("黄", "Yellow", (236, 226, 96)),
         ("黄緑", "Lime", (168, 214, 88)), ("緑", "Green", (86, 190, 110)), ("青緑", "Teal", (64, 184, 164)), ("水色", "Cyan", (88, 200, 228)),
         ("空", "Sky", (110, 164, 240)), ("青", "Blue", (86, 112, 232)), ("藍", "Indigo", (120, 96, 214)), ("紫", "Purple", (168, 104, 220)),
         ("赤紫", "Magenta", (214, 98, 196)), ("桃", "Pink", (240, 150, 186)), ("茶", "Brown", (176, 128, 92)), ("白", "White", (226, 228, 236))]
NT = len(TEAMS)
def tname(i): return TEAMS[i][1] if EN else TEAMS[i][0]

# 盤面（画面の座標そのまま）
FX0, FX1 = 470, 1450; FY0 = 150; PEG_Y0, PEG_Y1 = 250, 830; BIN_Y = 870; FLOOR = 1010; NB = 12; BW = (FX1 - FX0) / NB
R = 7.5; PEG_R = 4.5; GRAV = 300.0; RES = 12.0; TS = .8   # ゆっくり落ちる（瞑想）。RES = 結果を見せる秒、TS = 再生の速さ（0.8倍のスロー）
def pegs():
    out = []; rows = 12; dy = (PEG_Y1 - PEG_Y0) / (rows - 1); dx = 56
    for j in range(rows):
        y = PEG_Y0 + j * dy; off = (j % 2) * dx / 2; x = FX0 + 32 + off   # 壁とくぎのすき間に玉がはさまらない幅
        while x < FX1 - 30: out.append((x, y)); x += dx
    return out
PEGS = pegs()

def bin_plan(P, stage, rng, alive):
    """玉の数 P から、箱12個の中身（2=×2, 1=そのまま, 0=OUT）を決める。次の段の見込みが 90〜220 個になるように"""
    target = float(np.clip(P * 1.0, 0, 1e9)); want = 150 if P < 120 else 120
    if alive <= 4: want = 110
    best = None
    for n2 in range(0, NB + 1):
        for n0 in range(0, NB + 1 - n2):
            n1 = NB - n2 - n0; e = P * (2 * n2 + n1) / NB
            if n0 < (1 if P > 30 else 0) or (P < 40 and n0 > 2): continue
            sc = abs(e - min(want, P * 2.2)) + (0 if n2 >= 1 else 50)
            if best is None or sc < best[0]: best = (sc, n2, n1, n0)
    _, n2, n1, n0 = best; kinds = [2] * n2 + [1] * n1 + [0] * n0; rng.shuffle(kinds); return kinds

# ---------- シミュレーション ----------
def simulate(seed, record=False, maxstage=30):
    rng = np.random.default_rng(seed); counts = np.ones(NT, int) * 4
    stages = []; frames = []; hits = []; t_glob = 0.0; dt = 1 / 120
    for st in range(maxstage):
        alive = int((counts > 0).sum())
        if alive <= 1: break
        P = int(counts.sum()); kinds = bin_plan(P, st, rng, alive)
        sp = pymunk.Space(); sp.gravity = (0, GRAV); sp.iterations = 14
        sb = sp.static_body; segs = []
        for (x, y) in PEGS: c = pymunk.Circle(sb, PEG_R, (x, y)); c.elasticity = .55; c.friction = .2; c.collision_type = 2; segs.append(c)
        for a, b in (((FX0, FY0 - 200), (FX0, FLOOR)), ((FX1, FY0 - 200), (FX1, FLOOR)), ((FX0, FLOOR), (FX1, FLOOR))): s = pymunk.Segment(sb, a, b, 3); s.elasticity = .3; s.friction = .5; segs.append(s)
        for k in range(1, NB): x = FX0 + k * BW; s = pymunk.Segment(sb, (x, BIN_Y), (x, FLOOR), 2.5); s.elasticity = .3; s.friction = .5; segs.append(s)
        sp.add(*segs)
        # 落とす順番：色をまぜる
        order = np.repeat(np.arange(NT), counts); rng.shuffle(order); Tdrop = float(np.clip(12 + P * .12, 14, 30)); tdrop = np.sort(rng.uniform(0, Tdrop, len(order)))
        balls = []; i_next = 0; t = 0.0; settled = 0.0; land = np.zeros(NT)
        def on_hit(arb, space, data):
            if not record: return
            sh = arb.shapes; bb = sh[0] if sh[0].collision_type == 1 else sh[1]
            if arb.is_first_contact:
                imp = arb.total_impulse.length
                if imp > 18: hits.append((t_glob + t / TS, bb.body.position.x, min(1.0, imp / 220), bb.team))
        sp.on_collision(1, 2, post_solve=on_hit)
        STEP = 4; fr_dt = TS / FPS; acc = 0.0
        while True:
            while i_next < len(order) and tdrop[i_next] <= t:
                b = pymunk.Body(1, pymunk.moment_for_circle(1, 0, R)); b.position = (rng.uniform(FX0 + 330, FX1 - 330), FY0 - 30); b.velocity = (rng.normal(0, 25), 40)
                c = pymunk.Circle(b, R); c.elasticity = .45; c.friction = .25; c.collision_type = 1; c.team = int(order[i_next]); sp.add(b, c); balls.append(c); i_next += 1
            for _ in range(STEP): sp.step(dt); t += dt; acc += dt
            if record and acc >= fr_dt - 1e-9:
                acc -= fr_dt; frames.append(dict(st=st, t=t, pos=np.array([[c.body.position.x, c.body.position.y, c.team, c.body.angle] for c in balls], np.float32)))
            for c in balls:
                if not getattr(c, 'landed', False) and c.body.position.y > BIN_Y: c.landed = True; land[c.team] = max(land[c.team], t)
            done = i_next == len(order) and all(c.body.position.y > PEG_Y1 + 12 and c.body.velocity.length < 14 for c in balls)
            if done: settled += STEP * dt
            else: settled = 0.0
            if settled > .6 or t > Tdrop + 40: break
        # 結果
        res = np.zeros((NB, NT), int)
        for c in balls:
            k = int(np.clip((c.body.position.x - FX0) // BW, 0, NB - 1)); res[k, c.team] += 1
        new = np.zeros(NT, int)
        for k in range(NB): new += res[k] * kinds[k]
        ne = 2 if alive > 8 else 1; al = [i for i in range(NT) if counts[i] > 0]; rank = sorted(al, key=lambda i: (new[i], -land[i])); out = rank[:ne]
        out += [i for i in al if new[i] == 0 and i not in out]
        for i in out: new[i] = 0
        stages.append(dict(Tv=t / TS, st=st, P=P, kinds=kinds, before=counts.copy(), after=new.copy(), out=[int(i) for i in out], land=land.tolist(), res=res.tolist(), T=t, t0=t_glob, alive=alive))
        counts = new; t_glob += t / TS + (RES if record else 0)
        if record: frames.append(dict(st=st, t=t, result=True, n=int(RES * FPS)))
    winner = int(np.argmax(counts)) if (counts > 0).sum() == 1 else -1
    return dict(stages=stages, winner=winner, frames=frames, hits=hits, final=counts)

def score(r):
    if r["winner"] < 0: return -1e9
    T = sum(s["T"] / TS + RES for s in r["stages"]); n = len(r["stages"]); last = r["stages"][-1]
    duel = 1 if last["alive"] == 2 else 0; spread = len(set(s["alive"] for s in r["stages"]))
    return -abs(T - 12.5 * 60) / 20 + duel * 8 + spread - (30 if T > 14.3 * 60 else 0)

def search(n=40):
    best = []
    for sd in range(n):
        r = simulate(sd); sc = score(r); T = sum(s["T"] / TS + RES for s in r["stages"]); last = r["stages"][-1]
        b2 = sorted(last["before"])[-2:]; close = abs(int(last["after"].max()) - 0)
        best.append((sc - abs(int(b2[1]) - int(b2[0])) * .3, sd, round(T / 60, 2), r["winner"], [int(x) for x in b2])); print(best[-1], flush=True)
    best.sort(reverse=True); print("上位", best[:5])

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "search":
    search(int(sys.argv[2]) if len(sys.argv) > 2 else 40)

# ---------- 絵 ----------
def sprite(col, r):
    s = int(r * 2 + 6); yy, xx = np.mgrid[0:s, 0:s].astype(np.float32); cx = cy = s / 2; d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    a = np.clip((1 - d) * r + .5, 0, 1); nz = np.sqrt(np.clip(1 - d * d, 0, 1)); lx, ly, lz = -.45, -.55, .7
    lam = np.clip(((xx - cx) / r * lx + (yy - cy) / r * ly + nz * lz), 0, 1); c = np.asarray(col, np.float32) / 255
    rgb = c * (.42 + .62 * lam)[..., None]; hl = np.exp(-(((xx - cx + r * .36) ** 2 + (yy - cy + r * .40) ** 2) / (r * .26) ** 2)); rgb = rgb + hl[..., None] * .45
    rim = np.clip(d - .78, 0, 1)[..., None] * .25; rgb = rgb * (1 - rim)
    return np.dstack([np.clip(rgb, 0, 1), a]).astype(np.float32)
SPR = [sprite(c, R) for _, _, c in TEAMS]; SPRB = [sprite(c, 13) for _, _, c in TEAMS]
def blit(buf, sp, x, y, al=1.0):
    h, w = sp.shape[:2]; x0, y0 = int(round(x - w / 2)), int(round(y - h / 2))
    if x0 < 0 or y0 < 0 or x0 + w > W or y0 + h > H: return
    a = sp[..., 3:4] * al; reg = buf[y0:y0 + h, x0:x0 + w]; reg[:] = reg * (1 - a) + sp[..., :3] * a
_BG = {}
def bg():
    if "b" in _BG: return _BG["b"]
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]; xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :, None]
    b = np.array([.035, .045, .085], np.float32) * (1 - .25 * yy) + np.array([.02, .02, .03], np.float32) * yy; b = b * (1 - .28 * xx ** 2)
    b = np.broadcast_to(b, (H, W, 3)).copy(); b[FY0 - 40:FLOOR + 8, FX0 - 6:FX1 + 6] += np.array([.012, .014, .022], np.float32)
    for (x, y) in PEGS: cv2.circle(b, (int(x * 4), int(y * 4)), int(PEG_R * 4), (.62, .66, .74), -1, cv2.LINE_AA, 2)
    for xw in (FX0, FX1): cv2.line(b, (int(xw), FY0 - 40), (int(xw), FLOOR), (.30, .33, .42), 3, cv2.LINE_AA)
    cv2.line(b, (FX0, FLOOR), (FX1, FLOOR), (.30, .33, .42), 3, cv2.LINE_AA)
    for k in range(1, NB): x = int(FX0 + k * BW); cv2.line(b, (x, BIN_Y), (x, FLOOR), (.30, .33, .42), 2, cv2.LINE_AA)
    _BG["b"] = b; return b
F = dict(t=fnt(40), m=fnt(30), s=fnt(24, False), xs=fnt(20, False), big=fnt(84), bin=fnt(26), name=fnt(26, False))
KC = {2: (255, 214, 120), 1: (200, 210, 230), 0: (200, 110, 120)}
def klabel(k): return ("x2" if EN else "×2") if k == 2 else ("x1" if EN else "×1") if k == 1 else "OUT"
def ease(x): x = min(1, max(0, x)); return x * x * (3 - 2 * x)

def draw_ui(img, d, st, counts, alive_set, P, kinds, extra=None, a_ui=1.0):
    A = lambda v=1.0: int(255 * v * a_ui)
    # 箱の札
    for k, kd in enumerate(kinds):
        x = FX0 + (k + .5) * BW; c = KC[kd]; d.rounded_rectangle([x - 34, BIN_Y - 40, x + 34, BIN_Y - 8], 8, fill=(c[0] // 6, c[1] // 6, c[2] // 6, A(.9)), outline=c + (A(.8),), width=2); d.text((x, BIN_Y - 24), klabel(kd), font=F["bin"], fill=c + (A(),), anchor="mm")
    # 左：段と残り
    d.text((80, 160), (f"STAGE {st + 1}" if EN else f"第{st + 1}段"), font=F["t"], fill=(240, 242, 250, A()))
    d.text((80, 220), (f"{len(alive_set)} colors left" if EN else f"残り {len(alive_set)}色"), font=F["m"], fill=(200, 210, 230, A()))
    d.text((80, 262), (f"{P} marbles" if EN else f"玉 {P}個"), font=F["m"], fill=(200, 210, 230, A()))
    rule = (["x2: doubles next stage", "OUT: removed", "Fewest marbles: out" + (" (2 colors)" if len(alive_set) > 8 else "")] if EN else
            ["×2 … 次の段で2倍", "×1 … そのまま", "OUT … なくなる", "いちばん少ない色が脱落" + ("（2色）" if len(alive_set) > 8 else "")])
    for j, ln in enumerate(rule): d.text((80, 360 + 36 * j), ln, font=F["s"], fill=(170, 180, 204, A()))
    # 右：順位
    al = sorted(alive_set, key=lambda i: -counts[i]); y0 = 120; dy = min(52, 820 / max(8, len(al)))
    for j, i in enumerate(al):
        y = y0 + j * dy; c = TEAMS[i][2]; d.ellipse([1520, y + 6, 1546, y + 32], fill=c + (A(),)); d.text((1562, y + 19), tname(i), font=F["name"], fill=(232, 236, 246, A()), anchor="lm")
        d.text((1850, y + 19), str(int(counts[i])), font=F["m"], fill=(240, 242, 250, A()), anchor="rm")
    if extra: extra(d, A)

def timeline(r):
    tl = [("intro", i) for i in range(int(7 * FPS))]; fr = r["frames"]; si = 0
    for f in fr:
        if f.get("result"): tl += [("res", f["st"], j, f["n"]) for j in range(f["n"])]
        else: tl.append(("sim", f))
    tl += [("end", i) for i in range(int(10 * FPS))]; return tl

def make_frame(r, item):
    S = r["stages"]; buf = bg().copy()
    img = None; kind = item[0]
    if kind == "intro":
        i = item[1]; s0 = S[0]; a = ease(i / 30) * (1 - ease((i - 7 * FPS + 25) / 25)); im = Image.fromarray((buf * 255).astype(np.uint8)).convert("RGBA"); ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
        draw_ui(im, d, 0, s0["before"], set(range(NT)), s0["P"], s0["kinds"], a_ui=ease(i / 40))
        d.rectangle([0, 0, W, H], fill=(8, 10, 20, int(150 * a)))
        d.text((W / 2, H / 2 - 70), ("Doubling Survival: 16 Colors" if EN else "倍々サバイバル 16色の玉"), font=F["big"], fill=(255, 255, 255, int(255 * a)), anchor="mm")
        d.text((W / 2, H / 2 + 30), ("Which color is the last one left? Pick one." if EN else "最後に残るのはどの色？ 1つ選んでね"), font=F["t"], fill=(255, 226, 150, int(255 * a)), anchor="mm")
        return np.asarray(Image.alpha_composite(im, ov).convert("RGB"))
    if kind == "sim":
        f = item[1]; st = f["st"]; s = S[st]
        for x, y, tm, ang in f["pos"]: blit(buf, SPR[int(tm)], x, y)
        im = Image.fromarray((np.clip(buf, 0, 1) * 255).astype(np.uint8)).convert("RGBA"); ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
        al = set(i for i in range(NT) if s["before"][i] > 0); draw_ui(im, d, st, s["before"], al, s["P"], s["kinds"])
        return np.asarray(Image.alpha_composite(im, ov).convert("RGB"))
    if kind == "res":
        _, st, j, n = item; s = S[st]; last = [f for f in r["frames"] if not f.get("result") and f["st"] == st][-1]; u = j / n
        fade_out = 1 - ease((u - .88) / .12)
        for x, y, tm, ang in last["pos"]: blit(buf, SPR[int(tm)], x, y, fade_out)
        im = Image.fromarray((np.clip(buf, 0, 1) * 255).astype(np.uint8)).convert("RGBA"); ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
        res = np.array(s["res"]); after = np.array(s["after"]); before = np.array(s["before"]); out = s["out"]
        mix = ease((u - .15) / .3); cnt = np.round(before + (np.where(np.isin(np.arange(NT), out), np.array(s["res"]).T @ np.array(s["kinds"]), after) - before) * mix).astype(int)
        al = set(i for i in range(NT) if before[i] > 0) if u < .62 else set(i for i in range(NT) if after[i] > 0)
        def extra(d, A):
            for k in range(NB):
                tot = int(res[k].sum()); x = FX0 + (k + .5) * BW; kd = s["kinds"][k]; v = tot * kd
                d.text((x, FLOOR + 30), (f"{tot}→{v}" if kd != 1 else f"{tot}"), font=F["xs"], fill=KC[kd] + (A(ease(u / .15) * fade_out),), anchor="mm")
            if u > .55:
                a2 = ease((u - .55) / .1) * fade_out; names = ("・" if not EN else ", ").join(tname(i) for i in out)
                d.rounded_rectangle([FX0 + 140, 430, FX1 - 140, 560], 18, fill=(10, 12, 24, int(220 * a2)), outline=(200, 110, 120, int(220 * a2)), width=2)
                d.text(((FX0 + FX1) / 2, 470), ("Out" if EN else "脱落"), font=F["m"], fill=(220, 150, 160, int(255 * a2)), anchor="mm")
                d.text(((FX0 + FX1) / 2, 520), names, font=F["t"], fill=(255, 255, 255, int(255 * a2)), anchor="mm")
                for q, i in enumerate(out): blit_c = TEAMS[i][2]; d.ellipse([(FX0 + FX1) / 2 - 20 * len(out) + 40 * q - 10, 580, (FX0 + FX1) / 2 - 20 * len(out) + 40 * q + 10, 600], fill=blit_c + (int(255 * a2),))
        draw_ui(im, d, st, cnt, al, int(cnt[list(al)].sum()) if al else 0, s["kinds"], extra)
        return np.asarray(Image.alpha_composite(im, ov).convert("RGB"))
    if kind == "end":
        i = item[1]; w = r["winner"]; a = ease(i / 40); im = Image.fromarray((buf * 255).astype(np.uint8)).convert("RGBA"); ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
        c = TEAMS[w][2]; cx, cy = W / 2, H / 2 - 40
        for q in range(14):
            ang = q / 14 * 2 * math.pi + i / FPS * .25; rr = 160 + 12 * math.sin(i / FPS * 1.3 + q)
            d.ellipse([cx + rr * math.cos(ang) - 14, cy + rr * math.sin(ang) - 14, cx + rr * math.cos(ang) + 14, cy + rr * math.sin(ang) + 14], fill=c + (int(230 * a),))
        d.text((cx, cy - 10), ("Winner" if EN else "優勝"), font=F["t"], fill=(255, 226, 150, int(255 * a)), anchor="mm"); d.text((cx, cy + 50), tname(w), font=F["big"], fill=c + (int(255 * a),), anchor="mm")
        d.text((cx, cy + 260), (f"{int(r['final'][w])} marbles" if EN else f"最後の玉 {int(r['final'][w])}個"), font=F["m"], fill=(220, 226, 240, int(255 * a)), anchor="mm")
        out = np.asarray(Image.alpha_composite(im, ov).convert("RGB")).astype(np.float32); g = 1 - ease((i - 10 * FPS + 50) / 50); return (out * g).astype(np.uint8)

# ---------- 音（カノン進行の上で、くぎに当たった玉が鳴らす。カリンバ） ----------
PROG = [(50, 54, 57), (45, 49, 52), (47, 50, 54), (42, 45, 49), (43, 47, 50), (38, 42, 45), (43, 47, 50), (45, 49, 52)]
BPM = 72; E8 = 60 / BPM / 2; CH = 60 / BPM * 8
def chord_at(t): return PROG[int(t // CH) % 8]
def tones(ch, lo=62, hi=88):
    pcs = {m % 12 for m in ch}; return [m for m in range(lo, hi + 1) if m % 12 in pcs]
def audio(r, tl, path):
    N = int(SR * len(tl) / FPS) + SR; st = np.zeros((N, 2), np.float32); T0 = 7.0
    def put(x, t, pan, g):
        i = int(t * SR)
        if i < 0 or i >= N: return
        k = min(len(x), N - i); st[i:i + k, 0] += x[:k] * math.cos(pan * math.pi / 2) * g; st[i:i + k, 1] += x[:k] * math.sin(pan * math.pi / 2) * g
    slots = {}
    for (t, x, imp, tm) in r["hits"]:
        q = round((t + T0) / E8); slots.setdefault(q, []).append((imp, x))
    for q, lst in slots.items():
        lst.sort(reverse=True); t = q * E8; tl_ = tones(chord_at(t))
        for imp, x in lst[:3]:
            u = (x - FX0) / (FX1 - FX0); m = tl_[int(np.clip(u, 0, .999) * len(tl_))]; put(K.note(m, .5 + .5 * imp), t + np.random.default_rng(q).normal(0, .006), .2 + .6 * u, .10 + .16 * imp)
    for c in range(int(N / SR / CH) + 1):   # 和音が変わるたびに低い音（ゆっくり）
        r_, t3, f5 = PROG[c % 8]; put(K.note(r_, .6), c * CH, .5, .34); put(K.note(f5, .5), c * CH + CH / 2, .45, .2)
    # 段の結果：×2 の箱があれば上がる分散和音、脱落は低い1音
    for s in r["stages"]:
        ts = T0 + s["t0"] + s["Tv"]; ch = chord_at(ts + 2); tl_ = tones(ch, 62, 86)
        for j, m in enumerate(tl_[:6]): put(K.note(m, .7), ts + 1.8 + j * E8, .3 + .08 * j, .22)
        put(K.note(chord_at(ts + 6.6)[0] - 12 + 12, .6), ts + 6.6, .5, .3)
    put_end = T0 + sum(s["Tv"] + RES for s in r["stages"])
    for j, m in enumerate([62, 66, 69, 74, 78, 81, 86]): put(K.note(m, .8), put_end + .5 + j * E8, .3 + .06 * j, .28)
    # ごく弱い持続音（和音の根音と5度）
    tt = np.arange(N) / SR; ci = (tt // CH).astype(int) % 8; root = np.array([mtf(PROG[i][0] - 12) for i in range(8)])[ci]; fifth = np.array([mtf(PROG[i][2] - 12) for i in range(8)])[ci]
    ph1 = 2 * np.pi * np.cumsum(root) / SR; ph2 = 2 * np.pi * np.cumsum(fifth) / SR; pad = (np.sin(ph1) + .6 * np.sin(ph2)) * .012 * (1 + .3 * np.sin(2 * np.pi * tt / 11)); st += pad[:, None].astype(np.float32)
    st = K.room(st, .12, .8); env = np.minimum(1, tt / 2) * np.minimum(1, (tt[-1] - tt) / 3); st *= env[:, None]
    pk = float(np.percentile(np.abs(st), 99.95)) or 1; st = np.tanh(st / pk * 1.1) * .62
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())
def mtf(m): return 440.0 * 2 ** ((m - 69) / 12)

def render(r, tl, a, b, path):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for i in range(a, b): p.stdin.write(np.ascontiguousarray(make_frame(r, tl[i])).tobytes())
    p.stdin.close(); p.wait()

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] != "search":
    m = sys.argv[1]; r = simulate(SEED, record=True); tl = timeline(r); print("長さ", round(len(tl) / FPS / 60, 2), "分 勝ち", tname(r["winner"]), flush=True)
    if m == "stills":
        for x in sys.argv[2].split(","): Image.fromarray(make_frame(r, tl[int(float(x) * FPS)])).save(f"{B}/s_{float(x):07.1f}.jpg", quality=90)
    elif m == "clip":
        a, b, out = float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]; render(r, tl, int(a * FPS), int(b * FPS), f"{B}/c.mp4"); audio(r, tl, f"{B}/a.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{B}/c.mp4", "-ss", str(a), "-t", str(b - a), "-i", f"{B}/a.wav", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out], check=True)
    elif m == "all":
        out = sys.argv[2] if len(sys.argv) > 2 else f"output/race1_{LANG}.mp4"; n = len(tl); q = n // 3
        import multiprocessing as mp
        ps = [mp.Process(target=render, args=(r, tl, a, b, f"{B}/p{k}.mp4")) for k, (a, b) in enumerate(((0, q), (q, 2 * q), (2 * q, n)))]; [p.start() for p in ps]; audio(r, tl, f"{B}/a.wav"); [p.join() for p in ps]
        open(f"{B}/l.txt", "w").write("".join(f"file 'p{k}.mp4'\n" for k in range(3)))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{B}/l.txt", "-i", f"{B}/a.wav", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True); print(out)
