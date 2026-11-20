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


def paper_cut(src, dst, maxh=1600, border=16):
    """透明PNGを切り詰め、白い紙のふちを付ける"""
    im = Image.open(src).convert("RGBA"); im = im.crop(im.getbbox()); r_ = 1.0
    if im.height > maxh: r_ = maxh / im.height; im = im.resize((int(im.width * r_), maxh), Image.LANCZOS)
    pad = border * 2; base = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0)); base.alpha_composite(im, (pad, pad))
    a = base.split()[3].point(lambda v: 255 if v > 40 else 0)
    ring = a.filter(ImageFilter.MaxFilter(border * 2 + 1)).filter(ImageFilter.GaussianBlur(1.5))
    paper = Image.new("RGBA", base.size, (247, 243, 234, 255)); paper.putalpha(ring)
    paper.alpha_composite(base); paper.save(dst)
    paper_cut.hpx = (paper.height) / r_   # 元の絵の px に直した、切り抜き後の高さ
    return paper.width / paper.height


def synth(sp, B):
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
    A = "vv_assets"; v = sp.get("voice", {"vvm": "10.vvm", "style": 42, "speed": .86})
    ort = Onnxruntime.load_once(filename=f"{A}/voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3")
    s = Synthesizer(ort, OpenJtalk(f"{A}/open_jtalk_dic_utf_8-1.11"))
    with VoiceModelFile.open(f"{A}/{v['vvm']}") as m: s.load_voice_model(m)
    out = {}
    for pi, pg in enumerate(sp["pages"]):
        for li, text in enumerate(pg["lines"]):
            p = f"{B}/v{pi:02d}_{li:02d}.wav"
            if not os.path.exists(p):
                say = re.sub(r"[ 　「」『』…]", "", text).replace("／", "、")
                for k, r in sp.get("yomi", {}).items(): say = say.replace(k, r)
                q = s.create_audio_query(say, v["style"]); q.speed_scale = v.get("speed", .92); q.pre_phoneme_length = .15; q.post_phoneme_length = .4
                q.intonation_scale = v.get("into", 1.1); q.volume_scale = v.get("vol", 1.5)
                open(p, "wb").write(s.synthesis(q, v["style"]))
            with wave.open(p) as w: out[(pi, li)] = (p, w.getnframes() / w.getframerate())
    return out


