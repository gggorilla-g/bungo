"""和音（オーナー 11/22「ぶつかった時に和音」「共通で和音大事に。カノン進行も可」）
カノン進行 D-A-Bm-F#m-G-D-G-A を、1小節 BAR 秒で回す。当たった音は今の和音の音に寄せ、和音の他の2音を小さく重ねる"""
import os
BAR = float(os.environ.get("SIM_BAR", "2.0"))
CANON = [(2, (0, 4, 7)), (9, (0, 4, 7)), (11, (0, 3, 7)), (6, (0, 3, 7)), (7, (0, 4, 7)), (2, (0, 4, 7)), (7, (0, 4, 7)), (9, (0, 4, 7))]
ON = os.environ.get("SIM_CHORDS", "1") == "1"


def pcs(t):
    r, q = CANON[int(max(0, t) / BAR) % len(CANON)]
    return [(r + x) % 12 for x in q]


def snap(m, t):
    """m に一番近い、今の和音の音"""
    P = pcs(t); best = min(range(m - 6, m + 7), key=lambda x: (0 if x % 12 in P else 99) + abs(x - m) * .01)
    return best


def others(m, t):
    """m（和音の音）の下に、和音の残り2音（m より下の近い音）"""
    P = pcs(t); out = []
    for k in range(1, 12):
        x = m - k
        if x % 12 in P and x % 12 != m % 12: out.append(x)
        if len(out) == 2: break
    return out
