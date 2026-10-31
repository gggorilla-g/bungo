# nazo/moso3d.py — 妄想科学ショートの新しい型（3DCG版）。縦 1080x1920。
#   冒頭で結論 → カウントダウン（計器の数字＋地上から月へ飛ぶCG）→ 本編を短いカットで畳みかける → 冒頭と同じ絵で終わってループ。
#   絵は nazo/cg/（three.js を Chromium で1コマずつ描く）。文字・ずんだもん・音はこのファイルで重ねる。
#   台本: nazo/shorts/<ID>.json（例 moso_moon_test.json）
#   使い方:
#     python nazo/moso3d.py check <ID>   … 読みの関門（src/yomi_gate.py）。合格すると nazo/state/moso3d_yomi_<ID>.json に記録
#     python nazo/moso3d.py build <ID>   … 動画を作る。関門の記録と台本の読みが一致しないと止める
#   環境変数: CG_SCALE（CGを描く大きさの倍率。1.0=1080x1920、0.5=540x960 を拡大）、ALLOW_CHIP_BGM（BGMが無い手元の試し用）
#   行のキー:
#     say / yomi（読み上げ文。省略時は自動）/ text（テロップ2行。2行目が黄色）/ face（左下のずんだもんの表情）/ setsu（右上に「説」）
#     parts（1文を区切って決まった時刻に読む：カウントダウン用）/ dur（その文の長さを固定）/ loop（最後の文。後ろの間を付けない）
#     cg: {scene, p}  … nazo/cg/scene.js の場面。p.sun="quarter" は文の長さで朝が4回来る速さ、p.t0="-d" は文の長さだけ時刻を戻す
#     fx: big（大きな文字）/ timer（計器の秒読み）/ clock（逆回りの時計と年の数字）/ count（数字が増える）/ tally（朝の回数）/ flip（2語の入れかわり）
import json, math, os, re, subprocess, sys, time, hashlib, shutil
sys.path[:0] = ["src", "nazo"]
from PIL import Image, ImageDraw
import render, yomi, se, motion

W, H, FPS = 1080, 1920, 30
YEL, BLK, WHT, RED = (255, 226, 0), (0, 0, 0), (255, 255, 255), (220, 40, 40)
CYAN = (60, 230, 255)
TEL_Y = 1290
SPEED, GAP = 1.1, 0.06
SE_GAIN = 0.7          # 効果音の音量（既存の妄想科学ショートの0.7倍＝約-3dB。声とBGMはそのまま）
B = "build_cg"
ZDIR = "assets/enc/parts"
ZH = 400


