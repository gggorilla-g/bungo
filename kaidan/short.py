# kaidan/short.py — 怪談「今晩の百物語」の入口ショート（縦 1080x1920、30〜40秒）。本編へ誘導する。
#   台本: kaidan/drafts/<作品ID>.json の "short" 欄
#     {"title": 投稿タイトル, "main_video": 本編の動画ID, "yomi_words": {ショートだけで使う語の読み},
#      "yomi_ok": [食い違いを確認して VOICEVOX 側で正しいとした文],
#      "lines": [{"say": 読む文, "text": 字幕（\n で改行）, "file": 画像, "focus": [x, y], "hush": true}, ...]}
#     lines[0] が 0秒の一文（大きく、声と同時に出す）。最後の「続きは、関連動画で。」は自動で足す。
#     画像を書かない行は直前の画像のまま（同じ画像の間は寄りが文をまたいでつながる）。
#   使い方:
#     python kaidan/short.py check  <作品ID>   … 読みの関門（チャット側。pyopenjtalk が要る）。通れば読みの確認記録を書く
#     python kaidan/short.py render <作品ID>   … 動画と投稿キット（Actions。確認記録と一致しない読みは読まない）
#   演出の決まり：点滅・急な明暗の切り替えなし（画像の替わり目は0.4秒のクロスフェード）、驚かせる音なし、血・傷の表現なし。
import hashlib, json, math, os, re, subprocess, sys
sys.path.insert(0, "src"); sys.path.insert(0, "nazo"); sys.path.insert(0, "kaidan")
import yomi
import kaidan_brand as brand

W, H, FPS = 1080, 1920, 30
IMG_Y, IMG_H = 250, 1080           # 絵の帯
TEL_Y = 1395                       # 字幕の上端
HOST_SIZE = 380                    # 宵狐（絵の帯の左下）
SPEED = 1.04                       # 本編(0.92)より少し速く
GAP, HOOK_GAP, END_PAD = 0.22, 0.35, 1.6
XFADE = 0.4
END_SAY = "続きは、関連動画で。"
RED, BLK, WHT = (142, 20, 20), (0, 0, 0), (255, 255, 255)
B = "build_kshort"


def load(wid):
    c = json.load(open(f"kaidan/state/texts/{wid}.json", encoding="utf-8"))
    k = json.load(open(f"kaidan/drafts/{wid}.json", encoding="utf-8"))
    return c, k, dict(c["meta"], no=k["no"]), k["short"]


def all_lines(sp):
    return sp["lines"] + [{"say": END_SAY, "text": "続きは\n関連動画で", "end": True}]


def words(k, sp):
    return dict(k.get("yomi_words", {}), **sp.get("yomi_words", {}))


def tts_text(t, c, wd):
    for w, r in sorted(wd.items(), key=lambda x: -len(x[0])):   # 長い語から（stock.words_fix と同じ）
        t = t.replace(w, r)
    return yomi.base_fix(t, c["meta"], c["ruby"])


def pairs_of(wid):
    c, k, work, sp = load(wid)
    wd = words(k, sp)
    return [(ln["say"], tts_text(ln["say"], c, wd)) for ln in all_lines(sp)], wd, k, sp


def sig(pairs):
    return hashlib.sha1(json.dumps(pairs, ensure_ascii=False).encode()).hexdigest()


