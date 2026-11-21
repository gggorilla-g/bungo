"""短い単音を合成する。実行時は samples/ に試聴用 WAV を生成する。"""

from pathlib import Path
import wave

import numpy as np

SAMPLE_RATE = 48_000


def _tone(f0, sr, duration, attack_ms, cutoff, modes, glide=0.0):
    """modes は (周波数比, 相対振幅, 振幅の時定数 ms)。"""
    if not np.isfinite(f0) or not 0 < f0 < 0.45 * sr or sr < 8000:
        raise ValueError("sr >= 8000、0 < f0 < 0.45 * sr が必要です")
    t = np.arange(round(sr * duration), dtype=float) / sr
    glide_tau = 0.018
    cycles = f0 * (t + glide * glide_tau * np.expm1(-t / glide_tau))
    sound = np.zeros_like(t)
    for ratio, amplitude, decay_ms in modes:
        hz = f0 * ratio
        if hz >= 0.45 * sr:
            continue
        # 各モードの周波数における、2次 Butterworth LP の振幅重み。
        weight = 1 / np.sqrt(1 + (hz / cutoff) ** 4)
        sound += amplitude * weight * np.exp(-1000 * t / decay_ms) * np.sin(
            2 * np.pi * ratio * cycles
        )

    attack = 0.5 - 0.5 * np.cos(np.pi * np.minimum(1, 1000 * t / attack_ms))
    release_t = (len(t) - 1 - np.arange(len(t))) / sr
    release = 0.5 - 0.5 * np.cos(np.pi * np.minimum(1, release_t / 0.020))
    return sound * attack * release


def glass(f0=523.251, sr=SAMPLE_RATE):
    return _tone(f0, sr, 0.45, 4, 2600,
                 [(1, 1, 78), (2.32, .34, 43), (4.16, .24, 25), (5.43, .15, 15)])


def bell(f0=523.251, sr=SAMPLE_RATE):
    return _tone(f0, sr, 0.92, 8, 2300,
                 [(.5, .25, 175), (1, 1, 165), (1.20, .23, 95),
                  (1.50, .18, 72), (2.03, .17, 45), (2.62, .13, 30)])


def marimba(f0=523.251, sr=SAMPLE_RATE):
    return _tone(f0, sr, 0.41, 5, 2200,
                 [(1, 1, 65), (4, .37, 24), (9.9, .16, 10)])


def kalimba(f0=523.251, sr=SAMPLE_RATE):
    return _tone(f0, sr, 0.60, 6, 2500,
                 [(1, 1, 110), (2.02, .27, 55), (3.08, .19, 32), (5.05, .11, 15)])


def xylophone(f0=523.251, sr=SAMPLE_RATE):
    return _tone(f0, sr, 0.20, 2.5, 3200,
                 [(1, 1, 28), (3, .52, 15), (6.2, .24, 8)])


def water_drop(f0=523.251, sr=SAMPLE_RATE):
    return _tone(f0, sr, 0.32, 4, 2000,
                 [(1, 1, 49), (2, .26, 26), (3.1, .11, 16)], glide=0.36)


def soft_pad(f0=523.251, sr=SAMPLE_RATE):
    return _tone(f0, sr, 1.20, 85, 1400,
                 [(1, 1, 250), (2, .24, 220), (3, .13, 175), (4, .06, 125)])


def music_box(f0=523.251, sr=SAMPLE_RATE):
    return _tone(f0, sr, 0.72, 3, 3000,
                 [(1, 1, 125), (2, .42, 65), (3, .23, 38), (4.06, .14, 26),
                  (6.75, .13, 14)])


RECIPES = {recipe.__name__: recipe for recipe in (
    glass, bell, marimba, kalimba, xylophone, water_drop, soft_pad, music_box
)}


def write_samples():
    """同じ基準音・単音ピークで比較できる、モノラルの試聴ファイル。"""
    directory = Path(__file__).resolve().parent / "samples"
    directory.mkdir(exist_ok=True)
    silence = np.zeros(round(0.050 * SAMPLE_RATE))
    for name, recipe in RECIPES.items():
        signal = recipe()
        signal *= 10 ** (-12 / 20) / np.max(np.abs(signal))
        pcm = np.rint(np.concatenate((silence, signal, silence)) * 32767).astype("<i2")
        with wave.open(str(directory / f"{name}.wav"), "wb") as output:
            output.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
            output.writeframes(pcm.tobytes())


if __name__ == "__main__":
    write_samples()
