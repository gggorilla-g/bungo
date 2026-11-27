#!/usr/bin/env python3
"""release.py — 見本を見せた動画を、公開予約つきで上げる（docs/trend-pipeline.md の「6 上げる」）

  python3 tools/trend/release.py [--at 2026-11-28T12:00:00Z | --now] [--only <id のはじめの文字>] [--dry]
    --only：持ち主が先に「上げていい」と言った動画だけを上げる時に使う（ほかは順番待ちに残る）

順番待ち：nazo/trend/queue.jsonl（1行1本）
  {"id": "tiles1_ja", "kit": "nazo/manual/tiles/tiles1_ja_upload.txt", "ch": "MOSO", "lang": "ja", "build": "python3 tools/tiles.py all", "shown": "2026-11-27"}
  ch は MOSO（妄想科学）か KAIDAN（Make It Work 3D）。英語版の build は頭に LANG_OUT=en を書く
  "echo": true を足すと、検査で余韻（エコー）を見ない。合体の型だけ（持ち主 11/27「これ系のやつは心地よい音にエコーたしていい」）

1本ずつ、次の順でする
  0. nazo/trend/hold.txt に id がある動画は上げない（順番待ちからも外す）
  1. output/<id>.mp4 が無いか、道具（tools/trendkit.py・tools/kalimba.py・build に出てくる tools/*.py）より古ければ、build で作り直す
  2. tools/trend/check.py を通す。NG なら上げずに残す
  3. tools/up.sh で上げる。公開は「今日の 21:00 JST」の予約（それまでは非公開）。20:55 を過ぎていたら、すぐ公開。--at で時刻を指定、--now ですぐ公開
  4. 上がったら順番待ちから外し、nazo/ballsim/upload_done.txt と docs/video-ledger.md に1行ずつ足す
1日の上限に当たったチャンネルは、その回はそこで止めて残す（次の回に回る）。
持ち主が「だめ」と言った動画・直しの指摘が来た動画は、上げる前に nazo/trend/hold.txt に「id 理由」を1行書く（この道具ではなく手でする）。直して出し直す時は、その行を消してから順番待ちに入れ直す。
"""
import datetime, json, os, subprocess, sys
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
Q = os.path.join(ROOT, "nazo", "trend", "queue.jsonl")

def default_at():
    """今日の 21:00 JST（UTC の書き方で返す）。20:55 を過ぎていたら空文字＝すぐ公開"""
    now = datetime.datetime.now(ZoneInfo("Asia/Tokyo")); t = datetime.datetime.combine(now.date(), datetime.time(21, 0), ZoneInfo("Asia/Tokyo"))
    return "" if now > t - datetime.timedelta(minutes=5) else t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def stale(mp4, build):
    """音や絵の道具を直したあとに、前の版の動画を上げてしまわないための確認"""
    src = [os.path.join(ROOT, "tools", "trendkit.py"), os.path.join(ROOT, "tools", "kalimba.py")] + [os.path.join(ROOT, w) for w in build.split() if w.startswith("tools/") and w.endswith(".py")]
    return any(os.path.exists(x) and os.path.getmtime(x) > os.path.getmtime(mp4) for x in src)

def held():
    hp = os.path.join(ROOT, "nazo", "trend", "hold.txt")
    return {l.split()[0] for l in open(hp, encoding="utf-8") if l.strip() and not l.startswith("#")} if os.path.exists(hp) else set()

def main():
    at = "" if "--now" in sys.argv else sys.argv[sys.argv.index("--at") + 1] if "--at" in sys.argv else default_at(); dry = "--dry" in sys.argv
    rows = [json.loads(l) for l in open(Q, encoding="utf-8") if l.strip()] if os.path.exists(Q) else []
    keep = []; full = set(); done = []; hold = held(); only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    jst = datetime.datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).astimezone(ZoneInfo("Asia/Tokyo")) if at else datetime.datetime.now(ZoneInfo("Asia/Tokyo"))
    when = f"{jst:%m/%d %H:%M} JST に公開予約" if at else "すぐ公開"
    print(f"公開：{when} 順番待ち {len(rows)} 本")
    for r in rows:
        vid, ch = r["id"], r["ch"]; mp4 = os.path.join(ROOT, "output", vid + ".mp4")
        if vid in hold: print(f"外す：{vid}（hold.txt にある＝持ち主が止めた）"); continue
        if only and not vid.startswith(only): keep.append(r); continue
        if ch in full: keep.append(r); print(f"残す：{vid}（{ch} は上限）"); continue
        if not os.path.exists(mp4) or stale(mp4, r["build"]):
            print(f"作り直す：{vid}（{r['build']}）", flush=True); subprocess.run(r["build"], shell=True, cwd=ROOT, stdin=subprocess.DEVNULL)
        if not os.path.exists(mp4): keep.append(r); print(f"残す：{vid}（動画が作れなかった）"); continue
        c = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "trend", "check.py"), mp4] + (["--echo"] if r.get("echo") else []), cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True)
        if c.returncode != 0: keep.append(r); print(f"残す：{vid}（検査で NG）\n" + "\n".join(l for l in c.stdout.splitlines() if l.startswith("NG"))); continue
        if dry: keep.append(r); print(f"（試し）上げる：{vid} → {ch}"); continue
        u = subprocess.run([os.path.join(ROOT, "tools", "up.sh"), vid, r["kit"], "YT_REFRESH_TOKEN_" + ch, r.get("lang", "ja"), "1", at], cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True)
        out = (u.stdout + u.stderr); ok = [l for l in out.splitlines() if " success " in l]
        if ok:
            yt = ok[-1].split(" success ")[1].split()[0]; done.append((vid, ch, yt)); print(f"上げた：{vid} → {ch} {yt}（{when}）")
            with open(os.path.join(ROOT, "nazo", "ballsim", "upload_done.txt"), "a", encoding="utf-8") as f: f.write(f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {vid} success {yt} (trend、{when})\n")
            with open(os.path.join(ROOT, "docs", "video-ledger.md"), "a", encoding="utf-8") as f: f.write(f"- {jst:%Y-%m-%d} {'妄想' if ch == 'MOSO' else 'MIW'} {vid} {yt}（trend の流れ。{when}、見本は {r.get('shown', '?')} に送付）\n")
        else:
            keep.append(r)
            if "exceeded the number of videos" in out: full.add(ch); print(f"残す：{vid}（{ch} は1日の上限。次の回に回す）")
            elif "重複" in out: print(f"残す：{vid}（同じ題名がもう出ている）")
            else: print(f"残す：{vid}（上げるのに失敗）\n" + "\n".join(out.splitlines()[-4:]))
    if not dry:
        with open(Q, "w", encoding="utf-8") as f:
            for r in keep: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"結果：上げた {len(done)} 本、残り {len(keep)} 本"); return 0

if __name__ == "__main__":
    sys.exit(main())
