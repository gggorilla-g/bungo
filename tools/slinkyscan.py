# slinkyscan.py — slinkyphys のつり合いを自動でさがす（何段下りたかを数える）
import sys, itertools, json, numpy as np, time
sys.path.insert(0, 'tools'); import slinkyphys as P
def run(V0, SH, SW, kt, pre, n=40, dur=6.0):
    S = np.array([(-.3, .03, 0.0)] + [(.03 + SW * i, .03 + SW * (i + 1), -SH * (i + 1)) for i in range(14)])
    sl = P.Slinky(n=n, h=.0016, k_tot=kt, preload=pre); M = n // 3; KA = n // 3
    c, a = P.init_arch(sl, -.01, 0.0, .03 + SW * .7, -SH, M, KA, lift=.08)
    def init(s): return c.copy(), a.copy()
    def vel(s, c_, a_):
        v = np.zeros_like(c_); w = np.zeros(s.n); nr = np.stack([-np.sin(a_), np.cos(a_)], 1); ar = np.arange(s.n); m = (ar >= M) & (ar < M + KA); v[m] = V0 * nr[m]; w[m] = -V0 / .09; return v, w
    init.vel = vel
    out = P.simulate(S, dur=dur, init=init, fps=10, sl=sl)
    ys = [o[0][:, 1].mean() for o in out]
    if not np.all(np.isfinite(ys)): return -1, ys
    return float(-min(ys) / SH), [round(float(y / -SH), 2) for y in ys]
if __name__ == "__main__":
    res = []
    grid = list(itertools.product([.6, 1.0], [.06, .08], [.12, .16], [.15, .3], [.03]))
    for g in grid:
        t = time.time(); s, ys = run(*g); res.append((s, g)); print(round(s, 2), g, ys[::5], round(time.time() - t), flush=True)
    print(sorted(res, reverse=True)[:5])
