"""fetch_open.py — Commons の写真（PD/CC0/CC BY 系だけ）を幅を指定して取り、出典と一緒に保存する（サムネ作り用）。
使い方: python tools/fetch_open.py 保存先 2400 "key=File:名前.jpg;key2=File:..." """
import json, os, sys
sys.path.insert(0, "src")
import m4_images
out, width, spec = sys.argv[1], int(sys.argv[2]), sys.argv[3]
os.makedirs(out, exist_ok=True)
pairs = [x.split("=", 1) for x in spec.split(";") if "=" in x]
got = m4_images.commons_files([t for _, t in pairs], width=width)
cred = {}
for key, t in pairs:
    if t in got:
        m4_images.download(got[t]["url"], os.path.join(out, key + ".jpg"))
        cred[key] = got[t]["credit"]
        print("取得:", key, got[t]["credit"])
    else:
        print("取れず:", t)
json.dump(cred, open(os.path.join(out, "credits.json"), "w"), ensure_ascii=False, indent=1)
