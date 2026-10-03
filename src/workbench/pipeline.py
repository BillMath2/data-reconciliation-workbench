"""Single-worker ingestion with durable capture and atomic curated publication."""

import json
from contextlib import closing, suppress
from pathlib import Path
from uuid import uuid4

from workbench import lifecycle, reconciliation
from workbench.config import Settings
from workbench.db import connect
from workbench.migrations import execute_batch, validate_database_name
from workbench.sources import (
    activity_capture,
    canonical,
    department_capture,
    registry_capture,
    sha256,
)
from workbench.validation import VERSION, LoadError, contract, validate_rows

TABLES = {
    "department-reference": "Department",
    "project-registry": "Project",
    "daily-activity": "Activity",
}


def json_text(value) -> str:
    return canonical(value).decode("utf-8")


def audit(cursor, load_id, actor, action, detail):
    cursor.execute(
        "INSERT INTO ops.AuditEvent (load_id, actor, action, detail_json) VALUES (?, ?, ?, ?)",
        (load_id, actor, action, json_text(detail)),
    )


def finding(cursor, load_id, rule, evidence, ordinal=None, field=None):
    cursor.execute(
        "INSERT INTO ops.Exception "
        "(load_id, row_ordinal, rule_id, rule_set_version, field_name, evidence_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (load_id, ordinal, rule, VERSION, field, json_text(evidence)),
    )


def current(cursor, source, business_date=None):
    cursor.execute(
        "SELECT l.load_id, l.reference_set_sha256, a.content_sha256, a.content "
        "FROM ops.Load AS l JOIN ops.InputArtifact AS a ON a.artifact_id=l.artifact_id "
        "WHERE l.source_id=? AND l.is_current=1 "
        "AND (l.business_date=? OR (l.business_date IS NULL AND ? IS NULL))",
        (source, business_date, business_date),
    )
    return cursor.fetchone()


def dependency(cursor, source, reference_hash):
    publication = current(cursor, source)
    cursor.execute(
        "SELECT TOP (1) status FROM ops.Load WHERE source_id=? ORDER BY attempt_number DESC",
        (source,),
    )
    latest = cursor.fetchone()
    if (
        publication is None
        or latest is None
        or latest[0]
        not in {
            "published",
            "published_with_exceptions",
            "no_op",
        }
    ):
        raise LoadError(
            "DEPENDENCY_UNAVAILABLE", "Publish the required reference successfully first."
        )
    if publication[1] != reference_hash:
        raise LoadError(
            "REFERENCE_CHANGED", "Reference fixture set changed; use a fresh demo database."
        )
    return publication


def check_references(cursor, capture):
    if capture.reference_hash is None:
        raise LoadError("SRC_SCHEMA", "A reference-set hash is required.")
    cursor.execute(
        "SELECT TOP (1) reference_set_sha256 FROM ops.Load WHERE published_at IS NOT NULL"
    )
    fixed = cursor.fetchone()
    if fixed is not None and fixed[0] != capture.reference_hash:
        raise LoadError(
            "REFERENCE_CHANGED", "Reference fixture set changed; use a fresh demo database."
        )
    if capture.source == "department-reference":
        previous = current(cursor, capture.source)
        if previous is not None and previous[2] != sha256(capture.content):
            raise LoadError(
                "REFERENCE_CHANGED", "Department source changed; use a fresh demo database."
            )
        return None
    departments = dependency(cursor, "department-reference", capture.reference_hash)
    if capture.source == "project-registry":
        # Verify the declared fixture hash against the actual captured source pair.
        try:
            combined = {
                "departments": sorted(
                    json.loads(bytes(departments[3])), key=lambda r: r["department_id"]
                ),
                "projects": sorted(capture.records, key=lambda r: r["project_id"]),
            }
            actual = sha256(canonical(combined))
        except (KeyError, TypeError, ValueError):
            raise LoadError("SRC_SCHEMA", "Invalid reference record structure.") from None
        if actual != capture.reference_hash:
            raise LoadError(
                "REFERENCE_CHANGED", "Captured references differ from the declared fixture hash."
            )
        previous = current(cursor, capture.source)
        if previous is not None and previous[2] != sha256(capture.content):
            raise LoadError(
                "REFERENCE_CHANGED", "Registry source changed; use a fresh demo database."
            )
        cursor.execute("SELECT department_id FROM core.Department")
    else:
        dependency(cursor, "project-registry", capture.reference_hash)
        cursor.execute("SELECT project_id FROM core.Project")
    return {row[0] for row in cursor.fetchall()}


