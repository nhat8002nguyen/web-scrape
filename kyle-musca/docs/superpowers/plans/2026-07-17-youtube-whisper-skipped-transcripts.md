# YouTube Whisper Skipped-Transcripts Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second retry path for YouTube videos listed in `skipped.jsonl` that downloads each video (via yt-dlp) and transcribes speech with Whisper `large-v3` (`faster-whisper`), without changing the existing YouTube caption API flow or any Instagram scripts.

**Architecture:** Keep `download_channel_transcripts.py` as the primary caption scraper. Add a sibling CLI `whisper_skipped_transcripts.py` that reads the same `skipped.jsonl` shape, downloads audio/video with yt-dlp, runs local Whisper (patterned on `insta-video-transcripts/instagram_reels_transcripts.py`), and writes `.txt` files using the same `{sanitized_title}__{video_id}.txt` naming so `consolidate_youtube_transcripts.py` keeps working. Shared pure helpers are imported from `download_channel_transcripts` where possible; Whisper load/transcribe helpers are copied/adapted into the new YouTube module (do **not** import from or edit Instagram).

**Tech Stack:** Python 3.9+ (developed against 3.11), yt-dlp (already present), faster-whisper, python-dotenv, simplepush (optional notify), pytest for unit tests. System dependency: `ffmpeg` on PATH (yt-dlp audio extract + Whisper decode).

## Global Constraints

- **Do not modify** `kyle-musca/insta-video-transcripts/` (reference only).
- **Do not change** the primary caption behavior of `download_channel_transcripts.py` channel runs or `--retry-from-skip-log` (API retry stays option 1).
- Default Whisper model: `large-v3`.
- Output filenames must match existing convention: `{sanitize_title(title)}__{video_id}.txt`.
- Transcript body format must match caption `.txt` files: one Whisper segment text per line (no Instagram-style metadata header), so consolidate/Excel workflows stay consistent.
- Default skip-log reason filter: only caption-missing reasons (`transcripts_disabled`, `no_matching_transcript`). Proxy/IP failures should still prefer API retry first; use `--all-reasons` when the user wants Whisper on every skip-log row.
- Prefer downloading **audio** (`bestaudio/best`) to save disk/time; fall back to muxed best if needed.
- Delete downloaded media after a successful transcript by default; `--keep-media` retains files.
- No Redis / producer-worker for v1 (YAGNI). Single-process local CLI only.
- No pyannote diarization in v1 (podcast/multi-speaker YouTube would lose content under dominant-speaker heuristics).
- Python style: `from __future__ import annotations`, pathlib, type hints, prefer immutable bindings; match existing YouTube script style.
- No Dockerfile in tree — target Python 3.11+ locally/EC2; do not rely on Node features.

---

## File structure

| Path | Responsibility |
|------|----------------|
| `youtube-transcripts-scrape/whisper_skipped_transcripts.py` | New CLI: load skip log → download → Whisper → write `.txt` / fail log |
| `youtube-transcripts-scrape/requirements.txt` | Add `faster-whisper` (+ keep existing deps) |
| `youtube-transcripts-scrape/tests/test_whisper_skipped_helpers.py` | Unit tests for reason filter, segment formatting, skip-log loading integration |
| `youtube-transcripts-scrape/tests/fixtures/sample_skipped.jsonl` | Tiny skip-log fixture for tests |
| `youtube-transcripts-scrape/README.md` | Document Whisper retry as option 2 next to `--retry-from-skip-log` |
| `youtube-transcripts-scrape/scripts/ec2_setup_and_run.sh` | Ensure `ffmpeg` in OS packages; document Whisper example (optional small edit) |
| `download_channel_transcripts.py` | **No behavior change** — only import-safe reuse of existing helpers (`load_retry_videos_from_skip_log`, `build_output_filename`, `sanitize_title`, `load_env_files`, `notify_simplepush`, `resolve_simplepush_key`, `youtube_watch_url`) |

---

### Task 1: Fixture + failing unit tests for skip-log filtering and segment text

