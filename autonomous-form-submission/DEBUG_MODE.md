# Debug Mode - Visible Browser

Use this mode to see exactly what the browser is doing and why contact forms aren't being detected.

## 🎯 Quick Start

```bash
cd /Users/nhatnguyen/Workspaces/web-scrape/autonomous-form-submission
./scripts/debug_run.sh https://vietnam.acclime.com/
```

That's it! The script will:
1. ✅ Stop any running workers
2. ✅ Clean up Chrome
3. ✅ Reset database
4. ✅ Load just this one domain
5. ✅ Start discovery worker with **visible browser**

## 👀 What You'll See

### 1. Chrome Window Opens (Visible!)
You'll see Chrome open and navigate automatically through:
- `https://vietnam.acclime.com/contact`
- `https://vietnam.acclime.com/contact-us`
- `https://vietnam.acclime.com/get-in-touch`
- ... and more patterns

### 2. Terminal Shows Detailed Logs
```
INFO  Starting contact form discovery
      domain: https://vietnam.acclime.com/
      patterns_to_try: 7

INFO  Checking contact page pattern
      attempt: 1
      pattern: /contact
      url: https://vietnam.acclime.com/contact

    📝 Found 2 form(s) on page: https://vietnam.acclime.com/contact
    📋 Form 1: 4 fields | Email: true | Message: true | IsContact: true
    ✅ Contact form detected (Form 1)
```

### 3. You Can Inspect
- Watch which pages it visits
- See if forms are visible
- Check if the page loaded properly
- Verify if email/message fields exist

## 🔍 Debug Different Domains

```bash
# Test vietnam.acclime.com
./scripts/debug_run.sh https://vietnam.acclime.com/

# Test another domain
./scripts/debug_run.sh https://www.avtech.com.au/

# Test any domain
./scripts/debug_run.sh https://example.com/
```

## 🛠️ Configuration

The debug mode uses: **`config/config.debug.yaml`**

Key settings:
```yaml
browser:
  headless: false              # ← Visible browser
  idle_timeout_seconds: 0      # ← No auto-close

workers:
  concurrent_browsers: 1       # ← Only 1 browser at a time
```

## 📋 Manual Debug Mode

If you want more control:

### 1. Stop workers
```bash
./scripts/stop_workers.sh
```

### 2. Reset and load single domain
```bash
# Create temp CSV
echo "domain" > temp.csv
echo "https://vietnam.acclime.com/" >> temp.csv

# Reset and load
./scripts/reset_light.sh
./scripts/load_domains.sh temp.csv config/config.debug.yaml
```

### 3. Run discovery worker manually
```bash
go run cmd/discovery-worker/main.go --config config/config.debug.yaml
```

### 4. Watch the browser
- Chrome will open
- You can see each page it visits
- Check the terminal for form detection logs

## 🔎 Understanding the Output

### Form Found ✅
```
📝 Found 2 form(s) on page
📋 Form 1: 4 fields | Email: true | Message: true | IsContact: true
✅ Contact form detected (Form 1)
```
**Meaning:** Found a form with both email and message fields

### Form Not Contact ❌
```
📝 Found 1 form(s) on page
📋 Form 1: 2 fields | Email: true | Message: false | IsContact: false
❌ No contact form found among 1 form(s)
```
**Meaning:** Found a form but it's missing message field (might be a newsletter signup)

### No Forms ℹ️
```
ℹ️  No forms found on page: https://example.com/contact
```
**Meaning:** The page has no HTML `<form>` elements

## 🐛 Common Issues

### Issue 1: Page Loads But No Form Visible
**Possible reasons:**
- Form loads with JavaScript (needs more wait time)
- Form is in an iframe (not accessible)
- Form appears after scroll/interaction

**Solution:** Increase timeouts in `config.debug.yaml`:
```yaml
browser:
  page_load_timeout_seconds: 30
```

### Issue 2: Form Exists But Not Detected
**Check in terminal output:**
- Does it find the form? (`📝 Found X form(s)`)
- What fields does it detect? (`📋 Form 1: X fields`)
- Does it have email? (`Email: true/false`)
- Does it have message? (`Message: true/false`)

**If Email or Message is false:**
The form field names don't match expected patterns. Check the actual field names in the browser.

### Issue 3: Browser Navigates Too Fast
**Add more wait time:**

Edit `cmd/discovery-worker/main.go`, line ~301:
```go
chromedp.Sleep(5*time.Second),  // Increase from 2 to 5 seconds
```

## 📊 Check Results

After running, check what was found:
```bash
./scripts/debug_domain.sh "" https://vietnam.acclime.com/
```

## 🔄 Return to Normal Mode

When done debugging:

```bash
# Stop debug worker (Ctrl+C in terminal)

# Return to headless mode
go run cmd/discovery-worker/main.go --config config/config.local.yaml
```

## 💡 Pro Tips

1. **Watch the browser carefully** - See if pages load completely
2. **Check terminal logs** - Shows exactly what forms it found
3. **Inspect manually** - Right-click in browser → Inspect forms
4. **Test one domain at a time** - Easier to understand
5. **Keep browser window visible** - Don't minimize it

## 📚 What to Look For

When debugging, check:
- ✅ Does the contact page actually exist?
- ✅ Does the form load properly?
- ✅ Are there `<input type="email">` fields?
- ✅ Are there `<textarea>` or message fields?
- ✅ Do field names/labels contain "email" or "message"?

If you can see the form but the system can't detect it, the field names might not match our detection patterns.

---

**Ready to debug?**
```bash
./scripts/debug_run.sh https://vietnam.acclime.com/
```
