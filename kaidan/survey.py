"""青空文庫カタログから、権利の切れた怪談の候補作品を集める（Actionsで実行）。
  python kaidan/survey.py → kaidan/state/catalog.json"""
import json, os, re, sys, collections
sys.path.insert(0, "src")
import m1_select

AUTHORS = ["田中貢太郎", "岡本綺堂", "小泉八雲", "柳田国男", "泉鏡花", "小酒井不木", "上田秋成", "鈴木鼓村", "江見水蔭"]
rows = m1_select.load_catalog()
out = collections.defaultdict(list)
seen = set()
for r in rows:
    n = r["姓"] + r["名"]
    if n not in AUTHORS or r["役割フラグ"] not in ("著者", "翻訳者"):
        continue
    if r["作品著作権フラグ"] != "なし" or r["人物著作権フラグ"] != "なし":
        continue
    if r["作品ID"] in seen:
        continue
    seen.add(r["作品ID"])
    out[n].append({"id": r["作品ID"], "title": r["作品名"], "kana": r["文字遣い種別"],
                   "role": r["役割フラグ"], "card": r.get("図書カードURL", ""), "html": r.get("XHTML/HTMLファイルURL", ""),
                   "text": r.get("テキストファイルURL", ""), "orig": r.get("底本名1", "")})
os.makedirs("kaidan/state", exist_ok=True)
json.dump(out, open("kaidan/state/catalog.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for n in AUTHORS:
    print(n, len(out[n]))
