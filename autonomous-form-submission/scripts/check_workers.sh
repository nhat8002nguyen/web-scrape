#!/bin/bash

# Check currently running workers and their status

echo "========================================="
echo "Running Workers Status"
echo "========================================="
echo ""

# Check for discovery workers
DISCOVERY_COUNT=$(ps aux | grep -E "discovery-worker|cmd/discovery-worker" | grep -v grep | wc -l | tr -d ' ')
if [ "$DISCOVERY_COUNT" -gt 0 ]; then
    echo "🔍 DISCOVERY WORKERS: $DISCOVERY_COUNT running"
    echo "----------------------------------------"
    ps aux | grep -E "discovery-worker|cmd/discovery-worker" | grep -v grep | awk '{print "  PID: " $2 " | CPU: " $3"% | MEM: " $4"% | Running: " $10 " " $11 " " $12 " " $13}'
    echo ""
else
    echo "🔍 DISCOVERY WORKERS: None running"
    echo ""
fi

# Check for submission workers
SUBMISSION_COUNT=$(ps aux | grep -E "submission-worker|cmd/submission-worker" | grep -v grep | wc -l | tr -d ' ')
if [ "$SUBMISSION_COUNT" -gt 0 ]; then
    echo "📤 SUBMISSION WORKERS: $SUBMISSION_COUNT running"
    echo "----------------------------------------"
    ps aux | grep -E "submission-worker|cmd/submission-worker" | grep -v grep | awk '{print "  PID: " $2 " | CPU: " $3"% | MEM: " $4"% | Running: " $10 " " $11 " " $12 " " $13}'
    echo ""
else
    echo "📤 SUBMISSION WORKERS: None running"
    echo ""
fi

# Check for domain loader
LOADER_COUNT=$(ps aux | grep -E "domain-loader|cmd/domain-loader" | grep -v grep | wc -l | tr -d ' ')
if [ "$LOADER_COUNT" -gt 0 ]; then
    echo "📥 DOMAIN LOADER: $LOADER_COUNT running"
    echo "----------------------------------------"
    ps aux | grep -E "domain-loader|cmd/domain-loader" | grep -v grep | awk '{print "  PID: " $2 " | CPU: " $3"% | MEM: " $4"% | Running: " $10 " " $11 " " $12 " " $13}'
    echo ""
else
    echo "📥 DOMAIN LOADER: None running"
    echo ""
fi

# Check for Chrome instances
CHROME_COUNT=$(ps aux | grep -i "Google Chrome" | grep -v grep | wc -l | tr -d ' ')
if [ "$CHROME_COUNT" -gt 0 ]; then
    echo "🌐 CHROME INSTANCES: $CHROME_COUNT running"
    echo "----------------------------------------"
    echo "  (Used by headless browser automation)"
    
    # Check for headless instances specifically
    HEADLESS_COUNT=$(ps aux | grep -i "Google Chrome" | grep -i headless | grep -v grep | wc -l | tr -d ' ')
    if [ "$HEADLESS_COUNT" -gt 0 ]; then
        echo "  Headless: $HEADLESS_COUNT instances"
    fi
    
    # Show memory usage
    CHROME_MEM=$(ps aux | grep -i "Google Chrome" | grep -v grep | awk '{sum+=$4} END {print sum}')
    echo "  Total Memory: ${CHROME_MEM}%"
    echo ""
    
    echo "  💡 TIP: If Chrome is stuck, run: pkill -9 \"Google Chrome\""
    echo ""
else
    echo "🌐 CHROME INSTANCES: None running"
    echo ""
fi

# Summary
echo "========================================="
echo "SUMMARY"
echo "========================================="
TOTAL_WORKERS=$((DISCOVERY_COUNT + SUBMISSION_COUNT + LOADER_COUNT))

if [ "$TOTAL_WORKERS" -eq 0 ]; then
    echo "❌ No workers currently running"
    echo ""
    echo "To start workers:"
    echo "  Terminal 1: go run cmd/discovery-worker/main.go --config config/config.local.yaml"
    echo "  Terminal 2: go run cmd/submission-worker/main.go --config config/config.local.yaml"
else
    echo "✅ Total workers running: $TOTAL_WORKERS"
    echo "   - Discovery: $DISCOVERY_COUNT"
    echo "   - Submission: $SUBMISSION_COUNT"
    echo "   - Domain Loader: $LOADER_COUNT"
fi

echo ""
echo "To stop all workers:"
echo "  pkill -f \"discovery-worker\""
echo "  pkill -f \"submission-worker\""
echo "  pkill -f \"domain-loader\""
echo ""
