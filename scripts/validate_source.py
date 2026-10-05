"""Fail closed when an upstream extract is empty or implausible."""

from __future__ import annotations

from scripts.common import clean, make_job_key


class ValidationError(Exception):
    """The source file must not replace the last good dashboard."""


def validate_rows(
    rows: list[dict],
    *,
    required_columns: list[str],
    min_rows: int,
    previous_rows: int | None = None,
    max_drop_ratio: float = 0.5,
    allow_row_drop: bool = False,
    check_duplicate_keys: bool = True,
) -> dict:
    if not rows:
        raise ValidationError("Source has no data rows.")
    columns = set(rows[0].keys())
    missing = [column for column in required_columns if column not in columns]
    if missing:
        raise ValidationError("Source is missing columns: " + ", ".join(missing))
    if len(rows) < min_rows:
        raise ValidationError(
            f"Source has {len(rows)} rows, below the minimum of {min_rows}."
        )
    if (
        previous_rows
        and previous_rows > 0
        and len(rows) < previous_rows * (1 - max_drop_ratio)
        and not allow_row_drop
    ):
        raise ValidationError(
            f"Source fell from {previous_rows} to {len(rows)} rows, "
            "more than the allowed drop. Re-run with allow_row_drop to override."
        )
    duplicate_count = 0
    if check_duplicate_keys:
        seen: set[str] = set()
        duplicates: list[str] = []
        for row in rows:
            key = make_job_key(row.get("platform"), row.get("jobId"), row.get("postingNo"))
            if key in seen and key not in duplicates:
                duplicates.append(key)
            seen.add(key)
        duplicate_count = len(duplicates)
        if duplicates:
            raise ValidationError(
                f"Source has {len(duplicates)} duplicate job keys, including {duplicates[0]}."
            )
    return {"rows": len(rows), "duplicateKeys": duplicate_count, "agencySample": clean(rows[0].get("agency"))}
