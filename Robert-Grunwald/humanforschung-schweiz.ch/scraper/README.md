# Human Research Switzerland — Contact Data Scraper

Automated scraper that collects contact data from all clinical trial study pages on
[humanforschung-schweiz.ch](https://www.humanforschung-schweiz.ch/en/trial-search/)
(filtered by Germany and Austria) and exports them to an Excel file.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| [Node.js](https://nodejs.org/) | ≥ 20 | Download the LTS version |
| npm | ≥ 10 | Comes with Node.js |
| Redis | Any recent | **Optional** — only needed for distributed multi-machine mode |

> **Check your Node version:** open a terminal and run `node --version`.
> If it shows `v20.x.x` or higher you are ready.

---

## Installation

```bash
# 1. Enter the scraper folder
cd scraper

# 2. Install dependencies  (~3 minutes, downloads a browser for Puppeteer)
npm install
```

That's it. No other setup is needed for a local single-machine run.

> Windows users: follow the dedicated setup guide in
> [`WINDOWS_SETUP.md`](WINDOWS_SETUP.md), from installing Node.js/npm to running
> the small test and full scrape.

---

## Quick Start — Single Machine (recommended for first run)

Run these two commands in order. Each can be left running unattended.

### Small Test Run — A Few Search Pages

Use this first when you only want to verify URL collection and detail scraping
without waiting for the full ~67k dataset. Each search API page contains about
10 study URLs, so `--pages 5` collects about 50 URLs.

```bash
# 1) Collect only the first 5 pages of study URLs
node gather-urls.js --pages 5 --output sample-urls.txt

# 2) Scrape details from that smaller URL list
node scrape.js --input sample-urls.txt --output sample-results.xlsx
```

- Sample URL list: `output/sample-urls.txt`
- Sample Excel file: `output/sample-results.xlsx`
- Increase or decrease `--pages` depending on how large a test you want.

### Full Production Run (No Redis, local in-memory queue)

If you want the final full dataset (~67k URLs) on one local machine, use this
flow. This is the recommended setup for clients because it does not require
Redis.

```bash
# 1) Collect all study URLs (Germany + Austria filters)
node gather-urls.js

# 2) Scrape all URLs using local in-memory queue
node scrape.js --input all-urls.txt --output results-final.xlsx
```

- `gather-urls.js` now reads from the website search API and collects all
  filtered URLs into `output/all-urls.txt`.
- `scrape.js` runs fully locally from that file (in-memory queue by default).
- Final Excel file: `output/results-final.xlsx`.

Optional: use proxies with safe fallback to direct/public IP if a proxy fails:

```bash
# Load rotating proxies from scraper/free_proxies.txt
node scrape.js --input all-urls.txt --output results-final.xlsx --proxy-file free_proxies.txt

# Or use a single proxy URL
node scrape.js --proxy-url "http://user:pass@host:port"
```

If the run is interrupted, resume with:

```bash
node gather-urls.js --resume
node scrape.js --input all-urls.txt --output results-final.xlsx --resume
```

### Step 1 — Collect all study URLs

```bash
node gather-urls.js
```

- Visits the search page, applies the Germany + Austria filter, then paginates
  through all ~7 000 pages and saves every study URL to `output/all-urls.txt`.
- **Expected time:** ~3–4 hours.
- Progress is printed every 50 pages and automatically saved. If your terminal
  closes you can resume (see below).

### Step 2 — Scrape contact data and export to Excel

```bash
node scrape.js
```

- Reads `output/all-urls.txt`, fetches each detail page in parallel using
  3 concurrent workers, parses all contact blocks, and writes the result to
  `output/results.xlsx`.
- **Expected time:** ~3.7 hours with default settings (3 workers, 500 ms delay).
  For a more conservative run use `--workers 3 --delay 1500` (~9 hours).
- Progress and estimated time remaining are printed every 100 URLs.

---

## Resuming an Interrupted Run

If the terminal closes or the machine restarts mid-run, both scripts support
`--resume` to continue from where they left off — no data is lost.

```bash
# Resume URL collection
node gather-urls.js --resume

# Resume scraping
node scrape.js --resume
```

---

## Retrying Failed URLs

After a full scrape run, any URLs that failed all 3 retry attempts are logged
to `output/failed-urls.txt`.

### Step 1 — Prepare the retry URL list

`failed-urls.txt` contains a URL and an error reason separated by a tab on each
line. Strip the error column before passing the file to `scrape.js`:

```bash
cut -f1 output/failed-urls.txt | grep -v '^$' > output/retry-urls.txt
```

### Step 2 — Re-scrape

Use a lower concurrency and longer delay to avoid re-triggering any rate limit
that caused the original failures:

```bash
node scrape.js \
  --input   retry-urls.txt \
  --output  results-retry.xlsx \
  --workers 3 \
  --delay   2000
```

### Step 3 — Merge back into the main file in original order

`merge-retry.js` reads both `results-final.xlsx` and `results-retry.xlsx`,
sorts every URL group by its original position in `all-urls.txt`, and writes
`results-merged.xlsx`:

```bash
node merge-retry.js
```

Optional flags (all paths are relative to `output/`):

```bash
node merge-retry.js \
  --final  results-final.xlsx \   # default
  --retry  results-retry.xlsx \   # default
  --out    results-merged.xlsx     # default
```

`results-merged.xlsx` is the final deliverable — it contains all rows from the
main run plus the retried rows inserted at their correct positions.

---

## Faster Runs — Tuning Workers and Delay

| Workers | Delay | Approx. RPS | Time for 67 k URLs |
|---|---|---|---|
| 3 (default) | 500 ms (default) | ~6 | ~3.1 h |
| 3 | 1500 ms | ~2 | ~9 h |
| 5 | 1500 ms | ~3.3 | ~5.5 h |
| 5 | 1000 ms | ~5 | ~3.7 h |
| 10 | 1000 ms | ~10 | ~1.9 h |

```bash
# Example: 5 workers, 1 second delay
node scrape.js --workers 5 --delay 1000
```

Increase workers only if the server responds quickly. If you see many failures,
reduce workers or increase delay.

---

## Advanced — Distributed Mode (Multiple Machines)

For the fastest possible run you can spread the scraping across several VMs
using Redis as a shared queue. Every VM picks URLs atomically — no URL is ever
processed twice.

### Requirements
- A Redis server reachable by all machines (e.g. Redis Cloud free tier, or
  a VPS running `redis-server`).
- `ioredis` installed: `npm install ioredis`

### Step 1 — Seed Redis with all URLs (run once, on any machine)

```bash
node gather-urls.js \
  --seed-redis \
  --redis-url redis://YOUR_REDIS_HOST:6379
```

This paginates the website and pushes every URL into Redis instead of a file.

### Step 2 — Start workers on each VM simultaneously

On **VM 1:**
```bash
node scrape.js \
  --queue     redis \
  --redis-url redis://YOUR_REDIS_HOST:6379 \
  --workers   5 \
  --output    output/results-vm1.xlsx
```

On **VM 2:**
```bash
node scrape.js \
  --queue     redis \
  --redis-url redis://YOUR_REDIS_HOST:6379 \
  --workers   5 \
  --output    output/results-vm2.xlsx
```

Repeat for as many VMs as you have. Each VM produces its own Excel file.
Merge them in Excel when all workers have finished.

---

## CLI Flags Reference

### `gather-urls.js`

| Flag | Default | Description |
|---|---|---|
| `--resume` | off | Continue from the last saved checkpoint |
| `--pages` | `0` | Limit URL collection to N search API pages (`0` means all pages) |
| `--output` | `all-urls.txt` | URL list filename written under `output/` |
| `--seed-redis` | off | Push collected URLs into Redis instead of writing to file |
| `--redis-url` | `redis://127.0.0.1:6379` | Redis connection string (used with `--seed-redis`) |
| `--redis-key` | `humres:urls` | Redis list key name |

### `scrape.js`

| Flag | Default | Description |
|---|---|---|
| `--input` | `output/all-urls.txt` | Path to URL list file (relative to `output/` or absolute) |
| `--output` | `output/results.xlsx` | Output Excel filename (placed in `output/`) |
| `--workers` | `3` | Number of concurrent HTTP workers |
| `--delay` | `500` | Milliseconds to wait between requests **per worker** |
| `--queue` | `memory` | Queue backend: `memory` or `redis` |
| `--redis-url` | `redis://127.0.0.1:6379` | Redis connection string (when `--queue redis`) |
| `--redis-key` | `humres:urls` | Redis list key name |
| `--resume` | off | Skip already-processed URLs and append to existing Excel |

---

## Output Files

All files are written to the `output/` folder.

| File | Created by | Description |
|---|---|---|
| `all-urls.txt` | `gather-urls.js` | ~67 k study page URLs, one per line |
| `results.xlsx` | `scrape.js` | Final Excel file with all contact data |
| `failed-urls.txt` | `scrape.js` | URLs that failed all 3 retries; re-run against this file |
| `gather-progress.json` | `gather-urls.js` | Checkpoint for `--resume` (do not edit) |
| `scrape-progress.json` | `scrape.js` | Checkpoint for `--resume` (do not edit) |

### Excel columns

| # | Column | Description |
|---|---|---|
| 1 | Study ID | All identifiers shown at the top of the study page, separated by ` \| ` |
| 2 | Study Title | Main study title as shown on the detail page |
| 3 | Study URL | Direct link to the study detail page |
| 4 | Contact Block Title | Heading of the contact block (e.g. *Contact Person Switzerland*) |
| 5 | Raw Contact Text | Full visible text of the contact block before field splitting |
| 6 | Contact First Name | Given name (personal contacts only; blank for organisations) |
| 7 | Contact Last Name | Surname, including multi-part surnames (e.g. *Le Rhun*) |
| 8 | Contact Email Address | Email exactly as displayed |
| 9 | Contact Phone Number | Phone exactly as displayed (stored as text) |
| 10 | Institution Name | Organisation / hospital / department name |
| 11 | Displayed Source Tag | Source marker shown on the page, e.g. `(BASEC)` or `(ICTRP)` |

---

## Troubleshooting

**Browser fails to launch (`Could not find Chrome`)**

Run the following to download the browser that Puppeteer needs:
```bash
npx puppeteer browsers install chrome
```

**Many URLs are failing**

The server may be rate-limiting requests. Try reducing concurrency:
```bash
node scrape.js --workers 2 --delay 2000
```

After the run finishes, retry the failures:
```bash
node scrape.js --input output/failed-urls.txt --output output/results-retry.xlsx
```

**Excel file is very large / slow to open**

A full run produces ~150 000–200 000 rows, which is normal. Excel handles this
best when you use **filters** (Data → Filter) rather than scrolling. If Excel
struggles, import the file into Google Sheets instead.

**gather-urls.js stops too early**

The script stops when 3 consecutive pages return no new URLs, which means it
has reached the end of the search results. If you believe there are more pages,
check the website directly for the total result count and compare it with the
number of lines in `output/all-urls.txt`.

**Redis connection refused**

Make sure your Redis server is running and the `--redis-url` flag points to the
correct host and port. Test the connection with:
```bash
redis-cli -u redis://YOUR_REDIS_HOST:6379 ping
# should respond: PONG
```
