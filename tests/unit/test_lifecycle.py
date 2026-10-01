from datetime import date

import pytest

from workbench.lifecycle import activity_key, resolution_for, successor_index
from workbench.validation import Finding, ValidatedRow

DAY = date(2026, 9, 25)


def row(key="ACT-1", *, valid=True, ordinal=1):
    result = ValidatedRow(ordinal, {"activity_id": key, "activity_date": str(DAY)})
    if not valid:
        result.disposition = "excluded_invalid"
        result.findings = [Finding("ROW_REQUIRED", "project_id", {})]
    return result


def test_normalized_identity_survives_row_reordering():
    old = row(" act-1 ", valid=False, ordinal=5)
    new = [row("ACT-2", ordinal=5), row("ACT-1", ordinal=77)]
    assert resolution_for(old.raw, DAY, successor_index(new, DAY)) == "key_valid"


@pytest.mark.parametrize("key", [None, "", "  ", "ß", "A" * 17, "bad/key"])
def test_invalid_identity_is_never_implicitly_resolved(key):
    assert activity_key(row(key).raw, DAY) is None
    assert resolution_for(row(key).raw, DAY, successor_index([], DAY)) is None


def test_removed_key_requires_a_complete_unambiguous_successor():
    assert resolution_for(row().raw, DAY, successor_index([], DAY)) == "key_removed"
    assert resolution_for(row().raw, DAY, successor_index([row(None, valid=False)], DAY)) is None


def test_persistent_or_changed_faults_do_not_resolve_old_findings():
    for rows in ([row(valid=False)], [row(), row(valid=False)]):
        assert resolution_for(row().raw, DAY, successor_index(rows, DAY)) is None


def test_date_mismatch_is_not_identity():
    assert activity_key(row().raw, date(2026, 9, 26)) is None
