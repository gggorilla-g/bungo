# ballsim.py — 「ボールが増えて、いつ割れる？」型の物理シミュレーション・ショート
#   python tools/ballsim.py <spec.json>   → output/<id>.mp4
#   spec: id / title (2行) / seed / dur_max / ring_r / ball_r / gold (金の点 [x,y,r] の並び) / burst_n (この数で割れる)
#         g（重力）/ v0（最初の速さ）/ scale（音階のルート）/ lang
#   物理: 円の中でボールが跳ねる（壁は完全弾性）。ボールどうしも当たる。金の点を通るたびに、その点から新しいボールが1個出る
#   音: 壁に当たるたびに和音の音を1つ（マリンバ風）。金の点は高い鈴。割れる時は上がっていく分散和音（低い衝撃音は使わない）
import json, os, sys, math, subprocess, wave
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SUB = 1080, 1920, 30, 8
if os.environ.get("SIM_LANDSCAPE"): W, H = 1920, 1080   # 長尺（横長）用
SR = 44100
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"


PALETTE = os.environ.get("SIM_PALETTE", "")   # "" = 虹色ネオン（標準）／ "amber" = オレンジ系の同系色でまとめる
WALL, WALL_GLOW = ((255, 214, 160), (255, 120, 30)) if PALETTE == "amber" else ((150, 235, 255), (40, 200, 255))


def hsv(h, s=.85, v=1.0):
    if PALETTE == "amber":   # 色相を赤橙〜琥珀（0.0〜0.13）の幅に寄せ、明るさで差をつける
        k = .5 - .5 * math.cos(2 * math.pi * (h % 1)); h, s, v = .012 + .115 * k, .78 + .12 * (1 - k), v * (.82 + .18 * k)
    i = int(h * 6) % 6; f = h * 6 - int(h * 6); p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
    return int(r * 255), int(g * 255), int(b * 255)


def simulate(sp):
    rng = np.random.default_rng(sp.get("seed", 1))
    R, r, g = sp.get("ring_r", 1.0), sp.get("ball_r", .028), sp.get("g", 1.6)
    gold = np.array(sp.get("gold", [[0, .5, .06], [0, -.5, .06]]), float)
    burst_n, dur_max = sp.get("burst_n", 600), sp.get("dur_max", 58)
    dt = 1 / (FPS * SUB)
    n0 = sp.get("n0", 4); ang = rng.uniform(0, 2 * np.pi, n0)
    P = np.stack([np.cos(ang) * .3, np.sin(ang) * .3 + .1], 1); V = np.stack([np.cos(ang + 1.3), np.sin(ang + 1.3)], 1) * sp.get("v0", 1.8); HUE = [(i * .618034) % 1 for i in range(n0)]; CD = np.zeros(n0)
    frames, events, t, burst_t = [], [], 0.0, None
    nframes = int(dur_max * FPS)
    for fi in range(nframes):
        for _ in range(SUB):
            t += dt
            V[:, 1] -= g * dt * (1 if burst_t is None else .5)
            P += V * dt
            CD -= dt
            # ボールどうし
            if len(P) > 1:
                pairs = cKDTree(P).query_pairs(2 * r, output_type="ndarray")
                if len(pairs):
                    i, j = pairs[:, 0], pairs[:, 1]
                    d = P[j] - P[i]; dist = np.linalg.norm(d, axis=1) + 1e-9; n = d / dist[:, None]
                    ov = (2 * r - dist)[:, None] * .5 * n
                    np.add.at(P, i, -ov); np.add.at(P, j, ov)
                    rv = np.einsum("ij,ij->i", V[j] - V[i], n)
                    m = rv < 0
                    imp = (-(1 + .92) * rv[m] / 2)[:, None] * n[m]
                    np.add.at(V, i[m], -imp); np.add.at(V, j[m], imp)
            # 壁
            if burst_t is None:
                dist = np.linalg.norm(P, axis=1); out = dist > R - r
                if out.any():
                    n = P[out] / dist[out, None]; vn = np.einsum("ij,ij->i", V[out], n)
                    hit = vn > 0
                    V[out] -= (2 * np.where(hit, vn, 0))[:, None] * n
                    P[out] = n * (R - r - 1e-4)
                    for k, idx in enumerate(np.where(out)[0]):
                        if hit[k] and vn[k] > .35:
                            events.append((t, "wall", math.atan2(P[idx, 1], P[idx, 0]), float(vn[k])))
                # 金の点：通ったボールから1個増える（同じボールは0.6秒待つ）
                for gx, gy, gr in gold:
                    dd = np.hypot(P[:, 0] - gx, P[:, 1] - gy); inn = (dd < gr + r) & (CD <= 0)
                    for idx in np.where(inn)[0]:
                        CD[idx] = .6
                        a = rng.uniform(0, 2 * np.pi); sp0 = rng.uniform(1.2, 2.0)
                        P = np.vstack([P, [gx + math.cos(a) * (gr + 2 * r), gy + math.sin(a) * (gr + 2 * r)]])
                        V = np.vstack([V, [math.cos(a) * sp0, math.sin(a) * sp0]])
                        CD = np.append(CD, .6); HUE.append((len(HUE) * .618034) % 1)
                        events.append((t, "gold", gy, 1.0))
                if len(P) >= burst_n:
                    burst_t = t
                    dist = np.linalg.norm(P, axis=1, keepdims=True) + 1e-9
                    V += P / dist * rng.uniform(.6, 1.8, (len(P), 1)) + np.array([0, .8])
                    events.append((t, "burst", 0, 1.0))
        frames.append((P.copy(), len(P), t, burst_t))
        if burst_t is not None and t > burst_t + 3.2:
            break
    return frames, events, np.array(HUE), gold


