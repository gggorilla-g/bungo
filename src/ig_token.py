# ig_token.py — Instagramトークン（60日で失効）の自動延長
#   延長したトークンは state/ig_token.enc に暗号化して保存する（リポジトリはPublicなので平文は置かない）。
#   暗号鍵は Secrets の IG_TOKEN（初回に登録したトークン）から作るので、追加のSecretは不要。
#   IG_TOKEN を新しく登録し直した場合は鍵が変わる → 古い暗号ファイルは読めず、新しい IG_TOKEN から再出発する。
import base64, hashlib, os, requests
from cryptography.fernet import Fernet, InvalidToken

ENC = "state/ig_token.enc"

def _f():
    seed = os.environ["IG_TOKEN"].encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"bungo-ig:" + seed).digest()))

def get():
    """使うべき現在のトークン（延長済みがあればそれ、無ければ登録時のもの）"""
    if os.path.exists(ENC):
        try:
            return _f().decrypt(open(ENC, "rb").read()).decode()
        except InvalidToken:
            print("保存トークンが読めない（IG_TOKENが登録し直された）。登録時のトークンを使う")
    return os.environ["IG_TOKEN"]

def refresh():
    """延長して保存。発行から24時間未満などで延長できない時は現状維持"""
    r = requests.get("https://graph.instagram.com/refresh_access_token", params={
        "grant_type": "ig_refresh_token", "access_token": get()}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"延長失敗 {r.status_code} {r.text[:300]}")
    j = r.json()
    open(ENC, "wb").write(_f().encrypt(j["access_token"].encode()))
    print(f"トークン延長: 残り約{int(j.get('expires_in', 0)) // 86400}日")

if __name__ == "__main__":
    refresh()
