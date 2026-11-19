# racesim.py — 「どれが先に壁を壊す？」関数レース型
#   python tools/racesim.py <spec.json> → output/<id>.mp4
#   spec: id / title / hp / rounds / round_sec / lanes: [{name, formula, rule: "const:1000" | "pow2" | "fib2" | "cube" | "lin:500", color}]
#   各回 n に、各レーンが「個数 × 1個の力」を落とす。ボールが壁に当たるたびに力の分だけ削る。壁の耐久 hp を最初に削り切ったレーンの勝ち
#   音: ボール1個ずつ当たった瞬間に1音（レーンごとに音域、回が進むほど少し上がる）。数が多いほど1音を短く小さく
import json, os, sys, math, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.signal import fftconvolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ballsim import W, H, FPS, font, SR, mtof

FIB = [0, 1, 1]
while len(FIB) < 40: FIB.append(FIB[-1] + FIB[-2])


def rule(r, n):
    """回 n の (個数, 1個の力)"""
    if r.startswith("const:"): return int(r.split(":")[1]), 1
    if r == "pow2": return 2 ** n, 1
    if r == "fib2": return FIB[n], FIB[n]
    if r == "cube": return n * n, n
    if r.startswith("lin:"): return int(r.split(":")[1]) * n, 1
    raise ValueError(r)


