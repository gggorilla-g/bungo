# nazo/brand.py — NAZOの見た目と言い回し。render.build_video(brand=...) に渡す。
# BUNGO(紺×金・明朝)と逆の、黒×赤・ゴシック。

PART_LABEL = {"toi": "謎", "jijitsu": "わかっていること", "setsu": "説", "shin_toi": "残る問い"}
# 事実と説の境目を、毎回声で宣言する（このチャンネルの約束事）
PART_INTRO = {"setsu": "ここから先は、説の話です。", "shin_toi": "最後に。"}

CSS = """
body { background:#111111; color:#ffffff; font-family:"Noto Sans CJK JP"; }
.scrim { background:rgba(0,0,0,{scrim}); }
.label { color:#bbbbbb; }
.rule { background:#c0392b; }
h1 { font-family:"Noto Sans CJK JP"; font-weight:900; letter-spacing:.04em; }
.credit { color:#999999; }
.label, .credit { text-shadow:0 2px 8px rgba(0,0,0,.95); }
.bg { background-size:contain; background-repeat:no-repeat; background-position:center; }
.subtitle { background:rgba(0,0,0,.62); padding:14px 36px; border-radius:8px; bottom:120px; }
"""


def title_narr(work, k):
    """冒頭で読み上げる文。チャンネル名→題材名→ひとこと"""
    return "世界の謎を10分解説。" + work["title"] + "。" + k.get("logline", "")


def nazo_brand(work):
    title = work["title"]
    label = f"世界の謎10分解説 — {title}"
    return {
        "label": label,
        "part_label": PART_LABEL,
        "part_intro": PART_INTRO,
        "title_narr": lambda k: title_narr(work, k),
        "title_card": (f'<div class="label">{label}</div><div class="rule"></div>'
                       f'<div class="center"><div>'
                       f'<div style="font-size:52px;color:#999999;text-align:center;'
                       f'margin-bottom:30px;letter-spacing:.2em;">未解決の謎を10分で</div>'
                       f'<h1 style="position:static;font-size:120px;text-align:center;">{title}</h1>'
                       f'</div></div>'
                       f'<div class="credit">参考：Wikipedia</div>'),
        "credit": "参考：Wikipedia　VOICEVOX:ずんだもん",
        "accent": "#c0392b",
        "css": CSS,
        "thumb_label": "世界の謎10分解説",
        "bgm": "assets/bgm_nazo_calming_seaside.mp3",
        "scrim": 0.12,          # 画像（写本のページ等）が見えるよう暗幕は薄く。字幕は自前の帯で読ませる
    }
