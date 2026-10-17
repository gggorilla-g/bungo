# kaidan/se_kaidan.py — （いまは未使用：効果音はさりげない既定の音でよいとの方針）怪談の世界観に合う効果音（すべて自前で合成。素材の権利問題なし）
#   install() を呼ぶと、nazo/se.py の音の一覧に怪談用の音を足し、
#   レンダラーが鳴らす既定の音（whoosh・pop など）を怪談用の音へ置き換える。
#   keyword_se(文) で、本文の言葉（戸を叩く・足音・雨…）に合わせた音を返す。
import re
import numpy as np
import se

SR = se.SR
_r = np.random.default_rng(23)


def _t(d):
    return np.arange(int(SR * d)) / SR


def _noise(d, lo, hi):
    return se._bp_noise(d, lo, hi)


def rin(f=1180, d=3.2):
    """仏具の鈴（りん）：倍音がずれた金属音が長く残る"""
    t = _t(d)
    y = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * k)
            for m, a, k in ((1, 1.0, 1.2), (2.76, 0.45, 2.2), (5.4, 0.25, 4.0), (8.9, 0.12, 6.0)))
    beat = 1 + 0.25 * np.sin(2 * np.pi * 3.2 * t)       # うなり
    return y * beat * np.minimum(1, t / 0.003)


def hyoshigi():
    """拍子木：硬い木を2回打つ"""
    def clap(d=0.12):
        t = _t(d)
        return (np.sin(2 * np.pi * 1850 * t) * 0.6 + _noise(d, 1200, 5200) * 0.5) * np.exp(-t * 55)
    a = clap()
    y = np.zeros(int(SR * 0.6))
    y[:len(a)] += a
    i = int(SR * 0.32); y[i:i + len(a)] += a * 0.9
    return y


def wind(d=2.6, lo=180, hi=1200):
    t = _t(d)
    x = _noise(d, lo, hi)
    lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.7 * t + 1.0)
    env = np.sin(np.pi * t / d) ** 1.5
    return x * lfo * env


def knock(n=3, gap=0.42):
    """戸を叩く音：低めの木の音を間をおいて"""
    def one(d=0.18):
        t = _t(d)
        return (np.sin(2 * np.pi * 180 * t) + 0.5 * np.sin(2 * np.pi * 410 * t) + 0.4 * _noise(d, 200, 1800)) * np.exp(-t * 30)
    a = one()
    y = np.zeros(int(SR * (gap * n + 0.3)))
    for k in range(n):
        i = int(SR * gap * k); y[i:i + len(a)] += a * (1 - 0.1 * k)
    return y


def heart(beats=2, gap=0.85):
    def lub(f=60, d=0.22):
        t = _t(d)
        return np.sin(2 * np.pi * f * t * (1 + 0.4 * np.exp(-t * 25))) * np.exp(-t * 14)
    y = np.zeros(int(SR * (gap * beats + 0.4)))
    a, b = lub(), lub(52) * 0.7
    for k in range(beats):
        i = int(SR * gap * k); y[i:i + len(a)] += a
        j = i + int(SR * 0.24); y[j:j + len(b)] += b
    return y


def creak(d=1.1):
    """戸がきしむ音：音程が揺れる、ざらついた低い音"""
    t = _t(d)
    f = 140 + 60 * np.sin(2 * np.pi * 1.3 * t) + 40 * t
    ph = 2 * np.pi * np.cumsum(f) / SR
    saw = 2 * ((ph / (2 * np.pi)) % 1) - 1
    grain = (np.sin(2 * np.pi * 23 * t) > 0.2).astype(float) * 0.6 + 0.4
    x = np.convolve(saw * grain, np.ones(6) / 6, mode="same")
    return x * np.sin(np.pi * t / d) ** 0.8


def drip():
    d = 0.35
    t = _t(d)
    f = 1500 * np.exp(-t * 9) + 600
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 18)


