#!/usr/bin/env python3
"""Build a smaller plain-text bundle from Fathom per-meeting .txt exports (not compression)."""

import re
import sys
from pathlib import Path

SKIP_NAMES = frozenset(
    {
        "all_transcripts_consolidated.txt",
        "all_transcripts_compact.txt",
        "all_transcripts_compact_merged.txt",
    }
)

TS_PREFIX = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s+")
EMAIL_IN_PARENS = re.compile(r"\s*\([^)]*@[^)]*\)")
SPEAKER_LINE = re.compile(r"^([^:]+):\s*(.*)$")


def merge_adjacent_speaker_lines(body_lines: list[str]) -> list[str]:
    out: list[str] = []
    current: str | None = None
    parts: list[str] = []
    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            if current is not None:
                out.append(f"{current}: {' '.join(parts)}")
                current, parts = None, []
            continue
        m = SPEAKER_LINE.match(stripped)
        if not m:
            if current is not None:
                out.append(f"{current}: {' '.join(parts)}")
                current, parts = None, []
            out.append(stripped)
            continue
        speaker, text = m.group(1), m.group(2)
        if speaker == current:
            if text:
                parts.append(text)
        else:
            if current is not None:
                out.append(f"{current}: {' '.join(parts)}")
            current = speaker
            parts = [text] if text else []
    if current is not None:
        out.append(f"{current}: {' '.join(parts)}")
    return out


def compact_one(raw: str, index: int, total: int, merge_speakers: bool) -> str:
    lines = raw.replace("\r\n", "\n").split("\n")
    meta: dict[str, str] = {}
    transcript_start = 0
    for idx, line in enumerate(lines):
        if line.startswith("Meeting:"):
            meta["meeting"] = line[len("Meeting:") :].strip()
        elif line.startswith("Date:"):
            meta["date"] = line[len("Date:") :].strip()
        elif line.startswith("Recording ID:"):
            meta["id"] = line[len("Recording ID:") :].strip()
        elif line.startswith("Participants:"):
            meta["participants"] = line[len("Participants:") :].strip()
        elif line.strip() == "--- TRANSCRIPT ---":
            transcript_start = idx + 1
            break

    meeting = meta.get("meeting", "")
    date = meta.get("date", "")
    rec_id = meta.get("id", "")
    header = f"\n>>> {index}/{total} | {meeting} | {date}"
    if rec_id:
        header += f" | id:{rec_id}"
    header += "\n"

    participants = meta.get("participants", "")
    if participants:
        participants = EMAIL_IN_PARENS.sub("", participants)
        participants = re.sub(r",\s*,", ", ", participants)
        participants = participants.strip().strip(",")
        if participants:
            header += f"People: {participants}\n"

    body_lines: list[str] = []
    for line in lines[transcript_start:]:
        s = line.strip()
        if not s:
            continue
        body_lines.append(TS_PREFIX.sub("", line).rstrip())

    if merge_speakers:
        body_lines = merge_adjacent_speaker_lines(body_lines)

    text_body = "\n".join(body_lines)
    return f"{header.rstrip()}\n\n{text_body}\n"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    merge_speakers = "--merge-speakers" in sys.argv[1:] or "-m" in sys.argv[1:]

    if len(args) >= 2:
        input_dir = Path(args[0]).resolve()
        output_path = Path(args[1]).resolve()
    elif len(args) == 1:
        input_dir = Path(args[0]).resolve()
        script_dir = Path(__file__).resolve().parent
        default_name = (
            "ALL_TRANSCRIPTS_COMPACT_MERGED.txt"
            if merge_speakers
            else "ALL_TRANSCRIPTS_COMPACT.txt"
        )
        output_path = input_dir / default_name
    else:
        script_dir = Path(__file__).resolve().parent
        input_dir = script_dir / "Fathom_Transcripts_2026-05-08_07_23_25"
        output_path = (
            input_dir / "ALL_TRANSCRIPTS_COMPACT_MERGED.txt"
            if merge_speakers
            else input_dir / "ALL_TRANSCRIPTS_COMPACT.txt"
        )

    if not input_dir.is_dir():
        print(f"Directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    on_lower = output_path.name.lower()
    txt_files = sorted(
        p
        for p in input_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".txt"
        and p.name.lower() != on_lower
        and p.name.lower() not in SKIP_NAMES
    )

    total = len(txt_files)
    if total == 0:
        print("No .txt files found.", file=sys.stderr)
        sys.exit(1)

    prelude = (
        "COMPACT TRANSCRIPT BUNDLE\n"
        f"Meetings: {total}\n"
        f"Folder: {input_dir.name}\n"
        "(Timestamps and long Fathom metadata removed; plain UTF-8 text only.)"
        + (" Consecutive turns by the same speaker merged." if merge_speakers else "")
        + "\n\n"
    )

    chunks: list[str] = [prelude]
    for i, path in enumerate(txt_files, start=1):
        raw = path.read_text(encoding="utf-8", errors="replace")
        chunks.append(compact_one(raw, i, total, merge_speakers))
        chunks.append("\n")

    output_path.write_text("".join(chunks).rstrip() + "\n", encoding="utf-8")
    original_bytes = sum(p.stat().st_size for p in txt_files)
    compact_bytes = output_path.stat().st_size
    pct = 100.0 * compact_bytes / original_bytes if original_bytes else 0.0
    print(f"Wrote {total} meetings → {output_path}")
    print(f"Size: {compact_bytes:,} bytes ({pct:.1f}% of sum of source .txt files)")


if __name__ == "__main__":
    main()
