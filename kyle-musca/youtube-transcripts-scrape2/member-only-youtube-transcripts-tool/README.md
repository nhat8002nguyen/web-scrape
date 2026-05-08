# Member-only YouTube transcripts (Node)

CLI that lists a channel’s **Videos** tab with `yt-dlp` (same approach as [`download_channel_transcripts.py`](../../youtube-transcripts-scrape/download_channel_transcripts.py)), then drives a **Chrome user profile** that has your transcript extension installed to save one `.txt` file per video.

The **channel URL you pass on the command line is not opened in Chrome**. `yt-dlp` uses it only to discover video IDs; the browser navigates to each **`https://www.youtube.com/watch?v=…`** link in turn.

Spec: [`../member-only-youtube-transcripts-tool.md`](../member-only-youtube-transcripts-tool.md).

## Requirements

- **Node.js** 18+
- **`yt-dlp`** on your `PATH`
- **Google Chrome** installed on the machine (`puppeteer-core` does not bundle Chromium)
- A Chrome **user data root** when the **script launches Chrome** (`--user-data-dir`): the folder that **contains** `Default`, `Profile 1`, etc. **Quit Chrome completely** (e.g. macOS **Cmd+Q**) before each launch — only one Chrome process may use that directory. If a run fails mid-launch, quit stray **Google Chrome** in Activity Monitor if needed. With **`--connect`**, you start Chrome yourself; the CLI does not need `--user-data-dir`.

## Install

```bash
cd member-only-youtube-transcripts-tool
npm install
```

## Usage

```bash
# Dry run on a few videos (then remove -n for the full channel)
node src/cli.mjs "https://www.youtube.com/@ChannelName" \
  --user-data-dir "/path/to/Chrome/User Data" \
  --profile-directory "Profile 1" \
  --chrome-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  -n 3 \
  --headed
```

Use **`-n N`**, **`--limit N`**, or **`--first N`** to process only the first *N* uploads (order is whatever `yt-dlp` returns). Omit them to run the full channel list.

### Attach to your own Chrome (`--connect`)

If launching Chrome from the script fails (profile lock, CDP timeouts), start **one** Chrome instance yourself with the [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) listening, then run the CLI with **`--connect`**. The script uses `puppeteer.connect` — it does **not** quit your browser when it finishes (only the automation disconnects).

#### Chrome 136+ and `--user-data-dir` (why your command failed)

Chrome **blocks** `--remote-debugging-port` when `--user-data-dir` is the **default install location** (macOS: `~/Library/Application Support/Google/Chrome`; similar rules on other OS). You will see:

`DevTools remote debugging requires a non-default data directory.`

Using **`--profile-directory=Profile 2`** (or any profile **inside** that folder) **does not** fix it — the path Chrome checks is the **parent** user-data root, not the profile name.

