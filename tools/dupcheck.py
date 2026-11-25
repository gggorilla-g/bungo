#!/usr/bin/env python3
"""dupcheck.py — 投稿前に「同じチャンネルに同じ題名がもう出ていないか」を確かめる。

11/25 持ち主「同じのあげてんじゃん」：11/20 に出した「2枚の鏡」を、順番待ちに残したまま 11/25 にもう一度上げた。
原因は、順番待ちを「チャンネルに実際に出ている一覧」と突き合わせていなかったこと（投稿の記録 upload_done.txt は 11/20 午後からで、
それより前や手で上げた分が抜けていた）。記録ではなく Studio の一覧そのものを台帳にして、上げる前に必ず照らす。

  dupcheck.py check <キット> <MOSO|KAIDAN|NAZO|ZATSU>   重複なら「重複: …」を出して終了コード1
  dupcheck.py add   <キット> <チャンネル> <動画ID>        上げたら台帳に1行足す
  dupcheck.py audit [順番待ちのパス]                      順番待ちを全部照らして一覧にする
  dupcheck.py selfcheck                                   台帳の中で、公開中の題名どうしが重なっている組を出す

台帳: nazo/ballsim/published_<チャンネル>.txt（動画ID|公開設定|日付|題名）。Studio の一覧を読んで写す。
判定:
  同じ   … かっこ書き（最後まで見て 等）とハッシュタグ・記号・空白を外して同じ題名
  ほぼ同じ … 上の形で 82% 以上似ていて、中の数字の並びも同じ（「3倍」と「5倍」のような別の回は数字が違うので通す）
どちらも、公開中の動画に当たったら上げない。非公開の動画にだけ当たったときは知らせて通す（古い版を先に非公開にした差し替え）。
わざと同じ題名で出し直すときだけ、ALLOW_DUP=1 を付けて up.sh を呼ぶ。
"""
import datetime
import difflib
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEAR = 0.82


def reg_path(tag):
    return os.path.join(ROOT, "nazo", "ballsim", "published_%s.txt" % tag)


def kit_title(kit):
    t = open(kit, encoding="utf-8").read()
    m = re.search(r"【タイトル】\s*\n(.+?)(?:\n\s*\n|\n【|\Z)", t, re.S)
    if not m:
        raise SystemExit("題名が読めない: %s" % kit)
    return " ".join(m.group(1).split())


def strip_tags(t):
    return re.sub(r"#\S*", "", t).strip()


def norm(t):
    t = unicodedata.normalize("NFKC", strip_tags(t)).lower()
    return re.sub(r"[^0-9a-z぀-ヿ一-鿿]", "", t)


def core(t):
    """かっこ書きを外した中身。全部かっこだった時は外さない。"""
    c = norm(re.sub(r"[（(][^（()）]*[)）]", "", strip_tags(t)))
    return c or norm(t)


def digits(t):
    return re.findall(r"\d+(?:\.\d+)?", unicodedata.normalize("NFKC", strip_tags(t)))


def load(tag):
    p = reg_path(tag)
    rows = []
    if not os.path.exists(p):
        return rows
    for line in open(p, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        a = line.split("|", 3)
        if len(a) == 4:
            rows.append({"id": a[0], "vis": a[1], "date": a[2], "title": a[3]})
    return rows


def match(title, rows, skip_id=None):
    """(種類, 行) の一覧。種類は「同じ」「ほぼ同じ」。"""
    c, d, out = core(title), digits(title), []
    for r in rows:
        if skip_id and r["id"] == skip_id:
            continue
        rc = core(r["title"])
        if rc == c:
            out.append(("同じ", r))
        elif digits(r["title"]) == d and difflib.SequenceMatcher(None, c, rc).ratio() >= NEAR:
            out.append(("ほぼ同じ", r))
    return out


def check(kit, tag, quiet=False):
    title = kit_title(kit)
    rows = load(tag)
    if not rows:
        if not quiet:
            print("台帳がない（%s）。Studio の一覧と目で照らしてから上げること" % os.path.basename(reg_path(tag)))
        return 0, []
    ms = match(title, rows)
    pub = [(k, r) for k, r in ms if r["vis"] == "公開"]
    for k, r in pub:
        print("重複: 題名が%s動画がもう公開されている → %s（%s 公開）「%s」" % (k, r["id"], r["date"], r["title"]))
    if not pub and not quiet:
        for k, r in ms:
            print("知らせ: 非公開の %s と題名が%s（差し替えなら問題なし）" % (r["id"], k))
    return (1 if pub else 0), ms


def add(kit, tag, vid):
    title = strip_tags(kit_title(kit))
    rows = load(tag)
    if any(r["id"] == vid for r in rows):
        return
    p = reg_path(tag)
    new = not os.path.exists(p)
    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write("# 動画ID|公開設定|日付|題名（ハッシュタグなし）。tools/dupcheck.py が投稿前に突き合わせる\n")
        jst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        f.write("%s|公開|%s|%s\n" % (vid, jst.strftime("%Y/%m/%d"), title))


def audit(qpath):
    bad = 0
    for line in open(qpath, encoding="utf-8"):
        a = line.split("#")[0].split()
        if len(a) < 2:
            continue
        vid, tag = a[0], a[1]
        kit = os.path.join(ROOT, "nazo", "manual", "ballsim", "%s_upload.txt" % vid)
        if not os.path.exists(kit):
            print("%-14s %-6s キットなし" % (vid, tag))
            continue
        title = kit_title(kit)
        ms = match(title, load(tag))
        pub = [(k, r) for k, r in ms if r["vis"] == "公開"]
        if pub:
            bad += 1
            print("%-14s %-6s 重複 %s" % (vid, tag, " / ".join("%s %s(%s)" % (k, r["id"], r["date"][5:]) for k, r in pub)))
        else:
            print("%-14s %-6s 可   %s" % (vid, tag, strip_tags(title)[:44]))
    print("重複 %d 本" % bad)
    return 1 if bad else 0


def selfcheck():
    for p in sorted(os.listdir(os.path.join(ROOT, "nazo", "ballsim"))):
        m = re.match(r"published_(\w+)\.txt$", p)
        if not m:
            continue
        rows = [r for r in load(m.group(1)) if r["vis"] == "公開"]
        print("%s: 公開 %d 本" % (m.group(1), len(rows)))
        for i, r in enumerate(rows):
            for k, q in match(r["title"], rows[i + 1:]):
                print("  %s: %s(%s) と %s(%s)「%s」" % (k, r["id"], r["date"][5:], q["id"], q["date"][5:], r["title"][:40]))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "check":
        sys.exit(check(a[1], a[2])[0])
    elif len(a) >= 4 and a[0] == "add":
        add(a[1], a[2], a[3])
    elif a and a[0] == "audit":
        sys.exit(audit(a[1] if len(a) > 1 else os.path.join(ROOT, "nazo", "ballsim", "upload_queue.txt")))
    elif a and a[0] == "selfcheck":
        selfcheck()
    else:
        print(__doc__)
        sys.exit(2)
