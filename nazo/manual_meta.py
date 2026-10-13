# nazo/manual_meta.py — 手動投稿用に、動画と同じ尺計算でチャプター付き説明文とサムネイルを作る（動画は作らない）
import json, math, os, sys
sys.path.insert(0, "src"); sys.path.insert(0, "nazo")
import render, yomi, brand, upload, m4_images
import thumb as thumbmod

job = json.load(open("nazo/manual/job.json", encoding="utf-8"))
k = job["kousei"]; tid = job["id"]
src = json.load(open(f"nazo/state/texts/{tid}.json", encoding="utf-8"))
br = brand.nazo_brand(job)
os.makedirs("build", exist_ok=True)
render._YOMI.clear(); render._YOMI.update(job["yomi"])

def dur(text, pad):
    render.tts(text, "build/_m.wav")
    return math.ceil((render._wav_len("build/_m.wav") + pad) * render.FPS) / render.FPS

plan = []
for i, s in enumerate(k["sections"]):
    intro = br["part_intro"].get(s["type"])
    first = (i == 0) or (k["sections"][i - 1]["type"] != s["type"])
    narr = (intro + s["narration"]) if (intro and first) else s["narration"]
    plan += [(i, x) for x in yomi.split_sentences(narr)]
t = dur(br["title_narr"](k), 0.8)
chapters, last = [], -1
for n, (i, sent) in enumerate(plan):
    if i != last:
        chapters.append([k["sections"][i]["slide_heading"], int(t)]); last = i
    end = (n == len(plan) - 1) or (plan[n + 1][0] != i)
    t += dur(sent, 1.2 if end else 0.5)

files = [im["file"] for s in k["sections"] for im in s.get("images", [])] + [k["thumb_image"]]
got = m4_images.commons_files(files)
credits = sorted({v["credit"] for f, v in got.items() if f in files[:-1]})
out = f"nazo/manual/{tid}"; os.makedirs(out, exist_ok=True)
desc = upload.make_description(k, src["meta"], credits, chapters=chapters)
open(f"{out}/upload.txt", "w", encoding="utf-8").write(
    "【タイトル】\n" + k["title_candidates"][0] + "\n\n【説明】\n" + desc + "\n\n【タグ】\n" + ",".join(k["tags"]) + "\n")
thumb = None
if k.get("thumb_image") in got and m4_images.download(got[k["thumb_image"]]["url"], "build/thumb_src.jpg"):
    thumb = "build/thumb_src.jpg"
thumbmod.build(k["thumbnail"]["main_copy"], job["title"], thumb, f"{out}/thumb.png")
print(f"尺 {t:.0f}秒 / チャプター {len(chapters)} / 画像出典 {len(credits)}")
