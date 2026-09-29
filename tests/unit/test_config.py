import pytest

from workbench.config import ConfigurationError, load_settings


@pytest.fixture
def env():
    return {
        "WB_SQL_SERVER": "example",
        "WB_SQL_DATABASE": "master",
        "WB_SQL_USERNAME": "test-user",
        "WB_SQL_PASSWORD": "secret;value}with'quotes",
    }


def test_required_settings_are_named_without_values():
    with pytest.raises(ConfigurationError, match="WB_SQL_PASSWORD"):
        load_settings(environ={})


def test_secrets_are_hidden_in_repr_and_escaped_in_connection_string(env):
    settings = load_settings(environ=env)
    assert env["WB_SQL_PASSWORD"] not in repr(settings)
    assert "PWD={secret;value}}with'quotes}" in settings.connection_string()
    assert "Encrypt=yes;TrustServerCertificate=no" in settings.connection_string()


def test_explicit_file_and_process_precedence(tmp_path, env):
    path = tmp_path / "settings.env"
    path.write_text("WB_SQL_DATABASE=from-file\nWB_SQL_PASSWORD='${UNCHANGED}'\n")
    env.pop("WB_SQL_PASSWORD")
    settings = load_settings(path, environ=env)
    assert settings.database == "master"
    assert settings.password == "${UNCHANGED}"


def test_default_does_not_read_unrelated_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("WB_SQL_PASSWORD=unrelated-secret\n")
    with pytest.raises(ConfigurationError, match="WB_SQL_PASSWORD"):
        load_settings(environ={})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("WB_SQL_DRIVER", "bad-driver"),
        ("WB_SQL_TRUST_CERTIFICATE", "perhaps"),
        ("WB_SQL_CONNECT_TIMEOUT", "0"),
        ("WB_SQL_CONNECT_TIMEOUT", "31"),
        ("WB_SQL_CONNECT_TIMEOUT", "private-invalid-value"),
    ],
)
def test_invalid_values_have_safe_errors(env, name, value):
    env[name] = value
    with pytest.raises(ConfigurationError) as caught:
        load_settings(environ=env)
    assert name in str(caught.value)
    if not value.isdecimal():
        assert value not in str(caught.value)


def test_missing_explicit_file(tmp_path):
    with pytest.raises(ConfigurationError, match="does not exist"):
        load_settings(tmp_path / "absent.env", environ={})
