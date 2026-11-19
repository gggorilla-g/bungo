# ellipsesim.py — 「楕円の片方の焦点から打つと、全部もう片方の焦点に集まる？」型
#   python tools/ellipsesim.py <spec.json>  → output/<id>.mp4
#   spec: id / title(2行) / count_label / a / b / v / n0（最初の数）/ doubles（何回倍にするか）/ seed / end_label
#   物理: 重力なし。焦点F1から全方向へ同じ速さで打つ。楕円の壁で反射すると、どの道も長さ2aでF2を通る（楕円の性質）
#   F1に戻るたびにボールを2倍にする。音: 壁は和音の音、F2・F1に集まる瞬間は和音全体
import json, os, sys, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ballsim import W, H, FPS, hsv, font, audio

SUB = 6


def main(spec_path):
    sp = json.load(open(spec_path, encoding="utf-8"))
    sid = sp["id"]; os.makedirs("build_ballsim", exist_ok=True)
    a, b, v = sp.get("a", 1.0), sp.get("b", .8), sp.get("v", 1.5)
    c = math.sqrt(a * a - b * b); F1, F2 = np.array([0, c]), np.array([0, -c])  # 縦長：焦点は上下
    rng = np.random.default_rng(sp.get("seed", 1))
    n0, doubles = sp.get("n0", 5), sp.get("doubles", 8)
    T_half = 2 * a / v                     # F1→壁→F2 の時間
    hold = sp.get("hold", .5)              # 集まった瞬間に止める秒数
    # 時間割：各周 = F1→F2（T_half）＋止め＋F2→F1（T_half）＋止め
    cycle = 2 * (T_half + hold)
    intro = .6
    total = intro + cycle * (doubles + 1) + 2.5
    dt = 1 / (FPS * SUB)
    events = []
    S = 2; px = W * S * .40 / b; cx, cy = W * S / 2, H * S * .55
    to = lambda p: (cx + p[0] * px, cy - p[1] * px)

    def launch(n, off):
        ang = off + np.arange(n) * 2 * np.pi / n
        return np.stack([np.cos(ang), np.sin(ang)], 1)

    def path(dirs, start):
        """各ボールの、壁の当たる点（start から dirs 方向に出たときの楕円との交点）"""
        x0, y0 = start; dx, dy = dirs[:, 0], dirs[:, 1]
        A = dx * dx / (b * b) + dy * dy / (a * a); B = 2 * (x0 * dx / (b * b) + y0 * dy / (a * a)); C = x0 * x0 / (b * b) + y0 * y0 / (a * a) - 1
        tt = (-B + np.sqrt(B * B - 4 * A * C)) / (2 * A)
        return np.stack([x0 + dx * tt, y0 + dy * tt], 1), tt

    # 周ごとの状態を作っておく
    rounds = []
    n = n0
    for k in range(doubles + 1):
        dirs = launch(n, rng.uniform(0, 2 * np.pi))
        hit1, l1 = path(dirs, F1)            # F1→壁
        rounds.append(dict(n=n, hit=hit1, l1=l1, hue=np.array([(i / n + k * .13) % 1 for i in range(n)])))
        n *= 2
    # 音の出来事
    for k, rd in enumerate(rounds):
        t0 = intro + k * cycle
        for leg in range(2):
            ts = t0 + leg * (T_half + hold)
            ls = rd["l1"] if leg == 0 else 2 * a - rd["l1"]  # 戻りは F2→壁 の長さ = 2a - l1（同じ壁の点で反射）
            for i in np.argsort(ls)[:: max(1, rd["n"] // 24)]:
                h = rd["hit"][i]; events.append((ts + ls[i] / v, "wall", math.atan2(h[1], h[0]), 1.0))
            events.append((ts + T_half, "gold", -1 if leg == 0 else 1, 1.0))
    events.append((intro + (doubles + 1) * cycle - hold, "burst", 0, 1))

    # 背景
    bg = Image.new("RGB", (W * S, H * S), (6, 8, 20)); dg = ImageDraw.Draw(bg)
    for k in range(0, H * S, 8):
        cc = int(6 + 10 * (k / (H * S))); dg.rectangle([0, k, W * S, k + 8], fill=(cc // 2, cc // 2 + 2, cc + 10))
    glow = Image.new("RGB", (W * S, H * S)); gd = ImageDraw.Draw(glow)
    box = [cx - b * px, cy - a * px, cx + b * px, cy + a * px]
    gd.ellipse(box, outline=(40, 200, 255), width=26 * S); glow = glow.filter(ImageFilter.GaussianBlur(28 * S))
    bg = Image.fromarray(np.clip(np.asarray(bg, np.int16) + np.asarray(glow, np.int16), 0, 255).astype(np.uint8)); dg = ImageDraw.Draw(bg)
    dg.ellipse(box, outline=(150, 235, 255), width=9 * S)
    for F in (F1, F2):
        x, y = to(F); q = .06 * px; dg.ellipse([x - q, y - q, x + q, y + q], outline=(255, 200, 60), width=5 * S)
    fT, fC, fN = font(58 * S), font(54 * S), font(66 * S)
    out_raw = f"build_ballsim/{sid}_v.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out_raw], stdin=subprocess.PIPE)
    nf = int(total * FPS); r = .028
    for fi in range(nf):
        t = fi / FPS; im = bg.copy(); d = ImageDraw.Draw(im)
        k = int(max(0, t - intro) // cycle); k = min(k, doubles); rd = rounds[k]; u = t - intro - k * cycle
        n = rd["n"]; hit = rd["hit"]; l1 = rd["l1"]
        if t < intro: s, leg = 0, 0
        elif u < T_half: s, leg = u * v, 0
        elif u < T_half + hold: s, leg = 2 * a, 0
        elif u < 2 * T_half + hold: s, leg = (u - T_half - hold) * v, 1
        else: s, leg = 2 * a, 1
        if t > intro + (doubles + 1) * cycle - hold: k, rd, s, leg = doubles, rounds[doubles], 2 * a, 1; n, hit, l1 = rd["n"], rd["hit"], rd["l1"]
        A0, A1 = (F1, F2) if leg == 0 else (F2, F1)
        la = l1 if leg == 0 else 2 * a - l1
        cols = [hsv(h) for h in rd["hue"]]
        lw = max(1, int(3 * S * min(1, 12 / math.sqrt(n))))
        pos = np.zeros((n, 2))
        for i in range(n):
            x0, y0 = to(A0); xh, yh = to(hit[i]); col = cols[i]
            if s <= la[i]:
                f = s / la[i]; pt = A0 + (hit[i] - A0) * f; xp, yp = to(pt); d.line([x0, y0, xp, yp], fill=tuple(int(c_ * .7) for c_ in col), width=lw)
            else:
                f = min(1, (s - la[i]) / (2 * a - la[i])); pt = hit[i] + (A1 - hit[i]) * f; xp, yp = to(pt)
                d.line([x0, y0, xh, yh], fill=tuple(int(c_ * .55) for c_ in col), width=lw); d.line([xh, yh, xp, yp], fill=tuple(int(c_ * .7) for c_ in col), width=lw)
            pos[i] = (xp, yp)
        q = r * px * (1 if n <= 80 else .7)
        for i in range(n):
            xp, yp = pos[i]; col = cols[i]; d.ellipse([xp - q, yp - q, xp + q, yp + q], fill=col)
        # 集まった瞬間に光る
        if s >= 2 * a - 1e-6:
            x, y = to(A1); qq = .12 * px; d.ellipse([x - qq, y - qq, x + qq, y + qq], outline=(255, 245, 200), width=6 * S)
        for kk, line in enumerate(sp["title"]):
            w = d.textlength(line, font=fT); d.text((W * S / 2 - w / 2, 150 * S + kk * 80 * S), line, font=fT, fill=(255, 255, 255) if kk == 0 else (255, 196, 60), stroke_width=6 * S, stroke_fill=(0, 0, 0))
        lab, num = sp.get("count_label", "balls: "), f"{n:,}"
        w1, w2 = d.textlength(lab, font=fC), d.textlength(num, font=fN); x0 = W * S / 2 - (w1 + w2) / 2; yb = cy + a * px + 60 * S
        d.text((x0, yb + 8 * S), lab, font=fC, fill=(235, 235, 240), stroke_width=5 * S, stroke_fill=(0, 0, 0)); d.text((x0 + w1, yb), num, font=fN, fill=(255, 210, 70), stroke_width=6 * S, stroke_fill=(0, 0, 0))
        if t > intro + (doubles + 1) * cycle - hold and sp.get("end_label"):
            fB = font(76 * S); msg = sp["end_label"]; wb = d.textlength(msg, font=fB); d.text((W * S / 2 - wb / 2, cy - 40 * S), msg, font=fB, fill=(255, 255, 255), stroke_width=9 * S, stroke_fill=(30, 90, 200))
        p.stdin.write(im.resize((W, H), Image.LANCZOS).tobytes())
    p.stdin.close(); p.wait()
    wv = f"build_ballsim/{sid}.wav"; audio(events, total, wv)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out_raw, "-i", wv, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", f"output/{sid}.mp4"], check=True)
    print(f"書き出し: output/{sid}.mp4  {total:.1f}秒  最後のボール {rounds[-1]['n']}")


if __name__ == "__main__":
    main(sys.argv[1])
