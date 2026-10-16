# main.py — BUNGO パイプライン本体(週3回 火木土 JST12:05 にActionsが実行、21:00公開)
# 設計原則: フェイルセーフは「投稿しない」。台本・引用・読み仮名のどれかの検査に落ちたら
#           欠番にしてログだけ残す（誤読や捏造引用のある動画は出さない）。
import json, os, sys, traceback, datetime
sys.path.insert(0, "src")
import m1_select, m2_extract, m3_script, m4_images, render, m8_upload

def load(p): return json.load(open(p, encoding="utf-8"))
def save(p, d): json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def main():
    published = load("state/published.json")
    failures = load("state/failures.json")
    queue = load("state/queue.json")
    pub_ids = {p["work_id"] for p in published}
    fail_counts = {}
    for f in failures:
        fail_counts[f["work_id"]] = fail_counts.get(f["work_id"], 0) + 1

    # 1) 作品決定: 在庫(チャットで仕込んだ台本+確定読み)だけを使う。
    #    在庫切れなら何もせず終了（有料APIを勝手に呼ばない）。ALLOW_API=1 のときだけ従来の自動生成。
    if queue:
        work = queue.pop(0)
    elif os.environ.get("ALLOW_API") == "1":
        skip = pub_ids | {w for w, n in fail_counts.items() if n >= 3}  # 3敗で永久スキップ
        work = m1_select.select_next(skip)
    else:
        print("在庫切れ: チャットで「在庫補充」を。今回は何もしない"); return
    if not work:
        print("候補なし。終了"); return

    try:
        # 2) 本文
        cached = f"state/texts/{work['work_id']}.json"
        if os.path.exists(cached):
            c = json.load(open(cached, encoding="utf-8")); text, ruby = c["text"], c["ruby"]
        else:
            text, ruby = m2_extract.fetch_text(work["url"])
        # 3) 台本 (キューに構成済みJSONがあればAPI呼び出しをスキップ=バッチ方式)
        kousei = work.get("kousei") or m3_script.generate(work, text)
        ok, why = m3_script.validate(kousei, text)
        if not ok:
            raise RuntimeError(f"品質チェック不合格: {why}")
        # 4) 画像 (セクションごと。Noneはタイポグラフィ型に自動フォールバック)
        images, credits = {}, []
        for i, s in enumerate(kousei["sections"]):
            q = s.get("img_query")
            if not q or s.get("images"): continue   # 画像を指定済みのセクションは検索しない
            hit = m4_images.fetch_image([q], f"build/img{i}.jpg")
            if hit:
                images[i] = f"build/img{i}.jpg"
                if hit["credit"] not in credits: credits.append(hit["credit"])
        # 4b) 台本で場面ごとに画像を指定している場合（謎と同じ方式。語っている内容と画像を対応させる）
        k = kousei
        wanted = [im["file"] for s in k["sections"] for im in s.get("images", [])]
        wanted += [f for f in (k.get("title_image"), k.get("thumb_image")) if f]
        wanted += [h["file"] for h in k.get("hook", []) if h.get("file")]
        if wanted:
            got, local = m4_images.commons_files(wanted), {}
            for j, (f, info) in enumerate(got.items()):
                if m4_images.download(info["url"], f"build/sel{j}.jpg", fallback=info.get("orig")):
                    local[f] = f"build/sel{j}.jpg"
            print(f"指定画像 {len(local)}/{len(set(wanted))} 枚")
            used = set()
            images["sec_list"] = {}
            for i, s in enumerate(k["sections"]):
                lst = [(im.get("at"), local[im["file"]]) for im in s.get("images", []) if im["file"] in local]
                if lst:
                    images["sec_list"][i] = lst
                    used |= {im["file"] for im in s.get("images", []) if im["file"] in local}
            images["hook_files"] = {h["file"]: local[h["file"]] for h in k.get("hook", []) if h.get("file") in local}
            used |= set(images["hook_files"])
            for key in ("title_image", "thumb_image"):
                if k.get(key) in local:
                    images[key] = local[k[key]]; used.add(k[key])
            sel = sorted({got[f]["credit"] for f in used})
            credits = sel + [c for c in credits if c not in sel]
            if len(images["sec_list"]) == len(k["sections"]):
                credits = sel
        # 5-7) 動画+サムネ
        os.makedirs("output", exist_ok=True)
        out = f"output/{work['work_id']}.mp4"
        render.build_video(kousei, work, text, ruby, images, out, llm=m3_script._call_llm)
        # サムネ：謎チャンネルと同じ強い型（箱囲みの極太文字）を紺×金で
        sys.path.insert(0, "nazo")
        import thumb as thumbmod
        thumbmod.build(kousei["thumbnail"]["main_copy"], f'{work["author"]}『{work["title"]}』',
                       images.get("thumb_image") or images.get("title_image") or images.get(0),
                       "output/thumb.png", badge="BUNGO　10分でわかる名作",
                       palette=thumbmod.PALETTE_BUNGO)
        # 8) 投稿 (Secrets未設定ならスキップ=ローカル/Phase1でも同一コードが動く)
        vid = None
        if os.environ.get("YT_REFRESH_TOKEN"):
            chapters = json.load(open("build/chapters.json", encoding="utf-8"))
            vid = m8_upload.upload(out, "output/thumb.png", kousei, credits,
                                   chapters=chapters, author=work["author"])
        if not vid:   # 自動投稿しないときは、手動で上げるための一式（サムネ・タイトル・概要欄・タグ）を残す
            kit = f"state/manual/{work['work_id']}"
            os.makedirs(kit, exist_ok=True)
            import shutil
            shutil.copy("output/thumb.png", f"{kit}/thumb.png")
            chapters = json.load(open("build/chapters.json", encoding="utf-8")) if os.path.exists("build/chapters.json") else None
            open(f"{kit}/upload.txt", "w", encoding="utf-8").write(
                "【タイトル】\n" + kousei["title_candidates"][0] + "\n\n【概要欄】\n"
                + m8_upload.make_description(kousei, credits, chapters)
                + "\n\n【タグ】\n" + ",".join(kousei["tags"]) + "\n")
            print("手動投稿用:", kit)
        # 9) Instagramリール素材（失敗しても本編の投稿・記録には影響させない）
        try:
            import reel
            reel.build(kousei, work, credits)
            print("リール素材: output/reel.mp4")
        except Exception as e:
            print("リール作成失敗(本編は成功):", e)
        published.append({"work_id": work["work_id"], "title": work["title"],
            "author": work["author"], "video_id": vid,
            "date": datetime.date.today().isoformat(), "credits": credits})
        save("state/published.json", published)
        save("state/queue.json", queue)
        print(f"完了: {work['title']} → {vid or '(未投稿/ローカル)'}")
    except Exception as e:
        failures.append({"work_id": work.get("work_id"), "title": work.get("title"),
            "date": datetime.date.today().isoformat(), "error": str(e)})
        save("state/failures.json", failures)
        traceback.print_exc()
        sys.exit(1)  # Actionsの失敗通知メールを発火させる

if __name__ == "__main__":
    main()
