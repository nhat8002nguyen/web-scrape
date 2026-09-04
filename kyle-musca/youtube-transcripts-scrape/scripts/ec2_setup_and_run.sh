#!/usr/bin/env bash
#
# Setup and run YouTube channel transcript scraping on a Linux EC2 instance
# (Amazon Linux 2023/2, Ubuntu). Run from the repo after clone, or set
# YT_SCRAPE_HOME to the project directory.
#
# Quick start on a fresh EC2 (Amazon Linux 2023 example):
#   sudo dnf update -y
#   # From your Mac (skips .venv, .venv-desktop-build, build/, dist/, etc.):
#   EC2_KEY=key.pem ./scripts/ec2_upload.sh ec2-user@<host>
#   scp -i key.pem .env ec2-user@<host>:~/youtube-transcripts-scrape/.env
#   ssh -i key.pem ec2-user@<host>
#   cd ~/youtube-transcripts-scrape
#   ./scripts/ec2_setup_and_run.sh run --detach -- \
#     "https://www.youtube.com/@YourChannel" --out ./transcripts --resume
#
# Attach to a detached run:  tmux attach -t youtube-transcripts
# Tail log:                   tail -f logs/run-*.log
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
YT_SCRAPE_HOME="${YT_SCRAPE_HOME:-$ROOT}"
YT_SCRAPE_VENV="${YT_SCRAPE_VENV:-$YT_SCRAPE_HOME/.venv}"
YT_SCRAPE_LOG_DIR="${YT_SCRAPE_LOG_DIR:-$YT_SCRAPE_HOME/logs}"
YT_SCRAPE_TMUX_SESSION="${YT_SCRAPE_TMUX_SESSION:-youtube-transcripts}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
MAIN_SCRIPT="$YT_SCRAPE_HOME/download_channel_transcripts.py"
REQUIREMENTS="$YT_SCRAPE_HOME/requirements.txt"

log() { printf '[ec2] %s\n' "$*"; }
die() { printf '[ec2] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: ec2_setup_and_run.sh <command> [options]

Commands:
  setup              Install OS packages (sudo), create .venv, pip install -r requirements.txt
  run [--detach] -- <args...>
                     Run downloader; auto-creates .venv and pip installs if missing (not uploaded)
  status             Show tmux session and latest log file if present
  shell              Start a subshell with the project venv activated
  help               Show this message

Environment:
  YT_SCRAPE_HOME          Project directory (default: parent of scripts/)
  YT_SCRAPE_VENV          Virtualenv path (default: $YT_SCRAPE_HOME/.venv)
  YT_SCRAPE_LOG_DIR       Log directory for detached runs (default: $YT_SCRAPE_HOME/logs)
  YT_SCRAPE_TMUX_SESSION  tmux session name (default: youtube-transcripts)
  PYTHON_BIN              Python executable for venv (default: python3)
  SKIP_SYSTEM_PACKAGES=1  Skip dnf/apt install during setup (venv only)

Examples:
  ./scripts/ec2_setup_and_run.sh setup

  ./scripts/ec2_setup_and_run.sh run -- \
    "https://www.youtube.com/@YourChannel" --out ./transcripts --resume

  ./scripts/ec2_setup_and_run.sh run --detach -- \
    "https://www.youtube.com/@YourChannel" --out ./transcripts --resume --delay 8

  # Retry from skip log (Webshare creds in .env):
  ./scripts/ec2_setup_and_run.sh run --detach -- \
    --retry-from-skip-log ./transcripts/skipped.jsonl --out ./transcripts-retry --resume

  # Whisper retry from skip log (needs ffmpeg + large-v3 cache):
  ./scripts/ec2_setup_and_run.sh shell
  python whisper_skipped_transcripts.py \
    --skip-log ./transcripts/CHANNEL/skipped.jsonl \
    --out ./transcripts/CHANNEL \
    --resume

Upload project from Mac (excludes .venv, .venv-desktop-build, build/, dist/):
  EC2_KEY=KEY.pem ./scripts/ec2_upload.sh ec2-user@HOST

Copy .env separately (Webshare / Simplepush / TRANSCRIPT_PROXY):
  scp -i KEY.pem .env ec2-user@HOST:$YT_SCRAPE_HOME/.env

EOF
}

