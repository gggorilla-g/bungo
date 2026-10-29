# nazo/short2.py — 謎のショート Ver.2（縦型 1080x1920、30〜40秒）
#   本編のあらすじを縮めるのではなく、本編から「単独で成り立つ疑問」を1つ切り出す。
#   最初の数秒は謎の物そのものを大きく見せ、ホー博士は情報が変わるところで大きさを変えて出る。
#   中盤で本編の疑問を匂わせ、最後に関連動画（本編）へ誘う。テロップは隙間なく出し続ける。
#   台本: nazo/shorts/<ID>.json   実行: ID=phaistos_3 python nazo/short2.py （A版。VARIANTS=A,B で比較用にB版も）
#     A: 冒頭からホー博士が出る   B: 謎の映像から始め、2文目でホー博士が出る
import json, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
sys.path.insert(0, "src"); sys.path.insert(0, "nazo")
import render, yomi, motion, se, m4_images
import brand as nazo_brand

W, H, FPS = 1080, 1920, 30
YEL, BLK, WHT, RED = (255, 226, 0), (0, 0, 0), (255, 255, 255), (192, 57, 43)
IMG_Y, IMG_H = 250, 960            # 絵を置く帯
TEL_Y = 1235                       # テロップの位置
HOST = {"none": 0, "small": 330, "mid": 450, "big": 600}
SPEED = 1.2                        # ショートは本編より速く
GAP = 0.04                         # 文と文のすき間（間を作らない）
CUT = 1.1                          # 1つの文の中でも、この秒数ごとに寄る場所を変えて切る
SPOTS = [(0.32, 0.35), (0.66, 0.42), (0.45, 0.68), (0.62, 0.62), (0.4, 0.45), (0.55, 0.3)]
B = "build_short2"


def ease_out(x):
    return 1 - (1 - min(max(x, 0), 1)) ** 3


def crop_zoom(src, cx, cy, z, w, h):
    """絵を w×h の枠に、中心(cx,cy)・倍率 z で切り抜く（z=1 で枠いっぱい）"""
    s = max(w / src.width, h / src.height) * z
    cw, ch = w / s, h / s
    x0 = min(max(cx * src.width - cw / 2, 0), max(src.width - cw, 0))
    y0 = min(max(cy * src.height - ch / 2, 0), max(src.height - ch, 0))
    return src.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.BILINEAR)


