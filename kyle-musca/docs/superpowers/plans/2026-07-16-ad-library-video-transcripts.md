# Meta Ad Library Video Transcripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a sibling CLI to `kyle-insta-video-transcripts` that scrapes Meta Ad Library video creatives for a page (default Hormozi `view_all_page_id=116482854782233`) and transcribes them with Whisper `large-v3`. **Primary path:** one process on one machine (`--redis-mode local`, default) — scrape → download → transcribe with no Redis. **Optional path:** Redis producer/worker for horizontal scaling (same as Instagram).

**Architecture:** Playwright headless loads the public Ad Library URL (logged-out), harvests GraphQL search payloads (initial HTML + scroll/`AdLibrarySearchPaginationQuery` responses), a pure parser turns nodes into `AdVideo` jobs. **Local mode** loads Whisper once and processes each video in-process (scrape → download → transcript → checkpoint) with zero queue infrastructure. **Optional Redis mode** uses the Instagram-compatible job schema (`mediaid`, `shortcode`, `title`, `video_url`, `post_url`, `date_utc`) via `XADD` / `XREADGROUP`. CDN `video_hd_url` values expire — download promptly after discovery (local mode does this immediately; Redis workers must start soon after the producer).

**Tech Stack:** Python 3.11+, Playwright (Chromium), requests, redis-py, faster-whisper, python-dotenv, pytest (same Whisper/Redis stack as `kyle-insta-video-transcripts`).

## Global Constraints

- Sibling package path: `kyle-musca/kyle-ad-library-video-transcripts/` (do not modify Instagram crawl logic in `kyle-insta-video-transcripts` except optional README cross-link).
- Stay **logged out** of Facebook in automation (public Ad Library only).
- Default target page ID: `116482854782233` (Alex Hormozi Ad Library).
- Default filters: `active_status=active`, `ad_type=all`, `country=ALL`, `media_type=video`, `search_type=page`.
- Redis job payload keys **must** match Instagram workers: `mediaid`, `shortcode`, `title`, `video_url`, `post_url`, `date_utc` (strings).
- Map `mediaid` = `ad_archive_id`; `shortcode` = `ad_archive_id`; `video_url` = `snapshot.videos[].video_hd_url` (fallback `video_sd_url`); `post_url` = `https://www.facebook.com/ads/library/?id={ad_archive_id}`.
- **Default `--redis-mode` is `local`** (single-machine, one-flow, no Redis). Redis URL is **not** required for `local` or `--dry-run`.
- Redis modes `producer` / `worker` / `requeue-skipped` are optional scaling paths only.
- Default Redis stream (when used): `adlib:video:jobs`; default group: `transcribers`.
- Default Whisper model: `large-v3`.
- Prefer `video_hd_url`; skip ads with no video URLs.
- Plain `curl`/anonymous requests often get a challenge page (~empty HTML); bootstrap via Playwright is required.
- GraphQL `doc_id` rotates; do **not** hardcode a permanent doc_id — capture live from Playwright network or page.
- Python style: `const`-equivalent via `const` N/A — use `const` mentality: prefer immutable bindings (`x = ...` once); use `list`/`dict` mutably only when needed; no `var`; match Instagram script style (`from __future__ import annotations`, dataclasses, pathlib).
- Node version N/A (Python project); no Dockerfile in tree — target Python 3.11+.

## Research notes (DevTools, 2026-07-16)

Live page: [Hormozi Ad Library](https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&is_targeted_country=false&media_type=all&search_type=page&sort_data[mode]=total_impressions&sort_data[direction]=desc&view_all_page_id=116482854782233)

Observed in browser DOM/HTML (~1.9MB document):

| Signal | Value |
|--------|--------|
| Result count UI | ~620 results (active) |
| Unique `ad_archive_id` in first paint | ~30 |
| `video_hd_url` / `video_sd_url` occurrences | 64 each in full HTML |
| `<video>` elements with playable `fbcdn` src | 19+ on viewport |
| Pagination | `has_next_page: true`, `end_cursor` present |
| Network | POST `https://www.facebook.com/api/graphql/` on scroll |

Example fields from embedded snapshot JSON:

- `ad_archive_id`: `1295034249373689`
- `page_id`: `116482854782233`, `page_name`: `Alex Hormozi`
- `display_format`: `VIDEO`
- `title`: e.g. `Download Free Personalized Scaling Roadmap`
- `body.text`: markdown-ish ad copy
- `videos[].video_hd_url` / `video_sd_url` / `video_preview_image_url`
- `link_url`, `cta_text`, `publisher_platform[]`, `is_active`, `start_date` (unix int)

UI shows **Library ID** matching `ad_archive_id`. Prefer GraphQL JSON over scraping the visible card DOM.

---

## File structure

| Path | Responsibility |
|------|----------------|
| `kyle-ad-library-video-transcripts/ad_library_parser.py` | Pure parse of GraphQL/HTML payloads → `AdVideo` + job dicts |
| `kyle-ad-library-video-transcripts/ad_library_client.py` | Playwright session, URL build, scroll + GraphQL capture/pagination |
| `kyle-ad-library-video-transcripts/ad_library_video_transcripts.py` | CLI: **`local` (default, no Redis)** / producer / worker / requeue-skipped |
| `kyle-ad-library-video-transcripts/tests/fixtures/sample_ad_node.json` | One collated ad node with video for unit tests |
| `kyle-ad-library-video-transcripts/tests/fixtures/sample_search_response.json` | Minimal `search_results_connection` page |
| `kyle-ad-library-video-transcripts/tests/test_ad_library_parser.py` | Parser unit tests |
| `kyle-ad-library-video-transcripts/tests/test_ad_library_client_url.py` | URL builder tests (no network) |
| `kyle-ad-library-video-transcripts/requirements.txt` | Dependencies |
| `kyle-ad-library-video-transcripts/.env.example` | Env template |
| `kyle-ad-library-video-transcripts/.gitignore` | Ignore venv, output, `.env`, browser profile |
| `kyle-ad-library-video-transcripts/README.md` | Runbook: **local one-flow first**, then optional Redis producer/worker |

