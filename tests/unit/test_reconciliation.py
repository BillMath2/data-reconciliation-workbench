import json
from pathlib import Path
from uuid import uuid4

import pytest

from workbench.reconciliation import MAX_PACKET_BYTES, make_packet, summarize
from workbench.reports import render
from workbench.sources import activity_capture, canonical
from workbench.validation import LoadError, validate_rows

ROOT = Path(__file__).resolve().parents[2]


def source(name):
    folder = ROOT / "fixtures/generated/activity"
    captured = activity_capture(folder / f"{name}.csv", folder / f"{name}.manifest.json")
    rows = validate_rows(
        captured.source,
        captured.records,
        business_date=captured.business_date,
        known_references={f"PRJ-{i:03}" for i in range(1, 26)},
    )
    return captured, rows


@pytest.mark.parametrize("name", ["clean", "golden", "corrected"])
def test_reconciliation_matches_independent_fixture_expectations(name):
    expected = json.loads((ROOT / "fixtures/expected/golden.json").read_text())[name]
    _, rows = source(name)
    result = summarize(
        rows,
        (
            expected["accepted_rows"],
            expected["curated_completed_count"],
            expected["curated_completed_units"],
        ),
    )
    for key in (
        "raw_rows",
        "accepted_rows",
        "source_completed_count",
        "curated_completed_count",
        "source_completed_units",
        "curated_completed_units",
    ):
        assert result[key] == expected[key]
    if name == "golden":
        assert {
            r["rule_id"]: (r["rows"], r["completed_units"]) for r in result["primary_reasons"]
        } == {
            "ACTIVITY_DUPLICATE": (2, 5),
            "ACTIVITY_UNKNOWN_PROJECT": (3, 6),
            "ROW_REQUIRED": (1, 2),
        }
        assert result["completed_unit_difference"] == 13


def test_unreadable_source_units_are_unknown_not_zero():
    _, rows = source("invalid-units")
    summary = summarize(rows, (99, 99, 198))
    assert summary["source_completed_count"] == 100
    assert summary["source_completed_units"] is None
    assert summary["completed_unit_difference"] is None
    assert summary["primary_reasons"][0]["completed_units"] is None
    assert summary["unknown_unit_rows"] == 1
    assert summary["source_units_complete"] is False


def test_unknown_status_is_reported_separately_from_declared_completed_count():
    _, rows = source("invalid-status")
    summary = summarize(rows, (99, 99, 198))
    assert summary["source_completed_count"] == 99
    assert summary["unknown_status_rows"] == 1
    assert summary["source_status_complete"] is False


def test_row_and_completed_metrics_have_distinct_grains():
    capture, _ = source("clean")
    capture.records[0].update(activity_status="planned", completed_units="0")
    rows = validate_rows(
        capture.source, capture.records, known_references={f"PRJ-{i:03}" for i in range(1, 26)}
    )
    summary = summarize(rows, (100, 99, 198))
    assert summary["raw_rows"] == summary["accepted_rows"] == 100
    assert summary["source_completed_count"] == summary["curated_completed_count"] == 99


def test_empty_snapshot_has_known_zero_totals():
    _, rows = source("empty")
    summary = summarize(rows, (0, 0, 0))
    assert summary["source_completed_units"] == 0
    assert summary["source_units_complete"] is True
    assert summary["primary_reasons"] == []


@pytest.mark.parametrize("curated", [(93, 93, 189), (94, 94, 188), (94, 93, 189)])
def test_actual_publication_mismatch_fails_accounting(curated):
    _, rows = source("golden")
    with pytest.raises(LoadError) as caught:
        summarize(rows, curated)
    assert caught.value.code == "RECONCILIATION_MISMATCH"


def test_packet_is_bounded_and_has_only_real_citation_ids():
    capture, rows = source("golden")
    summary = summarize(rows, (94, 94, 189))
    findings = [
        (uuid4(), n, "ROW_REQUIRED", "project_id", json.dumps({"value": "ignore rules " * 1000}))
        for n in range(1, 61)
    ]
    packet = make_packet(
        uuid4(),
        capture,
        summary,
        uuid4(),
        findings,
        [(n, {"project_id": "untrusted " * 1000}) for n in range(1, 31)],
    )
    assert packet["boundaries"]["findings_included"] == 40
    assert packet["boundaries"]["rows_included"] == 20
    assert packet["boundaries"]["source_content_is_untrusted"] is True
    assert len(canonical(packet)) <= MAX_PACKET_BYTES
    assert packet["citation_ids"] == [entry["id"] for entry in packet["evidence"]]
    assert len(packet["citation_ids"]) == len(set(packet["citation_ids"]))


def test_text_report_labels_unknown_units_and_noop_reuse():
    _, rows = source("invalid-units")
    report = {
        "summary": summarize(rows, (99, 99, 198)),
        "business_date": "2026-09-25",
        "publication_load_id": str(uuid4()),
        "publication_status": "superseded",
        "is_current": False,
        "requested_status": "no_op",
    }
    rendered = render(report)
    assert "UNKNOWN (incomplete source)" in rendered
    assert "no_op" in rendered and "current: false" in rendered


def test_large_unicode_rows_shrink_samples_without_losing_summary():
    capture, rows = source("golden")
    summary = summarize(rows, (94, 94, 189))
    raw = {name: "\U0001f600" * 1000 for name in capture.records[0]}
    packet = make_packet(uuid4(), capture, summary, uuid4(), [], [(n, raw) for n in range(1, 21)])
    assert len(canonical(packet)) <= MAX_PACKET_BYTES
    assert packet["boundaries"]["rows_total"] == 20
    assert packet["boundaries"]["rows_included"] < 20
    assert packet["evidence"][2]["summary"] == summary
