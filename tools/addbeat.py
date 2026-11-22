"""できた動画に、やさしいリズムを足す（オーナー 11/22「リズムつけて」）
使い方: python3 tools/addbeat.py in.mp4 out.mp4 [bpm=120] [gain=.22]
1小節2秒（120BPM）でカノン進行の和音とそろう。キックは1・3拍、ハイハットは8分、たまに休む"""
import sys, subprocess, wave, numpy as np
SR = 44100
src, dst = sys.argv[1], sys.argv[2]; bpm = float(sys.argv[3]) if len(sys.argv) > 3 else 120.0; gain = float(sys.argv[4]) if len(sys.argv) > 4 else .22
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]).decode())
n = int(SR * (dur + 1)); L = np.zeros(n); R = np.zeros(n); rng = np.random.default_rng(3)
def put(i, s, pan=.5):
    m = min(len(s), n - i)
    if m > 0: L[i:i + m] += s[:m] * (1 - pan) * 1.4; R[i:i + m] += s[:m] * pan * 1.4
t = np.arange(int(SR * .45)) / SR
kick = np.sin(2 * np.pi * (48 + 70 * np.exp(-t * 28)) * t) * np.exp(-t * 9) * .9
th = np.arange(int(SR * .08)) / SR
hat = rng.normal(0, 1, len(th)); hat = np.diff(np.concatenate([[0], hat])) * np.exp(-th * 70) * .16
beat = 60 / bpm; start = .6; k = 0
while start + k * beat / 2 < dur - .8:
    tt = start + k * beat / 2; i = int(tt * SR); bar = int(k // 8)
    if k % 4 == 0 and bar % 4 != 3: put(i, kick)                 # 1・3拍（4小節目は休む）
    if k % 2 == 1 or bar % 2 == 1: put(i, hat * (.8 if k % 2 else .5), .35 + .3 * (k % 3) / 2)
    k += 1
st = np.stack([L, R], 1); st = st / (np.abs(st).max() + 1e-9) * .9
wv = dst + ".beat.wav"
with wave.open(wv, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes())
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", wv, "-filter_complex",
                f"[1:a]volume={gain}[b];[0:a][b]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5[a]", "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", dst], check=True)
import os; os.remove(wv); print("リズム追加:", dst)