def glyph_tile(g, size, mode):
    """円盤の文字（線画）を、型（mode=stamp：木の札に浮き彫り）か、押した跡（mode=print：粘土のくぼみ）にする"""
    a = g.convert("L").resize((int(g.width * size / g.height), size), Image.LANCZOS)
    ink = a.point(lambda v: 255 if v < 140 else 0)
    if mode == "stamp":
        tile = Image.new("RGB", (size + 40, size + 40), (92, 64, 40))
        tile.paste((236, 214, 170), (20 + (size - a.width) // 2, 20), ink)
    else:
        tile = Image.new("RGB", (size + 24, size + 24), (196, 150, 104))
        sh = ink.filter(ImageFilter.GaussianBlur(2))
        tile.paste((120, 84, 52), (12 + (size - a.width) // 2 + 2, 14), sh)
        tile.paste((98, 66, 40), (12 + (size - a.width) // 2, 12), ink)
    return tile


def diagram(kind, glyphs, t):
    """自前で描く簡単な模式図（実写の再現映像の代わり）"""
    im = Image.new("RGB", (W, IMG_H), (24, 22, 20))
    d = ImageDraw.Draw(im)
    f = motion.font(46, "Bold")
    if kind == "stamps":
        d.text((W // 2, 40), "型", font=f, fill=YEL, anchor="mt")
        uniq = list({id(g): g for g in glyphs}.values())[:3]
        for j, g in enumerate(uniq):              # 上段：型
            tile = glyph_tile(g, 150, "stamp")
            x = 120 + j * 310
            y = 120 - int(30 * math.sin(min(1, max(0, t * 2 - j * 0.4)) * math.pi))   # 順に押す動き
            im.paste(tile, (x, y))
        d.text((W // 2, 420), "↓ 押す", font=f, fill=WHT, anchor="mt")
        d.rectangle([40, 500, W - 40, 800], fill=(196, 150, 104))   # 下段：粘土
        n = min(len(glyphs), 1 + int(t * 4))       # 押した跡が1つずつ増える
        for j, g in enumerate(glyphs[:n]):
            im.paste(glyph_tile(g, 110, "print"), (70 + j * 160, 570))
    else:   # type：円盤と活字の考え方を並べる
        for col, (label, items) in enumerate((("円盤", glyphs[:3]), ("活字", ["印", "刷", "物"]))):
            x0 = 60 + col * 500
            d.text((x0 + 220, 140), label, font=f, fill=WHT, anchor="mt")
            for j, it in enumerate(items):
                y = 240 + j * 190
                if isinstance(it, str):
                    d.rectangle([x0 + 130, y, x0 + 310, y + 170], fill=(70, 70, 76))
                    d.text((x0 + 220, y + 85), it, font=motion.font(110), fill=(230, 230, 230), anchor="mm")
                else:
                    im.paste(glyph_tile(it, 130, "stamp"), (x0 + 130, y))
    return im


def cut_plan(ln, d, li):
    """画像の文を CUT 秒ごとに切る。最初のカットは台本の zoom、あとは別の場所へ寄る／引く（Ver.2 濃い版）"""
    if not ln.get("file") or ln.get("main_thumb"):
        return [(0.0, None)]
    files = [ln["file"]] + ln.get("alts", [])
    n = max(1, int(d / CUT + 0.35))
    out = [(0.0, (ln["file"],) + tuple(ln.get("zoom", [0.5, 0.5, 1.0, 1.08])))]
    for c in range(1, n):
        cx, cy = (ln["spots"][(c - 1) % len(ln["spots"])] if ln.get("spots") else SPOTS[(li * 3 + c) % len(SPOTS)])
        z = 1.15 if c % 3 == 2 else 2.0 + 0.4 * ((li + c) % 2)     # 寄り・寄り・引き の順
        out.append((c * d / n, (files[c % len(files)], cx, cy, z, z * 1.06)))
    return out


def loud_offset(path, win=8.0):
    """BGMのいちばん盛り上がっているところの開始秒"""
    wav = f"{B}/bgm_full.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-ac", "1", "-ar", "8000", wav], check=True)
    with wave.open(wav) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
    hop = 8000
    rms = [np.sqrt((x[i:i + hop] ** 2).mean()) for i in range(0, len(x) - hop, hop)]
    k = int(win)
    best = max(range(max(1, len(rms) - k)), key=lambda i: sum(rms[i:i + k]))
    return float(max(0, best - 1))


def build(sid):
    sp = json.load(open(f"nazo/shorts/{sid}.json", encoding="utf-8"))
    main = sp["main"]
    os.makedirs(B, exist_ok=True); os.makedirs("output", exist_ok=True)
    render.B = B
    v = dict(sp.get("voice") or nazo_brand.VOICE); v["speed"] = v.get("speed", 1.0) * SPEED
    vname = sp.get("voice_name", nazo_brand.VOICE_NAME)       # 台本で声を替えられる（例：ずんだもんの雑学ショート）
    label = sp.get("label", "ホー博士｜世界の謎")
    render.set_voice(**v)
    fixes = {}
    if os.path.exists(f"nazo/drafts/{main}_yomi.json"):
        fixes = json.load(open(f"nazo/drafts/{main}_yomi.json", encoding="utf-8"))
    fixes.update(sp.get("yomi", {}))
    lines = sp["lines"]
    for ln in lines:
        render._YOMI[ln["say"]] = fixes.get(ln["say"]) or yomi.base_fix(ln["say"], {"title": "", "author": ""}, {})
        print("読み:", ln["say"], "→", yomi.kana(render._YOMI[ln["say"]]))
    # 画像
    files = list(dict.fromkeys([f for ln in lines if ln.get("file") for f in [ln["file"]] + ln.get("alts", [])]
                               + sp.get("glyphs", [])))
    got = m4_images.commons_files(files, width=2400) if files else {}
    local = {}
    for j, (fn, info) in enumerate(got.items()):
        if m4_images.download(info["url"], f"{B}/img{j}.png", fallback=info.get("orig")):
            local[fn] = f"{B}/img{j}.png"
    print(f"画像 {len(local)}/{len(files)}")
    def _rgb(p):           # 透明な部分（線画など）は紙の色の上に
        im = Image.open(p)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            return Image.alpha_composite(Image.new("RGBA", im.size, (226, 214, 190, 255)), im).convert("RGB")
        return im.convert("RGB")
    imgs = {fn: _rgb(p) for fn, p in local.items() if fn not in sp.get("glyphs", [])}
    _gc = {}
    for g in sp.get("glyphs", []):            # 同じ文字は同じ画像（模式図で「同じ型」を表すため）
        if g in local and g not in _gc:
            _gc[g] = Image.open(local[g]).convert("RGBA")
    glyphs = [_gc[g] for g in sp.get("glyphs", []) if g in _gc]
    if glyphs:   # 透明部分を白地に
        _w = {id(g): Image.alpha_composite(Image.new("RGBA", g.size, (255, 255, 255, 255)), g).convert("RGB") for g in _gc.values()}
        glyphs = [_w[id(g)] for g in glyphs]
    main_thumb = Image.open(f"nazo/manual/{main}/thumb.png").convert("RGB") if os.path.exists(f"nazo/manual/{main}/thumb.png") else None
    # 音声（A・B共通）
    wavs, durs, plans = [], [], []
    for li, ln in enumerate(lines):
        wav = f"{B}/l{li}.wav"
        render.tts(ln["say"], wav)
        last = li == len(lines) - 1
        d = math.ceil((render._wav_len(wav) + ((GAP if ln.get("loop") else 0.9) if last else GAP)) * FPS) / FPS   # ループの締めは間を空けず頭へつなぐ
        render._pad_wav(wav, f"{B}/l{li}_p.wav", d)
        cuts = cut_plan(ln, d, li)
        ev = [(("whoosh_s" if c % 2 else "tick"), t0, 0.7) for c, (t0, _) in enumerate(cuts) if c > 0]
        if ln.get("emph"):
            ev.append(("thud", 0.02, 1.0))
        plans.append(cuts)
        se.mix(f"{B}/l{li}_p.wav", ev + [("pop_mid" if li % 2 else "pop_hi", 0.0, 0.8)] +
               ([("whoosh_l", 0.0, 1)] if li == (1 if lines[0].get("greet") else 0) else []) + ([("chime_b", d - 0.8, 0.8)] if li == len(lines) - 1 and not ln.get("loop") else []))
        wavs.append(f"{B}/l{li}_p.wav"); durs.append(d)
    open(f"{B}/a.txt", "w").write("\n".join(f"file '{os.path.basename(a)}'" for a in wavs))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "a.txt", "all_a.wav"], check=True, cwd=B)
    total = render._wav_len(f"{B}/all_a.wav")
    bgm = sp["bgm"] if "bgm" in sp else nazo_brand.nazo_brand({"title": ""}).get("bgm_hook")
    off = loud_offset(bgm) if bgm and os.path.exists(bgm) else 0.0
    print("BGM開始", off, "秒")
    f_ch, f_cr = motion.font(40), motion.font(26, "Bold")
    outs = []
    for var in os.environ.get("VARIANTS", "A").split(","):   # 既定はA（冒頭からホー博士）。比べたいときだけ VARIANTS=A,B
        vids = []
        for li, ln in enumerate(lines):
            d = durs[li]; n = int(round(d * FPS))
            mouth = motion.mouth_track(wavs[li], n)
            hsz = HOST[ln.get("host", "small")]
            first = 1 if lines[0].get("greet") else 0     # 冒頭のあいさつ（1秒）があれば、謎の映像はその次の文
            if var == "B" and li <= first:
                hsz = 0                                   # B：あいさつは声だけ。謎の映像の文まで博士は出さない
            if var == "A" and li <= first and sp.get("owl", True):
                hsz = HOST["mid"]
            out = f"{B}/{var}{li}.mp4"
            p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                                  "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                                  "-pix_fmt", "yuv420p", "-an", out], stdin=subprocess.PIPE)
            src = imgs.get(ln.get("file"))
            bgsrc = src or (main_thumb if ln.get("main_thumb") else None)
            bg = (ImageEnhance.Brightness(crop_zoom(bgsrc, 0.5, 0.5, 1.0, W, H).filter(ImageFilter.GaussianBlur(30))).enhance(0.3)
                  if bgsrc else Image.new("RGB", (W, H), (16, 16, 18)))
            tel = ln["text"].split("\n")
            for i in range(n):
                t = i / FPS
                fr = bg.copy()
                if ln.get("diagram"):
                    fr.paste(diagram(ln["diagram"], glyphs, t / d), (0, IMG_Y))
                elif ln.get("main_thumb") and main_thumb:
                    th = main_thumb.resize((960, 540), Image.LANCZOS)
                    fr.paste(th, (60, IMG_Y + 140))
                    ImageDraw.Draw(fr).text((W // 2, IMG_Y + 60), sp.get("cta_head", "関連動画の本編"), font=motion.font(52), fill=YEL, anchor="mt")
                elif src:
                    cuts = plans[li]
                    ci = max(c for c, (t0, _) in enumerate(cuts) if t0 <= t + 1e-6)
                    t0 = cuts[ci][0]; t1 = cuts[ci + 1][0] if ci + 1 < len(cuts) else d
                    fn, cx, cy, z0, z1 = cuts[ci][1]
                    tc = t - t0
                    if ci == 0 and ln.get("fast"):
                        k = 0.85 * ease_out(tc / 1.0) + 0.15 * tc / (t1 - t0)   # 冒頭は一気に寄る
                    else:
                        k = tc / max(t1 - t0, 0.1)
                    z = z0 + (z1 - z0) * k
                    if ci > 0:
                        z *= 1 + 0.10 * (1 - ease_out(tc / 0.18))             # 切った瞬間に少し寄って止まる
                    img = crop_zoom(imgs.get(fn, src), cx, cy, z, W, IMG_H)
                    if ci > 0 and tc < 2 / FPS:                                # 切り替わりの2コマだけ白く光る
                        img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), 0.35)
                    if ln.get("emph") and t < 0.3:                              # 強調の文は頭で小さく揺れる
                        img = img.transform(img.size, Image.AFFINE, (1, 0, int(8 * math.sin(t * 60)), 0, 1, 0))
                    if ln.get("dim"):
                        img = ImageEnhance.Brightness(img).enhance(1 - (1 - ln["dim"]) * min(1, t / d * 1.5))
                    fr.paste(img, (0, IMG_Y))
                dr = ImageDraw.Draw(fr)
                motion.box_text(dr, W // 2, 90, label, f_ch, WHT, RED, 26, 12, anchor="ct")
                e = motion.back(min(1, t / 0.22))
                ft = motion.font(int(92 * (0.9 + 0.1 * e)) if max(len(x) for x in tel) <= 9 else int(80 * (0.9 + 0.1 * e)))
                y = TEL_Y
                for j, l in enumerate(tel):
                    fg_, bg_ = (BLK, YEL) if j == len(tel) - 1 else (WHT, BLK)
                    _, hh = motion.box_text(dr, W // 2, y, l, ft, fg_, bg_, 34, 18, anchor="ct")
                    y += hh + 14
                hsz = min(hsz, H - 40 - y - 10) if hsz else 0     # 博士はテロップにかぶらない大きさまで
                if hsz:
                    # 出てきた最初の文だけ、下から少し持ち上がって登場
                    prev = HOST[lines[li - 1].get("host", "small")] if li else 0
                    if var == "B" and li == first + 1: prev = 0
                    rise = int(80 * (1 - ease_out(t / 0.35))) if prev == 0 else 0
                    o, _ = motion.owl_frame(i, mouth[i], bool(ln.get("point")), li, size=hsz)
                    fr.paste(o, (W - o.width + 30, H - o.height - 40 + rise), o)
                dr.text((30, H - 50), f"VOICEVOX:{vname}", font=f_cr, fill=(200, 200, 200))
                p.stdin.write(fr.tobytes())
            p.stdin.close(); p.wait()
            vids.append(out)
        open(f"{B}/v{var}.txt", "w").write("\n".join(f"file '{os.path.basename(x)}'" for x in vids))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", f"v{var}.txt", "-c", "copy",
                        f"all_{var}.mp4"], check=True, cwd=B)
        out = f"output/short2_{sid}_{var}.mp4"
        if bgm and os.path.exists(bgm):
            fc = ("[1:a]aresample=48000[v];[2:a]aresample=48000,atrim=start=%.2f,asetpts=PTS-STARTPTS,volume=0.11,"
                  "afade=t=out:st=%.2f:d=1.2[m];[v][m]amix=inputs=2:normalize=0:duration=first,"
                  "loudnorm=I=-14:TP=-1.5:LRA=11[a]" % (off, max(0, total - 1.2)))
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/all_{var}.mp4", "-i", f"{B}/all_a.wav", "-i", bgm,
                            "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                            "-b:a", "192k", "-t", f"{total:.3f}", out], check=True)
        else:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/all_{var}.mp4", "-i", f"{B}/all_a.wav",
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out], check=True)
        outs.append(out)
        kit = f"nazo/manual/{main}"; os.makedirs(kit, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", "fps=1/2.5,scale=270:-1,tile=8x2",
                        "-frames:v", "1", f"{kit}/short2_{sid}_{var}_sheet.jpg"])
    # 投稿用
    used = [fn for fn in files if fn in local]
    open(f"nazo/manual/{main}/short2_{sid}_upload.txt", "w", encoding="utf-8").write(
        f"【タイトル】\n{sp['title']}\n\n【説明】\n{sp.get('desc', '本編は関連動画から：' + nazo_brand.CHANNEL)}\n\n"
        f"音声: VOICEVOX:{vname}\n" + ("BGM: the ghost house / 稿屋 隆（DOVA-SYNDROME）\n" if bgm else "")
        + "".join(f"画像: {got[fn]['credit']}\n" for fn in used) +
        f"\n【タグ】\n{','.join(sp.get('tags') or (nazo_brand.VOICE_TAGS + ['世界の謎', 'ショート']))}\n\n"
        "【メモ（貼らない）】\n"
        "アップ後、編集画面の「関連動画」に本編を選ぶ\n")
    print("short2", outs, round(total, 1), "秒")


if __name__ == "__main__":
    build(os.environ.get("ID") or sys.argv[1])
