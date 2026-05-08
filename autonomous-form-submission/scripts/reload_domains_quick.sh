#!/bin/bash

# Quick reload domains without stopping workers
# This clears old failed domains and loads fresh ones

set -e

CONFIG_FILE="${1:-config/config.local.yaml}"
DOMAINS_FILE="${2:-my-test-domains.csv}"

echo "========================================="
echo "Quick Reload Domains"
echo "========================================="
echo "Config: $CONFIG_FILE"
echo "Domains: $DOMAINS_FILE"
echo ""
echo "This will:"
echo "  1. Clear old failed domains from database"
echo "  2. Flush Redis cache"
echo "  3. Load fresh domains to Kafka"
echo "  4. Worker will pick them up automatically"
echo ""

# Extract database connection details
DB_HOST=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"')
DB_PORT=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "port:" | awk '{print $2}')
DB_NAME=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "database:" | awk '{print $2}' | tr -d '"')
DB_USER=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "user:" | awk '{print $2}' | tr -d '"')
DB_PASS=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "password:" | awk '{print $2}' | tr -d '"')

export PGPASSWORD="$DB_PASS"

echo "Step 1: Clearing database..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF > /dev/null 2>&1
TRUNCATE TABLE submissions CASCADE;
TRUNCATE TABLE contact_forms CASCADE;
TRUNCATE TABLE domains CASCADE;
TRUNCATE TABLE errors CASCADE;
INSERT INTO metrics (metric_name, metric_value, labels) VALUES
    ('system_initialized', 1, '{"version": "1.0", "budget_mode": true}')
ON CONFLICT DO NOTHING;
EOF

unset PGPASSWORD
echo "✓ Database cleared"

echo ""
echo "Step 2: Flushing Redis..."
REDIS_HOST=$(grep -A 5 "^redis:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"' | cut -d: -f1)
REDIS_PORT=$(grep -A 5 "^redis:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"' | cut -d: -f2)
[ -z "$REDIS_PORT" ] && REDIS_PORT="6379"

redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" FLUSHDB > /dev/null 2>&1
echo "✓ Redis cleared"

echo ""
echo "Step 3: Loading domains..."
./scripts/load_domains.sh "$DOMAINS_FILE" "$CONFIG_FILE"

echo ""
echo "========================================="
echo "✅ Done!"
echo "========================================="
echo ""
echo "The running discovery worker will now pick up the fresh domains."
echo "Watch the monitor to see progress!"
echo ""
