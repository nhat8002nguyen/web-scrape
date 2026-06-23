#!/usr/bin/env bash
#
# Upload the project to EC2 without local venvs, build output, or heavy artifacts.
# Uses rsync (scp cannot exclude directories). Copy .env separately (see below).
#
# Usage (from youtube-transcripts-scrape/):
#   ./scripts/ec2_upload.sh ubuntu@ec2-xx.ap-southeast-1.compute.amazonaws.com
#   EC2_KEY=./video-transcripts-server.pem ./scripts/ec2_upload.sh ubuntu@host
#
# Then copy secrets:
#   scp -i ./video-transcripts-server.pem .env ubuntu@host:~/youtube-transcripts-scrape/.env
#
# Manual rsync (note: -e must be "ssh -i KEY", not the .pem path alone):
#   rsync -avz --progress -e "ssh -i ./video-transcripts-server.pem" \
#     --exclude '.venv/' --exclude '.venv-desktop-build/' \
#     --exclude 'build/' --exclude 'dist/' \
#     ./ ubuntu@host:~/youtube-transcripts-scrape/
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REMOTE="${1:-}"
EC2_KEY="${EC2_KEY:-${SSH_KEY:-}}"
EC2_REMOTE_PATH="${EC2_REMOTE_PATH:-~/youtube-transcripts-scrape}"

if [[ -z "$REMOTE" ]]; then
  printf 'Usage: %s ubuntu@ec2-host\n' "$(basename "$0")" >&2
  printf 'Optional: EC2_KEY or SSH_KEY=path/to/key.pem\n' >&2
  printf 'Optional: EC2_REMOTE_PATH=~/youtube-transcripts-scrape (default)\n' >&2
  exit 1
fi

resolve_pem() {
  if [[ -n "$EC2_KEY" ]]; then
    echo "$EC2_KEY"
    return
  fi
  local candidate
  for candidate in \
    "$ROOT/video-transcripts-server.pem" \
    "$SCRIPT_DIR/video-transcripts-server.pem" \
    "$(pwd)/video-transcripts-server.pem" \
    "$ROOT/../video-transcripts-server.pem"; do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return
    fi
  done
  return 1
}

PEM=""
if PEM="$(resolve_pem)"; then
  chmod 400 "$PEM" 2>/dev/null || true
else
  PEM=""
fi

if [[ -n "$PEM" ]]; then
  RSYNC_RSH="ssh -i ${PEM} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
else
  RSYNC_RSH="ssh"
  printf '[upload] WARNING: no .pem found — set EC2_KEY=./video-transcripts-server.pem\n' >&2
fi

log() { printf '[upload] %s\n' "$*"; }

log "Syncing $ROOT/ -> $REMOTE:$EC2_REMOTE_PATH/"
[[ -n "$PEM" ]] && log "SSH key: $PEM"
log "Excluding: .venv, .venv-desktop-build, build/, dist/, transcripts/, .env, *.pem, caches"

rsync -avz --progress \
  -e "$RSYNC_RSH" \
  --exclude '.venv/' \
  --exclude '.venv-desktop-build/' \
  --exclude 'build/' \
  --exclude 'dist/' \
  --exclude '.tmp-build-test/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'transcripts/' \
  --exclude '.env' \
  --exclude '*.pem' \
  --exclude 'Webshare*.txt' \
  --exclude '*proxies*.txt' \
  "$ROOT/" "$REMOTE:$EC2_REMOTE_PATH/"

log "Done. On EC2: cd $EC2_REMOTE_PATH && ./scripts/ec2_setup_and_run.sh setup"
if [[ -n "$PEM" ]]; then
  log "Copy .env: scp -i \"$PEM\" .env $REMOTE:$EC2_REMOTE_PATH/.env"
fi
