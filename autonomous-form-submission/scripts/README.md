# Scripts Directory

Utility scripts for managing the Autonomous Form Submission system.

> **Note:** See `ANALYSIS.md` for detailed script analysis and cleanup decisions.

## Available Scripts

### Quick Reference

| Category | Script | Purpose |
|----------|--------|---------|
| **Reset** | `reset_and_reload_test_domains.sh` | Quick reset + load test domains (recommended) |
| **Reset** | `reset_light.sh` | Fast reset without Kafka recreation |
| **Reset** | `reset.sh` | Full reset with Kafka topic recreation |
| **Debug** | `debug_run.sh` | Debug with visible browser |
| **Debug** | `debug_domain.sh` | Show domain details |
| **Monitor** | `monitor.sh` | Continuous auto-refresh monitoring |
| **Monitor** | `check_progress.sh` | Progress statistics |
| **Monitor** | `health_check.sh` | Infrastructure health check |
| **Monitor** | `check_workers.sh` | Worker status |
| **Monitor** | `diagnose.sh` | Comprehensive diagnostics |
| **Domains** | `load_domains.sh` | Load domains from CSV |
| **Domains** | `list_domains.sh` | List all domains |
| **Domains** | `show_failures.sh` | Show failed domains |
| **Workers** | `stop_workers.sh` | Stop all workers |

---

## Available Scripts

### 🔄 `reset_and_reload_test_domains.sh` ⭐ RECOMMENDED

**Quick reset and reload for testing** - Most convenient option for local development.

```bash
./scripts/reset_and_reload_test_domains.sh [config-file]
```

**What it does:**
1. Clears PostgreSQL database (all tables)
2. Flushes Redis cache
3. Loads `test-domains.csv` into the system
4. Runs diagnostics to verify

**Example:**
```bash
# Use default config (recommended)
./scripts/reset_and_reload_test_domains.sh

# Use custom config
./scripts/reset_and_reload_test_domains.sh config/config.yaml
```

**Why use this:**
- ✅ Fastest way to reset and test
- ✅ All-in-one command
- ✅ Includes verification
- ✅ Perfect for development iteration

---

### 🪶 `reset_light.sh`

**Lightweight reset** - Fast reset without Kafka topic recreation.

```bash
./scripts/reset_light.sh [config-file]
```

**What it does:**
- Truncates all PostgreSQL tables
- Flushes Redis cache
- Resets Kafka consumer group offsets to earliest
- Preserves Kafka topics (no deletion/recreation)

**Why use this:**
- ✅ Faster than full reset
- ✅ More reliable (no Kafka topic timing issues)
- ✅ Achieves same result as full reset
- ✅ Good for clearing data between different domain lists

**Example:**
```bash
./scripts/reset_light.sh config/config.local.yaml
```

**When to use:**
- You want to clear all data but load different domains
- Testing different domain lists
- Reset between test runs

---

### 🗑️ `reset.sh`

**Full reset with topic recreation** - Use only if you need to change topic partitions or fix Kafka issues.

```bash
./scripts/reset.sh [config-file]
```

**What it does:**
- Truncates all PostgreSQL tables
- Flushes Redis cache
- Deletes and recreates Kafka topics
- Asks for confirmation before proceeding

**Use when:**
- You need to change Kafka topic partitions
- Kafka topics are corrupted or stuck
- Complete fresh start needed (rare)

**Example:**
```bash
./scripts/reset.sh config/config.local.yaml
```

**Note:** For most cases, use `reset_light.sh` instead - it's faster and more reliable.

---

### 📥 `load_domains.sh`

**Load domains into the system** - Reads CSV file and publishes to Kafka.

```bash
./scripts/load_domains.sh <domains-file> [config-file]
```

**Arguments:**
- `domains-file`: Path to CSV file with domain list (required)
- `config-file`: Path to config file (default: `config/config.yaml`)

**CSV Format:**
```csv
domain
example.com
another-site.com
https://company.org/
```

**Example:**
```bash
# Load test domains
./scripts/load_domains.sh test-domains.csv config/config.local.yaml

# Load custom domain list
./scripts/load_domains.sh my-domains.csv

# Load sample domains
./scripts/load_domains.sh scripts/sample-domains.csv
```

---

### 📊 `check_progress.sh`

**Monitor system progress** - Shows real-time statistics.

```bash
./scripts/check_progress.sh [config-file]
```

**Displays:**
- Domain statistics (pending, discovered, found, etc.)
- Submission statistics (success rate, CAPTCHA stats, etc.)
- Redis cache metrics
- Recent errors
- CAPTCHA budget spent
- Average processing time

**Example:**
```bash
# Check progress once with default config
./scripts/check_progress.sh

# Check with custom config
./scripts/check_progress.sh config/config.local.yaml
```

