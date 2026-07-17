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
