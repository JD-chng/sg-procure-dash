"""Match configured keywords in posting text and write one CSV per keyword."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.common import load_yaml, parse_date_any

TEXT_FIELDS = {
    "title": "jobTitle",
    "responsibilities": "responsibilities",
    "requirements": "requirements",
    "description": "description",
}
SNIPPET_RADIUS = 110

CSV_COLUMNS = [
    "job_key",
    "status",
    "population",
    "internship",
    "agency",
    "jobTitle",
    "contractType",
    "employmentType",
    "experienceMinYears",
    "postingDate",
    "firstSeenDate",
    "lastSeenDate",
    "closingDate",
    "matchedWords",
    "matchedIn",
    "snippet",
    "sourceURL",
    "responsibilities",
    "requirements",
    "description",
]

INDEX_COLUMNS = [
    "keyword_id",
    "group",
    "label",
    "generic",
    "searched_in",
    "patterns",
    "postings_all",
    "postings_core",
    "open_core",
    "file",
]


@dataclass
class Keyword:
    id: str
    label: str
    group_id: str
    group_label: str
    generic: bool
    fields: list[str]
    patterns: list[str]
    compiled: list[re.Pattern] = field(default_factory=list)


@dataclass
class Hit:
    words: list[str]
    parts: list[str]
    snippet: str


def load_keywords(config: dict | None = None) -> list[Keyword]:
    config = config or load_yaml("keywords.yml")
    default_fields = config.get("default_fields") or list(TEXT_FIELDS)
    keywords: list[Keyword] = []
    seen: set[str] = set()
    for group in config.get("groups", []):
        for item in group.get("keywords", []):
            key = str(item["id"])
            if key in seen:
                raise ValueError(f"Duplicate keyword id in keywords.yml: {key}")
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", key):
                raise ValueError(f"Keyword id must be lowercase letters, digits, and hyphens: {key}")
            seen.add(key)
            fields = item.get("fields") or default_fields
            unknown = [name for name in fields if name not in TEXT_FIELDS]
            if unknown:
                raise ValueError(f"Keyword {key} has unknown fields: {unknown}")
            patterns = [str(p) for p in item.get("patterns", [])]
            if not patterns:
                raise ValueError(f"Keyword {key} has no patterns")
            keywords.append(
                Keyword(
                    id=key,
                    label=str(item["label"]),
                    group_id=str(group["id"]),
                    group_label=str(group["label"]),
                    generic=bool(item.get("generic", group.get("generic", False))),
                    fields=list(fields),
                    patterns=patterns,
                    compiled=[re.compile(p, re.IGNORECASE) for p in patterns],
                )
            )
    return keywords


def match_record(record: dict, keywords: list[Keyword]) -> dict[str, Hit]:
    hits: dict[str, Hit] = {}
    for keyword in keywords:
        words: list[str] = []
        parts: list[str] = []
        snippet = ""
        for name in keyword.fields:
            text = record.get(TEXT_FIELDS[name]) or ""
            if not text:
                continue
            found = False
            for pattern in keyword.compiled:
                for match in pattern.finditer(text):
                    found = True
                    word = match.group(0).lower()
                    if word not in words:
                        words.append(word)
                    if not snippet:
                        snippet = _snippet(text, match.start(), match.end())
            if found:
                parts.append(name)
        if parts:
            hits[keyword.id] = Hit(words=words, parts=parts, snippet=snippet)
    return hits


def _snippet(text: str, start: int, end: int) -> str:
    left = max(0, start - SNIPPET_RADIUS)
    right = min(len(text), end + SNIPPET_RADIUS)
    if left > 0:
        space = text.find(" ", left)
        left = space + 1 if 0 <= space < start else left
    if right < len(text):
        space = text.rfind(" ", end, right)
        right = space if space > end else right
    return ("…" if left > 0 else "") + text[left:right].strip() + ("…" if right < len(text) else "")


def write_keyword_files(
    directory: Path,
    records: list[dict],
    hits_by_key: dict[str, dict[str, Hit]],
    keywords: list[Keyword],
    *,
    contract_of,
    internship_of,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    wanted = {f"{keyword.id}.csv" for keyword in keywords} | {"index.csv"}
    for stale in directory.glob("*.csv"):
        if stale.name not in wanted:
            stale.unlink()
    ordered = sorted(records, key=lambda r: r.get("jobTitle", ""))
    ordered.sort(key=lambda r: r.get("firstSeenDate", ""), reverse=True)
    ordered.sort(key=lambda r: r.get("currentlyListed") != "true")
    index_rows = []
    for keyword in keywords:
        rows = []
        core = open_core = 0
        for record in ordered:
            hit = hits_by_key.get(record.get("job_key", ""), {}).get(keyword.id)
            if hit is None:
                continue
            is_core = record.get("procurementMatchBasis") != "duty_phrase"
            is_open = record.get("currentlyListed") == "true"
            if is_core:
                core += 1
                open_core += int(is_open)
            rows.append(
                {
                    "job_key": record.get("job_key", ""),
                    "status": "open" if is_open else "closed",
                    "population": "core" if is_core else "duties-only",
                    "internship": "yes" if internship_of(record) else "no",
                    "agency": record.get("agency", ""),
                    "jobTitle": record.get("jobTitle", ""),
                    "contractType": contract_of(record),
                    "employmentType": record.get("employmentType", ""),
                    "experienceMinYears": record.get("experienceMinYears", ""),
                    "postingDate": record.get("postingDate", ""),
                    "firstSeenDate": record.get("firstSeenDate", ""),
                    "lastSeenDate": record.get("lastSeenDate", ""),
                    "closingDate": _iso(record.get("closingDate")),
                    "matchedWords": "; ".join(hit.words),
                    "matchedIn": "; ".join(hit.parts),
                    "snippet": hit.snippet,
                    "sourceURL": record.get("sourceURL", ""),
                    "responsibilities": record.get("responsibilities", "") if "responsibilities" in hit.parts else "",
                    "requirements": record.get("requirements", "") if "requirements" in hit.parts else "",
                    "description": record.get("description", "") if "description" in hit.parts else "",
                }
            )
        _write_csv(directory / f"{keyword.id}.csv", CSV_COLUMNS, rows)
        index_rows.append(
            {
                "keyword_id": keyword.id,
                "group": keyword.group_label,
                "label": keyword.label,
                "generic": "yes" if keyword.generic else "no",
                "searched_in": "; ".join(keyword.fields),
                "patterns": " | ".join(keyword.patterns),
                "postings_all": len(rows),
                "postings_core": core,
                "open_core": open_core,
                "file": f"{keyword.id}.csv",
            }
        )
    _write_csv(directory / "index.csv", INDEX_COLUMNS, index_rows)


def _iso(value: object) -> str:
    parsed = parse_date_any(value)
    return parsed.isoformat() if parsed else ""


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    temporary = path.with_suffix(".csv.partial")
    # utf-8-sig so Excel opens accented and dash characters correctly.
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)
