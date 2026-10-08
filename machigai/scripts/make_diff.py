"""任意の元絵に、コードで差分を入れる。
・絵を色でざっくり分けて「背景の上に乗った独立した物体」を探す
・物体単位で 色を変える／消す／左右反転 のどれかを施す
・答えは「実際に変わったピクセル」から逆算する
・最後に全体の差分を数え、答えの枠外に変化があれば失敗扱い（予期しない違いの混入を防ぐ）"""
import json, random, sys
import cv2, numpy as np

def segment(img, k=14):
    small = cv2.GaussianBlur(img, (3, 3), 0)
    Z = small.reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, lab, _ = cv2.kmeans(Z, k, None, crit, 2, cv2.KMEANS_PP_CENTERS)
    return lab.reshape(img.shape[:2])

def objects(img, rnd):
    H, W = img.shape[:2]
    q = segment(img)
    objs = []
    for c in np.unique(q):
        n, lab, st, _ = cv2.connectedComponentsWithStats((q == c).astype(np.uint8))
        # 空・地面など「背景の色」の小さな塊は、柵のすき間のような"穴"なので物体扱いしない
        if n > 1 and st[1:, 4].max() > W*H*0.03:
            continue
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if a < 350 or a > W*H*0.02:
                continue
            if x < 15 or y < 15 or x+w > W-15 or y+h > H-15:
                continue
            m = (lab == i).astype(np.uint8)
            # 周囲1リングがほぼ単一の色＝背景の上に独立して乗っている物体
            ring = cv2.dilate(m, np.ones((9, 9), np.uint8)) - m
            rl = q[ring > 0]
            dom = np.bincount(rl).max() / max(len(rl), 1)
            if dom < 0.75:
                continue
            objs.append({"mask": m, "bbox": (x, y, w, h), "area": int(a)})
    rnd.shuffle(objs)
    return objs

def op_recolor(img, m, rnd):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.int16)
    sel = m > 0
    if np.median(hsv[..., 1][sel]) < 60:
        return None, None          # 白黒グレーは色替えしても分かりにくい
    hsv[..., 0][sel] = (hsv[..., 0][sel] + rnd.choice([40, 60, 90])) % 180
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR), "色"

def op_erase(img, m, rnd):
    mm = cv2.dilate(m, np.ones((5, 5), np.uint8))
    ring = cv2.dilate(mm, np.ones((7, 7), np.uint8)) - mm
    rp = img[ring > 0].astype(np.float32)
    if rp.std(axis=0).max() < 10:      # 周りがベタ塗りなら同じ色で埋める（ぼやけ跡を残さない）
        out = img.copy(); out[mm > 0] = np.median(rp, axis=0).astype(np.uint8)
        return out, "消失"
    return cv2.inpaint(img, mm * 255, 7, cv2.INPAINT_TELEA), "消失"

def op_flip(img, m, rnd):
    x, y, w, h = cv2.boundingRect(m)
    fm = np.zeros_like(m); fm[y:y+h, x:x+w] = cv2.flip(m[y:y+h, x:x+w], 1)
    if (fm & m).sum() > 0.85 * m.sum():
        return None, None          # 左右対称の物は反転しても変化しない
    base = cv2.inpaint(img, cv2.dilate(m, np.ones((5, 5), np.uint8)) * 255, 7, cv2.INPAINT_TELEA)
    src = img.copy(); src[y:y+h, x:x+w] = cv2.flip(img[y:y+h, x:x+w], 1)
    out = base.copy(); out[fm > 0] = src[fm > 0]
    return out, "反転"

OPS = [op_recolor, op_erase, op_flip]

def make(base_path, out_path, ans_path, n=5, seed=1):
    rnd = random.Random(seed)
    img = cv2.imread(base_path)
    H, W = img.shape[:2]
    out = img.copy()
    answers, boxes = [], []
    order = OPS[:]
    for o in objects(img, rnd):
        if len(answers) >= n:
            break
        x, y, w, h = o["bbox"]
        pad = 40   # 答え同士が近すぎないように
        if any(x < bx+bw+pad and bx < x+w+pad and y < by+bh+pad and by < y+h+pad for bx, by, bw, bh in boxes):
            continue
        # 種類が偏らないよう、次に欲しい種類から試す（消失ばかりになるのを防ぐ）
        want = [op_recolor, op_erase, op_flip][len(answers) % 3]
        rest = [p for p in OPS if p is not want]; rnd.shuffle(rest)
        for op in [want] + rest:
            new, kind = op(out, o["mask"], rnd)
            if new is None:
                continue
            diff = np.abs(new.astype(int) - out.astype(int)).sum(axis=2) > 45
            if diff.sum() < 300:
                continue
            ys, xs = np.nonzero(diff)
            delta = float(np.abs(new.astype(int) - out.astype(int)).sum(axis=2)[diff].mean())
            vis = (diff.sum() / (W*H) * 100) * (delta / 100)   # 見つけやすさ＝変化面積(%)×色の差
            out = new
            answers.append({"x": int(xs.min()), "y": int(ys.min()), "w": int(xs.max()-xs.min()+1),
                            "h": int(ys.max()-ys.min()+1), "kind": kind, "vis": round(float(vis), 3),
                            "level": "易" if vis > 0.6 else ("中" if vis > 0.2 else "難")})
            boxes.append((x, y, w, h))
            break
    # 検証
    full = (np.abs(out.astype(int) - img.astype(int)).sum(axis=2) > 45).astype(np.uint8)
    inside = np.zeros_like(full)
    for a in answers:
        inside[a["y"]:a["y"]+a["h"], a["x"]:a["x"]+a["w"]] = 1
    stray = int((full & (1 - inside)).sum())
    ok = len(answers) == n and stray == 0
    answers.sort(key=lambda a: -a["vis"])   # 答えは見つけやすい順に出す（最後が難問）
    cv2.imwrite(out_path, out)
    json.dump({"n": len(answers), "answers": answers, "stray_px": stray, "ok": ok, "size": [W, H]},
              open(ans_path, "w"), ensure_ascii=False, indent=1)
    return ok, answers, stray

if __name__ == "__main__":
    seed = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    ok, ans, stray = make(*sys.argv[1:4], n=int(sys.argv[4]) if len(sys.argv) > 4 else 5, seed=seed)
    print("ok" if ok else "NG", len(ans), "stray", stray)
    for a in ans: print(a)
