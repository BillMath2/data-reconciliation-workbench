"""Explicit development database creation and separate runtime credential provisioning."""

from contextlib import closing
from dataclasses import replace
from pathlib import Path

from workbench.config import Settings
from workbench.db import connect, health
from workbench.migrations import (
    DEFAULT_MIGRATIONS,
    discover,
    execute_batch,
    migrate,
    validate_database_name,
)

RUNTIME_LOGIN = "workbench_app"


class BootstrapError(RuntimeError):
    """Safe bootstrap diagnostic."""


def create_database(settings: Settings) -> dict:
    validate_database_name(settings.database)
    with closing(connect(replace(settings, database="master"))) as connection:
        connection.autocommit = True  # CREATE DATABASE cannot run inside a user transaction.
        with closing(connection.cursor()) as cursor:
            cursor.execute("SELECT DB_ID(?)", (settings.database,))
            exists = cursor.fetchone()[0] is not None
            if not exists:
                # validate_database_name restricts this identifier to ASCII letters/digits/_.
                execute_batch(cursor, f"CREATE DATABASE [{settings.database}]")
    return {"status": "ok", "check": "database-create", "created": not exists}


def validate_runtime_password(settings: Settings) -> str:
    password = settings.runtime_password
    if not password or not 16 <= len(password) <= 128 or any(ord(c) < 32 for c in password):
        raise BootstrapError("WB_SQL_RUNTIME_PASSWORD must be 16-128 characters without controls.")
    if password == settings.password:
        raise BootstrapError("Runtime and administrator passwords must differ.")
    return password


def provision_runtime(settings: Settings) -> dict:
    validate_database_name(settings.database)
    password = validate_runtime_password(settings)
    with closing(connect(replace(settings, database="master"))) as connection:
        connection.autocommit = True
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT type_desc FROM sys.server_principals WHERE name = ?", (RUNTIME_LOGIN,)
            )
            principal = cursor.fetchone()
            if principal is None:
                # CREATE LOGIN does not accept a password parameter. Escape the literal;
                # never log this statement or return a driver's exception from the CLI.
                literal = password.replace("'", "''")
                execute_batch(
                    cursor,
                    f"CREATE LOGIN [{RUNTIME_LOGIN}] WITH PASSWORD=N'{literal}', "
                    "CHECK_POLICY=ON, CHECK_EXPIRATION=OFF;",
                )
            elif principal[0] != "SQL_LOGIN":
                raise BootstrapError(
                    "The runtime principal already exists with an unexpected type."
                )
            cursor.execute(
                "SELECT COUNT(*) FROM sys.server_role_members AS m "
                "JOIN sys.server_principals AS p ON p.principal_id=m.member_principal_id "
                "WHERE p.name = ?",
                (RUNTIME_LOGIN,),
            )
            if cursor.fetchone()[0] != 0:
                raise BootstrapError("The runtime login must not have server role memberships.")
            cursor.execute("SELECT SUSER_SID(?)", (RUNTIME_LOGIN,))
            login_sid = cursor.fetchone()[0]

    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute(
            "SELECT sid, type FROM sys.database_principals WHERE name = ?", (RUNTIME_LOGIN,)
        )
        existing = cursor.fetchone()
        if existing is None:
            execute_batch(cursor, f"CREATE USER [{RUNTIME_LOGIN}] FOR LOGIN [{RUNTIME_LOGIN}];")
        elif existing[0] != login_sid or existing[1] != "S":
            raise BootstrapError("An unrelated database principal uses the runtime user's name.")
        cursor.execute(
            "SELECT r.name FROM sys.database_role_members AS m "
            "JOIN sys.database_principals AS r ON r.principal_id=m.role_principal_id "
            "JOIN sys.database_principals AS u ON u.principal_id=m.member_principal_id "
            "WHERE u.name = ?",
            (RUNTIME_LOGIN,),
        )
        memberships = {row[0] for row in cursor.fetchall()}
        if memberships - {"workbench_runtime"}:
            raise BootstrapError("The runtime user has unexpected database role memberships.")
        if "workbench_runtime" not in memberships:
            execute_batch(cursor, f"ALTER ROLE workbench_runtime ADD MEMBER [{RUNTIME_LOGIN}];")
        connection.commit()
    # Verify the supplied credential; reruns never silently rotate an existing password.
    health(replace(settings, username=RUNTIME_LOGIN, password=password))
    return {"status": "ok", "check": "runtime-login"}


def setup_database(settings: Settings, directory: Path = DEFAULT_MIGRATIONS) -> dict:
    # Fail before creating anything if configuration is incomplete.
    validate_runtime_password(settings)
    discover(directory)
    created = create_database(settings)
    migrated = migrate(settings, directory)
    provision_runtime(settings)
    return {
        "status": "ok",
        "check": "database-setup",
        "created": created["created"],
        "applied": migrated["applied"],
        "current_version": migrated["current_version"],
        "runtime_login": RUNTIME_LOGIN,
    }