---

### Task 1: Scaffold package + parser fixture + failing parser tests

**Files:**
- Create: `kyle-ad-library-video-transcripts/requirements.txt`
- Create: `kyle-ad-library-video-transcripts/.gitignore`
- Create: `kyle-ad-library-video-transcripts/tests/fixtures/sample_ad_node.json`
- Create: `kyle-ad-library-video-transcripts/tests/fixtures/sample_search_response.json`
- Create: `kyle-ad-library-video-transcripts/tests/test_ad_library_parser.py`
- Create: `kyle-ad-library-video-transcripts/ad_library_parser.py` (minimal stub only if needed for import; prefer TDD fail-first)

**Interfaces:**
- Consumes: none
- Produces: fixture JSON shapes; tests that expect `parse_ad_node`, `iter_videos_from_search_payload`, `ad_video_job_dict`

- [ ] **Step 1: Create package files**

`kyle-ad-library-video-transcripts/requirements.txt`:

```text
faster-whisper>=1.1.0
pyannote.audio>=3.3.2
simplepush>=2.2.4
python-dotenv>=1.0.1
tqdm>=4.66.0
requests>=2.31.0
redis>=5.0.0
playwright>=1.49.0
pytest>=8.0.0
```

`kyle-ad-library-video-transcripts/.gitignore`:

```text
.venv/
__pycache__/
*.pyc
.env
output/
videos/
transcripts/
metadata/
checkpoint.json
skipped.jsonl
.playwright/
*.pem
.DS_Store
```

- [ ] **Step 2: Write fixtures**

`kyle-ad-library-video-transcripts/tests/fixtures/sample_ad_node.json`:

```json
{
  "ad_archive_id": "1295034249373689",
  "page_id": "116482854782233",
  "page_name": "Alex Hormozi",
  "is_active": true,
  "start_date": 1719014400,
  "publisher_platform": ["FACEBOOK", "INSTAGRAM"],
  "snapshot": {
    "body": {
      "text": "**Are you struggling to scale?**\n\nTo scale, you need one of these three things."
    },
    "title": "Download Free Personalized Scaling Roadmap",
    "cta_text": "Download",
    "display_format": "VIDEO",
    "link_url": "https://www.acquisition.com/roadmap",
    "images": [],
    "videos": [
      {
        "video_hd_url": "https://video.xx.fbcdn.net/example-hd.mp4",
        "video_sd_url": "https://video.xx.fbcdn.net/example-sd.mp4",
        "video_preview_image_url": "https://scontent.xx.fbcdn.net/example.jpg"
      }
    ]
  }
}
```

`kyle-ad-library-video-transcripts/tests/fixtures/sample_search_response.json`:

```json
{
  "data": {
    "ad_library_main": {
      "search_results_connection": {
        "edges": [
          {
            "node": {
              "collated_results": [
                {
                  "ad_archive_id": "1295034249373689",
                  "page_id": "116482854782233",
                  "page_name": "Alex Hormozi",
                  "is_active": true,
                  "start_date": 1719014400,
                  "publisher_platform": ["FACEBOOK", "INSTAGRAM"],
                  "snapshot": {
                    "body": {"text": "Hello world ad copy"},
                    "title": "Download Free Personalized Scaling Roadmap",
                    "display_format": "VIDEO",
                    "videos": [
                      {
                        "video_hd_url": "https://video.xx.fbcdn.net/example-hd.mp4",
                        "video_sd_url": "https://video.xx.fbcdn.net/example-sd.mp4"
                      }
                    ]
                  }
                },
                {
                  "ad_archive_id": "999",
                  "page_id": "116482854782233",
                  "page_name": "Alex Hormozi",
                  "snapshot": {
                    "title": "Image only",
                    "display_format": "IMAGE",
                    "videos": [],
                    "images": [{"original_image_url": "https://scontent.xx.fbcdn.net/x.jpg"}]
                  }
                }
              ]
            }
          }
        ],
        "page_info": {
          "has_next_page": true,
          "end_cursor": "CURSOR_ABC"
        }
      }
    }
  }
}
```

- [ ] **Step 3: Write the failing tests**

`kyle-ad-library-video-transcripts/tests/test_ad_library_parser.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ad_library_parser import (
    AdVideo,
    ad_video_from_job_dict,
    ad_video_job_dict,
    iter_videos_from_search_payload,
    parse_ad_node,
    parse_page_info,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ad_node_prefers_hd_url():
    node = json.loads((FIXTURES / "sample_ad_node.json").read_text(encoding="utf-8"))
    item = parse_ad_node(node)
    assert item is not None
    assert item.mediaid == "1295034249373689"
    assert item.shortcode == "1295034249373689"
    assert item.video_url.endswith("example-hd.mp4")
    assert item.post_url == "https://www.facebook.com/ads/library/?id=1295034249373689"
    assert "Scaling Roadmap" in item.title
    assert item.date_utc.startswith("2024-")


def test_parse_ad_node_skips_image_only():
    node = {
        "ad_archive_id": "1",
        "snapshot": {"title": "x", "videos": []},
    }
    assert parse_ad_node(node) is None


def test_iter_videos_from_search_payload_skips_non_video():
    payload = json.loads((FIXTURES / "sample_search_response.json").read_text(encoding="utf-8"))
    items = list(iter_videos_from_search_payload(payload))
    assert len(items) == 1
    assert items[0].mediaid == "1295034249373689"


def test_parse_page_info():
    payload = json.loads((FIXTURES / "sample_search_response.json").read_text(encoding="utf-8"))
    info = parse_page_info(payload)
    assert info["has_next_page"] is True
    assert info["end_cursor"] == "CURSOR_ABC"


def test_job_dict_roundtrip_matches_instagram_keys():
    item = AdVideo(
        mediaid="1295034249373689",
        shortcode="1295034249373689",
        title="Hello",
        video_url="https://video.xx.fbcdn.net/a.mp4",
        post_url="https://www.facebook.com/ads/library/?id=1295034249373689",
        date_utc="2024-06-22 00:00:00",
    )
    d = ad_video_job_dict(item)
    assert set(d.keys()) == {
        "mediaid",
        "shortcode",
        "title",
        "video_url",
        "post_url",
        "date_utc",
    }
    assert ad_video_from_job_dict(d).mediaid == item.mediaid
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```bash
cd kyle-ad-library-video-transcripts
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/test_ad_library_parser.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ad_library_parser'` (or import errors for missing symbols).

