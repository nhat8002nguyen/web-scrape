#!/usr/bin/env python3
"""
Connect to Appium, scrape Contacts list, export CSV/Excel.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.driver_factory import create_driver
from src.export.csv_exporter import write_csv, write_excel
from src.scrapers.contacts_demo import scrape_contacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo Contacts scraper via Appium")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=100,
        help="Maximum contacts to collect (default: 100)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "output" / "contacts.csv",
        help="CSV output path",
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=None,
        help="Optional Excel output path",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Checkpoint JSON path (default: output/checkpoint.json)",
    )
    parser.add_argument(
        "--reset-checkpoint",
        action="store_true",
        help="Delete checkpoint before run",
    )
    args = parser.parse_args()

    out_path = args.out if args.out.is_absolute() else PROJECT_ROOT / args.out
    checkpoint = args.checkpoint
    if checkpoint is None:
        checkpoint = PROJECT_ROOT / "output" / "checkpoint.json"
    elif not checkpoint.is_absolute():
        checkpoint = PROJECT_ROOT / checkpoint

    if args.reset_checkpoint and checkpoint.exists():
        checkpoint.unlink()

    driver = None
    try:
        print("Connecting to Appium...")
        driver = create_driver()
        print("Session started. Scraping contacts...")
        rows = scrape_contacts(
            driver,
            max_rows=args.max_rows,
            checkpoint_path=checkpoint,
        )
        count = write_csv(rows, out_path)
        print(f"Wrote {count} rows to {out_path}")

        if args.excel:
            excel_path = (
                args.excel
                if args.excel.is_absolute()
                else PROJECT_ROOT / args.excel
            )
            xcount = write_excel(rows, excel_path)
            print(f"Wrote {xcount} rows to {excel_path}")

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            "\nChecklist:\n"
            "  1. Emulator running: adb devices\n"
            "  2. Appium running: appium\n"
            "  3. APPIUM_URL in .env matches server\n"
            "  4. Update appPackage/appActivity if Contacts fails to open",
            file=sys.stderr,
        )
        sys.exit(1)
    finally:
        if driver is not None:
            driver.quit()
            print("Session closed.")


if __name__ == "__main__":
    main()
