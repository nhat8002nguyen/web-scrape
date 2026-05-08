#!/bin/bash

# List all domains with their current status

set -e

CONFIG_FILE="${1:-config/config.local.yaml}"

# Extract database connection details
DB_HOST=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"')
DB_PORT=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "port:" | awk '{print $2}')
DB_NAME=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "database:" | awk '{print $2}' | tr -d '"')
DB_USER=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "user:" | awk '{print $2}' | tr -d '"')
DB_PASS=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "password:" | awk '{print $2}' | tr -d '"')

export PGPASSWORD="$DB_PASS"

echo "========================================="
echo "All Domains Status"
echo "========================================="
echo ""

# Colorized output using SQL
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << 'EOF'
\pset border 2
\pset format wrapped

SELECT 
    id,
    CASE 
        WHEN status = 'found' THEN '✅ ' || url
        WHEN status = 'not_found' THEN '❌ ' || url
        WHEN status = 'failed' THEN '⚠️ ' || url
        WHEN status = 'pending' THEN '⏳ ' || url
        WHEN status = 'discovery' THEN '🔍 ' || url
        ELSE url
    END as domain,
    status,
    CASE 
        WHEN contact_url IS NOT NULL THEN '✓ Found'
        ELSE '-'
    END as "contact_page",
    attempts,
    LEFT(COALESCE(last_error, '-'), 50) as "error"
FROM domains 
ORDER BY 
    CASE status
        WHEN 'found' THEN 1
        WHEN 'discovery' THEN 2
        WHEN 'pending' THEN 3
        WHEN 'not_found' THEN 4
        WHEN 'failed' THEN 5
    END,
    created_at;
EOF

echo ""
echo "========================================="
echo "Legend:"
echo "  ✅ Found - Contact form discovered"
echo "  ❌ Not Found - No contact form on domain"
echo "  ⚠️  Failed - Error during discovery"
echo "  ⏳ Pending - Waiting to be processed"
echo "  🔍 Discovery - Currently being checked"
echo "========================================="
echo ""

# Show summary
echo "📊 SUMMARY"
echo "----------------------------------------"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t << EOF
SELECT 
    '✅ Found: ' || COUNT(CASE WHEN status = 'found' THEN 1 END)::text ||
    ' | ❌ Not Found: ' || COUNT(CASE WHEN status = 'not_found' THEN 1 END)::text ||
    ' | ⚠️  Failed: ' || COUNT(CASE WHEN status = 'failed' THEN 1 END)::text ||
    ' | ⏳ Pending: ' || COUNT(CASE WHEN status = 'pending' THEN 1 END)::text
FROM domains;
EOF

unset PGPASSWORD

echo ""
echo "Use './scripts/debug_domain.sh <url>' for details on a specific domain"
echo ""
