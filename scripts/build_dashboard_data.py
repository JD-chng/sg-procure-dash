"""Turn classified history into the browser payload."""

from __future__ import annotations

from datetime import date, timedelta

from scripts.common import clean, load_yaml, month_key, parse_date_any, parse_iso, quarter_key


def slim_job(record: dict, rules: dict) -> dict:
    first = parse_iso(record.get("firstSeenDate"))
    min_years = _optional_int(record.get("experienceMinYears"))
    in_trend = record.get("inTrend") == "true"
    return {
        "jobKey": record.get("job_key", ""),
        "agency": record.get("agency", ""),
        "jobTitle": record.get("jobTitle", ""),
        "url": record.get("sourceURL", ""),
        "open": record.get("currentlyListed") == "true",
        "postingDate": record.get("postingDate", ""),
        "closingDate": _iso(record.get("closingDate")),
        "daysUntilClosing": _optional_int(record.get("daysUntilClosing")),
        "firstSeen": record.get("firstSeenDate", ""),
        "lastSeen": record.get("lastSeenDate", ""),
        "firstMonth": month_key(first) if first else "",
        "firstQuarter": quarter_key(first) if first else "",
        "daysListed": _optional_int(record.get("daysListed")),
        "relistCount": _optional_int(record.get("relistCount")) or 0,
        "employmentType": record.get("employmentType", ""),
        "contractType": contract_type(record.get("employmentType"), rules),
        "experienceMinYears": min_years,
        "experienceBand": experience_band(min_years, rules),
        "internship": _is_internship(record),
        "matchBasis": record.get("procurementMatchBasis", ""),
        "inTrend": in_trend,
        "trendMonth": month_key(first) if in_trend and first else "",
        "trendQuarter": quarter_key(first) if in_trend and first else "",
    }


def contract_type(value: object, rules: dict) -> str:
    text = clean(value).lower()
    if not text:
        return rules.get("contract_not_stated", "Not stated")
    for item in rules.get("contract_types", []):
        if text in {str(option).lower() for option in item.get("values", [])}:
            return item["label"]
    return rules.get("contract_other", "Other")


def experience_band(min_years: int | None, rules: dict) -> str:
    if min_years is None:
        return rules.get("experience_not_stated", "Not stated")
    for band in rules.get("experience_bands", []):
        low = band.get("min")
        high = band.get("max")
        if (low is None or min_years >= low) and (high is None or min_years <= high):
            return band["label"]
    return rules.get("experience_not_stated", "Not stated")


def period_calendar(coverage_start: date | None, through: date | None) -> dict:
    """Months and quarters inside coverage, flagged complete or partial."""
    if coverage_start is None or through is None or through < coverage_start:
        return {"months": [], "quarters": [], "yoyAvailableFrom": ""}
    months = []
    cursor = date(coverage_start.year, coverage_start.month, 1)
    while cursor <= through:
        nxt = _add_months(cursor, 1)
        months.append(_period(month_key(cursor), _month_label(cursor), cursor, nxt - timedelta(days=1), coverage_start, through))
        cursor = nxt
    quarters = []
    cursor = date(coverage_start.year, 3 * ((coverage_start.month - 1) // 3) + 1, 1)
    while cursor <= through:
        nxt = _add_months(cursor, 3)
        label = f"Q{(cursor.month - 1) // 3 + 1} {cursor.year}"
        quarters.append(_period(quarter_key(cursor), label, cursor, nxt - timedelta(days=1), coverage_start, through))
        cursor = nxt
    coverage_quarter = date(coverage_start.year, 3 * ((coverage_start.month - 1) // 3) + 1, 1)
    first_full = coverage_quarter if coverage_quarter == coverage_start else _add_months(coverage_quarter, 3)
    yoy = _add_months(first_full, 12)
    return {
        "months": months,
        "quarters": quarters,
        "yoyAvailableFrom": f"Q{(yoy.month - 1) // 3 + 1} {yoy.year}",
    }


def _period(key: str, label: str, start: date, end: date, coverage_start: date, through: date) -> dict:
    complete = start >= coverage_start and end <= through
    if complete:
        note = ""
    elif start < coverage_start:
        note = f"from {coverage_start.day} {coverage_start.strftime('%b')}"
    else:
        note = "to date"
    return {
        "key": key,
        "label": label,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "complete": complete,
        "note": note,
    }


def _add_months(value: date, count: int) -> date:
    index = value.month - 1 + count
    return date(value.year + index // 12, index % 12 + 1, 1)


def _month_label(value: date) -> str:
    return value.strftime("%b %Y")


def _iso(value: object) -> str:
    parsed = parse_date_any(value)
    return parsed.isoformat() if parsed else ""


def _optional_int(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _internship_types() -> set[str]:
    rules = load_yaml("validation.yml")
    return {item.lower() for item in rules.get("internship_employment_types", [])}


def _is_internship(record: dict) -> bool:
    employment = clean(record.get("employmentType")).lower()
    title = clean(record.get("jobTitle")).lower()
    if employment in _INTERNSHIP_TYPES:
        return True
    return "[intern]" in title or title.startswith("intern ") or " internship" in title


_INTERNSHIP_TYPES = _internship_types()


def build_payload(
    records: dict[str, dict],
    *,
    metadata: dict,
) -> dict:
    rules = load_yaml("dashboard.yml")
    jobs = [
        slim_job(record, rules)
        for record in records.values()
        if record.get("procurementRelevant") == "true"
    ]
    jobs.sort(key=lambda job: (job.get("postingDate") or "", job.get("jobTitle") or ""), reverse=True)
    calendar = period_calendar(parse_iso(metadata.get("coverageStart")), parse_iso(metadata.get("processedThrough")))
    contract_labels = [item["label"] for item in rules.get("contract_types", [])]
    contract_labels += [rules.get("contract_other", "Other"), rules.get("contract_not_stated", "Not stated")]
    band_labels = [band["label"] for band in rules.get("experience_bands", [])]
    band_labels.append(rules.get("experience_not_stated", "Not stated"))
    comparison = rules.get("comparison", {})
    keyword_trend = rules.get("keyword_trend", {})
    return {
        "metadata": {
            **metadata,
            **calendar,
            "contractLabels": contract_labels,
            "noPermanentOption": rules.get("no_permanent_option", []),
            "experienceBands": band_labels,
            "closingSoonDays": int(rules.get("closing_soon_days", 7)),
            "comparisonMinCount": int(comparison.get("min_period_count", 5)),
            "comparisonMinChange": int(comparison.get("min_change", 3)),
            "comparisonMinPercent": float(comparison.get("min_change_percent", 10)),
            "keywordTrendMinPostings": int(keyword_trend.get("min_quarter_postings", 10)),
            "keywordTrendMinPoints": float(keyword_trend.get("min_change_points", 5)),
            "topAgencies": int(rules.get("top_agencies", 10)),
            "procurementCount": len(jobs),
            "currentlyListedCount": sum(1 for job in jobs if job["open"]),
        },
        "jobs": jobs,
    }


def coverage_start_from(records: dict[str, dict]) -> date | None:
    dates = [
        parse_iso(record.get("firstSeenDate"))
        for record in records.values()
        if parse_iso(record.get("firstSeenDate"))
    ]
    dates = [item for item in dates if item is not None]
    if not dates:
        return None
    return min(dates)
