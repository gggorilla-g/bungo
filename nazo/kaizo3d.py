# kaizo3d.py — 改造ショート（問題が出るたびにパーツを1つ足していく3DCG）
#   使い方:
#     python nazo/moso3d.py check <ID>          … 読みの関門（妄想科学と共通。合格記録 nazo/state/moso3d_yomi_<ID>.json）
#     python nazo/kaizo3d.py voice <ID>         … 声を作り、実際の長さで時間割を決める（nazo/kaizo/specs/<ID>*.json）
#     python nazo/kaizo3d.py build <ID> [--bgm 曲.mp3] [--gpu] [--jobs 2]
#                                               … 3DCGを1コマずつ描き、声・効果音・BGMを重ねて output/<ID>.mp4
#   台本: nazo/shorts/<ID>.json（lines: id / say / yomi / cap（字幕の行）/ kind（intro・problem・fix・end）/ add（足すパーツ）/ fx（場面の動き））
#   絵: nazo/kaizo/<scene>.html（three.js。window.renderAt(t) で1コマ）。描画は nazo/kaizo/render.js（Playwright）
import json, os, re, subprocess, sys, wave
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render, moso3d

KZ = "nazo/kaizo"
B = "build_kaizo"
SR = 24000
FPS = 30
GAP = 0.12          # セリフとセリフの間（秒）
TAIL = 0.9          # 最後のセリフのあとの余白（秒）
POP_AT = 0.25       # パーツはセリフの出だしからこの秒数で付く（scene側と同じ値）


def load(sid):
    return json.load(open(f"nazo/shorts/{sid}.json", encoding="utf-8"))


def gate_ok(sid, sp):
    rec = f"nazo/state/moso3d_yomi_{sid}.json"
    pairs = moso3d.all_says(sp)
    if not os.path.exists(rec) or json.load(open(rec, encoding="utf-8"))["key"] != moso3d.gate_key(pairs):
        sys.exit(f"読みの関門を通っていない（python nazo/moso3d.py check {sid}）")
    return pairs


KOKORO = os.environ.get("KOKORO_DIR", "vv_assets/kokoro")   # 英語の声（kokoro-onnx、Apache-2.0）。kokoro-v1.0.onnx と voices-v1.0.bin を置く


def tts_en(text, wav, v):
    """英語の声。モデルは GitHub の thewh1teagle/kokoro-onnx の model-files-v1.0 から取る"""
    from kokoro_onnx import Kokoro
    import soundfile as sf
    global _kk
    if "_kk" not in globals():
        _kk = Kokoro(f"{KOKORO}/kokoro-v1.0.onnx", f"{KOKORO}/voices-v1.0.bin")
    a, sr = _kk.create(text, voice=v.get("speaker", "af_heart"), speed=v.get("speed", 1.0), lang="en-us")
    sf.write(wav, a, sr, subtype="PCM_16")


