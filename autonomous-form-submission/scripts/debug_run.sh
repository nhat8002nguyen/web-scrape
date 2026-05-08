#!/bin/bash

# Debug mode - Run discovery with visible browser to see what's happening

set -e

DOMAIN="${1}"

if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain-url>"
    echo ""
    echo "Example:"
    echo "  $0 https://vietnam.acclime.com/"
    echo ""
    echo "This will:"
    echo "  1. Stop any running workers"
    echo "  2. Reset and load just this one domain"
    echo "  3. Start discovery worker in DEBUG mode (visible browser)"
    echo "  4. You can watch the browser navigate and check pages"
    exit 1
fi

CONFIG_FILE="config/config.debug.yaml"

echo "========================================="
echo "🔍 Debug Mode - Visible Browser"
echo "========================================="
echo "Domain: $DOMAIN"
echo "Config: $CONFIG_FILE"
echo ""

# Stop any running workers
echo "Step 1: Stopping workers..."
pkill -9 -f "discovery-worker" 2>/dev/null && echo "  ✓ Stopped discovery workers" || echo "  - No workers running"
pkill -9 -f "submission-worker" 2>/dev/null && echo "  ✓ Stopped submission workers" || echo "  - No workers running"
sleep 2

# Kill Chrome instances
echo ""
echo "Step 2: Cleaning up Chrome..."
pkill -9 "Google Chrome" 2>/dev/null && echo "  ✓ Chrome closed" || echo "  - No Chrome running"
sleep 1

# Reset system
echo ""
echo "Step 3: Resetting system..."
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

# Reset Kafka consumer groups
if command -v docker &> /dev/null && docker ps | grep -q kafka; then
    KAFKA_CONTAINER=$(docker ps --filter "name=kafka" --format "{{.Names}}" | head -n 1)
    
    # Delete consumer groups to reset offsets
    docker exec "$KAFKA_CONTAINER" kafka-consumer-groups --bootstrap-server localhost:9092 --delete --group form-submitters-discovery 2>/dev/null || true
    docker exec "$KAFKA_CONTAINER" kafka-consumer-groups --bootstrap-server localhost:9092 --delete --group form-submitters-submission 2>/dev/null || true
    sleep 1
fi

echo "  ✓ Database, cache, and Kafka consumer groups cleared"

# Create temp domain file
echo ""
echo "Step 4: Loading domain to Kafka..."
TEMP_FILE=$(mktemp)
echo "domain" > "$TEMP_FILE"
echo "$DOMAIN" >> "$TEMP_FILE"

# Wait a moment to ensure consumer groups are deleted
sleep 2

./scripts/load_domains.sh "$TEMP_FILE" "$CONFIG_FILE"
rm "$TEMP_FILE"

# Verify domain was loaded to Kafka (not database - that happens when worker processes it)
echo ""
echo "  ✓ Domain published to Kafka (discovery-tasks topic)"
echo ""
echo "Note: Domain will appear in database once discovery worker processes it"

echo ""
echo "========================================="
echo "🚀 Starting Discovery Worker in Debug Mode"
echo "========================================="
echo ""
echo "📌 WHAT TO WATCH FOR:"
echo ""
echo "  1. Chrome window will open (VISIBLE)"
echo "  2. Watch it navigate to different pages:"
echo "     - /contact"
echo "     - /contact-us"
echo "     - /get-in-touch"
echo "     - etc."
echo ""
echo "  3. In the terminal, you'll see:"
echo "     📝 Found X form(s) on page"
echo "     📋 Form details (email?, message?)"
echo "     ✅ or ❌ If contact form detected"
echo ""
echo "  4. Browser will stay open so you can inspect"
echo ""
echo "========================================="
echo "Press Ctrl+C to stop when done"
echo "========================================="
echo ""

sleep 2

# Run discovery worker
go run cmd/discovery-worker/main.go --config "$CONFIG_FILE"