def load_audio(path, sr=SR, lp=None):
    """mp3/wav などを ffmpeg でモノラルの浮動小数に。lp: 高い音を落とす（サーというかすれを消す）"""
    af = ["-af", f"lowpass=f={lp},lowpass=f={lp}"] if lp else []
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, *af, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def main(path, mode=None, arg=None):
    sp = json.load(open(path, encoding="utf-8")); sid = sp["id"]; B = f"build_ehon/{sid}"; os.makedirs(B, exist_ok=True)
    A = sp["assets"]; OUT = f"{KZ}/ehon/{sid}"; os.makedirs(OUT, exist_ok=True)
    # 絵を紙人形に
    aspect = {}; hpx = {}
    SC = json.load(open(f"{A}/scale.json")) if os.path.exists(f"{A}/scale.json") else {}
    WR = sp.get("world", {"pino": ["head_w", .44], "lulu": ["shell_d", .5], "leaf": ["len", 1.6], "drop": ["h", .09], "flower": ["w", 1.2]})
    def prep(name, cut=True):
        if name in aspect: return f"ehon/{sid}/{name}.png"
        src = f"{A}/{name}.png"; os.makedirs(os.path.dirname(f"{OUT}/{name}.png"), exist_ok=True)
        if cut: aspect[name] = paper_cut(src, f"{OUT}/{name}.png"); hpx[name] = paper_cut.hpx
        else:
            im = Image.open(src).convert("RGB"); im.thumbnail((1800, 1800)); im.save(f"{OUT}/{name}.png"); aspect[name] = im.width / im.height
        return f"ehon/{sid}/{name}.png"
    vo = synth(sp, B)
    GAP, PAD0, PAD1, TR = .55, 1.4, 1.4, 1.2
    TC = sp.get("title_sec", 3.5); t = TC + .6 if TC else .9; pages = []
    for pi, pg in enumerate(sp["pages"]):
        t0 = t; tl = t + pg.get("pad0", PAD0); L = []; G = pg.get("gap", sp.get("gap", GAP))
        for li, text in enumerate(pg["lines"]):
            p, d = vo[(pi, li)]; L.append(dict(t=tl, d=d, wrap=sum([wrap(x, pg.get("text", {}).get("wrap", 16)) for x in text.split("／")], []), wav=p)); tl += d + G + (pg.get("pause", {}).get(str(li), 0) if isinstance(pg.get("pause"), dict) else 0)
        t1 = tl - G + PAD1 + pg.get("tail", 0)
        if not pg["lines"]: t1 = t0 + pg.get("dur", 6.0)   # 声の入らないカット（雨雲だけ、など）
        pages.append((t0, t1, L)); t = t1 + pg.get("trans", TR)
    END = sp.get("end_sec", 6.0); total = pages[-1][1] + END   # 終わりの余韻：紙色に溶けて「おしまい」、オルゴールが静かに閉じる
    cover = prep(sp["cover"], cut=False) if sp.get("cover") else None
    stage = {"cover": cover, "logo": sp.get("logo_rel"), "label": sp.get("label", "ほほほブックス"), "title": sp["title"], "end_t": pages[-1][1], "end_text": sp.get("end_text", "おしまい"), "pages": [], "title_t": [.3, TC] if TC else [0, 0], "title_card": sp.get("title_card", {}), "fov": sp.get("fov", 24)}
    def U(pi, u):
        """ページ内の時刻。数なら割合、"L2" なら2番目の文の読み始め、"L2e" なら読み終わり、"L2+0.5" のように秒をずらせる"""
        if isinstance(u, str) and u.startswith("s"): return pages[pi][0] + float(u[1:])   # "s2.4" ならページの頭から2.4秒
        if isinstance(u, str):
            m = re.match(r"L(\d+)(e?)([+-][\d.]+)?$", u); l = pages[pi][2][int(m.group(1))]
            return l["t"] + (l["d"] if m.group(2) else 0) + float(m.group(3) or 0)
        return pages[pi][0] + u * (pages[pi][1] - pages[pi][0])
    for pi, pg in enumerate(sp["pages"]):
        t0, t1, L = pages[pi]; bg = prep(pg["bg"], cut=False)
        P = {"t0": t0, "t1": t1, "bg": bg, "bg_aspect": aspect[pg["bg"]], "floor": pg.get("floor", "#7f9a6a"), "light": pg.get("light", 1.0),
             "lines": [{"t": l["t"], "d": l["d"], "wrap": l["wrap"]} for l in L], "items": []}
        if "fx" in pg: P["fx"] = [dict(f, **({"at": [U(pi, u) for u in f["at"]]} if "at" in f else {}), **({"t": U(pi, f["t"])} if "t" in f else {}), **({"t0": U(pi, f["t0"])} if "t0" in f else {})) for f in pg["fx"]]
        for k in ("bg_h", "bg_y", "bg_x", "text"):
            if k in pg: P[k] = pg[k]
        if "cam" in pg:
            P["cam"] = []
            for c in pg["cam"]:
                k = dict(c, t=U(pi, c["u"]))
                if "img" in k: k["img"] = prep(k["img"], cut=False); k["aspect"] = aspect[c["img"]]
                if "fx" in k: k["fx"] = [dict(f, **({"at": [U(pi, u) for u in f["at"]]} if "at" in f else {}), **({"t": U(pi, f["t"])} if "t" in f else {}), **({"t0": U(pi, f["t0"])} if "t0" in f else {})) for f in k["fx"]]
                P["cam"].append(k)
        if "bg2" in pg: P["bg2"] = {"img": prep(pg["bg2"]["img"], cut=False), "t": U(pi, pg["bg2"]["u"]), "dur": pg["bg2"].get("dur", 2)}
        if "light_to" in pg: P["light_to"] = [U(pi, pg["light_to"][0]), pg["light_to"][1]]
        if "rain" in pg: P["rain"] = [U(pi, pg["rain"][0]), U(pi, pg["rain"][1])]
        if "thunder" in pg: P["thunder"] = [U(pi, u) for u in pg["thunder"]]
        for it in pg["items"]:
            q = {"tex": prep(it["img"]), "aspect": aspect[it["img"]], "x": it.get("x", 0), "z": it.get("z", 0), "h": it.get("h", .8), "face": it.get("face", 1),
                 "pop": it.get("pop", True), "breath": it.get("breath", False), "shadow": it.get("shadow", True), "y0": it.get("y0", 0), "acts": []}
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
    # 絵ごとの大きさのムラをそろえる：scale.json の実測（頭の幅・殻の直径・葉の長さ）から、世界での高さを決める
    HW = {}
    for k, hp in hpx.items():
        e = SC.get(k.split("/")[-1], {})
        for key, (field, world) in WR.items():
            if key in e and field in e[key] and e[key][field]:
                HW[f"ehon/{sid}/{k}.png"] = hp * world / e[key][field]; break
    stage["hw"] = HW; print("大きさをそろえた絵:", len(HW))
    json.dump(stage, open(f"{KZ}/specs/{sid}.json", "w"), ensure_ascii=False)
    print("長さ", round(total, 1), "秒")
    rel = f"specs/{sid}.json"
    if mode == "stills":
        subprocess.run(["node", "render.js", "--page", "ehon_stage.html", "--spec", rel, "stills", arg, os.path.abspath(f"{B}/stills")], cwd=KZ, check=True); return
    N = int(total * FPS); fr = os.path.abspath(f"{B}/frames")
    if not os.environ.get("REUSE_FRAMES") and not os.environ.get("RENDER_FROM"): shutil.rmtree(fr, ignore_errors=True)
    jobs = int(os.environ.get("JOBS", "2")); F0 = int(os.environ.get("RENDER_FROM", "0")); cut = [F0 + (N - F0) * i // jobs for i in range(jobs + 1)]
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
    # ページ替えのかすれ音（サー）は耳障りなので鳴らさない（2026-11-20 オーナー指摘）
    sfxlib = sp.get("sfx_files", {})
    for pi, pg in enumerate(sp["pages"]):
        for s in pg.get("sfx", []):
            a = load_audio(sfxlib[s["name"]], lp=s.get("lp", sp.get("sfx_lp", 3200))); du = int(s.get("dur", 4) * SR); st = int(s.get("from", 0) * SR) % max(1, len(a) - min(du, len(a) - 1))
            a = np.tile(a, 1 + du // max(1, len(a)))[st:st + du] if len(a) else a   # 素材より長く使うときはくり返す
            if len(a) < 10: continue
            fade = int(min(.3, s.get("dur", 4) / 5) * SR); a[:fade] *= np.linspace(0, 1, fade); a[-fade:] *= np.linspace(1, 0, fade)
            put(fx, a, U(pi, s["at"]), s.get("gain", .5))
        for it in pg["items"]:   # 跳ねる着地ごとに小さな木琴
            for a in it.get("acts", []):
                if a["do"] == "hop":
                    for j in range(1, a["n"] + 1):
                        tt = U(pi, a["t0"]) + (U(pi, a["t1"]) - U(pi, a["t0"])) * j / a["n"]; put(fx, bell(mtof([67, 69, 72, 74, 76][j % 5]), 1.2), tt, .07)
            if "show" in it: [put(fx, bell(mtof(m), 1.5), U(pi, it["show"]) + q * .08, .08) for q, m in enumerate([84, 88, 91])]
    mb = musicbox(pages[-1][1] + 1.0, sp.get("music_seed", 5))
    mb = np.pad(mb, (0, max(0, n - len(mb))))[:n]
    te = pages[-1][1]; k0, k1 = int(te * SR), int((te + 1.2) * SR); env_o = np.ones(n); env_o[k0:k1] = np.linspace(1, 0, k1 - k0); env_o[k1:] = 0; mb *= env_o
    for q, m in enumerate([72, 76, 79, 84]): put(mb, bell(mtof(m), 3.5) * .5, te + .9 + q * .32)   # 終わりの和音（ゆっくり上がる）
    put(mb, bell(mtof(60), 4.5) * .35, te + .9)
    mb = mb * sp.get("music_gain", .22); fx *= sp.get("sfx_gain", .7)
    env = np.convolve((np.abs(voice) > .01).astype(float), np.ones(SR // 4) / (SR // 4), "same"); mb *= 1 - .65 * np.clip(env * 3, 0, 1); fx *= 1 - .45 * np.clip(env * 3, 0, 1)
    voice = np.tanh(voice * 2.2) / np.tanh(2.2)   # 声をそろえて前に出す（軽いコンプ）
    mix = voice * 1.0 + mb + fx; mix = mix / (np.abs(mix).max() + 1e-9) * .9
    wv = f"{B}/mix.wav"
    with wave.open(wv, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    os.makedirs("output", exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-i", wv, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", f"output/{sid}.mp4"], check=True)
    print(f"書き出し: output/{sid}.mp4  {total:.1f}秒")


if __name__ == "__main__":
    main(sys.argv[1], *(sys.argv[2:4]))
