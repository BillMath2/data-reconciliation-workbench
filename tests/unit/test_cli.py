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


def test_database_failure_never_prints_driver_message(configured, monkeypatch, capsys):
    def failed_connection(_):
        raise RuntimeError("PWD=private-password; private server details")

    monkeypatch.setattr(cli.db, "connect", failed_connection)
    assert cli.main(["health"]) == 3
    output = capsys.readouterr()
    assert json.loads(output.err)["status"] == "error"
    assert "private-password" not in output.out + output.err
    assert "private server details" not in output.out + output.err


def test_missing_settings_exit_code(monkeypatch, capsys):
    monkeypatch.delenv("WB_SQL_PASSWORD", raising=False)
    assert cli.main(["config-check"]) == 2
    assert "WB_SQL_PASSWORD" in capsys.readouterr().err
