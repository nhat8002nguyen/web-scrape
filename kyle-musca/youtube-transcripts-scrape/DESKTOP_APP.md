# macOS desktop app (no Python install for end users)

The **YouTube Transcripts** app wraps the same logic as `download_channel_transcripts.py`: you paste a channel URL, Webshare **residential rotating** username and password, pick an output folder, and run. Transcripts land as `.txt` files plus `transcripts.xlsx` and `skipped.jsonl` in that folder (see the main [README.md](README.md)).

## For end users (the built `.app`)

1. Get `YouTube Transcripts.app` from your developer (zip the `dist` folder or the app alone).
2. Unzip if needed, drag the app into **Applications** (optional).
3. **First launch on macOS:** unsigned apps often show “damaged” or “can’t be opened.” **Right‑click (or Control‑click) the app → Open → Open.** Or allow it under **System Settings → Privacy & Security**.
4. Enter your full channel URL (e.g. `https://www.youtube.com/@Handle`), Webshare dashboard **Proxy username** and **Proxy password** (Residential rotating product, not static datacenter lines).
5. Output defaults to `Documents/YouTubeTranscripts`; use **Choose…** to change it.
6. Under **Videos to download**, choose **All videos on the channel** or **Only the first N videos** (same as CLI `--limit`; order follows the channel uploads list from yt-dlp).
7. Enable **Resume** if you stopped a run and want to skip videos that already have a `.txt` file.

Credentials are passed only to the built-in downloader for that session; they are not saved to disk by the app (unless you use a separate `.env` next to the script when running from source).

## For developers — build on a Mac

The build script **always deletes** `build/` and `dist/` first so each run picks up the latest `youtube_transcripts_gui.py`.

From the repo root:

```bash
chmod +x scripts/build_mac_desktop_app.sh
./scripts/build_mac_desktop_app.sh
```

This creates **`dist/YouTube Transcripts.app`** using a disposable venv `.venv-desktop-build` (ignored if you add it to git — add to `.gitignore`).

- Build on the architecture you ship: run the script on **Apple Silicon** for M1/M2/M3 users, or on **Intel** for older Macs (or build a universal binary with extra PyInstaller/Xcode steps — not covered here).
- **Code signing & notarization:** For wide distribution outside your team, sign and notarize with an Apple Developer ID. Otherwise rely on **Right-click → Open** for testers.

## Run the GUI from source (development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python youtube_transcripts_gui.py
```
