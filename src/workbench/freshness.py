"""Read-only feed deadline evaluation using an injected clock and publication state."""

from contextlib import closing
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from workbench.db import connect


def assess(business_date: date, now: datetime, available: bool) -> dict:
    if now.tzinfo is None:
        raise ValueError("The freshness clock must include a timezone.")
    due = datetime.combine(
        business_date + timedelta(days=1), time(9), tzinfo=ZoneInfo("America/New_York")
    )
    stale = now >= due and not available
    return {
        "business_date": business_date.isoformat(),
        "deadline_utc": due.astimezone(UTC).isoformat(),
        "observed_at": now.astimezone(UTC).isoformat(),
        "available": available,
        "status": "stale" if stale else "available" if available else "not_due",
        "rule_id": "FEED_STALE" if stale else None,
    }


def inspect(settings, business_date: date, now: datetime) -> dict:
    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM ops.Load WHERE source_id='daily-activity' "
            "AND business_date=? AND is_current=1",
            (business_date,),
        )
        available = cursor.fetchone()[0] > 0
        cursor.execute(
            "SELECT TOP (1) status FROM ops.Load WHERE source_id='daily-activity' "
            "AND business_date=? ORDER BY attempt_number DESC",
            (business_date,),
        )
        latest = cursor.fetchone()
    return {
        **assess(business_date, now, available),
        "last_attempt_status": latest[0] if latest else None,
        "failed_refresh": latest is not None and latest[0] == "failed",
    }
