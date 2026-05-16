# Mentorship transcripts (Node)

CLI that connects to **Google Chrome** with [`puppeteer-core`](https://pptr.dev/), opens the Business Mentorship hub, discovers each course and lesson, plays the VdoCipher player, and saves transcripts.

## Requirements

- **Node.js** 18+
- **Google Chrome** installed (`puppeteer-core` does not bundle Chromium)
- A Chrome session logged in to [content.jamessmith.business](https://content.jamessmith.business) (member access)

## Install

```bash
cd mentorship-transcripts-tool
npm install
```

## Usage — attach to your Chrome (`--connect`)

Start Chrome with [remote debugging](https://developer.chrome.com/blog/remote-debugging-port) on a **non-default user-data directory** (Chrome 136+ blocks the default profile path). See the [member-only YouTube transcripts README](../../youtube-transcripts-scrape2/member-only-youtube-transcripts-tool/README.md) for copying your profile and launch examples.

Then:

```bash
node src/cli.mjs --connect -n 2 --verbose
```

Optional start URL (defaults to `https://content.jamessmith.business/mentorship`):

```bash
node src/cli.mjs "https://content.jamessmith.business/mentorship" --connect
```

Optional DevTools URL:

```bash
node src/cli.mjs --connect --browser-url http://127.0.0.1:9223
```

## Usage — launch Chrome from the script

Quit other Chrome instances using the same `--user-data-dir`, then:

```bash
node src/cli.mjs \
  --user-data-dir "/path/to/Chrome/User Data" \
  --profile-directory "Profile 1" \
  --chrome-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  -n 3
```

| Option | Description |
|--------|-------------|
| `url` | Optional first positional: hub URL (default: mentorship URL above) |
| `-o`, `--out` | Output directory (default: `transcripts`) |
| `--user-data-dir` | Chrome user data **root** — **required** unless `--connect` |
| `--profile-directory`, `--profile` | Profile folder: `Default`, `Profile 1`, … |
| `--chrome-path` | Chrome binary (default: common path per OS) |
| `--headed`, `--no-headless` | Visible window when **launching** (default) |
| `--headless` | Headless when **launching** |
| `--delay` | Seconds after each successful lesson (default: `2`) |
| `-n`, `--limit`, `--first` | Process at most **N** lessons (after `--start-at`) |
| `--start-at`, `--from` | Begin at the Nth lesson in the discovered list (1-based) |
| `--resume` | Skip when `*__[lessonId].txt` exists under `-o` (root or category subfolder) |
| `--navigation-timeout` | ms (default: `120000`) |
| `--scrape-timeout` | Max ms to wait for the VdoCipher iframe before starting playback (default: `120000`) |
| `--transcript-after-play-ms` | Max ms **after playback starts** to obtain transcript (lyrics poll, then VTT with any time left; default: `10000`) |
| `--simplepush-key` | [Simplepush](https://simplepush.io/) key: push when **3** lessons fail in a row |
| `--lesson-cache` | Path to lesson list JSON (default: `OUT_DIR/lesson-queue.json`) |
| `--refresh-lesson-list` | Re-scan the site and overwrite the lesson cache |
| `--verbose`, `-V` | Log steps to stderr |
| `--connect` | Attach to existing Chrome with `--remote-debugging-port` |
| `--browser-url` | DevTools browser URL (default: `http://127.0.0.1:9222`); implies `--connect` |

## Outputs

Inside `-o`:

- **Per lesson:** `{hub course name}/{sanitized title}__{lessonId}.txt` (eight course folders, same names as on the mentorship hub)
- **`lead-magnet-mastery-transcripts.txt`** (root) — rollup for **Lead Magnet Mastery** only
- **`content-transcripts.txt`** (root) — rollup for **all** hub courses (including Lead Magnet Mastery blocks)
- **`skipped.jsonl`** — failures (URL, lesson id, error). After transcripts exist on disk, prune stale rows with `node src/pruneSkippedJsonl.mjs transcripts` (optional `--dry-run`).

To move older flat files into course folders, run:

```bash
node src/migrateLessonsToCategoryDirs.mjs transcripts
```

Transcripts are taken from the VdoCipher iframe `.Lyrics-Prompter p[data-cue-id]` when possible, otherwise from the **WebVTT** URL in the player metadata.

## License

Use only in compliance with the site’s terms and your membership.
