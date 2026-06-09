from __future__ import annotations

import csv
from pathlib import Path

FIELDS = ["student_id", "supervisor_id", "institution", "area", "sent_at", "outcome"]


def read_outcomes(csv_path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for r in reader:
            row = {k: (r.get(k) or "").strip() for k in FIELDS}
            if row["supervisor_id"]:
                rows.append(row)
    return rows