def font(sz):
    return ImageFont.truetype(FONT, sz, index=0)


def render(sp, frames, hue, gold, out_raw):
    S = 2  # 描くときは2倍、最後に縮める（なめらかにする）
    R = sp.get("ring_r", 1.0); r = sp.get("ball_r", .028)
    cx, cy, px = W * S / 2, H * S * .54, W * S * .44 / R
    to = lambda x, y: (cx + x * px, cy - y * px)
    # 背景：紺のグラデーションと、光る輪（ぼかしを重ねる）
    bg = Image.new("RGB", (W * S, H * S), (6, 8, 20))
    dg = ImageDraw.Draw(bg)
    for k in range(0, H * S, 8):
        c = int(6 + 10 * (k / (H * S))); dg.rectangle([0, k, W * S, k + 8], fill=(c // 2, c // 2 + 2, c + 10))
    bg0 = bg.copy()
    glow = Image.new("RGB", (W * S, H * S), (0, 0, 0)); gd = ImageDraw.Draw(glow)
    rr = R * px
    gd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(40, 200, 255), width=int(26 * S))
    glow = glow.filter(ImageFilter.GaussianBlur(28 * S))
    bg = Image.fromarray(np.clip(np.asarray(bg, np.int16) + np.asarray(glow, np.int16), 0, 255).astype(np.uint8))
    dg = ImageDraw.Draw(bg)
    dg.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(150, 235, 255), width=int(9 * S))
    for gx, gy, gr in gold:
        x, y = to(gx, gy); q = gr * px
        dg.ellipse([x - q, y - q, x + q, y + q], outline=(255, 200, 60), width=int(5 * S))
    title = sp["title"]
    cols = np.array([hsv(h) for h in hue]) if len(hue) else np.zeros((1, 3))
    fT, fC, fN = font(60 * S), font(54 * S), font(66 * S)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out_raw], stdin=subprocess.PIPE)
    trail = None
    for fi, (P, n, t, bt) in enumerate(frames):
        broken = bt is not None and t > bt
        im = (bg0 if broken else bg).copy(); d = ImageDraw.Draw(im)
        # 輪が割れたら、12個のかけらが外へ飛ぶ
        if broken:
            k = t - bt
            for j in range(12):
                a0 = j * 30 + 4; ofs = rr * (1 + .55 * k + .1 * k * k); dx, dy = math.cos(math.radians(a0 + 13)) * (ofs - rr), -math.sin(math.radians(a0 + 13)) * (ofs - rr) + 260 * S * k * k * .5
                d.arc([cx - rr + dx, cy - rr + dy, cx + rr + dx, cy + rr + dy], -a0 - 24, -a0, fill=(150, 235, 255), width=int(9 * S))
        q = r * px
        gl = Image.new("RGB", (W * S // 8, H * S // 8)); gq = ImageDraw.Draw(gl)
        for i in range(n):
            x, y = to(P[i, 0], P[i, 1]); c = tuple(int(v) for v in cols[i])
            gq.ellipse([x / 8 - q / 4, y / 8 - q / 4, x / 8 + q / 4, y / 8 + q / 4], fill=c)
        gl = gl.filter(ImageFilter.GaussianBlur(6)).resize((W * S, H * S), Image.BILINEAR)
        im = Image.fromarray(np.clip(np.asarray(im, np.int16) + (np.asarray(gl, np.int16) * .55).astype(np.int16), 0, 255).astype(np.uint8)); d = ImageDraw.Draw(im)
        for i in range(n):
            x, y = to(P[i, 0], P[i, 1]); c = tuple(int(v) for v in cols[i])
            d.ellipse([x - q, y - q, x + q, y + q], fill=c)
            d.ellipse([x - q * .45, y - q * .55, x - q * .05, y - q * .15], fill=tuple(min(255, v + 90) for v in c))
        # 文字
        for k, line in enumerate(title):
            w = d.textlength(line, font=fT)
            d.text((W * S / 2 - w / 2, 150 * S + k * 82 * S), line, font=fT, fill=(255, 255, 255) if k == 0 else (255, 196, 60), stroke_width=int(6 * S), stroke_fill=(0, 0, 0))
        lab = sp.get("count_label", "balls: ")
        s1, s2 = lab, f"{n:,}"
        w1, w2 = d.textlength(s1, font=fC), d.textlength(s2, font=fN)
        x0 = W * S / 2 - (w1 + w2) / 2; yb = cy + rr + 70 * S
        d.text((x0, yb + 8 * S), s1, font=fC, fill=(235, 235, 240), stroke_width=int(5 * S), stroke_fill=(0, 0, 0))
        d.text((x0 + w1, yb), s2, font=fN, fill=(255, 210, 70), stroke_width=int(6 * S), stroke_fill=(0, 0, 0))
        tm = f"{min(t, bt) if bt else t:.1f}s"
        wt = d.textlength(tm, font=fC); d.text((W * S / 2 - wt / 2, yb + 100 * S), tm, font=fC, fill=(170, 190, 220), stroke_width=int(4 * S), stroke_fill=(0, 0, 0))
        if bt is not None and t > bt:
            msg = sp.get("burst_label", "BURST!"); fB = font(120 * S); wb = d.textlength(msg, font=fB)
            a = min(1, (t - bt) / .3); d.text((W * S / 2 - wb / 2, cy - 80 * S), msg, font=fB, fill=(255, 255, 255), stroke_width=int(10 * S), stroke_fill=(220, 40, 90))
        p.stdin.write(im.resize((W, H), Image.LANCZOS).tobytes())
    p.stdin.close(); p.wait()


# ---- 音 ----
# 和音を2小節ごとに進める（Gmaj7 → Dmaj7 → Em7 → Aadd9 のくり返し）。壁に当たった角度で和音の中の音を選ぶ
CHORDS = [[55, 59, 62, 66, 71, 74, 78], [50, 54, 57, 61, 66, 69, 73], [52, 55, 59, 62, 67, 71, 74], [57, 59, 61, 64, 69, 71, 76]]


def mtof(m):
    return 440 * 2 ** ((m - 69) / 12)


def tone(f, dur, kind):
    t = np.arange(int(SR * dur)) / SR
    if kind == "bell":
        s = np.sin(2 * np.pi * f * t) + .45 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6) + .25 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 10)
        env = np.exp(-t * 2.2) * np.minimum(1, t / .003)
    else:  # マリンバ風
        s = np.sin(2 * np.pi * f * t) + .3 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 18) + .12 * np.sin(2 * np.pi * f * 10 * t) * np.exp(-t * 40)
        env = np.exp(-t * 4.5) * np.minimum(1, t / .002)
    return s * env


