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
