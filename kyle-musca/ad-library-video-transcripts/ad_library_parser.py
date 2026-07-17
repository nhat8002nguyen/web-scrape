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


def extract_graphql_payloads_from_html(html: str) -> list[dict[str, Any]]:
    """Best-effort: find search_results_connection blobs inside page HTML."""
    if not html or "search_results_connection" not in html:
        return _payloads_from_raw_ad_archive_chunks(html)
    payloads: list[dict[str, Any]] = []
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
            video_url = unquote(
                hd.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
            )
        elif sd:
            video_url = unquote(
                sd.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
            )
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
