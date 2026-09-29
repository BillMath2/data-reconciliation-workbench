import json
import os
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from workbench.bootstrap import provision_runtime
from workbench.db import connect
from workbench.freshness import inspect
from workbench.migrations import execute_batch, migrate
from workbench.pipeline import load_activities, load_departments, load_projects

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures/generated"
HASHES = json.loads((FIXTURES / "index.json").read_text())["reference_sets"]
GOLDEN = json.loads((ROOT / "fixtures/expected/golden.json").read_text())


def query(settings, sql, params=()):
    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute(sql, params) if params else cursor.execute(sql)
        return [tuple(row) for row in cursor.fetchall()]


@pytest.fixture
def runtime(database):
    migrate(database, ROOT / "sql/migrations")
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        execute_batch(cursor, (FIXTURES / "reference/departments.sql").read_text("utf-8"))
        connection.commit()
    provision_runtime(database)
    return replace(database, username="workbench_app", password=database.runtime_password)


def registry(scenario="default"):
    return (
        os.environ.get("WB_TEST_REGISTRY_URL", "http://127.0.0.1:8001/projects")
        + f"?scenario={scenario}"
    )


def references(runtime, scenario="default"):
    departments = load_departments(runtime, HASHES[scenario], actor="integration-operator")
    assert departments["status"] == "published", departments
    projects = load_projects(runtime, registry(scenario), actor="integration-operator")
    assert projects["status"] in {"published", "published_with_exceptions"}, projects
    return departments, projects


def activity(runtime, name, **kwargs):
    return load_activities(
        runtime,
        FIXTURES / f"activity/{name}.csv",
        FIXTURES / f"activity/{name}.manifest.json",
        **kwargs,
    )


def totals(runtime):
    return query(runtime, "SELECT COUNT(*), COALESCE(SUM(completed_units), 0) FROM core.Activity")[
        0
    ]


def test_golden_correction_noop_and_empty_snapshot_retain_history(runtime):
    departments, projects = references(runtime)
    assert load_departments(runtime, HASHES["default"])["status"] == "no_op"
    assert load_projects(runtime, registry())["status"] == "no_op"
    first = activity(runtime, "golden")
    assert first["status"] == "published_with_exceptions", first
    expected = GOLDEN["golden"]
    assert totals(runtime) == (expected["accepted_rows"], expected["curated_completed_units"])
    assert query(
        runtime,
        "SELECT row_ordinal, primary_rule_id FROM stg.SourceRow "
        "WHERE load_id=? AND disposition<>'accepted' ORDER BY row_ordinal",
        (first["load_id"],),
    ) == [(row["row_ordinal"], row["rule_id"]) for row in expected["exclusions"]]
    assert query(
        runtime, "SELECT COUNT(*) FROM ops.Exception WHERE load_id=?", (first["load_id"],)
    ) == [(6,)]
    repeated = activity(runtime, "golden")
    assert repeated["status"] == "no_op", repeated
    assert repeated["reused_load_id"].lower() == first["load_id"].lower()
    assert query(
        runtime, "SELECT COUNT(*) FROM stg.SourceRow WHERE load_id=?", (repeated["load_id"],)
    ) == [(0,)]
    corrected = activity(runtime, "corrected")
    assert corrected["status"] == "published", corrected
    expected = GOLDEN["corrected"]
    assert totals(runtime) == (expected["accepted_rows"], expected["curated_completed_units"])
    assert query(
        runtime, "SELECT status, is_current FROM ops.Load WHERE load_id=?", (first["load_id"],)
    ) == [("superseded", False)]
    assert query(
        runtime, "SELECT COUNT(*) FROM stg.SourceRow WHERE load_id=?", (first["load_id"],)
    ) == [(100,)]
    assert activity(runtime, "corrected")["status"] == "no_op"
    assert activity(runtime, "empty")["status"] == "published"
    assert totals(runtime) == (0, 0)
    # Historical successful input is a no-op, never an implicit rollback to older data.
    assert activity(runtime, "corrected")["status"] == "no_op"
    assert totals(runtime) == (0, 0)
    assert query(
        runtime, "SELECT COUNT(*) FROM ops.Load WHERE source_id='daily-activity' AND is_current=1"
    ) == [(1,)]
    assert (
        query(runtime, "SELECT COUNT(*) FROM ops.AuditEvent WHERE action='load_no_op'")[0][0] == 5
    )
    assert departments["accepted"] == 5 and projects["accepted"] == 25


