import math
# simkit.py — シミュレーション・ショートの共通部品
#   背景・光る線・軌跡の重ね描き（消さない）・小さいボール・問いのタイトルと数だけの文字・1個ずつ鳴る音・書き出し
#   ハウスルール（オーナーの指摘）: ボールは小さく／速すぎない／途中で止めない／増え方はゆっくり／
#     ボール1個ごとに音／軌跡は残す／余計な文字は入れない／低い衝撃音は使わない
#   確認用: STILLS="3,12.5,30" を付けて実行すると、その時刻の絵だけ build_ballsim/<id>_<秒>.jpg に出す（動画と音は作らない）
import os, sys, math, json, subprocess, wave
import numpy as np
import harmony
from PIL import Image, ImageDraw, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ballsim import W, H, FPS, hsv, font, SR, mtof

S = int(os.environ.get("SIM_S", "2"))  # 2倍で描いて縮める（長尺は1で速く）
BALL_K = float(os.environ.get("SIM_BALL_K", "1"))   # 玉の大きさの倍率（11/22 オーナー：伸びた放物線・楕円の大きさを基準に戻す）
BALL_MAX = float(os.environ.get("SIM_BALL_MAX", "99"))   # 玉の半径の上限px（指定したときだけ効く）
MAX_MIDI = int(os.environ.get("SIM_MAX_MIDI", "127"))   # 音の高さの上限（指定したときだけ。81 = A5）
SOFT_LP = os.environ.get("SIM_SOFT_LP", "0") == "1"   # 高音をやわらげるローパス（指定したときだけ）
FLASH_MAX = float(os.environ.get("SIM_FLASH_MAX", "999"))
PENTA = [m for o in (60, 72, 84) for m in (o, o + 2, o + 4, o + 7, o + 9)] + [96]  # ド レ ミ ソ ラ を3オクターブ（16音）


def dim(c, g): return tuple(int(v * g) for v in c)


_F = {}
def F(sz):
    """文字の大きさごとに1回だけ読み込む"""
    sz = int(sz)
    if sz not in _F: _F[sz] = font(sz)
    return _F[sz]


class Sim:
    def __init__(self, sp, box, area=(.06, .225, .94, .80)):
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
    def neon(self, pts, closed=False, color=(150, 235, 255), glow=(40, 200, 255), width=9):
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
        if draw: draw(d)
        if label:
            lab, num = label; fC, fN = F(50 * S), F(62 * S); w1, w2 = d.textlength(lab, font=fC), d.textlength(num, font=fN); x0 = W * S / 2 - (w1 + w2) / 2; y = 318 * S
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
        while midi > MAX_MIDI: midi -= 12   # 高すぎる音はオクターブ下げる（オーナー 11/21「ハイキーは気持ち悪い」）
        if harmony.ON and kind not in ("kick", "hat"):   # 当たった音を今の和音（カノン進行）に寄せ、残りの2音を小さく重ねる
            midi = harmony.snap(int(round(midi)), t)
            for o in harmony.others(midi, t): self.notes.append((t, o, gain * .3, min(1, max(0, pan)), dec * 1.1, kind))
        self.notes.append((t, midi, gain, min(1, max(0, pan)), dec, kind))

    def chord(self, t, midis, gain=.35, dec=3.0, kind="mar"):
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
        st = np.stack([L, R], 1); st = st / (np.abs(st).max() + 1e-9) * .85
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())

    def finish(self, total):
        if self.stills is not None: print("確認用の絵:", self.stills); return
        self.proc.stdin.close(); self.proc.wait(); wv = f"build_ballsim/{self.id}.wav"; self._audio(total, wv)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", self.raw, "-i", wv, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-af", "loudnorm=I=-19:TP=-3:LRA=11", "-shortest", "-movflags", "+faststart", f"output/{self.id}.mp4"], check=True)
        print(f"書き出し: output/{self.id}.mp4  {total:.1f}秒  音 {len(self.notes)}")


def kit(sp):
    """投稿キット（タイトル・説明・タグ）を nazo/manual/ballsim/<id>_upload.txt に書く"""
    y = sp.get("yt")
    if not y: return
    os.makedirs("nazo/manual/ballsim", exist_ok=True)
    open(f"nazo/manual/ballsim/{sp['id']}_upload.txt", "w", encoding="utf-8").write(f"【タイトル】\n{y['title']}\n\n【説明】\n{y['desc']}\n\n【タグ】\n{', '.join(y['tags'])}\n")
