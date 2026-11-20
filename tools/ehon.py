# ehon.py — 動く絵本（紙芝居の舞台 × 水彩の紙人形）
#   紙芝居の木の枠の中に、水彩で塗った紙人形（白いふち付きの切り抜き）を奥行きの違う層に並べ、
#   カメラをゆっくり寄せ・横に流して立体感を出す（視差）。ページは紙芝居のように横へ抜いて替える。
#   声：VOICEVOX:No.7（読み聞かせ）。音楽：オルゴール風の自作フレーズ。
#   使い方: python3 tools/ehon.py nazo/ehon/<id>.json            … 書き出し output/<id>.mp4
#           STILLS="1.5,8" python3 tools/ehon.py nazo/ehon/<id>.json … 確認用の絵だけ build_ehon/<id>_<秒>.jpg
#   台本: title / pages[]（bg・props・chars・lines）。絵の部品は SPRITES（下）か spec の "sprites" に図形で書く
import os, sys, re, json, math, wave, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ballsim import font, mtof

W, H, FPS, SR = 1080, 1920, 30, 48000
FX, FY, FW, FH = 60, 520, 960, 720          # 絵の窓（紙芝居の 4:3）
WORLD = 1240                                # 絵の世界の横幅（窓より広く、横に流せる）
B = "build_ehon"


# ---------------- 水彩 ----------------
def rngf(seed): return np.random.default_rng(seed)


def noise(h, w, scale, seed):
    """なめらかなノイズ（小さく作って拡大）"""
    r = rngf(seed); sh, sw = max(2, int(h / scale)), max(2, int(w / scale))
    a = (r.random((sh, sw)) * 255).astype(np.uint8)
    return np.asarray(Image.fromarray(a).resize((w, h), Image.BICUBIC), dtype=np.float32) / 255


_PAPER = {}
def paper(h, w):
    if (h, w) not in _PAPER:
        n = .6 * noise(h, w, 2, 7) + .4 * noise(h, w, 9, 8)
        _PAPER[(h, w)] = .93 + .07 * n
    return _PAPER[(h, w)]


def blur(a, r): return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), dtype=np.float32) / 255


def hexc(c):
    c = c.lstrip("#"); return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255


def wash(mask, color, seed, edge=.55, wob=6):
    """mask(0..1) に水彩を1層。ふちを揺らし、濃淡のむら・ふちのたまり・粒子を足す。戻り値 (濃さ0..1, 色)"""
    h, w = mask.shape
    m = blur(mask, wob * .8); m = np.clip((m + (noise(h, w, 18, seed) - .5) * .5 - .5) * 6 + .5, 0, 1)   # ふちの揺れ
    m = blur(m, 1.2)
    dens = .55 + .30 * (noise(h, w, 40, seed + 1) - .5) + .12 * (noise(h, w, 3, seed + 2) - .5)            # むら・粒子
    rim = np.clip(m - blur(m, 7), 0, 1) * 2.2                                                                # ふちのたまり
    return np.clip(m * (dens + edge * rim), 0, 1) * m, hexc(color)


def shape_mask(h, w, parts_draw):
    im = Image.new("L", (w, h), 0); d = ImageDraw.Draw(im); parts_draw(d)
    return np.asarray(im, dtype=np.float32) / 255


def draw_prim(d, p, ox=0, oy=0, s=1.0, fill=255):
    if "e" in p:
        cx, cy, rx, ry = [v * s for v in p["e"][:4]]; cx += ox; cy += oy; rot = p["e"][4] if len(p["e"]) > 4 else 0
        if rot:
            pts = [(cx + rx * math.cos(t) * math.cos(rot) - ry * math.sin(t) * math.sin(rot), cy + rx * math.cos(t) * math.sin(rot) + ry * math.sin(t) * math.cos(rot)) for t in np.linspace(0, 2 * np.pi, 72)]
            d.polygon(pts, fill=fill)
        else: d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill)
    elif "p" in p: d.polygon([(x * s + ox, y * s + oy) for x, y in p["p"]], fill=fill)
    elif "r" in p:
        x0, y0, x1, y1 = [v * s for v in p["r"]]; d.rectangle([x0 + ox, y0 + oy, x1 + ox, y1 + oy], fill=fill)
    elif "l" in p:
        d.line([(x * s + ox, y * s + oy) for x, y in p["l"]], fill=fill, width=max(1, int(p.get("w", 6) * s)), joint="curve")


