#!/bin/bash

# All-in-one script to test the timeout fix
# This ensures everything happens in the right order

set -e

CONFIG_FILE="${1:-config/config.local.yaml}"
DOMAINS_FILE="${2:-my-test-domains.csv}"

echo "========================================="
echo "🧪 Testing Discovery Worker with Fix"
echo "========================================="
echo ""

# Step 1: Kill any old workers
echo "Step 1: Stopping any old workers..."
pkill -9 -f "discovery-worker" 2>/dev/null && echo "  ✓ Killed old discovery workers" || echo "  - No old workers found"
pkill -9 -f "submission-worker" 2>/dev/null && echo "  ✓ Killed old submission workers" || echo "  - No submission workers"
sleep 2

# Step 2: Clear database
echo ""
echo "Step 2: Clearing database and cache..."

DB_HOST=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"')
DB_PORT=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "port:" | awk '{print $2}')
DB_NAME=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "database:" | awk '{print $2}' | tr -d '"')
DB_USER=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "user:" | awk '{print $2}' | tr -d '"')
DB_PASS=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "password:" | awk '{print $2}' | tr -d '"')

export PGPASSWORD="$DB_PASS"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF > /dev/null 2>&1
TRUNCATE TABLE submissions CASCADE;
TRUNCATE TABLE contact_forms CASCADE;
TRUNCATE TABLE domains CASCADE;
TRUNCATE TABLE errors CASCADE;
EOF
unset PGPASSWORD

REDIS_HOST=$(grep -A 5 "^redis:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"' | cut -d: -f1)
REDIS_PORT=$(grep -A 5 "^redis:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"' | cut -d: -f2)
[ -z "$REDIS_PORT" ] && REDIS_PORT="6379"
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" FLUSHDB > /dev/null 2>&1

echo "  ✓ Database and cache cleared"

# Step 3: Start discovery worker in background
echo ""
echo "Step 3: Starting discovery worker with FIX..."
echo "  (Running in background, logs will show below)"
echo ""

# Start worker in background and capture output
nohup go run cmd/discovery-worker/main.go --config "$CONFIG_FILE" > /tmp/discovery-worker.log 2>&1 &
WORKER_PID=$!

echo "  ✓ Discovery worker started (PID: $WORKER_PID)"
echo "  📝 Logs: tail -f /tmp/discovery-worker.log"
echo ""

# Wait for worker to initialize
echo "  ⏳ Waiting 5 seconds for worker to initialize..."
sleep 5

# Step 4: Load domains
echo ""
echo "Step 4: Loading domains..."
./scripts/load_domains.sh "$DOMAINS_FILE" "$CONFIG_FILE" | grep -E "(Total domains|published|complete)"

echo ""
echo "========================================="
echo "✅ Setup Complete!"
echo "========================================="
echo ""
echo "Worker is now processing domains with the 45-second timeout fix!"
echo ""
echo "📊 Monitor progress:"
echo "  ./scripts/monitor.sh"
echo ""
echo "📝 Watch worker logs:"
echo "  tail -f /tmp/discovery-worker.log"
echo ""
echo "🛑 Stop worker when done:"
echo "  kill $WORKER_PID"
echo ""
echo "⏱️  Expected: Each domain takes ~45-60 seconds to process"
echo "   Total time for 11 domains: ~8-10 minutes"
echo ""
