#!/usr/bin/env python3
"""Consolidate YouTube channel transcript .txt files into one LLM-readable file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SEPARATOR = "=" * 79
_VIDEO_ID_SUFFIX_RE = re.compile(r"__([A-Za-z0-9_-]{11})\.txt$")


def parse_transcript_filename(path: Path) -> tuple[str, str]:
    match = _VIDEO_ID_SUFFIX_RE.search(path.name)
    if not match:
        return path.stem, ""
    video_id = match.group(1)
    title = path.name[: match.start()]
    return title, video_id


def youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def non_empty_line_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def format_video_block(title: str, video_id: str, body: str) -> str:
    lines = [
        SEPARATOR,
        "=",
        f"VIDEO: {title}",
        SEPARATOR,
        "=",
    ]
    if video_id:
        lines.append(f"Video ID: {video_id}")
        lines.append(f"URL: {youtube_watch_url(video_id)}")
    lines.extend(["", "--- Transcript ---", body.rstrip("\n")])
    return "\n".join(lines)


def consolidate_folder(folder_path: Path, output_path: Path | None = None) -> Path:
    if not folder_path.is_dir():
        raise ValueError(f"Not a directory: {folder_path}")

    channel_name = folder_path.name
    if output_path is None:
        output_path = folder_path / f"{channel_name}_consolidated.txt"

    kept: list[tuple[str, str]] = []
    removed = 0
    total = 0

    for transcript_path in sorted(folder_path.glob("*.txt")):
        if transcript_path.resolve() == output_path.resolve():
            continue
        if transcript_path.name.endswith("_consolidated.txt"):
            continue
        total += 1
        raw = transcript_path.read_text(encoding="utf-8", errors="replace")
        body = raw.replace("\r\n", "\n").strip("\n")
        if non_empty_line_count(body) < 3:
            removed += 1
            continue

        title, video_id = parse_transcript_filename(transcript_path)
        kept.append((video_id or title.lower(), format_video_block(title, video_id, body)))

    kept.sort(key=lambda item: item[0])
    header = "\n".join(
        [
            f"# Consolidated YouTube Transcripts: {channel_name}",
            f"# Source folder: {channel_name}/",
            "# Filter: exclude empty transcripts with fewer than 3 non-empty lines",
            f"# Kept: {len(kept)} videos | Removed: {removed} of {total} total",
            "",
        ]
    )
    body = "\n\n".join(block for _, block in kept)
    output_path.write_text(
        header + body + ("\n" if body else ""),
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consolidate YouTube transcript .txt files into one LLM-readable file.",
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="Channel output folder containing .txt transcript files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: FOLDER/FOLDER_consolidated.txt).",
    )
    args = parser.parse_args()

    folder_path = args.folder.resolve()
    if not folder_path.is_dir():
        print(f"Folder not found: {folder_path}", file=sys.stderr)
        sys.exit(1)

    output_path = consolidate_folder(
        folder_path,
        args.output.resolve() if args.output else None,
    )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
