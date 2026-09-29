"""Publication-time accounting and immutable, bounded evidence for later explanation."""

import json
from collections import defaultdict
from pathlib import Path

from workbench.sources import canonical, sha256
from workbench.validation import LoadError

CALCULATION_VERSION = "1.0.0"
MAX_FINDINGS = 40
MAX_ROWS = 20
MAX_TEXT = 240
MAX_PACKET_BYTES = 65536


def summarize(rows, curated: tuple[int, int, int]) -> dict:
    counts = defaultdict(int)
    source_count, source_units, unknown_units, unknown_status = 0, 0, 0, 0
    accepted_completed, accepted_units = 0, 0
    reasons = {}
    for row in rows:
        counts[row.disposition] += 1
        status = row.raw.get("activity_status")
        status = status.strip().lower() if isinstance(status, str) else None
        declared_completed = status == "completed"
        unknown_status += status not in {"completed", "planned", "cancelled"}
        units = row.values.get("completed_units")
        if declared_completed:
            source_count += 1
            if units is None:
                unknown_units += 1
            else:
                source_units += units
        if row.disposition == "accepted":
            if declared_completed:
                accepted_completed += 1
                accepted_units += units
        else:
            if row.primary_rule is None:
                raise LoadError("RECONCILIATION_MISMATCH", "Excluded row has no primary reason.")
            reason = reasons.setdefault(
                row.primary_rule,
                {
                    "rule_id": row.primary_rule,
                    "rows": 0,
                    "completed_count": 0,
                    "completed_units": 0,
                    "unknown_unit_rows": 0,
                },
            )
            reason["rows"] += 1
            if declared_completed:
                reason["completed_count"] += 1
                if units is None:
                    reason["unknown_unit_rows"] += 1
                else:
                    reason["completed_units"] += units
    expected = (counts["accepted"], accepted_completed, accepted_units)
    excluded = counts["excluded_duplicate"] + counts["excluded_invalid"]
    if (
        curated != expected
        or len(rows) != curated[0] + excluded
        or source_count - curated[1] != sum(r["completed_count"] for r in reasons.values())
        or (
            unknown_units == 0
            and source_units - curated[2] != sum(r["completed_units"] for r in reasons.values())
        )
    ):
        raise LoadError(
            "RECONCILIATION_MISMATCH", "Published rows do not reconcile to staged evidence."
        )
    for reason in reasons.values():
        if reason["unknown_unit_rows"]:
            reason["completed_units"] = None
    return {
        "calculation_version": CALCULATION_VERSION,
        "scope": "one full activity date; completed metrics use declared completed status",
        "raw_rows": len(rows),
        "accepted_rows": curated[0],
        "excluded_duplicate_rows": counts["excluded_duplicate"],
        "excluded_invalid_rows": counts["excluded_invalid"],
        "source_completed_count": source_count,
        "curated_completed_count": curated[1],
        "completed_count_difference": source_count - curated[1],
        "source_completed_units": None if unknown_units else source_units,
        "curated_completed_units": curated[2],
        "completed_unit_difference": None if unknown_units else source_units - curated[2],
        "unknown_unit_rows": unknown_units,
        "unknown_status_rows": unknown_status,
        "source_units_complete": unknown_units == 0,
        "source_status_complete": unknown_status == 0,
        "primary_reasons": sorted(reasons.values(), key=lambda r: r["rule_id"]),
        "accounting_verified": True,
    }


def bounded(value):
    """Bound untrusted source values; they are data, never instructions."""
    if isinstance(value, str):
        return value if len(value) <= MAX_TEXT else value[:MAX_TEXT] + "… [truncated]"
    if isinstance(value, list):
        return [bounded(item) for item in value[:20]]
    if isinstance(value, dict):
        return {str(k): bounded(v) for k, v in list(value.items())[:20]}
    return value


