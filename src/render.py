# render.py — M5(組版)+M6(音声)+M7(合成)
#   v0.4: 全文朗読を廃止し、解説一本(約10分)に。
#   読み上げる全文は合成前に yomi.prepare() の読み検査を通す（通らなければ投稿しない）。
#   同期: 各スライドの映像と音声を同じ秒数(1/24秒単位)に揃え、映像は映像、音声は音声で
#         無劣化連結してから最後に1回だけ多重化＋音量正規化 → 字幕と声がズレない。
import base64, json, math, os, re, subprocess, sys, wave
# 動き・効果音・案内役の部品（nazo/ に置いている共通部品）を、どのチャンネルからも使えるように
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nazo"))
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
VVM = "0.vvm"
def set_voice(vvm, style, speed=None, pitch=None, intonation=None):
    """チャンネルごとの声（VOICEVOXのモデルファイルと話者スタイルID）"""
    global VVM, STYLE, SPEED, PITCH, INTONATION, _syn
    VVM, STYLE = vvm, style
    if speed is not None: SPEED = speed
    if pitch is not None: PITCH = pitch
    if intonation is not None: INTONATION = intonation
    _syn = None

def syn():
    global _syn
    if _syn is None:
        ort = Onnxruntime.load_once(
            filename=f"{A}/voicevox_onnxruntime-linux-x64-{ORT}/lib/libvoicevox_onnxruntime.so.{ORT}")
        _syn = Synthesizer(ort, OpenJtalk(f"{A}/open_jtalk_dic_utf_8-1.11"))
        with VoiceModelFile.open(f"{A}/{VVM}") as m:
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

def slide(body_html, out_png, image_path=None, scrim=0.45, subtitle=None, css_extra="", transparent=False):
    img64 = base64.b64encode(open(image_path, "rb").read()).decode() if image_path else ""
    css = CSS_BASE % (img64, scrim) + css_extra.replace("{scrim}", str(scrim))
    if transparent:
        css += " body { background:transparent !important; } "
    bg = '<div class="bg"></div><div class="scrim"></div>' if image_path else ''
    sub = f'<div class="subtitle">{subtitle}</div>' if subtitle else ''
    html = f'<html><head><meta charset="utf-8"><style>{css}</style></head><body>{bg}{body_html}{sub}</body></html>'
    HTML(string=html).write_pdf(f"{B}/_s.pdf")
    if transparent:
        subprocess.run(["pdftocairo", "-png", "-transp", "-r", "96", "-singlefile", f"{B}/_s.pdf",
                        out_png.replace(".png", "")], check=True)
        return
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

def _se(name, events):
    if events:
        import se
        se.mix(f"{B}/{name}_p.wav", events)


PAN_MODE = "pan"   # "pan"＝1文ごとに引き／寄りとパンを切り替える（謎・BUNGO）、"fix"＝動かさない（怪談）


