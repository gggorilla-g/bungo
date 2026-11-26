# mergelong.py — 長尺：横長の箱で、星の合体を流し続ける（オーナー 11/26「長尺考えたい」「リサーチして文脈に乗りたい。再現性」）
#   mergebox と同じ物理・同じ絵・同じ音。ちがう所：横長（1920x1080）、落とす間隔は一定でゆっくり、太陽はできたら少し光って箱を出ていき「太陽 n個め」と数える。
#   線の近くまで積もったら、合体で下がるまで落とすのを待つ（あふれない）。種（SEED）を変えるだけで、別の回が何本でも作れる。
#   python3 tools/mergelong.py out.mp4    MIN=30（分） SEED=1 IV=0.5   TEST=20 で頭の20秒だけ
import math, os, sys, subprocess, wave, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mergebox as mb
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from scipy.signal import fftconvolve, butter, sosfilt, sosfilt_zi

W, H, FPS, SR = 1920, 1080, 30, 48000
mb.XL, mb.XR, mb.YB, mb.YWALL, mb.YLIM, mb.YRAIL = 420.0, 1500.0, 1010.0, 170.0, 250.0, 100.0
mb.FPS = FPS; mb.SUB = 8; mb.DT = 1 / 240
R0 = 30.0; mb.RAD[:] = [R0 * 1.235 ** k for k in range(9)] + [R0 * 6.8]; mb.MASS[:] = [(r / mb.RAD[0]) ** 2 for r in mb.RAD]
XL, XR, YB, YWALL, YLIM, YRAIL, RAD, NT, EN = mb.XL, mb.XR, mb.YB, mb.YWALL, mb.YLIM, mb.YRAIL, mb.RAD, mb.NT, mb.EN
TEST = float(os.environ.get("TEST", 0)); DUR = TEST or float(os.environ.get("MIN", 30)) * 60; SEED = int(os.environ.get("SEED", 1)); IV = float(os.environ.get("IV", .8)); STAY = 3.0
OUT = sys.argv[1] if len(sys.argv) > 1 else f"output/mergelong_s{SEED}_{mb.LANG}.mp4"
os.makedirs("build_mergelong", exist_ok=True)
RX0, RY0, RW, RH = 360, 60, 1200, 1000
fnt = mb.fnt; FI = mb.FI

def build_static():
    rs = np.random.default_rng(7); yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]; bg = np.zeros((H, W, 3), np.float32); bg[..., 0] = 8 + 7 * yy; bg[..., 1] = 9 + 2 * yy; bg[..., 2] = 22 + 12 * yy
    im = Image.fromarray(bg.astype(np.uint8)); glow = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(glow).ellipse([500, 200, 1420, 1000], fill=(14, 12, 34)); im = ImageChops.add(im, glow.filter(ImageFilter.GaussianBlur(170))); d = ImageDraw.Draw(im)
    for _ in range(260):
        x, y = rs.uniform(0, W), rs.uniform(0, H); b = int(rs.uniform(40, 150)); r = rs.choice([1, 1, 1, 2]); d.ellipse([x - r, y - r, x + r, y + r], fill=(b, b, min(255, b + 20)))
    tint = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(tint).rectangle([XL, YWALL, XR, YB], fill=(150, 170, 255, 9)); im = Image.alpha_composite(im.convert("RGBA"), tint).convert("RGB")
    fr = Image.new("RGBA", (W, H), (0, 0, 0, 0)); f = ImageDraw.Draw(fr); col = (176, 190, 226, 175); o = 5
    f.line([(XL - o, YWALL), (XL - o, YB + o), (XR + o, YB + o), (XR + o, YWALL)], fill=col, width=4, joint="curve")
    f.line([(XL - 26, YRAIL), (XR + 26, YRAIL)], fill=(150, 166, 210, 120), width=2)
    for x in range(int(XL) + 6, int(XR) - 6, 28): f.line([x, YLIM, x + 15, YLIM], fill=(255, 214, 150, 80), width=3)
    l1, l2 = ("Two of the same", "merge into a bigger one") if EN else ("同じ星がぶつかると", "1つ大きい星になる")
    f.text((210, 150), l1, font=fnt(36), fill=(244, 244, 250, 255), anchor="mm"); f.text((210, 200), l2, font=fnt(36), fill=(244, 244, 250, 255), anchor="mm")
    f.text((210, 330), "Suns made" if EN else "できた太陽", font=fnt(34), fill=(255, 226, 122, 255), anchor="mm"); f.text((210, 610), "Dropped" if EN else "落とした星", font=fnt(30), fill=(196, 202, 224, 255), anchor="mm")
    for k in range(NT):
        y = 130 + 92 * k; f.text((1640, y), mb.NAMES[k], font=fnt(32), fill=(236, 238, 246, 255), anchor="lm")
    return im, fr

