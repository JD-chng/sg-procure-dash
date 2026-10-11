from datetime import date

from scripts.build_dashboard_data import contract_type, experience_band, period_calendar
from scripts.common import load_yaml

RULES = load_yaml("dashboard.yml")


def test_contract_types_map_source_values():
    assert contract_type("Fixed Terms", RULES) == "Fixed term"
    assert contract_type("Permanent/Contract", RULES) == "Permanent or contract"
    assert contract_type("permanent", RULES) == "Permanent"
    assert contract_type("Casual", RULES) == "Contract"
    assert contract_type("", RULES) == "Not stated"
    assert contract_type("Secondment", RULES) == "Other"


def test_experience_bands_use_stated_minimum():
    assert experience_band(0, RULES) == "0 years"
    assert experience_band(2, RULES) == "1–2 years"
    assert experience_band(4, RULES) == "3–4 years"
    assert experience_band(7, RULES) == "5–7 years"
    assert experience_band(15, RULES) == "8+ years"
    assert experience_band(None, RULES) == "Not stated"


def test_partial_quarters_are_flagged_and_yoy_waits_for_a_full_year():
    calendar = period_calendar(date(2026, 2, 9), date(2026, 10, 5))
    quarters = {item["key"]: item for item in calendar["quarters"]}
    assert list(quarters) == ["2026Q1", "2026Q2", "2026Q3", "2026Q4"]
    assert quarters["2026Q1"]["complete"] is False
    assert quarters["2026Q1"]["note"] == "from 9 Feb"
    assert quarters["2026Q2"]["complete"] is True
    assert quarters["2026Q3"]["complete"] is True
    assert quarters["2026Q4"]["note"] == "to date"
    assert calendar["yoyAvailableFrom"] == "Q2 2027"
    assert calendar["months"][0]["complete"] is False
    assert calendar["months"][-1]["key"] == "2026-10"


def test_coverage_starting_on_a_quarter_boundary_counts_that_quarter():
    calendar = period_calendar(date(2026, 4, 1), date(2026, 7, 2))
    assert calendar["quarters"][0]["complete"] is True
    assert calendar["yoyAvailableFrom"] == "Q2 2027"
