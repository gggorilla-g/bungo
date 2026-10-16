"""作り終えた BUNGO 動画の手動投稿キット（サムネ・タイトル・概要欄・タグ）と確認用のコマ一覧を作る。
  WORK=001567 VIDEO=dl/001567.mp4 python tools/bungo_kit.py"""
import json, os, subprocess, sys
sys.path.insert(0, "src"); sys.path.insert(0, "nazo")
import m4_images, m8_upload, thumb

w = os.environ["WORK"]
k = json.load(open(f"stock/{w}.json", encoding="utf-8"))
meta = json.load(open(f"state/texts/{w}.json", encoding="utf-8"))["meta"]
kit = f"state/manual/{w}"
os.makedirs(kit, exist_ok=True)
os.makedirs("build", exist_ok=True)
hit = m4_images.fetch_image([k["sections"][0]["img_query"]], "build/img0.jpg")
credits = [hit["credit"]] if hit else []
thumb.build(k["thumbnail"]["main_copy"], f'{meta["author"]}『{meta["title"]}』',
            "build/img0.jpg" if hit else None, f"{kit}/thumb.png",
            badge="BUNGO　10分でわかる名作", palette=thumb.PALETTE_BUNGO)
open(f"{kit}/upload.txt", "w", encoding="utf-8").write(
    "【タイトル】\n" + k["title_candidates"][0] + "\n\n【概要欄】\n"
    + m8_upload.make_description(k, credits) + "\n\n【タグ】\n" + ",".join(k["tags"]) + "\n")

# 確認用：20秒ごとのコマを並べた一覧
v = os.environ.get("VIDEO")
if v and os.path.exists(v):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", v],
                               capture_output=True, text=True).stdout)
    open(f"{kit}/duration.txt", "w").write(f"{dur:.1f}\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", v, "-vf", "fps=1/20,scale=480:-1,tile=5x8",
                    "-frames:v", "1", f"{kit}/sheet.jpg"], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", v, "-vf", "select='lt(t,60)*not(mod(n,60))',scale=480:-1,tile=5x6",
                    "-vsync", "vfr", "-frames:v", "1", f"{kit}/sheet_open.jpg"], check=True)
print("kit:", kit)
