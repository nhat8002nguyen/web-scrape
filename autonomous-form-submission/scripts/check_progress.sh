#!/bin/bash

# Quick script to check system progress

CONFIG_FILE="${1:-config/config.local.yaml}"

# Extract database connection details
DB_HOST=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"')
DB_PORT=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "port:" | awk '{print $2}')
DB_NAME=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "database:" | awk '{print $2}' | tr -d '"')
DB_USER=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "user:" | awk '{print $2}' | tr -d '"')
DB_PASS=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "password:" | awk '{print $2}' | tr -d '"')

# Extract Redis connection details
REDIS_HOST=$(grep -A 5 "^redis:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"' | cut -d: -f1)
REDIS_PORT=$(grep -A 5 "^redis:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"' | cut -d: -f2)

if [ -z "$REDIS_PORT" ]; then
    REDIS_PORT="6379"
fi

export PGPASSWORD="$DB_PASS"

clear
echo "========================================="
echo "Autonomous Form Submission - Progress"
echo "========================================="
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

echo "📊 DOMAIN STATISTICS"
echo "----------------------------------------"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F"," -c "SELECT * FROM domain_stats;" | \
while IFS=, read -r total pending discovery found not_found failed with_contact; do
    echo "Total Domains:           $total"
    echo "Pending:                 $pending"
    echo "In Discovery:            $discovery"
    echo "Found Contact Forms:     $found"
    echo "No Contact Form:         $not_found"
    echo "Failed:                  $failed"
    echo "With Contact URL:        $with_contact"
done

echo ""
echo "📝 SUBMISSION STATISTICS"
echo "----------------------------------------"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F"," -c "SELECT * FROM submission_stats;" | \
while IFS=, read -r total successful failed skipped captcha_failed success_rate with_captcha solved cost avg_duration last_sub; do
    echo "Total Submissions:       $total"
    echo "Successful:              $successful"
    echo "Failed:                  $failed"
    echo "Skipped:                 $skipped"
    echo "CAPTCHA Failed:          $captcha_failed"
    echo "Success Rate:            $success_rate%"
    echo "With CAPTCHA:            $with_captcha"
    echo "CAPTCHAs Solved:         $solved"
    echo "Total CAPTCHA Cost:      \$${cost:-0.00}"
    echo "Avg Duration:            ${avg_duration:-0}ms"
    if [ -n "$last_sub" ] && [ "$last_sub" != "" ]; then
        echo "Last Submission:         $last_sub"
    fi
done

echo ""
echo "📦 REDIS CACHE"
echo "----------------------------------------"
DOMAINS_LOADED=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" GET progress:domains:loaded 2>/dev/null || echo "0")
FORMS_FOUND=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" GET progress:forms:found 2>/dev/null || echo "0")
SUBMISSIONS_SUCCESS=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" GET progress:submissions:success 2>/dev/null || echo "0")
SUBMISSIONS_FAILED=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" GET progress:submissions:failed 2>/dev/null || echo "0")
SUBMISSIONS_SKIPPED=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" GET progress:submissions:skipped 2>/dev/null || echo "0")

echo "Domains Loaded:          ${DOMAINS_LOADED:-0}"
echo "Forms Found (cache):     ${FORMS_FOUND:-0}"
echo "Submissions Success:     ${SUBMISSIONS_SUCCESS:-0}"
echo "Submissions Failed:      ${SUBMISSIONS_FAILED:-0}"
echo "Submissions Skipped:     ${SUBMISSIONS_SKIPPED:-0}"

echo ""
echo "🔄 RECENT ERRORS (Last 5)"
echo "----------------------------------------"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
    "SELECT created_at, error_type, LEFT(error_message, 80) as error 
     FROM errors 
     ORDER BY created_at DESC 
     LIMIT 5;" 2>/dev/null || echo "No errors or error table not accessible"

echo ""
echo "📋 DOMAIN STATUS SUMMARY"
echo "----------------------------------------"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t << 'EOSQL'
SELECT 
    CASE status
        WHEN 'found' THEN '✅ FOUND'
        WHEN 'not_found' THEN '❌ NOT FOUND'
        WHEN 'failed' THEN '⚠️  FAILED'
        WHEN 'pending' THEN '⏳ PENDING'
        WHEN 'discovery' THEN '🔍 DISCOVERING'
    END || ': ' || url
FROM domains 
ORDER BY 
    CASE status
        WHEN 'found' THEN 1
        WHEN 'discovery' THEN 2
        WHEN 'pending' THEN 3
        WHEN 'not_found' THEN 4
        WHEN 'failed' THEN 5
    END,
    created_at
LIMIT 20;
EOSQL

unset PGPASSWORD

echo ""
echo "========================================="
echo "💡 TIP: For detailed logs, watch worker output"
echo "   ./scripts/list_domains.sh - Show all domains"
echo "   ./scripts/debug_domain.sh <url> - Debug specific domain"
echo "========================================="
