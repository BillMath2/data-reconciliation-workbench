"""Actual plan and logical-read comparison; no forced index and no latency CI threshold."""

import os
import statistics
import time
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from test_ingestion import query, references
from test_ingestion import runtime as runtime
from test_recovery import retain

from workbench.db import connect
from workbench.evidence import EXCEPTION_COLUMNS, EvidenceService
from workbench.migrations import execute_batch

pytestmark = pytest.mark.integration
QUERY = (
    "SELECT " + EXCEPTION_COLUMNS + " FROM ops.Exception e JOIN ops.Load l ON l.load_id=e.load_id "
    "WHERE e.resolved_at IS NULL AND l.business_date=? "
    "ORDER BY l.attempt_number DESC, e.row_ordinal, e.rule_id, e.exception_id "
    "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
)
PARAMS = (date(2026, 9, 25), 0, 50)
NS = {"s": "http://schemas.microsoft.com/sqlserver/2004/07/showplan"}


def measure(settings):
    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        execute_batch(cursor, "SET STATISTICS XML ON;")
        started = time.perf_counter()
        cursor.execute(QUERY, PARAMS)
        rows = [tuple(r) for r in cursor.fetchall()]
        plan = None
        while cursor.nextset():
            if cursor.description:
                for row in cursor.fetchall():
                    if isinstance(row[0], str) and "ShowPlanXML" in row[0]:
                        plan = row[0]
        elapsed = (time.perf_counter() - started) * 1000
        execute_batch(cursor, "SET STATISTICS XML OFF;")
        connection.rollback()
    assert plan, "Driver did not return an actual XML execution plan"
    tree = ET.fromstring(plan)
    counters = tree.findall(".//s:RunTimeCountersPerThread", NS)
    assert any("ActualLogicalReads" in c.attrib for c in counters)
    reads = sum(int(c.get("ActualLogicalReads", 0)) for c in counters)
    indexes = sorted({o.get("Index") for o in tree.findall(".//s:Object", NS) if o.get("Index")})
    return (
        {
            "logical_reads": reads,
            "elapsed_ms_including_plan_transfer": round(elapsed, 3),
            "rows": len(rows),
            "indexes": indexes,
        },
        plan,
        rows,
    )


def test_unresolved_page_index_reduces_reads_on_100000_activities(runtime, database):
    assert database.database.startswith("workbench_schema_test_")
    references(runtime)
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        connection.timeout = 120
        execute_batch(
            cursor,
            Path("tests/helpers/performance_seed.sql").read_text("utf-8"),
            (str(uuid4()), str(uuid4())),
        )
        # Only in the owned fixture DB: compare with the pre-P11 index set.
        execute_batch(cursor, "DROP INDEX IX_Exception_UnresolvedPage ON ops.Exception;")
        execute_batch(cursor, "UPDATE STATISTICS ops.Exception WITH FULLSCAN;")
        execute_batch(cursor, "UPDATE STATISTICS ops.Load WITH FULLSCAN;")
        connection.commit()
    assert query(runtime, "SELECT COUNT(*) FROM core.Activity") == [(100000,)]
    assert query(runtime, "SELECT COUNT(*) FROM ops.Exception WHERE resolved_at IS NULL") == [
        (100,)
    ]
    measure(database)  # Warm cache, no server-wide flush or plan-cache manipulation.
    before = [measure(database) for _ in range(3)]
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        execute_batch(
            cursor, Path("sql/migrations/009_open_exception_index.sql").read_text("utf-8")
        )
        connection.commit()
    measure(database)
    after = [measure(database) for _ in range(3)]
    assert all(item[2] == before[0][2] for item in [*before, *after])
    old_reads = statistics.median(m[0]["logical_reads"] for m in before)
    new_reads = statistics.median(m[0]["logical_reads"] for m in after)
    assert new_reads < old_reads, (before[0][0], after[0][0])
    assert "[IX_Exception_UnresolvedPage]" in after[0][0]["indexes"]
    timings = []
    for _ in range(3):
        started = time.perf_counter()
        result = EvidenceService(runtime).exceptions(business_date=PARAMS[0])
        timings.append(round((time.perf_counter() - started) * 1000, 3))
        assert len(result["items"]) == 50
        assert [r["row_ordinal"] for r in result["items"]] == list(range(99901, 99951))
    hardware = query(
        database,
        "SELECT cpu_count, physical_memory_kb, sqlserver_start_time FROM sys.dm_os_sys_info",
    )[0]
    version = query(database, "SELECT CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(100))")[0][
        0
    ]
    retain(
        "performance",
        {
            "activities": 100000,
            "historical_findings": 100000,
            "unresolved_findings": 100,
            "fixture_kind": "set-based query-only synthetic fixture; not ingestion throughput",
            "query": QUERY,
            "parameters": [str(p) for p in PARAMS],
            "sql_version": version,
            "cpu_count": hardware[0],
            "physical_memory_kb": hardware[1],
            "server_started_at": str(hardware[2]),
            "warm_cache": True,
            "before": [m[0] for m in before],
            "after": [m[0] for m in after],
            "median_logical_reads_before": old_reads,
            "median_logical_reads_after": new_reads,
            "read_reduction_percent": round(100 * (old_reads - new_reads) / old_reads, 2),
            "evidence_service_elapsed_ms": timings,
            "scope": "one selected date, first unresolved page; excludes HTTP/browser rendering",
            "identical_results": True,
        },
    )
    if directory := os.environ.get("WB_P11_EVIDENCE_DIR"):
        for name, runs in (("before", before), ("after", after)):
            (Path(directory) / f"{name}.sqlplan").write_text(runs[0][1], "utf-8")
