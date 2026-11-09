# nazo/machigai3d.py — 妄想科学「動く間違い探し」ショート（3DCGの箱庭。2026-11-03〜）
#   python nazo/machigai3d.py check <ID>   … 読みの関門（合格すると nazo/state/mach3d_yomi_<ID>.json）
#   python nazo/machigai3d.py build <ID>   … 書き出し（output/<ID>.mp4 と nazo/manual/moso_science/<ID>_*）
#   台本: nazo/shorts/<ID>.json
#     diffs: [[違いの名前, 答えの読み上げ, 答えのテロップ], ...]   … 名前は nazo/cg/scene.js の hakoniwa の説明を参照
#     search: 探す秒数 / cam: [回り始めの角度, 終わりの角度] / title, desc, tags
#   画面：上がA（元の箱庭）、下がB（違いあり）。カメラは同じ動き。探す時間が終わったらカメラを止め、答えの丸を順に出す。
import json, math, os, subprocess, sys, time, shutil, hashlib, wave
sys.path[:0] = ["src", "nazo"]
import numpy as np
from PIL import Image, ImageDraw
import render, yomi, se, motion

W, H, FPS = 1080, 1920, 30
PW, PH, TOPY, GAPY = 1080, 640, 290, 16          # パネルの大きさ、上のパネルの位置、パネルの間
# 11/3 ゲンタさん「下の部分が詰まって見にくい」：YouTube の画面では下の約2割（チャンネル名・登録ボタン・タイトル）と
# 右端（高評価・コメント・共有のボタン）に重なる。絵と答えの丸は y≦1600、x≦0.86 に収める（下の帯は空けておく）
YEL, BLK, WHT, RED, CYAN = (255, 226, 0), (0, 0, 0), (255, 255, 255), (230, 40, 40), (60, 230, 255)
B = "build_mach3d"
SE_GAIN, BGM_GAIN = 0.7, 0.8


def reveal(sp):
    # 11/3 ゲンタさん「答えは概要欄…映像の中で答え合わせはせずに」：reveal=false なら答え合わせをせず、答えは説明欄に書く（実験B）
    return sp.get("reveal", True)


def lines_of(sp):
    n = len(sp["diffs"])
    L = [("intro", sp.get("intro", f"違いは{n}つ。{sp['search']}秒で探すのだ！")),
         ("left3", sp.get("left3", "あと3秒なのだ！"))]
    if not reveal(sp):
        # 11/3 ゲンタさん「時間内に見つけられたら天才なのだ、とかにしましょう。ずんだもんだから許される」
        L.append(("end", sp.get("end", "時間内に見つけられたら、天才なのだ。")))
        return L
    L += [("ans", sp.get("ans", "答え合わせなのだ。"))]
    L += [(f"d{i}", d[1]) for i, d in enumerate(sp["diffs"])]
    L.append(("end", sp.get("end", f"{n}つ全部、見つけられたのだ？")))
    return L


def gate_key(pairs):
    return hashlib.md5(json.dumps(pairs, ensure_ascii=False).encode()).hexdigest()


def pairs_of(sp):
    return [(t, sp.get("yomi", {}).get(t, t)) for _, t in lines_of(sp)]


def check(sid):
    import yomi_gate
    sp = json.load(open(f"nazo/shorts/{sid}.json", encoding="utf-8"))
    pairs = pairs_of(sp)
    yomi_gate._V = dict(yomi_gate.verified()); yomi_gate._V.update({w: "ok" for w in sp.get("yomi_ok", [])})
    iss = yomi_gate.check(pairs, sp.get("yomi_words", {}), yomi.kana)
    for s, t in pairs:
        print(s, "→", yomi.kana(t))
    if iss:
        print("\n関門で止めた:\n" + "\n".join(iss)); sys.exit(1)
    os.makedirs("nazo/state", exist_ok=True)
    json.dump({"key": gate_key(pairs)}, open(f"nazo/state/mach3d_yomi_{sid}.json", "w"))
    print("関門: 合格")


def voiced(wav):
    with wave.open(wav) as w:
        sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16)
    idx = np.nonzero(np.abs(a) > 400)[0]
    return (idx[-1] / sr if len(idx) else 0.3), sr


def tts(text, wav):
    render.tts(text, wav)
    return voiced(wav)[0]


