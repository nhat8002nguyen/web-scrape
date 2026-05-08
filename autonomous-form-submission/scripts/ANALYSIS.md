# Scripts Analysis & Cleanup

## Overview
This document analyzes all scripts in the `scripts/` directory, identifies redundancies, and recommends which scripts to keep or remove.

---

## Script Categories

### 1. Reset Scripts

| Script | Purpose | Keep/Remove | Notes |
|--------|---------|-------------|-------|
| `reset.sh` | Full reset with Kafka topic recreation | ✅ **KEEP** | Main reset script for when you need to change Kafka partitions |
| `reset_light.sh` | Fast reset without topic recreation | ✅ **KEEP** | Recommended for most use cases |
| `full_reset.sh` | Complete reset + infrastructure restart | ❌ **REMOVE** | **REDUNDANT** - Just adds docker-compose restart to reset.sh |
| `fresh_start.sh` | Stops workers + reset_light.sh | ❌ **REMOVE** | **REDUNDANT** - Simple wrapper, functionality can be done manually |
| `reset_and_reload_test_domains.sh` | Reset + load test domains | ✅ **KEEP** | Convenient for testing workflow |

**Redundancy Details:**
- `full_reset.sh` = `stop_workers.sh` + `docker-compose down/up` + `reset.sh` - Too specific and heavy
- `fresh_start.sh` = `stop_workers.sh` + `reset_light.sh` + instructions - Unnecessary wrapper

---

### 2. Debug Scripts

| Script | Purpose | Keep/Remove | Notes |
|--------|---------|-------------|-------|
| `debug_domain.sh` | Show database details for specific domain | ✅ **KEEP** | Useful for debugging specific domains |
| `debug_run.sh` | Full debug workflow with visible browser | ✅ **KEEP** | Complete debug workflow using real system |
| `test_single_domain.sh` | Direct browser test without system | ❌ **REMOVE** | **REDUNDANT** - Similar to debug_run.sh but bypasses system |

**Redundancy Details:**
- `test_single_domain.sh` creates a temporary Go script to test domains directly
- `debug_run.sh` does the same but uses the actual system (Kafka, workers, DB)
- `debug_run.sh` is more realistic and useful for actual debugging

---

### 3. Monitoring Scripts

| Script | Purpose | Keep/Remove | Notes |
|--------|---------|-------------|-------|
| `check_progress.sh` | Show statistics and progress | ✅ **KEEP** | Core monitoring script |
| `monitor.sh` | Continuous auto-refresh monitoring | ✅ **KEEP** | Wraps check_progress.sh with loop |
| `health_check.sh` | Check infrastructure health | ✅ **KEEP** | Verifies services are running |
| `check_workers.sh` | Show running workers | ✅ **KEEP** | Quick worker status check |
| `diagnose.sh` | Comprehensive system diagnostics | ✅ **KEEP** | Detailed troubleshooting |

**No redundancy** - Each script serves a specific monitoring purpose

---

### 4. Domain Management Scripts

| Script | Purpose | Keep/Remove | Notes |
|--------|---------|-------------|-------|
| `load_domains.sh` | Load domains from CSV file | ✅ **KEEP** | Essential for loading domains |
| `list_domains.sh` | List all domains with status | ✅ **KEEP** | Useful for viewing domain list |
| `show_failures.sh` | Show failed domains with errors | ✅ **KEEP** | Helpful for debugging failures |

**No redundancy** - All serve different purposes

---

### 5. Worker Management Scripts

| Script | Purpose | Keep/Remove | Notes |
|--------|---------|-------------|-------|
| `stop_workers.sh` | Stop all running workers | ✅ **KEEP** | Useful for cleanup |

**No redundancy** - Single purpose script

---

## Summary

### Scripts to Remove (3 total)

1. **`full_reset.sh`** - Redundant with `reset.sh` + `stop_workers.sh`
2. **`fresh_start.sh`** - Unnecessary wrapper around `reset_light.sh`
3. **`test_single_domain.sh`** - Redundant with `debug_run.sh`

### Scripts to Keep (14 total)

**Reset/Setup:**
1. `reset.sh` - Full reset with Kafka recreation
2. `reset_light.sh` - Fast reset (recommended)
3. `reset_and_reload_test_domains.sh` - Convenient testing workflow

**Debug:**
4. `debug_domain.sh` - Show domain details
5. `debug_run.sh` - Debug with visible browser

**Monitoring:**
6. `check_progress.sh` - Progress statistics
7. `monitor.sh` - Continuous monitoring
8. `health_check.sh` - Infrastructure health
9. `check_workers.sh` - Worker status
10. `diagnose.sh` - Comprehensive diagnostics

**Domain Management:**
11. `load_domains.sh` - Load domains from CSV
12. `list_domains.sh` - List all domains
13. `show_failures.sh` - Show failures

**Worker Management:**
14. `stop_workers.sh` - Stop all workers

---

## Recommended Workflows After Cleanup

### Quick Testing
```bash
# Reset and load test domains
./scripts/reset_and_reload_test_domains.sh

# Start workers (in separate terminals)
go run cmd/discovery-worker/main.go --config config/config.local.yaml
go run cmd/submission-worker/main.go --config config/config.local.yaml

# Monitor progress
./scripts/monitor.sh
```

### Debug Single Domain
```bash
# Debug with visible browser
./scripts/debug_run.sh https://example.com/
```

### Check System Health
```bash
# Quick health check
./scripts/health_check.sh

# Comprehensive diagnostics
./scripts/diagnose.sh

# Check running workers
./scripts/check_workers.sh
```

### Stop Everything
```bash
# Stop all workers
./scripts/stop_workers.sh
```

---

## Impact Analysis

### Before Cleanup: 18 scripts
- 5 Reset scripts (28% redundancy)
- 3 Debug scripts (33% redundancy)
- 5 Monitoring scripts
- 3 Domain management scripts
- 1 Worker management script
- 1 README

### After Cleanup: 15 scripts
- 3 Reset scripts (focused and distinct)
- 2 Debug scripts (complementary)
- 5 Monitoring scripts
- 3 Domain management scripts
- 1 Worker management script
- 1 README

**Result:** 17% reduction, eliminating redundancy while maintaining full functionality
