# trendkit.py — 「伸びている型を自前で作り直す」ときの共通の道具（縦のショート 1080×1920・60コマ）
#   流れと決まりは docs/trend-pipeline.md。新しい型は、このファイルを使って tools/<名前>.py を1つ書く（見本：tools/tiles.py）。
#   ここに入っているもの
#     絵：background() 背景 ／ sprite()・blit() 玉 ／ to_frame() 文字をのせて1コマにする ／ PALETTE8 8色
#     音：Audio … 当たった時刻にそのまま鳴らす（時刻をそろえ直さない）。音色は乾いた「カロッ」（kalimba.karo）、音の高さはカノン進行の和音の音
#         持ち主 2026-11-27「音はもっと乾いたカロっ(飴玉を口で転がすような)音がいい。音階はカノン」
#         11/25「バウンドのタイミングと音が鳴るタイミングは合わせて」／11/27「ブラーエコーもかけすぎない」
#     書き出し：encode() コマを ffmpeg に流して音と合わせる ／ stills() 確認用の絵 ／ pick_seed() 乱数さがし
#   確かめるのは tools/trend/check.py（長さ・音量・高い音・止まって見える時間）と、出だし・真ん中・最後の絵を目で見ること
import math, os, sys, subprocess, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kalimba as K

W, H, FPS, SR = 1080, 1920, 60, 48000
LANG = os.environ.get("LANG_OUT", "ja"); EN = LANG == "en"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FJ = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"; FJM = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
_f = {}
def fnt(sz, bold=True):
    k = (sz, bold)
    if k not in _f: _f[k] = ImageFont.truetype(FJ if bold else FJM, sz)
    return _f[k]
def tr(ja, en): return en if EN else ja
def sstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a))) if b != a else float(x >= b); return t * t * (3 - 2 * t)

# 8色（落ち着いた明るさ。白く飛ばさない）
PALETTE8 = [("赤", "Red", (232, 96, 96)), ("橙", "Orange", (240, 150, 74)), ("黄", "Yellow", (236, 214, 96)), ("緑", "Green", (104, 196, 118)),
            ("水色", "Cyan", (92, 198, 226)), ("青", "Blue", (98, 126, 236)), ("紫", "Purple", (170, 110, 222)), ("桃", "Pink", (240, 150, 190))]
def cname(i): return PALETTE8[i][1] if EN else PALETTE8[i][0]

# ---------- 絵 ----------
def sprite(col, r):
    """光沢を少しだけつけた玉（RGBA、0..1）"""
    s = int(r * 2 + 8); yy, xx = np.mgrid[0:s, 0:s].astype(np.float32); c0 = s / 2; d = np.sqrt((xx - c0) ** 2 + (yy - c0) ** 2) / r
    a = np.clip((1 - d) * r + .5, 0, 1); nz = np.sqrt(np.clip(1 - d * d, 0, 1)); lam = np.clip(-(xx - c0) / r * .4 - (yy - c0) / r * .5 + nz * .75, 0, 1)
    c = np.asarray(col, np.float32) / 255; rgb = c * (.5 + .6 * lam)[..., None] + np.exp(-(((xx - c0 + r * .35) ** 2 + (yy - c0 + r * .38) ** 2) / (r * .3) ** 2))[..., None] * .30
    return np.dstack([np.clip(rgb, 0, 1), a]).astype(np.float32)
def blit(buf, sp, x, y, al=1.0):
    """buf（H,W,3 の 0..1）に玉を置く。画面の外にはみ出した分は切る"""
    h, w = sp.shape[:2]; x0, y0 = int(round(x - w / 2)), int(round(y - h / 2)); xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb <= xa or yb <= ya or al <= 0: return
    s = sp[ya - y0:yb - y0, xa - x0:xb - x0]; a = s[..., 3:4] * al; reg = buf[ya:yb, xa:xb]; reg[:] = reg * (1 - a) + s[..., :3] * a
