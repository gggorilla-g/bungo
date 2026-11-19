#!/bin/bash
# up.sh — ここで作った mp4 を up-<id> ブランチに置いて、upload_file.yml で YouTube に上げる
#   tools/up.sh <id> <キットのパス> <YT_REFRESH_TOKEN_MOSO|_KAIDAN|_NAZO> <ja|en> [no_voice=1] [publish_at(UTC)]
#   キットは先に kaizo3d-fridge へ push しておくこと。結果の動画IDを最後に出す
set -e
ID="$1"; KIT="$2"; TOKEN="$3"; LANGC="${4:-ja}"; NOVOICE="${5:-1}"; PUB="${6:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; URL="$(git -C "$ROOT" remote get-url origin)"
T="$(mktemp -d)"; cp "$ROOT/output/$ID.mp4" "$T/"
( cd "$T" && git init -q && git checkout -q -b "up-$ID" && git add "$ID.mp4" && git -c user.name=bot -c user.email=bot@example.com commit -qm up && git remote add origin "$URL" && git push -q -f origin "up-$ID" 2>&1 | grep -v -e "^remote:" -e "negotiation" || true )
git -C "$ROOT" ls-remote origin "up-$ID" | grep -q . || { echo "ブランチの push に失敗: up-$ID"; exit 1; }
cd "$ROOT"
BEFORE="$(gh run list --workflow upload_file.yml -L 1 --json databaseId -q '.[0].databaseId')"
gh workflow run upload_file.yml --ref kaizo3d-fridge -f id="$ID" -f kit="$KIT" -f token="$TOKEN" -f publish_at="$PUB" -f lang="$LANGC" -f no_voice="$NOVOICE" >/dev/null
for i in $(seq 1 20); do sleep 3; R="$(gh run list --workflow upload_file.yml -L 1 --json databaseId -q '.[0].databaseId')"; [ "$R" != "$BEFORE" ] && break; done
gh run watch "$R" --exit-status >/dev/null 2>&1 || true
C="$(gh run view "$R" --json conclusion -q .conclusion)"
V="$(gh run view "$R" --log 2>/dev/null | grep -oE '"id": "[^"]+"' | head -1 | sed 's/"id": "//; s/"//')"
echo "$ID $C $V (run $R)"
[ "$C" = "success" ] || { gh run view "$R" --log-failed 2>/dev/null | grep -iE "quota|error|Traceback|HttpError" | tail -5 | cut -c1-300; exit 1; }
