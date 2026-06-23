import csv
from pathlib import Path
from typing import Iterable

FIELDNAMES = [
    "first_name",
    "last_name",
    "job_title",
    "company",
    "linkedin_url",
    "masterclass_attendance",
]


def write_csv(rows: Iterable[dict], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row_list = list(rows)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in row_list:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
    return len(row_list)


def write_excel(rows: Iterable[dict], output_path: Path) -> int:
    import pandas as pd

    output_path.parent.mkdir(parents=True, exist_ok=True)
    row_list = list(rows)
    df = pd.DataFrame(row_list, columns=FIELDNAMES)
    df.to_excel(output_path, index=False)
    return len(row_list)
