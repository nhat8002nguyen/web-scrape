#!/usr/bin/env python3
"""Remove short transcript files and rebuild a consolidated export."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADER_KEYS = frozenset({"Title", "Media ID", "Shortcode", "URL", "Date UTC"})
SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")


def parse_transcript(path: Path) -> tuple[dict[str, str], str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    meta: dict[str, str] = {}
    body_start = 0

    for i, line in enumerate(lines):
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            if key in HEADER_KEYS:
                meta[key] = value.strip()
                body_start = i + 1
                continue
        if meta:
            break

    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1

    body = "\n".join(lines[body_start:]).strip()
    return meta, body


def non_empty_line_count(body: str) -> int:
    return sum(1 for line in body.splitlines() if line.strip())


def sentence_count(body: str) -> int:
    return sum(1 for part in SENTENCE_SPLIT_RE.split(body) if part.strip())


def is_long_enough(body: str, min_lines: int) -> bool:
    if not body.strip():
        return False
    return (
        non_empty_line_count(body) >= min_lines
        or sentence_count(body) >= min_lines
    )


def consolidate(transcripts_dir: Path, out_path: Path, min_lines: int) -> int:
    entries: list[tuple[dict[str, str], str]] = []

    for path in sorted(transcripts_dir.glob("*.txt")):
        meta, body = parse_transcript(path)
        if not is_long_enough(body, min_lines):
            continue
        entries.append((meta, body))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as out:
        for idx, (meta, body) in enumerate(entries, 1):
            title = meta.get("Title") or "Untitled"
            url = meta.get("URL", "")
            date = meta.get("Date UTC", "")

            out.write(f"{'=' * 80}\n")
            out.write(f"[{idx}] {title}\n")
            if url:
                out.write(f"URL: {url}\n")
            if date:
                out.write(f"Date UTC: {date}\n")
            out.write("\n")
            out.write(body)
            out.write("\n\n")

    return len(entries)


def filter_short_transcripts(transcripts_dir: Path, min_lines: int, dry_run: bool) -> tuple[int, int]:
    removed = 0
    kept = 0

    for path in sorted(transcripts_dir.glob("*.txt")):
        _, body = parse_transcript(path)
        if is_long_enough(body, min_lines):
            kept += 1
            continue
        removed += 1
        if dry_run:
            print(f"would remove: {path.name} ({non_empty_line_count(body)} lines, {sentence_count(body)} sentences)")
        else:
            path.unlink()

    return kept, removed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete transcript .txt files shorter than N lines/sentences and rebuild consolidated export.",
    )
    parser.add_argument(
        "data_dir",
        type=Path,
        help="Profile output dir containing transcripts/ (e.g. output/_biggcal)",
    )
    parser.add_argument(
        "--min-lines",
        type=int,
        default=3,
        help="Minimum non-empty body lines or sentences to keep (default: 3)",
    )
    parser.add_argument(
        "--consolidated-name",
        default=None,
        help="Consolidated output filename (default: <profile>-transcripts-consolidated.txt)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print files that would be removed without deleting or rewriting consolidated output",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    transcripts_dir = data_dir / "transcripts"
    if not transcripts_dir.is_dir():
        print(f"error: transcripts dir not found: {transcripts_dir}", file=sys.stderr)
        return 1

    profile = data_dir.name
    consolidated_name = args.consolidated_name or f"{profile}-transcripts-consolidated.txt"
    out_path = data_dir / consolidated_name

    kept, removed = filter_short_transcripts(transcripts_dir, args.min_lines, args.dry_run)

    if args.dry_run:
        print(f"\ndry-run: would remove {removed}, keep {kept}")
        return 0

    written = consolidate(transcripts_dir, out_path, args.min_lines)
    print(f"removed {removed} short transcript file(s)")
    print(f"kept {kept} transcript file(s)")
    print(f"wrote {written} entries -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
