#!/bin/bash

# Stop all running workers

echo "========================================="
echo "Stopping All Workers"
echo "========================================="
echo ""

# Check what's running before stopping
DISCOVERY_COUNT=$(ps aux | grep -E "discovery-worker|cmd/discovery-worker" | grep -v grep | wc -l | tr -d ' ')
SUBMISSION_COUNT=$(ps aux | grep -E "submission-worker|cmd/submission-worker" | grep -v grep | wc -l | tr -d ' ')
LOADER_COUNT=$(ps aux | grep -E "domain-loader|cmd/domain-loader" | grep -v grep | wc -l | tr -d ' ')

if [ "$DISCOVERY_COUNT" -eq 0 ] && [ "$SUBMISSION_COUNT" -eq 0 ] && [ "$LOADER_COUNT" -eq 0 ]; then
    echo "ℹ️  No workers currently running"
    exit 0
fi

echo "Found running workers:"
[ "$DISCOVERY_COUNT" -gt 0 ] && echo "  - Discovery workers: $DISCOVERY_COUNT"
[ "$SUBMISSION_COUNT" -gt 0 ] && echo "  - Submission workers: $SUBMISSION_COUNT"
[ "$LOADER_COUNT" -gt 0 ] && echo "  - Domain loaders: $LOADER_COUNT"
echo ""

read -p "Stop all workers? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Stopping workers..."

# Stop discovery workers
if [ "$DISCOVERY_COUNT" -gt 0 ]; then
    pkill -f "discovery-worker" && echo "  ✓ Stopped discovery workers" || echo "  - No discovery workers to stop"
fi

# Stop submission workers
if [ "$SUBMISSION_COUNT" -gt 0 ]; then
    pkill -f "submission-worker" && echo "  ✓ Stopped submission workers" || echo "  - No submission workers to stop"
fi

# Stop domain loaders
if [ "$LOADER_COUNT" -gt 0 ]; then
    pkill -f "domain-loader" && echo "  ✓ Stopped domain loaders" || echo "  - No domain loaders to stop"
fi

echo ""
echo "✅ All workers stopped"
echo ""

# Ask about Chrome instances
CHROME_COUNT=$(ps aux | grep -i "Google Chrome" | grep -v grep | wc -l | tr -d ' ')
if [ "$CHROME_COUNT" -gt 0 ]; then
    echo "Found $CHROME_COUNT Chrome instances still running"
    read -p "Stop Chrome instances too? (yes/no): " CHROME_CONFIRM
    
    if [ "$CHROME_CONFIRM" = "yes" ]; then
        pkill -9 "Google Chrome"
        echo "  ✓ Stopped Chrome instances"
    fi
fi

echo ""
