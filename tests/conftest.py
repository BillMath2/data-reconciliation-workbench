import pytest


def pytest_addoption(parser):
    parser.addoption("--run-sql", action="store_true", help="Run checks against a real SQL Server")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-sql"):
        return
    skip = pytest.mark.skip(reason="SQL integration requires --run-sql and a configured SQL Server")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
