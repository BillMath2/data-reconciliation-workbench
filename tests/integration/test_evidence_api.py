import csv
import json
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_ingestion import activity, query, references
from test_ingestion import runtime as runtime

from workbench import api, reports
from workbench.db import connect
from workbench.evidence import EvidenceService
from workbench.migrations import execute_batch
from workbench.pipeline import load_activities
from workbench.validation import LoadError

pytestmark = pytest.mark.integration
FIXTURES = Path("fixtures/generated/activity")
DAY = date(2026, 9, 25)


def replacement(runtime, tmp_path, rows, name):
    target = tmp_path / f"{name}.csv"
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = json.loads((FIXTURES / "corrected.manifest.json").read_text())
    manifest["row_count"] = len(rows)
    sidecar = tmp_path / f"{name}.json"
    sidecar.write_text(json.dumps(manifest))
    return load_activities(runtime, target, sidecar, actor="integration-operator")


def corrected_rows():
    with (FIXTURES / "corrected.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_api_acknowledgement_then_successor_resolution_preserves_original_evidence(runtime):
    references(runtime)
    first = activity(runtime, "golden")
    service = EvidenceService(runtime)
    packet = service.packet(first["load_id"])
    finding = service.exceptions(first["load_id"])["items"][0]
    identifier = finding["exception_id"]
    origin = "http://127.0.0.1:8000"
    app = api.create_app(runtime, analyst_token="a" * 40, operator_token="o" * 40)
    with TestClient(app, base_url=origin) as client:
        login = client.post("/api/session", headers={"Origin": origin}, json={"token": "o" * 40})
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]}
        url = f"/api/exceptions/{identifier}"
        before = client.get(url).json()
        assert before["status"] == "open" and before["rule_definition"]
        acknowledged = client.post(
            url + "/acknowledge", headers=headers, json={"reason": "Reviewed captured source"}
        )
        assert acknowledged.status_code == 200 and acknowledged.json()["changed"]
        assert not client.post(
            url + "/acknowledge", headers=headers, json={"reason": "Another reason"}
        ).json()["changed"]
        during = client.get(url).json()
        assert during["status"] == "acknowledged"
        assert during["acknowledged_by"] == "demo-operator"
        assert during["resolved_at"] is None
        assert during["events"][0]["action"] == "exception_acknowledged"
        corrected = activity(runtime, "corrected", actor="correction-operator")
        assert corrected["status"] == "published", corrected
        after = client.get(url).json()
        assert after["status"] == "resolved" and after["acknowledged_by"] == "demo-operator"
        assert after["resolved_by_load_id"] == corrected["load_id"]
        assert after["untrusted_source"] == before["untrusted_source"]
        assert after["untrusted_evidence"] == before["untrusted_evidence"]
        assert after["events"][-1]["actor"] == "correction-operator"
        assert (
            client.post(
                url + "/acknowledge", headers=headers, json={"reason": "Too late"}
            ).status_code
            == 409
        )
        assert client.get(f"/api/loads/{first['load_id']}/evidence").json() == packet
        for item in packet["evidence"]:
            assert client.get(f"/api/loads/{first['load_id']}/evidence/{item['id']}").json() == item
    assert service.exceptions(first["load_id"])["items"] == []
    assert len(service.exceptions(first["load_id"], status="resolved")["items"]) == 6
    assert query(runtime, "SELECT COUNT(*) FROM report.vw_OpenExceptions") == [(0,)]
    repeated = activity(runtime, "golden")
    assert repeated["status"] == "no_op"
    assert service.packet(repeated["load_id"]) == packet
    assert len(service.exceptions(repeated["load_id"], status="all")["items"]) == 6


def test_failed_publication_and_noop_do_not_resolve_findings(runtime):
    references(runtime)
    first = activity(runtime, "golden")
    service = EvidenceService(runtime)
    identifier = service.exceptions(first["load_id"])["items"][0]["exception_id"]
    service.acknowledge(identifier, "operator", "Review only")

    def fault(stage):
        if stage == "before_commit":
            raise RuntimeError("Rollback resolution with publication")

    failed = activity(runtime, "corrected", fault=fault)
    assert failed["status"] == "failed", failed
    assert len(service.exceptions(first["load_id"])["items"]) == 6
    assert service.exception(identifier)["status"] == "acknowledged"
    assert query(
        runtime, "SELECT COUNT(*) FROM ops.AuditEvent WHERE action='exception_resolved'"
    ) == [(0,)]
    assert activity(runtime, "golden")["status"] == "no_op"
    assert len(service.exceptions(failed["load_id"])["items"]) == 1
    corrected = activity(runtime, "corrected")
    assert corrected["status"] == "published", corrected
    failure = service.exceptions(failed["load_id"], status="all")["items"][0]
    assert failure["resolution_reason"] == "load_recovered"
    assert failure["resolved_by_load_id"] == corrected["load_id"]