- [ ] **Step 5: Commit**

```bash
git add kyle-ad-library-video-transcripts/requirements.txt \
  kyle-ad-library-video-transcripts/.gitignore \
  kyle-ad-library-video-transcripts/tests
git commit -m "test: scaffold Ad Library parser fixtures and failing tests"
```

---

### Task 2: Implement `ad_library_parser.py`

**Files:**
- Create: `kyle-ad-library-video-transcripts/ad_library_parser.py`
- Test: `kyle-ad-library-video-transcripts/tests/test_ad_library_parser.py`

**Interfaces:**
- Consumes: fixture JSON from Task 1
- Produces:
  - `@dataclass AdVideo(mediaid: str, shortcode: str, title: str, video_url: str, post_url: str, date_utc: str)`
  - `parse_ad_node(node: dict) -> AdVideo | None`
  - `iter_videos_from_search_payload(payload: dict) -> Iterable[AdVideo]`
  - `parse_page_info(payload: dict) -> dict` with keys `has_next_page: bool`, `end_cursor: str | None`
  - `ad_video_job_dict(item: AdVideo) -> dict[str, str]`
  - `ad_video_from_job_dict(d: dict) -> AdVideo`
  - `extract_graphql_payloads_from_html(html: str) -> list[dict]` (best-effort; used by client)

- [ ] **Step 1: Write minimal implementation**

