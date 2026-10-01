import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from workbench import api
from workbench.config import ConfigurationError
from workbench.validation import LoadError

ORIGIN = "http://127.0.0.1:8000"
ANALYST = "a" * 40
OPERATOR = "o" * 40
PACKET = json.loads(Path("docs/evidence/p05/golden-evidence.json").read_text())
LOAD = PACKET["load_id"]
EXCEPTION = str(uuid4())


class FakeEvidence:
    def __init__(self):
        self.calls = []

    def loads(self, *args):
        return {"items": [{"load_id": LOAD}]}

    def report(self, load_id):
        return {"packet": PACKET, "publication_load_id": LOAD}

    def packet(self, load_id):
        return copy.deepcopy(PACKET)

    def citation(self, load_id, evidence_id):
        match = next((e for e in PACKET["evidence"] if e["id"] == evidence_id), None)
        if match is None:
            raise LoadError("NOT_FOUND", "Evidence ID is not in this saved packet.")
        return match

    def exceptions(self, *args):
        return {"items": [{"exception_id": EXCEPTION}]}

    def exception(self, exception_id):
        return {
            "exception_id": exception_id,
            "untrusted_source": {"value": "<script>alert(1)</script>"},
        }

    def acknowledge(self, *args):
        self.calls.append(args)
        return {"exception_id": args[0], "changed": True}


@pytest.fixture
def client():
    app = api.create_app(None, analyst_token=ANALYST, operator_token=OPERATOR)
    app.state.evidence = FakeEvidence()
    with TestClient(app, base_url=ORIGIN) as client:
        yield client


def login(client, role="analyst"):
    response = client.post(
        "/api/session",
        headers={"Origin": ORIGIN},
        json={"token": OPERATOR if role == "operator" else ANALYST},
    )
    assert response.status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}


@pytest.mark.parametrize(
    "path",
    [
        "/api/loads",
        "/api/exceptions",
        f"/api/exceptions/{EXCEPTION}",
        f"/api/loads/{LOAD}/reconciliation",
        f"/api/loads/{LOAD}/evidence",
        f"/api/loads/{LOAD}/evidence/reconciliation:{LOAD}",
    ],
)
def test_all_evidence_routes_require_a_session(client, path):
    assert client.get(path).status_code == 401
    login(client)
    assert client.get(path).status_code == 200


def test_saved_packet_is_returned_without_modification(client):
    login(client)
    response = client.get(f"/api/loads/{LOAD}/evidence")
    assert response.json() == PACKET
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/api/loads/{LOAD}/evidence/unknown").status_code == 404


def test_session_cookie_is_opaque_and_role_is_bound_on_server(client):
    headers = login(client, "operator")
    session_id = client.cookies[api.COOKIE]
    assert "operator" not in session_id and OPERATOR not in session_id
    assert client.get("/api/session").json()["actor"] == "demo-operator"
    response = client.post(
        f"/api/exceptions/{EXCEPTION}/acknowledge",
        headers=headers,
        json={"reason": "Reviewed with source owner"},
    )
    assert response.status_code == 200
    assert client.app.state.evidence.calls == [
        (EXCEPTION, "demo-operator", "Reviewed with source owner")
    ]


def test_analyst_cannot_acknowledge_even_with_valid_csrf(client):
    headers = login(client)
    response = client.post(
        f"/api/exceptions/{EXCEPTION}/acknowledge", headers=headers, json={"reason": "reviewed"}
    )
    assert response.status_code == 403 and not client.app.state.evidence.calls


@pytest.mark.parametrize(
    "fault",
    ["no_csrf", "wrong_csrf", "other_session", "evil_origin", "null_origin", "missing_origin"],
)
def test_cross_site_and_forged_writes_never_reach_service(client, fault):
    headers = login(client, "operator")
    if fault == "no_csrf":
        headers.pop("X-CSRF-Token")
    elif fault == "wrong_csrf":
        headers["X-CSRF-Token"] = "wrong"
    elif fault == "other_session":
        stale = headers["X-CSRF-Token"]
        headers = login(client, "operator")
        headers["X-CSRF-Token"] = stale
    elif fault == "missing_origin":
        headers.pop("Origin")
    else:
        headers["Origin"] = "null" if fault == "null_origin" else "https://evil.example"
    assert (
        client.post(
            f"/api/exceptions/{EXCEPTION}/acknowledge", headers=headers, json={"reason": "reviewed"}
        ).status_code
        == 403
    )
    assert not client.app.state.evidence.calls


def test_caller_cannot_choose_role_or_actor(client):
    bad = client.post(
        "/api/session", headers={"Origin": ORIGIN}, json={"token": ANALYST, "role": "operator"}
    )
    assert bad.status_code == 422 and ANALYST not in bad.text
    headers = login(client, "operator")
    assert (
        client.post(
            f"/api/exceptions/{EXCEPTION}/acknowledge",
            headers=headers,
            json={"reason": "reviewed", "actor": "somebody"},
        ).status_code
        == 422
    )
    assert not client.app.state.evidence.calls


def test_cookie_attributes_logout_rotation_and_expiry(client, monkeypatch):
    result = client.post("/api/session", headers={"Origin": ORIGIN}, json={"token": OPERATOR})
    cookie = result.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    old = client.cookies[api.COOKIE]
    headers = login(client, "operator")
    assert old not in client.app.state.sessions.values
    assert client.post("/api/session/logout", headers=headers, json={}).status_code == 200
    assert client.get("/api/session").status_code == 401
    login(client)
    now = api.time.monotonic()
    monkeypatch.setattr(api.time, "monotonic", lambda: now + api.SESSION_SECONDS + 1)
    assert client.get("/api/session").status_code == 401


def test_driver_errors_are_redacted(client):
    login(client)

    def fail(*args):
        raise RuntimeError("PWD=super-secret private-server")

    client.app.state.evidence.loads = fail
    response = client.get("/api/loads")
    assert response.status_code == 503
    assert "super-secret" not in response.text and "private-server" not in response.text


@pytest.mark.parametrize("query", ["limit=101", "offset=-1", "load_id=not-a-uuid", "status=madeup"])
def test_invalid_filters_are_rejected(client, query):
    login(client)
    assert client.get("/api/exceptions?" + query).status_code == 422


def test_wrong_host_and_form_login_blocked(client):
    assert client.get("/health", headers={"Host": "evil.example"}).status_code == 400
    assert (
        client.post(
            "/api/session", headers={"Origin": ORIGIN}, data={"token": OPERATOR}
        ).status_code
        == 415
    )
    assert (
        client.post(
            "/api/session", headers={"Origin": ORIGIN}, json={"token": "x" * 9000}
        ).status_code
        == 413
    )


def test_untrusted_source_is_json_not_html(client):
    login(client)
    response = client.get(f"/api/exceptions/{EXCEPTION}")
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json()["untrusted_source"]["value"] == "<script>alert(1)</script>"


@pytest.mark.parametrize("tokens", [(None, OPERATOR), (ANALYST, ANALYST), ("short", OPERATOR)])
def test_api_refuses_missing_or_shared_demo_credentials(tokens):
    with pytest.raises(ConfigurationError):
        api.create_app(None, analyst_token=tokens[0], operator_token=tokens[1])
