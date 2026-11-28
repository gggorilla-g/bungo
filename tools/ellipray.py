# ellipray.py — 楕円の鏡の中で、光は焦点に着くたびに2本に分かれる。光は楕円を埋めつくせる？ 埋まったら早回しで巻きもどり、最初にもどってループする（縦のショート 1080×1920・60コマ）
#   持ち主 11/28：向かい合った2枚の皿の中で光がふえていく動画（録画）を見せて
#     「これのスケール感スピード感とかサイズ感をかなり真似て欲しい。あとさいごは…かなり何度も高密度になって最終的には虹ベタになり
#       かなり早いキュルキュルキュルキュルみたいな巻き戻しが入って頭からループするという機構。うまい。おとは234でいい」
#   まねたのは、大きさ・速さの感じ（形が画面いっぱい、光が1〜2秒で横切る、数字が大きい）と、流れ（倍々にふえる → ぜんぶ埋まる → 早回しの巻きもどし → 頭につながる）。
#   形・決まり・色・字・音は自前：
#     ・形は楕円の鏡。楕円では、焦点から出た光は、どこで はね返っても、もう1つの焦点を通る。道のりはどの向きでも同じ（長いほうの直径と同じ長さ）なので、全部が同じ瞬間に着く（本当の性質）
#     ・焦点に着いた光は、左右に直角に2本に分かれる（この動画の中だけの決まり）。2秒ごとに数が2倍：1 → 2 → 4 → … → 8,192
#     ・光が通った所は、場所で決まる色（中心のまわりを一周する虹）に光る。全部通ると、虹で埋まる
#   音：2・3・4（木・竹・空洞のある木）のうち1つ（動画ごとに回す）。光が鏡に当たった瞬間に1打。高い所に当たるほど高い音。和音はカノン進行（2秒ごとに1つ進む）。
#       焦点に集まった瞬間にも1打（全部が1点でぶつかる）。巻きもどしの音は、それまでの音を逆向きに早回ししたもの（足した音ではない）
#   python3 tools/ellipray.py stills ／ zoom ／ all（LANG_OUT=en で英語、MAT=wood|bamboo|hollow）→ output/ellipray1_<ja|en>.mp4
import math, os, sys, wave
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendkit as T
import kalimba as K

W, H, FPS = T.W, T.H, T.FPS
MAT = os.environ.get("MAT", "stone")                                    # 持ち主 11/28「二百三十四ではなく。少し空洞のある石や宝石をたたいてかつ音階がある音」→ kalimba の stone
CX, CY, A, B = 540.0, 1046.0, 606.0, 476.0; C = math.sqrt(A * A - B * B); F = [(CX, CY - C), (CX, CY + C)]   # 楕円（縦長）と、2つの焦点（上・下）
G, TP = 19, 2.75; V = 2 * A / TP                                         # 世代の数（0〜13）、1世代の長さ（秒）、光の速さ（px/秒）
TFWD = G * TP; HOLD, TREW = .9, 1.4; DUR = TFWD + HOLD + TREW; NF = int(round(DUR * FPS)); TH0 = math.radians(-62)
LW = 1                                                                  # 光の線の太さ（px）。通るたびに明るさが足されていくので、こみぐあいが段階的に見える（持ち主 11/28「密度高めて…エスカレーションはもっと段階欲しい」）
KS = [1, 2, 4, 8, 16, 26, 36, 46, 56, 66, 76, 86, 96, 106, 116, 126, 134, 142, 150]     # 1世代に鳴らす打の数

def wall(f, th):
    """焦点 f（0＝上、1＝下）から角度 th に出た光が、鏡に当たる点と、そこまでの長さ"""
    fx, fy = F[f]; dx, dy = np.cos(th), np.sin(th); X0, Y0 = (fx - CX) / B, (fy - CY) / A; ux, uy = dx / B, dy / A
    a_ = ux * ux + uy * uy; b_ = 2 * (X0 * ux + Y0 * uy); c_ = X0 * X0 + Y0 * Y0 - 1; s = (-b_ + np.sqrt(b_ * b_ - 4 * a_ * c_)) / (2 * a_); return fx + s * dx, fy + s * dy, s
