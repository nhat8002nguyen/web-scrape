#!/usr/bin/env python3
"""
Seed demo contacts on the Android emulator via the contacts content provider.

Requires: emulator running, adb on PATH.
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PERMISSIONS = [
    "android.permission.READ_CONTACTS",
    "android.permission.WRITE_CONTACTS",
    "android.permission.POST_NOTIFICATIONS",
]


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def _adb_devices() -> list[str]:
    result = _run(["adb", "devices"])
    lines = result.stdout.strip().splitlines()[1:]
    return [line.split()[0] for line in lines if "\tdevice" in line]


def _grant_permissions() -> None:
    for permission in PERMISSIONS:
        _run(
            [
                "adb",
                "shell",
                "pm",
                "grant",
                "com.google.android.contacts",
                permission,
            ],
            check=False,
        )


def _latest_raw_contact_id() -> int | None:
    result = _run(
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
    for line in result.stdout.splitlines():
        if "_id=" in line:
            ids.append(int(line.split("_id=")[-1].strip()))
    return max(ids) if ids else None


def _insert_contact(name: str, company: str, title: str, linkedin: str) -> bool:
    _run(
        [
            "adb",
            "shell",
            "content",
            "insert",
            "--uri",
            "content://com.android.contacts/raw_contacts",
            "--bind",
            "account_type:s:com.android.localphone",
            "--bind",
            "account_name:s:Phone",
        ]
    )
    raw_id = _latest_raw_contact_id()
    if raw_id is None:
        return False

    note = f"Company: {company}; Title: {title}; LinkedIn: {linkedin}"
    inserts = [
        (
            "content://com.android.contacts/data",
            [
                ("raw_contact_id", "i", str(raw_id)),
                ("mimetype", "s", "vnd.android.cursor.item/name"),
                ("data1", "s", name),
            ],
        ),
        (
            "content://com.android.contacts/data",
            [
                ("raw_contact_id", "i", str(raw_id)),
                ("mimetype", "s", "vnd.android.cursor.item/note"),
                ("data1", "s", note),
            ],
        ),
    ]

    for uri, binds in inserts:
        parts = ["content", "insert", "--uri", uri]
        for column, kind, value in binds:
            if kind == "i":
                parts.append(f"--bind {column}:{kind}:{value}")
            else:
                safe = value.replace("'", "\\'")
                parts.append(f"--bind {column}:{kind}:'{safe}'")
        shell_cmd = " ".join(parts)
        _run(["adb", "shell", shell_cmd])
    return True


def seed_contacts(count: int) -> None:
    devices = _adb_devices()
    if not devices:
        print("No adb device found. Start an emulator first.", file=sys.stderr)
        sys.exit(1)

    _grant_permissions()

    companies = ["Acme GmbH", "FlexHome AG", "BauTech", "Urban Living", "PropTech"]
    titles = ["Manager", "Architect", "Consultant", "Engineer", "Director"]
    created = 0

    for i in range(1, count + 1):
        company = companies[i % len(companies)]
        title = titles[i % len(titles)]
        linkedin = f"https://www.linkedin.com/in/demo-contact-{i}"
        name = f"Demo Contact {i:03d}"
        if _insert_contact(name, company, title, linkedin):
            created += 1

    print(f"\nInserted {created} contacts.")
    print("Open Contacts on the emulator to confirm, then run the scraper.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo contacts on emulator")
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of contacts to generate (default: 50)",
    )
    args = parser.parse_args()
    seed_contacts(args.count)


if __name__ == "__main__":
    main()
