#!/bin/bash
# up.sh — ここで作った mp4 を up-<id> ブランチに置いて、upload_file.yml で YouTube に上げる
#   tools/up.sh <id> <キットのパス> <YT_REFRESH_TOKEN_MOSO|_KAIDAN|_NAZO> <ja|en> [no_voice=1] [publish_at(UTC)]
#   環境変数 KIDS=1（子ども向け）、THUMB=<リポジトリ内のサムネ>
#   キットは先に kaizo3d-fridge へ push しておくこと。結果の動画IDを最後に出す
set -e
ID="$1"; KIT="$2"; TOKEN="$3"; LANGC="${4:-ja}"; NOVOICE="${5:-1}"; PUB="${6:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; URL="$(git -C "$ROOT" remote get-url origin)"
# 同じチャンネルに同じ題名がもう公開されていたら上げない（11/25 持ち主「同じのあげてんじゃん」）。台帳は nazo/ballsim/published_<チャンネル>.txt
#   わざと同じ題名で出し直すときだけ ALLOW_DUP=1。終了コード3 = 重複で止めた
case "$KIT" in /*) KP="$KIT";; *) KP="$ROOT/$KIT";; esac
TAG="${TOKEN#YT_REFRESH_TOKEN}"; TAG="${TAG#_}"; [ -z "$TAG" ] && TAG=ZATSU
if [ -z "$ALLOW_DUP" ] && [ -f "$KP" ]; then python3 "$ROOT/tools/dupcheck.py" check "$KP" "$TAG" || exit 3; fi
T="$(mktemp -d)"; cp "$ROOT/output/$ID.mp4" "$T/"
# GitHub は1ファイル100MBまで。超えるときは 90MB ずつに分けて置く（upload_file.yml がつなぎ直す）
[ "$(stat -c %s "$T/$ID.mp4")" -gt 95000000 ] && ( cd "$T" && split -b 90000000 -d "$ID.mp4" "$ID.mp4.part" && rm "$ID.mp4" )
( cd "$T" && git init -q && git checkout -q -b "up-$ID" && git add . && git -c user.name=bot -c user.email=bot@example.com commit -qm up && git remote add origin "$URL" && git push -q -f origin "up-$ID" 2>&1 | grep -v -e "^remote:" -e "negotiation" || true )
git -C "$ROOT" ls-remote origin "up-$ID" | grep -q . || { echo "ブランチの push に失敗: up-$ID"; exit 1; }
cd "$ROOT"
SEEN="$(gh run list --workflow upload_file.yml -L 20 --json databaseId -q '.[].databaseId' | sort)"
gh workflow run upload_file.yml --ref kaizo3d-fridge -f id="$ID" -f kit="$KIT" -f token="$TOKEN" -f publish_at="$PUB" -f lang="$LANGC" -f no_voice="$NOVOICE" -f kids="${KIDS:-}" -f thumb="${THUMB:-}" >/dev/null
R=""   # 新しく出てきた実行のうち、ログにこの動画IDがあるものを選ぶ
for i in $(seq 1 60); do
  sleep 5
  for c in $(gh run list --workflow upload_file.yml -L 10 --json databaseId -q '.[].databaseId'); do
    echo "$SEEN" | grep -qx "$c" && continue
    gh run view "$c" --log 2>/dev/null | grep -q "up-$ID\b\|/tmp/$ID.mp4" && { R="$c"; break; }
  done
  [ -n "$R" ] && break
done
[ -n "$R" ] || { echo "$ID 実行が見つからない"; exit 1; }
gh run watch "$R" --exit-status >/dev/null 2>&1 || true
C="$(gh run view "$R" --json conclusion -q .conclusion)"
V="$(gh run view "$R" --log 2>/dev/null | grep -oE '"id": "[^"]+"' | head -1 | sed 's/"id": "//; s/"//')"
echo "$ID $C $V (run $R)"
[ "$C" = "success" ] && [ -n "$V" ] && [ -f "$KP" ] && python3 "$ROOT/tools/dupcheck.py" add "$KP" "$TAG" "$V" || true   # 上がったら台帳に足す
[ "$C" = "success" ] || { gh run view "$R" --log-failed 2>/dev/null | grep -iE "quota|error|Traceback|HttpError" | tail -5 | cut -c1-300; exit 1; }
