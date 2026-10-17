# kaidan/brand.py — 怪談チャンネル「今晩の百物語」の見た目と言い回し。render.build_video(brand=...) に渡す。
# 黒×白×朱、明朝。語り部は狐面の「宵狐」。声は冥鳴ひまり。
# 効果音はほかのチャンネルと同じさりげない音のまま（演出的な音は使わない）。BGMは拾ってきた曲に差し替える前提
import math

CHANNEL = "今晩の百物語"
HOST = "宵狐"
VOICE = {"vvm": "1.vvm", "style": 14, "speed": 0.92, "pitch": -0.02, "intonation": 0.9}   # 冥鳴ひまり
VOICE_NAME = "冥鳴ひまり"
# 冥鳴ひまりの規約：商用可・申請不要・クレジット必須（書式自由）→「VOICEVOX:冥鳴ひまり」を概要欄と画面に自動で入れる
VOICE_TAGS = ["冥鳴ひまり"]
# BGMは展開ごとに3曲を切り替える（音で驚かせるためではなく、単調にさせず最後まで聞いてもらうため）。
# 台本のセクションに "bgm": "main" / "calm2" / "climax"。書いていない章は直前と同じ扱いではなく main
BGM_TRACKS = {
    "main":   ("assets/bgm_kaidan_haikyo.mp3", "廃墟に居る者 / ゆうり(Yuli Audio Craft)"),
    "calm2":  ("assets/bgm_kaidan_babybed.mp3", "空っぽのベビーベッド / ゆうり(Yuli Audio Craft)"),
    "climax": ("assets/bgm_kaidan_kimodameshi.mp3", "肝試し / alaki paca"),
}


def bgm_for(work, k):
    """地の曲と、概要欄のクレジット（実際に使った曲だけを載せる）"""
    keys = ["main"] + [s.get("bgm", "main") for s in k["sections"]]
    used = [BGM_TRACKS[x] for x in dict.fromkeys(keys) if x in BGM_TRACKS]
    credit = "BGM: " + "、".join(c for _, c in used) + "（OpenTracks（旧DOVA-SYNDROME））"
    return BGM_TRACKS["main"][0], credit

KANSUJI = "〇一二三四五六七八九"


def kansuji(n):
    """1〜999 を漢数字に（第百話 まで想定）"""
    if n == 100:
        return "百"
    s = ""
    h, r = divmod(n, 100)
    t, o = divmod(r, 10)
    if h: s += ("" if h == 1 else KANSUJI[h]) + "百"
    if t: s += ("" if t == 1 else KANSUJI[t]) + "十"
    if o: s += KANSUJI[o]
    return s or "〇"


def host_intro(work, k):
    """名乗り（第二話から）。京ことばは頭のあいさつ「ようおこしやす」だけ。あとは丁寧な語り口。
    締めは案内の口上「〇〇へ、ご案内いたします」。〇〇は台本の kojo_place（既定「この世とあの世の境」）"""
    where = k.get("where") or "古く"
    place = k.get("kojo_place") or "この世とあの世の境"
    return (f"今宵も、ようおこしやす。語り部の、宵狐でございます。"
            f"百物語、第{kansuji(work['no'])}話。これは、{where}に伝わるお話。"
            f"{place}へ、ご案内いたします。")


def host_outro(work, k):
    src = f"{work['author']}の、{work['title']}"
    return (f"……これで、今宵のお話は、おしまい。原作は、{src}でございました。"
            f"百物語は、まだまだ続きます。次の夜も、どうぞお越しくださいませ。"
            f"チャンネル登録をしてお待ちいただければ、宵狐、うれしゅうございます。")


