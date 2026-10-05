import pytest

from scripts.bootstrap_history import normalize_snapshot_rows
from scripts.validate_source import ValidationError, validate_rows

REQUIRED = ["platform", "jobId", "postingNo", "jobTitle"]


def _row(job_id="1", posting="p"):
    return {"platform": "hrp", "jobId": job_id, "postingNo": posting, "jobTitle": "Role"}


def test_empty_and_missing_columns_fail():
    with pytest.raises(ValidationError, match="no data"):
        validate_rows([], required_columns=REQUIRED, min_rows=1)
    with pytest.raises(ValidationError, match="missing columns"):
        validate_rows([{"platform": "hrp"}], required_columns=REQUIRED, min_rows=1)


def test_short_file_and_sharp_drop_fail():
    rows = [_row(str(i)) for i in range(3)]
    with pytest.raises(ValidationError, match="below the minimum"):
        validate_rows(rows, required_columns=REQUIRED, min_rows=10)
    with pytest.raises(ValidationError, match="allowed drop"):
        validate_rows(
            rows,
            required_columns=REQUIRED,
            min_rows=1,
            previous_rows=10,
            max_drop_ratio=0.5,
        )
    checked = validate_rows(
        rows,
        required_columns=REQUIRED,
        min_rows=1,
        previous_rows=10,
        max_drop_ratio=0.5,
        allow_row_drop=True,
    )
    assert checked["rows"] == 3


def test_snapshots_without_a_platform_column_are_treated_as_hrp():
    rows = normalize_snapshot_rows([{"jobId": "1", "jobTitle": "Role", "platform": ""}, {"jobId": "2", "platform": "greenhouse"}])
    assert rows[0]["platform"] == "hrp"
    assert rows[1]["platform"] == "greenhouse"


def test_duplicate_keys_fail_and_nan_closing_dates_are_usable_rows():
    with pytest.raises(ValidationError, match="duplicate"):
        validate_rows(
            [_row("1", "p"), _row("1", "p")],
            required_columns=REQUIRED,
            min_rows=1,
        )
    rows = [_row("1"), _row("2", "")]
    rows[0]["closingDate"] = "NaN"
    result = validate_rows(rows, required_columns=REQUIRED, min_rows=1, check_duplicate_keys=True)
    assert result["rows"] == 2
