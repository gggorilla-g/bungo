# 雑学ショート 11/11〜11/13 の3本（2026-11-09）。実験B（docs/experiments.md）：1行目からずんだもんの踊りを出さず、題材の写真を大きく出す
#   python nazo/shorts/make_trivia_1111.py で nazo/shorts/trivia_<id>.json を書き出す
import json, os

BASE = {
    "voice": {"vvm": "0.vvm", "style": 3, "speed": 1.0, "pitch": 0.0, "intonation": 1.15},
    "voice_name": "ずんだもん",
    "bgm_file": "assets/enc/bgm_trivia_mood2.mp3",
    "bgm_credit": "ムード２ / 今川彰人オーケストラ（OpenTracks（旧DOVA-SYNDROME））",
    "bgm_vol": 0.16,
    "main": "trivia_daily",
}
Y, R, W = [255, 226, 0], [230, 40, 40], [255, 255, 255]


def st(text, at=0.4, y=0.35, size=200, color=Y):
    return {"type": "stamp", "text": text, "at": at, "y": y, "size": size, "color": color}


def cnt(to, unit, label, at=0.3):
    return {"type": "count", "to": to, "unit": unit, "label": label, "at": at}


def L(say, text, face="通常", wiki=None, i=0, fx=None, **kw):
    d = {"say": say, "text": text, "face": face}
    if wiki in FILES:                    # 記事の写真が合わない題材は、写真を直接指定（11/3 コマ割りで確認：ヤツメウナギ＝マンホール、ヨダレカケ・ニセクロスジギンポ＝写真なし）
        d["file"] = FILES[wiki][i % len(FILES[wiki])]
    elif wiki:
        d["wiki"] = ["ja", wiki]; d["wiki_i"] = i
    if fx:
        d["fx"] = fx
    d.update(kw)
    return d


FILES = {
    "カブトガニ": ["File:Limule(dD).jpg", "File:Tachypleus tridentatus (YPM IZ 002430.CR) 001.jpeg", "File:Limule(dD)Ventral.jpg"],
    "ハダカカメガイ": ["File:Campagne IBTS 2010 - Mollusque ange de mer (Clione limacina) (Ifremer 00569-68118).jpg", "File:Clione limacina5.jpg", "File:Sea angel.jpg"],
    "タツノオトシゴ": ["File:Boston Aquarium, Central Wharf, Boston (493608) (11062160045).jpg", "File:Cavalo Marinho2.jpg", "File:Ecomare - zeepaardje (zeepaardje-sw).jpg"],
}
S = {}