def voice(sid):
    sp = load(sid)
    eng = sp["voice"].get("engine")
    en, mute = eng == "kokoro", eng == "none"          # none = 声なし（字幕だけ）。各行の dur（秒）か字幕の長さで時間を決める
    os.makedirs(f"{B}/{sid}", exist_ok=True)
    if not en and not mute:                                              # 日本語は読みの関門を通してから VOICEVOX
        pairs = gate_ok(sid, sp)
        render.B = B; render.TIGHT = True
        v = dict(sp["voice"]); v["speed"] = v.get("speed", 1.0) * moso3d.SPEED
        render.set_voice(**v)
        for say, yt in pairs:
            render._YOMI[say] = yt
    beats, t = [], 0.25
    for ln in sp["lines"]:
        wav = f"{B}/{sid}/{ln['id']}.wav"
        if mute:
            d = ln.get("dur") or min(2.8, max(1.6, 1.0 + 0.1 * len("".join(ln["cap"]))))
            beats.append({"id": ln["id"], "t0": round(t, 3), "t1": round(t + d, 3), "voice": round(d, 3)})
            t += d + sp.get("gap", GAP)
            continue
        if en:
            tts_en(ln["say"], wav, sp["voice"])
        else:
            render.tts(ln["say"], wav)
        d = moso3d.voiced_len(wav)
        beats.append({"id": ln["id"], "t0": round(t, 3), "t1": round(t + d, 3), "voice": round(d, 3)})
        t += d + sp.get("gap", GAP)
    total = round(t + sp.get("tail", TAIL), 2)
    scene = {"title": sp["scene_title"], "parts": sp["parts"], "labels": sp.get("labels", {}), "params": sp.get("params", {}),
             "lines": [{k: ln[k] for k in ("id", "kind", "cap", "add", "fx", "at") if k in ln} | {"text": ln.get("say", "".join(ln["cap"]))} for ln in sp["lines"]]}
    os.makedirs(f"{KZ}/specs", exist_ok=True)
    json.dump(scene, open(f"{KZ}/specs/{sid}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"total": total, "estimated": 0, "beats": beats}, open(f"{KZ}/specs/{sid}_timeline.json", "w", encoding="utf-8"), indent=1)
    print(f"声 {len(beats)}行、全体 {total} 秒")


def read_wav(p):
    with wave.open(p) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return a, w.getframerate()


def sfx_track(sid, sp, tl, sr):
    """効果音：パーツが付く「ポン」、発射と大気圏の低い音"""
    total = tl["total"]; out = np.zeros(int(sr * total), np.float32)
    def add(t0, s):
        i = int(t0 * sr); n = min(len(s), len(out) - i)
        if n > 0: out[i:i + n] += s[:n]
    bt = {b["id"]: b for b in tl["beats"]}
    for ln in sp["lines"]:
        b = bt[ln["id"]]
        if ln.get("add"):
            d = .16; t = np.arange(int(sr * d)) / sr; f = 520 + 380 * (1 - np.exp(-t * 30))
            add(b["t0"] + POP_AT, np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 22) * .35)
        if ln.get("fx") in ("launchSpin", "reentry"):
            d = b["t1"] - b["t0"] + .3; n = int(sr * d); t = np.arange(n) / sr
            rng = np.random.default_rng(len(ln["id"]))
            noise = np.convolve(rng.standard_normal(n), np.ones(60) / 60, "same")
            env = np.minimum(1, t / .3) * np.minimum(1, (d - t) / .4)
            add(b["t0"], noise * env * (1.6 if ln["fx"] == "launchSpin" else 1.1))
        fx, at = ln.get("fx"), b["t0"] + ln.get("at", 0) * b["voice"]
        # 11/15 ルール：ボフン・ドーン（低い衝撃音）は全チャンネルで使わない。軽い高めの音だけにする
        def knock(t0, f, amp=.35, d=.07):
            t = np.arange(int(sr * d)) / sr
            add(t0, (np.sin(2 * np.pi * f * t) + .3 * np.sin(2 * np.pi * f * 2.7 * t)) * np.exp(-t * 60) * amp)
        if fx in ("stuck", "ball"):                                     # コツ（軽く当たる）
            knock(at, 900)
        if fx == "deflect":                                             # キン（はじく音）
            d = .35; t = np.arange(int(sr * d)) / sr
            add(at, (np.sin(2 * np.pi * 1850 * t) + .5 * np.sin(2 * np.pi * 2900 * t)) * np.exp(-t * 12) * .35)
        if fx == "fire":                                                # 的に当たる「コン」だけ
            knock(at + .55, 1200, .4)
    return out


def build(sid, bgm=None, gpu=False, jobs=2, audio_only=False):
    sp = load(sid)
    tl = json.load(open(f"{KZ}/specs/{sid}_timeline.json", encoding="utf-8"))
    page = sp.get("scene_page", "scene_fridge.html")
    n = int(round(tl["total"] * FPS))
    fr = f"{B}/{sid}/fr"; os.makedirs(fr, exist_ok=True)
    # ---- 絵（並列でコマを描く）。audio_only なら描いてあるコマを使い、音だけ作り直す
    env = dict(os.environ); env.setdefault("NODE_PATH", "/opt/npm-tools/node_modules")
    step = (n + jobs - 1) // jobs; procs = []
    for j in range(jobs):
        a, z = j * step, min(n, (j + 1) * step)
        args = ["node", "render.js", "--page", page, "--spec", f"specs/{sid}.json"] + (["--gpu"] if gpu else []) + ["range", str(a), str(z), os.path.abspath(fr)]
        procs.append(subprocess.Popen(args, cwd=KZ, env=env)) if not audio_only else None
    if any(p.wait() for p in procs):
        sys.exit("コマの書き出しに失敗")
    # ---- 音（声を時刻どおりに置き、効果音とBGMを重ねる）
    total = tl["total"]; vo = np.zeros(int(SR * total), np.float32)
    for b in tl["beats"]:
        if sp["voice"].get("engine") == "none": break
        a, sr = read_wav(f"{B}/{sid}/{b['id']}.wav"); a = a[:int(b["voice"] * sr)]
        i = int(b["t0"] * SR); vo[i:i + len(a)] += a[:len(vo) - i]
    sf = sfx_track(sid, sp, tl, SR) * moso3d.SE_GAIN
    mix = np.clip(vo + sf, -1, 1)
    wv = f"{B}/{sid}/voice_sfx.wav"
    with wave.open(wv, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    bgm = bgm or sp.get("bgm_file")
    out = f"output/{sid}.mp4"; os.makedirs("output", exist_ok=True)
    vol = sp.get("bgm_vol", .16) * moso3d.BGM_GAIN
    fc = (f"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0[v];"
          f"[2:a]aresample=48000,volume={vol:.3f},afade=t=out:st={total - 1.5:.2f}:d=1.5[m];"
          f"[v][m]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]") if bgm and os.path.exists(bgm) else \
         "[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{fr}/f%04d.jpg", "-i", wv]
    if bgm and os.path.exists(bgm): cmd += ["-stream_loop", "-1", "-i", bgm]
    cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]",
            "-vf", "scale=1080:1920:in_color_matrix=bt601:out_color_matrix=bt709:in_range=full:out_range=tv,format=yuv420p",
            "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-maxrate", "2500k", "-bufsize", "5000k",
            "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    print("書き出し:", out, f"{os.path.getsize(out) / 1e6:.1f}MB", "BGMあり" if bgm and os.path.exists(bgm) else "BGMなし")


if __name__ == "__main__":
    cmd, sid = sys.argv[1], sys.argv[2]
    opt = sys.argv[3:]
    get = lambda k, d=None: opt[opt.index(k) + 1] if k in opt else d
    if cmd == "voice":
        voice(sid)
    elif cmd == "build":
        build(sid, bgm=get("--bgm"), gpu="--gpu" in opt, jobs=int(get("--jobs", 2)), audio_only="--audio-only" in opt)
    else:
        sys.exit("voice / build")