def pan_seg(img_path, overlay_png, wav, name, k, pad=0.5, se_events=None):
    """静止画をゆっくりパンする1カット（ffmpegだけで作るので軽い）。
    k（カット番号）で、引き／寄り と パンの向きを交互に変えて、カットにリズムを出す"""
    import motion
    d = math.ceil((_wav_len(wav) + pad) * FPS) / FPS
    _pad_wav(wav, f"{B}/{name}_p.wav", d)
    _se(name, se_events)
    close = (k % 2 == 1) and PAN_MODE != "fix"
    scale = 1.45 if close else (1.0 if PAN_MODE == "fix" else 1.12)
    canvas, _ = motion.stage(img_path, scale=scale)
    canvas.save(f"{B}/{name}_bg.jpg", quality=92)
    cw, ch = canvas.size
    mx, my = cw - 1920, ch - 1080
    span = mx * (0.5 if close else 1.0)                   # 寄りは動きを半分に
    x0 = (mx - span) / 2 if (k // 2) % 2 == 0 else (mx + span) / 2
    x1 = (mx + span) / 2 if (k // 2) % 2 == 0 else (mx - span) / 2
    y = my * (0.42 if close else 0.5)
    if PAN_MODE == "fix":                 # 同じ画像が続いても絵が動かず、字幕だけが変わる（カットに見えない）
        x0 = x1 = mx / 2; y = my / 2
    n = int(round(d * FPS))
    fc = (f"[0:v]crop=1920:1080:x='{x0:.1f}+({x1 - x0:.1f})*t/{d:.3f}':y={y:.1f},setsar=1[b];"
          f"[1:v]scale=1920:1080[o];[b][o]overlay=0:0,format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", f"{B}/{name}_bg.jpg",
                    "-loop", "1", "-framerate", str(FPS), "-i", overlay_png, "-filter_complex", fc,
                    "-map", "[v]", "-frames:v", str(n), "-c:v", "libx264", "-preset", "fast", "-crf", "21",
                    "-an", f"{B}/{name}.mp4"], check=True)
    return d


def host_face(sentence):
    """ホー博士の表情：問いかけ・念押しはジト目、お願いはうるうる"""
    if any(w in sentence for w in ("登録", "待っていて", "お願い", "うれしい")):
        return "uruuru"
    if any(w in sentence for w in ("なぜ", "本当", "見逃さん", "どの説")):
        return "jito"
    return None


def beat_se(spec):
    """ビート（図解）が出るときの効果音。種類ごとに、出るタイミングに合わせて小さく鳴らす"""
    import se
    t = spec.get("type", "photo")
    if t == "year":
        return [("tick", 0.05, 1), ("tick_lo", 0.5, 0.8), ("ding", 1.0, 1)]
    if t == "map":
        return [("whoosh_s", 0.0, 1), ("pop_lo", 1.3, 1), ("pop_hi", 1.7, 0.9)]
    if t == "size":
        return [("whoosh_s", 0.15, 1), ("tick", 0.95, 1)]
    if t == "words":
        n = len(str(spec.get("text", "")).split("\n"))
        return [(se.pick("words"), 0.05 + i * 0.25, 1) for i in range(n)]
    if t == "photo" and spec.get("zoom"):
        return [("whoosh_s", 0.0, 0.9)]
    return [(se.pick("cut"), 0.0, 0.8)]


def motion_seg(overlay_png, wav, name, beat, t_offset, pad=0.5, talk=True, face=None, se_events=None):
    """動く1文。映像は motion.render_segment、音声は seg と同じく d 秒に合わせる"""
    import motion
    d = math.ceil((_wav_len(wav) + pad) * FPS) / FPS
    _pad_wav(wav, f"{B}/{name}_p.wav", d)
    _se(name, se_events)
    motion.render_segment(f"{B}/{name}.mp4", d, f"{B}/{name}_p.wav", beat, overlay_png,
                          talk_owl=talk, t_offset=t_offset, face=face)
    return d


BUNGO_CSS = """
.rule { display:none; }
.label { background:rgba(13,27,51,.82); padding:8px 20px; color:#e8eef8; }
h1 { background:#0d1b33; color:#ffffff; padding:.12em .45em .16em; text-shadow:none !important;
     border-bottom:8px solid #d9a520; }
.badge { display:none !important; }
.credit { background:rgba(13,27,51,.78); padding:6px 16px; color:#dfe7f3; }
.subtitle { background:rgba(13,27,51,.80); padding:14px 36px; bottom:120px; }
"""


def bungo_brand(work):
    """BUNGOの見た目と言い回し（既定値）。他チャンネルは同じ形のdictを渡す。"""
    label = f'BUNGO — {work["author"]}『{work["title"]}』'
    return {
        "label": label,
        "part_label": {"toi": "問い", "yoyaku": "読み解き", "shin_toi": "問い"},
        "part_intro": {"shin_toi": "最後に、もう一つの問いを。"},
        "title_narr": lambda k: work["title"] + "。" + work["author"] + "。" + k.get("logline", ""),
        "title_card": (f'<div class="label">{label}</div><div class="rule"></div>'
             f'<div class="center"><div><div style="font-size:56px;color:#8fa8cf;'
             f'text-align:center;margin-bottom:30px;letter-spacing:.2em;">10分でわかる名作</div>'
             f'<h1 style="position:static;font-size:110px;text-align:center;">'
             f'{work["title"]}</h1>'
             f'<div style="font-size:44px;color:#cdd9ec;text-align:center;margin-top:30px;">'
             f'{work["author"]}</div></div></div>'
             f'<div class="credit">底本：青空文庫</div>'),
        "title_card_motion": (f'<div class="label">BUNGO — 10分でわかる名作</div>'
             f'<div class="center"><div style="text-align:center;">'
             f'<div style="display:inline-block;background:#d9a520;color:#0d1b33;font-family:\'Noto Sans CJK JP\';'
             f'font-weight:900;font-size:54px;padding:14px 36px;margin-bottom:34px;">{work["author"]}</div><br>'
             f'<h1 style="position:static;display:inline-block;font-size:140px;">{work["title"]}</h1>'
             f'</div></div>'),
        "credit": "底本：青空文庫　VOICEVOX:ずんだもん",
        "accent": "#d9a520",
        "css": BUNGO_CSS,
        "thumb_label": "BUNGO",
        "bgm": "assets/bgm_bungo.m4a",
        "motion": True,           # つかみ・静止画のパン・章カード・効果音（滞在時間のため）
        "motion_first": False,    # 図解のビートは使わない（文学は画像＋文字で見せる）
        "card_style": {"bg": (16, 30, 56), "grid": (30, 50, 84), "grid2": (40, 64, 104),
                       "card": (246, 240, 226), "edge": (13, 27, 51), "shadow": (217, 165, 32), "ink": (13, 27, 51)},
    }


def build_video(kousei, work, genbun, ruby, images, out_mp4, llm, brand=None):
    import yomi
    os.makedirs(B, exist_ok=True)
    br = brand or bungo_brand(work)
    if br.get("voice"):
        set_voice(**br["voice"])
    global PAN_MODE
    PAN_MODE = br.get("pan_mode", "pan")
    label = br["label"]
    PART_LABEL = br["part_label"]
    PART_INTRO = br["part_intro"]
    css = br["css"]

    # ---- 読み上げる文を先に全部確定させる ----
    title_narr = br["title_narr"](kousei)
    plan = []  # (セクション番号, 文)
    for i, s in enumerate(kousei["sections"]):
        intro = PART_INTRO.get(s["type"])
        first_of_part = (i == 0) or (kousei["sections"][i-1]["type"] != s["type"])
        narr = (intro + s["narration"]) if (intro and first_of_part) else s["narration"]
        for sent in yomi.split_sentences(narr):
            plan.append((i, sent))
    host_sents = yomi.split_sentences(kousei["host_intro"]) if (br.get("motion") and kousei.get("host_intro")) else []
    hook_items = kousei.get("hook", []) if br.get("motion") else []
    outro_text = kousei.get("host_outro") or br.get("host_outro", "")
    outro_sents = yomi.split_sentences(outro_text) if (br.get("motion") and outro_text) else []
    _YOMI.clear()
    _YOMI.update(yomi.prepare([h["say"] for h in hook_items] + [title_narr] + [s for _, s in plan]
                              + host_sents + outro_sents, work, ruby, llm))

    names, durs, ch_marks = [], [], []
    # ---- タイトルカード ----
    # images["pool"] があれば、すべてのカット（タイトル含む）に画像を敷く。
    # 文の数に対して画像を均等に割り当て、同じ画像は連続する数カットで使う（チカチカさせない）
    pool = images.get("pool") or []
    sec_list = images.get("sec_list") or {}
    cur = {}
    def pick(k, i):
        # 1) 台本の指定: セクション内で、"at" の語を含む文から次の画像に切り替える
        if i in sec_list:
            lst = sec_list[i]
            if cur.get("sec") != i:
                cur.update(sec=i, img=lst[0][1])
            for at, path in lst[1:]:
                if at and at in plan[k][1]:
                    cur["img"] = path
            return cur["img"]
        # 2) 記事の画像を均等に割り当て
        if pool:
            return pool[min(len(pool) - 1, k * len(pool) // max(1, len(plan)))]
        return images.get(i)
    title_img = images.get("title_image") or (pool[0] if pool else images.get(0))
    use_motion = bool(br.get("motion"))
    bgm_switch_at = None
    # つかみ（冒頭の数秒）：題材のいちばん引っかかる事実を、短い文で畳みかける
    if use_motion and hook_items:
        import motion
        for j, h in enumerate(hook_items):
            hn = f"k{j:02d}"
            tts(h["say"], f"{B}/{hn}.wav")
            img = images.get("hook_files", {}).get(h.get("file")) or title_img
            hb_ = motion.Beat({"type": "hook", "text": h.get("text", h["say"])}, img)
            ev = [("whoosh_l", 0.0, 1), ("thud", 0.3, 1)] if j == 0 else [("thud", 0.0, 0.9), ("tick", 0.05, 0.8)]
            if j == len(hook_items) - 1:
                ev.append(("shimmer", 0.2, 0.8))
            slide("", f"{B}/{hn}_ov.png", None, transparent=True, css_extra=css)
            durs.append(motion_seg(f"{B}/{hn}_ov.png", f"{B}/{hn}.wav", hn, hb_, 0.0,
                                   pad=0.6 if j == len(hook_items) - 1 else 0.25, se_events=ev))
            names.append(hn)
    tts(title_narr, f"{B}/title.wav")
    if use_motion:
        import motion
        slide(br.get("title_card_motion", br["title_card"]), f"{B}/title_ov.png", None,
              css_extra=css, transparent=True)
        tb = motion.Beat({"type": "photo"}, title_img)
        durs.append(motion_seg(f"{B}/title_ov.png", f"{B}/title.wav", "title", tb, 0.0, pad=0.8,
                               se_events=[("whoosh_l", 0.0, 1), ("thud", 0.45, 1)]))
    else:
        slide(br["title_card"], f"{B}/title.png", title_img,
              scrim=0.6 if title_img else 0.5, css_extra=css)
        durs.append(seg(f"{B}/title.png", f"{B}/title.wav", "title", pad=0.8))
    names.append("title")
    # タイトルの直後に、案内役のピンショットで名乗って本題へ（つかみ→タイトル→「ホー博士じゃ」）
    if use_motion and host_sents:
        import motion
        bgm_switch_at = sum(durs)
        hb = motion.Beat({"type": "host", "name": br.get("host_name", "ホー博士"),
                          "role": br.get("host_role", "")}, title_img)
        ht = 0.0
        for j, hs in enumerate(host_sents):
            hn = f"h{j:02d}"
            tts(hs, f"{B}/{hn}.wav")
            slide("", f"{B}/{hn}_ov.png", None, subtitle=hs, transparent=True,
                  css_extra=css + " .subtitle { left:1180px !important; right:70px !important; } ")
            fc = host_face(hs)
            ev = [("pop_mid", 0.0, 1), ("shimmer", 0.15, 0.9)] if j == 0 else []
            if fc == "uruuru": ev.append(("shimmer", 0.1, 0.8))
            if fc == "jito": ev.append(("tick_lo", 0.05, 0.9))
            hd = motion_seg(f"{B}/{hn}_ov.png", f"{B}/{hn}.wav", hn, hb, ht,
                            pad=0.9 if j == len(host_sents) - 1 else 0.4, face=fc, se_events=ev)
            ht += hd
            durs.append(hd); names.append(hn)
    # 動かすセクション：台本に "motion" があるセクション（なければ最初のセクションだけ）
    motion_secs = {i for i, s_ in enumerate(kousei["sections"]) if "motion" in s_}
    if use_motion and not motion_secs and br.get("motion_first", True):
        motion_secs = {0}
    beat_state = {}
    pan_state = {}

    last_sec = -1
    bgm_marks = [(0.0, "main")]          # 展開ごとの曲の切り替え（台本のセクションに "bgm": 曲の名前）
    for k, (i, sent) in enumerate(plan):
        s = kousei["sections"][i]
        first_of_sec = (i != last_sec)
        if i != last_sec:
            key = s.get("bgm", "main")
            if key != bgm_marks[-1][1]:
                bgm_marks.append((sum(durs), key))
            ch_marks.append((s["slide_heading"], sum(durs)))  # 見出し=チャプター（ズレなし）
            last_sec = i
            if use_motion and i > 0:
                import motion
                cn = f"c{i:02d}"
                cd = round(br.get("card_dur", 1.6) * FPS) / FPS
                import se
                motion.chime_wav(f"{B}/{cn}_p.wav", cd, silent=True)
                if br.get("card_se"):          # チャンネル固有の章の音（怪談は鐘の「ぼーん」）
                    se.mix(f"{B}/{cn}_p.wav", br["card_se"])
                else:
                    a, b2 = se.pick("card")
                    se.mix(f"{B}/{cn}_p.wav", [(b2, 0.0, 1), (a, 0.08, 1)])
                motion.chapter_card(s["slide_heading"], f"{B}/{cn}.mp4", cd, style=br.get("card_style"))
                durs.append(cd); names.append(cn)
        plabel = PART_LABEL.get(s["type"], "")
        badge = (f'<div class="badge" style="position:absolute;top:88px;right:125px;'
                 f'font-family:\'Noto Sans CJK JP\';font-size:30px;color:{br["accent"]};'
                 f'letter-spacing:.2em;">{plabel}</div>') if plabel else ""
        body = (f'<div class="label">{label}</div><div class="rule"></div>{badge}'
                f'<h1 style="bottom:auto;top:185px;font-size:{br.get("heading_px", 64)}px;'
                f'text-shadow:0 2px 16px rgba(0,0,0,.8);">{s["slide_heading"]}</h1>'
                f'<div class="credit">{br["credit"]}</div>')
        n = f"s{k:03d}"
        tts(sent, f"{B}/{n}.wav")
        is_sec_end = (k == len(plan) - 1) or (plan[k+1][0] != i)
        if use_motion and i in motion_secs:
            import motion
            img = pick(k, i)
            # この文で切り替わるビート（"at" の語を含む文から）。なければ今のビートを続ける
            new = None
            if beat_state.get("sec") != i:
                beat_state.update(sec=i, beat=None, t=0.0, img=None)
            for b in s.get("motion", []):
                if b.get("at") and b["at"] in sent:
                    new = b
            if new is None and (beat_state["beat"] is None or img != beat_state["img"]):
                new = {"type": "photo"}
            if new is not None:
                spec = dict(new)
                if spec.get("file") and images.get("motion_files", {}).get(spec["file"]):
                    spec["path"] = images["motion_files"][spec["file"]]
                beat_state.update(beat=motion.Beat(spec, img), t=0.0, img=img, spec_at=new.get("at"))
            ev = beat_se(spec) if new is not None else []
            if first_of_sec:
                ev.append(("pop_lo", 0.02, 0.8))          # 見出しの箱が出る
            slide(body, f"{B}/{n}_ov.png", None, subtitle=sent, transparent=True, css_extra=css)
            d = motion_seg(f"{B}/{n}_ov.png", f"{B}/{n}.wav", n, beat_state["beat"], beat_state["t"],
                           pad=1.2 if is_sec_end else 0.5, se_events=ev)
            beat_state["t"] += d
            durs.append(d)
            names.append(n)
            continue
        elif use_motion and pick(k, i):
            # 本編：静止画もゆっくりパンし、1文ごとに引き／寄りを切り替える
            slide(body, f"{B}/{n}_ov.png", None, subtitle=sent, transparent=True, css_extra=css)
            import se
            img = pick(k, i)
            ev = []
            if img != pan_state.get("img"):
                ev.append((se.pick("cut"), 0.0, 0.7))
            if first_of_sec:
                ev.append(("pop_lo", 0.02, 0.8))
            if br.get("keyword_se"):      # 本文の言葉に合わせた音（怪談の戸を叩く音など）
                ev += br["keyword_se"](sent)
            pan_state["img"] = img
            durs.append(pan_seg(img, f"{B}/{n}_ov.png", f"{B}/{n}.wav", n, k,
                                pad=1.2 if is_sec_end else 0.5, se_events=ev))
        else:
            slide(body, f"{B}/{n}.png", pick(k, i), scrim=br.get("scrim", 0.5), subtitle=sent, css_extra=css)
            durs.append(seg(f"{B}/{n}.png", f"{B}/{n}.wav", n, pad=1.2 if is_sec_end else 0.5))
        names.append(n)

    if bgm_marks[-1][1] != "main":
        bgm_marks.append((sum(durs), "main"))   # 締めは地の曲に戻す
    # 最後：案内役のピンショットで締め（感想の問いかけ・次回・チャンネル登録）
    if use_motion and outro_sents:
        import motion
        ob = motion.Beat({"type": "host", "name": br.get("host_name", "ホー博士"),
                          "role": br.get("host_role", "")}, pick(len(plan) - 1, plan[-1][0]) if plan else title_img)
        ch_marks.append((br.get("outro_heading", "おわりに"), sum(durs)))
        ot = 0.0
        for j, os_ in enumerate(outro_sents):
            on = f"o{j:02d}"
            tts(os_, f"{B}/{on}.wav")
            slide("", f"{B}/{on}_ov.png", None, subtitle=os_, transparent=True,
                  css_extra=css + " .subtitle { left:1180px !important; right:70px !important; } ")
            fc = host_face(os_)
            ev = [("whoosh_s", 0.0, 1), ("pop_hi", 0.2, 1)] if j == 0 else []
            if fc == "uruuru": ev.append(("shimmer", 0.1, 0.8))
            if fc == "jito": ev.append(("tick_lo", 0.05, 0.9))
            if j == len(outro_sents) - 1: ev.append(("chime_b", 1.0, 0.9))
            od = motion_seg(f"{B}/{on}_ov.png", f"{B}/{on}.wav", on, ob, ot,
                            pad=2.0 if j == len(outro_sents) - 1 else 0.4, face=fc, se_events=ev)
            ot += od
            durs.append(od); names.append(on)

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
    bgm = br.get("bgm")
    if bgm and os.path.exists(bgm):
        total = sum(durs)
        bgm = _bgm_loop(bgm, total)
        hook_bgm = br.get("bgm_hook")
        if hook_bgm and os.path.exists(hook_bgm) and bgm_switch_at:
            # 冒頭（つかみ〜概要）はミステリアスな曲、ホー博士の名乗りで本編の曲へ
            hb_loop = _bgm_loop(hook_bgm, bgm_switch_at + 5, dst_name="bgm_hook_loop.wav")
            bgm = _bgm_two(bgm, hb_loop, total, bgm_switch_at)
        tracks = dict(br.get("bgm_tracks") or {})
        if tracks and len(bgm_marks) > 1:
            tracks.setdefault("main", br["bgm"])
            bgm = _bgm_timeline(tracks, total, bgm_marks)
        # 声の区間だけBGMを下げる。文の切れ目程度の短い無音では戻さず、下げ幅も小さく、ゆっくり動かす
        bgm = _bgm_duck(bgm, f"{B}/all_a.wav", total, br.get("bgm_volume", 0.09),
                        duck_db=br.get("bgm_duck_db", -5.0))
        fc = ("[1:a]aresample=48000[v];[2:a]aresample=48000[m];"
              "[v][m]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11[a]")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/all_v.mp4", "-i", f"{B}/all_a.wav",
            "-i", bgm, "-filter_complex", fc,
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-ar", "48000", "-t", f"{total:.3f}", out_mp4], check=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/all_v.mp4", "-i", f"{B}/all_a.wav",
            "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
            "-ar", "48000", out_mp4], check=True)
    return sum(durs)

def _bgm_loop(src, total, xfade=4.0, dst_name="bgm_loop.wav"):
    """BGMを動画の尺までつなぐ。継ぎ目は数秒のクロスフェードにして、曲の頭に戻る違和感を消す。
    曲自体は加工しない（音量・つなぎのみ）"""
    import numpy as np
    sr = 48000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                         check=True, capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    n_x, need = int(xfade * sr), int((total + 1) * sr)
    out = x.copy()
    ramp = np.linspace(0, 1, n_x)
    while len(out) < need:
        out[-n_x:] = out[-n_x:] * (1 - ramp) + x[:n_x] * ramp
        out = np.concatenate([out, x[n_x:]])
    dst = f"{B}/{dst_name}"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-", dst],
                   input=np.clip(out[:need], -32768, 32767).astype(np.int16).tobytes(), check=True)
    return dst



