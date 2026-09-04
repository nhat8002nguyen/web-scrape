# Reel Captions Backfill + Forward Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist full Instagram reel captions into metadata and transcript `Title:` headers (filenames unchanged), keep reel listing stable when captions are missing, and ship a backfill CLI that enriches existing results without re-transcribing.

**Architecture:** Listing stays on the clips enumerator (no per-item caption fetch in the iterator). Caption is fetched via Instaloader `Post.from_shortcode` (using existing GraphQL patches) only at process time or in a dedicated **local** backfill script. Missing caption = bypass enrichment, keep `reel_{shortcode}`. Transcript `Title:` gets the full caption as a single physical line (newlines collapsed). Backfill is laptop-friendly: Instaloader + cookies (+ optional Webshare from `.env` with direct fallback) — no cloud transcription stack.

**Tech Stack:** Python 3, Instaloader (`>=4.14`), `requests`, `python-dotenv`, existing `instagram_reels_transcripts.py` auth/patches/Webshare helpers, `unittest` for tests. Backfill does **not** use faster-whisper, pyannote, torch, Redis, or GPU.

## Global Constraints

- Option B: update metadata + transcript `Title:` header; **never rename** transcript files.
- Full caption goes in transcript `Title:` (whitespace-collapsed to one line so `filter_and_consolidate_transcripts.py` keeps working).
- Listing must not break: empty/missing caption → bypass enrichment, continue.
- Do not re-run Whisper or re-download videos in the backfill path.
- **Backfill must run locally on a developer laptop** (not EC2). No Whisper/diarization/Redis/cloud required.
- Ship `requirements-backfill.txt` with only lightweight deps so a local venv installs in seconds without torch.
- Importing helpers for backfill must not eagerly import `faster_whisper` / `pyannote` / `redis` (keep those lazy in the main script; backfill must never call those code paths).
- **Backfill proxy:** use Webshare from `.env` (`WEBSHARE_PROXY_*` via `resolve_proxy_urls`) when configured; on proxy failure retry once on direct/default network. `--bypass-proxy` = direct only.
- Reuse `patch_instaloader()` and existing cookie/session helpers; do not invent a second auth path.
- Follow existing project style in `instagram_reels_transcripts.py` (`const`/`let` N/A — Python; prefer clear functions, minimal comments).

## File Structure

| File | Responsibility |
|------|----------------|
| `instagram_reels_transcripts.py` | Add `caption` on `ReelVideo`; helpers `caption_as_title`, `fetch_reel_caption_with_proxy_fallback`, `enrich_reel_caption`; sidecar/job/transcript writers; enrich inside `process_queue_item` after resume path is resolved, before writing outputs. Keep Whisper/Redis imports lazy. |
| `backfill_reel_captions.py` | **Local CLI:** walk `metadata/`, fetch captions via Webshare-then-direct, patch metadata + matching transcript headers. No transcription. |
| `requirements-backfill.txt` | Minimal local deps: `instaloader`, `requests`, `python-dotenv`. |
| `tests/test_reel_captions.py` | Unit tests for normalize, header patch, enrich bypass, metadata round-trip. |
| `docs/superpowers/specs/2026-07-29-reel-captions-design.md` | Approved design (already written). |

---

### Task 1: Caption helpers + `ReelVideo.caption` + unit tests

**Files:**
- Modify: `instagram_reels_transcripts.py` (`ReelVideo`, new helpers near `post_title`)
- Create: `tests/test_reel_captions.py`

