# setup_voicevox.py — core資材をGitHub Releasesから取得(actions/cacheで2回目以降スキップ)
import os, subprocess, sys

VER = "0.16.4"
ORT = "1.17.3"
A = "vv_assets"

def sh(cmd): subprocess.run(cmd, shell=True, check=True)

if os.path.exists(f"{A}/0.vvm"):
    print("vv_assets cached, skip")
    sys.exit(0)

os.makedirs(A, exist_ok=True)
base = f"https://github.com/VOICEVOX/voicevox_vvm/releases/download/{VER}"
sh(f"curl -sL -o {A}/0.vvm {base}/0.vvm")  # ずんだもん(スタイル3)を含むモデル
sh(f"curl -sL -o {A}/ort.tgz https://github.com/VOICEVOX/onnxruntime-builder/releases/download/voicevox_onnxruntime-{ORT}/voicevox_onnxruntime-linux-x64-{ORT}.tgz && tar xzf {A}/ort.tgz -C {A}")
sh(f"curl -sL -o {A}/dic.tar.gz https://github.com/jpreprocess/open_jtalk/releases/download/v1.11.3/open_jtalk_dic_utf_8-1.11.tar.gz && tar xzf {A}/dic.tar.gz -C {A}")
print("vv_assets ready")
