#!/bin/bash

# Comprehensive diagnostic script

set -e

CONFIG_FILE="${1:-config/config.local.yaml}"

echo "========================================="
echo "🔍 System Diagnostics"
echo "========================================="
echo ""

# 1. Check workers
echo "1️⃣  WORKERS STATUS"
echo "----------------------------------------"
DISCOVERY_COUNT=$(ps aux | grep -E "discovery-worker|cmd/discovery-worker" | grep -v grep | wc -l | tr -d ' ')
SUBMISSION_COUNT=$(ps aux | grep -E "submission-worker|cmd/submission-worker" | grep -v grep | wc -l | tr -d ' ')

if [ "$DISCOVERY_COUNT" -gt 0 ]; then
    echo "✅ Discovery workers running: $DISCOVERY_COUNT"
else
    echo "❌ NO discovery workers running"
fi

if [ "$SUBMISSION_COUNT" -gt 0 ]; then
    echo "✅ Submission workers running: $SUBMISSION_COUNT"
else
    echo "❌ NO submission workers running"
fi
echo ""

# 2. Check database
echo "2️⃣  DATABASE STATUS"
echo "----------------------------------------"

DB_HOST=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"')
DB_PORT=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "port:" | awk '{print $2}')
DB_NAME=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "database:" | awk '{print $2}' | tr -d '"')
DB_USER=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "user:" | awk '{print $2}' | tr -d '"')
DB_PASS=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "password:" | awk '{print $2}' | tr -d '"')

export PGPASSWORD="$DB_PASS"

TOTAL_DOMAINS=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM domains;" | tr -d ' ')
PENDING=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM domains WHERE status='pending';" | tr -d ' ')
FAILED=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM domains WHERE status='failed';" | tr -d ' ')

echo "Total domains in DB: $TOTAL_DOMAINS"
echo "Pending domains: $PENDING"
echo "Failed domains: $FAILED"

if [ "$FAILED" -gt 0 ]; then
    echo "⚠️  WARNING: $FAILED domains are marked as FAILED"
    echo "   This means old failed data wasn't cleared"
fi

if [ "$PENDING" -eq 0 ] && [ "$TOTAL_DOMAINS" -gt 0 ]; then
    echo "⚠️  WARNING: No domains are in PENDING state"
    echo "   Workers need PENDING domains to process"
fi

unset PGPASSWORD
echo ""

# 3. Check Kafka
echo "3️⃣  KAFKA TOPICS"
echo "----------------------------------------"

if command -v docker &> /dev/null && docker ps | grep -q kafka; then
    KAFKA_CONTAINER=$(docker ps --filter "name=kafka" --format "{{.Names}}" | head -n 1)
    
    # Check discovery-tasks topic
    echo "Discovery tasks topic:"
    DISCOVERY_MESSAGES=$(docker exec "$KAFKA_CONTAINER" kafka-run-class.sh kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic discovery-tasks --time -1 2>/dev/null | awk -F ':' '{sum+=$3} END {print sum}')
    
    if [ -z "$DISCOVERY_MESSAGES" ]; then
        DISCOVERY_MESSAGES=0
    fi
    
    echo "  Messages in queue: $DISCOVERY_MESSAGES"
    
    if [ "$DISCOVERY_MESSAGES" -eq 0 ]; then
        echo "  ⚠️  No messages in discovery-tasks topic"
        echo "     This means domains weren't loaded to Kafka"
    fi
    
    # Check consumer groups
    echo ""
    echo "Consumer groups:"
    docker exec "$KAFKA_CONTAINER" kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list 2>/dev/null | grep -E "form-submitters|discovery|submission" || echo "  No consumer groups found"
else
    echo "❌ Kafka container not accessible"
fi

echo ""

# 4. Summary
echo "========================================="
echo "📋 DIAGNOSIS SUMMARY"
echo "========================================="

if [ "$DISCOVERY_COUNT" -eq 0 ]; then
    echo "❌ PROBLEM: Discovery worker is NOT running"
    echo "   Solution: Start worker in a terminal:"
    echo "   go run cmd/discovery-worker/main.go --config $CONFIG_FILE"
    echo ""
fi

if [ "$FAILED" -gt 0 ]; then
    echo "❌ PROBLEM: Database has $FAILED failed domains from previous run"
    echo "   Solution: Reset database:"
    echo "   ./scripts/reset_light.sh"
    echo ""
fi

if [ "$PENDING" -eq 0 ] && [ "$TOTAL_DOMAINS" -gt 0 ]; then
    echo "❌ PROBLEM: No pending domains to process"
    echo "   Solution: Load domains after reset:"
    echo "   ./scripts/load_domains.sh test-domains.csv $CONFIG_FILE"
    echo ""
fi

if [ "$DISCOVERY_MESSAGES" -eq 0 ] && [ "$TOTAL_DOMAINS" -gt 0 ]; then
    echo "❌ PROBLEM: Domains in DB but not in Kafka queue"
    echo "   Solution: Reload domains:"
    echo "   ./scripts/load_domains.sh test-domains.csv $CONFIG_FILE"
    echo ""
fi

if [ "$DISCOVERY_COUNT" -gt 0 ] && [ "$DISCOVERY_MESSAGES" -gt 0 ] && [ "$PENDING" -gt 0 ]; then
    echo "✅ Everything looks good! Workers should be processing."
    echo "   Check worker logs for progress."
fi

echo ""
