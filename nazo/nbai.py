# nbai.py — 「1回ごとにN倍」系の計算ショート（文字だけ・声なし）を、台本JSONから自動で作る
#   台本: nazo/shorts/nbai/<id>.json（template: jump / fold、post: タイトル・説明・タグ）
#   python nazo/nbai.py check <id>    … 数字と比較の照合だけ（NG があれば終了コード1）
#   python nazo/nbai.py build <id>    … 照合 → 3DCGを1コマずつ → 効果音とBGM → output/<id>.mp4 と投稿キット
#   python nazo/nbai.py next          … 予約表（queue.json）から、今日（JST）作る1本の id と公開日時を出す
#   予約表: nazo/shorts/nbai/queue.json  [{"id": ..., "publish_at": "2026-11-18T11:00:00Z"}, ...]
#   投稿済みの記録: nazo/manual/nbai/api_upload_<id>.txt（あれば作らない）
import datetime, json, os, shutil, subprocess, sys, wave
import numpy as np

KZ = "nazo/kaizo"
SD = "nazo/shorts/nbai"
MAN = "nazo/manual/nbai"
B = "build_nbai"
SR = 48000
BGM = "assets/bgm_nazo.m4a"          # tools/bgm.py で合成したオリジナル曲（権利の心配なし）
TPL = {"jump": {"page": "scene_jump.html", "verify": "verify.js"},
       "fold": {"page": "scene_fold.html", "verify": "verify_fold.js"}}


def load(sid):
    return json.load(open(f"{SD}/{sid}.json", encoding="utf-8"))


def node_env():
    e = dict(os.environ); e.setdefault("NODE_PATH", "/opt/npm-tools/node_modules"); return e


