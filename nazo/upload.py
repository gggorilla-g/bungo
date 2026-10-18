# nazo/upload.py — NAZOチャンネルへの投稿。認証・予約公開の仕組みはBUNGO(src/m8_upload.py)と同じ。
# 違い: 概要欄にWikipediaの出典(CC BY-SA)を記載／再生リストは「シリーズ」単位。
import os, datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import m8_upload

PUBLISH_MODE = os.environ.get("PUBLISH_MODE") or "private"  # private | scheduled


def group_credits(credits):
    """同じ作者・同じライセンスの画像が3点以上なら1行にまとめる（概要欄が出典で埋まらないように）"""
    import re
    groups = {}
    for c in credits:
        c = re.sub(r"(.{3,}?)\1", r"\1", c)          # 「Unknown authorUnknown author」の重複を直す
        key = c.split("（File:")[0]
        groups.setdefault(key, []).append(c)
    out = []
    for key, items in groups.items():
        out += [f"{key}（{len(items)}点）"] if len(items) >= 3 else items
    return out


CREDITS_URL = "https://github.com/gggorilla-g/bungo/blob/main/nazo/manual/{id}/credits.md"


def _short_credit(c):
    """「作者 / ライセンス / Wikimedia Commons（File:…）」→「作者（ライセンス）」"""
    import re
    c = re.sub(r"(.{3,}?)\1", r"\1", c)
    parts = [p.strip() for p in c.split("（File:")[0].split("（")[0].split(" / ")]
    artist = parts[0] if parts else c
    lic = parts[1] if len(parts) > 1 else ""
    if "No machine-readable author" in artist:
        artist = "Marsyas"
    if artist.lower().startswith("unknown"):
        artist = "作者不詳"
    return f"{artist}（{lic}）" if lic else artist


def credits_md(title, image_credits):
    """画像の出典の全一覧（ファイル名つき）。概要欄からはここへリンクする"""
    return "\n".join([f"# {title} 画像の出典", "", "すべて Wikimedia Commons より。作者 / ライセンス / ファイル名", ""]
                     + [f"- {c}" for c in sorted(set(image_credits))]) + "\n"


def tags_for(kousei):
    """台本のタグに、声の規約で求められているタグ（例:「ちび式じい」）を必ず足す"""
    import brand
    t = list(kousei.get("tags", []))
    for x in getattr(brand, "VOICE_TAGS", []):
        if x not in t:
            t.append(x)
    return t


def assert_voice_terms(desc, tags):
    """声の規約の必須事項（クレジット・タグ）が欠けていたら止める。欠けたまま公開すると請求対象になるため"""
    import brand
    need = f"VOICEVOX:{brand.VOICE_NAME}"
    if need not in desc:
        raise RuntimeError(f"概要欄に「{need}」のクレジットがない")
    for t in getattr(brand, "VOICE_TAGS", []):
        if t not in tags:
            raise RuntimeError(f"タグ「{t}」がない")


def make_description(kousei, meta, image_credits, chapters=None, work_id=None):
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
    import brand
    lines.append(f"音声: VOICEVOX:{brand.VOICE_NAME}（合成音声）")
    lines.append("BGM: the ghost house / 稿屋 隆（DOVA-SYNDROME）、Calming seaside / 蒲鉾さちこ（DOVA-SYNDROME）")
    if work_id:
        # 概要欄の字数を抑えるため、作者とライセンスだけを並べ、ファイル名つきの全一覧はリンク先に置く
        names = list(dict.fromkeys(_short_credit(c) for c in image_credits))
        lines.append("画像: Wikimedia Commons より（" + "、".join(names) + "）")
        lines.append("画像の出典一覧（ファイル名つき）: " + CREDITS_URL.format(id=work_id))
    else:
        lines += [f"画像: {c}" for c in group_credits(image_credits)]
    return "\n".join(lines)


def upload(video_path, thumb_path, kousei, meta, image_credits, chapters=None, work_id=None):
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        client_id=os.environ["YT_CLIENT_ID"],
                        client_secret=os.environ["YT_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=creds)
    status = {"selfDeclaredMadeForKids": False, "containsSyntheticMedia": False,  # 申告対象外（合成音声は概要欄で開示）
             
              "privacyStatus": "private"}
    if PUBLISH_MODE == "scheduled":
        status["publishAt"] = datetime.datetime.now(datetime.timezone.utc).replace(
            hour=12, minute=0, second=0, microsecond=0).isoformat()  # JST 21:00
    body = {"snippet": {"title": kousei["title_candidates"][0],
                        "description": make_description(kousei, meta, image_credits, chapters, work_id),
                        "tags": tags_for(kousei), "categoryId": "27",
                        "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
            "status": status}
    assert_voice_terms(body["snippet"]["description"], body["snippet"]["tags"])
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
    return vid
