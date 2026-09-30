#!/usr/bin/env bash
# release.sh -- TRVVTH automated release.
# Runs the test suite, rebuilds sdist+wheel, commits, and tags.
# Usage: ./release.sh "short description of what changed"
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -lt 1 ]; then
  echo "usage: ./release.sh \"what changed\"" >&2
  exit 1
fi

PY="${PY:-.venv/bin/python}"
VER=$($PY -c "import trvvth; print(trvvth.__version__)")
echo "== TRVVTH v$VER =="

echo "-- tests (script-style: each file run directly, assert on failure)"
pass=0
for t in tests/test_*.py; do
  out=$($PY "$t" 2>&1) || { echo "FAIL: $t"; echo "$out" | tail -5; exit 1; }
  n=$(echo "$out" | grep -oE '[0-9]+ [a-z]+ tests passed' | grep -oE '^[0-9]+' || true)
  pass=$((pass + ${n:-0}))
done
echo "all test files green ($pass checks)"

echo "-- build"
rm -rf dist/
$PY -m build -q
ls dist/

echo "-- commit + tag"
git add -A
git commit -qm "v$VER -- $1"
git tag -a "v$VER" -m "TRVVTH v$VER" 2>/dev/null || git tag -f -a "v$VER" -m "TRVVTH v$VER"
git log --oneline -2
git tag -l "v$VER"
echo "done. To publish: git push origin main --tags"
