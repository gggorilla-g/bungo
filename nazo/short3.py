# nazo/short3.py — 雑学ショート（縦型 1080x1920）。写真の使い回しで単調にならないよう、
#   文ごとに簡単なモーショングラフィックス（fx）を重ねる。冒頭はダイジェスト（今日の顔ぶれを一気見せ）。
#   台本: nazo/shorts/<ID>.json  実行: python nazo/short3.py <ID>
#   行のキー:
#     file / fit: "contain"（全体を見せる。既定）| "cover"（寄り） / zoom: [cx, cy, z0, z1]（coverのとき）
#     fx: [{type: stamp|count|vs|ring|warn|split|rank, ...}]  … 下の draw_fx を参照
#     digest: [{"file":..., "name":...}, ...]  … 冒頭の一気見せ
import json, math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
sys.path.insert(0, "src"); sys.path.insert(0, "nazo")
import render, yomi, motion, se, m4_images

W, H, FPS = 1080, 1920, 30
YEL, BLK, WHT, RED = (255, 226, 0), (0, 0, 0), (255, 255, 255), (220, 40, 40)
PY, PH = 250, 960                  # 絵の帯
TEL_Y = 1235
SPEED, GAP = 1.2, 0.04
B = "build_short3"


def ease(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def back(x):
    return motion.back(min(max(x, 0), 1))


def cover(src, cx, cy, z, w, h):
    s = max(w / src.width, h / src.height) * z
    cw, ch = w / s, h / s
    x0 = min(max(cx * src.width - cw / 2, 0), max(src.width - cw, 0))
    y0 = min(max(cy * src.height - ch / 2, 0), max(src.height - ch, 0))
    return src.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.BILINEAR)


def contain(src, s=1.0):
    """全体が入る大きさで中央に置く。戻り値：(画像, 左上x, 左上y, 倍率) … ringの座標合わせに使う"""
    k = min(W * 0.96 / src.width, PH * 0.92 / src.height) * s
    im = src.resize((max(1, int(src.width * k)), max(1, int(src.height * k))), Image.BILINEAR)
    return im, (W - im.width) // 2, (PH - im.height) // 2, k


def panel_bg(src):
    return ImageEnhance.Brightness(cover(src, 0.5, 0.5, 1.2, W, PH).filter(ImageFilter.GaussianBlur(28))).enhance(0.45)


def big_text(d, x, y, text, size, fg, stroke=10, sfill=BLK, anchor="mm"):
    d.text((x, y), text, font=motion.font(size), fill=fg, stroke_width=stroke, stroke_fill=sfill, anchor=anchor)