---

### 🔄 `monitor.sh`

**Continuous monitoring** - Auto-refresh progress display (macOS compatible).

```bash
./scripts/monitor.sh [config-file] [interval-seconds]
```

**What it does:**
- Continuously runs `check_progress.sh` at specified interval
- Auto-refreshes the display (clears screen between updates)
- Works on macOS and Linux (no `watch` command needed)
- Press Ctrl+C to stop

**Example:**
```bash
# Monitor with default config, refresh every 5 seconds
./scripts/monitor.sh

# Monitor with custom config, refresh every 3 seconds
./scripts/monitor.sh config/config.local.yaml 3

# Monitor every 10 seconds
./scripts/monitor.sh config/config.local.yaml 10
```

---

### 🏥 `health_check.sh`

**Check infrastructure health** - Verifies all services are running.

```bash
./scripts/health_check.sh
```

**Checks:**
- PostgreSQL connection
- Redis connection
- Kafka broker availability
- Required topics exist

---

### 📋 `list_domains.sh`

**List all domains with status** - See all domains and their discovery results.

```bash
./scripts/list_domains.sh [config-file]
```

**Displays:**
- All domains with visual status indicators (✅ ❌ ⚠️ ⏳ 🔍)
- Contact page status
- Number of attempts
- Error messages (if any)
- Summary statistics

**Example:**
```bash
./scripts/list_domains.sh
```

**Output shows:**
- ✅ Found - Contact form discovered
- ❌ Not Found - No contact form on domain
- ⚠️ Failed - Error during discovery
- ⏳ Pending - Waiting to be processed
- 🔍 Discovery - Currently being checked

---

### 🔍 `debug_run.sh`

**Debug with visible browser** - Watch the discovery process in real-time.

```bash
./scripts/debug_run.sh <domain-url>
```

**What it does:**
1. Stops any running workers
2. Resets system (clears database and cache)
3. Publishes domain to Kafka
4. Starts discovery worker with visible Chrome browser
5. Worker picks up domain from Kafka and processes it
6. You can watch Chrome navigate and detect forms

**Example:**
```bash
./scripts/debug_run.sh https://vietnam.acclime.com/
```

**Perfect for:**
- Understanding how form detection works
- Debugging why a form wasn't detected
- Seeing which pages are checked
- Visual inspection of the process

**What you'll see:**
- Chrome window opens (not headless)
- Browser navigates to /contact, /contact-us, etc.
- Terminal shows form detection details
- Worker logs show processing steps
- Browser stays open so you can inspect

**Note:** Domain is first published to Kafka, then the worker picks it up and inserts it into PostgreSQL. This matches how the production system works.

---

### 🔍 `debug_domain.sh`

**Show domain details from database** - View stored information about a domain.

```bash
./scripts/debug_domain.sh [config-file] <domain-url>
```

**Shows for a specific domain:**
- Domain status and metadata
- Contact form details (fields, CAPTCHA info)
- All submission attempts
- Error logs
- Full timeline

**Example:**
```bash
# Debug a specific domain
./scripts/debug_domain.sh config/config.local.yaml https://vietnam.acclime.com/

# Or with default config
./scripts/debug_domain.sh "" https://vietnam.acclime.com/
```

**Use this when:**
- You want to see what's stored in the database
- Checking submission history
- Reviewing error messages
- Understanding why a domain failed

---

### 🔍 `diagnose.sh`

**Comprehensive system diagnostics** - Identify common issues automatically.

```bash
./scripts/diagnose.sh [config-file]
```

**Checks:**
1. Workers status (are they running?)
2. Database status (domains, pending count, failures)
3. Kafka topics (messages in queue, consumer groups)
4. Automatic problem detection

**Example:**
```bash
./scripts/diagnose.sh config/config.local.yaml
```

**Output includes:**
- ✅ What's working correctly
- ❌ Problems found
- 💡 Solutions for each problem

**Use this when:**
- System isn't working as expected
- Need quick health overview
- Troubleshooting issues

---

### 👷 `check_workers.sh`

**Check running workers** - See what workers are currently active.

```bash
./scripts/check_workers.sh
```

**Displays:**
- Discovery workers (count, PIDs, CPU, memory)
- Submission workers (count, PIDs, CPU, memory)
- Domain loaders (if running)
- Chrome instances (count, memory usage)
- Summary and helpful commands

**Example output:**
```
🔍 DISCOVERY WORKERS: 1 running
  PID: 12345 | CPU: 2.5% | MEM: 1.2%

📤 SUBMISSION WORKERS: 1 running
  PID: 12346 | CPU: 3.1% | MEM: 1.5%

🌐 CHROME INSTANCES: 4 running
  Total Memory: 5.2%
```

