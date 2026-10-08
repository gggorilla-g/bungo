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
"""


def nazo_brand(work):
    title = work["title"]
    label = f"NAZO — {title}"
    return {
        "label": label,
        "part_label": PART_LABEL,
        "part_intro": PART_INTRO,
        "title_narr": lambda k: title + "。" + k.get("logline", ""),
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
        "thumb_label": "NAZO",
    }
