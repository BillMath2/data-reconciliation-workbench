import csv
import hashlib
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pytest

from workbench.fixtures import build_fixtures, main, reference_hash

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "fixtures/generated"


def read_json(path):
    return json.loads(path.read_text("utf-8"))


def activities(name):
    with (GENERATED / f"activity/{name}.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_generated_bytes_and_hashes_match_checked_in_sources():
    expected = build_fixtures()
    actual = {
        p.relative_to(GENERATED).as_posix(): p.read_bytes()
        for p in GENERATED.rglob("*")
        if p.is_file()
    }
    assert actual == expected
    for name, digest in read_json(GENERATED / "index.json")["sha256"].items():
        assert hashlib.sha256(actual[name]).hexdigest() == digest


def test_fixture_check_reports_changes_without_rewriting(tmp_path, capsys):
    assert main(["--output", str(tmp_path)]) == 0
    assert main(["--check", str(tmp_path)]) == 0
    changed = tmp_path / "activity/golden.csv"
    changed.write_bytes(b"changed")
    assert main(["--check", str(tmp_path)]) == 1
    assert changed.read_bytes() == b"changed"
    assert "activity/golden.csv" in capsys.readouterr().out


def test_reference_keys_and_manifest_identity():
    departments = read_json(GENERATED / "reference/departments.json")
    snapshot = read_json(GENERATED / "reference/projects-default.json")
    assert len(departments) == len({d["department_id"] for d in departments}) == 5
    assert len(snapshot["items"]) == len({p["project_id"] for p in snapshot["items"]}) == 25
    assert {p["department_id"] for p in snapshot["items"]} == {
        d["department_id"] for d in departments
    }
    assert snapshot["reference_set_sha256"] == reference_hash(departments, snapshot["items"])
    for name in ("clean", "golden", "corrected"):
        manifest = read_json(GENERATED / f"activity/{name}.manifest.json")
        assert manifest["reference_set_sha256"] == snapshot["reference_set_sha256"]
        assert manifest["row_count"] == len(activities(name))


def test_contract_ownership_and_rule_references_are_complete():
    rules = read_json(ROOT / "config/rules.json")["rules"]
    known_rules = {r["id"] for r in rules}
    assert len(known_rules) == len(rules)
    ownership = read_json(ROOT / "config/field-ownership.json")["sources"]
    for source, metadata in ownership.items():
        contract = read_json(ROOT / "config" / metadata["contract"])
        assert contract["source_id"] == source
        assert contract["contract_version"] == "1.0.0"
        fields = {f["name"] for f in contract["fields"]}
        assert fields == set(metadata["owns"])
        assert set(contract["key"]) <= fields
        assert set(contract["rules"]) <= known_rules
        assert all(f["target"] and f["required"] for f in contract["fields"])


def _assert_valid_source_rows(rows):
    project_ids = {
        p["project_id"] for p in read_json(GENERATED / "reference/projects-default.json")["items"]
    }
    assert len({(r["activity_date"], r["activity_id"]) for r in rows}) == len(rows)
    for row in rows:
        assert row["project_id"] in project_ids
        assert row["activity_status"] == "completed"
        assert int(row["completed_units"]) > 0
        assert date.fromisoformat(row["activity_date"]) == date(2026, 9, 25)
        assert datetime.fromisoformat(row["source_updated_at"]).utcoffset().total_seconds() == 0


@pytest.mark.parametrize("name", ["clean", "corrected"])
def test_valid_exports_match_independent_expectations(name):
    expected = read_json(ROOT / "fixtures/expected/golden.json")[name]
    rows = activities(name)
    _assert_valid_source_rows(rows)
    assert len(rows) == expected["raw_rows"] == expected["accepted_rows"]
    assert sum(int(r["completed_units"]) for r in rows) == expected["source_completed_units"]
    assert expected["source_completed_units"] == expected["curated_completed_units"]


def test_golden_exclusions_and_totals_are_independently_accounted_for():
    expected = read_json(ROOT / "fixtures/expected/golden.json")["golden"]
    rows = activities("golden")
    excluded = {e["row_ordinal"] for e in expected["exclusions"]}
    assert excluded == {95, 96, 97, 98, 99, 100}
    accepted = [row for ordinal, row in enumerate(rows, 1) if ordinal not in excluded]
    _assert_valid_source_rows(accepted)
    project_ids = {
        p["project_id"] for p in read_json(GENERATED / "reference/projects-default.json")["items"]
    }
    for finding in expected["exclusions"]:
        row = rows[finding["row_ordinal"] - 1]
        assert row["activity_id"] == finding["activity_id"]
        if "duplicate_of_ordinal" in finding:
            assert row == rows[finding["duplicate_of_ordinal"] - 1]
        else:
            assert row[finding["field"]] == finding["value"]
            assert row["project_id"] not in project_ids
    assert len(rows) == expected["raw_rows"] == expected["source_completed_count"] == 100
    assert all(row["activity_status"] == "completed" for row in rows)
    assert len(accepted) == expected["accepted_rows"] == expected["curated_completed_count"] == 94
    assert sum(int(row["completed_units"]) for row in rows) == expected["source_completed_units"]
    assert (
        sum(int(row["completed_units"]) for row in accepted) == expected["curated_completed_units"]
    )
    duplicate_units = sum(
        int(rows[e["row_ordinal"] - 1]["completed_units"])
        for e in expected["exclusions"]
        if "duplicate_of_ordinal" in e
    )
    assert duplicate_units == expected["excluded_duplicate_units"] == 5
    assert expected["source_completed_units"] == (
        expected["curated_completed_units"] + duplicate_units + expected["excluded_invalid_units"]
    )


def test_correction_changes_only_declared_source_records():
    expected = read_json(ROOT / "fixtures/expected/golden.json")
    rows = activities("golden")
    fixed = []
    for ordinal, row in enumerate(rows, 1):
        if ordinal in expected["correction"]["remove_raw_ordinals"]:
            continue
        repaired = expected["correction"]["repair_project_assignments"].get(row["activity_id"])
        fixed.append(
            {
                **row,
                "project_id": repaired,
                "source_updated_at": expected["correction"]["source_updated_at_for_repaired_rows"],
            }
            if repaired
            else row
        )
    assert fixed == activities("corrected")
    assert hashlib.sha256((GENERATED / "activity/golden.csv").read_bytes()).digest() != (
        hashlib.sha256((GENERATED / "activity/corrected.csv").read_bytes()).digest()
    )


def test_scenarios_reference_existing_sources_and_intentional_faults():
    scenarios = read_json(ROOT / "fixtures/scenarios.json")["scenarios"]
    assert [s["id"] for s in scenarios] == [f"S{i:02}" for i in range(1, 13)]
    for scenario in scenarios:
        names = scenario.get("activity_variants", []) + (
            [scenario["activity"]] if scenario.get("activity") else []
        )
        for name in names:
            assert (GENERATED / f"activity/{name}.csv").is_file()
            assert (GENERATED / f"activity/{name}.manifest.json").is_file()
    assert len(activities("manifest-mismatch")) == 100
    assert read_json(GENERATED / "activity/manifest-mismatch.manifest.json")["row_count"] == 99
    assert activities("empty") == []
    assert read_json(GENERATED / "activity/empty.manifest.json")["row_count"] == 0
    counts = Counter(row["activity_id"] for row in activities("conflict"))
    assert counts["ACT-0001"] == 2
    assert activities("conflict")[0] != activities("conflict")[1]
    assert activities("invalid-units")[0]["completed_units"] == "not-a-number"
    assert activities("invalid-status")[0]["activity_status"] == "unrecognized"
    assert "completed_units" not in activities("schema-mismatch")[0]
    assert activities("mixed-date")[0]["activity_date"] == "2026-09-24"