def save_capture(cursor, load_id, capture):
    artifact_id = str(uuid4())
    cursor.execute(
        "INSERT INTO ops.InputArtifact "
        "(artifact_id, source_id, content_sha256, content, metadata_json) VALUES (?, ?, ?, ?, ?)",
        (
            artifact_id,
            capture.source,
            sha256(capture.content),
            capture.content,
            json_text(capture.metadata),
        ),
    )
    cursor.execute(
        "UPDATE ops.Load SET artifact_id=?, business_date=?, reference_set_sha256=?, "
        "contract_version=?, rule_set_version=?, status='captured' WHERE load_id=?",
        (artifact_id, capture.business_date, capture.reference_hash, VERSION, VERSION, load_id),
    )


def evaluation_key(capture):
    return sha256(
        canonical(
            {
                "source": capture.source,
                "business_date": capture.business_date,
                "content_sha256": sha256(capture.content),
                "metadata": capture.metadata,
                "reference_set_sha256": capture.reference_hash,
                "contract_version": VERSION,
                "rule_set_version": VERSION,
            }
        )
    )


def stage_rows(cursor, load_id, capture, rows):
    for row in rows:
        raw = canonical(row.raw)
        cursor.execute(
            "INSERT INTO stg.SourceRow (load_id, row_ordinal, source_id, raw_record_json, "
            "row_sha256, disposition, primary_rule_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                load_id,
                row.ordinal,
                capture.source,
                raw.decode("utf-8"),
                sha256(raw),
                row.disposition,
                row.primary_rule,
            ),
        )
        for item in row.findings:
            finding(
                cursor,
                load_id,
                item.rule,
                {**item.evidence, "reference_set_sha256": capture.reference_hash},
                row.ordinal,
                item.field,
            )


def publish(cursor, load_id, capture, rows, fault=None, *, actor="cli"):
    previous = current(cursor, capture.source, capture.business_date)
    if previous is not None:
        cursor.execute(
            "UPDATE ops.Load SET is_current=0, status='superseded' WHERE load_id=?",
            (str(previous[0]),),
        )
    if capture.source == "daily-activity":
        cursor.execute("DELETE FROM core.Activity WHERE activity_date=?", (capture.business_date,))
    if fault is not None:
        fault("after_delete")
    fields = [field["name"] for field in contract(capture.source)["fields"]]
    # Only checked-in source/column mappings form SQL identifiers; all values are bound.
    table = TABLES[capture.source]
    columns = ", ".join([*fields, "origin_load_id", "origin_row_ordinal"])
    placeholders = ", ".join("?" for _ in range(len(fields) + 2))
    for row in rows:
        if row.disposition == "accepted":
            cursor.execute(
                f"INSERT INTO core.{table} ({columns}) VALUES ({placeholders})",
                (*[row.values[name] for name in fields], load_id, row.ordinal),
            )
    status = "published_with_exceptions" if any(row.findings for row in rows) else "published"
    cursor.execute(
        "UPDATE ops.Load SET status=?, is_current=1, previous_load_id=?, "
        "finished_at=SYSUTCDATETIME(), published_at=SYSUTCDATETIME() WHERE load_id=?",
        (status, str(previous[0]) if previous else None, load_id),
    )
    if capture.source == "daily-activity":
        reconciliation.save(cursor, load_id, capture, rows)
        lifecycle.resolve(cursor, load_id, capture, rows, actor)
    if fault is not None:
        fault("before_commit")
    return status


