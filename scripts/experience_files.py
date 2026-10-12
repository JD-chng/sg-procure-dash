"""Write one CSV per minimum-experience band for cross-reference."""

from __future__ import annotations

from pathlib import Path

from scripts.build_dashboard_data import experience_band, experience_lists
from scripts.classify_experience import stated_minimum_with_evidence
from scripts.common import parse_date_any, to_int
from scripts.io_store import write_listing_csv

CSV_COLUMNS = [
    "job_key",
    "status",
    "population",
    "internship",
    "agency",
    "jobTitle",
    "experienceMinYears",
    "foundIn",
    "experienceField",
    "experienceFieldYears",
    "contractType",
    "employmentType",
    "postingDate",
    "firstSeenDate",
    "lastSeenDate",
    "closingDate",
    "sourceURL",
    "requirements",
]
INDEX_COLUMNS = [
    "band_id",
    "label",
    "min_years",
    "max_years",
    "postings_all",
    "postings_core",
    "open_core",
    "file",
]


def write_experience_files(
    directory: Path,
    records: list[dict],
    *,
    dashboard_rules: dict,
    experience_rules: dict,
    contract_of,
    internship_of,
) -> None:
    bands = experience_lists(dashboard_rules)
    open_ended = int(experience_rules.get("open_ended_max", 90))
    directory.mkdir(parents=True, exist_ok=True)
    wanted = {f"{band['id']}.csv" for band in bands} | {"index.csv"}
    for stale in directory.glob("*.csv"):
        if stale.name not in wanted:
            stale.unlink()
    ordered = sorted(records, key=lambda r: r.get("jobTitle", ""))
    ordered.sort(key=lambda r: r.get("firstSeenDate", ""), reverse=True)
    ordered.sort(key=lambda r: r.get("currentlyListed") != "true")
    rows_by_band: dict[str, list[dict]] = {band["label"]: [] for band in bands}
    counts = {band["label"]: [0, 0] for band in bands}
    for record in ordered:
        years = to_int(record.get("experienceStatedMinYears"))
        label = experience_band(years, dashboard_rules)
        if label not in rows_by_band:
            continue
        _, found_in = stated_minimum_with_evidence(
            experience_required=record.get("experienceRequired", ""),
            years_min=record.get("experienceYearsMin", ""),
            requirements=record.get("requirements", ""),
            description=record.get("description", ""),
            rules=experience_rules,
        )
        is_core = record.get("procurementMatchBasis") != "duty_phrase"
        is_open = record.get("currentlyListed") == "true"
        if is_core:
            counts[label][0] += 1
            counts[label][1] += int(is_open)
        rows_by_band[label].append(
            {
                "job_key": record.get("job_key", ""),
                "status": "open" if is_open else "closed",
                "population": "core" if is_core else "duties-only",
                "internship": "yes" if internship_of(record) else "no",
                "agency": record.get("agency", ""),
                "jobTitle": record.get("jobTitle", ""),
                "experienceMinYears": "" if years is None else years,
                "foundIn": found_in,
                "experienceField": record.get("experienceRequired", ""),
                "experienceFieldYears": _field_years(record, open_ended),
                "contractType": contract_of(record),
                "employmentType": record.get("employmentType", ""),
                "postingDate": record.get("postingDate", ""),
                "firstSeenDate": record.get("firstSeenDate", ""),
                "lastSeenDate": record.get("lastSeenDate", ""),
                "closingDate": _iso(record.get("closingDate")),
                "sourceURL": record.get("sourceURL", ""),
                "requirements": record.get("requirements", ""),
            }
        )
    index_rows = []
    for band in bands:
        rows = rows_by_band[band["label"]]
        write_listing_csv(directory / f"{band['id']}.csv", CSV_COLUMNS, rows)
        index_rows.append(
            {
                "band_id": band["id"],
                "label": band["label"],
                "min_years": "" if band["min"] is None else band["min"],
                "max_years": "" if band["max"] is None else band["max"],
                "postings_all": len(rows),
                "postings_core": counts[band["label"]][0],
                "open_core": counts[band["label"]][1],
                "file": f"{band['id']}.csv",
            }
        )
    write_listing_csv(directory / "index.csv", INDEX_COLUMNS, index_rows)


def _field_years(record: dict, open_ended: int) -> str:
    low = to_int(record.get("experienceYearsMin"))
    high = to_int(record.get("experienceYearsMax"))
    if low is None and high is None:
        return ""
    if high is not None and high >= open_ended:
        return f"{low or 0}+"
    if high is None or high == low:
        return str(low if low is not None else high)
    return f"{'' if low is None else low}–{high}"


def _iso(value: object) -> str:
    parsed = parse_date_any(value)
    return parsed.isoformat() if parsed else ""
