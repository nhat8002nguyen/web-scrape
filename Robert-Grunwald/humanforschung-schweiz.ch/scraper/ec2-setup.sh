#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ec2-setup.sh  —  Bootstrap & run the humanforschung-schweiz.ch scraper
#                  on a fresh Amazon Linux 2023 / Ubuntu 22.04 EC2 instance.
#
# Usage (run on the EC2 instance):
#   chmod +x ec2-setup.sh
#   ./ec2-setup.sh
#
# The scraper runs inside a tmux session called "scraper" so it keeps going
# after you disconnect from SSH.
#
# Monitor progress at any time:
#   tmux attach -t scraper
# Detach without stopping:   Ctrl-b  d
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_URL="https://github.com/nhat8002nguyen/web-scrape.git"
REPO_DIR="$HOME/web-scrape"
SCRAPER_DIR="$REPO_DIR/Robert-Grunwald/humanforschung-schweiz.ch/scraper"
OUTPUT_DIR="$SCRAPER_DIR/output"
SESSION="scraper"

# Scraper tuning — 10 workers @ 1 s delay ≈ 10 req/s → ~67k URLs in ~1.9 h
WORKERS=10
DELAY=1000

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

log()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $*"; }

# ── 1. System packages ────────────────────────────────────────────────────────

log "Detecting OS and installing base packages…"

if command -v apt-get &>/dev/null; then
  sudo apt-get update -y -q
  sudo apt-get install -y -q git curl tmux

elif command -v dnf &>/dev/null; then
  sudo dnf update -y -q
  sudo dnf install -y -q git curl tmux

elif command -v yum &>/dev/null; then
  sudo yum update -y -q
  sudo yum install -y -q git curl tmux

else
  warn "Unknown package manager — skipping system package install."
fi

# ── 2. Node.js 20 ────────────────────────────────────────────────────────────

if ! command -v node &>/dev/null || [[ "$(node -e 'process.stdout.write(process.version.split(".")[0].slice(1))')" -lt 20 ]]; then
  log "Installing Node.js 20 via NodeSource…"

  if command -v apt-get &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
  else
    curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
    sudo yum install -y nodejs || sudo dnf install -y nodejs
  fi
else
  log "Node.js $(node --version) already installed — skipping."
fi

log "Node $(node --version)  |  npm $(npm --version)"

# ── 3. Clone / update repo ────────────────────────────────────────────────────

if [ -d "$REPO_DIR/.git" ]; then
  log "Repo already cloned — pulling latest changes…"
  git -C "$REPO_DIR" pull --ff-only
else
  log "Cloning repo…"
  git clone --depth=1 "$REPO_URL" "$REPO_DIR"
fi

# ── 4. Install npm dependencies ───────────────────────────────────────────────

log "Installing npm dependencies…"
npm install --prefer-offline --no-audit --progress=false \
  --prefix "$SCRAPER_DIR" \
  --omit=optional 2>&1 | tail -5

# ── 5. Ensure output directory and all-urls.txt exist ─────────────────────────

mkdir -p "$OUTPUT_DIR"

if [ ! -f "$OUTPUT_DIR/all-urls.txt" ]; then
  warn "output/all-urls.txt not found."
  warn "You have two options:"
  warn "  A) Copy it from your local machine (recommended — already collected):"
  warn "       scp -i your-key.pem output/all-urls.txt ec2-user@<EC2-IP>:$OUTPUT_DIR/"
  warn "  B) Let this script gather URLs now (adds ~30 min)."
  echo ""
  read -r -p "Gather URLs now? [y/N]: " GATHER
  if [[ "${GATHER,,}" == "y" ]]; then
    log "Gathering all study URLs — this takes ~30 min…"
    node "$SCRAPER_DIR/gather-urls.js"
  else
    echo ""
    echo "Upload all-urls.txt then re-run this script, or start scraping manually:"
    echo "  node $SCRAPER_DIR/scrape.js --queue memory --input all-urls.txt --output results-final.xlsx --workers $WORKERS --delay $DELAY"
    exit 0
  fi
else
  URL_COUNT=$(wc -l < "$OUTPUT_DIR/all-urls.txt")
  log "Found $URL_COUNT URLs in output/all-urls.txt — skipping gather step."
fi

# ── 6. Kill any existing scraper session ─────────────────────────────────────

if tmux has-session -t "$SESSION" 2>/dev/null; then
  warn "Existing tmux session '$SESSION' found — killing it."
  tmux kill-session -t "$SESSION"
fi

# ── 7. Launch scraper inside tmux ────────────────────────────────────────────

SCRAPE_CMD="node scrape.js \
  --queue memory \
  --input all-urls.txt \
  --output results-final.xlsx \
  --workers $WORKERS \
  --delay $DELAY; \
  echo ''; \
  echo '===================================='; \
  echo 'Scrape finished — press Enter to exit'; \
  echo '===================================='; \
  read"

log "Starting scraper in tmux session '$SESSION'…"
log "  Workers : $WORKERS"
log "  Delay   : ${DELAY}ms"
log "  Est. time: ~$((67441 / (WORKERS * 1000 / DELAY / 1) / 3600 + 1))h for 67k URLs"

tmux new-session -d -s "$SESSION" -c "$SCRAPER_DIR" "bash -c '$SCRAPE_CMD'"

# ── 8. Done ───────────────────────────────────────────────────────────────────

EC2_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "<EC2-IP>")

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Scraper is running!${NC}"
echo ""
echo "  Monitor live:    tmux attach -t $SESSION"
echo "  Detach (no stop): Ctrl-b  d"
echo ""
echo "  Output file:  $OUTPUT_DIR/results-final.xlsx"
echo "  Failed URLs:  $OUTPUT_DIR/failed-urls.txt  (if any)"
echo ""
echo "  Download results when done (run on your LOCAL machine):"
echo "    scp -i your-key.pem ec2-user@${EC2_IP}:${OUTPUT_DIR}/results-final.xlsx ."
echo "    scp -i your-key.pem ec2-user@${EC2_IP}:${OUTPUT_DIR}/failed-urls.txt ."
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
