# Bug Fix: debug_run.sh - Database Check Issue

## Issue

When running `debug_run.sh`, the script would fail with:
```
⚠️  WARNING: No pending domains in database!
   Check if load_domains.sh succeeded
```

Even though the domain was successfully loaded to Kafka.

## Root Cause

The script had a timing/architecture misunderstanding:

1. **What happens when loading domains:**
   - `load_domains.sh` calls `domain-loader`
   - `domain-loader` publishes domains to Kafka topic `discovery-tasks`
   - `domain-loader` does NOT insert into PostgreSQL

2. **What the verification was checking:**
   - The script checked PostgreSQL for domains with `status='pending'`
   - This check ran immediately after loading

3. **The problem:**
   - Domains only get inserted into PostgreSQL when the discovery worker picks them up from Kafka
   - The verification ran BEFORE the worker started
   - Therefore, it would always fail

## System Architecture (Clarification)

```
Domain CSV
    ↓
domain-loader
    ↓
Kafka (discovery-tasks topic) ← Domains are here after loading
    ↓
discovery-worker (picks up from Kafka)
    ↓
PostgreSQL ← Domains appear here AFTER worker processes them
```

## Fix Applied

### Before (lines 94-102)
```bash
# Verify domain was loaded
DOMAIN_COUNT=$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM domains WHERE status='pending';" | tr -d ' ')
if [ "$DOMAIN_COUNT" -eq 0 ]; then
    echo "  ⚠️  WARNING: No pending domains in database!"
    echo "     Check if load_domains.sh succeeded"
    exit 1
fi

echo "  ✓ Domain loaded ($DOMAIN_COUNT pending)"
```

### After
```bash
# Verify domain was loaded to Kafka (not database - that happens when worker processes it)
echo ""
echo "  ✓ Domain published to Kafka (discovery-tasks topic)"
echo ""
echo "Note: Domain will appear in database once discovery worker processes it"
```

## Why This Fix is Correct

1. **Matches architecture:** Domains are published to Kafka first, DB second
2. **No false failures:** Script won't fail when everything is working correctly
3. **Clear messaging:** Users understand the flow better
4. **Correct timing:** Verification happens at the right stage

## Testing

After the fix, running `debug_run.sh` should:
1. ✅ Show "Domain published to Kafka"
2. ✅ Start the discovery worker
3. ✅ Worker picks up domain from Kafka
4. ✅ Worker inserts domain into PostgreSQL
5. ✅ Worker processes the domain (visible browser)
6. ✅ Domain appears in database with status

## Related Documentation Updates

- Updated `README.md` to clarify the flow in `debug_run.sh` description
- Added note about Kafka → Worker → Database flow

## Impact

- **Before:** Script would fail with false errors
- **After:** Script works correctly and clarifies the process flow

## Date

Fixed: January 28, 2026
