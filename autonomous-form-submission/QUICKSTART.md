# Quick Start Guide - macOS Local Development

A step-by-step guide to get the system running on your Mac.

## Prerequisites

1. **Install required tools:**
   ```bash
   brew install postgresql redis go
   ```

2. **Start Docker Desktop** (for Kafka, Redis, PostgreSQL containers)

3. **Start infrastructure:**
   ```bash
   cd /Users/nhatnguyen/Workspaces/web-scrape/autonomous-form-submission
   docker-compose -f deployments/docker/docker-compose.instance1.yml up -d
   ```

4. **Wait for services to be ready (30 seconds):**
   ```bash
   ./scripts/health_check.sh
   ```

## Reset and Load Test Domains

**Quick command (all-in-one):**
```bash
./scripts/reset_and_reload_test_domains.sh
```

This will:
- ✅ Clear all databases and caches
- ✅ Reset Kafka consumer groups
- ✅ Load test-domains.csv (11 domains)
- ✅ Prepare system for fresh run

## Run Workers

Open 3 terminal windows:

### Terminal 1: Discovery Worker
```bash
cd /Users/nhatnguyen/Workspaces/web-scrape/autonomous-form-submission
go run cmd/discovery-worker/main.go --config config/config.local.yaml
```

**What it does:** Crawls domains to find contact forms

### Terminal 2: Submission Worker
```bash
cd /Users/nhatnguyen/Workspaces/web-scrape/autonomous-form-submission
go run cmd/submission-worker/main.go --config config/config.local.yaml
```

**What it does:** Fills and submits discovered contact forms

### Terminal 3: Progress Monitor
```bash
cd /Users/nhatnguyen/Workspaces/web-scrape/autonomous-form-submission
./scripts/monitor.sh
```

**What it shows:** Real-time statistics (refreshes every 5 seconds)

## Monitor Progress

The monitor will show:
```
📊 DOMAIN STATISTICS
Total Domains:           11
Pending:                 0
In Discovery:            2
Found Contact Forms:     5
No Contact Form:         3
Failed:                  1

📝 SUBMISSION STATISTICS
Total Submissions:       5
Successful:              4
Failed:                  1
Success Rate:            80.00%
Total CAPTCHA Cost:      $0.00
```

## Common Tasks

### Check Progress Once (no auto-refresh)
```bash
./scripts/check_progress.sh
```

### Reset and Start Over
```bash
# Stop workers (Ctrl+C in each terminal)

# Reset everything
./scripts/reset_and_reload_test_domains.sh

# Restart workers (see above)
```

### Load Different Domains
```bash
# Stop workers first

# Reset
./scripts/reset_light.sh

# Load your domains
./scripts/load_domains.sh your-domains.csv config/config.local.yaml

# Restart workers
```

### View Database Directly
```bash
# Connect to PostgreSQL
psql -h 127.0.0.1 -U formbot -d form_submissions

# Example queries
SELECT * FROM domain_stats;
SELECT * FROM submission_stats;
SELECT url, status FROM domains LIMIT 10;
```

### View Redis Cache
```bash
redis-cli

# Check keys
KEYS progress:*

# Get specific values
GET progress:domains:loaded
GET progress:submissions:success
```

## Troubleshooting

### Workers not processing tasks

**Check if infrastructure is running:**
```bash
docker ps
```

You should see: `kafka`, `zookeeper`, `redis`, `postgres`

**Restart infrastructure if needed:**
```bash
docker-compose -f deployments/docker/docker-compose.instance1.yml down
docker-compose -f deployments/docker/docker-compose.instance1.yml up -d
```

### "Cannot open Chrome" error

**You have idle browser instances running. Close them:**
```bash
pkill -9 "Google Chrome"
```

**Or wait 5 minutes** - the system auto-closes idle browsers due to:
```yaml
browser:
  idle_timeout_seconds: 300  # in config.local.yaml
```

### Database connection error

**Check PostgreSQL is running:**
```bash
docker ps | grep postgres
```

**Test connection:**
```bash
psql -h 127.0.0.1 -p 5432 -U formbot -d form_submissions
# Password: formbot123
```

### Redis connection error

**Check Redis is running:**
```bash
redis-cli ping
# Should return: PONG
```

### Kafka errors

**List topics:**
```bash
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list
```

**Check consumer groups:**
```bash
docker exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 --list
```

## Configuration Files

- **Local development:** `config/config.local.yaml`
- **Production:** `config/config.yaml`

Key settings for local dev:
```yaml
browser:
  headless: true
  idle_timeout_seconds: 300  # Close idle browsers after 5 min

budget:
  captcha_limit_usd: 0.0  # Disable CAPTCHA solving (free mode)

workers:
  concurrent_browsers: 2  # Limit concurrent browser instances
```

## Next Steps

1. **Monitor the first run:** Watch how the system discovers and submits forms
2. **Check results:** Look at the database/logs to see what worked
3. **Adjust config:** Tune workers, timeouts, etc. based on your needs
4. **Scale up:** Add more domains, enable CAPTCHA solving, etc.

## Useful Commands Summary

| Command | Purpose |
|---------|---------|
| `./scripts/reset_and_reload_test_domains.sh` | Full reset + load test domains |
| `./scripts/monitor.sh` | Watch progress continuously |
| `./scripts/check_progress.sh` | Check progress once |
| `./scripts/reset_light.sh` | Quick reset (keeps Kafka topics) |
| `./scripts/load_domains.sh <file>` | Load custom domain list |
| `pkill -9 "Google Chrome"` | Kill all Chrome instances |
| `docker-compose ... up -d` | Start infrastructure |
| `docker-compose ... down` | Stop infrastructure |

---

**Happy testing!** 🚀
