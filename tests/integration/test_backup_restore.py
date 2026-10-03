import hashlib
import json
from dataclasses import replace

import pytest
from test_ingestion import activity, query, references, totals
from test_ingestion import runtime as runtime
from test_recovery import retain

from workbench.backup import restored_copy
from workbench.db import health
from workbench.evidence import EvidenceService
from workbench.investigations import InvestigationService
from workbench.operations import OperationsService

pytestmark = pytest.mark.integration
TABLES = (
    "meta.SchemaMigration",
    "source.Department",
    "ops.InputArtifact",
    "ops.Load",
    "ops.Exception",
    "ops.AuditEvent",
    "ops.ReconciliationResult",
    "ops.Investigation",
    "stg.SourceRow",
    "core.Department",
    "core.Project",
    "core.Activity",
)


def snapshot(settings):
    result = {}
    for table in TABLES:
        rows = query(settings, "SELECT * FROM " + table)
        canonical = sorted(json.dumps(row, default=str, ensure_ascii=True) for row in rows)
        result[table] = {
            "count": len(rows),
            "sha256": hashlib.sha256(json.dumps(canonical).encode()).hexdigest(),
        }
    return result


def test_backup_restores_all_history_permissions_and_retry(runtime, database):
    references(runtime)
    golden = activity(runtime, "golden")["load_id"]
    evidence = EvidenceService(runtime)
    finding = evidence.exceptions(golden)["items"][0]["exception_id"]
    evidence.acknowledge(finding, "backup-reviewer", "Keep this lifecycle history")
    saved = InvestigationService(runtime).create(
        evidence, OperationsService(runtime), golden, finding, "stub", "backup-reviewer"
    )
    assert activity(runtime, "manifest-mismatch")["status"] == "failed"
    before = snapshot(runtime)
    with restored_copy(database) as (restored_admin, record):
        restored = replace(runtime, database=restored_admin.database)
        assert health(restored)["status"] == "ok"
        assert snapshot(restored) == before
        assert InvestigationService(restored).get(saved["investigation_id"]) == saved
        assert EvidenceService(restored).exception(finding)["status"] == "acknowledged"
        assert activity(restored, "corrected")["status"] == "published"
        assert activity(restored, "corrected")["status"] == "no_op"
        assert totals(restored) == (98, 197)
        assert EvidenceService(restored).exception(finding)["status"] == "resolved"
        assert totals(runtime) == (94, 189) and snapshot(runtime) == before
        record.update(
            tables_verified=before,
            saved_investigation_unchanged=True,
            restored_runtime_login_works=True,
            retry_totals=[98, 197],
            repeated_retry="no_op",
            source_unchanged=True,
        )
    assert query(database, "SELECT DB_ID(?)", (record["restored_database"],)) == [(None,)]
    record["owned_restored_database_removed"] = True
    retain("backup-restore", record)
