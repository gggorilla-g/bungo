# ellipsesim.py — 「楕円の片方の焦点から打つと、全部もう片方の焦点に集まる？」型
#   python tools/ellipsesim.py <spec.json>  → output/<id>.mp4
#   spec: id / title(2行) / count_label / a / b / v / n0（最初の数）/ doubles（何回倍にするか）/ seed / end_label
#   物理: 重力なし。焦点F1から全方向へ同じ速さで打つ。楕円の壁で反射すると、どの道も長さ2aでF2を通る（楕円の性質）
#   F1に戻るたびにボールを2倍にする。音: 壁は和音の音、F2・F1に集まる瞬間は和音全体
import json, os, sys, math, subprocess
import numpy as np
import harmony
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):   # spec の "palette" を色の決まりとして先に渡す
    os.environ.setdefault("SIM_PALETTE", json.load(open(sys.argv[1])).get("palette", ""))
from ballsim import WALL, WALL_GLOW, W, H, FPS, hsv, font, audio

SUB = 6


PENTA = [m for o in (60, 72) for m in (o, o + 2, o + 4, o + 5, o + 7, o + 9, o + 11)] + [84, 86]  # ドレミファソラシド（2オクターブ＋2音、16音。名前は互換のため PENTA のまま）
GLASS = False


def audio_perball(events, total, out_wav):
    """1音ずつ足す。ボールが多いほど1音を短く小さくする（濁り・音割れを防ぐ）"""
    import wave as _w
    from ballsim import SR, mtof
    n = int(SR * (total + 2)); L = np.zeros(n); R = np.zeros(n); cache = {}
    def mar(m, dec):
        key = (m, round(dec, 2))
        if key not in cache:
            f = mtof(m); t = np.arange(int(SR * min(2.2, 8 / dec))) / SR
            if GLASS:   # ガラスに当たった「カラン」：倍音が整数倍からずれた鈴のような部分音＋短いはじき
                s = sum(g * np.sin(2 * np.pi * f * r * t + r) * np.exp(-t * dec * k) for r, g, k in ((1, 1, .55), (2.0, .32, 1.0), (3.01, .14, 1.8), (4.25, .07, 3.0)))
                cl = np.random.default_rng(m).normal(0, 1, len(t)) * np.exp(-t * 1400) * .08
                cache[key] = (s + cl) * np.minimum(1, t / .0015)
            else:
                s = np.sin(2 * np.pi * f * t) + .28 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 20) + .1 * np.sin(2 * np.pi * f * 10 * t) * np.exp(-t * 45)
                cache[key] = s * np.exp(-t * dec) * np.minimum(1, t / .003)
        return cache[key]
    for t, kind, a, cnt in events:
        i = int(t * SR)
        if kind == "pb":
            dec = 4 + 3 * math.sqrt(cnt / 5)            # 5個: 減衰ゆっくり、640個: とても短い
            pan = .5 + .35 * ((a - 78) / 18)
            if harmony.ON:   # カノン進行の和音に寄せて、残り2音を小さく重ねる
                a = harmony.snap(int(a), t); snd = mar(a, dec).copy()
                for o in harmony.others(a, t): x = mar(o, dec) * .3; k = min(len(x), len(snd)); snd[:k] += x[:k]
                snd = snd * .9 / math.sqrt(cnt)
            else: snd = mar(a, dec) * .9 / math.sqrt(cnt)
        elif kind == "arrive":
            if GLASS: continue   # 集まる瞬間の和音は鳴らさない（同じ間隔で鳴ると単調になる）
            snd = sum(mar(m, 3.0) for m in ([72, 79, 84] if a == 0 else [60, 67, 72])) * .35; pan = .5
        else:
            continue
        m = min(len(snd), n - i)
        if m <= 0: continue
        L[i:i + m] += snd[:m] * (1 - pan) * 1.2; R[i:i + m] += snd[:m] * pan * 1.2
    for dly, g in [(.031, .3), (.067, .24), (.113, .18), (.171, .13), (.257, .09)]:
        o = int(SR * dly); L[o:] += R[:-o] * g; R[o:] += L[:-o] * g
    st = np.stack([L, R], 1); st = st / (np.abs(st).max() + 1e-9) * .85
    with _w.open(out_wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())


