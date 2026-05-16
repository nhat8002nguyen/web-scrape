#!/usr/bin/env bash
# Copy this repo to one or more EC2 Ubuntu hosts (adjust SSH_KEY / env / arguments).
set -euo pipefail

REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_HOST="${REMOTE_HOST:-ec2-13-250-60-93.ap-southeast-1.compute.amazonaws.com}"
REMOTE_DIR="${REMOTE_DIR:-~/kyle-insta-video-transcripts}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--help] [user@host ...]

Sync this directory to one or more hosts (default remote dir: ~/kyle-insta-video-transcripts).

Examples:
  $(basename "$0") ubuntu@ec2-47-128-222-232.ap-southeast-1.compute.amazonaws.com
  $(basename "$0") ubuntu@host1 ubuntu@host2
  $(basename "$0") ec2-1.example.com ec2-2.example.com   # uses REMOTE_USER (default ubuntu)

If no hosts are given, uses REMOTE_USER and REMOTE_HOST from the environment (or script defaults).

Env: SSH_KEY, REMOTE_USER, REMOTE_HOST, REMOTE_DIR
EOF
}

TARGETS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h | --help)
      usage
      exit 0
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

# PEM path: set SSH_KEY or place video-transcripts-server.pem next to this script / cwd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${SSH_KEY:-}" ]]; then
  PEM="$SSH_KEY"
elif [[ -f "${SCRIPT_DIR}/video-transcripts-server.pem" ]]; then
  PEM="${SCRIPT_DIR}/video-transcripts-server.pem"
elif [[ -f "./video-transcripts-server.pem" ]]; then
  PEM="$(pwd)/video-transcripts-server.pem"
else
  echo "error: set SSH_KEY to your .pem path or copy video-transcripts-server.pem into:" >&2
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
  --exclude '__pycache__/'
  --exclude '*.py[cod]'
  --exclude '.git/'
  --exclude 'output/videos/'
  --exclude 'output/transcripts/'
  --exclude 'output/metadata/'
  --exclude 'output/skipped.jsonl'
  --exclude 'output/checkpoint.json'
  --exclude '.env'
  --exclude 'cookies.json'
)

for ssh_target in "${SSH_TARGETS[@]}"; do
  echo "Syncing ${SCRIPT_DIR}/ -> ${ssh_target}:${REMOTE_DIR}"
  rsync -avz --delete \
    "${RSYNC_EXCLUDES[@]}" \
    -e "ssh -i ${PEM} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
    "${SCRIPT_DIR}/" \
    "${ssh_target}:${REMOTE_DIR}/"
  echo ""
done

echo "Done. On each instance:"
echo "  cd ${REMOTE_DIR} && python3 -m venv .venv && source .venv/bin/activate"
echo "  pip install --upgrade pip && pip install -r requirements.txt"
echo "  sudo apt update && sudo apt install -y ffmpeg   # if not already installed"
echo "  cp .env.example .env   # then edit .env; copy cookies.json if needed"
echo "  python instagram_reels_transcripts.py ... --out ./output --verbose"
