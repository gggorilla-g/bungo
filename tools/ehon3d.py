# ehon3d.py — 動く絵本（ペーパーマリオ式の紙芝居舞台）を書き出す
#   台本（演出）: nazo/ehon/<id>.json … pages[]: bg / floor / light / rain / thunder / items[] / lines[] / sfx[]
#     時刻は各ページの中の割合 u（0〜1）で書く。読み上げの長さからページの長さが決まり、秒に直して舞台へ渡す
#   絵: Codex が画像生成で作った PNG（assets フォルダ）。紙人形にするため、白い紙のふちを付けて nazo/kaizo/ehon/<id>/ に置く
#   舞台: nazo/kaizo/ehon_stage.html（three.js）。1コマずつ render.js で描く
#   声: VOICEVOX:ちび式じい（ホー博士の声）。音楽：オルゴール風の自作。効果音：YouTube オーディオライブラリなどの「ありもの」
#   使い方: python3 tools/ehon3d.py nazo/ehon/<id>.json [stills 1,5,9]
import os, sys, re, json, math, wave, subprocess, shutil
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ehon import musicbox, swish, bell, wrap, SR, rngf
from ballsim import mtof

KZ = "nazo/kaizo"; FPS = 30


def paper_cut(src, dst, maxh=1100, border=14):
    """透明PNGを切り詰め、白い紙のふちを付ける"""
    im = Image.open(src).convert("RGBA"); im = im.crop(im.getbbox())
    if im.height > maxh: im = im.resize((int(im.width * maxh / im.height), maxh), Image.LANCZOS)
    pad = border * 2; base = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0)); base.alpha_composite(im, (pad, pad))
    a = base.split()[3].point(lambda v: 255 if v > 40 else 0)
    ring = a.filter(ImageFilter.MaxFilter(border * 2 + 1)).filter(ImageFilter.GaussianBlur(1.5))
    paper = Image.new("RGBA", base.size, (247, 243, 234, 255)); paper.putalpha(ring)
    paper.alpha_composite(base); paper.save(dst); return paper.width / paper.height


def synth(sp, B):
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
    A = "vv_assets"; v = sp.get("voice", {"vvm": "10.vvm", "style": 42, "speed": .92})
    ort = Onnxruntime.load_once(filename=f"{A}/voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3")
    s = Synthesizer(ort, OpenJtalk(f"{A}/open_jtalk_dic_utf_8-1.11"))
    with VoiceModelFile.open(f"{A}/{v['vvm']}") as m: s.load_voice_model(m)
    out = {}
    for pi, pg in enumerate(sp["pages"]):
        for li, text in enumerate(pg["lines"]):
            p = f"{B}/v{pi:02d}_{li:02d}.wav"
            if not os.path.exists(p):
                say = re.sub(r"[ 　]", "", text)
                for k, r in sp.get("yomi", {}).items(): say = say.replace(k, r)
                q = s.create_audio_query(say, v["style"]); q.speed_scale = v.get("speed", .92); q.pre_phoneme_length = .15; q.post_phoneme_length = .4
                q.intonation_scale = v.get("into", 1.1)
                open(p, "wb").write(s.synthesis(q, v["style"]))
            with wave.open(p) as w: out[(pi, li)] = (p, w.getnframes() / w.getframerate())
    return out


