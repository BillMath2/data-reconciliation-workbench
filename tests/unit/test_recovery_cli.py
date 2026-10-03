import json

import pytest

from workbench import cli, recovery
from workbench.config import Settings
from workbench.validation import LoadError

SETTINGS = Settings("test", "workbench", "test", "private-test-password")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"apply": True},
        {"apply": True, "reason": " "},
        {"apply": True, "reason": "x" * 501},
        {"actor": ""},
        {"actor": "x" * 129},
    ],
)
def test_invalid_recovery_input_never_opens_database(monkeypatch, kwargs):
    def unexpected(_):
        raise AssertionError("Validation must precede the connection")

    monkeypatch.setattr(recovery, "connect", unexpected)
    with pytest.raises(LoadError):
        recovery.recover(SETTINGS, **kwargs)


def test_cli_defaults_to_preview_and_passes_explicit_apply(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_settings", lambda _: SETTINGS)
    calls = []

    def capture(settings, **kwargs):
        calls.append(kwargs)
        return {"status": "ok", "applied": kwargs["apply"], "count": 0}

    monkeypatch.setattr(recovery, "recover", capture)
    assert cli.main(["recover-loads"]) == 0
    assert json.loads(capsys.readouterr().out)["applied"] is False
    assert (
        cli.main(["recover-loads", "--apply", "--actor", "Bill", "--reason", "Worker stopped"]) == 0
    )
    assert calls[-1] == {"apply": True, "actor": "Bill", "reason": "Worker stopped"}


def test_recovery_cli_withholds_driver_details(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_settings", lambda _: SETTINGS)

    def fail(_):
        raise RuntimeError("private-test-password")

    monkeypatch.setattr(recovery, "connect", fail)
    assert cli.main(["recover-loads"]) == 3
    assert "private-test-password" not in capsys.readouterr().err


def test_apply_flag_is_not_accepted_on_other_commands():
    with pytest.raises(SystemExit):
        cli.main(["load-projects", "--apply"])
