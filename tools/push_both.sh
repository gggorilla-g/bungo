#!/bin/bash
# push_both.sh — コミット済みの変更を kaizo3d-fridge に push し、main にも取りこんで push する（作業フォルダは切りかえない）
#   使い方：git add … && git commit … のあとに tools/push_both.sh
set -e
cd "$(dirname "$0")/.."
git pull -q --rebase origin kaizo3d-fridge
git push -q origin kaizo3d-fridge
git fetch -q origin main
if git merge-base --is-ancestor origin/main HEAD; then git push -q origin HEAD:main; echo "両方に反映した（main は早送り）"; exit 0; fi
if git merge-base --is-ancestor HEAD origin/main; then echo "両方に反映した（main はすでに含んでいる）"; exit 0; fi
T="$(git merge-tree --write-tree origin/main HEAD)" || { echo "main との取りこみで食いちがい。手で直す"; exit 1; }
C="$(git -c user.name="${GIT_AUTHOR_NAME:-$(git config user.name || echo bot)}" -c user.email="${GIT_AUTHOR_EMAIL:-$(git config user.email || echo bot@example.com)}" commit-tree "$T" -p origin/main -p HEAD -m "Merge kaizo3d-fridge into main")"
git push -q origin "$C:refs/heads/main"
echo "両方に反映した（main に取りこみ）"
