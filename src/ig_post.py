# ig_post.py — reel/reel.mp4 を Instagram にリール投稿する（Instagram Graph API / Facebookログイン方式）
#   必要なSecrets: IG_USER_ID（InstagramビジネスアカウントID）, IG_TOKEN（ページアクセストークン=無期限）
#   動画は rupload へ直接送る（公開URLのホスティング不要）。
#   使い方: python src/ig_post.py reel        ※ DRY_RUN=1 なら送信せず内容だけ表示
import json, os, sys, time, requests

VER = os.environ.get("GRAPH_VER", "v23.0")
G = f"https://graph.facebook.com/{VER}"

def _chk(r):
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} {r.text[:500]}")
    return r.json()

def post(mp4, caption, user_id, token):
    # 1) 再開可能アップロードの枠を作る
    c = _chk(requests.post(f"{G}/{user_id}/media", data={
        "media_type": "REELS", "upload_type": "resumable",
        "caption": caption, "share_to_feed": "true", "access_token": token}, timeout=60))
    cid, uri = c["id"], c["uri"]
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
    p = _chk(requests.post(f"{G}/{user_id}/media_publish", data={
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
    mid = post(f"{d}/reel.mp4", meta["caption"], os.environ["IG_USER_ID"], os.environ["IG_TOKEN"])
    log.append({"work_id": meta["work_id"], "title": meta["title"], "media_id": mid,
                "date": time.strftime("%Y-%m-%d")})
    json.dump(log, open(log_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("投稿完了:", meta["title"], mid)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "reel")
