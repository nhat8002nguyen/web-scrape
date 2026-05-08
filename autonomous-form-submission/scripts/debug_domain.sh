#!/bin/bash

# Debug script to check a specific domain's discovery status

set -e

CONFIG_FILE="${1:-config/config.local.yaml}"
DOMAIN="${2}"

if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 [config-file] <domain>"
    echo ""
    echo "Example:"
    echo "  $0 config/config.local.yaml https://vietnam.acclime.com/"
    exit 1
fi

# Extract database connection details
DB_HOST=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "host:" | awk '{print $2}' | tr -d '"')
DB_PORT=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "port:" | awk '{print $2}')
DB_NAME=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "database:" | awk '{print $2}' | tr -d '"')
DB_USER=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "user:" | awk '{print $2}' | tr -d '"')
DB_PASS=$(grep -A 5 "^postgres:" "$CONFIG_FILE" | grep "password:" | awk '{print $2}' | tr -d '"')

export PGPASSWORD="$DB_PASS"

echo "========================================="
echo "Debug Domain: $DOMAIN"
echo "========================================="
echo ""

echo "📊 DOMAIN STATUS"
echo "----------------------------------------"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF
SELECT 
    id,
    url,
    status,
    contact_url,
    attempts,
    created_at,
    updated_at,
    last_error
FROM domains 
WHERE url LIKE '%${DOMAIN}%' OR url = '${DOMAIN}'
ORDER BY created_at DESC
LIMIT 1;
EOF

echo ""
echo "📝 CONTACT FORMS (if found)"
echo "----------------------------------------"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF
SELECT 
    cf.id,
    cf.url,
    cf.has_captcha,
    cf.captcha_type,
    jsonb_array_length(cf.fields) as field_count,
    cf.fields
FROM contact_forms cf
JOIN domains d ON cf.domain_id = d.id
WHERE d.url LIKE '%${DOMAIN}%' OR d.url = '${DOMAIN}'
ORDER BY cf.created_at DESC
LIMIT 1;
EOF

echo ""
echo "📤 SUBMISSIONS (if any)"
echo "----------------------------------------"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF
SELECT 
    s.id,
    s.form_url,
    s.status,
    s.submitted_at,
    s.completed_at,
    s.duration_ms,
    s.had_captcha,
    s.error_message
FROM submissions s
JOIN domains d ON s.domain_id = d.id
WHERE d.url LIKE '%${DOMAIN}%' OR d.url = '${DOMAIN}'
ORDER BY s.submitted_at DESC
LIMIT 5;
EOF

echo ""
echo "❌ ERRORS (if any)"
echo "----------------------------------------"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF
SELECT 
    e.created_at,
    e.error_type,
    e.error_message,
    e.context
FROM errors e
JOIN domains d ON e.domain_id = d.id
WHERE d.url LIKE '%${DOMAIN}%' OR d.url = '${DOMAIN}'
ORDER BY e.created_at DESC
LIMIT 5;
EOF

unset PGPASSWORD

echo ""
echo "========================================="
echo "To see detailed logs, check the worker output"
echo "========================================="
