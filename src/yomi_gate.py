# src/yomi_gate.py — 読み間違いの関門（チャット側で在庫に積む前に必ず通す。Actionsでは使わない）
# 2つの見張りで、怪しい読みを人（Claude）の確認に回す。確認が済むまで在庫に積めない。
#  1) 固有名（人名・地名・寺社名など）は、辞書の読みを信用しない。
#     台本の yomi_words（または verified 辞書）で読みを明示したものだけ通す。例「芳一」→ヨシカズ と読まれた事故
#  2) 2つの読み上げエンジン（VOICEVOXの読み と pyopenjtalk の読み）が食い違う文を全部出す。
#     例「殿」→シンガリ、「最後」→シマイ のような、片方だけが外す読みを拾う
import json, os, re, difflib

VERIFIED = os.path.join(os.path.dirname(__file__), "..", "state", "yomi_verified.json")
_V = None


def verified():
    global _V
    if _V is None:
        try:
            _V = json.load(open(VERIFIED, encoding="utf-8"))
        except FileNotFoundError:
            _V = {}
    return _V


VOWEL = {}
for row, v in (("アカサタナハマヤラワガザダバパァャ", "ア"), ("イキシチニヒミリギジヂビピィ", "イ"),
               ("ウクスツヌフムユルグズヅブプゥュヴ", "ウ"), ("エケセテネヘメレゲゼデベペェ", "エ"),
               ("オコソトノホモヨロヲゴゾドボポォョ", "オ")):
    for ch in row:
        VOWEL[ch] = v


def norm(kana):
    """2つのエンジンの書き方の差（長音・を・記号）をならす"""
    s = re.sub(r"[’'、。，．・！？\s　]", "", kana).replace("ヲ", "オ")
    out = []
    for ch in s:
        if ch == "ー" and out:
            out.append(VOWEL.get(out[-1], ""))
        else:
            out.append(ch)
    s = "".join(out)
    # 「ウ」と「オ」の長音のゆれ（トウ/トオ、ユウ/ユウ）は同じとみなす
    s = re.sub(r"(?<=[オコソトノホモヨロゴゾドボポョ])ウ", "オ", s)
    s = re.sub(r"(?<=[エケセテネヘメレゲゼデベペ])イ", "エ", s)
    return s


def proper_nouns(text):
    import pyopenjtalk
    out = []
    for f in pyopenjtalk.run_frontend(text):
        if f["pos_group1"] == "固有名詞" and re.search(r"[一-龥々]", f["string"]):
            out.append((f["string"], f["read"], f["pos_group2"]))
    return out


def pj_kana(text):
    import pyopenjtalk
    return "".join(f["pron"] for f in pyopenjtalk.run_frontend(text) if f["pos"] != "記号")


def check(pairs, words, vv_kana):
    """pairs = [(原文, 読み上げ用テキスト)]、words = 台本で読みを明示した語。vv_kana = VOICEVOXの読みを返す関数。
    戻り値: 問題のリスト（空なら合格）"""
    ok_words = set(words) | set(verified())
    issues = []
    for orig, tts in pairs:
        # 1) 固有名：読みが明示されていないもの（読み上げ用テキストに漢字のまま残っているもの）
        for w, r, kind in proper_nouns(tts):
            if w not in ok_words:
                issues.append(f"固有名（{kind}）の読みが未確認: {w}（辞書の読み {r}）｜{orig[:40]}")
        # 2) 2つのエンジンの食い違い
        a, b = norm(vv_kana(tts)), norm(pj_kana(tts))
        if a != b:
            sm = difflib.SequenceMatcher(None, a, b)
            diffs = [f"{a[i1:i2] or '∅'}/{b[j1:j2] or '∅'}" for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
            issues.append(f"読みが割れる [{' '.join(diffs)}]｜{orig[:50]}")
    return issues
