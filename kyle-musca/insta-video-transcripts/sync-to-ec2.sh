#!/usr/bin/env bash
# Copy this repo to one or more EC2 Ubuntu hosts (adjust SSH_KEY / env / arguments).
#
# Remote layout (same EC2 host, separate folders — do not share REMOTE_DIR with Ad Library):
#   ~/kyle-insta-video-transcripts      <- this script (default)
#   ~/kyle-ad-library-video-transcripts <- ad-library-video-transcripts/sync-to-ec2.sh
set -euo pipefail

REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_HOST="${REMOTE_HOST:-ec2-13-250-60-93.ap-southeast-1.compute.amazonaws.com}"
AD_LIBRARY_REMOTE_DIR="${AD_LIBRARY_REMOTE_DIR:-~/kyle-ad-library-video-transcripts}"
REMOTE_DIR="${REMOTE_DIR:-~/kyle-insta-video-transcripts}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--help] [user@host ...]

Sync this directory to one or more hosts (default remote dir: ~/kyle-insta-video-transcripts).
Ad Library transcripts live in a separate folder: ~/kyle-ad-library-video-transcripts (not touched by this script).

Examples:
  $(basename "$0") ubuntu@ec2-47-128-222-232.ap-southeast-1.compute.amazonaws.com
  $(basename "$0") ubuntu@host1 ubuntu@host2
  $(basename "$0") ec2-1.example.com ec2-2.example.com   # uses REMOTE_USER (default ubuntu)

If no hosts are given, uses REMOTE_USER and REMOTE_HOST from the environment (or script defaults).

Env: SSH_KEY, REMOTE_USER, REMOTE_HOST, REMOTE_DIR, AD_LIBRARY_REMOTE_DIR
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

assert_not_ad_library_remote_dir() {
  local target resolved_ad_library
  target="$(normalize_remote_dir "$1")"
  resolved_ad_library="$(normalize_remote_dir "${AD_LIBRARY_REMOTE_DIR}")"
  if [[ "$target" == "$resolved_ad_library" ]]; then
    echo "error: REMOTE_DIR points at the Ad Library project folder:" >&2
    echo "  ${AD_LIBRARY_REMOTE_DIR}" >&2
    echo "  Instagram must sync elsewhere (default: ~/kyle-insta-video-transcripts)." >&2
    exit 1
  fi
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

# PEM path: set SSH_KEY or place crawler1.pem next to this script / cwd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${SSH_KEY:-}" ]]; then
  PEM="$SSH_KEY"
elif [[ -f "${SCRIPT_DIR}/crawler1.pem" ]]; then
  PEM="${SCRIPT_DIR}/crawler1.pem"
elif [[ -f "./crawler1.pem" ]]; then
  PEM="$(pwd)/crawler1.pem"
else
  echo "error: set SSH_KEY to your .pem path or copy crawler1.pem into:" >&2
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
  --exclude 'output/'
  --exclude 'transcripts/'
  --exclude '.env'
)

if [[ ! -f "${SCRIPT_DIR}/cookies.json" ]]; then
  echo "warning: ${SCRIPT_DIR}/cookies.json not found; sync will skip it unless you add it locally." >&2
fi

assert_not_ad_library_remote_dir "${REMOTE_DIR}"

for ssh_target in "${SSH_TARGETS[@]}"; do
  echo "Syncing ${SCRIPT_DIR}/ -> ${ssh_target}:${REMOTE_DIR}"
  echo "  (Ad Library folder ${AD_LIBRARY_REMOTE_DIR} is left unchanged)"
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
echo "  cp .env.example .env   # then edit .env on the host"
echo "  python instagram_reels_transcripts.py ... --out ./output --verbose"
