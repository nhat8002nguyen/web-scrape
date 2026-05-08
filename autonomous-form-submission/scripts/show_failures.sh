#!/bin/bash

# Show why domains failed with their error messages

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
echo "Failed Domains - Error Details"
echo "========================================="
echo ""

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << 'EOF'
\pset border 2
\pset format wrapped

SELECT 
    id,
    url,
    status,
    attempts,
    updated_at,
    COALESCE(last_error, 'No error message recorded') as error_message
FROM domains 
WHERE status = 'failed'
ORDER BY id;
EOF

unset PGPASSWORD

echo ""
echo "========================================="
echo "💡 Common Failure Reasons:"
echo "   - Navigation timeout (website too slow)"
echo "   - Website is down or unreachable"
echo "   - Chrome/browser initialization failed"
echo "   - Network connectivity issues"
echo "========================================="
