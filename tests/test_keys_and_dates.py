from datetime import date, datetime
from zoneinfo import ZoneInfo

from scripts.common import job_url, make_job_key, parse_epoch_ms, parse_iso, today_sgt


def test_job_key_keeps_empty_posting_number():
    assert make_job_key("greenhouse", "4007414201", "") == "greenhouse|4007414201|"
    assert make_job_key("greenhouse", "4007414201", None) == "greenhouse|4007414201|"


def test_workable_key_uses_shortcode_not_account_alone():
    first = make_job_key("workable", "psd-sg", "69C959EF15")
    second = make_job_key("workable", "psd-sg", "ABCDEF1234")
    assert first != second
    assert first == "workable|psd-sg|69C959EF15"


def test_job_urls_follow_platform_patterns():
    assert job_url("hrp", "15219929", "005056a3-d347-1fe1-80df-725f7689c286").endswith(
        "/jobs/hrp/15219929/005056a3-d347-1fe1-80df-725f7689c286"
    )
    assert "gh_jid=4001978201" in job_url("greenhouse", "4001978201", "")
    assert job_url("workable", "psd-sg", "69C959EF15") == "https://apply.workable.com/j/69C959EF15"
    assert job_url("hrp", "", "abc") == ""


def test_epoch_milliseconds_and_nan_closing_dates():
    assert parse_epoch_ms("1781049600000") == date(2026, 6, 10)
    assert parse_epoch_ms("NaN") is None
    assert parse_epoch_ms("") is None
    assert parse_epoch_ms("null") is None
    # 13-digit timestamps must not be read as a compact calendar date.
    assert parse_iso("1792022400000") is None
    assert parse_epoch_ms("1792022400000") == date(2026, 10, 15)
    assert parse_epoch_ms("253402214400000") is None


def test_run_date_uses_singapore_not_utc_near_midnight():
    # 17:30 UTC is 01:30 the next calendar day in Singapore.
    moment = datetime(2026, 10, 5, 17, 30, tzinfo=ZoneInfo("UTC"))
    assert today_sgt(moment) == date(2026, 10, 6)