def main(spec_path):
    sp = json.load(open(spec_path, encoding="utf-8"))
    sid = sp["id"]; os.makedirs("build_ballsim", exist_ok=True)
    global GLASS; V2 = sp.get("style", 1) >= 2; GLASS = V2
    a, b, v = sp.get("a", 1.0), sp.get("b", .8), sp.get("v", 1.5)
    c = math.sqrt(a * a - b * b); F1, F2 = np.array([0, c]), np.array([0, -c])  # 縦長：焦点は上下
    rng = np.random.default_rng(sp.get("seed", 1))
    n0, doubles = sp.get("n0", 5), sp.get("doubles", 8)
    ST = sp.get("stagger", 0.0)           # ボールごとに速さを少しずつ変えて、着く時刻をずらす（オーナー 11/22「全部同じタイミングはつまらない」）
    T_half = 2 * a / (v * (1 - ST))        # F1→壁→F2 の時間（いちばん遅いボールに合わせる）
    hold = sp.get("hold", .08)             # 集まった瞬間に止める秒数
    # 時間割：各周 = F1→F2（T_half）＋止め＋F2→F1（T_half）＋止め
    cycle = 2 * (T_half + hold); SM = 2 * a / (1 - ST)   # いちばん遅いボールが着くときの s
    intro = .6
    total = intro + cycle * (doubles + 1) + 2.5
    dt = 1 / (FPS * SUB)
    events = []
    S = 2; px = min(W * S * .40 / b, H * S * .30 / a); cx, cy = W * S / 2, H * S * .55   # 細長い楕円でもはみ出さない
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
        rounds.append(dict(n=n, hit=hit1, l1=l1, hue=np.array([(i / n + k * .13) % 1 for i in range(n)]), spd=1 - ST * (.5 - .5 * np.cos(2 * np.pi * np.arange(n) / n - 2.1 * k))))   # ばらつきはランダムでなく波：ある向きのボールから先に着き、両隣へ順に伝わる（オーナー 11/22）
        n = int(round(n * sp.get("growth", 2)))
    # 音の出来事
    melodic = sp.get("melodic", True)
    for k, rd in enumerate(rounds):
        t0 = intro + k * cycle
        for leg in range(2):
            ts = t0 + leg * (T_half + hold)
            ls = rd["l1"] if leg == 0 else 2 * a - rd["l1"]  # 戻りは F2→壁 の長さ = 2a - l1（同じ壁の点で反射）
            if sp.get("perball", True):  # ボール1個ごとに、壁に当たった瞬間に1音。先に当たった順に低→高（帰りは高→低）
                order = np.argsort(np.argsort(ls)); frac = order / max(1, rd["n"] - 1)
                if GLASS:   # 壁のどこに当たったかで音の高さを決める → 数がふえるたびに並びが変わり、重なったりずれたりする
                    ang = (np.arctan2(rd["hit"][:, 1], rd["hit"][:, 0]) / (2 * np.pi)) % 1; frac = ang
                for i in range(rd["n"]):
                    events.append((ts + ls[i] / (v * rd["spd"][i]), "pb", PENTA[int(frac[i] * (len(PENTA) - 1) + .5)] + (12 if GLASS else 0), rd["n"]))
                events.append((ts + T_half, "arrive", leg, rd["n"]))
            elif melodic:  # 1区間に目立つ反射3回まで、時刻順に ド・ミ・ソ（120ms以上あける）、到着の直前120msは空ける
                tl = np.sort(ls / v); picks, last = [], -1
                for q in np.quantile(tl, [.15, .5, .85]):
                    if q - last >= .12 and q < T_half - .12: picks.append(q); last = q
                for m, q in zip([60, 64, 67], picks): events.append((ts + q, "note", m + 12, .8))
                events.append((ts + T_half, "note", 72 + 12, 1.15))
            else:
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
    gd.ellipse(box, outline=WALL_GLOW, width=26 * S); glow = glow.filter(ImageFilter.GaussianBlur(28 * S))
    bg = Image.fromarray(np.clip(np.asarray(bg, np.int16) + np.asarray(glow, np.int16), 0, 255).astype(np.uint8)); dg = ImageDraw.Draw(bg)
    dg.ellipse(box, outline=WALL, width=9 * S)
    for F in (F1, F2):
        x, y = to(F); q = .06 * px; dg.ellipse([x - q, y - q, x + q, y + q], outline=(255, 200, 60), width=5 * S)
    fT, fC, fN = font(58 * S), font(54 * S), font(66 * S)
    out_raw = f"build_ballsim/{sid}_v.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out_raw], stdin=subprocess.PIPE)
    nf = int(total * FPS); r = sp.get("ball_r", .028)
    from PIL import ImageChops
    acc = Image.new("RGB", (W * S, H * S)); done = set()   # 終わった周の軌跡を重ねて残す（行きと帰りは同じ線なので周ごとに1回）
    keep = sp.get("keep_trails", True)
    for fi in range(nf):
        t = fi / FPS
        if keep:
            for kk in range(doubles + 1):
                if kk not in done and t >= intro + kk * cycle + T_half:
                    done.add(kk); rk = rounds[kk]; tmp = Image.new("RGB", (W * S, H * S)); td = ImageDraw.Draw(tmp)
                    lwk = max(1, int(2 * S * min(1, 10 / math.sqrt(rk["n"])))); gk = sp.get("trail_gain", .30)
                    for i in range(rk["n"]):
                        c_ = tuple(int(x * gk) for x in hsv(rk["hue"][i])); xh, yh = to(rk["hit"][i])
                        td.line([*to(F1), xh, yh], fill=c_, width=lwk); td.line([xh, yh, *to(F2)], fill=c_, width=lwk)
                    acc = ImageChops.add(acc, tmp)
        im = ImageChops.add(bg, acc) if keep else bg.copy(); d = ImageDraw.Draw(im)
        k = int(max(0, t - intro) // cycle); k = min(k, doubles); rd = rounds[k]; u = t - intro - k * cycle
        n = rd["n"]; hit = rd["hit"]; l1 = rd["l1"]; spd = rd["spd"]
        if t < intro: s, leg = 0, 0
        elif u < T_half: s, leg = u * v, 0
        elif u < T_half + hold: s, leg = SM, 0
        elif u < 2 * T_half + hold: s, leg = (u - T_half - hold) * v, 1
        else: s, leg = SM, 1
        if t > intro + (doubles + 1) * cycle - hold: k, rd, s, leg = doubles, rounds[doubles], SM, 1; n, hit, l1, spd = rd["n"], rd["hit"], rd["l1"], rd["spd"]
        S_ = np.minimum(2 * a, s * spd)   # ボールごとの進んだ道のり（遅いボールも最後まで同じ速さで。途中で一斉に着地させない）
        A0, A1 = (F1, F2) if leg == 0 else (F2, F1)
        la = l1 if leg == 0 else 2 * a - l1
        cols = [hsv(h) for h in rd["hue"]]
        lw = max(1, int(3 * S * min(1, 12 / math.sqrt(n))))
        pos = np.zeros((n, 2))
        for i in range(n):
            x0, y0 = to(A0); xh, yh = to(hit[i]); col = cols[i]
            si = S_[i]
            if si <= la[i]:
                f = si / la[i]; pt = A0 + (hit[i] - A0) * f; xp, yp = to(pt); d.line([x0, y0, xp, yp], fill=tuple(int(c_ * .7) for c_ in col), width=lw)
            else:
                f = min(1, (si - la[i]) / (2 * a - la[i])); pt = hit[i] + (A1 - hit[i]) * f; xp, yp = to(pt)
                d.line([x0, y0, xh, yh], fill=tuple(int(c_ * .55) for c_ in col), width=lw); d.line([xh, yh, xp, yp], fill=tuple(int(c_ * .7) for c_ in col), width=lw)
            pos[i] = (xp, yp)
        if V2:   # 壁に当たった点が一瞬光る（当たった直後0.35秒で消える）
            gl_ = Image.new("RGB", (W * S // 4, H * S // 4)); gq = ImageDraw.Draw(gl_)
            for i in range(n):
                dt_ = (S_[i] - la[i]) / (v * spd[i])
                if 0 <= dt_ < .35:
                    xh, yh = to(hit[i]); al = 1 - dt_ / .35; rr = (10 + 26 * al) * S / 4; c_ = tuple(int(x * al) for x in cols[i])
                    gq.ellipse([xh / 4 - rr, yh / 4 - rr, xh / 4 + rr, yh / 4 + rr], fill=c_)
                    d.ellipse([xh - 5 * S, yh - 5 * S, xh + 5 * S, yh + 5 * S], fill=tuple(min(255, int(x * al + 255 * al * .5)) for x in cols[i]))
            im = ImageChops.add(im, gl_.filter(ImageFilter.GaussianBlur(4)).resize((W * S, H * S), Image.BILINEAR)); d = ImageDraw.Draw(im)
            # 枠も「ポーン」と軽く光る：直近に当たった数に応じて枠を明るく
            hits_ = sum(max(0, 1 - ((S_[i] - la[i]) / (v * spd[i])) / .3) for i in range(n) if S_[i] >= la[i])
            pw = min(1, hits_ / max(2, n ** .5) * 1.2)
            if pw > .02:
                fr = Image.new("RGB", (W * S // 4, H * S // 4)); ImageDraw.Draw(fr).ellipse([x_ / 4 for x_ in box], outline=tuple(int(c_ * pw) for c_ in (120, 230, 255)), width=max(2, 5 * S // 4))
                im = ImageChops.add(im, fr.filter(ImageFilter.GaussianBlur(3)).resize((W * S, H * S), Image.BILINEAR)); d = ImageDraw.Draw(im)
                d.ellipse(box, outline=tuple(min(255, int(150 + 105 * pw)) for _ in range(3)), width=int((9 + 4 * pw) * S))
        q = r * px * (1 if n <= 80 else .7)
        for i in range(n):
            xp, yp = pos[i]; col = cols[i]
            if V2:   # 質感：暗めの縁→本体→左上の光
                d.ellipse([xp - q, yp - q, xp + q, yp + q], fill=tuple(int(c_ * .45) for c_ in col))
                d.ellipse([xp - q * .82, yp - q * .9, xp + q * .7, yp + q * .62], fill=col)
                h_ = q * .32; d.ellipse([xp - q * .5 - h_, yp - q * .5 - h_, xp - q * .5 + h_, yp - q * .5 + h_], fill=(255, 255, 255))
            else: d.ellipse([xp - q, yp - q, xp + q, yp + q], fill=col)
        # 集まった瞬間に光る
        ta = None  # いちばん最近の到着から0.22秒だけ光らせる
        if s >= 2 * a - 1e-6: ta, AF = 0.0, A1
        elif t >= intro and (u - (T_half if leg == 1 else -hold)) < .22 + hold and not (leg == 0 and k == 0):
            ta, AF = (u - T_half - hold) if leg == 1 else (u + hold), A0
        if ta is not None and ta < .22 and not V2:
            x, y = to(AF); qq = .12 * px * (1 + ta * 1.5); al = 1 - ta / .22; d.ellipse([x - qq, y - qq, x + qq, y + qq], outline=tuple(int(c_ * al + 10) for c_ in (255, 245, 200)), width=6 * S)
        for kk, line in enumerate(sp["title"]):
            w = d.textlength(line, font=fT); d.text((W * S / 2 - w / 2, 150 * S + kk * 80 * S), line, font=fT, fill=(255, 255, 255) if kk == 0 else (255, 196, 60), stroke_width=6 * S, stroke_fill=(0, 0, 0))
        lab, num = sp.get("count_label", "balls: "), f"{n:,}"
        w1, w2 = d.textlength(lab, font=fC), d.textlength(num, font=fN); x0 = W * S / 2 - (w1 + w2) / 2; yb = cy + a * px + 60 * S
        d.text((x0, yb + 8 * S), lab, font=fC, fill=(235, 235, 240), stroke_width=5 * S, stroke_fill=(0, 0, 0)); d.text((x0 + w1, yb), num, font=fN, fill=(255, 210, 70), stroke_width=6 * S, stroke_fill=(0, 0, 0))
        if t > intro + (doubles + 1) * cycle - hold and sp.get("end_label"):
            fB = font(76 * S); msg = sp["end_label"]; wb = d.textlength(msg, font=fB); d.text((W * S / 2 - wb / 2, cy - 40 * S), msg, font=fB, fill=(255, 255, 255), stroke_width=9 * S, stroke_fill=(30, 90, 200))
        if V2:   # 軽いネオン：小さくして滲ませ、足し戻す
            sm = im.resize((W * S // 6, H * S // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)).resize((W * S, H * S), Image.BILINEAR)
            im = ImageChops.add(im, Image.eval(sm, lambda x: int(x * .55)))
        p.stdin.write(im.resize((W, H), Image.LANCZOS).tobytes())
    p.stdin.close(); p.wait()
    wv = f"build_ballsim/{sid}.wav"
    if sp.get("perball", True): audio_perball(events, total, wv)
    else: audio(events, total, wv)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out_raw, "-i", wv, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", "loudnorm=I=-19:TP=-3:LRA=11", "-shortest", "-movflags", "+faststart", f"output/{sid}.mp4"], check=True)
    print(f"書き出し: output/{sid}.mp4  {total:.1f}秒  最後のボール {rounds[-1]['n']}")


if __name__ == "__main__":
    main(sys.argv[1])
