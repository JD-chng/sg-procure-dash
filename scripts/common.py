"""Shared parsing, paths, and config loading."""

from __future__ import annotations

import hashlib
import math
import re
from datetime import date, datetime
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_CSV = DATA_DIR / "raw" / "latest.csv"
HISTORY_CSV = DATA_DIR / "historical" / "jobs_history.csv"
STATE_JSON = DATA_DIR / "historical" / "source_state.json"
PROCESSED_CSV = DATA_DIR / "processed" / "procurement_jobs.csv"
DOCS_DATA = ROOT / "docs" / "data" / "dashboard_data.json"
DOCS_META = ROOT / "docs" / "data" / "metadata.json"
DOCS_TEXT = ROOT / "docs" / "data" / "job_text.json"
KEYWORD_DIR = ROOT / "docs" / "data" / "keywords"

SOURCE_URL = (
    "https://raw.githubusercontent.com/opengovsg/careersgovsg-jobs-data/"
    "main/data/job-listings.csv"
)
UPSTREAM_REPO = "https://github.com/opengovsg/careersgovsg-jobs-data.git"
SGT = ZoneInfo("Asia/Singapore")

HISTORY_COLUMNS = [
    "job_key",
    "platform",
    "jobId",
    "postingNo",
    "jobTitle",
    "agency",
    "employmentType",
    "startDate",
    "closingDate",
    "postingDate",
    "firstSeenDate",
    "lastSeenDate",
    "currentlyListed",
    "relistCount",
    "experienceRequired",
    "experienceYearsMin",
    "experienceYearsMax",
    "field",
    "functionalArea",
    "industry",
    "procurementRelevant",
    "procurementMatchScore",
    "procurementMatchedTerms",
    "procurementMatchBasis",
    "procurementSector",
    "sectorMatchedTerms",
    "experienceMinYears",
    "experienceMaxYears",
    "experienceTextMatched",
    "careerLevel",
    "pcfCompetencies",
    "pcfPrimary",
    "pcfMatchedTerms",
    "sourceURL",
    "postingMonth",
    "postingQuarter",
    "postingYear",
    "closingMonth",
    "daysUntilClosing",
    "daysListed",
    "isNewThisRun",
    "isNewThisWeek",
    "isNewThisMonth",
    "inTrend",
    "responsibilities",
    "requirements",
    "description",
]


def load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a mapping")
    return data


def today_sgt(now: datetime | None = None) -> date:
    moment = now or datetime.now(SGT)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=SGT)
    return moment.astimezone(SGT).date()


def html_to_text(value: object) -> str:
    if value is None:
        return ""
    text = unescape(str(value))
    text = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null", "nat", "<na>"}:
        return ""
    return text


def contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    pattern = r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)"
    return re.search(pattern, text.lower()) is not None


def _plausible_posting_date(value: date) -> bool:
    return date(1990, 1, 1) <= value <= date(2100, 12, 31)


def parse_epoch_ms(value: object) -> date | None:
    text = clean(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number) or number <= 0:
        return None
    if number > 10_000_000_000:
        number = number / 1000.0
    try:
        parsed = datetime.fromtimestamp(number, tz=SGT).date()
    except (OverflowError, OSError, ValueError):
        return None
    if not _plausible_posting_date(parsed):
        return None
    return parsed


def parse_iso(value: object) -> date | None:
    text = clean(value)
    if len(text) < 10 or text[4] != "-" or text[7] != "-":
        return None
    try:
        parsed = date.fromisoformat(text[:10])
    except ValueError:
        return None
    if not _plausible_posting_date(parsed):
        return None
    return parsed


def parse_date_any(value: object) -> date | None:
    """Read an ISO date or a source epoch timestamp."""
    return parse_iso(value) or parse_epoch_ms(value)


def to_int(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number):
        return None
    return int(number)


def quarter_key(value: date) -> str:
    return f"{value.year}Q{(value.month - 1) // 3 + 1}"


def month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def job_url(platform: str, job_id: str, posting_no: str) -> str:
    platform_id = clean(platform).lower()
    job = clean(job_id)
    posting = clean(posting_no)
    if not platform_id or not job:
        return ""
    if platform_id == "hrp" and posting:
        return f"https://jobs.careers.gov.sg/jobs/hrp/{job}/{posting}"
    if platform_id == "greenhouse":
        return f"https://jobs.careers.gov.sg/jobs/greenhouse/{job}?gh_jid={job}"
    if platform_id == "workable" and posting:
        return f"https://apply.workable.com/j/{posting}"
    if posting:
        return f"https://jobs.careers.gov.sg/jobs/{platform_id}/{job}/{posting}"
    return f"https://jobs.careers.gov.sg/jobs/{platform_id}/{job}"


def make_job_key(platform: object, job_id: object, posting_no: object) -> str:
    return f"{clean(platform)}|{clean(job_id)}|{clean(posting_no)}"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
