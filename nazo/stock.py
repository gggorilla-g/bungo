# nazo/stock.py — チャット側（Claude）でNAZOの在庫を仕込む道具。Actionsでは使わない。
#   python nazo/stock.py check <題材ID> <台本.json>
#        … 事実照合の結果と、読み上げ文ごとのカナ（VOICEVOXが実際に読む音）を一覧
#   python nazo/stock.py push  <題材ID> <台本.json> [読み修正.json]
#        … 読み修正 {"原文の文": "読み上げ用テキスト"} を当てて在庫(queue)に積む
import json, re, sys
sys.path.insert(0, "src"); sys.path.insert(0, "nazo")
import check, yomi, brand

S = "nazo/state"


def sentences(k, work):
    """render.build_video が読み上げる文と同じ並び・同じ切り方"""
    out = [work["title"] + "。" + k.get("logline", "")]
    for i, s in enumerate(k["sections"]):
        intro = brand.PART_INTRO.get(s["type"])
        first = (i == 0) or (k["sections"][i - 1]["type"] != s["type"])
        narr = (intro + s["narration"]) if (intro and first) else s["narration"]
        out += yomi.split_sentences(narr)   # render.build_video と同じ区切り方
    return list(dict.fromkeys(out))


def _load(tid, kpath):
    src = json.load(open(f"{S}/texts/{tid}.json", encoding="utf-8"))
    return src, json.load(open(kpath, encoding="utf-8"))


def _work(src):
    m = src["meta"]
    return {"id": m["id"], "title": m["title"]}


def do_check(tid, kpath):
    src, k = _load(tid, kpath)
    ok, errs = check.validate(k, src)
    print("事実照合:", "合格" if ok else "不合格")
    for e in errs:
        print("  -", e)
    total = sum(len(s["narration"]) for s in k["sections"])
    print(f"文字数 {total}")
    for i, t in enumerate(sentences(k, _work(src))):
        print(f"[{i}] {t}\n     {yomi.kana(t)}")


def do_push(tid, kpath, fixpath=None):
    src, k = _load(tid, kpath)
    ok, errs = check.validate(k, src)
    assert ok, errs
    fixes = json.load(open(fixpath, encoding="utf-8")) if fixpath else {}
    work = _work(src)
    ym = {}
    for t in sentences(k, work):
        ym[t] = fixes.get(t, t)
        if t in fixes:
            print("修正:", t[:24], "→", yomi.kana(ym[t]))
    unused = [f for f in fixes if f not in ym]
    assert not unused, f"台本に無い文への読み修正: {unused[:2]}"
    q = json.load(open(f"{S}/queue.json", encoding="utf-8"))
    q = [x for x in q if x["id"] != tid]
    q.append(dict(work, kousei=k, yomi=ym))
    json.dump(q, open(f"{S}/queue.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"在庫に追加: {work['title']}（在庫 {len(q)} 本）")


if __name__ == "__main__":
    if sys.argv[1] == "check":
        do_check(sys.argv[2], sys.argv[3])
    else:
        do_push(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
