"""P09 SQL persistence, attribution, lifecycle isolation, and atomic audit."""

from contextlib import closing

import pytest
from test_ingestion import activity, query, references, totals
from test_ingestion import runtime as runtime
from test_permissions_audit import client_for, login

from workbench.db import connect
from workbench.evidence import EvidenceService
from workbench.investigations import InvestigationService
from workbench.migrations import execute_batch
from workbench.operations import OperationsService

pytestmark = pytest.mark.integration


def test_saved_finding_survives_correction_and_new_service_instance(runtime):
    references(runtime)
    golden = activity(runtime, "golden")["load_id"]
    evidence = EvidenceService(runtime)
    finding = evidence.exceptions(golden)["items"][0]["exception_id"]
    original = evidence.packet(golden)
    with client_for(runtime) as client:
        headers = login(client, "analyst")
        result = client.post(
            "/api/investigations",
            headers=headers,
            json={"load_id": golden, "exception_id": finding},
        )
        assert result.status_code == 200, result.text
        saved = result.json()
        assert saved["created_by"] == "demo-analyst"
        assert saved["context"]["observation"]["selected_finding"]["status"] == "open"
        assert totals(runtime) == (94, 189)
        assert evidence.packet(golden) == original
        corrected = activity(runtime, "corrected")["load_id"]
        assert evidence.exception(finding)["status"] == "resolved"
        svc = InvestigationService(runtime)
        assert svc.get(saved["investigation_id"]) == saved
        assert (
            svc.citation(saved["investigation_id"], f"reconciliation:{golden}")["summary"][
                "accepted_rows"
            ]
            == 94
        )
        assert len(svc.list(golden)["items"]) == 1
        assert svc.list(golden, offset=1)["items"] == []
        assert svc.list(corrected)["items"] == []
        rejected = client.post(
            "/api/investigations",
            headers=headers,
            json={"load_id": corrected, "exception_id": finding},
        )
        assert rejected.status_code == 422
        event = [
            e for e in evidence.audit(golden)["items"] if e["action"] == "investigation_saved"
        ][0]
        assert event["actor"] == "demo-analyst"
        assert event["detail"]["context_sha256"] == saved["context_sha256"]


def test_noop_investigation_keeps_attempt_and_publication_separate(runtime):
    references(runtime)
    first = activity(runtime, "golden")["load_id"]
    attempt = activity(runtime, "golden")["load_id"]
    svc = InvestigationService(runtime)
    saved = svc.create(
        EvidenceService(runtime), OperationsService(runtime), attempt, None, "off", "demo-operator"
    )
    assert saved["requested_load_id"] == attempt
    assert saved["publication_load_id"] == first
    assert saved["result"]["status"] == "off"
    assert len(svc.list(attempt)["items"]) == 1 and svc.list(first)["items"] == []
    with closing(connect(runtime)) as connection, closing(connection.cursor()) as cursor:
        for sql in (
            "DELETE FROM ops.Investigation WHERE investigation_id=?",
            "UPDATE ops.Investigation SET created_by=N'forged' WHERE investigation_id=?",
        ):
            with pytest.raises(Exception, match="(?i)permission"):
                cursor.execute(sql, (saved["investigation_id"],))
            connection.rollback()


def test_required_investigation_audit_failure_rolls_back_artifact(runtime, database):
    references(runtime)
    load_id = activity(runtime, "golden")["load_id"]
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        execute_batch(
            cursor,
            "CREATE TRIGGER ops.FailInvestigationAudit ON ops.AuditEvent AFTER INSERT AS "
            "IF EXISTS (SELECT 1 FROM inserted WHERE action='investigation_saved') "
            "THROW 51021, 'Injected investigation audit failure', 1;",
        )
        connection.commit()
    with client_for(runtime) as client:
        headers = login(client, "analyst")
        response = client.post("/api/investigations", headers=headers, json={"load_id": load_id})
        assert response.status_code == 503 and "Injected" not in response.text
    assert query(runtime, "SELECT COUNT(*) FROM ops.Investigation") == [(0,)]
    assert totals(runtime) == (94, 189)


def test_failed_report_and_unauthorized_creation_have_no_artifact(runtime):
    references(runtime)
    first = activity(runtime, "golden")["load_id"]
    failed = activity(runtime, "manifest-mismatch")["load_id"]
    with client_for(runtime) as client:
        headers = login(client, "analyst")
        assert (
            client.post(
                "/api/investigations", headers=headers, json={"load_id": failed}
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/investigations",
                headers={"Origin": "http://127.0.0.1:8000"},
                json={"load_id": first},
            ).status_code
            == 403
        )
    assert query(runtime, "SELECT COUNT(*) FROM ops.Investigation") == [(0,)]