See: [Changes to remote debugging switches (Chrome Developers)](https://developer.chrome.com/blog/remote-debugging-port).

#### Working setup: a **copy** of your profile under a **new** path

You need a user-data directory whose path is **not** the default one. The usual approach is to **duplicate** your Chrome data while Chrome is **fully quit** (macOS **Cmd+Q**), then launch against the copy:

```bash
# 1) Quit Chrome completely (Dock → Quit, or Cmd+Q). Confirm in Activity Monitor if unsure.

# 2) One-time (or whenever you want to refresh logins/extensions from your main profile):
rm -rf "$HOME/Chrome-for-remote-debug"
cp -R "$HOME/Library/Application Support/Google/Chrome" "$HOME/Chrome-for-remote-debug"
```

Then start Chrome **only from the terminal** for automation (replace `Profile 2` with the folder name from **chrome://version** → Profile path):

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Chrome-for-remote-debug" \
  --profile-directory="Profile 2"
```

- **Do not** point both normal browsing and this command at the **same** directory at the same time. Keep daily browsing on the original path, or quit the regular browser and use only the copy for the scrape session.
- The copy **diverges** from your main profile (bookmarks, cookies, etc.). Re-run the `rm -rf` + `cp -R` when you need it to match your main Chrome again.

#### If you see `Opening in existing browser session`

Another Chrome process is already using that **`--user-data-dir`**. Quit **all** Chrome windows for that profile (or pick a copy path nothing else is using).

#### Console noise (`GoogleUpdater`, `DEPRECATED_ENDPOINT`, TensorFlow)

Those lines are **normal** on many installs; they are not the cause of the remote-debugging block.

#### Then run the CLI

1. In that window, sign in if needed and keep the extension available (on first use of a **copy**, you may need to sign in again or reload the extension).
2. Run:

   ```bash
   node src/cli.mjs "https://www.youtube.com/@ChannelName" \
     --connect \
     -n 3
   ```

   Optional: **`--browser-url http://127.0.0.1:9223`** if you use a port other than 9222.

Only processes on your machine can reach that port by default; do not expose it on a network you do not trust.

Full channel with Simplepush (script launches Chrome — `--user-data-dir` required):

```bash
node src/cli.mjs "https://www.youtube.com/@ChannelName" \
  --user-data-dir "/path/to/Chrome/User Data" \
  --profile-directory "Profile 1" \
  --chrome-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --simplepush-key "YOUR_KEY"
```

| Option | Description |
|--------|-------------|
| `channel` | Positional: channel or profile URL |
| `--out`, `-o` | Output directory (default: `transcripts`) |
| `--user-data-dir` | Chrome user data **root** — **required** unless you use **`--connect`** |
| `--profile-directory`, `--profile` | Which profile to use: `Default`, `Profile 1`, … (from **chrome://version** → Profile path) |
| `--chrome-path` | Chrome binary (default: common path per OS) |
| `--simplepush-key` | Simplepush key; notification when 5 videos fail in a row |
| `--headed`, `--no-headless` | Always use a visible Chrome window (no headless) |
| `--headless` | Headless first; on failure, reopen headed and retry (same as default) |
| `--headless-only` | Headless only; no headed fallback |
| `--delay` | Seconds after each successful save (default: `5`) |
| `-n`, `--limit`, `--first` | Only process the first N videos (good for testing) |
| `--resume` | Skip when the output `.txt` already exists |
| `--verbose`, `-V` | Log each watch URL and navigation step to stderr |
| `--connect` | Attach to an existing Chrome with `--remote-debugging-port` (no launch; see above) |
| `--browser-url` | DevTools browser URL (default: `http://127.0.0.1:9222`); implies `--connect` |

Output file names match the Python script: `{sanitized_title}__{video_id}.txt`.

Skips are appended to `skipped.jsonl` in the output directory.

## Chrome user data vs profile

- **`--user-data-dir`**: parent directory of the profile folders. On macOS that is usually  
  `~/Library/Application Support/Google/Chrome`. On Windows it is often  
  `...\Google\Chrome\User Data`.
- **`--profile-directory`**: the **folder name only** (`Default`, `Profile 1`, `Profile 2`, …). Open Chrome in that profile → **chrome://version** → **Profile path** ends with that name.

If you omit `--profile-directory`, Chrome picks its default (often the last-used profile in that user data dir).

- **Many restored tabs / wrong tab focused:** Each video uses a dedicated automation tab, **`bringToFront`**, then navigates to `youtube.com/watch?v=…`. Extensions often need the **active** tab.

- **Stuck on `about:blank`:** Prefer **`--connect`** and a Chrome you started yourself, or ensure the CLI’s launched Chrome uses a fresh tab (you should see `Loading watch page: https://www.youtube.com/watch?v=…`); use `--verbose` for more detail.

## Headless vs headed

- **`--connect`:** Ignores headless / headed flags — you are using whatever Chrome window you started.
- **Default / `--headless`:** Chrome starts in **headless** mode; if the extension flow fails, the tool **reopens in headed mode** and retries, then keeps using headed for the rest of the run.
- **`--headed` or `--no-headless`:** Only a **visible** window — useful when you know extensions need a real browser UI.
- **`--headless-only`:** **No** headed fallback (can fail if the extension does not run headless).