S["kabutogani"] = dict(label="名前がウソすぎる生き物", format="vs", themes=["orange_rays", "deep_sea", "checker"],
    title="カブトガニは、カニじゃなくてクモの仲間なのだ。名前がウソすぎる生き物 #Shorts #雑学 #海の生き物",
    tags=["ずんだもん", "雑学", "海の生き物", "名前がひどい", "カブトガニ", "生きている化石", "天然記念物", "脳がとける雑学", "ショート"],
    desc="名前はカニなのに、カニじゃないのだ。\n\n・カブトガニは節足動物だが、カニではなくクモの仲間。約2億年前に今の形になり、ほとんど変わらずに生き残ってきた。日本やアジアのカブトガニは最大で70cmほど（サカナト「カブトガニの生態や秘密に迫る」笠岡市立カブトガニ博物館の取材）https://sakanato.jp/7892/\n・およそ2億年前から形がほとんど変わらず「生きている化石」と呼ばれる。恐竜よりずっと前から生きていた。笠岡市神島水道の「カブトガニ繁殖地」は1971年に国の天然記念物に指定（岡山県「岡山県の文化財」）https://www.pref.okayama.jp/uploaded/attachment/260903.pdf\n・血液が青いのは、酸素を運ぶヘモシアニンという銅をふくむたんぱく質による（Chem-Station「カブトガニの血液が人類を救う」）https://www.chem-station.com/blog/2016/04/Tachypleustridentatus.html",
    lines=[
        L("カブトガニは、カニじゃなくてクモの仲間なのだ。", "カブトガニは\nカニじゃなくクモの仲間", "ドヤ", "カブトガニ", 0, [st("クモ", 0.0, 0.35, 260, R)], hook=True),
        L("姿は、約2億年前からほとんど変わっていないのだ。", "姿は約2億年前から\nほぼそのまま", "驚き", "カブトガニ", 1, [cnt(2, "億年", "姿がほぼ同じ")]),
        L("恐竜より前から、海にいたのだ。", "恐竜より前から\n海にいた", "驚き", "カブトガニ", 1),
        L("しかも、血が青いのだ。", "しかも\n血が青い", "青ざめ", "カブトガニ", 2, [st("青", 0.3, 0.35, 260, [60, 140, 255])]),
        L("血の中の銅が、酸素を運んでいるからなのだ。", "血の中の銅が\n酸素を運ぶ", "指差し", "カブトガニ", 2),
        L("日本のカブトガニは、大きいと70センチくらい。", "日本のカブトガニは\n最大70cmくらい", "通常", "カブトガニ", 0, [cnt(70, "cm", "最大（くらい）")]),
        L("カニって名前なのに、カニじゃないのだ！", "カニって名前なのに\nカニじゃない", "怒り", up=True),
        L("岡山県笠岡市の繁殖地は、国の天然記念物なのだ。", "笠岡市の繁殖地は\n国の天然記念物", "ドヤ", "カブトガニ", 1, [st("天然記念物", 0.4, 0.35, 190, Y)]),
        L("レッツ脳とけ！", "レッツ\n脳とけ！", "笑顔", logo=True),
        L("ちなみにこの生き物…", "ちなみに\nこの生き物…", "ドヤ", "カブトガニ", 0, loop=True),
    ])

S["clione"] = dict(label="名前がウソすぎる生き物", format="story", themes=["pink_grad", "newspaper", "forest"],
    title="クリオネは、貝の仲間なのだ。天使の正体 #Shorts #雑学 #海の生き物",
    tags=["ずんだもん", "雑学", "海の生き物", "クリオネ", "ハダカカメガイ", "流氷の天使", "脳がとける雑学", "ショート"],
    desc="流氷の天使は、貝の仲間なのだ。\n\n・クリオネの和名はハダカカメガイ。殻をもたない巻貝の仲間（腹足綱 裸殻翼足類）で、体長は1〜3cmほど。幼生のときは殻をもつが、育つと失う。頭から6本の触手（バッカルコーン）を出して、ミジンウキマイマイという巻貝を食べる（Wikipedia「ハダカカメガイ」）https://ja.wikipedia.org/wiki/ハダカカメガイ",
    lines=[
        L("クリオネは、貝の仲間なのだ。", "クリオネは\n貝の仲間", "ドヤ", "ハダカカメガイ", 0, [st("貝", 0.0, 0.35, 280, R)], hook=True),
        L("本当の名前は、ハダカカメガイ。", "本当の名前は\nハダカカメガイ", "指差し", "ハダカカメガイ", 1, [st("ハダカ", 0.4, 0.3, 230, Y)]),
        L("殻をもたない、巻貝の仲間なのだ。", "殻をもたない\n巻貝の仲間", "驚き", "ハダカカメガイ", 2),
        L("赤ちゃんのときは、殻があるのだ。", "赤ちゃんのときは\n殻がある", "驚き", "ハダカカメガイ", 1),
        L("大きさは、1センチから3センチくらい。", "大きさは\n1〜3cm", "通常", "ハダカカメガイ", 0, [cnt(3, "cm", "体長（くらい）")]),
        L("ごはんのときは、頭から触手が6本出るのだ。", "ごはんのときは\n頭から触手が6本", "青ざめ", "ハダカカメガイ", 2, [st("6本", 0.4, 0.3, 230, R)]),
        L("食べるのは、ミジンウキマイマイという巻貝。", "食べるのは\nミジンウキマイマイ", "焦り", "ハダカカメガイ", 1),
        L("天使が、貝を食べる貝だったのだ！", "天使が\n貝を食べる貝", "驚き", up=True),
        L("レッツ脳とけ！", "レッツ\n脳とけ！", "笑顔", logo=True),
        L("ちなみにこの天使…", "ちなみに\nこの天使…", "ドヤ", "ハダカカメガイ", 0, loop=True),
    ])

