import json
import os
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from test_ingestion import activity, query, references, totals
from test_ingestion import runtime as runtime

from workbench.db import connect
from workbench.evidence import EvidenceService
from workbench.migrations import execute_batch
from workbench.recovery import recover
from workbench.validation import LoadError

pytestmark = pytest.mark.integration


def retain(name, value):
    if directory := os.environ.get("WB_P11_EVIDENCE_DIR"):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        (path / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n", "utf-8")


@pytest.mark.parametrize(
    "point",
    [
        "started",
        "after_capture",
        "after_validation",
        "after_delete",
        "before_commit",
        "after_commit",
    ],
)
def test_process_exit_recovery_and_exactly_once_retry(runtime, point):
    references(runtime)
    golden = activity(runtime, "golden")["load_id"]
    packet = EvidenceService(runtime).packet(golden)
    process = subprocess.run(
        [sys.executable, "tests/helpers/crash_loader.py", point],
        env={
            **os.environ,
            "WB_SQL_DATABASE": runtime.database,
            "WB_SQL_USERNAME": runtime.username,
            "WB_SQL_PASSWORD": runtime.password,
        },
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert process.returncode == 23, "Crash worker did not reach its controlled fault point"
    assert "Interrupted at " + point in process.stdout
    before = totals(runtime)
    assert before == ((98, 197) if point == "after_commit" else (94, 189))
    preview = recover(runtime)
    assert preview["count"] == (0 if point == "after_commit" else 1)
    assert recover(runtime) == preview  # Preview has no side effects.
    result = recover(
        runtime, apply=True, actor="recovery-operator", reason="Stopped worker verified"
    )
    assert result["count"] == preview["count"]
    assert (
        recover(runtime, apply=True, actor="recovery-operator", reason="Repeated check")["count"]
        == 0
    )
    assert totals(runtime) == before
    if result["items"]:
        load_id = result["items"][0]["load_id"]
        assert query(
            runtime, "SELECT status, failure_code FROM ops.Load WHERE load_id=?", (load_id,)
        ) == [("failed", "LOAD_INTERRUPTED")]
        events = EvidenceService(runtime).audit(load_id)["items"]
        assert [e["actor"] for e in events if e["action"] == "load_recovered"] == [
            "recovery-operator"
        ]
    retry = activity(runtime, "corrected")
    assert retry["status"] == ("no_op" if point == "after_commit" else "published")
    assert activity(runtime, "corrected")["status"] == "no_op"
    assert totals(runtime) == (98, 197)
    assert query(runtime, "SELECT COUNT(*) FROM ops.ReconciliationResult") == [(2,)]
    assert query(
        runtime, "SELECT COUNT(*) FROM ops.Load WHERE source_id='daily-activity' AND is_current=1"
    ) == [(1,)]
    assert EvidenceService(runtime).packet(golden) == packet
    retain(
        "crash-" + point,
        {
            "fault_point": point,
            "worker_exit": 23,
            "before_recovery": before,
            "recovery": result,
            "retry_status": retry["status"],
            "final_totals": [98, 197],
            "reconciliation_records": 2,
            "historical_packet_unchanged": True,
        },
    )


def test_active_ingestion_blocks_recovery(runtime):
    with closing(connect(runtime)) as connection, closing(connection.cursor()) as cursor:
        execute_batch(
            cursor,
            "EXEC sys.sp_getapplock @Resource=N'workbench:ingestion', "
            "@LockMode='Exclusive', @LockOwner='Session', @LockTimeout=0;",
        )
        with pytest.raises(LoadError, match="active"):
            recover(runtime, apply=True, reason="Must not interrupt active work")


def test_recovery_audit_failure_rolls_back_and_can_retry(runtime, database):
    with closing(connect(runtime)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute(
            "INSERT INTO ops.Load(source_id,started_by) VALUES ('daily-activity','probe')"
        )
        connection.commit()
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        execute_batch(
            cursor,
            "CREATE TRIGGER ops.FailRecoveryAudit ON ops.AuditEvent AFTER INSERT AS "
            "IF EXISTS(SELECT 1 FROM inserted WHERE action='load_recovered') "
            "THROW 51030, 'Test recovery audit fault', 1;",
        )
        connection.commit()
    with pytest.raises(Exception, match="Test recovery audit fault"):
        recover(runtime, apply=True, reason="Audit rollback rehearsal")
    assert query(runtime, "SELECT status FROM ops.Load") == [("started",)]
    assert query(runtime, "SELECT COUNT(*) FROM ops.Exception") == [(0,)]
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        execute_batch(cursor, "DROP TRIGGER ops.FailRecoveryAudit")
        connection.commit()
    assert recover(runtime, apply=True, reason="Audit restored")["count"] == 1
