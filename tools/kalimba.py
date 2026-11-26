# kalimba.py — カリンバふうの音色（オーナー 11/27「音がキンキンしてる。カランコロンって感じのカリンバっぽい心地よい音色をとにかく追求したい。ブラーエコーもかけすぎない」）
#   これまでの stone（石琴）は、上の倍音（基音の 2.76・5.4・8.9 倍）と 0.8ms の立ち上がり・ノイズで、高い音ほど 8〜13kHz が鳴っていた → キンキン。
#   ここでは：
#     ・基音が主役。2倍音を少し（木の箱の「コ」）、金属の舌の2番目の振動（6.27倍）はごく短く小さく、5kHz を超えるなら鳴らさない
#     ・立ち上がり 3ms（爪ではじく丸さ）。はじいた瞬間に音程がほんの少し上から落ちる
#     ・箱の鳴り：250Hz 前後の短い胴鳴り（「コロン」の丸み）
#     ・最後に 3.6kHz から上をなだらかに落とす
#     ・残響は小さな部屋（0.8 秒）を 12% だけ。ぼかさない
#   使い方：from kalimba import note, room; x = note(midi, vel); y = room(stereo, send=.12)
import math
import numpy as np

SR = 48000
_c = {}

def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)

def _lp(x, fc):
    a = math.exp(-2 * math.pi * fc / SR); y = np.empty_like(x); z = 0.0
    # 1次の低域通過を2回（-12dB/oct）。長い配列でも速いように scipy があれば使う
    try:
        from scipy.signal import lfilter
        y = lfilter([1 - a], [1, -a], x); return lfilter([1 - a], [1, -a], y).astype(np.float32)
    except Exception:
        for i, v in enumerate(x): z = (1 - a) * v + a * z; y[i] = z
        return _lp_once(y, a)

def _lp_once(x, a):
    y = np.empty_like(x); z = 0.0
    for i, v in enumerate(x): z = (1 - a) * v + a * z; y[i] = z
    return y

def note(m, vel=1.0, length=None):
    """MIDI 番号 m のカリンバの1音（モノラル float32）。vel は 0..1（強いほど少し明るい）"""
    key = (int(m), round(vel, 2))
    if key in _c: return _c[key]
    f = mtof(m); dec = float(np.clip(1.9 * (440 / f) ** .45, .7, 3.2))   # 低い音ほど長く鳴る
    L = length or min(4.0, dec * 4.2); tt = np.arange(int(SR * L)) / SR
    glide = 1 + .004 * np.exp(-tt / .025)                                  # はじいた瞬間だけ少し高い
    ph = 2 * np.pi * f * np.cumsum(glide) / SR
    x = np.sin(ph) * np.exp(-tt / dec)
    x += .22 * np.sin(2 * ph + .4) * np.exp(-tt / (dec * .28))             # 2倍音（箱の「コ」）
    x += .07 * np.sin(3 * ph + 1.1) * np.exp(-tt / (dec * .12))
    f2 = f * 6.27
    if f2 < 5000: x += .05 * vel * np.sin(2 * np.pi * f2 * tt + .3) * np.exp(-tt / .035) * (1 - f2 / 5000)   # 舌の2番目の振動（「カ」）。ごく短く
    body = np.sin(2 * np.pi * 245 * tt) * np.exp(-tt / .045) * .16 + np.sin(2 * np.pi * 410 * tt + 1) * np.exp(-tt / .03) * .07   # 胴鳴り（「コロン」）
    x += body * min(1.0, 330 / f + .25)
    nz = np.random.default_rng(int(m)).normal(0, 1, len(tt)); nz = _lp(nz.astype(np.float32), 1800) * np.exp(-tt / .006) * .25   # 爪の当たり（やわらかく）
    x += nz * vel
    x *= .5 - .5 * np.cos(np.pi * np.minimum(1, tt / .003))                # 立ち上がり 3ms
    x *= np.minimum(1, (L - tt) / .05)
    x = _lp(x.astype(np.float32), 3600 + 1200 * vel)
    x *= (f / 523.25) ** -.25 * (.75 + .25 * vel)
    _c[key] = x.astype(np.float32); return _c[key]

def room(st, send=.12, rt=.8, seed=7):
    """小さな部屋の残響を send だけ足す（st: (N,2)）。ぼかしすぎない"""
    from scipy.signal import fftconvolve
    n = int(SR * rt * 1.4); tt = np.arange(n) / SR; out = st.copy()
    for c in (0, 1):
        r = np.random.default_rng(seed + c).normal(0, 1, n).astype(np.float32) * np.exp(-tt * 6.9 / rt)
        r = _lp(r, 3000); r[: int(SR * .012)] = 0; r /= np.sqrt((r ** 2).sum()) + 1e-9
        out[:, c] += fftconvolve(st[:, c], r)[: len(st)] * send
    return out
