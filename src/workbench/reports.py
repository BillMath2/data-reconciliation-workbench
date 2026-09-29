"""Read stored publication evidence without recomputing historical findings."""

import json
from contextlib import closing
from uuid import UUID

from workbench.db import connect
from workbench.validation import LoadError


def read(settings, *, load_id=None, business_date=None) -> dict:
    if (load_id is None) == (business_date is None):
        raise LoadError("REPORT_SELECTION", "Select exactly one load ID or business date.")
    if load_id is not None:
        try:
            load_id = str(UUID(str(load_id)))
        except ValueError:
            raise LoadError("REPORT_SELECTION", "Load ID must be a UUID.") from None
    predicate = (
        "q.load_id=?"
        if load_id
        else "q.source_id='daily-activity' AND q.business_date=? AND q.is_current=1"
    )
    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute(
            "SELECT q.load_id, q.status, l.load_id, l.status, l.is_current, l.business_date, "
            "r.summary_json, r.evidence_json FROM ops.Load q "
            "JOIN ops.Load l ON l.load_id=COALESCE(q.reused_load_id,q.load_id) "
            "JOIN ops.ReconciliationResult r ON r.load_id=l.load_id "
            "WHERE l.published_at IS NOT NULL AND " + predicate,
            (load_id or business_date,),
        )
        row = cursor.fetchone()
    if row is None:
        raise LoadError(
            "REPORT_UNAVAILABLE",
            "No saved reconciliation for this selection. "
            "Failed loads and publications predating migration 006 have no report.",
        )
    return {
        "requested_load_id": str(row[0]).lower(),
        "requested_status": row[1],
        "publication_load_id": str(row[2]).lower(),
        "publication_status": row[3],
        "is_current": bool(row[4]),
        "business_date": str(row[5]),
        "summary": json.loads(row[6]),
        "packet": json.loads(row[7]),
    }


def render(report) -> str:
    s = report["summary"]

    def unit(value):
        return "UNKNOWN (incomplete source)" if value is None else str(value)

    lines = [
        "DATA RECONCILIATION WORKBENCH",
        f"Business date: {report['business_date']}",
        f"Publication: {report['publication_load_id']}",
        f"State: {report['publication_status']} | current: {str(report['is_current']).lower()}",
        "",
        f"Source rows {s['raw_rows']} = accepted {s['accepted_rows']} "
        f"+ duplicate extras {s['excluded_duplicate_rows']} + invalid {s['excluded_invalid_rows']}",
        f"Declared completed activities: source {s['source_completed_count']} "
        f"| report {s['curated_completed_count']} | difference {s['completed_count_difference']}",
        f"Completed units: source {unit(s['source_completed_units'])} "
        f"| report {s['curated_completed_units']} "
        f"| difference {unit(s['completed_unit_difference'])}",
        "",
        "Primary exclusion reason                Rows  Completed  Units",
    ]
    for reason in s["primary_reasons"]:
        lines.append(
            f"{reason['rule_id']:<38} {reason['rows']:>4} "
            f"{reason['completed_count']:>10}  {unit(reason['completed_units'])}"
        )
    if not s["primary_reasons"]:
        lines.append("No excluded rows.")
    if s["unknown_status_rows"]:
        lines.append(
            f"WARNING: {s['unknown_status_rows']} rows have unknown status; "
            "completed metrics count declared completed rows only."
        )
    if s["unknown_unit_rows"]:
        lines.append(f"WARNING: {s['unknown_unit_rows']} completed rows have unreadable units.")
    if report["requested_status"] == "no_op":
        lines.append(
            "Identical rerun: no_op. Showing the reused publication; no data was replaced."
        )
    lines += ["", "Accounting verified against SQL publication. Findings retain their history."]
    return "\n".join(lines)