**Interfaces:**
- Consumes: existing `ReelVideo`, `patch_instaloader`, `ProxyPool.as_requests_proxies`
- Produces:
  - `ReelVideo(..., caption: str = "")`
  - `caption_as_title(caption: str) -> str`
  - `fetch_reel_caption(loader, shortcode: str) -> str | None` (returns `None` on empty or any fetch error)
  - `fetch_reel_caption_with_proxy_fallback(loader, shortcode: str, proxy_url: str | None) -> str | None` (try proxy, then direct)
  - `enrich_reel_caption(loader, item: ReelVideo, proxy_url: str | None = None) -> ReelVideo` (no-op if caption already set or fetch returns `None`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reel_captions.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "instagram_reels_transcripts",
    ROOT / "instagram_reels_transcripts.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class CaptionAsTitleTests(unittest.TestCase):
    def test_collapses_newlines_and_spaces(self) -> None:
        raw = "Line one\nLine two\n\n  Line three  "
        self.assertEqual(mod.caption_as_title(raw), "Line one Line two Line three")

    def test_empty(self) -> None:
        self.assertEqual(mod.caption_as_title(""), "")
        self.assertEqual(mod.caption_as_title("   \n  "), "")


class EnrichReelCaptionTests(unittest.TestCase):
    def test_keeps_existing_caption(self) -> None:
        item = mod.ReelVideo(
            mediaid="1",
            shortcode="AbC",
            title="already",
            video_url="http://x",
            post_url="http://y",
            date_utc="",
            caption="already full",
        )
        out = mod.enrich_reel_caption(MagicMock(), item)
        self.assertIs(out, item)

    def test_bypass_when_fetch_returns_none(self) -> None:
        item = mod.ReelVideo(
            mediaid="1",
            shortcode="AbC",
            title="reel_AbC",
            video_url="http://x",
            post_url="http://y",
            date_utc="",
            caption="",
        )
        with patch.object(mod, "fetch_reel_caption_with_proxy_fallback", return_value=None):
            out = mod.enrich_reel_caption(MagicMock(), item, proxy_url="http://user:pass@proxy:80")
        self.assertEqual(out.title, "reel_AbC")
        self.assertEqual(out.caption, "")

    def test_sets_caption_and_title_when_found(self) -> None:
        item = mod.ReelVideo(
            mediaid="1",
            shortcode="AbC",
            title="reel_AbC",
            video_url="http://x",
            post_url="http://y",
            date_utc="",
            caption="",
        )
        with patch.object(
            mod, "fetch_reel_caption_with_proxy_fallback", return_value="Hello\nWorld"
        ):
            out = mod.enrich_reel_caption(MagicMock(), item, proxy_url=None)
        self.assertEqual(out.caption, "Hello\nWorld")
        self.assertEqual(out.title, "Hello World")


class ProxyFallbackTests(unittest.TestCase):
    def test_falls_back_to_direct_when_proxy_fetch_raises(self) -> None:
        loader = MagicMock()
        loader.context._session.proxies = {}

        def fetch_side_effect(ldr, _sc: str) -> str:
            if ldr.context._session.proxies:
                raise OSError("proxy failed")
            return "from direct"

        with patch.object(mod, "_fetch_reel_caption_or_raise", side_effect=fetch_side_effect):
            text = mod.fetch_reel_caption_with_proxy_fallback(
                loader, "AbC", "http://user:pass@p.webshare.io:80"
            )
        self.assertEqual(text, "from direct")
        self.assertEqual(loader.context._session.proxies, {})

    def test_empty_caption_on_proxy_does_not_retry_direct(self) -> None:
        loader = MagicMock()
        loader.context._session.proxies = {"http": "x"}
        with patch.object(
            mod, "_fetch_reel_caption_or_raise", side_effect=LookupError("empty caption")
        ) as mocked:
            text = mod.fetch_reel_caption_with_proxy_fallback(
                loader, "AbC", "http://user:pass@p.webshare.io:80"
            )
        self.assertIsNone(text)
        mocked.assert_called_once()

    def test_no_proxy_uses_direct_only(self) -> None:
        loader = MagicMock()
        loader.context._session.proxies = {}
        with patch.object(mod, "_fetch_reel_caption_or_raise", return_value="plain") as mocked:
            text = mod.fetch_reel_caption_with_proxy_fallback(loader, "AbC", None)
        self.assertEqual(text, "plain")
        mocked.assert_called_once()
```

Implement caption fetch with proxy-then-direct fallback:

```python
def _fetch_reel_caption_or_raise(loader, shortcode: str) -> str:
    import instaloader
    patch_instaloader()
    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    text = (post.caption or "").strip()
    if not text:
        raise LookupError("empty caption")
    return text


def fetch_reel_caption(loader, shortcode: str) -> str | None:
    try:
        return _fetch_reel_caption_or_raise(loader, shortcode)
    except Exception:
        return None


def fetch_reel_caption_with_proxy_fallback(
    loader, shortcode: str, proxy_url: str | None
) -> str | None:
    session = loader.context._session
    if proxy_url:
        session.proxies = ProxyPool.as_requests_proxies(proxy_url) or {}
        try:
            return _fetch_reel_caption_or_raise(loader, shortcode)
        except LookupError:
            session.proxies = {}
            return None
        except Exception:
            session.proxies = {}
    else:
        session.proxies = {}
    try:
        return _fetch_reel_caption_or_raise(loader, shortcode)
    except Exception:
        return None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nhatnguyen/SourceCode/web-scrape/kyle-musca/insta-video-transcripts && python3 -m unittest tests.test_reel_captions -v`

Expected: FAIL with `AttributeError: module ... has no attribute 'caption_as_title'` (or similar).

- [ ] **Step 3: Minimal implementation**

In `instagram_reels_transcripts.py`:

1. Extend dataclass:

```python
@dataclass
class ReelVideo:
    mediaid: str
    shortcode: str
    title: str
    video_url: str
    post_url: str
    date_utc: str
    caption: str = ""
```

2. Add helpers after `post_title` (include `_fetch_reel_caption_or_raise`, `fetch_reel_caption`, `fetch_reel_caption_with_proxy_fallback`, `enrich_reel_caption` as specified above). `enrich_reel_caption` must call `fetch_reel_caption_with_proxy_fallback(loader, item.shortcode, proxy_url)`.

```python
def enrich_reel_caption(
    loader, item: ReelVideo, proxy_url: str | None = None
) -> ReelVideo:
    if loader is None:
        return item
    if (item.caption or "").strip():
        return item
    text = fetch_reel_caption_with_proxy_fallback(loader, item.shortcode, proxy_url)
    if not text:
        return item
    return ReelVideo(
        mediaid=item.mediaid,
        shortcode=item.shortcode,
        title=caption_as_title(text),
        video_url=item.video_url,
        post_url=item.post_url,
        date_utc=item.date_utc,
        caption=text,
    )
```

3. Update constructors that build `ReelVideo` from clips/posts to pass `caption=` when text is known (clips path: full `caption_text` into `caption`, and set `title=caption_as_title(caption_text)` when present; keep `reel_{shortcode}` when absent). Listing must still yield items with empty caption.

Example clips branch change inside `reel_video_from_clips_media`:

```python
    caption = media.get("caption")
    caption_text = caption.get("text") if isinstance(caption, dict) else None
    caption_full = str(caption_text).strip() if caption_text else ""
    if caption_full:
        title = caption_as_title(caption_full)
    else:
        title = f"reel_{shortcode}"
    # ...
    return ReelVideo(
        mediaid=mediaid,
        shortcode=shortcode,
        title=title,
        video_url=str(video_versions[-1]["url"]),
        post_url=f"https://www.instagram.com/reel/{shortcode}/",
        date_utc=date_utc,
        caption=caption_full,
    )
```

And in the `Post` branch of `iter_reel_candidates`:

```python
            cap = (getattr(post, "caption", None) or "").strip()
            item = ReelVideo(
                mediaid=str(post.mediaid),
                shortcode=str(post.shortcode),
                title=post_title(post) if not cap else caption_as_title(cap),
                video_url=str(post.video_url),
                post_url=post_url(post),
                date_utc=str(post.date_utc),
                caption=cap,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_reel_captions -v`

Expected: PASS for Task 1 tests.

- [ ] **Step 5: Commit**

```bash
git add instagram_reels_transcripts.py tests/test_reel_captions.py
git commit -m "$(cat <<'EOF'
feat: add reel caption helpers with Webshare-then-direct fallback

EOF
)"
```

---

### Task 2: Persist caption in metadata, jobs, and transcript headers; enrich at process time

**Files:**
- Modify: `instagram_reels_transcripts.py` (`write_sidecar_metadata`, `reel_video_job_dict`, `reel_video_from_job_dict`, `build_transcript_text`, `process_queue_item`)
- Modify: `tests/test_reel_captions.py`

**Interfaces:**
- Consumes: `enrich_reel_caption`, `caption_as_title`, `ReelVideo.caption`
- Produces: sidecar/job JSON with `"caption"`; transcript `Title:` = full caption single-line when present; `process_queue_item` enriches after resume skip decision using a `loader` argument (or lazy import of loader from args — see steps)

- [ ] **Step 1: Write failing tests for metadata + transcript text**

Append to `tests/test_reel_captions.py`:

```python
class TranscriptAndMetadataTests(unittest.TestCase):
    def test_build_transcript_text_uses_full_caption_title(self) -> None:
        item = mod.ReelVideo(
            mediaid="99",
            shortcode="Zz",
            title="Hello World",
            video_url="http://x",
            post_url="https://www.instagram.com/reel/Zz/",
            date_utc="2026-01-01 00:00:00",
            caption="Hello\nWorld",
        )
        text = mod.build_transcript_text(item, [{"text": "spoken words", "start": 0, "end": 1}])
        self.assertIn("Title: Hello World\n", text)
        self.assertIn("spoken words", text)

    def test_job_dict_round_trip_preserves_caption(self) -> None:
        item = mod.ReelVideo(
            mediaid="99",
            shortcode="Zz",
            title="Hello World",
            video_url="http://x",
            post_url="https://www.instagram.com/reel/Zz/",
            date_utc="",
            caption="Hello\nWorld",
        )
        d = mod.reel_video_job_dict(item)
        self.assertEqual(d["caption"], "Hello\nWorld")
        back = mod.reel_video_from_job_dict(d)
        self.assertEqual(back.caption, "Hello\nWorld")
        self.assertEqual(back.title, "Hello World")

    def test_job_dict_missing_caption_defaults_empty(self) -> None:
        back = mod.reel_video_from_job_dict(
            {
                "mediaid": "1",
                "shortcode": "Ab",
                "title": "reel_Ab",
                "video_url": "http://x",
                "post_url": "",
                "date_utc": "",
            }
        )
        self.assertEqual(back.caption, "")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.TestTranscriptAndMetadataTests -v`  
(or full module)

Expected: FAIL until writers/readers updated (`caption` KeyError or Title mismatch).

- [ ] **Step 3: Implement persistence + enrich in process path**

1. `write_sidecar_metadata` — add `"caption": item.caption or ""`.

2. `reel_video_job_dict` — add `"caption": item.caption or ""`.

3. `reel_video_from_job_dict` — `caption=str(d.get("caption") or "")`.

4. `build_transcript_text`:

```python
def build_transcript_text(item: ReelVideo, segments: list[dict[str, object]]) -> str:
    lines = [str(seg["text"]).strip()
             for seg in segments if str(seg["text"]).strip()]
    body = "\n".join(lines).strip()
    title_line = caption_as_title(item.caption) if (item.caption or "").strip() else item.title
    header = [
        f"Title: {title_line}",
        f"Media ID: {item.mediaid}",
        f"Shortcode: {item.shortcode}",
        f"URL: {item.post_url}",
        f"Date UTC: {item.date_utc}",
        "",
    ]
    if body:
        return "\n".join(header) + body + "\n"
    return "\n".join(header) + "\n"
```

5. `process_queue_item`: add `loader` parameter. **Order matters for stable filenames:**

```python
    # Resolve paths from current title FIRST (usually reel_*), so resume + filenames stay stable.
    title_sanitized = sanitize_title(item.title)
    transcript_name = build_output_filename(item.title, item.mediaid)
    transcript_path = transcript_dir / transcript_name
    # ... resume check unchanged using transcript_path / mediaid ...

    # After resume miss: enrich caption (bypass if none). Do not recompute transcript_path.
    # Prefer Webshare from proxy_pool when configured; enrich helper falls back to direct on proxy failure.
    proxy_url = None
    if not getattr(args, "no_proxy", False):
        proxy_url = proxy_pool.next_url() if proxy_pool is not None else None
    item = enrich_reel_caption(loader, item, proxy_url=proxy_url)
```

Thread `loader` from `run_local` / worker loop call sites into `process_queue_item`. If a call site has no loader (should not happen for transcribe paths), pass `None` and make `enrich_reel_caption` no-op when `loader is None`.

```python
def enrich_reel_caption(loader, item: ReelVideo) -> ReelVideo:
    if loader is None:
        return item
    if (item.caption or "").strip():
        return item
    # ... as Task 1 ...
```

Producer path: listing stays unchanged (no enrich required for enqueue stability); jobs may still have empty caption; workers enrich at process time. Optional: producer may leave caption empty — acceptable.

- [ ] **Step 4: Run tests**

Run: `python3 -m unittest tests.test_reel_captions -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add instagram_reels_transcripts.py tests/test_reel_captions.py
git commit -m "$(cat <<'EOF'
feat: enrich captions at process time and persist in metadata/transcripts

EOF
)"
```

---

### Task 3: Transcript header patch helper + tests

**Files:**
- Modify: `instagram_reels_transcripts.py` (or keep helpers in `backfill_reel_captions.py` if preferred — **prefer main module** so backfill imports one place)
- Modify: `tests/test_reel_captions.py`

**Interfaces:**
- Produces:
  - `find_transcript_path_for_mediaid(transcript_dir: Path, mediaid: str) -> Path | None`
  - `patch_transcript_title(path: Path, title: str) -> bool` — replaces `Title:` header line; returns False if file missing or no Title line

- [ ] **Step 1: Write failing tests**

```python
import tempfile