def ease(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def back(x):
    return motion.back(min(max(x, 0), 1))


def reading(sp, ln):
    """読み上げ文（読点は抜いて畳みかける。区切りの間は文の分け方で作る）"""
    yt = ln.get("yomi") or yomi.base_fix(ln["say"], {"title": "", "author": ""}, {})
    return re.sub(r"[、,]", "", yt)


def all_says(sp):
    out = []
    for ln in sp["lines"]:
        for pt in ln.get("parts") or [ln]:
            out.append((pt["say"], reading(sp, pt)))
    return out


def gate_key(pairs):
    return hashlib.sha1(json.dumps(pairs, ensure_ascii=False).encode()).hexdigest()


def check(sid):
    """読みの関門。漢字の語を1語ずつ読みと並べて出し、問題があれば止める"""
    import pyopenjtalk, yomi_gate
    sp = json.load(open(f"nazo/shorts/{sid}.json", encoding="utf-8"))
    pairs = all_says(sp)
    words = sp.get("yomi_words", {})
    rep = []
    for say, yt in pairs:
        vk = yomi.kana(yt)
        rep.append(f"{say}\n  読み上げ: {yt}\n  VOICEVOX: {vk}")
        for f in pyopenjtalk.run_frontend(say):           # 原文の漢字の語と、辞書の読み
            if re.search(r"[一-龥々]", f["string"]):
                rep.append(f"    {f['string']} → {f['pron']}" + (f"（台本で指定: {words[f['string']]}）" if f["string"] in words else ""))
        if yt != say:                                     # 読み上げ文に漢字が残っていれば、その語も
            for f in pyopenjtalk.run_frontend(yt):
                if re.search(r"[一-龥々]", f["string"]):
                    rep.append(f"    [読み上げ文] {f['string']} → {f['pron']}")
    issues = yomi_gate.check(pairs, words, yomi.kana)
    for say, yt in pairs:                                 # 助詞「は、」がハと読まれていないか（読点を詰めると「はやく」等に化ける。2つのエンジンが同じ間違いをするので別に見る）
        if say.count("は、") > yomi.kana(yt).count("ワ"):
            issues.append(f"助詞の「は」がワと読まれていない: {yomi.kana(yt)}｜{say}")
    kit = f"nazo/manual/{sp['main']}"; os.makedirs(kit, exist_ok=True)
    open(f"{kit}/{sid}_yomi.txt", "w", encoding="utf-8").write("\n".join(rep) + "\n\n関門: " + ("合格" if not issues else "\n".join(issues)) + "\n")
    print("\n".join(rep))
    if issues:
        print("\n関門で止めた:\n" + "\n".join(issues)); sys.exit(1)
    os.makedirs("nazo/state", exist_ok=True)
    json.dump({"key": gate_key(pairs), "pairs": pairs}, open(f"nazo/state/moso3d_yomi_{sid}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n関門: 合格（記録した）")


# ---------------- 画面の部品 ----------------
_zp = {}


def zunda_img(face, mouth, blink):
    for f in (face, "通常"):
        for b in ((blink, 0) if blink else (0,)):
            k = f"{f}_{mouth}_{b}"
            if k not in _zp and os.path.exists(f"{ZDIR}/{k}.png"):
                im = Image.open(f"{ZDIR}/{k}.png").convert("RGBA")
                _zp[k] = im.resize((int(im.width * ZH / im.height), ZH), Image.LANCZOS)
            if k in _zp:
                return _zp[k]
    return None


def voiced_len(wav):
    import wave as _w, numpy as _np
    with _w.open(wav) as w:
        sr = w.getframerate(); a = _np.abs(_np.frombuffer(w.readframes(w.getnframes()), _np.int16))
    idx = _np.nonzero(a > max(300, a.max() * 0.03))[0]
    return (idx[-1] / sr + 0.02) if len(idx) else len(a) / sr


def mouth_levels(wav, n):
    import wave as _w, numpy as _np
    with _w.open(wav) as w:
        sr = w.getframerate(); a = _np.frombuffer(w.readframes(w.getnframes()), _np.int16).astype(_np.float32)
    hop = sr / FPS
    rms = _np.array([_np.sqrt(_np.mean(a[int(i * hop):int((i + 1) * hop)] ** 2)) if int(i * hop) < len(a) else 0 for i in range(n)])
    pk = max(rms.max(), 1)
    return [0 if r < pk * 0.12 else (1 if r < pk * 0.45 else 2) for r in rms]


def stroke_text(d, x, y, text, size, fg, stroke=12, sfill=BLK, anchor="mm"):
    d.text((x, y), text, font=motion.font(size), fill=fg, stroke_width=stroke, stroke_fill=sfill, anchor=anchor)


def mono(d, cx, cy, text, size, fg, stroke=10):
    """数字を等幅に並べる（桁が変わっても揺れない）"""
    f = motion.font(size)
    cw = int(size * 0.62)
    x = cx - cw * len(text) / 2
    for ch in text:
        w = cw * (0.45 if ch == "." else 1)
        d.text((x + w / 2, cy), ch, font=f, fill=fg, stroke_width=stroke, stroke_fill=BLK, anchor="mm")
        x += w


def fx_big(fr, fx, t):
    u = t - fx.get("at", 0.2)
    if u < 0:
        return
    s = 1.7 - 0.7 * back(u / 0.22)
    size = int(fx.get("size", 230) * s)
    lay = Image.new("RGBA", (W, 600), (0, 0, 0, 0))
    stroke_text(ImageDraw.Draw(lay), W // 2, 300, fx["text"], size, tuple(fx.get("color", YEL)), 18)
    ang = -6 + (10 * math.sin(u * 70) * math.exp(-u * 8)) + 1.5 * math.sin(u * 4)
    lay = lay.rotate(ang, center=(W // 2, 300), resample=Image.BICUBIC)
    fr.paste(lay, (0, int(H * fx.get("y", 0.33)) - 300), lay)


def fx_timer(fr, fx, t, burst_t):
    """計器盤風の秒読み：3.00 → 0.00（1/100秒きざみ）。目盛りの弧と針、0.00で赤く点滅"""
    d = ImageDraw.Draw(fr, "RGBA")
    v = max(0.0, fx["from"] - max(0.0, t - fx["at"]))
    boot = t < fx["at"]                                      # 「3」の声より前（3.00 で止めておく）
    # 読み上げ「月を消すまで」の間は 3.00 のまま構え、「3」の声から単調に減る
    cx, cy = W // 2, 470                                     # 月が画面の中央に見えるよう、盤は上に寄せる
    pop = back(t / 0.25)
    R = int(270 * pop)
    if R < 5:
        return
    d.rounded_rectangle([cx - 420, cy - 240, cx + 420, cy + 300], 40, fill=(0, 10, 20, 150), outline=CYAN + (255,), width=6)
    for k in range(0, 61):                                   # 目盛り（弧）
        a = math.radians(200 - k * (220 / 60))
        r0 = R - (36 if k % 10 == 0 else 20)
        on = k <= int(60 * v / fx["from"])
        col = (RED if v < 1.0 else CYAN) + (255,) if on else (60, 80, 90, 255)
        d.line([(cx + r0 * math.cos(a), cy - r0 * math.sin(a) + 110), (cx + R * math.cos(a), cy - R * math.sin(a) + 110)],
               fill=col, width=8 if k % 10 == 0 else 5)
    a = math.radians(200 - 220 * (1 - v / fx["from"]))       # 針
    d.line([(cx, cy + 110), (cx + (R - 55) * math.cos(a), cy + 110 - (R - 55) * math.sin(a))], fill=WHT + (255,), width=10)
    d.ellipse([cx - 18, cy + 92, cx + 18, cy + 128], fill=WHT + (255,))
    motion.box_text(d, cx, cy - 225, fx.get("label", ""), motion.font(54), BLK, CYAN, 24, 10, anchor="ct")
    col = RED if 0 < v < 1.0 else WHT                        # 0.00 は白で止める（点滅させない）
    mono(d, cx, cy + 20, f"{v:.2f}", 210, col, 12)
    d.text((cx + 280, cy + 95), "SEC", font=motion.font(40), fill=CYAN, anchor="mm")
    sec = 0 if boot else (int(math.ceil(v)) if v > 0 else 0)   # 小さな数字の窓（声の 3・2・1 と同じ）
    for q in range(3):
        on = sec == 3 - q
        x = cx - 150 + q * 150
        d.rectangle([x - 50, cy + 185, x + 50, cy + 275], fill=(RED if on else (20, 30, 40)) + (255,), outline=CYAN + (255,), width=4)
        d.text((x, cy + 230), str(3 - q), font=motion.font(70), fill=WHT if on else (90, 110, 120), anchor="mm")


def fx_clock(fr, fx, t, dur):
    """逆回りの時計と、年の数字が増えていく（45億年前へ）"""
    d = ImageDraw.Draw(fr, "RGBA")
    cx, cy, r = W // 2, 560, int(230 * back(t / 0.25))
    if r < 5:
        return
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 235), outline=BLK + (255,), width=14)
    for k in range(12):
        a = math.radians(k * 30)
        d.line([(cx + (r - 34) * math.sin(a), cy - (r - 34) * math.cos(a)), (cx + (r - 8) * math.sin(a), cy - (r - 8) * math.cos(a))],
               fill=BLK + (255,), width=10 if k % 3 == 0 else 5)
    spin = -(t * 4 + 40 * (t / dur) ** 2)                     # 反時計回りにだんだん速く
    for L, wd, sp_ in ((r * 0.75, 12, 1.0), (r * 0.5, 18, 1 / 12)):
        a = spin * sp_ * 2 * math.pi
        d.line([(cx, cy), (cx + L * math.sin(a), cy - L * math.cos(a))], fill=(RED if wd == 12 else BLK) + (255,), width=wd)
    d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=BLK + (255,))
    # 左回りの矢印
    d.arc([cx - r - 40, cy - r - 40, cx + r + 40, cy + r + 40], 200, 330, fill=YEL + (255,), width=16)
    a = math.radians(200)
    ax, ay = cx + (r + 40) * math.cos(a), cy + (r + 40) * math.sin(a)
    d.polygon([(ax - 30, ay - 10), (ax + 24, ay - 34), (ax + 14, ay + 30)], fill=YEL + (255,))
    v = fx["to"] * ease(t / (dur * 0.75))
    stroke_text(d, cx, cy + r + 120, f"{v:.0f}億年前", 150, YEL, 14)


def fx_count(fr, fx, t, dur):
    u = t - fx.get("at", 0.1)
    if u < 0:
        return
    d = ImageDraw.Draw(fr)
    T = max(0.5, dur * 0.45)                                 # 文の半ばで目標の数に着き、そのあとは止める
    done = u >= T
    v = fx["to"] if done else fx["from"] + (fx["to"] - fx["from"]) * min(ease(u / T), 0.999)
    stroke_text(d, W // 2, 470, fx.get("label", ""), 110, WHT, 12)
    pop = 1.0 + (0.25 * math.exp(-(u - T) * 10) if done else 0)
    num = f"{int(v)}{fx.get('unit', '')}"
    stroke_text(d, W // 2, 660, (fx.get("prefix", "") + num) if done else num, int(220 * pop), YEL, 16)
    stroke_text(d, W // 2, 820, f"いまは{fx['from']}{fx.get('unit', '')}", 60, WHT, 8)


def fx_tally(fr, fx, t, times):
    """朝が来るたびに四角い太陽が1つずつ並ぶ"""
    d = ImageDraw.Draw(fr)
    n = sum(1 for x in times if x <= t)
    sz, gap = 150, 40
    x0 = W // 2 - (fx["n"] * sz + (fx["n"] - 1) * gap) // 2
    for q in range(fx["n"]):
        x = x0 + q * (sz + gap)
        if q < n:
            u = t - times[q]
            s = back(u / 0.2)
            e = int(sz * s / 2)
            c = x + sz // 2
            d.rectangle([c - e, 560 - e, c + e, 560 + e], fill=(255, 200, 40), outline=BLK, width=8)
            stroke_text(d, c, 560, str(q + 1), int(90 * s) or 1, BLK, 0)
        else:
            d.rectangle([x, 560 - sz // 2, x + sz, 560 + sz // 2], outline=WHT, width=6)
    stroke_text(d, W // 2, 780, f"{fx.get('label', '')} {n}回", 170, YEL, 16)
    if fx.get("hours"):                                      # 0〜24時のバー。6時間ごとに朝が来る
        x0b, x1b, yb = 140, W - 140, 400
        d.rectangle([x0b, yb - 14, x1b, yb + 14], fill=(30, 40, 60), outline=WHT, width=4)
        pos = min(1.0, t / (times[-1] + (times[1] - times[0]))) if len(times) > 1 else 0
        d.rectangle([x0b, yb - 14, x0b + int((x1b - x0b) * pos), yb + 14], fill=YEL)
        for k in range(fx["n"] + 1):
            xk = x0b + (x1b - x0b) * k / fx["n"]
            d.line([(xk, yb - 30), (xk, yb + 30)], fill=WHT, width=5)
            stroke_text(d, int(xk), yb - 62, f"{fx['hours'] * k // fx['n']}時", 44, WHT, 6)


def fx_calendar(fr, fx, t):
    """カレンダーがめくれていく（1月〜12月）。下に一言。文字が変わるだけで明るさは変えない"""
    d = ImageDraw.Draw(fr)
    k = int(t / fx.get("per", 0.13)) % 12
    x0, y0, w, h = W // 2 - 190, 330, 380, 360
    d.rectangle([x0, y0, x0 + w, y0 + h], fill=WHT, outline=BLK, width=10)
    d.rectangle([x0, y0, x0 + w, y0 + 90], fill=RED, outline=BLK, width=10)
    for q in range(2):
        d.ellipse([x0 + 90 + q * 170, y0 - 30, x0 + 130 + q * 170, y0 + 30], fill=BLK)
    stroke_text(d, W // 2, y0 + 225, f"{k + 1}月", 150, BLK, 0)
    if fx.get("sub"):
        stroke_text(d, W // 2, y0 + h + 90, fx["sub"], 90, YEL, 12)


def fx_flip(fr, fx, t):
    """2語がなめらかに入れかわる（CGの雪⇄猛暑と同じ周期。急に切り替えない）"""
    w = 0.5 - 0.5 * math.cos(2 * math.pi * t / fx["period"])          # 0=1語目 1=2語目
    for k, a in ((0, 1 - w), (1, w)):
        if a < 0.02:
            continue
        lay = Image.new("RGBA", (W, 400), (0, 0, 0, 0))
        stroke_text(ImageDraw.Draw(lay), W // 2, 200, fx["texts"][k], int(240 * (0.9 + 0.1 * a)), (130, 200, 255) if k == 0 else (255, 120, 40), 18)
        lay.putalpha(lay.getchannel("A").point(lambda x: int(x * a)))
        fr.paste(lay, (0, 620 - 200), lay)


# ---------------- 明るさの点検（点滅・急な明暗の切り替えを数える） ----------------
def flash_check(mp4, th=20.0):
    """各コマの平均輝度（0〜255）を出し、th 以上の明暗の変化（向きが変わるまでの上がり・下がり）を数える。
    「明暗の大きな変化は1秒に3回未満」（RULES.md）を、どの1秒の窓でも変化が3回未満かで判定する"""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                        "-f", "null", "-"], capture_output=True, text=True).stdout
    y = [float(l.split("=")[1]) for l in r.splitlines() if "YAVG=" in l]
    ev, dirn, piv, ext, ie = [], 0, y[0], y[0], 0       # 山と谷をたどり、th 以上の上がり・下がりを1回と数える
    for i, v in enumerate(y):
        if dirn == 0:
            if abs(v - piv) >= th:
                dirn, ext, ie = (1 if v > piv else -1), v, i
        elif (v - ext) * dirn > 0:
            ext, ie = v, i
        elif (ext - v) * dirn >= th:
            ev.append(ie / FPS); dirn, ext, ie = -dirn, v, i
    if dirn:
        ev.append(ie / FPS)
    mx = max([sum(1 for e in ev if a <= e < a + 1.0) for a in [x / FPS for x in range(len(y))]] or [0])
    return y, ev, mx


# ---------------- 組み立て ----------------
def cg_param(ln, d):
    p = dict(ln["cg"].get("p", {}))
    if p.get("sun") == "line":                               # 文の長さでちょうど1回、ゆっくり空を渡る
        p["sun"] = d
    if p.get("t0") == "-d":
        p["t0"] = -d
    return p


def sunrise_times(p, d):
    """land 場面の太陽が地平線を上へ越える時刻（ph = t/sun*2π + ph0 が 2πの倍数）"""
    sun, ph0 = p["sun"], p.get("ph0", 0.9)
    if p.get("arc"):                                         # 弧だけを渡る太陽：各周の頭が朝
        return [k * sun for k in range(int(d / sun) + 1) if k * sun < d]
    out, k = [], math.ceil(ph0 / (2 * math.pi))
    while True:
        tt = (2 * math.pi * k - ph0) / (2 * math.pi) * sun
        if tt > d:
            return out
        if tt >= 0:
            out.append(tt)
        k += 1


def build(sid):
    T0 = time.time()
    sp = json.load(open(f"nazo/shorts/{sid}.json", encoding="utf-8"))
    pairs = all_says(sp)
    rec = f"nazo/state/moso3d_yomi_{sid}.json"
    if not os.path.exists(rec) or json.load(open(rec, encoding="utf-8"))["key"] != gate_key(pairs):
        sys.exit(f"読みの関門を通っていない（python nazo/moso3d.py check {sid} を手元で通して記録をコミットする）")
    os.makedirs(B, exist_ok=True); os.makedirs("output", exist_ok=True)
    render.B = B; render.TIGHT = True
    v = dict(sp["voice"]); v["speed"] = v.get("speed", 1.0) * SPEED
    render.set_voice(**v)
    for say, yt in pairs:
        render._YOMI[say] = yt
    lines = sp["lines"]
    # ---- 声
    wavs, durs = [], []
    for li, ln in enumerate(lines):
        wav = f"{B}/l{li}.wav"
        if ln.get("parts"):                                    # 区切って決まった時刻に読む
            import wave as _w, numpy as _np
            segs = []
            for pi, pt in enumerate(ln["parts"]):
                pw = f"{B}/l{li}_{pi}.wav"; render.tts(pt["say"], pw)
                with _w.open(pw) as w:
                    sr = w.getframerate(); a = _np.frombuffer(w.readframes(w.getnframes()), _np.int16)
                a = a[:int(voiced_len(pw) * sr)]
                segs.append((pt["at"], a))
            d = ln.get("dur") or max(at + len(a) / sr for at, a in segs) + GAP
            buf = _np.zeros(int(d * sr) + 1, _np.int32)
            for at, a in segs:
                i = int(at * sr); buf[i:i + len(a)] += a[:len(buf) - i]
            with _w.open(wav, "wb") as o:
                o.setnchannels(1); o.setsampwidth(2); o.setframerate(sr)
                o.writeframes(_np.clip(buf, -32768, 32767).astype(_np.int16).tobytes())
        else:
            render.tts(ln["say"], wav)
            d = voiced_len(wav) + (0.0 if ln.get("loop") else GAP)
            d = max(d, ln.get("dur", 0))
        d = math.ceil(d * FPS) / FPS
        render._pad_wav(wav, f"{B}/l{li}_p.wav", d)
        wavs.append(f"{B}/l{li}_p.wav"); durs.append(d)
    print("文の長さ:", [round(x, 2) for x in durs], "合計", round(sum(durs), 2), "秒")
    # ---- CG（全部の文をまとめて1回で描く）
    sc = float(os.environ.get("CG_SCALE", "1.0"))
    cw, chh = int(W * sc) // 2 * 2, int(H * sc) // 2 * 2
    jobs, params = [], []
    for li, ln in enumerate(lines):
        p = cg_param(ln, durs[li]); params.append(p)
        out = f"{B}/cg{li}"
        shutil.rmtree(out, ignore_errors=True)
        jobs.append({"scene": ln["cg"]["scene"], "p": p, "d": durs[li], "fps": FPS, "w": cw, "h": chh, "out": out})
    json.dump(jobs, open(f"{B}/jobs.json", "w"), ensure_ascii=False)
    t1 = time.time()
    subprocess.run(["node", "nazo/cg/render_cg.js", f"{B}/jobs.json"], check=True)
    t_cg = time.time() - t1
    # ---- 効果音
    for li, ln in enumerate(lines):
        d = durs[li]
        ev = [("pop_big", 0.0, 0.8)]
        for fx in ln.get("fx", []):
            at = fx.get("at", 0.2)
            if fx["type"] == "big":
                ev += [("boom", at, 1.0), ("crash", at, 0.4)]
            elif fx["type"] == "timer":
                ev += [("tick", at + k, 1.4) for k in range(int(fx["from"]))] + [("boom", at + fx["from"], 1.3), ("crash", at + fx["from"], 1.0)]
            elif fx["type"] == "clock":
                ev += [("whoosh_l", 0.0, 1.0), ("zip_long", 0.3, 0.9), ("whoosh_l", d * 0.5, 0.8)]
            elif fx["type"] == "count":
                ev += [("drumroll", at, 1.0), ("ding", at + max(0.5, d * 0.6), 1.2)]
            elif fx["type"] == "tally":
                ev += [("pop_hi", k * d / fx["n"], 1.2) for k in range(fx["n"])]
            elif fx["type"] == "calendar":
                ev += [("paper", k * fx.get("per", 0.13), 0.7) for k in range(int(d / fx.get("per", 0.13)))]
            elif fx["type"] == "flip":
                ev += [("whoosh_s", (k + 0.5) * fx["period"] - 0.15, 0.8) for k in range(int(d / fx["period"]) + 1)]
        if ln["cg"]["scene"] == "flight":
            ev += [("whoosh_l", 0.2, 1.0), ("whoosh_l", 1.4, 1.0), ("zip_long", 2.6, 0.9)]
        if ln["cg"].get("p", {}).get("wind"):
            ev += [("whoosh_l", x, 0.9) for x in (0.0, 0.6, 1.2)]
        if ln["cg"].get("p", {}).get("blow"):
            ev += [("zip_long", ln["cg"]["p"].get("blow_at", 0.3), 1.0), ("boing", ln["cg"]["p"].get("blow_at", 0.3), 0.8)]
        if ln["cg"]["scene"] == "spin" and not ln["cg"].get("p", {}).get("slow"):
            ev += [("whoosh_s", x, 0.8) for x in (0.2, 0.6, 0.9, 1.15, 1.35)]
        se.mix(wavs[li], [(n_, at_, k_ * SE_GAIN) for n_, at_, k_ in ev if at_ < d])
    open(f"{B}/a.txt", "w").write("\n".join(f"file '{os.path.basename(a)}'" for a in wavs))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "a.txt", "all_a.wav"], check=True, cwd=B)
    total = render._wav_len(f"{B}/all_a.wav")
    # ---- 絵の合成（CGのコマ＋文字＋ずんだもん）
    t2 = time.time()
    f_ch, f_cr, f_setsu = motion.font(40), motion.font(26, "Bold"), motion.font(64)
    use_z = os.path.isdir(ZDIR)
    vids = []
    for li, ln in enumerate(lines):
        d = durs[li]; n = int(round(d * FPS))
        out = f"{B}/v{li}.mp4"
        pr = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                               "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p", "-an", out],
                              stdin=subprocess.PIPE)
        lv = mouth_levels(f"{B}/l{li}.wav", n) if use_z else None
        tel = ln["text"].split("\n")
        times = [k * d / f["n"] for f in ln.get("fx", []) if f["type"] == "tally" for k in range(f["n"])]   # 0〜24時のバーの6時間ごと
        burst_t = d * params[li].get("burst", 0.92) if ln["cg"]["scene"] == "flight" else 0
        for i in range(n):
            t = i / FPS
            fp = f"{B}/cg{li}/{i:05d}.jpg"
            fr = Image.open(fp).convert("RGB")
            if fr.size != (W, H):
                fr = fr.resize((W, H), Image.LANCZOS)
            if t < 0.15 and li and not ln.get("loop"):              # 切り替わりで少し寄った絵がパッと戻る
                z = 1 + 0.07 * (1 - t / 0.15)
                cw2, ch2 = int(W / z), int(H / z)
                fr = fr.crop(((W - cw2) // 2, (H - ch2) // 2, (W - cw2) // 2 + cw2, (H - ch2) // 2 + ch2)).resize((W, H), Image.BILINEAR)
            for fx in ln.get("fx", []):
                k = fx["type"]
                if k == "big":
                    fx_big(fr, fx, t)
                elif k == "timer":
                    fx_timer(fr, fx, t, burst_t)
                elif k == "clock":
                    fx_clock(fr, fx, t, d)
                elif k == "count":
                    fx_count(fr, fx, t, d)
                elif k == "tally":
                    fx_tally(fr, fx, t, times)
                elif k == "flip":
                    fx_flip(fr, fx, t)
                elif k == "calendar":
                    fx_calendar(fr, fx, t)
            dr = ImageDraw.Draw(fr)
            if use_z:                                                # 左下でずんだもんが喋る
                gf = int(sum(durs[:li]) * FPS) + i
                zi = zunda_img(ln.get("face", "通常"), lv[i], gf % 110 < 4)
                if zi is not None:
                    hop = int(10 * math.sin(math.pi * t / 0.25)) if t < 0.25 else 0
                    fr.paste(zi, (-90, TEL_Y - 10 - zi.height - hop), zi)
            motion.box_text(dr, W // 2, 90, sp.get("label", ""), f_ch, WHT, RED, 26, 12, anchor="ct")
            if ln.get("setsu"):                                      # 推定に幅がある話：右上に小さく「説」
                l_, t_, r_, b_ = dr.textbbox((0, 0), "説", font=f_setsu)
                bw, bh = r_ - l_ + 40, b_ - t_ + 24
                dr.rectangle([W - 40 - bw, 70, W - 40, 70 + bh], fill=WHT, outline=RED, width=6)
                dr.text((W - 40 - bw + 20 - l_, 70 + 12 - t_), "説", font=f_setsu, fill=RED)
            e = back(t / 0.2)
            mx_ = max(len(x) for x in tel)                           # 長い行は画面幅に収まる大きさまで縮める
            ft = motion.font(int(min(100 if mx_ <= 7 else 84, 960 // mx_) * (0.85 + 0.15 * e)))
            y = TEL_Y
            for j, l in enumerate(tel):
                _, hh = motion.box_text(dr, W // 2, y, l, ft, WHT, BLK, 34, 18, anchor="ct")   # 字幕は2行とも黒地に白文字
                y += hh + 14
            dr.text((30, H - 50), f"VOICEVOX:{sp.get('voice_name', '')}", font=f_cr, fill=(200, 200, 200))
            pr.stdin.write(fr.tobytes())
        pr.stdin.close(); pr.wait()
        vids.append(out)
    t_comp = time.time() - t2
    open(f"{B}/v.txt", "w").write("\n".join(f"file '{os.path.basename(x)}'" for x in vids))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "v.txt", "-c", "copy", "all.mp4"], check=True, cwd=B)
    # ---- BGM と仕上げ
    out = os.environ.get("OUT") or f"output/{sid}.mp4"
    bgm_file = sp.get("bgm_file")
    if bgm_file and os.path.exists(bgm_file):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", bgm_file, "-t", f"{total:.2f}",
                        "-ar", "24000", "-ac", "1", f"{B}/bgm.wav"], check=True)      # ループするのでフェードアウトしない
        bgm_credit = sp.get("bgm_credit", "")
    elif os.environ.get("ALLOW_CHIP_BGM"):
        import chip, wave as _w, numpy as _np
        y = chip.bgm(total + 0.5, "bounce")
        with _w.open(f"{B}/bgm.wav", "wb") as o:
            o.setnchannels(1); o.setsampwidth(2); o.setframerate(chip.SR)
            o.writeframes((y * 32767).astype(_np.int16).tobytes())
        bgm_credit = "オリジナル（手元の試し）"
    else:
        sys.exit(f"BGM {bgm_file} がない（復号前）。CIで作る")
    fc = (f"[1:a]aresample=48000[v];[2:a]aresample=48000,volume={sp.get('bgm_vol', 0.15)}[m];"
          "[v][m]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,alimiter=limit=0.79:level=disabled[a]")   # 既存と同じ -1.5dB 以下に（loudnorm だけでは 0dB に触れた）
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/all.mp4", "-i", f"{B}/all_a.wav", "-i", f"{B}/bgm.wav",
                    "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out], check=True)
    # ---- 確認用のコマ割りと投稿キット（投稿はしない）
    kit = f"nazo/manual/{sp['main']}"; os.makedirs(kit, exist_ok=True)
    nt = int(math.ceil(total / 2))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", f"fps=1/2,scale=216:-1,tile={min(nt, 9)}x{math.ceil(nt / 9)}",
                    "-frames:v", "1", f"{kit}/{sid}_sheet2s.jpg"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-t", "10", "-i", out, "-vf", "fps=4,scale=180:-1,tile=10x4",
                    "-frames:v", "1", f"{kit}/{sid}_head10.jpg"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.05", "-i", out, "-frames:v", "1", "-vf", "scale=540:-1", f"{kit}/{sid}_last.jpg"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-frames:v", "1", "-vf", "scale=540:-1", f"{kit}/{sid}_first.jpg"])
    desc = (f"{sp.get('desc', '')}\n\n音声: VOICEVOX:{sp.get('voice_name', '')}\n" + ("立ち絵: 坂本アヒル\n" if use_z else "")
            + f"BGM: {bgm_credit}\n効果音: オリジナル\n3DCG: オリジナル（three.js で作成）")
    if len(desc.encode()) > 5000 or "VOICEVOX:ずんだもん" not in desc:
        sys.exit(f"説明欄が5000バイトを超えた、またはクレジットがない（{len(desc.encode())}バイト）")
    open(f"{kit}/{sid}_upload.txt", "w", encoding="utf-8").write(
        f"【タイトル】\n{sp['title']}\n\n【説明】\n{desc}\n\n【タグ】\n{','.join(sp.get('tags', []))}\n")
    y, ev, mx = flash_check(out)
    open(f"{kit}/{sid}_luma.txt", "w", encoding="utf-8").write(
        f"明暗の大きな変化（平均輝度の差20以上）: {len(ev)}回 / どの1秒でも最大 {mx}回（基準：3回未満）\n"
        f"変化の時刻: {', '.join(f'{e:.2f}' for e in ev)}\n\n秒\t平均輝度（0〜255、0.1秒ごと）\n"
        + "".join(f"{i / FPS:.1f}\t{y[i]:.0f}\n" for i in range(0, len(y), 3)))
    print(f"明暗の変化 {len(ev)}回、1秒あたり最大 {mx}回")
    tm = (f"長さ {total:.1f}秒 / CG {sum(int(round(x * FPS)) for x in durs)}コマ {cw}x{chh} {t_cg:.0f}秒 / "
          f"合成 {t_comp:.0f}秒 / 全体 {time.time() - T0:.0f}秒")
    open(f"{kit}/{sid}_time.txt", "w", encoding="utf-8").write(tm + "\n")
    print("moso3d", out, tm)


if __name__ == "__main__":
    cmd, sid = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else os.environ.get("ID"))
    {"check": check, "build": build}[cmd](sid)
