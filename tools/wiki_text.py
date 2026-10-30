"""tools/wiki_text.py — Wikipedia 記事の本文（プレーンテキスト）を保存する（台本の事実確認用。CIで実行）。
使い方: OUT=nazo/wiki_text/<id> PAGES="ja:ナマケモノ;en:Sloth" python tools/wiki_text.py"""
import os, sys, requests
sys.path.insert(0, "src")
import m4_images

out = os.environ["OUT"]; os.makedirs(out, exist_ok=True)
for item in [x.strip() for x in os.environ["PAGES"].split(";") if ":" in x]:
    lang, title = item.split(":", 1)
    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params={
        "action": "query", "format": "json", "prop": "extracts|info", "explaintext": 1, "inprop": "url",
        "titles": title, "redirects": 1}, headers=m4_images.UA, timeout=30).json()
    for pg in r.get("query", {}).get("pages", {}).values():
        txt = pg.get("extract") or ""
        fn = f"{out}/{lang}_{title.replace('/', '_').replace(' ', '_')}.txt"
        open(fn, "w", encoding="utf-8").write(f"{pg.get('fullurl', '')}\n\n{txt}\n")
        print(lang, title, len(txt))
