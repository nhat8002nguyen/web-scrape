#!/bin/bash

# View Results Script - Shows submission results from local testing

echo "========================================="
echo "Local Test Results"
echo "========================================="
echo ""

# Check if PostgreSQL is running
if ! docker ps | grep -q postgres; then
    echo "ERROR: PostgreSQL is not running"
    echo "Start the system first: ./test-local.sh"
    exit 1
fi

# Get statistics
echo "Overall Statistics:"
echo "-------------------"
docker exec postgres psql -U formbot -d form_submissions -t -c "
SELECT 
  'Total Domains: ' || total_domains || E'\n' ||
  'Forms Found: ' || found_domains || E'\n' ||
  'Not Found: ' || not_found_domains || E'\n' ||
  'Failed: ' || failed_domains
FROM domain_stats;
"

echo ""
docker exec postgres psql -U formbot -d form_submissions -t -c "
SELECT 
  'Total Submissions: ' || total_submissions || E'\n' ||
  'Successful: ' || successful_submissions || E'\n' ||
  'Failed: ' || failed_submissions || E'\n' ||
  'Success Rate: ' || success_rate || '%' || E'\n' ||
  'Avg Duration: ' || avg_duration_ms || 'ms' || E'\n' ||
  'Total CAPTCHA Cost: $' || total_captcha_cost
FROM submission_stats;
"

echo ""
echo "Detailed Results:"
echo "-----------------"
docker exec postgres psql -U formbot -d form_submissions -c "
SELECT 
  d.url as domain,
  s.status,
  s.duration_ms,
  s.had_captcha,
  s.error_message
FROM submissions s
JOIN domains d ON s.domain_id = d.id
ORDER BY s.submitted_at DESC;
" | head -20

echo ""
echo "Export to CSV:"
echo "--------------"
echo "Run this command to export results:"
echo ""
echo "docker exec postgres psql -U formbot -d form_submissions -c \\"
echo "  \"COPY (SELECT d.url, s.status, s.duration_ms, s.had_captcha FROM submissions s JOIN domains d ON s.domain_id = d.id) \\"
echo "  TO STDOUT WITH CSV HEADER\" > results.csv"
echo ""
