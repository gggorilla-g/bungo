# nazo/stock.py — チャット側（Claude）でNAZOの在庫を仕込む道具。Actionsでは使わない。
#   python nazo/stock.py check <題材ID> <台本.json>
#        … 事実照合の結果と、読み上げ文ごとのカナ（VOICEVOXが実際に読む音）を一覧
#   python nazo/stock.py push  <題材ID> <台本.json> [読み修正.json]
#        … 読み修正 {"原文の文": "読み上げ用テキスト"} を当てて在庫(queue)に積む
#          読みの関門（src/yomi_gate.py）に1件でも残れば積まない（2026-10-31〜）
#   python nazo/stock.py short <ショートID>
#        … ショート台本 nazo/shorts/<ID>.json の読みの関門（short2.py が読む文と同じ読み上げ文で）
# 台本の yomi_words {"語": "読み"} は固有名・読みが2通りある語の読みの明示。全文に当てる
import json, os, re, sys
sys.path.insert(0, "src"); sys.path.insert(0, "nazo")
import check, yomi, brand, yomi_gate

S = "nazo/state"


def sentences(k, work):
    """render.build_video が読み上げる文と同じ並び・同じ切り方"""
    out = [h["say"] for h in k.get("hook", [])]           # つかみ
    out += [brand.title_narr(work, k)]   # render が読む冒頭文と同じ
    for i, s in enumerate(k["sections"]):
        intro = brand.PART_INTRO.get(s["type"])
        first = (i == 0) or (k["sections"][i - 1]["type"] != s["type"])
        narr = (intro + s["narration"]) if (intro and first) else s["narration"]
        out += yomi.split_sentences(narr)   # render.build_video と同じ区切り方
    if k.get("host_intro"):                                 # ホー博士の名乗りと締め
        out += yomi.split_sentences(k["host_intro"])
    out += yomi.split_sentences(k.get("host_outro") or brand.HOST_OUTRO)
    out += [c["say"] for s in k["sections"] for c in s.get("cutins", [])]   # ホー博士のカットイン
    return list(dict.fromkeys(out))


def words_fix(t, k):
    """台本の yomi_words を長い語から順に当てる"""
    for w, r in sorted(k.get("yomi_words", {}).items(), key=lambda x: -len(x[0])):
        t = t.replace(w, r)
    return t


def gate(pairs, k):
    """読みの関門。台本の yomi_ok（食い違いを確認してVOICEVOX側が正しいと判断した文）は通す"""
    ok = set(k.get("yomi_ok", []))
    issues = yomi_gate.check(pairs, k.get("yomi_words", {}), yomi.kana)
    return [x for x in issues if x.split("｜", 1)[1] not in {o[:50] for o in ok} | {o[:40] for o in ok}]


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
    fixes = json.load(open(f"nazo/drafts/{tid}_yomi.json", encoding="utf-8")) if os.path.exists(f"nazo/drafts/{tid}_yomi.json") else {}
    pairs = [(t, words_fix(fixes.get(t, t), k)) for t in sentences(k, _work(src))]
    for i, (t, y) in enumerate(pairs):
        print(f"[{i}] {t}\n     {yomi.kana(y)}")
    for x in gate(pairs, k):
        print("【読み要確認】", x)


def do_push(tid, kpath, fixpath=None):
    src, k = _load(tid, kpath)
    ok, errs = check.validate(k, src)
    assert ok, errs
    fixes = json.load(open(fixpath, encoding="utf-8")) if fixpath else {}
    work = _work(src)
    ym = {}
    for t in sentences(k, work):
        ym[t] = words_fix(fixes.get(t, t), k)
        if ym[t] != t:
            print("修正:", t[:24], "→", yomi.kana(ym[t]))
    bad = gate(list(ym.items()), k)
    if bad:
        for x in bad:
            print("【読み要確認】", x)
        raise SystemExit(f"読みの確認が済んでいない文が {len(bad)} 件。yomi_words か読み修正で直してから積む")
    unused = [f for f in fixes if f not in ym]
    assert not unused, f"台本に無い文への読み修正: {unused[:2]}"
    q = json.load(open(f"{S}/queue.json", encoding="utf-8"))
    q = [x for x in q if x["id"] != tid]
    q.append(dict(work, kousei=k, yomi=ym))
    json.dump(q, open(f"{S}/queue.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"在庫に追加: {work['title']}（在庫 {len(q)} 本）")


def do_short(sid):
    """short2.py と同じ読み上げ文（台本の yomi > 本編の読み修正 > そのまま、読点は詰める）で関門を通す"""
    sp = json.load(open(f"nazo/shorts/{sid}.json", encoding="utf-8"))
    fixes = {}
    if os.path.exists(f"nazo/drafts/{sp['main']}_yomi.json"):
        fixes = json.load(open(f"nazo/drafts/{sp['main']}_yomi.json", encoding="utf-8"))
    fixes.update(sp.get("yomi", {}))
    pairs = []
    for ln in sp["lines"]:
        y = fixes.get(ln["say"]) or yomi.base_fix(ln["say"], {"title": "", "author": ""}, {})
        if sp.get("tight", True):
            y = re.sub(r"[、,]", "", y)
        pairs.append((ln["say"], y))
        print(ln["say"], "\n    ", yomi.kana(y))
    bad = gate(pairs, sp)
    for x in bad:
        print("【読み要確認】", x)
    print("関門:", "合格" if not bad else f"{len(bad)} 件で止めた")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if sys.argv[1] == "short":
        do_short(sys.argv[2])
    elif sys.argv[1] == "check":
        do_check(sys.argv[2], sys.argv[3])
    else:
        do_push(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
