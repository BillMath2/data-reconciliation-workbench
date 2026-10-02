"""Capture authorized evidence, explain it, and append an audited investigation artifact."""

import json
from contextlib import closing
from datetime import UTC, date, datetime
from threading import Lock
from uuid import uuid4

from workbench.db import connect
from workbench.investigation_assistant import MAX_CONTEXT, canonical, digest, explain
from workbench.reconciliation import bounded
from workbench.runbooks import select
from workbench.validation import LoadError


def capture(evidence, operations, load_id, exception_id, investigation_id):
    report = evidence.report(load_id)
    packet = report.pop("packet")
    detail = evidence.exception(exception_id) if exception_id else None
    if detail and detail["load_id"] != report["publication_load_id"]:
        raise LoadError("INVESTIGATION_SCOPE", "Select a finding from this publication.")
    if detail:
        # SQL dates must have the same representation in saved JSON and browser fixtures.
        def encode_date(value):
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            raise TypeError("Unsupported observation value.")

        detail = json.loads(json.dumps(detail, default=encode_date))
        detail = {k: bounded(v) for k, v in detail.items()}
    rules = {r["rule_id"] for r in report["summary"]["primary_reasons"]}
    rules.update(e["rule_id"] for e in packet["evidence"] if e["kind"] == "finding")
    if detail:
        rules.add(detail["rule_id"])
    feed = operations.freshness(date.fromisoformat(report["business_date"]))
    if feed["status"] == "stale":
        rules.add("FEED_STALE")
    observation = {
        "id": f"observation:{investigation_id}",
        "kind": "observation",
        "captured_at": datetime.now(UTC).isoformat(),
        "report_state": report,
        "freshness": feed,
        "selected_finding": detail,
        "boundary": (
            "Sequential observations at capture time; not a transactionally consistent "
            "live-state guarantee. Selected finding text and event lists may be truncated."
        ),
    }
    runbooks = select(rules)
    context = {
        "version": "1.0.0",
        "publication_load_id": report["publication_load_id"],
        "packet": packet,
        "observation": observation,
        "runbooks": runbooks,
        "citation_ids": [*packet["citation_ids"], observation["id"], *(r["id"] for r in runbooks)],
    }
    if len(canonical(context).encode()) > MAX_CONTEXT:
        raise LoadError("CONTEXT_LIMIT", "Investigation context exceeds the size limit.")
    return context


class InvestigationService:
    def __init__(self, settings, *, key=None, live_enabled=False):
        self.settings = settings
        self.key = key if live_enabled else None
        self.lock = Lock()

    def capabilities(self):
        return {"live_enabled": bool(self.key), "default_provider": "stub"}

    def create(self, evidence, operations, load_id, exception_id, provider, actor):
        if not self.lock.acquire(blocking=False):
            raise LoadError("WORKER_BUSY", "An investigation is in progress. Try again later.")
        try:
            identifier = str(uuid4())
            context = capture(evidence, operations, load_id, exception_id, identifier)
            result = explain(context, provider=provider, key=self.key)
            self.save(identifier, load_id, exception_id, actor, context, result)
            return self.get(identifier)
        finally:
            self.lock.release()

    def save(self, identifier, load_id, exception_id, actor, context, result):
        with closing(connect(self.settings)) as connection, closing(connection.cursor()) as cursor:
            try:
                cursor.execute(
                    "INSERT INTO ops.Investigation (investigation_id, requested_load_id, "
                    "publication_load_id, exception_id, created_by, context_sha256, context_json, "
                    "result_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        identifier,
                        load_id,
                        context["publication_load_id"],
                        exception_id,
                        actor,
                        digest(context),
                        canonical(context),
                        canonical(result),
                    ),
                )
                cursor.execute(
                    "INSERT INTO ops.AuditEvent (load_id, actor, action, detail_json) "
                    "VALUES (?, ?, 'investigation_saved', ?)",
                    (
                        load_id,
                        actor,
                        canonical(
                            {
                                "investigation_id": identifier,
                                "provider": result["provider"],
                                "model": result["model"],
                                "prompt_version": result["prompt_version"],
                                "status": result["status"],
                                "context_sha256": digest(context),
                                "latency_ms": result["latency_ms"],
                            }
                        ),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def list(self, load_id, limit=25, offset=0):
        with closing(connect(self.settings)) as connection, closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT investigation_id, created_by, created_at, exception_id "
                "FROM ops.Investigation WHERE requested_load_id=? "
                "ORDER BY created_at DESC, investigation_id DESC "
                "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
                (load_id, offset, limit),
            )
            items = [
                {
                    "investigation_id": str(r[0]).lower(),
                    "created_by": r[1],
                    "created_at": str(r[2]),
                    "exception_id": str(r[3]).lower() if r[3] else None,
                }
                for r in cursor.fetchall()
            ]
        return {"items": items, "limit": limit, "offset": offset}

    def get(self, identifier):
        with closing(connect(self.settings)) as connection, closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT requested_load_id, publication_load_id, exception_id, created_by, "
                "created_at, context_sha256, context_json, result_json FROM ops.Investigation "
                "WHERE investigation_id=?",
                (identifier,),
            )
            row = cursor.fetchone()
        if row is None:
            raise LoadError("NOT_FOUND", "Saved investigation not found.")
        return {
            "investigation_id": identifier,
            "requested_load_id": str(row[0]).lower(),
            "publication_load_id": str(row[1]).lower(),
            "exception_id": str(row[2]).lower() if row[2] else None,
            "created_by": row[3],
            "created_at": str(row[4]),
            "context_sha256": row[5],
            "context": json.loads(row[6]),
            "result": json.loads(row[7]),
        }

    def citation(self, identifier, evidence_id):
        context = self.get(identifier)["context"]
        for entry in [*context["packet"]["evidence"], context["observation"], *context["runbooks"]]:
            if entry["id"] == evidence_id:
                return entry
        raise LoadError("NOT_FOUND", "Citation is not part of this saved investigation.")
