#!/bin/bash

# Quick Local Testing Script
# This script starts all infrastructure and workers for local testing

set -e

echo "========================================="
echo "Local Testing - Quick Start"
echo "========================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "ERROR: Docker is not installed"; exit 1; }
command -v go >/dev/null 2>&1 || { echo "ERROR: Go is not installed"; exit 1; }

# Download Go dependencies if not already downloaded
if [ ! -f "go.sum" ]; then
    echo "Downloading Go dependencies (first time setup)..."
    go mod download
    echo "✓ Dependencies downloaded"
fi

# Check if config exists
if [ ! -f "config/config.local.yaml" ]; then
    echo "Creating local config from template..."
    cat > config/config.local.yaml << 'CONFIGEOF'
kafka:
  brokers: ["localhost:9092"]
  topics:
    discovery: "discovery-tasks"
    submission: "submission-tasks"
  consumer_group: "form-submitters-local"
  partition_count:
    discovery: 3
    submission: 5

redis:
  host: "localhost:6379"
  password: ""
  db: 0
  ttl_days: 7
  pool_size: 10

postgres:
  host: "localhost"
  port: 5432
  database: "form_submissions"
  user: "formbot"
  password: "formbot123"
  max_connections: 20
  
captcha:
  provider: "capsolver"
  api_key: "${CAPSOLVER_API_KEY}"
  timeout_seconds: 30
  max_retries: 2
  solve_delay_ms: 1000

proxy:
  provider: "webshare"
  api_key: "${PROXY_API_KEY}"
  rotation_strategy: "per_domain"
  fallback_free_proxies: true
  enable_direct: true
  health_check_interval_seconds: 300
  max_failures_before_remove: 3
  
workers:
  discovery_count: 2
  submission_count: 3
  concurrent_browsers: 2
  max_tasks_per_worker: 100
  restart_interval_minutes: 60

budget:
  captcha_limit_usd: 0.0
  captcha_solve_types: ["recaptcha_v2_checkbox"]
  skip_on_budget_exceeded: true
  alert_threshold_usd: 25.0

browser:
  headless: false
  disable_gpu: true
  window_size: "1920,1080"
  user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
  timeout_seconds: 30
  page_load_timeout_seconds: 20

discovery:
  max_depth: 3
  max_pages_per_domain: 10
  contact_path_patterns:
    - "/contact"
    - "/contact-us"
    - "/get-in-touch"
    - "/support"
    - "/help"
    - "/reach-us"
    - "/about/contact"
  
submission:
  verify_success_timeout_seconds: 10
  screenshot_on_failure: true
  max_retries: 2
  retry_delay_seconds: 5

monitoring:
  prometheus_port: 9090
  metrics_port: 8080
  log_level: "info"
  
templates:
  - name: "default"
    email: "contact@business-inquiry.com"
    sender_name: "Michael Anderson"
    company: "TechVentures Inc"
    phone: "+1-555-0123"
    subject: "Business Partnership Inquiry"
    message: |
      Hello,
      
      I came across your website and was impressed by your offerings. 
      I represent TechVentures Inc, and we're interested in exploring 
      potential partnership opportunities.
      
      Would you be available for a brief call to discuss how we might 
      work together?
      
      Best regards,
      Michael Anderson
CONFIGEOF
    echo "✓ Local config created"
fi

# Create test domains if not exist
if [ ! -f "test-domains.csv" ]; then
    echo "Creating test domains file..."
    cat > test-domains.csv << 'EOF'
domain
https://vietnam.acclime.com/
https://www.avtech.com.au/
afg.vn
https://alchemy-asia.com/
https://aminds.com/
https://anthonyinnovations.com.au/
anz.com
https://artemisdigital.com/
https://aswhiteglobal.com/
https://asiasummitconsulting.com/
https://www.asif.foundation/
EOF
    echo "✓ Test domains file created (11 domains)"
fi

# Start infrastructure
echo ""
echo "Starting infrastructure services..."
docker-compose -f deployments/docker/docker-compose.instance1.yml up -d zookeeper kafka redis postgres

echo "Waiting for services to be ready (30 seconds)..."
sleep 30

# Check services
echo "Checking services..."
docker-compose -f deployments/docker/docker-compose.instance1.yml ps

# Initialize database
echo ""
echo "Initializing database schema..."
docker exec -i postgres psql -U formbot -d form_submissions < migrations/001_init_schema.sql 2>/dev/null || true

echo "✓ Database initialized"

# Create logs directory
mkdir -p logs

# Start workers in background
echo ""
echo "Starting workers..."

echo "  Starting discovery worker..."
go run cmd/discovery-worker/main.go --config config/config.local.yaml --metrics-port 8080 > logs/discovery-worker.log 2>&1 &
DISCOVERY_PID=$!
echo "  ✓ Discovery worker started (PID: $DISCOVERY_PID)"

echo "  Starting submission worker..."
go run cmd/submission-worker/main.go --config config/config.local.yaml --metrics-port 0 > logs/submission-worker.log 2>&1 &
SUBMISSION_PID=$!
echo "  ✓ Submission worker started (PID: $SUBMISSION_PID)"

# Save PIDs for cleanup
echo "$DISCOVERY_PID" > logs/discovery-worker.pid
echo "$SUBMISSION_PID" > logs/submission-worker.pid

echo "  Waiting for workers to initialize..."
sleep 5

# Load test domains
echo ""
echo "Loading test domains..."
go run cmd/domain-loader/main.go \
  --config config/config.local.yaml \
  --file test-domains.csv \
  --batch 10

echo ""
echo "========================================="
echo "System is Running!"
echo "========================================="
echo ""
echo "Workers are processing in background:"
echo "  Discovery Worker PID: $DISCOVERY_PID"
echo "  Submission Worker PID: $SUBMISSION_PID"
echo ""
echo "Logs:"
echo "  Discovery: tail -f logs/discovery-worker.log"
echo "  Submission: tail -f logs/submission-worker.log"
echo ""
echo "Monitor Progress:"
echo "  Redis: docker exec redis redis-cli GET progress:submissions:success"
echo "  Database: docker exec postgres psql -U formbot -d form_submissions -c 'SELECT COUNT(*) FROM submissions;'"
echo "  Prometheus: http://localhost:9090"
echo ""
echo "View Results:"
echo "  ./scripts/health_check.sh"
echo ""
echo "Stop System:"
echo "  ./stop-local.sh"
echo ""
echo "Processing 5 domains should complete in 2-5 minutes..."
echo ""
