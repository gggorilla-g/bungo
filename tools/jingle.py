# tools/jingle.py — 締めのジングル「レッツ・脳とけ！」（オリジナル曲）。ずんだもんの声に1音ずつ音程を付けて歌わせ、
#   簡単な伴奏（ベース・コード・ドラム）を足す。出力: assets/jingle_letsnotoke.wav（24kHz モノラル）
import json, math, sys, wave
import numpy as np
sys.path.insert(0, "src")
import render

SR = 24000
BPM = 160
B = 60 / BPM                         # 1拍 = 0.375秒（締めのダンスの拍も合わせる）
NOTE = {"A4": 440.0, "B4": 493.9, "C#5": 554.4, "D5": 587.3, "E5": 659.3, "F#5": 740.0}
# 「のうが とける ざつがく」。日本語の高低（脳＝高→低、とける＝低→高、ざつがく＝低→高）に沿ったメロディ（ニ長調）
PHRASES = [
    (0.0, "のうがとける", [("E5", 0.5), ("D5", 0.5), ("B4", 0.5), ("A4", 0.5), ("D5", 0.5), ("D5", 0.5)]),
    (3.5, "ざつがく",     [("A4", 0.5), ("D5", 0.5), ("E5", 0.5), ("D5", 1.5)]),
]
INTRO = 1.0                          # 歌の前に1拍
SONG_BEATS = 5.5                     # 歌の長さ（拍）


def sing(text, notes):
    """ずんだもんの声で、1音（モーラ）ずつ音の高さと長さを決めて歌わせる"""
    render.set_voice("0.vvm", 3)
    aq = render.syn().create_audio_query(text, style_id=render.STYLE)
    moras = [m for ap in aq.accent_phrases for m in ap.moras]
    assert len(moras) == len(notes), ([m.text for m in moras], len(notes))
    for m, (note, beats) in zip(moras, notes):
        if m.vowel in ("A", "I", "U", "E", "O"):     # 無声化した母音も声に出す
            m.vowel = m.vowel.lower()
        dur = beats * B
        c = min(m.consonant_length or 0.0, 0.07)
        if m.consonant is not None:
            m.consonant_length = c
        m.vowel_length = max(0.05, dur - c)
        m.pitch = math.log(NOTE[note])
    aq.pre_phoneme_length = 0.0; aq.post_phoneme_length = 0.05
    aq.speed_scale = 1.0; aq.intonation_scale = 1.0; aq.volume_scale = 1.5
    open("build_jingle_voice.wav", "wb").write(render.syn().synthesis(aq, style_id=render.STYLE))
    with wave.open("build_jingle_voice.wav") as w:
        sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if sr != SR:
        x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x).astype(np.float32)
    return x


def tone(f, dur, shape="square", vol=0.2, dec=6.0):
    t = np.arange(int(dur * SR)) / SR
    if shape == "square":
        y = np.sign(np.sin(2 * np.pi * f * t)) * 0.6 + np.sin(2 * np.pi * f * t) * 0.4
    elif shape == "tri":
        y = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t))
    else:
        y = np.sin(2 * np.pi * f * t)
    env = np.minimum(1, t / 0.005) * np.exp(-t * dec)
    return y * env * vol


def kick():
    t = np.arange(int(0.25 * SR)) / SR
    f = 120 * np.exp(-t * 18) + 45
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14) * 0.7


def clap():
    t = np.arange(int(0.18 * SR)) / SR
    return np.random.default_rng(1).normal(0, 1, len(t)) * np.exp(-t * 28) * 0.25


def add(buf, x, at):
    i = int(at * SR)
    buf[i:i + len(x)] += x[:max(0, len(buf) - i)]


def hat():
    t = np.arange(int(0.05 * SR)) / SR
    return np.random.default_rng(3).normal(0, 1, len(t)) * np.exp(-t * 90) * 0.12


def main(out="assets/jingle_letsnotoke.wav"):
    total = INTRO * B + SONG_BEATS * B + 1.5
    buf = np.zeros(int(total * SR), np.float32)
    # 頭：スネアのダダダダ（16分）で勢いをつける
    for q in range(4):
        add(buf, clap() * (0.6 + 0.15 * q), q * B / 4)
    # ドラム：キック4つ打ち＋手拍子の裏＋8分のハイハット
    for b in range(int(SONG_BEATS + 0.5)):
        at = INTRO * B + b * B
        add(buf, kick() * 1.2, at)
        if b % 2:
            add(buf, clap() * 1.3, at)
        add(buf, hat(), at); add(buf, hat(), at + B / 2)
    # ベース（8分で刻む）とリード（歌のメロディをなぞる明るい音）
    bass = ["D5", "B4", "A4", "D5", "A4", "D5"]          # D - Bm - A - D - A - D（ベースは2オクターブ下）
    for b in range(len(bass)):
        for h in (0, 0.5):
            add(buf, tone(NOTE[bass[b]] / 4, B * 0.45, "square", 0.16, 6), INTRO * B + (b + h) * B)
    for st, _, notes in PHRASES:                       # リード：歌のメロディをなぞる
        at = INTRO * B + st * B
        for note, beats in notes:
            add(buf, tone(NOTE[note] * 2, beats * B * 0.9, "square", 0.04, 3), at)
            at += beats * B
    # 終わり：E メジャーのジャーン＋シンバル
    end = INTRO * B + SONG_BEATS * B
    for f in (293.7, 370.0, 440.0, 587.3, 740.0):         # D メジャーのジャーン
        add(buf, tone(f, 1.3, "square", 0.07, 2.5), end)
    add(buf, np.random.default_rng(2).normal(0, 1, int(1.2 * SR)) * np.exp(-np.arange(int(1.2 * SR)) / SR * 3.5) * 0.12, end)
    add(buf, kick() * 1.2, end)
    # 歌（伴奏より前に出す）
    vox = np.zeros_like(buf)
    for st, text, notes in PHRASES:
        add(vox, sing(text, notes) * 1.4, INTRO * B + st * B - 0.02)
    buf += vox
    with wave.open(out.replace(".wav", "_voice.wav"), "wb") as w:   # 口パク用（歌声だけ）
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(vox, -1, 1) * 32767).astype(np.int16).tobytes())
    buf = np.tanh(buf * 1.6) / np.tanh(1.6)        # 軽く潰して元気な音圧に
    buf = buf / max(1e-6, np.abs(buf).max()) * 0.92
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((buf * 32767).astype(np.int16).tobytes())
    print(out, f"{total:.2f}s")


if __name__ == "__main__":
    main(*sys.argv[1:])