def make_packet(load_id, capture, summary, artifact_id, findings, raw_rows) -> dict:
    load_id, artifact_id = str(load_id).lower(), str(artifact_id).lower()
    evidence = [
        {
            "id": f"load:{load_id}",
            "kind": "load",
            "source_id": capture.source,
            "business_date": capture.business_date.isoformat(),
            "reference_set_sha256": capture.reference_hash,
        },
        {
            "id": f"artifact:{artifact_id}",
            "kind": "artifact",
            "load_id": load_id,
            "content_sha256": sha256(capture.content),
            "source_exported_at": capture.metadata.get("manifest", {}).get("exported_at"),
        },
        {"id": f"reconciliation:{load_id}", "kind": "reconciliation", "summary": summary},
    ]
    for item in findings[:MAX_FINDINGS]:
        evidence.append(
            {
                "id": f"exception:{str(item[0]).lower()}",
                "kind": "finding",
                "row_ordinal": item[1],
                "rule_id": item[2],
                "field": item[3],
                "untrusted_evidence": bounded(json.loads(item[4])),
            }
        )
    for ordinal, raw in raw_rows[:MAX_ROWS]:
        evidence.append(
            {
                "id": f"row:{load_id}:{ordinal}",
                "kind": "source_row",
                "ordinal": ordinal,
                "untrusted_source": bounded(raw),
            }
        )
    rule_ids = {r["rule_id"] for r in summary["primary_reasons"]}
    rule_ids.update(item[2] for item in findings[:MAX_FINDINGS])
    rules = json.loads(Path("config/rules.json").read_text("utf-8"))
    packet = {
        "packet_version": "1.0.0",
        "calculation_version": CALCULATION_VERSION,
        "load_id": load_id,
        "business_date": capture.business_date.isoformat(),
        "contract_version": "1.0.0",
        "rule_set_version": rules["rule_set_version"],
        "rules": [rule for rule in rules["rules"] if rule["id"] in rule_ids],
        "evidence": evidence,
        "boundaries": {
            "source_content_is_untrusted": True,
            "source_correction_actions": "not recorded",
            "exception_resolution": "not assessed; findings are historical",
            "findings_total": len(findings),
            "findings_included": min(len(findings), MAX_FINDINGS),
            "rows_total": len(raw_rows),
            "rows_included": min(len(raw_rows), MAX_ROWS),
        },
    }
    # Large multibyte source values must shrink the explanation sample, not turn
    # otherwise publishable row-level faults into a failed load.
    while True:
        packet["citation_ids"] = [item["id"] for item in evidence]
        packet["boundaries"]["rows_included"] = sum(
            item["kind"] == "source_row" for item in evidence
        )
        packet["boundaries"]["findings_included"] = sum(
            item["kind"] == "finding" for item in evidence
        )
        if len(canonical(packet)) <= MAX_PACKET_BYTES:
            break
        removable = next(
            (item for item in reversed(evidence) if item["kind"] in {"source_row", "finding"}), None
        )
        if removable is None:
            raise LoadError("EVIDENCE_TOO_LARGE", "Core evidence exceeds its bounded size.")
        evidence.remove(removable)
    return packet


def save(cursor, load_id, capture, rows):
    cursor.execute(
        "SELECT COUNT_BIG(*), COALESCE(SUM(CASE WHEN activity_status='completed' "
        "THEN CAST(1 AS BIGINT) ELSE 0 END),0), "
        "COALESCE(SUM(CAST(completed_units AS BIGINT)),0) "
        "FROM core.Activity WHERE activity_date=? AND origin_load_id=?",
        (capture.business_date, load_id),
    )
    summary = summarize(rows, tuple(cursor.fetchone()))
    cursor.execute("SELECT artifact_id FROM ops.Load WHERE load_id=?", (load_id,))
    artifact_id = cursor.fetchone()[0]
    cursor.execute(
        "SELECT exception_id, row_ordinal, rule_id, field_name, evidence_json "
        "FROM ops.Exception WHERE load_id=? ORDER BY row_ordinal, rule_id, exception_id",
        (load_id,),
    )
    findings = list(cursor.fetchall())
    packet = make_packet(
        load_id,
        capture,
        summary,
        artifact_id,
        findings,
        [(row.ordinal, row.raw) for row in rows if row.findings],
    )
    columns = (
        "raw_rows",
        "accepted_rows",
        "excluded_duplicate_rows",
        "excluded_invalid_rows",
        "source_completed_count",
        "curated_completed_count",
        "source_completed_units",
        "curated_completed_units",
    )
    cursor.execute(
        "INSERT INTO ops.ReconciliationResult (load_id, calculation_version, "
        + ", ".join(columns)
        + ", summary_json, evidence_json) VALUES ("
        + ", ".join("?" for _ in range(len(columns) + 4))
        + ")",
        (
            load_id,
            CALCULATION_VERSION,
            *[summary[column] for column in columns],
            canonical(summary).decode("utf-8"),
            canonical(packet).decode("utf-8"),
        ),
    )
    return summary
