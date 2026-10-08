# prefetch.py — 在庫仕込み用に、次の作品の本文を先に取っておく（LLMは呼ばない・無料）
# 置き場所: state/texts/<作品ID>.json  {meta, text, ruby}
# Claudeのチャット側はこのファイルを読んで台本と読みを仕込み、state/queue.json に積む。
import json, os, sys
sys.path.insert(0, "src")
import m1_select, m2_extract

N = 12
D = "state/texts"

def load(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default

def main():
    os.makedirs(D, exist_ok=True)
    # video_idのない記録は過去の試験実行（未公開）なので、在庫の対象に戻す
    done = {p["work_id"] for p in load("state/published.json", []) if p.get("video_id")}
    queued = {q["work_id"] for q in load("state/queue.json", [])}
    fails = {}
    for f in load("state/failures.json", []):
        fails[f.get("work_id")] = fails.get(f.get("work_id"), 0) + 1
    have = {f[:-5] for f in os.listdir(D) if f.endswith(".json")}
    # 投稿済みの本文は不要なので掃除
    for w in have & done:
        os.remove(f"{D}/{w}.json")
    have -= done
    need = N - len(have - queued)
    if need <= 0:
        print("在庫用本文は足りている"); return
    skip = done | queued | have | {w for w, n in fails.items() if n >= 3}
    for meta in m1_select.select_candidates(skip, need):
        try:
            text, ruby = m2_extract.fetch_text(meta["url"])
        except Exception as e:
            print("本文取得失敗:", meta["title"], e); continue
        json.dump({"meta": meta, "text": text, "ruby": ruby},
                  open(f"{D}/{meta['work_id']}.json", "w", encoding="utf-8"),
                  ensure_ascii=False)
        print("取得:", meta["title"])

if __name__ == "__main__":
    main()
