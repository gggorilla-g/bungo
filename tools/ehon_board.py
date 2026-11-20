# ehon_board.py — Codex の絵コンテ（ビートの並び）を、ehon3d の演出（nazo/ehon/<id>.json）に組み立てる
#   1ビート＝読み上げのひとこと＋そのとき映すもの（舞台＝背景と紙人形をカメラで撮る／1枚絵＝寄りの絵を全面に）
#   同じ背景が続くビートは1ページにまとめ、ビートの頭でカメラを切り替える。紙人形の絵が替わったらポーズ替え（ディゾルブ）
#   使い方: python3 tools/ehon_board.py 絵コンテ.json 素材フォルダ 出力id [題名]
import json, sys, os, re

DARK = ("overcast", "rain", "low_overcast")          # 暗い背景では本文を明るい色に
FAM = lambda n: "pino" if n.startswith("mouse") else "lulu" if n.startswith("snail") else "both" if n.startswith("pino_lulu") else n
POS = {"pino": (-.65, .4), "lulu": (.75, 0), "both": (0, 0), "leaf": (.3, -.3), "drop": (0, 0)}
WALK = ["mouse_walk_a", "mouse_walk_b", "mouse_walk_c", "mouse_walk_d"]
BIG = {"name": "pochan", "from": 0, "dur": .6, "gain": .8, "lp": 9000, "fin": 0}
SMALL = {"name": "pichon", "from": 0, "dur": .45, "gain": .6, "lp": 9000, "fin": 0}


def plus(at, x):
    if isinstance(at, str) and at.startswith("s"): return f"s{float(at[1:]) + x:.2f}"
    if isinstance(at, str): return f"{at}+{x}"
    return at


def sfx_of(names, at):
    out = []
    for n in names or []:
        if "雷" in n: out.append({"name": "thunder", "at": at, "from": 6.2, "dur": 6, "gain": .45})
        elif "ポトン" in n or "大粒" in n: out.append(dict(BIG, at=at))
        elif "ピチ" in n or "小粒" in n or "しずく" in n or "一滴" in n: out.append(dict(SMALL, at=at))
        elif "雨" in n: out.append({"name": "rain", "at": at, "from": 5, "dur": 20, "gain": .18})
        elif "風" in n or "そよ" in n: out.append({"name": "breeze", "at": at, "from": 4, "dur": 12, "gain": .12})
    return out


def cam_of(shot, xs):
    f = shot.get("focus", "both"); fr = shot.get("frame", "mid")
    x, y = xs.get(f, (0, 0))[0], 1.0
    d = {"wide": 8.0, "mid": 4.6, "close": 3.3}.get(fr, 4.6)
    if fr == "wide": x *= .4; y = 1.15
    elif f == "leaf": y = 1.25
    else: y = .85
    return x, y, d


