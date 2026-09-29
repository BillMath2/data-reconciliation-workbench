from contextlib import closing
from dataclasses import replace
from uuid import uuid4

import pytest

from workbench.bootstrap import create_database
from workbench.config import load_settings
from workbench.db import connect
from workbench.migrations import execute_batch


@pytest.fixture
def database():
    settings = replace(
        load_settings(), database="workbench_schema_test_" + uuid4().hex, connect_timeout=30
    )
    assert create_database(settings)["created"] is True
    try:
        yield settings
    finally:
        # Only the randomly named database created by this fixture is removed.
        with closing(connect(replace(settings, database="master"))) as admin:
            admin.autocommit = True
            with closing(admin.cursor()) as cursor:
                execute_batch(
                    cursor,
                    f"ALTER DATABASE [{settings.database}] "
                    "SET SINGLE_USER WITH ROLLBACK IMMEDIATE;",
                )
                execute_batch(cursor, f"DROP DATABASE [{settings.database}];")


def pytest_addoption(parser):
    parser.addoption("--run-sql", action="store_true", help="Run checks against a real SQL Server")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-sql"):
        return
    skip = pytest.mark.skip(reason="SQL integration requires --run-sql and a configured SQL Server")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
