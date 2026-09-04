---
name: debugging-instagram-429
description: Use when instagram_reels_transcripts.py or Instaloader fails with 429 Too Many Requests, web_profile_info, GraphQL execution error, stale doc_id, empty reel listing, current_user fail, cookie session rejected, or Profile.from_username breaks. Diagnose the failing Instagram endpoint before changing code.
---

# Debugging Instagram 429 / Instaloader Breaks

**REQUIRED BACKGROUND:** Use systematic-debugging. Do not guess a new `doc_id` or re-export cookies until the failing URL is identified.

Patches live in `instagram_reels_transcripts.py` (`patch_instaloader_*`, `INSTAGRAM_*_DOC_ID`). PyPI Instaloader is often already latest; the break is usually Instagram rotating an endpoint.

## Do this first

1. **Stop retries.** Instaloader waits ~666s on 429. Kill the process. Do not run producer on EC2 and locally in parallel.
2. **Reproduce locally** with a tiny dry-run (same `cookies.json`):

```bash
source .venv/bin/activate
python instagram_reels_transcripts.py "https://www.instagram.com/<user>/reels/" \
  --dry-run -n 3 --cookies-json ./cookies.json --verbose
```

3. **Read the first failing URL**, not the last retry. Map it with the table below.
4. **Probe that one endpoint** with a short Python snippet (cookies + `patch_instaloader()`). Do not start a producer.

## Symptom → cause

| Log / symptom | Likely cause | Fix |
|---|---|---|
| `web_profile_info` **429** (often after `session verified as @…`) | Instaloader `Profile.from_username()` still hits this first. AWS IPs make it worse. | Keep/repair `patch_instaloader_profile_from_username()` (topsearch). Do **not** treat as “need newer Instaloader”. |
| `current_user` 200 + `"fail"` / “something went wrong” | iPhone login probe is flaky. Fallback GraphQL (`d6f4427fbe92d846298cf93df0b937d3`) may still verify the session. | Ignore if the next line is `session verified`. Only re-export cookies if verification fails. |
| GraphQL `execution error` / `data: null` / 400 invalid request | Stale **or** too-new `doc_id`. Live JS ids can fail via Instaloader’s POST. | Extract live ids ([doc-ids.md](doc-ids.md)), **probe each** (old + new). Keep the id that returns `data`. |
| Dry-run: `No video posts found` but profile exists | Clips connection works but list items omit `video_versions`. Old code returned `None` and skipped every reel. | `reel_video_from_clips_media` must accept `product_type==clips` / missing `video_versions`. Hydrate URL via `api/v1/media/{pk}/info/`. Do not skip empty `video_url` in `iter_reel_candidates`. |
| 403 on `graphql/query` after cookies | Cookie IP ≠ crawl IP, or missing `csrftoken` / `X-CSRFToken`. | Crawl on the same IP as the browser export. `--proxy-downloads-only`. Re-export cookies. |
| 429 with **tiny** request counts (1–3 in 60 min) | Session or IP cooldown, not “too many queries”. | Wait. Re-export cookies from the **home/residential** machine. Keep **producer off EC2**. |
| `pip install -U instaloader` no-op at 4.15.3 | Already latest. `from_username` still uses `web_profile_info`. | Patch here; do not wait for a release. |

## Known-good constants (verify before replacing)

```
INSTAGRAM_PROFILE_PAGE_DOC_ID  27937681195819736   # PolarisProfilePageContentQuery
INSTAGRAM_POST_ROOT_DOC_ID     27128499623469141   # PolarisPostRootQuery (may error)
INSTAGRAM_CLIPS_USER_DOC_ID    27234427476213202   # xdt_api__v1__clips__user__connection_v2
```

Live JS (Sep 2026) also shipped `28036671149327607` (profile) and `29326377470285825` (post). Those returned **execution error** through Instaloader. Never swap a constant just because it appears in the web bundle.

Clips field must stay `data.xdt_api__v1__clips__user__connection_v2`.

## Diagnose before patching

```
429 / fail
  → which URL?
     web_profile_info     → from_username patch / IP / cookies
     graphql/query        → probe doc_id (old vs extracted)
     clips connection     → field name + video_versions / media info
     current_user only    → session fallback; do not rewrite listing
```

**Probe rules**

- A `doc_id` is valid only if `data` is non-null (errors array alone is a fail).
- Profile metadata needs `id` + the existing relay variables (see `patch_instaloader_profile_graphql`). Slimmer variable sets can 400.
- After a clips query, print first media keys. If `code`/`pk` exist but `video_versions` is missing, that is a mapping bug, not a 429.

## Ops constraints (do not “fix” with more EC2 retries)

- Cookies from a browser + **producer on AWS** is the usual 429. Run producer on the cookie machine; workers may stay on EC2.
- `.env` `INSTALOADER_SESSION_USERNAME` must match the cookie account (`ds_user_id` / verified `@user`).
- `sync-to-ec2.sh` excludes `.env`. After a code fix, sync `instagram_reels_transcripts.py` (and `cookies.json` if refreshed).
- Do not wait out Instaloader’s 666s retry in an agent session. Kill it.

## After a code change

Dry-run `-n 3` locally until three `mediaid shortcode` lines print. Only then sync and run `--redis-mode producer`.

## Additional resources

- Extract and probe GraphQL `doc_id`s: [doc-ids.md](doc-ids.md)
