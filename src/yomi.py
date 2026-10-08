# yomi.py — 読み仮名の検査と修正（読み上げ前の関門）
#
# 方針: 読み上げる全文を、合成前にこの関門に通す。
#   1) 確定読みの差し込み : 作品名・作者名（青空文庫カタログの公式読み）と、
#                           作品のルビ（作品内で読みが一つに定まる2字以上の漢字語）
#   2) 実際の読みを取り出す: VOICEVOX(OpenJTalk)が読もうとしているカナを取得
#   3) 照合               : 原文(漢字)とカナをLLMに並べて見せ、誤読だけを指摘させる
#   4) 修正→再照合       : 指摘箇所をかなに置換して、もう一度2)3)を回す
#   5) 2周しても残る/判断保留がある → 例外。main.pyが当日を欠番にする（誤読で投稿しない）
#
# 人が聴かない前提なので、ここを通らない読み上げは存在させない。
import json, os, re

_oj = None
LEARNED = "state/yomi_learned.json"
KANJI = re.compile(r'[一-鿿々〆]')
BATCH = 30


def split_sentences(text):
    """字幕・読み上げの単位に分ける。「」の内側の句点では切らない（字幕に」だけ残るのを防ぐ）"""
    out, depth, cur = [], 0, ""
    for ch in text:
        cur += ch
        if ch in "「『": depth += 1
        elif ch in "」』": depth = max(0, depth - 1)
        quote_end = ch in "」』" and depth == 0 and (cur[-2:-1] in ("。", "？", "！")
                                                     or cur.lstrip()[:1] in ("「", "『"))
        if depth == 0 and (ch in "。？！" or quote_end):   # 文頭からの引用は、閉じ括弧で1枚にする
            out.append(cur.strip()); cur = ""
    if cur.strip():
        out.append(cur.strip())
    return [x for x in out if x]


def _openjtalk():
    global _oj
    if _oj is None:
        from voicevox_core.blocking import OpenJtalk
        _oj = OpenJtalk("vv_assets/open_jtalk_dic_utf_8-1.11")
    return _oj


def kana(text):
    """VOICEVOXが実際に読むカナ（モーラ列）。読点位置のポーズは「、」で表す。"""
    out = []
    for ap in _openjtalk().analyze(text):
        out.append("".join(m.text for m in ap.moras))
        if ap.pause_mora:
            out.append("、")
    return "".join(out)


def _kata(s):
    """読みはカタカナで差し込む（ひらがなで差すと直後の助詞「は」を「ハ」と読む誤動作が出るため。実測済み）"""
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def base_fix(text, work, ruby):
    """確定している読みを差し込む。差し込みは長い語から順に行い、部分一致の誤爆を防ぐ。"""
    fixed = {}
    if work.get("title_yomi"):
        fixed[work["title"]] = _kata(work["title_yomi"])
    if work.get("author_yomi"):
        fixed[work["author"]] = _kata(work["author_yomi"])
    for base, yomis in (ruby or {}).items():
        if len(base) >= 2 and all(KANJI.match(c) for c in base) and len(yomis) == 1:
            fixed.setdefault(base, _kata(next(iter(yomis))))
    for k in sorted(fixed, key=len, reverse=True):
        text = text.replace(k, fixed[k])
    return text


CHECK_PROMPT = """あなたは日本語の朗読校正者です。合成音声が以下の文を読み上げます。
各項目の src は読み上げる文（一部すでにかなに開いてある）、kana は合成音声が実際に読むカナです。
近代文学の解説動画で、誤読は致命傷になります。kana の誤読だけを指摘してください。

## 判定の基準
- 指摘するのは「明らかな誤読」：人名・作品名・地名の読み違い、熟語の読み違い（例：一途をイット）、
  文脈に合わない訓読み/音読み、数字の読み違い。
- 助詞の「は」「へ」は ワ/エ と読むのが正しい。助詞なのに ハ/ヘ と読んでいたら誤読として指摘する。
- 指摘しないもの：アクセント、長音表記（オオ/オウ等）、
  複数の正しい読みがありどちらも自然なもの（例：私=わたし/わたくし）。
- 作品のルビ（参考）: {hints}
  ルビにある語は、その読みが正しい。
- 自信がない語は fixes に入れず unsure に入れる。推測で直さない。

## 出力（JSONのみ。前置き・コードフェンス禁止）
{{"fixes": [{{"id": 項目番号, "before": "src中の該当箇所（前後の文字を含め、srcで一度しか出現しない長さにする）",
              "word": "誤読された語", "reading": "正しい読み(ひらがな)"}}],
 "unsure": [{{"id": 項目番号, "word": "判断できない語"}}]}}
誤読がなければ {{"fixes": [], "unsure": []}}。

## 項目
{items}
"""