def paint(parts, size, seed, cut=True, scale=1.0):
    """図形の部品を水彩で塗った RGBA 画像に。cut=True なら白い紙のふちと影を付けた紙人形にする"""
    w, h = int(size[0] * scale), int(size[1] * scale); pad = int(28 * scale) if cut else 0
    W2, H2 = w + 2 * pad, h + 2 * pad; pp = paper(H2, W2)
    out = np.ones((H2, W2, 3), np.float32) * pp[..., None]; alpha = np.zeros((H2, W2), np.float32)
    for i, p in enumerate(parts):
        m = shape_mask(H2, W2, lambda d: draw_prim(d, p, pad, pad, scale))
        if p.get("ink"):   # 目・鼻など：にじまない濃い線
            m = blur(m, .8); out = out * (1 - m[..., None]) + m[..., None] * hexc(p["c"]) * pp[..., None]; alpha = np.maximum(alpha, m); continue
        dn, col = wash(m, p["c"], seed * 31 + i, wob=max(2, 5 * scale))
        dn = dn * p.get("a", 1.0)
        out = out * (1 - dn[..., None] * (1 - col))                                                 # 絵の具を重ねる（下の色が透ける）
        alpha = np.maximum(alpha, np.clip(blur(m, 2) * 1.2, 0, 1))
    if cut:   # 紙人形：白いふち＋影
        border = np.clip(blur(alpha, 9 * scale) * 3, 0, 1); border = np.clip((border - .25) * 4, 0, 1)
        A = np.maximum(alpha, border)
        img = np.concatenate([np.clip(out, 0, 1), A[..., None]], 2)
    else:
        img = np.concatenate([np.clip(out, 0, 1), alpha[..., None]], 2)
    return Image.fromarray((img * 255).astype(np.uint8), "RGBA")


