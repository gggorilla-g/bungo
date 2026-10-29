# nazo/thumb_only.py — 台本の下書き（nazo/drafts/<id>.json）からサムネだけ作り直す
#   ID=antikythera python nazo/thumb_only.py → nazo/manual/<id>/thumb.png
import json, os, sys
sys.path.insert(0, "src"); sys.path.insert(0, "nazo")
import m4_images, thumb
i = os.environ["ID"]
k = json.load(open(f"nazo/drafts/{i}.json"))
os.makedirs("build", exist_ok=True)
src = None
got = m4_images.commons_files([k["thumb_image"]]) if k.get("thumb_image") else {}
if got:
    info = next(iter(got.values()))
    if m4_images.download(info["url"], "build/thumb_src.jpg", fallback=info.get("orig")):
        src = "build/thumb_src.jpg"
subject = os.environ.get("SUBJECT") or k["thumbnail"].get("sub_copy", "")
print(thumb.build(k["thumbnail"]["main_copy"], subject, src, f"nazo/manual/{i}/thumb.png"))

# 「テストと比較」用の別案（台本の thumb_variants: [{key, main_copy, image}] → thumb_<key>.png）
for v in k.get("thumb_variants", []):
    vsrc = None
    g = m4_images.commons_files([v["image"]]) if v.get("image") else {}
    if g:
        inf = next(iter(g.values()))
        if m4_images.download(inf["url"], f"build/thumb_src_{v['key']}.jpg", fallback=inf.get("orig")):
            vsrc = f"build/thumb_src_{v['key']}.jpg"
    fn = thumb.build_v2 if v.get("style") == "v2" else thumb.build
    print(fn(v["main_copy"], subject, vsrc or src, f"nazo/manual/{i}/thumb_{v['key']}.png"))

# 画像の出典の全一覧（ファイル名つき）も作り直す
import upload
files = [im["file"] for s in k["sections"] for im in s.get("images", [])]
files += [f for f in (k.get("title_image"), k.get("thumb_image")) if f]
info = m4_images.commons_files(files)
credits = [v["credit"] for v in info.values()]
title = os.environ.get("SUBJECT") or k["thumbnail"].get("sub_copy", i)
open(f"nazo/manual/{i}/credits.md", "w", encoding="utf-8").write(upload.credits_md(title, credits))
print("credits", len(credits))
