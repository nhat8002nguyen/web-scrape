# Appium + Python — Android emulator learning project

Demo project for mobile UI automation: scroll a contact list on an Android emulator, extract fields, and export CSV/Excel. Patterns map to larger jobs (login, long lists, checkpoints).

## Architecture

```
Python scraper  --HTTP-->  Appium server  --adb-->  Emulator  -->  App UI
```

Python can run locally or remotely; Appium and the emulator must share a host where `adb devices` shows the device.

## Prerequisites (macOS, one-time)

### 1. Core tooling

- [Android Studio](https://developer.android.com/studio) with SDK Platform (API 33–34), Build-Tools, Platform-Tools, Emulator
- Java JDK 17+
- **Node.js 20.19+** (or 22.12+) — required for Appium 3; see [Appium install troubleshooting](#appium-install-troubleshooting) if `appium` crashes after install
- Python 3.10+

Add to `~/.zshrc`:

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator"
```

### 2. Android emulator

1. Android Studio → Device Manager → Create Device (e.g. Pixel 6, API 34, Google APIs) if you need a new AVD.
2. This Mac already has **`Medium_Phone_API_36.0`**. Start it:

```bash
./scripts/start_emulator.sh
```

3. Verify: `adb devices` → `emulator-5554 device`.

### 3. Appium + UiAutomator2

**Check Node first:**

```bash
node -v   # must be v20.19.0+ or v22.12.0+ for Appium 3
```

**Option A — Appium 3 (recommended if Node is new enough):**

```bash
# Avoid sudo; use nvm or brew node if possible
npm install -g appium@latest
appium driver install uiautomator2
appium driver list
```

**Option B — Appium 2 (if Node is older, e.g. v20.11):**

```bash
npm uninstall -g appium
npm install -g appium@2
appium driver install uiautomator2
appium --version
```

Start the server (default `http://127.0.0.1:4723`):

```bash
appium
```

Optional: [Appium Inspector](https://github.com/appium/appium-inspector) to find `resource-id` and text locators.

### Appium install troubleshooting

| Symptom | Cause | Fix |
|---------|--------|-----|
| `EBADENGINE` + Node `v20.11.x` | Appium 3 needs Node **≥ 20.19** | Upgrade Node (below) **or** use Option B (`appium@2`) |
| `ERR_REQUIRE_ESM` when running `appium` | Broken/incompatible global install (often Node too old for Appium 3) | `npm uninstall -g appium`, upgrade Node, reinstall; or pin `appium@2` |
| Permission errors with `sudo npm` | Mixed root/user global modules | Prefer `npm install -g` **without** sudo after fixing Node via nvm/Homebrew |

**Upgrade Node on macOS (pick one):**

```bash
# Homebrew
brew install node

# If brew says node is "shadowed" or link failed, prefer Homebrew's bin first:
export PATH="/usr/local/opt/node/bin:$PATH"
node -v   # should be v20.19+ (e.g. v26.x)

# Permanent fix — add to ~/.zshrc:
# export PATH="/usr/local/opt/node/bin:$PATH"

# If you want brew link to replace old /usr/local/bin/node (may need sudo):
# sudo chown -R "$(whoami):admin" /usr/local/include/node /usr/local/bin/node
# brew link --overwrite node

# Or nvm (if installed)
nvm install 22
nvm use 22
node -v
```

Then reinstall Appium:

```bash
npm uninstall -g appium
npm install -g appium@latest
appium driver install uiautomator2
appium
```

## Project setup

```bash
cd test-appium
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
mkdir -p output
```

## Daily runbook

**Terminal 1** — emulator (if not already running):

```bash
./scripts/start_emulator.sh
```

**Terminal 2** — Appium:

```bash
appium
```

**Terminal 3** — scrape:

```bash
source .venv/bin/activate
python scripts/clear_seeded_contacts.py   # remove demo contacts before reseed
python scripts/seed_contacts.py --count 50    # optional demo data
python scripts/run_demo_scrape.py --max-rows 100 --out output/contacts.csv
```

Excel export:

```bash
python scripts/run_demo_scrape.py --max-rows 100 --out output/contacts.csv --excel output/contacts.xlsx
```

## Remote Appium

Point Python at a remote server (emulator + Appium on that host):

```bash
# .env
APPIUM_URL=http://your-server-ip:4723
```

Do not expose port 4723 to the public internet without authentication/VPN.

## Switching to a real app

1. Install APK: `adb install app.apk`
2. Open the app, then find focus:
   ```bash
   adb shell dumpsys window | grep -E 'mCurrentFocus'
   ```
3. Update `config/capabilities.android.json` (`appPackage`, `appActivity`) or `.env` overrides.
4. Use Appium Inspector to record login fields and list row selectors.
5. Implement `src/scrapers/login.py` (stub provided) and adjust locators in `contacts_demo.py` or a new scraper module.
6. Prefer `resource-id` > accessibility id > text; avoid long XPath chains.

Package/activity names vary by Android version. If Contacts does not launch, fix caps using Inspector.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Could not find a connected Android device` | Start emulator; run `adb devices` |
| Session not created / wrong activity | Update `appPackage` / `appActivity` in capabilities |
| Empty scrape | Run `seed_contacts.py --count 50`; on first launch tap **No thanks** / **Dismiss** on sync prompts (scraper tries this automatically) |
| Only a few rows | Reset checkpoint: `python scripts/run_demo_scrape.py --reset-checkpoint` |
| Stale element | Increase waits; reduce scroll speed via `SCROLL_PAUSE_SEC` |

## Legal note

Only automate apps you are authorized to access. This demo uses the system Contacts app for learning.
