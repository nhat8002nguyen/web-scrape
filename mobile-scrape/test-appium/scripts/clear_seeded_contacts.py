#!/usr/bin/env python3
"""
Remove contacts created by seed_contacts.py (local Phone account).

Also clears scraper checkpoint and CSV output for a clean reseed.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

# Must match seed_contacts.py
ACCOUNT_TYPE = "com.android.localphone"
ACCOUNT_NAME = "Phone"


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def _adb_devices() -> list[str]:
    result = _run(["adb", "devices"])
    lines = result.stdout.strip().splitlines()[1:]
    return [line.split()[0] for line in lines if "\tdevice" in line]


def clear_seeded_contacts(keep_first_account: bool = True) -> None:
    if not _adb_devices():
        print("No adb device found. Start the emulator first.", file=sys.stderr)
        sys.exit(1)

    if keep_first_account:
        result = _run(
            [
                "adb",
                "shell",
                "content",
                "delete",
                "--uri",
                "content://com.android.contacts/raw_contacts",
                "--where",
                "_id>1",
            ],
            check=False,
        )
    else:
        where = (
            f"account_type='{ACCOUNT_TYPE}' AND account_name='{ACCOUNT_NAME}'"
        )
        result = _run(
            [
                "adb",
                "shell",
                "content",
                "delete",
                "--uri",
                "content://com.android.contacts/raw_contacts",
                "--where",
                where,
            ],
            check=False,
        )
    if result.returncode != 0:
        # Fallback: delete by id when --where is mangled by the device shell
        query = _run(
            [
                "adb",
                "shell",
                "content",
                "query",
                "--uri",
                "content://com.android.contacts/raw_contacts",
                "--projection",
                "_id",
            ]
        )
        ids = []
        for line in query.stdout.splitlines():
            if "_id=" in line:
                ids.append(int(line.split("_id=")[-1].strip()))
        for raw_id in sorted(ids, reverse=True):
            if keep_first_account and raw_id <= 1:
                continue
            _run(
                [
                    "adb",
                    "shell",
                    f"content delete --uri content://com.android.contacts/raw_contacts --where _id={raw_id}",
                ],
                check=False,
            )

    for path in (OUTPUT_DIR / "checkpoint.json", OUTPUT_DIR / "contacts.csv"):
        if path.exists():
            path.unlink()
            print(f"Removed {path}")

    print(
        "\nDemo/test contacts removed.\n"
        "Re-seed with: python scripts/seed_contacts.py --count 50"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clear seeded demo contacts")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Delete only local Phone account rows (not _id>1 wipe)",
    )
    args = parser.parse_args()
    clear_seeded_contacts(keep_first_account=not args.all)
