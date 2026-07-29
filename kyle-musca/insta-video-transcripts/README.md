# Kyle Instagram Video Transcripts

Resumable CLI pipeline to:

- crawl `kyle.musca` (or any target profile) with Instaloader,
- download reel videos for later processing,
- transcribe with local Whisper Large V3 (`faster-whisper`),
- keep dominant-speaker transcript segments (Kyle-main heuristic),
- write deduplicated text files as `{sanitized_title}__{mediaid}.txt`,
- **optional:** enqueue work to **Redis** (`--redis-mode producer`) and run **horizontal workers** (`--redis-mode worker`) that consume a stream with **consumer groups** (no duplicate delivery per message).

## Install

The script is **portable Python 3**; use a **venv** on both **macOS** (local) and **Linux** (e.g. **Ubuntu on EC2**). OS-specific packages (mainly **`ffmpeg`**) are called out below.

```bash
cd kyle-insta-video-transcripts
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**macOS:** install **`ffmpeg`** too (e.g. `brew install ffmpeg`) so `ffmpeg` is on your `PATH` and pyannote/TorchCodec can resolve libraries; see **Dominant Speaker → macOS** if you hit loader errors.

Copy and edit environment values if needed:

```bash
cp .env.example .env
```

### Ubuntu Linux (including EC2)

The CLI is OS-agnostic (`ffmpeg` via **PATH**, Hugging Face cache under `~/.cache/huggingface/hub`). On **Ubuntu 22.04/24.04** (typical on EC2):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg git

cd kyle-insta-video-transcripts
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

or simply run the following command:
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip ffmpeg git redis-server && cd kyle-insta-video-transcripts && python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt && sudo systemctl enable --now redis-server
```

