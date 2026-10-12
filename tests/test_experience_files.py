import csv

import pytest

from scripts.build_dashboard_data import experience_lists
from scripts.common import load_yaml
from scripts.experience_files import write_experience_files

DASHBOARD = load_yaml("dashboard.yml")
EXPERIENCE = load_yaml("experience_rules.yml")


def _record(key, years, **extra):
    base = {
        "job_key": key,
        "jobTitle": "Procurement Manager",
        "agency": "Example Agency",
        "currentlyListed": "true",
        "procurementMatchBasis": "title",
        "firstSeenDate": "2026-05-01",
        "experienceStatedMinYears": years,
        "experienceRequired": "",
        "experienceYearsMin": "",
        "experienceYearsMax": "",
        "requirements": "",
    }
    base.update(extra)
    return base


def _read(path):
    with path.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_writes_one_list_per_band_with_evidence(tmp_path):
    (tmp_path / "old-band.csv").write_text("stale")
    records = [
        _record("hrp|1|a", "3", requirements="At least 3 years of procurement experience.", experienceRequired="00-08 year(s)", experienceYearsMin="0", experienceYearsMax="8"),
        _record("hrp|2|a", "0", experienceRequired="Entry level", currentlyListed="false", procurementMatchBasis="duty_phrase"),
        _record("hrp|3|a", ""),
    ]
    write_experience_files(
        tmp_path, records, dashboard_rules=DASHBOARD, experience_rules=EXPERIENCE,
        contract_of=lambda r: "Permanent", internship_of=lambda r: False,
    )
    assert not (tmp_path / "old-band.csv").exists()
    three = _read(tmp_path / "3-4-years.csv")
    assert [row["job_key"] for row in three] == ["hrp|1|a"]
    assert three[0]["foundIn"].startswith("Requirements: At least 3 years")
    assert three[0]["experienceFieldYears"] == "0–8"
    zero = _read(tmp_path / "0-years.csv")
    assert zero[0]["status"] == "closed" and zero[0]["population"] == "duties-only"
    assert [row["job_key"] for row in _read(tmp_path / "not-stated.csv")] == ["hrp|3|a"]
    index = {row["band_id"]: row for row in _read(tmp_path / "index.csv")}
    assert index["0-years"]["postings_all"] == "1" and index["0-years"]["postings_core"] == "0"
    assert index["3-4-years"]["open_core"] == "1"
    assert set(index) == {band["id"] for band in experience_lists(DASHBOARD)}


def test_band_ids_must_be_valid_and_unique():
    with pytest.raises(ValueError):
        experience_lists({"experience_bands": [{"label": "0 years", "min": 0, "max": 0}]})
    with pytest.raises(ValueError):
        experience_lists({"experience_bands": [{"id": "x", "label": "A", "min": 0, "max": 0}, {"id": "x", "label": "B", "min": 1, "max": 1}], "experience_not_stated_id": "y"})
