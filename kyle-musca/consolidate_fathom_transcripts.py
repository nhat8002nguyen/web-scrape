#!/usr/bin/env python3
"""Concatenate all Fathom-export .txt transcripts into one file with clear dividers."""

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) >= 3:
        input_dir = Path(sys.argv[1]).resolve()
        output_path = Path(sys.argv[2]).resolve()
    else:
        script_dir = Path(__file__).resolve().parent
        input_dir = script_dir / "Fathom_Transcripts_2026-05-08_07_23_25"
        output_path = input_dir / "ALL_TRANSCRIPTS_CONSOLIDATED.txt"

    if not input_dir.is_dir():
        print(f"Directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_name_lower = output_path.name.lower()
    txt_files = sorted(
        p
        for p in input_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".txt"
        and p.name.lower() != output_name_lower
    )

    total = len(txt_files)
    if total == 0:
        print("No .txt files found.", file=sys.stderr)
        sys.exit(1)

    def divider_block(index: int, total: int, name: str) -> str:
        bar = "#" * 80
        return f"\n{bar}\n# TRANSCRIPT {index} OF {total}\n# FILE: {name}\n{bar}\n\n"

    sep = "=" * 80

    header = "\n".join(
        [
            sep,
            "CONSOLIDATED TRANSCRIPT EXPORT",
            f"Source directory: {input_dir}",
            f"Transcript files included: {total}",
            sep,
            "",
        ]
    )
    lines_out: list[str] = [header]

    for i, path in enumerate(txt_files, start=1):
        label = path.stem.replace("_", " ")
        body = path.read_text(encoding="utf-8", errors="replace")
        if body and not body.endswith("\n"):
            body += "\n"
        lines_out.append(divider_block(i, total, path.name))
        lines_out.append(body)
        lines_out.append("\n")
        lines_out.append(sep + "\n")
        lines_out.append(f"END OF TRANSCRIPT {i} OF {total} — {label}\n")
        lines_out.append(sep + "\n")
        lines_out.append("\n")

    output_path.write_text("".join(lines_out), encoding="utf-8")
    print(f"Wrote {total} transcripts to {output_path}")


if __name__ == "__main__":
    main()
