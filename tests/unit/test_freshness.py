from datetime import UTC, date, datetime

import pytest

from workbench.freshness import assess


@pytest.mark.parametrize(
    ("clock", "available", "status"),
    [
        ("2026-09-26T12:59:59", False, "not_due"),
        ("2026-09-26T13:00:00", False, "stale"),
        ("2026-09-26T13:00:01", False, "stale"),
        ("2026-09-26T13:00:01", True, "available"),
    ],
)
def test_missing_day_deadline_with_injected_clock(clock, available, status):
    result = assess(date(2026, 9, 25), datetime.fromisoformat(clock).replace(tzinfo=UTC), available)
    assert result["status"] == status
    assert result["rule_id"] == ("FEED_STALE" if status == "stale" else None)


def test_winter_uses_standard_time_and_rejects_naive_clock():
    result = assess(date(2026, 12, 1), datetime(2026, 12, 2, 13, 30, tzinfo=UTC), False)
    assert result["status"] == "not_due"
    assert result["deadline_utc"] == "2026-12-02T14:00:00+00:00"
    with pytest.raises(ValueError, match="timezone"):
        assess(date(2026, 12, 1), datetime(2026, 12, 2), False)
