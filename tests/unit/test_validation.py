import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from workbench.sources import activity_capture
from workbench.validation import LoadError, validate_rows

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
PROJECTS = {f"PRJ-{i:03}" for i in range(1, 26)}


def activity(name):
    folder = FIXTURES / "generated/activity"
    return activity_capture(folder / f"{name}.csv", folder / f"{name}.manifest.json")


def validated(name):
    capture = activity(name)
    assert capture.error is None
    return validate_rows(
        capture.source,
        capture.records,
        business_date=capture.business_date,
        known_references=PROJECTS,
    )


def test_golden_exclusions_match_independently_authored_expectations():
    expected = json.loads((FIXTURES / "expected/golden.json").read_text())["golden"]
    rows = validated("golden")
    assert len(rows) == expected["raw_rows"]
    assert sum(row.disposition == "accepted" for row in rows) == expected["accepted_rows"]
    actual = [(row.ordinal, row.primary_rule) for row in rows if row.findings]
    assert actual == [(row["row_ordinal"], row["rule_id"]) for row in expected["exclusions"]]
    accepted_units = sum(
        row.values["completed_units"] for row in rows if row.disposition == "accepted"
    )
    assert accepted_units == expected["curated_completed_units"]


@pytest.mark.parametrize(
    ("name", "accepted", "rule", "excluded"),
    [
        ("clean", 100, None, 0),
        ("corrected", 98, None, 0),
        ("empty", 0, None, 0),
        ("duplicates", 98, "ACTIVITY_DUPLICATE", 2),
        ("conflict", 98, "ACTIVITY_CONFLICT", 2),
        ("invalid-status", 99, "ROW_ENUM", 1),
        ("invalid-units", 99, "ACTIVITY_UNITS", 1),
    ],
)
def test_fixture_dispositions(name, accepted, rule, excluded):
    rows = validated(name)
    assert sum(row.disposition == "accepted" for row in rows) == accepted
    counts = Counter(row.primary_rule for row in rows if row.findings)
    assert counts == ({rule: excluded} if rule else {})


@pytest.mark.parametrize(
    ("field", "value", "rule"),
    [
        ("activity_id", "straße", "ROW_FORMAT"),
        ("activity_id", "x" * 17, "ROW_FORMAT"),
        ("activity_date", "2026-02-30", "ROW_FORMAT"),
        ("activity_date", "", "ROW_REQUIRED"),
        ("source_updated_at", "2026-09-25T23:00:00+00:00", "ROW_TIMESTAMP"),
        ("source_updated_at", "2026-02-30T23:00:00Z", "ROW_TIMESTAMP"),
        ("completed_units", "-1", "ACTIVITY_UNITS"),
        ("completed_units", "1.0", "ACTIVITY_UNITS"),
        ("completed_units", "2147483648", "ACTIVITY_UNITS"),
        ("completed_units", "0", "ACTIVITY_UNITS"),
        ("completed_units", "١", "ACTIVITY_UNITS"),
        ("project_id", None, "ROW_REQUIRED"),
    ],
)
def test_bad_values_are_quarantined_with_original_evidence(field, value, rule):
    raw = activity("clean").records[0]
    raw[field] = value
    row = validate_rows("daily-activity", [raw], known_references=PROJECTS)[0]
    assert row.disposition == "excluded_invalid"
    assert row.primary_rule == rule
    assert row.findings[0].evidence["value"] == value


def test_normalization_and_duplicate_precedence_preserve_all_findings():
    raw = activity("clean").records[0]
    first, second = deepcopy(raw), deepcopy(raw)
    first.update(
        activity_id=" act-0001 ",
        project_id=" prj-unknown ",
        activity_status=" COMPLETED ",
        completed_units="0003",
    )
    second.update(project_id="PRJ-UNKNOWN")
    rows = validate_rows("daily-activity", [first, second], known_references=PROJECTS)
    assert rows[0].primary_rule == "ACTIVITY_UNKNOWN_PROJECT"
    assert rows[1].primary_rule == "ACTIVITY_DUPLICATE"
    assert {f.rule for f in rows[1].findings} == {"ACTIVITY_DUPLICATE", "ACTIVITY_UNKNOWN_PROJECT"}
    assert rows[1].disposition == "excluded_duplicate"
    assert first["activity_id"] == " act-0001 "  # Raw input is unchanged.


def test_conflicting_group_is_never_resolved_by_arrival_order():
    rows = activity("conflict").records[:2]
    for ordered in (rows, rows[::-1]):
        result = validate_rows("daily-activity", ordered, known_references=PROJECTS)
        assert [row.primary_rule for row in result] == ["ACTIVITY_CONFLICT"] * 2


def test_missing_keys_do_not_form_a_duplicate_group():
    raw = activity("clean").records[0]
    raw["activity_id"] = ""
    result = validate_rows("daily-activity", [raw, deepcopy(raw)], known_references=PROJECTS)
    assert all([f.rule for f in row.findings] == ["ROW_REQUIRED"] for row in result)


@pytest.mark.parametrize(
    ("status", "units", "accepted"),
    [
        ("planned", "0", True),
        ("cancelled", "0", True),
        ("planned", "1", False),
        ("completed", "0" * 100 + "1", True),
    ],
)
def test_status_units_contract(status, units, accepted):
    raw = activity("clean").records[0]
    raw.update(activity_status=status, completed_units=units)
    row = validate_rows("daily-activity", [raw], known_references=PROJECTS)[0]
    assert (row.disposition == "accepted") is accepted


def test_duplicate_invalid_payloads_compare_normalized_values():
    raw = activity("clean").records[0]
    raw["activity_status"] = " UNKNOWN "
    duplicate = {**raw, "activity_status": "unknown"}
    rows = validate_rows("daily-activity", [raw, duplicate], known_references=PROJECTS)
    assert all(row.primary_rule == "ROW_ENUM" for row in rows)
    assert {f.rule for f in rows[1].findings} == {"ROW_ENUM", "ACTIVITY_DUPLICATE"}


def test_mixed_dates_fail_whole_load():
    capture = activity("mixed-date")
    with pytest.raises(LoadError) as caught:
        validate_rows(
            capture.source,
            capture.records,
            business_date=capture.business_date,
            known_references=PROJECTS,
        )
    assert caught.value.code == "SRC_BUSINESS_DATE"


def test_reference_duplicates_fail_and_unknown_parent_is_quarantined():
    raw = json.loads((FIXTURES / "generated/reference/projects-default.json").read_text())["items"][
        0
    ]
    duplicate = {**raw, "project_id": " prj-001 "}
    with pytest.raises(LoadError) as caught:
        validate_rows("project-registry", [raw, duplicate], known_references={"DEPT-01"})
    assert caught.value.code == "REF_DUPLICATE"
    result = validate_rows("project-registry", [raw], known_references=set())
    assert result[0].primary_rule == "PROJECT_UNKNOWN_DEPARTMENT"


def test_inactive_departments_and_paused_projects_are_valid_references():
    department = {"department_id": "D_01-A", "department_name": " Synthetic ", "is_active": False}
    assert validate_rows("department-reference", [department])[0].disposition == "accepted"
    raw = json.loads((FIXTURES / "generated/reference/projects-default.json").read_text())["items"][
        0
    ]
    for status in ("paused", "closed"):
        assert (
            validate_rows(
                "project-registry",
                [{**raw, "project_status": status}],
                known_references={"DEPT-01"},
            )[0].disposition
            == "accepted"
        )
