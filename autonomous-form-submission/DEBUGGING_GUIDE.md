# Debugging Guide - Understanding Discovery Results

This guide helps you understand why domains show "not found" and how to troubleshoot discovery issues.

## Enhanced Logging

The system now provides detailed real-time logging during discovery to help you see exactly what's happening.

### What You'll See in Worker Logs

When a discovery worker processes a domain, you'll now see:

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

INFO  ✓ Contact form found on pattern page
      url: https://vietnam.acclime.com/contact
      fields: 4
      has_captcha: false
```

### Understanding the Form Analysis

For each form found, you'll see:
- **📝 Found X form(s)** - How many HTML forms exist on the page
- **📋 Form N** - Details about each form:
  - Number of fields
  - Whether it has an email field
  - Whether it has a message field
  - Whether it qualifies as a contact form
- **✅ Contact form detected** - When a valid contact form is found
- **❌ No contact form found** - When forms exist but don't qualify

### Why a Form Might Not Be Detected

A form must have BOTH:
1. ✅ **Email field** - Contains "email" or "e-mail" in name/placeholder/label
2. ✅ **Message field** - Contains "message", "comment", "inquiry" or is a textarea

If either is missing, the form is NOT classified as a contact form.

## Quick Debugging Scripts

### 1. Check All Domains Status

```bash
./scripts/list_domains.sh
```

**Shows:**
- ✅ Found domains (with contact forms)
- ❌ Not found domains (no contact form detected)
- ⚠️ Failed domains (errors during discovery)
- ⏳ Pending domains (not yet processed)
- 🔍 Discovering domains (currently being checked)

**Output Example:**
```
========================================
All Domains Status
========================================

 id |           domain                | status    | contact_page | attempts | error
----+---------------------------------+-----------+--------------+----------+-------
  1 | ✅ https://vietnam.acclime.com/ | found     | ✓ Found      | 1        | -
  2 | ❌ https://www.avtech.com.au/  | not_found | -            | 1        | -
  3 | ⚠️  https://afg.vn              | failed    | -            | 2        | Navigation timeout
```

### 2. Debug Specific Domain

```bash
./scripts/debug_domain.sh "" https://vietnam.acclime.com/
```

**Shows detailed information:**
- Domain status and timestamps
- Contact form details (all fields as JSON)
- Submission attempts
- Error logs with context

### 3. Monitor with Enhanced Display

```bash
./scripts/monitor.sh
```

Now includes a **Domain Status Summary** section showing all domains with their current status.

## Common Issues and Solutions

### Issue 1: "No forms found on page"

**Symptom:**
```
ℹ️  No forms found on page: https://example.com/contact
```

**Possible Causes:**
1. Page uses JavaScript to load forms (needs time to render)
2. Form is behind authentication/cookies
3. No HTML `<form>` elements exist (uses AJAX instead)

**Solution:**
- Increase wait time in config: `browser.page_load_timeout_seconds`
- Check if page requires JavaScript execution
- Verify manually that a form exists on the page

### Issue 2: "No contact form found among X form(s)"

**Symptom:**
```
📝 Found 2 form(s) on page
📋 Form 1: 3 fields | Email: false | Message: true | IsContact: false
📋 Form 2: 2 fields | Email: true | Message: false | IsContact: false
❌ No contact form found among 2 form(s)
```

**Possible Causes:**
1. Forms are missing required fields (email or message)
2. Field names don't match expected patterns
3. Forms are newsletter signups, login forms, etc.

**Solution:**
- Check the worker logs to see field names
- Verify if form truly has both email and message fields
- Consider adjusting form detection criteria if needed

### Issue 3: "Failed to navigate"

**Symptom:**
```
⚠️  Failed to check page
    url: https://example.com/contact
    error: failed to navigate: context deadline exceeded
