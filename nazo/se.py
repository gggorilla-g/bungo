# nazo/se.py — さりげない効果音（すべて自前で合成。素材の権利問題なし）
#   mix(wav_path, [(名前, 秒, 音量倍率), ...]) で、セグメントの音声wavに重ねる
#   派手にしない：ピークは -16dBFS 前後、短く、高すぎない音。同じ音が続かないよう、種類を回して使う
import wave
import numpy as np

SR = 24000
_rng = np.random.default_rng(11)


def _t(d):
    return np.arange(int(SR * d)) / SR


def _env(t, a=0.004, k=12.0):
    e = np.exp(-t * k)
    n = int(SR * a)
    if n:
        e[:n] *= np.linspace(0, 1, n)
    return e


def _bp_noise(d, lo, hi):
    """帯域を絞ったノイズ（FFTで削る）"""
    n = int(SR * d)
    x = _rng.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    y = np.fft.irfft(X, n)
    return y / (np.abs(y).max() + 1e-9)


def pop(f0=700, d=0.12):
    t = _t(d)
    f = f0 * (1.0 + 0.6 * np.exp(-t * 40))          # 少し上から落ちる
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * _env(t, 0.002, 28)


def tick(f0=2200, d=0.05):
    t = _t(d)
    return (0.6 * np.sin(2 * np.pi * f0 * t) + 0.4 * _bp_noise(d, 1500, 5000)) * _env(t, 0.001, 90)


def whoosh(d=0.45, lo=300, hi=3000, rise=0.55):
    t = _t(d)
    x = _bp_noise(d, lo, hi)
    e = np.where(t < d * rise, (t / (d * rise)) ** 2, np.exp(-(t - d * rise) * 12))
    return x * e


def chime(notes=(988, 1319), gap=0.11, d=0.6):
    t = _t(d)
    y = np.zeros_like(t)
    for i, f in enumerate(notes):
        s = int(SR * i * gap)
        tt = t[: len(t) - s]
        y[s:] += (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * f * 2.01 * tt)) * _env(tt, 0.003, 7)
    return y


def thud(d=0.35):
    t = _t(d)
    f = 95 * (1 + 0.5 * np.exp(-t * 30))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(t, 0.003, 10)


def shimmer(d=0.7):
    t = _t(d)
    y = sum(np.sin(2 * np.pi * f * t + p) * _env(t - dt, 0.002, 6) * (t >= dt)
            for f, p, dt in ((2637, 0.0, 0.0), (3136, 1.0, 0.06), (3951, 2.0, 0.12), (3520, 0.5, 0.18)))
    return y * 0.5


def paper(d=0.22):
    t = _t(d)
    return _bp_noise(d, 800, 6000) * np.sin(np.pi * t / d) ** 2


def ding(f=1568, d=0.7):
    t = _t(d)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 8)) * _env(t, 0.002, 5)


# 名前 → (波形, 基本の音量)。音量はピークに対する倍率（声よりかなり小さく）
LIB = {
    "pop_lo":   (lambda: pop(520), 0.16),
    "pop_mid":  (lambda: pop(760), 0.15),
    "pop_hi":   (lambda: pop(1040), 0.13),
    "tick":     (lambda: tick(), 0.12),
    "tick_lo":  (lambda: tick(1500), 0.12),
    "whoosh_s": (lambda: whoosh(0.32, 500, 4000), 0.12),
    "whoosh_l": (lambda: whoosh(0.7, 250, 2500, 0.65), 0.13),
    "chime_a":  (lambda: chime((988, 1319)), 0.14),
    "chime_b":  (lambda: chime((880, 1175, 1568), 0.08), 0.12),
    "chime_c":  (lambda: chime((1319, 988)), 0.13),
    "thud":     (lambda: thud(), 0.22),
    "shimmer":  (lambda: shimmer(), 0.10),
    "paper":    (lambda: paper(), 0.10),
    "ding":     (lambda: ding(), 0.12),
}
_cache = {}


def sound(name):
    if name not in _cache:
        f, g = LIB[name]
        y = f()
        _cache[name] = y / (np.abs(y).max() + 1e-9) * g
    return _cache[name]


def mix(wav_path, events):
    """wav（24kHz・モノラル・16bit）に効果音を重ねて上書きする。events = [(名前, 秒, 倍率)]"""
    if not events:
        return
    with wave.open(wav_path) as w:
        p = w.getparams()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    sr = p.framerate
    for name, at, k in events:
        s = sound(name)
        if sr != SR:   # 念のため（通常は24kHz）
            s = np.interp(np.arange(int(len(s) * sr / SR)) * SR / sr, np.arange(len(s)), s)
        i = int(at * sr)
        if i >= len(x):
            continue
        j = min(len(x), i + len(s))
        x[i:j] += s[: j - i] * k
    with wave.open(wav_path, "wb") as o:
        o.setparams(p)
        o.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


# 種類を回して使う（同じ音が続かないように）
ROT = {
    "card":   [("chime_a", "paper"), ("chime_b", "whoosh_s"), ("chime_c", "paper")],
    "words":  ["pop_mid", "pop_hi", "pop_lo"],
    "cut":    ["paper", "whoosh_s", "tick_lo"],
}
_count = {}


def pick(kind):
    lst = ROT[kind]
    n = _count.get(kind, 0)
    _count[kind] = n + 1
    return lst[n % len(lst)]
