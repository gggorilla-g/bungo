# wm_diag.py — 台本で指定した画像が全部取れるかを、動画を作らずに確認する
import json, sys, time
sys.path.insert(0, "src")
import m4_images
k = json.load(open("nazo/drafts/voynich.json", encoding="utf-8"))
wanted = [im["file"] for s in k["sections"] for im in s.get("images", [])] + [k["title_image"], k["thumb_image"]]
t = time.time()
got = m4_images.commons_files(wanted)
out = [f"情報 {len(got)}/{len(set(wanted))}"]
miss = [f for f in set(wanted) if f not in got]
out += ["情報なし: " + f for f in miss]
ok = 0
for j, (f, info) in enumerate(got.items()):
    if m4_images.download(info["url"], f"build/d{j}.jpg", fallback=info.get("orig")):
        ok += 1
    else:
        out.append("取得失敗: " + f)
out.append(f"取得 {ok}/{len(got)}  {time.time()-t:.0f}秒")
print("\n".join(out)); open("state/wm_diag.txt", "w").write("\n".join(out))
