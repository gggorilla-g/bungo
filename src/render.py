# render.py — M5(組版)+M6(音声)+M7(合成) 確定仕様:
#   静止画+1.2秒クロスフェードのみ / 話速0.92 / 朗読前後1.5秒の間 / 末尾に全文朗読(1枚固定・暗め)
import base64, json, os, re, subprocess
from weasyprint import HTML
from voicevox_core.blocking import Synthesizer, Onnxruntime, OpenJtalk, VoiceModelFile

A = "vv_assets"
ORT = "1.17.3"
STYLE = 3            # ずんだもん ノーマル
SPEED = 0.92         # 睡眠導入向けにわずかに遅く
PAUSE = 1.5          # 朗読の前後の間(秒)
B = "build"

_syn = None
def syn():
    global _syn
    if _syn is None:
        ort = Onnxruntime.load_once(
            filename=f"{A}/voicevox_onnxruntime-linux-x64-{ORT}/lib/libvoicevox_onnxruntime.so.{ORT}")
        _syn = Synthesizer(ort, OpenJtalk(f"{A}/open_jtalk_dic_utf_8-1.11"))
        with VoiceModelFile.open(f"{A}/0.vvm") as m:
            _syn.load_voice_model(m)
    return _syn

def tts(text, out_wav, ruby):
    for k, v in ruby.items():
        if len(k) >= 2:
            text = text.replace(k, v)
    text = re.sub(r'[「」『』]', '', text)
    aq = syn().create_audio_query(text, style_id=STYLE)
    aq.speed_scale = SPEED
    open(out_wav, "wb").write(syn().synthesis(aq, style_id=STYLE))

CSS_BASE = """
@page { size: 2400px 1350px; margin: 0; }
body { margin:0; width:2400px; height:1350px; position:relative;
       font-family:"Noto Serif CJK JP"; color:#fff; background:#17335e; }
.bg { position:absolute; inset:0; background:url(data:image/jpeg;base64,%s) center/cover; }
.scrim { position:absolute; inset:0; background:rgba(13,22,44,%s); }
.label { position:absolute; top:88px; left:125px; font-family:"Noto Sans CJK JP";
         font-size:33px; letter-spacing:.25em; color:#cdd9ec; }
.rule { position:absolute; top:150px; left:125px; width:200px; height:4px; background:#d9a520; }
h1 { position:absolute; left:125px; bottom:110px; margin:0; font-size:120px; font-weight:900;
     letter-spacing:.08em; text-shadow:0 4px 30px rgba(0,0,0,.6); }
.center { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; }
.quote { font-size:80px; line-height:2.1; margin:0 250px; }
.quote .q { color:#d9a520; font-family:"Noto Sans CJK JP"; font-size:38px;
            letter-spacing:.3em; display:block; margin-bottom:50px; }
.credit { position:absolute; bottom:60px; right:125px; font-family:"Noto Sans CJK JP";
          font-size:26px; color:#aebdd6; }
"""

def slide(body_html, out_png, image_path=None, scrim=0.45):
    img64 = base64.b64encode(open(image_path, "rb").read()).decode() if image_path else ""
    css = CSS_BASE % (img64, scrim)
    bg = '<div class="bg"></div><div class="scrim"></div>' if image_path else ''
    html = f'<html><head><meta charset="utf-8"><style>{css}</style></head><body>{bg}{body_html}</body></html>'
    HTML(string=html).write_pdf(f"{B}/_s.pdf")
    subprocess.run(["pdftoppm", "-png", "-r", "96", "-singlefile", f"{B}/_s.pdf",
                    out_png.replace(".png", "")], check=True)

def dur_of(wav):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav]))

def seg(png, wav, mp4, pad=0.8):
    d = dur_of(wav) + pad
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", png, "-i", wav,
        "-t", str(d), "-af", f"apad=pad_dur={pad}",
        "-vf", "scale=1920:1080,fps=24,format=yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", mp4], check=True)
    return d

def chunk_fulltext(text, size=400):
    """全文朗読用: 文境界で400字前後に分割"""
    sents = re.split(r'(?<=。)', text.replace("\n", ""))
    chunks, cur = [], ""
    for s in sents:
        if len(cur) + len(s) > size and cur:
            chunks.append(cur); cur = ""
        cur += s
    if cur:
        chunks.append(cur)
    return chunks