def shadowed(sprite, off=(8, 10), r=7, op=.35):
    """紙人形の下に落ちる影を付けた画像（少し大きくなる）"""
    a = sprite.split()[3]; pad = r * 3 + max(off)
    base = Image.new("RGBA", (sprite.width + 2 * pad, sprite.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", base.size, 0); sh.paste(a, (pad + off[0], pad + off[1])); sh = sh.filter(ImageFilter.GaussianBlur(r)).point(lambda v: int(v * op))
    base.paste(Image.new("RGBA", base.size, (40, 30, 50, 255)), (0, 0), sh); base.alpha_composite(sprite, (pad, pad)); return base, pad


# ---------------- 部品の図形（座標は部品の箱の中の px） ----------------
SPRITES = {
    "rabbit": {"size": [150, 210], "parts": [
        {"e": [52, 42, 13, 44, -.12], "c": "#f3ece4"}, {"e": [86, 40, 13, 44, .15], "c": "#f3ece4"},
        {"e": [52, 44, 6, 32, -.12], "c": "#f2b8c0", "a": .7}, {"e": [86, 42, 6, 32, .15], "c": "#f2b8c0", "a": .7},
        {"e": [72, 160, 52, 46], "c": "#efe6dc"}, {"e": [70, 100, 40, 36], "c": "#f3ece4"},
        {"e": [116, 172, 13, 12], "c": "#ffffff"}, {"e": [56, 96, 4, 5], "c": "#2b2430", "ink": 1}, {"e": [84, 96, 4, 5], "c": "#2b2430", "ink": 1},
        {"e": [70, 110, 4, 3], "c": "#d9788a", "ink": 1}, {"e": [48, 112, 8, 5], "c": "#f2a0ae", "a": .6}, {"e": [93, 112, 8, 5], "c": "#f2a0ae", "a": .6}]},
    "moon": {"size": [120, 120], "parts": [{"e": [60, 60, 52, 52], "c": "#f7e08a"}, {"e": [44, 48, 9, 8], "c": "#e8c868", "a": .6}, {"e": [74, 78, 12, 10], "c": "#e8c868", "a": .5}]},
    "tree": {"size": [220, 330], "parts": [{"r": [98, 200, 124, 330], "c": "#7a5a44"}, {"e": [110, 120, 96, 92], "c": "#3f6e5a"}, {"e": [70, 160, 60, 52], "c": "#4f8068"}, {"e": [150, 150, 62, 56], "c": "#37604f"}]},
    "house": {"size": [300, 300], "parts": [{"r": [40, 130, 260, 290], "c": "#e9c9a0"}, {"p": [[20, 140], [150, 30], [280, 140]], "c": "#b4584a"},
        {"r": [120, 200, 172, 290], "c": "#8a5a40"}, {"r": [196, 170, 240, 214], "c": "#f6dc84"}, {"r": [60, 170, 104, 214], "c": "#f6dc84"}]},
    "puddle": {"size": [240, 70], "parts": [{"e": [120, 35, 112, 28], "c": "#4c6a9a", "a": .8}]},
    "bucket": {"size": [110, 110], "parts": [{"p": [[14, 30], [96, 30], [84, 104], [26, 104]], "c": "#9a7a5a"}, {"e": [55, 32, 41, 10], "c": "#3f5f8f"}, {"l": [[14, 30], [55, -2], [96, 30]], "c": "#5a4a3a", "w": 4, "a": .9}]},
    "cloud": {"size": [300, 130], "parts": [{"e": [90, 80, 70, 44], "c": "#c9cfe0"}, {"e": [160, 60, 80, 54], "c": "#d4d9e8"}, {"e": [230, 84, 62, 40], "c": "#c3c9db"}]},
    "grass": {"size": [160, 70], "parts": [{"p": [[0, 70], [20, 10], [34, 70]], "c": "#5f8f5a"}, {"p": [[30, 70], [58, 0], [70, 70]], "c": "#4f7f4f"}, {"p": [[66, 70], [96, 18], [108, 70]], "c": "#6a9a60"}, {"p": [[104, 70], [130, 6], [146, 70]], "c": "#5a8a56"}]},
    "star": {"size": [40, 40], "parts": [{"p": [[20, 0], [25, 15], [40, 15], [28, 25], [33, 40], [20, 31], [7, 40], [12, 25], [0, 15], [15, 15]], "c": "#f7e7a0"}]},
}


# ---------------- 声・音 ----------------
def synth_lines(sp):
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
    A = "vv_assets"; v = sp.get("voice", {"vvm": "6.vvm", "style": 31, "speed": .9})
    ort = Onnxruntime.load_once(filename=f"{A}/voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3")
    s = Synthesizer(ort, OpenJtalk(f"{A}/open_jtalk_dic_utf_8-1.11"))
    with VoiceModelFile.open(f"{A}/{v['vvm']}") as m: s.load_voice_model(m)
    res = []
    for pi, pg in enumerate(sp["pages"]):
        for li, text in enumerate(pg["lines"]):
            p = f"{B}/{sp['id']}_v{pi:02d}_{li:02d}.wav"
            if not os.path.exists(p):
                say = re.sub(r"[ 　]", "", text)
                for k, r in sp.get("yomi", {}).items(): say = say.replace(k, r)
                q = s.create_audio_query(say, v["style"]); q.speed_scale = v.get("speed", .9); q.pre_phoneme_length = .15; q.post_phoneme_length = .35
                open(p, "wb").write(s.synthesis(q, v["style"]))
            with wave.open(p) as w: res.append((pi, li, p, w.getnframes() / w.getframerate(), w.getframerate()))
    return res


def bell(f, dur, sr=SR):
    t = np.arange(int(sr * dur)) / sr
    s = np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t * 4) + .15 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 9)
    return s * np.exp(-t * 2.2) * np.minimum(1, t / .004)


def musicbox(total, seed):
    """オルゴール風の自作フレーズ（ドレミソラ）。8小節を繰り返す"""
    r = rngf(seed); scale = [72, 74, 76, 79, 81, 84, 86, 88]; out = np.zeros(int(SR * (total + 3))); beat = .5
    mel = [int(r.integers(0, len(scale))) for _ in range(16)]
    for i in range(int(total / beat)):
        t = i * beat; m = scale[mel[i % 16]]; s = bell(mtof(m), 2.0) * .22; k = int(t * SR); out[k:k + len(s)] += s[:len(out) - k]
        if i % 4 == 0:
            s = bell(mtof(scale[mel[i % 16]] - 24), 2.5) * .16; out[k:k + len(s)] += s[:len(out) - k]
    return out


def swish(dur=.7, seed=3):
    """紙を引き抜くかすれ音（高めのノイズを山なりに）"""
    r = rngf(seed); n = r.standard_normal(int(SR * dur)); t = np.linspace(0, 1, len(n))
    n = np.convolve(n, np.ones(6) / 6, "same") - np.convolve(n, np.ones(60) / 60, "same")
    return n * np.sin(np.pi * t) ** 2 * .25


