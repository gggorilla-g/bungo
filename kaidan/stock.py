# kaidan/stock.py — チャット側（Claude）で怪談の在庫を仕込む道具。Actionsでは使わない。
#   python kaidan/stock.py check <作品ID>            … 検査と、読み上げ文ごとのカナ一覧
#   python kaidan/stock.py push  <作品ID> [読み修正.json]  … 在庫(kaidan/state/queue.json)に積む
#   台本は kaidan/drafts/<作品ID>.json、原作は kaidan/state/texts/<作品ID>.json
import json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "kaidan")
import yomi, brand, check, yomi_gate


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


def gate(c, k, work, fixes=None):
    """読みの関門。固有名の読みの明示と、2エンジンの食い違いの確認が済んでいない文を返す"""
    fixes = fixes or {}
    pairs = [(t, fixes.get(t) or yomi.base_fix(words_fix(t, k), c["meta"], c["ruby"])) for t in sentences(k, work)]
    ok = set(k.get("yomi_ok", []))      # 食い違いを確認して、VOICEVOX側の読みで正しいと判断した文
    issues = yomi_gate.check(pairs, k.get("yomi_words", {}), yomi.kana)
    return [x for x in issues if x.split("｜", 1)[1] not in {o[:50] for o in ok} | {o[:40] for o in ok}]


def run_check(wid):
    c, k, work = load(wid)
    print("検査:", check.validate(k, c))
    for x in gate(c, k, work):
        print("【読み要確認】", x)
    for i, t in enumerate(sentences(k, work)):
        f = yomi.base_fix(words_fix(t, k), c["meta"], c["ruby"])
        print(f"[{i}] {t}\n     {yomi.kana(f)}")


def push(wid, fixpath=None):
    c, k, work = load(wid)
    ok, why = check.validate(k, c)
    assert ok, why
    fixes = json.load(open(fixpath, encoding="utf-8")) if fixpath else {}
    bad = gate(c, k, work, fixes)
    if bad:
        for x in bad:
            print("【読み要確認】", x)
        raise SystemExit(f"読みの確認が済んでいない文が {len(bad)} 件。直すか、確認して yomi_ok に入れてから積む")
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