def ingest(
    settings: Settings, source: str, capture_source, *, actor="cli", fault=None, reason=None
) -> dict:
    """Capture callback receives a SQL cursor. Fault callback is test-only, never a CLI option."""
    validate_database_name(settings.database)
    if source not in TABLES or not isinstance(actor, str) or not actor.strip() or len(actor) > 128:
        raise LoadError("INVALID_REQUEST", "A supported source and a nonempty actor are required.")
    if reason is not None:
        if (
            not isinstance(reason, str)
            or not reason.strip()
            or len(reason.encode("utf-16-le")) > 1000
        ):
            raise LoadError(
                "INVALID_REQUEST", "A nonempty reason of at most 500 units is required."
            )
        reason = reason.strip()
    load_id = str(uuid4())
    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        # Fail fast if another ingestion command is active; there is no worker queue.
        cursor.execute(
            "DECLARE @r INT; EXEC @r=sys.sp_getapplock "
            "@Resource=N'workbench:ingestion', @LockMode='Exclusive', "
            "@LockOwner='Session', @LockTimeout=0; SELECT @r;"
        )
        lock = cursor.fetchone()[0]
        while cursor.nextset():
            pass
        if lock < 0:
            raise LoadError("WORKER_BUSY", "Another ingestion is active; retry after it finishes.")
        try:
            cursor.execute(
                "INSERT INTO ops.Load (load_id, source_id, started_by) VALUES (?, ?, ?)",
                (load_id, source, actor),
            )
            audit(cursor, load_id, actor, "load_started", {"reason": reason} if reason else {})
            connection.commit()
            try:
                capture = capture_source(cursor)
                if capture.source != source:
                    raise LoadError(
                        "SRC_SCHEMA", "Captured source does not match the requested source."
                    )
                save_capture(cursor, load_id, capture)
                connection.commit()
                if fault is not None:
                    fault("after_capture")
                if capture.error:
                    raise capture.error
                known = check_references(cursor, capture)
                rows = validate_rows(
                    source,
                    capture.records,
                    business_date=capture.business_date,
                    known_references=known,
                )
                key = evaluation_key(capture)
                cursor.execute(
                    "UPDATE ops.Load SET evaluation_key=? WHERE load_id=?", (key, load_id)
                )
                cursor.execute(
                    "SELECT load_id FROM ops.Load WHERE evaluation_key=? "
                    "AND published_at IS NOT NULL",
                    (key,),
                )
                reused = cursor.fetchone()
                if reused:
                    cursor.execute(
                        "UPDATE ops.Load SET status='no_op', reused_load_id=?, "
                        "finished_at=SYSUTCDATETIME() WHERE load_id=?",
                        (str(reused[0]), load_id),
                    )
                    audit(cursor, load_id, actor, "load_no_op", {"reused_load_id": str(reused[0])})
                    connection.commit()
                    return {"status": "no_op", "load_id": load_id, "reused_load_id": str(reused[0])}
                stage_rows(cursor, load_id, capture, rows)
                cursor.execute("UPDATE ops.Load SET status='validated' WHERE load_id=?", (load_id,))
                connection.commit()
                if fault is not None:
                    fault("after_validation")
                status = publish(cursor, load_id, capture, rows, fault, actor=actor)
                counts = {
                    name: sum(row.disposition == name for row in rows)
                    for name in ("accepted", "excluded_duplicate", "excluded_invalid")
                }
                audit(cursor, load_id, actor, "load_published", counts)
                connection.commit()
                result = {"status": status, "load_id": load_id, "raw_rows": len(rows), **counts}
            except Exception as error:
                connection.rollback()
                code = error.code if isinstance(error, LoadError) else "LOAD_FAILED"
                message = (
                    str(error)
                    if isinstance(error, LoadError)
                    else "Load failed; previous publication retained."
                )
                cursor.execute(
                    "UPDATE ops.Load SET status='failed', failure_code=?, "
                    "finished_at=SYSUTCDATETIME() WHERE load_id=?",
                    (code, load_id),
                )
                finding(cursor, load_id, code, {"message": message})
                audit(cursor, load_id, actor, "load_failed", {"code": code})
                connection.commit()
                return {"status": "failed", "load_id": load_id, "code": code, "message": message}
            # Simulate lost acknowledgement only after the durable transaction. A
            # test fault here must never relabel a committed publication as failed.
            if fault is not None:
                fault("after_commit")
            return result
        finally:
            with suppress(Exception):
                connection.rollback()
                execute_batch(
                    cursor,
                    "EXEC sys.sp_releaseapplock "
                    "@Resource=N'workbench:ingestion', @LockOwner='Session';",
                )
                connection.commit()


def load_departments(settings, reference_hash, **kwargs):
    return ingest(
        settings,
        "department-reference",
        lambda cursor: department_capture(cursor, reference_hash),
        **kwargs,
    )


def load_projects(settings, url, **kwargs):
    return ingest(settings, "project-registry", lambda _: registry_capture(url), **kwargs)


def load_activities(settings, csv_path: Path, manifest_path: Path, **kwargs):
    return ingest(
        settings, "daily-activity", lambda _: activity_capture(csv_path, manifest_path), **kwargs
    )
