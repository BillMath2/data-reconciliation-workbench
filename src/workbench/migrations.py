"""Numbered, transactional T-SQL migrations with an applied-version ledger."""

import re
from contextlib import closing, suppress
from dataclasses import dataclass
from pathlib import Path

from workbench.config import Settings
from workbench.db import connect

DEFAULT_MIGRATIONS = Path("sql/migrations")
SYSTEM_DATABASES = {"master", "model", "msdb", "tempdb"}


class MigrationError(RuntimeError):
    """Safe migration diagnostic, without connection strings or driver messages."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


def validate_database_name(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,62}", name):
        raise MigrationError("Database name must be 1-63 ASCII letters/digits/underscores.")
    if name.lower() in SYSTEM_DATABASES:
        raise MigrationError("Use a user database; system databases cannot be migrated.")


def discover(directory: Path) -> list[Migration]:
    if not directory.is_dir():
        raise MigrationError("Migration directory does not exist.")
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        match = re.fullmatch(r"([0-9]{3})_([a-z][a-z0-9_]*)\.sql", path.name)
        if not match:
            raise MigrationError("Migration filenames must match 001_description.sql.")
        sql = path.read_text(encoding="utf-8-sig")
        if not sql.strip() or re.search(r"^\s*GO(?:\s|$)", sql, re.MULTILINE | re.IGNORECASE):
            raise MigrationError(
                "Migrations must be nonempty single batches without GO separators."
            )
        migrations.append(Migration(int(match[1]), path.name, sql))
    if not migrations or [m.version for m in migrations] != list(range(1, len(migrations) + 1)):
        raise MigrationError("Migration versions must be unique and contiguous starting at 001.")
    return migrations


def validate_history(migrations: list[Migration], applied: list[tuple[int, str]]) -> None:
    expected = [(m.version, m.name) for m in migrations]
    if applied != expected[: len(applied)]:
        raise MigrationError(
            "Database migration history is not a prefix of the local migration set."
        )


def execute_batch(cursor, sql: str, params: tuple = ()) -> None:
    cursor.execute(sql, params) if params else cursor.execute(sql)
    while cursor.nextset():
        pass


def migrate(settings: Settings, directory: Path = DEFAULT_MIGRATIONS) -> dict:
    validate_database_name(settings.database)
    migrations = discover(directory)
    applied_now = []
    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        # One deployment session at a time, across per-migration commits.
        # This is deployment coordination, not multi-worker ingestion support.
        cursor.execute(
            "DECLARE @result INT; EXEC @result = sys.sp_getapplock "
            "@Resource=N'workbench:migrations', @LockMode='Exclusive', "
            "@LockOwner='Session', @LockTimeout=10000; SELECT @result;"
        )
        lock_result = cursor.fetchone()[0]
        while cursor.nextset():
            pass
        if lock_result < 0:
            raise MigrationError("Could not acquire the migration lock; retry later.")
        try:
            execute_batch(cursor, "SET NOCOUNT ON; SET XACT_ABORT ON;")
            execute_batch(cursor, "IF SCHEMA_ID(N'meta') IS NULL EXEC(N'CREATE SCHEMA meta');")
            execute_batch(
                cursor,
                """
                IF OBJECT_ID(N'meta.SchemaMigration', N'U') IS NULL
                    CREATE TABLE meta.SchemaMigration (
                        version INT NOT NULL PRIMARY KEY CHECK (version > 0),
                        name NVARCHAR(128) NOT NULL UNIQUE,
                        applied_at DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
                        applied_by SYSNAME NOT NULL DEFAULT ORIGINAL_LOGIN()
                    );
            """,
            )
            connection.commit()
            cursor.execute("SELECT version, name FROM meta.SchemaMigration ORDER BY version")
            applied = [(int(row[0]), str(row[1])) for row in cursor.fetchall()]
            validate_history(migrations, applied)
            connection.commit()
            for migration in migrations[len(applied) :]:
                try:
                    execute_batch(cursor, migration.sql)
                    execute_batch(
                        cursor,
                        "INSERT INTO meta.SchemaMigration (version, name) VALUES (?, ?)",
                        (migration.version, migration.name),
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise MigrationError(
                        f"Migration {migration.name} failed; its transaction was rolled back."
                    ) from None
                applied_now.append(migration.version)
            return {
                "status": "ok",
                "check": "migrations",
                "applied": applied_now,
                "current_version": migrations[-1].version,
            }
        finally:
            # Release explicitly, including with drivers that pool sessions on close.
            with suppress(Exception):
                connection.rollback()
                execute_batch(
                    cursor,
                    "EXEC sys.sp_releaseapplock "
                    "@Resource=N'workbench:migrations', @LockOwner='Session';",
                )
                connection.commit()
