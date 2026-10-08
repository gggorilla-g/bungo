# nazo/upload.py — NAZOチャンネルへの投稿。認証・予約公開の仕組みはBUNGO(src/m8_upload.py)と同じ。
# 違い: 概要欄にWikipediaの出典(CC BY-SA)を記載／再生リストは「シリーズ」単位。
import os, datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import m8_upload

PUBLISH_MODE = os.environ.get("PUBLISH_MODE") or "private"  # private | scheduled


def make_description(kousei, meta, image_credits, chapters=None):
    lines = [kousei["description"], ""]
    if chapters:
        lines += [f"{'0:00' if i == 0 else m8_upload._ts(t)} {n}"
                  for i, (n, t) in enumerate(chapters)] + [""]
    lines += ["#未解決の謎 #歴史ミステリー #古代史", "", "──",
              "この動画の事実（年代・数字・名称）はWikipediaの記述のみを根拠にしています。",
              "仮説は「説」として紹介しており、どれも定説ではありません。", "",
              f"参考: Wikipedia「{meta['title']}」 {meta['url_ja']} （CC BY-SA 4.0）"]
    if meta.get("url_en"):
        lines.append(f"参考: Wikipedia \"{meta['en_title']}\" {meta['url_en']} (CC BY-SA 4.0)")
    lines.append("音声: VOICEVOX:ずんだもん（合成音声）")
    for c in image_credits:
        lines.append(f"画像: {c}")
    return "\n".join(lines)


def add_to_series(yt, video_id, series):
    pl_id = None
    res = yt.playlists().list(part="snippet", mine=True, maxResults=50).execute()
    for p in res.get("items", []):
        if p["snippet"]["title"] == series:
            pl_id = p["id"]; break
    if not pl_id:
        pl_id = yt.playlists().insert(part="snippet,status", body={
            "snippet": {"title": series, "description": f"{series}の未解決の謎"},
            "status": {"privacyStatus": "public"}}).execute()["id"]
    yt.playlistItems().insert(part="snippet", body={"snippet": {
        "playlistId": pl_id,
        "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()


def upload(video_path, thumb_path, kousei, meta, image_credits, chapters=None):
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        client_id=os.environ["YT_CLIENT_ID"],
                        client_secret=os.environ["YT_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=creds)
    status = {"selfDeclaredMadeForKids": False, "containsSyntheticMedia": True,
              "privacyStatus": "private"}
    if PUBLISH_MODE == "scheduled":
        status["publishAt"] = datetime.datetime.now(datetime.timezone.utc).replace(
            hour=12, minute=0, second=0, microsecond=0).isoformat()  # JST 21:00
    body = {"snippet": {"title": kousei["title_candidates"][0],
                        "description": make_description(kousei, meta, image_credits, chapters),
                        "tags": kousei["tags"], "categoryId": "27",
                        "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
            "status": status}
    en = kousei.get("en")
    if en:
        body["localizations"] = {"en": {"title": en["title"][:100], "description": en["description"]}}
    req = yt.videos().insert(part="snippet,status,localizations", body=body,
        media_body=MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True))
    res = None
    while res is None:
        _, res = req.next_chunk()
    vid = res["id"]
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb_path)).execute()
    if kousei.get("series"):
        try:
            add_to_series(yt, vid, kousei["series"])
        except Exception as e:
            print("再生リスト追加失敗(投稿自体は成功):", e)
    return vid
