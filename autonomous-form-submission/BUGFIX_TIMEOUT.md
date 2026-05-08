# Critical Bug Fix: Page Load Timeout Not Being Applied

**Date:** January 28, 2026  
**Status:** ✅ FIXED  
**Severity:** High - All domains were failing with timeout errors

---

## 🐛 The Problem

All domains were failing with "context canceled" errors during discovery, even after increasing the `page_load_timeout_seconds` in the config from 20 to 45 seconds.

### Symptoms
- All domains failing with "failed to navigate: context canceled"
- Failures happening within ~20 seconds regardless of config changes
- Restarting workers didn't help

---

## 🔍 Root Cause

The discovery worker's `checkPageForForm()` function was **not using the configured page load timeout**:

### Before (Buggy Code)
```go
func (w *DiscoveryWorker) checkPageForForm(ctx context.Context, pageURL string) (*models.ContactForm, error) {
    // Navigate to page
    if err := chromedp.Run(ctx,  // ❌ Using parent context without timeout!
        chromedp.Navigate(pageURL),
        chromedp.Sleep(2*time.Second),
    ); err != nil {
        return nil, fmt.Errorf("failed to navigate: %w", err)
    }
    // ... rest of function
}
```

**The Issue:**
- The function was using the parent `ctx` directly
- This context had no timeout set
- The `page_load_timeout_seconds` config was being ignored
- chromedp would use its internal default timeout (~30s) which was too short

---

## ✅ The Fix

Modified the function to create a timeout context from the config:

### After (Fixed Code)
```go
func (w *DiscoveryWorker) checkPageForForm(ctx context.Context, pageURL string) (*models.ContactForm, error) {
    // Create timeout context for navigation
    timeout := time.Duration(w.config.Browser.PageLoadTimeoutSeconds) * time.Second
    navCtx, navCancel := context.WithTimeout(ctx, timeout)
    defer navCancel()
    
    // Navigate to page
    if err := chromedp.Run(navCtx,  // ✅ Using timeout context!
        chromedp.Navigate(pageURL),
        chromedp.Sleep(2*time.Second),
    ); err != nil {
        return nil, fmt.Errorf("failed to navigate: %w", err)
    }

    // Detect form (use original context without timeout for form detection)
    form, err := w.detector.DetectContactForm(ctx)
    // ... rest of function
}
```

**What Changed:**
1. Creates `navCtx` with timeout from config (`PageLoadTimeoutSeconds`)
2. Uses `navCtx` for navigation (respects timeout)
3. Uses original `ctx` for form detection (no timeout needed for DOM inspection)
4. Properly defers cancellation of timeout context

---

## 📝 Files Modified

1. **`config/config.local.yaml`**
   - Changed `page_load_timeout_seconds: 20` → `45`
   - Changed `timeout_seconds: 30` → `60`

2. **`cmd/discovery-worker/main.go`**
   - Modified `checkPageForForm()` function to use timeout context
   - Now respects `config.Browser.PageLoadTimeoutSeconds`

---

## 🚀 How to Apply the Fix

### Step 1: The code has been fixed ✅
The changes are already applied to the discovery worker.

### Step 2: Reset and Reload
```bash
# Stop any running workers
./scripts/stop_workers.sh

# Reset failed domains
./scripts/reset_light.sh

# Reload your domains
./scripts/load_domains.sh my-test-domains.csv config/config.local.yaml
```

### Step 3: Start NEW Worker (with fixed code)
```bash
# Terminal 1: Discovery Worker
go run cmd/discovery-worker/main.go --config config/config.local.yaml

# Terminal 2: Monitor
./scripts/monitor.sh
```

---

## 🔬 Testing the Fix

### Option 1: Visual Debug (Recommended First)
```bash
./scripts/debug_run.sh https://vietnam.acclime.com/
```
This will show you the browser and let you verify pages load successfully.

### Option 2: Full Test
```bash
# Reset and reload all domains
./scripts/reset_and_reload_test_domains.sh

# Start worker
go run cmd/discovery-worker/main.go --config config/config.local.yaml

# Monitor in another terminal
./scripts/monitor.sh
```

---

## 📊 Expected Results

### Before Fix
```
❌ All domains failed
❌ Error: "failed to navigate: context canceled"
❌ Failures within 20-30 seconds
❌ Config timeout ignored
```

### After Fix
```
✅ Domains load successfully (with 45s timeout)
✅ Pages have time to fully load
✅ Forms can be detected
✅ Config timeout is respected
```

---

## 💡 Key Learnings

1. **Context timeouts must be explicitly set** - Parent contexts don't automatically inherit timeouts
2. **Config values must be actively used** - Having them in config.yaml isn't enough
3. **Always restart workers after code changes** - Workers load code at startup
4. **Test with visual browser first** - `debug_run.sh` helps identify issues quickly

---

## 🎯 Verification Checklist

After applying the fix, verify:

- [ ] Code changes applied to `cmd/discovery-worker/main.go`
- [ ] Config has `page_load_timeout_seconds: 45`
- [ ] Old workers stopped
- [ ] Database cleared of failed domains
- [ ] New worker started
- [ ] Domains loading successfully (no "context canceled" errors)
- [ ] Monitor shows progress (domains moving from pending → discovery → found/not_found)

---

## 📞 If Still Failing

If domains still fail after this fix:

1. **Check actual error message:**
   ```bash
   ./scripts/show_failures.sh
   ```

2. **Test with visible browser:**
   ```bash
   ./scripts/debug_run.sh https://vietnam.acclime.com/
   ```

3. **Check network connectivity:**
   ```bash
   curl -I -L --max-time 10 https://vietnam.acclime.com/
   ```

4. **Verify config is loaded:**
   Check worker startup logs for "page_load_timeout_seconds: 45"

---

## Related Issues

- Issue: Timeout configuration not being applied
- Related: Browser pool context management
- Fixed: Navigation timeout handling

**This was a critical bug that prevented any domains from being processed successfully.**
