#!/usr/bin/env python3
"""vet.py — 目で確かめた動画だけを上げるための照合（オーナー 11/23「勘所を押さえない動画はあげないで。密度が綺麗なんだから」）

定時の投稿は新しい作業場で動画を作り直してから上げる。作り直した絵が、確かめた時の絵と同じかをここで照合する。
  python3 tools/vet.py add <id> "見た点のメモ"   output/<id>.mp4 の指紋を nazo/ballsim/vetted.json に書く（最後の絵・途中の絵・出だしを目で見てから）
  python3 tools/vet.py check <id>               いまの output/<id>.mp4 が確かめた時と同じか。未確認・違う絵なら終了コード 1（upq.sh がその行をとばす）
  python3 tools/vet.py fp <mp4>                 指紋を表示（長さ、最後の絵の埋まり具合％、絵の縮小）
指紋：長さ（秒）／最後の絵（終わりの1.6秒前）で、明るい画素の割合（題名より下の範囲）／最後の絵と真ん中の絵の 12×12 の縮小。
"""
import json, os, subprocess, sys, datetime, io

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.path.join(ROOT, "nazo", "ballsim", "vetted.json")
TOL_DUR, TOL_FILL, TOL_TH = 0.4, 6.0, 14.0


def _frame(mp4, t):
    from PIL import Image
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.2f}", "-i", mp4, "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                         stdin=subprocess.DEVNULL, capture_output=True).stdout
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _thumb(im):
    g = im.convert("L").resize((12, 12))
    return g.tobytes().hex()


def fp(mp4):
    import numpy as np
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True).stdout.strip())
    end, mid = _frame(mp4, dur - 1.6), _frame(mp4, dur * .5)
    a = np.asarray(end).astype(float); h = a.shape[0]
    fill = float((a[int(h * .30):int(h * .88)].max(axis=2) > 60).mean() * 100)
    return {"dur": round(dur, 2), "fill": round(fill, 1), "end": _thumb(end), "mid": _thumb(mid)}


def _diff(a, b):
    x = [int(a[i:i + 2], 16) for i in range(0, len(a), 2)]; y = [int(b[i:i + 2], 16) for i in range(0, len(b), 2)]
    return sum(abs(p - q) for p, q in zip(x, y)) / max(1, len(x))


def load():
    return json.load(open(DB)) if os.path.exists(DB) else {}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fp":
        f = fp(sys.argv[2]); print(f"長さ {f['dur']}秒  埋まり {f['fill']}%"); return 0
    if cmd == "add":
        vid = sys.argv[2]; note = sys.argv[3] if len(sys.argv) > 3 else ""; loose = "--loose" in sys.argv
        f = fp(os.path.join(ROOT, "output", vid + ".mp4")); f["note"] = note; f["date"] = datetime.date.today().isoformat()
        if loose: f["loose"] = True   # 毎回動きが変わる作り（乱数）のもの：長さと埋まり具合だけ照合
        db = load(); db[vid] = f; json.dump(db, open(DB, "w"), ensure_ascii=False, indent=1, sort_keys=True)
        print(f"確認済みに登録: {vid}  長さ {f['dur']}秒  埋まり {f['fill']}%"); return 0
    if cmd == "check":
        vid = sys.argv[2]; db = load()
        if vid not in db: print("未確認（vetted.json に無い）"); return 1
        ref = db[vid]; f = fp(os.path.join(ROOT, "output", vid + ".mp4")); bad = []
        if abs(f["dur"] - ref["dur"]) > TOL_DUR: bad.append(f"長さ {ref['dur']}→{f['dur']}秒")
        if abs(f["fill"] - ref["fill"]) > TOL_FILL: bad.append(f"埋まり {ref['fill']}→{f['fill']}%")
        if not ref.get("loose"):
            for k, nm in (("end", "最後の絵"), ("mid", "真ん中の絵")):
                dv = _diff(f[k], ref[k])
                if dv > TOL_TH: bad.append(f"{nm}が違う（差 {dv:.0f}）")
        if bad: print("確かめた時と違う: " + "、".join(bad)); return 1
        print("確認済みと一致"); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
