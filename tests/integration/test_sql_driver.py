import pytest

from workbench.config import load_settings
from workbench.db import health, smoke

pytestmark = pytest.mark.integration


def test_sql_health():
    assert health(load_settings())["status"] == "ok"


def test_parameter_unicode_commit_and_rollback():
    assert smoke(load_settings())["status"] == "ok"
