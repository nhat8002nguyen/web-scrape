# Local Testing Guide

Complete guide to run and test the autonomous form submission system on your local computer with a small dataset.

## Prerequisites

### Required Software
1. **Docker Desktop** (for Mac/Windows) or Docker Engine (for Linux)
   - Download: https://www.docker.com/products/docker-desktop/
   - Minimum: 8GB RAM allocated to Docker
   
2. **Go 1.21+**
   - Download: https://go.dev/dl/
   - Verify: `go version`

3. **Git** (for cloning dependencies)

### API Keys (Optional for Local Testing)
- **CapSolver API Key** - Get free credits at https://capsolver.com
  - Can skip if testing without CAPTCHA solving
  - Set budget to $0 to skip all CAPTCHAs

---

## Step 1: Setup Project

```bash
# Navigate to project directory
cd /Users/nhatnguyen/Workspaces/web-scrape/autonomous-form-submission

# Download Go dependencies
go mod download

# Verify dependencies
go mod tidy
```

---

## Step 2: Configure for Local Testing

### Create Local Configuration

Create a local config file for testing:

```bash
cp config/config.yaml config/config.local.yaml
```

Edit `config/config.local.yaml` to reduce worker counts for local testing:

```yaml
kafka:
  brokers: ["localhost:9092"]
  topics:
    discovery: "discovery-tasks"
    submission: "submission-tasks"
  consumer_group: "form-submitters-local"

redis:
  host: "localhost:6379"
  password: ""
  db: 0
  ttl_days: 7

postgres:
  host: "localhost"
  port: 5432
  database: "form_submissions"
  user: "formbot"
  password: "formbot123"
  
captcha:
  provider: "capsolver"
  api_key: "${CAPSOLVER_API_KEY}"
  timeout_seconds: 30
  max_retries: 2

proxy:
  provider: "webshare"
  api_key: "${PROXY_API_KEY}"
  enable_direct: true  # Use direct connection for testing
  fallback_free_proxies: false
  
workers:
  discovery_count: 2      # Reduced from 5
  submission_count: 3     # Reduced from 10
  concurrent_browsers: 2  # Reduced from 3

budget:
  captcha_limit_usd: 0.0  # Set to 0 to skip CAPTCHAs for testing
  captcha_solve_types: ["recaptcha_v2_checkbox"]
  skip_on_budget_exceeded: true

browser:
  headless: true          # Set to false to see browser in action
  disable_gpu: true
  timeout_seconds: 30

monitoring:
  prometheus_port: 9090
  metrics_port: 8080
  log_level: "info"
```

### Setup Environment Variables

```bash
# Create .env file
cat > .env << 'EOF'
CAPSOLVER_API_KEY=your_key_here_or_leave_empty
PROXY_API_KEY=optional
KAFKA_BROKERS=localhost:9092
REDIS_HOST=localhost:6379
POSTGRES_HOST=localhost
EOF

# Load environment variables
source .env
```

---

## Step 3: Start Infrastructure Services

### Option A: Using Docker Compose (Recommended)

Start Kafka, Redis, and PostgreSQL:

```bash
# Start all infrastructure services
docker-compose -f deployments/docker/docker-compose.instance1.yml up -d zookeeper kafka redis postgres

# Wait for services to be ready (30 seconds)
sleep 30

# Verify services are running
docker-compose -f deployments/docker/docker-compose.instance1.yml ps

# Check logs if needed
docker-compose -f deployments/docker/docker-compose.instance1.yml logs kafka
```

### Option B: Using Individual Docker Commands

If you prefer to start services individually:

```bash
# Start Kafka (includes Zookeeper)
docker run -d --name zookeeper \
  -p 2181:2181 \
  -e ZOOKEEPER_CLIENT_PORT=2181 \
  confluentinc/cp-zookeeper:7.5.0

docker run -d --name kafka \
  -p 9092:9092 \
  -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  --link zookeeper \
  confluentinc/cp-kafka:7.5.0

# Start Redis
docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine

# Start PostgreSQL
docker run -d --name postgres \
  -p 5432:5432 \
  -e POSTGRES_DB=form_submissions \
  -e POSTGRES_USER=formbot \
  -e POSTGRES_PASSWORD=formbot123 \
  postgres:15-alpine
```

### Initialize Database Schema

```bash
# Wait for PostgreSQL to be ready
sleep 10

# Run migrations
docker exec -i postgres psql -U formbot -d form_submissions < migrations/001_init_schema.sql

# Verify tables created
docker exec postgres psql -U formbot -d form_submissions -c "\dt"
```

### Verify Services

```bash
# Test Kafka
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Test Redis
docker exec redis redis-cli ping

# Test PostgreSQL
docker exec postgres pg_isready -U formbot
```

---

## Step 4: Prepare Test Data

### Create Small Test Dataset

```bash
# Create a test domains file with 5 domains
cat > test-domains.csv << 'EOF'
domain
example.com
httpbin.org
postman-echo.com
webhook.site
reqres.in
EOF
```

