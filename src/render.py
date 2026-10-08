# render.py — M5(組版)+M6(音声)+M7(合成)
#   v0.4: 全文朗読を廃止し、解説一本(約10分)に。
#   読み上げる全文は合成前に yomi.prepare() の読み検査を通す（通らなければ投稿しない）。
#   同期: 各スライドの映像と音声を同じ秒数(1/24秒単位)に揃え、映像は映像、音声は音声で
#         無劣化連結してから最後に1回だけ多重化＋音量正規化 → 字幕と声がズレない。
import base64, json, math, os, re, subprocess, wave
from weasyprint import HTML
from voicevox_core.blocking import Synthesizer, Onnxruntime, OpenJtalk, VoiceModelFile

A = "vv_assets"
ORT = "1.17.3"
STYLE = 3            # ずんだもん ノーマル
SPEED = 0.95         # 睡眠向け（B設定）
PITCH = -0.03        # 声を少し低く（キーキー対策）
INTONATION = 0.9     # 抑揚おさえめ
FPS = 24
SR = 24000          # VOICEVOX出力のサンプルレート
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

_YOMI = {}  # 原文 → 読み上げ用テキスト（yomi.prepareの結果）

def tts(text, out_wav):
    if text not in _YOMI:
        raise RuntimeError(f"読み検査を通っていない文を読もうとした: {text[:30]}")
    t = re.sub(r'[「」『』]', '', _YOMI[text])
    aq = syn().create_audio_query(t, style_id=STYLE)
    aq.speed_scale = SPEED
    aq.pitch_scale = PITCH
    aq.intonation_scale = INTONATION
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
.subtitle { position:absolute; left:180px; right:180px; bottom:150px;
            font-family:"Noto Sans CJK JP"; font-size:52px; line-height:1.9;
            color:#f0f4fa; text-align:center; text-shadow:0 3px 20px rgba(0,0,0,.85);
            letter-spacing:.02em; }
