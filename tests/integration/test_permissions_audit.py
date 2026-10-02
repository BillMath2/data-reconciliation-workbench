"""P08: database effects, attributable attempts, and mandatory audit rollback."""

from contextlib import closing

import pytest
from fastapi.testclient import TestClient
from test_ingestion import activity, query, references, totals
from test_ingestion import runtime as runtime

from workbench import api
from workbench.db import connect
from workbench.evidence import EvidenceService
from workbench.migrations import execute_batch

pytestmark = pytest.mark.integration
ORIGIN = "http://127.0.0.1:8000"


def client_for(runtime):
    return TestClient(
        api.create_app(runtime, analyst_token="a" * 40, operator_token="o" * 40), base_url=ORIGIN
    )


def login(client, role="operator"):
    result = client.post(
        "/api/session",
        headers={"Origin": ORIGIN},
        json={"token": ("a" if role == "analyst" else "o") * 40},
    )
    assert result.status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": result.json()["csrf_token"]}


def run(client, headers, snapshot, reason="Source owner supplied correction"):
    return client.post(
        "/api/activity-runs",
        headers=headers,
        json={
            "snapshot": snapshot,
            "business_date": "2026-09-25",
            "reason": reason,
        },
    )


def counts(runtime):
    return query(
        runtime,
        "SELECT (SELECT COUNT(*) FROM ops.Load), "
        "(SELECT COUNT(*) FROM ops.AuditEvent), (SELECT COUNT(*) FROM ops.Exception), "
        "(SELECT COUNT(*) FROM core.Activity), (SELECT COUNT(*) FROM ops.InputArtifact)",
    )


def test_denied_operator_requests_leave_sql_unchanged(runtime, monkeypatch):
    references(runtime)
    golden = activity(runtime, "golden")
    service = EvidenceService(runtime)
    finding = service.exceptions(golden["load_id"])["items"][0]["exception_id"]
    original = service.exception(finding)
    packet = service.packet(golden["load_id"])
    baseline = counts(runtime)
    with client_for(runtime) as client:
        for fault in (
            "analyst",
            "no_csrf",
            "wrong_csrf",
            "other_origin",
            "no_origin",
            "null_origin",
            "forged_cookie",
            "logged_out",
            "rotated",
            "spoof_actor",
            "expired",
        ):
            client.cookies.clear()
            headers = login(client, "analyst" if fault == "analyst" else "operator")
            extra = {}
            if fault == "no_csrf":
                headers.pop("X-CSRF-Token")
            elif fault == "wrong_csrf":
                headers["X-CSRF-Token"] = "wrong"
            elif fault in {"other_origin", "null_origin"}:
                headers["Origin"] = "null" if fault == "null_origin" else "http://localhost:8000"
            elif fault == "no_origin":
                headers.pop("Origin")
            elif fault == "forged_cookie":
                client.cookies.clear()
                client.cookies.set(api.COOKIE, "demo-operator")
            elif fault == "logged_out":
                old = client.cookies[api.COOKIE]
                client.post("/api/session/logout", headers=headers, json={})
                client.cookies.set(api.COOKIE, old)
            elif fault == "rotated":
                login(client)
            elif fault == "spoof_actor":
                extra = {"actor": "administrator"}
            with monkeypatch.context() as patch:
                if fault == "expired":
                    now = api.time.monotonic()
                    patch.setattr(
                        api.time, "monotonic", lambda now=now: now + api.SESSION_SECONDS + 1
                    )
                for path, body in [
                    (
                        "/api/activity-runs",
                        {"snapshot": "corrected", "business_date": "2026-09-25"},
                    ),
                    (f"/api/exceptions/{finding}/acknowledge", {}),
                ]:
                    response = client.post(
                        path, headers=headers, json={**body, "reason": "Unauthorized", **extra}
                    )
                    assert response.status_code in {401, 403, 422}, (fault, path, response.text)
        assert counts(runtime) == baseline
        assert service.exception(finding) == original
        assert service.packet(golden["load_id"]) == packet
        assert totals(runtime) == (94, 189)