Create `kyle-ad-library-video-transcripts/ad_library_parser.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Iterator
from urllib.parse import unquote


@dataclass
class AdVideo:
    mediaid: str
    shortcode: str
    title: str
    video_url: str
    post_url: str
    date_utc: str


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        cleaned = line.strip().strip("*").strip()
        if cleaned:
            return cleaned
    return ""


def _title_from_snapshot(snapshot: dict[str, Any], ad_archive_id: str) -> str:
    title = str(snapshot.get("title") or "").strip()
    if title:
        return title
    body = _as_dict(snapshot.get("body"))
    body_text = _first_line(str(body.get("text") or ""))
    if body_text:
        return body_text
    return f"ad_{ad_archive_id}"


def _pick_video_url(snapshot: dict[str, Any]) -> str:
    videos = snapshot.get("videos") or []
    if not isinstance(videos, list):
        return ""
    for video in videos:
        if not isinstance(video, dict):
            continue
        hd = str(video.get("video_hd_url") or "").strip()
        if hd:
            return hd.replace("\\/", "/")
        sd = str(video.get("video_sd_url") or "").strip()
        if sd:
            return sd.replace("\\/", "/")
    return ""


def _date_utc_from_start(start_date: Any) -> str:
    if start_date is None or start_date == "":
        return ""
    try:
        ts = int(start_date)
    except (TypeError, ValueError):
        return str(start_date)
    # Guard absurd values; Ad Library uses unix seconds for start_date.
    if ts < 1_000_000_000 or ts > 4_000_000_000:
        return str(start_date)
    return str(dt.datetime.utcfromtimestamp(ts))


def parse_ad_node(node: dict[str, Any]) -> AdVideo | None:
    if not isinstance(node, dict):
        return None
    ad_archive_id = str(node.get("ad_archive_id") or "").strip()
    if not ad_archive_id:
        return None
    snapshot = _as_dict(node.get("snapshot"))
    video_url = _pick_video_url(snapshot)
    if not video_url:
        return None
    return AdVideo(
        mediaid=ad_archive_id,
        shortcode=ad_archive_id,
        title=_title_from_snapshot(snapshot, ad_archive_id),
        video_url=video_url,
        post_url=f"https://www.facebook.com/ads/library/?id={ad_archive_id}",
        date_utc=_date_utc_from_start(node.get("start_date")),
    )


def _walk_collated_results(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    connection = (
        _as_dict(_as_dict(payload.get("data")).get("ad_library_main"))
        .get("search_results_connection")
    )
    connection = _as_dict(connection)
    edges = connection.get("edges") or []
    if not isinstance(edges, list):
        return
    for edge in edges:
        node = _as_dict(_as_dict(edge).get("node"))
        collated = node.get("collated_results") or []
        if isinstance(collated, list):
            for item in collated:
                if isinstance(item, dict):
                    yield item
        # Some payloads put fields directly on node
        if node.get("ad_archive_id") and node.get("snapshot"):
            yield node


def iter_videos_from_search_payload(payload: dict[str, Any]) -> Iterable[AdVideo]:
    seen: set[str] = set()
    for raw in _walk_collated_results(payload):
        item = parse_ad_node(raw)
        if item is None or item.mediaid in seen:
            continue
        seen.add(item.mediaid)
        yield item


def parse_page_info(payload: dict[str, Any]) -> dict[str, Any]:
    connection = (
        _as_dict(_as_dict(payload.get("data")).get("ad_library_main"))
        .get("search_results_connection")
    )
    page_info = _as_dict(_as_dict(connection).get("page_info"))
    has_next = bool(page_info.get("has_next_page"))
    cursor = page_info.get("end_cursor")
    end_cursor = str(cursor).strip() if cursor else None
    return {"has_next_page": has_next, "end_cursor": end_cursor or None}


def ad_video_job_dict(item: AdVideo) -> dict[str, str]:
    return {
        "mediaid": item.mediaid,
        "shortcode": item.shortcode,
        "title": item.title,
        "video_url": item.video_url,
        "post_url": item.post_url,
        "date_utc": item.date_utc,
    }


def ad_video_from_job_dict(d: dict[str, Any]) -> AdVideo:
    return AdVideo(
        mediaid=str(d["mediaid"]),
        shortcode=str(d["shortcode"]),
        title=str(d.get("title") or ""),
        video_url=str(d["video_url"]),
        post_url=str(d.get("post_url") or ""),
        date_utc=str(d.get("date_utc") or ""),
    )


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_graphql_payloads_from_html(html: str) -> list[dict[str, Any]]:
    """Best-effort: find search_results_connection blobs inside page HTML."""
    if not html or "search_results_connection" not in html:
        # Fallback: still try to recover ad nodes via regex-assembled mini payloads
        return _payloads_from_raw_ad_archive_chunks(html)
    payloads: list[dict[str, Any]] = []
    # Facebook embeds escaped JSON; normalize common escapes then scan.
    normalized = (
        html.replace("\\/", "/")
        .replace("\\u00253D", "=")
        .replace("\\u003C", "<")
        .replace("\\u003E", ">")
    )
    marker = "search_results_connection"
    start = 0
    while True:
        idx = normalized.find(marker, start)
        if idx < 0:
            break
        # Walk left to a nearby '{' — bounded search
        left = normalized.rfind("{", max(0, idx - 500), idx)
        if left < 0:
            start = idx + len(marker)
            continue
        snippet = normalized[left : left + 2_000_000]
        try:
            obj = json.loads(snippet)
            if isinstance(obj, dict):
                payloads.append(obj if "data" in obj else {"data": {"ad_library_main": obj}})
        except Exception:
            pass
        start = idx + len(marker)
        if len(payloads) >= 5:
            break
    if payloads:
        return payloads
    return _payloads_from_raw_ad_archive_chunks(html)


def _payloads_from_raw_ad_archive_chunks(html: str) -> list[dict[str, Any]]:
    """Build a synthetic search payload from ad_archive_id + video_hd_url pairs in HTML."""
    if not html:
        return []
    text = html.replace("\\/", "/").replace("\\u00253D", "=")
    ids = re.findall(r'"ad_archive_id"\s*:\s*"(\d+)"', text)
    # Pair each archive id window with a nearby hd url
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(r'"ad_archive_id"\s*:\s*"(\d+)"', text):
        ad_id = match.group(1)
        if ad_id in seen:
            continue
        window = text[match.start() : match.start() + 8000]
        hd = re.search(r'"video_hd_url"\s*:\s*"(https:[^"]+)"', window)
        sd = re.search(r'"video_sd_url"\s*:\s*"(https:[^"]+)"', window)
        title_m = re.search(r'"title"\s*:\s*"([^"]*)"', window)
        start_m = re.search(r'"start_date"\s*:\s*(\d+)', window)
        video_url = ""
        if hd:
            video_url = unquote(hd.group(1).encode("utf-8").decode("unicode_escape", errors="ignore"))
        elif sd:
            video_url = unquote(sd.group(1).encode("utf-8").decode("unicode_escape", errors="ignore"))
        if not video_url:
            continue
        seen.add(ad_id)
        results.append(
            {
                "ad_archive_id": ad_id,
                "start_date": int(start_m.group(1)) if start_m else None,
                "snapshot": {
                    "title": title_m.group(1) if title_m else f"ad_{ad_id}",
                    "videos": [{"video_hd_url": video_url}],
                },
            }
        )
    if not results:
        return []
    return [
        {
            "data": {
                "ad_library_main": {
                    "search_results_connection": {
                        "edges": [{"node": {"collated_results": results}}],
                        "page_info": {"has_next_page": False, "end_cursor": None},
                    }
                }
            }
        }
    ]
```

- [ ] **Step 2: Run tests to verify they pass**

Run:

```bash
cd kyle-ad-library-video-transcripts
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_ad_library_parser.py -v
```

Expected: PASS (all tests green).

- [ ] **Step 3: Commit**

```bash
git add kyle-ad-library-video-transcripts/ad_library_parser.py
git commit -m "feat: parse Ad Library GraphQL nodes into video jobs"
```

---

### Task 3: Ad Library URL builder + Playwright client

**Files:**
- Create: `kyle-ad-library-video-transcripts/ad_library_client.py`
- Create: `kyle-ad-library-video-transcripts/tests/test_ad_library_client_url.py`

**Interfaces:**
- Consumes: `iter_videos_from_search_payload`, `parse_page_info`, `extract_graphql_payloads_from_html`, `AdVideo`
- Produces:
  - `build_ad_library_url(*, page_id: str, country: str = "ALL", active_status: str = "active", ad_type: str = "all", media_type: str = "video", sort_mode: str = "total_impressions", sort_direction: str = "desc") -> str`
  - `iter_ad_videos_playwright(*, page_id: str, limit: int | None, max_scroll_rounds: int, headless: bool, request_delay_min: float, request_delay_max: float, verbose: bool, country: str, active_status: str, media_type: str) -> Iterable[AdVideo]`

- [ ] **Step 1: Write failing URL tests**

