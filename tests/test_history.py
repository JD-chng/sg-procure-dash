from datetime import date

from scripts.update_history import apply_snapshot, finalize_records


def _row(job_id, title="Procurement Manager", posting="p1", **extra):
    base = {
        "platform": "hrp",
        "jobId": job_id,
        "postingNo": posting,
        "jobTitle": title,
        "agency": "Example Agency",
        "employmentType": "Permanent",
        "startDate": "1767225600000",
        "closingDate": "1798502400000",
        "experienceRequired": "05-07 year(s)",
        "experienceYearsMin": "5",
        "experienceYearsMax": "7",
        "field": "Procurement",
        "functionalArea": "Procurement",
        "industry": "",
        "jobDescription": "Lead procurement activities.",
        "jobResponsibilities": "",
        "jobRequirements": "5-7 years of relevant experience",
    }
    base.update(extra)
    return base


def test_new_existing_and_disappeared_jobs_keep_one_row():
    records = {}
    first = apply_snapshot(records, [_row("1"), _row("2")], date(2026, 1, 10))
    assert first["new"] == 2
    assert records["hrp|1|p1"]["currentlyListed"] == "true"
    assert records["hrp|1|p1"]["firstSeenDate"] == "2026-01-10"

    second = apply_snapshot(
        records,
        [_row("1", title="Procurement Manager, Updated")],
        date(2026, 1, 12),
    )
    assert second["updated"] == 1
    assert second["unlisted"] == 1
    assert len(records) == 2
    kept = records["hrp|1|p1"]
    assert kept["firstSeenDate"] == "2026-01-10"
    assert kept["lastSeenDate"] == "2026-01-12"
    assert kept["jobTitle"] == "Procurement Manager, Updated"
    assert kept["currentlyListed"] == "true"
    gone = records["hrp|2|p1"]
    assert gone["currentlyListed"] == "false"
    assert gone["lastSeenDate"] == "2026-01-10"


def test_relisted_job_keeps_first_seen_and_increments_relist_count():
    records = {}
    apply_snapshot(records, [_row("9")], date(2026, 2, 1))
    apply_snapshot(records, [], date(2026, 2, 2))
    third = apply_snapshot(records, [_row("9")], date(2026, 2, 5))
    record = records["hrp|9|p1"]
    assert third["relisted"] == 1
    assert record["currentlyListed"] == "true"
    assert record["firstSeenDate"] == "2026-02-01"
    assert record["lastSeenDate"] == "2026-02-05"
    assert record["relistCount"] == "1"


def test_opening_stock_is_excluded_from_the_trend():
    records = {}
    apply_snapshot(
        records,
        [
            _row("1", startDate="1704067200000"),  # 2024-01-01 SGT
            _row("2", startDate="1767225600000"),  # 2026-01-01
        ],
        date(2026, 1, 15),
    )
    apply_snapshot(
        records,
        [
            _row("1", startDate="1704067200000"),
            _row("2", startDate="1767225600000"),
            _row("3", startDate="1769904000000"),
        ],
        date(2026, 2, 2),
    )
    finalize_records(records, date(2026, 2, 2), date(2026, 1, 15))
    assert records["hrp|1|p1"]["inTrend"] == "false"
    assert records["hrp|2|p1"]["inTrend"] == "true"
    assert records["hrp|3|p1"]["inTrend"] == "true"