- **`ffmpeg`** satisfies pyannote’s need for a normal decode path and the script’s temporary WAV extraction; distro packages install libraries under `/usr/lib/...` where TorchCodec/pyannote expect them on Linux—no Homebrew on servers.
- **Graviton (arm64)** and **x86_64** AMIs both work; use wheels that match your architecture (pip resolves this automatically in most cases).
- **GPU workers** (`g5.*`, etc.): install the **NVIDIA driver + CUDA runtime** stack for your AMI (e.g. [AWS GPU docs](https://docs.aws.amazon.com/dcv/latest/adminguide/setting-up-gpu.html), or use an AWS **Deep Learning Base AMI**), then run with **`--device cuda`** and a suitable **`--compute-type`** (see faster-whisper docs).

### Amazon Linux 2023 (EC2)

Example system packages (adjust names if your AMI uses a different Python):

```bash
sudo dnf install -y python3 python3-pip ffmpeg git
cd kyle-insta-video-transcripts
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**First real run (no `--dry-run`):** `faster-whisper` may download **multiple GB** for `large-v3` from Hugging Face. The terminal can look idle for a long time; use `--verbose` to see *Loading Whisper model…* / *Whisper model ready.* Set `HF_TOKEN` or `HUGGINGFACE_TOKEN` if you see Hub rate-limit warnings.

The script prints the **Hugging Face hub cache path** and a **heartbeat every 30s** while the model loads. To verify a download in progress, watch cache growth, e.g.:

```bash
du -sh ~/.cache/huggingface/hub
# or refresh every few seconds:
watch -n 5 'du -sh ~/.cache/huggingface/hub'
```

- **Rough time:** `large-v3` is on the order of **~2.5–4 GB**; on a typical home connection often **~5–40+ minutes** for the download alone, then extra time to initialize **CPU** (slower) or **GPU** (faster). Smaller models (`tiny`, `base`, `small`) are much faster for testing.

## Quick Start

Dry-run queue check:

```bash
python instagram_reels_transcripts.py "https://www.instagram.com/kyle.musca/reels/" \
  --dry-run \
  -n 5
```

Small real run:

```bash
python instagram_reels_transcripts.py "https://www.instagram.com/kyle.musca/reels/" \
  --out ./output \
  -n 3 \
  --resume \
  --verbose
```

Output layout (default):

- `output/videos/*.mp4`
- `output/metadata/*.json`
- `output/transcripts/*__<mediaid>.txt`
- `output/checkpoint.json`
- `output/skipped.jsonl`

## Backfill reel captions (local laptop; no re-transcribe)

Transcription can stay on EC2. Caption backfill runs on your Mac or PC with a
lightweight virtual environment:

```bash
cd kyle-musca/insta-video-transcripts
python3 -m venv .venv-backfill
source .venv-backfill/bin/activate
pip install -r requirements-backfill.txt

# Point at local output (rsync it from the cloud first if needed).
python backfill_reel_captions.py output/_biggcal \
  --cookies-json cookies.json \
  --dry-run --limit 5 --verbose

python backfill_reel_captions.py output/_biggcal --cookies-json cookies.json
```

The command uses `WEBSHARE_PROXY_*` from `.env` when configured. Each item
tries the proxy first and falls back to the default network if the proxy fails.
Pass `--bypass-proxy` to force direct-only requests.

It updates `metadata/*.json` (`caption` and `title`) and patches the `Title:`
header in matching `transcripts/*__{mediaid}.txt` files. It does not rename
transcripts, download videos, or re-transcribe them. Reels without captions are
left unchanged.

## Parallel chunks without Redis (one machine, multiple processes)

Use **`--limit` / `-n`** plus **`--start-after-mediaid`** so each process only **processes** its slice. Enumeration order is whatever Instaloader returns (for reels, usually **newest first**), so “1–100” means the first 100 reels in that order.

**No duplicate videos:** use the **same** `--out` for every process and **`--resume`**. With `--resume`, the script skips any `mediaid` that already has a transcript under `output/transcripts/`. Use a **different** `--checkpoint-file` per process (e.g. `checkpoint-chunk1.json`, `checkpoint-chunk2.json`) so parallel runs do not overwrite the same checkpoint JSON.

**1. Get boundary `mediaid`s** (100th and 200th reel in the listing — the **first column** of `dry-run` output):

```bash
python instagram_reels_transcripts.py "https://www.instagram.com/kyle.musca/reels/" \
  --dry-run \
  -n 300 \
  --cookies-json ./cookies.json \
  --proxy-downloads-only
```

Set shell variables from the output (example — replace with your real ids):

```bash
AFTER100=<mediaid_of_reel_100>   # last reel of chunk 1; chunk 2 starts after this
AFTER200=<mediaid_of_reel_200>   # last reel of chunk 2; chunk 3 starts after this
```

**`--start-after-mediaid`** skips until that `mediaid` appears, **does not** re-process it, then takes the next **`--limit`** reels.

**2. Run three jobs on the same host** (three terminals, or background with `&`). Adjust proxy/cookies/model flags to match your setup:

```bash
# Chunk 1: reels 1–100
python instagram_reels_transcripts.py "https://www.instagram.com/kyle.musca/reels/" \
  --out ./output \
  --checkpoint-file checkpoint-chunk1.json \
  -n 100 \
  --resume \
  --cookies-json ./cookies.json \
  --proxy-downloads-only \
  --webshare-user "$WEBSHARE_PROXY_USERNAME" \
  --webshare-password "$WEBSHARE_PROXY_PASSWORD" \
  --hf-token "$HUGGINGFACE_TOKEN" \
  --verbose
```

```bash
# Chunk 2: reels 101–200
python instagram_reels_transcripts.py "https://www.instagram.com/kyle.musca/reels/" \
  --out ./output \
  --checkpoint-file checkpoint-chunk2.json \
  --start-after-mediaid "$AFTER100" \
  -n 100 \
  --resume \
  --cookies-json ./cookies.json \
  --proxy-downloads-only \
  --webshare-user "$WEBSHARE_PROXY_USERNAME" \
  --webshare-password "$WEBSHARE_PROXY_PASSWORD" \
  --hf-token "$HUGGINGFACE_TOKEN" \
  --verbose
```

```bash
# Chunk 3: reels 201–300
python instagram_reels_transcripts.py "https://www.instagram.com/kyle.musca/reels/" \
  --out ./output \
  --checkpoint-file checkpoint-chunk3.json \
  --start-after-mediaid "$AFTER200" \
  -n 100 \
  --resume \
  --cookies-json ./cookies.json \
  --proxy-downloads-only \
  --webshare-user "$WEBSHARE_PROXY_USERNAME" \
  --webshare-password "$WEBSHARE_PROXY_PASSWORD" \
  --hf-token "$HUGGINGFACE_TOKEN" \
  --verbose
```

**Parallelism caveat:** chunks 2 and 3 still **scan** the reel iterator from the beginning until they reach `--start-after-mediaid` (Instagram/Instaloader traffic per process). Running all three at once can increase **rate-limit** risk; if you see throttling, stagger starts or run chunks back-to-back on one machine.

Optional one-liner to print boundary ids (same args as your dry-run):

```bash
python instagram_reels_transcripts.py "https://www.instagram.com/kyle.musca/reels/" \
  --dry-run -n 300 --cookies-json ./cookies.json --proxy-downloads-only \
  | awk 'NR==100 {print "AFTER100="$1} NR==200 {print "AFTER200="$1}'
```

## Webshare Username/Password (Primary Proxy Mode)

Use either CLI args or environment variables:

- `--webshare-user`, `--webshare-password`
- `WEBSHARE_PROXY_USERNAME`, `WEBSHARE_PROXY_PASSWORD`

Optional host/port overrides:

- `--webshare-host` (default `p.webshare.io`)
- `--webshare-port` (default `80`)

Example:

```bash
python instagram_reels_transcripts.py kyle.musca \
  --webshare-user "$WEBSHARE_PROXY_USERNAME" \
  --webshare-password "$WEBSHARE_PROXY_PASSWORD" \
  --proxy-mode rotating \
  --resume
```

The script masks credentials in logs.

**Bypass proxy (use machine IP everywhere):** if Webshare bandwidth is exhausted or you want no proxy, pass **`--bypass-proxy`** so Instaloader and video **`requests`** downloads ignore Webshare, **`--proxy-url`**, **`--proxy-file`**, and **`TRANSCRIPT_PROXY`**. You can instead set **`TRANSCRIPT_NO_PROXY=1`** or **`DIRECT_INSTAGRAM_DOWNLOADS=1`** in `.env` as the default; use **`--with-proxy`** on a one-off run to keep using Webshare anyway.

## Rate-Limit Safety Defaults (for ~1000 reels)

Built-in controls:

- jitter per Instagram listing request: `--request-delay-min` / `--request-delay-max`
- periodic cooldown: `--cooldown-every` + `--cooldown-seconds`
- exponential retry backoff: `--max-retries`, `--retry-backoff-base`, `--retry-backoff-max`
- emergency stop on unstable conditions: `--max-consecutive-errors`
- resumable progress with `checkpoint.json` + `--resume`

Suggested high-volume run:

```bash
python instagram_reels_transcripts.py kyle.musca \
  --resume \
  --request-delay-min 2 \
  --request-delay-max 6 \
  --cooldown-every 40 \
  --cooldown-seconds 120 \
  --max-consecutive-errors 8 \
  --verbose
```

## Dominant Speaker Extraction

Transcription:

- model: `faster-whisper` `large-v3`
- per-segment timestamps from Whisper

Dominant-speaker filtering:

- uses `pyannote.audio` diarization when token + model are available
- picks speaker with highest total speaking duration
- keeps Whisper segments with overlap ratio >= `--speaker-overlap-threshold` (default `0.5`)
- for non-WAV media, builds a temporary **16 kHz mono WAV** with **`ffmpeg`** before pyannote (avoids `ValueError: ... samples instead of the expected ...` on some MP4 decodes)

**Skip diarization entirely:** pass **`--disable-diarization`** (no pyannote load, no WAV extract for diarization) or set **`DISABLE_DIARIZATION=1`** in `.env`. Transcripts include **all** Whisper segments. To turn diarization back on when the env default is off, use **`--no-disable-diarization`**.

If diarization is unavailable (missing token/dependency), the script falls back to full transcript segments.

To enable diarization model download:

- set `HUGGINGFACE_TOKEN` in env or pass `--hf-token`.
- on Hugging Face, **each** of these repos is gated separately — sign in and accept the user conditions on **all** of them (the pipeline loads several dependencies; any missing accept still yields **403**):
  - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
  - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
  - [pyannote/wespeaker-voxceleb-resnet34-LM](https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM)
  - [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) (`xvec_transform.npz` and related assets)
- use a **read** access token for the **same** Hugging Face account (`HUGGINGFACE_TOKEN` / `HF_TOKEN` / `--hf-token`). A token from another login, or a fine‑grained token without read access to these models, still yields **403**.

**Linux (Ubuntu / EC2):** install **`ffmpeg`** from the distro (`apt install ffmpeg` above). If pyannote/torchcodec still cannot load `libav*`, ensure **`ffmpeg`** is on **`PATH`** (`which ffmpeg`) and install any missing **`libav*-dev`** / **`ffmpeg`** packages your OS documents; on stock Ubuntu the runtime libs are usually enough. **`LD_LIBRARY_PATH`** is rarely needed if `ffmpeg` came from `apt`.

**macOS (local dev):** **TorchCodec** (used by recent `pyannote.audio`) often looks for FFmpeg under **`/opt/homebrew/opt/ffmpeg/lib/`** (Apple Silicon Homebrew). If `brew install ffmpeg` says FFmpeg is installed but errors show **`/opt/homebrew/opt/ffmpeg/...` (no such file)** while **`brew --prefix ffmpeg`** is **`/usr/local`** (Intel/Rosetta Homebrew on an arm64 Mac), libraries live under **`/usr/local/opt/ffmpeg/lib/`** instead.

**Fix on macOS (pick one):**

- Prefer native ARM Homebrew: `eval "$(/opt/homebrew/bin/brew shellenv)"` then `brew install ffmpeg`.
- Symlink so the expected path exists, e.g. after `brew --prefix ffmpeg` prints `/usr/local/opt/ffmpeg`:
  `sudo mkdir -p /opt/homebrew/opt && sudo ln -sf "$(brew --prefix ffmpeg)" /opt/homebrew/opt/ffmpeg`
- Or try: `DYLD_LIBRARY_PATH="$(brew --prefix ffmpeg)/lib" python instagram_reels_transcripts.py …`

On **macOS only**, duplicate FFmpeg loads may print **`objc[…]: Class AVFFrameReceiver … PyAV … and … Cellar/ffmpeg`**; it is often harmless. If you see crashes, try `pip install -U av` or **`--disable-diarization`**.

## CLI Arguments (Main)

- Target and mode: `target`, `--target`, `--mode reels|posts`
- Compatibility args: `--out/-o`, `--delay`, `-n/--limit/--first`, `--resume`, `--verbose`
- Batch/resume: `--start-after-mediaid`, `--max-items-per-run`, `--checkpoint-file`, `--skip-log`
- Instagram auth: `--sessionfile`, `--session-username` (or `INSTALOADER_SESSION_USERNAME`), `--cookies-json` (or `COOKIES_JSON`), `--instagram-user`, `--instagram-password` / `INSTAGRAM_PASSWORD`, `--user-agent`
- Proxy: `--proxy-mode`, `--proxy-url`, `--proxy-file`, `--webshare-user`, `--webshare-password`, **`--proxy-downloads-only`**, **`--bypass-proxy`**, **`--with-proxy`**
- Whisper: `--model-size`, `--device`, `--compute-type`, `--beam-size`, `--language`, `--vad-filter`
- Diarization: `--hf-token`, `--disable-diarization`, `--speaker-overlap-threshold`
- Redis scaling: `--redis-mode` (`local`|`producer`|`worker`|`requeue-skipped`), `--redis-url`, `--redis-stream`, `--redis-group`, `--redis-consumer-name`, `--redis-block-ms`, `--redis-idle-exit-seconds`, **`--redis-idle-notify-seconds`** (Simplepush when idle), `--redis-max-jobs`, `--redis-producer-dedupe`, **`--requeue-reason-contains`**
- Per-item cap: `--item-timeout-seconds` (optional; Unix **SIGALRM** for download+transcribe; failures logged as **`JobTimeout`** in `skipped.jsonl`)
- Notifications: `--simplepush-key`, `--simplepush-title`, `--simplepush-event`, `--test-simplepush`

Run `python instagram_reels_transcripts.py --help` for full flags.

## Simplepush Notifications

Test:

```bash
python instagram_reels_transcripts.py --test-simplepush --simplepush-key "YOUR_KEY"
```

During normal runs, notifications are sent on stop-threshold events and completion summaries.

## Horizontal scaling (Redis)

Use a **Redis stream** and **consumer group** so many EC2 workers pull jobs **without duplicates**: each message is delivered to **one** consumer until it **`XACK`**s after a successful run.

**Roles**

| Role | `--redis-mode` | What it does |
|------|----------------|--------------|
| Crawl / enqueue | `producer` | Runs Instaloader and **`XADD`s** each reel to Redis **as soon as it is enumerated** (workers can start before the full crawl finishes). Does **not** load Whisper. |
| Transcribe | `worker` | Loops **`XREADGROUP`**, download + Whisper + diarize for each job. Does **not** hit Instagram for listing. |
| Re-queue failures | `requeue-skipped` | Reads **`skipped.jsonl`** + **`metadata/<mediaid>.json`** (must include `video_url`), **`XADD`s** jobs again. No Instaloader / Whisper. Use **`--dry-run`** to preview. Optional **`--requeue-reason-contains JobTimeout`** to filter lines. |

**Re-run failed jobs (multiple workers in parallel):** workers already share one consumer group—each job goes to **one** worker. After **`requeue-skipped`** has refilled the stream, start **the same** `worker` command on as many EC2 instances as you like (or multiple terminals), all with the **same** `--out`, `REDIS_URL`, `--redis-stream`, and **`--redis-group`**.

1. **Inspect** (optional): `python ... --redis-mode requeue-skipped --out /mnt/efs/kyle-insta-output --dry-run --verbose`
2. **Enqueue** from skip log:  
   `python instagram_reels_transcripts.py kyle.musca --redis-mode requeue-skipped --redis-url "$REDIS_URL" --out /mnt/efs/kyle-insta-output --resume --skip-log skipped.jsonl`  
   Add **`--requeue-reason-contains JobTimeout`** (or `PermissionError`, etc.) to only replay matching failures.
3. **Run workers** (N machines or N processes—typically **one worker process per machine**): same command as your normal **`--redis-mode worker`** (e.g. `--bypass-proxy`, `--disable-diarization`, `--item-timeout-seconds`, `--redis-max-jobs` as needed).

Entries **without** a metadata file or **`video_url`** (e.g. download failed before the sidecar was written) are **not** enqueued; re-run the **producer** for those reels or fix paths. Expired CDN **`video_url`** values may still fail until you refresh metadata via a new crawl.

**Redis on the producer EC2 (skip ElastiCache):** you can run **redis-server** on the same instance that runs `--redis-mode producer` and point workers at it over the **VPC private network** (do **not** expose port 6379 to the public internet).

1. **Install** (Ubuntu):
   ```bash
   sudo apt update && sudo apt install -y redis-server
   sudo systemctl enable --now redis-server
   ```
2. **Configure** `/etc/redis/redis.conf` on that instance:
   - **`bind`:** use the instance **private IPv4** (see EC2 → instance details) or `0.0.0.0` only if you lock down access with a security group (default `127.0.0.1` is not enough for remote workers).
   - **`requirepass`:** set a strong password. With `protected-mode yes`, a password is expected when Redis listens on non-loopback addresses.
   - Restart: `sudo systemctl restart redis-server`
3. **Security group:** allow inbound **TCP 6379** (or the port in `port`) **only** from the workers’ security group or your VPC subnet—not `0.0.0.0/0`.
4. **`REDIS_URL`** — password-only URLs use a **leading colon** before the password (no username):
   - **On the producer** (same machine):  
     `export REDIS_URL='redis://:YOUR_PASSWORD@127.0.0.1:6379/0'`
   - **On workers:** use the producer’s **private DNS** (e.g. `ip-10-0-2-45.ap-southeast-1.compute.internal`) or **private IP**:  
     `export REDIS_URL='redis://:YOUR_PASSWORD@10.0.2.45:6379/0'`  
   The CLI also accepts `--redis-url` or `REDIS_URL` in `.env` (see `.env.example`).

Quick check from a worker: `redis-cli -h <producer-private-ip> -a YOUR_PASSWORD ping` (returns `PONG`). With **Redis 8** `redis-cli`, avoid `redis://:password@host` — use **`redis-cli -u 'redis://default:YOUR_PASSWORD@host:6379/0' ping`** (explicit `default` user) or stick to `-h` / `-a`. In **`REDIS_URL`**, `redis://:password@...` is still fine for **redis-py**; if a client ever misbehaves, try `redis://default:password@...`.

**Shared storage:** point every worker at the **same** `--out` tree (e.g. **Amazon EFS** mounted at `/mnt/efs/kyle-insta-output` on all instances) so transcripts, checkpoint, and `skipped.jsonl` stay consistent. Alternatively use a single shared volume or sync objects to S3 yourself.

**Topology: 1 instance = producer + worker, 2 instances = worker only (3 workers total)**  
Run **Redis** on the same host that also runs the producer (see **Redis on the producer EC2** above). All three machines use the **same** `REDIS_URL` (instance A uses `127.0.0.1` in the URL; B and C use A’s **private IP** or **private DNS**), the **same** `--redis-stream` and **`--redis-group`**, and the **same** `--out` path (typically EFS).

1. **Instance A** — enqueue, then consume (two processes, e.g. two `tmux` panes or run producer to completion then start the worker):
   - **Producer** (Instaloader + `XADD` only; no Whisper load):

     ```bash
     export REDIS_URL='redis://:YOUR_PASSWORD@127.0.0.1:6379/0'

     python instagram_reels_transcripts.py "https://www.instagram.com/kyle.musca/reels/" \
       --redis-mode producer \
       --redis-url "$REDIS_URL" \
       --cookies-json ./cookies.json \
       --proxy-downloads-only \
       --resume \
       --out /mnt/efs/kyle-insta-output \
       --verbose
     ```

   - **Worker** on the **same** instance (Whisper + downloads from the stream). Default consumer name is `hostname:pid`, so one process per machine is already unique):

     ```bash
     export REDIS_URL='redis://:YOUR_PASSWORD@127.0.0.1:6379/0'

     python instagram_reels_transcripts.py kyle.musca \
       --redis-mode worker \
       --redis-url "$REDIS_URL" \
       --redis-stream insta:reel:jobs \
       --redis-group transcribers \
       --out /mnt/efs/kyle-insta-output \
       --resume \
       --proxy-downloads-only \
       --webshare-user "$WEBSHARE_PROXY_USERNAME" \
       --webshare-password "$WEBSHARE_PROXY_PASSWORD" \
       --hf-token "$HUGGINGFACE_TOKEN" \
       --model-size large-v3 \
       --verbose
     ```

   You can **start the worker before the producer finishes** so B/C and A drain jobs while new ones are added; or finish the producer first, then run three workers.

2. **Instances B and C** — **worker only**, with `REDIS_URL` pointing at **instance A** (not `127.0.0.1`):

   ```bash
   export REDIS_URL='redis://:YOUR_PASSWORD@10.0.1.23:6379/0'   # A’s private IPv4, example only

   python instagram_reels_transcripts.py kyle.musca \
     --redis-mode worker \
     --redis-url "$REDIS_URL" \
     --redis-stream insta:reel:jobs \
     --redis-group transcribers \
     --out /mnt/efs/kyle-insta-output \
     --resume \
     --proxy-downloads-only \
     --webshare-user "$WEBSHARE_PROXY_USERNAME" \
     --webshare-password "$WEBSHARE_PROXY_PASSWORD" \
     --hf-token "$HUGGINGFACE_TOKEN" \
     --model-size large-v3 \
     --verbose
   ```

With one consumer group, **each job is delivered to exactly one** of the three workers until it **`XACK`**s. **`--resume`** plus shared `--out` avoids redoing transcripts that already exist on disk.

**Example (producer on one small instance or laptop)**

```bash
export REDIS_URL='redis://your-elasticache.xxx.cache.amazonaws.com:6379/0'

python instagram_reels_transcripts.py "https://www.instagram.com/kyle.musca/reels/" \
  --redis-mode producer \
  --redis-url "$REDIS_URL" \
  --cookies-json ./cookies.json \
  --proxy-downloads-only \
  --resume \
  --out /mnt/efs/kyle-insta-output \
  --verbose
# Add other crawl flags as needed: --request-delay-min, -n, etc.
```

Optional **`--redis-producer-dedupe`**: uses a Redis set `stream:enqueued` so re-running the producer does not enqueue the same `mediaid` again (after failures you may need to `DEL insta:reel:jobs:enqueued` or omit dedupe).

**Example (worker on N GPU/CPU instances)**

Use the **same** `--out`, `REDIS_URL`, `--redis-stream`, and **`--redis-group`**. Each machine gets a unique consumer name by default (`hostname:pid`).

```bash
export REDIS_URL='redis://your-elasticache.xxx.cache.amazonaws.com:6379/0'

python instagram_reels_transcripts.py kyle.musca \
  --redis-mode worker \
  --redis-url "$REDIS_URL" \
  --redis-stream insta:reel:jobs \
  --redis-group transcribers \
  --out /mnt/efs/kyle-insta-output \
  --resume \
  --proxy-downloads-only \
  --webshare-user "$WEBSHARE_PROXY_USERNAME" \
  --webshare-password "$WEBSHARE_PROXY_PASSWORD" \
  --hf-token "$HUGGINGFACE_TOKEN" \
  --model-size large-v3 \
  --verbose
```

Jobs are **`XACK`**ed after processing (including when `--resume` skips an already-finished item). If a worker dies **before** `XACK`, the message stays **pending**; use Redis **`XPENDING`** / **`XAUTOCLAIM`** (or clear the stream in dev) to reclaim—see [Redis streams intro](https://redis.io/docs/latest/develop/data-types/streams/).

**Smoke test (5 reel jobs):** use the **same** `--out` path on producer and workers (e.g. **EFS** mounted at the same location on every instance). Load env first if you use a `.env` file (`set -a && source .env && set +a`). Run **producer** once, then **worker** (or run both on one machine and the same `--out` for a quick check).

```bash
# Terminal A — producer (enqueue 5 reels; needs cookies / Instaloader)
python instagram_reels_transcripts.py "https://www.instagram.com/kyle.musca/reels/" \
  --redis-mode producer \
  -n 5 \
  --cookies-json ./cookies.json \
  --proxy-downloads-only \
  --resume \
  --out /mnt/efs/kyle-insta-output \
  --verbose
```

```bash
# Terminal B — worker (consume 5 jobs then exit; set REDIS_URL or --redis-url)
python instagram_reels_transcripts.py kyle.musca \
  --redis-mode worker \
  --redis-stream insta:reel:jobs \
  --redis-group transcribers \
  --redis-max-jobs 5 \
  --out /mnt/efs/kyle-insta-output \
  --resume \
  --proxy-downloads-only \
  --webshare-user "$WEBSHARE_PROXY_USERNAME" \
  --webshare-password "$WEBSHARE_PROXY_PASSWORD" \
  --hf-token "$HUGGINGFACE_TOKEN" \
  --model-size small \
  --verbose
```

Use **`--model-size small`** (or `base`) for a faster CPU sanity check; switch to **`large-v3`** for real quality. If you re-run the producer and use **`--redis-producer-dedupe`**, clear dev state when needed (`redis-cli` … `DEL insta:reel:jobs insta:reel:jobs:enqueued` or flush that stream key per your ops policy).

**Worker idle:** **`--redis-idle-notify-seconds 1800`** sends a **Simplepush** when no jobs arrive for ~30 minutes (requires **`--simplepush-key`** or **`SIMPLEPUSH_KEY`**). The worker **keeps running**; the notification repeats after each subsequent idle streak of the same length.

**Worker idle exit:** **`--redis-idle-exit-seconds 600`** exits after ~10 minutes with no jobs (handy with auto-scaling); a Simplepush **summary** is still sent if a key is configured. **`--redis-max-jobs 50`** processes a batch then exits.

**In-process queue mode:** omit `--redis-mode` or set **`REDIS_MODE=local`** (default): one machine does crawl + transcribe as before.

## EC2 Deployment Notes

These notes assume **64-bit Linux** on EC2 (e.g. **Ubuntu Server** or **Amazon Linux 2023**). The same `venv` + `pip install -r requirements.txt` flow as above applies; use **systemd**, **tmux**, or **screen** for long runs.

Two common deployment shapes:

- **CPU-only:** cheapest operationally; **`large-v3`** with `int8` is slow but fine for overnight batches if you scale **horizontally** (many workers + Redis) instead of buying one huge box.
- **GPU:** one **`g5.xlarge`** / **`g5.2xlarge`** (A10G) per worker usually gives a large speedup on Whisper versus CPU; costs more but fewer node-hours. Use an AMI with NVIDIA drivers (or install them per AWS documentation) before relying on **`--device cuda`**.

**Rough, cost-conscious picks (CPU `large-v3` + int8, no GPU)**

These are **“enough RAM + steady CPU”** targets—not the fastest single node, but reasonable for long jobs when you are **not** optimizing for minimum wall-clock:

| Use case | Instance type | Notes |
|----------|----------------|-------|
| **Producer only** (Instaload enqueue) | **`t3a.small`**–**`t3a.medium`** | Mostly network + light CPU; no Whisper. |
| **Worker** (Whisper + optional pyannote on CPU) | **`m7g.xlarge`** (4 vCPU, 16 GiB, Graviton) or **`m6i.xlarge`** (Intel) | ~16 GiB helps **`large-v3`** + overhead; Graviton is often better price/performance in **`us-east-1`**. |
| **Even cheaper / bursty** | **`t3a.2xlarge`** (8 vCPU, 32 GiB, burstable) | Large RAM headroom; **CPU credits** can throttle sustained `large-v3`—watch **`CPUCreditBalance`**. Prefer **m7g.xlarge** for steady full CPU without burst quirks. |
| **Faster CPU workers (still no GPU)** | **`c7g.2xlarge`** | More CPU than **m7g.xlarge**; same 16 GiB class depending on size—step up if transcription is CPU-bound and you want shorter wall time per video. |

If **`large-v3` OOMs**, move up to **32 GiB** (e.g. **`m7g.2xlarge`**) or use a smaller model (`small` / `medium`) for workers.

**GPU workers:** consider **`g5.xlarge`** (1×A10G, 24 GiB) as a balanced starting tier; use **`--device cuda`** and a **float16**-friendly **`--compute-type`** per faster-whisper docs.

Best practices:

- Install **Python 3** + **`ffmpeg`** from the distro (`apt`/`dnf`), then use a **venv** for this project—same layout as on macOS.
- Use env vars for secrets (`WEBSHARE_PROXY_*`, `SIMPLEPUSH_KEY`, `HUGGINGFACE_TOKEN`, `REDIS_URL`).
- Run under `tmux`/`screen`/systemd for long jobs.
- Keep outputs on **EBS** or **EFS** with enough space for videos + transcripts; open **security groups** only as needed (Redis often **6379** inside the VPC only).
- Use `--resume` on workers so restarts skip finished `mediaid`s.
- Put **Redis** on **ElastiCache for Redis** (same VPC as workers), **redis-server on the producer EC2** (see **Redis on the producer EC2** above), or a small **EC2** with Redis only for experiments.

Example single-node EC2 command (no Redis):

```bash
python instagram_reels_transcripts.py kyle.musca \
  --out /mnt/ebs/kyle-insta-output \
  --resume \
  --webshare-user "$WEBSHARE_PROXY_USERNAME" \
  --webshare-password "$WEBSHARE_PROXY_PASSWORD" \
  --hf-token "$HUGGINGFACE_TOKEN" \
  --verbose
```

## Notes

- `mediaid` is used for dedupe and output filenames.
- The script does not expose proxy credentials in logs.
- Instagram anti-automation behavior can change; tune delays/cooldowns as needed.

## Browser cookies (`cookies.json`)

You can authenticate with an **EditThisCookie-style** JSON export (array of objects with `domain`, `name`, `value`, `path`, etc.):

```bash
python instagram_reels_transcripts.py kyle.musca \
  --cookies-json ./cookies.json \
  --verbose \
  --dry-run -n 3
```

- **`--cookies-json`** cannot be combined with **`--sessionfile`** (pick one).
- You can set **`COOKIES_JSON`** in `.env` instead of the flag.
- The script calls Instaloader’s **`test_login()`** after loading cookies; if that fails, export fresh cookies while logged in, or set **`--user-agent`** to match your browser.
- Using **cookies + a different IP than the browser** (e.g. Webshare proxy) can trigger challenges. If you see 403 on `graphql/query` but `test_login` succeeded, run with **`--proxy-downloads-only`**: Instaloader uses your **direct** connection (same idea as the machine where you exported cookies), while **video file downloads** still use your Webshare proxy.
- If **`test_login` still passes** but listing returns **403** even **without** a crawl proxy, your cookie export may be missing **`csrftoken`**, or Instaloader’s **doc_id** POST is being blocked. The script syncs **`X-CSRFToken`** after import; also run **`pip install -U instaloader`** and set **`--user-agent`** to your real browser string.

**Security:** `cookies.json` is a **live session**. Do not commit it or share it. This repo’s `.gitignore` ignores `cookies.json`.

## Troubleshooting: `403 Forbidden` on `graphql/query` / "Profile does not exist"

Instagram often returns **403** for automated or datacenter-looking traffic. Instaloader may then report **Profile … does not exist** even when the URL opens fine in a browser — treat that as a **block**, not proof the handle is wrong.

What usually works:

1. **Session from a clean IP**  
   On a network that is not blocked, run Instaloader once to create a session, then point this script at it with `--sessionfile` (see [Instaloader login/session docs](https://instaloader.github.io/cli-options.html)).

2. **Residential proxy + same region as normal browsing**  
   If you must use Webshare, try a residential exit in a country you normally use; some exits still get 403.

3. **Optional in-script login**  
   Set `INSTAGRAM_LOGIN_USER` and `INSTAGRAM_PASSWORD` (or `--instagram-user` / `--instagram-password`), complete any checkpoint in the browser if Instagram requires it.

When using **`--sessionfile`**, set **`INSTALOADER_SESSION_USERNAME`** (or `--session-username`) to the Instagram account you logged in with (`instaloader -l`), **not** `kyle.musca`.

4. **Optional `--user-agent`**  
   Some environments benefit from matching a normal browser User-Agent string.

Use `--verbose` to confirm which proxy and session path are active.

## See also

- [`kyle-ad-library-video-transcripts`](../kyle-ad-library-video-transcripts/) — Meta Ad Library video scrape + Whisper (local or Redis).
