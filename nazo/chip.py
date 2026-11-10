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


def groove(dur, bpm=124, seed=5):
    """11/10 ゲンタさん「デザインあ」：木琴のような丸い音の短いくり返し＋キック・手拍子・シェイカー。
    リズムで画面を切る前提のミニマルな曲（自作。権利の心配なし）"""
    step = 60 / bpm / 4
    n = int(SR * step)
    total = int(SR * dur) + n * 16
    out = np.zeros(total)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    def mar(f, amp):   # 木琴っぽい音（正弦波＋倍音、すぐ減衰）
        return amp * (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 3.9 * t) * np.exp(-t * 60)) * np.exp(-t * 14)
    # 4小節でひと回りする音型（C D E G A の5音）
    sc = [0, 2, 4, 7, 9, 12, 14, 16]
    mel = [0, None, 4, 2, 5, None, 3, 4, 0, None, 4, 5, 6, 5, 3, None]
    bass = [0, 0, -3, -5]
    i = s = 0
    while i < total - n:
        p = s % 16; bar = (s // 16) % 4
        m = mel[p]
        if m is not None:
            out[i:i + n] += mar(523.25 * 2 ** ((sc[m] + bass[bar] * 0) / 12), 0.30)
        if p in (0, 6, 8, 14):
            out[i:i + n] += mar(130.81 * 2 ** (bass[bar] / 12), 0.42)
        if p % 4 == 0:   # キック
            out[i:i + n] += 0.55 * np.sin(2 * np.pi * np.cumsum(55 * (1 + 2.5 * np.exp(-t * 35))) / SR) * np.exp(-t * 16)
        if p in (4, 12):   # 手拍子
            out[i:i + n] += 0.22 * rng.standard_normal(n) * np.exp(-t * 45)
        out[i:i + n] += 0.05 * rng.standard_normal(n) * np.exp(-t * 160) * (1.0 if p % 2 else 0.6)   # シェイカー
        i += n; s += 1
    out = out[: int(SR * dur)]
    fade = int(SR * 0.5)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out / (np.abs(out).max() + 1e-9)


def jingle():
    """番組の頭とおしまいの短い音（ド・ミ・ソ・ド＋ポン）"""
    t = np.arange(int(SR * 0.16)) / SR
    notes = [523.25, 659.25, 783.99, 1046.5]
    out = []
    for k, f in enumerate(notes):
        a = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 3.9 * t) * np.exp(-t * 60)) * np.exp(-t * (14 if k < 3 else 5))
        out.append(a)
    y = np.concatenate(out + [np.zeros(int(SR * 0.3))])
    return y / (np.abs(y).max() + 1e-9)
