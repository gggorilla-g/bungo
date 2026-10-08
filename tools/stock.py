# tools/stock.py — チャット側（Claude）で在庫を仕込むための道具。Actionsでは使わない。
#   python tools/stock.py check <作品ID> <台本.json>   … 構成・引用照合と、読み上げ文ごとのカナを一覧
#   python tools/stock.py push  <作品ID> <台本.json> <読み修正.json>
#        … 読み修正 {"原文の文": "読み上げ用テキスト"} を当てて再度カナを出し、在庫(queue)に積む
import json, re, sys, os
sys.path.insert(0, "src")
import m3_script, yomi

PART_INTRO = {"shin_toi": "最後に、もう一つの問いを。"}

def sentences(k, work):
    out = [work["title"] + "。" + work["author"] + "。" + k.get("logline", "")]
    for i, s in enumerate(k["sections"]):
        first = (i == 0) or (k["sections"][i-1]["type"] != s["type"])
        intro = PART_INTRO.get(s["type"])
        narr = (intro + s["narration"]) if (intro and first) else s["narration"]
        out += yomi.split_sentences(narr)
    return list(dict.fromkeys(out))

def load(wid, kpath):
    c = json.load(open(f"state/texts/{wid}.json", encoding="utf-8"))
    return c, json.load(open(kpath, encoding="utf-8"))

def check(wid, kpath):
    c, k = load(wid, kpath)
    print("validate:", m3_script.validate(k, c["text"]))
    for i, t in enumerate(sentences(k, c["meta"])):
        f = yomi.base_fix(t, c["meta"], c["ruby"])
        print(f"[{i}] {t}\n     {yomi.kana(f)}")

def push(wid, kpath, fixpath):
    c, k = load(wid, kpath)
    ok, why = m3_script.validate(k, c["text"])
    assert ok, why
    fixes = json.load(open(fixpath, encoding="utf-8")) if fixpath else {}
    ym = {}
    for t in sentences(k, c["meta"]):
        ym[t] = fixes.get(t) or yomi.base_fix(t, c["meta"], c["ruby"])
        if t in fixes:
            print("修正後:", ym[t], "→", yomi.kana(ym[t]))
    q = json.load(open("state/queue.json", encoding="utf-8"))
    q = [x for x in q if x["work_id"] != wid]
    q.append(dict(c["meta"], kousei=k, yomi=ym))
    json.dump(q, open("state/queue.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"在庫に追加: {c['meta']['title']}（在庫 {len(q)} 本）")

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "check": check(sys.argv[2], sys.argv[3])
    else: push(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