CSS = """
body { background:#0a0a0c; color:#ffffff; font-family:"Noto Serif CJK JP"; }
.scrim { background:rgba(0,0,0,{scrim}); }
.label { color:#bbbbbb; background:rgba(0,0,0,.72); padding:8px 20px; text-shadow:none !important; font-family:"Noto Serif CJK JP"; }
.rule { display:none; }
h1 { display:none !important; }
.badge { display:none !important; }
.credit { color:#cccccc !important; background:rgba(0,0,0,.72); padding:6px 16px; font-family:"Noto Serif CJK JP"; }
.bg { background-size:contain; background-repeat:no-repeat; background-position:center; }
.subtitle { background:rgba(0,0,0,.78); padding:14px 36px; border-radius:0; bottom:110px;
            font-family:"Noto Serif CJK JP"; font-weight:700; }
"""

# 章のアイキャッチ：暗い地に章題が静かに浮かんで消える＋遠くの鐘「ぼーん」（第二話から）
CARD_STYLE = dict(kind="fade", bg=(6, 6, 8), ink=(232, 228, 220))


# ---- 語り部の絵（提灯の炎がゆらぐ。じっと見る場面では首をかしげる）----
_cache = {}
HOST_SIZE = 900


def host_draw(i, talking, face):
    import kitsune
    lamp = 0.78 + 0.14 * math.sin(i * 0.37) + 0.06 * math.sin(i * 1.31 + 1.0)
    lv = round(lamp * 20) / 20
    tilt = -8 if face == "jito" else 0
    key = (lv, tilt)
    if key not in _cache:
        _cache[key] = kitsune.kitsune(lv, tilt, HOST_SIZE)
    bob = int(3 * math.sin(i / 30 * 2 * math.pi / 5.0))
    return _cache[key], (90, 1080 - HOST_SIZE + 30 + bob)


def kaidan_brand(work, k):
    no = kansuji(work["no"])
    title = work["title"]
    label = f"{CHANNEL} — 第{no}話"
    src = f"{work['author']}『{title}』" + (f"（{work['translator'].removesuffix('訳')}訳）" if work.get("translator") else "")
    return {
        "label": label,
        "part_label": {},
        "part_intro": {},
        "title_narr": lambda _k: f"第{no}話。{k.get('display_title', title)}。",
        "title_card": "",
        "title_card_motion": (f'<div class="label">{label}</div>'
                              f'<div class="center"><div style="text-align:center;">'
                              f'<div style="display:inline-block;background:#8e1414;color:#fff;font-size:50px;font-weight:900;'
                              f'padding:12px 32px;margin-bottom:34px;letter-spacing:.12em;font-family:\'Noto Serif CJK JP\';">'
                              f'{CHANNEL}　第{no}話</div><br>'
                              f'<div style="display:inline-block;background:#000;color:#fff;font-size:150px;font-weight:900;'
                              f'padding:.1em .45em;font-family:\'Noto Serif CJK JP\';">{k.get("display_title", title)}</div>'
                              f'</div></div>'),
        "motion": True,
        "motion_first": False,
        "pan_mode": "slow",              # ごくゆっくりの横パン。同じ画像の間は文をまたいでつながる（カット割りしない）
        "host_name": HOST,
        "host_role": "百物語の語り部",
        "host_outro": host_outro(work, k),
        "voice": VOICE,
        "credit": f"原作：{src}（青空文庫）　VOICEVOX:{VOICE_NAME}",
        "accent": "#8e1414",
        "css": CSS,
        "card_style": CARD_STYLE,
        "card_dur": 3.2,
        "card_se": [("k_bonsho", 0.05, 1.0)],
        "bgm": bgm_for(work, k)[0],
        "bgm_tracks": {key: p for key, (p, _) in BGM_TRACKS.items()},
        "scrim": 0.25,
        "outro_heading": "おしまい",
    }


def install_motion():
    """motion.py（共通の動きの部品）を怪談用に切り替える"""
    import motion
    motion.HOST_DRAW = host_draw
    motion.NAME_COLORS = ((255, 255, 255), (142, 20, 20))
    motion.HOOK_COLORS = (((255, 255, 255), (142, 20, 20)), ((255, 255, 255), (0, 0, 0)))
    motion.FAMILY = "Noto Serif CJK JP"
    import se_kaidan
    se_kaidan.install_subtle()         # 効果音：不協和のさりげない短い音（第二話から）
