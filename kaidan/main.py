# kaidan/main.py — 怪談チャンネル「今晩の百物語」の制作本体（Actionsが実行）
# 在庫（このチャットで仕込んだ台本＋確定した読み）だけで動く。実行時にLLMは呼ばない。
# フェイルセーフは「出さない」：検査に落ちたら欠番にしてログだけ残す。
import json, os, sys, shutil, traceback, datetime
sys.path.insert(0, "src"); sys.path.insert(0, "nazo"); sys.path.insert(0, "kaidan")
import m4_images, render, thumb
import kaidan_check as check, kaidan_brand as brand

S = "kaidan/state"
PALETTE_KAIDAN = {"badge": ((255, 255, 255), (142, 20, 20)), "l1": ((255, 255, 255), (0, 0, 0)),
                  "l2": ((255, 255, 255), (142, 20, 20)), "subj": ((0, 0, 0), (240, 236, 228))}


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def save(p, d):
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _no_llm(_):
    raise RuntimeError("怪談は在庫方式専用: 実行時にLLMは呼ばない")


def description(k, work, credits, chapters):
    src = f"{work['author']}『{work['title']}』" + (f"（{work['translator'].removesuffix('訳')}訳）" if work.get("translator") else "")
    lines = [k["description"], ""]
    if chapters:
        lines += [f"{render_ts(t) if i else '0:00'} {h}" for i, (h, t) in enumerate(chapters)] + [""]
    lines += ["※この動画は、権利の切れた古典の怪談を、いまの言葉で語り直した朗読です。実話ではありません。", "",
              "#怪談 #百物語 #朗読", "", "──",
              f"原作: {src}（青空文庫 {work.get('url', 'https://www.aozora.gr.jp/')}）",
              f"語り: VOICEVOX:{brand.VOICE_NAME}", brand.bgm_for(work, k)[1]]
    for c in credits:
        lines.append(f"画像: {c}")
    return "\n".join(lines)


def render_ts(sec):
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


def assert_terms(desc, tags):
    """冥鳴ひまりの規約：クレジット必須。欠けていたら出さない"""
    if f"VOICEVOX:{brand.VOICE_NAME}" not in desc:
        raise RuntimeError("概要欄に声のクレジットがない")
    if "実話ではありません" not in desc:
        raise RuntimeError("概要欄に「実話ではありません」がない")


def rerender_entry(wid):
    """作り直し用：台本(drafts)と原作から在庫と同じ形の1件を組み立てる（stock.py push と同じ読みの差し込み）。
    読みの関門は在庫に積んだときに通過済み。queue/published には触れない"""
    import importlib.util, yomi
    spec = importlib.util.spec_from_file_location("kaidan_stock", "kaidan/stock.py")   # nazo/stock.py と名前がぶつかるので場所で読む
    stock = importlib.util.module_from_spec(spec); spec.loader.exec_module(stock)
    c, k, work = stock.load(wid)
    ym = {t: yomi.base_fix(stock.words_fix(t, k), c["meta"], c["ruby"]) for t in stock.sentences(k, work)}
    return dict(work, kousei=k, yomi=ym)


