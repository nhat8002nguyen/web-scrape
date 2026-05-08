#!/bin/bash

# Lightweight reset script - clears data but keeps Kafka topics
# Useful when you just want to clear database/cache without topic recreation issues

set -e

CONFIG_FILE="${1:-config/config.local.yaml}"

echo "========================================="
echo "Lightweight Reset (keeps Kafka topics)"
echo "========================================="
echo "Config file: $CONFIG_FILE"
echo ""
echo "This will clear:"
echo "  - PostgreSQL (domains, forms, submissions, errors)"
echo "  - Redis cache"
echo "  - Kafka consumer group offsets"
echo ""
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Reset cancelled."
    exit 0
fi

echo ""
echo "========================================="
echo "Step 1: Clearing PostgreSQL database"
echo "========================================="

# Extract database connection details
DB_HOST=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"')
DB_PORT=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "port:" | awk '{print $2}')
DB_NAME=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "database:" | awk '{print $2}' | tr -d '"')
DB_USER=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "user:" | awk '{print $2}' | tr -d '"')
DB_PASS=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "password:" | awk '{print $2}' | tr -d '"')

export PGPASSWORD="$DB_PASS"

echo "Truncating tables..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF
TRUNCATE TABLE submissions CASCADE;
TRUNCATE TABLE contact_forms CASCADE;
TRUNCATE TABLE domains CASCADE;
TRUNCATE TABLE errors CASCADE;
TRUNCATE TABLE metrics CASCADE;
TRUNCATE TABLE proxy_performance CASCADE;

-- Re-insert initial metric
INSERT INTO metrics (metric_name, metric_value, labels) VALUES
    ('system_initialized', 1, '{"version": "1.0", "budget_mode": true}');

SELECT 'Database tables cleared successfully!' as result;
EOF

unset PGPASSWORD

echo "✓ PostgreSQL cleared"
echo ""

echo "========================================="
echo "Step 2: Clearing Redis cache"
echo "========================================="

REDIS_HOST=$(grep -A 5 "^redis:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"' | cut -d: -f1)
REDIS_PORT=$(grep -A 5 "^redis:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"' | cut -d: -f2)

if [ -z "$REDIS_PORT" ]; then
    REDIS_PORT="6379"
fi

echo "Flushing Redis cache at $REDIS_HOST:$REDIS_PORT..."
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" FLUSHDB

echo "✓ Redis cache cleared"
echo ""

echo "========================================="
echo "Step 3: Resetting Kafka consumer groups"
echo "========================================="

if command -v docker &> /dev/null && docker ps | grep -q kafka; then
    KAFKA_CONTAINER=$(docker ps --filter "name=kafka" --format "{{.Names}}" | head -n 1)
    
    # Extract consumer group from config
    CONSUMER_GROUP=$(grep -A 5 "^kafka:" "$CONFIG_FILE" | grep "consumer_group:" | awk '{print $2}' | tr -d '"')
    
    echo "Resetting consumer groups: ${CONSUMER_GROUP}-discovery, ${CONSUMER_GROUP}-submission"
    
    # Reset consumer group offsets to earliest
    docker exec "$KAFKA_CONTAINER" kafka-consumer-groups --bootstrap-server localhost:9092 --group "${CONSUMER_GROUP}-discovery" --reset-offsets --to-earliest --topic discovery-tasks --execute 2>/dev/null || echo "  Discovery consumer group reset (or doesn't exist yet)"
    
    docker exec "$KAFKA_CONTAINER" kafka-consumer-groups --bootstrap-server localhost:9092 --group "${CONSUMER_GROUP}-submission" --reset-offsets --to-earliest --topic submission-tasks --execute 2>/dev/null || echo "  Submission consumer group reset (or doesn't exist yet)"
    
    echo "✓ Kafka consumer groups reset"
else
    echo "⚠️  Docker not found. Skipping Kafka consumer group reset."
fi

echo ""
echo "========================================="
echo "✅ Lightweight Reset Complete!"
echo "========================================="
echo ""
echo "Kafka topics are preserved. New domains will be processed."
echo ""
echo "Next steps:"
echo "  1. Load domains: ./scripts/load_domains.sh test-domains.csv $CONFIG_FILE"
echo "  2. Start workers (they will pick up from the beginning)"
echo ""