detect_os() {
  if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "${ID:-unknown}"
    return
  fi
  echo "unknown"
}

install_system_packages() {
  if [[ "${SKIP_SYSTEM_PACKAGES:-}" == "1" ]]; then
    log "SKIP_SYSTEM_PACKAGES=1 — skipping OS package install"
    return
  fi

  local os_id
  os_id="$(detect_os)"
  log "Detected OS: $os_id"

  case "$os_id" in
    amzn|amazon)
      if command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3 python3-pip git tmux ffmpeg
      else
        sudo yum install -y python3 python3-pip git tmux ffmpeg
      fi
      ;;
    ubuntu|debian)
      sudo apt-get update -y
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
        python3 python3-venv python3-pip git tmux ffmpeg
      ;;
    rhel|centos|fedora|rocky|almalinux)
      if command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3 python3-pip git tmux ffmpeg
      else
        sudo yum install -y python3 python3-pip git tmux ffmpeg
      fi
      ;;
    *)
      log "Unknown OS ($os_id). Install manually: python3 (3.9+), pip, git, tmux, ffmpeg"
      ;;
  esac
}

check_python_version() {
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    die "$PYTHON_BIN not found. Run: $0 setup (installs python3 via apt/dnf)"
  fi
  local ver
  ver="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  local major minor
  major="${ver%%.*}"
  minor="${ver#*.}"
  if [[ "$major" -lt 3 ]] || [[ "$major" -eq 3 && "$minor" -lt 9 ]]; then
    die "Python 3.9+ required; found $ver ($PYTHON_BIN)"
  fi
  log "Using $PYTHON_BIN ($ver)"
}

validate_project_files() {
  cd "$YT_SCRAPE_HOME"
  [[ -f "$REQUIREMENTS" ]] || die "requirements.txt not found at $REQUIREMENTS"
  [[ -f "$MAIN_SCRIPT" ]] || die "download_channel_transcripts.py not found at $MAIN_SCRIPT"
}

create_venv() {
  log "Creating virtualenv at $YT_SCRAPE_VENV (local .venv is not uploaded to EC2)"
  if ! "$PYTHON_BIN" -m venv "$YT_SCRAPE_VENV" 2>/dev/null; then
    log "python3 -m venv failed — installing OS packages (python3-venv, etc.)..."
    install_system_packages
    check_python_version
    "$PYTHON_BIN" -m venv "$YT_SCRAPE_VENV"
  fi
}

install_venv_requirements() {
  # shellcheck disable=SC1091
  source "$YT_SCRAPE_VENV/bin/activate"
  log "Installing Python packages from requirements.txt"
  python -m pip install -U pip
  python -m pip install -r "$REQUIREMENTS"
}

# Create .venv + pip install when missing; refresh requirements on every run/setup.
ensure_python_env() {
  validate_project_files

  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    log "$PYTHON_BIN not found — installing OS packages..."
    install_system_packages
  fi
  check_python_version

  if [[ ! -d "$YT_SCRAPE_VENV" ]]; then
    create_venv
  fi

  install_venv_requirements
  mkdir -p "$YT_SCRAPE_LOG_DIR"
}

cmd_setup() {
  if [[ "${SKIP_SYSTEM_PACKAGES:-}" != "1" ]]; then
    install_system_packages
  fi
  ensure_python_env
  log "Setup complete."
  log "Next: place .env in $YT_SCRAPE_HOME (see README), then:"
  log "  $0 run --detach -- \"https://www.youtube.com/@Channel\" --out ./transcripts --resume"
}

activate_venv() {
  ensure_python_env
}

warn_if_no_env() {
  if [[ ! -f "$YT_SCRAPE_HOME/.env" ]]; then
    log "WARNING: no .env at $YT_SCRAPE_HOME/.env"
    log "EC2 IPs are often blocked by YouTube — set WEBSHARE_PROXY_USERNAME/PASSWORD or TRANSCRIPT_PROXY."
  fi
}

