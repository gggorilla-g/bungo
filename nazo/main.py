# nazo/main.py — NAZO パイプライン本体（月金 JST12:35 にActionsが実行、21:00公開）
# 在庫(このチャットで仕込んだ台本＋確定読み)だけで動く。LLM・有料APIは一切呼ばない。
# フェイルセーフは「投稿しない」: 事実照合・読みのどちらかに落ちたら欠番にしてログだけ残す。
import json, os, sys, traceback, datetime
sys.path.insert(0, "src"); sys.path.insert(0, "nazo")
import m4_images, render, check, brand, thumb

S = "nazo/state"


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def save(p, d):
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _no_llm(_):
    raise RuntimeError("NAZOは在庫方式専用: 実行時にLLMは呼ばない")



def zoom_crop(path, zoom):
    """画像の一部を切り出して「寄り」の絵を作る。zoom = [中心x, 中心y, 幅]（どれも画像に対する0〜1の割合）。
    切り出す枠は画面と同じ16:9。画像の端からはみ出す分は内側に寄せる"""
    import subprocess, hashlib
    cx, cy, fw = zoom
    W, H = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height", "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip().split(",")[:2])
    w = min(W, max(64, int(W * fw)))
    h = min(H, int(w * 9 / 16))
    w = min(w, int(h * 16 / 9))
    x = min(max(0, int(cx * W - w / 2)), W - w)
    y = min(max(0, int(cy * H - h / 2)), H - h)
    out = path.replace(".jpg", f"_z{hashlib.md5(str(zoom).encode()).hexdigest()[:6]}.jpg")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vf", f"crop={w}:{h}:{x}:{y}", "-q:v", "2", out], check=True)
    return out