S["tatsu"] = dict(label="名前がウソすぎる生き物", format="story", themes=["space", "lemon_dots", "checker"],
    title="タツノオトシゴは、お父さんが赤ちゃんを産むのだ #Shorts #雑学 #海の生き物",
    tags=["ずんだもん", "雑学", "海の生き物", "タツノオトシゴ", "魚", "育児嚢", "脳がとける雑学", "ショート"],
    desc="竜の子どもみたいな名前の、魚なのだ。\n\n・タツノオトシゴはヨウジウオ科の魚（Wikipedia「タツノオトシゴ」）。\n・オスのお腹には育児嚢という袋があり、メスはその中に卵を産む。オスは受精した卵を育児嚢で育て、かえった子を水中に産み出す（東京都建設局 資料）https://www.kensetsu.metro.tokyo.lg.jp/content/000066182.pdf",
    lines=[
        L("タツノオトシゴは、お父さんが赤ちゃんを産むのだ。", "タツノオトシゴは\nお父さんが産む", "ドヤ", "タツノオトシゴ", 0, [st("パパ", 0.0, 0.35, 260, R)], hook=True),
        L("竜の子どもみたいな名前だけど、魚なのだ。", "竜の子みたいな名前\nでも魚", "指差し", "タツノオトシゴ", 1),
        L("お父さんのお腹には、袋があるのだ。", "お父さんのお腹に\n袋がある", "驚き", "タツノオトシゴ", 2),
        L("お母さんは、その袋の中に卵を産むのだ。", "お母さんは\n袋の中に卵を産む", "通常", "タツノオトシゴ", 2),
        L("お父さんは、袋の中で卵を育てるのだ。", "お父さんが\n袋の中で育てる", "驚き", "タツノオトシゴ", 1),
        L("かえった赤ちゃんを、水の中に産み出すのだ。", "かえった赤ちゃんを\n水の中に産み出す", "驚き", "タツノオトシゴ", 0, [st("出産", 0.4, 0.3, 230, Y)]),
        L("産むのは、お父さんなのだ！", "産むのは\nお父さん", "焦り", up=True),
        L("この袋は、育児嚢というのだ。", "この袋は\n育児嚢", "ドヤ", "タツノオトシゴ", 2, [st("育児嚢", 0.4, 0.35, 210, Y)]),
        L("レッツ脳とけ！", "レッツ\n脳とけ！", "笑顔", logo=True),
        L("ちなみにこの魚…", "ちなみに\nこの魚…", "ドヤ", "タツノオトシゴ", 0, loop=True),
    ])

EXTRA_YOMI = {"kabutogani": {"日本のカブトガニは、大きいと70センチくらい。": "にほんのカブトガニは、おおきいとななじゅっセンチくらい。"}}
YOMI_OK = ["体", "中", "頭", "動物", "仲間", "生き物", "上", "下", "天然記念物", "名前", "子", "触手", "銅"]

ORDER = ["kabutogani", "clione", "tatsu"]

if __name__ == "__main__":
    for k in ORDER:
        d = dict(BASE); d.update(S[k])
        d["yomi"] = {"レッツ脳とけ！": "レッツのーとけ！"}
        d["yomi"].update(EXTRA_YOMI.get(k, {}))
        d["yomi_ok"] = YOMI_OK
        d["meta"] = {"exp": "雑学 冒頭0秒の絵 B（1行目から題材の写真）"}
        out = os.path.join(os.path.dirname(__file__), f"trivia_{k}.json")
        json.dump(d, open(out, "w"), ensure_ascii=False, indent=1)
        print(out, len(d["lines"]), "lines")