```

**Possible Causes:**
1. Website is down or slow to respond
2. Network timeout
3. Website blocks automated browsers

**Solution:**
- Increase timeout: `browser.timeout_seconds`
- Check if website is accessible manually
- Consider using proxies if site blocks automation

### Issue 4: Forms detected but fields look wrong

**Example:**
```
📋 Form 1: 8 fields | Email: true | Message: true | IsContact: true
```

But when you check the database, the form has strange fields.

**Solution:**
Use the debug script to see the actual JSON:
```bash
./scripts/debug_domain.sh "" https://example.com/
```

Look at the `fields` JSON column to see what was extracted.

## Field Detection Rules

The system looks for fields based on common patterns:

### Email Field
Matches if name/placeholder/label contains:
- `email`
- `e-mail`
- `mail`

### Message Field
Matches if:
- name/placeholder/label contains: `message`, `comment`, `inquiry`
- OR field type is `textarea`

### Name Field (informational)
- Detected but not required for contact form classification

### Phone Field
- Detected but not required

## Testing Individual Domains

### Quick Test

1. **Reset system:**
   ```bash
   ./scripts/reset_light.sh
   ```

2. **Create test CSV:**
   ```csv
   domain
   https://example.com/
   ```

3. **Load domain:**
   ```bash
   ./scripts/load_domains.sh test.csv
   ```

4. **Watch discovery worker logs** (Terminal 1):
   ```bash
   go run cmd/discovery-worker/main.go --config config/config.local.yaml
   ```

5. **Check results** (Terminal 2):
   ```bash
   ./scripts/list_domains.sh
   ```

### Manual Form Check

To manually verify what's on a page:

```bash
# Open the URL in headless browser and check
curl -s https://example.com/contact | grep -i "<form"
```

Or use browser dev tools to inspect form elements.

## Advanced Debugging

### Enable Verbose Browser Logging

Currently, the system logs to stdout. Watch the discovery worker terminal for real-time logs:

```bash
go run cmd/discovery-worker/main.go --config config/config.local.yaml 2>&1 | tee discovery.log
```

This saves logs to `discovery.log` while displaying them.

### Check Database Directly

```bash
psql -h 127.0.0.1 -U formbot -d form_submissions

-- See all domains
SELECT id, url, status, contact_url, attempts, last_error 
FROM domains 
ORDER BY updated_at DESC;

-- See form fields as JSON
SELECT url, fields::text 
FROM contact_forms 
WHERE domain_id = 1;

-- See recent errors
SELECT * FROM errors ORDER BY created_at DESC LIMIT 10;
```

### Check Specific Pages

The system checks these paths for each domain (in order):

1. `/contact`
2. `/contact-us`
3. `/get-in-touch`
4. `/support`
5. `/help`
6. `/reach-us`
7. `/about/contact`
8. Homepage (if none of the above work)

You can modify these patterns in `config/config.local.yaml`:

```yaml
discovery:
  contact_path_patterns:
    - "/contact"
    - "/contact-us"
    # Add more patterns here
```

## Interpreting Results

### Success Case ✅

```
✅ https://vietnam.acclime.com/
   Status: found
   Contact URL: https://vietnam.acclime.com/contact
   Fields: 4 (email, name, phone, message)
   CAPTCHA: No
```

This domain will proceed to submission.

### Not Found Case ❌

```
❌ https://example.com/
   Status: not_found
   Attempted: 8 pages
   Reason: No form with both email and message fields
```

This domain is skipped (won't submit).

### Failed Case ⚠️

```
⚠️  https://slow-site.com/
   Status: failed
   Error: navigation timeout
   Attempts: 2
```

This domain encountered errors and stopped processing.

## Summary of New Tools

| Command | Purpose |
|---------|---------|
| `./scripts/list_domains.sh` | View all domains with status icons |
| `./scripts/debug_domain.sh <url>` | Deep dive into specific domain |
| `./scripts/monitor.sh` | Watch progress with domain list |
| Enhanced worker logs | Real-time form detection details |

## Next Steps

1. **Run discovery on your test domains**
2. **Watch the worker logs** to see detailed form analysis
3. **Use `list_domains.sh`** to see which domains succeeded/failed
4. **Use `debug_domain.sh`** to investigate specific domains
5. **Adjust config if needed** (timeouts, patterns, etc.)

---

**Remember:** Not all websites have contact forms! It's normal to see some "not found" results.
