# tools/compile_long.py — 既存ショートをつないだ総集編（横長1920x1080・30fps）を作る
#   使い方: python tools/compile_long.py nazo/compile/<id>.json output/<id>.mp4 [--from 秒 --to 秒]
#   組み方（2026-10-31 決定「ショート中心＋総集編」。15分未満、カスタムサムネが使えないのでどのコマでもサムネになる画面に）
#   - ショートは縦のまま横長の真ん中に置き、左に章名、右に要点を大きく出す（b）
#   - ショートの前後に、ずんだもんの短い導入と追加の小ネタ（a）。写真の代わりにショートのコマを使う
#   - 1章目は導入なしでショートの頭（キラーワード）から始める
#   描画の部品は tools/trivia_long.py を使う。BGM はショートと同じ曲（CIで復号）。無ければBGMなし。
import json, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, "tools"); sys.path.insert(0, "nazo"); sys.path.insert(0, "src")
import trivia_long as T                                    # noqa: E402
import theme, se                                           # noqa: E402

FPS = 30
T.FPS = FPS
W, H, SR = T.W, T.H, T.SR
WORK = "build_compile"
GAP, SEG_GAP = 0.24, 0.35


def fr(t):
    return math.ceil(t * FPS - 1e-6) / FPS


def probe(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout.strip())


def still(video, t, out, crop):
    """ショートの1コマを写真の代わりに使う（縦型 short3 は絵の帯 y=250〜1210 を切り出す）"""
    if not os.path.exists(out):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", out + ".png"], check=True)
        im = Image.open(out + ".png").convert("RGB")
        x, y, w, h = crop or (0, 250, 1080, 960)
        im.crop((x, y, x + w, y + h)).save(out, quality=92)
        os.remove(out + ".png")
    return out


