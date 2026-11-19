#!/bin/bash
# upq.sh — 順番待ちの投稿を上から上げる。1日の上限に当たったチャンネルは、その回は飛ばして残す
#   順番待ち: nazo/ballsim/upload_queue.txt（1行 = "<id> <MOSO|KAIDAN|NAZO> <ja|en>"）。済んだ行は upload_done.txt へ移す
cd "$(dirname "$0")/.."
Q=nazo/ballsim/upload_queue.txt; D=nazo/ballsim/upload_done.txt; touch "$Q" "$D"
declare -A full; for c in $SKIP; do full[$c]=1; done   # SKIP="MOSO" で、そのチャンネルを今回は飛ばす
cp "$Q" "$Q.tmp"; : > "$Q.keep"
while read -r id ch lg; do
  [ -z "$id" ] && continue
  if [ -n "${full[$ch]}" ] || [ ! -f "output/$id.mp4" ] || [ ! -f "nazo/manual/ballsim/${id}_upload.txt" ]; then echo "$id $ch $lg" >> "$Q.keep"; continue; fi
  out="$(tools/up.sh "$id" "nazo/manual/ballsim/${id}_upload.txt" "YT_REFRESH_TOKEN_$ch" "$lg" 1 2>&1 | grep -v '^fatal: expected')"
  echo "$out" | tail -1
  if echo "$out" | grep -q " success "; then echo "$(date -u +%FT%TZ) $out" | tail -1 >> "$D"
  else echo "$id $ch $lg" >> "$Q.keep"; echo "$out" | grep -q "exceeded the number of videos" && { full[$ch]=1; echo "上限: $ch はあとで"; }; fi
done < "$Q.tmp"
mv "$Q.keep" "$Q"; rm -f "$Q.tmp"; echo "残り $(wc -l < "$Q") 本"