class PatchTranscriptTitleTests(unittest.TestCase):
    def test_finds_by_mediaid_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            path = tdir / "reel_AbC__123.txt"
            path.write_text(
                "Title: reel_AbC\nMedia ID: 123\nShortcode: AbC\nURL: u\nDate UTC: \n\nbody\n",
                encoding="utf-8",
            )
            found = mod.find_transcript_path_for_mediaid(tdir, "123")
            self.assertEqual(found, path)

    def test_patch_title_keeps_body_and_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reel_AbC__123.txt"
            path.write_text(
                "Title: reel_AbC\nMedia ID: 123\nShortcode: AbC\nURL: u\nDate UTC: \n\nbody line\n",
                encoding="utf-8",
            )
            ok = mod.patch_transcript_title(path, "Full Caption Here")
            self.assertTrue(ok)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("Title: Full Caption Here\n"))
            self.assertIn("body line", text)
            self.assertEqual(path.name, "reel_AbC__123.txt")
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python3 -m unittest tests.test_reel_captions.PatchTranscriptTitleTests -v`

- [ ] **Step 3: Implement**

```python
def find_transcript_path_for_mediaid(transcript_dir: Path, mediaid: str) -> Path | None:
    matches = sorted(transcript_dir.glob(f"*__{mediaid}.txt"))
    if not matches:
        return None
    return matches[0]


