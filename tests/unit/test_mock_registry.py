from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from workbench.mock_registry import create_app

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/generated"


@pytest.fixture
def client():
    with TestClient(create_app(FIXTURES)) as instance:
        yield instance


def test_registry_pagination_is_complete_and_repeatable(client):
    first = client.get("/projects").json()
    assert client.get("/projects").json() == first
    second = client.get("/projects", params={"cursor": first["next_cursor"]}).json()
    third = client.get("/projects", params={"cursor": second["next_cursor"]}).json()
    assert [len(page["items"]) for page in (first, second, third)] == [10, 10, 5]
    assert third["next_cursor"] is None
    for key in ("snapshot_id", "reference_set_sha256", "exported_at", "total_count"):
        assert first[key] == second[key] == third[key]
    assert first["total_count"] == 25
    assert len({p["project_id"] for page in (first, second, third) for p in page["items"]}) == 25


def test_incomplete_scenario_preserves_declared_total(client):
    first = client.get("/projects?scenario=incomplete").json()
    second = client.get("/projects?scenario=incomplete&cursor=page-2").json()
    assert first["total_count"] == second["total_count"] == 25
    assert len(first["items"]) + len(second["items"]) == 20
    assert second["next_cursor"] is None
    assert client.get("/projects?scenario=incomplete&cursor=page-3").status_code == 503


def test_unknown_department_is_an_explicit_separate_reference_set(client):
    normal = client.get("/projects").json()
    fault = client.get("/projects?scenario=unknown-department").json()
    assert fault["items"][0]["department_id"] == "DEPT-UNKNOWN"
    assert normal["items"][0]["department_id"] == "DEPT-01"
    assert normal["reference_set_sha256"] != fault["reference_set_sha256"]
    assert client.get("/projects").json() == normal


@pytest.mark.parametrize("query", ["cursor=../secret", "cursor=page-4", "scenario=unknown"])
def test_invalid_queries_do_not_expose_files(client, query):
    assert client.get("/projects?" + query).status_code == 400


def test_registry_is_read_only_and_has_health_endpoint(client):
    assert client.post("/projects", json={}).status_code == 405
    assert client.get("/health").json() == {
        "status": "ok",
        "source": "project-registry",
        "synthetic": True,
    }
