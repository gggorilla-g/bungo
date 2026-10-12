# tools/bgm.py — チャンネルBGMをプログラムで一から合成する（完全オリジナル・権利フリー）
#   python tools/bgm.py nazo   → assets/bgm_nazo.m4a   短調の静かな牧歌（低い持続音＋和音＋笛＋オルゴール）
#   python tools/bgm.py bungo  → assets/bgm_bungo.m4a  静かな牧歌（オルゴール＋やわらかい和音）
# どちらも約96秒で、頭と尻がつながるループ。動画側で尺に合わせて繰り返す。
import os, subprocess, sys
import numpy as np

SR = 44100
rng = np.random.default_rng(7)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def env(n, a, r):
    e = np.ones(n)
    a, r = int(a * SR), int(r * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if r: e[-r:] *= np.linspace(1, 0, r)
    return e


def flute(f, dur, amp=0.18):
    """息の混じった柔らかい笛。ゆっくりしたビブラートつき"""
    n = int(dur * SR); t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 4.8 * t) * np.clip(t / 0.6, 0, 1)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    tone = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
    breath = np.convolve(rng.standard_normal(n), np.ones(30) / 30, "same") * 0.02
    return (tone + breath) * env(n, 0.25, min(0.8, dur * 0.5)) * amp


def bell(f, dur, amp=0.12):
    """オルゴール風。倍音が速く減衰する"""
    n = int(dur * SR); t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * t) * np.exp(-t * 1.6)
         + 0.45 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 4.0)
         + 0.2 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 7.0))
    return s * env(n, 0.003, 0.05) * amp


def pad(freqs, dur, amp=0.05):
    n = int(dur * SR); t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.003 * t) for f in freqs)
    return s / len(freqs) * env(n, 2.0, 2.0) * amp


def drone(dur, root, amp=0.10, uneasy=True):
    """低く続く持続音。わずかにずらした2本でうねりを出す。不穏版は半音上を薄く混ぜる"""
    n = int(dur * SR); t = np.arange(n) / SR
    f = midi(root); lfo = 0.5 + 0.5 * np.sin(2 * np.pi * t / 24)
    s = np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.004 * t) + 0.6 * np.sin(2 * np.pi * f * 1.5 * t)
    if uneasy:
        s += 0.18 * lfo * np.sin(2 * np.pi * midi(root + 13) * t)   # 短9度＝不穏の芯
    return s * amp * (0.75 + 0.25 * lfo)


def place(buf, sig, at):
    i = int(at * SR); j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i]


def reverb(x, sec=2.6, wet=0.35):
    n = int(sec * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 3.0)
    ir /= np.abs(ir).sum() / 8
    y = np.fft.irfft(np.fft.rfft(x, len(x) + n) * np.fft.rfft(ir, len(x) + n))[: len(x)]
    return x * (1 - wet) + y * wet


def make_loop(body, total):
    """尻尾の残響を頭に重ねて、継ぎ目のないループにする"""
    tail = body[total:]
    out = body[:total].copy()
    out[: len(tail)] += tail
    return out


def nazo(total=96.0):
    """短調の静かな牧歌。不穏さは低い持続音と短調だけで出し、音同士をぶつけない（v2: 不協和を撤去）"""
    buf = np.zeros(int((total + 4) * SR))
    place(buf, drone(total + 4, 38, amp=0.07, uneasy=False), 0)   # D2＋5度
    chords = [[50, 53, 57], [46, 50, 53], [48, 52, 55], [45, 48, 52]]   # Dm B♭ C Am
    for i, at in enumerate(np.arange(0, total, 12)):
        place(buf, pad([midi(n) for n in chords[i % 4]], 13, amp=0.035), at)
    phrase = [(62, 1.5), (65, 1.0), (67, 1.5), (69, 3.0), (67, 1.0), (65, 1.0), (64, 4.0),
              (62, 1.5), (65, 1.0), (69, 1.5), (70, 3.0), (69, 1.0), (67, 1.0), (62, 4.0)]
    t = 6.0
    while t < total - 20:
        for note, d in phrase:
            place(buf, flute(midi(note), d * 1.1, amp=0.13), t); t += d
        t += 8.0
    for at in np.arange(12, total - 6, 24):
        for k, note in enumerate([74, 77, 81, 77]):
            place(buf, bell(midi(note), 3.5, amp=0.07), at + k * 0.6)
    return make_loop(reverb(buf, wet=0.4), int(total * SR))


def bungo(total=96.0):
    buf = np.zeros(int((total + 4) * SR))
    place(buf, drone(total + 4, 45, amp=0.05, uneasy=False), 0)   # A2、穏やか
    chords = [[57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 56, 59]]   # Am F G E
    for i, at in enumerate(np.arange(0, total, 12)):
        place(buf, pad([midi(n) for n in chords[i % 4]], 13), at)
    melody = [76, 72, 74, 71, 72, 69, 71, 68]
    for i, at in enumerate(np.arange(3, total - 4, 3)):
        place(buf, bell(midi(melody[i % len(melody)]), 4.0, amp=0.09), at)
    return make_loop(reverb(buf, wet=0.4), int(total * SR))


if __name__ == "__main__":
    which = sys.argv[1]
    x = {"nazo": nazo, "bungo": bungo}[which]()
    x = x / np.abs(x).max() * 0.8
    os.makedirs("assets", exist_ok=True)
    wav = f"assets/bgm_{which}.wav"
    import wave
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "aac", "-b:a", "128k",
                    f"assets/bgm_{which}.m4a"], check=True)
    os.remove(wav)
    print("ok", which)
