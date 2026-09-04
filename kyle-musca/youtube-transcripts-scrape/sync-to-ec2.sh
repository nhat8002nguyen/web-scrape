#!/usr/bin/env bash
# Copy this repo to one or more EC2 Ubuntu hosts (adjust SSH_KEY / env / arguments).
#
# Remote layout (same EC2 host, separate folders — do not share REMOTE_DIR with siblings):
#   ~/kyle-insta-video-transcripts      <- insta-video-transcripts/sync-to-ec2.sh
#   ~/kyle-ad-library-video-transcripts <- ad-library-video-transcripts/sync-to-ec2.sh
#   ~/youtube-transcripts-scrape        <- this script (default)
set -euo pipefail

REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_HOST="${REMOTE_HOST:-ec2-13-250-60-93.ap-southeast-1.compute.amazonaws.com}"
INSTAGRAM_REMOTE_DIR="${INSTAGRAM_REMOTE_DIR:-~/kyle-insta-video-transcripts}"
AD_LIBRARY_REMOTE_DIR="${AD_LIBRARY_REMOTE_DIR:-~/kyle-ad-library-video-transcripts}"
REMOTE_DIR="${REMOTE_DIR:-~/youtube-transcripts-scrape}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--help] [--with-transcripts] [user@host ...]

Sync this directory to one or more hosts (default remote dir: ~/youtube-transcripts-scrape).
Includes .env and cookies.txt when present locally. Instagram / Ad Library folders are left unchanged.

Examples:
  $(basename "$0") ubuntu@ec2-47-128-222-232.ap-southeast-1.compute.amazonaws.com
  $(basename "$0") ubuntu@host1 ubuntu@host2
  $(basename "$0") --with-transcripts   # also sync transcripts/ (for --resume / skipped.jsonl)
  $(basename "$0") ec2-1.example.com    # uses REMOTE_USER (default ubuntu)

If no hosts are given, uses REMOTE_USER and REMOTE_HOST from the environment (or script defaults).

Env: SSH_KEY, REMOTE_USER, REMOTE_HOST, REMOTE_DIR, INSTAGRAM_REMOTE_DIR, AD_LIBRARY_REMOTE_DIR
EOF
}

normalize_remote_dir() {
  local dir="$1"
  if [[ "$dir" == "~/"* ]]; then
    echo "${HOME}/${dir:2}"
  elif [[ "$dir" == "~" ]]; then
    echo "${HOME}"
  else
    echo "$dir"
  fi
}

assert_not_sibling_remote_dir() {
  local target resolved_instagram resolved_ad_library
  target="$(normalize_remote_dir "$1")"
  resolved_instagram="$(normalize_remote_dir "${INSTAGRAM_REMOTE_DIR}")"
  resolved_ad_library="$(normalize_remote_dir "${AD_LIBRARY_REMOTE_DIR}")"
  if [[ "$target" == "$resolved_instagram" ]]; then
    echo "error: REMOTE_DIR points at the Instagram project folder:" >&2
    echo "  ${INSTAGRAM_REMOTE_DIR}" >&2
    echo "  YouTube must sync elsewhere (default: ~/youtube-transcripts-scrape)." >&2
    exit 1
  fi
  if [[ "$target" == "$resolved_ad_library" ]]; then
    echo "error: REMOTE_DIR points at the Ad Library project folder:" >&2
    echo "  ${AD_LIBRARY_REMOTE_DIR}" >&2
    echo "  YouTube must sync elsewhere (default: ~/youtube-transcripts-scrape)." >&2
    exit 1
  fi
}

WITH_TRANSCRIPTS=0
TARGETS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h | --help)
      usage
      exit 0
      ;;
    --with-transcripts)
      WITH_TRANSCRIPTS=1
      shift
      ;;
    *)
      TARGETS+=("$1")
      shift
      ;;
  esac
done

normalize_ssh_target() {
  local t="$1"
  if [[ "$t" == *@* ]]; then
    echo "$t"
  else
    echo "${REMOTE_USER}@${t}"
  fi
}

# PEM path: set SSH_KEY or place video-transcripts-server.pem / crawler1.pem next to this script / cwd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${SSH_KEY:-}" ]]; then
  PEM="$SSH_KEY"
elif [[ -f "${SCRIPT_DIR}/video-transcripts-server.pem" ]]; then
  PEM="${SCRIPT_DIR}/video-transcripts-server.pem"
elif [[ -f "./video-transcripts-server.pem" ]]; then
  PEM="$(pwd)/video-transcripts-server.pem"