`kyle-ad-library-video-transcripts/tests/test_ad_library_client_url.py`:

```python
from ad_library_client import build_ad_library_url


def test_build_ad_library_url_contains_page_and_video_filter():
    url = build_ad_library_url(page_id="116482854782233")
    assert "view_all_page_id=116482854782233" in url
    assert "media_type=video" in url
    assert "country=ALL" in url
    assert "active_status=active" in url
    assert "search_type=page" in url
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd kyle-ad-library-video-transcripts
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_ad_library_client_url.py -v
```

Expected: FAIL `ModuleNotFoundError: No module named 'ad_library_client'`.

- [ ] **Step 3: Implement client**

Create `kyle-ad-library-video-transcripts/ad_library_client.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import sys
import time
from typing import Any, Iterable
from urllib.parse import urlencode

from ad_library_parser import (
    AdVideo,
    extract_graphql_payloads_from_html,
    iter_videos_from_search_payload,
)


def build_ad_library_url(
    *,
    page_id: str,
    country: str = "ALL",
    active_status: str = "active",
    ad_type: str = "all",
    media_type: str = "video",
    sort_mode: str = "total_impressions",
    sort_direction: str = "desc",
) -> str:
    params = {
        "active_status": active_status,
        "ad_type": ad_type,
        "country": country,
        "is_targeted_country": "false",
        "media_type": media_type,
        "search_type": "page",
        "sort_data[mode]": sort_mode,
        "sort_data[direction]": sort_direction,
        "view_all_page_id": str(page_id).strip(),
    }
    return "https://www.facebook.com/ads/library/?" + urlencode(params)


def _sleep_jitter(min_seconds: float, max_seconds: float) -> None:
    lo = max(0.0, min_seconds)
    hi = max(lo, max_seconds)
    time.sleep(random.uniform(lo, hi))


def _payload_looks_like_ad_search(payload: dict[str, Any]) -> bool:
    raw = json.dumps(payload)
    return "search_results_connection" in raw or "ad_archive_id" in raw


def iter_ad_videos_playwright(
    *,
    page_id: str,
    limit: int | None,
    max_scroll_rounds: int = 80,
    headless: bool = True,
    request_delay_min: float = 1.0,
    request_delay_max: float = 3.0,
    verbose: bool = False,
    country: str = "ALL",
    active_status: str = "active",
    media_type: str = "video",
) -> Iterable[AdVideo]:
    from playwright.sync_api import sync_playwright

    url = build_ad_library_url(
        page_id=page_id,
        country=country,
        active_status=active_status,
        media_type=media_type,
    )
    seen: set[str] = set()
    yielded = 0
    captured: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = context.new_page()

        def on_response(response) -> None:
            try:
                if "/api/graphql/" not in response.url:
                    return
                # GraphQL may be JSON or text; ignore failures
                data = response.json()
            except Exception:
                return
            if isinstance(data, dict) and _payload_looks_like_ad_search(data):
                captured.append(data)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and _payload_looks_like_ad_search(item):
                        captured.append(item)

        page.on("response", on_response)
        if verbose:
            print(f"Ad Library navigate: {url}", file=sys.stderr, flush=True)
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        # Dismiss location / cookie dialogs if present (best-effort)
        for label in ("All", "Allow all cookies", "Decline optional cookies", "Close"):
            try:
                page.get_by_role("button", name=label).first.click(timeout=1500)
            except Exception:
                try:
                    page.get_by_text(label, exact=True).first.click(timeout=1500)
                except Exception:
                    pass
        page.wait_for_timeout(2500)
        html = page.content()
        for payload in extract_graphql_payloads_from_html(html):
            captured.append(payload)

        def drain() -> list[AdVideo]:
            nonlocal yielded
            out: list[AdVideo] = []
            while captured:
                payload = captured.pop(0)
                for item in iter_videos_from_search_payload(payload):
                    if item.mediaid in seen:
                        continue
                    seen.add(item.mediaid)
                    out.append(item)
            return out

        for item in drain():
            yielded += 1
            yield item
            if limit is not None and yielded >= limit:
                browser.close()
                return

        for round_i in range(max_scroll_rounds):
            if limit is not None and yielded >= limit:
                break
            page.mouse.wheel(0, 3500)
            _sleep_jitter(request_delay_min, request_delay_max)
            # Also re-parse DOM periodically — FB sometimes hydrates without graphql JSON parseable body
            if round_i % 5 == 4:
                for payload in extract_graphql_payloads_from_html(page.content()):
                    captured.append(payload)
            batch = drain()
            if verbose:
                print(
                    f"scroll_round={round_i + 1} new={len(batch)} total_seen={len(seen)}",
                    file=sys.stderr,
                    flush=True,
                )
            for item in batch:
                yielded += 1
                yield item
                if limit is not None and yielded >= limit:
                    break
            if not batch and round_i > 3:
                # stagnation: try one more deep scroll then stop if still empty
                page.mouse.wheel(0, 6000)
                _sleep_jitter(request_delay_min, request_delay_max)
                batch2 = drain()
                for item in batch2:
                    yielded += 1
                    yield item
                    if limit is not None and yielded >= limit:
                        break
                if not batch2:
                    break

        browser.close()
```

- [ ] **Step 4: Install Playwright browser and run URL tests**

Run:

```bash
cd kyle-ad-library-video-transcripts
source .venv/bin/activate
playwright install chromium
PYTHONPATH=. pytest tests/test_ad_library_client_url.py tests/test_ad_library_parser.py -v
```

Expected: PASS.

- [ ] **Step 5: Manual smoke (optional but recommended before Task 4)**

Run:

