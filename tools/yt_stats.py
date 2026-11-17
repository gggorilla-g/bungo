# yt_stats.py — 自分のチャンネルの動画の数字を集めて state/ に残す（読み取りだけ。投稿・編集はしない）
#   環境変数: YT_CLIENT_ID / YT_CLIENT_SECRET / TOKEN_MOSO / TOKEN_MIW
#   出力: state/stats_<ch>.json（最新）と state/stats_history.csv（時刻ごとの再生数の記録）
import csv, datetime, json, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def creds(tok):
    return Credentials(None, refresh_token=tok, client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                       token_uri="https://oauth2.googleapis.com/token")


def one(ch, tok):
    c = creds(tok); yt = build("youtube", "v3", credentials=c, cache_discovery=False)
    me = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    up = me["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = [i["contentDetails"]["videoId"] for i in yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=50).execute().get("items", [])]
    vids = yt.videos().list(part="snippet,statistics,status,contentDetails", id=",".join(ids)).execute().get("items", []) if ids else []
    rows = []
    for v in vids:
        st = v.get("statistics", {}); s = v["snippet"]
        rows.append({"id": v["id"], "title": s["title"], "published": s.get("publishedAt"), "privacy": v["status"]["privacyStatus"],
                     "publishAt": v["status"].get("publishAt"), "duration": v["contentDetails"]["duration"],
                     "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)), "comments": int(st.get("commentCount", 0))})
    # 視聴の深さ（Analytics。権限が無ければ飛ばす）
    an = {}
    try:
        ya = build("youtubeAnalytics", "v2", credentials=c, cache_discovery=False)
        r = ya.reports().query(ids="channel==MINE", startDate="2026-10-01", endDate=NOW.date().isoformat(),
                               metrics="views,averageViewPercentage,averageViewDuration,subscribersGained,likes",
                               dimensions="video", sort="-views", maxResults=200).execute()
        hd = [h["name"] for h in r["columnHeaders"]]
        for row in r.get("rows", []):
            d = dict(zip(hd, row)); an[d["video"]] = d
    except Exception as e:
        an = {"_error": str(e)[:300]}
    for x in rows:
        if x["id"] in an: x["analytics"] = an[x["id"]]
    out = {"at": NOW.isoformat(), "channel": me["snippet"]["title"], "subs": int(me["statistics"].get("subscriberCount", 0)),
           "channel_views": int(me["statistics"].get("viewCount", 0)), "analytics_error": an.get("_error"), "videos": rows}
    json.dump(out, open(f"state/stats_{ch}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    new = not os.path.exists("state/stats_history.csv")
    with open("state/stats_history.csv", "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(["at", "channel", "id", "views", "likes", "comments", "avg_view_pct", "subs_gained"])
        for x in rows:
            if x["privacy"] != "public": continue
            a = x.get("analytics", {})
            w.writerow([NOW.isoformat(), ch, x["id"], x["views"], x["likes"], x["comments"], a.get("averageViewPercentage", ""), a.get("subscribersGained", "")])
    print(ch, out["channel"], "登録者", out["subs"], "動画", len(rows), "Analytics", "OK" if not out["analytics_error"] else "NG: " + out["analytics_error"][:120])


if __name__ == "__main__":
    os.makedirs("state", exist_ok=True)
    for ch, env in [("moso", "TOKEN_MOSO"), ("miw", "TOKEN_MIW")]:
        if os.environ.get(env):
            try: one(ch, os.environ[env])
            except Exception as e: print(ch, "失敗", str(e)[:300])
