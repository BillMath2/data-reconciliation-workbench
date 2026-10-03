from pathlib import Path

import pytest

from workbench.bootstrap import BootstrapError, validate_runtime_password
from workbench.config import Settings
from workbench.migrations import (
    Migration,
    MigrationError,
    discover,
    validate_database_name,
    validate_history,
)


@pytest.mark.parametrize(
    "name", ["master", "MASTER", "tempdb", "a]; DROP TABLE x", "", "a-b", "1db"]
)
def test_database_identifiers_reject_system_names_and_unsafe_characters(name):
    with pytest.raises(MigrationError):
        validate_database_name(name)


def test_repository_migrations_are_ordered_single_batches():
    files = discover(Path(__file__).resolve().parents[2] / "sql/migrations")
    assert [m.version for m in files] == [1, 2, 3, 4, 5, 6, 7, 8, 9]


@pytest.mark.parametrize(
    "files",
    [
        {},
        {"002_late.sql": "SELECT 1"},
        {"001_one.sql": "SELECT 1", "001_duplicate.sql": "SELECT 2"},
        {"1_bad_name.sql": "SELECT 1"},
        {"001_empty.sql": " "},
        {"001_batches.sql": "SELECT 1;\nGO\nSELECT 2;"},
    ],
)
def test_invalid_migration_sets_fail_before_connecting(tmp_path, files):
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    with pytest.raises(MigrationError):
        discover(tmp_path)


def test_history_must_be_a_known_contiguous_prefix():
    files = [Migration(1, "001_one.sql", "SELECT 1"), Migration(2, "002_two.sql", "SELECT 2")]
    validate_history(files, [])
    validate_history(files, [(1, "001_one.sql")])
    validate_history(files, [(1, "001_one.sql"), (2, "002_two.sql")])
    for history in (
        [(2, "002_two.sql")],
        [(1, "001_renamed.sql")],
        [(1, "001_one.sql"), (2, "002_two.sql"), (3, "003_unknown.sql")],
    ):
        with pytest.raises(MigrationError):
            validate_history(files, history)


@pytest.mark.parametrize("password", [None, "short", "secret\n" + "x" * 20, "a" * 129])
def test_invalid_runtime_password_never_appears_in_error(password):
    settings = Settings("server", "workbench", "sa", "admin-secret", runtime_password=password)
    with pytest.raises(BootstrapError) as caught:
        validate_runtime_password(settings)
    if password:
        assert password not in str(caught.value)
    assert "admin-secret" not in repr(settings)


def test_admin_and_runtime_passwords_must_differ():
    password = "Wb1!independent-test-password"
    settings = Settings("server", "workbench", "sa", password, runtime_password=password)
    with pytest.raises(BootstrapError, match="must differ"):
        validate_runtime_password(settings)
