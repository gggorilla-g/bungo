# kaidan/main.py — 怪談チャンネル「今晩の百物語」の制作本体（Actionsが実行）
# 在庫（このチャットで仕込んだ台本＋確定した読み）だけで動く。実行時にLLMは呼ばない。
# フェイルセーフは「出さない」：検査に落ちたら欠番にしてログだけ残す。
import json, os, sys, shutil, traceback, datetime
sys.path.insert(0, "src"); sys.path.insert(0, "nazo"); sys.path.insert(0, "kaidan")
import m4_images, render, thumb, check, brand

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
    src = f"{work['author']}『{work['title']}』" + (f"（{work['translator']}訳）" if work.get("translator") else "")
    lines = [k["description"], ""]
    if chapters:
        lines += [f"{render_ts(t) if i else '0:00'} {h}" for i, (h, t) in enumerate(chapters)] + [""]
    lines += ["※この動画は、権利の切れた古典の怪談を、いまの言葉で語り直した朗読です。実話ではありません。", "",
              "#怪談 #百物語 #朗読", "", "──",
              f"原作: {src}（青空文庫 {work.get('url', 'https://www.aozora.gr.jp/')}）",
              f"語り: VOICEVOX:{brand.VOICE_NAME}"]
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


def main():
    published = load(f"{S}/published.json", [])
    failures = load(f"{S}/failures.json", [])
    queue = load(f"{S}/queue.json", [])
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
        thumb.build(k["thumbnail"]["main_copy"], k["thumbnail"].get("sub_copy", work["title"]),
                    images.get("thumb_image") or images.get("title_image"), "output/thumb.png",
                    badge=f"{brand.CHANNEL}　第{brand.kansuji(work['no'])}話", palette=PALETTE_KAIDAN)

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
        published.append({"work_id": work["work_id"], "no": work["no"], "title": work["title"], "video_id": None,
                          "date": datetime.date.today().isoformat(), "credits": credits})
        save(f"{S}/published.json", published)
        save(f"{S}/queue.json", queue)
        print(f"完了: 第{work['no']}話 {work['title']} → 手動投稿用 {kit}")
    except Exception as e:
        failures.append({"work_id": work.get("work_id"), "title": work.get("title"),
                         "date": datetime.date.today().isoformat(), "error": str(e)})
        save(f"{S}/failures.json", failures)
        save(f"{S}/queue.json", queue)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
