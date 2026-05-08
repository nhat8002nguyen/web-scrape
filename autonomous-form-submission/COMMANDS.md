# Quick Command Reference

Essential commands for running and managing the autonomous form submission system.

## ⚡ Quick Start (Fresh Run)

**Most Common Use Case - Start from scratch:**

```bash
# 1. Complete reset and clean start
./scripts/fresh_start.sh

# 2. Then open 3 terminals and run:
# Terminal 1:
go run cmd/discovery-worker/main.go --config config/config.local.yaml

# Terminal 2:
go run cmd/submission-worker/main.go --config config/config.local.yaml

# Terminal 3:
./scripts/monitor.sh
```

**⚠️ CRITICAL: Keep Terminals 1 & 2 running!** Don't close them or press Ctrl+C until processing is complete.

---

## 🚀 Starting Workers

### Discovery Worker
```bash
go run cmd/discovery-worker/main.go --config config/config.local.yaml
```
Discovers contact forms on domains.

### Submission Worker
```bash
go run cmd/submission-worker/main.go --config config/config.local.yaml
```
Submits discovered contact forms.

### Both at Once (Recommended)
```bash
# Terminal 1
go run cmd/discovery-worker/main.go --config config/config.local.yaml

# Terminal 2
go run cmd/submission-worker/main.go --config config/config.local.yaml
```

---

## 🔍 Checking Status

### Check Running Workers
```bash
./scripts/check_workers.sh
```
Shows all running workers, their PIDs, CPU/memory usage, and Chrome instances.

**Alternative (quick check):**
```bash
ps aux | grep -E "discovery-worker|submission-worker" | grep -v grep
```

### Monitor Progress
```bash
./scripts/monitor.sh
```
Continuous monitoring with auto-refresh (every 5 seconds).

### Check Progress Once
```bash
./scripts/check_progress.sh
```
One-time snapshot of current progress.

### List All Domains
```bash
./scripts/list_domains.sh
```
Shows all domains with status indicators (✅ ❌ ⚠️ ⏳ 🔍).

### Debug Specific Domain
```bash
./scripts/debug_domain.sh "" https://example.com/
```
Deep dive into a specific domain's discovery and submission.

---

## 🛑 Stopping Workers

### Stop All Workers (Interactive)
```bash
./scripts/stop_workers.sh
```
Prompts for confirmation, stops all workers and optionally Chrome.

### Stop Workers Immediately
```bash
# Stop discovery workers
pkill -f "discovery-worker"

# Stop submission workers
pkill -f "submission-worker"

# Stop domain loaders
pkill -f "domain-loader"

# Stop all workers at once
pkill -f "discovery-worker|submission-worker|domain-loader"
```

### Stop Chrome Instances
```bash
pkill -9 "Google Chrome"
```
Use this if Chrome is consuming too many resources.

---

## 🔄 Resetting System

### Quick Reset + Reload Test Domains (Recommended)
```bash
./scripts/reset_and_reload_test_domains.sh
```
Clears everything and loads test-domains.csv in one command.

### Light Reset (Faster)
```bash
./scripts/reset_light.sh
```
Clears data but keeps Kafka topics (more reliable).

### Full Reset
```bash
./scripts/reset.sh config/config.local.yaml
```
Deletes and recreates Kafka topics (can have timing issues).

---

## 📥 Loading Domains

### Load Test Domains
```bash
./scripts/load_domains.sh test-domains.csv config/config.local.yaml
```

### Load Custom Domains
```bash
./scripts/load_domains.sh my-domains.csv config/config.local.yaml
```

---

## 🏥 Infrastructure

### Check Infrastructure Health
```bash
./scripts/health_check.sh
```
Verifies PostgreSQL, Redis, Kafka are running.

### Start Infrastructure
```bash
docker-compose -f deployments/docker/docker-compose.instance1.yml up -d
```

### Stop Infrastructure
```bash
docker-compose -f deployments/docker/docker-compose.instance1.yml down
```

### Check Docker Containers
```bash
docker ps
```
Should show: kafka, zookeeper, redis, postgres.

---

## 📊 Database Queries

### Connect to PostgreSQL
```bash
psql -h 127.0.0.1 -U formbot -d form_submissions
```
Password: `formbot123`

### Quick Queries
```sql
-- Domain stats
SELECT * FROM domain_stats;

-- Submission stats
SELECT * FROM submission_stats;

-- All domains
SELECT id, url, status, contact_url FROM domains;

-- Contact forms
SELECT id, url, jsonb_array_length(fields) as field_count 
FROM contact_forms;

-- Recent errors
SELECT * FROM errors ORDER BY created_at DESC LIMIT 10;
```

