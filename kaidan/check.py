# kaidan/check.py — 怪談の台本の検査。不合格なら作らない（欠番にしてログだけ残す）。
# 守ること：
#  - 原作（青空文庫・権利切れ）がある話だけを語る。実話・実在の事件として語らない
#  - 実在の会社・人物・店を悪く言わない／実際の事件・事故をネタにしない／心霊スポットへ行くよう促さない
#  - 自傷の方法や、信じると実害が出る話（病気・災害の予言など）を入れない
#  - 差別・宗教への攻撃をしない（冥鳴ひまりの規約：公序良俗・第三者への不利益・特定の思想団体）
import re

KEYS = ["no", "display_title", "hook", "sections", "title_candidates", "thumbnail", "description", "tags"]

NG = [
    (r"実話|本当にあった|実際に起き|実際にあった事件|ノンフィクション", "実話として語っている"),
    (r"行ってみ|訪れてみ|確かめに行|肝試しに", "心霊スポットなどへ行くよう促している"),
    (r"自殺の方法|死に方を|首の吊り|手首を切", "自傷の方法に触れている"),
    (r"地震が起き|予言|ワクチン|陰謀", "信じると実害が出る話"),
    (r"株式会社|有限会社|\(株\)|（株）", "実在の会社名らしき語"),
]
NG_RESPECT = ["部落", "穢多", "非人", "キチガイ", "気違い", "めくら", "つんぼ", "おし", "かたわ", "土人", "邪教", "カルト"]


def _all_text(k):
    parts = [h.get("say", "") + h.get("text", "") for h in k.get("hook", [])]
    parts += [s.get("narration", "") + s.get("slide_heading", "") for s in k["sections"]]
    parts += [k.get("description", ""), " ".join(k.get("title_candidates", [])), k["thumbnail"].get("main_copy", "")]
    return "\n".join(parts)


def validate(k, src):
    errs = []
    for key in KEYS:
        if key not in k:
            errs.append(f"キー欠落: {key}")
    if errs:
        return False, errs
    total = sum(len(s["narration"]) for s in k["sections"])
    if not 2400 <= total <= 6500:
        errs.append(f"語りの文字数が範囲外: {total}")
    if not src or len(src.get("text", "")) < 500:
        errs.append("原作の本文が手元にない")
    txt = _all_text(k)
    for pat, why in NG:
        m = re.search(pat, txt)
        if m:
            errs.append(f"{why}: 「{m.group(0)}」")
    for w in NG_RESPECT:
        # 「おし」は「お知らせ」などに含まれるため、単独の語のときだけ
        if (w == "おし" and re.search(r"(?<![ぁ-ん])おし(?![ぁ-ん])", txt)) or (w != "おし" and w in txt):
            errs.append(f"差別につながる語: {w}")
    # 原作に出てこない固有名（カタカナ語）を足していないか（作り話の混入を防ぐ）
    body = src.get("text", "") if src else ""
    allow = {"ドラマ", "チャンネル"}
    for w in set(re.findall(r"[ァ-ヴー]{3,}", txt)):
        if w not in body and w not in allow:
            errs.append(f"原作にないカタカナ語: {w}")
    return (not errs), errs
