"""雑学ショートがテンプレ化していないかを、直前の雑学ショートと比べて確かめる。

使い方: python3 tools/variety_check.py nazo/shorts/<id>.json
直前の雑学ショートは nazo/shorts/queue.json の並び（channel が「雑学」）から取る。
問題があれば理由を出して終了コード1。

決めごと（2026-10-27、ゲンタ「毎回背景とかの構成は変えて、テンプレ化させない」）
- 背景の配色（themes）：直前の回と2つ以上かぶらない。最初の配色は直前の2回と別。
- 構成（format）：同じ構成を3回続けない。
- 冒頭（1行目と2行目の演出の種類）：直前の回と同じにしない。
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHORTS = os.path.join(ROOT, "nazo", "shorts")


def load(sid):
    p = os.path.join(SHORTS, sid + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def fx_types(ln):
    return [f.get("type") for f in (ln.get("fx") or [])]


def fmt(sp):
    """構成。台本に format があればそれ。なければ演出から推定する。"""
    if sp.get("format"):
        return sp["format"]
    ranks = sum(1 for ln in sp["lines"] if "rank" in fx_types(ln))
    if ranks >= 3:
        return "ranking"
    if any("vs" in fx_types(ln) or "split" in fx_types(ln) for ln in sp["lines"]):
        return "story_vs"
    return "story"


def opening(sp):
    return tuple(tuple(fx_types(ln)) for ln in sp["lines"][:2])


def themes(sp):
    seen = []
    for t in (sp.get("themes") or []) + [ln.get("theme") for ln in sp["lines"] if ln.get("theme")]:
        if t not in seen:
            seen.append(t)
    return seen


def main(path):
    sp = json.load(open(path))
    sid = os.path.splitext(os.path.basename(path))[0]
    q = json.load(open(os.path.join(SHORTS, "queue.json")))["items"]
    ids = [it["id"] for it in q if it.get("channel") == "雑学" and it["id"] != sid]
    if sid in [it["id"] for it in q]:                         # キューにある回は、その前の回とだけ比べる
        before = []
        for it in q:
            if it["id"] == sid:
                break
            if it.get("channel") == "雑学":
                before.append(it["id"])
        ids = before
    prev = [p for p in (load(i) for i in ids[-2:]) if p]
    probs = []
    th = themes(sp)
    if prev:
        last = prev[-1]
        common = set(th) & set(themes(last))
        if len(common) >= 2:
            probs.append(f"配色が直前の回と{len(common)}つかぶっている: {sorted(common)}")
        if th and th[0] in [themes(p)[0] for p in prev if themes(p)]:
            probs.append(f"最初の配色 {th[0]} が直前の2回と同じ")
        if opening(sp) == opening(last):
            probs.append(f"冒頭の演出が直前の回と同じ: {opening(sp)}")
    if len(prev) == 2 and fmt(prev[0]) == fmt(prev[1]) == fmt(sp):
        probs.append(f"構成「{fmt(sp)}」が3回続く")
    print(f"{sid}: 構成={fmt(sp)} 配色={th} 冒頭={opening(sp)}")
    for p in prev:
        print(f"  直前: 構成={fmt(p)} 配色={themes(p)}")
    for p in probs:
        print("  NG:", p)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
