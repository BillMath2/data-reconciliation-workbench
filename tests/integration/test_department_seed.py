from contextlib import closing
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from workbench.config import load_settings
from workbench.db import connect

pytestmark = pytest.mark.integration
SEED_SQL = (
    Path(__file__).resolve().parents[2] / "fixtures/generated/reference/departments.sql"
).read_text("utf-8")


def execute_seed(cursor):
    cursor.execute(SEED_SQL)
    # Consume the whole T-SQL batch so an error in a later statement is observed.
    while cursor.nextset():
        pass


def test_department_seed_repeats_and_preserves_changed_reference_data():
    # Only this newly created, uniquely named test database is removed in cleanup.
    settings = replace(load_settings(), database="master", connect_timeout=30)
    name = "workbench_fixture_test_" + uuid4().hex
    with closing(connect(settings)) as admin:
        admin.autocommit = True
        with closing(admin.cursor()) as cursor:
            cursor.execute(f"CREATE DATABASE [{name}]")
        try:
            with closing(connect(replace(settings, database=name))) as connection:
                with closing(connection.cursor()) as cursor:
                    execute_seed(cursor)
                    connection.commit()
                    execute_seed(cursor)
                    connection.commit()
                    cursor.execute("SELECT COUNT(*) FROM source.Department")
                    assert cursor.fetchone()[0] == 5
                    cursor.execute(
                        "UPDATE source.Department SET department_name = ? WHERE department_id = ?",
                        ("Changed by operator", "DEPT-01"),
                    )
                    connection.commit()
                    with pytest.raises(Exception, match="Reference data differs"):
                        execute_seed(cursor)
                    connection.rollback()
                    cursor.execute(
                        "SELECT department_name FROM source.Department WHERE department_id = ?",
                        ("DEPT-01",),
                    )
                    assert cursor.fetchone()[0] == "Changed by operator"
        finally:
            with closing(admin.cursor()) as cursor:
                cursor.execute(f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
                cursor.execute(f"DROP DATABASE [{name}]")


def test_department_seed_refuses_system_databases():
    with closing(connect(replace(load_settings(), database="master"))) as connection:
        with closing(connection.cursor()) as cursor:
            with pytest.raises(Exception, match="disposable user database"):
                execute_seed(cursor)
            connection.rollback()