```bash
cd kyle-ad-library-video-transcripts
source .venv/bin/activate
PYTHONPATH=. python - <<'PY'
from ad_library_client import iter_ad_videos_playwright
n = 0
for item in iter_ad_videos_playwright(page_id="116482854782233", limit=3, verbose=True):
    print(item.mediaid, item.title[:60], item.video_url[:80])
    n += 1
print("count", n)
PY
```

Expected: prints 3 lines with numeric Library IDs and `fbcdn.net` video URLs. If 0, re-check country dialog dismissal / increase wait; do not proceed to wire CLI until this works.

- [ ] **Step 6: Commit**

```bash
git add kyle-ad-library-video-transcripts/ad_library_client.py \
  kyle-ad-library-video-transcripts/tests/test_ad_library_client_url.py
git commit -m "feat: Playwright Ad Library client with URL builder"
```

---

### Task 4: CLI skeleton — args, env, dry-run enumeration

**Files:**
- Create: `kyle-ad-library-video-transcripts/ad_library_video_transcripts.py` (enumeration + dry-run first; Redis/Whisper stubs deferred to Task 5–6)
- Create: `kyle-ad-library-video-transcripts/.env.example`

**Interfaces:**
- Consumes: `iter_ad_videos_playwright`, `AdVideo`
- Produces: CLI entrypoint `main(argv) -> int` with `--redis-mode local|producer|worker|requeue-skipped` (worker/redis bodies filled next tasks); dry-run works now

- [ ] **Step 1: Write `.env.example`**

```bash
# Numeric Facebook Page ID (Ad Library view_all_page_id)
AD_LIBRARY_PAGE_ID=116482854782233

# Optional full Ad Library URL (overrides page id + filters if set)
# AD_LIBRARY_URL=

SIMPLEPUSH_KEY=
SIMPLEPUSH_TITLE=Ad Library transcripts

# Run mode: local (default) = one machine, scrape+download+transcribe, no Redis.
# REDIS_MODE=local
# Optional Redis (only for producer/worker/requeue-skipped):
# REDIS_URL=redis://127.0.0.1:6379/0
# REDIS_STREAM=adlib:video:jobs
# REDIS_GROUP=transcribers

HUGGINGFACE_TOKEN=
HF_TOKEN=
DISABLE_DIARIZATION=1
```

- [ ] **Step 2: Implement CLI with dry-run path**

Implement `ad_library_video_transcripts.py` with:

- `load_env_files()` (copy pattern from Instagram script)
- `parse_args()` including:
  - `--page-id` (default env `AD_LIBRARY_PAGE_ID` or `116482854782233`)
  - `--ad-library-url` optional full URL override (if set, client should navigate to it instead of built URL — add `start_url` param to client in this task if missing)
  - `--media-type` default `video`
  - `--country` default `ALL`
  - `--active-status` default `active`
  - `--out`, `--download-dir`, `--transcript-dir`, `--metadata-dir`, `--checkpoint-file`, `--skip-log`
  - `--limit` / `-n`, `--resume`, `--verbose`, `--dry-run`
  - `--max-scroll-rounds` default `80`
  - `--headed` flag (Playwright headful)
  - `--request-delay-min/max`
  - Whisper flags (`--model-size` default `large-v3`, device, diarization, etc.)
  - `--redis-mode` choices `local|producer|worker|requeue-skipped`, **default `local`** (env `REDIS_MODE`, same helper as Instagram `_env_redis_mode_default`)
  - Redis flags only required when mode ≠ `local`: `--redis-url`, `--redis-stream` default `adlib:video:jobs`, etc.
- Help text for `--redis-mode` must state explicitly:
  - `local`: single-machine one-flow (scrape → download → Whisper); **no Redis**
  - `producer` / `worker`: optional queue-based scaling
- `main()` for dry-run (any mode that enumerates): call `iter_ad_videos_playwright`, print `mediaid title video_url`, return 0 — **no Redis connection**
- For non-dry-run `local`/`producer`/`worker`: temporarily raise `NotImplementedError` with clear message **only until Task 5/6**

Also update `iter_ad_videos_playwright` / `build` usage so `--ad-library-url` can pass `start_url: str | None = None` into the client (`page.goto(start_url or build_ad_library_url(...))`).

- [ ] **Step 3: Dry-run smoke**

Run:

```bash
cd kyle-ad-library-video-transcripts
source .venv/bin/activate
PYTHONPATH=. python ad_library_video_transcripts.py \
  --page-id 116482854782233 \
  --dry-run \
  -n 5 \
  --verbose
```

Expected: 5 lines of `mediaid` + title; exit 0.

- [ ] **Step 4: Commit**

```bash
git add kyle-ad-library-video-transcripts/ad_library_video_transcripts.py \
  kyle-ad-library-video-transcripts/.env.example
git commit -m "feat: Ad Library CLI dry-run enumeration"
```

---

### Task 5: Optional Redis producer + requeue-skipped (reuse Instagram job contract)

> Scaling path only. **`local` mode (Task 6) must work without any of this.** Do not make Redis a dependency of the default CLI path.

**Files:**
- Modify: `kyle-ad-library-video-transcripts/ad_library_video_transcripts.py`
- Reference implementation: `kyle-insta-video-transcripts/instagram_reels_transcripts.py` functions `run_redis_producer`, `run_redis_requeue_skipped`, `make_redis_client`, checkpoint helpers — **copy and adapt** (do not import across packages; keep sibling self-contained). Replace `ReelVideo` with `AdVideo` / `ad_video_job_dict`.

**Interfaces:**
- Consumes: `Iterable[AdVideo]` from client; Redis URL/stream
- Produces: `run_redis_producer(...) -> int`, `run_redis_requeue_skipped(...) -> int`; stream messages `{"job": "<json>"}` with Instagram-compatible keys

- [ ] **Step 1: Port helper utilities into the CLI module**

Copy (adapt names only where needed) from Instagram script into `ad_library_video_transcripts.py`:

