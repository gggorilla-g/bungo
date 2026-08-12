# M1: 作品選定 — 青空文庫カタログから未投稿作品を選ぶ
import csv, io, json, zipfile, requests

UA = {"User-Agent": "BUNGO/0.1 (automated literature channel)"}
CATALOG = "https://raw.githubusercontent.com/aozorabunko/aozorabunko/master/index_pages/list_person_all_extended_utf8.zip"

# 知名度の重み: 教科書定番・検索需要の太い作家を優先(初期運転用の静的リスト)
PRIORITY_AUTHORS = ["太宰治", "芥川龍之介", "夏目漱石", "宮沢賢治", "中島敦",
                    "梶井基次郎", "森鷗外", "樋口一葉", "泉鏡花", "坂口安吾",
                    "小林多喜二", "夢野久作", "江戸川乱歩", "新美南吉", "有島武郎"]

def load_catalog():
    z = zipfile.ZipFile(io.BytesIO(requests.get(CATALOG, headers=UA, timeout=60).content))
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8-sig")))
    return rows

def select_next(published_ids):
    rows = load_catalog()
    cands = []
    for r in rows:
        if r["作品著作権フラグ"] != "なし":         # 著作権存続作品は構造的に除外
            continue
        if "新字新仮名" not in r["文字遣い種別"]:    # 可読性・TTS精度のため
            continue
        if r["作品ID"] in published_ids:
            continue
        author = r["姓"] + r["名"]
        if author not in PRIORITY_AUTHORS:
            continue
        url = r.get("XHTML/HTMLファイルURL", "")
        if not url:
            continue
        title = r["作品名"]
        score = (len(PRIORITY_AUTHORS) - PRIORITY_AUTHORS.index(author)) * 10
        # 誰もが名前を知る定番作を大幅加点(初期はこれらを優先的に消化)
        FAMOUS = ["走れメロス","人間失格","斜陽","羅生門","蜘蛛の糸","杜子春","地獄変",
                  "こころ","坊っちゃん","吾輩は猫である","銀河鉄道の夜","注文の多い料理店",
                  "セロ弾きのゴーシュ","山月記","檸檬","舞姫","高瀬舟","たけくらべ",
                  "ごん狐","手袋を買いに","走れメロス","桜の樹の下には"]
        if any(f in title for f in FAMOUS):
            score += 1000
        cands.append({"work_id": r["作品ID"], "title": title, "author": author,
                      "birth": r.get("生年月日", ""), "death": r.get("没年月日", ""),
                      "pub": r.get("初出", ""), "url": url, "score": score})
    if not cands:
        return None
    # 同点内は作品IDの小さい順(≒登録が古い≒定番作)
    cands.sort(key=lambda c: (-c["score"], int(c["work_id"])))
    return cands[0]

if __name__ == "__main__":
    pub = {p["work_id"] for p in json.load(open("state/published.json"))}
    print(select_next(pub))