def main():
    published = load(f"{S}/published.json", [])
    failures = load(f"{S}/failures.json", [])
    queue = load(f"{S}/queue.json", [])
    today = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).date().isoformat()   # 日本時間の日付
    rerender = os.environ.get("WORK_ID", "").strip()
    if rerender:
        # 指定した回だけ作り直す（投稿しない・在庫と公開記録は変えない）
        work = rerender_entry(rerender)
        print(f"作り直し: 第{work['no']}話 {work['title']}（{rerender}）")
    else:
        if published and published[-1].get("date") == today and not os.environ.get("FORCE"):
            # 定時の起動はGitHub側で数時間遅れることがある。手動で先に作った日は、遅れて来た定時分で2本目を作らない
            print("今日の分はもう作ってある。何もしない"); return
        if not queue:
            print("在庫切れ: チャットで「怪談の在庫補充」を。今回は何もしない"); return
        work = queue.pop(0)
    try:
        src = load(f"{S}/texts/{work['work_id']}.json", None)
        k = work["kousei"]
        ok, errs = check.validate(k, src)
        if not ok:
            raise RuntimeError("検査に不合格: " + " / ".join(errs[:5]))
        # 画像：台本で場面ごとに指定したもの（PD/CC0/CC BY系だけ）
        images, credits = {}, []
        wanted = [im["file"] for s in k["sections"] for im in s.get("images", [])]
        wanted += [h["file"] for h in k.get("hook", []) if h.get("file")]
        wanted += [f for f in (k.get("title_image"), k.get("thumb_image")) if f]
        os.makedirs("build", exist_ok=True)
        local, got = {}, {}
        if wanted:
            got = m4_images.commons_files(wanted)
            for j, (f, info) in enumerate(got.items()):
                if m4_images.download(info["url"], f"build/sel{j}.jpg", fallback=info.get("orig")):
                    local[f] = f"build/sel{j}.jpg"
        print(f"指定画像 {len(local)}/{len(set(wanted))} 枚")
        if wanted and len(local) < max(3, len(set(wanted)) // 2):
            raise RuntimeError("画像がほとんど取れなかった（真っ黒な動画を出さないため中止）")
        images["sec_list"] = {}
        used = set()
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
        credits = sorted({got[f]["credit"] for f in used})

        # 共通の部品を怪談用に切り替えてから作る
        brand.install_motion()
        k = dict(k, host_intro=brand.host_intro(work, k))
        br = brand.kaidan_brand(work, k)
        os.makedirs("output", exist_ok=True)
        out = f"output/kaidan_{work['work_id']}.mp4"
        render_work = dict(work, yomi=work["yomi"])
        render.build_video(k, render_work, src["text"], src["ruby"], images, out, llm=_no_llm, brand=br)
        import thumb_mid         # ほどよいインパクトの型（絵を大きく＋話の中の一言＋朱の札。煽り文句なし）
        thumb_mid.build(k.get("display_title", work["title"]), brand.kansuji(work["no"]), work["author"],
                        images.get("thumb_image") or images.get("title_image"), "output/thumb.png",
                        copy=k.get("thumb_copy", ""), focus=tuple(k.get("thumb_focus", (0.6, 0.4))))

        chapters = json.load(open("build/chapters.json", encoding="utf-8"))
        desc = description(k, work, credits, chapters)
        tags = list(dict.fromkeys(k["tags"] + brand.VOICE_TAGS))
        assert_terms(desc, tags)
        kit = f"kaidan/manual/{work['work_id']}"; os.makedirs(kit, exist_ok=True)
        txt = ("【タイトル】\n" + k["title_candidates"][0] + "\n\n【説明】\n" + desc +
               "\n\n【タグ】\n" + ",".join(tags) + "\n")
        open(f"{kit}/upload.txt", "w", encoding="utf-8").write(txt)
        open("output/upload.txt", "w", encoding="utf-8").write(txt)
        shutil.copy("output/thumb.png", f"{kit}/thumb.png")
        # 確認用：冒頭1分は2秒ごと、全体は20秒ごとのコマ一覧（チャットから中身を確かめるため）
        import subprocess
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", "fps=1/20,scale=480:-1,tile=5x9",
                        "-frames:v", "1", f"{kit}/sheet.jpg"])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-t", "60", "-i", out, "-vf", "fps=1/2,scale=480:-1,tile=5x6",
                        "-frames:v", "1", f"{kit}/sheet_open.jpg"])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-45", "-i", out, "-vf", "fps=1,scale=480:-1,tile=9x5",
                        "-frames:v", "1", f"{kit}/sheet_end.jpg"])   # 終わり45秒は1秒ごと（暗転と語り部の確認用）
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                             capture_output=True, text=True).stdout.strip()
        open(f"{kit}/duration.txt", "w").write(dur + "\n")
        # 確認用：全体を10秒ごと（左上に時刻）。1枚20コマ＝200秒ぶん
        for old in os.listdir(kit):
            if old.startswith("sheet10_"):
                os.remove(f"{kit}/{old}")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf",
                        "fps=1/10,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                        "text='%{pts\\:hms}':x=12:y=12:fontsize=44:fontcolor=yellow:box=1:boxcolor=black,"
                        "scale=480:-1,tile=4x5", f"{kit}/sheet10_%02d.jpg"])
        if rerender:
            print(f"完了（作り直し・投稿なし）: 第{work['no']}話 {work['title']} {dur}秒 → {out}")
            return
        import kaidan_upload as yt_upload   # YT_REFRESH_TOKEN が空（投稿なしモード）なら None が返る
        vid = yt_upload.upload(out, "output/thumb.png", k["title_candidates"][0], desc, tags, k.get("en"))
        if vid:
            print(f"投稿しました: https://youtu.be/{vid}")
        published.append({"work_id": work["work_id"], "no": work["no"], "title": work["title"], "video_id": vid,
                          "date": today, "credits": credits})
        save(f"{S}/published.json", published)
        save(f"{S}/queue.json", queue)
        print(f"完了: 第{work['no']}話 {work['title']} → 手動投稿用 {kit}")
    except Exception as e:
        print(f"::error::{type(e).__name__}: {str(e)[:300]}")   # ログが読めないとき用（check-runs の annotations に出る）
        if rerender:
            traceback.print_exc(); sys.exit(1)
        failures.append({"work_id": work.get("work_id"), "title": work.get("title"),
                         "date": datetime.date.today().isoformat(), "error": str(e)})
        save(f"{S}/failures.json", failures)
        save(f"{S}/queue.json", queue)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