def check(wid):
    import yomi_gate
    pairs, wd, k, sp = pairs_of(wid)
    ok = set(k.get("yomi_ok", [])) | set(sp.get("yomi_ok", []))
    issues = yomi_gate.check(pairs, wd, yomi.kana)
    issues = [x for x in issues if x.split("｜", 1)[1] not in {o[:50] for o in ok} | {o[:40] for o in ok}]
    rows = [{"say": o, "tts": t, "kana": yomi.kana(t)} for o, t in pairs]
    for r in rows:
        print(r["say"], "\n   ", r["kana"])
    for x in issues:
        print("【読み要確認】", x)
    if issues:
        raise SystemExit(f"読みの確認が済んでいない文が {len(issues)} 件")
    os.makedirs(f"kaidan/manual/{wid}", exist_ok=True)
    json.dump({"sig": sig(pairs), "lines": rows}, open(f"kaidan/manual/{wid}/short_yomi.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("読みの関門を通過 → kaidan/manual/%s/short_yomi.json" % wid)


# ---------------- 描画 ----------------
def crop_zoom(src, cx, cy, z, w, h):
    from PIL import Image
    s = max(w / src.width, h / src.height) * z
    cw, ch = w / s, h / s
    x0 = min(max(cx * src.width - cw / 2, 0), max(src.width - cw, 0))
    y0 = min(max(cy * src.height - ch / 2, 0), max(src.height - ch, 0))
    return src.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.BILINEAR)


def fit_font(lines, start, maxw):
    import motion
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    s = start
    while s > 40:
        f = motion.font(s, "Bold")
        if max(d.textbbox((0, 0), l, font=f)[2] for l in lines) <= maxw:
            return f
        s -= 4
    return motion.font(s, "Bold")


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def render_short(wid):
    import motion, render, m4_images, kitsune
    from PIL import Image, ImageDraw, ImageEnhance
    c, k, work, sp = load(wid)
    pairs, wd, _, _ = pairs_of(wid)
    rec = json.load(open(f"kaidan/manual/{wid}/short_yomi.json", encoding="utf-8"))
    if rec["sig"] != sig(pairs):
        raise SystemExit("読みの確認記録と台本が一致しない。チャット側で python kaidan/short.py check を通す")
    lines = all_lines(sp)
    os.makedirs(B, exist_ok=True); os.makedirs("output", exist_ok=True)
    motion.FAMILY = "Noto Serif CJK JP"
    render.B = B
    v = dict(brand.VOICE, speed=SPEED)
    render.set_voice(**v)
    render.TIGHT = True
    for o, t in pairs:
        render._YOMI[o] = t
    # 画像（台本の場面ごとの指定。PD/CC0/CC BY系だけが返る）
    files = list(dict.fromkeys([ln["file"] for ln in lines if ln.get("file")] + [k["title_image"]]))
    got = m4_images.commons_files(files, width=2000)
    imgs = {}
    for j, (fn, info) in enumerate(got.items()):
        p = m4_images.download(info["url"], f"{B}/{wid}_{j}.jpg", fallback=info.get("orig"))
        if p:
            im = Image.open(f"{B}/{wid}_{j}.jpg").convert("RGB")
            im = ImageEnhance.Brightness(ImageEnhance.Color(im).enhance(0.7)).enhance(0.82)   # 色を少し抜いて暗く（一定）
            imgs[fn] = im
    print(f"画像 {len(imgs)}/{len(files)}")
    if len(imgs) < max(2, len(files) - 1):
        raise SystemExit("画像がほとんど取れなかった")
    # 音声
    wavs, durs = [], []
    for li, ln in enumerate(lines):
        wav = f"{B}/{wid}_l{li}.wav"
        if ln.get("hush"):          # ここぞという一文：低く、ゆっくり
            sv = (render.SPEED, render.PITCH)
            render.SPEED, render.PITCH = SPEED * 0.9, brand.VOICE["pitch"] - 0.04
            render.tts(ln["say"], wav)
            render.SPEED, render.PITCH = sv
        else:
            render.tts(ln["say"], wav)
        pad = END_PAD if ln.get("end") else (HOOK_GAP if li == 0 else GAP)
        d = math.ceil((render._wav_len(wav) + pad) * FPS) / FPS
        render._pad_wav(wav, f"{B}/{wid}_l{li}_p.wav", d)
        wavs.append(f"{B}/{wid}_l{li}_p.wav"); durs.append(d)
    open(f"{B}/{wid}_a.txt", "w").write("\n".join(f"file '{os.path.basename(a)}'" for a in wavs))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", f"{wid}_a.txt",
                    f"{wid}_all.wav"], check=True, cwd=B)
    total = sum(durs)
    starts = [sum(durs[:i]) for i in range(len(durs))]
    # 画像の流れ：行ごとの画像（無ければ直前のまま）。同じ画像が続く間を1つのショットにして、ゆっくり寄る
    cur, shots = None, []
    for li, ln in enumerate(lines):
        fn = ln.get("file") or (k["title_image"] if ln.get("end") else cur)
        if fn not in imgs:
            fn = cur if cur in imgs else next(iter(imgs))
        foc = tuple(ln.get("focus", (0.5, 0.45)))
        if not shots or fn != cur:
            shots.append({"file": fn, "t0": starts[li], "t1": starts[li] + durs[li], "focus": foc})
        else:
            shots[-1]["t1"] = starts[li] + durs[li]
        cur = fn

    def shot_frame(s, t):
        k_ = (t - s["t0"]) / max(s["t1"] - s["t0"], 0.1)
        z = 1.0 + 0.16 * ease(k_ * 0.85 + 0.15 * k_)            # ゆっくり寄る（急な動きなし）
        return crop_zoom(imgs[s["file"]], s["focus"][0], s["focus"][1], z, W, IMG_H)

    no = brand.kansuji(work["no"])
    title = k.get("display_title", work["title"])
    f_lab, f_cr, f_end = motion.font(40, "Bold"), motion.font(28, "Bold"), motion.font(60, "Bold")
    host_cache = {}
    out_v = f"{B}/{wid}_v.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                          "-pix_fmt", "yuv420p", "-an", out_v], stdin=subprocess.PIPE)
    tel_fonts = [fit_font(ln["text"].split("\n"), 118 if li == 0 else 96, W - 120) for li, ln in enumerate(lines)]
    n_all = int(round(total * FPS))
    for i in range(n_all):
        t = i / FPS
        li = max(j for j in range(len(lines)) if starts[j] <= t + 1e-6)
        ln = lines[li]
        si = max(j for j, s in enumerate(shots) if s["t0"] <= t + 1e-6)
        img = shot_frame(shots[si], t)
        if si > 0 and t - shots[si]["t0"] < XFADE:              # 画像の替わり目はクロスフェード（点滅させない）
            img = Image.blend(shot_frame(shots[si - 1], t), img, ease((t - shots[si]["t0"]) / XFADE))
        fr = Image.new("RGB", (W, H), (8, 8, 10))
        fr.paste(img, (0, IMG_Y))
        dr = ImageDraw.Draw(fr)
        motion.box_text(dr, W // 2, 110, f"{brand.CHANNEL}　第{no}話「{title}」", f_lab, (230, 230, 230), RED, 24, 12, anchor="ct")
        if li > 0:                                               # 宵狐：0秒の一文の後から、提灯がゆらぐ
            lv = round((0.8 + 0.12 * math.sin(i * 0.11) + 0.05 * math.sin(i * 0.37 + 1)) * 20) / 20
            if lv not in host_cache:
                host_cache[lv] = kitsune.kitsune(lv, 0, HOST_SIZE)
            hi = host_cache[lv]
            a = ease((t - starts[1]) / 0.8)                      # 最初だけゆっくり浮かぶ
            if a < 1:
                hi = hi.copy(); hi.putalpha(hi.getchannel("A").point(lambda x: int(x * a)))
            fr.paste(hi, (-20, IMG_Y + IMG_H - hi.height + 10), hi)
        if ln.get("end"):
            motion.box_text(dr, W // 2, TEL_Y - 140, f"本編「{title}」", f_end, WHT, BLK, 30, 14, anchor="ct")
        tel = ln["text"].split("\n")
        y = TEL_Y
        for j, l in enumerate(tel):
            fg_, bg_ = (WHT, RED) if j == len(tel) - 1 else (WHT, BLK)
            _, hh = motion.box_text(dr, W // 2, y, l, tel_fonts[li], fg_, bg_, 30, 16, anchor="ct")
            y += hh + 12
        dr.text((30, H - 56), f"VOICEVOX:{brand.VOICE_NAME}", font=f_cr, fill=(190, 190, 190))
        if t > total - 1.0:                                      # 最後の1秒でゆっくり暗く
            fr = ImageEnhance.Brightness(fr).enhance(max(0.0, (total - t) / 1.0))
        p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait()
    bgm = brand.BGM_TRACKS[sp.get("bgm", "climax")]
    out = f"output/kaidan_short_{wid}.mp4"
    fc = ("[1:a]aresample=48000[v];[2:a]aresample=48000,volume=%.2f,afade=t=in:d=0.6,afade=t=out:st=%.2f:d=1.6[m];"
          "[v][m]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[a]" % (sp.get("bgm_vol", 0.12), max(0, total - 1.6)))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", out_v, "-i", f"{B}/{wid}_all.wav", "-stream_loop", "-1", "-i", bgm[0],
                    "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{total:.3f}", out], check=True)
    kit = f"kaidan/manual/{wid}"; os.makedirs(kit, exist_ok=True)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                         capture_output=True, text=True).stdout.strip()
    open(f"{kit}/short_duration.txt", "w").write(dur + "\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", "fps=1/2.5,scale=270:-1,tile=8x2",
                    "-frames:v", "1", f"{kit}/short_sheet.jpg"], check=True)
    # 投稿キット（tools/short_upload.py がそのまま読む形）
    src = f"{work['author']}『{work['title']}』" + (f"（{work['translator'].removesuffix('訳')}訳）" if work.get("translator") else "")
    used = [fn for fn in dict.fromkeys(s["file"] for s in shots)]
    desc = "\n".join([f"本編はこちら → https://youtu.be/{sp['main_video']}", "",
                      sp.get("desc", f"{src}を、語り部・宵狐が語ります。続きは本編で。"), "",
                      "※権利の切れた古典の怪談を、いまの言葉で語り直した朗読です。実話ではありません。", "",
                      "#Shorts #怪談 #百物語", "", "──",
                      f"原作: {src}（青空文庫 {work.get('url', 'https://www.aozora.gr.jp/')}）",
                      f"語り: VOICEVOX:{brand.VOICE_NAME}", "BGM: " + bgm[1] + "（OpenTracks（旧DOVA-SYNDROME））"]
                     + [f"画像: {got[fn]['credit']}" for fn in used])
    tags = list(dict.fromkeys(["怪談", "百物語", "今晩の百物語", title, work["author"], "怖い話", "朗読", "Shorts"] + brand.VOICE_TAGS))
    txt = f"【タイトル】\n{sp['title']}\n\n【説明】\n{desc}\n\n【タグ】\n{','.join(tags)}\n"
    assert len(sp["title"]) <= 100 and len(desc.encode()) <= 5000, "タイトルか説明が長すぎる"
    assert f"VOICEVOX:{brand.VOICE_NAME}" in desc and "画像:" in desc
    open(f"{kit}/short_upload.txt", "w", encoding="utf-8").write(txt)
    print(f"完了: {out} {dur}秒 / 冒頭「{lines[0]['say']}」")
    if not 28 <= float(dur) <= 45:
        print(f"::warning::長さが目安（30〜40秒）から外れた: {dur}秒")


if __name__ == "__main__":
    (check if sys.argv[1] == "check" else render_short)(sys.argv[2])
