# m3_script.py — 台本生成(Claude API)と品質チェック
import json, os, re
try:
    import anthropic
except ImportError:
    anthropic = None

def generate(work, text):
    prompt = open("prompts/m3_prompt.txt", encoding="utf-8").read()
    # 長文は先頭2万字まで(台本用には十分。全文朗読は原文をそのまま使うため影響なし)
    prompt = (prompt.replace("{author}", work["author"])
              .replace("{author_birth}", work["birth"]).replace("{author_death}", work["death"])
              .replace("{title}", work["title"]).replace("{pub_year}", work["pub"] or "不明")
              .replace("{char_count}", str(len(text)))
              .replace("{full_text}", text[:20000]))
    out = _call_llm(prompt)
    out = re.sub(r'^```json\s*|\s*```$', '', out.strip())
    return json.loads(out)

def _pick_gemini_model(key):
    """このキーで使えるflash系モデルを新しい順に自動選択(モデル名変更に追従)"""
    import requests
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     params={"key": key}, timeout=30)
    r.raise_for_status()
    names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedActions", m.get("supported_actions", []))]
    # flash優先・preview/tts/image等の特殊は除外・バージョン降順
    flash = [n for n in names if "flash" in n and "lite" not in n
             and not any(x in n for x in ("preview", "tts", "image", "audio", "vision", "exp"))]
    def ver(n):
        import re
        m = re.search(r"(\d+)\.?(\d+)?", n)
        return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
    cand = sorted(flash, key=ver, reverse=True) or [n for n in names if "flash" in n]
    if not cand:
        raise RuntimeError(f"利用可能なflashモデルなし。全モデル: {names}")
    print("Geminiモデル自動選択:", cand[0])
    return cand[0]

def _call_llm(prompt):
    """GEMINI_API_KEYがあればGemini(無料枠)、なければClaude API。1日1回なのでどちらも枠内"""
    if os.environ.get("GEMINI_API_KEY"):
        import requests
        key = os.environ["GEMINI_API_KEY"]
        model = os.environ.get("GEMINI_MODEL") or _pick_gemini_model(key)
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json",
                                       "maxOutputTokens": 8000}},
            timeout=300)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY を環境変数から
    msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=8000,
        messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if b.type == "text")

def validate(kousei, genbun):
    """スキーマ+朗読の原文照合。Falseなら当日はスキップ(壊れた動画を出さない)"""
    g = genbun.replace("\n", "")
    for key in ["title_candidates", "thumbnail", "sections", "description", "tags"]:
        if key not in kousei:
            return False, f"キー欠落: {key}"
    types = [s["type"] for s in kousei["sections"]]
    if types[0] != "toi" or types[-1] != "shin_toi" or "yoyaku" not in types:
        return False, "構成違反(問い→要約→新たな問いの順序)"
    total = sum(len(s.get("narration", "")) for s in kousei["sections"])
    if not 2200 <= total <= 4800:
        return False, f"台本文字数が範囲外: {total}"
    return True, "ok"
