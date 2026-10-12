# yt_check.py — 登録した鍵で、どのYouTubeチャンネルにつながるかだけ確認する（投稿はしない）
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

for k in ["YT_CLIENT_ID","YT_CLIENT_SECRET","TOKEN_BUNGO","TOKEN_NAZO"]:
    print(k, "あり" if os.environ.get(k) else "なし")
for label, env in [("BUNGO", "TOKEN_BUNGO"), ("NAZO", "TOKEN_NAZO")]:
    tok = os.environ.get(env)
    if not tok:
        print(f"{label}: 鍵が未登録"); continue
    try:
        creds = Credentials(None, refresh_token=tok, client_id=os.environ["YT_CLIENT_ID"],
                            client_secret=os.environ["YT_CLIENT_SECRET"],
                            token_uri="https://oauth2.googleapis.com/token")
        yt = build("youtube", "v3", credentials=creds)
        items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
        print(f"{label}: OK → " + ", ".join(i["snippet"]["title"] for i in items))
    except Exception as e:
        print(f"{label}: 失敗 → {str(e)[:200]}")
