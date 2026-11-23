"""雑学 UI シリーズの BGM（自作）：120BPM の柔らかいキック＋石の音のカノン進行の分散和音＋行の頭の小さなベル。
使い方: python3 tools/ui_bgm.py <ID>   → build_kaizo/<ID>/bgm.wav（kaizo3d build --bgm に渡す）"""
import json, sys, os, math, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harmony
SR = 44100
sid = sys.argv[1]; tl = json.load(open(f"nazo/kaizo/specs/{sid}_timeline.json")); sp = json.load(open(f"nazo/kaizo/specs/{sid}.json"))
bpm = sp.get("labels", {}).get("bpm", 120); B = 60 / bpm; total = tl["total"] + 1.5; n = int(SR * total); L = np.zeros(n); R = np.zeros(n)
mf = lambda m: 440 * 2 ** ((m - 69) / 12)
def stone(m, dec=2.6):
    f = mf(m); t = np.arange(int(SR * 2.2)) / SR
    s = (np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * f * 1.003 * t)) * np.exp(-t * dec) + .34 * np.sin(2 * np.pi * f * 2.76 * t + .7) * np.exp(-t * 7) + .15 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 15)
    nz = np.convolve(np.random.default_rng(m).normal(0, 1, len(t)), np.ones(5) / 5, "same") * np.exp(-t * 700) * .2
    return (s + nz) * np.minimum(1, t / .0008) * (f / 523.25) ** -.3
def kick():
    t = np.arange(int(SR * .35)) / SR; ph = 2 * np.pi * np.cumsum(52 + 70 * np.exp(-t * 30)) / SR; return np.sin(ph) * np.exp(-t * 9)
def hat():
    t = np.arange(int(SR * .05)) / SR; nz = np.random.default_rng(3).normal(0, 1, len(t)); nz -= np.convolve(nz, np.ones(6) / 6, "same"); return nz * np.exp(-t * 80) * .5
def add(t0, s, g, pan=.5):
    i = int(t0 * SR); k = min(len(s), n - i)
    if k > 0 and i >= 0: L[i:i + k] += s[:k] * g * (1 - pan) * 1.4; R[i:i + k] += s[:k] * g * pan * 1.4
K, Hh = kick(), hat(); b = 0; t = 0.0
while t < total - .5:
    add(t, K, .55 if b % 2 == 0 else .38); add(t + B / 2, Hh, .12, .6)
    r, q = harmony.CANON[int(t / (2 * B * 2)) % 8]; arp = [60 + r, 64 + r if 4 in q else 63 + r, 67 + r, 72 + r]
    for j in range(2): m = arp[(2 * b + j) % 4]; m = m - 12 if m > 79 else m; add(t + j * B / 2, stone(m), .16, .35 + .3 * ((2 * b + j) % 4) / 3)
    if b % 4 == 0: add(t, stone(36 + r if r >= 4 else 48 + r, 1.2), .22)
    t += B; b += 1
for bt in tl["beats"]: add(bt["t0"], stone(84, 4), .10, .55)
fxb = {ln.get("fx"): bt for ln, bt in zip(sp["lines"], tl["beats"])}
if "touch" in fxb:   # ギザギザを指でなぞる：1本ごとに「コッ」（上から下へ、音も下がる）
    tb = fxb["touch"]; t0 = tb["t0"] + .12 * tb["voice"]
    for i, m in enumerate([84, 83, 81, 79, 77, 76]): add(t0 + i * B / 2, stone(m, 5), .34, .6)
if "mark" in fxb:    # QR：目印が1拍に1つずつ入る（上がる3音）
    tb = fxb["mark"]; t0 = tb["t0"] + .3 * tb["voice"]
    for i, m in enumerate([76, 79, 84]): add(t0 + i * B, stone(m, 3), .36, .35 + .15 * i)
if "ratio" in fxb:   # QR：点が 1:1:3:1:1 の区切りを通るたびに1音
    tb = fxb["ratio"]; t0 = tb["t0"] + .38 * tb["voice"]; d = tb["voice"] * .5
    for u, m in zip([0, 1 / 7, 2 / 7, 5 / 7, 6 / 7, 1], [72, 76, 79, 76, 79, 84]): add(t0 + u * d, stone(m, 5), .34, .3 + .4 * u)
if "open" in fxb and "mark" in fxb:   # QR：広がる（1枚ごとに小さく）
    tb = fxb["open"]; t0 = tb["t0"] + .1 * tb["voice"]
    for i in range(12): add(t0 + i * .16, stone([79, 84, 86, 88][i % 4], 6), .16, .2 + .05 * i)
if "odd" in fxb:     # バーコードの検算：札を1枚ずつ足す音、3倍、合計、答え
    Q = B / 4
    for f, base, pan in [("odd", 72, .3), ("even", 74, .7)]:
        a0 = fxb[f]["t0"] + .12
        for j, st in enumerate([0, 2, 4, 5, 7, 9]): add(a0 + j * Q, stone(base + st, 6), .3, pan)
    for m in [79, 83, 86]: add(fxb["even"]["t0"] + 1.12, stone(m, 3), .2, .7)
    for m in [72, 76, 79]: add(fxb["sum"]["t0"], stone(m, 2.5), .22)
    tb = fxb["chk"]; add(tb["t0"] + .45 * tb["voice"], stone(88, 2.2), .36); add(tb["t0"] + .45 * tb["voice"], stone(84, 2.2), .25)
    tb = fxb["err"]; add(tb["t0"] + .3 * tb["voice"], stone(61, 3), .3); add(tb["t0"] + .3 * tb["voice"], stone(66, 3), .22)
    tb = fxb["beep"]; add(tb["t0"] + .62 * tb["voice"], stone(84, 2.5), .3); add(tb["t0"] + .62 * tb["voice"] + .09, stone(88, 2.5), .3)
    tb = fxb["all"]
    for j in range(int((tb["voice"] - .1) / Q)): add(tb["t0"] + .1 + j * Q, stone(77 + (j % 4) * 2, 8), .17, .2 + .05 * (j % 12))
for dly, g in [(.031, .3), (.067, .24), (.113, .18), (.171, .12)]:
    o = int(SR * dly); L[o:] += R[:-o] * g; R[o:] += L[:-o] * g
st = np.stack([L, R], 1); st = st / (np.abs(st).max() + 1e-9) * .8
os.makedirs(f"build_kaizo/{sid}", exist_ok=True); out = f"build_kaizo/{sid}/bgm.wav"
with wave.open(out, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())
print("BGM:", out, f"{total:.1f}秒")
