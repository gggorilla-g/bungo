# M4: PD画像収集モジュール（本番用・GitHub Actions上で実行）
# 方針: ライセンスは検索結果を信用せず、メタデータフィールドを機械検証してから採用する。
#       検証不能・全滅時は None を返し、M5がタイポグラフィスライドにフォールバックする。
import os, requests, time

UA = {"User-Agent": "BUNGO-NAZO/0.3 (https://github.com/gggorilla-g/bungo; gggorilla.0510@gmail.com) python-requests"}  # 連絡先なしのUAはWikimediaに弾かれる（429）
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

OPEN_LICENSES = ("public domain", "pd", "cc0", "cc by")   # CC BY / CC BY-SA は出典表示つきで使う
SKIP_WORDS = ("logo", "icon", "flag", "symbol", "map of", "locator", "wiki", "edit-", "ambox", "question_book")


def _plain(html):
    import re
    return re.sub(r"<[^>]+>", "", html or "").strip()


def article_images(pages, max_n=12, min_width=800):
    """Wikipedia記事（[(lang, 記事名), ...]）に載っている画像のうち、
    ライセンスがPD/CC0/CC BY/CC BY-SAのものを集める。出典表示用の文字列を付けて返す。"""
    files = []
    for lang, title in pages:
        try:
            r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params={
                "action": "query", "format": "json", "titles": title, "prop": "images",
                "imlimit": 50, "redirects": 1}, headers=UA, timeout=20).json()
            for pg in r.get("query", {}).get("pages", {}).values():
                for im in pg.get("images", []):
                    t = im["title"].split(":", 1)[1]
                    if t not in files and t.lower().endswith((".jpg", ".jpeg", ".png")) \
                            and not any(w in t.lower() for w in SKIP_WORDS):
                        files.append(t)
        except Exception as e:
            print("記事画像の一覧取得に失敗:", lang, title, e)
    hits = []
    for b in range(0, len(files), 20):
        try:
            r = requests.get("https://commons.wikimedia.org/w/api.php", params={
                "action": "query", "format": "json", "prop": "imageinfo",
                "titles": "|".join("File:" + f for f in files[b:b + 20]),
                "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 1920}, headers=UA, timeout=30).json()
        except Exception as e:
            print("画像情報の取得に失敗:", e); continue
        for pg in r.get("query", {}).get("pages", {}).values():
            info = (pg.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            lic = meta.get("LicenseShortName", {}).get("value", "")
            if not any(lic.lower().startswith(k) or k in lic.lower() for k in OPEN_LICENSES):
                continue
            if "nc" in lic.lower() or "nd" in lic.lower().split("-"):
                continue
            if info.get("width", 0) < min_width or info.get("mime") not in ("image/jpeg", "image/png"):
                continue
            artist = _plain(meta.get("Artist", {}).get("value", "")) or "作者不明"
            hits.append({"url": info.get("thumburl") or info["url"], "file": pg["title"],
                         "credit": f"{artist} / {lic} / Wikimedia Commons（{pg['title']}）"})
            if len(hits) >= max_n:
                return hits
    return hits


def commons_files(files, width=1920):
    """Commonsのファイル名を指定して、URLと出典表示を引く（ライセンスがPD/CC0/CC BY系のものだけ）"""
    found = {}
    files = list(dict.fromkeys(files))
    for b in range(0, len(files), 40):
        r = requests.get("https://commons.wikimedia.org/w/api.php", params={
            "action": "query", "format": "json", "prop": "imageinfo",
            "titles": "|".join(files[b:b + 40]), "iiprop": "url|extmetadata", "iiurlwidth": width},
            headers=UA, timeout=60).json()
        for pg in r.get("query", {}).get("pages", {}).values():
            info = (pg.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            lic = meta.get("LicenseShortName", {}).get("value", "")
            l = lic.lower()
            if not any(k in l for k in OPEN_LICENSES) or "nc" in l.replace("-", " ").split() or "nd" in l.replace("-", " ").split():
                print("ライセンス対象外のため不使用:", pg.get("title"), lic); continue
            artist = _plain(meta.get("Artist", {}).get("value", "")) or "作者不明"
            found[pg["title"]] = {"url": info.get("thumburl") or info.get("url"), "orig": info.get("url"),
                                  "credit": f"{artist} / {lic} / Wikimedia Commons（{pg['title']}）"}
    return found


def download(url, dest, fallback=None):
    """Wikimedia等から1枚取得。画像でなければ None（エラーページを画像として使わない）。
    429（混雑）は待って再試行。縮小版がだめなら原寸URL(fallback)も試す"""
    last = ""
    for u in [url] + ([fallback] if fallback else []):
        for attempt in range(4):
            try:
                r = requests.get(u, headers=UA, timeout=60)
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
                    open(dest, "wb").write(r.content)
                    time.sleep(1.0)   # 連続取得で弾かれないよう間を空ける
                    return dest
                last = f"{r.status_code} {r.headers.get('content-type', '')}"
                wait = int(r.headers.get("retry-after", "0") or 0) if r.status_code == 429 else 0
                time.sleep(max(wait, 3 * (attempt + 1)))
            except requests.RequestException as e:
                last = str(e)[:80]; time.sleep(3 * (attempt + 1))
    print("画像の取得失敗:", url[:90], last)
    return None


def fetch_image(queries, dest, sources=None):
    """検索語リストを順に試し、最初にライセンス検証を通過した画像を保存。
       全滅なら None（→タイポグラフィスライドにフォールバック）"""
    for q in queries:
        for fn in (sources or (_met, _wikimedia)):  # 既定はMet優先（CC0が構造的に保証されるため）
            try:
                hit = fn(q)
            except Exception:
                hit = None
            if hit:
                img = requests.get(hit["url"], headers=UA, timeout=30).content
                os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
                open(dest, "wb").write(img)
                return hit
    return None

if __name__ == "__main__":
    hit = fetch_image(["ancient greek runner classical painting"], "test_m4.jpg")
    print(hit or "no image → typography fallback")
