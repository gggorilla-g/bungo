# nazo/chip.py — 雑学ショート用の自作BGM（8ビット風のループ。権利の心配なし）
#   bgm(秒数, 種類) -> 24kHzモノラルの波形（-1〜1）。声の下に小さく敷く前提
import numpy as np

SR = 24000
PATTERNS = {
    # (BPM, ベースのルート列（半音）, メロディの音列（半音、Noneは休符）)
    "bounce": (150, [0, 0, 5, 7], [12, None, 15, 12, 19, None, 17, 15, 12, None, 15, 17, 19, 22, 19, None]),
    "silly":  (138, [0, 3, 5, 3], [7, 7, None, 10, 12, None, 10, 7, 5, None, 3, 5, 7, None, 12, None]),
    "hyper":  (168, [0, 7, 5, 3], [12, 15, 19, 15, 12, 15, 19, 24, 22, 19, 15, 19, 22, 19, 15, 12]),
}


def _sq(f, n, duty=0.5):
    ph = (np.arange(n) * f / SR) % 1.0
    return np.where(ph < duty, 1.0, -1.0)


def bgm(dur, kind="bounce", root=220.0):
    bpm, bass, mel = PATTERNS[kind]
    step = 60 / bpm / 4                    # 16分音符
    n_step = int(SR * step)
    total = int(SR * dur) + n_step * 16
    out = np.zeros(total)
    rng = np.random.default_rng(3)
    i = 0
    s = 0
    while i < total - n_step:
        bar_pos = s % 16
        env = np.exp(-np.arange(n_step) / SR * 18)
        # ベース（8分ごと）
        if bar_pos % 2 == 0:
            r = bass[(s // 16) % len(bass)]
            f = root / 2 * 2 ** (r / 12)
            out[i:i + n_step] += 0.35 * _sq(f, n_step, 0.5) * np.exp(-np.arange(n_step) / SR * 6)
        # メロディ
        m = mel[bar_pos]
        if m is not None:
            r = bass[(s // 16) % len(bass)]
            f = root * 2 ** ((m + r) / 12)
            out[i:i + n_step] += 0.22 * _sq(f, n_step, 0.25) * env
        # ハイハット（16分）とキック（4分）
        out[i:i + n_step] += 0.08 * rng.standard_normal(n_step) * np.exp(-np.arange(n_step) / SR * 120)
        if bar_pos % 4 == 0:
            t = np.arange(n_step) / SR
            out[i:i + n_step] += 0.5 * np.sin(2 * np.pi * np.cumsum(60 * (1 + 2 * np.exp(-t * 40))) / SR) * np.exp(-t * 18)
        i += n_step
        s += 1
    out = out[: int(SR * dur)]
    fade = int(SR * 0.6)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out / (np.abs(out).max() + 1e-9)
