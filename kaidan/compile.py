"""睡眠用の長尺まとめ（数話をつないだ1本）を作る。
python kaidan/compile.py <まとめ名> <work_id> <work_id> ...
  入力: dl/<work_id>/kaidan_<work_id>.mp4 と dl/<work_id>/upload.txt（各話の動画と投稿用テキスト）
  各話の「おしまい」（宵狐のしめの挨拶）は最後の話だけ残し、途中では切る。"""
import json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = "kaidan/state"


def ts(sec):
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse(upload):
    txt = open(upload, encoding="utf-8").read()
    title = re.search(r"【タイトル】\n(.+)", txt).group(1).strip()
    chap = re.findall(r"^(\d+(?::\d+)+) (.+)$", txt, re.M)
    def sec(t):
        p = [int(x) for x in t.split(":")]
        return sum(v * 60 ** i for i, v in enumerate(reversed(p)))
    end = next((sec(t) for t, n in chap if n.strip() == "おしまい"), None)
    credits = [l for l in txt.split("\n") if l.startswith(("原作:", "語り:", "BGM:", "画像:"))]
    tags = re.search(r"【タグ】\n(.+)", txt).group(1).split(",")
    return title, end, credits, tags


def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True).stdout.strip())


def thumb(paths, n, minutes, out):
    """睡眠用まとめのサムネ：夜の藍に、語り部の宵狐と大きな題字。下に各話のサムネを札のように並べて「中身の量」を見せる"""
    import sys as _s
    _s.path.insert(0, "kaidan")
    from kitsune import kitsune
    W, H = 1280, 720
    bg = Image.open(paths[0]).convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(18))
    im = Image.blend(bg, Image.new("RGB", (W, H), (10, 12, 30)), 0.72)
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([60, 120, 520, 620], fill=120)
    im.paste((90, 40, 20), (0, 0), glow.filter(ImageFilter.GaussianBlur(90)))
    fox = kitsune(lamp=0.85, tilt=-4, size=620)
    im.paste(fox, (20, 40), fox)
    f = lambda s, w="Black": ImageFont.truetype(f"/usr/share/fonts/opentype/noto/NotoSerifCJK-{w}.ttc", s, index=0)
    d = ImageDraw.Draw(im)
    x = 560
    d.rectangle([x, 70, x + 200, 128], fill=(150, 18, 18))
    d.text((x + 100, 99), "睡眠用", font=f(44, "Bold"), fill=(255, 255, 255), anchor="mm")
    d.text((x + 230, 99), "今晩の百物語", font=f(40, "Bold"), fill=(196, 190, 182), anchor="lm")
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).text((x - 6, 150), "怪談朗読", font=f(170), fill=255)
    im.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(12)))
    d.text((x - 6, 150), "怪談朗読", font=f(170), fill=(246, 242, 234))
    d.text((x, 360), f"{n}話", font=f(110), fill=(246, 242, 234), stroke_width=3, stroke_fill=(0, 0, 0))
    w6 = d.textlength(f"{n}話", font=f(110))
    d.text((x + w6 + 24, 360), f"約{minutes}分", font=f(110), fill=(214, 30, 30), stroke_width=4, stroke_fill=(20, 0, 0))
    # 各話の札（サムネを小さく並べる）
    cw, ch, gap = 100, 56, 8
    total = len(paths) * cw + (len(paths) - 1) * gap
    x0 = x + 4
    for i, p in enumerate(paths[:6]):
        t = Image.open(p).convert("RGB").resize((cw, ch))
        px = x0 + i * (cw + gap)
        d.rectangle([px - 3, 535, px + cw + 2, 538 + ch + 2], fill=(214, 180, 120))
        im.paste(t, (px, 538))
    im.save(out)


def main(name, ids):
    os.makedirs("build_compile", exist_ok=True)
    kit = f"kaidan/manual/{name}"
    os.makedirs(kit, exist_ok=True)
    parts, chapters, credits, tags, titles, thumbs = [], [], [], [], [], []
    t = 0.0
    for i, wid in enumerate(ids):
        mp4 = f"dl/{wid}/kaidan_{wid}.mp4"
        title, end, cr, tg = parse(f"dl/{wid}/upload.txt")
        last = i == len(ids) - 1
        cut = dur(mp4) if (last or not end) else end + 0.5
        seg = f"build_compile/p{i}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-t", f"{cut:.2f}", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "21", "-pix_fmt", "yuv420p", "-r", "24", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", seg],
                       check=True)
        short = re.sub(r"^【怪談朗読】", "", title).split("｜")[0]
        m = re.search(r"「(.+?)」", short)          # 古い題名の形（〜「耳なし芳一」【…】）から作品名だけ取る
        if m:
            short = f"{m.group(1)}（{re.search(r'原作: (.+?)『', ' '.join(cr)).group(1)}）"
        chapters.append(f"{ts(t)} {short}")
        titles.append(short.split("（")[0])
        t += dur(seg)
        parts.append(seg)
        credits += cr
        tags += tg
        if os.path.exists(f"dl/{wid}/thumb.png"):
            thumbs.append(f"dl/{wid}/thumb.png")
    open("build_compile/list.txt", "w").write("".join(f"file '{os.path.basename(p)}'\n" for p in parts))
    out = f"output/{name}.mp4"
    os.makedirs("output", exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "build_compile/list.txt", "-c", "copy",
                    "-movflags", "+faststart", out], check=True)
    minutes = int(round(t / 60 / 5) * 5) or int(t / 60)
    thumb(thumbs, len(ids), minutes, f"{kit}/thumb.png")
    seen, cred = set(), []
    for c in credits:
        if c not in seen:
            seen.add(c); cred.append(c)
    tg = list(dict.fromkeys(["睡眠用", "怪談朗読", "作業用", "怪談", "朗読", "百物語"] + [x for x in tags if x]))[:30]
    names = "・".join(titles[:3]) + (" ほか" if len(titles) > 3 else "")
    ttl = f"【睡眠用】怪談朗読 {len(ids)}話まとめ 約{minutes}分｜{names}｜今晩の百物語"
    desc = "\n".join([
        f"今晩の百物語の怪談朗読を、{len(ids)}話つないだ長尺版です。寝る前や作業のおともにどうぞ。",
        "途中のしめの挨拶は省き、最後の話だけ残しています。", "",
        *chapters, "",
        "※この動画は、権利の切れた古典の怪談を、いまの言葉で語り直した朗読です。実話ではありません。", "",
        "#怪談 #睡眠用 #朗読", "", "──", *cred])
    open(f"{kit}/upload.txt", "w", encoding="utf-8").write(
        f"【タイトル】\n{ttl}\n\n【説明】\n{desc}\n\n【タグ】\n{','.join(tg)}\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", f"fps=1/{max(60, int(t / 40))},scale=480:-1,tile=8x5",
                    "-frames:v", "1", f"{kit}/sheet.jpg"])
    open(f"{kit}/duration.txt", "w").write(f"{t:.1f}\n")
    print(f"完了: {ttl}（{t / 60:.1f}分）")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
