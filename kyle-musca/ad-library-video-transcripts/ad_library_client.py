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
    start_url: str | None = None,
) -> Iterable[AdVideo]:
    from playwright.sync_api import sync_playwright

    url = (start_url or "").strip() or build_ad_library_url(
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
