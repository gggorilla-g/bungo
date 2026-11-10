# bigface/music.py — 『ビッグフェイスの〇〇』の共通BGM（オリジナル。ここで音を合成する）
# どの曲にもメインテーマの短い音型（MOTIF）を入れ、曲ごとに形を変える（仕様書 08）。
#   bgm02(秒)：なんだかへんだ 104 BPM 丸い低音（ぽん）＋クラリネット（音型の1音を半音ずらして「へん」にする）
#   bgm04(秒)：ひとりぼっち 68 BPM フェルトピアノ（音型を短調でゆっくり）
#   bgm05(秒)：そういうことか 76 BPM マリンバ＋やわらかい弦（音型を長調で、最後は和音で止める）
import numpy as np
SR = 48000
A4 = 440.0
def hz(n): return A4 * 2 ** ((n - 69) / 12)          # MIDI 番号 → 周波数
# メインテーマの音型（拍）：ミ ソ ラ ソ ミ レ ド
MOTIF = [(64, 1), (67, .5), (69, .5), (67, 1), (64, 1), (62, 1), (60, 2)]

def _env(L, a, d, s=0.0):
    t = np.arange(L) / SR; e = np.minimum(1, t / max(a, 1e-4)); return e * (s + (1 - s) * np.exp(-t / d))
def _lp(x, k):
    if k <= 1: return x
    c = np.ones(k) / k; return np.convolve(x, c, "same")

def toypiano(f, dur):
    L = int(dur * SR); t = np.arange(L) / SR
    return (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 9)) * _env(L, 0.002, 0.35)
def marimba(f, dur):
    L = int(dur * SR); t = np.arange(L) / SR
    return (np.sin(2 * np.pi * f * t) * _env(L, 0.004, 0.45) + 0.25 * np.sin(2 * np.pi * f * 3.93 * t) * _env(L, 0.002, 0.05))
def pizz(f, dur, rng=np.random.default_rng(5)):        # はじいた弦（カープラス・ストロング）
    L = int(dur * SR); P = max(2, int(SR / f)); buf = rng.uniform(-1, 1, P); out = np.zeros(L)
    for i in range(L): out[i] = buf[i % P]; buf[i % P] = 0.5 * (buf[i % P] + buf[(i + 1) % P]) * 0.993
    return _lp(out, 3) * _env(L, 0.001, 0.18)
def softpluck(f, dur):                                  # 丸く短い「ぽん」（倍音少なめ、すぐ消える）
    L = int(dur * SR); t = np.arange(L) / SR
    return (np.sin(2 * np.pi * f * t) + 0.15 * np.sin(4 * np.pi * f * t) * np.exp(-t * 20)) * _env(L, 0.006, 0.09)
def clarinet(f, dur):
    L = int(dur * SR); t = np.arange(L) / SR; vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.3)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    x = sum(np.sin(k * ph) / k for k in (1, 3, 5, 7)) * 0.6
    e = np.minimum(1, t / 0.04) * np.minimum(1, (dur - t) / 0.06).clip(0, 1)
    return _lp(x, 4) * e
def feltpiano(f, dur):
    L = int(dur * SR); t = np.arange(L) / SR
    x = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) * np.exp(-t * 3) + 0.1 * np.sin(6 * np.pi * f * t) * np.exp(-t * 6)
    return _lp(x * _env(L, 0.012, 1.4), 6)
def strings(f, dur):
    L = int(dur * SR); t = np.arange(L) / SR
    x = sum(np.sin(2 * np.pi * f * (1 + dt) * t + p) for dt, p in ((0, 0), (0.003, 1.1), (-0.003, 2.3)))
    x += 0.3 * sum(np.sin(4 * np.pi * f * (1 + dt) * t) for dt in (0.002, -0.002))
    e = np.minimum(1, t / 0.5) * np.minimum(1, (dur - t) / 0.6).clip(0, 1)
    return _lp(x * e * 0.25, 10)

def _place(buf, x, at, g):
    i = int(at * SR); j = min(len(buf), i + len(x))
    if i < len(buf): buf[i:j] += g * x[: j - i]

def bgm02(sec):
    """なんだかへんだ：104 BPM。ピチカートの低音（ド・ソ）＋クラリネットの音型（ラを半音下げる）"""
    bpm = 104; b = 60 / bpm; out = np.zeros(int((sec + 2) * SR))
    bass = [48, 55, 50, 55]
    for k in range(int(sec / b) + 1): _place(out, softpluck(hz(bass[k % 4]), 0.4), k * b, 0.32)   # 弦（ギターっぽい）をやめて丸い音に（11/10 ゲンタさん「ギターみたいな音がうるさい」）
    mot = [(n - 1 if n == 69 else n, d) for n, d in MOTIF]          # 1音だけ「へん」
    t = 2 * b
    while t < sec - 1:
        for n, d in mot:
            _place(out, clarinet(hz(n - 12), d * b * 0.85), t, 0.22); t += d * b
        t += 2 * b
    for k in range(int(sec / (b * 2))): _place(out, toypiano(hz(79 if k % 2 else 76), 0.3), k * 2 * b + b * 1.5, 0.08)
    return out[: int(sec * SR)]

def bgm04(sec):
    """ひとりぼっち：68 BPM。音型を短調（ラ・ド・レ・ド・ラ・ソ・ミ）で、フェルトピアノ。左手は長い和音"""
    bpm = 68; b = 60 / bpm; out = np.zeros(int((sec + 3) * SR))
    mot = [(69, 1), (72, .5), (74, .5), (72, 1), (69, 1), (67, 1), (64, 2)]
    chords = [[45, 52, 57], [41, 48, 53], [43, 50, 55], [45, 52, 57]]
    t = 0.0; k = 0
    while t < sec:
        for n in chords[k % 4]: _place(out, feltpiano(hz(n), 4 * b + 1), t, 0.16)
        t += 4 * b; k += 1
    t = b
    for n, d in mot:
        if t > sec - 1: break
        _place(out, feltpiano(hz(n), d * b + 1.2), t, 0.3); t += d * b * 1.15     # 少しゆっくり、ためらうように
    return out[: int(sec * SR)]

def bgm05(sec):
    """そういうことか：76 BPM。マリンバで音型（長調）＋やわらかい弦。最後は C の和音で止める"""
    bpm = 76; b = 60 / bpm; out = np.zeros(int((sec + 4) * SR))
    chords = [[48, 55, 64], [53, 60, 69], [50, 57, 65], [48, 55, 64]]
    t = 0.0; k = 0
    while t < sec - 4 * b:
        for n in chords[k % 4]: _place(out, strings(hz(n), 4 * b), t, 0.18)
        for j in range(4): _place(out, marimba(hz(chords[k % 4][0] + 12), 0.5), t + j * b, 0.14)
        t += 4 * b; k += 1
    tm = 2 * b
    for rep in range(3):
        for n, d in MOTIF:
            if tm > sec - 3: break
            _place(out, marimba(hz(n + (12 if rep == 1 else 0)), d * b + 0.4), tm, 0.32); tm += d * b
        tm += 2 * b
    end = sec - 2.6
    for n in [48, 55, 60, 64, 67]: _place(out, strings(hz(n), 2.6), end, 0.15); _place(out, marimba(hz(n + 12), 2.0), end, 0.12)
    return out[: int(sec * SR)]
