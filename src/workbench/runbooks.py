"""Small versioned catalog, selected by recorded rule IDs, never by model instructions."""

from copy import deepcopy

VERSION = "1.0.0"
CATALOG = (
    (
        "reconcile",
        (),
        "Review the saved reconciliation",
        "Reporting owner",
        "Compare the saved source and curated totals. "
        "Unknown totals need source evidence before comparison.",
    ),
    (
        "duplicates",
        ("ACTIVITY_DUPLICATE", "ACTIVITY_CONFLICT"),
        "Review repeated activity keys",
        "Activity source owner",
        "Compare every captured row for the key. Confirm the intended source record "
        "before preparing a corrected full-date snapshot.",
    ),
    (
        "references",
        ("ACTIVITY_UNKNOWN_PROJECT", "PROJECT_UNKNOWN_DEPARTMENT"),
        "Check captured reference membership",
        "Project registry owner",
        "Compare project and department identifiers against the captured reference set. "
        "A missing match does not establish an upstream cause. "
        "Reference fixture changes require a fresh demo database.",
    ),
    (
        "fields",
        ("ROW_REQUIRED", "ROW_FORMAT", "ROW_ENUM", "ACTIVITY_UNITS", "ROW_TIMESTAMP"),
        "Check source fields against the recorded contract",
        "Activity source owner",
        "Inspect the field, source row and versioned rule. "
        "Ask the source owner for a valid value; do not infer missing units or status.",
    ),
    (
        "freshness",
        ("FEED_STALE",),
        "Check the expected delivery",
        "Feed operations owner",
        "Check the selected business date, delivery deadline and latest load audit. "
        "Availability for a historical date does not establish current feed health.",
    ),
    (
        "review",
        (),
        "Verify any proposed correction",
        "Workbench operator",
        "Review source changes, explicitly run a supplied snapshot, then inspect the successor "
        "totals and recorded finding lifecycle. Investigation text never performs these actions.",
    ),
)


def select(rule_ids):
    selected = []
    known = {rule for _, rules, *_ in CATALOG for rule in rules}
    for name, rules, title, owner, check in CATALOG:
        if not rules or set(rules) & set(rule_ids) or (name == "fields" and set(rule_ids) - known):
            selected.append(
                {
                    "id": f"runbook:{name}:{VERSION}",
                    "kind": "runbook",
                    "version": VERSION,
                    "title": title,
                    "owner": owner,
                    "rule_ids": list(rules),
                    "check": check,
                }
            )
    return deepcopy(selected)
