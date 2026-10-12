# wm_diag.py — Wikimediaからの画像取得が通るかの診断（UA・サイズ別）
import requests, json
files = ["File:Voynich Manuscript (32).jpg", "File:Michał Wojnicz wśród książek w swoim antykwariacie na Soho Square.jpg"]
UAS = {"old": "BUNGO/0.1 (automated literature channel; contact via repo)",
       "new": "BUNGO-NAZO/0.3 (https://github.com/gggorilla-g/bungo; gggorilla.0510@gmail.com) python-requests"}
out = []
for w in (1920, 1280, 960):
    r = requests.get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "format": "json",
        "prop": "imageinfo", "titles": "|".join(files), "iiprop": "url", "iiurlwidth": w},
        headers={"User-Agent": UAS["new"]}, timeout=30).json()
    for pg in r["query"]["pages"].values():
        info = (pg.get("imageinfo") or [{}])[0]
        for name, ua in UAS.items():
            for kind in ("thumburl", "url"):
                u = info.get(kind)
                if not u: continue
                try:
                    x = requests.get(u, headers={"User-Agent": ua}, timeout=30)
                    out.append(f"w={w} {name} {kind} {x.status_code} {x.headers.get('content-type')} {len(x.content)} {u[-60:]}")
                except Exception as e:
                    out.append(f"w={w} {name} {kind} ERR {e}")
print("\n".join(out))
open("state/wm_diag.txt", "w").write("\n".join(out))
