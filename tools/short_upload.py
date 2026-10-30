"""short_upload.py — 作ったショートを、APIで予約公開として上げる（videos.insert だけ。API審査で申告した使い方の範囲）。

使い方: ID=<id> PUBLISH_AT=2026-10-30T11:00:00Z python tools/short_upload.py <動画.mp4> <upload.txt>
upload.txt は nazo/manual/<id>/short3_<id>_upload.txt（【タイトル】【説明】【タグ】）。
結果（動画IDと、APIが返した公開設定）を nazo/manual/<id>/api_upload.txt に書く。
"""
import os, re, sys, json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

video, kit = sys.argv[1], sys.argv[2]
t = open(kit, encoding="utf-8").read()
def sec(name):
    m = re.search(r"【" + name + r"】\n(.*?)(?=\n【|\Z)", t, re.S)
    return m.group(1).strip() if m else ""
title, desc, tags = sec("タイトル"), sec("説明"), [x.strip() for x in sec("タグ").split(",") if x.strip()]
assert title and desc, "タイトルか説明が空"
assert "VOICEVOX:" in desc, "声のクレジットがない"
publish_at = os.environ.get("PUBLISH_AT", "").strip()   # 空ならすぐ公開

creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], client_id=os.environ["YT_CLIENT_ID"],
                    client_secret=os.environ["YT_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token")
yt = build("youtube", "v3", credentials=creds)
body = {"snippet": {"title": title[:100], "description": desc, "tags": tags, "categoryId": "27",
                    "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
        "status": {"selfDeclaredMadeForKids": False, "containsSyntheticMedia": False}}
body["status"].update({"privacyStatus": "private", "publishAt": publish_at} if publish_at else {"privacyStatus": "public"})
req = yt.videos().insert(part="snippet,status", body=body,
                         media_body=MediaFileUpload(video, chunksize=8 * 1024 * 1024, resumable=True))
res = None
while res is None:
    _, res = req.next_chunk()
thumb = os.environ.get("THUMB", "").strip()
thumb_err = ""
if thumb:
    try:
        yt.thumbnails().set(videoId=res["id"], media_body=MediaFileUpload(thumb)).execute()
    except Exception as e:                       # サムネだけ失敗しても投稿は済んでいるので、記録して先へ進む
        thumb_err = str(e)[:300]
        print("::warning::サムネを設定できなかった:", thumb_err)
out = {"thumb": thumb, "thumb_error": thumb_err, "id": res["id"], "url": "https://youtube.com/shorts/" + res["id"], "requested_publishAt": publish_at,
       "returned_status": res.get("status", {})}
print(json.dumps(out, ensure_ascii=False, indent=1))
open(os.path.join(os.path.dirname(kit), "api_upload_" + os.path.basename(kit).replace("_upload.txt", "") + ".txt"), "w").write(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