def steps(n=4, gap=0.55):
    """板の間を歩く足音（ひた、ひた…）"""
    def one(d=0.16):
        t = _t(d)
        return (_noise(d, 120, 900) * 0.8 + np.sin(2 * np.pi * 95 * t) * 0.5) * np.exp(-t * 32)
    a = one()
    y = np.zeros(int(SR * (gap * n + 0.3)))
    for k in range(n):
        i = int(SR * gap * k); y[i:i + len(a)] += a * (0.8 + 0.2 * (k % 2))
    return y


def rain(d=3.0):
    t = _t(d)
    x = _noise(d, 1500, 7000) * 0.5
    for _ in range(60):
        i = _r.integers(0, len(t) - 400)
        x[i:i + 400] += np.exp(-np.arange(400) / 60) * _r.uniform(0.3, 0.9)
    return x * np.minimum(1, t / 0.4) * np.minimum(1, (d - t) / 0.6)


def drone(d=3.5):
    """不穏に膨らむ低音（つかみ・山場に）"""
    t = _t(d)
    y = np.sin(2 * np.pi * 55 * t) + 0.6 * np.sin(2 * np.pi * 55.7 * t) + 0.3 * np.sin(2 * np.pi * 82.5 * t)
    return y * (t / d) ** 2 * np.minimum(1, (d - t) / 0.3)


NEW = {
    "k_rin":      (lambda: rin(), 0.16),
    "k_rin_lo":   (lambda: rin(780, 3.6), 0.15),
    "k_hyoshigi": (lambda: hyoshigi(), 0.18),
    "k_wind":     (lambda: wind(), 0.14),
    "k_wind_s":   (lambda: wind(1.2, 250, 1600), 0.10),
    "k_knock":    (lambda: knock(), 0.30),
    "k_heart":    (lambda: heart(), 0.32),
    "k_creak":    (lambda: creak(), 0.10),
    "k_drip":     (lambda: drip(), 0.12),
    "k_steps":    (lambda: steps(), 0.22),
    "k_rain":     (lambda: rain(), 0.12),
    "k_drone":    (lambda: drone(), 0.22),
}

# レンダラーが鳴らす既定の音 → 怪談用の音
ALIAS = {
    "whoosh_l": "k_wind", "whoosh_s": "k_wind_s", "thud": "k_heart", "shimmer": "k_rin",
    "pop_lo": "k_drip", "pop_mid": "k_rin_lo", "pop_hi": "k_drip", "chime_a": "k_rin",
    "chime_b": "k_rin_lo", "chime_c": "k_rin", "tick": "k_drip", "tick_lo": "k_hyoshigi",
    "paper": "k_wind_s", "ding": "k_rin",
}
ROT = {
    "card":  [("k_hyoshigi", "k_wind_s"), ("k_rin", "k_wind_s"), ("k_hyoshigi", "k_drip")],
    "words": ["k_drip", "k_rin_lo", "k_drip"],
    "cut":   ["k_wind_s", "k_drip", "k_wind_s"],
}

# 本文の言葉に合わせて鳴らす音（1文に1つまで）
KEYWORDS = [
    (r"戸を叩|戸をたた|とん、とん|トン、トン|コツ、コツ", "k_knock"),
    (r"足音|ひた、ひた|ひたひた|ぎしり、ぎしり", "k_steps"),
    (r"きしむ|軋|襖が開|障子が開|戸が開|戸があ", "k_creak"),
    (r"雨が|雨の|夕立|雨音", "k_rain"),
    (r"風が|風の音|木枯らし", "k_wind"),
    (r"鐘|鈴の音|お経", "k_rin_lo"),
    (r"しずく|滴|水が垂|ぽたり", "k_drip"),
    (r"心臓|胸が高鳴|どきり|ぞっと", "k_heart"),
]


def keyword_se(sentence):
    for pat, name in KEYWORDS:
        if re.search(pat, sentence):
            return [(name, 0.15, 1.0)]
    return []