- `sanitize_title`, `build_output_filename`, `ensure_dir`, `timestamp_now`
- `load_checkpoint`, `save_checkpoint`, `load_existing_transcript_mediaids`
- `append_jsonl`, `ProxyPool`, `resolve_proxy_urls`, download helpers (needed by worker in Task 6; can land now)
- `run_redis_producer` using `ad_video_job_dict` and default stream `adlib:video:jobs`
- `run_redis_requeue_skipped` reading `metadata/{mediaid}.json`

Producer loop body (canonical):

```python
payload = json.dumps(ad_video_job_dict(item), ensure_ascii=False)
client.xadd(stream, {"job": payload})
```

- [ ] **Step 2: Wire `--redis-mode producer`**

In `main()`, when `args.redis_mode == "producer"` and not dry-run:

```python
return run_redis_producer(
    args,
    iter_ad_videos_playwright(
        page_id=page_id,
        limit=args.limit,
        max_scroll_rounds=args.max_scroll_rounds,
        headless=not args.headed,
        request_delay_min=args.request_delay_min,
        request_delay_max=args.request_delay_max,
        verbose=args.verbose,
        country=args.country,
        active_status=args.active_status,
        media_type=args.media_type,
        start_url=ad_library_url_override,
    ),
    transcript_dir=transcript_dir,
    processed_mediaids=processed_mediaids,
)
```

- [ ] **Step 3: Manual producer smoke (local Redis)**

Run:

```bash
redis-cli ping   # expect PONG
cd kyle-ad-library-video-transcripts
source .venv/bin/activate
PYTHONPATH=. python ad_library_video_transcripts.py \
  --page-id 116482854782233 \
  --redis-mode producer \
  --redis-url redis://127.0.0.1:6379/0 \
  --redis-stream adlib:video:jobs \
  --redis-producer-dedupe \
  -n 3 \
  --verbose
```

Then:

```bash
redis-cli XLEN adlib:video:jobs
redis-cli XRANGE adlib:video:jobs - + COUNT 1
```

Expected: `XLEN` ≥ 1; job JSON contains `video_url` and `mediaid`.

- [ ] **Step 4: Commit**

```bash
git add kyle-ad-library-video-transcripts/ad_library_video_transcripts.py
git commit -m "feat: Redis producer for Ad Library video jobs"
```

---

### Task 6: Local one-flow mode + optional Redis worker (download, Whisper large-v3)

**Files:**
- Modify: `kyle-ad-library-video-transcripts/ad_library_video_transcripts.py`
- Reference: `kyle-insta-video-transcripts/instagram_reels_transcripts.py` — port `process_queue_item`, `run_redis_worker`, `load_whisper_model`, `transcribe_segments`, optional diarization, `build_transcript_text` (header labels can say `Library ID` instead of `Shortcode` but keep filename pattern `{title}__{mediaid}.txt`). Mirror Instagram `main()` **local** branch (enumerate → for-each `process_queue_item`) as the default path.

**Interfaces:**
- Consumes: `Iterable[AdVideo]` from Playwright (local) or Redis jobs via `ad_video_from_job_dict` (worker); Whisper model
- Produces: `videos/{mediaid}.mp4`, `metadata/{mediaid}.json`, `transcripts/*__{mediaid}.txt`, checkpoint updates; worker also `XACK`

- [ ] **Step 1: Port transcription pipeline**

Adapt Instagram `process_queue_item` to accept `AdVideo` (same fields). Sidecar metadata may include extras:

```python
{
  "mediaid": item.mediaid,
  "shortcode": item.shortcode,
  "title": item.title,
  "post_url": item.post_url,
  "video_url": item.video_url,
  "date_utc": item.date_utc,
  "source": "meta_ad_library",
  "video_file": str(video_path),
  "captured_at": timestamp_now(),
}
```

Transcript header:

```text
Title: ...
Library ID: ...
URL: https://www.facebook.com/ads/library/?id=...
Date UTC: ...
```

Default `--model-size large-v3`, `--disable-diarization` default from env (same as Instagram `.env.example`).

- [ ] **Step 2: Wire `local` (required) and `worker` (optional) in `main()`**

Mirror Instagram control flow **with local first**:

1. **`local` (default):** do **not** connect to Redis. Load Whisper once → `iter_ad_videos_playwright(...)` → for each item call `process_queue_item` → summary + optional Simplepush. Same as Instagram when `--redis-mode` is omitted/`local`.
2. **`worker`:** load Whisper → `run_redis_worker` (requires `--redis-url` / `REDIS_URL`).
3. Keep `producer` / `requeue-skipped` from Task 5.

Canonical local loop (must exist — not Redis-only):

```python
if args.redis_mode == "local":
    whisper_model = load_whisper_model(args)
    diarization_pipeline = None if args.disable_diarization else load_diarization_pipeline(args)
    queue = list(
        iter_ad_videos_playwright(
            page_id=page_id,
            limit=args.limit,
            max_scroll_rounds=args.max_scroll_rounds,
            headless=not args.headed,
            request_delay_min=args.request_delay_min,
            request_delay_max=args.request_delay_max,
            verbose=args.verbose,
            country=args.country,
            active_status=args.active_status,
            media_type=args.media_type,
            start_url=ad_library_url_override,
        )
    )
    for index, item in enumerate(queue, start=1):
        process_queue_item(
            item,
            label=f"[{index}/{len(queue)}]",
            args=args,
            whisper_model=whisper_model,
            diarization_pipeline=diarization_pipeline,
            proxy_pool=proxy_pool,
            video_dir=video_dir,
            transcript_dir=transcript_dir,
            metadata_dir=metadata_dir,
            checkpoint_path=checkpoint_path,
            processed_mediaids=processed_mediaids,
            skip_log_path=skip_log_path,
        )
    return 0  # or 1 if failures, matching Instagram
```

