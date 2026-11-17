# 仕組みショート（kaizo3d の台本）から投稿キット（【タイトル】【説明】【タグ】）を書く
#   python tools/explain_kit.py <ID>  → nazo/manual/explain/<ID>_upload.txt
import json, sys
sid = sys.argv[1]
sp = json.load(open(f"nazo/shorts/{sid}.json", encoding="utf-8"))
txt = f"【タイトル】\n{sp['title']}\n\n【説明】\n{sp['desc']}\n\n【タグ】\n{','.join(sp['tags'])}\n"
open(f"nazo/manual/explain/{sid}_upload.txt", "w", encoding="utf-8").write(txt)
print(txt)