**Files:**
- Create: `youtube-transcripts-scrape/tests/fixtures/sample_skipped.jsonl`
- Create: `youtube-transcripts-scrape/tests/test_whisper_skipped_helpers.py`
- Create: `youtube-transcripts-scrape/whisper_skipped_transcripts.py` (minimal stubs only as needed for imports)

**Interfaces:**
- Consumes: existing `load_retry_videos_from_skip_log` / skip-log JSONL shape `{video_id, title, reason, detail?}`
- Produces: `DEFAULT_WHISPER_REASONS: frozenset[str]`; `load_skipped_entries(path: Path) -> list[dict]`; `filter_entries_by_reason(entries: list[dict], *, reasons: frozenset[str] | None, reason_contains: str | None) -> list[dict]`; `segments_to_transcript_text(segments: list[dict[str, object]], style: str) -> str`

- [ ] **Step 1: Create fixture**

`youtube-transcripts-scrape/tests/fixtures/sample_skipped.jsonl`:

```jsonl
{"video_id": "p4kM2Z81C4c", "title": "Hattie BOYDLE talking to Studio 10 on all things Hattie.", "reason": "transcripts_disabled"}
{"video_id": "Ouo7Se6zpfM", "title": "The Reset", "reason": "proxy_or_network_error", "detail": "ProxyError"}
{"video_id": "aAKbKr51jgg", "title": "Nordic Drops", "reason": "transcripts_disabled"}
{"video_id": "JU1LP-datLI", "title": "Training Compilation", "reason": "no_matching_transcript"}
{"video_id": "badid", "title": "Invalid", "reason": "transcripts_disabled"}
```

- [ ] **Step 2: Write the failing tests**

`youtube-transcripts-scrape/tests/test_whisper_skipped_helpers.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from whisper_skipped_transcripts import (
    DEFAULT_WHISPER_REASONS,
    filter_entries_by_reason,
    load_skipped_entries,
    segments_to_transcript_text,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skipped.jsonl"


def test_default_whisper_reasons():
    assert "transcripts_disabled" in DEFAULT_WHISPER_REASONS
    assert "no_matching_transcript" in DEFAULT_WHISPER_REASONS
    assert "proxy_or_network_error" not in DEFAULT_WHISPER_REASONS


def test_load_skipped_entries_skips_invalid_video_id():
    entries = load_skipped_entries(FIXTURE)
    ids = [e["video_id"] for e in entries]
    assert "p4kM2Z81C4c" in ids
    assert "badid" not in ids
    assert len(entries) == 4


def test_filter_default_reasons_excludes_proxy_errors():
    entries = load_skipped_entries(FIXTURE)
    filtered = filter_entries_by_reason(
        entries, reasons=DEFAULT_WHISPER_REASONS, reason_contains=None
    )
    ids = {e["video_id"] for e in filtered}
    assert ids == {"p4kM2Z81C4c", "aAKbKr51jgg", "JU1LP-datLI"}
    assert "Ouo7Se6zpfM" not in ids


def test_filter_all_reasons_when_reasons_none():
    entries = load_skipped_entries(FIXTURE)
    filtered = filter_entries_by_reason(entries, reasons=None, reason_contains=None)
    assert len(filtered) == 4


def test_filter_reason_contains():
    entries = load_skipped_entries(FIXTURE)
    filtered = filter_entries_by_reason(
        entries, reasons=None, reason_contains="proxy"
    )
    assert [e["video_id"] for e in filtered] == ["Ouo7Se6zpfM"]


def test_segments_to_transcript_text_lines():
    segments = [
        {"start": 0.0, "end": 1.0, "text": " Hello "},
        {"start": 1.0, "end": 2.0, "text": "world"},
        {"start": 2.0, "end": 3.0, "text": "  "},
    ]
    text = segments_to_transcript_text(segments, style="lines")
    assert text == "Hello\nworld\n"


def test_segments_to_transcript_text_paragraph():
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello"},
        {"start": 1.0, "end": 2.0, "text": "world"},
    ]
    text = segments_to_transcript_text(segments, style="paragraph")
    assert text == "Hello world\n"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd /Users/nhatnguyen/SourceCode/web-scrape/kyle-musca/youtube-transcripts-scrape
python3 -m venv .venv
source .venv/bin/activate
pip install -q pytest
PYTHONPATH=. pytest tests/test_whisper_skipped_helpers.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'whisper_skipped_transcripts'` (or import errors for missing symbols).

