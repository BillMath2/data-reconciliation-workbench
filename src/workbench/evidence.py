"""Read-only saved evidence plus the explicit, audited acknowledgement operation."""

import json
from contextlib import closing
from pathlib import Path
from uuid import UUID

from workbench import reports
from workbench.db import connect
from workbench.validation import LoadError

EXCEPTION_COLUMNS = (
    "e.exception_id, e.load_id, e.row_ordinal, e.rule_id, e.rule_set_version, "
    "e.field_name, e.created_at, e.acknowledged_at, e.acknowledged_by, "
    "e.acknowledgement_reason, e.resolved_at, e.resolved_by_load_id, e.resolution_reason"
)


def identifier(value):
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise LoadError("INVALID_REQUEST", "Expected a UUID.") from None


def exception_record(row):
    names = (
        "exception_id",
        "load_id",
        "row_ordinal",
        "rule_id",
        "rule_set_version",
        "field_name",
        "created_at",
        "acknowledged_at",
        "acknowledged_by",
        "acknowledgement_reason",
        "resolved_at",
        "resolved_by_load_id",
        "resolution_reason",
    )
    result = dict(zip(names, row[:13], strict=True))
    for key in ("exception_id", "load_id", "resolved_by_load_id"):
        if result[key] is not None:
            result[key] = str(result[key]).lower()
    result["status"] = (
        "resolved"
        if result["resolved_at"]
        else ("acknowledged" if result["acknowledged_at"] else "open")
    )
    return result