def _ask(items, hints, llm):
    body = "\n".join(json.dumps({"id": i, "src": s, "kana": k}, ensure_ascii=False)
                     for i, (s, k) in items.items())
    out = llm(CHECK_PROMPT.format(hints=hints or "なし", items=body))
    out = re.sub(r'^```json\s*|\s*```$', '', out.strip())
    return json.loads(out)


def _hint_text(texts, ruby):
    joined = "".join(texts)
    pairs = [f"{b}={'/'.join(y)}" for b, y in (ruby or {}).items() if b in joined]
    return "、".join(pairs[:200])


def prepare(texts, work, ruby, llm):
    """読み上げる全テキストを受け取り {原文: 読み上げ用テキスト} を返す。
    誤読が解消しなければ RuntimeError（=当日は投稿しない）。"""
    uniq = list(dict.fromkeys(t for t in texts if t.strip()))
    if work.get("yomi"):
        # 在庫方式: チャットで検査済みの読みをそのまま使う。台本と1文でも食い違えば中止
        missing = [t for t in uniq if t not in work["yomi"]]
        if missing:
            raise RuntimeError(f"検査済みの読みがない文が{len(missing)}件: {missing[0][:30]}")
        return {t: work["yomi"][t] for t in uniq}
    tts = {t: base_fix(t, work, ruby) for t in uniq}
    hints = _hint_text(uniq, ruby)
    learned = []
    pending = list(uniq)  # かなだけの文も検査する（「かれは」を「カレハ」と読む例を実測）
    for rnd in range(2):
        if not pending:
            break
        next_pending, unsure = [], []
        for b in range(0, len(pending), BATCH):
            chunk = pending[b:b + BATCH]
            items = {i: (tts[t], kana(tts[t])) for i, t in enumerate(chunk)}
            res = _ask(items, hints, llm)
            for u in res.get("unsure", []):
                if 0 <= u.get("id", -1) < len(chunk):
                    unsure.append(f'{u.get("word")}（{chunk[u["id"]][:30]}…）')
            for f in res.get("fixes", []):
                i = f.get("id", -1)
                if not 0 <= i < len(chunk):
                    continue
                t = chunk[i]
                before, word, reading = f.get("before", ""), f.get("word", ""), f.get("reading", "")
                if not before or not word or not reading or tts[t].count(before) != 1 \
                        or word not in before:
                    unsure.append(f'{f.get("word")}（修正位置を特定できず）')
                    continue
                tts[t] = tts[t].replace(before, before.replace(word, _kata(reading), 1))
                learned.append({"word": f.get("word"), "reading": f.get("reading"),
                                "work": work.get("title")})
                if t not in next_pending:
                    next_pending.append(t)
        if unsure:
            raise RuntimeError("読み不確定のため投稿中止: " + " / ".join(unsure[:10]))
        pending = next_pending  # 直した文だけ、もう一周検査する
    if pending:
        raise RuntimeError(f"2周しても誤読が残る文が{len(pending)}件: 投稿中止")
    _save_learned(learned)
    return tts


def _save_learned(rows):
    if not rows:
        return
    try:
        cur = json.load(open(LEARNED, encoding="utf-8"))
    except Exception:
        cur = []
    cur.extend(rows)
    os.makedirs(os.path.dirname(LEARNED), exist_ok=True)
    json.dump(cur, open(LEARNED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
