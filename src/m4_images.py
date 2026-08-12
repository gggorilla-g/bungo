# M4: PD画像収集モジュール（本番用・GitHub Actions上で実行）
# 方針: ライセンスは検索結果を信用せず、メタデータフィールドを機械検証してから採用する。
#       検証不能・全滅時は None を返し、M5がタイポグラフィスライドにフォールバックする。
import requests, time

UA = {"User-Agent": "BUNGO/0.1 (automated literature channel; contact via repo)"}
PD_LICENSES = {"pd", "public domain", "cc0"}
MIN_WIDTH = 1600

def _wikimedia(query):
    """Wikimedia Commons: extmetadataのLicenseShortNameで機械検証"""
    r = requests.get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": 8,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 2400,
    }, headers=UA, timeout=20).json()
    for page in r.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo", [{}])[0]
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "").lower()
        if not any(k in lic for k in PD_LICENSES):
            continue  # PD/CC0以外は候補から除外
        if info.get("width", 0) < MIN_WIDTH:
            continue
        artist = meta.get("Artist", {}).get("value", "")
        return {"url": info.get("thumburl") or info["url"],
                "credit": f"Wikimedia Commons / {lic.upper()}",
                "artist_html": artist, "source": "wikimedia"}
    return None

def _met(query):
    """Met Museum Open Access: isPublicDomain=true のみ採用（API自体がPDフラグを持つ）"""
    ids = requests.get("https://collectionapi.metmuseum.org/public/collection/v1/search",
        params={"q": query, "hasImages": "true"}, headers=UA, timeout=20).json().get("objectIDs") or []
    for oid in ids[:6]:
        time.sleep(0.3)
        o = requests.get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}",
                         headers=UA, timeout=20).json()
        if o.get("isPublicDomain") and o.get("primaryImage"):
            return {"url": o["primaryImage"],
                    "credit": "The Metropolitan Museum of Art / Public Domain (CC0)",
                    "artist_html": o.get("artistDisplayName", ""), "source": "met"}
    return None

def fetch_image(queries, dest):
    """検索語リストを順に試し、最初にライセンス検証を通過した画像を保存。
       全滅なら None（→タイポグラフィスライドにフォールバック）"""
    for q in queries:
        for fn in (_met, _wikimedia):  # Metを優先（CC0が構造的に保証されるため）
            try:
                hit = fn(q)
            except Exception:
                hit = None
            if hit:
                img = requests.get(hit["url"], headers=UA, timeout=30).content
                open(dest, "wb").write(img)
                return hit
    return None

if __name__ == "__main__":
    # 動作テスト（Actions上で実行）: python m4_images.py
    hit = fetch_image(["ancient greek runner classical painting"], "test_m4.jpg")
    print(hit or "no image → typography fallback")
