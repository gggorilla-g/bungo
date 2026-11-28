# windowrain.py — 雨の夜の車の窓。しずくがくっつくたびに音が鳴る。大きくなったしずくは流れ落ち、通り道のしずくを集めていく。最後はワイパーがふき取って、最初の窓にもどる（縦のショート）
#   持ち主 11/28：mergeball1 に付いたコメント「なんか雨の日の車内で窓見てる気分」を見せて「この水滴がくっつくみたいなギミックで一本ヒーリング作れそう」
#   決まり（本物のしずくと同じ向き）
#     ・しずくは少しずつ増える。ふれ合ったしずくはくっついて1つになる（面積が足される）
#     ・ある大きさをこえたしずくは、重さで流れ落ちる。大きいほど速い。通り道に小さなしずくを残し、通り道のしずくを集めていく
#     ・しずくはレンズになるので、うしろの街の灯りが上下さかさまに小さく映る
#   音：しずくがくっついた瞬間に1打。大きいしずくほど低い音（カノン進行の和音の音）。ガラス石の音（kalimba の stone）＋瞑想のエコー。うしろに小さな雨の音
#       最後は雨が強くなって（音も密に）、ワイパーが1回ふき取る（テンポが変わる。持ち主 11/28「動画の最後だけ…リズムテンポ変える」）
#   python3 tools/windowrain.py stills ／ all（LANG_OUT=en で英語）→ output/windowrain1_<ja|en>.mp4
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS = T.W, T.H, T.FPS
GX0, GY0, GX1, GY1 = 40, 430, 1040, 1740                                # 窓（ガラス）の範囲
RSL = 32.0; TW = 50.0; TWIPE = 2.2; DUR = TW + TWIPE + 2.2; NF = int(DUR * FPS)   # 流れ出す半径、ワイパーが動き出す時刻、ふく時間
SEED = int(os.environ.get("SEED", "3"))

def rate(t): return 6 + 7 * (t / TW) ** 1.5 + (12 if t > TW - 6 else 0) * min(1, (t - TW + 6) / 2) if t < TW else 8.0   # 1秒に生まれるしずく（だんだん増え、最後の6秒は本降り。ふいたあとも降りつづける）
def simulate():
    rng = np.random.default_rng(SEED); D = [dict(x=float(rng.uniform(GX0 + 10, GX1 - 10)), y=float(rng.uniform(GY0 + 10, GY1 - 30)), r=float(rng.uniform(5, 14)), vy=0.0, sl=False, ph=float(rng.uniform(0, 6.3)), trail=0.0, id=-1 - k) for k in range(70)] + [dict(x=float(GX0 + (GX1 - GX0) * (.15 + .23 * q)), y=float(GY0 + 60 + 140 * (q % 2)), r=33.0 + 2 * q, vy=0.0, sl=True, ph=float(q), trail=0.0, id=-200 - q) for q in range(4)]; frames = []; ev = []; dt = 1 / (FPS * 2); t = 0.0; nid = 0   # 最初から窓にしずくがあり、大きいしずく4つは最初から流れ落ちる（冒頭から動きが見える。11/28「冒頭からわかりやすい変化」）
    for fi in range(NF):
        for _ in range(2):
            t += dt
            for _ in range(rng.poisson(rate(t) * dt)):                  # 生まれる
                r = float(rng.uniform(6.0, 13.0) * (1.5 if rng.random() < .2 else 1)); D.append(dict(x=float(rng.uniform(GX0 + 10, GX1 - 10)), y=float(rng.uniform(GY0 + 10, GY1 - 30)), r=r, vy=0.0, sl=False, ph=float(rng.uniform(0, 6.3)), trail=0.0, id=nid)); nid += 1
            for d in D:                                                  # 流れる（止まっているしずくは、くもりを集めて少しずつ大きくなる）
                if not d["sl"] and t < TW: d["r"] += .22 * dt
                if d["r"] > RSL: d["sl"] = True
                if d["sl"]:
                    vt = 70 + 34 * (d["r"] - RSL); d["vy"] += (vt - d["vy"]) * dt / .4; dy = d["vy"] * dt; d["y"] += dy; d["x"] += 9 * math.sin(d["y"] / 37 + d["ph"]) * dt * d["vy"] / 60; d["trail"] += dy
                    if d["trail"] > 22 and d["r"] > RSL * .8:            # 通り道に小さなしずくを残す
                        d["trail"] = 0.0; rr = float(rng.uniform(1.6, 2.8)); D.append(dict(x=d["x"] + float(rng.uniform(-2, 2)), y=d["y"] - d["r"] * 1.1, r=rr, vy=0.0, sl=False, ph=0.0, trail=0.0, id=nid)); nid += 1; d["r"] = math.sqrt(max(4.0, d["r"] ** 2 - rr ** 2))
                        if d["r"] < RSL * .75: d["sl"] = False; d["vy"] = 0.0
            if len(D) > 1:                                               # くっつく
                X = np.array([[d["x"], d["y"], d["r"]] for d in D]); dx = X[:, 0, None] - X[None, :, 0]; dy = X[:, 1, None] - X[None, :, 1]; rs = X[:, 2, None] + X[None, :, 2]
                ii, jj = np.where(np.triu(dx * dx + dy * dy < (rs * .92) ** 2, 1)); dead = set()
                for i, j in zip(ii, jj):
                    if i in dead or j in dead: continue
                    a, b = D[i], D[j]
                    if b["r"] > a["r"] or b["sl"]: a, b, i, j = b, a, j, i
                    A1, A2 = a["r"] ** 2, b["r"] ** 2; a["x"] = (a["x"] * A1 + b["x"] * A2) / (A1 + A2); a["y"] = (a["y"] * A1 + b["y"] * A2) / (A1 + A2) if not a["sl"] else a["y"]; a["r"] = math.sqrt(A1 + A2); dead.add(j)
                    if b["r"] > 2.5: ev.append((t, a["r"], a["x"]))
                D = [d for k, d in enumerate(D) if k not in dead]
            if t > TW:                                                   # ワイパー：窓の下の中心を軸にまわる棒がふき取る
                ang = wiper_angle(t)
                D = [d for d in D if not wiped(d["x"], d["y"], ang)]
            D = [d for d in D if d["y"] < GY1 + 30]
        frames.append(np.array([[d["x"], d["y"], d["r"], 1.0 if d["sl"] else 0.0] for d in D], np.float32).reshape(-1, 4))
    return frames, ev
