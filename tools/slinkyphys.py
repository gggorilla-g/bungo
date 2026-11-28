# slinkyphys.py — バネ（スリンキー）が階段を下りる様子を、物理で計算する（見た目の動きを手で決めない）
#   持ち主 11/28：「このバネのショートももう少し動きに慣性的なリアリティだして、独自の路線として展開させたい」（spring2 の画面）
#   作り：輪を1つずつ「重さのある輪」（横から見ると、はばのある棒）として扱う。となりの輪とは、左右のふち（2か所）でばねでつながる
#     ・ふちどうしが巻き線の太さより近づくと、強く押し返す（輪が重なる）
#     ・ばねには最初から縮める力（プレロード）がかかっていて、積み重なった輪は一つの柱のように立つ。片側だけ開くと、そこがちょうつがいになる
#     ・輪の中心が横にずれるのを、巻き線がおさえる（せん断のばね）
#     ・重力。段の上面・角とふちが当たると押し返し、摩擦で止める
#   単位はメートル・秒・キログラム。simulate(...) は 1コマごとの (中心, 角度) を返す
import math
import numpy as np
G_ON = 1.0

class Slinky:
    def __init__(s, n=48, R=.034, mass=.2, h=.0013, k_tot=.15, preload=.03, kc=20000., ks=600., damp=.04, mu=.8):
        s.n, s.R, s.h = n, R, h; s.m = mass / n; s.I = s.m * R * R / 2
        s.k = n * k_tot / 2                                                     # ふち1か所あたりのばね
        s.d0 = h - (preload / 2) / s.k                                          # 自然長（巻き線の太さより短い＝最初から縮める力）
        s.kc, s.ks, s.damp, s.mu = kc, ks, damp, mu
        s.cdamp = 2 * math.sqrt(kc * s.m) * .4; s.sdamp = 2 * math.sqrt(s.k * s.m) * damp * 10
    def rims(s, c, a):
        e = np.stack([np.cos(a), np.sin(a)], 1); return c + s.R * e, c - s.R * e, e

def steps_poly(steps):
    """steps：[(x_left, x_right, y_top)]（左から右へ下りる）"""
    return np.array(steps, float)

def ground_force(P, V, S, kg=40000., cg=8., mu=.8):
    """点 P（M,2）が段（下にずっと続く箱）に食いこんだら、近いほうの面（上面か、右の縦の面）から押し出す。上面では摩擦も"""
    F = np.zeros_like(P)
    for x0, x1, y in S:
        inside = (P[:, 0] > x0) & (P[:, 0] < x1) & (P[:, 1] < y)
        if not inside.any(): continue
        pu = y - P[inside, 1]; pr = x1 - P[inside, 0]; up = pu <= pr
        Vi = V[inside]; Fi = np.zeros((inside.sum(), 2))
        fn = np.maximum(kg * pu - cg * Vi[:, 1], 0); ft = np.clip(-Vi[:, 0] * 30.0, -mu * fn, mu * fn)
        Fi[up, 1] = fn[up]; Fi[up, 0] = ft[up]
        fr = np.maximum(kg * pr - cg * Vi[:, 0], 0); fy = np.clip(-Vi[:, 1] * 30.0, -mu * fr, mu * fr)
        Fi[~up, 0] = fr[~up]; Fi[~up, 1] = fy[~up]
        F[inside] += Fi
    return F

