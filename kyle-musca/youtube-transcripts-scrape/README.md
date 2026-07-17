# Bulk YouTube channel transcripts

Downloads **YouTube-hosted captions** (manual or auto-generated) for **every upload** listed on a channel’s uploads tab. Video discovery uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) so large channels paginate correctly (RSS alone only covers recent items). Transcripts use [youtube-transcript-api](https://pypi.org/project/youtube-transcript-api/), which reads the same caption tracks the site exposes—**no paid API keys**. Captions are the primary path; for videos logged in `skipped.jsonl` with no captions (`transcripts_disabled` / `no_matching_transcript`), an optional **Whisper** CLI can download audio and transcribe locally (see **Usage §4**).

**macOS desktop app:** build a standalone `.app` so clients do not install Python — see [DESKTOP_APP.md](DESKTOP_APP.md).

## Requirements

- Python **3.9+** recommended (developed against 3.11).
- Network access while the script runs.

## Setup

```bash
cd kyle-musca
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a **`.env`** in the **project folder** (next to `download_channel_transcripts.py`) or the **current working directory**. Both are loaded (cwd overrides if both exist). Examples: `SIMPLEPUSH_KEY=…`, `56F6LP=…`, `TRANSCRIPT_PROXY=http://user:pass@p.webshare.io:80/` (same URL Webshare uses for both HTTP and HTTPS transcript requests), `WEBSHARE_PROXY_USERNAME=…`, `WEBSHARE_PROXY_PASSWORD=…`.

## Usage

Provide a channel profile URL (`@handle`, `/channel/UC…`, `/c/…`). The script turns it into the uploads tab (`/videos`) internally when needed:

```bash
python3 download_channel_transcripts.py "https://www.youtube.com/@YourChannelHandle"
python3 download_channel_transcripts.py --channel "https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxxxxxx" --out ./transcripts
```

### Example commands clients can copy (use placeholders only)

Replace `YOUR_WEBSHARE_PROXY_USERNAME` and `YOUR_WEBSHARE_PROXY_PASSWORD` with the **Proxy username** and **Proxy password** from [Webshare proxy settings](https://dashboard.webshare.io/proxy/settings) (Residential rotating). Do **not** paste real passwords into READMEs, tickets, or git.

**1. Full channel — Webshare credentials on the command line**

```bash
python3 download_channel_transcripts.py \
  "https://www.youtube.com/@YourChannelHandle" \
  --out ./out \
  --webshare-user 'YOUR_WEBSHARE_PROXY_USERNAME' \
  --webshare-password 'YOUR_WEBSHARE_PROXY_PASSWORD'
```

Tip: add `--resume` after an interrupted run so existing `.txt` files in `./out` are skipped.

**2. Full channel — Webshare via environment variables** (better than putting passwords in shell history):

```bash
export WEBSHARE_PROXY_USERNAME='YOUR_WEBSHARE_PROXY_USERNAME'
export WEBSHARE_PROXY_PASSWORD='YOUR_WEBSHARE_PROXY_PASSWORD'
python3 download_channel_transcripts.py "https://www.youtube.com/@YourChannelHandle" --out ./out
```

**3. Retry only IDs listed in a skip log** (no channel URL). Writes new transcripts under `--out`; pair with **`--resume`** if some downloads already succeeded and you wish to skip those files.

```bash
python3 download_channel_transcripts.py \
  --retry-from-skip-log ./out/skipped.jsonl \
  --out ./out-skipped \
  --resume \
  --webshare-user 'YOUR_WEBSHARE_PROXY_USERNAME' \
  --webshare-password 'YOUR_WEBSHARE_PROXY_PASSWORD'
```

Adjust paths (`./out/skipped.jsonl`, `./out-skipped`) to match where you store `skipped.jsonl` and where you want new `.txt` files.

**4. Retry skipped videos with Whisper (local speech-to-text)** — for rows where YouTube has no captions (`transcripts_disabled` / `no_matching_transcript`), even if the video has speech:

Requires **`ffmpeg`** on PATH and a one-time Hugging Face download of Whisper `large-v3` (~2.5–4 GB).

```bash
# macOS
brew install ffmpeg

pip install -r requirements.txt

python3 whisper_skipped_transcripts.py \
  --skip-log ./transcripts/hattieboydle7662/skipped.jsonl \
  --out ./transcripts/hattieboydle7662 \
  --download-dir videos \
  --cookies-from-browser chrome \
  --resume \
  --verbose
```

Requires **Node.js** on PATH (yt-dlp JS challenge solving) and browser cookies when YouTube returns a bot/sign-in challenge.
- Default reason filter: `transcripts_disabled`, `no_matching_transcript`.
- Use `--all-reasons` to include proxy/IP skip rows (prefer API `--retry-from-skip-log` for those first).
- Use `--dry-run` to preview selected IDs.
- Failures append to `whisper_failed.jsonl` inside `--out`.
- Output `.txt` names match the caption scraper so consolidate still works.

### Useful flags

| Flag | Meaning |
|------|---------|
| `--out`, `-o` | Output folder for `.txt` files (default: `./transcripts`). |
| `--delay` | Seconds to sleep **after each successful download** (default `5`; increase if YouTube still limits you). |
| `--max-retries` | Number of **additional** tries after the first transcript request on transient failures (default `3` ⇒ up to four attempts total). Retries apply to block/rate‑style errors, not missing captions. |
| `--ip-ban-retries` | If **IpBlocked / RequestBlocked** still appears after those attempts, retry the **whole** transcript fetch for that video up to **N** more times with longer waits between rounds (default `3`). Use `0` to disable these extra IP‑ban waves (only `--max-retries` applies). |
| `--resume` | Skip IDs whose output `.txt` already exists. |
| `--retry-from-skip-log` | Path to `skipped.jsonl` (same JSONL shape): retry only those **`video_id`** lines. **Do not** pass a channel URL. Uses each line’s **`title`** for output filenames; combine with **`--resume`** if some IDs already have `.txt` in **`--out`**. |
| `--lang` | Preferred language codes in priority order (default `en`). Example: `--lang en en-US`. |
| `--strict-lang` | Require a track matching `--lang`; do **not** fall back to other languages. |
| `--format` | `lines` (one caption segment per line) or `paragraph` (space‑joined). |
| `--skip-log` | JSONL inside `--out` for skips/fails (default `skipped.jsonl`). |
| `--proxy` | Single HTTP(S) proxy URL for transcripts (e.g. `http://user:pass@p.webshare.io:80/`). **Ignored** if `--proxy-file` or Webshare rotating is used. If omitted, **`TRANSCRIPT_PROXY`** in `.env` is used (overridden by `--proxy`). |
| `--proxy-file` | File of proxies (one per line): `host:port:user:pass` (**datacenter** lists) or `http://user:pass@host:port`. **Round-robin** per video. Not for Webshare **Residential** rotating — use `--webshare-user` / `--webshare-password` instead. |
| `--webshare-user`, `--webshare-password` | Webshare **rotating residential** (see [dashboard proxy settings](https://dashboard.webshare.io/proxy/settings)). Or `WEBSHARE_PROXY_USERNAME` / `WEBSHARE_PROXY_PASSWORD` in `.env`. **Mutually exclusive** with **`--proxy`** and **`--proxy-file`** (not with `TRANSCRIPT_PROXY` alone — that env var is ignored with a warning when Webshare mode is on). |
| `--webshare-locations` | Optional comma-separated country codes (e.g. `US,DE`) to **restrict** the pool. **Leave unset** (default) to use **all** locations Webshare offers for your plan. |
| `--webshare-retries-when-blocked` | Retries on 429 in Webshare mode (default `10`). |
| `--limit`, `-n` | Process at most **N** videos from the enumerated list (default: all). Useful for dry runs or partial exports. |
| `--xlsx` | Excel workbook path (default: `transcripts.xlsx` in `--out`). Columns: real title, sanitized filename, video ID, watch URL, transcript. |
| `--no-xlsx` | Skip writing the `.xlsx` file (only `.txt` + logs). |
| `--simplepush-key` | [Simplepush](https://simplepush.io/) key (`SIMPLEPUSH_KEY` / `56F6LP` in `.env`). Notifies on **IP-ban stop** and when the run **finishes all videos** in the list (not stopped early by a ban). |
| `--simplepush-title` | Simplepush title (default: `YouTube transcripts`). |
| `--simplepush-event` | Optional Simplepush **event** id — must match an event in your app; leave unset for default delivery. A wrong id causes failed sends. |
| `--test-simplepush` | Send **one test** notification and exit (verifies `.env` and Simplepush). |
| `--continue-on-ip-ban` | Do **not** terminate on `IpBlocked`/`RequestBlocked`; continue like older versions (default is **stop immediately** after an IP ban). |

### Webshare rotating residential (recommended vs IP blocks)

[youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) ships with **`WebshareProxyConfig`**: one rotating endpoint (`p.webshare.io`) and your dashboard **Proxy Username** / **Proxy Password**. You need Webshare’s **Residential** product — not the static datacenter IP list format used in `Webshare-10-proxies.txt`.

Example (same placeholders as in **Usage** above):

```bash
export WEBSHARE_PROXY_USERNAME='YOUR_WEBSHARE_PROXY_USERNAME'
export WEBSHARE_PROXY_PASSWORD='YOUR_WEBSHARE_PROXY_PASSWORD'
python3 download_channel_transcripts.py "https://www.youtube.com/@YourChannelHandle" --out ./transcripts
```

Or in `.env` next to the script, same variable names. Omit `--webshare-locations` to use all countries, or e.g. `--webshare-locations US,GB` to restrict.

## Running on EC2

Upload the project from your Mac (skips local `.venv`, build output, transcripts, and `.env`). Run from the `youtube-transcripts-scrape/` folder. The `-e` flag must be **`ssh -i KEY.pem`**, not the `.pem path alone.

```bash
chmod 400 ./video-transcripts-server.pem

rsync -avz --progress \
  -e "ssh -i ./video-transcripts-server.pem -o IdentitiesOnly=yes" \
  --exclude '.venv/' --exclude '.venv-desktop-build/' \
  --exclude 'build/' --exclude 'dist/' \
  --exclude '__pycache__/' --exclude 'transcripts/' --exclude '.env' \
  --exclude '*.pem' \
  ./ ubuntu@ec2-54-255-143-205.ap-southeast-1.compute.amazonaws.com:~/youtube-transcripts-scrape/
```

Or use `./scripts/ec2_upload.sh ubuntu@your-ec2-host` (same excludes; auto-detects the `.pem`).

Copy `.env` separately, then on the instance (`.venv` is created on the server):

```bash
scp -i ./video-transcripts-server.pem .env ubuntu@ec2-54-255-143-205.ap-southeast-1.compute.amazonaws.com:~/youtube-transcripts-scrape/.env

ssh -i ./video-transcripts-server.pem ubuntu@ec2-54-255-143-205.ap-southeast-1.compute.amazonaws.com
cd ~/youtube-transcripts-scrape
./scripts/ec2_setup_and_run.sh run --detach -- \
  "https://www.youtube.com/@YourChannelHandle" --out ./transcripts --resume
```

Attach to a detached run: `tmux attach -t youtube-transcripts`

## Output files

- One UTF‑8 `.txt` per video, named **`{sanitized_title}__{VIDEO_ID}.txt`** so collisions are avoided.
- **`transcripts.xlsx`** in the same output folder (unless `--no-xlsx` or a custom `--xlsx` path): one **row per video** in this run, with columns **Real title** (exact YouTube title), **Filename** (sanitized `.txt` name), **Video ID**, **Video URL** (`https://www.youtube.com/watch?v=…`), **Transcript** (empty when no transcript was saved). The workbook is written at the end of the run using a memory‑efficient streaming writer.
- Very long transcripts may be **truncated in the spreadsheet** to fit Excel’s per‑cell limit (32,767 characters); the matching `.txt` file always has the full text.
- `skipped.jsonl` appends JSON lines `{ "video_id", "title", "reason", … }` for captures with no captions, disabled transcripts, removals, etc., and hard errors during fetch. The same **`video_id` is only written once** per file (existing lines are loaded at startup so re-runs do not duplicate IDs).

Final stdout summary includes downloads this run, resume skips, soft skips (no captions / unavailable), and failures.

## Caveats & troubleshooting

- **No captions**: Some videos genuinely have transcripts disabled—those are counted as skips and logged.
- **IpBlocked / RequestBlocked**: YouTube sometimes blocks the **transcript** HTTP endpoint for your IP (bulk runs, datacenter/VPN IPs, or rate limits). **Channel listing still works** because it uses yt-dlp, which is separate from `youtube-transcript-api`. If every video fails with `IpBlocked` in `skipped.jsonl`, try: waiting and increasing `--delay`, switching networks, or passing **`--proxy`** with a **residential** HTTP(S) proxy URL (see [youtube-transcript-api: IP bans](https://github.com/jdepoix/youtube-transcript-api?tab=readme-ov-file#working-around-ip-bans-requestblocked-or-ipblocked-exception)). Browser cookie auth in the library is currently unreliable per upstream.
- **Throttling**: If requests start failing (`RequestBlocked`, `IpBlocked`), raise `--delay`, pause, rerun with `--resume`, or retry later off the same IP/VPN exit.
- **Proxy / network errors** (`ProxyError`, `Max retries exceeded`, `RemoteDisconnected` in `skipped.jsonl` as **`proxy_or_network_error`**): the script retries these like other transient HTTP failures. Persistent failures usually mean the proxy URL or product type is wrong. On Webshare, dashboard **`client_connect_invalid_params`** often means the connect string does not match the plan (e.g. **Residential** rotating uses dashboard *Proxy Username* + *Proxy Password* with **`WebshareProxyConfig`** / `--webshare-user`, not a static `user-GB-1:pass@p.webshare.io` line from a datacenter export), HTTP vs SOCKS mismatch, or a bad username/password/format.
- **Proxy lists**: Keep credential files **out of git**; add patterns like `Webshare*.txt` or `*proxies*.txt` to `.gitignore` if you store lists locally.

- Captions reflect what YouTube offers (manual, auto‑generated, or translations when selected); `--strict-lang` controls how far alternatives are explored.
