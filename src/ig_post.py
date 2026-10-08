# ig_post.py — reel/reel.mp4 を Instagram にリール投稿する
#   方式: Instagram API with Instagram Login（Facebookページ連携は不要）
#   必要なSecret: IG_TOKEN（Metaのアプリ画面で発行する長期トークン）だけ。延長は ig_token.py が自動で行う。
#   動画は rupload へ直接送る（公開URLのホスティング不要）。
#   使い方: python src/ig_post.py reel        ※ DRY_RUN=1 なら送信せず内容だけ表示
import json, os, sys, time, requests

VER = os.environ.get("GRAPH_VER", "v23.0")
G = f"https://graph.instagram.com/{VER}"

def _chk(r):
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} {r.text[:500]}")
    return r.json()

def post(mp4, caption, token):
    # 1) 再開可能アップロードの枠を作る
    c = _chk(requests.post(f"{G}/me/media", data={
        "media_type": "REELS", "upload_type": "resumable",
        "caption": caption, "share_to_feed": "true", "access_token": token}, timeout=60))
    cid = c["id"]
    uri = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{VER}/{cid}"
    # 2) 動画本体を送る
    size = os.path.getsize(mp4)
    with open(mp4, "rb") as f:
        _chk(requests.post(uri, data=f, timeout=600, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)}))
    # 3) Instagram側の処理完了を待つ（最大10分）
    for _ in range(60):
        s = _chk(requests.get(f"{G}/{cid}", params={
            "fields": "status_code,status", "access_token": token}, timeout=60))
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"処理失敗: {s}")
        time.sleep(10)
    else:
        raise RuntimeError("処理待ちタイムアウト")
    # 4) 公開
    p = _chk(requests.post(f"{G}/me/media_publish", data={
        "creation_id": cid, "access_token": token}, timeout=60))
    return p["id"]

def main(d):
    meta = json.load(open(f"{d}/reel.json", encoding="utf-8"))
    log_p = "state/ig_posted.json"
    log = json.load(open(log_p, encoding="utf-8")) if os.path.exists(log_p) else []
    if meta["work_id"] in {x["work_id"] for x in log}:
        print("投稿済みのため何もしない:", meta["title"]); return
    if os.environ.get("DRY_RUN") == "1":
        print(meta["caption"]); return
    sys.path.insert(0, "src")
    import ig_token
    mid = post(f"{d}/reel.mp4", meta["caption"], ig_token.get())
    log.append({"work_id": meta["work_id"], "title": meta["title"], "media_id": mid,
                "date": time.strftime("%Y-%m-%d")})
    json.dump(log, open(log_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("投稿完了:", meta["title"], mid)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "reel")
