"""Download, validate, update history, classify, and write the dashboard."""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from scripts.build_dashboard_data import build_payload, coverage_start_from
from scripts.classify_jobs import classify_records
from scripts.common import (
    DOCS_DATA,
    DOCS_META,
    HISTORY_CSV,
    PROCESSED_CSV,
    RAW_CSV,
    SOURCE_URL,
    STATE_JSON,
    load_yaml,
    sha256_file,
    today_sgt,
)
from scripts.download_jobs import download_jobs
from scripts.io_store import read_history, read_json, read_source_csv, write_history, write_json
from scripts.update_history import apply_snapshot, finalize_records
from scripts.validate_source import ValidationError, validate_rows


def run(url: str = SOURCE_URL, run_date: date | None = None) -> int:
    configs = {
        "procurement": load_yaml("procurement_taxonomy.yml"),
        "sector": load_yaml("sector_taxonomy.yml"),
        "experience": load_yaml("experience_rules.yml"),
        "pcf": load_yaml("pcf_competencies.yml"),
        "validation": load_yaml("validation.yml"),
    }
    run_day = run_date or today_sgt()
    print(f"Run date (Asia/Singapore): {run_day.isoformat()}")
    download = download_jobs(url, RAW_CSV)
    print(
        f"Downloaded {download['bytes']} bytes "
        f"sha256={download['sha256'][:12]} last-modified={download['lastModified'] or 'unknown'}"
    )
    validation = configs["validation"]
    if download["bytes"] < int(validation["min_bytes"]):
        raise ValidationError(
            f"Downloaded file is {download['bytes']} bytes, below {validation['min_bytes']}."
        )
    rows = read_source_csv(RAW_CSV)
    previous = read_json(STATE_JSON)
    previous_rows = previous.get("sourceRows")
    allow_drop = os.environ.get("ALLOW_ROW_DROP", "").lower() in {"1", "true", "yes"}
    checked = validate_rows(
        rows,
        required_columns=validation["required_columns"],
        min_rows=int(validation["min_rows"]),
        previous_rows=int(previous_rows) if previous_rows else None,
        max_drop_ratio=float(validation["max_drop_ratio"]),
        allow_row_drop=allow_drop,
    )
    if previous.get("sha256") == download["sha256"] and previous.get("throughDate") == run_day.isoformat():
        print("No material change: this source snapshot was already processed today.")
        return 0

    records = read_history(HISTORY_CSV)
    stats = apply_snapshot(records, rows, run_day)
    class_stats = classify_records(records, configs)
    coverage = coverage_start_from(records)
    finalize_records(records, run_day, coverage)
    _write_outputs(
        records,
        download=download,
        source_rows=checked["rows"],
        run_day=run_day,
        coverage=coverage,
        snapshot_stats=stats,
        class_stats=class_stats,
        history_source=previous.get("historySource") or "current-snapshot",
        snapshots_used=previous.get("snapshotsUsed"),
        snapshots_skipped=previous.get("snapshotsSkipped"),
    )
    _print_stats(checked["rows"], stats, class_stats, len(records))
    return 0


def write_from_records(
    records: dict[str, dict],
    *,
    run_day: date,
    history_source: str,
    source_rows: int,
    download: dict,
    snapshot_stats: dict,
    snapshots_used: int | None = None,
    snapshots_skipped: int | None = None,
) -> None:
    configs = {
        "procurement": load_yaml("procurement_taxonomy.yml"),
        "sector": load_yaml("sector_taxonomy.yml"),
        "experience": load_yaml("experience_rules.yml"),
        "pcf": load_yaml("pcf_competencies.yml"),
    }
    class_stats = classify_records(records, configs)
    coverage = coverage_start_from(records)
    finalize_records(records, run_day, coverage)
    _write_outputs(
        records,
        download=download,
        source_rows=source_rows,
        run_day=run_day,
        coverage=coverage,
        snapshot_stats=snapshot_stats,
        class_stats=class_stats,
        history_source=history_source,
        snapshots_used=snapshots_used,
        snapshots_skipped=snapshots_skipped,
    )
    _print_stats(source_rows, snapshot_stats, class_stats, len(records))


def _write_outputs(
    records: dict[str, dict],
    *,
    download: dict,
    source_rows: int,
    run_day: date,
    coverage: date | None,
    snapshot_stats: dict,
    class_stats: dict,
    history_source: str,
    snapshots_used: int | None,
    snapshots_skipped: int | None,
) -> None:
    write_history(HISTORY_CSV, records)
    procurement_rows = {
        key: value
        for key, value in records.items()
        if value.get("procurementRelevant") == "true"
    }
    write_history(PROCESSED_CSV, procurement_rows)
    metadata = {
        "processedThrough": run_day.isoformat(),
        "processedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sourceUrl": download.get("url", ""),
        "sourceSha256": download.get("sha256", ""),
        "sourceLastModified": download.get("lastModified", ""),
        "sourceRows": source_rows,
        "historySource": history_source,
        "coverageStart": coverage.isoformat() if coverage else "",
        "coverageEnd": run_day.isoformat(),
        "snapshotsUsed": snapshots_used,
        "snapshotsSkipped": snapshots_skipped,
        "runStats": {"snapshot": snapshot_stats, "classification": class_stats},
    }
    payload = build_payload(records, metadata=metadata)
    write_json(DOCS_DATA, payload)
    write_json(DOCS_META, payload["metadata"])
    write_json(
        STATE_JSON,
        {
            "sha256": download.get("sha256", ""),
            "throughDate": run_day.isoformat(),
            "sourceRows": source_rows,
            "historySource": history_source,
            "snapshotsUsed": snapshots_used,
            "snapshotsSkipped": snapshots_skipped,
        },
    )


def _print_stats(source_rows: int, stats: dict, class_stats: dict, history_rows: int) -> None:
    print(f"Source rows: {source_rows}")
    print(f"Historical rows: {history_rows}")
    print(
        "Snapshot: "
        f"new={stats.get('new', 0)} updated={stats.get('updated', 0)} "
        f"relisted={stats.get('relisted', 0)} unlisted={stats.get('unlisted', 0)}"
    )
    print(
        "Procurement: "
        f"{class_stats['procurement']} "
        f"(title={class_stats['byBasis']['title']}, "
        f"field={class_stats['byBasis']['field']}, "
        f"duty={class_stats['byBasis']['duty_phrase']})"
    )
    print(
        "Classification: "
        f"sector_other={class_stats['sectorOther']} "
        f"career_broad={class_stats['careerBroad']} "
        f"experience_parsed={class_stats['experienceParsed']}"
    )


def main() -> None:
    try:
        code = run()
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Existing dashboard data was left unchanged.", file=sys.stderr)
        sys.exit(1)
    sys.exit(code)


if __name__ == "__main__":
    main()