These domains are API testing sites that have simple forms or endpoints.

---

## Step 5: Run Services Locally

### Terminal 1: Run Discovery Worker

```bash
# Run discovery worker
go run cmd/discovery-worker/main.go --config config/config.local.yaml
```

You should see:
```
{"level":"info","msg":"Starting discovery worker"}
{"level":"info","msg":"Kafka consumer started"}
{"level":"info","msg":"Discovery worker started, waiting for tasks"}
```

### Terminal 2: Run Submission Worker

```bash
# Run submission worker
go run cmd/submission-worker/main.go --config config/config.local.yaml
```

You should see:
```
{"level":"info","msg":"Starting submission worker"}
{"level":"info","msg":"Kafka consumer started"}
{"level":"info","msg":"Submission worker started, waiting for tasks"}
```

### Terminal 3: Load Test Domains

```bash
# Load the test domains
go run cmd/domain-loader/main.go \
  --config config/config.local.yaml \
  --file test-domains.csv \
  --batch 10
```

Expected output:
```
{"level":"info","msg":"Starting domain loader"}
{"level":"info","msg":"Domains loaded","count":5}
{"level":"info","msg":"Batch processed","published":5,"skipped":0}
{"level":"info","msg":"Domain loading complete","total_domains":5,"published":5}
```

---

## Step 6: Monitor Progress

### Option A: Watch Logs

In your terminals, you'll see the workers processing:

**Discovery Worker Output:**
```
{"level":"info","msg":"Processing discovery task","domain_id":1,"url":"https://example.com"}
{"level":"info","msg":"Contact form found","url":"https://example.com/contact"}
```

**Submission Worker Output:**
```
{"level":"info","msg":"Processing submission task","domain_id":1,"form_url":"https://example.com/contact"}
{"level":"info","msg":"Submission completed","status":"success"}
```

### Option B: Check Redis Progress

```bash
# Open a Redis CLI session
docker exec -it redis redis-cli

# Check progress counters
GET progress:domains:total
GET progress:domains:processed
GET progress:forms:found
GET progress:submissions:success
GET progress:submissions:failed
```

### Option C: Query PostgreSQL

```bash
# Check domains discovered
docker exec postgres psql -U formbot -d form_submissions -c \
  "SELECT url, status, contact_url FROM domains;"

# Check submissions
docker exec postgres psql -U formbot -d form_submissions -c \
  "SELECT d.url, s.status, s.duration_ms, s.had_captcha 
   FROM submissions s 
   JOIN domains d ON s.domain_id = d.id 
   ORDER BY s.submitted_at DESC;"

# Get statistics
docker exec postgres psql -U formbot -d form_submissions -c \
  "SELECT * FROM submission_stats;"
```

### Option D: Prometheus Metrics

Open browser to http://localhost:9090

Useful queries:
```promql
# Total forms found
forms_found_total

# Submission success rate
rate(submissions_successful_total[5m])

# Active browser contexts
browser_contexts_active
```

---

## Step 7: View Results

### Export Results to CSV

```bash
# Export all results
docker exec postgres psql -U formbot -d form_submissions -c \
  "COPY (
    SELECT 
      d.url as domain,
      s.form_url,
      s.status,
      s.submitted_at,
      s.duration_ms,
      s.error_message
    FROM submissions s
    JOIN domains d ON s.domain_id = d.id
    ORDER BY s.submitted_at DESC
  ) TO STDOUT WITH CSV HEADER" > test-results.csv

# View results
cat test-results.csv
```

### View in Terminal

```bash
# Pretty print results
docker exec postgres psql -U formbot -d form_submissions -c \
  "SELECT 
    d.url,
    s.status,
    s.duration_ms,
    s.had_captcha,
    s.captcha_solved
   FROM submissions s
   JOIN domains d ON s.domain_id = d.id
   ORDER BY s.submitted_at DESC;" \
  | column -t -s '|'
```

---

## Step 8: Testing with Headless Browser OFF

To see the browser in action:

1. Edit `config/config.local.yaml`:
```yaml
browser:
  headless: false  # Change from true to false
```

2. Restart the submission worker

3. Run a test domain

You'll see Chrome browser windows opening and the automation in action!

---

## Common Testing Scenarios

### Test 1: Simple Discovery (No Submission)

```bash
# Only run discovery worker
go run cmd/discovery-worker/main.go --config config/config.local.yaml &

# Load domains
go run cmd/domain-loader/main.go --config config/config.local.yaml --file test-domains.csv

# Wait 30 seconds, then check Redis for discovered forms
docker exec redis redis-cli GET progress:forms:found
```

### Test 2: With CAPTCHA Budget

```bash
# Edit config to enable CAPTCHA solving
sed -i '' 's/captcha_limit_usd: 0.0/captcha_limit_usd: 1.0/' config/config.local.yaml

# Add your CapSolver API key
export CAPSOLVER_API_KEY="your_actual_key"

# Run the full pipeline
# (discovery worker + submission worker + load domains)
```

