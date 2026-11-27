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

# ---------- オルゴールに近い澄んだ音（11/27 オーナーが送った参考録画の音を測って寄せた） ----------
#   参考の音：基音 0.9〜2kHz のほぼ純音（2倍音が少し）。0.5〜1 秒ほど鳴って消える。D のペンタトニック（D E F# A B）で、出来事ごとに上がっていく。
#   下に、D と A の温かい持続音（ゆっくり和音が変わる）。上の倍音のザラつきや、はじく雑音はない
_b = {}
def bell(m, vel=1.0):
    key = (int(m), round(vel, 2))
    if key in _b: return _b[key]
    f = mtof(m); dec = float(np.clip(.95 * (1000 / f) ** .35, .45, 1.6)); L = dec * 3.6; tt = np.arange(int(SR * L)) / SR
    x = np.sin(2 * np.pi * f * tt) * np.exp(-tt / dec) + .16 * np.sin(4 * np.pi * f * tt + .3) * np.exp(-tt / (dec * .45)) + .04 * np.sin(6 * np.pi * f * tt + .9) * np.exp(-tt / (dec * .25))
    x *= (1 + .0025 * np.sin(2 * np.pi * 5.2 * tt))                        # ほんの少しゆらぐ
    x *= .5 - .5 * np.cos(np.pi * np.minimum(1, tt / .006))                 # 立ち上がり 6ms（硬くしない）
    x *= np.minimum(1, (L - tt) / .05); x = _lp(x.astype(np.float32), 7000)
    x *= (f / 1000) ** -.35 * (.7 + .3 * vel); _b[key] = x.astype(np.float32); return _b[key]

def pad(chords, ch_len, total, gain=.06, seed=3):
    """温かい持続音：chords（MIDI の組の列）を ch_len 秒ずつ。少しずらした2本の正弦でうなり、ゆっくり入れかわる（モノラル）"""
    N = int(SR * total); out = np.zeros(N, np.float32); fade = min(1.6, ch_len * .4); n1 = int(SR * (ch_len + fade))
    tt = np.arange(n1) / SR; env = np.minimum(1, tt / fade) * np.minimum(1, (n1 / SR - tt) / fade)
    for c in range(int(total / ch_len) + 1):
        ms = chords[c % len(chords)]; s = np.zeros(n1)
        for q, m in enumerate(ms):
            f = mtof(m); s += (np.sin(2 * np.pi * f * tt + q) + .7 * np.sin(2 * np.pi * f * 1.0035 * tt + 2 * q)) * (1.0 if f < 300 else .55) / (1 + .3 * q)
        i = int(SR * (c * ch_len - fade / 2)); a, b = max(0, i), min(N, i + n1)
        if b > a: out[a:b] += (s * env)[a - i:b - i].astype(np.float32)
    return _lp(out, 1400) * gain

# ---------- 乾いた「カロッ」（持ち主 2026-11-27「音はもっと乾いたカロっ(飴玉を口で転がすような)音がいい。音階はカノン」） ----------
#   飴玉が歯に当たる音を目安にした、短くて丸い打音。
#     ・当たった瞬間だけ少し高く、すぐ音の高さに落ちる（「カ」→「ロ」）
#     ・鳴っているのは 0.1〜0.25 秒。余韻を残さない（乾いた音）
#     ・口の中の短い響き（1〜1.7kHz あたり、0.01 秒）と、やわらかい当たりの音（1.2〜4.5kHz、0.002 秒）
#     ・roll=True で「カロッ」：0.045 秒おくれて、同じ高さの丸い2打めが小さく入る（1打めより鈍い音色）
#     ・5kHz から上はなだらかに落とす（キンキンさせない）
#   使うとき：残響はほとんどかけない（room の send は 0.03 まで）。音の高さはカノン進行の和音の音から選ぶ
_k = {}
def karo(m, vel=1.0, roll=True, hard=.5):
    """hard：当たりの硬さ（0＝やわらかい「コロ」、1＝硬い「カロ」）。音の高さは A4〜G6（MIDI 69〜91）あたりが飴玉らしい"""
    key = (int(m), round(vel, 2), bool(roll), round(hard, 2))
    if key in _k: return _k[key]
    f = mtof(m); tau = float(np.clip(.070 * (800 / f) ** .35, .035, .11)); L = .42; n = int(SR * L); tt = np.arange(n) / SR
    rng = np.random.default_rng(int(m) * 7 + 1)
    def hit(amp, tau_, bright, formant, fa, glide_amt):
        glide = 1 + glide_amt * np.exp(-tt / .010); ph = 2 * np.pi * f * np.cumsum(glide) / SR
        x = np.sin(ph) * np.exp(-tt / tau_) + .30 * np.sin(2 * ph + .5) * np.exp(-tt / (tau_ * .45)) + .12 * np.sin(3.01 * ph + 1.0) * np.exp(-tt / (tau_ * .25))
        x += fa * np.sin(2 * np.pi * formant * tt + .3) * np.exp(-tt / .011)                        # 口の中の短い響き
        nz = rng.normal(0, 1, n).astype(np.float32); bp = _lp(nz, 5000) - _lp(nz, 1500)             # 当たりの音（帯域をしぼった雑音）
        x += bp * np.exp(-tt / .0022) * bright
        return x * amp
    x = hit(1.0, tau, (.5 + 3.0 * hard) * (.6 + .4 * vel), 1650 + 500 * hard, .20 + .25 * hard, .035 + .03 * hard)
    if roll:
        d = int(SR * .045); y = hit(.40, tau * .8, .15 + .5 * hard, 950, .22, .02); x[d:] += y[:n - d]
    x *= np.minimum(1, tt / .0008); x *= np.minimum(1, (L - tt) / .03)
    x = _lp(x.astype(np.float32), 5000 + 1600 * hard); x *= (f / 700) ** -.30 * (.72 + .28 * vel)
    _k[key] = x.astype(np.float32); return _k[key]

