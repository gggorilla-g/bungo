# tools/dazai_art.py — 太宰治のPD写真（1936年）を、墨の線画＋薄い陰影のイラストにしてBUNGOのアイコンとヘッダーを作る
# 元写真: Commons "File:Dazai1936.jpg"（Public domain）。人物の切り抜きは rembg で作成 → channel/src_dazai/cut_06.png
import subprocess
import numpy as np
from PIL import Image, ImageFilter, ImageOps

PAPER = np.array([236, 230, 216], float)   # 生成り
INK = np.array([24, 32, 52], float)        # 紺がかった墨
NAVY, GOLD = (23, 51, 94), (217, 165, 32)

def illustrate(cut_png, scale=1.0):
    """写真を、墨の輪郭線＋平塗り3階調の版画風イラストにする。印刷写真の網点は先にならして消す"""
    from scipy import ndimage
    im = Image.open(cut_png).convert("RGBA")
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    a = np.asarray(im.split()[3], float) / 255
    lab, n = ndimage.label(a > .5)                       # 切り抜きのゴミ（離れた小片）を除く
    if n > 1:
        keep = 1 + int(np.argmax(ndimage.sum(np.ones_like(a), lab, range(1, n + 1))))
        a = a * ndimage.binary_dilation(lab == keep, iterations=3)
    g = im.convert("L").filter(ImageFilter.MedianFilter(9)).filter(ImageFilter.GaussianBlur(2.5 * scale))
    g = ImageOps.autocontrast(g, cutoff=1)
    gf = np.asarray(g, float) / 255
    inside = a > .5
    ys = np.where(inside.any(1))[0]
    head = inside.copy(); head[ys[0] + int((ys[-1] - ys[0]) * 0.30):] = False
    q = np.quantile(gf[head], [0.30, 0.62])             # 顔と髪の明暗で3段に分ける（白い着物に引っぱられないように）
    tone = np.where(gf < q[0], 0.92, np.where(gf < q[1], 0.42, 0.0))
    tone = np.asarray(Image.fromarray((tone * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5)), float) / 255
    # 輪郭線：人物の外形＋明暗の境目
    sm = ndimage.gaussian_filter(gf, 1.5)
    edge = np.hypot(ndimage.sobel(sm, 0), ndimage.sobel(sm, 1))
    line = np.clip((edge - 0.10) * 5, 0, 1)
    outline = np.clip(ndimage.gaussian_filter(np.hypot(ndimage.sobel(a, 0), ndimage.sobel(a, 1)), 1.0) * 1.6, 0, 1)
    ink = np.clip(np.maximum.reduce([tone, line * 0.85, outline]), 0, 1) * np.clip(a * 1.2, 0, 1)
    rng = np.random.default_rng(3)                       # 紙にのった墨のかすれ
    grain = np.asarray(Image.fromarray((rng.random(ink.shape) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0)), float) / 255
    ink = np.clip(ink * (0.9 + 0.2 * grain), 0, 1)
    return ink, a

def compose(ink, w, h, x, y, out, bg=PAPER):
    canvas = np.ones((h, w, 1)) * bg
    k = np.zeros((h, w))
    ih, iw = ink.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(w, x + iw), min(h, y + ih)
    k[y0:y1, x0:x1] = ink[y0 - y:y1 - y, x0 - x:x1 - x]
    img = canvas * (1 - k[..., None]) + INK * k[..., None]
    Image.fromarray(img.astype(np.uint8)).save(out)

def text_png(html, w, h, out):
    from weasyprint import HTML
    css = f"@page {{ size:{w}px {h}px; margin:0 }} body {{ margin:0; width:{w}px; height:{h}px; position:relative; overflow:hidden; background:transparent }}"
    HTML(string=f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{html}</body></html>").write_pdf("build/_t.pdf")
    subprocess.run(["pdftocairo", "-png", "-transp", "-r", "96", "-singlefile", "build/_t.pdf", out.replace(".png", "")], check=True)

if __name__ == "__main__":
    import os
    os.makedirs("build", exist_ok=True)
    src = "channel/src_dazai/cut_06.png"
    # ---- ヘッダー 2560x1440：中央の帯（1546x423、スマホでも見える範囲）に顔と文字 ----
    ink, a = illustrate(src, scale=0.95)
    ys = np.where(a.max(1) > .5)[0]; xs = np.where(a.max(0) > .5)[0]
    # 顔が帯の中に入るように：頭頂を帯の上端少し上に置く
    top = ys[0]
    W, H = 2560, 1440
    head_cx = int(np.where(a[top + 150] > .5)[0].mean())
    x = 900 - head_cx
    y = 508 - top + 6
    compose(ink, W, H, x, y, "build/banner_base.png")
    NAV = "#17335e"; GD = "#d9a520"
    text_png(f"""<div style="position:absolute;left:1330px;top:560px;width:800px;color:{NAV}">
      <div style="font-family:'Noto Sans CJK JP';font-size:92px;letter-spacing:.3em;line-height:1">BUNGO</div>
      <div style="width:160px;height:7px;background:{GD};margin:30px 0 28px"></div>
      <div style="font-family:'Noto Serif CJK JP';font-size:54px;letter-spacing:.06em">名作文学を10分で読み解く</div>

      </div>""", W, H, "build/banner_text.png")
    base = Image.open("build/banner_base.png").convert("RGBA")
    base.alpha_composite(Image.open("build/banner_text.png").convert("RGBA"))
    base.convert("RGB").save("channel/banner.png")
    # ---- アイコン 800x800：顔の寄り ----
    ink2, a2 = illustrate(src, scale=1.0)
    ys2 = np.where(a2.max(1) > .5)[0]
    face_cx = int(np.where(a2[ys2[0] + 250] > .5)[0].mean())
    compose(ink2, 800, 800, 400 - face_cx, 90 - ys2[0], "channel/icon.png")
    print("ok")
