# tools/channel_art.py — BUNGOのチャンネルアイコンとヘッダー画像を作る（動画と同じ紺×金・明朝）
import subprocess
from weasyprint import HTML

NAVY, GOLD = "#17335e", "#d9a520"

def png(html, w, h, out):
    css = f"@page {{ size:{w}px {h}px; margin:0 }} body {{ margin:0; width:{w}px; height:{h}px; background:{NAVY}; color:#fff; position:relative; overflow:hidden }}"
    HTML(string=f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{html}</body></html>").write_pdf("build/_a.pdf")
    subprocess.run(["pdftoppm", "-png", "-r", "96", "-singlefile", "build/_a.pdf", out.replace(".png", "")], check=True)

# アイコン 800x800（丸く切り抜かれる前提で、要素は中央60%に収める）
png(f"""<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center">
  <div style="font-family:'Noto Serif CJK JP';font-weight:900;font-size:420px;line-height:1">文</div>
  <div style="width:150px;height:10px;background:{GOLD};margin-top:28px"></div>
  <div style="font-family:'Noto Sans CJK JP';font-size:44px;letter-spacing:.35em;margin-top:26px;padding-left:.35em">BUNGO</div>
</div>""", 800, 800, "channel/icon.png")

# ヘッダー 2560x1440（全端末で見える中央 1546x423 に文字を収める）
png(f"""<div style="position:absolute;left:507px;top:508px;width:1546px;height:423px;display:flex;align-items:center;justify-content:center;gap:70px">
  <div style="font-family:'Noto Serif CJK JP';font-weight:900;font-size:230px;line-height:1">文</div>
  <div>
    <div style="font-family:'Noto Sans CJK JP';font-size:96px;letter-spacing:.3em;line-height:1">BUNGO</div>
    <div style="width:180px;height:8px;background:{GOLD};margin:34px 0 30px"></div>
    <div style="font-family:'Noto Serif CJK JP';font-size:58px;letter-spacing:.08em">名作文学を10分で読み解く</div>
    <div style="font-family:'Noto Sans CJK JP';font-size:36px;color:#cdd9ec;letter-spacing:.1em;margin-top:22px">火・木・土 21:00 更新</div>
  </div>
</div>""", 2560, 1440, "channel/banner.png")
print("ok")
