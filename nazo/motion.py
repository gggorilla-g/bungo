# nazo/motion.py — 冒頭（最初のセクション）を「動く図解＋案内役が解説する」映像にする
#
# 1文 = 1セグメント（render.py と同じ単位）。背景を「ビート」で動かし、その上に
# 見出し・字幕のオーバーレイ（静止PNG）と、口パクする案内役（owl.py）を重ねる。
#
# 台本のセクションに "motion": [{"at": "語", "type": ..., ...}, ...] を書くと、
# その語を含む文から、そのビートに切り替わる（画像指定の "at" と同じ考え方）。
#   type="photo"  file=画像          ゆっくり寄る（Ken Burns）。zoom=[cx,cy,幅] で寄り先を指定可
#   type="map"    lat, lon, label, span(度)   地図が寄っていき、ピンが落ちて地名の札が出る
#   type="year"   year, label         年号が数えあがって止まる（背景は直前の画像を暗く）
#   type="size"   file, label         実物の画像に寸法の矢印が伸び、数値の札が出る
#   type="words"  text                大きな語を箱に入れて出す（背景は直前の画像）
# ビートの指定がない文は、セクションの画像を photo として動かす。
import json, math, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

import owl as owlmod

FPS = 24
W, H = 1920, 1080
RED, YELLOW, WHITE, BLACK = (192, 57, 43), (255, 226, 0), (255, 255, 255), (0, 0, 0)
OWL_SIZE = 380
OWL_POS = (W - OWL_SIZE - 30, H - OWL_SIZE + 20)


# ---------- 文字 ----------
_fc = {}
def font(size, weight="Black"):
    key = (size, weight)
    if key not in _fc:
        for name in (f"Noto Sans CJK JP:style={weight}", "Noto Sans CJK JP:style=Bold", "Noto Sans CJK JP"):
            r = subprocess.run(["fc-match", "-f", "%{file}|%{index}", name], capture_output=True, text=True).stdout
            if "CJK" in r:
                p, i = r.split("|"); _fc[key] = ImageFont.truetype(p, size, index=int(i or 0)); break
        else:
            _fc[key] = ImageFont.load_default()
    return _fc[key]


def box_text(d, x, y, text, f, fg, bg, padx=28, pady=14, anchor="lt"):
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    w, h = r - l + padx * 2, b - t + pady * 2
    if anchor == "ct":
        x -= w // 2
    d.rectangle([x, y, x + w, y + h], fill=bg)
    d.text((x + padx - l, y + pady - t), text, font=f, fill=fg)
    return w, h


def ease(t):  # 0→1 なめらか
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)


def back(t):  # 少し行き過ぎて戻る（ポップ）
    t = max(0.0, min(1.0, t)); c = 1.7
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


