#!/bin/bash

# Convenience script to reset and reload test domains in one command

set -e

CONFIG_FILE="${1:-config/config.local.yaml}"
DOMAINS_FILE="test-domains.csv"

echo "========================================="
echo "Reset and Reload Test Domains"
echo "========================================="
echo "Config: $CONFIG_FILE"
echo "Domains: $DOMAINS_FILE"
echo ""

# Check if domains file exists
if [ ! -f "$DOMAINS_FILE" ]; then
    echo "❌ ERROR: $DOMAINS_FILE not found!"
    exit 1
fi

# Prompt for confirmation
read -p "This will clear all data and reload test domains. Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Step 1: Resetting system..."
echo "----------------------------------------"

# Extract database connection details
DB_HOST=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"')
DB_PORT=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "port:" | awk '{print $2}')
DB_NAME=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "database:" | awk '{print $2}' | tr -d '"')
DB_USER=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "user:" | awk '{print $2}' | tr -d '"')
DB_PASS=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "password:" | awk '{print $2}' | tr -d '"')

export PGPASSWORD="$DB_PASS"

# Clear database
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF > /dev/null 2>&1
TRUNCATE TABLE submissions CASCADE;
TRUNCATE TABLE contact_forms CASCADE;
TRUNCATE TABLE domains CASCADE;
TRUNCATE TABLE errors CASCADE;
TRUNCATE TABLE metrics CASCADE;
TRUNCATE TABLE proxy_performance CASCADE;
INSERT INTO metrics (metric_name, metric_value, labels) VALUES
    ('system_initialized', 1, '{"version": "1.0", "budget_mode": true}');
EOF

unset PGPASSWORD

echo "✓ Database cleared"

# Clear Redis
REDIS_HOST=$(grep -A 5 "^redis:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"' | cut -d: -f1)
REDIS_PORT=$(grep -A 5 "^redis:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"' | cut -d: -f2)
[ -z "$REDIS_PORT" ] && REDIS_PORT="6379"

redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" FLUSHDB > /dev/null 2>&1
echo "✓ Redis cleared"

echo ""
echo "Step 2: Loading test domains..."
echo "----------------------------------------"

# Load domains
./scripts/load_domains.sh "$DOMAINS_FILE" "$CONFIG_FILE"

echo ""
echo "Step 3: Verifying..."
echo "----------------------------------------"

# Wait a moment for data to settle
sleep 2

# Run diagnostic
./scripts/diagnose.sh "$CONFIG_FILE" | tail -20

echo ""
echo "========================================="
echo "✅ Reset and reload complete!"
echo "========================================="
echo ""
echo "⚠️  IMPORTANT: Make sure workers are running!"
echo ""
echo "Check workers:"
echo "  ./scripts/check_workers.sh"
echo ""
echo "If no workers running, start them:"
echo "  Terminal 1: go run cmd/discovery-worker/main.go --config $CONFIG_FILE"
echo "  Terminal 2: go run cmd/submission-worker/main.go --config $CONFIG_FILE"
echo ""