def background(center=(W / 2, 1000)):
    """暗い紺の背景（まん中がほんの少し明るい）"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); d = np.sqrt((xx - center[0]) ** 2 + (yy - center[1]) ** 2)
    b = np.zeros((H, W, 3), np.float32) + np.array([.030, .032, .060], np.float32); b += (np.exp(-d / 900) * .03)[..., None] * np.array([.8, .8, 1.2], np.float32); return np.clip(b, 0, 1)
def to_frame(buf, draw=None):
    """0..1 の絵を1コマ（uint8）にする。draw(d) で文字や線をのせる（d は RGBA の ImageDraw。色の4つめで濃さを指定できる）"""
    im = Image.fromarray((np.clip(buf, 0, 1) * 255).astype(np.uint8))
    if draw is None: return np.asarray(im)
    im = im.convert("RGBA"); ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); draw(ImageDraw.Draw(ov)); return np.asarray(Image.alpha_composite(im, ov).convert("RGB"))
def fit_text(d, xy, s, size, maxw, fill, anchor="mm", bold=True, minsize=22):
    """幅 maxw におさまる大きさに下げて書く（はみ出し防止）"""
    while size > minsize and d.textlength(s, font=fnt(size, bold)) > maxw: size -= 2
    d.text(xy, s, font=fnt(size, bold), fill=fill, anchor=anchor); return size

# ---------- 音 ----------
class Audio:
    """当たった出来事を集めて、最後に1本の音にする。
       hit(t, u)：時刻 t に、u（0＝低い … 1＝高い）の高さで「カロッ」。音は、その時のカノン進行の和音の音から選ぶので、重なっても濁らない
       note(t, midi)：高さを直接指定
       同じ瞬間（window 秒以内）に鳴るのは max_same 音まで（強いものを残す）"""
    def __init__(self, dur, lo=69, hi=91, hard=.8, roll=True, chord_len=2.4, max_same=3, window=.03):
        self.dur, self.lo, self.hi, self.hard, self.roll, self.chord_len, self.max_same, self.window = dur, lo, hi, hard, roll, chord_len, max_same, window; self.ev = []
    def chord_index(self, t): return int(t // self.chord_len) % 8
    def hit(self, t, u, vel=.8, chord=None, octave=0, roll=None, hard=None):
        tones = K.canon_tones(self.chord_index(t) if chord is None else chord, self.lo, self.hi); m = tones[int(min(.999, max(0, u)) * len(tones))] + 12 * octave
        self.ev.append((float(t), int(m), float(vel), .2 + .6 * float(min(1, max(0, u))), self.roll if roll is None else roll, self.hard if hard is None else hard)); return m
    def note(self, t, midi, vel=.8, pan=.5, roll=None, hard=None):
        self.ev.append((float(t), int(midi), float(vel), float(pan), self.roll if roll is None else roll, self.hard if hard is None else hard))
    def write(self, path, target_rms=.15, pad_gain=0.0):
        N = int(SR * self.dur); st = np.zeros((N, 2), np.float32); ev = sorted(self.ev); kept = []; i = 0
        while i < len(ev):   # 同時に鳴りすぎないように間引く
            j = i
            while j < len(ev) and ev[j][0] - ev[i][0] < self.window: j += 1
            kept += sorted(ev[i:j], key=lambda e: -e[2])[:self.max_same]; i = j
        for (t, m, vel, pan, roll, hard) in kept:
            x = K.karo(m, vel, roll, hard); a = int(t * SR)
            if a < 0 or a >= N: continue
            k = min(len(x), N - a); st[a:a + k, 0] += x[:k] * math.cos(pan * math.pi / 2) * vel; st[a:a + k, 1] += x[:k] * math.sin(pan * math.pi / 2) * vel
        if pad_gain: st += K.pad([(r - 12, r, f5, t3 + 12) for (r, t3, f5) in K.CANON], self.chord_len, self.dur, pad_gain)[:, None]
        st = K.room(st, .03, .25)                                   # 響きはほとんど足さない（乾いた音）
        tt = np.arange(N) / SR; st *= (np.minimum(1, tt / .05) * np.minimum(1, (self.dur - tt) / .4))[:, None]
        act = np.abs(st).max(1) > 1e-4; rms = float(np.sqrt((st[act] ** 2).mean())) if act.any() else 1.0
        st = np.tanh(st / rms * target_rms * 1.2) / 1.2             # 聞こえる大きさでそろえ、短い山はやわらかく丸める
        with wave.open(path, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())
        return len(kept)

# ---------- 書き出し ----------
def encode(n, frame_fn, wav, out, crf=18):
    """frame_fn(i) → (H,W,3) uint8 を n コマ流し、音（wav）と合わせて mp4 にする"""
    tmp = out + ".v.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for i in range(n): p.stdin.write(np.ascontiguousarray(frame_fn(i)).tobytes())
    p.stdin.close(); p.wait()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True); os.remove(tmp)
def stills(n, frame_fn, prefix, at=(.02, .5, .96)):
    """出だし・真ん中・最後の絵を書き出す（目で見る用）。横に並べた1枚も作る"""
    ims = [Image.fromarray(frame_fn(int(n * a))) for a in at]; sheet = Image.new("RGB", (W * len(ims) // 2, H // 2))
    for k, im in enumerate(ims): im.save(f"{prefix}_{k}.jpg", quality=88); sheet.paste(im.resize((W // 2, H // 2)), (k * W // 2, 0))
    sheet.save(f"{prefix}_sheet.jpg", quality=85); return f"{prefix}_sheet.jpg"
def pick_seed(simulate, score, seeds, show=5):
    """乱数をいくつも試し、score（大きいほど良い）で並べる。simulate(seed) の結果を score に渡す"""
    out = []
    for sd in seeds:
        r = simulate(sd); out.append((round(float(score(r)), 2), sd)); print(out[-1], flush=True)
    out.sort(reverse=True); print("上位", out[:show]); return out[0][1]
