# nazo/compile/kit.py — 総集編の投稿キット（【タイトル】【説明】【タグ】）。説明欄の先頭にチャプター、クレジットは元のショートのものを統合
#   使い方: python nazo/compile/kit.py <id> <チャプターtxt> <ショートの upload.txt があるフォルダ>
#   説明欄は API で 5000 バイトまで（日本語は1文字3バイト）。
import glob, json, os, re, sys

KIT = {
    "moso_compile_1": {
        "dir": "nazo/manual/moso_science",
        "title": "ずんだもんが宇宙と地球で7回ひどい目にあう【妄想科学 総集編】",
        "lead": "ブラックホール、地球の穴、木星、地球停止、光の速さ、タイムマシン、太陽系移住。ずんだもんの妄想科学ショートをまとめて、小ネタを足したのだ。",
        "src": ["Wikipedia「ブラックホール」「スパゲッティ化」「コラ半島超深度掘削坑」「木星」「大赤斑」「ガリレオ (探査機)」「自転」「光速」「太陽系」「タイムトラベル」「海王星」、英語版「Gravity train」",
                "NASA Science 各惑星の Facts", "各ショートの説明欄の出典（NASA、Klotz 2015 American Journal of Physics ほか）"],
        "extra_credit": ["NASA の写真・画像（パブリックドメイン。NASA は本動画を推奨・監修していません）"],
        "note": "※ 「もしも」の場面は思考実験です。数値は代表値・概数です。",
        "tags": ["ずんだもん", "妄想科学", "もしも", "宇宙", "ブラックホール", "木星", "光の速さ", "タイムマシン", "空想科学", "総集編"],
    },
    "trivia_compile_1": {
        "dir": "nazo/manual/trivia_compile",
        "title": "名前がひどすぎる生き物・駅・湖まとめ【ずんだもんの脳がとける雑学 総集編】",
        "lead": "名前がひどすぎる駅、生き物、植物、海の生き物、カナダの湖、魚。ずんだもんの雑学ショートをまとめて、小ネタを足したのだ。",
        "src": ["Wikipedia「半家駅」「大歩危駅」「小歩危駅」「母恋駅」「おもちゃのまち駅」「バカガイ」「ハダカデバネズミ」「アホウドリ」「ヘクソカズラ」「ママコノシリヌグイ」「ハキダメギク」「オオイヌノフグリ」「タナカゲンゲ」「ウッカリカサゴ」「スベスベマンジュウガニ」「ニュウドウカジカ」",
                "各ショートの説明欄の出典（コトバンク、笹川平和財団、三重県水産研究所、沖縄県水産海洋技術センター、CNN、カナダの地名データベースほか）"],
        "extra_credit": [],
        "note": "※ 名前の由来には諸説あるものがあります。",
        "tags": ["ずんだもん", "雑学", "名前がひどい", "生き物", "駅名", "植物", "魚", "脳がとける雑学", "総集編"],
    },
}


def credits(folder):
    """元のショートの upload.txt から、音声・立ち絵・BGM・効果音・画像の行を集める（重複は1つに）"""
    keep = {}
    for p in sorted(glob.glob(os.path.join(folder, "short3_*_upload.txt"))):
        txt = open(p, encoding="utf-8").read()
        body = txt.split("【説明】", 1)[-1].split("【タグ】")[0]
        for ln in body.splitlines():
            ln = ln.strip()
            m = re.match(r"^(音声|立ち絵|BGM|効果音|画像)\s*[:：]\s*(.+)$", ln)
            if m:
                keep.setdefault(m.group(1), [])
                if m.group(2) not in keep[m.group(1)]:
                    keep[m.group(1)].append(m.group(2))
    return keep


def short_img(s):
    """画像の行を短く：作者 / ライセンス / ファイル名（頭だけ）"""
    m = re.match(r"(.+?) / (.+?) / Wikimedia Commons（File:(.+)）", s)
    if not m:
        return s[:80]
    who, lic, fn = m.groups()
    fn = fn.rsplit(".", 1)[0]
    return f"{who[:30]}({lic.replace('CC BY-SA ', 'BY-SA').replace('CC BY ', 'BY').replace('Public domain', 'PD')}): {fn[:18]}{'…' if len(fn) > 18 else ''}"


def main(cid, chap, folder):
    k = KIT[cid]
    c = credits(folder)
    lines = [k["lead"], "", open(chap, encoding="utf-8").read().strip(), "", "■ 出典"] + ["・" + s for s in k["src"]] + [k["note"], "", "■ クレジット"]
    lines += [f"音声: {' / '.join(c.get('音声', ['VOICEVOX:ずんだもん']))}", "立ち絵: 坂本アヒル"]
    lines += [f"BGM: {b}" for b in c.get("BGM", [])] + ["効果音: オリジナル"] + k["extra_credit"]
    imgs = c.get("画像", [])
    if imgs:
        lines += ["画像（Wikimedia Commons 作者(ライセンス): ファイル名。BY=CC BY、BY-SA=CC BY-SA、PD=パブリックドメイン）"] + [short_img(s) for s in imgs]
    lines += ["", " ".join("#" + t for t in k["tags"][:3])]
    desc = "\n".join(lines)
    while len(desc.encode()) > 4950 and imgs:            # 5000バイトを超えるなら画像の行のファイル名を外す
        lines = [re.sub(r": .+$", "", l) if l in [short_img(s) for s in imgs] else l for l in lines]
        desc = "\n".join(dict.fromkeys(lines)) if len("\n".join(lines).encode()) > 4950 else "\n".join(lines)
        break
    out = os.path.join(k["dir"], f"{cid}_upload.txt")
    os.makedirs(k["dir"], exist_ok=True)
    open(out, "w", encoding="utf-8").write(f"【タイトル】\n{k['title']}\n\n【説明】\n{desc}\n\n【タグ】\n{','.join(k['tags'])}\n")
    print(out, len(desc.encode()), "バイト")


if __name__ == "__main__":
    main(*sys.argv[1:4])
