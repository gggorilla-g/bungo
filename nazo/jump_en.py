# jump_en.py — 日本語のジャンプ台本から英語版（ft・mph、Make It Work 3D 向け）を作る
#   python nazo/jump_en.py jump_x3   → nazo/shorts/nbai/jump_x3_en.json
#   字幕は日本語の言い回しを型で英訳する（型に無い言い回しは止める）
import json, re, sys, copy
SD = "nazo/shorts/nbai"
PAT = [  # (日本語の正規表現, 英語)  {..} はそのまま引き継ぐ
    (r"^(\d+)回目は、\{cm\}センチ$", r"Jump \1: {h} ft"),
    (r"^(\d+)回目[はで、]、?\{h\}メートル$", r"Jump \1: {h} ft"),
    (r"^(\d+)回目、\{h\}メートル$", r"Jump \1: {h} ft"),
    (r"^(\d+)回目で、$", r"Jump \1 clears"),
    (r"^(\d+)回目で、校舎をこえる$", r"Jump \1 clears the school"),
    (r"^(\d+)回目、踏み切りで\{g\}G$", r"Jump \1: {g} G at takeoff"),
    (r"^東京タワーをこえる$", "Tokyo Tower"),
    (r"^富士山をこえる$", "Mt. Fuji"),
    (r"^高さ\{h\}メートル$", "{h} ft high"),
    (r"^高さ\{h\}メートル。滞空は\{air\}秒$", "{h} ft. {air} s in the air"),
    (r"^高さ\{h\}メートル。校舎は約\{ref:school\}m$", "{h} ft. The school is about {ref:school.ft} ft"),
    (r"^滞空は\{air\}秒$", "{air} s in the air"),
    (r"^跳ぶたびに、高さが(\d+)倍になる$", r"Each jump goes \1x higher"),
    (r"^バスケットゴール（\{ref:hoop\}m）より上$", "Above a basketball hoop ({ref:hoop.ft} ft)"),
    (r"^人が耐えた記録は\{ref:stapp\}G（\{ref:stapp.year\}年）$", "Human record: {ref:stapp} G ({ref:stapp.year})"),
    (r"^この先、\{space\}回目で宇宙$", "Space (62 miles up) by jump {space}"),
    (r"^(\d+)回目の滞空は\{air\}秒$", r"Jump \1 hangs in the air {air} s"),
    (r"^着地は時速\{kmh\}km。新幹線より速い$", "Lands at {mph} mph, faster than a bullet train"),
    (r"^着地の速さは時速\{kmh\}km$", "Landing at {mph} mph"),
    (r"^新幹線（時速\{ref:shinkansen\}km）より速い$", "Faster than a bullet train ({ref:shinkansen.mph} mph)"),
    (r"^あと1回で富士山（\{ref:fuji\}m）をこえる$", "One more clears Mt. Fuji ({ref:fuji.ft} ft)"),
    (r"^富士山（\{ref:fuji\}m）より高い$", "Higher than Mt. Fuji ({ref:fuji.ft} ft)"),
    (r"^東京タワー（\{ref:tokyo_tower\}m）まであと少し$", "Almost Tokyo Tower ({ref:tokyo_tower.ft} ft)"),
    (r"^東京都庁（\{ref:tocho\}m）をこえる$", "Taller than Tokyo's city hall ({ref:tocho.ft} ft)"),
    (r"^(\d+)階建てのビルくらい$", r"About a \1-story building"),
    (r"^2階建ての家くらい$", "About a two-story house"),
    (r"^高さ\{h\}メートル。4階建ての屋上より上$", "{h} ft, above a 4-story roof"),
    (r"^(\d+)回目で、校舎をこえる$", r"Jump \1 clears the school"),
]
FT = {"school": 49, "hoop": 10, "tokyo_tower": "1,093", "tocho": "797", "fuji": "12,388"}
LBL = {"tokyo_tower": "Tokyo Tower 1,093 ft", "fuji": "Mt. Fuji 12,388 ft"}


def tr(s):
    for a, b in PAT:
        if re.match(a, s):
            return re.sub(a, b, s)
    sys.exit(f"英訳の型がない: {s}")


def main(sid):
    e = copy.deepcopy(json.load(open(f"{SD}/{sid}.json", encoding="utf-8")))
    k = e["physics"]["multiplier"]; mul = f"{k:g}x"
    e["id"] = sid + "_en"; e["lang"] = "en"
    e["titleLines"] = ["What if every jump", [["went ", 0], [mul, 1], [" higher?", 0]]]
    e["notes"] = {"exp": "*Thought experiment. Numbers are theoretical", "big": "*Figure enlarged. No air resistance",
                  "end": "*Earth gravity only. No air resistance"}
    for r in e["references"]:
        if r["id"] in FT: r["ft"] = FT[r["id"]]
        if r["id"] in LBL: r["labelEn"] = LBL[r["id"]]
        if r["id"] == "shinkansen": r["mph"] = 199
    for c in e["captions"]:
        c["main"] = [tr(x) for x in c["main"]]; c["sub"] = [tr(x) for x in c["sub"]]
        b = c.setdefault("bindings", {})
        for key in list(b):
            m = b[key]["metric"]
            if m in ("heightM", "heightCm"):
                v = b.pop(key); v["metric"] = "heightFt"; v["format"] = "oneDecimal" if 0.5 * k ** (v["n"] - 1) * 3.28 < 10 else "integer"; b["h"] = v
            elif m == "landingKmh":
                v = b.pop(key); v["metric"] = "landingMph"; v["format"] = "integer"; b["mph"] = v
        if c.get("note", "").startswith("※踏みこみ"):
            c["note"] = "*Assumes a {in}-inch push-off"; b.pop("cm", None); b["in"] = {"metric": "pushIn", "format": "integer"}
    src = {r["id"]: r for r in e["references"]}
    S = ["- Basketball hoop 3.05 m (10 ft): FIBA Official Rules 2026 Equipment " + src["hoop"]["sourceUrl"]]
    if "tocho" in src: S.append("- Tokyo Metropolitan Government Building No.1, about 243 m: " + src["tocho"]["sourceUrl"])
    S.append("- Tokyo Tower 333 m: GO TOKYO " + src["tokyo_tower"]["sourceUrl"])
    if "fuji" in src: S.append("- Mt. Fuji 3,776 m: Japan Meteorological Agency " + src["fuji"]["sourceUrl"])
    S += ["- Shinkansen E5 top speed 320 km/h: JR East " + src["shinkansen"]["sourceUrl"],
          "- 46.2 G human record (John Stapp, 1954): Smithsonian " + src["stapp"]["sourceUrl"]]
    fuji = "\nMt. Fuji is placed for height comparison; its position is not real." if "fuji" in src else ""
    e["post"] = {"title": f"What if every jump went {mul} higher? #shorts",
                 "desc": f"Jump 1 is 50 cm (1.6 ft). Every jump goes {k:g} times higher. When does it clear Tokyo Tower, and when does it reach space?\n"
                         f"*A thought experiment. Earth gravity only, no air resistance. Takeoff G assumes a 50 cm (20 in) push-off. The figure is enlarged for visibility.{fuji}\n\nSources\n"
                         + "\n".join(S) + "\n\nMusic: original\n#whatif #physics #science",
                 "tags": ["what if", "physics", "thought experiment", "science", "jump"]}
    json.dump(e, open(f"{SD}/{e['id']}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(e["id"])


if __name__ == "__main__":
    main(sys.argv[1])
