# Scripts Index

Quick reference guide for all available scripts.

## 🚀 Quick Start

```bash
# Reset and load test domains
./scripts/reset_and_reload_test_domains.sh

# Start workers (in separate terminals)
go run cmd/discovery-worker/main.go --config config/config.local.yaml
go run cmd/submission-worker/main.go --config config/config.local.yaml

# Monitor progress
./scripts/monitor.sh
```

---

## 📁 All Scripts by Category

### 🔄 Reset & Setup

| Script | Use Case | Speed |
|--------|----------|-------|
| `reset_and_reload_test_domains.sh` ⭐ | Quick test workflow | ⚡⚡⚡ Fast |
| `reset_light.sh` | Clear data, keep Kafka topics | ⚡⚡ Faster |
| `reset.sh` | Full reset with Kafka recreation | ⚡ Slow |

**Recommendation:** Use `reset_and_reload_test_domains.sh` for daily development

---

### 🔍 Debug & Troubleshoot

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `debug_run.sh` | Watch browser in action | Visual debugging needed |
| `debug_domain.sh` | Show database details | Check stored data |
| `diagnose.sh` | Auto-detect issues | System not working |
| `show_failures.sh` | Show error messages | Domains failing |

**Recommendation:** Start with `diagnose.sh` for quick issue detection

---

### 📊 Monitor & Check

| Script | Purpose | Update Frequency |
|--------|---------|------------------|
| `monitor.sh` | Continuous monitoring | Auto-refresh every 5s |
| `check_progress.sh` | One-time progress check | On-demand |
| `health_check.sh` | Infrastructure status | On-demand |
| `check_workers.sh` | Worker status | On-demand |

**Recommendation:** Use `monitor.sh` in a dedicated terminal during development

---

### 📋 Domain Management

| Script | Purpose |
|--------|---------|
| `load_domains.sh` | Load domains from CSV file |
| `list_domains.sh` | List all domains with status |
| `show_failures.sh` | Show failed domains with errors |

---

### 🛑 Worker Management

| Script | Purpose |
|--------|---------|
| `stop_workers.sh` | Stop all workers and optionally Chrome |

---

## 🎯 Common Scenarios

### Scenario 1: Daily Development Testing
```bash
./scripts/reset_and_reload_test_domains.sh
# Workers running? Check: ./scripts/check_workers.sh
# Monitor: ./scripts/monitor.sh
```

### Scenario 2: Debug a Problematic Domain
```bash
./scripts/debug_run.sh https://problematic-domain.com/
# Watch the browser and see what's happening
```

### Scenario 3: System Not Working
```bash
./scripts/diagnose.sh
# Automatic issue detection with solutions
```

### Scenario 4: Load Custom Domains
```bash
./scripts/reset_light.sh
./scripts/load_domains.sh my-domains.csv
./scripts/list_domains.sh
```

### Scenario 5: Check Progress
```bash
# Continuous monitoring:
./scripts/monitor.sh

# One-time check:
./scripts/check_progress.sh
```

### Scenario 6: Clean Shutdown
```bash
./scripts/stop_workers.sh
```

---

## 📚 Documentation Files

- **`README.md`** - Comprehensive guide with examples
- **`ANALYSIS.md`** - Detailed script analysis and decisions
- **`CLEANUP_SUMMARY.md`** - Cleanup actions and migration guide
- **`INDEX.md`** - This file - quick reference

---

## 🎓 Learning Path

**New to the project?** Follow this order:

1. Read `README.md` - Understand what each script does
2. Try `reset_and_reload_test_domains.sh` - Get familiar with the workflow
3. Use `monitor.sh` - Watch the system work
4. Check `ANALYSIS.md` - Understand design decisions

**Debugging issues?** Follow this order:

1. Run `diagnose.sh` - Auto-detect common issues
2. Run `check_workers.sh` - Verify workers are running
3. Run `health_check.sh` - Check infrastructure
4. Use `debug_run.sh` - Visual debugging

---

## 💡 Tips

- **Most Used:** `reset_and_reload_test_domains.sh` + `monitor.sh`
- **Fastest Reset:** `reset_light.sh` (doesn't recreate Kafka topics)
- **Visual Debugging:** `debug_run.sh` (see browser in action)
- **Stuck?** Run `diagnose.sh` first
- **Daily Workflow:** Reset → Start Workers → Monitor

---

## 📊 Statistics

- **Total Scripts:** 14 (plus 4 documentation files)
- **Reset Options:** 3 (fast, faster, fastest)
- **Debug Tools:** 4 (visual, database, diagnostics, failures)
- **Monitoring Tools:** 4 (continuous, one-time, health, workers)
- **Management Tools:** 4 (load, list, show, stop)

**No redundancy** - Each script serves a unique purpose!
