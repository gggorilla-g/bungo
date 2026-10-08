"""YouTubeへ投稿。BUNGO(src/m8_upload.py)と同じ公開ルール：
PUBLISH_MODE=private（既定）… 非公開で上げる（APIプロジェクト監査前は非公開ロックの仕様）
PUBLISH_MODE=scheduled  … 次の JST 20:00 に予約公開（監査通過後に切替で完全無人化）"""
import datetime, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def _next_publish(hour_utc=11):   # 11:00 UTC = JST 20:00
    now = datetime.datetime.now(datetime.timezone.utc)
    t = now.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    if t <= now + datetime.timedelta(minutes=15):
        t += datetime.timedelta(days=1)
    return t.isoformat()

def upload(path, meta):
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=creds)
    status = {"selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": True,   # 元絵はAI生成。BUNGOと同じく正直に立てる
              "privacyStatus": "private"}
    if os.environ.get("PUBLISH_MODE", "private") == "scheduled":
        status["publishAt"] = _next_publish()
    body = {"snippet": {"title": meta["title"][:100], "description": meta["description"],
                        "tags": meta["tags"], "categoryId": "24",   # 24=エンタメ
                        "defaultLanguage": "ja"},
            "status": status}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(path, mimetype="video/mp4", resumable=True))
    res = None
    while res is None:
        _, res = req.next_chunk()
    return res["id"]
