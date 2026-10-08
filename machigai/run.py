"""間違い探しショート：1本分を最初から最後まで回す司令塔。
テーマ選択 → 元絵(Codex) → 差分 → 検査 → 動画 → 投稿 → 状態保存
失敗したら作り直し、最後までダメなら投稿せずに終了する（壊れた動画は出さない）。"""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from gen_image import generate
from make_diff import make
from render_short import build

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "state", "state.json")
OUT = os.path.join(ROOT, "out")

TITLES = ["間違いは{n}つ", "{n}か所、違う", "違うところが{n}つ"]

def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"episode": 0, "history": []}

def plan(ep, themes):
    """回ごとに変える要素：テーマ・個数・制限時間・見出し"""
    theme = themes[ep % len(themes)]
    n = [5, 4, 6][ep % 3]
    search = {4: 10, 5: 15, 6: 20}[n]
    title = TITLES[ep % len(TITLES)].format(n=n)
    return theme, n, search, title

def good_mix(ans):
    lv = [a["level"] for a in ans]
    return "易" in lv and ("中" in lv or "難" in lv)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="Codexを使わず仮絵で試す")
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    themes = json.load(open(os.path.join(ROOT, "themes.json")))
    st = load_state()
    ep = st["episode"] + 1
    theme, n, search, title = plan(ep, themes)
    print(f"#{ep:03d} {theme['ja']} n={n} {search}秒")

    base, diff, ans_p = f"{OUT}/base.png", f"{OUT}/diff.png", f"{OUT}/answers.json"
    done = None
    for img_try in range(3):
        src = generate(theme["en"], base, local=a.local)
        for seed in range(1, 9):
            ok, ans, stray = make(base, diff, ans_p, n=n, seed=seed + img_try * 100)
            if ok and good_mix(ans):
                done = (src, seed); break
        if done: break
        print("この絵では差分が作れないので描き直し")
    if not done:
        print("3枚試しても成立せず。今回は投稿しない"); sys.exit(1)

    video = f"{OUT}/short.mp4"
    build(base, diff, ans_p, video, search=search, title=title, audio=f"{OUT}/audio.wav")

    meta = {
        "title": f"【間違い探し】{theme['ja']} {search}秒で{n}つ #{ep:03d} #shorts",
        "description": (f"{search}秒で{n}か所の違いを探してください。答えは最後に出ます。\n"
                        f"テーマ：{theme['ja']}\n\n#間違い探し #脳トレ #shorts"),
        "tags": ["間違い探し", "脳トレ", "spot the difference", "puzzle", theme["ja"]],
    }
    json.dump(meta, open(f"{OUT}/meta.json", "w"), ensure_ascii=False, indent=1)

    vid = None
    if not a.no_upload:
        from upload import upload
        vid = upload(video, meta)
    st["episode"] = ep
    st["history"].append({"ep": ep, "theme": theme["ja"], "n": n, "image": done[0], "video_id": vid})
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, "w"), ensure_ascii=False, indent=1)
    print("完了", vid or "(投稿なし)")

if __name__ == "__main__":
    main()