cmd_run() {
  local detach=0
  local downloader_args=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --detach) detach=1; shift ;;
      --) shift; downloader_args=("$@"); break ;;
      -h|--help) usage; exit 0 ;;
      *)
        die "Unknown run option: $1 (use -- before downloader flags)"
        ;;
    esac
  done

  [[ ${#downloader_args[@]} -gt 0 ]] || die "No downloader arguments. Example: $0 run -- \"https://www.youtube.com/@x\" --out ./transcripts"

  log "Ensuring .venv and Python dependencies on EC2..."
  activate_venv
  cd "$YT_SCRAPE_HOME"
  warn_if_no_env
  mkdir -p "$YT_SCRAPE_LOG_DIR"

  local log_file
  log_file="$YT_SCRAPE_LOG_DIR/run-$(date +%Y%m%d-%H%M%S).log"

  if [[ "$detach" -eq 1 ]]; then
    if ! command -v tmux >/dev/null 2>&1; then
      log "tmux not found — installing OS packages..."
      install_system_packages
    fi
    command -v tmux >/dev/null 2>&1 || die "tmux not installed"
    if tmux has-session -t "$YT_SCRAPE_TMUX_SESSION" 2>/dev/null; then
      die "tmux session '$YT_SCRAPE_TMUX_SESSION' already exists. Attach: tmux attach -t $YT_SCRAPE_TMUX_SESSION"
    fi
    local wrapper="$YT_SCRAPE_LOG_DIR/.run-wrapper.sh"
    {
      printf '%s\n' '#!/usr/bin/env bash' 'set -euo pipefail'
      printf 'cd %q\n' "$YT_SCRAPE_HOME"
      printf 'source %q\n' "$YT_SCRAPE_VENV/bin/activate"
      printf 'python %q' "$MAIN_SCRIPT"
      for arg in "${downloader_args[@]}"; do
        printf ' %q' "$arg"
      done
      printf ' 2>&1 | tee -a %q\n' "$log_file"
    } > "$wrapper"
    chmod +x "$wrapper"
    log "Starting detached run in tmux session '$YT_SCRAPE_TMUX_SESSION'"
    log "Log file: $log_file"
    tmux new-session -d -s "$YT_SCRAPE_TMUX_SESSION" "$wrapper"
    log "Attach with: tmux attach -t $YT_SCRAPE_TMUX_SESSION"
    log "Detach with: Ctrl+b then d"
  else
    log "Running in foreground (log also written to $log_file)"
    python "$MAIN_SCRIPT" "${downloader_args[@]}" 2>&1 | tee -a "$log_file"
  fi
}

cmd_status() {
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$YT_SCRAPE_TMUX_SESSION" 2>/dev/null; then
    log "tmux session '$YT_SCRAPE_TMUX_SESSION' is running"
    tmux list-panes -t "$YT_SCRAPE_TMUX_SESSION" -F '#{pane_current_command}' 2>/dev/null || true
  else
    log "No active tmux session '$YT_SCRAPE_TMUX_SESSION'"
  fi
  if [[ -d "$YT_SCRAPE_LOG_DIR" ]]; then
    local latest
    latest="$(ls -t "$YT_SCRAPE_LOG_DIR"/run-*.log 2>/dev/null | head -1 || true)"
    if [[ -n "$latest" ]]; then
      log "Latest log: $latest"
      tail -5 "$latest" 2>/dev/null || true
    fi
  fi
}

cmd_shell() {
  activate_venv
  log "Virtualenv activated. Run manually, e.g.:"
  log "  python download_channel_transcripts.py \"https://www.youtube.com/@Channel\" --out ./transcripts"
  exec "${SHELL:-/bin/bash}"
}

main() {
  local cmd="${1:-help}"
  shift || true

  case "$cmd" in
    setup) cmd_setup ;;
    run) cmd_run "$@" ;;
    status) cmd_status ;;
    shell) cmd_shell ;;
    help|-h|--help) usage ;;
    *)
      die "Unknown command: $cmd (try: $0 help)"
      ;;
  esac
}

main "$@"