WPX, WPY, WPL = 540.0, GY1 + 120, 1800.0                               # ワイパーの軸（窓の下）と長さ
def wiper_angle(t):
    u = min(1.0, max(0.0, (t - TW) / TWIPE)); return math.pi * (1 - T.sstep(0, 1, u)) if u < 1 else 0.0   # 左（π）から右（0）へ一往復の半分
def wiped(x, y, ang):
    a = math.atan2(-(y - WPY), x - WPX); return a > ang and math.hypot(x - WPX, y - WPY) < WPL
FR, EV = simulate()

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
def city():
    """うしろの夜の街：ぼけた灯り（選んだ配色：琥珀・珊瑚・薔薇・すみれ・青緑）"""
    rng = np.random.default_rng(7); b = np.zeros((H, W, 3), np.float32)
    b += (np.array([14, 18, 40], np.float32) * (1 - yy / H)[..., None] + np.array([30, 22, 46], np.float32) * (yy / H)[..., None]) / 255
    pal = np.array([(255, 196, 120), (246, 140, 110), (222, 110, 150), (150, 120, 220), (100, 190, 200)], np.float32) / 255
    for _ in range(46):
        x, y, r = rng.uniform(0, W), rng.uniform(H * .25, H * .95), rng.uniform(26, 90); c = pal[rng.integers(0, 5)] * rng.uniform(.35, .85)
        m = np.exp(-(((xx - x) ** 2 + (yy - y) ** 2) / (r * r)) ** 3)[..., None]; b += m * c * .32
    sharp = np.clip(b, 0, 1); blur = cv2.GaussianBlur(sharp, (0, 0), 14)
    return blur.astype(np.float32), sharp.astype(np.float32)
BGB, BGS = city()
FOG = np.zeros((H, W), np.float32); FOG[GY0:GY1, GX0:GX1] = 1; FOG = cv2.GaussianBlur(FOG, (0, 0), 6)
GLASS = (BGB * .78 + .045).astype(np.float32)                           # 窓ごしの景色（少し白くくもる）
GS = T.glow(12); INK = (244, 246, 255, 255); GOLD = (255, 222, 150, 255)
def drop(buf, x, y, r, sl):
    """しずく1つ：うしろの景色が上下さかさまに小さく映るレンズ。上が少し明るく、下のふちが暗い"""
    ry = r * (1.18 if sl else 1.0); k = int(r * 1.6) + 3; x0, y0 = int(x) - k, int(y - (ry - r)) - k - int(ry - r); w = h = 2 * k
    if x0 < 0 or y0 < 0 or x0 + w >= W or y0 + h >= H: return
    s = int(r * 3.4) + 4; sx0, sy0 = max(0, int(x) - s), max(0, int(y) - s); src = BGS[sy0:sy0 + 2 * s, sx0:sx0 + 2 * s]
    if src.shape[0] < 4 or src.shape[1] < 4: return
    lens = cv2.resize(src[::-1, ::-1], (w, h), interpolation=cv2.INTER_AREA) * 1.15 + .03
    c = (np.arange(w, dtype=np.float32) + .5 - w / 2); X, Y = np.meshgrid(c, c * (r / ry)); d = np.hypot(X, Y) / r
    a = np.clip((1 - d) * r * .9, 0, 1); rim = np.exp(-((d - .88) / .14) ** 2) * (.45 + .4 * (Y > 0)) * .75; hi = np.exp(-(((X + r * .32) ** 2 + (Y + r * .38) ** 2) / (r * r * .025))) + .35 * np.exp(-((d - .8) / .08) ** 2) * (Y < -r * .3)
    col = lens * 1.25 * (1 - rim[..., None]) + hi[..., None] * .85; reg = buf[y0:y0 + h, x0:x0 + w]; reg[:] = reg * (1 - a[..., None]) + col * a[..., None]