def patch_transcript_title(path: Path, title: str) -> bool:
    if not path.is_file():
        return False
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        return False
    replaced = False
    out: list[str] = []
    for line in lines:
        if not replaced and line.startswith("Title:"):
            out.append(f"Title: {title}\n")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        return False
    path.write_text("".join(out), encoding="utf-8")
    return True
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add instagram_reels_transcripts.py tests/test_reel_captions.py
git commit -m "$(cat <<'EOF'
feat: add transcript Title header patch helpers for caption backfill

EOF
)"
```

---

### Task 4: Local `backfill_reel_captions.py` CLI (+ lightweight deps)

**Files:**
- Create: `backfill_reel_captions.py`
- Create: `requirements-backfill.txt`
- Modify: `tests/test_reel_captions.py` (fixture dry-run logic tests for metadata update function)
- Modify: `README.md` (local backfill usage section)

**Interfaces:**
- Consumes: `fetch_reel_caption_with_proxy_fallback`, `caption_as_title`, `patch_transcript_title`, `find_transcript_path_for_mediaid`, `resolve_proxy_urls`, `ProxyPool`, loader setup from main (`load_env_files`, `patch_instaloader`, cookie/session helpers)
- Produces: CLI exit 0 with summary counts: `updated`, `skipped_has_caption`, `skipped_no_caption`, `skipped_error`, `missing_transcript`
- **Local-only contract:** runs on a laptop with `pip install -r requirements-backfill.txt`; never imports or invokes Whisper/pyannote/Redis/video download.
- **Proxy contract:** load Webshare from `.env` via `resolve_proxy_urls`; each caption fetch tries proxy first, then direct on failure; `--bypass-proxy` forces direct-only.

Extract a pure function for testability:

```python
def backfill_one_metadata_file(
    meta_path: Path,
    transcript_dir: Path,
    *,
    loader,
    proxy_url: str | None,
    dry_run: bool,
) -> str:
    """Return outcome label: updated|skipped_has_caption|skipped_no_caption|skipped_error|missing_transcript|..."""
