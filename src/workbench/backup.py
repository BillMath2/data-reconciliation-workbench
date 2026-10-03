"""Administrator-only Linux SQL Server copy/restore rehearsal; never replace a database."""

import time
from contextlib import closing, contextmanager
from dataclasses import replace
from uuid import uuid4

from workbench.db import connect
from workbench.migrations import execute_batch, validate_database_name


@contextmanager
def restored_copy(settings):
    """Yield an isolated restored database, then remove only that owned copy.

    The copy-only backup file is retained in the SQL Server volume for inspection.
    This is a single-instance rehearsal, not a point-in-time/offsite backup system.
    """
    validate_database_name(settings.database)
    token = uuid4().hex
    target = "workbench_restore_" + token
    backup_path = f"/var/opt/mssql/data/wb_rehearsal_{token}.bak"
    restored = False
    with closing(connect(replace(settings, database="master"))) as admin:
        admin.autocommit = True
        admin.timeout = 120
        with closing(admin.cursor()) as cursor:
            cursor.execute("SELECT DB_ID(?)", (target,))
            if cursor.fetchone()[0] is not None:
                raise RuntimeError("Restore target already exists; refusing to replace it.")
            started = time.monotonic()
            execute_batch(
                cursor,
                f"BACKUP DATABASE [{settings.database}] TO DISK=? "
                "WITH COPY_ONLY, CHECKSUM, COMPRESSION;",
                (backup_path,),
            )
            backup_ms = round((time.monotonic() - started) * 1000)
            execute_batch(cursor, "RESTORE VERIFYONLY FROM DISK=? WITH CHECKSUM;", (backup_path,))
            cursor.execute("RESTORE FILELISTONLY FROM DISK=?", (backup_path,))
            files = [(r[0], r[2]) for r in cursor.fetchall()]
            while cursor.nextset():
                pass
            if sorted(kind for _, kind in files) != ["D", "L"]:
                raise RuntimeError("Rehearsal expects one data file and one log file.")
            moves = []
            for logical, kind in files:
                logical = logical.replace("'", "''")
                suffix = "mdf" if kind == "D" else "ldf"
                moves.append(f"MOVE N'{logical}' TO N'/var/opt/mssql/data/{target}.{suffix}'")
            started = time.monotonic()
            try:
                execute_batch(
                    cursor,
                    f"RESTORE DATABASE [{target}] FROM DISK=? WITH "
                    + ", ".join(moves)
                    + ", CHECKSUM, RECOVERY;",
                    (backup_path,),
                )
                restored = True
                restore_ms = round((time.monotonic() - started) * 1000)
                execute_batch(cursor, f"DBCC CHECKDB ([{target}]) WITH NO_INFOMSGS;")
                yield (
                    replace(settings, database=target),
                    {
                        "source_database": settings.database,
                        "restored_database": target,
                        "backup_path_on_sql_server": backup_path,
                        "backup_ms": backup_ms,
                        "restore_ms": restore_ms,
                        "copy_only": True,
                        "checksum_verified": True,
                        "checkdb_passed": True,
                        "replace_used": False,
                        "scope": "same-instance synthetic rehearsal",
                    },
                )
            finally:
                if restored:
                    # Name is generated above, never caller-controlled or the source DB.
                    execute_batch(
                        cursor,
                        f"ALTER DATABASE [{target}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;",
                    )
                    execute_batch(cursor, f"DROP DATABASE [{target}];")
