# yt_playlists.py — チャンネルの公開動画を、題名の言葉のルールで複数の再生リストに振り分ける（オーナー 11/25「妄想は再生リスト作って」）
#   設定: PL_CONFIG の JSON  {"playlists": [{"title", "desc", "any": [題名にどれかがあれば入れる], "none": [どれかがあれば入れない],
#                                          "min_sec", "max_sec", "first": [先頭に置く動画ID], "order": "new"（新しい順）/ "old"}]}
#   DRY=1（既定）なら振り分けを表示するだけ。DRY=0 で作る。何度動かしても、同じ名前の再生リストに足りない動画を足すだけ
#   ※ 読むのは題名・公開状態・長さだけ（再生数などの数字は読まない）
import json, os, re, time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

cfg = json.load(open(os.environ["PL_CONFIG"], encoding="utf-8")); DRY = os.environ.get("DRY", "1") != "0"
creds = Credentials(None, refresh_token=os.environ["TOKEN"], client_id=os.environ["YT_CLIENT_ID"],
                    client_secret=os.environ["YT_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token")
yt = build("youtube", "v3", credentials=creds)
ch = yt.channels().list(part="snippet,contentDetails", mine=True).execute()["items"][0]
print("チャンネル:", ch["snippet"]["title"], "／ DRY" if DRY else "／ 本番")
uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
vids, tok = [], None
while True:
    r = yt.playlistItems().list(part="snippet,status", playlistId=uploads, maxResults=50, pageToken=tok).execute()
    for it in r["items"]:
        sn = it["snippet"]; vids.append({"at": sn["publishedAt"], "id": sn["resourceId"]["videoId"], "title": sn["title"], "privacy": it.get("status", {}).get("privacyStatus")})
    tok = r.get("nextPageToken")
    if not tok: break
def secs(iso):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or ""); return (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)) if m else 0
for i in range(0, len(vids), 50):
    r = yt.videos().list(part="contentDetails", id=",".join(v["id"] for v in vids[i:i + 50])).execute()
    dur = {it["id"]: secs(it["contentDetails"].get("duration")) for it in r["items"]}
    for v in vids[i:i + 50]: v["sec"] = dur.get(v["id"], 0)
pub = [v for v in vids if v["privacy"] == "public"]
print(f"公開中 {len(pub)} 本（全 {len(vids)} 本）")
def match(v, p):
    t = v["title"]
    if p.get("any") and not any(k in t for k in p["any"]): return False
    if any(k in t for k in p.get("none", [])): return False
    if v["sec"] < p.get("min_sec", 0) or v["sec"] > p.get("max_sec", 10 ** 9): return False
    return True
mine = {}
r = yt.playlists().list(part="snippet,status,contentDetails", mine=True, maxResults=50).execute()
for p in r.get("items", []): mine[p["snippet"]["title"]] = p["id"]
print("今ある再生リスト:", list(mine) or "なし")
used = set()
for p in cfg["playlists"]:
    mem = [v for v in pub if match(v, p)]; used |= {v["id"] for v in mem}
    first = [x for x in p.get("first", []) if any(v["id"] == x for v in mem)]
    rest = sorted([v for v in mem if v["id"] not in first], key=lambda v: v["at"], reverse=(p.get("order", "new") == "new"))
    order = [next(v for v in mem if v["id"] == x) for x in first] + rest
    print(f"\n== {p['title']}  {len(order)} 本")
    for v in order: print(f"   {v['id']} {v['sec']:>4}秒 {v['at'][:10]} {v['title'][:60]}")
    if DRY or len(order) < p.get("min_count", 1): continue
    pl = mine.get(p["title"])
    if not pl:
        pl = yt.playlists().insert(part="snippet,status", body={"snippet": {"title": p["title"], "description": p.get("desc", ""), "defaultLanguage": "ja"}, "status": {"privacyStatus": "public"}}).execute()["id"]
        print("   作った:", pl); time.sleep(3)
    have, tok = [], None
    while True:
        try: r = yt.playlistItems().list(part="snippet", playlistId=pl, maxResults=50, pageToken=tok).execute()
        except HttpError as e:
            if e.resp.status == 404: break
            raise
        have += [it["snippet"]["resourceId"]["videoId"] for it in r["items"]]; tok = r.get("nextPageToken")
        if not tok: break
    n = 0
    for v in order:
        if v["id"] in have: continue
        for k in range(5):
            try: yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pl, "resourceId": {"kind": "youtube#video", "videoId": v["id"]}}}).execute(); n += 1; break
            except HttpError as e:
                if e.resp.status != 404 or k == 4: raise
                time.sleep(5)
    print(f"   足した {n} 本（すでに {len(have)} 本） https://www.youtube.com/playlist?list={pl}")
rest = [v for v in pub if v["id"] not in used]
print(f"\n== どの再生リストにも入らない公開動画 {len(rest)} 本")
for v in rest: print(f"   {v['id']} {v['sec']:>4}秒 {v['at'][:10]} {v['title'][:60]}")
