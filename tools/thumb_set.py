"""thumb_set.py — 投稿済みの動画のサムネだけを差し替える（thumbnails.set だけ。API審査で申告した範囲）。
使い方: VIDEO_ID=<id> python tools/thumb_set.py <thumb.png>"""
import os, sys
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], client_id=os.environ["YT_CLIENT_ID"],
                    client_secret=os.environ["YT_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token")
yt = build("youtube", "v3", credentials=creds)
for pair in os.environ["PAIRS"].split():
    vid, path = pair.split("=", 1)
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(path)).execute()
    print("thumb set", vid, path)
