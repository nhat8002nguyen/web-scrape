#!/bin/bash

# Health check script for the distributed system

set -e

echo "========================================="
echo "System Health Check"
echo "========================================="
echo ""

# Check Kafka
echo "Checking Kafka..."
if docker ps | grep -q kafka; then
    echo "✓ Kafka is running"
    docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | head -5
else
    echo "✗ Kafka is not running"
fi
echo ""

# Check Redis
echo "Checking Redis..."
if docker ps | grep -q redis; then
    echo "✓ Redis is running"
    redis-cli ping 2>/dev/null || echo "  Could not connect to Redis"
else
    echo "✗ Redis is not running"
fi
echo ""

# Check PostgreSQL
echo "Checking PostgreSQL..."
if docker ps | grep -q postgres; then
    echo "✓ PostgreSQL is running"
    docker exec postgres pg_isready -U formbot 2>/dev/null || echo "  Could not connect to PostgreSQL"
else
    echo "✗ PostgreSQL is not running"
fi
echo ""

# Check Workers
echo "Checking Workers..."
DISCOVERY_COUNT=$(docker ps | grep discovery-worker | wc -l)
SUBMISSION_COUNT=$(docker ps | grep submission-worker | wc -l)
echo "✓ Discovery workers: $DISCOVERY_COUNT/5"
echo "✓ Submission workers: $SUBMISSION_COUNT/10"
echo ""

# Check Prometheus
echo "Checking Prometheus..."
if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✓ Prometheus is healthy"
    echo "  Access at: http://localhost:9090"
else
    echo "✗ Prometheus is not accessible"
fi
echo ""

# Get Redis stats
echo "System Stats (from Redis):"
redis-cli GET progress:domains:total 2>/dev/null | xargs -I {} echo "  Total domains: {}"
redis-cli GET progress:domains:processed 2>/dev/null | xargs -I {} echo "  Processed: {}"
redis-cli GET progress:forms:found 2>/dev/null | xargs -I {} echo "  Forms found: {}"
redis-cli GET progress:submissions:success 2>/dev/null | xargs -I {} echo "  Successful submissions: {}"
redis-cli GET progress:submissions:failed 2>/dev/null | xargs -I {} echo "  Failed submissions: {}"
echo ""

# Get CAPTCHA budget
echo "Budget Status:"
redis-cli GET budget:captcha:spent 2>/dev/null | xargs -I {} echo "  CAPTCHA spent: \${}"
echo ""

echo "========================================="
echo "Health check complete!"
echo "========================================="