---

## 💾 Redis

### Connect to Redis
```bash
redis-cli
```

### Check Progress Keys
```redis
KEYS progress:*
GET progress:domains:loaded
GET progress:submissions:success
GET progress:submissions:failed
```

---

## 🐛 Debug Mode (Visible Browser)

### See What the Browser is Doing

```bash
# Debug a specific domain with VISIBLE browser
./scripts/debug_run.sh https://vietnam.acclime.com/
```

**What this does:**
- Opens Chrome window (you can see it!)
- Processes just ONE domain at a time
- Shows detailed logs in terminal
- You can watch it navigate and check pages
- Helps understand why forms aren't detected

**Perfect for:**
- Understanding why a specific domain shows "NOT FOUND"
- Watching which pages are checked
- Seeing if forms load properly
- Verifying email/message fields exist

See full guide: `DEBUG_MODE.md`

---

## 🔧 Troubleshooting

### Issue: All Domains Show "FAILED"

**Symptom:**
```
⚠️  FAILED: https://vietnam.acclime.com/
⚠️  FAILED: https://www.avtech.com.au/
... (all domains failed)
```

**Cause:** Workers were stopped or never started after loading domains.

**Solution:**
```bash
# 1. Check if workers are running
./scripts/check_workers.sh

# If no workers running:
# 2. Do a fresh start
./scripts/fresh_start.sh

# 3. Start workers in 3 separate terminals (see above)
```

**To prevent this:**
- ✅ Always start workers AFTER resetting/loading domains
- ✅ Keep worker terminals open and running
- ✅ Don't press Ctrl+C on worker terminals

### Check Logs
```bash
# Discovery worker with logs saved
go run cmd/discovery-worker/main.go --config config/config.local.yaml 2>&1 | tee discovery.log

# Submission worker with logs saved
go run cmd/submission-worker/main.go --config config/config.local.yaml 2>&1 | tee submission.log
```

### Check Resource Usage
```bash
# Overall
./scripts/check_workers.sh

# Chrome only
ps aux | grep "Google Chrome" | grep -v grep

# Memory usage
ps aux | grep -E "discovery-worker|submission-worker|Chrome" | awk '{sum+=$4} END {print "Total Memory: " sum "%"}'
```

### Kill Stuck Processes
```bash
# By name
pkill -9 -f "discovery-worker"

# By PID
kill -9 <PID>

# All Chrome
pkill -9 "Google Chrome"
```

---

## 📝 Common Workflows

### Start Fresh Run
```bash
# 1. Stop everything
./scripts/stop_workers.sh

# 2. Reset and load domains
./scripts/reset_and_reload_test_domains.sh

# 3. Start workers (2 terminals)
go run cmd/discovery-worker/main.go --config config/config.local.yaml
go run cmd/submission-worker/main.go --config config/config.local.yaml

# 4. Monitor (terminal 3)
./scripts/monitor.sh
```

### Check Why Domain Failed
```bash
# 1. List all domains
./scripts/list_domains.sh

# 2. Debug specific domain
./scripts/debug_domain.sh "" https://problem-domain.com/

# 3. Check worker logs for that domain
# (look in terminal where worker is running)
```

### Clean Up After Testing
```bash
# Stop workers
./scripts/stop_workers.sh

# Stop infrastructure (optional)
docker-compose -f deployments/docker/docker-compose.instance1.yml down

# Clean Chrome
pkill -9 "Google Chrome"
```

---

## 🎯 One-Liners

```bash
# Check if workers are running
./scripts/check_workers.sh

# Stop all workers
./scripts/stop_workers.sh

# Quick status
./scripts/check_progress.sh

# See domain list with icons
./scripts/list_domains.sh

# Watch progress live
./scripts/monitor.sh

# Reset everything
./scripts/reset_and_reload_test_domains.sh

# Kill Chrome
pkill -9 "Google Chrome"

# Check infrastructure
docker ps && redis-cli ping && psql -h 127.0.0.1 -U formbot -d form_submissions -c "SELECT 1"
```

---

## 📚 More Information

- **Full documentation:** `README.md`
- **Debugging guide:** `DEBUGGING_GUIDE.md`
- **Quick start:** `QUICKSTART.md`
- **Scripts reference:** `scripts/README.md`

---

**Pro Tip:** Keep 3 terminals open:
1. Discovery Worker (with verbose logging)
2. Submission Worker (with verbose logging)
3. Monitor script (./scripts/monitor.sh)
