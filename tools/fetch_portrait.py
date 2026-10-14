# fetch_portrait.py — Wikimedia Commonsの作家カテゴリから肖像写真を探し、PDのものだけ保存する
#   使い方: python tools/fetch_portrait.py dazai "Category:Osamu Dazai"
import json, sys, os, requests
UA = {"User-Agent": "BUNGO/0.3 (channel art; https://github.com/gggorilla-g/bungo; gggorilla.0510@gmail.com)"}
key, cat = sys.argv[1], sys.argv[2]
API = "https://commons.wikimedia.org/w/api.php"
r = requests.get(API, params={"action": "query", "format": "json", "generator": "categorymembers",
    "gcmtitle": cat, "gcmtype": "file", "gcmlimit": 100, "prop": "imageinfo",
    "iiprop": "url|size|extmetadata", "iiurlwidth": 1600}, headers=UA, timeout=60).json()
os.makedirs(f"channel/src_{key}", exist_ok=True)
out = []
for pg in r.get("query", {}).get("pages", {}).values():
    info = (pg.get("imageinfo") or [{}])[0]; meta = info.get("extmetadata", {})
    g = lambda k: meta.get(k, {}).get("value", "")
    lic = g("LicenseShortName")
    row = {"title": pg["title"], "license": lic, "size": [info.get("width"), info.get("height")],
           "date": g("DateTimeOriginal")[:80], "artist": g("Artist")[:120], "desc": g("ImageDescription")[:200]}
    pd = "public domain" in lic.lower() or lic.lower().startswith("pd")
    if pd and pg["title"].lower().endswith((".jpg", ".jpeg", ".png")):
        fn = f"channel/src_{key}/{len(out):02d}.jpg"
        open(fn, "wb").write(requests.get(info.get("thumburl") or info["url"], headers=UA, timeout=60).content)
        row["local"] = fn
    out.append(row)
json.dump(out, open(f"channel/src_{key}/info.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