# ---------------- 舞台 ----------------
def frame_overlay():
    """紙芝居の木の舞台（窓の外側）と、外の暗い背景"""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    wood = np.zeros((H, W, 3), np.float32); g = noise(H, W, 6, 11)[:, :1]
    grain = .5 + .5 * np.sin(np.linspace(0, 1, W)[None, :] * 60 + noise(H, W, 30, 12) * 9) * .5 + g * .2
    wood[...] = hexc("#8a5a36") * (.8 + .25 * grain[..., None])
    m = np.zeros((H, W), np.float32); bx = 34
    m[FY - bx:FY + FH + bx, FX - bx:FX + FW + bx] = 1; m[FY:FY + FH, FX:FX + FW] = 0
    a = Image.fromarray((m * 255).astype(np.uint8)); woodim = Image.fromarray((np.clip(wood, 0, 1) * 255).astype(np.uint8)).convert("RGBA"); woodim.putalpha(a)
    im.alpha_composite(woodim); d = ImageDraw.Draw(im)
    d.rectangle([FX - bx, FY - bx, FX + FW + bx, FY + FH + bx], outline=(60, 38, 24, 255), width=4); d.rectangle([FX - 4, FY - 4, FX + FW + 4, FY + FH + 4], outline=(60, 38, 24, 255), width=6)
    return im


def outside_bg():
    a = np.zeros((H, W, 3), np.float32); y = np.linspace(0, 1, H)[:, None, None]
    a[...] = hexc("#1c1824") * (1 - y) + hexc("#2a2230") * y
    a *= (.9 + .1 * noise(H, W, 8, 21))[..., None]
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert("RGBA")


def backdrop(bg, seed):
    """空と地面を水彩で（ふちなし）。WORLD x FH"""
    h, w = FH, WORLD; pp = paper(h, w); out = np.ones((h, w, 3), np.float32) * pp[..., None]
    y = np.linspace(0, 1, h)[:, None]
    sky = np.ones((h, w), np.float32); c1, c2 = hexc(bg["sky"][0]), hexc(bg["sky"][1])
    dn = np.clip(.78 + .12 * (noise(h, w, 90, seed) - .5) + .05 * (noise(h, w, 3, seed + 1) - .5), 0, 1)[..., None]
    col = c1 * (1 - y[..., None]) + c2 * y[..., None]
    out = out * (1 - dn * (1 - col))
    for i, gnd in enumerate(bg.get("hills", [])):   # [高さ(0..1), 色, うねり]
        hy, c, amp = gnd; xs = np.arange(w)
        top = (hy + amp * np.sin(xs / w * 2 * np.pi * (1.3 + i * .7) + i * 2) + .02 * (noise(1, w, 40, seed + 9 + i)[0] - .5)) * h
        m = (np.arange(h)[:, None] > top[None, :]).astype(np.float32)
        d2, cc = wash(m, c, seed + 50 + i, edge=.4, wob=5); out = out * (1 - d2[..., None] * (1 - cc))
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).convert("RGBA")


def ease(x): x = min(1, max(0, x)); return x * x * (3 - 2 * x)


def keyval(k, u):
    """[[u, v], ...] を u で直線補間（ゆっくり）"""
    if not isinstance(k, list): return k
    if u <= k[0][0]: return k[0][1]
    for (a, va), (b, vb) in zip(k, k[1:]):
        if u <= b: f = ease((u - a) / (b - a)) if b > a else 1; return va + (vb - va) * f
    return k[-1][1]


def wrap(s, n=17):
    out, cur = [], ""
    for tok in re.split(r"(\s+)", s):
        if len(cur) + len(tok.strip()) > n and cur.strip(): out.append(cur.strip()); cur = tok.strip()
        else: cur += tok
    if cur.strip(): out.append(cur.strip())
    return out


