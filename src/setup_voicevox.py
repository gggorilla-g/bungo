# setup_voicevox.py — core資材をGitHub Releasesから取得(actions/cacheで2回目以降スキップ)
import os, subprocess, sys, time

VER = "0.16.4"
ORT = "1.17.3"
A = "vv_assets"

def sh(cmd):
    subprocess.run(cmd, shell=True, check=True)

def fetch(url, out, retries=3):
    """DL成功(HTTP200かつ非空)を検証してから返す。失敗はリトライ。"""
    for i in range(retries):
        code = subprocess.run(
            f'curl -sL -w "%{{http_code}}" -o "{out}" "{url}"',
            shell=True, capture_output=True, text=True).stdout.strip()
        if code == "200" and os.path.getsize(out) > 1000:
            return
        print(f"DL失敗(code={code}, try={i+1}/{retries}): {url}")
        time.sleep(3)
    raise RuntimeError(f"ダウンロード失敗: {url}")

if os.path.exists(f"{A}/0.vvm"):
    print("vv_assets cached, skip")
    sys.exit(0)

os.makedirs(A, exist_ok=True)

# 1) ずんだもん音声モデル
fetch(f"https://github.com/VOICEVOX/voicevox_vvm/releases/download/{VER}/0.vvm", f"{A}/0.vvm")

# 2) ONNXランタイム
fetch(f"https://github.com/VOICEVOX/onnxruntime-builder/releases/download/"
      f"voicevox_onnxruntime-{ORT}/voicevox_onnxruntime-linux-x64-{ORT}.tgz", f"{A}/ort.tgz")
sh(f"tar xzf {A}/ort.tgz -C {A}")

# 3) Open JTalk辞書(UTF-8)
fetch("https://github.com/r9y9/open_jtalk/releases/download/v1.11.1/"
      "open_jtalk_dic_utf_8-1.11.tar.gz", f"{A}/dic.tar.gz")
sh(f"tar xzf {A}/dic.tar.gz -C {A}")

# 検証: 必須ファイルが揃ったか
need = [f"{A}/0.vvm", f"{A}/open_jtalk_dic_utf_8-1.11",
        f"{A}/voicevox_onnxruntime-linux-x64-{ORT}"]
for p in need:
    if not os.path.exists(p):
        raise RuntimeError(f"資材が欠落: {p}")
print("vv_assets ready")