def build_video(kousei, work, genbun, ruby, images, out_mp4):
    os.makedirs(B, exist_ok=True)
    label = f'BUNGO — {work["author"]}『{work["title"]}』'
    parts, durs, ch_marks = [], [], []
    for i, s in enumerate(kousei["sections"]):
        png, wav, mp4 = f"{B}/s{i:02d}.png", f"{B}/s{i:02d}.wav", f"{B}/s{i:02d}.mp4"
        img = images.get(i)  # M4の結果(Noneならタイポグラフィ型)
        body = (f'<div class="label">{label}</div><div class="rule"></div>'
                f'<div class="center"><h1>{s["slide_heading"]}</h1></div>'
                f'<div class="credit">底本：青空文庫</div>')
        slide(body, png, img, scrim=0.45)
        tts(s["narration"], wav, ruby)
        # 最終セクション(新たな問い)の後は、全文朗読へ渡す前に1.5秒の間
        pad = 0.8 + PAUSE if i == len(kousei["sections"]) - 1 else 0.8
        # 見出しをそのままチャプター名に(動画ごとに個別化)
        ch_marks.append((s["slide_heading"], sum(durs) - 1.2 * len(durs)))
        durs.append(seg(png, wav, mp4, pad=pad))
        parts.append(mp4)

    # ---- 全文朗読パート: 1枚の暗い固定スライド(画面の光の変化を排除) ----
    body = (f'<div class="label">{label}</div><div class="rule"></div>'
            f'<div class="center"><h1 style="position:static;font-size:96px;">全文朗読</h1></div>'
            f'<div class="credit">底本：青空文庫　VOICEVOX:ずんだもん</div>')
    slide(body, f"{B}/full.png", None, scrim=0.8)
    wavs = []
    for j, ch in enumerate(chunk_fulltext(genbun)):
        w = f"{B}/f{j:03d}.wav"
        tts(ch, w, ruby)
        wavs.append(w)
    with open(f"{B}/fw.txt", "w") as f:
        f.write("\n".join(f"file '{os.path.basename(w)}'" for w in wavs))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", "fw.txt", "-af", "loudnorm=I=-16:TP=-1.5", f"full.wav"], check=True, cwd=B)
    ch_marks.append(("全文朗読", sum(durs) - 1.2 * len(durs)))
    durs.append(seg(f"{B}/full.png", f"{B}/full.wav", f"{B}/full.mp4", pad=2.0))
    parts.append(f"{B}/full.mp4")
    json.dump([[n, max(0, int(t))] for n, t in ch_marks],
              open(f"{B}/chapters.json", "w", encoding="utf-8"), ensure_ascii=False)

    # ---- 1.2秒クロスフェードで全結合 ----
    n = len(parts)
    ins = sum([["-i", p] for p in parts], [])
    fc, cur, off = [], "0:v", 0.0
    for i in range(1, n):
        off += dur_of(parts[i-1].replace(".mp4", ".wav")) + (0.8 if i < n else 2.0) - 1.2
        nxt = f"v{i}"
        fc.append(f"[{cur}][{i}:v]xfade=transition=fade:duration=1.2:offset={off:.3f}[{nxt}]")
        cur = nxt
    ac = "".join(f"[{i}:a]" for i in range(n)) + f"acrossfade=d=1.2[a]" if n == 2 else None
    # 音声はacrossfadeの多段が煩雑なためconcat(+末尾フェード)で簡潔に
    fc.append("".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1,afade=t=out:st=9999:d=0[a]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *ins,
        "-filter_complex", ";".join(fc), "-map", f"[{cur}]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac",
        out_mp4], check=True)

def build_thumbnail(kousei, work, image_path, out_png):
    t = kousei["thumbnail"]
    body = (f'<div class="label">BUNGO</div><div class="rule"></div>'
            f'<div class="center"><h1 style="position:static;font-size:180px;text-align:center;'
            f'line-height:1.4;">{t["main_copy"]}</h1></div>'
            f'<div class="credit" style="font-size:44px;color:#fff;">{t["sub_copy"]}</div>')
    slide(body, f"{B}/thumb_raw.png", image_path, scrim=0.5)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/thumb_raw.png",
        "-vf", "scale=1280:720", out_png], check=True)