class EvidenceService:
    def __init__(self, settings):
        self.settings = settings

    def report(self, load_id):
        return reports.read(self.settings, load_id=identifier(load_id))

    def packet(self, load_id):
        return self.report(load_id)["packet"]

    def citation(self, load_id, evidence_id):
        packet = self.packet(load_id)
        for item in packet["evidence"]:
            if item["id"] == evidence_id and evidence_id in packet["citation_ids"]:
                return item
        raise LoadError("NOT_FOUND", "Evidence ID is not in this saved packet.")

    def audit(self, load_id, limit=50, offset=0):
        """Return this attempt's history, never a no-op's reused publication history."""
        load_id = identifier(load_id)
        with closing(connect(self.settings)) as connection, closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT source_id, business_date, status, started_by, started_at, "
                "reused_load_id FROM ops.Load WHERE load_id=?",
                (load_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise LoadError("NOT_FOUND", "Load not found.")
            load = dict(
                zip(
                    (
                        "source_id",
                        "business_date",
                        "status",
                        "started_by",
                        "started_at",
                        "reused_load_id",
                    ),
                    row,
                    strict=True,
                )
            )
            load["load_id"] = load_id
            if load["reused_load_id"] is not None:
                load["reused_load_id"] = str(load["reused_load_id"]).lower()
            cursor.execute(
                "SELECT event_id, actor, action, occurred_at, detail_json FROM ops.AuditEvent "
                "WHERE load_id=? ORDER BY occurred_at, event_id "
                "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
                (load_id, offset, limit),
            )
            items = [
                {
                    "event_id": str(r[0]).lower(),
                    "actor": r[1],
                    "action": r[2],
                    "occurred_at": r[3],
                    "detail": json.loads(r[4]),
                }
                for r in cursor.fetchall()
            ]
        return {"load": load, "items": items, "limit": limit, "offset": offset}

    def loads(self, business_date=None, limit=50, offset=0):
        with closing(connect(self.settings)) as connection, closing(connection.cursor()) as cursor:
            clause = "WHERE source_id='daily-activity'"
            params = []
            if business_date:
                clause += " AND business_date=?"
                params.append(business_date)
            cursor.execute(
                "SELECT load_id, business_date, status, is_current, started_at, "
                "published_at, reused_load_id, previous_load_id, failure_code FROM ops.Load "
                + clause
                + " ORDER BY attempt_number DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
                (*params, offset, limit),
            )
            names = (
                "load_id",
                "business_date",
                "status",
                "is_current",
                "started_at",
                "published_at",
                "reused_load_id",
                "previous_load_id",
                "failure_code",
            )
            items = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
            for item in items:
                for key in ("load_id", "reused_load_id", "previous_load_id"):
                    if item[key] is not None:
                        item[key] = str(item[key]).lower()
            return {"items": items, "limit": limit, "offset": offset}

    def exceptions(self, load_id=None, business_date=None, status="unresolved", limit=50, offset=0):
        states = {
            "all": "1=1",
            "unresolved": "e.resolved_at IS NULL",
            "resolved": "e.resolved_at IS NOT NULL",
            "open": "e.resolved_at IS NULL AND e.acknowledged_at IS NULL",
            "acknowledged": "e.resolved_at IS NULL AND e.acknowledged_at IS NOT NULL",
        }
        if status not in states:
            raise LoadError("INVALID_REQUEST", "Unknown exception status.")
        with closing(connect(self.settings)) as connection, closing(connection.cursor()) as cursor:
            clauses, params = [states[status]], []
            if load_id:
                cursor.execute(
                    "SELECT COALESCE(reused_load_id, load_id) FROM ops.Load WHERE load_id=?",
                    (identifier(load_id),),
                )
                selected = cursor.fetchone()
                if selected is None:
                    raise LoadError("NOT_FOUND", "Load not found.")
                clauses.append("e.load_id=?")
                params.append(str(selected[0]))
            if business_date:
                clauses.append("l.business_date=?")
                params.append(business_date)
            cursor.execute(
                "SELECT " + EXCEPTION_COLUMNS + " FROM ops.Exception e "
                "JOIN ops.Load l ON l.load_id=e.load_id WHERE "
                + " AND ".join(clauses)
                + " ORDER BY l.attempt_number DESC, e.row_ordinal, e.rule_id, e.exception_id "
                "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
                (*params, offset, limit),
            )
            return {
                "items": [exception_record(row) for row in cursor.fetchall()],
                "limit": limit,
                "offset": offset,
            }

    def exception(self, exception_id):
        with closing(connect(self.settings)) as connection, closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT " + EXCEPTION_COLUMNS + ", e.evidence_json, s.raw_record_json, "
                "l.source_id, l.business_date, l.reference_set_sha256 FROM ops.Exception e "
                "JOIN ops.Load l ON l.load_id=e.load_id LEFT JOIN stg.SourceRow s "
                "ON s.load_id=e.load_id AND s.row_ordinal=e.row_ordinal WHERE e.exception_id=?",
                (identifier(exception_id),),
            )
            row = cursor.fetchone()
            if row is None:
                raise LoadError("NOT_FOUND", "Exception not found.")
            result = exception_record(row)
            result.update(
                evidence_id=f"exception:{result['exception_id']}",
                untrusted_evidence=json.loads(row[13]),
                untrusted_source=json.loads(row[14]) if row[14] else None,
                source_id=row[15],
                business_date=row[16],
                reference_set_sha256=row[17],
            )
            rules = json.loads(Path("config/rules.json").read_text("utf-8"))
            result["rule_definition"] = (
                next((r for r in rules["rules"] if r["id"] == result["rule_id"]), None)
                if rules["rule_set_version"] == result["rule_set_version"]
                else None
            )
            cursor.execute(
                "SELECT actor, action, occurred_at, detail_json FROM ops.AuditEvent "
                "WHERE load_id=? AND JSON_VALUE(detail_json,'$.exception_id')=? "
                "ORDER BY occurred_at, event_id",
                (result["load_id"], result["exception_id"]),
            )
            result["events"] = [
                {"actor": r[0], "action": r[1], "occurred_at": r[2], "detail": json.loads(r[3])}
                for r in cursor.fetchall()
            ]
            # Capture related records from this load / fixed reference set, never current
            # external data. The investigation freezes these under its observation ID.
            result["related_records"] = []
            original = result["untrusted_evidence"].get("duplicate_of_ordinal")
            if result["rule_id"] == "ACTIVITY_DUPLICATE" and type(original) is int:
                cursor.execute(
                    "SELECT row_ordinal, disposition, raw_record_json FROM stg.SourceRow "
                    "WHERE load_id=? AND row_ordinal=?",
                    (result["load_id"], original),
                )
                result["related_records"] = [
                    {
                        "load_id": result["load_id"],
                        "row_ordinal": r[0],
                        "disposition": r[1],
                        "untrusted_source": json.loads(r[2]),
                    }
                    for r in cursor.fetchall()
                ]
            if result["rule_id"] == "ACTIVITY_UNKNOWN_PROJECT":
                project = result["untrusted_evidence"].get("normalized_value")
                cursor.execute(
                    "SELECT TOP (5) s.load_id, s.row_ordinal, s.disposition, "
                    "s.raw_record_json, e.rule_id, e.evidence_json FROM stg.SourceRow s "
                    "JOIN ops.Load l ON l.load_id=s.load_id "
                    "LEFT JOIN ops.Exception e ON e.load_id=s.load_id "
                    "AND e.row_ordinal=s.row_ordinal "
                    "WHERE l.source_id='project-registry' AND l.published_at IS NOT NULL "
                    "AND l.reference_set_sha256=? "
                    "AND JSON_VALUE(s.raw_record_json,'$.project_id')=? "
                    "ORDER BY l.attempt_number, s.row_ordinal, e.rule_id",
                    (result["reference_set_sha256"], project),
                )
                result["related_records"] = [
                    {
                        "load_id": str(r[0]).lower(),
                        "row_ordinal": r[1],
                        "disposition": r[2],
                        "untrusted_source": json.loads(r[3]),
                        "rule_id": r[4],
                        "untrusted_evidence": json.loads(r[5]) if r[5] else None,
                    }
                    for r in cursor.fetchall()
                ]
            return result

    def acknowledge(self, exception_id, actor, reason):
        exception_id = identifier(exception_id)
        if (
            not isinstance(reason, str)
            or not reason.strip()
            or len(reason.encode("utf-16-le")) > 1000
            or not actor
            or len(actor) > 128
        ):
            raise LoadError(
                "INVALID_REQUEST",
                "A nonempty actor and reason of at most 500 UTF-16 units are required.",
            )
        with closing(connect(self.settings)) as connection, closing(connection.cursor()) as cursor:
            try:
                cursor.execute(
                    "SELECT load_id, acknowledged_at, resolved_at FROM ops.Exception "
                    "WITH (UPDLOCK, HOLDLOCK) WHERE exception_id=?",
                    (exception_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise LoadError("NOT_FOUND", "Exception not found.")
                if row[2] is not None:
                    raise LoadError("ALREADY_RESOLVED", "This finding is already resolved.")
                changed = row[1] is None
                if changed:
                    cursor.execute(
                        "UPDATE ops.Exception SET acknowledged_at=SYSUTCDATETIME(), "
                        "acknowledged_by=?, acknowledgement_reason=? WHERE exception_id=?",
                        (actor, reason.strip(), exception_id),
                    )
                    cursor.execute(
                        "INSERT INTO ops.AuditEvent (load_id, actor, action, detail_json) "
                        "VALUES (?, ?, 'exception_acknowledged', ?)",
                        (
                            str(row[0]),
                            actor,
                            json.dumps({"exception_id": exception_id, "reason": reason.strip()}),
                        ),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {"exception_id": exception_id, "changed": changed}