def _bgm_two(main_wav, hook_wav, total, t_switch, xfade=2.5):
    """冒頭（〜t_switch）は hook の曲、そこから本編の曲へクロスフェードでつなぐ。
    2曲の音量差が出ないよう、それぞれの平均音量をそろえてからつなぐ"""
    import numpy as np
    sr = 48000
    def load(p):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                             check=True, capture_output=True).stdout
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    m, h = load(main_wav), load(hook_wav)
    n = int((total + 1) * sr)
    m = np.pad(m, (0, max(0, n - len(m))))[:n]; h = np.pad(h, (0, max(0, n - len(h))))[:n]
    rms = lambda x: float(np.sqrt((x[: int(60 * sr)] ** 2).mean()) + 1e-9)
    h = h * (rms(m) / rms(h))
    t = np.arange(n) / sr
    g = np.clip((t - (t_switch - xfade / 2)) / xfade, 0, 1)      # 0=冒頭の曲, 1=本編の曲
    y = h * np.cos(g * np.pi / 2) + m * np.sin(g * np.pi / 2)
    dst = f"{B}/bgm_two.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-", dst],
                   input=(np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes(), check=True)
    return dst


def _bgm_timeline(tracks, total, marks, xfade=3.0):
    """展開ごとに曲を切り替える。marks = [(開始秒, 曲の名前), ...]。
    切り替えのたびにその曲を頭から流し、前後は xfade 秒の等パワーのクロスフェード。
    曲ごとの音量差が出ないよう、平均音量を地の曲（main）にそろえる"""
    import numpy as np
    sr = 48000
    def load(p):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                             check=True, capture_output=True).stdout
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    n = int((total + 1) * sr)
    rms = lambda x: float(np.sqrt((x ** 2).mean()) + 1e-9)
    ref = None
    y = np.zeros(n, dtype=np.float32)
    bounds = [m[0] for m in marks] + [total + 1]
    for idx, (t0, key) in enumerate(marks):
        t1 = bounds[idx + 1]
        a0 = 0.0 if idx == 0 else t0 - xfade / 2          # この曲が鳴り始める時刻
        a1 = min(total + 1, t1 + xfade / 2)               # 鳴り終わる時刻
        src = load(_bgm_loop(tracks[key], a1 - a0 + 1, dst_name=f"bgm_tl_{idx}.wav"))
        whole = rms(load(tracks[key]))                     # 曲全体の平均音量でそろえる
        if ref is None:
            ref = whole
        src *= ref / whole
        i0 = int(a0 * sr); L = min(len(src), int((a1 - a0) * sr), n - i0)
        seg = src[:L].copy()
        tt = np.arange(L) / sr + a0
        g = np.ones(L, dtype=np.float32)
        if idx > 0:                                        # 入り
            g *= np.sin(np.clip((tt - a0) / xfade, 0, 1) * np.pi / 2)
        if idx < len(marks) - 1:                           # 抜け
            g *= np.cos(np.clip((tt - (t1 - xfade / 2)) / xfade, 0, 1) * np.pi / 2)
        y[i0:i0 + L] += seg * g
    dst = f"{B}/bgm_timeline.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-", dst],
                   input=(np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes(), check=True)
    return dst


