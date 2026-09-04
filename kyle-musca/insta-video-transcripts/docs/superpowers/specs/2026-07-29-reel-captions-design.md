# Reel Captions Design

**Date:** 2026-07-29  
**Status:** Approved (option B)

## Problem

`instagram_reels_transcripts.py` already maps caption → `title` when present (`post.caption` / clips `media.caption.text`), falling back to `reel_{shortcode}`. After the GraphQL crash fix, crawl uses the clips connection enumerator. That list payload usually omits caption, so every saved sidecar is `title: "reel_<shortcode>"` with no caption field (~3k metadata files across profiles). Instaloader still supports captions via full post metadata (`Post.caption`), and the local `patch_instaloader_post_metadata` already maps `caption.text` → `edge_media_to_caption`.

## Goals

1. Persist full reel caption in metadata without breaking reel listing / enqueue / transcribe.
2. Put the full caption into each transcript’s `Title:` header (filenames stay as-is for existing files).
3. Backfill captions for existing `metadata/*.json` + matching `transcripts/*.txt` without re-downloading or re-running Whisper.
4. If a reel has no caption (or fetch fails), bypass enrichment and leave `reel_*` title — never abort the listing loop.

## Non-goals

- Renaming transcript files.
- Re-transcribing audio.
- Changing Redis job schema in a breaking way (additive `caption` only).
- Fetching caption during clips enumeration (extra GraphQL per page item would slow/break listing under rate limits).

## Design

### Data model

Extend `ReelVideo` and sidecar JSON:

| Field | Role |
|-------|------|
| `caption` | Full caption text as posted (may be `""`). New optional field; default `""` when missing. |
| `title` | Display title. When caption exists: same as full caption with internal newlines collapsed to spaces (single-line safe for `Title:` headers and consolidate parser). When no caption: `reel_{shortcode}`. |

Filenames continue to use `build_output_filename(title, mediaid)` at process time. Backfill **must not** rename files. Forward path: compute transcript path **before** caption enrichment when title is still `reel_*`, so resume paths stay stable even if title is updated afterward for the header/metadata.

### Caption fetch

Shared helper (used by live enrich + backfill):

```text
fetch_reel_caption(loader, shortcode) -> str | None
```

- Call `patch_instaloader()` then `Post.from_shortcode(context, shortcode)`.
- Return stripped `post.caption` or `None` if empty/missing.
- On Instaloader/network errors: return `None` (caller bypasses). Never raise into the listing iterator.

Backfill / enrich with proxy (local):

```text
fetch_reel_caption_with_proxy_fallback(loader, shortcode, proxy_url: str | None) -> str | None
```

1. If `proxy_url` is set, apply it to `loader.context._session.proxies` (same shape as `ProxyPool.as_requests_proxies`) and attempt the caption fetch.
2. On success with a non-empty caption → return it.
3. On empty caption → return `None` (do not retry direct; reel has no caption).
4. On proxy/network/Instaloader failure → clear session proxies and retry once on the **default/direct** network.
5. If direct also fails or caption empty → return `None` (bypass).

Proxy source for backfill: `load_env_files()` + existing `resolve_proxy_urls(args)` so `.env` `WEBSHARE_PROXY_USERNAME` / `WEBSHARE_PROXY_PASSWORD` / host / port work without extra flags. Support `--bypass-proxy` to skip Webshare entirely. When credentials are present, backfill **prefers proxy first**, then falls back to direct (unlike cloud crawl’s cookie-IP caution — backfill is local and needs anti-block; fallback covers proxy outages).

Normalize for `title` / transcript header:

```text
caption_as_title(caption: str) -> str
# collapse newlines/whitespace to single spaces; strip; empty → ""
```

### Forward path (keep scraping flow)