def hexc(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def main(spec_path):
    sp = json.load(open(spec_path, encoding="utf-8")); sid = sp["id"]; os.makedirs("build_ballsim", exist_ok=True)
    lanes, HP, NR, RS = sp["lanes"], sp.get("hp", 30000), sp.get("rounds", 12), sp.get("round_sec", 2.8)
    rng = np.random.default_rng(sp.get("seed", 3)); intro, fall = .8, 1.05
    S = 2; LW = W * S / len(lanes); y_top, y_wall = 640 * S, 1500 * S; G = 2 * (y_wall - y_top) / fall ** 2
    # すべてのボール：レーン・回・出る時刻・当たる時刻・x・力
    balls = []
    for li, ln in enumerate(lanes):
        for n in range(1, NR + 1):
            cnt, pw = rule(ln["rule"], n); t0 = intro + (n - 1) * RS
            ts = t0 + rng.uniform(0, RS * .45, cnt); xs = li * LW + LW * (.12 + .76 * rng.random(cnt))
            balls.append(np.stack([np.full(cnt, li), np.full(cnt, n), ts, ts + fall, xs, np.full(cnt, pw)], 1))
    B = np.concatenate(balls); B = B[np.argsort(B[:, 3])]
    # 壁を壊した時刻（当たる順に足していく）
    broke = [None] * len(lanes); dmg_at = []
    for li in range(len(lanes)):
        m = B[:, 0] == li; hits = B[m]; cum = np.cumsum(hits[:, 5])
        k = np.searchsorted(cum, HP)
        broke[li] = hits[k, 3] if k < len(hits) else None
        dmg_at.append((hits[:, 3], cum))
    tb = min([b for b in broke if b is not None], default=None)
    winner = broke.index(tb) if tb is not None else None
    t_end = (tb + 3.0) if tb is not None else intro + NR * RS + fall + 2
    # 壊れた後は、そのレーンのボールはもう数えない。他のレーンは止める（その時点の順位を出す）
    total = t_end
    def dmg(li, t):
        tt, cum = dmg_at[li]; tc = min(t, tb) if tb is not None else t; k = np.searchsorted(tt, tc, side="right"); return int(cum[k - 1]) if k else 0
    # ---- 絵
    bg = Image.new("RGB", (W * S, H * S), (8, 9, 14)); dg = ImageDraw.Draw(bg)
    for li in range(1, len(lanes)): dg.line([li * LW, 300 * S, li * LW, 1700 * S], fill=(34, 36, 46), width=2 * S)
    fT, fN, fF, fS, fM = font(56 * S), font(40 * S), font(76 * S), font(30 * S), font(44 * S)
    out_raw = f"build_ballsim/{sid}_v.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out_raw], stdin=subprocess.PIPE)
    cols = [hexc(l["color"]) for l in lanes]
    for fi in range(int(total * FPS)):
        t = fi / FPS; im = bg.copy(); d = ImageDraw.Draw(im)
        n_now = int(min(NR, max(1, (t - intro) // RS + 1))) if t >= intro else 1
        if tb is not None and t > tb: n_now = int(B[(B[:, 3] <= tb)][-1, 1])
        w = d.textlength(sp["title"], font=fT); d.text((W * S / 2 - w / 2, 120 * S), sp["title"], font=fT, fill=(255, 255, 255), stroke_width=5 * S, stroke_fill=(0, 0, 0))
        sub = sp.get("sub", "").replace("{hp}", f"{HP:,}"); w = d.textlength(sub, font=fS); d.text((W * S / 2 - w / 2, 196 * S), sub, font=fS, fill=(170, 175, 190))
        gl = Image.new("RGB", (W * S // 6, H * S // 6)); gq = ImageDraw.Draw(gl)
        for li, ln in enumerate(lanes):
            cx = (li + .5) * LW; c = cols[li]
            w = d.textlength(ln["name"], font=fN); d.text((cx - w / 2, 290 * S), ln["name"], font=fN, fill=(220, 222, 230))
            w = d.textlength(ln["formula"], font=fF); d.text((cx - w / 2, 345 * S), ln["formula"], font=fF, fill=c)
            cnt, pw = rule(ln["rule"], n_now)
            for k_, (lab, val) in enumerate([(sp.get("lab_balls", "個数"), f"{cnt:,}"), (sp.get("lab_power", "1個の力"), f"{pw:,}")]):
                xx = cx - LW * .22 + k_ * LW * .44; w = d.textlength(lab, font=fS); d.text((xx - w / 2, 460 * S), lab, font=fS, fill=(150, 155, 170))
                w = d.textlength(val, font=fM); d.text((xx - w / 2, 498 * S), val, font=fM, fill=c)
            nl = f"n = {n_now}"; w = d.textlength(nl, font=fS); d.text((cx - w / 2, 560 * S), nl, font=fS, fill=(120, 125, 140))
            # 壁（残りの耐久に合わせて薄くなる。壊れたら破片）
            dm = dmg(li, t); left = max(0, 1 - dm / HP); x0, x1 = li * LW + 18 * S, (li + 1) * LW - 18 * S
            if broke[li] is not None and tb is not None and li == winner and t > tb:
                k = t - tb; r2 = np.random.default_rng(li)
                for j in range(14):
                    px_ = x0 + (x1 - x0) * (j + .5) / 14 + r2.uniform(-20, 20) * S * k; py = y_wall + 40 * S * k + 900 * S * k * k * r2.uniform(.5, 1)
                    d.rectangle([px_ - 14 * S, py, px_ + 14 * S, py + 30 * S], fill=c)
            else:
                d.rectangle([x0, y_wall, x1, y_wall + 46 * S], fill=tuple(int(v * (.25 + .75 * left)) for v in c), outline=c, width=3 * S)
            # 耐久のバー
            yb = y_wall + 90 * S; d.rounded_rectangle([x0, yb, x1, yb + 18 * S], radius=9 * S, fill=(40, 42, 52))
            d.rounded_rectangle([x0, yb, x0 + (x1 - x0) * min(1, dm / HP), yb + 18 * S], radius=9 * S, fill=c)
            tx = f"{min(dm, HP):,} / {HP:,}"; w = d.textlength(tx, font=fS); d.text((cx - w / 2, yb + 34 * S), tx, font=fS, fill=(210, 212, 222))
            if tb is not None and t > tb:
                lab = sp.get("win_label", "勝ち") if li == winner else ""
                if lab: w = d.textlength(lab, font=fF); d.text((cx - w / 2, 1000 * S), lab, font=fF, fill=(255, 255, 255), stroke_width=7 * S, stroke_fill=c)
        # ボール（落ちている最中のものだけ）
        m = (B[:, 2] <= t) & (B[:, 3] > t)
        if tb is not None and t > tb: m &= False
        for li_, n_, t0, t1, x, pw in B[m]:
            y = y_top + .5 * G * (t - t0) ** 2; rr = (3 + 2.2 * math.sqrt(pw)) * S; c = cols[int(li_)]
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=c); gq.ellipse([x / 6 - rr / 3, y / 6 - rr / 3, x / 6 + rr / 3, y / 6 + rr / 3], fill=c)
        # 当たった瞬間の火花（0.12秒）
        mh = (B[:, 3] <= t) & (B[:, 3] > t - .12)
        if tb is not None: mh &= B[:, 3] <= tb
        for li_, n_, t0, t1, x, pw in B[mh][-400:]:
            k = (t - t1) / .12; rr = (4 + 6 * k) * S * (1 + .3 * math.sqrt(pw)); c = cols[int(li_)]
            gq.ellipse([x / 6 - rr / 3, y_wall / 6 - rr / 3, x / 6 + rr / 3, y_wall / 6 + rr / 3], fill=c)
        gl = gl.filter(ImageFilter.GaussianBlur(4)).resize((W * S, H * S), Image.BILINEAR)
        im = Image.fromarray(np.clip(np.asarray(im, np.int16) + (np.asarray(gl, np.int16) * .8).astype(np.int16), 0, 255).astype(np.uint8))
        p.stdin.write(im.resize((W, H), Image.LANCZOS).tobytes())
    p.stdin.close(); p.wait()
    # ---- 音：ボール1個ずつ。同じレーン・同じ回のボールは同じ音色なので、当たる時刻の列に1音をたたみこむ
    n = int(SR * (total + 2)); L = np.zeros(n); R = np.zeros(n)
    base = sp.get("lane_midi", [60, 67, 72]); scale = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24, 26]
    for li in range(len(lanes)):
        pan = .5 if len(lanes) == 1 else .15 + .7 * li / (len(lanes) - 1)
        for rn in range(1, NR + 1):
            m = (B[:, 0] == li) & (B[:, 1] == rn);
            if tb is not None: m &= B[:, 3] <= tb
            if not m.any(): continue
            cnt = int(m.sum()); f = mtof(base[li] + scale[(rn - 1) % len(scale)]); dec = 5 + 4 * math.sqrt(cnt / 10)
            tt = np.arange(int(SR * min(1.2, 6 / dec))) / SR
            tone = (np.sin(2 * np.pi * f * tt) + .28 * np.sin(2 * np.pi * f * 4 * tt) * np.exp(-tt * 20)) * np.exp(-tt * dec) * np.minimum(1, tt / .003)
            imp = np.zeros(n); idx = (B[m, 3] * SR).astype(int); np.add.at(imp, idx[idx < n], 1 / math.sqrt(cnt) * (1 + .15 * math.sqrt(B[m, 5][idx < n])))
            y = fftconvolve(imp, tone)[:n]; L += y * (1 - pan); R += y * pan
    if tb is not None:  # 壊れた時：上がる分散和音（低い衝撃音は使わない）
        for i, mm in enumerate([72, 76, 79, 84, 88, 91]):
            tt = np.arange(int(SR * 1.4)) / SR; f = mtof(mm); s = (np.sin(2 * np.pi * f * tt) + .4 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 6)) * np.exp(-tt * 2.5)
            o = int((tb + i * .07) * SR); k = min(len(s), n - o); L[o:o + k] += s[:k] * .5; R[o:o + k] += s[:k] * .5
    for dly, g in [(.031, .3), (.067, .24), (.113, .18), (.171, .13), (.257, .09)]:
        o = int(SR * dly); L[o:] += R[:-o] * g; R[o:] += L[:-o] * g
    st = np.stack([L, R], 1); st = st / (np.abs(st).max() + 1e-9) * .85; wv = f"build_ballsim/{sid}.wav"
    with wave.open(wv, "wb") as w_:
        w_.setnchannels(2); w_.setsampwidth(2); w_.setframerate(SR); w_.writeframes((st * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out_raw, "-i", wv, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", f"output/{sid}.mp4"], check=True)
    print(f"書き出し: output/{sid}.mp4  {total:.1f}秒  勝ち {winner and lanes[winner]['name'] if winner is not None else 'なし'}  壊れた時刻 {tb and round(tb, 2)}")
    for li in range(len(lanes)): print(" ", lanes[li]["name"], dmg(li, total))


if __name__ == "__main__":
    main(sys.argv[1])
