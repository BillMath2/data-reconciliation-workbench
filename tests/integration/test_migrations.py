from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from shutil import copytree
from uuid import uuid4

import pytest

from workbench.bootstrap import create_database
from workbench.db import connect
from workbench.migrations import MigrationError, discover, execute_batch, migrate

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "sql/migrations"
VERSIONS = [m.version for m in discover(MIGRATIONS)]


def test_empty_database_migrates_and_repeats_without_reapplying(database):
    assert create_database(database)["created"] is False
    assert migrate(database, MIGRATIONS)["applied"] == VERSIONS
    assert migrate(database, MIGRATIONS)["applied"] == []
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute("SELECT version FROM meta.SchemaMigration ORDER BY version")
        assert [r[0] for r in cursor.fetchall()] == VERSIONS
        cursor.execute(
            "SELECT s.name, t.name FROM sys.tables AS t "
            "JOIN sys.schemas AS s ON s.schema_id=t.schema_id"
        )
        assert set(map(tuple, cursor.fetchall())) == {
            ("meta", "SchemaMigration"),
            ("source", "Department"),
            ("ops", "InputArtifact"),
            ("ops", "Load"),
            ("ops", "Exception"),
            ("ops", "AuditEvent"),
            ("stg", "SourceRow"),
            ("core", "Department"),
            ("core", "Project"),
            ("core", "Activity"),
        }


def test_failed_migration_rolls_back_ddl_and_ledger_and_can_retry(database, tmp_path):
    destination = tmp_path / "migrations"
    copytree(MIGRATIONS, destination)
    next_version = len(VERSIONS) + 1
    bad = destination / f"{next_version:03}_probe.sql"
    bad.write_text(
        "CREATE TABLE ops.FailureProbe (id INT); THROW 51010, 'Injected migration failure', 1;",
        encoding="utf-8",
    )
    with pytest.raises(MigrationError, match=bad.name):
        migrate(database, destination)
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute("SELECT COUNT(*) FROM meta.SchemaMigration")
        assert cursor.fetchone()[0] == len(VERSIONS)
        cursor.execute("SELECT OBJECT_ID(N'ops.FailureProbe', N'U')")
        assert cursor.fetchone()[0] is None
    bad.write_text("CREATE TABLE ops.FailureProbe (id INT);", encoding="utf-8")
    assert migrate(database, destination)["applied"] == [next_version]
    assert migrate(database, destination)["applied"] == []
    with pytest.raises(MigrationError, match="history"):
        migrate(database, MIGRATIONS)  # An older checkout must not silently ignore newer versions.


def test_existing_p02_source_seed_is_preserved(database):
    seed = (ROOT / "fixtures/generated/reference/departments.sql").read_text("utf-8")
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        execute_batch(cursor, seed)
        connection.commit()
    migrate(database, MIGRATIONS)
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute("SELECT COUNT(*) FROM source.Department")
        assert cursor.fetchone()[0] == 5


def test_identifier_patch_accepts_literal_separators_and_rejects_other_characters(database):
    migrate(database, MIGRATIONS)
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        load = stage(cursor, "department-reference")
        connection.commit()
        sql = "INSERT INTO core.Department "
        sql += "(department_id, department_name, is_active, origin_load_id, origin_row_ordinal) "
        sql += "VALUES (?, N'Synthetic', 1, ?, 1)"
        for identifier in ("DEPT-01", "D_02-A", "ABC123", "-", "_"):
            cursor.execute(sql, (identifier, load))
            connection.commit()
        for identifier in ("", "lower", "A B", "A.", "A/", "A[", "A ", "É", "A\t"):
            with pytest.raises(Exception, match="CK_Department_Id"):
                cursor.execute(sql, (identifier, load))
            connection.rollback()


def stage(cursor, source):
    artifact, load = str(uuid4()), str(uuid4())
    cursor.execute(
        "INSERT INTO ops.InputArtifact "
        "(artifact_id, source_id, content_sha256, content) VALUES (?, ?, ?, ?)",
        (artifact, source, "a" * 64, b"synthetic"),
    )
    cursor.execute(
        "INSERT INTO ops.Load (load_id, source_id, artifact_id, started_by) VALUES (?, ?, ?, ?)",
        (load, source, artifact, "pytest"),
    )
    cursor.execute(
        "INSERT INTO stg.SourceRow "
        "(load_id, row_ordinal, source_id, raw_record_json, row_sha256, disposition) "
        "VALUES (?, 1, ?, N'{}', ?, 'accepted')",
        (load, source, "b" * 64),
    )
    return load


def parents(cursor):
    department_load = stage(cursor, "department-reference")
    project_load = stage(cursor, "project-registry")
    activity_load = stage(cursor, "daily-activity")
    cursor.execute(
        "INSERT INTO core.Department "
        "(department_id, department_name, is_active, origin_load_id, origin_row_ordinal) "
        "VALUES (N'DEPT-01', N'Synthetic', 1, ?, 1)",
        (department_load,),
    )
    cursor.execute(
        "INSERT INTO core.Project "
        "(project_id, project_name, department_id, project_status, updated_at, "
        "origin_load_id, origin_row_ordinal) "
        "VALUES (N'PRJ-001', N'Synthetic', N'DEPT-01', 'active', ?, ?, 1)",
        (datetime(2026, 9, 24), project_load),
    )
    return department_load, project_load, activity_load


