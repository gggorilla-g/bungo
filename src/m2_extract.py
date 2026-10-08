# m2_extract.py — 本文取得と正規化
# 返り値: (本文, ルビ辞書)
#   本文     : ルビを外した表示用テキスト（台本生成・引用照合に使う）
#   ルビ辞書 : {親文字: {読み: 出現回数}} — 作品内で読みが割れている語を検出できる形
import re, requests

UA = {"User-Agent": "BUNGO/0.2 (automated literature channel)"}
RUBY_RE = re.compile(r'<ruby><rb>(.*?)</rb><rp>（</rp><rt>(.*?)</rt><rp>）</rp></ruby>', re.S)
GAIJI_RE = re.compile(r'<img[^>]*class="gaiji"[^>]*/?>')


def _expand_odoriji(s):
    """くの字点（／＼ ／″＼）と一の字点（ゝゞヽヾ）を展開する。
    台本生成と引用照合で記号のまま残ると誤読・照合漏れの原因になるため。"""
    def kunoji(m):
        prev = m.string[max(0, m.start() - 2):m.start()]
        if m.group(0) == "／″＼" and prev:
            return _dakuten(prev[0]) + prev[1:]
        return prev
    s = re.sub(r'／″?＼', kunoji, s)
    out = []
    for ch in s:
        if ch in "ゝヽ" and out:
            out.append(out[-1])
        elif ch in "ゞヾ" and out:
            out.append(_dakuten(out[-1]))
        else:
            out.append(ch)
    return "".join(out)


def _dakuten(ch):
    t = str.maketrans("かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホ",
                      "がぎぐげござじずぜぞだぢづでどばびぶべぼガギグゲゴザジズゼゾダヂヅデドバビブベボ")
    return ch.translate(t)


def parse(raw_html):
    m = re.search(r'<div class="main_text">(.*?)</div>', raw_html, re.S)
    if not m:
        raise RuntimeError("本文ブロック(main_text)が見つからない")
    body = m.group(1)
    ruby = {}
    for base, yomi in RUBY_RE.findall(body):
        base = re.sub(r'<[^>]+>', '', base)
        yomi = re.sub(r'<[^>]+>', '', yomi)
        ruby.setdefault(base, {})
        ruby[base][yomi] = ruby[base].get(yomi, 0) + 1
    body = RUBY_RE.sub(r'\1', body)
    body = GAIJI_RE.sub('〓', body)            # 外字は〓に（引用照合で〓を含む引用は不合格にする）
    body = re.sub(r'<br\s*/?>', '\n', body)
    body = re.sub(r'<[^>]+>', '', body)
    body = re.sub(r'［＃[^］]*］', '', body)
    body = body.replace('\r\n', '\n')
    body = _expand_odoriji(body)
    body = re.sub(r'\n{3,}', '\n\n', body).strip()
    return body, ruby


def fetch_text(xhtml_url):
    # GitHubミラー優先（本家の負荷を逃がす）、だめなら本家
    mirror = xhtml_url.replace("https://www.aozora.gr.jp/",
        "https://raw.githubusercontent.com/aozorabunko/aozorabunko/master/")
    data = None
    for url in (mirror, xhtml_url):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200 and b"main_text" in r.content:
                data = r.content; break
        except requests.RequestException:
            pass
    if data is None:
        raise RuntimeError(f"本文を取得できない: {xhtml_url}")
    enc = "utf-8" if re.search(rb'charset="?utf-8', data[:2000], re.I) else "cp932"
    raw = data.decode(enc, errors="replace")
    if raw.count("�") > 5:
        raise RuntimeError("本文の文字化けが多い（文字コード不一致の疑い）")
    return parse(raw)
