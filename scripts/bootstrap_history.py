"""Replay upstream Careers@Gov snapshots once to seed history.

This is not part of the weekday job. A failed clone falls back to the
current CSV. A bad old snapshot is skipped and the replay continues.
Running it again rebuilds history from scratch.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd

from scripts.common import RAW_CSV, SGT, UPSTREAM_REPO, clean, load_yaml, sha256_bytes, today_sgt
from scripts.run_pipeline import run, write_from_records
from scripts.update_history import apply_snapshot
from scripts.validate_source import ValidationError, validate_rows

CLONE_DIR = Path(__file__).resolve().parents[1] / ".tmp" / "upstream"


def ensure_clone(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if (dest / ".git").exists():
        _git(["git", "-C", str(dest), "fetch", "origin", "main"])
        _git(["git", "-C", str(dest), "reset", "--hard", "origin/main"])
        return
    if dest.exists():
        raise ValidationError(f"Clone path exists but is not a git repo: {dest}")
    _git(["git", "clone", UPSTREAM_REPO, str(dest)])


def normalize_snapshot_rows(rows: list[dict]) -> list[dict]:
    """Snapshots from before the platform column are HRP-only extracts."""
    for row in rows:
        if not clean(row.get("platform")):
            row["platform"] = "hrp"
    return rows


def replay(dest: Path) -> dict:
    validation = load_yaml("validation.yml")
    listed = _git(
        [
            "git",
            "-C",
            str(dest),
            "log",
            "--reverse",
            "--format=%H%x09%cI",
            "--",
            "data/job-listings.csv",
        ],
        capture=True,
    )
    commits = [line.split("\t") for line in listed.splitlines() if line.strip()]
    records: dict[str, dict] = {}
    used = 0
    skipped = 0
    last_date = None
    last_payload = b""
    last_rows = 0
    print(f"Upstream snapshots to replay: {len(commits)}")
    for index, (sha, committed) in enumerate(commits, start=1):
        try:
            payload = _read_blob(dest, sha)
            frame = pd.read_csv(StringIO(payload.decode("utf-8")), dtype=str, keep_default_na=False)
            rows = normalize_snapshot_rows(frame.to_dict(orient="records"))
            validate_rows(
                rows,
                required_columns=validation["bootstrap_required_columns"],
                min_rows=int(validation["bootstrap_min_rows"]),
                check_duplicate_keys=False,
            )
        except (ValidationError, pd.errors.ParserError, UnicodeError, subprocess.CalledProcessError) as exc:
            skipped += 1
            print(f"Skip {sha[:8]}: {exc}")
            continue
        seen = datetime.fromisoformat(committed).astimezone(SGT).date()
        apply_snapshot(records, rows, seen)
        used += 1
        last_date = seen
        last_payload = payload
        last_rows = len(rows)
        if index % 25 == 0 or index == len(commits):
            print(f"Replayed {index}/{len(commits)} snapshots; history rows={len(records)}")
    if used == 0 or last_date is None:
        raise ValidationError("No usable upstream snapshots were found.")
    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    RAW_CSV.write_bytes(last_payload)
    download = {
        "bytes": len(last_payload),
        "sha256": sha256_bytes(last_payload),
        "lastModified": "",
        "url": "https://github.com/opengovsg/careersgovsg-jobs-data",
    }
    write_from_records(
        records,
        run_day=last_date,
        history_source="upstream-replay",
        source_rows=last_rows,
        download=download,
        snapshot_stats={"snapshotsUsed": used, "snapshotsSkipped": skipped},
        snapshots_used=used,
        snapshots_skipped=skipped,
    )
    return {"used": used, "skipped": skipped, "through": last_date.isoformat()}


def _read_blob(dest: Path, sha: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(dest), "cat-file", "blob", f"{sha}:data/job-listings.csv"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip() or "blob missing"
        raise ValidationError(message)
    if not result.stdout:
        raise ValidationError("Snapshot file was empty.")
    return result.stdout


def _git(command: list[str], capture: bool = False) -> str:
    result = subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "GIT_TERMINAL_PROMPT": "0"},
    )
    return result.stdout if capture else ""


def main() -> None:
    try:
        ensure_clone(CLONE_DIR)
        summary = replay(CLONE_DIR)
        print(
            f"Bootstrap complete: used={summary['used']} "
            f"skipped={summary['skipped']} through={summary['through']}"
        )
    except (ValidationError, subprocess.CalledProcessError, OSError) as exc:
        print(f"Bootstrap unavailable ({exc}). Falling back to the current CSV.", file=sys.stderr)
        try:
            code = run(run_date=today_sgt())
        except ValidationError as inner:
            print(f"ERROR: {inner}", file=sys.stderr)
            sys.exit(1)
        sys.exit(code)


if __name__ == "__main__":
    main()