def audio(events, total, out_wav, bpm=72):
    n = int(SR * (total + 2)); L = np.zeros(n); Rr = np.zeros(n)
    bar = 4 * 60 / bpm
    last, budget = -1, []
    ev = sorted(events)
    for t, kind, a, s in ev:
        if kind == "wall":
            # 1秒あたりの音の数を抑える（多すぎると濁る）
            budget = [x for x in budget if x > t - 1]
            if len(budget) >= 14 or t - last < .045: continue
            budget.append(t); last = t
            ch = CHORDS[int(t / (bar * 2)) % 4]
            k = int(((a + np.pi) / (2 * np.pi)) * len(ch)) % len(ch)
            snd = tone(mtof(ch[k] + 12), 1.2, "mar") * min(1, .25 + s * .25) * .22
            pan = .5 + .45 * math.cos(a)
        elif kind == "note":  # 音の高さを指定（a=MIDI、s=音量、減衰を長めに）
            snd = tone(mtof(a), 1.1, "mar") * .3 * s; pan = .5
        elif kind == "gold":
            ch = CHORDS[int(t / (bar * 2)) % 4]
            snd = tone(mtof(ch[-1] + 12 + (0 if a > 0 else -5)), 1.6, "bell") * .12; pan = .5
        else:  # 割れる：上がる分散和音
            snd = np.zeros(int(SR * 2.2))
            for i, m in enumerate([62, 66, 69, 74, 78, 81, 86, 90]):
                tt = tone(mtof(m + 12), 1.4, "bell") * .2; o = int(SR * i * .07); snd[o:o + len(tt)] += tt[:len(snd) - o]
            pan = .5
        i = int(t * SR); m = min(len(snd), n - i)
        if m <= 0: continue
        L[i:i + m] += snd[:m] * (1 - pan) * 2 ** .5 * .7; Rr[i:i + m] += snd[:m] * pan * 2 ** .5 * .7
    # 簡単な残響（ずらして重ねる）
    for dly, g in [(.031, .35), (.067, .28), (.113, .22), (.171, .16), (.257, .11)]:
        o = int(SR * dly); L[o:] += Rr[:-o] * g; Rr[o:] += L[:-o] * g
    st = np.stack([L, Rr], 1); st = st / (np.abs(st).max() + 1e-9) * .85
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())


def main(spec_path):
    sp = json.load(open(spec_path, encoding="utf-8"))
    sid = sp["id"]; os.makedirs("build_ballsim", exist_ok=True); os.makedirs("output", exist_ok=True)
    frames, events, hue, gold = simulate(sp)
    total = len(frames) / FPS
    bt = frames[-1][3]
    print(f"{len(frames)} コマ（{total:.1f}秒）、割れた時刻 {bt and round(bt, 2)}、ボール {frames[-1][1]}、音 {len(events)}")
    if sp.get("dry"): return
    raw = f"build_ballsim/{sid}_v.mp4"; wv = f"build_ballsim/{sid}.wav"
    render(sp, frames, hue, gold, raw); audio(events, total, wv)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-i", wv, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", "loudnorm=I=-19:TP=-3:LRA=11", "-shortest", "-movflags", "+faststart", f"output/{sid}.mp4"], check=True)
    print("書き出し:", f"output/{sid}.mp4")


if __name__ == "__main__":
    main(sys.argv[1])
