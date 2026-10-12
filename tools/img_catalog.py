# tools/img_catalog.py — 題材の画像候補を集め、縮小版と出典情報を nazo/img_catalog/<id>/ に保存する
# （Claudeが中身を見て、台本のセクションごとに画像を割り当てるための下見用）
#   ONLY=<題材ID> CATEGORY="Voynich manuscript" python tools/img_catalog.py
import json, os, sys, time, requests
sys.path.insert(0, "src")
import m4_images

UA = m4_images.UA
tid = os.environ["ONLY"]
src = json.load(open(f"nazo/state/texts/{tid}.json", encoding="utf-8"))["meta"]
out = f"nazo/img_catalog/{tid}"; os.makedirs(out, exist_ok=True)

files = []
for lang, title in [("ja", src["title"]), ("en", src.get("en_title"))]:
    if not title: continue
    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params={"action": "query", "format": "json",
        "titles": title, "prop": "images", "imlimit": 100, "redirects": 1}, headers=UA, timeout=30).json()
    for pg in r["query"]["pages"].values():
        files += [im["title"].split(":", 1)[1] for im in pg.get("images", [])]
cat = os.environ.get("CATEGORY", "").strip()
if cat:
    cont = {}
    while True:
        r = requests.get("https://commons.wikimedia.org/w/api.php", params=dict({"action": "query", "format": "json",
            "list": "categorymembers", "cmtitle": "Category:" + cat, "cmtype": "file", "cmlimit": 200}, **cont),
            headers=UA, timeout=30).json()
        files += [m["title"].split(":", 1)[1] for m in r["query"]["categorymembers"]]
        if "continue" not in r or len(files) > 400: break
        cont = r["continue"]
files = [f for f in dict.fromkeys(files) if f.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff"))
         and not any(w in f.lower() for w in m4_images.SKIP_WORDS)]
print("候補", len(files))

rows = []
for b in range(0, len(files), 40):
    r = requests.get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "format": "json",
        "prop": "imageinfo", "titles": "|".join("File:" + f for f in files[b:b + 40]),
        "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 360}, headers=UA, timeout=60).json()
    for pg in r.get("query", {}).get("pages", {}).values():
        info = (pg.get("imageinfo") or [{}])[0]; meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        rows.append({"file": pg["title"], "license": lic, "w": info.get("width"), "h": info.get("height"),
                     "desc": m4_images._plain(meta.get("ImageDescription", {}).get("value", ""))[:200],
                     "artist": m4_images._plain(meta.get("Artist", {}).get("value", ""))[:120],
                     "thumb": info.get("thumburl")})
rows = [r for r in rows if r["thumb"]]
rows.sort(key=lambda r: r["file"])
for i, r in enumerate(rows[:120]):
    r["n"] = i
    try:
        c = requests.get(r["thumb"], headers=UA, timeout=30)
        if c.headers.get("content-type", "").startswith("image/"):
            open(f"{out}/{i:03d}.jpg", "wb").write(c.content)
    except Exception as e:
        print("縮小版の取得失敗", r["file"], e)
    time.sleep(0.3)
json.dump(rows[:120], open(f"{out}/catalog.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("保存", min(len(rows), 120))
