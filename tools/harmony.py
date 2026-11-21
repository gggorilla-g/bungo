"""和音（オーナー 11/22「ぶつかった時に和音」「共通で和音大事に。カノン進行も可」）
カノン進行 D-A-Bm-F#m-G-D-G-A を、1小節 BAR 秒で回す。当たった音は今の和音の音に寄せ、和音の他の2音を小さく重ねる"""
import os
BAR = float(os.environ.get("SIM_BAR", "2.0"))
# ハ長調のカノン進行 C-G-Am-Em-F-C-F-G（オーナー 11/22「とにかくドレミファソラシドと和音」）
CANON = [(0, (0, 4, 7)), (7, (0, 4, 7)), (9, (0, 3, 7)), (4, (0, 3, 7)), (5, (0, 4, 7)), (0, (0, 4, 7)), (5, (0, 4, 7)), (7, (0, 4, 7))]
MAJOR = (0, 2, 4, 5, 7, 9, 11)   # ドレミファソラシ
ON = os.environ.get("SIM_CHORDS", "1") == "1"


def pcs(t):
    r, q = CANON[int(max(0, t) / BAR) % len(CANON)]
    return [(r + x) % 12 for x in q]


def snap(m, t):
    """m に一番近いドレミファソラシの音（同じ近さなら今の和音の音を優先）"""
    P = pcs(t)
    return min(range(m - 6, m + 7), key=lambda x: (0 if x % 12 in MAJOR else 99) + abs(x - m) * .1 - (.05 if x % 12 in P else 0))


def others(m, t):
    """m（和音の音）の下に、和音の残り2音（m より下の近い音）"""
    P = pcs(t); out = []
    for k in range(1, 12):
        x = m - k
        if x % 12 in P and x % 12 != m % 12 and m - x >= 3: out.append(x)
        if len(out) == 2: break
    return out
