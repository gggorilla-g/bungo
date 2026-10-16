"""作成済みの回のサムネだけを作り直す（Actionsで実行）。 python kaidan/thumb_only.py <作品ID>"""
import json, os, sys
sys.path.insert(0, "src"); sys.path.insert(0, "kaidan")
import m4_images, thumb_quiet
import kaidan_brand as brand
wid = sys.argv[1]
k = json.load(open(f"kaidan/drafts/{wid}.json", encoding="utf-8"))
meta = json.load(open(f"kaidan/state/texts/{wid}.json", encoding="utf-8"))["meta"]
f = k.get("thumb_image") or k.get("title_image")
got = m4_images.commons_files([f], width=2000)
os.makedirs("build", exist_ok=True)
src = None
if got and m4_images.download(next(iter(got.values()))["url"], "build/thumb_src.jpg"):
    src = "build/thumb_src.jpg"
os.makedirs(f"kaidan/manual/{wid}", exist_ok=True)
thumb_quiet.build(k.get("display_title", meta["title"]), brand.kansuji(k["no"]), meta["author"], src,
                  f"kaidan/manual/{wid}/thumb.png")
print("thumb", wid, bool(src))