```

Logic:

1. Load JSON; require `shortcode` + `mediaid`.
2. If `(data.get("caption") or "").strip()` and title already equals `caption_as_title(caption)` → `skipped_has_caption` (still ensure transcript Title matches; if transcript Title stale, treat as needs update).
3. `text = fetch_reel_caption_with_proxy_fallback(loader, shortcode, proxy_url)`; if None → `skipped_no_caption`.
4. `title = caption_as_title(text)`.
5. If not dry_run: write metadata with `caption=text`, `title=title`; patch transcript if found; if transcript missing → still update metadata, return `updated_metadata_only` or count `missing_transcript` separately after update.
6. Never rename transcript files.
7. Never call `load_whisper_model`, diarization, Redis clients, or `download_video`.
8. Resolve `proxy_url` once at startup from `.env` Webshare (`resolve_proxy_urls`); pass into each `backfill_one_metadata_file` call. On proxy failure the fetch helper clears proxies and retries direct.

- [ ] **Step 1: Create lightweight requirements for local laptop**

Create `requirements-backfill.txt`:

```text
instaloader>=4.14
requests>=2.31.0
python-dotenv>=1.0.1
```

Do **not** list `faster-whisper`, `pyannote.audio`, `redis`, `torch`, or `simplepush` here.

- [ ] **Step 2: Write unit tests for `backfill_one_metadata_file` with mocked fetch**

(Same tests as previously planned — dry-run updated / bypass when no caption. Place them in `tests/test_reel_captions.py`.)

Also add a guard test that backfill module source does not reference heavy stacks:

```python
class BackfillLocalDepsTests(unittest.TestCase):
    def test_backfill_source_avoids_whisper_redis_pyannote(self) -> None:
        src = (ROOT / "backfill_reel_captions.py").read_text(encoding="utf-8")
        for banned in ("faster_whisper", "pyannote", "redis", "load_whisper_model", "WhisperModel"):
            self.assertNotIn(banned, src)
