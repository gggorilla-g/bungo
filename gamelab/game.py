"""AIずんだもん用の鬼畜ゲーム（決定論的な2Dアクション）。
1tick=1/60秒。面はタイル(40px)。行動は6tickごとに1つ（左右×ジャンプ）。"""
import math

T = 40                 # タイルの大きさ
ROWS = 18              # 画面の高さ 720px
GRAV, JUMP, RUN, MAXF = 0.9, -15.0, 5.0, 18.0
AW, AH = 24, 24        # プレイヤーの大きさ
STEP = 6               # 行動を変える間隔（tick）
MAXT = 60 * 70         # 1回の挑戦は70秒まで
ACTS = [(-1, 0), (0, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]   # (左右, ジャンプ)

def build_level():
    W = 200
    g = [[0] * W for _ in range(ROWS)]
    def fill(c0, c1, r0, r1, v=1):
        for c in range(c0, c1):
            for r in range(r0, r1):
                g[r][c] = v
    fill(0, W, 15, 18)                       # 地面
    fill(12, 15, 15, 18, 0)                  # 穴1
    for c in (19, 20): g[14][c] = 2          # トゲ
    fill(23, 25, 14, 15); fill(25, 27, 13, 15); fill(27, 29, 12, 15)   # 階段
    fill(29, 37, 15, 18, 0)                  # 長い穴
    fill(32, 34, 12, 13)                     # 浮き足場
    fill(37, 39, 12, 15)                     # 着地台
    fill(48, 58, 10, 11)                     # 低い天井
    for c in range(49, 57): g[11][c] = 3     # 天井のトゲ（下向き）
    for c in range(60, 77): fill(c, c + 1, 15, 18, 0)   # 柱の谷
    for c in (61, 64, 67, 70, 73): fill(c, c + 1, 13, 18)
    fill(77, 80, 15, 18)
    for c in (88, 89): g[14][c] = 2
    fill(96, 100, 15, 18, 0)                 # 穴
    fill(126, 140, 15, 18, 0)                # 崩れる橋の下は奈落
    for c in range(128, 138): g[15][c] = 5   # 崩れる床
    fill(126, 128, 15, 16); fill(138, 140, 15, 16)
    g[14][148] = 2
    for c in (163, 164, 167, 168, 171, 172): g[14][c] = 2
    for c in (181, 182): g[14][c] = 2
    return g

LEVEL = build_level()
WPX = len(LEVEL[0]) * T
GOAL_X = 190 * T
HIDDEN = [(45 * T, 14 * T), (176 * T, 14 * T)]                  # 近づくと飛び出すトゲ（x, y）
FAKE_GOAL_X = 93 * T
FAKE_GOAL2_X = 185 * T                          # 偽ゴール（旗の下がトゲ）

THWOMP_X = 116 * T                           # 落ちてくる天井（近づくと落ちる）
def thwomp_y(trig, t):
    """落ちる天井の上端y（幅2タイル・高さ2タイル）。trig=作動したtick"""
    if trig is None: return 120.0
    d = t - trig
    if d < 16: return 120 + 25 * d
    if d < 46: return 520.0
    return max(120.0, 520 - 4 * (d - 46))

def saws(t):
    """動くノコギリ（中心x, 中心y, 半径）"""
    return [(42 * T, (11.5 + 2.5 * math.sin(t / 40)) * T, 22),
            (84 * T + 3 * T * math.sin(t / 50), 13.5 * T, 22),
            (104 * T, (12 + 2 * math.sin(t / 30 + 1)) * T, 22),
            (146 * T, (11.5 + 2.5 * math.sin(t / 25)) * T, 22),
            (151 * T, (11.5 + 2.5 * math.sin(t / 25 + 2.2)) * T, 22),
            (157 * T + 2 * T * math.sin(t / 35), 13.5 * T, 22)]

def solid(px, py, gone=()):
    c, r = int(px // T), int(py // T)
    if c < 0 or c >= len(LEVEL[0]): return True
    if r < 0 or r >= ROWS: return False
    v = LEVEL[r][c]
    if v == 5: return (r, c) not in gone
    return v in (1, 4)

def hit_box_solid(x, y, gone=()):
    return any(solid(px, py, gone) for px in (x, x + AW - 1) for py in (y, y + AH - 1))

class Agent:
    __slots__ = ("x", "y", "vx", "vy", "ground", "alive", "won", "t", "maxx", "death", "cause", "gone", "stand", "bumped", "trig")
    def __init__(self):
        self.x, self.y = 2 * T, 15 * T - AH
        self.vx = self.vy = 0.0
        self.ground, self.alive, self.won = True, True, False
        self.t, self.maxx, self.death, self.cause = 0, self.x, None, None
        self.gone, self.stand, self.bumped, self.trig = set(), {}, set(), None

    def step(self, act, t):
        if not self.alive or self.won: return
        mx, jp = ACTS[act]
        self.vx = mx * RUN
        if jp and self.ground: self.vy = JUMP
        self.vy = min(self.vy + GRAV, MAXF)
        G = self.gone
        nx = self.x + self.vx
        if not hit_box_solid(nx, self.y, G): self.x = nx
        ny = self.y + self.vy
        if hit_box_solid(self.x, ny, G):
            if self.vy > 0:
                self.y = (int((ny + AH) // T)) * T - AH; self.ground = True
                r = int((self.y + AH) // T)
                for px in (self.x, self.x + AW - 1):
                    c = int(px // T)
                    if 0 <= c < len(LEVEL[0]) and LEVEL[r][c] == 5:
                        k = (r, c); self.stand[k] = self.stand.get(k, 0) + 1
                        if self.stand[k] > 14: G.add(k)
            else:
                r = int(ny // T)
                for px in (self.x, self.x + AW - 1):
                    c = int(px // T)
                    if 0 <= r < ROWS and 0 <= c < len(LEVEL[0]) and LEVEL[r][c] == 4: self.bumped.add((r, c))
                self.y = (r + 1) * T
        else:
            self.y = ny; self.ground = False
        self.t = t
        self.maxx = max(self.maxx, self.x)
        self.check(t)

    def die(self, cause):
        self.alive, self.death, self.cause = False, (self.x, self.y), cause

    def check(self, t):
        cx, cy = self.x + AW / 2, self.y + AH / 2
        if self.y > ROWS * T: return self.die("落下")
        for px in (self.x + 2, self.x + AW - 3):
            for py in (self.y + 2, self.y + AH - 3):
                c, r = int(px // T), int(py // T)
                if 0 <= r < ROWS and 0 <= c < len(LEVEL[0]):
                    v = LEVEL[r][c]
                    if v == 2 and py % T > T / 2: return self.die("トゲ")
                    if v == 3 and py % T < T / 2: return self.die("天井トゲ")
        for sx, sy, rad in saws(t):
            if (cx - sx) ** 2 + (cy - sy) ** 2 < (rad + 10) ** 2: return self.die("ノコギリ")
        if self.trig is None and cx > THWOMP_X - 20: self.trig = t
        ty = thwomp_y(self.trig, t)
        if THWOMP_X - 2 < self.x + AW and self.x < THWOMP_X + 2 * T - 2 and self.y < ty + 2 * T - 2 and self.y + AH > ty + 2:
            return self.die("落ちる天井")
        for hx, hy in HIDDEN:
            if hx - 4 < cx < hx + T + 4 and self.y + AH > hy + 6: return self.die("隠しトゲ")
        for fx in (FAKE_GOAL_X, FAKE_GOAL2_X):
            if fx - 4 < cx < fx + T and self.y + AH > 14 * T + 4: return self.die("偽ゴール")
        if self.x >= GOAL_X: self.won = True

def run(genome, record=False):
    a = Agent(); path = []
    for t in range(MAXT):
        a.step(genome[min(t // STEP, len(genome) - 1)], t)
        if record: path.append((a.x, a.y, a.alive, a.won))
        if not a.alive or a.won: break
    return a, path