- [ ] **Step 4: Minimal implementation of helpers**

Create `youtube-transcripts-scrape/whisper_skipped_transcripts.py` with at least:

```python
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

DEFAULT_WHISPER_REASONS: frozenset[str] = frozenset(
    {
        "transcripts_disabled",
        "no_matching_transcript",
    }
)


def load_skipped_entries(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    text = path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        vid = obj.get("video_id")
        if not isinstance(vid, str) or not _YOUTUBE_VIDEO_ID_RE.fullmatch(vid):
            continue
        if vid in seen:
            continue
        seen.add(vid)
        title_o = obj.get("title")
        title = (
            title_o.strip()
            if isinstance(title_o, str) and title_o.strip()
            else vid
        )
        reason = obj.get("reason")
        entry: dict[str, Any] = {
            "video_id": vid,
            "title": title,
            "reason": reason if isinstance(reason, str) else "",
        }
        detail = obj.get("detail")
        if isinstance(detail, str) and detail:
            entry["detail"] = detail
        rows.append(entry)
    return rows


def filter_entries_by_reason(
    entries: list[dict[str, Any]],
    *,
    reasons: frozenset[str] | None,
    reason_contains: str | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    needle = (reason_contains or "").strip().lower()
    for entry in entries:
        reason = str(entry.get("reason") or "")
        if reasons is not None and reason not in reasons:
            continue
        if needle and needle not in reason.lower():
            continue
        out.append(entry)
    return out


def segments_to_transcript_text(
    segments: list[dict[str, object]],
    style: str,
) -> str:
    lines: list[str] = []
    for seg in segments:
        t = str(seg.get("text") or "").replace("\u200b", "").strip()
        if t:
            lines.append(t)
    if not lines:
        return ""
    if style == "paragraph":
        body = " ".join(lines)
    else:
        body = "\n".join(lines)
    if not body.endswith("\n"):
        body += "\n"
    return body
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd /Users/nhatnguyen/SourceCode/web-scrape/kyle-musca/youtube-transcripts-scrape
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_whisper_skipped_helpers.py -v
```

Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add youtube-transcripts-scrape/tests/fixtures/sample_skipped.jsonl \
  youtube-transcripts-scrape/tests/test_whisper_skipped_helpers.py \
  youtube-transcripts-scrape/whisper_skipped_transcripts.py
git commit -m "test: add Whisper skipped-log helper coverage for YouTube retry"
```

---

### Task 2: Add faster-whisper dependency + Whisper model load / transcribe helpers

**Files:**
- Modify: `youtube-transcripts-scrape/requirements.txt`
- Modify: `youtube-transcripts-scrape/whisper_skipped_transcripts.py`
- Modify: `youtube-transcripts-scrape/tests/test_whisper_skipped_helpers.py` (optional stub test for `transcribe_segments` with a fake model — see below)

**Interfaces:**
- Consumes: `argparse.Namespace` fields `model_size`, `device`, `compute_type`, `beam_size`, `language`, `vad_filter`
- Produces: `huggingface_cache_hub_dir() -> str`; `load_whisper_model(args) -> object`; `transcribe_segments(model, media_path: Path, args) -> list[dict[str, object]]` with keys `start`, `end`, `text`

- [ ] **Step 1: Update requirements**

Append to `youtube-transcripts-scrape/requirements.txt`:

```text
faster-whisper>=1.1.0
```

Keep existing pins (`youtube-transcript-api`, `yt-dlp`, `openpyxl`, `simplepush`, `python-dotenv`, `requests`).

- [ ] **Step 2: Write failing test for segment extraction shape (fake model)**

Add to `tests/test_whisper_skipped_helpers.py`:

```python
from pathlib import Path
from types import SimpleNamespace