GEN = []; _th = np.array([TH0])
for _g in range(G):
    f = _g % 2; px, py, l1 = wall(f, _th); f2 = 1 - f; ph = np.arctan2(F[f2][1] - py, F[f2][0] - px)                 # ph＝次の焦点に着く時の向き
    GEN.append(dict(f=f, n=len(_th), ux=np.cos(_th), uy=np.sin(_th), px=px, py=py, l1=l1, wx=np.cos(ph), wy=np.sin(ph)))
    _th = np.concatenate([ph + math.pi / 2, ph - math.pi / 2])                                                              # 左右に直角に分かれる

def polys(g, d):
    """世代 g の光を、出てから d だけ進んだ所までの折れ線にする（8倍の整数座標）。頭の位置も返す"""
    q = GEN[g]; fx, fy = F[q["f"]]; pre = d <= q["l1"]; e = np.maximum(0, d - q["l1"])
    hx = np.where(pre, fx + d * q["ux"], q["px"] + e * q["wx"]); hy = np.where(pre, fy + d * q["uy"], q["py"] + e * q["wy"])
    f0 = (int(round(fx * 8)), int(round(fy * 8))); P = np.stack([q["px"], q["py"]], 1); Hd = np.stack([hx, hy], 1); out = []
    for i in range(q["n"]):
        out.append(np.array([f0, np.round(Hd[i] * 8)] if pre[i] else [f0, np.round(P[i] * 8), np.round(Hd[i] * 8)], np.int32))
    return out, hx, hy
MK = [np.zeros((H, W), np.float32)]                                     # MK[g]＝世代 g がはじまる時までに、光が何回通ったか（重なるほど大きい）
def LWG(g): return 1 + g // 5                                           # 軌跡の太さ：段階が進むごとに少しずつ太く（1→4px）（11/28「軌跡をほんのちょっとずつ太くしてもいい」）
def layer(pl, g=0):
    m = np.zeros((H, W), np.uint8); cv2.polylines(m, pl, False, 255, LWG(g), cv2.LINE_AA, 3); return m.astype(np.float32) / 255
def mask_at(g):
    while len(MK) <= g:
        k = len(MK) - 1; MK.append(MK[k] + WG(k) * layer(polys(k, 2 * A)[0], k))
    return MK[g]
KD = .48                                                                # 明るさ＝1−exp(−KD×通った回数)
def WG(g): return max(1.0, 4.0 * .78 ** g)                                 # 光が少ないうちは1本を明るく（はじめが暗すぎないように）

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); EL = ((xx - CX) / B) ** 2 + ((yy - CY) / A) ** 2; INS = EL < 1.0
def rainbow():
    """場所で決まる色：楕円の中心のまわりを一周する虹。中心に近いほど白っぽい"""
    h = (np.arctan2(yy - CY, xx - CX) / (2 * np.pi) + .62) % 1.0; r = np.sqrt(np.clip(EL, 0, 1)); s = .30 + .58 * r ** .8; hsv = np.dstack([h * 179.99, s * 255, np.full_like(h, 255)]).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB).astype(np.float32) / 255
RB = rainbow()
def make_bg():
    b = np.array([7, 8, 20], np.float32)[None, None] * np.ones((H, W, 1), np.float32) + (np.exp(-(((xx - CX) / 620) ** 2 + ((yy - CY) / 800) ** 2)) * 9)[..., None] * np.array([.8, .9, 1.6], np.float32)
    b = b / 255; rim = np.exp(-((np.sqrt(EL) - 1) * 520 / 2.2) ** 2); glow = np.exp(-((np.sqrt(EL) - 1) * 520 / 13) ** 2) * .07       # 鏡のふち（白い細い線と、やわらかい光）
    return (1 - (1 - b) * (1 - np.clip(rim * .95 + glow, 0, 1)[..., None] * np.array([.93, .96, 1.0], np.float32))).astype(np.float32)
