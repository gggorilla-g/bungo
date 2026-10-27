# tools/fetch_commons.py — Wikimedia Commons から指定のファイルを取り、ライセンス情報と一緒に保存する
#   使い方: python tools/fetch_commons.py 保存先フォルダ "key=File:名前.jpg;key2=File:..."
#   パブリックドメイン（NASA など）かどうかを meta.json に残す。PD以外は保存しない。
import json, os, sys, requests

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "bungo-bot/1.0 (https://github.com/gggorilla-g/bungo)"}


def main(out, spec):
    os.makedirs(out, exist_ok=True)
    meta = {}
    mp = os.path.join(out, "meta.json")
    if os.path.exists(mp):
        meta = json.load(open(mp))
    for item in spec.split(";"):
        if "=" not in item:
            continue
        key, title = [x.strip() for x in item.split("=", 1)]
        r = requests.get(API, params={"action": "query", "titles": title, "prop": "imageinfo", "iiprop": "url|extmetadata",
                                      "iiurlwidth": 2000, "format": "json"}, headers=UA, timeout=60).json()
        page = next(iter(r["query"]["pages"].values()))
        if "imageinfo" not in page:
            print("見つからない:", title); continue
        ii = page["imageinfo"][0]
        em = ii.get("extmetadata", {})
        lic = em.get("LicenseShortName", {}).get("value", "")
        artist = em.get("Artist", {}).get("value", "")
        credit = em.get("Credit", {}).get("value", "")
        if "public domain" not in lic.lower() and lic.upper() not in ("PD", "CC0"):
            print("PDではないので保存しない:", title, lic); continue
        url = ii.get("thumburl") or ii["url"]
        img = requests.get(url, headers=UA, timeout=120).content
        open(os.path.join(out, f"{key}.jpg"), "wb").write(img)
        meta[key] = {"title": title, "license": lic, "artist": artist, "credit": credit, "page": ii.get("descriptionurl", "")}
        print("保存:", key, title, lic)
    json.dump(meta, open(mp, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
