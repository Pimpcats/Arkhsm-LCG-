#!/bin/bash
# One-click launcher — macOS (double-click) and Linux (./"Start CardForge.command")
cd "$(dirname "$0")" || exit 1

PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys;raise SystemExit(0 if sys.version_info>=(3,8) else 1)' 2>/dev/null; then
      PY="$c"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.8+ was not found. Install it from python.org, then double-click this again."
  read -r -p "Press Return to close..." _
  exit 1
fi

if ! "$PY" -c 'import PIL' >/dev/null 2>&1; then
  echo "First run: installing Pillow (image library)..."
  "$PY" -m pip install --quiet Pillow || {
    echo "Could not install Pillow. Try:  $PY -m pip install Pillow"
    read -r -p "Press Return to close..." _; exit 1; }
fi

URL="http://127.0.0.1:8570"
echo "Starting CardForge Studio at $URL"
( sleep 2
  if command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  fi ) >/dev/null 2>&1 &

"$PY" cardforge/studio.py
echo
read -r -p "CardForge stopped. Press Return to close..." _
