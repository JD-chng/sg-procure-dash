"""Turn classified history into the browser payload."""

from __future__ import annotations

from datetime import date

from scripts.common import clean, load_yaml, parse_iso


def slim_job(record: dict) -> dict:
    competencies = [
        item.strip()
        for item in clean(record.get("pcfCompetencies")).split(";")
        if item.strip()
    ]
    return {
        "jobKey": record.get("job_key", ""),
        "agency": record.get("agency", ""),
        "jobTitle": record.get("jobTitle", ""),
        "sector": record.get("procurementSector", "") or "Other / Unclassified",
        "careerLevel": record.get("careerLevel", "") or "Broad / No Clear Preference",
        "experienceMinYears": _optional_int(record.get("experienceMinYears")),
        "postingDate": record.get("postingDate", ""),
        "closingDate": _closing_iso(record.get("closingDate", "")),
        "url": record.get("sourceURL", ""),
        "currentlyListed": record.get("currentlyListed") == "true",
        "competencies": competencies,
        "primaryCompetency": record.get("pcfPrimary", ""),
        "postingMonth": record.get("postingMonth", ""),
        "postingQuarter": record.get("postingQuarter", ""),
        "postingYear": record.get("postingYear", ""),
        "firstSeen": record.get("firstSeenDate", ""),
        "lastSeen": record.get("lastSeenDate", ""),
        "daysListed": _optional_int(record.get("daysListed")),
        "employmentType": record.get("employmentType", ""),
        "internship": _is_internship(record),
        "matchBasis": record.get("procurementMatchBasis", ""),
        "matchedTerms": record.get("procurementMatchedTerms", ""),
        "inTrend": record.get("inTrend") == "true",
        "trendMonth": _trend_month(record),
        "trendQuarter": _trend_quarter(record),
        "isNewThisRun": record.get("isNewThisRun") == "true",
        "isNewThisMonth": record.get("isNewThisMonth") == "true",
    }


def _trend_month(record: dict) -> str:
    if record.get("inTrend") != "true":
        return ""
    first = parse_iso(record.get("firstSeenDate"))
    if first is None:
        return ""
    return f"{first.year:04d}-{first.month:02d}"


def _trend_quarter(record: dict) -> str:
    if record.get("inTrend") != "true":
        return ""
    first = parse_iso(record.get("firstSeenDate"))
    if first is None:
        return ""
    return f"{first.year}Q{(first.month - 1) // 3 + 1}"


def _closing_iso(value: str) -> str:
    parsed = parse_iso(value)
    if parsed:
        return parsed.isoformat()
    from scripts.common import parse_epoch_ms

    epoch = parse_epoch_ms(value)
    return epoch.isoformat() if epoch else ""


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
    types = _internship_types()
    if employment in types:
        return True
    return "[intern]" in title or title.startswith("intern ") or " internship" in title


def build_payload(
    records: dict[str, dict],
    *,
    metadata: dict,
) -> dict:
    jobs = [
        slim_job(record)
        for record in records.values()
        if record.get("procurementRelevant") == "true"
    ]
    jobs.sort(key=lambda job: (job.get("postingDate") or "", job.get("jobTitle") or ""), reverse=True)
    sector_labels = [
        sector["label"] for sector in load_yaml("sector_taxonomy.yml").get("sectors", [])
    ]
    sector_labels.append("Other / Unclassified")
    career_labels = list(load_yaml("experience_rules.yml")["labels"].values())
    competency_labels = [
        item["label"] for item in load_yaml("pcf_competencies.yml").get("competencies", [])
    ]
    validation = load_yaml("validation.yml")
    return {
        "metadata": {
            **metadata,
            "sectorLabels": sector_labels,
            "careerLabels": career_labels,
            "competencyLabels": competency_labels,
            "insightMinPeriodCount": int(validation.get("insight_min_period_count", 5)),
            "insightMinChange": int(validation.get("insight_min_change", 3)),
            "medianMinSample": int(validation.get("median_min_sample", 10)),
            "procurementCount": len(jobs),
            "currentlyListedCount": sum(1 for job in jobs if job["currentlyListed"]),
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