def main():
    published = load(f"{S}/published.json", [])
    failures = load(f"{S}/failures.json", [])
    queue = load(f"{S}/queue.json", [])
    if not queue:
        print("在庫切れ: チャットで「NAZO在庫補充」を。今回は何もしない"); return
    work = queue.pop(0)
    try:
        src = load(f"{S}/texts/{work['id']}.json", None)
        if src is None:
            raise RuntimeError("本文(Wikipedia)が手元にない")
        k = work["kousei"]
        ok, errs = check.validate(k, src)
        if not ok:
            raise RuntimeError("事実照合に不合格: " + " / ".join(errs[:5]))
        # 画像: 記事に載っている画像（PD/CC BY/CC BY-SA）を集め、全カットに割り当てる
        images, credits = {}, []
        meta = src["meta"]
        pages = [("ja", meta["title"])] + ([("en", meta["en_title"])] if meta.get("en_title") else [])
        pool = []
        for j, hit in enumerate(m4_images.article_images(pages, max_n=12)):
            if m4_images.download(hit["url"], f"build/pool{j}.jpg"):
                pool.append(f"build/pool{j}.jpg")
                credits.append(hit["credit"])
        if len(pool) < 3:   # 記事の画像が少ない題材は、台本の検索語で補う
            for i, s in enumerate(k["sections"]):
                q = s.get("img_query")
                if not q:
                    continue
                hit = m4_images.fetch_image([q], f"build/img{i}.jpg",
                                            sources=(m4_images._wikimedia, m4_images._met))
                if hit:
                    pool.append(f"build/img{i}.jpg")
                    if hit["credit"] not in credits:
                        credits.append(hit["credit"])
        if pool:
            images["pool"] = pool
        # 台本で場面ごとに画像を指定している場合（語っている内容と画像を対応させる）
        wanted = [im["file"] for s in k["sections"] for im in s.get("images", [])]
        wanted += [f for f in (k.get("title_image"), k.get("thumb_image")) if f]
        wanted += [b["file"] for s in k["sections"] for b in s.get("motion", []) if b.get("file")]
        if wanted:
            got, local = m4_images.commons_files(wanted), {}
            print(f"指定画像の情報取得 {len(got)}/{len(set(wanted))}")
            # 寄り（zoom）を使う画像は、切り出しても粗くならないよう大きめで取る
            zoomed = {im["file"] for s in k["sections"] for im in s.get("images", []) if im.get("zoom")}
            zoomed |= {b["file"] for s in k["sections"] for b in s.get("motion", []) if b.get("file") and b.get("zoom")}
            if zoomed:
                got.update(m4_images.commons_files(sorted(zoomed), width=4000))
            for j, (f, info) in enumerate(got.items()):
                if m4_images.download(info["url"], f"build/sel{j}.jpg", fallback=info.get("orig")):
                    local[f] = f"build/sel{j}.jpg"
            used = set()
            images["sec_list"] = {}
            for i, s in enumerate(k["sections"]):
                lst = [(im.get("at"), zoom_crop(local[im["file"]], im["zoom"]) if im.get("zoom") else local[im["file"]])
                       for im in s.get("images", []) if im["file"] in local]
                if lst:
                    images["sec_list"][i] = lst
                    used |= {im["file"] for im in s.get("images", []) if im["file"] in local}
            images["motion_files"] = {b["file"]: local[b["file"]] for s in k["sections"]
                                      for b in s.get("motion", []) if b.get("file") in local}
            used |= set(images["motion_files"])
            for key in ("title_image", "thumb_image"):
                if k.get(key) in local:
                    images[key] = local[k[key]]; used.add(k[key])
            sel_credits = sorted({got[f]["credit"] for f in used})
            all_sel = len(images["sec_list"]) == len(k["sections"])
            # 全セクションが指定画像なら、記事の画像は使わない（出典も載せない）
            credits = sel_credits if all_sel else sel_credits + [c for c in credits if c not in sel_credits]
            print(f"指定画像 {len(local)}/{len(set(wanted))} 枚")
        print(f"画像 {len(pool)} 枚")
        os.makedirs("output", exist_ok=True)
        out = f"output/nazo_{work['id']}.mp4"
        br = brand.nazo_brand(work)
        render.build_video(k, work, "", {}, images, out, llm=_no_llm, brand=br)
        thumb.build(k["thumbnail"]["main_copy"], work["title"], images.get("thumb_image") or (pool[0] if pool else None), "output/thumb.png")
        vid = None
        import upload, shutil
        chapters = json.load(open("build/chapters.json", encoding="utf-8"))
        # 手動投稿用キット（タイトル・チャプター付き説明・タグ・サムネイル）。自動投稿の有無にかかわらず残す
        kit = f"nazo/manual/{work['id']}"; os.makedirs(kit, exist_ok=True)
        desc = upload.make_description(k, src["meta"], credits, chapters=chapters, work_id=work["id"])
        open(f"{kit}/credits.md", "w", encoding="utf-8").write(upload.credits_md(work["title"], credits))
        txt = ("【タイトル】\n" + k["title_candidates"][0] + "\n\n【説明】\n" + desc +
               "\n\n【タグ】\n" + ",".join(k["tags"]) + "\n")
        open(f"{kit}/upload.txt", "w", encoding="utf-8").write(txt)
        open("output/upload.txt", "w", encoding="utf-8").write(txt)
        shutil.copy("output/thumb.png", f"{kit}/thumb.png")
        if os.environ.get("YT_REFRESH_TOKEN"):
            vid = upload.upload(out, "output/thumb.png", k, src["meta"], credits, chapters=chapters, work_id=work["id"])
        published.append({"id": work["id"], "title": work["title"], "video_id": vid,
                          "date": datetime.date.today().isoformat(), "credits": credits})
        save(f"{S}/published.json", published)
        save(f"{S}/queue.json", queue)
        print(f"完了: {work['title']} → {vid or '(未投稿/ローカル)'}")
    except Exception as e:
        failures.append({"id": work.get("id"), "title": work.get("title"),
                         "date": datetime.date.today().isoformat(), "error": str(e)})
        save(f"{S}/failures.json", failures)
        save(f"{S}/queue.json", queue)   # 不合格の回は在庫から外す（同じ失敗を繰り返さない）
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
