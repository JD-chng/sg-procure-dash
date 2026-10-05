"""Multi-label competency tagging from a public, editable phrase list."""

from __future__ import annotations

from scripts.common import contains_phrase, html_to_text


def classify_pcf(*, title: str, body: str, taxonomy: dict) -> dict:
    text = f"{html_to_text(title)} {html_to_text(body)}".lower()
    ranked: list[tuple[int, int, str, str, list[str]]] = []
    for index, competency in enumerate(taxonomy.get("competencies", [])):
        hits = [
            phrase
            for phrase in competency.get("phrases", [])
            if contains_phrase(text, phrase)
        ]
        if hits:
            ranked.append((len(hits), -index, competency["id"], competency["label"], hits))
    if not ranked:
        return {"pcfCompetencies": "", "pcfPrimary": "", "pcfMatchedTerms": ""}
    ranked.sort(reverse=True)
    labels = [item[3] for item in sorted(ranked, key=lambda item: -item[1])]
    # Keep config order for the stored list; primary is the highest hit count.
    ordered = []
    for competency in taxonomy.get("competencies", []):
        if competency["label"] in labels:
            ordered.append(competency["label"])
    primary = ranked[0][3]
    terms = []
    for item in ranked:
        for phrase in item[4]:
            if phrase not in terms:
                terms.append(phrase)
    return {
        "pcfCompetencies": "; ".join(ordered),
        "pcfPrimary": primary,
        "pcfMatchedTerms": "; ".join(terms),
    }
