"""Resolve historical activity findings only inside a successful publication transaction."""

import json
import re
from collections import defaultdict

from workbench.validation import parse_date


def activity_key(raw, business_date):
    identifier = raw.get("activity_id")
    if not isinstance(identifier, str):
        return None
    identifier = identifier.strip()
    if not identifier.isascii() or not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", identifier):
        return None
    try:
        if parse_date(raw.get("activity_date", "").strip()) != business_date:
            return None
    except (ValueError, AttributeError):
        return None
    return identifier.upper()


def successor_index(rows, business_date):
    by_key = defaultdict(list)
    has_unknown_key = False
    for row in rows:
        key = activity_key(row.raw, business_date)
        if key is None:
            has_unknown_key = True
        else:
            by_key[key].append(row)
    return by_key, has_unknown_key


def resolution_for(raw, business_date, index):
    key = activity_key(raw, business_date)
    if key is None:
        return None  # Ordinal matching cannot prove that a keyless row was corrected.
    by_key, has_unknown_key = index
    matches = by_key.get(key, [])
    if not matches:
        return None if has_unknown_key else "key_removed"
    if all(row.disposition == "accepted" and not row.findings for row in matches):
        return "key_valid"
    return None  # A different error on the same key is not a proven correction.


def resolve(cursor, load_id, capture, rows, actor):
    """No commits here: lifecycle and audit must roll back with publication."""
    index = successor_index(rows, capture.business_date)
    cursor.execute(
        "SELECT e.exception_id, e.load_id, e.row_ordinal, s.raw_record_json "
        "FROM ops.Exception e WITH (UPDLOCK) JOIN ops.Load old ON old.load_id=e.load_id "
        "JOIN ops.Load successor ON successor.load_id=? "
        "LEFT JOIN stg.SourceRow s ON s.load_id=e.load_id AND s.row_ordinal=e.row_ordinal "
        "WHERE e.resolved_at IS NULL AND old.source_id='daily-activity' "
        "AND old.business_date=successor.business_date "
        "AND old.reference_set_sha256=successor.reference_set_sha256 "
        "AND old.contract_version=successor.contract_version "
        "AND old.rule_set_version=successor.rule_set_version "
        "AND old.attempt_number<successor.attempt_number "
        "AND (old.published_at IS NOT NULL OR old.status='failed') "
        "AND successor.published_at IS NOT NULL AND successor.is_current=1",
        (load_id,),
    )
    for exception_id, old_load_id, ordinal, raw in cursor.fetchall():
        reason = (
            "load_recovered"
            if ordinal is None
            else resolution_for(json.loads(raw), capture.business_date, index)
        )
        if reason is None:
            continue
        cursor.execute(
            "UPDATE ops.Exception SET resolved_at=SYSUTCDATETIME(), "
            "resolved_by_load_id=?, resolution_reason=? WHERE exception_id=?",
            (load_id, reason, str(exception_id)),
        )
        cursor.execute(
            "INSERT INTO ops.AuditEvent (load_id, actor, action, detail_json) "
            "VALUES (?, ?, 'exception_resolved', ?)",
            (
                str(old_load_id),
                actor,
                json.dumps(
                    {
                        "exception_id": str(exception_id).lower(),
                        "successor_load_id": load_id,
                        "reason": reason,
                    }
                ),
            ),
        )