def _bgm_duck(bgm_wav, voice_wav, total, vol, duck_db=-5.0, hold=3.0, down=0.8, up=2.0):
    """BGMの音量カーブを先に計算して掛ける（コンプレッサーを使わない）。
    - 声のある区間で duck_db だけ下げる（下げ幅は小さめ）
    - hold 秒未満の無音（文と文の間）は「声が続いている」とみなし、BGMを戻さない
    - 下げは down 秒、戻しは up 秒かけてなめらかに動かす
    - 頭2秒フェードイン、最後4秒フェードアウト"""
    import numpy as np
    sr = 48000
    def load(p):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                             check=True, capture_output=True).stdout
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    m, v = load(bgm_wav), load(voice_wav)
    n = int(total * sr)
    m = np.pad(m, (0, max(0, n - len(m))))[:n]
    v = np.pad(v, (0, max(0, n - len(v))))[:n]
    hop = sr // 100                                   # 10ms単位で判定
    k = n // hop
    rms = np.sqrt((v[:k * hop].reshape(k, hop) ** 2).mean(1) + 1e-12)
    speech = rms > 0.01
    # 短い無音を埋める
    idx = np.flatnonzero(speech)
    if len(idx):
        gaps = np.flatnonzero(np.diff(idx) > 1)
        for g in gaps:
            a, b = idx[g], idx[g + 1]
            if (b - a) * 0.01 < hold:
                speech[a:b] = True
    target = np.where(speech, 10 ** (duck_db / 20), 1.0)
    # 片側ずつ時定数を変えてなめらかに（下げは速め、戻しはゆっくり）
    g = np.empty(k); cur = target[0]
    a_dn, a_up = 1 - np.exp(-0.01 / (down / 3)), 1 - np.exp(-0.01 / (up / 3))
    for i, t in enumerate(target):
        cur += (t - cur) * (a_dn if t < cur else a_up)
        g[i] = cur
    gain = np.interp(np.arange(n), np.arange(k) * hop + hop / 2, g)
    fade = np.ones(n)
    fi, fo = int(2 * sr), int(4 * sr)
    fade[:fi] = np.linspace(0, 1, fi); fade[-fo:] *= np.linspace(1, 0, fo)
    out = m * gain * fade * vol
    dst = f"{B}/bgm_ducked.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-", dst],
                   input=(np.clip(out, -1, 1) * 32767).astype(np.int16).tobytes(), check=True)
    return dst

def build_thumbnail(kousei, work, image_path, out_png, brand=None):
    br = brand or bungo_brand(work)
    t = kousei["thumbnail"]
    body = (f'<div class="label">{br["thumb_label"]}</div><div class="rule"></div>'
            f'<div class="center"><h1 style="position:static;font-size:180px;text-align:center;'
            f'line-height:1.4;">{t["main_copy"]}</h1></div>'
            f'<div class="credit" style="font-size:44px;color:#fff;">{t["sub_copy"]}</div>')
    slide(body, f"{B}/thumb_raw.png", image_path, scrim=0.5, css_extra=br["css"])
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/thumb_raw.png",
        "-vf", "scale=1280:720", out_png], check=True)