- [ ] **Step 3: End-to-end smoke — local one-flow (no Redis) — REQUIRED**

Run on a single machine (no `redis-server` needed):

```bash
cd kyle-ad-library-video-transcripts
source .venv/bin/activate
PYTHONPATH=. python ad_library_video_transcripts.py \
  --page-id 116482854782233 \
  --redis-mode local \
  --out ./output \
  -n 1 \
  --resume \
  --model-size large-v3 \
  --disable-diarization \
  --bypass-proxy \
  --verbose
```

Equivalent (default mode — omit `--redis-mode`):

```bash
PYTHONPATH=. python ad_library_video_transcripts.py \
  --page-id 116482854782233 \
  --out ./output \
  -n 1 \
  --resume \
  --model-size large-v3 \
  --disable-diarization \
  --verbose
```

Expected:

- Process scrapes Ad Library, downloads one MP4, writes one transcript — all in one command
- No Redis connection attempted (no `REDIS_URL` required)
- `output/videos/<ad_archive_id>.mp4` exists
- `output/transcripts/*__<ad_archive_id>.txt` exists
- `output/checkpoint.json` updated

**Note:** first `large-v3` load may take many minutes (HF download). For a faster gate, temporarily use `--model-size small` then re-run once with `large-v3`.

- [ ] **Step 4: Optional smoke — Redis worker (scaling path only)**

Only if validating queue mode. Terminal A: producer `-n 1`. Terminal B:

```bash
PYTHONPATH=. python ad_library_video_transcripts.py \
  --redis-mode worker \
  --redis-url redis://127.0.0.1:6379/0 \
  --redis-stream adlib:video:jobs \
  --redis-group transcribers \
  --redis-max-jobs 1 \
  --out ./output \
  --resume \
  --model-size large-v3 \
  --disable-diarization \
  --verbose
```

Expected: transcript written; Redis message ACKed.

- [ ] **Step 5: Commit**

```bash
git add kyle-ad-library-video-transcripts/ad_library_video_transcripts.py
git commit -m "feat: local one-flow Whisper path and optional Redis worker"
```

---

### Task 7: README + ops examples

**Files:**
- Create: `kyle-ad-library-video-transcripts/README.md`
- Optional modify: `kyle-insta-video-transcripts/README.md` (one short “See also” link only)

**Interfaces:**
- Consumes: working CLI from Tasks 4–6
- Produces: operator docs

- [ ] **Step 1: Write README**

Include sections **in this order**:

1. Install (`venv`, `pip install -r requirements.txt`, `playwright install chromium`, `ffmpeg`)
2. Dry-run Hormozi page
3. **Quick Start — single machine, one flow (no Redis)** — default `--redis-mode local`
4. Optional Redis producer / worker topology (stream `adlib:video:jobs`) — scaling only
5. Warning: CDN URLs expire; local mode downloads immediately; Redis workers must start soon after producer
6. Warning: `doc_id` / UI changes may break capture — verbose scroll logs + fixture tests for parser

Mode table (must appear near top of usage):

| Mode | Redis? | What it does |
|------|--------|--------------|
| `local` (default) | No | One process: scrape Ad Library → download → Whisper → write transcripts |
| `producer` | Yes | Scrape and `XADD` jobs only |
| `worker` | Yes | Consume stream and transcribe |
| `requeue-skipped` | Yes | Re-enqueue from `skipped.jsonl` + metadata |

**Primary example (local one-flow):**

```bash
python ad_library_video_transcripts.py \
  --page-id 116482854782233 \
  --out ./output \
  -n 5 \
  --resume \
  --model-size large-v3 \
  --disable-diarization \
  --verbose
```

Optional Redis producer (only when scaling):

```bash
python ad_library_video_transcripts.py \
  --page-id 116482854782233 \
  --redis-mode producer \
  --redis-url "$REDIS_URL" \
  --redis-stream adlib:video:jobs \
  --redis-producer-dedupe \
  --resume \
  --out /mnt/efs/adlib-output \
  --verbose
```

Optional worker: same as Instagram worker but script name + stream `adlib:video:jobs`.

- [ ] **Step 2: Commit**

```bash
git add kyle-ad-library-video-transcripts/README.md
git commit -m "docs: Ad Library video transcripts runbook"
```

---

## Self-review

**1. Spec coverage**

| Requirement | Task |
|-------------|------|
| Research Ad Library HTML/DevTools video fields | Research notes + parser fixtures |
| Parser for videos | Tasks 1–2 |
| **Single-machine one-flow without Redis (`local`)** | Task 6 Step 2–3 (default mode); Task 7 README primary |
| Download videos | Task 6 (`download_video`) |
| Queue metadata to Redis stream (optional) | Task 5 |
| Consume stream + Whisper large-v3 (optional) | Task 6 Step 4 |
| Similar flow to Instagram package | Tasks 4–7 (modes, dirs, checkpoint, resume) |
| Target Hormozi library URL/page id | Defaults in client/CLI/README |

**2. Placeholder scan:** No TBD/TODO steps; code and commands are concrete. Client dialog dismissal is best-effort (explicit). HTML extract is fallback if GraphQL JSON intercept fails.

**3. Type consistency:** `AdVideo` fields and `ad_video_job_dict` keys stay aligned with Instagram worker contract across Tasks 2–6. Stream default `adlib:video:jobs` consistent in env, CLI, README.

**Gaps intentionally out of scope (YAGNI):** Apify/ScrapeCreators paid APIs; official Meta Ad Library API (no commercial creatives); downloading image-only ads; shared refactor extracting common Redis/Whisper module from Instagram (can be a later cleanup).

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-16-ad-library-video-transcripts.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
