"""Upsert postings so a job that leaves Careers@Gov stays in history."""

from __future__ import annotations

from datetime import date

from scripts.common import (
    clean,
    html_to_text,
    job_url,
    make_job_key,
    month_key,
    parse_date_any,
    parse_iso,
    quarter_key,
)


def blank_record() -> dict:
    return {
        "job_key": "",
        "platform": "",
        "jobId": "",
        "postingNo": "",
        "jobTitle": "",
        "agency": "",
        "employmentType": "",
        "startDate": "",
        "closingDate": "",
        "postingDate": "",
        "firstSeenDate": "",
        "lastSeenDate": "",
        "currentlyListed": "false",
        "relistCount": "0",
        "experienceRequired": "",
        "experienceYearsMin": "",
        "experienceYearsMax": "",
        "field": "",
        "functionalArea": "",
        "industry": "",
        "procurementRelevant": "false",
        "procurementMatchScore": "0",
        "procurementMatchedTerms": "",
        "procurementMatchBasis": "",
        "procurementSector": "",
        "sectorMatchedTerms": "",
        "experienceMinYears": "",
        "experienceMaxYears": "",
        "experienceTextMatched": "",
        "careerLevel": "",
        "pcfCompetencies": "",
        "pcfPrimary": "",
        "pcfMatchedTerms": "",
        "sourceURL": "",
        "postingMonth": "",
        "postingQuarter": "",
        "postingYear": "",
        "closingMonth": "",
        "daysUntilClosing": "",
        "daysListed": "",
        "isNewThisRun": "false",
        "isNewThisWeek": "false",
        "isNewThisMonth": "false",
        "inTrend": "false",
        "responsibilities": "",
        "requirements": "",
        "description": "",
    }


def apply_snapshot(records: dict[str, dict], rows: list[dict], seen_date: date) -> dict:
    """Fold one Careers@Gov snapshot into the historical table.

    Returns counts for new keys, refreshed keys, relists, and jobs that
    dropped off this snapshot.
    """
    seen: set[str] = set()
    stats = {"new": 0, "updated": 0, "relisted": 0, "unlisted": 0, "duplicateSkipped": 0}
    seen_iso = seen_date.isoformat()
    for row in rows:
        key = make_job_key(row.get("platform"), row.get("jobId"), row.get("postingNo"))
        if not clean(row.get("jobId")) or not clean(row.get("platform")):
            continue
        if key in seen:
            stats["duplicateSkipped"] += 1
            continue
        seen.add(key)
        existing = records.get(key)
        if existing is None:
            record = blank_record()
            record["job_key"] = key
            record["firstSeenDate"] = seen_iso
            record["relistCount"] = "0"
            records[key] = record
            stats["new"] += 1
        else:
            record = existing
            if record.get("currentlyListed") == "false":
                record["relistCount"] = str(int(record.get("relistCount") or "0") + 1)
                stats["relisted"] += 1
            else:
                stats["updated"] += 1
        record["lastSeenDate"] = seen_iso
        record["currentlyListed"] = "true"
        _copy_source_fields(record, row)

    for key, record in records.items():
        if key not in seen and record.get("currentlyListed") == "true":
            record["currentlyListed"] = "false"
            stats["unlisted"] += 1
    return stats


def finalize_records(records: dict[str, dict], run_date: date, coverage_start: date | None) -> None:
    for record in records.values():
        _derive_dates(record, run_date, coverage_start)


def retain_text(record: dict) -> None:
    """Keep full text for procurement rows and near-misses only."""
    relevant = record.get("procurementRelevant") == "true"
    try:
        score = int(record.get("procurementMatchScore") or "0")
    except ValueError:
        score = 0
    if relevant or score > 0 or str(record.get("procurementMatchedTerms", "")).startswith("veto:"):
        return
    record["description"] = ""
    record["responsibilities"] = ""
    record["requirements"] = ""


def _copy_source_fields(record: dict, row: dict) -> None:
    record["platform"] = clean(row.get("platform"))
    record["jobId"] = clean(row.get("jobId"))
    record["postingNo"] = clean(row.get("postingNo"))
    record["jobTitle"] = html_to_text(row.get("jobTitle"))
    record["agency"] = clean(row.get("agency"))
    record["employmentType"] = clean(row.get("employmentType"))
    record["startDate"] = _iso_or_blank(row.get("startDate"))
    record["closingDate"] = _iso_or_blank(row.get("closingDate"))
    record["experienceRequired"] = html_to_text(row.get("experienceRequired"))
    record["experienceYearsMin"] = clean(row.get("experienceYearsMin"))
    record["experienceYearsMax"] = clean(row.get("experienceYearsMax"))
    record["field"] = clean(row.get("field"))
    record["functionalArea"] = clean(row.get("functionalArea"))
    record["industry"] = clean(row.get("industry"))
    record["description"] = html_to_text(row.get("jobDescription"))
    record["responsibilities"] = html_to_text(row.get("jobResponsibilities"))
    record["requirements"] = html_to_text(row.get("jobRequirements"))
    record["sourceURL"] = job_url(record["platform"], record["jobId"], record["postingNo"])
    record["postingDate"] = record["startDate"]


def _iso_or_blank(value: object) -> str:
    parsed = parse_date_any(value)
    return parsed.isoformat() if parsed else ""


def _derive_dates(record: dict, run_date: date, coverage_start: date | None) -> None:
    record["startDate"] = _iso_or_blank(record.get("startDate"))
    record["closingDate"] = _iso_or_blank(record.get("closingDate"))
    first = parse_iso(record.get("firstSeenDate"))
    last = parse_iso(record.get("lastSeenDate"))
    posted = parse_iso(record.get("postingDate"))
    closing = parse_iso(record.get("closingDate"))
    if posted:
        record["postingMonth"] = month_key(posted)
        record["postingQuarter"] = quarter_key(posted)
        record["postingYear"] = str(posted.year)
    elif first:
        record["postingMonth"] = month_key(first)
        record["postingQuarter"] = quarter_key(first)
        record["postingYear"] = str(first.year)
    else:
        record["postingMonth"] = ""
        record["postingQuarter"] = ""
        record["postingYear"] = ""
    record["closingMonth"] = month_key(closing) if closing else ""
    if first and last:
        record["daysListed"] = str((last - first).days + 1)
    else:
        record["daysListed"] = ""
    if (
        record.get("currentlyListed") == "true"
        and closing is not None
    ):
        record["daysUntilClosing"] = str((closing - run_date).days)
    else:
        record["daysUntilClosing"] = ""
    record["isNewThisRun"] = "true" if first == run_date else "false"
    record["isNewThisWeek"] = (
        "true" if first and 0 <= (run_date - first).days <= 6 else "false"
    )
    record["isNewThisMonth"] = (
        "true" if first and first.year == run_date.year and first.month == run_date.month else "false"
    )
    record["inTrend"] = "true" if _in_trend(first, posted, coverage_start) else "false"


def _in_trend(first: date | None, posted: date | None, coverage_start: date | None) -> bool:
    if first is None or coverage_start is None:
        return False
    if (first.year, first.month) < (coverage_start.year, coverage_start.month):
        return False
    if (first.year, first.month) == (coverage_start.year, coverage_start.month):
        return posted is not None and (posted.year, posted.month) == (first.year, first.month)
    return True
