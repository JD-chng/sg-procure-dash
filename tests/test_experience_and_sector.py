from scripts.classify_experience import classify_experience, stated_minimum_with_evidence, stated_minimum_years
from scripts.classify_sector import classify_sector
from scripts.common import load_yaml

RULES = load_yaml("experience_rules.yml")
SECTORS = load_yaml("sector_taxonomy.yml")


def stated(**kwargs):
    defaults = {"experience_required": "", "years_min": "", "requirements": "", "description": "", "rules": RULES}
    defaults.update(kwargs)
    return stated_minimum_years(**defaults)


def test_stated_minimum_takes_the_highest_floor_written():
    assert stated(experience_required="00-08 year(s)", years_min="0", requirements="At least 3 years of relevant work experience") == 3
    assert stated(experience_required="02-15 year(s)", years_min="2") == 2
    assert stated(years_min="", requirements="Minimum 5 years in procurement") == 5


def test_stated_minimum_respects_entry_level_and_ignores_agency_history():
    assert stated(experience_required="Entry level", requirements="Candidates with at least 3 years may apply") == 0
    assert stated(description="An agency with over 50 years of service.") is None
    assert stated(requirements="Fresh graduates are welcome") == 0


def test_stated_minimum_reports_where_it_was_found():
    base = {"experience_required": "", "years_min": "", "requirements": "", "description": "", "rules": RULES}
    years, found = stated_minimum_with_evidence(**{**base, "experience_required": "00-08 year(s)", "years_min": "0", "requirements": "At least 3 years of relevant work experience"})
    assert years == 3 and found.startswith("Requirements: ") and "At least 3 years" in found
    assert stated_minimum_with_evidence(**{**base, "experience_required": "05-10 year(s)", "years_min": "5"}) == (5, "Experience field: minimum 5 years")
    assert stated_minimum_with_evidence(**{**base, "experience_required": "Entry level"}) == (0, "Experience field: Entry level")
    assert stated_minimum_with_evidence(**base) == (None, "")


def level(**kwargs):
    defaults = {
        "experience_required": "",
        "years_min": "",
        "years_max": "",
        "requirements": "",
        "description": "",
        "rules": RULES,
    }
    defaults.update(kwargs)
    return classify_experience(**defaults)


def test_experience_phrases_from_the_brief():
    fresh = level(requirements="Fresh graduates are welcome")
    assert fresh["careerLevel"] == "Fresh Graduate / Entry Level"

    at_least_three = level(requirements="At least 3 years of procurement experience")
    assert at_least_three["experienceMinYears"] == "3"
    assert at_least_three["careerLevel"] == "Broad / No Clear Preference"

    minimum_eight = level(requirements="Minimum 8 years of relevant experience")
    assert minimum_eight["careerLevel"] == "Experienced / Senior"
    assert minimum_eight["experienceMinYears"] == "8"

    mid = level(requirements="5-7 years of relevant experience")
    assert mid["careerLevel"] == "Mid-Career"
    assert mid["experienceMinYears"] == "5"
    assert mid["experienceMaxYears"] == "7"

    plus = level(requirements="8+ years")
    assert plus["careerLevel"] == "Experienced / Senior"


def test_zero_years_without_an_entry_label_stay_broad():
    silent = level(years_min="0", years_max="0")
    assert silent["careerLevel"] == "Broad / No Clear Preference"

    labelled = level(experience_required="Entry level", years_min="0", years_max="0")
    assert labelled["careerLevel"] == "Fresh Graduate / Entry Level"

    wide = level(experience_required="03-15 year(s)", years_min="3", years_max="15")
    assert wide["careerLevel"] == "Broad / No Clear Preference"

    open_ended = level(experience_required="03-99 year(s)", years_min="3", years_max="99")
    assert open_ended["careerLevel"] == "Broad / No Clear Preference"

    crossing = level(experience_required="05-10 year(s)", years_min="5", years_max="10")
    assert crossing["careerLevel"] == "Broad / No Clear Preference"


def test_sector_needs_clear_evidence():
    vague = classify_sector(
        title="Procurement Manager",
        field="Procurement",
        functional_area="Procurement",
        industry="",
        description="Coordinate the team's work and report to the director.",
        responsibilities="",
        requirements="",
        taxonomy=SECTORS,
    )
    assert vague["procurementSector"] == "Other / Unclassified"

    ict = classify_sector(
        title="Procurement Manager, Cybersecurity",
        field="Procurement",
        functional_area="Procurement",
        industry="",
        description="",
        responsibilities="",
        requirements="",
        taxonomy=SECTORS,
    )
    assert ict["procurementSector"] == "ICT / Digital / Technology"


def test_tied_sector_evidence_stays_unclassified():
    tied = classify_sector(
        title="Manager",
        field="",
        functional_area="",
        industry="",
        description="Healthcare procurement for hospital wards and rail vehicle spares.",
        responsibilities="",
        requirements="",
        taxonomy=SECTORS,
    )
    assert tied["procurementSector"] == "Other / Unclassified"
