# nazo/trivia_long/names10_kit.py — 長尺「名前がひどすぎる生き物10選」の投稿キット（【タイトル】【説明】【タグ】）
#   使い方: python nazo/trivia_long/names10_kit.py output/trivia_long_names10_chapters.txt
import json, os, sys

J = "nazo/trivia_long/names10.json"
OUT = "nazo/manual/trivia_names10/trivia_long_names10_upload.txt"
data = json.load(open(J, encoding="utf-8"))
chap = open(sys.argv[1], encoding="utf-8").read().strip()

used = []
for s in data["sections"]:
    for l in s["lines"]:
        if l.get("img") and l["img"] not in used:
            used.append(l["img"])
cred = []
for p in used:
    folder, key = os.path.dirname(p), os.path.basename(p)[:-4]
    c = json.load(open(os.path.join(folder, "credits.json"), encoding="utf-8"))
    v = c[key]                                           # 「作者 / ライセンス / Wikimedia Commons（File:名前）」を、作者ごとにまとめて短く
    who, lic = v.split(" / ")[0], v.split(" / ")[1]
    who = " ".join(who.replace("&amp;", "&").split())
    if "made by" in who:
        who = who.split("made by", 1)[1].split()[0]
    who = who[:40]
    fn = v.split("（File:")[-1].rstrip("）")
    cred.append(((who, lic), fn))
grp = {}
for k, fn in cred:
    grp.setdefault(k, []).append(fn)
def short(fn, n=16):                                     # 説明欄は API で 5000 バイトまで。ファイル名は頭だけ残す
    stem = fn.rsplit(".", 1)[0]
    return stem if len(stem) <= n else stem[:n] + "…"
cred = [f"{who}({lic.replace('CC BY-SA ', 'BY-SA').replace('CC BY ', 'BY').replace('Public domain', 'PD')}): " + "/".join(short(f) for f in fns)
        for (who, lic), fns in grp.items()]

SRC = """■ 出典（事実の確認に使ったもの）
・ナマケモノ：Wikipedia日本語版「ナマケモノ」、英語版「Sloth」
・ヘッピリムシ（ミイデラゴミムシ）：Wikipedia日本語版「ミイデラゴミムシ」（100℃以上のガス・名前の由来）／Sugiura & Sato (2018) Biology Letters "Successful escape of bombardier beetles from predator digestive systems"
・ウスバカゲロウ：Wikipedia日本語版「ウスバカゲロウ」
・ハリセンボン：Wikipedia日本語版「ハリセンボン」
・カエルアンコウ：Wikipedia日本語版「カエルアンコウ」／日本魚類学会（2007年の標準和名の改名）
・ツチブタ：Wikipedia日本語版「ツチブタ」
・ウソ：サントリー「日本の鳥百科 ウソ」、キヤノン「バードブランチ ウソ」／Wikipedia日本語版「鷽替え」
・アフリカハゲコウ：Wikipedia日本語版「アフリカハゲコウ」
・ボケ：Wikipedia日本語版「ボケ (植物)」
・ヒモムシ：Wikipedia日本語版「ヒモムシ」、英語版「Lineus longissimus」
※ 名前の由来には諸説あるものがあります。"""

desc = f"""名前はひどいけど、中身はすごい生き物10種なのだ。

{chap}

{SRC}

■ 写真 Wikimedia Commons 作者(ライセンス): ファイル名（BY=CC BY、BY-SA=CC BY-SA、PD=パブリックドメイン）
""" + "\n".join(cred) + """

■ 音声・立ち絵・音楽
音声: VOICEVOX:ずんだもん
立ち絵: 坂本アヒル
BGM・効果音: オリジナル

#ずんだもん #雑学 #生き物"""

tags = ["ずんだもん", "雑学", "生き物", "名前がひどい", "ナマケモノ", "ハリセンボン", "ウスバカゲロウ", "カエルアンコウ", "ツチブタ",
        "脳がとける雑学", "動物", "VOICEVOX"]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(f"【タイトル】\n{data['meta']['title']}\n\n【説明】\n{desc}\n\n【タグ】\n{','.join(tags)}\n")
print(OUT, len(desc), "文字")
