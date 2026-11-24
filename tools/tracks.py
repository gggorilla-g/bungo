"""複数の書き出しを、たての帯ごとに1本へ重ねる（列ごとに別のカメラで追った絵を、楽譜の段のように並べる）。
使い方: python3 tools/tracks.py <出力id> <土台.mp4> <重ねる.mp4:y0:y1> ... [--labels 文字1,文字2,…]
  y0,y1 は画面の高さに対する割合。土台の絵に、各入力の帯だけを切り出して重ねる。音は全部を足す。帯の左上に小さく名前を入れる"""
import subprocess, sys
from PIL import Image, ImageDraw, ImageFont
a = sys.argv[1:]; labels = []
if "--labels" in a: i = a.index("--labels"); labels = a[i + 1].split(","); a = a[:i]
oid, base, rest = a[0], a[1], [x.split(":") for x in a[2:]]
W, H = 1080, 1920; F = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 30, index=0)
im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
bands = [(float(rest[0][1]) - (float(rest[0][2]) - float(rest[0][1])), float(rest[0][1]))] + [(float(y0), float(y1)) for _, y0, y1 in rest] if rest else []
for i, (y0, y1) in enumerate(bands):
    if i: d.line([(0, int(y0 * H)), (W, int(y0 * H))], fill=(120, 200, 255, 110), width=2)
    if i < len(labels): d.text((26, int(y0 * H) + 12), labels[i], font=F, fill=(225, 235, 250, 235), stroke_width=4, stroke_fill=(5, 6, 15, 255))
im.save(f"build_ballsim/{oid}_labels.png")
cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", base]
for f, _, _ in rest: cmd += ["-i", f]
cmd += ["-i", f"build_ballsim/{oid}_labels.png"]; fc = []; last = "[0:v]"
for i, (f, y0, y1) in enumerate(rest):
    yy = int(float(y0) * H); hh = int(float(y1) * H) - yy; fc.append(f"[{i + 1}:v]crop={W}:{hh}:0:{yy}[c{i}];{last}[c{i}]overlay=0:{yy}[v{i}]"); last = f"[v{i}]"
fc.append(f"{last}[{len(rest) + 1}:v]overlay=0:0[vo]"); fc.append("".join(f"[{i}:a]" for i in range(len(rest) + 1)) + f"amix=inputs={len(rest) + 1}:normalize=0,alimiter=limit=0.95[ao]")
cmd += ["-filter_complex", ";".join(fc), "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", f"output/{oid}.mp4"]
subprocess.run(cmd, check=True); print("書き出し:", f"output/{oid}.mp4")
