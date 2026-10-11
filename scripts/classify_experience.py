"""Parse explicit experience requirements into a career level."""

from __future__ import annotations

import re

from scripts.common import clean, html_to_text, to_int

_YEAR = r"years?|yrs?|year\(s\)"
_RANGE = re.compile(
    rf"\b(\d{{1,2}})\s*(?:-|–|—|to)\s*(\d{{1,2}})\s*(?:\+?\s*)?(?:{_YEAR})\b",
    re.IGNORECASE,
)
_AT_LEAST = re.compile(
    rf"\b(?:at least|minimum|min\.?|more than|over)\s+(\d{{1,2}})\s*(?:\+?\s*)?(?:{_YEAR})\b",
    re.IGNORECASE,
)
_PLUS = re.compile(
    rf"\b(\d{{1,2}})\s*\+\s*(?:{_YEAR})\b",
    re.IGNORECASE,
)


def classify_experience(
    *,
    experience_required: str,
    years_min: object,
    years_max: object,
    requirements: str,
    description: str,
    rules: dict,
) -> dict:
    labels = rules["labels"]
    entry_phrases = [phrase.lower() for phrase in rules.get("entry_phrases", [])]
    required = html_to_text(experience_required)
    requirement_text = html_to_text(requirements)
    description_text = html_to_text(description)
    # Requirements and the structured label outrank a long description.
    scan_parts = [requirement_text, required, description_text]
    scan = " ".join(part for part in scan_parts if part)
    lowered = scan.lower()

    welcomes_entry = any(phrase in lowered for phrase in entry_phrases)
    ranges = [(int(match.group(1)), int(match.group(2)), match.group(0)) for match in _RANGE.finditer(scan)]
    minima = [(int(match.group(1)), match.group(0)) for match in _AT_LEAST.finditer(scan)]
    minima.extend((int(match.group(1)), match.group(0)) for match in _PLUS.finditer(scan))
    positive_floor = any(mn >= 1 for mn, _, _ in ranges) or any(mn >= 1 for mn, _ in minima)

    if welcomes_entry and positive_floor:
        evidence = _first_evidence(ranges, minima, entry_phrases, lowered)
        return _result(None, None, evidence, labels["broad"])

    if welcomes_entry and not ranges and not minima:
        phrase = next(item for item in entry_phrases if item in lowered)
        return _result(0, 0, phrase, labels["entry"])

    if ranges:
        levels = [_range_label(mn, mx, rules) for mn, mx, _ in ranges]
        evidence = ranges[0][2]
        if len(set(levels)) > 1:
            return _result(ranges[0][0], ranges[0][1], evidence, labels["broad"])
        return _result(ranges[0][0], ranges[0][1], evidence, levels[0])

    if minima:
        floor = max(item[0] for item in minima)
        evidence = minima[0][1]
        if floor >= int(rules["bands"]["senior_min"]):
            return _result(floor, None, evidence, labels["senior"])
        return _result(floor, None, evidence, labels["broad"])

    structured_min = to_int(years_min)
    structured_max = to_int(years_max)
    if clean(experience_required).lower() == "entry level":
        return _result(structured_min if structured_min is not None else 0, structured_max if structured_max is not None else 0, "Entry level", labels["entry"])

    if structured_min is None and structured_max is None:
        return _result(None, None, "", labels["broad"])

    return _result(
        structured_min,
        structured_max,
        clean(experience_required),
        _range_label(
            structured_min if structured_min is not None else 0,
            structured_max,
            rules,
        ),
    )


MAX_PLAUSIBLE_MINIMUM = 20


def stated_minimum_years(
    *,
    experience_required: str,
    years_min: object,
    requirements: str,
    description: str,
    rules: dict,
) -> int | None:
    """Highest minimum the posting states anywhere.

    A posting with a structured 0-8 range and "at least 3 years" in the
    requirements asks for 3. The description is read only when there are no
    requirements, because it often describes the agency ("over 50 years").
    """
    if clean(experience_required).lower() == "entry level":
        return 0
    required = html_to_text(experience_required)
    text = html_to_text(requirements) or html_to_text(description)
    scan = " ".join(part for part in [text, required] if part)
    candidates = [int(m.group(1)) for m in _AT_LEAST.finditer(scan)]
    candidates += [int(m.group(1)) for m in _PLUS.finditer(scan)]
    candidates += [int(m.group(1)) for m in _RANGE.finditer(scan)]
    structured = to_int(years_min)
    if structured is not None:
        candidates.append(structured)
    candidates = [value for value in candidates if 0 <= value <= MAX_PLAUSIBLE_MINIMUM]
    if candidates:
        return max(candidates)
    lowered = scan.lower()
    if any(phrase.lower() in lowered for phrase in rules.get("entry_phrases", [])):
        return 0
    return None


def _range_label(years_min: int, years_max: int | None, rules: dict) -> str:
    labels = rules["labels"]
    bands = rules["bands"]
    open_ended = int(rules.get("open_ended_max", 90))
    if years_max is not None and years_max >= open_ended:
        years_max = None
    if years_min <= 0 and (years_max is None or years_max <= 0):
        return labels["broad"]
    if years_min <= 0 and years_max is not None and years_max > 0:
        return labels["broad"]
    if years_max is None:
        if years_min >= int(bands["senior_min"]):
            return labels["senior"]
        return labels["broad"]
    low = _band(years_min, bands)
    high = _band(years_max, bands)
    if low != high:
        return labels["broad"]
    return labels[low]


def _band(years: int, bands: dict) -> str:
    if years <= 0:
        return "entry"
    if int(bands["early_min"]) <= years <= int(bands["early_max"]):
        return "early"
    if int(bands["mid_min"]) <= years <= int(bands["mid_max"]):
        return "mid"
    if years >= int(bands["senior_min"]):
        return "senior"
    return "broad"


def _first_evidence(ranges, minima, entry_phrases, lowered) -> str:
    if ranges:
        return ranges[0][2]
    if minima:
        return minima[0][1]
    return next(item for item in entry_phrases if item in lowered)


def _result(years_min: int | None, years_max: int | None, evidence: str, level: str) -> dict:
    return {
        "experienceMinYears": "" if years_min is None else str(years_min),
        "experienceMaxYears": "" if years_max is None else str(years_max),
        "experienceTextMatched": clean(evidence),
        "careerLevel": level,
    }
