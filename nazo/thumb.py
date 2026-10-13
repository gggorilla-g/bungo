# nazo/thumb.py — NAZOのサムネイル（型を固定して毎回同じ品質で自動生成する）
#   左: 黒地に巨大な見出し（2行まで）。2行目は赤。上に「世界の謎を10分で解説」の赤帯、下に題材名
#   右: 実物の画像（写本・遺物・肖像など）を暗くせずに大きく
import base64, subprocess
from weasyprint import HTML

RED = "#d0281c"


def build(main_copy, subject, image_path, out_png):
    img = base64.b64encode(open(image_path, "rb").read()).decode() if image_path else ""
    lines = [l for l in main_copy.replace("、", "、\n").split("\n") if l.strip()][:2]
    if len(lines) == 1 and len(lines[0]) > 6:   # 1行で長いときは真ん中で割る
        h = len(lines[0]) // 2; lines = [lines[0][:h], lines[0][h:]]
    l1 = lines[0]; l2 = lines[1] if len(lines) > 1 else ""
    size = min(160, int(670 / max(len(l1), len(l2), 1)))   # 1行が左側の幅に必ず収まる大きさ
    html = f"""<html><head><meta charset="utf-8"><style>
@page {{ size: 1280px 720px; margin: 0; }}
body {{ margin:0; width:1280px; height:720px; position:relative; overflow:hidden;
       background:#0b0b0b; font-family:"Noto Sans CJK JP"; color:#fff; }}
.img {{ position:absolute; top:0; right:0; width:560px; height:720px;
        background:url(data:image/jpeg;base64,{img}) center/cover; }}
.fade {{ position:absolute; top:0; left:690px; width:140px; height:720px;
         background:linear-gradient(90deg,#0b0b0b,rgba(11,11,11,0)); }}
.band {{ position:absolute; top:46px; left:0; background:{RED}; padding:14px 34px 16px 48px;
         font-size:40px; font-weight:900; letter-spacing:.06em; }}
.copy {{ position:absolute; left:48px; top:{int(400 - size * 1.18)}px; width:720px; font-weight:900; line-height:1.18;
         font-size:{size}px; letter-spacing:-.01em; white-space:nowrap; }}
.copy .r {{ color:{RED}; }}
.subj {{ position:absolute; left:48px; bottom:52px; font-size:44px; font-weight:700;
         border-left:10px solid {RED}; padding-left:20px; color:#f2f2f2; }}
</style></head><body>
<div class="img"></div><div class="fade"></div>
<div class="band">世界の謎を10分で解説</div>
<div class="copy">{l1}<br><span class="r">{l2}</span></div>
<div class="subj">{subject}</div>
</body></html>"""
    HTML(string=html).write_pdf("build/_thumb.pdf")
    subprocess.run(["pdftoppm", "-png", "-r", "96", "-singlefile", "build/_thumb.pdf", out_png[:-4]], check=True)