def make_frame(fi):
    t = fi / FPS; buf = BGB.copy(); buf = buf * (1 - FOG[..., None]) + GLASS * FOG[..., None]
    for x, y, r, sl in FR[fi]: drop(buf, x, y, r, sl > .5)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    if TW <= t <= TW + TWIPE + .1:                                       # ワイパー（黒い棒）
        a = wiper_angle(t); ex, ey = WPX + WPL * math.cos(a), WPY - WPL * math.sin(a); d.line([(WPX, WPY), (ex, ey)], fill=(8, 8, 14, 255), width=22); d.line([(WPX, WPY), (ex, ey)], fill=(40, 42, 56, 255), width=6)
    d.rounded_rectangle([GX0 - 6, GY0 - 6, GX1 + 6, GY1 + 6], radius=26, outline=(16, 16, 24, 255), width=14)
    n = int(np.searchsorted(np.array([e[0] for e in EV] + [1e9]), t, "right"))
    T.fit_text(d, (W / 2, 140), T.tr("雨の窓で、しずくがくっつくと鳴る", "Raindrops ring when they join"), 58, 1000, INK)
    d.text((W / 2, 230), T.tr(f"くっついた回数 {n}", f"Drops joined: {n}"), font=T.fnt(42), fill=(214, 224, 246, 255), anchor="mm")
    out = np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=fi)).convert("RGBA"), ov).convert("RGB"))
    g = min(T.sstep(0, .4, t), 1 - T.sstep(DUR - .8, DUR, t))
    return out if g >= .999 else (out.astype(np.float32) * g).astype(np.uint8)

def audio(path):
    a = T.Audio(DUR, mat="stone", max_same=3, window=.03, chord_len=2.4); last = -1
    for t, r, x in EV:
        if t - last < 1 / 9: continue
        last = t; tn = K.canon_tones(a.chord_index(t), 55, 88); k = int(np.clip((r - 3) / 22 * len(tn), 0, len(tn) - 1)); a.note(t, tn[len(tn) - 1 - k], vel=float(np.clip(.32 + r / 60, .32, .7)), pan=.15 + .7 * (x - GX0) / (GX1 - GX0))
    N = int(T.SR * DUR); rng = np.random.default_rng(5); n = rng.normal(0, 1, N).astype(np.float32)          # 雨の音：やわらかい息の音。強さは雨の量に合わせる
    rain = K._lp(n, 2600) - K._lp(n, 300); tt = np.arange(N) / T.SR; lvl = np.array([rate(min(x, TW + 1)) for x in tt[::480]]); lvl = np.interp(tt, tt[::480], lvl)
    rain *= (.006 + .0005 * lvl) * np.clip((DUR - tt) / 1.5, 0, 1)
    body = K.pad([(r, r + 12, f5 + 12) for (r, t3, f5) in K.CANON], 2.4, DUR, .03)[:N]
    return a.write(path, room=(.30, 3.0), under=(rain + body[:N]).astype(np.float32))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_windowrain", exist_ok=True)
    print("長さ", round(DUR, 1), "くっついた", len(EV), "しずくの数（最後のほう）", len(FR[int((TW - .5) * FPS)]))
    if cmd == "stills": print(T.stills(NF, make_frame, "build_windowrain/s", at=(.1, .35, .6, (TW - 2) / DUR, (TW + 1.0) / DUR, (TW + TWIPE + .8) / DUR))); sys.exit()
    out = f"output/windowrain1_{T.LANG}.mp4"; audio("build_windowrain/a.wav"); T.encode(NF, make_frame, "build_windowrain/a.wav", out); print(out)