def build(sid):
    T0 = time.time()
    sp = json.load(open(f"nazo/shorts/{sid}.json", encoding="utf-8"))
    pairs = pairs_of(sp)
    rec = f"nazo/state/mach3d_yomi_{sid}.json"
    if not os.path.exists(rec) or json.load(open(rec))["key"] != gate_key(pairs):
        sys.exit(f"読みの関門を通っていない（python nazo/machigai3d.py check {sid}）")
    shutil.rmtree(B, ignore_errors=True); os.makedirs(B); os.makedirs("output", exist_ok=True)
    render.B = B; render.TIGHT = True
    render.set_voice(**sp.get("voice", {"vvm": "0.vvm", "style": 3, "speed": 1.1, "intonation": 1.15}))
    for s, t in pairs:
        render._YOMI[s] = t
    # ---- 声と時間割
    L = dict(lines_of(sp)); dur = {}
    for k, t in lines_of(sp):
        dur[k] = tts(t, f"{B}/{k}.wav")
    n, S = len(sp["diffs"]), sp["search"]
    t_intro = max(1.8, dur["intro"] + 0.2)                     # 冒頭：0秒から箱庭が2つ動いている。声とテロップで出題
    t_search0 = t_intro                                        # 探す時間（タイマーが動く）
    t_ans0 = t_search0 + S
    RV = reveal(sp)
    if RV:
        per = [max(1.2, dur[f"d{i}"] + 0.2) for i in range(n)]
        t_d = [t_ans0 + dur["ans"] + 0.25 + sum(per[:i]) for i in range(n)]
        t_end0 = t_d[-1] + per[-1]
        total = t_end0 + dur["end"] + 0.6
        events = [("intro", 0.05), ("left3", t_ans0 - 3.0), ("ans", t_ans0 + 0.1)] + [(f"d{i}", t_d[i]) for i in range(n)] + [("end", t_end0)]
    else:
        t_d = []
        t_end0 = t_ans0 + 0.15
        total = t_end0 + max(dur["end"] + 0.5, 2.4)             # 「答えはタイトルをタップ→説明欄」を読める長さ。そのまま冒頭に戻る
        events = [("intro", 0.05), ("left3", t_ans0 - 3.0), ("end", t_end0)]
    print("長さ", round(total, 1), "秒")
    # ---- CG（A と B を同じカメラで描く。答え合わせの間はカメラを止める）
    names = [d[0] for d in sp["diffs"]]
    a0, a1 = sp.get("cam", [-0.45, 0.45])
    base = {"cam_a0": a0, "cam_a1": a1, "hold": t_ans0, "cam_r": sp.get("cam_r", 21), "cam_h": sp.get("cam_h", 11)}
    jobs = [{"scene": sp.get("scene", "hakoniwa"), "p": dict(base), "d": total, "fps": FPS, "w": PW, "h": PH, "out": f"{B}/A"},
            {"scene": sp.get("scene", "hakoniwa"), "p": dict(base, diff=names), "d": total, "fps": FPS, "w": PW, "h": PH, "out": f"{B}/B",
             "probe": {"t": t_ans0 + 0.01, "names": names}}]
    json.dump(jobs, open(f"{B}/jobs.json", "w"))
    t1 = time.time()
    subprocess.run(["node", "nazo/cg/render_cg.js", f"{B}/jobs.json"], check=True)
    t_cg = time.time() - t1
    pos = json.load(open(f"{B}/B/probe.json"))
    for nm, q in zip(names, pos):
        if q is None or not (0.05 < q[0] < 0.86 and 0.06 < q[1] < 0.94):   # 右端のボタンに丸がかからないように
            sys.exit(f"違い {nm} の場所が画面の外（{q}）。カメラの角度を変える")
    # ---- 音（声＋効果音）
    sr = 24000
    mix = np.zeros(int((total + 1) * sr), np.float32)
    for k, at in events:
        with wave.open(f"{B}/{k}.wav") as w:
            r = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if r != sr:
            a = np.interp(np.arange(int(len(a) * sr / r)) * r / sr, np.arange(len(a)), a)
        i = int(at * sr); mix[i:i + len(a)] += a[:len(mix) - i]
    sev = [("pop_big", 0.0), ("chime_b", t_ans0)] + [("ding", t) for t in t_d]
    sev += [("tick", t_ans0 - k) for k in (3, 2, 1)]
    for nm, at in sev:
        s = se.sound(nm).astype(np.float32) * SE_GAIN
        i = int(at * sr); mix[i:i + len(s)] += s[:len(mix) - i]
    mix = np.clip(mix, -1, 1)
    with wave.open(f"{B}/voice.wav", "wb") as o:
        o.setnchannels(1); o.setsampwidth(2); o.setframerate(sr); o.writeframes((mix * 32767).astype(np.int16).tobytes())
    # ---- 合成
    tel = {k: t for k, t in lines_of(sp)}
    tel_d = {f"d{i}": d[2] for i, d in enumerate(sp["diffs"])}
    def cur_tel(t):
        k = None
        for kk, at in events:
            if at <= t:
                k = kk
        if k is None:
            k = "intro"
        if k == "left3" and t > t_ans0:
            k = "ans"
        return k
    f_title, f_sub, f_tel, f_cr = motion.font(92), motion.font(54), motion.font(66), motion.font(26)
    t2 = time.time()
    pr = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", f"{B}/v.mp4"], stdin=subprocess.PIPE)
    nf = int(round(total * FPS))
    for fi in range(nf):
        t = fi / FPS
        fr = Image.new("RGB", (W, H), (255, 214, 64))
        ia = min(fi, len(os.listdir(f"{B}/A")) - 1)
        A = Image.open(f"{B}/A/{ia:05d}.jpg"); Bm = Image.open(f"{B}/B/{ia:05d}.jpg")
        fr.paste(A, (0, TOPY)); fr.paste(Bm, (0, TOPY + PH + GAPY))
        d = ImageDraw.Draw(fr, "RGBA")
        d.rectangle([0, TOPY + PH, W, TOPY + PH + GAPY], fill=YEL)
        # 上の見出し：動く間違い探し／違いは n つ
        d.text((36, 74), sp.get("head", "動く間違い探し"), font=f_title, fill=YEL, anchor="lm", stroke_width=10, stroke_fill=BLK)
        # タイマー（探す時間だけ。数字が減る。残り3秒で赤）
        if t_search0 <= t < t_ans0:
            v = t_ans0 - t
            col = RED if v < 3 else WHT
            # 11/9 ゲンタさん「中央のタイマーが邪魔すぎます」：絵の上には置かず、いちばん上の見出しの右に置く
            tx, ty = W - 36 - 120, 74
            d.rounded_rectangle([tx - 120, ty - 48, tx + 120, ty + 48], 18, fill=(0, 0, 0, 230), outline=CYAN, width=4)
            d.text((tx, ty), f"{v:05.2f}", font=motion.font(60), fill=col, anchor="mm")
            p = v / S
            d.rectangle([24, 262, 24 + int((W - 48) * p), 276], fill=(RED if v < 3 else CYAN))
        # 字幕（黒地に白文字。答えは黄色）
        k = cur_tel(t)
        txt = tel_d.get(k, tel.get(k, ""))
        if k == "intro" or t < t_ans0:
            txt = tel["intro"] if t < t_ans0 - 3 else tel["left3"]
        if k == "end":
            txt = tel["end"]
        motion.box_text(d, W // 2, 178, txt, f_tel if len(txt) <= 14 else motion.font(int(66 * 14 / len(txt))), WHT if not k.startswith("d") else YEL, BLK, 30, 14, anchor="ct")
        if not RV and t >= t_end0:
            # 答えの場所の案内。字幕のすぐ下（絵のまん中には置かない）。ショートでは説明欄はタイトルをタップして開く
            motion.box_text(d, W // 2, 262, sp.get("to_desc", "答えはタイトルをタップ→説明欄"), motion.font(48), YEL, BLK, 22, 10, anchor="ct")
        # 答えの丸（出した丸は残す）。上下の両方に
        for i in range(len(t_d)):
            if t >= t_d[i]:
                u = min(1, (t - t_d[i]) / 0.25)
                x, y = pos[i][0] * PW, pos[i][1] * PH
                r = int(70 * (1.6 - 0.6 * u))
                for oy in (TOPY, TOPY + PH + GAPY):
                    d.ellipse([x - r, oy + y - r, x + r, oy + y + r], outline=RED, width=12)
                    d.text((x + r * 0.75, oy + y - r * 0.75), str(i + 1), font=motion.font(54), fill=WHT, anchor="mm", stroke_width=8, stroke_fill=RED)
        d.text((W - 22, 36 + TOPY - 30), "A", font=motion.font(44), fill=WHT, anchor="ra", stroke_width=6, stroke_fill=BLK)
        d.text((W - 22, TOPY + PH + GAPY + 10), "B", font=motion.font(44), fill=WHT, anchor="ra", stroke_width=6, stroke_fill=BLK)
        d.text((24, TOPY + 2 * PH + GAPY + 26), "VOICEVOX:ずんだもん", font=f_cr, fill=(90, 70, 20), anchor="lm")
        pr.stdin.write(fr.tobytes())
    pr.stdin.close(); pr.wait()
    t_comp = time.time() - t2
    # ---- BGM と仕上げ
    out = f"output/{sid}.mp4"
    bgm_file = sp.get("bgm_file", "assets/enc/bgm_trivia_mood2.mp3")
    chip_kind = sp.get("bgm_chip")                           # 11/3 ゲンタさん「まちがいさがしのbgmは8bitのほうがいい」：自作の8ビット風（nazo/chip.py）
    if chip_kind:
        import chip
        y = chip.bgm(total + 0.5, chip_kind)
        with wave.open(f"{B}/bgm.wav", "wb") as o:
            o.setnchannels(1); o.setsampwidth(2); o.setframerate(chip.SR); o.writeframes((y * 32767).astype(np.int16).tobytes())
        bgm_credit = "オリジナル（8ビット風）"
    elif os.path.exists(bgm_file):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", bgm_file, "-t", f"{total:.2f}", "-ar", "24000", "-ac", "1", f"{B}/bgm.wav"], check=True)
        bgm_credit = sp.get("bgm_credit", "ムード２ / 今川彰人オーケストラ（OpenTracks（旧DOVA-SYNDROME））")
    elif os.environ.get("ALLOW_CHIP_BGM"):
        import chip
        y = chip.bgm(total + 0.5, "bounce")
        with wave.open(f"{B}/bgm.wav", "wb") as o:
            o.setnchannels(1); o.setsampwidth(2); o.setframerate(chip.SR); o.writeframes((y * 32767).astype(np.int16).tobytes())
        bgm_credit = "オリジナル（手元の試し）"
    else:
        sys.exit(f"BGM {bgm_file} がない（復号前）。CIで作る")
    fc = (f"[1:a]aresample=48000[v];[2:a]aresample=48000,volume={sp.get('bgm_vol', 0.15) * BGM_GAIN:.4f}[m];"
          "[v][m]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,alimiter=limit=0.79:level=disabled[a]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/v.mp4", "-i", f"{B}/voice.wav", "-i", f"{B}/bgm.wav",
                    "-filter_complex", fc + ";[0:v]scale=1440:2560:flags=lanczos[vo]", "-map", "[vo]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", out], check=True)
    kit = "nazo/manual/moso_science"; os.makedirs(kit, exist_ok=True)
    nt = int(math.ceil(total / 2))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", f"fps=1/2,scale=216:-1,tile={min(nt, 9)}x{math.ceil(nt / 9)}", "-frames:v", "1", f"{kit}/{sid}_sheet2s.jpg"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t_end0:.2f}", "-i", out, "-frames:v", "1", "-vf", "scale=540:-1", f"{kit}/{sid}_answers.jpg"])
    ans_txt = ""
    if not RV:
        ans_txt = "\n\n■ 答え（下の絵Bで違うところ）\n" + "\n".join(f"{i + 1}. {d[2]}" for i, d in enumerate(sp["diffs"]))
    desc = (f"{sp.get('desc', '')}{ans_txt}\n\n音声: VOICEVOX:ずんだもん\nBGM: {bgm_credit}\n効果音: オリジナル\n3DCG: オリジナル（three.js で作成）")
    open(f"{kit}/{sid}_upload.txt", "w", encoding="utf-8").write(f"【タイトル】\n{sp['title']}\n\n【説明】\n{desc}\n\n【タグ】\n{','.join(sp.get('tags', []))}\n")
    tm = f"長さ {total:.1f}秒 / CG {t_cg:.0f}秒 / 合成 {t_comp:.0f}秒 / 全体 {time.time() - T0:.0f}秒"
    open(f"{kit}/{sid}_time.txt", "w", encoding="utf-8").write(tm + "\n")
    print("mach3d", out, tm)


if __name__ == "__main__":
    {"check": check, "build": build}[sys.argv[1]](sys.argv[2])