def simulate(S, dur=8.0, fps=60, sl=None, init=None, dt=2e-5, push=None):
    sl = sl or Slinky(); n = sl.n
    c, a = init(sl) if init else (None, None)
    v = np.zeros_like(c); w = np.zeros(n); g = np.array([0, -9.81 * G_ON])
    out = []; nsub = int(round(1 / (fps * dt))); t = 0.0
    if push: v, w = push(sl, c, a, v, w)
    if callable(getattr(init, 'vel', None)): v, w = init.vel(sl, c, a)
    for fi in range(int(dur * fps)):
        for _ in range(nsub):
            p1, p2, e = sl.rims(c, a); nrm = np.stack([-e[:, 1], e[:, 0]], 1)
            vr1 = v + w[:, None] * sl.R * nrm; vr2 = v - w[:, None] * sl.R * nrm
            F = np.tile(g * sl.m, (n, 1)); Tq = np.zeros(n)
            for P, VR, sg in ((p1, vr1, 1), (p2, vr2, -1)):
                dvec = P[1:] - P[:-1]; d = np.linalg.norm(dvec, axis=1) + 1e-12; u = dvec / d[:, None]; dv = ((VR[1:] - VR[:-1]) * u).sum(1)
                f = sl.k * (d - sl.d0) + sl.sdamp * dv * .1                                       # 引く力（プラス）
                fv = f[:, None] * u
                ax_ = nrm[:-1]; sep = (dvec * ax_).sum(1); dvn = ((VR[1:] - VR[:-1]) * ax_).sum(1)          # 輪の軸の向きに測った、すき間（符号つき。すりぬけない）
                fc = np.where(sep < sl.h, sl.kc * (sl.h - sep) - sl.cdamp * dvn, 0.0); fc = np.maximum(fc, 0)  # 重なったら、軸の向きに押し返す
                fv = fv - fc[:, None] * ax_
                Fi = np.zeros((n, 2)); Fi[:-1] += fv; Fi[1:] -= fv
                Fg = ground_force(P, VR, S)
                Fi += Fg
                F += Fi; arm = sg * sl.R * e; Tq += arm[:, 0] * Fi[:, 1] - arm[:, 1] * Fi[:, 0]
            em = e[:-1] + e[1:]; em /= np.linalg.norm(em, axis=1)[:, None] + 1e-9; dc = c[1:] - c[:-1]; sh = (dc * em).sum(1); dvs = ((v[1:] - v[:-1]) * em).sum(1)   # せん断：となりの中心が輪の面の向きにずれない
            fs = (sl.ks * sh + 2 * math.sqrt(sl.ks * sl.m) * dvs)[:, None] * em; F[:-1] += fs; F[1:] -= fs
            v += F / sl.m * dt; w += Tq / sl.I * dt; w *= (1 - 2e-4); v *= (1 - 1e-5)
            c += v * dt; a += w * dt; t += dt
        out.append((c.copy(), a.copy()))
    return out

def init_arch(sl, xA, yA, xB, yB, m, k, lift=.06):
    """はじめの形：段A（xA, yA）に輪 0〜m−1 が積み重なり、段B（xB, yB）に輪 n−1 から下に積み重なり、そのあいだ k 個の輪が弧をえがく"""
    n, h = sl.n, sl.h; c = np.zeros((n, 2)); a = np.zeros(n)
    for i in range(m): c[i] = (xA, yA + h / 2 + i * h); a[i] = 0.0
    nb = n - m - k
    for j in range(nb): i = n - 1 - j; c[i] = (xB, yB + h / 2 + j * h); a[i] = math.pi
    P0 = np.array((xA, yA + m * h)); P3 = np.array((xB, yB + nb * h)); P1 = P0 + (0, lift + .5 * abs(xB - xA)); P2 = P3 + (0, lift + .5 * abs(xB - xA) + (P0[1] - P3[1]))
    tt = np.linspace(0, 1, 400)[:, None]; B = (1 - tt) ** 3 * P0 + 3 * (1 - tt) ** 2 * tt * P1 + 3 * (1 - tt) * tt * tt * P2 + tt ** 3 * P3
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(B, axis=0), axis=1))]); s = np.linspace(0, L[-1], k + 2)[1:-1]
    for q, sv in enumerate(s):
        i = m + q; p = np.array([np.interp(sv, L, B[:, 0]), np.interp(sv, L, B[:, 1])]); j = min(398, int(np.searchsorted(L, sv))); tg = B[j + 1] - B[j]; tg /= np.linalg.norm(tg)
        c[i] = p; ax = math.atan2(tg[1], tg[0]); a[i] = ax - math.pi / 2                              # 輪の面は、弧の向きに直角
    return c, a
