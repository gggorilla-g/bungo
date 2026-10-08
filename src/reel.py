# reel.py — Instagramリール用の縦型動画（1080x1920）を作る
#   本編の「問い」パート（冒頭の裏切り）だけを縦に組み直す。
#   音声は本編で読み検査を通した wav をそのまま使う＝新たな読み上げは発生しない（誤読リスクを増やさない）。
#   本編の build/ に残った素材（plan.json・*_p.wav・img*.jpg）を読むだけ。失敗しても本編には影響しない。
import base64, json, os, subprocess, wave

B = "build"
FPS = 24
W, H = 1080, 1920
MAX_SEC = 85          # リールの上限90秒に余裕を持たせる
END_SEC = 2.5         # 末尾の誘導カード（無音）

# Instagramの画面UI（上部ヘッダー、下部のキャプション、右のボタン列）に文字が隠れない位置に置く
CSS = """
@page { size: 1080px 1920px; margin: 0; }
body { margin:0; width:1080px; height:1920px; position:relative; overflow:hidden;
       font-family:"Noto Serif CJK JP"; color:#fff; background:#17335e; }
.bg { position:absolute; inset:0; background:url(data:image/jpeg;base64,%s) center/cover; }
.scrim { position:absolute; inset:0; background:rgba(13,22,44,%s); }
.brand { position:absolute; top:190px; left:90px; font-family:"Noto Sans CJK JP";
         font-size:34px; letter-spacing:.3em; color:#cdd9ec; }
.rule { position:absolute; top:250px; left:90px; width:140px; height:4px; background:#d9a520; }
.work { position:absolute; top:285px; left:90px; right:160px; font-family:"Noto Sans CJK JP";
        font-size:30px; color:#aebdd6; letter-spacing:.05em; }
.heading { position:absolute; top:520px; left:90px; right:160px; font-size:84px; font-weight:900;
           line-height:1.45; letter-spacing:.06em; text-shadow:0 4px 30px rgba(0,0,0,.6); }
.sub { position:absolute; top:1000px; left:90px; right:160px; font-family:"Noto Sans CJK JP";
       font-size:52px; line-height:1.85; color:#f0f4fa; text-shadow:0 3px 20px rgba(0,0,0,.85); }
.endbox { position:absolute; top:640px; left:90px; right:160px; text-align:center; }
.endbox .s { font-family:"Noto Sans CJK JP"; font-size:40px; color:#cdd9ec; letter-spacing:.1em; }
.endbox .b { font-size:150px; font-weight:900; letter-spacing:.12em; margin:40px 0; }
.credit { position:absolute; top:1480px; left:90px; right:160px; font-family:"Noto Sans CJK JP";
          font-size:24px; color:#aebdd6; }
"""

def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _slide(body, out_png, image_path=None, scrim=0.5):
    from weasyprint import HTML
    img64 = base64.b64encode(open(image_path, "rb").read()).decode() if image_path else ""
    bg = '<div class="bg"></div><div class="scrim"></div>' if image_path else ''
    html = (f'<html><head><meta charset="utf-8"><style>{CSS % (img64, scrim)}</style></head>'
            f'<body>{bg}{body}</body></html>')
    HTML(string=html).write_pdf(f"{B}/_r.pdf")
    subprocess.run(["pdftoppm", "-png", "-r", "96", "-singlefile", f"{B}/_r.pdf",
                    out_png[:-4]], check=True)

def _still(png, d, out_mp4):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS),
        "-i", png, "-frames:v", str(int(round(d * FPS))),
        "-vf", f"scale={W}:{H},format=yuv420p", "-c:v", "libx264", "-preset", "fast",
        "-tune", "stillimage", "-an", out_mp4], check=True)

def _silence(d, out_wav, like_wav):
    with wave.open(like_wav) as w:
        p = w.getparams()
    n = int(round(d * p.framerate))
    with wave.open(out_wav, "wb") as o:
        o.setparams(p); o.writeframes(b"\0" * n * p.sampwidth * p.nchannels)

def caption(kousei, work, credits):
    lines = [f'{work["author"]}『{work["title"]}』', ""]
    if kousei.get("logline"):
        lines += [kousei["logline"], ""]
    lines += ["全編（約10分）は YouTube「BUNGO」で。プロフィールのリンクから。", ""]
    tag_author = work["author"].replace(" ", "")
    lines += [f"#青空文庫 #名作解説 #日本文学 #読書 #{tag_author}", "",
              "音声: VOICEVOX:ずんだもん（合成音声）"]
    lines += [f"画像: {c}" for c in credits]
    lines.append("底本: 青空文庫")
    return "\n".join(lines)[:2200]   # Instagramのキャプション上限

def build(kousei, work, credits, out_dir="output"):
    plan = json.load(open(f"{B}/plan.json", encoding="utf-8"))
    toi = [p for p in plan if p["type"] == "toi"]
    if not toi:
        raise RuntimeError("問いパートが無い")
    use, total = [], 0.0
    for p in toi:                       # 文の途中では切らない
        if use and total + p["dur"] > MAX_SEC - END_SEC:
            break
        use.append(p); total += p["dur"]

    work_line = _esc(f'{work["author"]}『{work["title"]}』')
    names = []
    for k, p in enumerate(use):
        img = f'{B}/img{p["sec"]}.jpg'
        body = (f'<div class="brand">BUNGO</div><div class="rule"></div>'
                f'<div class="work">{work_line}</div>'
                f'<div class="heading">{_esc(p["heading"])}</div>'
                f'<div class="sub">{_esc(p["sent"])}</div>')
        n = f"r{k:03d}"
        _slide(body, f"{B}/{n}.png", img if os.path.exists(img) else None)
        _still(f"{B}/{n}.png", p["dur"], f"{B}/{n}.mp4")
        names.append((n, f'{p["name"]}_p.wav'))

    end = ('<div class="brand">BUNGO</div><div class="rule"></div>'
           f'<div class="work">{work_line}</div>'
           '<div class="endbox"><div class="s">続き（約10分）は YouTube</div>'
           '<div class="b">BUNGO</div><div class="s">10分でわかる名作</div></div>'
           '<div class="credit">底本：青空文庫　VOICEVOX:ずんだもん</div>')
    _slide(end, f"{B}/r_end.png", None)
    _still(f"{B}/r_end.png", END_SEC, f"{B}/r_end.mp4")
    _silence(END_SEC, f"{B}/r_end.wav", f'{B}/{use[0]["name"]}_p.wav')
    names.append(("r_end", "r_end.wav"))

    with open(f"{B}/rv.txt", "w") as f:
        f.write("\n".join(f"file '{n}.mp4'" for n, _ in names))
    with open(f"{B}/ra.txt", "w") as f:
        f.write("\n".join(f"file '{a}'" for _, a in names))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "rv.txt",
                    "-c", "copy", "reel_v.mp4"], check=True, cwd=B)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "ra.txt",
                    "-c", "copy", "reel_a.wav"], check=True, cwd=B)
    os.makedirs(out_dir, exist_ok=True)
    out = f"{out_dir}/reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/reel_v.mp4", "-i", f"{B}/reel_a.wav",
        "-map", "0:v", "-map", "1:a", "-c:v", "copy",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
        "-movflags", "+faststart", out], check=True)
    meta = {"work_id": work["work_id"], "title": work["title"], "author": work["author"],
            "caption": caption(kousei, work, credits), "seconds": round(total + END_SEC, 1)}
    json.dump(meta, open(f"{out_dir}/reel.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out
