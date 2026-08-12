# m2_extract.py — 本文取得と正規化(汎用版)
import re, requests

UA = {"User-Agent": "BUNGO/0.1 (automated literature channel)"}

def fetch_text(xhtml_url):
    # 本家URL→GitHubミラーに変換して負荷を逃がす
    url = xhtml_url.replace("https://www.aozora.gr.jp/",
        "https://raw.githubusercontent.com/aozorabunko/aozorabunko/master/")
    raw = requests.get(url, headers=UA, timeout=60).content.decode("shift_jis", errors="replace")
    m = re.search(r'<div class="main_text">(.*?)</div>', raw, re.S)
    body = m.group(1)
    ruby = {}
    for base, yomi in re.findall(
            r'<ruby><rb>(.*?)</rb><rp>（</rp><rt>(.*?)</rt><rp>）</rp></ruby>', body):
        ruby.setdefault(base, yomi)
    body = re.sub(r'<ruby><rb>(.*?)</rb><rp>（</rp><rt>.*?</rt><rp>）</rp></ruby>', r'\1', body)
    body = re.sub(r'<[^>]+>', '', body)
    body = re.sub(r'［＃[^］]*］', '', body)
    body = re.sub(r'\r\n', '\n', body)
    body = re.sub(r'\n{3,}', '\n\n', body).strip()
    return body, ruby