def main(board, assets, sid, title=None):
    B = json.load(open(board))["beats"]; PT = {}
    if os.path.exists(f"{assets}/close/points.json"): PT = json.load(open(f"{assets}/close/points.json"))
    pages = []; cur = None
    def new_page(bg, image=False):
        pg = {"bg": bg, "lines": [], "items": [], "cam": [], "sfx": [], "gap": 1.0, "_fam": {}, "_pend": 0.0, "_image": image}
        if image: pg.update(bg_h=5.6, bg_y=-1.6)
        else: pg.update(bg_h=7.8, bg_y=-2.7)
        dark = any(k in bg for k in DARK) and "clear" not in bg
        pg["text"] = {"size": 25, "group": 2, "wrap": 14}
        if "rain" in bg: pg["rain"] = [-.1, 1.2]; pg["sfx"].append({"name": "rain", "at": 0, "from": 30, "dur": 90, "gain": .16})
        if "overcast" in bg: pg["light"] = .9
        pages.append(pg); return pg
    for i, b in enumerate(B):
        sh = b["shot"]; txt = b.get("text", "").strip(); walking = False
        if sh["kind"] == "stage" and any(n.startswith("mouse_walk_") for n in sh.get("items", [])):
            sh = dict(sh, items=["mouse_walk"] + [n for n in sh["items"] if not n.startswith("mouse_walk")]); walking = True
        if sh["kind"] == "stage":
            if cur is None or cur["_image"] or cur["bg"] != sh["bg"]: cur = new_page(sh["bg"])
            at = f"L{len(cur['lines'])}" if txt else None
            if not txt:   # 声なしビート：前の文のあとに間を置き、その間にカメラを替える
                if not cur["lines"]: at = f"s{cur.get('_t', 0):.2f}"; cur["_t"] = cur.get("_t", 0) + b.get("dur", 3); cur["dur"] = cur["_t"]; cur["pad0"] = cur["_t"] + .6
                else: li = len(cur["lines"]) - 1; cur.setdefault("pause", {})[str(li)] = cur.get("pause", {}).get(str(li), 0) + b.get("dur", 3); at = f"L{li}e+0.6"
            # 紙人形：家族（ピノ・ルル・ふたり）ごとに今の絵を追う
            xs = {}
            for n in sh.get("items", []):
                fam = FAM(n); base = POS.get(fam, (0, 0))
                if fam not in cur["_fam"]:
                    it = {"img": n, "x": base[0], "z": base[1], "_fam": fam, "acts": []}
                    if n == "leaf": it.update(h=.34, auto=False)
                    if n.startswith("snail"): it["face"] = -1
                    if cur["lines"] or cur["cam"]: it["show"] = at
                    cur["items"].append(it); cur["_fam"][fam] = it
                else:
                    it = cur["_fam"][fam]; last = it["acts"][-1]["pose"] if it["acts"] and "pose" in it["acts"][-1] else it["img"]
                    if last != n: it["acts"].append({"do": "pose", "t": at, "pose": n, "dur": .45})
                if fam == "both":   # ふたりの絵が出たら、ひとりずつの絵は消す
                    for f2 in ("pino", "lulu"):
                        if f2 in cur["_fam"] and "hide" not in cur["_fam"][f2]: cur["_fam"][f2]["hide"] = at
                xs[fam] = (it.get("_x", it["x"]), 0)
                if walking and fam == "pino" and txt:
                    nx = it.get("_x", it["x"]) + .55; it["acts"].append({"do": "walk", "t0": at, "t1": f"L{len(cur['lines'])}e+0.3", "x": nx, "frames": WALK, "fps": 5, "end": "mouse_walk"}); it["_x"] = nx
            if "leaf" in [FAM(n) for n in sh.get("items", [])]: xs["leaf"] = POS["leaf"]
            x, y, d = cam_of(sh, xs); key = {"u": at, "x": x, "y": y, "d": d, "cut": bool(cur["cam"])}
            sig = (sh.get("frame"), sh.get("focus"))
            if cur.get("_sig") == sig and cur["cam"] and not cur["cam"][-1].get("img"):
                cur["cam"][-1]["u"] = f"L{len(cur['lines'])}e+0.4" if txt else cur["cam"][-1]["u"]; cur["cam"][-1].update(x=x, y=y + .02); key = None
            cur["_sig"] = sig
            if key: cur["cam"].append(key); cur["cam"].append({"u": f"L{len(cur['lines'])}e+0.4" if txt else (at if isinstance(at, str) else .9), "x": x, "y": y + .02, "d": d * .95})
        else:   # 1枚絵
            img = sh["img"]; nm = img.split("/")[-1]
            if cur is None or (not cur["lines"] and not cur["cam"]) or cur["_image"]:
                cur = new_page(img, image=True); cur["cam"] = [{"u": 0, "x": 0, "y": 1.2, "d": 8.8}, {"u": 1, "x": 0, "y": 1.2, "d": 8.0}]
                if not txt: cur["dur"] = cur.get("dur", 0) + b.get("dur", 3)
                at = f"L{len(cur['lines'])}" if txt else 0; fxk = cur.setdefault("fx", [])
            else:
                at = f"L{len(cur['lines'])}" if txt else None
                if not txt and not cur["lines"]: at = f"s{cur.get('_t', 0):.2f}"; cur["_t"] = cur.get("_t", 0) + b.get("dur", 3); cur["dur"] = cur["_t"]; cur["pad0"] = cur["_t"] + .6
                elif not txt: li = len(cur["lines"]) - 1; cur.setdefault("pause", {})[str(li)] = cur.get("pause", {}).get(str(li), 0) + b.get("dur", 3); at = f"L{li}e+0.6"
                if cur["cam"] and cur["cam"][-1].get("img") == img: fxk = cur["cam"][-1]["fx"]   # 同じ寄りが続くなら切らない
                else: key = {"u": at, "x": 0, "y": 1, "d": 9, "img": img, "fx": []}; cur["cam"].append(key); fxk = key["fx"]; cur["_sig"] = None
            p = PT.get(nm)
            act = sh.get("action", "")
            if p and any(k in act for k in ("落ち", "落と", "粒", "しずく", "輪")):
                fxk.append({"type": "ripple", "x": p["x"], "y": p["y"], "at": [plus(at, .4)], "speed": .07, "flat": .5} if ("まんなか" in nm or "mid" in nm or "puddle" in nm) else {"type": "drop", "x": p["x"], "y": p["y"] + .02, "t": plus(at, .3), "g": 1500})
            if p and any(k in act for k in ("光", "にじ", "きら")): fxk.append({"type": "sparkle", "n": 6, "x0": p["x"] - .05, "x1": p["x"] + .05, "y0": p["y"] - .05, "y1": p["y"] + .05, "seed": i})
        if txt:
            if cur["lines"] and not re.search(r"[。」！？!?]$", cur["lines"][-1]) and not cur.get("pause", {}).get(str(len(cur["lines"]) - 1)):
                cur.setdefault("gaps", {})[str(len(cur["lines"]) - 1)] = .18
            cur["lines"].append(txt)
        cur["sfx"] += sfx_of(b.get("sfx"), at if at is not None else 0)
    for pg in pages:
        for k in [k for k in pg if k.startswith("_")]: pg.pop(k)
        for it in pg["items"]:
            for k in [k for k in it if k.startswith("_")]: it.pop(k)
        if not pg["lines"]: pg.setdefault("dur", 4); pg["cam"] = [c for c in pg["cam"] if not isinstance(c["u"], str)] or [{"u": 0, "x": 0, "y": 1.2, "d": 8.6}, {"u": 1, "x": 0, "y": 1.2, "d": 7.8}]
        if not pg["cam"]: pg.pop("cam")
    pages[-1]["tail"] = 6.0
    sp = {"id": sid, "title": title or "えほん", "assets": assets, "voice": {"vvm": "6.vvm", "style": 31, "speed": .86, "vol": 1.5},
          "sfx_files": {"rain": "assets/sfx/yt_light_rain.mp3", "thunder": "assets/sfx_pd/thunder.ogg", "drip": "assets/sfx_pd/drip.ogg", "breeze": "assets/sfx_pd/breeze.ogg", "pochan": "assets/sfx_gen/pochan.wav", "pichon": "assets/sfx_gen/pichon.wav"},
          "world": {"pino": ["head_w", .44], "lulu": ["shell_d", .55], "leaf": ["len", 1.1], "drop": ["h", .09], "flower": ["w", .9]},
          "scale_alias": {"pino_lulu_leaf_smile": "pino_lulu_leaf_sit", "mouse_stop": "mouse_walk"},
          "title_sec": 5.5, "cover": "cover", "logo_rel": "ehon/brand/logo_sil_light.png", "output": {"width": 1920, "height": 1080}, "music_gain": .2, "pages": pages}
    json.dump(sp, open(f"nazo/ehon/{sid}.json", "w"), ensure_ascii=False, indent=1); print("ページ", len(pages), "ビート", len(B))


if __name__ == "__main__":
    main(*sys.argv[1:5])