BG = make_bg(); GS = T.glow(16); GF = T.glow(60); NIN = float(INS.sum())
INK = (244, 246, 255, 255); GOLD = (255, 222, 150, 255); SOFT = (176, 186, 214, 255)

def frame_at(ts, rew=0.0):
    """ts＝動画の中の時刻（0〜TFWD）。巻きもどし中は ts が小さくなっていく（rew＝巻きもどしの進み 0〜1。字のためだけに使う）"""
    g = min(G - 1, int(ts // TP)); d = min(2 * A, V * (ts - g * TP)); q = GEN[g]; acc = mask_at(g); pl, hx, hy = polys(g, d)
    if d > .5: acc = acc + WG(g) * layer(pl, g)
    mf = 1 - np.exp(-KD * acc); lit = 100 * float((acc[INS] > .35).sum()) / NIN                                                          # うまった＝1回でも通った所
    a = mf[..., None]; buf = BG * (1 - a) + RB * a
    # 光の頭：同時に出たので、焦点を中心にした輪（波の面）になって進む
    n = q["n"]
    # 玉（光の頭）は数が多くても1つずつ見えるように、いつも白い点で描く。光らせない（持ち主 11/28「玉は常に表示で発光も最低限」）
    rr = 5.0 if n <= 64 else 3.6 if n <= 512 else 2.6 if n <= 4096 else 2.0
    if n <= 4096:
        dots = np.zeros((H, W), np.uint8); pts = np.round(np.stack([hx, hy], 1) * 8).astype(np.int32)
        for pxy in pts: cv2.circle(dots, (int(pxy[0]), int(pxy[1])), int(rr * 8), 255, -1, cv2.LINE_AA, 3)
        df = dots.astype(np.float32) / 255
    else:                                                                  # 数が多い時は、1つずつ小さな点を打つ（まとめて計算）
        df = np.zeros((H, W), np.float32); ix = np.clip(np.round(hx).astype(int), 1, W - 2); iy = np.clip(np.round(hy).astype(int), 1, H - 2)
        for ox, oy in ((0, 0), (1, 0), (0, 1), (1, 1)): df[iy + oy, ix + ox] = 1.0
    df = df[..., None]; buf[:] = buf * (1 - df) + df
    for k in (0, 1):                                                       # 焦点の印。集まった瞬間（世代のはじまり）に光る
        e = ts - g * TP if (g >= 1 and q["f"] == k) else (TP if g == 0 or ts < TFWD else 9)
        if ts >= TFWD - 1e-6 and (G % 2) == k: e = 0.0 if rew == 0 else 9
        if e < .4: T.add_glow(buf, GS, F[k][0], F[k][1], (255, 255, 255), .45 * math.exp(-e / .10))                       # 焦点に集まった瞬間だけ、小さく光る
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(ov)
    for k in (0, 1): dr.ellipse([F[k][0] - 9, F[k][1] - 9, F[k][0] + 9, F[k][1] + 9], outline=(255, 255, 255, 235), width=3)
    if g < 2 and rew == 0:                                                 # はじめだけ「焦点」と書く
        al = int(255 * (1 - T.sstep(2.6, 3.6, ts)))
        for k in (0, 1): dr.text((F[k][0] + 22, F[k][1] - 2), T.tr("焦点", "focus"), font=T.fnt(30, False), fill=(214, 222, 244, al), anchor="lm", stroke_width=3, stroke_fill=(7, 8, 20, al))
    T.fit_text(dr, (W / 2, 132), T.tr("光は、楕円の鏡を埋めつくせる？", "Can light fill an elliptical mirror?"), 62, 1010, INK)
    T.fit_text(dr, (W / 2, 210), T.tr("焦点に着くたびに、左右に2本に分かれる", "At each focus it splits in two, left and right"), 42, 1010, GOLD)
    done = ts >= TFWD - 1e-6; cnt = n
    dr.text((58, 296), T.tr("光の数", "Rays"), font=T.fnt(32, False), fill=SOFT, anchor="lm"); dr.text((54, 368), f"{cnt:,}", font=T.fnt(84), fill=INK, anchor="lm")
    dr.text((W - 58, 296), T.tr("うまった", "Filled"), font=T.fnt(32, False), fill=SOFT, anchor="rm"); dr.text((W - 54, 368), f"{lit:.1f}%", font=T.fnt(84), fill=GOLD, anchor="rm")
    cap = None
    if rew > 0: cap = (T.tr("◀◀ 巻きもどし", "◀◀ Rewind"), 1.0, INK)
    elif done: cap = (T.tr("虹で埋まった", "Filled with a rainbow"), 1.0, GOLD)
    else:
        for (ta, tb, s_) in CAPS:
            if ta <= ts < tb: cap = (s_, min(1, (ts - ta) / .3) * min(1, (tb - ts) / .35), (255, 232, 170, 255))
    if cap: T.fit_text(dr, (W / 2, 1752), cap[0], 44, 1010, cap[2][:3] + (int(255 * cap[1]),))
    return np.asarray(Image.alpha_composite(Image.fromarray(T.to_frame(buf, None, grain=int(ts * FPS))).convert("RGBA"), ov).convert("RGB"))
CAPS = [(2.6, 8.4, T.tr("楕円では、どの向きの光も同じ瞬間に次の焦点に着く", "In an ellipse, every ray reaches the other focus at the same moment")),
        (9.0, 17.0, T.tr("着くたびに、光の数は2倍", "Every arrival doubles the number of rays"))]
def sim_time(t):
    """動画の時刻 → 中の時刻。進む（TFWD まで）→ 止まる（HOLD）→ 早回しでもどる（TREW）。最後は 0 にもどるので、頭につながる"""
    import loopkit as L
    if not L.REWIND: return min(t, TFWD), 0.0                              # 巻きもどしなし（11/28）
    if t <= TFWD: return t, 0.0
    if t <= TFWD + HOLD: return TFWD, 0.0
    x = min(1.0, (t - TFWD - HOLD) / TREW); return max(0.0, TFWD * (1 - T.sstep(0, 1, x) ** .9)), max(1e-3, x)
def make_frame(fi):
    import loopkit as L
    ts, rew = sim_time(fi / FPS)
    if not L.REWIND: return frame_at(ts, 0.0)
    return frame_at(ts, rew if fi < NF - 1 else 0.0) if fi < NF - 1 else frame_at(0.0)

def audio(path):
    fwd = TFWD + HOLD; a = T.Audio(fwd, lo=62, hi=88, mat=MAT, max_same=3, window=.008)
    for g, q in enumerate(GEN):
        # 鏡に当たった瞬間に1打。高い所ほど高い音。数がふえたら全部は鳴らせないので、時刻の順に等間隔で選ぶ（1世代に最大 KMAX 打。世代が進むほど多く、1打は小さく）
        k_ = min(q["n"], KS[g]); order = np.argsort(q["l1"]); pick = order[np.round(np.linspace(0, q["n"] - 1, k_)).astype(int)]; vel = .8 / k_ ** .30
        for i in pick: a.hit(g * TP + q["l1"][i] / V, float(np.clip((CY + A - q["py"][i]) / (2 * A), 0, .999)), vel=vel, chord=g % 8)
        if g >= 1: a.note(g * TP, K.CANON[g % 8][0] + 24, vel=min(.62, .36 + .02 * g), pan=.5)                                                  # 焦点に集まった瞬間（全部が1点でぶつかる）
    a.note(TFWD, K.CANON[G % 8][0] + 24, vel=.62, pan=.5); tmp = path + ".fwd.wav"
    import loopkit as L; ns = int(T.SR * fwd)
    under = None                                                           # 鼓動は入れない（持ち主 11/28「鼓動はいらないかも」）   # 隠し味の鼓動（持ち主 11/28「グルーブではなくて調和」）：和音の根音で、和音1つに2拍
    n = a.write(tmp, under=under)
    with wave.open(tmp) as w: x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
    os.remove(tmp); sr = T.SR; n_out = int(sr * TREW); pitch = 2.6; mono = x[: int(sr * TFWD)].mean(1)[::-1]; n_mid = int(n_out * pitch)             # 巻きもどしの音：それまでの音を逆向きに早回し
    grain = int(sr * .03); hop = grain // 2; ratio = (len(mono) - grain) / n_mid; mid = np.zeros(n_mid + grain, np.float32); win = np.hanning(grain).astype(np.float32)
    for k in range(0, n_mid - grain, hop): s0 = int(k * ratio); mid[k:k + grain] += mono[s0:s0 + grain] * win
    tt = np.arange(n_out) / sr; pos = (n_mid / TREW) * (tt + (.25 / (2 * np.pi * 11)) * np.sin(2 * np.pi * 11 * tt)); y = np.interp(np.clip(pos, 0, n_mid - 1), np.arange(n_mid + grain), mid)   # 回る速さが少しゆれる（キュルキュル）
    y = K._lp(y.astype(np.float32), 5200); dense = np.sqrt((x[int(sr * (TFWD - 6)):int(sr * TFWD)] ** 2).mean()) + 1e-9; y *= .62 * dense / (np.sqrt((y ** 2).mean()) + 1e-9)
    import loopkit as L
    y *= np.minimum(1, tt / .02) * np.minimum(1, (TREW - tt) / .12) * (1.0 if L.REWIND else 0.0); N = int(sr * DUR); out = np.zeros((N, 2), np.float32); out[: len(x)] = x[:N]; a0 = int(sr * fwd); k = min(n_out, N - a0); out[a0:a0 + k] += y[:k, None]
    out *= (1.0 if L.REWIND else np.clip((N - np.arange(N)) / (sr * 1.6), 0, 1)[:, None]); out = np.tanh(out * 1.2) / 1.2
    with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes((out * 32767).astype(np.int16).tobytes())
    return n

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"; os.makedirs("build_ellipray", exist_ok=True)
    print("長さ", round(DUR, 2), "世代", G, "最後の光の数", GEN[-1]["n"], "速さ(px/秒)", round(V), "材質", MAT)
    if cmd == "lit":                                                       # 世代ごとの「うまった」
        for g in range(G + 1): print(g, GEN[min(g, G - 1)]["n"], round(100 * float((mask_at(g)[INS] > .35).sum()) / NIN, 1), round(float((1 - np.exp(-KD * mask_at(g)))[INS].mean()), 3))
        sys.exit()
    if cmd == "stills": print(T.stills(NF, make_frame, "build_ellipray/s", at=(5.0 / DUR, 22.0 / DUR, 33.5 / DUR, 41.5 / DUR, 47.5 / DUR, (TFWD + .5) / DUR))); sys.exit()
    if cmd == "zoom":
        for name, tt_, box in (("a", 5.2, (0, 240, 1080, 1700)), ("b", 17.3, (0, 240, 1080, 1700)), ("c", TFWD + .4, (0, 240, 1080, 1700))): Image.fromarray(make_frame(int(tt_ * FPS))).crop(box).save(f"build_ellipray/z_{name}.png")
        sys.exit()
    if cmd == "audio": print(audio("build_ellipray/a.wav")); sys.exit()
    out = f"output/ellipray1_{T.LANG}.mp4"; audio("build_ellipray/a.wav"); T.encode(NF, make_frame, "build_ellipray/a.wav", out); print(out)