def install():
    for k, v in NEW.items():
        se.LIB[k] = v
    se.ALIAS.update(ALIAS)
    se.ROT.clear(); se.ROT.update(ROT)
    se._count.clear()


# ---- 怪談の効果音（採用版）：俗っぽくない、不協和のさりげない短い音 ----
# 演出的な音（戸を叩く・足音など）は使わない。どれもやわらかく立ち上がり、小さく、短い
def dyad(f1, f2, d=1.6, attack=0.08, k=2.2, glassy=False):
    t = _t(d)
    env = np.minimum(1, t / attack) * np.exp(-t * k)
    y = np.sin(2 * np.pi * f1 * t) + np.sin(2 * np.pi * f2 * t)
    if glassy:   # ガラスのような倍音を少しだけ
        y += 0.3 * np.sin(2 * np.pi * f1 * 2.76 * t) * np.exp(-t * 6)
    return y * env


def swell(f1=110, f2=116.5, d=2.4):
    """低い不協和のふくらみ（ゆっくり立ち上がって消える）"""
    t = _t(d)
    env = np.sin(np.pi * t / d) ** 2
    return (np.sin(2 * np.pi * f1 * t) + np.sin(2 * np.pi * f2 * t) + 0.4 * np.sin(2 * np.pi * f1 * 1.5 * t)) * env


def bonsho(f=82.0, d=3.1):
    """遠くの鐘「ぼーん」：低い基音と、ずれた倍音がうなりながら長く残る"""
    t = _t(d)
    parts = ((1.0, 1.0, 0.7), (2.06, 0.55, 1.0), (2.74, 0.35, 1.4), (3.9, 0.18, 2.2), (5.4, 0.08, 3.0))
    y = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * k) for m, a, k in parts)
    y *= 1 + 0.18 * np.sin(2 * np.pi * 1.7 * t)          # うなり
    strike = _noise(0.08, 200, 1200) * np.exp(-np.arange(int(SR * 0.08)) / SR * 40) * 0.25
    y[: len(strike)] += strike
    return y * np.minimum(1, t / 0.01) * np.minimum(1, (d - t) / 0.8)   # 章カードの尺の中で自然に消える


SUBTLE = {
    "k_bonsho":   (lambda: bonsho(), 0.16),
    "k_dis_m2":   (lambda: dyad(440, 466.2), 0.07),            # 短2度（ぶつかる2音）
    "k_dis_tri":  (lambda: dyad(330, 466.2, 1.8), 0.07),       # 増4度
    "k_dis_glass": (lambda: dyad(1318.5, 1864.7, 1.2, 0.02, 3.5, True), 0.05),  # 高い増4度、ガラス質
    "k_dis_lo":   (lambda: swell(), 0.09),                     # 低いふくらみ
}
SUBTLE_ALIAS = {
    "whoosh_l": "k_dis_lo", "whoosh_s": "k_dis_glass", "thud": "k_dis_lo", "shimmer": "k_dis_glass",
    "pop_lo": "k_dis_m2", "pop_mid": "k_dis_tri", "pop_hi": "k_dis_glass", "chime_a": "k_dis_tri",
    "chime_b": "k_dis_m2", "chime_c": "k_dis_tri", "tick": "k_dis_glass", "tick_lo": "k_dis_m2",
    "paper": "k_dis_glass", "ding": "k_dis_tri",
}
SUBTLE_ROT = {
    "card":  [("k_dis_lo", "k_dis_tri"), ("k_dis_lo", "k_dis_m2")],
    "words": ["k_dis_glass", "k_dis_m2"],
    "cut":   ["k_dis_glass", "k_dis_m2", "k_dis_tri"],
}


def install_subtle():
    for k, v in SUBTLE.items():
        se.LIB[k] = v
    se.ALIAS.clear(); se.ALIAS.update(SUBTLE_ALIAS)
    se.ROT.clear(); se.ROT.update(SUBTLE_ROT)
    se._count.clear()
