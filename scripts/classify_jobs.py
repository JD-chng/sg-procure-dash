"""Apply every classifier to the historical table."""

from __future__ import annotations

from scripts.classify_experience import classify_experience
from scripts.classify_pcf import classify_pcf
from scripts.classify_sector import classify_sector
from scripts.identify_procurement import identify_procurement
from scripts.update_history import retain_text


def classify_records(records: dict[str, dict], configs: dict) -> dict:
    stats = {
        "procurement": 0,
        "byBasis": {"title": 0, "field": 0, "duty_phrase": 0},
        "sectorOther": 0,
        "careerBroad": 0,
        "experienceParsed": 0,
    }
    for record in records.values():
        procurement = identify_procurement(
            title=record.get("jobTitle", ""),
            field=record.get("field", ""),
            functional_area=record.get("functionalArea", ""),
            description=record.get("description", ""),
            responsibilities=record.get("responsibilities", ""),
            requirements=record.get("requirements", ""),
            taxonomy=configs["procurement"],
        )
        record.update(procurement)
        if procurement["procurementRelevant"] == "true":
            stats["procurement"] += 1
            basis = procurement["procurementMatchBasis"]
            if basis in stats["byBasis"]:
                stats["byBasis"][basis] += 1
            sector = classify_sector(
                title=record.get("jobTitle", ""),
                field=record.get("field", ""),
                functional_area=record.get("functionalArea", ""),
                industry=record.get("industry", ""),
                description=record.get("description", ""),
                responsibilities=record.get("responsibilities", ""),
                requirements=record.get("requirements", ""),
                taxonomy=configs["sector"],
            )
            record.update(sector)
            if sector["procurementSector"] == "Other / Unclassified":
                stats["sectorOther"] += 1
            body = " ".join(
                [
                    record.get("description", ""),
                    record.get("responsibilities", ""),
                    record.get("requirements", ""),
                ]
            )
            record.update(
                classify_pcf(
                    title=record.get("jobTitle", ""),
                    body=body,
                    taxonomy=configs["pcf"],
                )
            )
        else:
            record["procurementSector"] = ""
            record["sectorMatchedTerms"] = ""
            record["pcfCompetencies"] = ""
            record["pcfPrimary"] = ""
            record["pcfMatchedTerms"] = ""

        experience = classify_experience(
            experience_required=record.get("experienceRequired", ""),
            years_min=record.get("experienceYearsMin", ""),
            years_max=record.get("experienceYearsMax", ""),
            requirements=record.get("requirements", ""),
            description=record.get("description", ""),
            rules=configs["experience"],
        )
        record.update(experience)
        if experience["careerLevel"] == configs["experience"]["labels"]["broad"]:
            stats["careerBroad"] += 1
        elif experience["experienceTextMatched"] or experience["experienceMinYears"]:
            stats["experienceParsed"] += 1
        retain_text(record)
    return stats