### Test 3: Error Handling

```bash
# Create a file with invalid domains
cat > error-test.csv << 'EOF'
domain
invalid-domain-that-does-not-exist.com
http://localhost:9999
EOF

# Load and watch error handling
go run cmd/domain-loader/main.go --config config/config.local.yaml --file error-test.csv

# Check error logs
docker exec postgres psql -U formbot -d form_submissions -c \
  "SELECT error_type, error_message FROM errors ORDER BY created_at DESC LIMIT 5;"
```

---

## Troubleshooting

### Issue: "Connection refused" errors

**Solution:** Make sure infrastructure services are running
```bash
docker-compose -f deployments/docker/docker-compose.instance1.yml ps
```

### Issue: Kafka consumer not starting

**Solution:** Wait for Kafka to be fully ready (can take 30-60 seconds)
```bash
# Check Kafka logs
docker-compose -f deployments/docker/docker-compose.instance1.yml logs kafka

# Test Kafka connection
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Issue: "Failed to create browser context"

**Solution:** Check if you have Chrome/Chromium installed
```bash
# On Mac
brew install chromium

# Or let chromedp download it automatically
# It will be downloaded to ~/.cache/chromedp/
```

### Issue: Out of memory

**Solution:** Reduce worker counts in config
```yaml
workers:
  discovery_count: 1
  submission_count: 1
  concurrent_browsers: 1
```

### Issue: Workers not processing

**Solution:** Check Kafka topics have messages
```bash
# List topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Check message count
docker exec kafka kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic discovery-tasks
```

---

## Cleanup

### Stop Workers
Press `Ctrl+C` in each terminal running the workers

### Stop Infrastructure
```bash
# Stop all services
docker-compose -f deployments/docker/docker-compose.instance1.yml down

# Or stop individual containers
docker stop kafka zookeeper redis postgres

# Remove containers (optional)
docker rm kafka zookeeper redis postgres

# Remove volumes to start fresh (optional)
docker-compose -f deployments/docker/docker-compose.instance1.yml down -v
```

### Clean Data
```bash
# Clear Redis
docker exec redis redis-cli FLUSHDB

# Drop PostgreSQL database
docker exec postgres psql -U formbot -c "DROP DATABASE form_submissions;"
docker exec postgres psql -U formbot -c "CREATE DATABASE form_submissions;"
docker exec -i postgres psql -U formbot -d form_submissions < migrations/001_init_schema.sql
```

---

## Quick Start Script

Create a helper script for easy testing:

```bash
cat > test-local.sh << 'EOF'
#!/bin/bash
set -e

echo "Starting infrastructure..."
docker-compose -f deployments/docker/docker-compose.instance1.yml up -d zookeeper kafka redis postgres

echo "Waiting for services..."
sleep 30

echo "Initializing database..."
docker exec -i postgres psql -U formbot -d form_submissions < migrations/001_init_schema.sql

echo "Starting discovery worker in background..."
go run cmd/discovery-worker/main.go --config config/config.local.yaml &
DISCOVERY_PID=$!

echo "Starting submission worker in background..."
go run cmd/submission-worker/main.go --config config/config.local.yaml &
SUBMISSION_PID=$!

echo "Waiting for workers to start..."
sleep 5

echo "Loading test domains..."
go run cmd/domain-loader/main.go --config config/config.local.yaml --file test-domains.csv

echo ""
echo "System is running! Workers processing in background."
echo "Discovery Worker PID: $DISCOVERY_PID"
echo "Submission Worker PID: $SUBMISSION_PID"
echo ""
echo "Monitor progress:"
echo "  Redis: docker exec redis redis-cli GET progress:submissions:success"
echo "  Database: docker exec postgres psql -U formbot -d form_submissions -c 'SELECT COUNT(*) FROM submissions;'"
echo "  Prometheus: http://localhost:9090"
echo ""
echo "Stop workers: kill $DISCOVERY_PID $SUBMISSION_PID"
EOF

chmod +x test-local.sh
```

Run it:
```bash
./test-local.sh
```

---

## Performance on Local Machine

**Expected performance with test dataset (5 domains):**
- Processing time: 2-5 minutes
- Memory usage: ~500MB-1GB
- CPU usage: 10-30%

**Scaling for larger local tests:**
- 50 domains: ~10-15 minutes
- 100 domains: ~20-30 minutes
- 1000 domains: ~3-4 hours (requires increasing Docker memory to 8GB+)

---

## Next Steps

Once local testing is successful:

1. ✅ Verify all 5 test domains are processed
2. ✅ Check submission success rate in PostgreSQL
3. ✅ Review Prometheus metrics
4. ✅ Test with your actual domain list (10-50 domains)
5. ✅ When ready, deploy to AWS using DEPLOYMENT.md

---

**Happy Testing! 🚀**
