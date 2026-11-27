# loopkit.py — 「ふえていく → 埋まる → 早回しで巻きもどる → 頭につながる」型の動画で使う道具（持ち主 2026-11-28）
#   持ち主：「さいごは…かなり何度も高密度になって最終的には虹ベタになりかなり早いキュルキュルキュルキュルみたいな巻き戻しが入って頭からループするという機構。うまい」
#           「これも同じループ構造。…その後まきもどしがありループする」
#   作り方の決まり
#     ・絵は「中の時刻 ts」だけで決まるように書く（frame_at(ts)）。進む時も、巻きもどす時も、同じ関数を使う
#     ・動画の最後のコマは ts がほぼ 0（＝最初のコマの直前）。出だし・終わりを暗くしない（ループのつなぎ目が見えなくなる）
#     ・巻きもどしの音は、それまでの音を逆向きに早回ししたもの（足した音ではない）。回る速さを少しゆらして「キュルキュル」にする
import math, wave
import numpy as np

def sstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a))); return t * t * (3 - 2 * t)
def sim_time(t, tfwd, hold, trew):
    """動画の時刻 t → (中の時刻 ts, 巻きもどしの進み rew)。進む（tfwd まで）→ 止まる（hold）→ 早回しでもどる（trew）。rew は進む間と止まっている間は 0"""
    if t <= tfwd: return t, 0.0
    if t <= tfwd + hold: return tfwd, 0.0
    x = min(1.0, (t - tfwd - hold) / trew); return max(0.0, tfwd * (1 - sstep(0, 1, x) ** .9)), max(1e-3, x)
def rewind_audio(mono, sr, trew, pitch=2.6, wob_hz=11.0, wob=.25, lp=5200.0):
    """mono（進む間の音）を逆向きにして trew 秒に縮める。高さは pitch 倍まで（そのまま縮めると高すぎて聞こえない）。回る速さが wob_hz でゆれる"""
    n_out = int(sr * trew); x = np.asarray(mono, np.float32)[::-1]; n_mid = int(n_out * pitch); grain = int(sr * .03); hop = grain // 2
    ratio = (len(x) - grain) / n_mid; mid = np.zeros(n_mid + grain, np.float32); win = np.hanning(grain).astype(np.float32)
    for k in range(0, n_mid - grain, hop): s0 = int(k * ratio); mid[k:k + grain] += x[s0:s0 + grain] * win            # 高さを変えずに縮める（短い切れはしを重ねる）
    tt = np.arange(n_out) / sr; pos = (n_mid / trew) * (tt + (wob / (2 * np.pi * wob_hz)) * np.sin(2 * np.pi * wob_hz * tt))
    y = np.interp(np.clip(pos, 0, n_mid - 1), np.arange(n_mid + grain), mid).astype(np.float32)                              # ここで pitch 倍に早回し
    if lp:
        a = math.exp(-2 * math.pi * lp / sr)
        for _ in range(2):
            from scipy.signal import lfilter
            y = lfilter([1 - a], [1, -a], y).astype(np.float32)
    return y * np.minimum(1, tt / .02) * np.minimum(1, (trew - tt) / .12)
def add_rewind(fwd_wav, out_wav, tfwd, hold, trew, gain=.62, pitch=2.6):
    """fwd_wav（長さ tfwd+hold のステレオ）のうしろに、巻きもどしの音を足して out_wav に書く。大きさは、最後の6秒の大きさの gain 倍"""
    with wave.open(fwd_wav) as w: sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
    y = rewind_audio(x[: int(sr * tfwd)].mean(1), sr, trew, pitch); dense = math.sqrt(float((x[int(sr * max(0, tfwd - 6)):int(sr * tfwd)] ** 2).mean())) + 1e-9
    y *= gain * dense / (math.sqrt(float((y ** 2).mean())) + 1e-9); N = int(sr * (tfwd + hold + trew)); out = np.zeros((N, 2), np.float32); out[: min(N, len(x))] = x[:N]
    a0 = int(sr * (tfwd + hold)); k = min(len(y), N - a0); out[a0:a0 + k] += y[:k, None]; out = np.tanh(out * 1.2) / 1.2
    with wave.open(out_wav, "wb") as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes((out * 32767).astype(np.int16).tobytes())

def heartbeat(beats, n, sr, gain=.10):
    """鼓動のような低い音（持ち主 2026-11-28「全体の隠し味で鼓動音的なのを入れてみたい。グルーブではなくて調和」）。
       beats＝[(時刻, 和音の根音の MIDI 番号)]。1拍は「ドッ・クン」の2つ：1つめは根音、0.27秒あとの2つめは5度上で小さく（和音の中の音だけで鳴らすので、にごらない）。
       隠し味なので小さく（gain）。拍を強く刻まない（アクセントや裏打ちをつけない）。長さ n のモノラルを返す（Audio.write の under に足す）"""
    out = np.zeros(n, np.float32)
    def thump(f, dur, amp):
        tt = np.arange(int(sr * dur)) / sr; ph = 2 * np.pi * np.cumsum(f * (1 + .8 * np.exp(-tt / .018))) / sr                  # 出だしだけ少し高い（やわらかい打音）
        return (amp * (np.sin(ph) + .35 * np.sin(2 * ph) + .12 * np.sin(3 * ph)) * np.exp(-tt / (dur * .26)) * np.minimum(1, tt / .008)).astype(np.float32)   # 2倍・3倍の音を少し足す（小さいスピーカーでも気配が残る）
    for t, m in beats:
        f = 440.0 * 2 ** ((m - 69) / 12)
        for dt, ff, dur, amp in ((0.0, f, .36, 1.0), (.27, f * 1.5, .27, .6)):
            a = int((t + dt) * sr); x = thump(ff, dur, amp)
            if 0 <= a < n: k = min(len(x), n - a); out[a:a + k] += x[:k]
    return out * gain