# ---------- 画像の下地 ----------
def stage(path, scale=1.25):
    """画像を画面に収め（contain）、余白は同じ画像をぼかして埋めた下地。寄れるよう少し大きく作る"""
    w, h = int(W * scale), int(H * scale)
    src = ImageOps.exif_transpose(Image.open(path))
    if src.mode in ("RGBA", "LA", "P"):
        src = src.convert("RGBA"); base = Image.new("RGBA", src.size, (34, 30, 28, 255))
        base.alpha_composite(src); src = base
    src = src.convert("RGB")
    bg = ImageOps.fit(src, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    fg = ImageOps.contain(src, (w, h), Image.LANCZOS)
    fg = ImageEnhance.Contrast(fg).enhance(1.08)
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    return bg, ((w - fg.width) / 2 / w, (h - fg.height) / 2 / h, fg.width / w, fg.height / h)


def view(canvas, cx, cy, zoom):
    """canvas の点(cx,cy：0〜1)を中心に、zoom倍で切り出して画面サイズにする（zoom=1で全体）"""
    cw, ch = canvas.size
    vw, vh = cw / zoom, ch / zoom
    x = min(max(0, cx * cw - vw / 2), cw - vw)
    y = min(max(0, cy * ch - vh / 2), ch - vh)
    return canvas.resize((W, H), Image.BILINEAR, box=(x, y, x + vw, y + vh))


# ---------- 地図 ----------
_land = None
def land():
    global _land
    if _land is None:
        d = json.load(open("assets/geo/ne_10m_land.geojson"))
        rings = []
        for f in d["features"]:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            for poly in polys:
                r = np.array(poly[0], float)
                rings.append((r, r[:, 0].min(), r[:, 0].max(), r[:, 1].min(), r[:, 1].max()))
        _land = rings
    return _land


def draw_map(lat0, lon0, span, size=(W, H)):
    """lon方向 span 度が画面幅になる地図（海=紺、陸=生成り）"""
    w, h = size
    k = math.cos(math.radians(lat0))
    sx = w / span
    half_lon = span / 2; half_lat = (h / sx) / 2
    im = Image.new("RGB", size, (22, 40, 64))
    d = ImageDraw.Draw(im)
    for r, x0, x1, y0, y1 in land():
        if x1 < lon0 - half_lon / k * 1.05 or x0 > lon0 + half_lon / k * 1.05 or y1 < lat0 - half_lat or y0 > lat0 + half_lat:
            continue
        pts = np.column_stack(((r[:, 0] - lon0) * k * sx + w / 2, -(r[:, 1] - lat0) * sx + h / 2))
        if len(pts) > 3:
            d.polygon([tuple(p) for p in pts], fill=(222, 210, 180), outline=(150, 135, 105))
    # 経緯線（うすく）
    for lon in range(int(lon0 - 40), int(lon0 + 40)):
        if lon % 5 == 0:
            x = (lon - lon0) * k * sx + w / 2
            if 0 <= x <= w: d.line([(x, 0), (x, h)], fill=(40, 62, 92), width=1)
    for lat in range(int(lat0 - 40), int(lat0 + 40)):
        if lat % 5 == 0:
            y = -(lat - lat0) * sx + h / 2
            if 0 <= y <= h: d.line([(0, y), (w, y)], fill=(40, 62, 92), width=1)
    return im


# ---------- ビート ----------
class Beat:
    def __init__(self, spec, img_path, prev_canvas=None):
        self.s, self.img, self.prev = spec, img_path, prev_canvas
        t = spec.get("type", "photo")
        self.type = t
        if t in ("photo", "size", "year", "words"):
            path = spec.get("path") or img_path
            self.canvas, self.box = stage(path) if path else (Image.new("RGB", (int(W * 1.25), int(H * 1.25)), (12, 12, 12)), (0, 0, 1, 1))
        if t == "map":
            self.wide = draw_map(spec["lat"], spec["lon"], spec.get("span", 4) * 6)
            self.close = draw_map(spec["lat"], spec["lon"], spec.get("span", 4))
        self.point = t in ("map", "size", "year")

    def frame(self, t, dur):
        s = self.s
        if self.type == "photo":
            z = s.get("zoom")
            if z:  # 指定の場所へ寄る
                cx0, cy0 = 0.5, 0.5
                bx, by, bw, bh = self.box
                cx1, cy1 = bx + z[0] * bw, by + z[1] * bh
                z1 = max(1.0, 1.0 / max(0.15, z[2] * bw))
                e = ease(t / min(dur, 2.2))
                return view(self.canvas, cx0 + (cx1 - cx0) * e, cy0 + (cy1 - cy0) * e, 1 + (z1 - 1) * e)
            p = t / max(dur, 0.01)
            return view(self.canvas, 0.5 + 0.03 * p, 0.5, 1.0 + 0.10 * p)  # ゆっくり寄る
        if self.type == "map":
            e = ease(t / 1.4)
            # 広域→寄りをクロスフェードしながら拡大
            a = view(self.wide, 0.5, 0.5, 1 + 5 * e)
            im = Image.blend(a, self.close, ease((t - 0.6) / 0.8)) if t > 0.6 else a
            d = ImageDraw.Draw(im)
            if t > 1.3:  # ピンが落ちる
                pt = min(1, (t - 1.3) / 0.35)
                px, py = W // 2, int(H // 2 - 260 * (1 - back(pt)))
                for r in range(3):  # 波紋
                    rr = int(((t - 1.6) * 60 + r * 40) % 120) if t > 1.6 else 0
                    if rr: d.ellipse([W // 2 - rr, H // 2 - rr * 0.5, W // 2 + rr, H // 2 + rr * 0.5], outline=RED, width=4)
                d.ellipse([px - 26, py - 86, px + 26, py - 34], fill=RED, outline=BLACK, width=4)
                d.polygon([(px - 20, py - 50), (px + 20, py - 50), (px, py)], fill=RED, outline=BLACK)
                d.ellipse([px - 9, py - 69, px + 9, py - 51], fill=WHITE)
            if t > 1.7 and s.get("label"):
                f = font(64)
                box_text(d, W // 2, H // 2 + 30, s["label"], f, BLACK, YELLOW, anchor="ct")
            if t > 0.2 and s.get("region"):
                f_ = font(44); w_ = int(f_.getlength(s["region"])) + 56
                box_text(d, W - 100 - w_, 170, s["region"], f_, WHITE, BLACK)
            return im
        if self.type == "year":
            im = ImageEnhance.Brightness(view(self.canvas, 0.5, 0.5, 1.02)).enhance(0.45)
            d = ImageDraw.Draw(im)
            y1 = int(s["year"]); y0 = y1 - int(s.get("from", 120 if y1 > 0 else -120))
            e = ease(t / 1.0)
            v = round(y0 + (y1 - y0) * e)
            txt = (f"紀元前{-v}年" if v < 0 else f"{v}年") if not s.get("text") or e < 1 else s["text"]
            base = 170
            while base > 60 and font(base).getlength(txt) > W - 560:
                base -= 6
            f = font(int(base * (0.9 + 0.1 * back(min(1, t / 0.4)))))
            box_text(d, (W - 380) // 2, 330, txt, f, BLACK, YELLOW, 40, 20, anchor="ct")
            if s.get("label") and t > 0.9:
                box_text(d, (W - 380) // 2, 600, s["label"], font(64), WHITE, BLACK, anchor="ct")
            return im
        if self.type == "size":
            im = view(self.canvas, 0.5, 0.5, 1.0)
            d = ImageDraw.Draw(im)
            bx, by, bw, bh = self.box
            # span=[左端x, 右端x, 高さy]（画像に対する割合）で、測る位置を指定する
            sp = s.get("span", [0.1, 0.9, 0.5])
            x0 = (bx + sp[0] * bw) * W; x1 = (bx + sp[1] * bw) * W
            yy = (by + sp[2] * bh) * H
            e = ease((t - 0.2) / 0.8)
            if s.get("axis", "x") == "x":
                cx = (x0 + x1) / 2; half = (x1 - x0) / 2 * e
                d.line([(cx - half, yy), (cx + half, yy)], fill=BLACK, width=16)
                d.line([(cx - half, yy), (cx + half, yy)], fill=YELLOW, width=8)
                for sx_, dirn in ((cx - half, 1), (cx + half, -1)):
                    d.polygon([(sx_, yy), (sx_ + 28 * dirn, yy - 16), (sx_ + 28 * dirn, yy + 16)], fill=YELLOW)
                    d.line([(sx_, yy - 40), (sx_, yy + 40)], fill=YELLOW, width=6)
                if t > 0.9:
                    box_text(d, int(cx), int(yy) - 140, s["label"], font(72), BLACK, YELLOW, anchor="ct")
            return im
        if self.type == "words":
            im = ImageEnhance.Brightness(view(self.canvas, 0.5, 0.5, 1.04)).enhance(0.5)
            d = ImageDraw.Draw(im)
            lines = s["text"].split("\n")
            y = 300
            for i, l in enumerate(lines):
                e = back(min(1, max(0, (t - i * 0.25) / 0.35)))
                if e <= 0: continue
                f = font(110)
                fg, bg = (WHITE, BLACK) if i == 0 and len(lines) > 1 else (BLACK, YELLOW)
                x = int(-900 + (900 + 120) * e)
                w_, h_ = box_text(d, x, y, l, f, fg, bg, 34, 18)
                y += h_ + 18
            return im
        return Image.new("RGB", (W, H))


# ---------- 案内役 ----------
_owl_cache = {}
def owl_img(eyes, beak, wing):
    k = (eyes, beak, wing)
    if k not in _owl_cache:
        _owl_cache[k] = owlmod.owl(eyes, beak, wing, size=OWL_SIZE)
    return _owl_cache[k]


def mouth_track(wav_path, n):
    """フレームごとに口を開けるか（声の大きさ）"""
    with wave.open(wav_path) as w:
        sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
        if w.getnchannels() > 1: x = x[::w.getnchannels()]
    hop = sr // FPS
    out = []
    for i in range(n):
        seg = x[i * hop:(i + 1) * hop]
        out.append(float(np.sqrt((seg ** 2).mean())) if len(seg) else 0.0)
    thr = 0.035
    op = [r > thr for r in out]
    # 開きっぱなしにならないよう、3フレームごとに一度閉じる
    return [o and (i % 4 != 3) for i, o in enumerate(op)]


def owl_frame(i, talk, point, seed=0):
    t = i / FPS
    # まばたき：約3.7秒ごとに3フレーム
    ph = (i + seed * 17) % 89
    eyes = "half" if ph in (0, 2) else ("closed" if ph == 1 else "open")
    beak = "open" if talk else "closed"
    wing = "point" if point else "rest"
    o = owl_img(eyes, beak, wing)
    bob = int(5 * math.sin(t * 2 * math.pi / 1.6))
    return o, (OWL_POS[0], OWL_POS[1] + bob)


# ---------- 1セグメント書き出し ----------
def render_segment(out_mp4, dur, wav_path, beat, overlay_png, talk_owl=True, seed=0, t_offset=0.0):
    n = int(round(dur * FPS))
    mouth = mouth_track(wav_path, n) if talk_owl else [False] * n
    ov = Image.open(overlay_png).convert("RGBA").resize((W, H)) if overlay_png else None
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                          "-pix_fmt", "yuv420p", "-an", out_mp4], stdin=subprocess.PIPE)
    for i in range(n):
        t = i / FPS + t_offset
        bg = beat.frame(t, dur + t_offset).convert("RGBA")
        if ov is not None:
            bg.alpha_composite(ov)
        o, pos = owl_frame(i, mouth[i], beat.point and 0.6 < t < 3.2, seed)
        bg.alpha_composite(o, pos)
        p.stdin.write(bg.convert("RGB").tobytes())
    p.stdin.close(); p.wait()
    if p.returncode:
        raise RuntimeError("ffmpeg failed")
    return n / FPS
