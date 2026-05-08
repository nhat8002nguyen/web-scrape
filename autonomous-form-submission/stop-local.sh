#!/bin/bash

# Stop Local Testing Script

echo "========================================="
echo "Stopping Local Test System"
echo "========================================="
echo ""

# Kill workers
if [ -f "logs/discovery-worker.pid" ]; then
    DISCOVERY_PID=$(cat logs/discovery-worker.pid)
    echo "Stopping discovery worker (PID: $DISCOVERY_PID)..."
    kill $DISCOVERY_PID 2>/dev/null || true
    rm logs/discovery-worker.pid
fi

if [ -f "logs/submission-worker.pid" ]; then
    SUBMISSION_PID=$(cat logs/submission-worker.pid)
    echo "Stopping submission worker (PID: $SUBMISSION_PID)..."
    kill $SUBMISSION_PID 2>/dev/null || true
    rm logs/submission-worker.pid
fi

# Stop infrastructure
echo "Stopping infrastructure services..."
docker-compose -f deployments/docker/docker-compose.instance1.yml stop

echo ""
echo "========================================="
echo "System Stopped"
echo "========================================="
echo ""
echo "To view results before cleanup:"
echo "  docker exec postgres psql -U formbot -d form_submissions -c 'SELECT * FROM submission_stats;'"
echo ""
echo "To completely remove containers and data:"
echo "  docker-compose -f deployments/docker/docker-compose.instance1.yml down -v"
echo ""
