"""怪談のBGM（自前で合成。素材の権利問題なし）：低いうなり＋遠い風＋まれに遠くの鈴。
  python kaidan/ambient.py assets/bgm_kaidan.mp3 [秒数]"""
import subprocess, sys, wave
import numpy as np
sys.path.insert(0, "nazo"); sys.path.insert(0, "kaidan")
import se, se_kaidan

SR = 24000
rng = np.random.default_rng(7)


def build(sec=90):
    n = int(SR * sec)
    t = np.arange(n) / SR
    # 低いうなり（わずかにずれた2音で、ゆっくりうねる）
    pad = (np.sin(2 * np.pi * 55 * t) + 0.7 * np.sin(2 * np.pi * 55.35 * t)
           + 0.35 * np.sin(2 * np.pi * 82.4 * t + 0.4 * np.sin(2 * np.pi * 0.05 * t))
           + 0.2 * np.sin(2 * np.pi * 110.2 * t))
    pad *= 0.6 + 0.4 * np.sin(2 * np.pi * t / 23.0) ** 2
    # 遠い風
    w = se._bp_noise(sec, 150, 700) * (0.35 + 0.3 * np.sin(2 * np.pi * t / 17.0 + 1) ** 2)
    y = pad * 0.5 + w * 0.35
    # ときどき遠くの鈴（とても小さく）
    for at in (14, 41, 67):
        if at < sec - 4:
            r = se_kaidan.rin(rng.choice([620, 700, 780]), 4.0) * 0.12
            i = int(SR * at); y[i:i + len(r)] += r[: n - i]
    # 最初と最後をつなぎ目なく（ループ用に端を短くフェード）
    f = int(SR * 2)
    y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
    return y / np.abs(y).max() * 0.6


if __name__ == "__main__":
    out = sys.argv[1]
    sec = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    y = build(sec)
    tmp = out + ".wav"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((y * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-ar", "44100", "-ac", "2", "-b:a", "160k", out], check=True)
    import os; os.remove(tmp)
