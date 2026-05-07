# Running on Windows (quick guide)

This project is a **Python** tool. Use **Python 3.9 or newer** (3.11 is a good choice; see the main [README.md](README.md)).

## 1. Install Python

- Install from [https://www.python.org/downloads/](https://www.python.org/downloads/) and check **“Add python.exe to PATH”** during setup, **or**
- Install from the Microsoft Store (“Python 3.12”, etc.).

Open **Command Prompt** or **PowerShell** and confirm:

```powershell
python --version
```

If `python` is not found, try `py --version` (Windows launcher). Use whichever works for the steps below (`python` vs `py`).

## 2. Go to the project folder

Replace the path with where you unpacked or cloned the repo:

```powershell
cd C:\path\to\youtube-transcripts-scrape
```

## 3. Virtual environment

```powershell
python -m venv .venv
```

**Activate**

- **PowerShell:** `.\.venv\Scripts\Activate.ps1`
- **Command Prompt (cmd):** `.venv\Scripts\activate.bat`

If PowerShell says scripts are disabled, run once (current user):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again.

## 4. Install dependencies

With the venv active (prompt usually shows `(.venv)`):

```powershell
python -m pip install -r requirements.txt
```

## 5. Optional: `.env`

Create a file named `.env` in this same folder (next to `download_channel_transcripts.py`) if you use proxy or Simplepush settings. See [README.md](README.md).

## 6. Run the script

On Windows, use `python` (not `python3` unless your install provides it):

```powershell
python download_channel_transcripts.py "https://www.youtube.com/@YourChannelHandle"
```

Output folder example:

```powershell
python download_channel_transcripts.py "https://www.youtube.com/@YourChannelHandle" --out .\transcripts
```

Resume after an interrupt:

```powershell
python download_channel_transcripts.py "https://www.youtube.com/@YourChannelHandle" --out .\transcripts --resume
```

**Webshare credentials via environment (PowerShell)** — avoids putting passwords in command history:

```powershell
$env:WEBSHARE_PROXY_USERNAME = "YOUR_WEBSHARE_PROXY_USERNAME"
$env:WEBSHARE_PROXY_PASSWORD = "YOUR_WEBSHARE_PROXY_PASSWORD"
python download_channel_transcripts.py "https://www.youtube.com/@YourChannelHandle" --out .\transcripts
```

**Command Prompt (cmd)** for the same env vars:

```cmd
set WEBSHARE_PROXY_USERNAME=YOUR_WEBSHARE_PROXY_USERNAME
set WEBSHARE_PROXY_PASSWORD=YOUR_WEBSHARE_PROXY_PASSWORD
python download_channel_transcripts.py "https://www.youtube.com/@YourChannelHandle" --out .\transcripts
```

## 7. Multi-line commands

The README uses Unix line continuations (`\`). On Windows:

- **PowerShell:** end a line with a backtick `` ` `` to continue on the next line, **or** put the whole command on one line.
- **cmd:** end a line with `^` to continue, **or** use one line.

## 8. Common issues

| Issue | What to try |
|--------|-------------|
| `python` not recognized | Reinstall Python with “Add to PATH”, or use `py -3.11` instead of `python`. |
| `pip` not found | `python -m pip install -r requirements.txt` |
| PowerShell won’t run `Activate.ps1` | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Permission / path errors on `--out` | Use a folder you own, e.g. `.\transcripts` under the project directory. |

For flags, proxies, and troubleshooting, use the full [README.md](README.md).
