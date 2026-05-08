#!/bin/bash

# Continuous monitoring script for macOS/Linux
# Alternative to 'watch' command which is not available on macOS by default

CONFIG_FILE="${1:-config/config.local.yaml}"
INTERVAL="${2:-5}"  # Refresh interval in seconds

# Function to run the progress check
run_check() {
    ./scripts/check_progress.sh "$CONFIG_FILE"
}

# Trap Ctrl+C to exit cleanly
trap 'echo ""; echo "Monitoring stopped."; exit 0' INT TERM

echo "Starting continuous monitoring (refresh every ${INTERVAL}s)"
echo "Press Ctrl+C to stop"
echo ""

# Run continuously
while true; do
    run_check
    echo ""
    echo "========================================="
    echo "Next refresh in ${INTERVAL}s... (Ctrl+C to stop)"
    echo "========================================="
    sleep "$INTERVAL"
    
    # Clear screen for next iteration (optional, comment out if you want history)
    clear
done