@pytest.mark.parametrize("point", ["after_delete", "before_commit"])
def test_failed_publication_rolls_back_replacement_and_state_then_retries(runtime, point):
    references(runtime)
    first = activity(runtime, "golden")
    assert first["status"] == "published_with_exceptions", first
    before = query(
        runtime,
        "SELECT activity_id, completed_units, origin_load_id "
        "FROM core.Activity ORDER BY activity_id",
    )

    def fault(stage):
        if stage == point:
            raise RuntimeError("Injected publication failure with private diagnostic")

    failed = activity(runtime, "corrected", fault=fault)
    assert failed["status"] == "failed" and failed["code"] == "LOAD_FAILED", failed
    assert "private" not in json.dumps(failed)
    assert (
        query(
            runtime,
            "SELECT activity_id, completed_units, origin_load_id "
            "FROM core.Activity ORDER BY activity_id",
        )
        == before
    )
    assert query(
        runtime, "SELECT is_current FROM ops.Load WHERE load_id=?", (first["load_id"],)
    ) == [(True,)]
    assert query(
        runtime, "SELECT published_at FROM ops.Load WHERE load_id=?", (failed["load_id"],)
    ) == [(None,)]
    assert query(
        runtime, "SELECT COUNT(*) FROM stg.SourceRow WHERE load_id=?", (failed["load_id"],)
    ) == [(98,)]
    assert activity(runtime, "corrected")["status"] == "published"
    assert totals(runtime) == (98, 197)


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("manifest-mismatch", "SRC_MANIFEST_COUNT"),
        ("schema-mismatch", "SRC_SCHEMA"),
        ("mixed-date", "SRC_BUSINESS_DATE"),
    ],
)
def test_structural_failures_preserve_previous_publication_and_capture(runtime, name, code):
    references(runtime)
    assert activity(runtime, "golden")["status"] == "published_with_exceptions"
    failed = activity(runtime, name)
    assert failed["code"] == code, failed
    assert totals(runtime) == (94, 189)
    evidence = query(
        runtime,
        "SELECT a.content FROM ops.InputArtifact a JOIN ops.Load l "
        "ON l.artifact_id=a.artifact_id WHERE l.load_id=?",
        (failed["load_id"],),
    )
    assert bytes(evidence[0][0]) == (FIXTURES / f"activity/{name}.csv").read_bytes()
    assert query(
        runtime,
        "SELECT rule_id FROM ops.Exception WHERE load_id=? AND row_ordinal IS NULL",
        (failed["load_id"],),
    ) == [(code,)]


@pytest.mark.parametrize(
    ("name", "accepted"),
    [
        ("duplicates", 98),
        ("conflict", 98),
        ("invalid-status", 99),
        ("invalid-units", 99),
    ],
)
def test_row_fault_scenarios_publish_only_valid_rows(runtime, name, accepted):
    references(runtime)
    result = activity(runtime, name)
    assert result["status"] == "published_with_exceptions", result
    assert result["accepted"] == accepted
    assert sum(result[key] for key in ("accepted", "excluded_duplicate", "excluded_invalid")) == 100
    assert totals(runtime)[0] == accepted


def test_unknown_department_evidence_propagates_to_activity_quarantine(runtime):
    _, projects = references(runtime, "unknown-department")
    assert projects["accepted"] == 24
    assert projects["excluded_invalid"] == 1
    result = activity(runtime, "unknown-department")
    assert result["accepted"] == 96, result
    assert query(
        runtime,
        "SELECT row_ordinal FROM stg.SourceRow WHERE load_id=? "
        "AND primary_rule_id='ACTIVITY_UNKNOWN_PROJECT' ORDER BY row_ordinal",
        (result["load_id"],),
    ) == [(1,), (26,), (51,), (76,)]


def test_missing_and_failed_dependencies_block_publication_until_successful_retry(runtime):
    assert activity(runtime, "golden")["code"] == "DEPENDENCY_UNAVAILABLE"
    references(runtime)
    assert activity(runtime, "golden")["status"] == "published_with_exceptions"
    incomplete = load_projects(runtime, registry("incomplete"))
    assert incomplete["code"] == "SRC_PAGINATION", incomplete
    assert activity(runtime, "corrected")["code"] == "DEPENDENCY_UNAVAILABLE"
    assert totals(runtime) == (94, 189)
    assert load_projects(runtime, registry())["status"] == "no_op"
    assert activity(runtime, "corrected")["status"] == "published"


def test_changed_reference_hash_and_actual_source_changes_are_rejected(runtime, database):
    references(runtime)
    assert load_departments(runtime, HASHES["unknown-department"])["code"] == "REFERENCE_CHANGED"
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute(
            "UPDATE source.Department SET department_name=N'Changed' WHERE department_id=N'DEPT-01'"
        )
        connection.commit()
    assert load_departments(runtime, HASHES["default"])["code"] == "REFERENCE_CHANGED"
    assert query(
        runtime, "SELECT department_name FROM core.Department WHERE department_id=N'DEPT-01'"
    ) == [("Synthetic Department 1",)]


def test_replacing_one_date_does_not_delete_other_dates(runtime, tmp_path):
    references(runtime)
    assert activity(runtime, "golden")["status"] == "published_with_exceptions"
    csv = tmp_path / "day.csv"
    csv.write_bytes(
        (FIXTURES / "activity/clean.csv").read_bytes().replace(b"2026-09-25", b"2026-09-24")
    )
    manifest = json.loads((FIXTURES / "activity/clean.manifest.json").read_text())
    manifest["business_date"] = "2026-09-24"
    sidecar = tmp_path / "day.json"
    sidecar.write_text(json.dumps(manifest))
    assert load_activities(runtime, csv, sidecar)["status"] == "published"
    assert activity(runtime, "empty")["status"] == "published"
    assert totals(runtime) == (100, 201)


def test_freshness_does_not_substitute_an_older_day_and_empty_day_is_available(runtime):
    references(runtime)
    clock = datetime(2026, 9, 27, 14, tzinfo=UTC)
    assert activity(runtime, "empty")["status"] == "published"
    assert inspect(runtime, date(2026, 9, 25), clock)["status"] == "available"
    assert inspect(runtime, date(2026, 9, 26), clock)["rule_id"] == "FEED_STALE"
    assert activity(runtime, "manifest-mismatch")["status"] == "failed"
    result = inspect(runtime, date(2026, 9, 25), clock)
    assert result["available"] is True and result["failed_refresh"] is True