def main(path):
    sp = json.load(open(path, encoding="utf-8")); sid = sp["id"]; os.makedirs(B, exist_ok=True); os.makedirs("output", exist_ok=True)
    stills = os.environ.get("STILLS"); stills = [float(x) for x in stills.split(",")] if stills else None
    spr = dict(SPRITES); spr.update(sp.get("sprites", {}))
    vo = synth_lines(sp)
    # 時間割
    GAP, PAD0, PAD1, TR = .45, 1.0, 1.1, .9
    pages, t = [], .6
    for pi, pg in enumerate(sp["pages"]):
        lines = [x for x in vo if x[0] == pi]; t0 = t; tl = t + PAD0; li_t = []
        for (_, li, p, d, sr) in lines: li_t.append((tl, d, p, pg["lines"][li])); tl += d + GAP
        t1 = tl - GAP + PAD1; pages.append(dict(t0=t0, t1=t1, lines=li_t)); t = t1 + TR
    total = pages[-1]["t1"] + 1.6
    # 絵を用意
    cache = {}
    def sprite(name, scale, seed):
        key = (name, round(scale, 3), seed)
        if key not in cache:
            s = spr[name]; im = paint(s["parts"], s["size"], seed, cut=s.get("cut", True), scale=scale)
            cache[key] = shadowed(im) if s.get("cut", True) else (im, 0)
        return cache[key]
    bgs = [backdrop(pg["bg"], 100 + i) for i, pg in enumerate(sp["pages"])]
    frame = frame_overlay(); outside = outside_bg()
    fT, fS = font(64), font(54)

    def picture(pi, u):
        """ページ pi の絵（窓サイズ）。u: ページ内の進み 0..1"""
        pg = sp["pages"][pi]; cam = pg.get("cam", {}); camx = keyval(cam.get("x", [[0, 0], [1, 120]]), u); zoom = keyval(cam.get("zoom", [[0, 1.0], [1, 1.06]]), u)
        world = bgs[pi].copy()
        items = []
        for k, it in enumerate(pg.get("props", []) + pg.get("chars", [])):
            z = it.get("z", 1.0); show = keyval(it.get("show", 1), u)
            if show <= .01: continue
            x, y = keyval(it["x"], u), keyval(it["y"], u)
            hop = it.get("hop"); dy = 0; rot = 0
            if hop and keyval(hop.get("on", 1), u) > .5: ph = u * hop.get("n", 4) % 1; dy = -abs(math.sin(math.pi * ph)) * hop.get("h", 30)
            sway = it.get("sway", 0)
            if sway: rot = math.sin(u * 2 * math.pi * it.get("sway_n", 2)) * sway
            items.append((z, it, x, y + dy, rot, show, k))
        items.sort(key=lambda a: a[0])
        layer = Image.new("RGBA", world.size, (0, 0, 0, 0)); out = world.copy()
        for z, it, x, y, rot, show, k in items:
            im, pad = sprite(it["s"], it.get("scale", 1.0) * sp.get("unit", 1.5), it.get("seed", k + 1))
            if it.get("flip"): im = im.transpose(Image.FLIP_LEFT_RIGHT)
            if rot: im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
            if show < 1: a = im.split()[3].point(lambda v: int(v * show)); im = im.copy(); im.putalpha(a)
            par = (z - 1.0) * camx * .8                                    # 手前ほど大きく動く（視差）
            out.alpha_composite(im, (int(x - im.width / 2 - par), int(y - im.height + pad)))
        # 窓に切り出し（カメラの横移動・寄り）
        vw, vh = FW / zoom, FH / zoom; cx = WORLD / 2 + camx - 60; cy = FH / 2 + (zoom - 1) * FH * .25
        box = (int(cx - vw / 2), int(cy - vh / 2), int(cx + vw / 2), int(cy + vh / 2))
        pic = out.crop(box).resize((FW, FH), Image.BICUBIC)
        # 舞台の明かり（周辺を少し落とす）
        return pic

    vig = Image.new("L", (FW, FH), 0); dv = ImageDraw.Draw(vig)
    for i in range(30): dv.rectangle([i * 6, i * 5, FW - i * 6, FH - i * 5], fill=int(255 * (1 - i / 30) * .5))
    vig = vig.filter(ImageFilter.GaussianBlur(40))
    dark = Image.new("RGBA", (FW, FH), (20, 12, 30, 255))

    def frame_at(t):
        im = outside.copy(); cur = 0
        for i, pg in enumerate(pages):
            if t >= pg["t0"]: cur = i
        pg = pages[cur]; u = (t - pg["t0"]) / max(.01, pg["t1"] - pg["t0"])
        pic = picture(cur, min(1, u))
        if t > pg["t1"] and cur + 1 < len(pages):   # 紙芝居の引き抜き：今の絵が左へ抜け、次の絵が出る
            k = ease((t - pg["t1"]) / TR); nxt = picture(cur + 1, 0)
            base = nxt.copy(); sx = int(-k * (FW + 40))
            sh = Image.new("RGBA", (FW, FH), (0, 0, 0, 0)); sh.paste((0, 0, 0, 110), (sx + FW - 2, 0, min(FW, sx + FW + 30), FH)); base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
            base.paste(pic, (sx, 0)); pic = base
        pic = Image.composite(pic, Image.alpha_composite(pic, Image.new("RGBA", pic.size, (20, 12, 30, 90))), vig)
        im.paste(pic, (FX, FY)); im.alpha_composite(frame)
        d = ImageDraw.Draw(im)
        tl = sp["title"]; w = d.textlength(tl, font=fT); d.text((W / 2 - w / 2, 300), tl, font=fT, fill=(250, 238, 214), stroke_width=4, stroke_fill=(30, 20, 26))
        for (ts, du, p, text) in pg["lines"]:
            if ts - .1 <= t <= ts + du + .35:
                for j, ln in enumerate(wrap(text)):
                    w = d.textlength(ln, font=fS); d.text((W / 2 - w / 2, FY + FH + 90 + j * 76), ln, font=fS, fill=(255, 255, 255), stroke_width=5, stroke_fill=(24, 16, 22))
        return im.convert("RGB")

    if stills:
        for s in stills: frame_at(s).save(f"{B}/{sid}_{s:06.2f}.jpg", quality=88)
        print("確認用の絵:", stills, "長さ", round(total, 1)); return
    raw = f"{B}/{sid}_v.mp4"
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", raw], stdin=subprocess.PIPE)
    for fi in range(int(total * FPS)): pr.stdin.write(frame_at(fi / FPS).tobytes())
    pr.stdin.close(); pr.wait()
    # 音
    n = int(SR * (total + 3)); voice = np.zeros(n); mb = musicbox(total, 5)[:n] * .5; fx = np.zeros(n)
    for pg in pages:
        for (ts, du, p, text) in pg["lines"]:
            with wave.open(p) as w: a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; sr = w.getframerate()
            if sr != SR: a = np.interp(np.arange(int(len(a) * SR / sr)) * sr / SR, np.arange(len(a)), a)
            k = int(ts * SR); voice[k:k + len(a)] += a[:n - k]
    for i, pg in enumerate(pages[:-1]):
        s = swish(seed=i); k = int(pg["t1"] * SR); fx[k:k + len(s)] += s
    # 動きの音：跳ねて着地するたびに木琴、ものが現れるときにきらきら
    def addn(t, f, g, dec=2.2):
        s_ = bell(f, 1.6) * g; k = int(t * SR)
        if 0 <= k < n: fx[k:k + len(s_)] += s_[:n - k]
    pent = [72, 74, 76, 79, 81]
    for pi, pg in enumerate(sp["pages"]):
        P = pages[pi]; dur = P["t1"] - P["t0"]
        for it in pg.get("props", []) + pg.get("chars", []):
            hop = it.get("hop")
            if hop:
                for j in range(1, int(hop.get("n", 4)) + 1):
                    u = j / hop.get("n", 4)
                    if keyval(hop.get("on", 1), u - .02) > .5: addn(P["t0"] + u * dur, mtof(pent[j % 5] - 12), .10)
            sh = it.get("show")
            if isinstance(sh, list):
                for (a0, v0), (a1, v1) in zip(sh, sh[1:]):
                    if v0 < .5 <= v1:
                        for q, m in enumerate([84, 88, 91, 96]): addn(P["t0"] + a0 * dur + q * .09, mtof(m), .12)
    # 声の間は音楽を下げる
    env = np.convolve(np.abs(voice) > .01, np.ones(SR // 4) / (SR // 4), "same"); mb = mb * (1 - .55 * np.clip(env * 3, 0, 1))
    mix = voice * 1.0 + mb + fx; mix = mix / (np.abs(mix).max() + 1e-9) * .9
    wv = f"{B}/{sid}.wav"
    with wave.open(wv, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-i", wv, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", f"output/{sid}.mp4"], check=True)
    print(f"書き出し: output/{sid}.mp4  {total:.1f}秒")


if __name__ == "__main__":
    main(sys.argv[1])