from whisper_skipped_transcripts import transcribe_segments


class _FakeSeg:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


class _FakeModel:
    def transcribe(self, path, beam_size=5, language=None, vad_filter=True):
        assert Path(path).name == "clip.wav"
        return iter([_FakeSeg(0.0, 1.0, " hi "), _FakeSeg(1.0, 2.0, "")]), None


def test_transcribe_segments_strips_empty():
    args = SimpleNamespace(beam_size=5, language="en", vad_filter=True)
    segs = transcribe_segments(_FakeModel(), Path("/tmp/clip.wav"), args)
    assert segs == [{"start": 0.0, "end": 1.0, "text": "hi"}]
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
PYTHONPATH=. pytest tests/test_whisper_skipped_helpers.py::test_transcribe_segments_strips_empty -v
```

Expected: FAIL (`transcribe_segments` not defined).

- [ ] **Step 4: Implement Whisper helpers (adapted from Instagram, no diarization)**

Add to `whisper_skipped_transcripts.py` (imports: `argparse`, `os`, `sys`, `threading`, `time`):

```python
def huggingface_cache_hub_dir() -> str:
    hf_home = os.environ.get("HF_HOME", "").strip() or os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface"
    )
    return os.path.join(os.path.expanduser(hf_home), "hub")


def _whisper_heartbeat(stop: threading.Event, label: str, hub_dir: str) -> None:
    start = time.monotonic()
    while not stop.wait(30.0):
        elapsed = int(time.monotonic() - start)
        print(
            f"  {label} still loading ({elapsed}s elapsed). "
            f"If downloading, this folder should grow: {hub_dir}",
            file=sys.stderr,
            flush=True,
        )


def load_whisper_model(args: argparse.Namespace) -> object:
    if os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS", "").strip() != "1":
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "0")

    from faster_whisper import WhisperModel

    device = args.device
    compute_type = args.compute_type
    if device == "auto":
        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    hub_dir = huggingface_cache_hub_dir()
    print(
        f"Loading Whisper model {args.model_size!r} "
        f"(device={device}, compute_type={compute_type})…",
        file=sys.stderr,
        flush=True,
    )
    print(f"  Hugging Face hub cache: {hub_dir}", file=sys.stderr, flush=True)
    print(
        "  First-time `large-v3` is ~2.5–4 GB; expect several minutes on first run.",
        file=sys.stderr,
        flush=True,
    )

    stop = threading.Event()
    beat = threading.Thread(
        target=_whisper_heartbeat,
        args=(stop, "Whisper:", hub_dir),
        daemon=True,
    )
    beat.start()
    try:
        model = WhisperModel(
            args.model_size,
            device=device,
            compute_type=compute_type,
        )
    finally:
        stop.set()
    return model