def test_load_audit_tracks_distinct_noop_and_failed_attempts_and_is_append_only(runtime):
    references(runtime)
    with client_for(runtime) as client:
        headers = login(client)
        first = run(client, headers, "golden", "  Reviewed golden source  ").json()
        assert first["status"] == "published_with_exceptions", first
        first_id = first["load_id"]
        finding = client.get(f"/api/exceptions?load_id={first_id}").json()["items"][0][
            "exception_id"
        ]
        ack_url = f"/api/exceptions/{finding}/acknowledge"
        assert client.post(ack_url, headers=headers, json={"reason": "Review evidence"}).json()[
            "changed"
        ]
        assert not client.post(ack_url, headers=headers, json={"reason": "Later reason"}).json()[
            "changed"
        ]
        corrected = run(client, headers, "corrected").json()
        assert corrected["status"] == "published", corrected
        repeated = run(client, headers, "corrected", "Verify unchanged source").json()
        assert repeated["status"] == "no_op", repeated
        failed = activity(
            runtime, "manifest-mismatch", actor="fixture-operator", reason="Test bad feed"
        )
        assert failed["status"] == "failed", failed
        # Both roles can inspect; no-op audit belongs to its own attempted run.
        for role in ("operator", "analyst"):
            login(client, role)
            audit = client.get(f"/api/loads/{first_id}/audit").json()
            assert audit["load"]["started_by"] == "demo-operator"
            events = audit["items"]
            assert events[0]["action"] == "load_started"
            assert events[0]["detail"]["reason"] == "Reviewed golden source"
            assert all(e["actor"] == "demo-operator" and e["occurred_at"] for e in events)
            assert sum(e["action"] == "exception_acknowledged" for e in events) == 1
            assert sum(e["action"] == "exception_resolved" for e in events) == 6
            pages = [
                client.get(f"/api/loads/{first_id}/audit?limit=2&offset={o}").json()["items"]
                for o in range(0, len(events), 2)
            ]
            assert [e for page in pages for e in page] == events
            no_op = client.get(f"/api/loads/{repeated['load_id']}/audit").json()
            assert no_op["load"]["load_id"] == repeated["load_id"]
            assert no_op["load"]["reused_load_id"] == corrected["load_id"]
            assert [e["action"] for e in no_op["items"]] == ["load_started", "load_no_op"]
            assert no_op["items"][0]["detail"]["reason"] == "Verify unchanged source"
            failure = client.get(f"/api/loads/{failed['load_id']}/audit").json()
            assert failure["load"]["status"] == "failed"
            assert [e["action"] for e in failure["items"]] == ["load_started", "load_failed"]
            assert failure["items"][1]["actor"] == "fixture-operator"
        unknown = "00000000-0000-0000-0000-000000000000"
        assert client.get(f"/api/loads/{unknown}/audit").status_code == 404
    with closing(connect(runtime)) as connection, closing(connection.cursor()) as cursor:
        for sql in (
            "UPDATE ops.AuditEvent SET actor=N'forged' WHERE load_id=?",
            "DELETE FROM ops.AuditEvent WHERE load_id=?",
        ):
            with pytest.raises(Exception, match="(?i)permission"):
                cursor.execute(sql, (first_id,))
            connection.rollback()


def test_required_load_audit_failures_prevent_unaudited_publication(runtime, database):
    references(runtime)
    golden = activity(runtime, "golden")
    service = EvidenceService(runtime)
    old_packet = service.packet(golden["load_id"])

    def trigger(action):
        with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
            execute_batch(cursor, "DROP TRIGGER IF EXISTS ops.FailRequiredAudit;")
            # The action value comes only from the fixed test cases below.
            execute_batch(
                cursor,
                "CREATE TRIGGER ops.FailRequiredAudit ON ops.AuditEvent AFTER INSERT AS "
                f"IF EXISTS (SELECT 1 FROM inserted WHERE action='{action}') "
                "THROW 51021, 'Injected required audit failure', 1;",
            )
            connection.commit()

    with client_for(runtime) as client:
        headers = login(client)
        baseline = counts(runtime)
        trigger("load_started")
        blocked = run(client, headers, "corrected")
        assert blocked.status_code == 503
        assert "Injected" not in blocked.text
        assert counts(runtime) == baseline
        trigger("load_published")
        failed = run(client, headers, "corrected").json()
        assert failed["status"] == "failed", failed
        assert totals(runtime) == (94, 189)
        assert service.packet(golden["load_id"]) == old_packet
        assert len(service.exceptions(golden["load_id"])["items"]) == 6
        events = service.audit(failed["load_id"])["items"]
        assert [e["action"] for e in events] == ["load_started", "load_failed"]
        assert all(e["actor"] == "demo-operator" for e in events)
        assert query(
            runtime, "SELECT COUNT(*) FROM ops.AuditEvent WHERE action='exception_resolved'"
        ) == [(0,)]
        trigger("load_no_op")
        failed_noop = run(client, headers, "golden").json()
        assert failed_noop["status"] == "failed", failed_noop
        assert totals(runtime) == (94, 189)
        assert [e["action"] for e in service.audit(failed_noop["load_id"])["items"]] == [
            "load_started",
            "load_failed",
        ]
