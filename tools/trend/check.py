#!/usr/bin/env python3
"""check.py — できた動画を数値で確かめる（docs/trend-pipeline.md の「5 確かめる」）

  python3 tools/trend/check.py output/<id>.mp4 [--long]

見るもの（NG が1つでもあれば終了コード 1）
  長さ        ショートは 12〜59 秒（--long は 60 秒〜15 分）
  音量        -18〜-11 LUFS
  高い音      5kHz より上が全体の 3% 以下、8kHz より上が 0.5% 以下（キンキンさせない）
  余韻        音が長く尾を引いていないか：鳴りはじめから 0.6 秒後に -25dB 以下まで下がる出来事が半分以上（乾いた音）
  無音        2.5 秒をこえる無音がない（最後の 3 秒は除く）
  出だし      最初の 1 秒で絵が動いている
  止まり      絵が 1.5 秒をこえて止まって見えない（最後の 3 秒は除く）
  白とび      真ん中の絵で、ほぼ白（245 以上）の画素が 6% 以下
数値で分からないこと（文字のはみ出し・重なり、おもしろいか）は、出だし・真ん中・最後の絵を目で見る。
"""
import subprocess, sys, re
import numpy as np

def run(cmd): return subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True)

def main():
    mp4 = sys.argv[1]; long = "--long" in sys.argv; echo = "--echo" in sys.argv; light = "--light" in sys.argv; bad = []; rep = []   # --echo：エコーを足してよい型（合体の型。持ち主 11/27）は、余韻の検査をしない
    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]).stdout.decode().strip())
    ok = (60 <= dur <= 900) if long else (12 <= dur <= 59); rep.append(("長さ", f"{dur:.1f}秒", ok))
    e = run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-vn", "-af", "ebur128", "-f", "null", "-"]).stderr.decode()
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", e); lufs = float(m[-1]) if m else -99; rep.append(("音量", f"{lufs:.1f} LUFS", -18 <= lufs <= -11))
    raw = run(["ffmpeg", "-v", "error", "-i", mp4, "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"]).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768; sr = 48000
    if len(x) > sr:
        f = np.fft.rfftfreq(len(x), 1 / sr); P = np.abs(np.fft.rfft(x)) ** 2; tot = P.sum() + 1e-12; h5, h8 = 100 * P[f > 5000].sum() / tot, 100 * P[f > 8000].sum() / tot
        rep.append(("高い音", f"5kHzより上 {h5:.2f}%、8kHzより上 {h8:.3f}%", h5 <= 3 and h8 <= .5))
        w = int(sr * .02); env = np.sqrt(np.convolve(x ** 2, np.ones(w) / w, "same")) + 1e-9; db = 20 * np.log10(env)
        on = np.where((db[w:] > db[:-w] + 12) & (db[w:] > -32))[0] + w; on = on[np.insert(np.diff(on) > int(sr * .08), 0, True)] if len(on) else on   # 鳴りはじめ
        if len(on) >= 4:
            iso = [i for k, i in enumerate(on) if (k + 1 == len(on) or on[k + 1] - i > int(sr * .62)) and i + int(sr * .6) < len(db)]   # あとに別の音が来ない鳴りはじめ
            if len(iso) >= 3 and not echo:
                drop = np.array([db[i:i + int(sr * .05)].max() - db[i + int(sr * .6)] for i in iso]); rate = float((drop >= 25).mean())
                rep.append(("余韻", f"0.6秒後に25dB以上下がる出来事 {100 * rate:.0f}%（{len(iso)}個で確認）", rate >= .5))
        quiet = db < -50; body = quiet[: max(0, len(quiet) - 3 * sr)]; run_ = 0; longest = 0
        for q in body[::480]:
            run_ = run_ + 1 if q else 0; longest = max(longest, run_)
        rep.append(("無音", f"いちばん長い無音 {longest * .01:.1f}秒", longest * .01 <= 2.5))
    else: rep.append(("音", "音が入っていない", False))
    raw = run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", "fps=4,scale=135:240,format=gray", "-f", "rawvideo", "-"]).stdout
    fr = np.frombuffer(raw, np.uint8).astype(np.float32).reshape(-1, 240, 135)
    if len(fr) > 8:
        d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2)); rep.append(("出だし", f"最初の1秒の動き {d[:4].max():.2f}", d[:4].max() > .08))
        still = d[: max(1, len(d) - 12)] < .03; run_ = 0; longest = 0
        for q in still:
            run_ = run_ + 1 if q else 0; longest = max(longest, run_)
        rep.append(("止まり", f"いちばん長く止まって見える時間 {longest * .25:.1f}秒", longest * .25 <= 1.5))
    raw = run(["ffmpeg", "-v", "error", "-ss", f"{dur * .5:.2f}", "-i", mp4, "-frames:v", "1", "-vf", "scale=270:480,format=gray", "-f", "rawvideo", "-"]).stdout
    if raw: g = np.frombuffer(raw, np.uint8); wh = 100 * float((g >= 245).mean()); rep.append(("白とび", f"ほぼ白の画素 {wh:.1f}%" + ("（白い背景の型なので見ない）" if light else ""), wh <= 6 or light))   # --light：白い背景の型（持ち主 11/27 の参考動画の雰囲気）
    for name, val, ok in rep:
        print(("OK  " if ok else "NG  ") + f"{name}: {val}")
        if not ok: bad.append(name)
    print("結果: " + ("数値の検査はすべて通過（このあと絵を目で見る）" if not bad else "NG あり → " + "、".join(bad))); return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
