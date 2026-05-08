#!/bin/bash

# Script to load domains into the system

set -e

DOMAINS_FILE="${1:-scripts/sample-domains.csv}"
CONFIG_FILE="${2:-config/config.yaml}"

if [ ! -f "$DOMAINS_FILE" ]; then
    echo "ERROR: Domains file not found: $DOMAINS_FILE"
    exit 1
fi

echo "========================================="
echo "Loading domains into the system"
echo "========================================="
echo "Domains file: $DOMAINS_FILE"
echo "Config file: $CONFIG_FILE"
echo ""

# Count domains
DOMAIN_COUNT=$(tail -n +2 "$DOMAINS_FILE" | wc -l)
echo "Total domains to process: $DOMAIN_COUNT"
echo ""

# Run domain loader
go run cmd/domain-loader/main.go \
    --config "$CONFIG_FILE" \
    --file "$DOMAINS_FILE" \
    --batch 100

echo ""
echo "========================================="
echo "Domain loading complete!"
echo "========================================="
echo ""
echo "Check Kafka topic 'discovery-tasks' for published tasks"
echo "Monitor progress: redis-cli GET progress:domains:loaded"
echo ""
