# nazo/prefetch.py — 在庫仕込み用に、題材のWikipedia本文（日本語版＋英語版）を取っておく。LLMは呼ばない・無料。
# 置き場所: nazo/state/texts/<題材ID>.json  {meta, text_ja, text_en}
# この本文が「事実の唯一の根拠」。台本の年号・数字・固有名詞はここに書かれていなければ不採用になる。
import json, os, sys, requests

UA = {"User-Agent": "NAZO/0.1 (automated history channel; github.com/gggorilla-g/bungo)"}
D = "nazo/state/texts"
N = 12


def load(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default


def _get(lang, params):
    params = dict(params, format="json", formatversion=2)
    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params=params,
                     headers=UA, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_page(lang, title):
    """本文(プレーンテキスト)・版ID・英語版タイトルを返す。見つからなければ None"""
    j = _get(lang, {"action": "query", "prop": "extracts|revisions|langlinks|info",
                    "explaintext": 1, "redirects": 1, "titles": title,
                    "rvprop": "ids", "lllang": "en", "inprop": "url"})
    p = j["query"]["pages"][0]
    if p.get("missing") or not p.get("extract"):
        return None
    return {"title": p["title"], "text": p["extract"], "url": p.get("fullurl", ""),
            "revid": p["revisions"][0]["revid"],
            "en_title": (p.get("langlinks") or [{}])[0].get("title", "")}


def search_title(lang, q):
    j = _get(lang, {"action": "query", "list": "search", "srsearch": q, "srlimit": 1})
    hits = j["query"]["search"]
    return hits[0]["title"] if hits else None


def main():
    os.makedirs(D, exist_ok=True)
    topics = load("nazo/topics.json", [])
    done = {p["id"] for p in load("nazo/state/published.json", []) if p.get("video_id")}
    queued = {q["id"] for q in load("nazo/state/queue.json", [])}
    have = {f[:-5] for f in os.listdir(D) if f.endswith(".json")}
    for w in have & done:
        os.remove(f"{D}/{w}.json")
    have -= done
    need = N - len(have - queued)
    print(f"手元の本文 {len(have)} / 必要 {need}")
    for t in topics:
        if need <= 0:
            break
        if t["id"] in done | queued | have:
            continue
        try:
            ja = fetch_page("ja", t["wiki"])
            if ja is None:
                alt = search_title("ja", t["wiki"])
                print(f"記事なし: {t['wiki']} → 検索候補: {alt}")
                ja = fetch_page("ja", alt) if alt else None
            if ja is None:
                print("取得失敗(日本語版なし):", t["wiki"]); continue
            en = fetch_page("en", ja["en_title"]) if ja["en_title"] else None
        except Exception as e:
            print("取得失敗:", t["wiki"], e); continue
        meta = {"id": t["id"], "title": ja["title"], "url_ja": ja["url"], "revid_ja": ja["revid"],
                "en_title": ja["en_title"],
                "url_en": en["url"] if en else "", "revid_en": en["revid"] if en else None}
        json.dump({"meta": meta, "text_ja": ja["text"], "text_en": en["text"] if en else ""},
                  open(f"{D}/{t['id']}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        need -= 1
        print(f"取得: {ja['title']}  ja {len(ja['text'])}字 / en {len(en['text']) if en else 0}字")


if __name__ == "__main__":
    main()
