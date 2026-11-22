#!/bin/bash
# upq.sh — 順番待ちの投稿を上から上げる。1日の上限に当たったチャンネルは、その回は飛ばして残す
#   順番待ち: nazo/ballsim/upload_queue.txt（1行 = "<id> <MOSO|KAIDAN|NAZO> <ja|en>"）。済んだ行は upload_done.txt へ移す
cd "$(dirname "$0")/.."
Q=nazo/ballsim/upload_queue.txt; D=nazo/ballsim/upload_done.txt; touch "$Q" "$D"
declare -A full; declare -A cnt; for c in $SKIP; do full[$c]=1; done   # SKIP="MOSO" で、そのチャンネルを今回は飛ばす
MAX=${MAX:-99}   # MAX=1 なら、1回の実行で各チャンネル1本まで（11/23：連続投稿の後半は配信されないため、間をあけて出す）
cp "$Q" "$Q.tmp"; : > "$Q.keep"
while read -r id ch lg; do
  [ -z "$id" ] && continue
  if [ -n "${full[$ch]}" ] || [ ! -f "output/$id.mp4" ] || [ ! -f "nazo/manual/ballsim/${id}_upload.txt" ]; then echo "$id $ch $lg" >> "$Q.keep"; continue; fi
  if [ "${cnt[$ch]:-0}" -ge "$MAX" ]; then echo "$id $ch $lg" >> "$Q.keep"; continue; fi
  up="$id"
  if [ "${TEASER:-1}" = 1 ] && [ ! -f "output/${id}_t.mp4" ]; then   # 冒頭に結末の一瞬（teaser.py）。終わり3.2秒前の1秒を使う
    d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "output/$id.mp4"); at=$(python3 -c "print(max(0, $d - 3.2))")
    python3 tools/teaser.py "output/$id.mp4" "output/${id}_t.mp4" "$at" 1.0 >/dev/null
  fi
  [ -f "output/${id}_t.mp4" ] && up="${id}_t"
  out="$(tools/up.sh "$up" "nazo/manual/ballsim/${id}_upload.txt" "YT_REFRESH_TOKEN_$ch" "$lg" 1 2>&1 | grep -v '^fatal: expected')"
  echo "$out" | tail -1
  if echo "$out" | grep -q " success "; then echo "$(date -u +%FT%TZ) $out" | tail -1 >> "$D"; cnt[$ch]=$(( ${cnt[$ch]:-0} + 1 ))
  else echo "$id $ch $lg" >> "$Q.keep"; echo "$out" | grep -q "exceeded the number of videos" && { full[$ch]=1; echo "上限: $ch はあとで"; }; fi
done < "$Q.tmp"
grep -vxFf "$Q.tmp" "$Q" >> "$Q.keep" 2>/dev/null   # 走っている間に足された行は残す
mv "$Q.keep" "$Q"; rm -f "$Q.tmp"; echo "残り $(wc -l < "$Q") 本"