def load_audio(path, sr=SR):
    """mp3/wav などを ffmpeg でモノラルの浮動小数に"""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def main(path, mode=None, arg=None):
    sp = json.load(open(path, encoding="utf-8")); sid = sp["id"]; B = f"build_ehon/{sid}"; os.makedirs(B, exist_ok=True)
    A = sp["assets"]; OUT = f"{KZ}/ehon/{sid}"; os.makedirs(OUT, exist_ok=True)
    # 絵を紙人形に
    aspect = {}
    def prep(name, cut=True):
        if name in aspect: return f"ehon/{sid}/{name}.png"
        src = f"{A}/{name}.png"
        if cut: aspect[name] = paper_cut(src, f"{OUT}/{name}.png")
        else:
            im = Image.open(src).convert("RGB"); im.thumbnail((1800, 1800)); im.save(f"{OUT}/{name}.png"); aspect[name] = im.width / im.height
        return f"ehon/{sid}/{name}.png"
    vo = synth(sp, B)
    GAP, PAD0, PAD1, TR = .55, 1.4, 1.4, 1.2
    TC = sp.get("title_sec", 3.5); t = TC + .6 if TC else .9; pages = []
    for pi, pg in enumerate(sp["pages"]):
        t0 = t; tl = t + PAD0; L = []
        for li, text in enumerate(pg["lines"]):
            p, d = vo[(pi, li)]; L.append(dict(t=tl, d=d, wrap=wrap(text, pg.get("text", {}).get("wrap", 16)), wav=p)); tl += d + GAP + pg.get("pause", [0] * 9)[li] if isinstance(pg.get("pause"), list) else d + GAP
        t1 = tl - GAP + PAD1 + pg.get("tail", 0); pages.append((t0, t1, L)); t = t1 + TR
    total = pages[-1][1] + 2.0
    stage = {"title": sp["title"], "pages": [], "title_t": [.3, TC] if TC else [0, 0], "title_card": sp.get("title_card", {}), "fov": sp.get("fov", 24)}
    U = lambda pi, u: pages[pi][0] + u * (pages[pi][1] - pages[pi][0])
    for pi, pg in enumerate(sp["pages"]):
        t0, t1, L = pages[pi]; bg = prep(pg["bg"], cut=False)
        P = {"t0": t0, "t1": t1, "bg": bg, "bg_aspect": aspect[pg["bg"]], "floor": pg.get("floor", "#7f9a6a"), "light": pg.get("light", 1.0),
             "lines": [{"t": l["t"], "d": l["d"], "wrap": l["wrap"]} for l in L], "items": []}
        for k in ("bg_h", "bg_y", "bg_x", "text"):
            if k in pg: P[k] = pg[k]
        if "cam" in pg: P["cam"] = [dict(c, t=U(pi, c["u"])) for c in pg["cam"]]
        if "bg2" in pg: P["bg2"] = {"img": prep(pg["bg2"]["img"], cut=False), "t": U(pi, pg["bg2"]["u"]), "dur": pg["bg2"].get("dur", 2)}
        if "light_to" in pg: P["light_to"] = [U(pi, pg["light_to"][0]), pg["light_to"][1]]
        if "rain" in pg: P["rain"] = [U(pi, pg["rain"][0]), U(pi, pg["rain"][1])]
        if "thunder" in pg: P["thunder"] = [U(pi, u) for u in pg["thunder"]]
        for it in pg["items"]:
            q = {"tex": prep(it["img"]), "aspect": aspect[it["img"]], "x": it.get("x", 0), "z": it.get("z", 0), "h": it.get("h", .8), "face": it.get("face", 1),
                 "pop": it.get("pop", True), "breath": it.get("breath", False), "shadow": it.get("shadow", True), "acts": []}
            if "show" in it: q["show"] = U(pi, it["show"])
            if "hide" in it: q["hide"] = U(pi, it["hide"])
            for a in it.get("acts", []):
                b = dict(a)
                for kk in ("t", "t0", "t1"):
                    if kk in b: b[kk] = U(pi, b[kk])
                if "pose" in b: b["pose"] = prep(b["pose"])
                if "frames" in b: b["frames"] = [prep(f) for f in b["frames"]]
                if "end" in b: b["end"] = prep(b["end"])
                q["acts"].append(b)
            P["items"].append(q)
        stage["pages"].append(P)
    stage["output"] = sp.get("output", {"width": 1920, "height": 1080})
    stage["aspect"] = {f"ehon/{sid}/{k}.png": v for k, v in aspect.items()}
    json.dump(stage, open(f"{KZ}/specs/{sid}.json", "w"), ensure_ascii=False)
    print("長さ", round(total, 1), "秒")
    rel = f"specs/{sid}.json"
    if mode == "stills":
        subprocess.run(["node", "render.js", "--page", "ehon_stage.html", "--spec", rel, "stills", arg, os.path.abspath(f"{B}/stills")], cwd=KZ, check=True); return
    N = int(total * FPS); fr = os.path.abspath(f"{B}/frames")
    if not os.environ.get("REUSE_FRAMES"): shutil.rmtree(fr, ignore_errors=True)
    jobs = int(os.environ.get("JOBS", "2")); cut = [N * i // jobs for i in range(jobs + 1)]
    if not os.environ.get("REUSE_FRAMES"):   # 絵はそのままで音だけ作り直すときは REUSE_FRAMES=1
        ps = [subprocess.Popen(["node", "render.js", "--page", "ehon_stage.html", "--spec", rel, "range", str(cut[i]), str(cut[i + 1]), fr], cwd=KZ) for i in range(jobs)]
        for p in ps: p.wait()
    raw = f"{B}/v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{fr}/f%04d.jpg", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", raw], check=True)
    # 音
    n = int(SR * (total + 3)); voice = np.zeros(n); fx = np.zeros(n)
    def put(buf, a, t, g=1.0):
        k = int(t * SR)
        if 0 <= k < n: buf[k:k + len(a)] += a[:n - k] * g
    for (t0, t1, L) in pages:
        for l in L: put(voice, load_audio(l["wav"]), l["t"])
    for i, (t0, t1, L) in enumerate(pages[:-1]): put(fx, swish(.9, i), t1 + .1, .8)
    sfxlib = sp.get("sfx_files", {})
    for pi, pg in enumerate(sp["pages"]):
        for s in pg.get("sfx", []):
            a = load_audio(sfxlib[s["name"]]); st = int(s.get("from", 0) * SR); du = int(s.get("dur", 4) * SR); a = a[st:st + du]
            fade = int(min(.3, s.get("dur", 4) / 5) * SR); a[:fade] *= np.linspace(0, 1, fade); a[-fade:] *= np.linspace(1, 0, fade)
            put(fx, a, U(pi, s["at"]), s.get("gain", .5))
        for it in pg["items"]:   # 跳ねる着地ごとに小さな木琴
            for a in it.get("acts", []):
                if a["do"] == "hop":
                    for j in range(1, a["n"] + 1):
                        tt = U(pi, a["t0"]) + (U(pi, a["t1"]) - U(pi, a["t0"])) * j / a["n"]; put(fx, bell(mtof([67, 69, 72, 74, 76][j % 5]), 1.2), tt, .07)
            if "show" in it: [put(fx, bell(mtof(m), 1.5), U(pi, it["show"]) + q * .08, .08) for q, m in enumerate([84, 88, 91])]
    mb = musicbox(total, sp.get("music_seed", 5))[:n] * sp.get("music_gain", .42)
    env = np.convolve((np.abs(voice) > .01).astype(float), np.ones(SR // 4) / (SR // 4), "same"); mb *= 1 - .5 * np.clip(env * 3, 0, 1)
    mix = voice + mb + fx; mix = mix / (np.abs(mix).max() + 1e-9) * .9
    wv = f"{B}/mix.wav"
    with wave.open(wv, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    os.makedirs("output", exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-i", wv, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", f"output/{sid}.mp4"], check=True)
    print(f"書き出し: output/{sid}.mp4  {total:.1f}秒")


if __name__ == "__main__":
    main(sys.argv[1], *(sys.argv[2:4]))