# ---------- 物が当たる音（持ち主 11/27「電子音ぽすぎるんだよな。もっと物理的な音がいい」「二度うちは違う感じがする。恣意的な感じがする」） ----------
#   これまでの karo は、正弦波・雑音・「ポッ」を別々に作って足していた（音程が上から落ちる仕掛け、あとから足す雑音、二度打ち）。それが電子音に聞こえる。
#   ここでは、物が当たる順番どおりに作る：
#     1) 当たる力：硬い玉が板に触れている 0.2〜0.4 ミリ秒だけの山（ヘルツの接触。強い当たりほど短い）。面のざらつきで少し揺れる
#     2) その力が、物の「固有の響き」を全部いっせいに鳴らす（力と響きのたたみこみ）。足すのではなく、1つの力から全部が出る
#        ・板の響き（音程になる）：曲げの1番目が音の高さ。2番目から上は整数倍からずれる。高い響きほど早く消える（木は高い音を吸う）。たたく場所で混ざり方が変わる
#        ・台の響き（音程に関係なく、いつも同じ）：枠や机が鳴る短い「コッ」。同じ物をたたいている感じは、ここから来る
#        ・空洞（板の下の筒、口の中）：基音のまわりだけがふくらむ、丸い響き
#     3) 1打ごとに、たたく場所・当たっている時間・台の鳴り方が少しずつ違う（同じ音がコピーのように並ばない）
#   音程が動く仕掛け、あとから足す雑音、二度打ちは入れない。鳴るのは、絵の中で当たった瞬間だけ
_BL = (4.7300, 7.8532, 10.9956, 14.1372, 17.2788)
def _phi(k, x):
    """両端が自由な棒の、k 番目の曲げの形（x＝0〜1。端で1）"""
    b = _BL[k]; s = (math.cosh(b) - math.cos(b)) / (math.sinh(b) - math.sin(b))
    return (math.cosh(b * x) + math.cos(b * x) - s * (math.sinh(b * x) + math.sin(b * x))) / 2