def side_panel(ch, no, n_all, out):
    """ショートの左右：左に章番号と章名、右に要点（大きく）"""
    img = T.background(ch["theme"], 0).convert("RGBA")
    d = ImageDraw.Draw(img)
    th = dict(theme.THEMES[ch["theme"]]); th["face"] = T.YEL; th["edge"] = T.BLK; th["side"] = (40, 40, 40)
    lw = (W - ch["_vw"]) // 2
    T.box(d, 40, 60, f"No.{no}", T.font(70), T.WHT, T.RED)
    rows = ch["name_rows"]
    for j, r in enumerate(rows):
        sz = min(150, int((lw - 70) / max(1, len(r)) * 0.98))
        theme.extrude_text(img, lw // 2, 330 + j * (sz + 40), r, sz, th, angle=-3 if j % 2 == 0 else 3)
    x0 = W - lw + 30
    y = 90
    d.text((x0, y), "ポイント", font=T.font(52), fill=T.YEL, stroke_width=6, stroke_fill=T.BLK)
    y += 100
    for p in ch["points"]:
        f = T.font(58 if max(len(s) for s in p.split("\n")) <= 9 else 50)
        for k, s in enumerate(p.split("\n")):
            T.box(d, x0, y, s, f, T.BLK if k == 0 else T.BLK, T.WHT if k else T.YEL, 16, 8)
            y += f.size + 30
        y += 26
    gx = W - 40 - n_all * 40                              # いま何章目か
    for q in range(n_all):
        d.rounded_rectangle([gx + q * 40, H - 40, gx + q * 40 + 30, H - 24], 6, fill=T.YEL if q < no else T.WHT, outline=T.BLK, width=3)
    img.convert("RGB").save(out)
    return out


def build(spec_path, out, t_from=None, t_to=None):
    spec = json.load(open(spec_path, encoding="utf-8"))
    meta, chs = spec["meta"], spec["chapters"]
    os.makedirs(WORK, exist_ok=True)
    vv = meta["voice"]
    # 1) 部品：ショートの長さ・コマ・声
    sections = []
    for ci, ch in enumerate(chs):
        ch["_dur"] = probe(ch["video"])
        cw, chh = (ch["crop"][2], ch["crop"][3]) if ch.get("crop") else (1080, 1920)
        s = min(H / chh, (W - 2 * 600) / cw) if not ch.get("crop") else min((W - 1000) / cw, H / chh)
        ch["_vw"], ch["_vh"] = int(cw * s) // 2 * 2, int(chh * s) // 2 * 2
        lines = []
        for part in ("intro", "extra"):
            for li, ln in enumerate(ch.get(part, [])):
                ln = dict(ln)
                ln["_part"] = part
                st = ln.get("still", ch.get("still", 1.0))
                ln["img"] = still(ch["video"], st, f"{WORK}/{ch['id']}_{st:.2f}.jpg", ch.get("crop_still"))
                ln["_img"] = ln["img"]
                fx = []
                if ln.get("stamp"):
                    fx.append(dict({"type": "stamp", "at": 0.25, "y": 0.25, "size": 150}, **ln["stamp"]))
                if ln.get("count"):
                    fx.append(dict({"type": "count", "at": 0.2, "dec": 0}, **ln["count"]))
                ln["fx"] = fx
                if part == "intro" and li == 0:
                    ln["chapter"] = True
                lines.append(ln)
        sections.append({"id": ch["id"], "name": ch["short_name"], "theme": ch["theme"], "lines": lines, "_no": ci + 1})
    data = {"sections": sections}
    # 2) タイムライン（声の行とショートの枠）
    rows, segs, chapters = [], [], []
    t = 0.0
    import hashlib
    for ci, (ch, sc) in enumerate(zip(chs, sections)):
        chapters.append((t, ch["chapter"]))
        def talk(part):
            nonlocal t
            t0 = t
            for li, ln in enumerate(sc["lines"]):
                if ln["_part"] != part:
                    continue
                say = ln["say"]
                for k_, v_ in meta.get("yomi_words", {}).items():
                    say = say.replace(k_, v_)
                p = f"{WORK}/v_" + hashlib.md5((say + json.dumps(vv, sort_keys=True)).encode()).hexdigest()[:12] + ".wav"
                if not os.path.exists(p) or not os.path.exists(p + ".kana"):
                    open(p + ".kana", "w").write(T.synth(vv, say, p))
                x = T.load_wav(p)
                hold = ln.get("hold", 0.0) + (0.1 if ln.get("up") else 0)
                rows.append([t, t + len(x) / SR + hold, ci, li, x, T.env_of(x)])
                t += len(x) / SR + hold + GAP
            if t > t0:
                t = fr(t + 0.1)
                segs.append(("talk", t0, t, ci))
        talk("intro")
        d = fr(ch["_dur"])
        segs.append(("short", t, t + d, ci))
        t = fr(t + d + 0.05)
        talk("extra")
        t = fr(t + SEG_GAP)
    total = t
    print("全体の長さ", round(total, 2), "秒", f"({int(total // 60)}分{total % 60:.2f}秒)")
    # 3) 音：声・効果音・BGM（話の部分だけ）・ショートの音
    mix = np.zeros(int((total + 1) * SR), np.float32)
    talk_mask = np.zeros(len(mix), np.float32)
    ev = []
    for t0, t1, ci, li, x, _ in rows:
        ln = sections[ci]["lines"][li]
        i = int(t0 * SR); mix[i:i + len(x)] += x * 0.9
        if ln.get("chapter"):
            ev += [("whoosh_l", t0, 0.5), ("boom", t0 + 0.3, 0.45)]
        if ln.get("up"):
            ev += [("boom", t0, 0.45)]
        for f in ln["fx"]:
            ev += {"stamp": [("pop_big", t0 + f["at"], 0.6)], "count": [("drumroll", t0 + f["at"], 0.5), ("ding", t0 + f["at"] + 0.9, 0.6)]}[f["type"]]
    for name, at, k in ev:
        s = se.sound(name)
        s = np.interp(np.arange(int(len(s) * SR / se.SR)) * se.SR / SR, np.arange(len(s)), s).astype(np.float32)
        i = int(at * SR); mix[i:i + len(s)] += s[:max(0, len(mix) - i)] * k
    for kind, a, b, ci in segs:
        if kind == "talk":
            talk_mask[int(a * SR):int(b * SR)] = 1
        else:
            tw = f"{WORK}/sa_{ci}.wav"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", chs[ci]["video"], "-vn", "-ac", "1", "-ar", str(SR), tw], check=True)
            y = T.load_wav(tw) * 0.75                     # ショートは音圧を上げてあるので少し下げて声と合わせる
            i = int(a * SR); n = min(len(y), int((b - a) * SR)); mix[i:i + n] += y[:n]
    bgm = meta.get("bgm_file")
    if bgm and os.path.exists(bgm):
        bw = f"{WORK}/bgm.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-stream_loop", "-1", "-i", bgm, "-t", f"{total + 1:.2f}", "-ac", "1", "-ar", str(SR), bw], check=True)
        y = T.load_wav(bw)[:len(mix)]
        k = np.convolve(talk_mask, np.ones(int(0.3 * SR)) / int(0.3 * SR), "same")[:len(y)]   # ショートの間は止める（つなぎ目は0.3秒でなめらかに）
        mix[:len(y)] += y * meta.get("bgm_vol", 0.14) * k
        print("BGM:", bgm)
    else:
        print("BGM なし（暗号化された曲は CI でだけ使える）")
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.92
    wav = f"{WORK}/mix.wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    open(f"{WORK}/yomi.txt", "w", encoding="utf-8").write(
        "\n".join(f"{sections[r[2]]['lines'][r[3]]['say']}\n  → {open(_vp(meta, sections[r[2]]['lines'][r[3]]['say']) + '.kana').read()}" for r in rows) + "\n")
    # 4) 映像：話の部分は1コマずつ描き、ショートの部分は ffmpeg で左右の板に重ねる
    starts = np.array([r[0] for r in rows])
    vids = []
    lo, hi = (t_from or 0), (t_to or total)
    for si, (kind, a, b, ci) in enumerate(segs):
        if b <= lo or a >= hi:
            continue
        o = f"{WORK}/seg{si:02d}.mp4"
        n = int(round((b - a) * FPS))
        enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]
        if kind == "talk":
            p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                                  "-i", "-"] + enc + [o], stdin=subprocess.PIPE)
            for k in range(n):
                p.stdin.write(T.frame(a + k / FPS, data, rows, starts).tobytes())
            p.stdin.close(); p.wait()
        else:
            ch = chs[ci]
            bg = side_panel(ch, ci + 1, len(chs), f"{WORK}/side_{ci}.png")
            vf = (f"[1:v]fps={FPS},{'crop=%d:%d:%d:%d,' % (ch['crop'][2], ch['crop'][3], ch['crop'][0], ch['crop'][1]) if ch.get('crop') else ''}"
                  f"scale={ch['_vw']}:{ch['_vh']},tpad=stop_mode=clone:stop_duration=2[v];"
                  f"[0:v][v]overlay={(W - ch['_vw']) // 2}:{(H - ch['_vh']) // 2}[o]")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-r", str(FPS), "-i", bg, "-i", ch["video"],
                            "-filter_complex", vf, "-map", "[o]", "-frames:v", str(n)] + enc + [o], check=True)
        vids.append((o, a, b))
        print(" ", kind, ch_name(chs[ci]), f"{a:.1f}-{b:.1f}", flush=True)
    open(f"{WORK}/v.txt", "w").write("\n".join(f"file '{os.path.basename(o)}'" for o, _, _ in vids))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", "v.txt", "-c", "copy", "video.mp4"], check=True, cwd=WORK)
    a0 = vids[0][1]; a1 = vids[-1][2]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", f"{WORK}/video.mp4", "-ss", f"{a0:.3f}", "-t", f"{a1 - a0:.3f}", "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", out], check=True)
    with open(out.replace(".mp4", "_chapters.txt"), "w", encoding="utf-8") as f:
        for ct, name in chapters:
            f.write(f"{int(ct // 60)}:{int(ct % 60):02d} {name}\n")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out, "-vf", "fps=1/10,scale=320:-1,tile=8x12", "-frames:v", "1",
                    out.replace(".mp4", "_sheet.jpg")])
    print(out, round(a1 - a0, 2), "s")


def ch_name(ch):
    return ch["chapter"]


def _vp(meta, say0):
    import hashlib
    say = say0
    for k_, v_ in meta.get("yomi_words", {}).items():
        say = say.replace(k_, v_)
    return f"{WORK}/v_" + hashlib.md5((say + json.dumps(meta["voice"], sort_keys=True)).encode()).hexdigest()[:12] + ".wav"


if __name__ == "__main__":
    a = sys.argv[1:]
    tf = float(a[a.index("--from") + 1]) if "--from" in a else None
    tt_ = float(a[a.index("--to") + 1]) if "--to" in a else None
    build(a[0], a[1], tf, tt_)