ACTIVITY_INSERT = """
    INSERT INTO core.Activity (activity_date, activity_id, project_id, activity_status,
        completed_units, source_updated_at, origin_load_id, origin_row_ordinal)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


@pytest.mark.parametrize(
    ("change", "constraint"),
    [
        ({"project": "PRJ-UNKNOWN"}, "FK_Activity_Project"),
        ({"units": -1}, "CK_Activity_Units"),
        ({"status": "planned", "units": 2}, "CK_Activity_Units"),
        ({"id": "lowercase"}, "CK_Activity_Id"),
        ({"ordinal": 999}, "FK_Activity_Row"),
        ({"wrong_source": True}, "FK_Activity_Row"),
    ],
)
def test_curated_rows_enforce_contract_and_lineage_constraints(database, change, constraint):
    migrate(database, MIGRATIONS)
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        department_load, _, activity_load = parents(cursor)
        connection.commit()
        load = department_load if change.get("wrong_source") else activity_load
        values = (
            date(2026, 9, 25),
            change.get("id", "ACT-0001"),
            change.get("project", "PRJ-001"),
            change.get("status", "completed"),
            change.get("units", 2),
            datetime(2026, 9, 25, 23),
            load,
            change.get("ordinal", 1),
        )
        with pytest.raises(Exception, match=constraint):
            cursor.execute(ACTIVITY_INSERT, values)
        connection.rollback()


def test_valid_activity_has_complete_lineage_and_unique_business_key(database):
    migrate(database, MIGRATIONS)
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        _, _, activity_load = parents(cursor)
        values = (
            date(2026, 9, 25),
            "ACT-0001",
            "PRJ-001",
            "completed",
            3,
            datetime(2026, 9, 25, 23),
            activity_load,
            1,
        )
        cursor.execute(ACTIVITY_INSERT, values)
        connection.commit()
        cursor.execute(
            "SELECT l.source_id, s.row_ordinal, a.completed_units "
            "FROM core.Activity AS a JOIN stg.SourceRow AS s "
            "ON s.load_id=a.origin_load_id AND s.row_ordinal=a.origin_row_ordinal "
            "JOIN ops.Load AS l ON l.load_id=s.load_id "
            "JOIN ops.InputArtifact AS i ON i.artifact_id=l.artifact_id"
        )
        assert tuple(cursor.fetchone()) == ("daily-activity", 1, 3)
        with pytest.raises(Exception, match="PK_Activity"):
            cursor.execute(ACTIVITY_INSERT, values)
        connection.rollback()


@pytest.mark.parametrize(
    ("same_key", "constraint"),
    [
        (True, "UX_Load_PublishedEvaluation"),
        (False, "UX_Load_Current"),
    ],
)
def test_only_one_successful_evaluation_and_current_publication(database, same_key, constraint):
    migrate(database, MIGRATIONS)
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        first = stage(cursor, "daily-activity")
        second = stage(cursor, "daily-activity")
        publish = """UPDATE ops.Load SET business_date='2026-09-25',
            reference_set_sha256=?, contract_version='1.0.0', rule_set_version='1.0.0',
            evaluation_key=?, status='published', is_current=?,
            published_at=SYSUTCDATETIME(), finished_at=SYSUTCDATETIME() WHERE load_id=?"""
        cursor.execute(publish, ("a" * 64, "c" * 64, 1, first))
        connection.commit()
        with pytest.raises(Exception, match=constraint):
            cursor.execute(
                publish, ("a" * 64, ("c" if same_key else "d") * 64, 0 if same_key else 1, second)
            )
        connection.rollback()


def test_runtime_role_can_write_pipeline_data_but_not_schema_or_source(database):
    migrate(database, MIGRATIONS)
    with closing(connect(database)) as connection, closing(connection.cursor()) as cursor:
        execute_batch(
            cursor,
            "CREATE USER runtime_probe WITHOUT LOGIN; "
            "ALTER ROLE workbench_runtime ADD MEMBER runtime_probe;",
        )
        connection.commit()
        execute_batch(cursor, "EXECUTE AS USER='runtime_probe';")
        try:
            parents(cursor)  # Permitted artifact, load, staging, and curated inserts.
            connection.commit()
            for sql in (
                "CREATE TABLE dbo.NotAllowed (id INT)",
                "INSERT INTO meta.SchemaMigration (version, name) VALUES (99, N'not_allowed')",
                "INSERT INTO source.Department VALUES (N'NO', N'Not allowed', 1)",
                "DELETE FROM ops.InputArtifact WHERE 1=0",
            ):
                with pytest.raises(Exception, match="(?i)permission"):
                    execute_batch(cursor, sql)
                connection.rollback()
        finally:
            execute_batch(cursor, "REVERT;")
            connection.commit()
