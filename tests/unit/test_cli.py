import json

import pytest

from workbench import cli


@pytest.fixture
def configured(monkeypatch):
    for key, value in {
        "WB_SQL_SERVER": "test-server",
        "WB_SQL_DATABASE": "master",
        "WB_SQL_USERNAME": "user",
        "WB_SQL_PASSWORD": "private-password",
        "WB_SQL_DRIVER": "mssql-python",
        "WB_SQL_CONNECT_TIMEOUT": "5",
        "WB_SQL_TRUST_CERTIFICATE": "true",
    }.items():
        monkeypatch.setenv(key, value)


def test_config_check_does_not_connect(configured, monkeypatch, capsys):
    def unexpected_connection(_):
        raise AssertionError("Configuration validation must work offline")

    monkeypatch.setattr(cli.db, "connect", unexpected_connection)
    assert cli.main(["config-check"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["check"] == "configuration"
    assert "private-password" not in output.out + output.err


@pytest.mark.parametrize("command", ["health", "db-create", "migrate", "db-setup"])
def test_database_failure_never_prints_driver_message(configured, monkeypatch, capsys, command):
    def failed_connection(_):
        raise RuntimeError("PWD=private-password; private server details")

    monkeypatch.setattr(cli.db, "connect", failed_connection)
    monkeypatch.setattr(cli.bootstrap, "connect", failed_connection)
    monkeypatch.setattr(cli.migrations, "connect", failed_connection)
    monkeypatch.setenv("WB_SQL_DATABASE", "workbench")
    monkeypatch.setenv("WB_SQL_RUNTIME_PASSWORD", "Wb1!test-runtime-secret")
    assert cli.main([command]) == 3
    output = capsys.readouterr()
    assert json.loads(output.err)["status"] == "error"
    assert "private-password" not in output.out + output.err
    assert "private server details" not in output.out + output.err


def test_migration_refuses_system_database_before_connection(configured, monkeypatch, capsys):
    def unexpected_connection(_):
        raise AssertionError("System databases must be rejected before connecting")

    monkeypatch.setattr(cli.migrations, "connect", unexpected_connection)
    assert cli.main(["migrate"]) == 4
    assert "system databases" in json.loads(capsys.readouterr().err)["message"]


def test_missing_settings_exit_code(monkeypatch, capsys):
    monkeypatch.delenv("WB_SQL_PASSWORD", raising=False)
    assert cli.main(["config-check"]) == 2
    assert "WB_SQL_PASSWORD" in capsys.readouterr().err


def test_failed_ingestion_exits_nonzero_with_recorded_load(configured, monkeypatch, capsys):
    monkeypatch.setattr(
        cli.pipeline,
        "load_projects",
        lambda *a, **k: {
            "status": "failed",
            "code": "SRC_PAGINATION",
            "load_id": "recorded-attempt",
        },
    )
    assert cli.main(["load-projects"]) == 5
    assert json.loads(capsys.readouterr().out)["load_id"] == "recorded-attempt"


@pytest.mark.parametrize(
    "command", ["load-departments", "load-activities", "freshness", "reconcile", "evidence"]
)
def test_ingestion_required_arguments_are_checked_before_connecting(command, capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main([command])
    assert caught.value.code == 2
    assert "requires" in capsys.readouterr().err


def test_evidence_export_preserves_existing_files(configured, monkeypatch, tmp_path, capsys):
    packet = {"load_id": "test-load", "citation_ids": []}
    monkeypatch.setattr(cli.reports, "read", lambda *a, **k: {"packet": packet})
    target = tmp_path / "evidence.json"
    command = ["evidence", "--business-date", "2026-09-25", "--output", str(target)]
    assert cli.main(command) == 0
    assert json.loads(target.read_text()) == packet
    original = target.read_bytes()
    assert cli.main(command) == 4
    assert target.read_bytes() == original
    assert "private-password" not in capsys.readouterr().out
