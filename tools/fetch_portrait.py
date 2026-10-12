# fetch_portrait.py — Wikimedia Commonsから肖像写真を取り、ライセンスがPDか確認して保存する
import json, sys, requests
UA = {"User-Agent": "BUNGO/0.2 (channel art; github.com/gggorilla-g/bungo)"}
out = {}
for key, title in [("soseki", "File:Natsume Soseki photo.jpg"),
                   ("akutagawa", "File:Akutagawa Ryunosuke photo2.jpg")]:
    r = requests.get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "format": "json", "titles": title, "prop": "imageinfo",
        "iiprop": "url|size|extmetadata"}, headers=UA, timeout=30).json()
    page = next(iter(r["query"]["pages"].values()))
    if "imageinfo" not in page:
        out[key] = {"title": title, "error": "not found"}; continue
    info = page["imageinfo"][0]; meta = info["extmetadata"]
    lic = meta.get("LicenseShortName", {}).get("value", "")
    out[key] = {"title": title, "license": lic, "url": info["url"], "size": [info["width"], info["height"]]}
    if "public domain" in lic.lower() or lic.lower().startswith("pd"):
        open(f"channel/src_{key}.jpg", "wb").write(requests.get(info["url"], headers=UA, timeout=60).content)
json.dump(out, open("channel/src_info.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