elif [[ -f "${SCRIPT_DIR}/crawler1.pem" ]]; then
  PEM="${SCRIPT_DIR}/crawler1.pem"
elif [[ -f "./crawler1.pem" ]]; then
  PEM="$(pwd)/crawler1.pem"
else
  echo "error: set SSH_KEY to your .pem path or copy video-transcripts-server.pem (or crawler1.pem) into:" >&2
  echo "  ${SCRIPT_DIR}/  or current directory" >&2
  exit 1
fi

chmod 400 "$PEM" 2>/dev/null || true

if ! command -v rsync >/dev/null 2>&1; then
  echo "error: rsync not found. Install rsync (e.g. brew install rsync on macOS)." >&2
  exit 1
fi

declare -a SSH_TARGETS=()
if [[ ${#TARGETS[@]} -eq 0 ]]; then
  SSH_TARGETS+=("$(normalize_ssh_target "${REMOTE_HOST}")")
else
  for t in "${TARGETS[@]}"; do
    SSH_TARGETS+=("$(normalize_ssh_target "$t")")
  done
fi

RSYNC_EXCLUDES=(
  --exclude '.venv/'
  --exclude '.venv-desktop-build/'
  --exclude 'build/'
  --exclude 'dist/'
  --exclude '.tmp-build-test/'
  --exclude '__pycache__/'
  --exclude '*.py[cod]'
  --exclude '.git/'
  --exclude 'videos/'
  --exclude '**/videos/'
  --exclude 'logs/'
  --exclude '*.pem'
  --exclude 'Webshare*.txt'
  --exclude '*proxies*.txt'
  --exclude '.DS_Store'
)

if [[ "$WITH_TRANSCRIPTS" -eq 0 ]]; then
  RSYNC_EXCLUDES+=(--exclude 'transcripts/')
fi

# .env and cookies.txt are synced when present (needed for EC2 caption + Whisper runs).
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  echo "including .env"
else
  echo "warning: ${SCRIPT_DIR}/.env not found; caption scrape on EC2 usually needs Webshare/TRANSCRIPT_PROXY." >&2
fi
if [[ -f "${SCRIPT_DIR}/cookies.txt" ]]; then
  echo "including cookies.txt"
else
  echo "warning: ${SCRIPT_DIR}/cookies.txt not found; Whisper downloads on EC2 usually need it (export from browser)." >&2
fi

assert_not_sibling_remote_dir "${REMOTE_DIR}"

for ssh_target in "${SSH_TARGETS[@]}"; do
  echo "Syncing ${SCRIPT_DIR}/ -> ${ssh_target}:${REMOTE_DIR}"
  echo "  (Instagram ${INSTAGRAM_REMOTE_DIR} and Ad Library ${AD_LIBRARY_REMOTE_DIR} are left unchanged)"
  if [[ "$WITH_TRANSCRIPTS" -eq 1 ]]; then
    echo "  including transcripts/ (media under **/videos/ still excluded)"
  else
    echo "  excluding transcripts/ (pass --with-transcripts to sync skipped.jsonl + .txt for --resume)"
  fi
  rsync -avz --delete \
    "${RSYNC_EXCLUDES[@]}" \
    -e "ssh -i ${PEM} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
    "${SCRIPT_DIR}/" \
    "${ssh_target}:${REMOTE_DIR}/"
  echo ""
done

echo "Done. On each instance:"
echo "  cd ${REMOTE_DIR}"
echo "  ./scripts/ec2_setup_and_run.sh setup   # or: python3 -m venv .venv && pip install -r requirements.txt"
echo "  sudo apt update && sudo apt install -y ffmpeg nodejs   # ffmpeg + Node for yt-dlp JS challenges"
echo ""
echo "  # Caption scrape (option 1):"
echo "  ./scripts/ec2_setup_and_run.sh run --detach -- \\"
echo "    \"https://www.youtube.com/@YourChannel\" --out ./transcripts/CHANNEL --resume"
echo ""
echo "  # Whisper skipped videos (option 2) — uses synced cookies.txt when present:"
echo "  source .venv/bin/activate"
echo "  python whisper_skipped_transcripts.py \\"
echo "    --skip-log ./transcripts/CHANNEL/skipped.jsonl \\"
echo "    --out ./transcripts/CHANNEL \\"
echo "    --download-dir videos \\"
echo "    --cookies ./cookies.txt \\"
echo "    --resume --verbose"