```

- [ ] **Step 3: Run tests — expect FAIL (module / requirements missing)**

Run: `python3 -m unittest tests.test_reel_captions.BackfillOneTests tests.test_reel_captions.BackfillLocalDepsTests -v`

- [ ] **Step 4: Implement local CLI + loader helper**

CLI sketch (local laptop entrypoint):

```python
#!/usr/bin/env python3
"""Backfill reel captions into existing metadata + transcript Title headers.

Runs locally (laptop). Uses Instaloader only — no Whisper, GPU, Redis, or re-download.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import instagram_reels_transcripts as irt


def backfill_one_metadata_file(
    meta_path: Path,
    transcript_dir: Path,
    *,
    loader,
    proxy_url: str | None,
    dry_run: bool,
) -> str:
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return "skipped_error"
    if not isinstance(data, dict):
        return "skipped_error"
    mediaid = str(data.get("mediaid") or meta_path.stem)
    shortcode = str(data.get("shortcode") or "").strip()
    if not shortcode:
        return "skipped_error"

    existing = str(data.get("caption") or "").strip()
    desired_title = irt.caption_as_title(existing) if existing else ""
    tpath = irt.find_transcript_path_for_mediaid(transcript_dir, mediaid)

    if existing and desired_title:
        needs_meta = str(data.get("title") or "") != desired_title
        needs_tx = False
        if tpath and tpath.is_file():
            first = tpath.read_text(encoding="utf-8").splitlines()[:1]
            needs_tx = not (first and first[0] == f"Title: {desired_title}")
        if not needs_meta and not needs_tx:
            return "skipped_has_caption"

    text = irt.fetch_reel_caption_with_proxy_fallback(loader, shortcode, proxy_url)
    if not text:
        return "skipped_no_caption"

    title = irt.caption_as_title(text)
    if dry_run:
        return "updated"

    data["caption"] = text
    data["title"] = title
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if tpath is None:
        return "missing_transcript"
    if not irt.patch_transcript_title(tpath, title):
        return "missing_transcript"
    return "updated"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Backfill Instagram reel captions into metadata JSON and transcript Title headers. "
            "Local laptop tool: Instaloader only (no Whisper / Redis / GPU)."
        ),
    )
    p.add_argument(
        "data_dir",
        type=Path,
        help="Local profile output dir containing metadata/ and transcripts/ (e.g. output/_biggcal)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--request-delay-min", type=float, default=1.0)
    p.add_argument("--request-delay-max", type=float, default=2.5)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--cookies-json", default=None)
    p.add_argument("--sessionfile", default=None)
    p.add_argument("--session-username", default=None)
    p.add_argument("--user-agent", default=None)
    p.add_argument("--webshare-user", default=None)
    p.add_argument("--webshare-password", default=None)
    p.add_argument("--webshare-host", default="p.webshare.io")
    p.add_argument("--webshare-port", type=int, default=80)
    p.add_argument("--proxy-url", default=None)
    p.add_argument("--proxy-file", default=None)
    p.add_argument("--proxy-mode", choices=("rotating", "single"), default="rotating")
    p.set_defaults(no_proxy=False)
    p.add_argument(
        "--bypass-proxy",
        dest="no_proxy",
        action="store_true",
        help="Skip Webshare/.env proxy; use direct network only.",
    )
    p.add_argument(
        "--with-proxy",
        dest="no_proxy",
        action="store_false",
        help="Use Webshare from .env when credentials are set (default).",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    irt.load_env_files()
    data_dir = args.data_dir.expanduser().resolve()
    metadata_dir = data_dir / "metadata"
    transcript_dir = data_dir / "transcripts"
    if not metadata_dir.is_dir():
        print(f"error: missing {metadata_dir}", file=sys.stderr)
        return 2

    # Build Instaloader via irt.build_authenticated_loader(args) (factor from main).
    # Must not load Whisper or connect to Redis.
    loader = build_loader_from_args(args)

    try:
        proxy_urls = irt.resolve_proxy_urls(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    proxy_pool = irt.ProxyPool(proxy_urls, mode=args.proxy_mode)
    proxy_url = proxy_pool.next_url() if proxy_urls else None
    if args.verbose:
        if proxy_url:
            print(
                f"caption fetch proxy={irt.mask_proxy_url(proxy_url)} "
                f"(fallback to direct on failure)",
                flush=True,
            )
        else:
            print("caption fetch: direct network (no Webshare configured)", flush=True)

    counts: dict[str, int] = {}
    paths = sorted(metadata_dir.glob("*.json"))
    if args.limit is not None:
        paths = paths[: max(0, args.limit)]
    for meta_path in paths:
        irt.sleep_jitter(args.request_delay_min, args.request_delay_max)
        # Rotate when proxy_mode=rotating so backfill spreads load across endpoints.
        item_proxy = proxy_pool.next_url() if proxy_urls else None
        outcome = backfill_one_metadata_file(
            meta_path,
            transcript_dir,
            loader=loader,
            proxy_url=item_proxy,
            dry_run=args.dry_run,
        )
        counts[outcome] = counts.get(outcome, 0) + 1
        if args.verbose:
            print(f"{meta_path.name} {outcome}", flush=True)
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Implement `build_loader_from_args` by factoring **minimal** loader construction from `irt.main` into `irt.build_authenticated_loader(args)` used by both CLIs (preferred). That helper must only set up Instaloader + cookies/session — no Whisper, no Redis.

README section (local laptop):

```markdown
## Backfill reel captions (local laptop; no re-transcribe)

Transcription can stay on EC2. Caption backfill runs on your Mac/PC with a light venv.

Uses `WEBSHARE_PROXY_*` from `.env` when set (try proxy first; on failure fall back to your default network). Pass `--bypass-proxy` to force direct-only.

```bash
cd kyle-musca/insta-video-transcripts
python3 -m venv .venv-backfill
source .venv-backfill/bin/activate
pip install -r requirements-backfill.txt

# Point at local output (rsync from cloud first if needed)
python backfill_reel_captions.py output/_biggcal \
  --cookies-json cookies.json \
  --dry-run --limit 5 --verbose

python backfill_reel_captions.py output/_biggcal --cookies-json cookies.json
```

Updates `metadata/*.json` (`caption`, `title`) and patches `Title:` in matching `transcripts/*__{mediaid}.txt`. Does not rename files, download videos, or run Whisper. Reels with no caption are skipped.
```

- [ ] **Step 5: Run all caption tests + local install smoke**

Run: `python3 -m unittest tests.test_reel_captions -v`

Expected: PASS.

Local install smoke (on the laptop; no GPU stack):

```bash
python3 -m venv /tmp/venv-backfill-smoke && \
  /tmp/venv-backfill-smoke/bin/pip install -r requirements-backfill.txt && \
  /tmp/venv-backfill-smoke/bin/python -c "import backfill_reel_captions; print('ok')"
```

Expected: `ok` without installing torch/whisper.

Manual Instagram smoke (optional, needs cookies):

```bash
python backfill_reel_captions.py output/_biggcal --cookies-json cookies.json --dry-run --limit 3 --verbose
```

- [ ] **Step 6: Commit**

```bash
git add backfill_reel_captions.py requirements-backfill.txt instagram_reels_transcripts.py tests/test_reel_captions.py README.md
git commit -m "$(cat <<'EOF'
feat: add local backfill_reel_captions CLI (no Whisper/cloud)

EOF
)"
```

---

### Task 5: Verification checklist (no new product code)

**Files:** none required beyond fixes if verification finds bugs

- [ ] **Step 1: Run full unit suite**

Run: `python3 -m unittest tests.test_reel_captions -v`

Expected: all PASS.

- [ ] **Step 2: Sanity-check listing still yields without captions**

Confirm `iter_reel_candidates` / `reel_video_from_clips_media` still return items when `caption` is absent (`title` stays `reel_*`). No live Instagram required — add a tiny unit test if not already covered:

```python
class ClipsMediaTests(unittest.TestCase):
    def test_missing_caption_still_builds_reel(self) -> None:
        media = {
            "media_type": 2,
            "video_versions": [{"url": "http://video"}],
            "code": "AbC123xyz",
            "pk": "42",
            "taken_at": 1700000000,
        }
        item = mod.reel_video_from_clips_media(media)
        assert item is not None
        self.assertEqual(item.title, "reel_AbC123xyz")
        self.assertEqual(item.caption, "")
```

- [ ] **Step 3: Commit test if added**

```bash
git add tests/test_reel_captions.py
git commit -m "$(cat <<'EOF'
test: ensure clips listing works when caption is absent

EOF
)"
```

---

## Self-Review

| Spec requirement | Task |
|------------------|------|
| Full caption in metadata | Task 2 sidecar + Task 4 backfill |
| Full caption in transcript `Title:` | Task 2 `build_transcript_text` + Task 3/4 patch |
| Keep filenames (option B) | Task 2 path-before-enrich; Task 4 no rename |
| Listing never breaks / no caption → bypass | Task 1 enrich bypass; Task 5 clips test; Task 4 `skipped_no_caption` |
| Backfill without re-transcribe | Task 4 CLI |
| **Backfill runs locally on laptop (no Whisper/cloud)** | Task 4 `requirements-backfill.txt` + local README + deps guard test |
| **Webshare from .env with direct fallback** | Task 1 `fetch_reel_caption_with_proxy_fallback`; Task 4 `resolve_proxy_urls` |
| Instaloader caption via post metadata | Task 1 `fetch_reel_caption` + existing patches |

Placeholder scan: none intentional. Types: `ReelVideo.caption: str`, helpers return `str | None` / `ReelVideo` / `Path | None` consistently.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-29-reel-captions.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — run tasks in this session with executing-plans checkpoints  

Which approach?