1. **Listing unchanged:** `iter_reel_candidates` / `reel_video_from_clips_media` keep current yield rules. Missing caption → `title=reel_{shortcode}`, `caption=""`. No new API calls in the iterator.
2. **Enrich at process time** (local/worker `process_queue_item`, and when writing sidecar in that path):
   - If `caption` already non-empty → skip fetch.
   - Else fetch by shortcode; if `None` → bypass (leave reel title).
   - If found → set `caption` + `title=caption_as_title(caption)`.
3. **`build_transcript_text`:** `Title:` uses `caption_as_title(caption)` if caption else `title` (full caption text, single line).
4. **`write_sidecar_metadata` / Redis job dict:** include `caption`; keep backward-compatible reads (`caption` default `""`).

### Backfill script (local laptop; no re-transcribe)

New CLI: `backfill_reel_captions.py` — **designed to run on the developer’s local machine**, not on the EC2/cloud transcription host.

- **Why local:** only Instaloader + cookies/session + filesystem writes. No Whisper, no pyannote, no GPU, no Redis, no video download.
- **Deps:** lightweight `requirements-backfill.txt` (`instaloader`, `requests`, `python-dotenv` only). Do not require installing `faster-whisper` / `pyannote.audio` / `redis` / torch to run backfill.
- **Import rule:** backfill may import helpers from `instagram_reels_transcripts.py`, but must never call `load_whisper_model`, diarization, Redis, or download helpers. Keep those heavy imports lazy inside the main script (already the case) so `import instagram_reels_transcripts` stays cheap on a laptop.
- Input: local profile output dir (e.g. `output/_biggcal`) with `metadata/` and `transcripts/` — copy/rsync from cloud if needed; backfill mutates local files then sync back if desired.
- Reuse the same Instaloader session/cookie setup as the main script (import helpers; do not duplicate auth patches). Prefer `--cookies-json` from a browser export on the laptop.
- **Proxy:** load Webshare from `.env` via existing `resolve_proxy_urls` / `WEBSHARE_PROXY_*`. For each caption fetch, try proxy first; if the proxy fails (connection error, timeout, Instaloader error), clear proxies and retry once on the default local network. `--bypass-proxy` forces direct-only.
- For each `metadata/{mediaid}.json`:
  - If `caption` already non-empty and transcript `Title:` already matches → skip.
  - Else fetch caption by `shortcode`.
  - No caption / error → bypass (log `skipped_no_caption` / `skipped_error`); continue.
  - On success: update metadata `caption` + `title`; patch matching transcript `*__{mediaid}.txt` header `Title:` only (find by mediaid suffix). Do not rename.
- Flags: `--dry-run`, `--limit`, `--request-delay-*`, same session/cookie flags as main where practical.
- Exit non-zero only on fatal setup failure (no cookies/session), not on per-item bypasses.

Local smoke:

```bash
python3 -m venv .venv-backfill && source .venv-backfill/bin/activate
pip install -r requirements-backfill.txt
# .env already has WEBSHARE_PROXY_*; script tries proxy then falls back to direct
python backfill_reel_captions.py output/_biggcal --cookies-json cookies.json --dry-run --limit 5 --verbose
```

### Transcript header format

Keep existing keys. `Title:` becomes one physical line containing the full caption with whitespace collapsed:

```text
Title: <full caption single-line>
Media ID: ...
Shortcode: ...
URL: ...
Date UTC: ...
```

`filter_and_consolidate_transcripts.py` continues to work (header keys unchanged).

## Testing

- Unit tests for `caption_as_title`, metadata/job round-trip with `caption`, transcript header rewrite by mediaid, bypass when caption missing.
- Dry-run backfill against a tiny fixture dir (no live Instagram in CI).
- Manual smoke: one shortcode with caption + one without, against real session if available.

## Success criteria

- Listing still yields reels with empty captions without crashing.
- New transcripts get full caption in `Title:` when Instagram returns one.
- Backfill updates existing metadata + transcript headers without Whisper/download.
- Backfill runs on a local laptop with only `requirements-backfill.txt` (no cloud GPU stack).
- Reels with no caption remain `reel_*` and are skipped by backfill enrichment.
