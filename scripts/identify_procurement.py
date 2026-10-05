"""Balanced, config-driven procurement identification."""

from __future__ import annotations

from scripts.common import clean, contains_phrase, html_to_text


def identify_procurement(
    *,
    title: str,
    field: str,
    functional_area: str,
    description: str,
    responsibilities: str,
    requirements: str,
    taxonomy: dict,
) -> dict:
    title_text = html_to_text(title).lower()
    field_text = clean(field).lower()
    area_text = clean(functional_area).lower()
    body = " ".join(
        html_to_text(part)
        for part in (description, responsibilities, requirements)
    ).lower()
    combined = f"{title_text} {body}".strip()

    matched: list[str] = []
    score = 0
    weights = taxonomy.get("weights", {})
    basis = ""

    high_hit = False
    for term in taxonomy.get("high_title_terms", []):
        if contains_phrase(title_text, term):
            high_hit = True
            matched.append(term)
            score += int(weights.get("high_title", 5))
    if high_hit:
        basis = "title"

    field_values = {clean(item).lower() for item in taxonomy.get("field_values", [])}
    field_hit = field_text in field_values or area_text in field_values
    if field_hit:
        matched.append("field:procurement")
        score += int(weights.get("field", 5))
        basis = basis or "field"

    medium_hit = False
    for phrase in taxonomy.get("medium_title_phrases", []):
        if contains_phrase(title_text, phrase):
            medium_hit = True
            matched.append(phrase)
            score += int(weights.get("medium_title", 3))
    if medium_hit:
        basis = basis or "title"

    sourcing = clean(taxonomy.get("sourcing_title_term", "sourcing")).lower()
    companions = taxonomy.get("sourcing_companions", [])
    sourcing_hit = contains_phrase(title_text, sourcing) and any(
        contains_phrase(title_text, companion) for companion in companions
    )
    if sourcing_hit and sourcing not in matched:
        matched.append(sourcing)
        score += int(weights.get("sourcing_title", 3))
        basis = basis or "title"

    duty_hits = [
        phrase
        for phrase in taxonomy.get("duty_phrases", [])
        if contains_phrase(body, phrase)
    ]
    if duty_hits:
        matched.extend(duty_hits)
        score += int(weights.get("duty_phrase", 4))
        basis = basis or "duty_phrase"

    high_confidence = high_hit or field_hit
    veto_hit = next(
        (
            phrase
            for phrase in taxonomy.get("veto_phrases", [])
            if contains_phrase(combined, phrase)
        ),
        "",
    )
    if veto_hit and not high_confidence:
        return {
            "procurementRelevant": "false",
            "procurementMatchScore": "0",
            "procurementMatchedTerms": f"veto:{veto_hit}",
            "procurementMatchBasis": "",
        }

    relevant = high_hit or field_hit or medium_hit or sourcing_hit or bool(duty_hits)
    # A duty phrase that is only the vetoed context should already have returned.
    if not relevant:
        return {
            "procurementRelevant": "false",
            "procurementMatchScore": "0",
            "procurementMatchedTerms": "",
            "procurementMatchBasis": "",
        }

    # De-duplicate while keeping order.
    seen: list[str] = []
    for term in matched:
        if term not in seen:
            seen.append(term)
    return {
        "procurementRelevant": "true",
        "procurementMatchScore": str(score),
        "procurementMatchedTerms": "; ".join(seen),
        "procurementMatchBasis": basis,
    }
