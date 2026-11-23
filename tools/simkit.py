import math
# simkit.py — シミュレーション・ショートの共通部品
#   背景・光る線・軌跡の重ね描き（消さない）・小さいボール・問いのタイトルと数だけの文字・1個ずつ鳴る音・書き出し
#   ハウスルール（オーナーの指摘）: ボールは小さく／速すぎない／途中で止めない／増え方はゆっくり／
#     ボール1個ごとに音／軌跡は残す／余計な文字は入れない／低い衝撃音は使わない
#   確認用: STILLS="3,12.5,30" を付けて実行すると、その時刻の絵だけ build_ballsim/<id>_<秒>.jpg に出す（動画と音は作らない）
import re, os, sys, math, json, subprocess, wave
import numpy as np
import harmony
from PIL import Image, ImageDraw, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ballsim import WALL, WALL_GLOW, W, H, FPS, hsv, font, SR, mtof

S = int(os.environ.get("SIM_S", "2"))  # 2倍で描いて縮める（長尺は1で速く）
BALL_K = float(os.environ.get("SIM_BALL_K", "1"))   # 玉の大きさの倍率（11/22 オーナー：伸びた放物線・楕円の大きさを基準に戻す）
BALL_MAX = float(os.environ.get("SIM_BALL_MAX", "99"))   # 玉の半径の上限px（指定したときだけ効く）
MAX_MIDI = int(os.environ.get("SIM_MAX_MIDI", "127"))   # 音の高さの上限（指定したときだけ。81 = A5）
SOFT_LP = os.environ.get("SIM_SOFT_LP", "0") == "1"   # 高音をやわらげるローパス（指定したときだけ）
FLASH_MAX = float(os.environ.get("SIM_FLASH_MAX", "999"))
PENTA = [m for o in (60, 72) for m in (o, o + 2, o + 4, o + 5, o + 7, o + 9, o + 11)] + [84, 86]  # ドレミファソラシド（2オクターブ＋2音、16音。名前は互換のため PENTA のまま）


def dim(c, g): return tuple(int(v * g) for v in c)


_F = {}
def F(sz):
    """文字の大きさごとに1回だけ読み込む"""
    sz = int(sz)
    if sz not in _F: _F[sz] = font(sz)
    return _F[sz]


