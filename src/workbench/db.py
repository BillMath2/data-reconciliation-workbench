"""SQL Server health and transactional driver checks for P01."""

from contextlib import closing
from importlib import import_module

from workbench.config import Settings


def connect(settings: Settings):
    """Use one configured DB-API driver; fallback selection is explicit."""
    module_name = "mssql_python" if settings.driver == "mssql-python" else "pyodbc"
    driver = import_module(module_name)
    connection = driver.connect(
        settings.connection_string(), autocommit=False, timeout=settings.connect_timeout
    )
    connection.timeout = settings.connect_timeout
    return connection


def health(settings: Settings) -> dict[str, str]:
    """Verify a real round trip, without changing application data."""
    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute("SELECT CAST(1 AS INT)")
        if cursor.fetchone()[0] != 1:
            raise RuntimeError("Unexpected health result")
        connection.rollback()
    return {"status": "ok", "check": "sql-health", "driver": settings.driver}


def smoke(settings: Settings) -> dict[str, str]:
    """Prove binding, Unicode, commit, and rollback using a session-local temp table."""
    sample = "Research – 大学; ' quoted } value"
    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute("SELECT CAST(? AS NVARCHAR(100)), CAST(? AS INT)", (sample, 42))
        row = cursor.fetchone()
        if tuple(row) != (sample, 42):
            raise RuntimeError("Parameter or Unicode round trip failed")

        cursor.execute("CREATE TABLE #wb_driver_probe (id INT PRIMARY KEY, label NVARCHAR(100))")
        connection.commit()
        cursor.execute("INSERT INTO #wb_driver_probe (id, label) VALUES (?, ?)", (1, sample))
        connection.commit()
        cursor.execute("INSERT INTO #wb_driver_probe (id, label) VALUES (?, ?)", (2, "rollback"))
        connection.rollback()
        cursor.execute("SELECT id, label FROM #wb_driver_probe ORDER BY id")
        if [tuple(row) for row in cursor.fetchall()] != [(1, sample)]:
            raise RuntimeError("Commit or rollback did not preserve the expected rows")
        connection.rollback()
        # Closing the session removes the temporary table, even on an error.
    return {"status": "ok", "check": "sql-smoke", "driver": settings.driver}