"""

def slide(body_html, out_png, image_path=None, scrim=0.45, subtitle=None):
    img64 = base64.b64encode(open(image_path, "rb").read()).decode() if image_path else ""
    css = CSS_BASE % (img64, scrim)
    bg = '<div class="bg"></div><div class="scrim"></div>' if image_path else ''
    sub = f'<div class="subtitle">{subtitle}</div>' if subtitle else ''
    html = f'<html><head><meta charset="utf-8"><style>{css}</style></head><body>{bg}{body_html}{sub}</body></html>'
    HTML(string=html).write_pdf(f"{B}/_s.pdf")
    subprocess.run(["pdftoppm", "-png", "-r", "96", "-singlefile", f"{B}/_s.pdf",
                    out_png.replace(".png", "")], check=True)

def _pad_wav(src, dst, total):
    """wavをtotal秒ちょうど(サンプル単位)まで無音で伸ばす"""
    with wave.open(src) as w:
        p = w.getparams(); frames = w.readframes(w.getnframes())
    n = int(round(total * p.framerate))
    need = n * p.sampwidth * p.nchannels - len(frames)
    frames = frames + b"\0" * max(0, need)
    with wave.open(dst, "wb") as o:
        o.setparams(p); o.writeframes(frames[:n * p.sampwidth * p.nchannels])

def _wav_len(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()

def seg(png, wav, name, pad=0.5):
    """1スライド分。映像(無音mp4)と音声(wav)を同じ長さd秒で作る。dは1/24秒の整数倍。"""
    d = math.ceil((_wav_len(wav) + pad) * FPS) / FPS
    _pad_wav(wav, f"{B}/{name}_p.wav", d)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS),
        "-i", png, "-frames:v", str(int(round(d * FPS))),
        "-vf", "scale=1920:1080,format=yuv420p", "-c:v", "libx264", "-preset", "fast",
        "-tune", "stillimage", "-an", f"{B}/{name}.mp4"], check=True)
    return d

def build_video(kousei, work, genbun, ruby, images, out_mp4, llm):
    import yomi
    os.makedirs(B, exist_ok=True)
    label = f'BUNGO — {work["author"]}『{work["title"]}』'
    PART_LABEL = {"toi": "問い", "yoyaku": "読み解き", "shin_toi": "問い"}
    PART_INTRO = {"shin_toi": "最後に、もう一つの問いを。"}

    # ---- 読み上げる文を先に全部確定させる ----
    logline = kousei.get("logline", "")
    title_narr = work["title"] + "。" + work["author"] + "。" + logline
    plan = []  # (セクション番号, 文)
    for i, s in enumerate(kousei["sections"]):
        intro = PART_INTRO.get(s["type"])
        first_of_part = (i == 0) or (kousei["sections"][i-1]["type"] != s["type"])
        narr = (intro + s["narration"]) if (intro and first_of_part) else s["narration"]
        for sent in yomi.split_sentences(narr):
            plan.append((i, sent))
    _YOMI.clear()
    _YOMI.update(yomi.prepare([title_narr] + [s for _, s in plan], work, ruby, llm))

    names, durs, ch_marks = [], [], []
    # ---- タイトルカード ----
    tcard = (f'<div class="label">{label}</div><div class="rule"></div>'
             f'<div class="center"><div><div style="font-size:56px;color:#8fa8cf;'
             f'text-align:center;margin-bottom:30px;letter-spacing:.2em;">10分でわかる名作</div>'
             f'<h1 style="position:static;font-size:110px;text-align:center;">'
             f'{work["title"]}</h1>'
             f'<div style="font-size:44px;color:#cdd9ec;text-align:center;margin-top:30px;">'
             f'{work["author"]}</div></div></div>'
             f'<div class="credit">底本：青空文庫</div>')
    slide(tcard, f"{B}/title.png", None, scrim=0.5)
    tts(title_narr, f"{B}/title.wav")
    durs.append(seg(f"{B}/title.png", f"{B}/title.wav", "title", pad=0.8)); names.append("title")

    last_sec = -1
    for k, (i, sent) in enumerate(plan):
        s = kousei["sections"][i]
        if i != last_sec:
            ch_marks.append((s["slide_heading"], sum(durs)))  # 見出し=チャプター（ズレなし）
            last_sec = i
        plabel = PART_LABEL.get(s["type"], "")
        badge = (f'<div style="position:absolute;top:88px;right:125px;'
                 f'font-family:\'Noto Sans CJK JP\';font-size:30px;color:#d9a520;'
                 f'letter-spacing:.2em;">{plabel}</div>') if plabel else ""
        body = (f'<div class="label">{label}</div><div class="rule"></div>{badge}'
                f'<div class="center"><h1 style="bottom:auto;top:280px;">{s["slide_heading"]}</h1></div>'
                f'<div class="credit">底本：青空文庫　VOICEVOX:ずんだもん</div>')
        n = f"s{k:03d}"
        slide(body, f"{B}/{n}.png", images.get(i), scrim=0.5, subtitle=sent)
        tts(sent, f"{B}/{n}.wav")
        is_sec_end = (k == len(plan) - 1) or (plan[k+1][0] != i)
        durs.append(seg(f"{B}/{n}.png", f"{B}/{n}.wav", n, pad=1.2 if is_sec_end else 0.5))
        names.append(n)

    json.dump([[h, int(t)] for h, t in ch_marks],
              open(f"{B}/chapters.json", "w", encoding="utf-8"), ensure_ascii=False)
    # リール(reel.py)用: 各文がどのスライド・音声・秒数か
    json.dump([{"sec": i, "type": kousei["sections"][i]["type"],
                "heading": kousei["sections"][i]["slide_heading"], "sent": sent,
                "name": f"s{k:03d}", "dur": durs[k + 1]} for k, (i, sent) in enumerate(plan)],
              open(f"{B}/plan.json", "w", encoding="utf-8"), ensure_ascii=False)

    # ---- 映像・音声をそれぞれ無劣化連結 → 1回だけ多重化＋音量正規化 ----
    with open(f"{B}/v.txt", "w") as f:
        f.write("\n".join(f"file '{n}.mp4'" for n in names))
    with open(f"{B}/a.txt", "w") as f:
        f.write("\n".join(f"file '{n}_p.wav'" for n in names))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "v.txt",
                    "-c", "copy", "all_v.mp4"], check=True, cwd=B)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "a.txt",
                    "-c", "copy", "all_a.wav"], check=True, cwd=B)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/all_v.mp4", "-i", f"{B}/all_a.wav",
        "-map", "0:v", "-map", "1:a", "-c:v", "copy",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", out_mp4], check=True)
    return sum(durs)

def build_thumbnail(kousei, work, image_path, out_png):
    t = kousei["thumbnail"]
    body = (f'<div class="label">BUNGO</div><div class="rule"></div>'
            f'<div class="center"><h1 style="position:static;font-size:180px;text-align:center;'
            f'line-height:1.4;">{t["main_copy"]}</h1></div>'
            f'<div class="credit" style="font-size:44px;color:#fff;">{t["sub_copy"]}</div>')
    slide(body, f"{B}/thumb_raw.png", image_path, scrim=0.5)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/thumb_raw.png",
        "-vf", "scale=1280:720", out_png], check=True)