def transcribe_segments(
    model,
    media_path: Path,
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    segments, _ = model.transcribe(
        str(media_path),
        beam_size=args.beam_size,
        language=args.language or None,
        vad_filter=args.vad_filter,
    )
    out: list[dict[str, object]] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        out.append(
            {
                "start": float(seg.start),
                "end": float(seg.end),
                "text": text,
            }
        )
    return out
```

- [ ] **Step 5: Install deps and run unit tests**

Run:

```bash
pip install -r requirements.txt pytest
PYTHONPATH=. pytest tests/test_whisper_skipped_helpers.py -v
```

Expected: PASS. (Model download is **not** required for unit tests.)

- [ ] **Step 6: Commit**

```bash
git add youtube-transcripts-scrape/requirements.txt \
  youtube-transcripts-scrape/whisper_skipped_transcripts.py \
  youtube-transcripts-scrape/tests/test_whisper_skipped_helpers.py
git commit -m "feat: add faster-whisper load/transcribe helpers for YouTube skipped retry"
```

---

### Task 3: yt-dlp download helper + process-one-video core

**Files:**
- Modify: `youtube-transcripts-scrape/whisper_skipped_transcripts.py`
- Modify: `youtube-transcripts-scrape/tests/test_whisper_skipped_helpers.py`

**Interfaces:**
- Consumes: `youtube_watch_url` / `build_output_filename` from `download_channel_transcripts`
- Produces:
  - `download_youtube_media(video_id: str, dest_dir: Path, *, quiet: bool = True) -> Path` — downloads audio-preferred file named `{video_id}.%(ext)s`, returns concrete path
  - `process_skipped_video(...)` — returns outcome `"transcribed" | "skipped_existing" | "failed"`

- [ ] **Step 1: Write failing tests for download path resolution helper**

Prefer testing a small pure helper used by download:

```python
from whisper_skipped_transcripts import resolve_downloaded_media_path


def test_resolve_downloaded_media_path_finds_file(tmp_path: Path):
    media = tmp_path / "abc12345678.m4a"
    media.write_bytes(b"x")
    found = resolve_downloaded_media_path(tmp_path, "abc12345678")
    assert found == media


def test_resolve_downloaded_media_path_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        resolve_downloaded_media_path(tmp_path, "abc12345678")
```

- [ ] **Step 2: Run to verify fail**

```bash
PYTHONPATH=. pytest tests/test_whisper_skipped_helpers.py::test_resolve_downloaded_media_path_finds_file -v
```

Expected: FAIL (`resolve_downloaded_media_path` missing).

- [ ] **Step 3: Implement download + process helpers**

```python
import yt_dlp
from download_channel_transcripts import (
    build_output_filename,
    youtube_watch_url,
)


def resolve_downloaded_media_path(dest_dir: Path, video_id: str) -> Path:
    matches = sorted(dest_dir.glob(f"{video_id}.*"))
    # Prefer non-partial / non-ytdl temp files
    matches = [
        p
        for p in matches
        if p.is_file()
        and not p.name.endswith(".part")
        and not p.name.endswith(".ytdl")
    ]
    if not matches:
        raise FileNotFoundError(
            f"No downloaded media for {video_id} under {dest_dir}"
        )
    return matches[0]


def download_youtube_media(
    video_id: str,
    dest_dir: Path,
    *,
    quiet: bool = True,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing = list(dest_dir.glob(f"{video_id}.*"))
    existing = [
        p
        for p in existing
        if p.is_file() and not p.name.endswith((".part", ".ytdl"))
    ]
    if existing:
        return existing[0]

    outtmpl = str(dest_dir / f"{video_id}.%(ext)s")
    opts: dict = {
        "outtmpl": outtmpl,
        "format": "bestaudio/best",
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": quiet,
    }
    url = youtube_watch_url(video_id)
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return resolve_downloaded_media_path(dest_dir, video_id)


def process_skipped_video(
    *,
    video_id: str,
    title: str,
    out_dir: Path,
    download_dir: Path,
    whisper_model,
    args: argparse.Namespace,
    fail_log_handle,
    fail_seen: set[str],
) -> str:
    """
    Returns: transcribed | skipped_existing | failed
    """
    from download_channel_transcripts import write_jsonl_skipped

    filename = build_output_filename(title, video_id)
    dest = out_dir / filename
    if args.resume and dest.is_file():
        return "skipped_existing"

    media_path: Path | None = None
    try:
        media_path = download_youtube_media(
            video_id, download_dir, quiet=not args.verbose
        )
        segments = transcribe_segments(whisper_model, media_path, args)
        body = segments_to_transcript_text(segments, style=args.format)
        if not body.strip():
            write_jsonl_skipped(
                fail_log_handle,
                {
                    "video_id": video_id,
                    "title": title,
                    "reason": "whisper_no_speech",
                    "detail": "transcription returned no segments",
                },
                fail_seen,
            )
            # Still write empty/near-empty file? Prefer fail without writing.
            return "failed"
        dest.write_text(body, encoding="utf-8")
        return "transcribed"
    except Exception as exc:
        write_jsonl_skipped(
            fail_log_handle,
            {
                "video_id": video_id,
                "title": title,
                "reason": type(exc).__name__,
                "detail": str(exc),
            },
            fail_seen,
        )
        return "failed"
    finally:
        if (
            media_path is not None
            and media_path.is_file()
            and not args.keep_media
            and dest.is_file()
        ):
            try:
                media_path.unlink()
            except OSError:
                pass
```

Notes for implementer:
- Only delete media when transcript file exists (successful write). On failure, leave media if present so a resume can skip re-download (`download_youtube_media` already reuses existing files).
- Adjust the `finally` condition carefully: delete only after `"transcribed"` success. Prefer restructuring so unlink happens only on success path rather than in a broad finally.

Recommended success-only cleanup:

```python
    outcome = "failed"
    try:
        media_path = download_youtube_media(...)
        segments = transcribe_segments(...)
        body = segments_to_transcript_text(...)
        if not body.strip():
            write_jsonl_skipped(... reason whisper_no_speech ...)
            return "failed"
        dest.write_text(body, encoding="utf-8")
        outcome = "transcribed"
        return outcome
    except Exception as exc:
        write_jsonl_skipped(...)
        return "failed"
    finally:
        if (
            outcome == "transcribed"
            and not args.keep_media
            and media_path is not None
            and media_path.is_file()
        ):
            try:
                media_path.unlink()
            except OSError:
                pass
```

- [ ] **Step 4: Run unit tests**

```bash
PYTHONPATH=. pytest tests/test_whisper_skipped_helpers.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add youtube-transcripts-scrape/whisper_skipped_transcripts.py \
  youtube-transcripts-scrape/tests/test_whisper_skipped_helpers.py
git commit -m "feat: download skipped YouTube media with yt-dlp for Whisper"
```

---

### Task 4: CLI `main()` — argparse, loop, Simplepush, summary

**Files:**
- Modify: `youtube-transcripts-scrape/whisper_skipped_transcripts.py`

**Interfaces:**
- CLI entry: `python whisper_skipped_transcripts.py --skip-log PATH --out DIR [options]`
- Required: `--skip-log` (path to `skipped.jsonl`)
- Default `--out`: parent of skip-log if under a channel folder is **not** inferred magically — require `--out` or default to `./transcripts` like the caption script; document that for Hattie this should be `./transcripts/hattieboydle7662`

- [ ] **Step 1: Implement `parse_args` + `main`**

Required flags / defaults (mirror Instagram Whisper knobs where useful):

| Flag | Default | Meaning |
|------|---------|---------|
| `--skip-log` | required | Path to `skipped.jsonl` |
| `--out` / `-o` | `transcripts` | Directory for `.txt` outputs |
| `--download-dir` | `videos` (resolved under `--out` if relative) | yt-dlp media cache |
| `--fail-log` | `whisper_failed.jsonl` (inside `--out`) | Failures from this Whisper run |
| `--resume` | off | Skip if output `.txt` already exists |
| `--all-reasons` | off | Process every skip-log row (ignore default reason set) |
| `--reason-contains` | `""` | Extra substring filter on `reason` |
| `--limit` / `-n` | none | Cap videos processed |
| `--model-size` | `large-v3` | Whisper model |
| `--device` | `auto` | `auto` / `cpu` / `cuda` |
| `--compute-type` | `auto` | faster-whisper compute type |
| `--beam-size` | `5` | |
| `--language` | `en` | Whisper language (`""` = auto-detect → pass `None`) |
| `--vad-filter` / `--no-vad-filter` | on | |
| `--format` | `lines` | `lines` \| `paragraph` |
| `--delay` | `0` | Sleep after each success |
| `--keep-media` | off | Keep downloaded audio/video |
| `--verbose` | off | |
| `--dry-run` | off | List selected video_ids and exit |
| `--simplepush-key` / title / event | same pattern as caption script | Notify on finish |
| `--test-simplepush` | off | |

`main` outline:

```python
def main(argv: list[str]) -> int:
    from download_channel_transcripts import (
        load_env_files,
        notify_simplepush,
        resolve_simplepush_key,
        write_jsonl_skipped,
        load_skip_log_video_ids,
    )

    load_env_files()
    args = parse_args(argv)
    # handle --test-simplepush like caption script

    skip_path = Path(args.skip_log).expanduser().resolve()
    if not skip_path.is_file():
        print(f"error: --skip-log not found: {skip_path}", file=sys.stderr)
        return 2

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    download_dir = Path(args.download_dir).expanduser()
    if not download_dir.is_absolute():
        download_dir = (out_dir / download_dir).resolve()
    download_dir.mkdir(parents=True, exist_ok=True)

    entries = load_skipped_entries(skip_path)
    reasons = None if args.all_reasons else DEFAULT_WHISPER_REASONS
    entries = filter_entries_by_reason(
        entries,
        reasons=reasons,
        reason_contains=args.reason_contains or None,
    )
    if args.limit is not None:
        entries = entries[: args.limit]

    if not entries:
        print("No matching skipped videos to process.")
        return 0

    if args.dry_run:
        for e in entries:
            print(f"{e['video_id']}\t{e.get('reason','')}\t{e['title']}")
        print(f"dry-run count={len(entries)}")
        return 0

    try:
        whisper_model = load_whisper_model(args)
    except Exception as exc:
        print(f"error: failed to load Whisper model: {exc}", file=sys.stderr)
        return 2

    fail_path = out_dir / args.fail_log
    fail_seen = load_skip_log_video_ids(fail_path)
    stats = {"transcribed": 0, "skipped_existing": 0, "failed": 0}

    with fail_path.open("a", encoding="utf-8") as fail_f:
        for index, entry in enumerate(entries, start=1):
            video_id = entry["video_id"]
            title = entry["title"]
            print(
                f"[{index}/{len(entries)}] {video_id}: {title[:120]}",
                flush=True,
            )
            outcome = process_skipped_video(
                video_id=video_id,
                title=title,
                out_dir=out_dir,
                download_dir=download_dir,
                whisper_model=whisper_model,
                args=args,
                fail_log_handle=fail_f,
                fail_seen=fail_seen,
            )
            stats[outcome if outcome != "skipped_existing" else "skipped_existing"] += 1
            # map outcome keys carefully:
            # transcribed -> stats["transcribed"]
            # skipped_existing -> stats["skipped_existing"]
            # failed -> stats["failed"]
            if outcome == "transcribed" and args.delay > 0:
                time.sleep(args.delay)

    # print Done summary + optional Simplepush
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Fix the stats increment to explicit if/elif (do not use the fragile dict key expression above).

- [ ] **Step 2: Smoke dry-run against real Hattie skip log (no Whisper load)**

Run:

```bash
cd /Users/nhatnguyen/SourceCode/web-scrape/kyle-musca/youtube-transcripts-scrape
source .venv/bin/activate
python whisper_skipped_transcripts.py \
  --skip-log ./transcripts/hattieboydle7662/skipped.jsonl \
  --out ./transcripts/hattieboydle7662 \
  --dry-run
```

Expected: lists ~9 videos with `transcripts_disabled` (not the 8 `proxy_or_network_error` rows).

With `--all-reasons`:

```bash
python whisper_skipped_transcripts.py \
  --skip-log ./transcripts/hattieboydle7662/skipped.jsonl \
  --out ./transcripts/hattieboydle7662 \
  --all-reasons \
  --dry-run
```

Expected: 17 rows (or fewer if invalid IDs).

- [ ] **Step 3: Optional tiny live smoke (limit 1) — only if machine has ffmpeg + disk/time**

```bash
python whisper_skipped_transcripts.py \
  --skip-log ./transcripts/hattieboydle7662/skipped.jsonl \
  --out ./transcripts/hattieboydle7662 \
  --download-dir ./transcripts/hattieboydle7662/videos \
  --resume \
  -n 1 \
  --model-size large-v3 \
  --verbose
```

Expected: downloads one media file, loads Whisper (first run may take long), writes one `{title}__{video_id}.txt`, deletes media unless `--keep-media`.

- [ ] **Step 4: Commit**

```bash
git add youtube-transcripts-scrape/whisper_skipped_transcripts.py
git commit -m "feat: CLI to Whisper-transcribe YouTube videos from skipped.jsonl"
```

---

### Task 5: README + EC2 setup notes

**Files:**
- Modify: `youtube-transcripts-scrape/README.md`
- Modify: `youtube-transcripts-scrape/scripts/ec2_setup_and_run.sh` (install `ffmpeg` in `install_system_packages`; add Whisper example in `usage`)

- [ ] **Step 1: Document option 2 in README**

After the existing **“3. Retry only IDs listed in a skip log”** API section, add:

```markdown
**4. Retry skipped videos with Whisper (local speech-to-text)** — for rows where YouTube has no captions (`transcripts_disabled` / `no_matching_transcript`), even if the video has speech:

Requires **`ffmpeg`** on PATH and a one-time Hugging Face download of Whisper `large-v3` (~2.5–4 GB).

```bash
# macOS
brew install ffmpeg

pip install -r requirements.txt

python3 whisper_skipped_transcripts.py \
  --skip-log ./transcripts/hattieboydle7662/skipped.jsonl \
  --out ./transcripts/hattieboydle7662 \
  --download-dir ./transcripts/hattieboydle7662/videos \
  --resume \
  --verbose
```

- Default reason filter: `transcripts_disabled`, `no_matching_transcript`.
- Use `--all-reasons` to include proxy/IP skip rows (prefer API `--retry-from-skip-log` for those first).
- Use `--dry-run` to preview selected IDs.
- Failures append to `whisper_failed.jsonl` inside `--out`.
- Output `.txt` names match the caption scraper so consolidate still works.
```

Also update the opening paragraph to say captions are primary; Whisper is an optional second retry for skipped videos.

- [ ] **Step 2: EC2 script — install ffmpeg**

In `install_system_packages`, add `ffmpeg` to both `dnf` and `apt` install lines (alongside `python3`, `tmux`, etc.).

Add usage example:

```bash
  # Whisper retry from skip log (needs ffmpeg + large-v3 cache):
  ./scripts/ec2_setup_and_run.sh shell
  python whisper_skipped_transcripts.py \
    --skip-log ./transcripts/CHANNEL/skipped.jsonl \
    --out ./transcripts/CHANNEL \
    --resume
```

(Optional: extend `ec2_setup_and_run.sh` with a `run-whisper` command that points at `whisper_skipped_transcripts.py` — nice-to-have; README example is enough if time-constrained.)

- [ ] **Step 3: Commit**

```bash
git add youtube-transcripts-scrape/README.md \
  youtube-transcripts-scrape/scripts/ec2_setup_and_run.sh
git commit -m "docs: document Whisper retry path for YouTube skipped videos"
```

---

## Spec coverage self-review

| Requirement | Task |
|-------------|------|
| Download skipped videos from `skipped.jsonl` | Task 3–4 |
| Transcribe with Whisper `large-v3` | Task 2–4 |
| Reference Instagram Whisper behavior | Task 2 (adapted helpers) |
| Do not modify Instagram scripts | Global Constraints |
| Second option only (API retry unchanged) | Separate CLI; Task 4–5 |
| Hattie path `.../hattieboydle7662/skipped.jsonl` documented | Task 5 + dry-run in Task 4 |

## Placeholder scan

No TBD / “implement later” / “add tests later” left — each step has concrete code or commands.

## Type consistency

- Skip entries always expose `video_id: str`, `title: str`, `reason: str`.
- Outcomes: `"transcribed" | "skipped_existing" | "failed"`.
- Segment dicts: `start: float`, `end: float`, `text: str`.
- Filename builder remains `build_output_filename(title, video_id)` from the caption module.

## Out of scope (intentional)

- GUI (`youtube_transcripts_gui.py`) Whisper button
- Auto-fallback inside the primary channel caption loop
- Redis workers / diarization / Instagram code changes
- Re-writing consolidate logic (existing consolidate already picks up new `.txt` files)

---