def render_video(path):
    BG, FRONT = build_static(); BGROI = np.asarray(BG, np.float32)[RY0:RY0 + RH, RX0:RX0 + RW] / 255; NOZ = mb.nozzle_img()
    ICON = [mb.icon(k, 30.0 if k != 7 else 23.0) for k in range(NT)]; ICON_DIM = [Image.merge("RGBA", (*[c.point(lambda v: int(v * .28)) for c in i_.split()[:3]], i_.split()[3])) for i_ in ICON]
    fBig = ImageFont.truetype(FI, 150); fCnt = ImageFont.truetype(FI, 64); fName = fnt(48); fSub = fnt(28)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    st = dict(pres=np.zeros(NT), n=0, t0=time.time(), merged={}, rings=[], last_drop=0.0, nd=0, sunpos={})
    def on_frame(F):
        t = F["t"]; bodies = F["bodies"]; st["n"] += 1
        if F["nd"] != st["nd"]: st["nd"] = F["nd"]; st["last_drop"] = t
        for k in range(NT): st["pres"][k] += ((1.0 if any(b[1] == k for b in bodies) else 0.0) - st["pres"][k]) * (1 - math.exp(-1 / FPS / .1))
        roi = BGROI.copy(); pos = {}
        for i, k, x, y, ang, r, born in sorted(bodies, key=lambda b: (-b[1], b[0])):
            age = t - born; pop = 1 + (.16 * math.exp(-max(0, age - .09) / .07) if (k > 0 and i in ALLM) else 0)
            if k == 9: pop *= (1 + .016 * math.sin(age * 2.4)) * min(1.0, max(.05, (STAY - age) / .45))   # 太陽は出ていく前に小さくなる
            mb.draw_body(roi, k, x - RX0, y - RY0, r, ang, pop); pos[i] = (x, y, r, k)
        if F["held"] is not None:
            g = min(1.0, (t - st["last_drop"]) / .12); hk = F["held"]; mb.draw_body(roi, hk, F["hx"] - RX0, YRAIL + 22 + RAD[hk] * g - RY0, RAD[hk] * max(.2, g), 0.0)
        im = BG.copy(); im.paste(Image.fromarray((np.clip(roi, 0, 1) * 255).astype(np.uint8)), (RX0, RY0)); im = Image.alpha_composite(im.convert("RGBA"), FRONT)
        add = Image.new("RGB", (W, H), (0, 0, 0)); ad = ImageDraw.Draw(add); ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        ov.alpha_composite(NOZ, (int(round(F["hx"] - 65)), int(YRAIL - 28)))
        while EV["i"] < len(MERGES) and MERGES[EV["i"]][0] <= t: st["rings"].append(MERGES[EV["i"]]); EV["i"] += 1
        st["rings"] = [m for m in st["rings"] if t - m[0] < (1.5 if m[1] == 9 else .45)]
        for tm, k, x, y, nid, first in st["rings"]:
            life = 1.5 if k == 9 else (.45 if first else .34); p = (t - tm) / life; bx, by, br, bk = pos.get(nid, (x, y, RAD[k], k)); R = RAD[k]; a = max(0.0, 1 - p) ** 1.6 * (.9 if (first or k == 9) else .62); r1 = R * (1.05 + (2.2 if k == 9 else .9) * p)
            ad.ellipse([bx - r1, by - r1, bx + r1, by + r1], outline=tuple(int(v * a) for v in mb.GLOW[k]), width=max(2, int(R * .07)))
            if first and k < 9 and t - tm < 1.6 * .28:
                pass
        for tm, k, x, y, nid, first in [m for m in FIRSTS if 0 <= t - m[0] < 1.8]:   # 初めての星の名前
            e = t - tm; A = int(255 * min(1, e / .08) * min(1, (1.8 - e) / .3)); bx, by, br, bk = pos.get(nid, (x, y, RAD[k], k)); ly = max(YLIM - 30, by - RAD[k] - 70)
            d.text((bx, ly), mb.NAMES[k], font=fName, fill=(248, 248, 252, A), anchor="mm", stroke_width=5, stroke_fill=(6, 6, 16, A))
        for k in range(NT):
            y = 130 + 92 * k; b = float(min(1, st["pres"][k])); ic = ICON[k]; ov.alpha_composite(ICON_DIM[k], (1580 - ic.width // 2, y - ic.height // 2))
            if b > .02: ov.paste(ic, (1580 - ic.width // 2, y - ic.height // 2), ic.split()[3].point(lambda v, b=b: int(v * b)))
        d.text((210, 440), str(F["suns"]), font=fBig, fill=(255, 226, 122, 255), anchor="mm"); d.text((210, 670), str(F["nd"]), font=fCnt, fill=(244, 244, 250, 255), anchor="mm")
        im = ImageChops.add(Image.alpha_composite(im, ov).convert("RGB"), add)
        src = add.copy(); src.paste(Image.fromarray((np.clip((roi - .60) * 1.3, 0, 1) * 255).astype(np.uint8)), (RX0, RY0))
        im = ImageChops.add(im, src.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(7)).resize((W, H), Image.BILINEAR))
        proc.stdin.write(im.tobytes())
        if st["n"] % 1800 == 0: print(f"  {st['n'] / FPS / 60:.0f}分 / {DUR / 60:.0f}分  経過 {time.time() - st['t0']:.0f}秒", flush=True)
    return proc, on_frame

class Live(list):   # シミュレーションが足していく合体の記録を、描く側からも読めるように
    pass
MERGES = []; FIRSTS = []; ALLM = set(); EV = dict(i=0)

def audio(res, path):
    N = int(SR * DUR); dry = np.lib.format.open_memmap("build_mergelong/dry.npy", "w+", np.float32, (N, 2)); snd = np.lib.format.open_memmap("build_mergelong/snd.npy", "w+", np.float32, (N, 2))
    def put(x, t, pan=.5, g=1.0, send=.35):
        i = int(round(t * SR))
        if i < 0 or i >= N: return
        k = min(len(x), N - i); l, r = math.cos(pan * math.pi / 2) * g, math.sin(pan * math.pi / 2) * g
        dry[i:i + k, 0] += x[:k] * l; dry[i:i + k, 1] += x[:k] * r; snd[i:i + k, 0] += x[:k] * l * send; snd[i:i + k, 1] += x[:k] * r * send
    pc = {}
    def pad(ms, d_, g):
        key = (tuple(ms), d_)
        if key not in pc:
            tt = np.arange(int(SR * d_)) / SR; s = np.zeros(len(tt))
            for q, m_ in enumerate(ms):
                f = mb.mtof(m_); s += (np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * f * 1.004 * tt + q) + .22 * np.sin(4 * np.pi * f * tt + 2 * q)) / (1 + .25 * q)
            pc[key] = s * np.minimum(1, tt / .25) * np.minimum(1, (d_ - tt) / .7)
        return pc[key] * g
    seq = mb.melody(); mi = -1; last_t = -9; last_note = None; chord = "D"
    for t, k, x, y, nid, first in res["merges"]:
        pan = .5 + .34 * (x - (XL + XR) / 2) / (XR - XL)
        if k == NT - 1:
            for m_, g_ in ((38, .9), (45, .7), (50, .9), (57, .6), (62, .8), (66, .6), (69, .6), (74, .7), (78, .5)): put(mb.stone(m_, 2.2), t, .5 + .2 * math.sin(m_), g_ * .62, .7)
            put(pad([50, 62, 66, 69], 3.4, .034), t - .03, .5, 1.0, .6); mi = -1; chord = "D"; last_t = t; last_note = 62; continue      # 太陽ができたら、旋律は頭に戻る
        if t - last_t < .09 and last_note is not None:
            tl = [m for m in mb.tones(chord, 50, 12) if m < last_note]; m = tl[-1] if tl else last_note - 12; last_note = m; g = .50
        else:
            mi += 1; m, ci = seq[mi % len(seq)]; g = .80 + .02 * k
            if mb.PROG[ci] != chord or t - last_t > 2.0:
                chord = mb.PROG[ci]; r_, t_, f_ = mb.TRI[chord]; put(pad([r_ - 12, r_, t_, f_], 4.5, .030), t - .02, .5, 1.0, .7)
            last_note = m
        last_t = t; put(mb.stone(m - 12, 2.4), t, pan, g * .8, .75); r_ = mb.TRI[chord][0]
        if k >= 4: put(mb.stone(r_ - 12, 2.8), t, pan, .30 + .05 * (k - 4), .5)
        if k >= 6: put(mb.stone(r_ - 24, 2.4), t, .5, .50, .5); put(mb.stone(mb.TRI[chord][2] - 12, 2.8), t, pan, .26, .5)
        if k >= 8: put(mb.stone(mb.TRI[chord][1], 2.8), t + .012, pan, .30, .5)
    TK = [mb.tok(1.0 - .045 * k) for k in range(NT)]; mt = np.array([m[0] for m in res["merges"]])
    for t, k, spd, x, y in res["toks"]:
        j = np.searchsorted(mt, t)
        if (j < len(mt) and mt[j] - t < .02) or (j > 0 and t - mt[j - 1] < .02): continue
        put(TK[k], t, .5 + .34 * (x - (XL + XR) / 2) / (XR - XL), min(.26, .05 + spd / 9000) * (.7 + .08 * k) * .3, .5)
    tt_ = np.arange(int(SR * 2.4)) / SR; irs = [np.convolve(np.random.default_rng(s_).normal(0, 1, len(tt_)) * np.exp(-tt_ * 1.6), np.ones(40) / 40, "same").astype(np.float32) * .02 for s_ in (11, 12)]
    B = SR * 30; L = len(tt_); tail = np.zeros((L, 2), np.float32); pk = 0.0
    for a in range(0, N, B):   # 残響：30秒ずつ、はみ出した分を次へ足す
        b = min(N, a + B); blk = np.zeros((b - a + L, 2), np.float32)
        for c in (0, 1): y_ = fftconvolve(snd[a:b, c], irs[c]); blk[:len(y_), c] = y_
        blk[:L] += tail; dry[a:b] += blk[:b - a]; tail = blk[b - a:b - a + L].copy() if b - a >= L else np.zeros((L, 2), np.float32); pk = max(pk, float(np.abs(dry[a:b]).max()))
    sos = butter(4, 15000, "low", fs=SR, output="sos"); zi = [sosfilt_zi(sos) * 0, sosfilt_zi(sos) * 0]; pk2 = 0.0
    out = np.lib.format.open_memmap("build_mergelong/mix.npy", "w+", np.float32, (N, 2))
    for a in range(0, N, B):
        b = min(N, a + B); x = np.tanh(dry[a:b] / pk * 1.5) / np.tanh(1.5)
        for c in (0, 1): x[:, c], zi[c] = sosfilt(sos, x[:, c], zi=zi[c])
        out[a:b] = x; pk2 = max(pk2, float(np.abs(x).max()))
    fo = int(SR * 3); out[N - fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        for a in range(0, N, B): w.writeframes((out[a:min(N, a + B)] * (.80 / pk2) * 32767).astype(np.int16).tobytes())
    for f_ in ("dry", "snd", "mix"): os.remove(f"build_mergelong/{f_}.npy")

if __name__ == "__main__":
    proc, on_frame = render_video("build_mergelong/v.mp4")
    # 合体の記録は simulate の中のリストに足されていく。描く側が同じリストを読めるよう、差しかえる
    import builtins
    res_holder = {}
    def hook(F):
        on_frame(F)
    # simulate の merges リストを外から見るため、小さく包む：1フレームごとに呼ばれる on_frame の前に、新しい合体を写す
    orig_sim = mb.simulate
    class Tap(list):
        def append(self, m):
            super().append(m); MERGES.append(m); ALLM.add(m[4])
            if m[5]: FIRSTS.append(m)
    import types
    src = orig_sim.__code__
    # merges は simulate の中の局所変数なので、list の代わりに Tap を使う版を作る
    import inspect, textwrap
    code = inspect.getsource(orig_sim).replace("drops = []; merges = [];", "drops = []; merges = P['tap'];")
    ns = {}; exec(compile(code, "simulate_tap", "exec"), mb.__dict__, ns); sim = ns["simulate"]
    t0 = time.time(); res = sim(SEED, P=dict(long=DUR, iv=IV, sunstay=STAY, on_frame=hook, tap=Tap()))
    proc.stdin.close(); proc.wait(); print("絵", round(time.time() - t0), "秒 / 太陽", len(res["suns"]), "個 / 合体", len(res["merges"]), "回 / 落とした星", len(res["drops"]), "個", flush=True)
    audio(res, "build_mergelong/a.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "build_mergelong/v.mp4", "-i", "build_mergelong/a.wav", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT], check=True)
    print(OUT, round(DUR / 60, 1), "分")
