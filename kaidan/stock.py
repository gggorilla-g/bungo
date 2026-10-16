# kaidan/stock.py — チャット側（Claude）で怪談の在庫を仕込む道具。Actionsでは使わない。
#   python kaidan/stock.py check <作品ID>            … 検査と、読み上げ文ごとのカナ一覧
#   python kaidan/stock.py push  <作品ID> [読み修正.json]  … 在庫(kaidan/state/queue.json)に積む
#   台本は kaidan/drafts/<作品ID>.json、原作は kaidan/state/texts/<作品ID>.json
import json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "kaidan")
import yomi, brand, check


def load(wid):
    c = json.load(open(f"kaidan/state/texts/{wid}.json", encoding="utf-8"))
    k = json.load(open(f"kaidan/drafts/{wid}.json", encoding="utf-8"))
    work = dict(c["meta"], no=k["no"])
    return c, k, work


def sentences(k, work):
    out = [h["say"] for h in k.get("hook", [])]
    out += [f"第{brand.kansuji(work['no'])}話。{k.get('display_title', work['title'])}。"]
    out += yomi.split_sentences(brand.host_intro(work, k))
    for s in k["sections"]:
        out += yomi.split_sentences(s["narration"])
    out += yomi.split_sentences(brand.host_outro(work, k))
    return list(dict.fromkeys(out))


def words_fix(t, k):
    """台本の yomi_words（固有名の読み）を、長い語から順に当てる"""
    for w, r in sorted(k.get("yomi_words", {}).items(), key=lambda x: -len(x[0])):
        t = t.replace(w, r)
    return t


def run_check(wid):
    c, k, work = load(wid)
    print("検査:", check.validate(k, c))
    for i, t in enumerate(sentences(k, work)):
        f = yomi.base_fix(words_fix(t, k), c["meta"], c["ruby"])
        print(f"[{i}] {t}\n     {yomi.kana(f)}")


def push(wid, fixpath=None):
    c, k, work = load(wid)
    ok, why = check.validate(k, c)
    assert ok, why
    fixes = json.load(open(fixpath, encoding="utf-8")) if fixpath else {}
    ym = {}
    for t in sentences(k, work):
        ym[t] = fixes.get(t) or yomi.base_fix(words_fix(t, k), c["meta"], c["ruby"])
        if t in fixes:
            print("修正後:", ym[t], "→", yomi.kana(ym[t]))
    try:
        q = json.load(open("kaidan/state/queue.json", encoding="utf-8"))
    except FileNotFoundError:
        q = []
    q = [x for x in q if x["work_id"] != wid]
    q.append(dict(work, kousei=k, yomi=ym))
    q.sort(key=lambda x: x["no"])
    json.dump(q, open("kaidan/state/queue.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"在庫に追加: 第{work['no']}話 {work['title']}（在庫 {len(q)} 本）")


if __name__ == "__main__":
    if sys.argv[1] == "check":
        run_check(sys.argv[2])
    else:
        push(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
