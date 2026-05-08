#!/bin/bash

# Script to reset the system and clear all data for a fresh run

set -e

CONFIG_FILE="${1:-config/config.local.yaml}"

echo "========================================="
echo "Resetting Autonomous Form Submission System"
echo "========================================="
echo "Config file: $CONFIG_FILE"
echo ""
echo "⚠️  WARNING: This will delete all data from:"
echo "  - PostgreSQL (domains, forms, submissions, errors)"
echo "  - Redis cache"
echo "  - Kafka topics (discovery-tasks, submission-tasks)"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Reset cancelled."
    exit 0
fi

echo ""
echo "========================================="
echo "Step 1: Clearing PostgreSQL database"
echo "========================================="

# Extract database connection details from config
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

# Extract Redis connection details
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
echo "Step 3: Clearing Kafka topics"
echo "========================================="

# Extract Kafka broker
KAFKA_BROKER=$(grep -A 3 "^kafka:" "$CONFIG_FILE" | grep "brokers:" | sed 's/.*\[\(.*\)\]/\1/' | tr -d '"' | tr -d ' ')

if command -v kafka-topics &> /dev/null; then
    echo "Using local Kafka installation..."
    echo "Deleting Kafka topics..."
    kafka-topics --bootstrap-server "$KAFKA_BROKER" --delete --topic discovery-tasks 2>/dev/null || echo "  discovery-tasks topic not found or already deleted"
    kafka-topics --bootstrap-server "$KAFKA_BROKER" --delete --topic submission-tasks 2>/dev/null || echo "  submission-tasks topic not found or already deleted"
    
    echo "Recreating Kafka topics..."
    kafka-topics --bootstrap-server "$KAFKA_BROKER" --create --topic discovery-tasks --partitions 3 --replication-factor 1
    kafka-topics --bootstrap-server "$KAFKA_BROKER" --create --topic submission-tasks --partitions 5 --replication-factor 1
    
    echo "✓ Kafka topics cleared and recreated"
elif command -v docker &> /dev/null && docker ps | grep -q kafka; then
    echo "Using Docker Kafka (Confluent)..."
    KAFKA_CONTAINER=$(docker ps --filter "name=kafka" --format "{{.Names}}" | head -n 1)
    
    echo "Deleting Kafka topics..."
    docker exec "$KAFKA_CONTAINER" kafka-topics --bootstrap-server localhost:9092 --delete --topic discovery-tasks 2>&1 | grep -v "does not exist" || true
    docker exec "$KAFKA_CONTAINER" kafka-topics --bootstrap-server localhost:9092 --delete --topic submission-tasks 2>&1 | grep -v "does not exist" || true
    
    # Wait for topics to be fully deleted
    echo "Waiting for topics to be deleted..."
    sleep 3
    
    echo "Recreating Kafka topics..."
    # Try to create topics, ignore error if they already exist
    docker exec "$KAFKA_CONTAINER" kafka-topics --bootstrap-server localhost:9092 --create --topic discovery-tasks --partitions 3 --replication-factor 1 2>&1 | grep -v "already exists" || echo "  ✓ discovery-tasks topic ready"
    docker exec "$KAFKA_CONTAINER" kafka-topics --bootstrap-server localhost:9092 --create --topic submission-tasks --partitions 5 --replication-factor 1 2>&1 | grep -v "already exists" || echo "  ✓ submission-tasks topic ready"
    
    # List topics to confirm
    echo ""
    echo "Current Kafka topics:"
    docker exec "$KAFKA_CONTAINER" kafka-topics --bootstrap-server localhost:9092 --list | grep -E "(discovery-tasks|submission-tasks)" || echo "  Warning: Topics may still be initializing"
    
    echo "✓ Kafka topics ready"
else
    echo "⚠️  Kafka command not found. Skipping Kafka topic cleanup."
    echo "   Manual cleanup: Delete and recreate topics 'discovery-tasks' and 'submission-tasks'"
fi

echo ""
echo "========================================="
echo "✅ Reset Complete!"
echo "========================================="
echo ""
echo "The system has been reset. You can now:"
echo "  1. Load domains: ./scripts/load_domains.sh test-domains.csv $CONFIG_FILE"
echo "  2. Start discovery workers: go run cmd/discovery-worker/main.go --config $CONFIG_FILE"
echo "  3. Start submission workers: go run cmd/submission-worker/main.go --config $CONFIG_FILE"
echo ""
