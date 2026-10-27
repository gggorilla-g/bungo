# yt_playlist.py — 雑学チャンネル（旧BUNGO）の再生リストを作り、雑学ショートを古い順に入れる
# 何度動かしても同じ再生リストに足すだけ（同じ名前があれば作らない。入っている動画は足さない）
import os, sys
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TITLE = os.environ.get("PL_TITLE", "脳がとける雑学 ショート")
DESC = os.environ.get("PL_DESC", "")
MATCH = os.environ.get("PL_MATCH", "#雑学")          # タイトルにこの文字がある動画を入れる
PRIVACY = os.environ.get("PL_PRIVACY", "public")

creds = Credentials(None, refresh_token=os.environ["TOKEN"], client_id=os.environ["YT_CLIENT_ID"],
                    client_secret=os.environ["YT_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token")
yt = build("youtube", "v3", credentials=creds)

ch = yt.channels().list(part="snippet,contentDetails", mine=True).execute()["items"][0]
print("チャンネル:", ch["snippet"]["title"])
uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]

# 投稿した動画（新しい順で返るので、あとで古い順に並べる）
vids, tok = [], None
while True:
    r = yt.playlistItems().list(part="snippet,status", playlistId=uploads, maxResults=50, pageToken=tok).execute()
    for it in r["items"]:
        sn = it["snippet"]
        vids.append((sn["publishedAt"], sn["resourceId"]["videoId"], sn["title"], it.get("status", {}).get("privacyStatus")))
    tok = r.get("nextPageToken")
    if not tok:
        break
vids.sort()
targets = [v for v in vids if MATCH in v[2] and v[3] == "public"]
print(f"対象の動画 {len(targets)} 本（全{len(vids)}本中、公開中でタイトルに「{MATCH}」）")

# 再生リスト（同じ名前があれば使う）
pl = None
r = yt.playlists().list(part="snippet,status", mine=True, maxResults=50).execute()
for p in r.get("items", []):
    if p["snippet"]["title"] == TITLE:
        pl = p["id"]
if pl:
    print("既存の再生リストを使う:", pl)
else:
    pl = yt.playlists().insert(part="snippet,status", body={
        "snippet": {"title": TITLE, "description": DESC, "defaultLanguage": "ja"},
        "status": {"privacyStatus": PRIVACY}}).execute()["id"]
    print("再生リストを作った:", pl)

import time
from googleapiclient.errors import HttpError
have, tok = set(), None
while True:
    try:
        r = yt.playlistItems().list(part="snippet", playlistId=pl, maxResults=50, pageToken=tok).execute()
    except HttpError as e:                       # 作ったばかり・空の再生リストは見つからないと返ることがある
        if e.resp.status == 404:
            break
        raise
    have |= {it["snippet"]["resourceId"]["videoId"] for it in r["items"]}
    tok = r.get("nextPageToken")
    if not tok:
        break
for _, vid, title, _ in targets:
    if vid in have:
        continue
    for k in range(5):                           # 作った直後は反映待ちで失敗することがあるので、待って試し直す
        try:
            yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pl, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
            break
        except HttpError as e:
            if e.resp.status != 404 or k == 4:
                raise
            time.sleep(5)
    print("追加:", title)
st = yt.playlists().list(part="status,contentDetails", id=pl).execute()["items"][0]
print("公開設定:", st["status"]["privacyStatus"], "／本数:", st["contentDetails"]["itemCount"])
print("URL: https://www.youtube.com/playlist?list=" + pl)
