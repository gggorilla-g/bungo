# platesim.py — 「どれが先に10枚の板を抜ける？」関数レース（板を順に壊す型）
#   python tools/platesim.py <spec.json> → output/<id>.mp4
#   spec: id / title / sub / plates（上から順の耐久の並び）/ rounds / round_sec / seed / win_label
#         lanes: [{name, formula（^で指数）, rule（racesim と同じ）, color}]
#   各回 n に、各レーンが「個数 × 1個の力」を落とす。ボールは今いちばん上に残っている板に当たり、力の分だけ削る。
#   削り切ると板が割れて、あふれた分は次の板へ。10枚とも抜けたレーンの勝ち（その瞬間に全レーン止める）
#   音: ボール1個ずつ当たった瞬間に1音。音の高さは当たった板で決まる（深い板ほど高い＝先頭のレーンほど高く聞こえる）。
#       板が割れた時は次の板の高さの鈴、ゴールは分散和音
import json, os, sys, math, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.signal import fftconvolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ballsim import W, H, FPS, font, SR, mtof
from racesim import rule, sup_text, hexc


def main(spec_path):
    sp = json.load(open(spec_path, encoding="utf-8")); sid = sp["id"]; os.makedirs("build_ballsim", exist_ok=True)
    lanes, PL, NR, RS = sp["lanes"], sp["plates"], sp.get("rounds", 14), sp.get("round_sec", 2.8)
    NP = len(PL); CUM = np.cumsum(PL); TOTAL = int(CUM[-1])
    rng = np.random.default_rng(sp.get("seed", 3)); intro, fall = sp.get("intro", .3), sp.get("fall", .85)
    S = 2; LW = W * S / len(lanes); y_top = 640 * S
    PH, PG, y0 = 34 * S, 10 * S, 1040 * S                  # 板の厚さ・すき間・1枚目の上端
    py = lambda k: y0 + k * (PH + PG)                      # k枚目の上端
    y_fin = py(NP) + 30 * S
    # ボール：レーン・回・出る・当たる・x・力
    rows = []
    for li, ln in enumerate(lanes):
        for n in range(1, NR + 1):
            cnt, pw = rule(ln["rule"], n); t0 = intro + (n - 1) * RS
            ts = t0 + rng.uniform(0, RS * .45, cnt); xs = li * LW + LW * (.14 + .72 * rng.random(cnt))
            rows.append(np.stack([np.full(cnt, li), np.full(cnt, n), ts, ts + fall, xs, np.full(cnt, pw)], 1))
    B = np.concatenate(rows); B = B[np.argsort(B[:, 3], kind="stable")]
    # tie_at（秒）があれば、全レーンがその瞬間に最後の板を抜けるように、レーンごとの板の耐久を決める（比率は plates のまま）
    PLs = [list(PL) for _ in lanes]; tie = sp.get("tie_at")
    if tie:
        for li in range(len(lanes)):
            idx = np.where((B[:, 0] == li) & (B[:, 3] <= tie))[0]; j = idx[-1]
            B[j, 3] = tie; B[j, 2] = tie - fall; tot = int(B[idx, 5].sum())
            raw = [x / sum(PL) * tot for x in PL]; q = [max(1, int(round(x))) for x in raw]; q[-1] += tot - sum(q); PLs[li] = q
        B = B[np.argsort(B[:, 3], kind="stable")]
    CUMs = [np.cumsum(q) for q in PLs]
    # レーンごとに当たった順に足して、各ボールが当たった板、各板が割れた時刻、ゴール時刻を出す
    plate_of = np.zeros(len(B), int); brk = [[None] * NP for _ in lanes]; fin = [None] * len(lanes); cums = []
    for li in range(len(lanes)):
        idx = np.where(B[:, 0] == li)[0]; c = np.cumsum(B[idx, 5]); before = c - B[idx, 5]
        CUM = CUMs[li]; plate_of[idx] = np.minimum(np.searchsorted(CUM, before, side="right"), NP)
        for k in range(NP):
            j = np.searchsorted(c, CUM[k]);
            if j < len(idx): brk[li][k] = B[idx[j], 3]
        fin[li] = brk[li][-1]; cums.append((B[idx, 3], c))
    tf = min([f for f in fin if f is not None], default=None); winner = fin.index(tf) if tf is not None else None
    total = (tf + 3.0) if tf is not None else intro + NR * RS + fall + 2
    stop = tf if tf is not None else 1e9
    def dmg(li, t):
        tt, c = cums[li]; k = np.searchsorted(tt, min(t, stop), side="right"); return int(c[k - 1]) if k else 0
    order = sorted(range(len(lanes)), key=lambda i: -dmg(i, stop)); rank = {li: r for r, li in enumerate(order)}
    # ---- 絵
    bg = Image.new("RGB", (W * S, H * S), (8, 9, 14)); dg = ImageDraw.Draw(bg)
    for li in range(1, len(lanes)): dg.line([li * LW, 300 * S, li * LW, y_fin + 40 * S], fill=(34, 36, 46), width=2 * S)
    dg.line([0, y_fin, W * S, y_fin], fill=(70, 72, 86), width=3 * S)
    fT, fS, f2 = font(56 * S), font(30 * S), font(24 * S)
    fl = sp.get("finish_label", "ゴール"); w = dg.textlength(fl, font=fS)
    for li in range(len(lanes)): dg.text(((li + .5) * LW - w / 2, y_fin + 12 * S), fl, font=fS, fill=(110, 114, 130))
    out_raw = f"build_ballsim/{sid}_v.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out_raw], stdin=subprocess.PIPE)
    cols = [hexc(l["color"]) for l in lanes]
    for fi in range(int(total * FPS)):
        t = fi / FPS; tc = min(t, stop); im = bg.copy(); d = ImageDraw.Draw(im)
        n_now = int(min(NR, max(1, (tc - intro) // RS + 1))) if tc >= intro else 1
        w = d.textlength(sp["title"], font=fT); d.text((W * S / 2 - w / 2, 120 * S), sp["title"], font=fT, fill=(255, 255, 255), stroke_width=5 * S, stroke_fill=(0, 0, 0))
        sub = sp.get("sub", ""); w = d.textlength(sub, font=fS); d.text((W * S / 2 - w / 2, 196 * S), sub, font=fS, fill=(170, 175, 190))
        nl = f"n = {n_now}"; fn = font(40 * S); w = d.textlength(nl, font=fn); d.text((W * S / 2 - w / 2, (240 if sub else 206) * S), nl, font=fn, fill=(255, 210, 70), stroke_width=4 * S, stroke_fill=(0, 0, 0))
        gl = Image.new("RGB", (W * S // 6, H * S // 6)); gq = ImageDraw.Draw(gl)
        for li, ln in enumerate(lanes):
            cx = (li + .5) * LW; c = cols[li]; cnt, pw = rule(ln["rule"], n_now)
            fz = int(min(70, LW / S / max(1, len(ln["formula"].replace("^", ""))) * 1.3) * S)
            sup_text(d, cx, 330 * S, ln["formula"], fz, c)
            for k_, (lab, val) in enumerate([(sp.get("lab_balls", "個数"), f"{cnt:,}"), (sp.get("lab_power", "1個の力"), f"{pw:,}")]):
                xx = cx - LW * .22 + k_ * LW * .44; w = d.textlength(lab, font=f2); d.text((xx - w / 2, 440 * S), lab, font=f2, fill=(140, 145, 160))
                fv = font(int(min(36, LW / S / max(4, len(val)) * 1.1) * S)); w = d.textlength(val, font=fv); d.text((xx - w / 2, 474 * S), val, font=fv, fill=c)
            dm = dmg(li, t); x0, x1 = li * LW + 14 * S, (li + 1) * LW - 14 * S
            CUM, PL = CUMs[li], PLs[li]; nb = int(np.searchsorted(CUM, dm, side="right"))   # 割れた枚数
            tb = f"{min(nb, NP)} / {NP}"; w = d.textlength(tb, font=f2); d.text((cx - w / 2, 540 * S), tb, font=f2, fill=(200, 204, 215))
            for k in range(NP):
                y = py(k)
                if k < nb:   # 割れた板：割れてから0.7秒だけ破片が落ちる
                    tk = brk[li][k]; e = t - tk if tk is not None else 99
                    if e < .7:
                        r2 = np.random.default_rng(li * 100 + k)
                        for j in range(8):
                            xx = x0 + (x1 - x0) * (j + .5) / 8 + r2.uniform(-30, 30) * S * e; yy = y + 30 * S * e + 1400 * S * e * e * r2.uniform(.6, 1)
                            a = 1 - e / .7; d.rectangle([xx - 10 * S, yy, xx + 10 * S, yy + PH * .6], fill=tuple(int(v * a) for v in c))
                    continue
                cur = k == nb; left = 1.0
                if cur: left = 1 - (dm - (CUM[k - 1] if k else 0)) / PL[k]
                shade = .22 + .5 * (k / NP)
                fillc = tuple(int(v * (shade if not cur else (.3 + .7 * left))) for v in c)
                d.rectangle([x0, y, x1, y + PH], fill=fillc, outline=c if cur else tuple(int(v * .5) for v in c), width=2 * S)
                lab = f"{int(PL[k] * left):,}" if cur else f"{PL[k]:,}"
                fp = font(int(min(22, LW / S / 7) * S)); w = d.textlength(lab, font=fp); d.text((cx - w / 2, y + (PH - 22 * S) / 2 - 3 * S), lab, font=fp, fill=(255, 255, 255) if cur else (30, 30, 36))
            if tf is not None and t > tf and sp.get("ranks", not tie):
                rk = rank[li]; lab = sp.get("rank_labels", ["1位", "2位", "3位", "4位", "5位", "6位"])[rk]
                fw = font(int(min(80 if rk == 0 else 48, LW / S / 2.2) * S)); w = d.textlength(lab, font=fw)
                d.text((cx - w / 2, (740 if rk == 0 else 770) * S), lab, font=fw, fill=(255, 255, 255) if rk == 0 else (190, 194, 205), stroke_width=(7 if rk == 0 else 4) * S, stroke_fill=c if rk == 0 else (0, 0, 0))
        # 落ちているボール：当たる板の上端まで
        m = (B[:, 2] <= t) & (B[:, 3] > t) & (B[:, 3] <= stop)
        for (li_, n_, t0, t1, x, pw), pk in zip(B[m], plate_of[m]):
            yl = py(min(pk, NP - 1)); y = y_top + (yl - y_top) * ((t - t0) / fall) ** 2; rr = (2.2 + 1.0 * math.sqrt(pw)) * S; c = cols[int(li_)]
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=c); gq.ellipse([x / 6 - rr / 3, y / 6 - rr / 3, x / 6 + rr / 3, y / 6 + rr / 3], fill=c)
        mh = (B[:, 3] <= min(t, stop)) & (B[:, 3] > t - .12)
        for (li_, n_, t0, t1, x, pw), pk in list(zip(B[mh], plate_of[mh]))[-400:]:
            k = (t - t1) / .12; rr = (4 + 6 * k) * S * (1 + .15 * math.sqrt(pw)); c = cols[int(li_)]; yl = py(min(pk, NP - 1))
            gq.ellipse([x / 6 - rr / 3, yl / 6 - rr / 3, x / 6 + rr / 3, yl / 6 + rr / 3], fill=c)
        gl = gl.filter(ImageFilter.GaussianBlur(4)).resize((W * S, H * S), Image.BILINEAR)
        im = Image.fromarray(np.clip(np.asarray(im, np.int16) + (np.asarray(gl, np.int16) * .8).astype(np.int16), 0, 255).astype(np.uint8))
        p.stdin.write(im.resize((W, H), Image.LANCZOS).tobytes())
    p.stdin.close(); p.wait()
    # ---- 音
    n = int(SR * (total + 2)); L = np.zeros(n); R = np.zeros(n)
    PENT = sp.get("plate_midi", [60, 62, 64, 67, 69, 72, 74, 76, 79, 81, 84])   # 板ごとの音（上から）。ド レ ミ ソ ラ の並び
    def bell(f, dur, dec):
        tt = np.arange(int(SR * dur)) / SR; return (np.sin(2 * np.pi * f * tt) + .4 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 6)) * np.exp(-tt * dec)
    for li in range(len(lanes)):
        pan = .15 + .7 * li / max(1, len(lanes) - 1)
        for rn in range(1, NR + 1):
            mr = (B[:, 0] == li) & (B[:, 1] == rn) & (B[:, 3] <= stop)
            if not mr.any(): continue
            cnt = int(mr.sum()); dec = 5 + 4 * math.sqrt(cnt / 10)
            tt = np.arange(int(SR * min(1.2, 6 / dec))) / SR
            for k in np.unique(plate_of[mr]):
                m = mr & (plate_of == k); f = mtof(PENT[min(int(k), len(PENT) - 1)] + 12)
                tone = (np.sin(2 * np.pi * f * tt) + .28 * np.sin(2 * np.pi * f * 4 * tt) * np.exp(-tt * 20)) * np.exp(-tt * dec) * np.minimum(1, tt / .003)
                imp = np.zeros(n); idx = (B[m, 3] * SR).astype(int); ok = idx < n
                np.add.at(imp, idx[ok], 1 / math.sqrt(cnt) * (1 + .15 * np.sqrt(B[m, 5][ok])))
                y = fftconvolve(imp, tone)[:n]; L += y * (1 - pan); R += y * pan
        for k in range(NP):  # 板が割れた：2音の上昇
            tk = brk[li][k]
            if tk is None or tk > stop: continue
            s = bell(mtof(PENT[min(k + 1, len(PENT) - 1)] + 12), .9, 4) * .4; o = int(tk * SR); kk = min(len(s), n - o)   # 次の板の高さの鈴を1つ
            if kk > 0: L[o:o + kk] += s[:kk] * (1 - pan); R[o:o + kk] += s[:kk] * pan
    if tf is not None:
        for i, mm in enumerate([72, 76, 79, 84, 88, 91]):
            s = bell(mtof(mm), 1.4, 2.5) * .5; o = int((tf + i * .07) * SR); kk = min(len(s), n - o); L[o:o + kk] += s[:kk]; R[o:o + kk] += s[:kk]
    for dly, g in [(.031, .3), (.067, .24), (.113, .18), (.171, .13), (.257, .09)]:
        o = int(SR * dly); L[o:] += R[:-o] * g; R[o:] += L[:-o] * g
    st = np.stack([L, R], 1); st = st / (np.abs(st).max() + 1e-9) * .85; wv = f"build_ballsim/{sid}.wav"
    with wave.open(wv, "wb") as w_:
        w_.setnchannels(2); w_.setsampwidth(2); w_.setframerate(SR); w_.writeframes((st * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out_raw, "-i", wv, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", "loudnorm=I=-19:TP=-3:LRA=11", "-shortest", "-movflags", "+faststart", f"output/{sid}.mp4"], check=True)
    print(f"書き出し: output/{sid}.mp4  {total:.1f}秒  勝ち {lanes[winner]['name'] if winner is not None else 'なし'}  ゴール {tf and round(tf, 2)}")
    for li in range(len(lanes)): print(" ", lanes[li]["name"], dmg(li, total), "割れた枚数", int(np.searchsorted(CUMs[li], dmg(li, total), side="right")), "板", PLs[li])


if __name__ == "__main__":
    main(sys.argv[1])
