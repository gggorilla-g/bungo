# nazo/short.py — 謎の本編から、縦型ショート（1080x1920、30〜45秒）を作る。本編への入口。
#   ID=phaistos python nazo/short.py → output/short_<id>.mp4（Actionsで実行。画像はCommonsから）
# 構成：つかみ（台本の hook）をホー博士が語る → 「続きは本編で」とホー博士が締める。
# テロップは隙間なく畳み掛ける（喋っている間は必ず大きな箱文字が出ている）。
import json, math, os, re, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
sys.path.insert(0, "src"); sys.path.insert(0, "nazo")
import render, yomi, motion, se, m4_images
import brand as nazo_brand

W, H, FPS = 1080, 1920, 30
YEL, BLK, WHT, RED = (255, 226, 0), (0, 0, 0), (255, 255, 255), (192, 57, 43)
CTA = {"say": "続きは、本編の動画で、くわしく話しておるぞい。", "text": "続きは本編で\nくわしく話すぞい"}
B = "build_short"


def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    r = img.resize((int(img.width * s) + 1, int(img.height * s) + 1))
    return r.crop(((r.width - w) // 2, (r.height - h) // 2, (r.width - w) // 2 + w, (r.height - h) // 2 + h))


def contain(img, w, h):
    s = min(w / img.width, h / img.height)
    return img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)


def build(work_id):
    k = json.load(open(f"nazo/drafts/{work_id}.json", encoding="utf-8"))
    fixes = {}
    if os.path.exists(f"nazo/drafts/{work_id}_yomi.json"):
        fixes = json.load(open(f"nazo/drafts/{work_id}_yomi.json", encoding="utf-8"))
    lines = list(k["hook"]) + [dict(CTA, file=k.get("title_image") or k["hook"][-1].get("file"))]
    os.makedirs(B, exist_ok=True); os.makedirs("output", exist_ok=True)
    render.B = B
    render.set_voice(**nazo_brand.VOICE)
    for ln in lines:
        render._YOMI[ln["say"]] = fixes.get(ln["say"]) or yomi.base_fix(ln["say"], {"title": "", "author": ""}, {})
    # 画像
    files = [ln["file"] for ln in lines if ln.get("file")]
    got = m4_images.commons_files(files) if files else {}
    local = {}
    for j, (f, info) in enumerate(got.items()):
        if m4_images.download(info["url"], f"{B}/img{j}.jpg", fallback=info.get("orig")):
            local[f] = f"{B}/img{j}.jpg"
    # 文字
    f_tel = motion.font(96)
    f_ch = motion.font(40)
    f_subj = motion.font(64)
    f_cr = motion.font(26, "Bold")
    subj = k["thumbnail"].get("sub_copy", "")
    vids, wavs = [], []
    for li, ln in enumerate(lines):
        wav = f"{B}/l{li}.wav"
        render.tts(ln["say"], wav)
        d = math.ceil((render._wav_len(wav) + (0.9 if li == len(lines) - 1 else 0.25)) * FPS) / FPS
        render._pad_wav(wav, f"{B}/l{li}_p.wav", d)
        se.mix(f"{B}/l{li}_p.wav", [("pop_mid" if li % 2 else "pop_hi", 0.02, 1.0)] +
               ([("whoosh_l", 0.0, 1)] if li == 0 else []) + ([("chime_b", d - 0.8, 0.8)] if li == len(lines) - 1 else []))
        n = int(round(d * FPS))
        mouth = motion.mouth_track(f"{B}/l{li}_p.wav", n)
        src = Image.open(local[ln["file"]]).convert("RGB") if ln.get("file") in local else Image.new("RGB", (1200, 900), (30, 30, 30))
        bg = ImageEnhance.Brightness(cover(src, W, H).filter(ImageFilter.GaussianBlur(30))).enhance(0.35)
        fg = contain(src, W - 60, 780)
        tel = ln["text"].split("\n")
        out = f"{B}/l{li}.mp4"
        p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                              "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                              "-pix_fmt", "yuv420p", "-an", out], stdin=subprocess.PIPE)
        for i in range(n):
            t = i / FPS
            fr = bg.copy()
            z = 1.0 + 0.06 * (t / d)                                 # 画像はゆっくり寄る
            g = fg.resize((int(fg.width * z), int(fg.height * z)), Image.BILINEAR)
            fr.paste(g, ((W - g.width) // 2, 290 + (780 - g.height) // 2))
            dr = ImageDraw.Draw(fr)
            motion.box_text(dr, W // 2, 70, nazo_brand.CHANNEL, f_ch, WHT, RED, 26, 12, anchor="ct")
            if subj:
                motion.box_text(dr, W // 2, 170, subj, f_subj, BLK, WHT, 30, 14, anchor="ct")
            # テロップ：出だしだけ少し弾む
            e = motion.back(min(1, t / 0.25))
            ft = motion.font(int(96 * (0.9 + 0.1 * e)))
            y = 1110
            for j, l in enumerate(tel):
                fg_, bg_ = (BLK, YEL) if j == len(tel) - 1 else (WHT, BLK)
                _, hh = motion.box_text(dr, W // 2, y, l, ft, fg_, bg_, 34, 18, anchor="ct")
                y += hh + 16
            # ホー博士（右下で語る）
            o, _ = motion.owl_frame(i, mouth[i], False, li, size=470)
            fr.paste(o, (W - 470 + 20, H - 470 - 10), o)
            dr.text((30, H - 50), f"VOICEVOX:{nazo_brand.VOICE_NAME}", font=f_cr, fill=(200, 200, 200))
            p.stdin.write(fr.tobytes())
        p.stdin.close(); p.wait()
        vids.append(out); wavs.append(f"{B}/l{li}_p.wav")
    open(f"{B}/v.txt", "w").write("\n".join(f"file '{os.path.basename(v)}'" for v in vids))
    open(f"{B}/a.txt", "w").write("\n".join(f"file '{os.path.basename(a)}'" for a in wavs))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "v.txt", "-c", "copy", "all_v.mp4"], check=True, cwd=B)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "a.txt", "all_a.wav"], check=True, cwd=B)
    total = render._wav_len(f"{B}/all_a.wav")
    bgm = nazo_brand.nazo_brand({"title": ""}).get("bgm_hook")
    out = f"output/short_{work_id}.mp4"
    if bgm and os.path.exists(bgm):
        bl = render._bgm_loop(bgm, total, dst_name="short_bgm.wav")
        fc = ("[1:a]aresample=48000[v];[2:a]aresample=48000,volume=0.10,afade=t=out:st=%.2f:d=1.2[m];"
              "[v][m]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[a]" % max(0, total - 1.2))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/all_v.mp4", "-i", f"{B}/all_a.wav", "-i", bl,
                        "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "192k", "-t", f"{total:.3f}", out], check=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/all_v.mp4", "-i", f"{B}/all_a.wav", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", out], check=True)
    # 投稿用（タイトル・説明）とコマ一覧
    kit = f"nazo/manual/{work_id}"; os.makedirs(kit, exist_ok=True)
    title = f"{k['thumbnail']['main_copy'].replace(chr(10), '')}「{subj}」 #ショート #世界の謎"
    open(f"{kit}/short_upload.txt", "w", encoding="utf-8").write(
        f"【タイトル】\n{title}\n\n【説明】\n続きは本編で：{nazo_brand.CHANNEL}\n\n"
        f"音声: VOICEVOX:{nazo_brand.VOICE_NAME}\nBGM: the ghost house / 稿屋 隆（DOVA-SYNDROME）\n"
        + "".join(f"画像: {got[f]['credit']}\n" for f in dict.fromkeys(files) if f in local) + f"\n【タグ】\n{','.join(nazo_brand.VOICE_TAGS + ['世界の謎', subj])}\n\n【メモ（貼らない）】\nアップ後、編集画面の「関連動画」に本編を選ぶ\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", "fps=1/3,scale=270:-1,tile=6x2",
                    "-frames:v", "1", f"{kit}/short_sheet.jpg"])
    print("short", out, round(total, 1), "秒")
    return out


if __name__ == "__main__":
    build(os.environ.get("ID") or sys.argv[1])
