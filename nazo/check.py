# nazo/check.py — 台本の検査（Wikipedia事実照合）。BUNGOの「原文照合」を事実照合に置き換えたもの。
#
# 線引き（チャンネルの規約）:
#   事実 … 年代・数字・地名・固有名詞・「」引用は、取得したWikipedia本文（日英）に書かれているものだけ
#   説   … 解釈・仮説は自由に語ってよいが、必ず「〜という説」「〜と考える人もいる」の形。断定しない
#   人名 … 現存の人物・近年の研究者の名前は出さない（説は中身で語り、提唱者の名前は出さない）
# 機械で止められるもの（数字・カタカナ語・引用・構成・禁句）はここで止める。人名の線引きは台本を書く側の規約。
import json, re, sys

TYPES_ORDER = ["toi", "jijitsu", "setsu", "shin_toi"]
# 本文に無くても使ってよい一般的なカタカナ語（事実を足さない語だけ）
KATAKANA_OK = set("""
ページ ミステリー ルール ヒント パターン リズム イメージ ストーリー テーマ メッセージ システム
スケッチ ノート メモ コード パズル ゲーム ルート リスト データ グループ スタート ゴール
シンプル ポイント ケース タイプ バランス セット ライン レベル チーム プロ アマチュア
ニュース テレビ インターネット コンピューター ネット サイズ フレーズ キーワード テキスト
センチ メートル キロ グラム トン パーセント
""".split())
# 断定・煽り・誤情報を呼びやすい言い回し（使ったら不採用）
NG_PHRASES = ["真相は", "正体は", "ついに解明", "完全に解読", "間違いなく", "確実に", "宇宙人",
              "陰謀", "隠蔽", "衝撃の", "ヤバい", "閲覧注意"]
# 声（ちび式じい）の規約で禁止：差別・誹謗中傷・政治や宗教への攻撃。人や民族・宗教を貶める言葉は自動で止める
NG_RESPECT = ["野蛮", "未開", "土人", "劣った民族", "劣等", "邪教", "異教徒", "狂信", "呪われた民族",
              "原始的な民族", "愚かな", "下等"]


def _norm(t):
    return re.sub(r'[\s　、。，．・…―ー\-“”"\'()（）]', '', t)


def _narr(kousei):
    return "".join(h.get("say", "") + h.get("text", "") for h in kousei.get("hook", [])) + \
        "".join(s.get("narration", "") for s in kousei["sections"])


def validate(kousei, src):
    """src = {"text_ja":..., "text_en":...}。(ok, 理由リスト) を返す。理由が空なら合格"""
    errs = []
    for key in ["title_candidates", "thumbnail", "sections", "description", "tags", "logline"]:
        if key not in kousei:
            errs.append(f"キー欠落: {key}")
    if errs:
        return False, errs
    types = [s["type"] for s in kousei["sections"]]
    # 構成: 問い → わかっていること(1以上) → 説(2以上) → 残る問い
    if types[0] != "toi" or types[-1] != "shin_toi":
        errs.append("構成違反: 先頭はtoi、末尾はshin_toi")
    order = [TYPES_ORDER.index(t) if t in TYPES_ORDER else -1 for t in types]
    if -1 in order or order != sorted(order):
        errs.append(f"構成違反: 並び順 {types}")
    if types.count("jijitsu") < 1 or types.count("setsu") < 2:
        errs.append("構成違反: jijitsu 1以上・setsu 2以上")
    for s in kousei["sections"]:
        if s["type"] == "setsu" and not re.search(r'説|考える人|見方|とも読める|主張', s["narration"]):
            errs.append(f"説パートに説であることの明示がない: {s.get('slide_heading')}")
        if len(s.get("slide_heading", "")) > 15:
            errs.append(f"見出しが15字超: {s.get('slide_heading')}")
    narr = _narr(kousei)
    total = len(narr)
    if not 2200 <= total <= 4300:
        errs.append(f"台本文字数が範囲外: {total}")

    ja, en = src.get("text_ja", ""), src.get("text_en", "")
    ja_n = _norm(ja)
    allt = ja + "\n" + en
    motion_txt = "\n".join("\n".join([str(b.get("label", "")), str(b.get("text", "")), str(b.get("region", ""))])
                           for s in kousei["sections"] for b in s.get("motion", []))
    alltxt = narr + kousei["logline"] + "".join(kousei["title_candidates"]) + \
        kousei["thumbnail"]["main_copy"] + "\n" + motion_txt
    host_txt = kousei.get("host_intro", "") + kousei.get("host_outro", "")
    # 1) 数字: 本文に無い数字は使わない（年号・寸法・ページ数の捏造を止める）
    nums_src = set(re.findall(r'\d+', allt.replace(",", "")))
    for n in sorted(set(re.findall(r'\d+', alltxt.replace(",", "")))):
        if n not in nums_src:
            errs.append(f"本文にない数字: {n}")
    # 2) カタカナ語(3字以上): 固有名詞の捏造を止める。中黒で区切られた名前は部分ごとに照合
    for w in sorted(set(re.findall(r'[ァ-ヴー]{3,}', alltxt))):
        if w in KATAKANA_OK or w in ja:
            continue
        errs.append(f"本文にないカタカナ語: {w}")
    # 3) 「」引用: 日本語版本文に一字一句
    for q in re.findall(r'「([^「」]{2,})」', narr):
        if _norm(q) not in ja_n:
            errs.append(f"本文にない引用: 「{q[:20]}」")
    # 4) 禁句
    for p in NG_PHRASES:
        if p in alltxt + host_txt:
            errs.append(f"禁句: {p}")
    for p in NG_RESPECT:
        if p in alltxt + host_txt + kousei.get("description", ""):
            errs.append(f"規約上の禁止語（差別・宗教への攻撃）: {p}")
    return (not errs), errs


if __name__ == "__main__":
    src = json.load(open(sys.argv[1], encoding="utf-8"))
    k = json.load(open(sys.argv[2], encoding="utf-8"))
    ok, errs = validate(k, src)
    print("合格" if ok else "不合格")
    for e in errs:
        print(" -", e)
