"""CSV and JSON boundaries for the historical store."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.common import HISTORY_COLUMNS, clean


def read_source_csv(path: Path) -> list[dict]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    return frame.to_dict(orient="records")


def read_history(path: Path) -> dict[str, dict]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    records: dict[str, dict] = {}
    for row in frame.to_dict(orient="records"):
        key = clean(row.get("job_key"))
        if not key:
            continue
        records[key] = {column: clean(row.get(column)) for column in HISTORY_COLUMNS}
    return records


def write_history(path: Path, records: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for key in sorted(records):
        record = records[key]
        rows.append({column: clean(record.get(column)) for column in HISTORY_COLUMNS})
    frame = pd.DataFrame(rows, columns=HISTORY_COLUMNS)
    temporary = path.with_suffix(path.suffix + ".partial")
    frame.to_csv(temporary, index=False, encoding="utf-8")
    temporary.replace(path)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