class Sim:
    def __init__(self, sp, box, area=(.06, .225, .94, .80)):
        self.mel = [] if sp.get("melody") else None   # "melody": "canon" = 当たるたびにカノンの旋律が1音進む
        """box: 図の範囲 (xmin, ymin, xmax, ymax)。area: 画面のどこに収めるか（左・上・右・下の割合）。数は上、図は中央（下2割は投稿画面の文字とかぶるので空ける）"""
        self.sp, self.id = sp, sp["id"]
        l, t, r, b = area; x0, y0, x1, y1 = box
        self.k = min((r - l) * W * S / (x1 - x0), (b - t) * H * S / (y1 - y0))
        self.cx, self.cy, self.mx, self.my = (l + r) / 2 * W * S, (t + b) / 2 * H * S, (x0 + x1) / 2, (y0 + y1) / 2
        bg = Image.new("RGB", (W * S, H * S), (6, 8, 20)); d = ImageDraw.Draw(bg)
        for k in range(0, H * S, 8):
            c = int(6 + 10 * (k / (H * S))); d.rectangle([0, k, W * S, k + 8], fill=(c // 2, c // 2 + 2, c + 10))
        self.bg = bg; self.acc = Image.new("RGB", (W * S, H * S)); self.notes = []; self.proc = None
        st = os.environ.get("STILLS"); self.stills = [float(x) for x in st.split(",")] if st else None
        os.makedirs("build_ballsim", exist_ok=True); os.makedirs("output", exist_ok=True)

    def to(self, p): return (self.cx + (p[0] - self.mx) * self.k, self.cy - (p[1] - self.my) * self.k)

    # ---- 動かない絵（背景に焼く）
    def neon(self, pts, closed=False, color=None, glow=None, width=9):
        color, glow = color or WALL, glow or WALL_GLOW
        P = [self.to(p) for p in pts]
        if closed: P = P + [P[0]]
        q = 4; g = Image.new("RGB", (W * S // q, H * S // q)); gd = ImageDraw.Draw(g)
        gd.line([(x / q, y / q) for x, y in P], fill=glow, width=max(1, int(26 * S / q * width / 9)), joint="curve")
        g = g.filter(ImageFilter.GaussianBlur(28 * S / q * width / 9)).resize((W * S, H * S), Image.BILINEAR)
        self.bg = ImageChops.add(self.bg, g); ImageDraw.Draw(self.bg).line(P, fill=color, width=int(width * S), joint="curve")

    def thin(self, pts, color=(60, 84, 110), width=2, closed=False):
        P = [self.to(p) for p in pts]
        if closed: P = P + [P[0]]
        ImageDraw.Draw(self.bg).line(P, fill=color, width=int(width * S), joint="curve")

    def ring(self, p, r=12, color=(255, 200, 60), width=5):
        x, y = self.to(p); ImageDraw.Draw(self.bg).ellipse([x - r * S, y - r * S, x + r * S, y + r * S], outline=color, width=int(width * S))

    def text(self, p, s, size=22, color=(120, 140, 165)):
        x, y = self.to(p); d = ImageDraw.Draw(self.bg); f = font(int(size * S)); w = d.textlength(s, font=f); d.text((x - w / 2, y - size * S * .72), s, font=f, fill=color)

    def title(self):
        d = ImageDraw.Draw(self.bg)
        if self.sp.get("style") == "big":   # 参考スクショ（オーナー 11/22）にならう：字を大きく、白地に、要の言葉だけ色を付ける。{…}＝黄、[…]＝水色
            y = 118 * S
            for line in self.sp["title"]:
                parts = [(m.group(1) or m.group(2) or m.group(3), (255, 205, 60) if m.group(1) else (90, 220, 255) if m.group(2) else (255, 255, 255)) for m in re.finditer(r"\{([^}]*)\}|\[([^\]]*)\]|([^{\[]+)", line)]
                plain = "".join(t for t, _ in parts); sz = 76 * S; f = font(sz); w = d.textlength(plain, font=f)
                if w > W * S * .94: sz = int(sz * W * S * .94 / w); f = font(sz); w = d.textlength(plain, font=f)
                x = W * S / 2 - w / 2
                for t, c in parts: d.text((x, y), t, font=f, fill=c, stroke_width=7 * S, stroke_fill=(0, 0, 0)); x += d.textlength(t, font=f)
                y += 100 * S
            self.label_y = y / S + 6
            if self.sp.get("mark"): f = font(30 * S); w = d.textlength(self.sp["mark"], font=f); d.text((W * S / 2 - w / 2, H * S * .905), self.sp["mark"], font=f, fill=(120, 130, 160))
            return
        for i, line in enumerate(self.sp["title"]):
            f = font(58 * S); w = d.textlength(line, font=f)
            if w > W * S * .93: f = font(int(58 * S * W * S * .93 / w)); w = d.textlength(line, font=f)
            d.text((W * S / 2 - w / 2, (150 + i * 80) * S), line, font=f, fill=(255, 255, 255) if i == 0 else (255, 196, 60), stroke_width=6 * S, stroke_fill=(0, 0, 0))

    # ---- 軌跡（確定した線は重ねて残す）
    def commit(self, segs, width=2.0):
        """segs: [(p0, p1, 色)]。同じ呼び出しの中では上書き、呼び出しをまたぐと明るさが足される"""
        if not segs: return
        P = [(self.to(a), self.to(b), c) for a, b, c in segs]
        xs = [q[0] for a, b, _ in P for q in (a, b)]; ys = [q[1] for a, b, _ in P for q in (a, b)]; m = int(width * S) + 3
        bx0, by0 = max(0, int(min(xs)) - m), max(0, int(min(ys)) - m); bx1, by1 = min(W * S, int(max(xs)) + m + 1), min(H * S, int(max(ys)) + m + 1)
        if bx1 <= bx0 or by1 <= by0: return
        tmp = Image.new("RGB", (bx1 - bx0, by1 - by0)); td = ImageDraw.Draw(tmp)
        for a, b, c in P: td.line([a[0] - bx0, a[1] - by0, b[0] - bx0, b[1] - by0], fill=c, width=max(1, int(width * S)))
        self.acc.paste(ImageChops.add(self.acc.crop((bx0, by0, bx1, by1)), tmp), (bx0, by0))

    def dot(self, p, r, color):
        """点を1つ、残る絵に足す（r は 1080幅での半径px）"""
        x, y = self.to(p); rr = r * S; bx0, by0, bx1, by1 = int(x - rr) - 2, int(y - rr) - 2, int(x + rr) + 3, int(y + rr) + 3
        if bx0 < 0 or by0 < 0 or bx1 > W * S or by1 > H * S: return
        tmp = Image.new("RGB", (bx1 - bx0, by1 - by0)); ImageDraw.Draw(tmp).ellipse([x - rr - bx0, y - rr - by0, x + rr - bx0, y + rr - by0], fill=color)
        self.acc.paste(ImageChops.add(self.acc.crop((bx0, by0, bx1, by1)), tmp), (bx0, by0))

    def cell(self, p0, p1, color):
        """四角を1つ、残る絵に上書きする（p0, p1 は対角）"""
        (x0, y0), (x1, y1) = self.to(p0), self.to(p1); ImageDraw.Draw(self.acc).rectangle([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], fill=color)

    # ---- 1コマ
    def frame(self, t, live=(), balls=(), label=None, flashes=(), draw=None):
        """live: [(p0, p1, 色, 太さ)] いま描いている途中の線。balls: [(位置, 色, 半径px)]。label: (文字, 数)。flashes: [(位置, 半径px, 色, 太さ)]"""
        if self.stills is not None and not any(abs(t - s) < .5 / FPS for s in self.stills): return
        im = ImageChops.add(self.bg, self.acc)
        bl = self.sp.get("bloom", .9)
        if bl:   # 残った軌跡に光のにじみ（ブルーム）。1/4で描いてぼかして戻す
            q = 4; g = self.acc.resize((W * S // q, H * S // q), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6))
            if bl != 1: g = Image.eval(g, lambda v: min(255, int(v * bl * 1.6)))
            im = ImageChops.add(im, g.resize((W * S, H * S), Image.BILINEAR))
        d = ImageDraw.Draw(im)
        for a, b, c, w in live: d.line([*self.to(a), *self.to(b)], fill=c, width=max(1, int(w * S)))
        if balls:   # 玉は点くらい小さく（オーナー 11/21「このくらい小さくてもいい」）。半径を 0.55 倍、最小 1.6px
            balls = [(p, c, min(BALL_MAX, max(1.6, r * BALL_K))) for p, c, r in balls]
            q = 8; gl = Image.new("RGB", (W * S // q, H * S // q)); gq = ImageDraw.Draw(gl)
            for p, c, r in balls:
                x, y = self.to(p); rr = r * S * 2.4 / q; gq.ellipse([x / q - rr, y / q - rr, x / q + rr, y / q + rr], fill=dim(c, .6))
            im = ImageChops.add(im, gl.filter(ImageFilter.GaussianBlur(1.6)).resize((W * S, H * S), Image.BILINEAR)); d = ImageDraw.Draw(im)
            for p, c, r in balls:
                x, y = self.to(p); rr = r * S; d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=c)
        flashes = [(p, min(r, FLASH_MAX), col, wd) for p, r, col, wd in flashes]
        for p, r, col, wd in flashes:
            x, y = self.to(p); d.ellipse([x - r * S, y - r * S, x + r * S, y + r * S], outline=col, width=max(1, int(wd * S)))
        if draw:
            draw(d)
            gw = self.sp.get("glow")
            if gw:   # 描いたものの明るいところだけにじませる（ブルーム）。draw で描く場面も発光感をそろえる（オーナー 11/23「発光の感じは踏襲」）
                q = 4; g = im.resize((W * S // q, H * S // q), Image.BILINEAR).point(lambda v: 0 if v < 70 else min(255, int((v - 70) * 1.5)))
                g = g.filter(ImageFilter.GaussianBlur(7)); g = Image.eval(g, lambda v: min(255, int(v * gw)))
                im = ImageChops.add(im, g.resize((W * S, H * S), Image.BILINEAR)); d = ImageDraw.Draw(im)
        if label:
            lab, num = label; fC, fN = F(50 * S), F(62 * S); w1, w2 = d.textlength(lab, font=fC), d.textlength(num, font=fN); x0 = W * S / 2 - (w1 + w2) / 2; y = getattr(self, "label_y", 318) * S
            d.text((x0, y + 8 * S), lab, font=fC, fill=(235, 235, 240), stroke_width=5 * S, stroke_fill=(0, 0, 0))
            d.text((x0 + w1, y), num, font=fN, fill=(255, 210, 70), stroke_width=6 * S, stroke_fill=(0, 0, 0))
        out = im.resize((W, H), Image.LANCZOS)
        if self.stills is not None: out.convert("RGB").save(f"build_ballsim/{self.id}_{t:06.2f}.jpg", quality=88); return
        if self.proc is None:
            self.raw = f"build_ballsim/{self.id}_v.mp4"
            self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", self.raw], stdin=subprocess.PIPE)
        self.proc.stdin.write(out.tobytes())

    # ---- 音（1個ずつ足す）
    def note(self, t, midi, gain=1.0, pan=.5, dec=6.0, kind="mar"):
        if self.mel is not None and kind in ("mar", "bell"): self.mel.append((t, gain, pan, dec, "n")); return
        while midi > MAX_MIDI: midi -= 12   # 高すぎる音はオクターブ下げる（オーナー 11/21「ハイキーは気持ち悪い」）
        if harmony.ON and kind not in ("kick", "hat", "piano"):   # 当たった音を今の和音（カノン進行）に寄せ、残りの2音を小さく重ねる
            midi = harmony.snap(int(round(midi)), t)
            for o in harmony.others(midi, t): self.notes.append((t, o, gain * .3, min(1, max(0, pan)), dec * 1.1, kind))
        self.notes.append((t, midi, gain, min(1, max(0, pan)), dec, kind))

    def chord(self, t, midis, gain=.35, dec=3.0, kind="mar"):
        if self.mel is not None: self.mel.append((t, gain, .5, dec * 2, "ch")); return   # 節目（全部そろう瞬間）は、今の和音をベルで鳴らす
        for m in midis: self.note(t, m, gain, .5, dec, kind)

    def _audio(self, total, path):
        n = int(SR * (total + 2.5)); L = np.zeros(n); R = np.zeros(n); cache = {}
        def tone(m, dec, kind):
            key = (m, round(dec, 1), kind)
            if key not in cache:
                f = mtof(m); tt = np.arange(int(SR * min(2.0, 7 / dec))) / SR
                if kind == "pluck":   # マリンバとウクレレの間：弦をはじく合成（カープラス・ストロング法）に、短い木の響き
                    N = max(2, int(round(SR / f))); rng = np.random.default_rng(int(m)); buf = rng.uniform(-1, 1, N)
                    buf = np.convolve(buf, np.ones(4) / 4, "same")   # はじきを柔らかく（爪でなく指）
                    out = np.zeros(len(tt)); ln = .4985
                    for i in range(len(tt)):
                        v = buf[i % N]; out[i] = v; buf[i % N] = ln * (v + buf[(i + 1) % N])
                    wood = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 9) + .35 * np.sin(2 * np.pi * f * 4 * tt) * np.exp(-tt * 30)
                    s = .8 * out / (np.abs(out).max() + 1e-9) + .55 * wood
                    cache[key] = s * np.exp(-tt * dec * .5) * np.minimum(1, tt / .002) * (f / 523.25) ** -.25; return cache[key]
                if kind == "edm":   # EDM ふうのマリンバ（オーナー 11/22）：短くはじける木の音＋1オクターブ下の丸い胴。余韻はディレイで作る
                    s = np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt * 14) + .22 * np.sin(2 * np.pi * 3 * f * tt) * np.exp(-tt * 28) + .4 * np.sin(2 * np.pi * f / 2 * tt) * np.exp(-tt * 6)
                    s = s + np.random.default_rng(int(m)).normal(0, 1, len(tt)) * np.exp(-tt * 900) * .12
                    cache[key] = s * np.exp(-tt * max(7.0, dec * 1.6)) * np.minimum(1, tt / .0012) * (f / 523.25) ** -.3; return cache[key]
                if kind == "piano":   # やわらかいピアノ：倍音を重ね、高い倍音ほど早く消える。打鍵はゆっくりめ
                    tt = np.arange(int(SR * 2.6)) / SR
                    s = sum((1 / h ** 1.25) * np.sin(2 * np.pi * f * h * (1 + .0004 * h * h) * tt) * np.exp(-tt * (1.1 + .55 * h)) for h in range(1, 8))
                    cache[key] = s * np.minimum(1, tt / .006) * (f / 261.6) ** -.35; return cache[key]
                if kind == "karo":   # 「カロッ」：ガラスとマリンバの中間（オーナー 11/22）。木の胴＋少しずれた澄んだ倍音、短く切れる
                    s = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 3) + .30 * np.sin(2 * np.pi * f * 4 * tt) * np.exp(-tt * 18) + .26 * np.sin(2 * np.pi * f * 2.76 * tt + 1) * np.exp(-tt * 9) + .10 * np.sin(2 * np.pi * f * 5.4 * tt) * np.exp(-tt * 16)
                    s = s + np.random.default_rng(int(m)).normal(0, 1, len(tt)) * np.exp(-tt * 1100) * .10
                    cache[key] = s * np.exp(-tt * max(6.0, dec * 1.3)) * np.minimum(1, tt / .0012) * (f / 523.25) ** -.28; return cache[key]
                if kind == "stone":   # 石を叩く音（石琴・サヌカイトふう。オーナー 11/22）：棒の振動の倍音比 1 : 2.76 : 5.4 : 8.9、澄んだ余韻＋短い「コッ」
                    s = (np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * f * 1.003 * tt)) * np.exp(-tt * 2.6) + .34 * np.sin(2 * np.pi * f * 2.76 * tt + .7) * np.exp(-tt * 7) \
                        + .15 * np.sin(2 * np.pi * f * 5.4 * tt + 1.3) * np.exp(-tt * 15) + .06 * np.sin(2 * np.pi * f * 8.9 * tt) * np.exp(-tt * 28)
                    nz = np.random.default_rng(int(m)).normal(0, 1, len(tt)); nz = np.convolve(nz, np.ones(5) / 5, "same") * np.exp(-tt * 700) * .22
                    cache[key] = (s + nz) * np.exp(-tt * max(2.5, dec * .6)) * np.minimum(1, tt / .0008) * (f / 523.25) ** -.3; return cache[key]
                if kind == "kick":   # 裏のリズム：やわらかい低い太鼓（音の高さが下がる正弦波）
                    tt2 = np.arange(int(SR * .35)) / SR; ph = 2 * np.pi * np.cumsum(55 + 70 * np.exp(-tt2 * 30)) / SR
                    cache[key] = np.sin(ph) * np.exp(-tt2 * 9) * np.minimum(1, tt2 / .002); return cache[key]
                if kind == "hat":    # 裏のリズム：ごく小さいシャカ（高い帯域を丸めたノイズ）
                    tt2 = np.arange(int(SR * .06)) / SR; nz = np.random.default_rng(7).normal(0, 1, len(tt2)); nz = nz - np.convolve(nz, np.ones(6) / 6, "same")
                    cache[key] = np.convolve(nz, np.ones(3) / 3, "same") * np.exp(-tt2 * 70) * .5; return cache[key]
                if kind == "glass":   # ガラスに当たった「カラン」：整数倍からずれた部分音＋短いはじき
                    s = sum(g_ * np.sin(2 * np.pi * f * r_ * tt + r_) * np.exp(-tt * dec * k_) for r_, g_, k_ in ((1, 1, .5), (2.0, .32, 1.0), (3.01, .14, 1.8), (4.25, .07, 3.0)))
                    s = s + np.random.default_rng(int(m)).normal(0, 1, len(tt)) * np.exp(-tt * 1400) * .08
                    cache[key] = s * np.minimum(1, tt / .0015) * (f / 523.25) ** -.3; return cache[key]
                if kind == "bell": s = np.sin(2 * np.pi * f * tt) + .4 * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 6) + .2 * np.sin(2 * np.pi * f * 5.4 * tt) * np.exp(-tt * 10)
                else: s = np.sin(2 * np.pi * f * tt) + .28 * np.sin(2 * np.pi * f * 4 * tt) * np.exp(-tt * 20) + .1 * np.sin(2 * np.pi * f * 10 * tt) * np.exp(-tt * 45)
                cache[key] = s * np.exp(-tt * dec) * np.minimum(1, tt / .003) * (f / 523.25) ** -.25   # 高い音ほど少し小さく
            return cache[key]
        for t, m, g, pan, dec, kind in self.notes:
            i = int(round(t * SR)); s = tone(m, dec, kind); k = min(len(s), n - i)
            if i < 0 or k <= 0: continue
            L[i:i + k] += s[:k] * g * (1 - pan) * 1.414; R[i:i + k] += s[:k] * g * pan * 1.414
        for dly, g in [(.031, .3), (.067, .24), (.113, .18), (.171, .13), (.257, .09)]:
            o = int(SR * dly); L[o:] += R[:-o] * g; R[o:] += L[:-o] * g
        a_ = math.exp(-2 * math.pi * 5000 / SR)   # 1次ローパス約5kHz。キンキンする成分を少し落とす
        for X in (L, R) if SOFT_LP else ():
            from scipy.signal import lfilter; X[:] = lfilter([1 - a_], [1, -a_], X)
        if self.sp.get("bed"):   # 参考動画の音の分析（11/23）：伸びている動画は音が途切れない（音量の幅 5〜11dB）・余韻が長い（0.9〜1.8秒）・低音が厚い。
            # → (1) 和音の持続音を薄く敷く (2) 残響を長くする (3) 低い根音を小節ごとに
            tt = np.arange(n) / SR; pad = np.zeros(n); mel = bool(self.sp.get("melody"))
            off = self.sp.get("bed_off", 0.0)   # 小節の頭を、動画の拍の頭に合わせる（秒）
            for b0 in np.arange(0, total + 2, harmony.BAR):
                i0, i1 = int((b0 + off) * SR), min(n, int((b0 + off + harmony.BAR + .6) * SR))
                if i0 >= n: break
                pcs = [0, 7, 4] if mel else harmony.pcs(b0 + .01); seg = tt[i0:i1] - b0 - off; env = np.minimum(1, seg / .5) * np.minimum(1, (harmony.BAR + .6 - seg) / .6)
                for k, pc in enumerate(pcs):
                    f = 440 * 2 ** ((48 + pc - 69) / 12); pad[i0:i1] += (np.sin(2 * np.pi * f * seg) + .25 * np.sin(2 * np.pi * 2 * f * seg)) * env * (.5 if k == 0 else .32)
                r = pcs[0]; fb = 440 * 2 ** ((36 + r - 69) / 12); bl = min(n - i0, int(SR * 1.6)); sb = np.arange(bl) / SR
                pad[i0:i0 + bl] += np.sin(2 * np.pi * fb * sb) * np.exp(-sb * 2.2) * np.minimum(1, sb / .01) * 1.6
            pk = max(np.abs(L).max(), np.abs(R).max(), 1e-9); pad *= pk * self.sp.get("bed_gain", .22) / (np.abs(pad).max() + 1e-9)
            L += pad; R += pad
            for dly, g in [(.089, .42), (.131, .36), (.197, .30), (.263, .25), (.347, .2), (.461, .15), (.613, .11)]:   # 長めの残響
                o = int(SR * dly); L[o:] += R[:-o] * g * .55; R[o:] += L[:-o] * g * .55
        st = np.stack([L, R], 1); st = st / (np.abs(st).max() + 1e-9) * .85
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())

    def finish(self, total):
        if self.mel:   # 旋律モード：当たった順に、著作権の切れた曲の旋律を1音ずつ進める。和音も音の歩みに合わせて進む
            MJ, MN = (0, 4, 7), (0, 3, 7); C_, G_, F_ = (0, MJ), (7, MJ), (5, MJ)
            P1 = [76, 74, 72, 71, 69, 67, 69, 71]; P2 = [72, 76, 79, 77, 76, 72, 76, 74, 72, 69, 72, 79, 77, 81, 79, 77]
            MELS = {
                "canon": [(m, harmony.CANON[i]) for i, m in enumerate(P1)] + [(m, harmony.CANON[i // 2]) for i, m in enumerate(P2)],   # パッヘルベル「カノン」
                "ode": [(m, c) for ms, c in (([76, 76, 77, 79], C_), ([79, 77, 76, 74], G_), ([72, 72, 74, 76], C_), ([76, 74, 74], G_),   # ベートーヴェン「歓喜の歌」
                                             ([76, 76, 77, 79], C_), ([79, 77, 76, 74], G_), ([72, 72, 74, 76], C_), ([74, 72, 72], C_)) for m in ms],
                "twinkle": [(m, c) for ms, c in (([72, 72, 79, 79], C_), ([81, 81, 79], F_), ([77, 77, 76, 76], C_), ([74, 74, 72], G_),   # きらきら星（フランス民謡）
                                                 ([79, 79, 77, 77], C_), ([76, 76, 74], G_), ([79, 79, 77, 77], C_), ([76, 76, 74], G_),
                                                 ([72, 72, 79, 79], C_), ([81, 81, 79], F_), ([77, 77, 76, 76], C_), ([74, 74, 72], C_)) for m in ms],
            }
            seq = MELS[self.sp.get("melody") if self.sp.get("melody") in MELS else "canon"]
            ev = sorted(e for e in self.mel if e[0] < total - .02); k = -1; last = -9; prev = None
            for t, gain, pan, dec, tag in ev:
                if tag == "ch":
                    r, q = seq[max(k, 0) % len(seq)][1]
                    for x in q: self.notes.append((t, 60 + (r + x) % 12, gain * .8, .5, dec, "bell"))
                    continue
                if t - last > .045: k += 1; last = t; new = True   # ほぼ同時の当たりは1歩にまとめる
                else: new = False
                m, (r, q) = seq[k % len(seq)]; pc = [(r + x) % 12 for x in q]
                self.notes.append((t, m, gain, pan, dec, "mar"))
                if new:
                    lo = [x for x in range(m - 3, m - 15, -1) if x % 12 in pc and x % 12 != m % 12][:2]
                    for x in lo: self.notes.append((t, x, gain * .32, pan, dec * 1.1, "mar"))
                    if (r, q) != prev: self.notes.append((t, 36 + r if r >= 4 else 48 + r, gain * .5, .5, dec * 1.6, "mar")); prev = (r, q)   # 和音が変わるところで低い根音
        if self.stills is not None: print("確認用の絵:", self.stills); return
        if self.sp.get("tone") in ("karo", "stone"): tn = self.sp["tone"]; self.notes = [(t, m, g, pan, dec, tn if kind == "mar" else kind) for t, m, g, pan, dec, kind in self.notes]
        if self.sp.get("tone") == "edm":   # 当たる音を EDM マリンバに。付点8分（0.375秒）のこだまを左右に振る
            ns = []
            for t, m, g, pan, dec, kind in self.notes:
                if kind != "mar": ns.append((t, m, g, pan, dec, kind)); continue
                ns.append((t, m, g, pan, dec, "edm"))
                if g > .12: ns.append((t + .375, m, g * .26, 1 - pan, dec, "edm")); ns.append((t + .75, m, g * .11, pan, dec, "edm"))
            self.notes = ns
        self.proc.stdin.close(); self.proc.wait(); wv = f"build_ballsim/{self.id}.wav"; self._audio(total, wv)
        mux(self.sp, self.raw, wv, f"output/{self.id}.mp4")
        print(f"書き出し: output/{self.id}.mp4  {total:.1f}秒  音 {len(self.notes)}")


def mux(sp, raw, wv, out):
    """絵と音を1本にする。spec の post_hue（度）・post_pitch（半音）があれば、題名より下の絵の色相と、音の高さをずらす。
    （オーナー 11/23「英語版でも出したい。完コピだと弾かれそうなのでマイナーチェンジで、書き出し負担が少ないもの」→ 作り直さず、この段だけで変える）"""
    hue, pit = sp.get("post_hue"), sp.get("post_pitch"); af = "loudnorm=I=-19:TP=-3:LRA=11"
    if pit: r = 2 ** (pit / 12.0); af = f"asetrate={SR}*{r:.6f},aresample={SR},atempo={1 / r:.6f}," + af
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", raw, "-i", wv]
    if hue: y0 = int(H * .215) // 2 * 2; cmd += ["-filter_complex", f"[0:v]split[a][b];[b]crop={W}:{H - y0}:0:{y0},hue=h={hue},lumakey=threshold=0:tolerance={sp.get('post_key', 0.07)}:softness=0.06[c];[a][c]overlay=0:{y0}[v]", "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
    else: cmd += ["-map", "0:v", "-c:v", "copy"]
    subprocess.run(cmd + ["-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-af", af, "-shortest", "-movflags", "+faststart", out], check=True)


def kit(sp):
    """投稿キット（タイトル・説明・タグ）を nazo/manual/ballsim/<id>_upload.txt に書く"""
    y = sp.get("yt")
    if not y: return
    os.makedirs("nazo/manual/ballsim", exist_ok=True)
    open(f"nazo/manual/ballsim/{sp['id']}_upload.txt", "w", encoding="utf-8").write(f"【タイトル】\n{y['title']}\n\n【説明】\n{y['desc']}\n\n【タグ】\n{', '.join(y['tags'])}\n")
