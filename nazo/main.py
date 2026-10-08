# nazo/main.py — NAZO パイプライン本体（月金 JST12:35 にActionsが実行、21:00公開）
# 在庫(このチャットで仕込んだ台本＋確定読み)だけで動く。LLM・有料APIは一切呼ばない。
# フェイルセーフは「投稿しない」: 事実照合・読みのどちらかに落ちたら欠番にしてログだけ残す。
import json, os, sys, traceback, datetime
sys.path.insert(0, "src"); sys.path.insert(0, "nazo")
import m4_images, render, check, brand

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
        images, credits = {}, []
        for i, s in enumerate(k["sections"]):
            q = s.get("img_query")
            if not q:
                continue
            hit = m4_images.fetch_image([q], f"build/img{i}.jpg",
                                        sources=(m4_images._wikimedia, m4_images._met))
            if hit:
                images[i] = f"build/img{i}.jpg"
                if hit["credit"] not in credits:
                    credits.append(hit["credit"])
        os.makedirs("output", exist_ok=True)
        out = f"output/nazo_{work['id']}.mp4"
        br = brand.nazo_brand(work)
        render.build_video(k, work, "", {}, images, out, llm=_no_llm, brand=br)
        render.build_thumbnail(k, work, images.get(0), "output/thumb.png", brand=br)
        vid = None
        if os.environ.get("YT_REFRESH_TOKEN"):
            import upload
            chapters = json.load(open("build/chapters.json", encoding="utf-8"))
            vid = upload.upload(out, "output/thumb.png", k, src["meta"], credits, chapters=chapters)
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