# 台の響き（Hz, Q, 重み）。Q が低い＝すぐ消える。音程に関係なく同じ
_BODY = [(236, 7, .55), (412, 9, .50), (655, 10, .66), (930, 12, .62), (1290, 13, .80), (1730, 14, .78), (2240, 15, .80), (2950, 16, .72), (3700, 16, .56), (4500, 17, .36), (5400, 18, .18)]
MATERIALS = {
    # r：板の響きの倍率 ／ w：重み（マイクに届くのは面の加速度なので、高い響きほど出だしは強い） ／ q：基音の Q（大きいほど長く鳴る） ／ qs：高い響きほど Q が下がる度合い
    # bar：棒の形でたたく場所を効かせるか ／ tor：ねじれの響き（倍率, 重み） ／ cav：空洞（強さ, Q） ／ body：台の鳴りの強さ ／ tc：当たっている時間（ミリ秒） ／ taumax：基音の余韻の上限（秒）
    "wood":   dict(r=(1, 3.01, 6.15, 9.9, 14.2), w=(1, 1.25, 1.35, 1.0, .6), q=140, qs=.35, bar=True, tor=(1.87, .12), cav=(.35, 14), body=.75, tc=.17, taumax=.085),   # 木の板（木琴に近い）
    "hollow": dict(r=(1, 1.52, 2.63, 3.94, 5.3, 7.1), w=(1, .50, .55, .50, .40, .30), q=44, qs=.15, bar=False, tor=None, cav=(.80, 9), body=1.0, tc=.15, taumax=.05),   # 空洞のある木（木魚・口の中に近い）
    # ガラス（持ち主 11/28「ガラスっぽい音でいいかも。音階カノンで瞑想エコー」）：ガラスの器の響き（倍率はワイングラス・クリスタルボウルの曲げの響きに近い 1 : 2.32 : 4.25 : 6.63）。
    #   硬いので当たっている時間はごく短い。響きは長い（〜1秒）が、高い響きほど早く消える（キンキンさせない）。台の鳴りはほとんど無い
    "glass":  dict(r=(1, 2.32, 4.25, 6.63), w=(1, .42, .16, .06), q=2600, qs=.85, bar=False, tor=None, cav=(0.0, 9), body=.10, tc=.09, taumax=.9, L=2.6),
    # ビードロ（持ち主 11/28「ビードロ系の音で瞑想エコー」）：うすいガラスの小びん。響きは基音がほとんどで、首の空洞がふくらませる丸い音。ガラスより短い
    "stone":  dict(r=(1, 2.76, 5.40, 8.93), w=(1, .50, .26, .10), q=520, qs=.55, bar=True, tor=(3.9, .05), cav=(.55, 18), body=.22, tc=.055, taumax=.42, L=1.7),   # 少し空洞のある石・宝石（持ち主 11/28「少し空洞のある石や宝石をたたいてかつ音階がある音」）：硬い当たり（短い接触）、基音がはっきり、木より長く・ガラスより短く響く
    "vidro":  dict(r=(1, 2.73, 5.2), w=(1, .28, .07), q=900, qs=.8, bar=False, tor=None, cav=(.65, 30), body=.06, tc=.12, taumax=.5, L=1.8),
    "bamboo": dict(r=(1, 2.76, 5.40, 8.93, 13.3), w=(1, 1.4, 1.5, 1.1, .7), q=100, qs=.30, bar=True, tor=(1.63, .16), cav=(.28, 9), body=.85, tc=.13, taumax=.07),      # 竹の板
}
_kn = {}
def knock(m, vel=1.0, mat="wood", var=0):
    """硬い玉が板に当たる音。m＝音の高さ（MIDI）、vel＝当たりの強さ、mat＝MATERIALS の名前、var＝1打ごとの違い（0,1,2…で少しずつ変わる）"""
    key = (int(m), round(vel, 2), mat, int(var))
    if key in _kn: return _kn[key]
    from scipy.signal import fftconvolve, lfilter
    P = MATERIALS[mat]; f = mtof(m); rng = np.random.default_rng(int(m) * 131 + int(var) * 977 + len(mat)); L = P.get("L", .55); n = int(SR * L); tt = np.arange(n) / SR
    # 1) 当たる力
    tc = P["tc"] * 1e-3 * max(.3, vel) ** -.2 * (1 + .07 * rng.normal()); k = max(5, int(round(SR * tc)))
    pulse = np.sin(np.pi * (np.arange(k) + .5) / k) ** 1.5 * (1 + .10 * rng.normal(0, 1, k)); pulse = (pulse / np.abs(pulse).sum()).astype(np.float64)
    # 2) 板の響き
    xs = rng.uniform(.33, .44); q1 = P["q"]; tau1 = q1 / (math.pi * f)
    if tau1 > P["taumax"]: q1 *= P["taumax"] / tau1
    ir = np.zeros(n)
    for i, (rk, wk) in enumerate(zip(P["r"], P["w"])):
        fk = f * rk * (1 + (.004 * rng.normal() if i else 0))
        if fk > 7000: continue
        a = wk * (abs(_phi(i, xs)) / .55 if P["bar"] and i < len(_BL) else math.exp(.22 * rng.normal()))
        ir += a * np.exp(-tt * math.pi * fk / (q1 * rk ** -P["qs"])) * np.sin(2 * math.pi * fk * tt)
    if P["tor"]:
        fk = f * P["tor"][0] * (1 + .006 * rng.normal()); ir += P["tor"][1] * rng.uniform(.2, 1.4) * np.exp(-tt * math.pi * fk / (q1 * .5)) * np.sin(2 * math.pi * fk * tt)
    #    台の響き
    nb = int(SR * .06); tb = tt[:nb]; body = np.zeros(nb)
    for (fb, qb, wb) in _BODY: body += wb * math.exp(.20 * rng.normal()) * np.exp(-tb * math.pi * fb / qb) * np.sin(2 * math.pi * fb * tb)
    ir[:nb] += P["body"] * body
    x = fftconvolve(ir, pulse)[:n] * 12
    #    空洞：基音のまわりだけを、短くふくらませる
    g, qc = P["cav"]; fc = f * (1 + .004 * rng.normal()); r = math.exp(-math.pi * fc / (qc * SR)); th = 2 * math.pi * fc / SR
    x = x + g * lfilter([(1 - r * r) / 2, 0, -(1 - r * r) / 2], [1, -2 * r * math.cos(th), r * r], x)
    x *= np.minimum(1, (L - tt) / .03); x = _lp(x.astype(np.float32), 7000)                   # 空気とマイクの丸み
    x *= (f / 700) ** -.28 * (.70 + .30 * vel) / (np.abs(x).max() + 1e-9) * .9
    _kn[key] = x.astype(np.float32); return _kn[key]

CANON = [(50, 54, 57), (45, 49, 52), (47, 50, 54), (42, 45, 49), (43, 47, 50), (38, 42, 45), (43, 47, 50), (45, 49, 52)]   # D A Bm F#m G D G A（根音・3度・5度の MIDI 番号）
def canon_tones(i, lo=62, hi=88):
    """カノン進行の i 番めの和音に入っている音を、lo〜hi の範囲で低い順に返す"""
    pcs = {m % 12 for m in CANON[i % 8]}; return [m for m in range(lo, hi + 1) if m % 12 in pcs]
