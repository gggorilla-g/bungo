# m8_upload.py — YouTube投稿とクレジット自動整形
# 注意: APIプロジェクトが監査未通過の間、アップロード動画は非公開ロックされる(仕様)。
#       その間は privacyStatus="private" で上げ、スマホから手動公開(Phase 2運用)。
#       監査通過後に PUBLISH_MODE="scheduled" へ切り替えると完全無人化。
import os, json, datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

PUBLISH_MODE = os.environ.get("PUBLISH_MODE", "private")  # private | scheduled

def _ts(sec):
    h, m, s2 = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s2:02d}" if h else f"{m}:{s2:02d}"

def make_description(kousei, image_credits, chapters=None):
    lines = [kousei["description"], ""]
    if chapters:
        chapters = [["0:00" if i == 0 else _ts(t), n] for i, (n, t) in enumerate(chapters)]
        lines += [f"{t} {n}" for t, n in chapters] + [""]
    lines += ["#青空文庫 #朗読 #睡眠導入", "", "──", "音声: VOICEVOX:ずんだもん"]
    for c in image_credits:
        lines.append(f"画像: {c}")
    lines.append("底本: 青空文庫 https://www.aozora.gr.jp/")
    return "\n".join(lines)

def add_to_author_playlist(yt, video_id, author):
    """作者名の再生リストを探し、なければ作って追加(連続再生の導線)"""
    pl_id = None
    res = yt.playlists().list(part="snippet", mine=True, maxResults=50).execute()
    for p in res.get("items", []):
        if p["snippet"]["title"] == author:
            pl_id = p["id"]; break
    if not pl_id:
        pl_id = yt.playlists().insert(part="snippet,status", body={
            "snippet": {"title": author, "description": f"{author}の名作要約と全文朗読"},
            "status": {"privacyStatus": "public"}}).execute()["id"]
    yt.playlistItems().insert(part="snippet", body={"snippet": {
        "playlistId": pl_id,
        "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()

def upload(video_path, thumb_path, kousei, image_credits, chapters=None, author=None):
    creds = Credentials(None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=creds)

    status = {"selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": True}   # AI生成コンテンツの開示(正直に立てる)
    if PUBLISH_MODE == "scheduled":
        publish_at = datetime.datetime.now(datetime.timezone.utc).replace(
            hour=10, minute=0, second=0).isoformat()  # JST 19:00
        status.update({"privacyStatus": "private", "publishAt": publish_at})
    else:
        status["privacyStatus"] = "private"

    body = {"snippet": {"title": kousei["title_candidates"][0],
                        "description": make_description(kousei, image_credits, chapters),
                        "tags": kousei["tags"], "categoryId": "27",  # 27=教育
                        "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
            "status": status}
    en = kousei.get("en")
    if en:  # 英語圏の検索結果に英題・英語概要を露出させる(音声は日本語のまま)
        body["localizations"] = {"en": {"title": en["title"][:100],
                                        "description": en["description"]}}
    req = yt.videos().insert(part="snippet,status,localizations", body=body,
        media_body=MediaFileUpload(video_path, chunksize=8*1024*1024, resumable=True))
    res = None
    while res is None:
        _, res = req.next_chunk()
    vid = res["id"]
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb_path)).execute()
    if author:
        try:
            add_to_author_playlist(yt, vid, author)
        except Exception as e:
            print("playlist追加失敗(投稿自体は成功):", e)
    return vid
