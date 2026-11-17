# sleep_long.py — 睡眠用・作業用の長尺（落ち着いた男性の声＋ゆっくり回る星）を台本 JSON から作る
#   python tools/sleep_long.py build nazo/sleep/<id>.json      → output/<id>.mp4 と nazo/manual/sleep/<id>_upload.txt
#   AUDIO_ONLY=1 で音だけ作り直す。JOBS で並列数
#   声：VOICEVOX（青山龍星・しっとり 84 が既定）。字幕は台本の文字（読みは yomi で声だけ変える）
import json, os, re, subprocess, sys, wave
import numpy as np

SR = 48000; KZ = "nazo/kaizo"; A = "vv_assets"


def wrap(s, n=30):
    out, cur = [], ""
    for part in re.split(r"(?<=[、。])", s):
        if len(cur) + len(part) > n and cur: out.append(cur); cur = part
        else: cur += part
    if cur: out.append(cur)
    return out


def synth_all(sp, B):
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
    v = sp.get("voice", {"vvm": "15.vvm", "style": 84, "speed": 0.92})
    ort = Onnxruntime.load_once(filename=f"{A}/voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3")
    s = Synthesizer(ort, OpenJtalk(f"{A}/open_jtalk_dic_utf_8-1.11"))
    with VoiceModelFile.open(f"{A}/{v['vvm']}") as m: s.load_voice_model(m)
    outs = []
    for ci, ch in enumerate(sp["chapters"]):
        for li, text in enumerate(ch["lines"]):
            text = text["text"] if isinstance(text, dict) else text
            p = f"{B}/v_{ci:02d}_{li:02d}.wav"
            if not os.path.exists(p):
                say = text
                for k, r in sp.get("yomi", {}).items(): say = say.replace(k, r)
                q = s.create_audio_query(re.sub(r"[「」『』（）()]", "", say), v["style"])
                q.speed_scale = v.get("speed", .92); q.pre_phoneme_length = .1; q.post_phoneme_length = .3
                open(p, "wb").write(s.synthesis(q, v["style"]))
            with wave.open(p) as w: d = w.getnframes() / w.getframerate()
            outs.append((ci, li, text, p, d))
    return outs


def timeline(sp, voices):
    gap = sp.get("gap", 1.6); cgap = sp.get("chapterGap", 4.0); t = sp.get("intro", 3.0)
    chapters, lines = [], []
    for ci, ch in enumerate(sp["chapters"]):
        c0 = t; t += 3.5                                     # 星の名前を見せる間
        st = {"shot": "orbit", "speed": 1, "gauge": []}
        for (c, li, text, p, d) in voices:
            if c != ci: continue
            src = ch["lines"][li]
            if isinstance(src, dict):
                for k in ("shot", "speed", "gauge"):
                    if k in src: st[k] = src[k]
                if "shot" in src and "gauge" not in src: st["gauge"] = []
            lines.append({"t0": round(t, 3), "t1": round(t + d, 3), "text": text, "rows": wrap(text), "wav": p, **st}); t += d + gap
        t += cgap; chapters.append({"t0": round(c0, 3), "t1": round(t, 3), "planet": ch["planet"], "title": ch["title"], "sub": ch.get("sub", "")})
    return chapters, lines, round(t + 2, 2)


def pad(dur):
    t = np.arange(int(SR * dur)) / SR; y = np.zeros_like(t)
    chords = [[110.0, 164.8, 220.0, 277.2], [98.0, 146.8, 196.0, 246.9], [87.3, 130.8, 174.6, 220.0], [92.5, 138.6, 185.0, 233.1]]
    seg = 12.0
    for i in range(int(dur / seg) + 2):
        a = int(i * seg * SR); b = min(len(t), int((i + 1) * seg * SR + 3 * SR))
        if a >= len(t): break
        tt = t[a:b] - t[a]; env = np.clip(tt / 4, 0, 1) * np.clip((tt[-1] - tt) / 4, 0, 1)
        for f in chords[i % 4]: y[a:b] += np.sin(2 * np.pi * f * tt) * env * .02
    return y


def build(path):
    sp = json.load(open(path, encoding="utf-8")); sid = sp["id"]; B = f"build_sleep/{sid}"; os.makedirs(B, exist_ok=True)
    voices = synth_all(sp, B); chapters, lines, dur = timeline(sp, voices)
    FR = sp.get("fpsRender", 12)
    spec = {"output": {"width": 1920, "height": 1080}, "fpsRender": FR, "duration": dur, "planets": sp["planets"], "chapters": chapters,
            "lines": [{k: v for k, v in l.items() if k != "wav"} for l in lines], "note": sp.get("note", "")}
    os.makedirs(f"{KZ}/specs", exist_ok=True); json.dump(spec, open(f"{KZ}/specs/{sid}.json", "w", encoding="utf-8"), ensure_ascii=False)
    n = int(dur * FR); fr = os.path.abspath(f"{B}/fr")
    if os.environ.get("AUDIO_ONLY") != "1":
        import shutil; shutil.rmtree(fr, ignore_errors=True); os.makedirs(fr)
        jobs = int(os.environ.get("JOBS", 3)); step = (n + jobs - 1) // jobs; env = dict(os.environ); env.setdefault("NODE_PATH", "/opt/npm-tools/node_modules")
        ps = [subprocess.Popen(["node", "render.js", "--page", "scene_planet.html", "--spec", f"specs/{sid}.json", "range", str(j * step), str(min(n, (j + 1) * step)), fr],
                               cwd=KZ, env=env, stdout=subprocess.DEVNULL) for j in range(jobs)]
        if any(p.wait() for p in ps): sys.exit("コマの書き出しに失敗")
    a = pad(dur)
    for l in lines:
        with wave.open(l["wav"]) as w: x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768; sr = w.getframerate()
        x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x)
        i = int(l["t0"] * SR); a[i:i + len(x)] += x[:len(a) - i] * .9
    wv = f"{B}/mix.wav"
    with wave.open(wv, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
    out = f"output/{sid}.mp4"; os.makedirs("output", exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FR), "-i", f"{fr}/f%04d.jpg", "-i", wv, "-af", "loudnorm=I=-18:TP=-2:LRA=9,aresample=48000,pan=stereo|c0=c0|c1=c0",
                    "-vf", "scale=1920:1080,fps=24,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "160k",
                    "-t", f"{dur:.2f}", "-movflags", "+faststart", out], check=True)
    p = sp["post"]; os.makedirs("nazo/manual/sleep", exist_ok=True)
    chap = "\n".join(f"{int(c['t0'])//60}:{int(c['t0'])%60:02d} {c['title']}" for c in chapters)
    if not chap.startswith("0:00"): chap = "0:00 はじめに\n" + chap
    desc = p["desc"].replace("{chapters}", chap)
    open(f"nazo/manual/sleep/{sid}_upload.txt", "w", encoding="utf-8").write(f"【タイトル】\n{p['title']}\n\n【説明】\n{desc}\n\n【タグ】\n{', '.join(p['tags'])}\n")
    print("書き出し:", out, f"{dur:.0f}秒")


if __name__ == "__main__":
    if sys.argv[1] == "build": build(sys.argv[2])
