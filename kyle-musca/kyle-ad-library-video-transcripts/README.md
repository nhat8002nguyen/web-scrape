# Kyle Ad Library Video Transcripts

Resumable CLI to scrape **Meta Ad Library** video creatives for a Facebook Page, download them, and transcribe with local Whisper (`faster-whisper`, default `large-v3`).

Sibling to [`kyle-insta-video-transcripts`](../kyle-insta-video-transcripts/) — same Redis producer/worker patterns, but the **default is single-machine one-flow with no Redis**.

## Modes

| Mode | Redis? | What it does |
|------|--------|--------------|
| `local` (default) | No | One process: scrape Ad Library → download → Whisper → write transcripts |
| `producer` | Yes | Scrape and `XADD` jobs only |
| `worker` | Yes | Consume stream and transcribe |
| `requeue-skipped` | Yes | Re-enqueue from `skipped.jsonl` + metadata |

## Install

```bash
cd kyle-ad-library-video-transcripts
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Also install **`ffmpeg`** (e.g. `brew install ffmpeg` on macOS).

```bash
cp .env.example .env
```

## Dry-run

```bash
python ad_library_video_transcripts.py \
  --page-id 116482854782233 \
  --dry-run \
  -n 5 \
  --verbose
```

Or pass a full Ad Library URL:

```bash
python ad_library_video_transcripts.py \
  --ad-library-url 'https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&media_type=video&search_type=page&view_all_page_id=116482854782233' \
  --dry-run \
  -n 5
```

## Quick Start — single machine, one flow (no Redis)

Default `--redis-mode local`. No `REDIS_URL` required.

```bash
python ad_library_video_transcripts.py \
  --page-id 116482854782233 \
  --out ./output \
  -n 5 \
  --resume \
  --model-size large-v3 \
  --disable-diarization \
  --verbose
```

Output layout:

- `output/videos/<ad_archive_id>.mp4`
- `output/metadata/<ad_archive_id>.json`
- `output/transcripts/*__<ad_archive_id>.txt`
- `output/checkpoint.json`
- `output/skipped.jsonl`

**CDN note:** Ad Library `video_hd_url` values expire. Local mode downloads immediately after scrape. If you use Redis, start workers soon after the producer.

## Optional Redis scaling

Stream default: `adlib:video:jobs`. Job payload keys match Instagram workers (`mediaid`, `shortcode`, `title`, `video_url`, `post_url`, `date_utc`) where `mediaid` is the Ad Library ID.

**Producer:**

```bash
python ad_library_video_transcripts.py \
  --page-id 116482854782233 \
  --redis-mode producer \
  --redis-url "$REDIS_URL" \
  --redis-stream adlib:video:jobs \
  --redis-producer-dedupe \
  --resume \
  --out /mnt/efs/adlib-output \
  --verbose
```

**Worker:**

```bash
python ad_library_video_transcripts.py \
  --redis-mode worker \
  --redis-url "$REDIS_URL" \
  --redis-stream adlib:video:jobs \
  --redis-group transcribers \
  --out /mnt/efs/adlib-output \
  --resume \
  --model-size large-v3 \
  --disable-diarization \
  --verbose
```

## Tests

```bash
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
```

## Maintenance notes

- Stay **logged out** of Facebook in automation (public Ad Library only).
- GraphQL `doc_id` / page HTML shape can change; parser unit tests cover the JSON contract; use `--verbose` when scroll extraction returns zero results.
- First `large-v3` load may download several GB into the Hugging Face cache.
