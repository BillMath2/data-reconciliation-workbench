"""In-memory browser fixture. Saved P05 facts; simulated P06 lifecycle, never SQL proof."""

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from workbench.freshness import assess
from workbench.operations import OperationsService
from workbench.validation import LoadError


class FixtureService:
    def __init__(self):
        self.packets = {
            name: json.loads(Path(f"docs/evidence/p05/{name}-evidence.json").read_text("utf-8"))
            for name in ("golden", "corrected")
        }
        self.attempts = []
        self.current = None
        self.ack = {}

    def snapshots(self):
        return OperationsService(None).snapshots()

    def freshness(self, day):
        available = self.current is not None and str(day) == "2026-09-25"
        return {
            **assess(day, datetime(2026, 10, 1, 16, tzinfo=UTC), available),
            "failed_refresh": False,
        }

    def run(self, snapshot, business_date, actor, reason):
        assert business_date == "2026-09-25"
        assert actor == "demo-operator" and reason.strip()
        packet = self.packets[snapshot]
        reused = any(a["load_id"] == packet["load_id"] for a in self.attempts)
        status = (
            "no_op"
            if reused
            else ("published_with_exceptions" if snapshot == "golden" else "published")
        )
        if not reused:
            self.current = packet["load_id"]
        item = {
            "load_id": str(uuid4()) if reused else packet["load_id"],
            "status": status,
            "business_date": "2026-09-25",
            "started_at": "2026-10-01T16:00:00",
            "reused_load_id": packet["load_id"] if reused else None,
        }
        self.attempts.insert(0, item)
        return copy.deepcopy(item)

    def loads(self, business_date=None, limit=50, offset=0):
        items = []
        for item in self.attempts:
            if business_date and str(business_date) != item["business_date"]:
                continue
            item = copy.deepcopy(item)
            item["is_current"] = item["load_id"] == self.current
            if not item["is_current"] and item["status"] != "no_op":
                item["status"] = "superseded"
            items.append(item)
        return {"items": items[offset : offset + limit]}

    def report(self, load_id):
        attempt = next(a for a in self.loads()["items"] if a["load_id"] == load_id)
        publication = attempt["reused_load_id"] or load_id
        packet = next(p for p in self.packets.values() if p["load_id"] == publication)
        return {
            "requested_load_id": load_id,
            "requested_status": attempt["status"],
            "publication_load_id": publication,
            "publication_status": "published" if publication == self.current else "superseded",
            "is_current": publication == self.current,
            "business_date": "2026-09-25",
            "packet": copy.deepcopy(packet),
            "summary": next(
                e["summary"] for e in packet["evidence"] if e["kind"] == "reconciliation"
            ),
        }

    def packet(self, load_id):
        return self.report(load_id)["packet"]

    def exceptions(self, load_id=None, business_date=None, status="unresolved", limit=50, offset=0):
        golden = self.packets["golden"]
        if business_date and business_date != date(2026, 9, 25):
            return {"items": []}
        if not self.attempts or (
            load_id and self.report(load_id)["publication_load_id"] != golden["load_id"]
        ):
            return {"items": []}
        items = [
            self.exception(e["id"].split(":")[1])
            for e in golden["evidence"]
            if e["kind"] == "finding"
        ]
        items = [
            e
            for e in items
            if status == "all"
            or status == e["status"]
            or (status == "unresolved" and e["status"] != "resolved")
        ]
        return {"items": items[offset : offset + limit]}

    def exception(self, exception_id):
        golden = self.packets["golden"]
        evidence = next(e for e in golden["evidence"] if e["id"] == "exception:" + exception_id)
        source = next(
            e
            for e in golden["evidence"]
            if e["kind"] == "source_row" and e["ordinal"] == evidence["row_ordinal"]
        )
        ack = self.ack.get(exception_id)
        resolved = self.current == self.packets["corrected"]["load_id"]
        return {
            "exception_id": exception_id,
            "load_id": golden["load_id"],
            "rule_id": evidence["rule_id"],
            "row_ordinal": evidence["row_ordinal"],
            "rule_set_version": "1.0.0",
            "field_name": evidence["field"],
            "status": "resolved" if resolved else "acknowledged" if ack else "open",
            "evidence_id": evidence["id"],
            "untrusted_source": source["untrusted_source"],
            "untrusted_evidence": evidence["untrusted_evidence"],
            "rule_definition": next(r for r in golden["rules"] if r["id"] == evidence["rule_id"]),
            "acknowledged_by": "demo-operator" if ack else None,
            "acknowledgement_reason": ack,
            "resolved_by_load_id": self.current if resolved else None,
            "resolution_reason": "key_valid" if resolved else None,
            "events": [{"actor": "demo-operator", "action": "exception_acknowledged"}]
            if ack
            else [],
        }

    def acknowledge(self, exception_id, actor, reason):
        if self.exception(exception_id)["status"] == "resolved":
            raise LoadError("ALREADY_RESOLVED", "Already resolved")
        changed = exception_id not in self.ack
        self.ack.setdefault(exception_id, reason)
        return {"changed": changed, "exception_id": exception_id}
