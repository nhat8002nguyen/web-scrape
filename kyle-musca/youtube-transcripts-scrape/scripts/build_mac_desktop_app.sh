#!/usr/bin/env bash
# Build a standalone macOS .app (includes Python + dependencies). Run on a Mac.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "This script must run on macOS." >&2
  exit 1
fi

python3 -m venv .venv-desktop-build
# shellcheck disable=SC1091
source .venv-desktop-build/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-desktop-build.txt

rm -rf build dist
python -m PyInstaller youtube_transcripts_gui.spec

echo ""
echo "Built: dist/YouTube Transcripts.app"
echo "First run: if macOS blocks it, right-click → Open, or System Settings → Privacy & Security."