def test_partial_correction_reorders_rows_and_preserves_remaining_finding(runtime, tmp_path):
    references(runtime)
    first = activity(runtime, "golden")
    rows = corrected_rows()
    next(r for r in rows if r["activity_id"] == "ACT-0095")["project_id"] = "PRJ-UNKNOWN"
    partial = replacement(runtime, tmp_path, list(reversed(rows)), "partial")
    assert partial["status"] == "published_with_exceptions", partial
    service = EvidenceService(runtime)
    remaining = service.exceptions(first["load_id"])["items"]
    assert len(remaining) == 1 and remaining[0]["row_ordinal"] == 95
    assert len(service.exceptions(first["load_id"], status="resolved")["items"]) == 5
    assert len(service.exceptions(business_date=DAY)["items"]) == 2
    corrected = activity(runtime, "corrected")
    assert corrected["status"] == "published", corrected
    assert service.exceptions(business_date=DAY)["items"] == []
    assert (
        service.exception(remaining[0]["exception_id"])["resolved_by_load_id"]
        == corrected["load_id"]
    )


def test_empty_replacement_records_removal_not_repair_and_date_isolation(runtime, tmp_path):
    references(runtime)
    first = activity(runtime, "golden")
    rows = corrected_rows()
    for row in rows:
        row["activity_date"] = "2026-09-24"
    # Use the existing helper fixture file but give the manifest its actual date.
    target = tmp_path / "other.csv"
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = json.loads((FIXTURES / "corrected.manifest.json").read_text())
    manifest["business_date"] = "2026-09-24"
    sidecar = tmp_path / "other.json"
    sidecar.write_text(json.dumps(manifest))
    assert load_activities(runtime, target, sidecar)["status"] == "published"
    service = EvidenceService(runtime)
    assert len(service.exceptions(first["load_id"])["items"]) == 6
    assert activity(runtime, "empty")["status"] == "published"
    assert {
        e["resolution_reason"] for e in service.exceptions(first["load_id"], status="all")["items"]
    } == {"key_removed"}


def test_acknowledgement_audit_failure_rolls_back_and_runtime_cannot_edit_evidence(
    runtime, database
):
    references(runtime)
    first = activity(runtime, "golden")
    service = EvidenceService(runtime)
    identifier = service.exceptions(first["load_id"])["items"][0]["exception_id"]
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        execute_batch(
            cursor,
            "CREATE TRIGGER ops.FailAcknowledgementAudit ON ops.AuditEvent AFTER INSERT AS "
            "IF EXISTS (SELECT 1 FROM inserted WHERE action='exception_acknowledged') "
            "THROW 51020, 'Injected audit failure', 1;",
        )
        connection.commit()
    with pytest.raises(Exception, match="Injected audit failure"):
        service.acknowledge(identifier, "operator", "Review")
    assert service.exception(identifier)["status"] == "open"
    assert service.exception(identifier)["events"] == []
    with closing(connect(runtime)) as connection, closing(connection.cursor()) as cursor:
        for sql in (
            "UPDATE ops.Exception SET evidence_json=N'{}' WHERE exception_id=?",
            "DELETE FROM ops.Exception WHERE exception_id=?",
        ):
            with pytest.raises(Exception, match="(?i)permission"):
                cursor.execute(sql, (identifier,))
            connection.rollback()


def test_exception_pagination_and_missing_selections(runtime):
    references(runtime)
    first = activity(runtime, "golden")
    service = EvidenceService(runtime)
    pages = [service.exceptions(first["load_id"], limit=2, offset=o)["items"] for o in (0, 2, 4)]
    ids = [item["exception_id"] for page in pages for item in page]
    assert len(ids) == len(set(ids)) == 6
    assert len(service.loads(DAY)["items"]) == 1
    with pytest.raises(LoadError, match="not found"):
        service.exception("00000000-0000-0000-0000-000000000000")
    failed = activity(runtime, "manifest-mismatch")
    assert service.exceptions(failed["load_id"])["items"]
    with pytest.raises(LoadError, match="No saved reconciliation"):
        reports.read(runtime, load_id=failed["load_id"])
