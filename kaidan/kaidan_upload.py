"""今晩の百物語の自動投稿（動画の投稿とサムネ設定だけ。権限は youtube.upload のみ）
YT_REFRESH_TOKEN が空なら何もしない（投稿なしモード）。"""
import os, datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def upload(video_path, thumb_path, title, desc, tags, en=None):
    if not os.environ.get("YT_REFRESH_TOKEN"):
        return None
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=creds)
    status = {"selfDeclaredMadeForKids": False, "containsSyntheticMedia": False,  # 合成音声は概要欄で開示
              "privacyStatus": "private"}
    if os.environ.get("PUBLISH_MODE") == "scheduled":
        status["publishAt"] = datetime.datetime.now(datetime.timezone.utc).replace(
            hour=12, minute=0, second=0, microsecond=0).isoformat()   # JST 21:00
    body = {"snippet": {"title": title, "description": desc, "tags": tags, "categoryId": "24",
                        "defaultLanguage": "ja", "defaultAudioLanguage": "ja"}, "status": status}
    parts = "snippet,status"
    if en:
        body["localizations"] = {"en": {"title": en["title"][:100], "description": en["description"]}}
        parts += ",localizations"
    req = yt.videos().insert(part=parts, body=body,
                             media_body=MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True))
    res = None
    while res is None:
        _, res = req.next_chunk()
    vid = res["id"]
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb_path)).execute()
    return vid
