import csv

import pytest

from scripts.keywords import load_keywords, match_record, write_keyword_files


def _config(**overrides):
    keyword = {"id": "gebiz", "label": "GeBIZ", "patterns": [r"\bgebiz\b"]}
    keyword.update(overrides)
    return {
        "default_fields": ["title", "responsibilities", "requirements", "description"],
        "groups": [{"id": "systems", "label": "Systems", "keywords": [keyword]}],
    }


def _record(key="hrp|1|a", **extra):
    base = {
        "job_key": key,
        "jobTitle": "Procurement Manager",
        "agency": "Example Agency",
        "responsibilities": "Run tenders on GeBIZ and manage supplier performance.",
        "requirements": "Degree in any discipline.",
        "description": "Our agency values compliance.",
        "currentlyListed": "true",
        "procurementMatchBasis": "title",
        "firstSeenDate": "2026-05-01",
        "closingDate": "2026-06-01",
    }
    base.update(extra)
    return base


def test_match_records_words_parts_and_snippet():
    keywords = load_keywords(_config())
    hits = match_record(_record(), keywords)
    assert list(hits) == ["gebiz"]
    assert hits["gebiz"].parts == ["responsibilities"]
    assert hits["gebiz"].words == ["gebiz"]
    assert "GeBIZ" in hits["gebiz"].snippet


def test_fields_limit_where_a_keyword_is_searched():
    config = _config(id="compliance", label="Compliance", patterns=[r"\bcompliance\b"], fields=["responsibilities", "requirements"])
    hits = match_record(_record(), load_keywords(config))
    assert hits == {}


def test_word_boundaries_avoid_partial_words():
    config = _config(id="sap", label="SAP", patterns=[r"\bsap\b"])
    hits = match_record(_record(responsibilities="Manage the sapling nursery budget."), load_keywords(config))
    assert hits == {}


def test_bad_config_fails_before_any_write():
    with pytest.raises(ValueError):
        load_keywords(_config(id="Bad Id"))
    with pytest.raises(ValueError):
        load_keywords(_config(fields=["summary"]))


def test_keyword_files_list_matches_and_drop_stale_files(tmp_path):
    (tmp_path / "removed-keyword.csv").write_text("old")
    keywords = load_keywords(_config())
    records = [_record(), _record("hrp|2|b", responsibilities="Nothing relevant.", currentlyListed="false")]
    hits = {r["job_key"]: match_record(r, keywords) for r in records}
    write_keyword_files(tmp_path, records, hits, keywords, contract_of=lambda r: "Permanent", internship_of=lambda r: False)
    assert not (tmp_path / "removed-keyword.csv").exists()
    with (tmp_path / "gebiz.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["job_key"] for row in rows] == ["hrp|1|a"]
    assert rows[0]["status"] == "open"
    assert rows[0]["population"] == "core"
    assert rows[0]["responsibilities"].startswith("Run tenders")
    assert rows[0]["requirements"] == ""
    with (tmp_path / "index.csv").open(encoding="utf-8-sig") as handle:
        index = list(csv.DictReader(handle))
    assert index[0]["postings_all"] == "1"
    assert index[0]["open_core"] == "1"


def test_shipped_keyword_config_loads():
    keywords = load_keywords()
    assert len({k.id for k in keywords}) == len(keywords) >= 15
