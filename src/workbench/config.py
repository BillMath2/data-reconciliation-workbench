"""Explicit configuration loading without exposing connection credentials."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


class ConfigurationError(ValueError):
    """An actionable configuration error safe to display to the operator."""


def _quoted(value: str) -> str:
    """Escape connection-string values, including semicolons and closing braces."""
    return "{" + value.replace("}", "}}") + "}"


@dataclass(frozen=True)
class Settings:
    server: str
    database: str
    username: str
    password: str = field(repr=False)
    driver: str = "mssql-python"
    trust_certificate: bool = False
    connect_timeout: int = 5

    def connection_string(self) -> str:
        parts = [
            f"Server={_quoted(self.server)}",
            f"Database={_quoted(self.database)}",
            f"UID={_quoted(self.username)}",
            f"PWD={_quoted(self.password)}",
            "Encrypt=yes",
            f"TrustServerCertificate={'yes' if self.trust_certificate else 'no'}",
        ]
        if self.driver == "pyodbc":
            parts.insert(0, "Driver={ODBC Driver 18 for SQL Server}")
        return ";".join(parts)


def load_settings(
    env_file: Path | None = None, *, environ: Mapping[str, str] | None = None
) -> Settings:
    """Load only the explicitly named file; process environment takes precedence."""
    values: dict[str, str | None] = {}
    if env_file is not None:
        if not env_file.is_file():
            raise ConfigurationError("The requested environment file does not exist.")
        try:
            values.update(dotenv_values(env_file, interpolate=False, encoding="utf-8-sig"))
        except (OSError, UnicodeError):
            raise ConfigurationError("The requested environment file could not be read.") from None
    values.update(os.environ if environ is None else environ)

    required = ("WB_SQL_SERVER", "WB_SQL_DATABASE", "WB_SQL_USERNAME", "WB_SQL_PASSWORD")
    missing = [name for name in required if not values.get(name)]
    if missing:
        raise ConfigurationError("Missing settings: " + ", ".join(missing))

    driver = values.get("WB_SQL_DRIVER", "mssql-python")
    if driver not in {"mssql-python", "pyodbc"}:
        raise ConfigurationError("WB_SQL_DRIVER must be mssql-python or pyodbc.")
    trust = (values.get("WB_SQL_TRUST_CERTIFICATE") or "false").lower()
    if trust not in {"true", "false"}:
        raise ConfigurationError("WB_SQL_TRUST_CERTIFICATE must be true or false.")
    try:
        timeout = int(values.get("WB_SQL_CONNECT_TIMEOUT") or "5")
    except ValueError:
        raise ConfigurationError(
            "WB_SQL_CONNECT_TIMEOUT must be an integer from 1 to 30."
        ) from None
    if not 1 <= timeout <= 30:
        raise ConfigurationError("WB_SQL_CONNECT_TIMEOUT must be an integer from 1 to 30.")
    return Settings(
        server=str(values["WB_SQL_SERVER"]),
        database=str(values["WB_SQL_DATABASE"]),
        username=str(values["WB_SQL_USERNAME"]),
        password=str(values["WB_SQL_PASSWORD"]),
        driver=driver,
        trust_certificate=trust == "true",
        connect_timeout=timeout,
    )
