"""怪談の原作本文を青空文庫から取ってくる（Actionsで実行）。
  python kaidan/fetch.py 042927 050326 ... → kaidan/state/texts/<id>.json"""
import json, os, re, sys, requests
sys.path.insert(0, "src")
import m2_extract

cat = json.load(open("kaidan/state/catalog.json", encoding="utf-8"))
by_id = {x["id"]: dict(x, author=a) for a, L in cat.items() for x in L}
os.makedirs("kaidan/state/texts", exist_ok=True)
for wid in sys.argv[1:]:
    x = by_id.get(wid)
    if not x:
        print("カタログに無い:", wid); continue
    try:
        body, ruby = m2_extract.fetch_text(x["html"])
    except Exception as e:
        print("取得失敗:", wid, x["title"], e); continue
    # 訳者（翻訳作品のとき）を本文HTMLの見出しから拾う
    translator = ""
    try:
        h = requests.get(x["html"].replace("https://www.aozora.gr.jp/",
                         "https://raw.githubusercontent.com/aozorabunko/aozorabunko/master/"), timeout=60).content
        enc = "utf-8" if re.search(rb'charset="?utf-8', h[:2000], re.I) else "cp932"
        m = re.search(r'class="translator"[^>]*>(.*?)</', h.decode(enc, "replace"), re.S)
        translator = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
        if not translator and x.get("card"):   # 図書カードの「翻訳者」欄から
            c = requests.get(x["card"].replace("https://www.aozora.gr.jp/",
                             "https://raw.githubusercontent.com/aozorabunko/aozorabunko/master/"), timeout=60).content
            ct = c.decode("utf-8" if b"utf-8" in c[:3000].lower() else "cp932", "replace")
            m = re.search(r"翻訳者.*?<a[^>]*>(.*?)</a>", ct, re.S)
            translator = m.group(1).strip() if m else ""
    except Exception:
        pass
    meta = {"work_id": wid, "title": x["title"], "author": x["author"], "translator": translator,
            "url": x["card"] or x["html"], "orig": x["orig"]}
    json.dump({"meta": meta, "text": body, "ruby": ruby},
              open(f"kaidan/state/texts/{wid}.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("OK", wid, x["author"], x["title"], translator, len(body))
