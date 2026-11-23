"""妄想科学の長尺「法則の図鑑」：書き出し済みのショートを章にして、後ろにずんだもんの解説（声と字幕）を足す。横長 1920x1080。
使い方: python3 tools/laws_long.py nazo/long/<id>.json   → output/<id>.mp4
  声は先に python3 nazo/kaizo3d.py voice <id>（nazo/shorts/<id>.json、読みの関門つき）で作っておく
  画面：左に縦のショート、右に章番号・章名・法則の名前と字幕。暗い背景と細い光の線（ショートと同じ雰囲気）。キャラクターの絵は使わない"""
import json, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
W, H, FPS, SR = 1920, 1080, 30, 44100
VW, VX = 608, 96                      # ショートの幅と左位置
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"; FONTB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
F = lambda s, b=False: ImageFont.truetype(FONTB if b else FONT, s, index=0)
sp = json.load(open(sys.argv[1], encoding="utf-8")); sid = sp["id"]; B = f"build_long/{sid}"; os.makedirs(B, exist_ok=True)
vs = json.load(open(f"nazo/shorts/{sid}.json", encoding="utf-8")); tl = json.load(open(f"nazo/kaizo/specs/{sid}_timeline.json"))
CAP = {l["id"]: l["cap"] for l in vs["lines"]}; VO = {b["id"]: b["voice"] for b in tl["beats"]}
CH = sp["chapters"]; N = len(CH)
HUE = [(65, 226, 255), (157, 255, 122), (255, 209, 102), (255, 143, 171), (127, 168, 255), (255, 111, 177), (94, 234, 212)]
def run(a): subprocess.run(a, check=True)
def dur(p): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout)
def fit(d, text, size, maxw, bold=False):
    while size > 20 and d.textlength(text, font=F(size, bold)) > maxw: size -= 2
    return F(size, bold)
def panel(ci, cap=None, li=0, ln=1):
    c = CH[ci]; col = HUE[ci % len(HUE)]; im = Image.new("RGB", (W, H), (5, 6, 15)); d = ImageDraw.Draw(im)
    for x in range(0, W, 96): d.line([(x, 0), (x, H)], fill=(11, 13, 30))
    for y in range(0, H, 96): d.line([(0, y), (W, y)], fill=(11, 13, 30))
    d.rectangle([VX - 3, 0, VX + VW + 2, H], outline=tuple(v // 3 for v in col), width=3)
    x0 = VX + VW + 110; mw = W - x0 - 90
    d.text((x0, 64), sp["title"], font=fit(d, sp["title"], 34, mw, True), fill=(150, 160, 215))
    for i in range(N):                                     # 章の目盛り
        on = i == ci; d.rounded_rectangle([x0 + i * 62, 128, x0 + i * 62 + 46, 140], 6, fill=HUE[i % len(HUE)] if i <= ci else (40, 44, 80))
    d.text((x0, 180), f"法則 {ci + 1} / {N}", font=F(46), fill=col)
    d.text((x0, 250), c["name"], font=fit(d, c["name"], 104, mw), fill=(255, 255, 255))
    d.rounded_rectangle([x0, 400, x0 + 12, 470], 6, fill=col); d.text((x0 + 34, 398), c["law"], font=fit(d, c["law"], 60, mw - 34), fill=col)
    if cap is None:
        for j, p in enumerate(c["pts"]):
            d.text((x0, 590 + j * 96), "・" + p, font=fit(d, "・" + p, 58, mw, True), fill=(205, 212, 245))
        d.text((x0, 940), "このあと解説", font=F(36, True), fill=(110, 118, 170))
    else:
        d.line([(x0, 540), (x0 + mw, 540)], fill=(40, 44, 80), width=2)
        for j, t in enumerate(cap):
            d.text((x0, 600 + j * 132), t, font=fit(d, t, 92, mw), fill=(255, 224, 102) if j == len(cap) - 1 else (255, 255, 255))
        for j in range(ln): d.ellipse([x0 + j * 34, 960, x0 + j * 34 + 16, 976], fill=col if j <= li else (40, 44, 80))
    return im
segs, audio = [], np.zeros((int(SR * 3600), 2), np.float32); T = 0.0; marks = []
def rd(p):
    w = f"{B}/tmp.wav"; run(["ffmpeg", "-loglevel", "error", "-y", "-i", p, "-ac", "2", "-ar", str(SR), w])
    with wave.open(w) as f: return np.frombuffer(f.readframes(f.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
def seg(png, video, ss, d, loop, out):
    if not os.path.exists(out) or os.environ.get("FORCE"):
        run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", png] + (["-stream_loop", "-1"] if loop else []) + ["-ss", f"{ss:.3f}", "-i", video,
             "-filter_complex", f"[1:v]fps={FPS},scale={VW}:{H}[v];[0:v][v]overlay={VX}:0:shortest=0[o]", "-map", "[o]", "-t", f"{d:.3f}", "-an",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), out])
    segs.append(out)
fr = lambda t: round(t * FPS) / FPS
for ci, c in enumerate(CH):
    v = f"output/{c['id']}_ja.mp4"; vd = fr(dur(v) - .04); a = rd(v); marks.append((T, c["name"]))
    p = f"{B}/p{ci}.png"; panel(ci).save(p); seg(p, v, 0, vd, False, f"{B}/s{ci}_a.mp4")
    i0 = int(T * SR); k = min(len(a), int(vd * SR)); audio[i0:i0 + k] += a[:k]; T += vd
    off = 0.0
    for li, lid in enumerate(c["lines"]):
        d = fr(VO[lid] + (.55 if li == len(c["lines"]) - 1 else .3) + (.35 if li == 0 else 0)); lead = .35 if li == 0 else .05
        p = f"{B}/p{ci}_{li}.png"; panel(ci, CAP[lid], li, len(c["lines"])).save(p); seg(p, v, off % vd, d, True, f"{B}/s{ci}_{li}.mp4")
        i0 = int(T * SR); n = int(d * SR); idx = (int((off % vd) * SR) + np.arange(n)) % min(len(a), int(vd * SR)); audio[i0:i0 + n] += a[idx] * .16
        with wave.open(f"build_kaizo/{sid}/{lid}.wav") as f: vw = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768; vsr = f.getframerate()
        vw = vw[:int(VO[lid] * vsr)]; vw = np.interp(np.arange(int(len(vw) * SR / vsr)) * vsr / SR, np.arange(len(vw)), vw)
        j0 = int((T + lead) * SR); audio[j0:j0 + len(vw)] += vw[:, None] * 1.6
        T += d; off += d
audio = np.clip(audio[:int(T * SR)], -1, 1)
with wave.open(f"{B}/audio.wav", "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((audio * 32767).astype(np.int16).tobytes())
open(f"{B}/list.txt", "w").write("".join(f"file '{os.path.abspath(s)}'\n" for s in segs))
out = f"output/{sid}.mp4"
run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{B}/list.txt", "-i", f"{B}/audio.wav", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out])
open(f"{B}/chapters.txt", "w").write("".join(f"{int(t) // 60}:{int(t) % 60:02d} {n}\n" for t, n in marks))
print("書き出し:", out, f"{T / 60:.1f}分"); print(open(f"{B}/chapters.txt").read())
