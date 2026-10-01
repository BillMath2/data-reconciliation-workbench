from datetime import UTC, date

import pytest

from workbench import operations, pipeline
from workbench.validation import LoadError


def test_snapshot_paths_and_date_are_server_controlled(monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "load_activities", lambda *a, **kw: calls.append((a, kw)))
    service = operations.OperationsService(None)
    for name, day in [("../golden", "2026-09-25"), ("corrected", "2026-09-26")]:
        with pytest.raises(LoadError):
            service.run(name, day, "demo-operator", "Review")
    assert not calls
    service.run("corrected", "2026-09-25", "demo-operator", "Correction")
    assert calls == [
        (
            (
                None,
                operations.FIXTURES / "corrected.csv",
                operations.FIXTURES / "corrected.manifest.json",
            ),
            {"actor": "demo-operator", "reason": "Correction"},
        )
    ]


def test_freshness_uses_server_utc_clock(monkeypatch):
    captured = []
    monkeypatch.setattr(operations.freshness, "inspect", lambda *a: captured.append(a))
    operations.OperationsService(None).freshness(date(2026, 9, 25))
    assert captured[0][:2] == (None, date(2026, 9, 25))
    assert captured[0][2].tzinfo == UTC


@pytest.mark.parametrize("reason", ["", "  ", "x" * 501, "😀" * 251])
def test_invalid_audit_reason_rejected_before_database_access(reason):
    class Settings:
        database = "workbench"

    with pytest.raises(LoadError, match="reason"):
        pipeline.ingest(Settings(), "daily-activity", None, reason=reason)