def draw_fx(pan, fx, t, d, place):
    """pan: 絵の帯（W×PH）に描く。t: 文の中の経過秒、d: 文の長さ、place: contain配置 (x0,y0,k,src) か None"""
    dr = ImageDraw.Draw(pan)
    at = fx.get("at", 0.15)
    u = t - at
    if u < 0:
        return
    k = fx["type"]
    if k == "stamp":                     # どんと押す大文字（少し傾けて揺らす）
        s = 1.6 - 0.6 * back(u / 0.25)
        size = int(fx.get("size", 190) * s)
        lay = Image.new("RGBA", (W, PH), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        big_text(ld, W // 2, int(PH * fx.get("y", 0.5)), fx["text"], size, tuple(fx.get("color", RED)), 14, WHT)
        lay = lay.rotate(fx.get("tilt", -8), center=(W // 2, PH * fx.get("y", 0.5)))
        if u < 0.3:
            lay = lay.transform(lay.size, Image.AFFINE, (1, 0, int(14 * math.sin(u * 80)), 0, 1, 0))
        pan.paste(lay, (0, 0), lay)
    elif k == "count":                   # 数字がぐるぐる上がって止まる
        dim = Image.new("RGBA", (W, PH), (0, 0, 0, 150))
        pan.paste(dim, (0, 0), dim)
        v = fx["to"] * ease(u / max(0.6, d * 0.5 - at))
        txt = f"{int(round(v)):,}" if fx["to"] >= 10 else f"{v:.1f}".rstrip("0").rstrip(".")
        if fx.get("label"):
            big_text(dr, W // 2, int(PH * 0.33), fx["label"], 80, WHT, 8)
        big_text(dr, W // 2, int(PH * 0.55), txt + fx.get("unit", ""), fx.get("size", 200), YEL, 12)
    elif k == "vs":                      # 左右に分けて比べる（左右から滑り込む）
        e = ease(u / 0.35)
        for side, key, col in ((-1, "left", (40, 90, 160)), (1, "right", (180, 50, 50))):
            it = fx[key]
            x = int(W / 4 * (2 + side) + side * (1 - e) * W / 2)
            box = Image.new("RGBA", (W // 2 - 20, PH - 120), col + (215,))
            pan.paste(box, (x - box.width // 2, 60), box)
            big_text(dr, x, 200, it["label"], it.get("size", 64), WHT, 8)
            if u > 0.45:
                p = back((u - 0.45) / 0.25)
                big_text(dr, x, PH // 2 + 60, it["value"], int(150 * (0.6 + 0.4 * p)), YEL, 12)
        if u > 0.3:
            big_text(dr, W // 2, PH // 2 + 60, "VS", 90, WHT, 10)
    elif k == "ring":                    # 写真の一点を丸で囲んで名札（contain配置のとき）
        if not place:
            return
        x0, y0, sc, src = place
        cx, cy = x0 + fx["x"] * src.width * sc, y0 + fx["y"] * src.height * sc
        r = fx.get("r", 0.1) * W
        a = 360 * ease(u / 0.4)
        dr.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + a, fill=YEL, width=14)
        if u > 0.35:
            p = back((u - 0.35) / 0.25)
            lx, ly = cx + (r + 40) * (1 if cx < W * 0.6 else -1), cy - r - 30
            f = motion.font(int(70 * p) or 1)
            motion.box_text(dr, int(lx), int(ly), fx["label"], f, BLK, YEL, 22, 10,
                            anchor="lt" if cx < W * 0.6 else "rt")
    elif k == "warn":                    # 黄黒の警告テープが横切る
        e = ease(u / 0.3)
        tape = Image.new("RGBA", (W * 2, 180), (0, 0, 0, 0))
        td = ImageDraw.Draw(tape)
        for i in range(0, W * 2, 90):
            td.polygon([(i, 0), (i + 45, 0), (i - 45 + 45, 180), (i - 45, 180)], fill=YEL + (255,))
            td.polygon([(i + 45, 0), (i + 90, 0), (i + 45, 180), (i, 180)], fill=BLK + (255,))
        off = int((1 - e) * W) - int(u * 120) % 90
        band = tape.crop((max(0, -off), 0, max(0, -off) + W, 180))
        y = int(PH * fx.get("y", 0.5)) - 90
        pan.paste(band.rotate(-6, expand=False), (0, y), band.rotate(-6, expand=False))
        if u > 0.2:
            motion.box_text(dr, W // 2, y + 40, fx["text"], motion.font(int(110 * back((u - 0.2) / 0.25)) or 1),
                            YEL, BLK, 40, 12, anchor="ct")
    elif k == "split":                   # 幕で真ん中を仕切り、片側だけ色が変わっていく
        e = ease(u / 0.5)
        lay = Image.new("RGBA", (W, PH), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        g = ease((u - 0.6) / 1.6)
        ld.rectangle([W // 2, 0, W, PH], fill=(60, 170, 60, int(170 * g)))
        ld.rectangle([0, 0, W // 2, PH], fill=(40, 110, 200, 70))
        pan.paste(lay, (0, 0), lay)
        dr.rectangle([W // 2 - 10, 0, W // 2 + 10, int(PH * e)], fill=WHT)
        if u > 0.5:
            big_text(dr, W // 4, 120, fx["left"], 64, WHT, 8)
            big_text(dr, W * 3 // 4, 120, fx["right"], 64, YEL, 8)
    elif k == "title":                   # 冒頭のタイトルをバーンと（放射の集中線＋拡大して止まる＋揺れ）
        pan.paste((10, 10, 14), (0, 0, W, PH))
        rays = Image.new("RGBA", (W, PH), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rays)
        cx, cy = W // 2, PH // 2
        for a in range(0, 360, 10):
            r1 = math.radians(a + u * 40); r2 = math.radians(a + 5 + u * 40)
            rd.polygon([(cx, cy), (cx + 1600 * math.cos(r1), cy + 1600 * math.sin(r1)),
                        (cx + 1600 * math.cos(r2), cy + 1600 * math.sin(r2))], fill=tuple(fx.get("ray", [200, 30, 30])) + (120,))
        pan.paste(rays, (0, 0), rays)
        rows = fx["text"].split("\n")
        for j, row in enumerate(rows):
            p = back((u - 0.12 * j) / 0.22)
            if p <= 0:
                continue
            size = int(fx.get("size", 150) * (2.2 - 1.2 * p))
            y = int(PH * (0.5 + (j - (len(rows) - 1) / 2) * 0.24))
            sh = int(10 * math.sin(u * 70)) if u < 0.35 + 0.12 * j else 0
            cols = fx.get("colors") or [WHT] * (len(rows) - 1) + [YEL]
            big_text(dr, W // 2 + sh, y, row, size, tuple(cols[j]), 16, BLK)
    elif k == "rank":                    # 左上の番号札
        p = back(u / 0.25)
        f = motion.font(int(96 * p) or 1)
        motion.box_text(dr, 40, 30, fx["text"], f, WHT, RED, 30, 12, anchor="lt")


def digest_frame(pan, items, imgs, t, d):
    """冒頭の一気見せ：顔ぶれが1つずつポップして並ぶ（2×2）"""
    n = len(items)
    per = max(0.25, (d - 0.3) / n)
    cw, ch = W // 2 - 30, PH // 2 - 40
    for i, it in enumerate(items):
        u = t - i * per
        if u < 0:
            continue
        p = back(u / 0.22)
        tile = cover(imgs[it["file"]], it.get("cx", 0.5), it.get("cy", 0.5), 1.0, cw, ch)
        tile = tile.resize((max(1, int(cw * (0.6 + 0.4 * p))), max(1, int(ch * (0.6 + 0.4 * p)))))
        x = 20 + (i % 2) * (W // 2) + (cw - tile.width) // 2
        y = 30 + (i // 2) * (PH // 2) + (ch - tile.height) // 2
        pan.paste(tile, (x, y))
        dr = ImageDraw.Draw(pan)
        motion.box_text(dr, x + tile.width // 2, y + tile.height - 20, it["name"], motion.font(46), BLK, YEL, 16, 8, anchor="cb")


def build(sid):
    sp = json.load(open(f"nazo/shorts/{sid}.json", encoding="utf-8"))
    main = sp["main"]
    os.makedirs(B, exist_ok=True); os.makedirs("output", exist_ok=True)
    render.B = B
    v = dict(sp["voice"]); v["speed"] = v.get("speed", 1.0) * SPEED
    render.set_voice(**v)
    fixes = sp.get("yomi", {})
    lines = sp["lines"]
    for ln in lines:
        render._YOMI[ln["say"]] = fixes.get(ln["say"]) or yomi.base_fix(ln["say"], {"title": "", "author": ""}, {})
        print("読み:", ln["say"], "→", yomi.kana(render._YOMI[ln["say"]]))
    files = list(dict.fromkeys([f for ln in lines for f in ([ln["file"]] if ln.get("file") else []) +
                                [x["file"] for x in ln.get("digest", [])]]))
    got = m4_images.commons_files(files, width=2000)
    imgs = {}
    for j, (fn, info) in enumerate(got.items()):
        p = f"{B}/img{j}.png"
        if m4_images.download(info["url"], p, fallback=info.get("orig")):
            imgs[fn] = Image.open(p).convert("RGB")
    print(f"画像 {len(imgs)}/{len(files)}")
    # 音声と効果音
    wavs, durs = [], []
    for li, ln in enumerate(lines):
        wav = f"{B}/l{li}.wav"
        render.tts(ln["say"], wav)
        d = math.ceil((render._wav_len(wav) + (0.9 if li == len(lines) - 1 else GAP)) * FPS) / FPS
        render._pad_wav(wav, f"{B}/l{li}_p.wav", d)
        ev = [("pop_big" if li % 2 else "bubble", 0.0, 0.9), ("zip_up", 0.0, 0.7)]   # 文の頭は毎回鳴らす
        for fx in ln.get("fx", []):
            at = fx.get("at", 0.15)
            ty = fx["type"]
            if ty == "title":
                rows = len(fx["text"].split("\n"))
                ev += [("boom", at, 1.0), ("crash", at, 0.8)] + [("thud", at + 0.12 * j, 1.0) for j in range(rows)] + [("kira", at + 0.5, 0.9)]
            elif ty == "stamp":
                ev += [("boom" if li % 2 else "boing", at, 1.0), ("crash", at, 0.45)]
            elif ty == "count":
                ev += [("drumroll", at, 1.0), ("ding", at + max(0.6, d * 0.5 - at), 1.2)]
            elif ty == "vs":
                ev += [("zip_up", at, 1.0), ("zip_dn", at + 0.15, 1.0), ("boom", at + 0.45, 0.9)]
            elif ty == "ring":
                ev += [("bubble", at, 1.0), ("kira", at + 0.35, 0.9)]
            elif ty == "warn":
                ev += [("buzzer", at, 1.0), ("boom", at, 0.8)]
            elif ty == "split":
                ev += [("whoosh_l", at, 1.0), ("slide_dn", at + 0.5, 0.8)]
            elif ty == "rank":
                ev += [("slide_up", at, 0.9), ("boing", at + 0.25, 0.9)]
        if ln.get("digest"):
            n = len(ln["digest"]); per = max(0.25, (d - 0.3) / n)
            ev += [("pop_big" if i % 2 else "zip_up", i * per, 1.0) for i in range(n)]
        if li == len(lines) - 1:
            ev += [("chime_b", d - 0.8, 1.0), ("crash", d - 0.8, 0.5)]
        se.mix(f"{B}/l{li}_p.wav", ev)
        wavs.append(f"{B}/l{li}_p.wav"); durs.append(d)
    open(f"{B}/a.txt", "w").write("\n".join(f"file '{os.path.basename(a)}'" for a in wavs))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "a.txt", "all_a.wav"], check=True, cwd=B)
    total = render._wav_len(f"{B}/all_a.wav")
    f_ch, f_cr = motion.font(40), motion.font(26, "Bold")
    vids = []
    for li, ln in enumerate(lines):
        d = durs[li]; n = int(round(d * FPS))
        out = f"{B}/v{li}.mp4"
        p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                              "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                              "-pix_fmt", "yuv420p", "-an", out], stdin=subprocess.PIPE)
        src = imgs.get(ln.get("file"))
        bg_full = (ImageEnhance.Brightness(cover(src, 0.5, 0.5, 1.0, W, H).filter(ImageFilter.GaussianBlur(30))).enhance(0.3)
                   if src else Image.new("RGB", (W, H), (16, 16, 18)))
        pbg = panel_bg(src) if src else Image.new("RGB", (W, PH), (20, 20, 24))
        tel = ln["text"].split("\n")
        for i in range(n):
            t = i / FPS
            fr = bg_full.copy()
            place = None
            if ln.get("digest"):
                pan = Image.new("RGB", (W, PH), (14, 14, 18))
                digest_frame(pan, ln["digest"], imgs, t, d)
            elif src and ln.get("fit", "contain") == "contain":
                pan = pbg.copy()
                im, x0, y0, k = contain(src, 1.0 + 0.06 * t / d)
                pan.paste(im, (x0, y0))
                place = (x0, y0, k, src)
            elif src:
                cx, cy, z0, z1 = ln.get("zoom", [0.5, 0.5, 1.0, 1.15])
                pan = cover(src, cx, cy, z0 + (z1 - z0) * ease(t / d), W, PH)
            else:
                pan = pbg.copy()
            if ln.get("title_card"):                   # タイトルの文は写真なし
                pan = Image.new("RGB", (W, PH), (10, 10, 14))
            if t < 2 / FPS and li:                       # 文の頭で2コマだけ白く光る
                pan = Image.blend(pan, Image.new("RGB", pan.size, WHT), 0.3)
            for fx in ln.get("fx", []):
                draw_fx(pan, fx, t, d, place)
            fr.paste(pan, (0, PY))
            dr = ImageDraw.Draw(fr)
            motion.box_text(dr, W // 2, 90, sp.get("label", ""), f_ch, WHT, RED, 26, 12, anchor="ct")
            e = motion.back(min(1, t / 0.22))
            ft = motion.font(int(92 * (0.9 + 0.1 * e)) if max(len(x) for x in tel) <= 9 else int(80 * (0.9 + 0.1 * e)))
            y = TEL_Y
            for j, l in enumerate(tel):
                fg_, bg_ = (BLK, YEL) if j == len(tel) - 1 else (WHT, BLK)
                _, hh = motion.box_text(dr, W // 2, y, l, ft, fg_, bg_, 34, 18, anchor="ct")
                y += hh + 14
            dr.text((30, H - 50), f"VOICEVOX:{sp.get('voice_name', '')}", font=f_cr, fill=(200, 200, 200))
            p.stdin.write(fr.tobytes())
        p.stdin.close(); p.wait()
        vids.append(out)
    open(f"{B}/v.txt", "w").write("\n".join(f"file '{os.path.basename(x)}'" for x in vids))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "v.txt", "-c", "copy", "all.mp4"],
                   check=True, cwd=B)
    out = f"output/short3_{sid}.mp4"
    import chip, wave as _w, numpy as _np                 # 自作BGM（8ビット風）を声の下に小さく敷く
    y = chip.bgm(total + 0.5, sp.get("bgm_kind", "bounce"))
    with _w.open(f"{B}/bgm.wav", "wb") as o:
        o.setnchannels(1); o.setsampwidth(2); o.setframerate(chip.SR)
        o.writeframes((y * 32767).astype(_np.int16).tobytes())
    vol = sp.get("bgm_vol", 0.13)
    fc = (f"[1:a]aresample=48000[v];[2:a]aresample=48000,volume={vol}[m];[v][m]amix=inputs=2:normalize=0:duration=first,"
          "loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/all.mp4", "-i", f"{B}/all_a.wav", "-i", f"{B}/bgm.wav",
                    "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out],
                   check=True)
    kit = f"nazo/manual/{main}"; os.makedirs(kit, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", "fps=1/1.5,scale=270:-1,tile=10x3",
                    "-frames:v", "1", f"{kit}/short3_{sid}_sheet.jpg"])
    used = [fn for fn in files if fn in imgs]
    open(f"{kit}/short3_{sid}_upload.txt", "w", encoding="utf-8").write(
        f"【タイトル】\n{sp['title']}\n\n【説明】\n{sp.get('desc', '')}\n\n"
        f"音声: VOICEVOX:{sp.get('voice_name', '')}\n" + "BGM・効果音: オリジナル\n" + "".join(f"画像: {got[fn]['credit']}\n" for fn in used) +
        f"\n【タグ】\n{','.join(sp.get('tags', []))}\n")
    print("short3", out, round(total, 1), "秒")


if __name__ == "__main__":
    build(os.environ.get("ID") or sys.argv[1])
