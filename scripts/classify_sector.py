"""Config-driven procurement sector classification."""

from __future__ import annotations

from scripts.common import clean, contains_phrase, html_to_text


def classify_sector(
    *,
    title: str,
    field: str,
    functional_area: str,
    industry: str,
    description: str,
    responsibilities: str,
    requirements: str,
    taxonomy: dict,
) -> dict:
    title_text = html_to_text(title).lower()
    body = " ".join(
        html_to_text(part)
        for part in (
            field,
            functional_area,
            industry,
            description,
            responsibilities,
            requirements,
        )
    ).lower()
    title_weight = int(taxonomy.get("title_weight", 3))
    body_weight = int(taxonomy.get("body_weight", 1))
    scored: list[tuple[int, int, str, str, list[str]]] = []

    for index, sector in enumerate(taxonomy.get("sectors", [])):
        hits: list[str] = []
        score = 0
        for keyword in sector.get("keywords", []):
            in_title = contains_phrase(title_text, keyword)
            in_body = contains_phrase(body, keyword)
            if in_title:
                score += title_weight
                hits.append(keyword)
            elif in_body:
                score += body_weight
                hits.append(keyword)
        if score:
            scored.append((score, -index, sector["label"], sector["id"], hits))

    min_score = int(taxonomy.get("min_score", 3))
    min_margin = int(taxonomy.get("min_margin", 2))
    if not scored:
        return _unclassified("")

    scored.sort(reverse=True)
    best_score, _, best_label, _, best_hits = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0
    if best_score < min_score or best_score - second_score < min_margin:
        tried = "; ".join(dict.fromkeys(best_hits))
        return _unclassified(tried)
    return {
        "procurementSector": best_label,
        "sectorMatchedTerms": "; ".join(dict.fromkeys(best_hits)),
    }


def _unclassified(terms: str) -> dict:
    return {
        "procurementSector": "Other / Unclassified",
        "sectorMatchedTerms": clean(terms),
    }
