"""Rebuild every output from the stored history without downloading.

Use after editing a file in config/. The source snapshot is not touched,
so first-seen, last-seen, and listing status stay exactly as recorded.
"""

from __future__ import annotations

from scripts.common import DOCS_META, HISTORY_CSV, STATE_JSON, parse_iso, today_sgt
from scripts.io_store import read_history, read_json
from scripts.run_pipeline import write_from_records


def main() -> None:
    records = read_history(HISTORY_CSV)
    if not records:
        raise SystemExit(f"No history at {HISTORY_CSV}. Run the pipeline or bootstrap first.")
    meta = read_json(DOCS_META)
    state = read_json(STATE_JSON)
    run_day = parse_iso(meta.get("processedThrough")) or parse_iso(state.get("throughDate")) or today_sgt()
    write_from_records(
        records,
        run_day=run_day,
        history_source=meta.get("historySource") or state.get("historySource") or "current-snapshot",
        source_rows=int(meta.get("sourceRows") or state.get("sourceRows") or 0),
        download={
            "url": meta.get("sourceUrl", ""),
            "sha256": meta.get("sourceSha256") or state.get("sha256", ""),
            "lastModified": meta.get("sourceLastModified", ""),
        },
        snapshot_stats=(meta.get("runStats") or {}).get("snapshot", {}),
        snapshots_used=meta.get("snapshotsUsed"),
        snapshots_skipped=meta.get("snapshotsSkipped"),
    )
    print(f"Rebuilt outputs through {run_day.isoformat()}.")


if __name__ == "__main__":
    main()