**Quick check:**
```bash
./scripts/check_workers.sh
```

---

### 🛑 `stop_workers.sh`

**Stop all workers** - Safely stop all running workers.

```bash
./scripts/stop_workers.sh
```

**What it does:**
- Checks what workers are running
- Prompts for confirmation
- Stops all workers gracefully
- Optionally stops Chrome instances
- Shows summary of stopped processes

**Quick stop (no confirmation):**
```bash
pkill -f "discovery-worker|submission-worker"
```

---

### 📋 `show_failures.sh`

**Show failed domains with error details** - Understand why domains failed.

```bash
./scripts/show_failures.sh [config-file]
```

**Displays:**
- All domains with `failed` status
- Error messages for each
- Timestamps and attempt counts
- Common failure patterns

**Example:**
```bash
./scripts/show_failures.sh
```

**Use this when:**
- Domains are failing and you want to know why
- Identifying patterns in failures
- Debugging network or timeout issues

---

## Common Workflows

### 🚀 Quick Start for Testing

**Fastest way to test the system:**

```bash
# 1. Reset and load test domains (all-in-one)
./scripts/reset_and_reload_test_domains.sh

# 2. Start workers in separate terminals
# Terminal 1:
go run cmd/discovery-worker/main.go --config config/config.local.yaml

# Terminal 2:
go run cmd/submission-worker/main.go --config config/config.local.yaml

# Terminal 3: Monitor progress continuously
./scripts/monitor.sh
```

---

### 🔍 Debug a Problematic Domain

**When a domain isn't working as expected:**

```bash
# Option 1: Watch browser in action (visual debugging)
./scripts/debug_run.sh https://problematic-domain.com/

# Option 2: Check database records
./scripts/debug_domain.sh "" https://problematic-domain.com/

# Option 3: See all failures
./scripts/show_failures.sh
```

---

### 📊 Check System Status

**Quick health check:**

```bash
# Are workers running?
./scripts/check_workers.sh

# Is infrastructure healthy?
./scripts/health_check.sh

# Comprehensive diagnostics (recommended)
./scripts/diagnose.sh
```

---

### 🔄 Loading Different Domain Lists

**Test with your own domains:**

```bash
# 1. Reset system (fast reset)
./scripts/reset_light.sh config/config.local.yaml

# 2. Load your custom domains
./scripts/load_domains.sh my-custom-domains.csv config/config.local.yaml

# 3. Check they loaded
./scripts/list_domains.sh

# 4. Start workers (if not already running)
# Terminal 1: go run cmd/discovery-worker/main.go --config config/config.local.yaml
# Terminal 2: go run cmd/submission-worker/main.go --config config/config.local.yaml
```

---

### 🛑 Stopping Everything

**Clean shutdown:**

```bash
# Stop all workers (includes Chrome)
./scripts/stop_workers.sh
```

---

### 🔧 Development Iteration Cycle

**Quick testing during development:**

```bash
# Make code changes...

# Reset and reload test domains
./scripts/reset_and_reload_test_domains.sh

# Workers will automatically pick up new tasks (no restart needed if still running)
# Check progress
./scripts/monitor.sh
```

## Requirements

**System tools needed:**
- `psql` - PostgreSQL client
- `redis-cli` - Redis client
- `docker` - For Kafka container access
- `bash` - Shell (built-in on macOS/Linux)

**Installation on macOS:**
```bash
brew install postgresql redis
# Docker Desktop for Mac (download from docker.com)
```

**Installation on Linux (Ubuntu/Debian):**
```bash
sudo apt-get install postgresql-client redis-tools docker.io
```

**Note:** The `watch` command is not needed - we provide `monitor.sh` which works on all platforms.

## Configuration Files

The scripts automatically extract connection details from your config files:

- **Default local:** `config/config.local.yaml`
- **Default production:** `config/config.yaml`

Make sure your config file contains:
```yaml
postgres:
  host: "127.0.0.1"
  port: 5432
  database: "form_submissions"
  user: "formbot"
  password: "formbot123"

redis:
  host: "127.0.0.1:6379"

kafka:
  brokers: ["127.0.0.1:9092"]
```

## Troubleshooting

### "Permission denied" error
```bash
chmod +x scripts/*.sh
```

### "Database connection failed"
Check that PostgreSQL is running:
```bash
docker ps | grep postgres
# or
pg_isready -h 127.0.0.1 -p 5432
```

### "Redis connection failed"
Check that Redis is running:
```bash
redis-cli ping
# Should return: PONG
```

### "Kafka topics not found"
Check Kafka is running:
```bash
docker ps | grep kafka
```

### Reset hangs on confirmation
Just type `yes` and press Enter when prompted.
