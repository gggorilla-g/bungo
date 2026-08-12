# get_token.py — 初期セットアップ時に1回だけローカルMacで実行し、refresh tokenを取得する
# 使い方: pip install google-auth-oauthlib && python src/get_token.py client_secret.json
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_secrets_file(
    sys.argv[1], scopes=["https://www.googleapis.com/auth/youtube.upload",
                          "https://www.googleapis.com/auth/youtube"])
creds = flow.run_local_server(port=0)
print("\nYT_REFRESH_TOKEN =", creds.refresh_token)