def stage(sid, sp):
    """描画用に specs/ へ置く（scene は specs/<id>.json を読む）"""
    os.makedirs(f"{KZ}/specs", exist_ok=True)
    json.dump(sp, open(f"{KZ}/specs/{sid}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def check(sid):
    sp = load(sid); t = TPL[sp["template"]]; stage(sid, sp)
    r = subprocess.run(["node", t["verify"], f"specs/{sid}.json"], cwd=KZ, env=node_env(), capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        sys.exit(f"照合で NG（{sid}）")
    for k in ("title", "desc", "tags"):
        if not sp.get("post", {}).get(k):
            sys.exit(f"post.{k} が空（{sid}）")
    return sp


def write_wav(p, a):
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(a, -1, 1) * 32767 * .9).astype(np.int16).tobytes())


def sfx_jump(sid, dur):
    """着地ごとに軽い「タッ」"""
    info = subprocess.run(["node", "render.js", "--page", TPL["jump"]["page"], "--spec", f"specs/{sid}.json", "info"],
                          cwd=KZ, env=node_env(), capture_output=True, text=True, check=True).stdout
    segs = json.loads([l for l in info.splitlines() if l.startswith("{")][-1])["segs"]
    # 11/15 ルール：ボフン・ドーン（低い衝撃音）は使わない。着地は軽い「タッ」だけ
    out = np.zeros(int(SR * dur)); rng = np.random.default_rng(1)
    for k, s in enumerate([s for s in segs if s["type"] == "contact"]):
        d = .06; t = np.arange(int(SR * d)) / SR
        nz = np.convolve(rng.standard_normal(len(t)), [1, -1], "same")   # 高めのかすれた音
        tap = (nz * .5 + np.sin(2 * np.pi * 1400 * t) * .3) * np.exp(-t * 70) * min(.6, .3 + .03 * k)
        i = int(s["t0"] * SR); out[i:i + len(tap)] += tap[:len(out) - i]
    return out


def sfx_fold(sid, dur):
    """1回折るごとに短い「カッ」、字幕が変わる節目に「チン」"""
    js = ("const {make}=require('./fold_calc.js'),spec=require('./specs/%s.json'),C=make(spec);const ticks=[],hits=[];let pn=null,pc=null;"
          "for(let i=0;i<=%d;i++){const t=i/30,n=C.nInt(t),c=C.captionAt(t).id;if(t>=C.CO&&pn!==null&&n!==pn)ticks.push({t,n});if(pc!==null&&c!==pc)hits.push({t,id:c});pn=n;pc=c}"
          "console.log(JSON.stringify({ticks,hits}))") % (sid, int(dur * 30))
    ev = json.loads(subprocess.run(["node", "-e", js], cwd=KZ, env=node_env(), capture_output=True, text=True, check=True).stdout)
    out = np.zeros(int(SR * dur)); rng = np.random.default_rng(3)
    def add(t0, s):
        i = int(t0 * SR); n = min(len(s), len(out) - i); out[i:i + n] += s[:n]
    for e in ev["ticks"]:
        d = .05; t = np.arange(int(SR * d)) / SR; f = 900 + e["n"] * 18
        add(e["t"], (np.sin(2 * np.pi * f * t) * .5 + rng.standard_normal(len(t)) * .25) * np.exp(-t * 90) * .32)
    for e in ev["hits"]:                       # 字幕の節目は「チン」（ボフン・ドーンは使わない 11/15）
        d = .4; t = np.arange(int(SR * d)) / SR
        add(e["t"], (np.sin(2 * np.pi * 1760 * t) + .4 * np.sin(2 * np.pi * 2640 * t)) * np.exp(-t * 9) * .22)
    return out


def kit(sid, sp):
    os.makedirs(MAN, exist_ok=True)
    p = sp["post"]; k = f"{MAN}/{sid}_upload.txt"
    open(k, "w", encoding="utf-8").write(f"【タイトル】\n{p['title']}\n\n【説明】\n{p['desc']}\n\n【タグ】\n{', '.join(p['tags'])}\n")
    return k


def build(sid, jobs=3):
    sp = check(sid); dur = sp["output"]["durationSeconds"]; fps = sp["output"]["fps"]; n = int(round(dur * fps))
    fr = os.path.abspath(f"{B}/{sid}/fr"); shutil.rmtree(fr, ignore_errors=True); os.makedirs(fr)
    step = (n + jobs - 1) // jobs; procs = []
    for j in range(jobs):
        a, z = j * step, min(n, (j + 1) * step)
        procs.append(subprocess.Popen(["node", "render.js", "--page", TPL[sp["template"]]["page"], "--spec", f"specs/{sid}.json", "range", str(a), str(z), fr],
                                      cwd=KZ, env=node_env()))
    if any(p.wait() for p in procs):
        sys.exit("コマの書き出しに失敗")
    se = (sfx_jump if sp["template"] == "jump" else sfx_fold)(sid, dur)
    wv = f"{B}/{sid}/sfx.wav"; write_wav(wv, se)
    out = f"output/{sid}.mp4"; os.makedirs("output", exist_ok=True)
    fc = (f"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0[s];[2:a]aresample=48000,volume=0.35,afade=t=in:d=0.3,afade=t=out:st={dur - 1.2:.2f}:d=1.2[m];"
          "[s][m]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", f"{fr}/f%04d.jpg", "-i", wv, "-stream_loop", "-1", "-i", BGM,
                    "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                    "-vf", "scale=1080:1920:in_color_matrix=bt601:out_color_matrix=bt709:in_range=full:out_range=tv,format=yuv420p",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-maxrate", "3000k", "-bufsize", "6000k",
                    "-c:a", "aac", "-b:a", "160k", "-t", f"{dur:.2f}", "-movflags", "+faststart", out], check=True)
    print("書き出し:", out, f"{os.path.getsize(out) / 1e6:.1f}MB", "キット:", kit(sid, sp))


def next_item(today=None):
    q = json.load(open(f"{SD}/queue.json", encoding="utf-8"))
    jst = datetime.timezone(datetime.timedelta(hours=9))
    today = today or datetime.datetime.now(jst).date().isoformat()
    for e in q:
        pa = datetime.datetime.fromisoformat(e["publish_at"].replace("Z", "+00:00")).astimezone(jst)
        if pa.date().isoformat() == today and not os.path.exists(f"{MAN}/api_upload_{e['id']}.txt"):
            return e
    return None


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "check":
        check(sys.argv[2])
    elif cmd == "build":
        build(sys.argv[2], jobs=int(os.environ.get("JOBS", 3)))
    elif cmd == "next":
        e = next_item(sys.argv[2] if len(sys.argv) > 2 else None)
        print(json.dumps(e) if e else "")
    else:
        sys.exit("check / build / next")
