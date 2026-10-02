import ast
import copy
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from workbench import api
from workbench import investigation_assistant as ai
from workbench.investigations import InvestigationService, capture
from workbench.runbooks import select
from workbench.validation import LoadError

PACKET = json.loads(Path("docs/evidence/p05/golden-evidence.json").read_text("utf-8"))
LOAD = PACKET["load_id"]
ORIGIN = "http://127.0.0.1:8000"


@pytest.fixture
def services():
    packet = copy.deepcopy(PACKET)
    report = {
        "requested_load_id": LOAD,
        "publication_load_id": LOAD,
        "requested_status": "published_with_exceptions",
        "publication_status": "published",
        "business_date": "2026-09-25",
        "is_current": True,
        "packet": packet,
        "summary": next(e["summary"] for e in packet["evidence"] if e["kind"] == "reconciliation"),
    }
    detail = {"load_id": LOAD, "rule_id": "ROW_REQUIRED", "status": "open"}
    evidence = SimpleNamespace(
        report=lambda _: copy.deepcopy(report), exception=lambda _: copy.deepcopy(detail)
    )
    operations = SimpleNamespace(freshness=lambda _: {"status": "available"})
    return evidence, operations, report, detail


@pytest.fixture
def context(services):
    return capture(*services[:2], LOAD, None, str(uuid4()))


def test_context_selects_versioned_runbooks_and_keeps_source_data(services):
    services[3]["created_at"] = datetime(2026, 10, 2, 12)
    context = capture(*services[:2], LOAD, str(uuid4()), str(uuid4()))
    assert context["packet"] == PACKET
    assert context["observation"]["selected_finding"]["status"] == "open"
    assert context["observation"]["selected_finding"]["created_at"] == "2026-10-02T12:00:00"
    assert {r["id"] for r in context["runbooks"]} == {
        "runbook:reconcile:1.0.0",
        "runbook:duplicates:1.0.0",
        "runbook:references:1.0.0",
        "runbook:fields:1.0.0",
        "runbook:review:1.0.0",
    }
    services[3]["load_id"] = str(uuid4())
    with pytest.raises(LoadError, match="this publication"):
        capture(*services[:2], LOAD, str(uuid4()), str(uuid4()))


@pytest.mark.parametrize("mode", ["stub", "off", "openai"])
@pytest.mark.parametrize("shape", ["golden", "clean", "incomplete"])
def test_offline_and_unavailable_preserve_clean_and_unknown_facts(services, mode, shape):
    summary = services[2]["summary"]
    if shape == "clean":
        summary["primary_reasons"] = []
        services[2]["packet"]["evidence"] = [
            e for e in services[2]["packet"]["evidence"] if e["kind"] != "finding"
        ]
    if shape == "incomplete":
        summary["source_completed_units"] = None
        summary["completed_unit_difference"] = None
        summary["source_units_complete"] = False
    context = capture(*services[:2], LOAD, None, str(uuid4()))
    frozen = copy.deepcopy(context)
    result = ai.explain(context, provider=mode)
    assert context == frozen
    assert result["status"] == ("unavailable" if mode == "openai" else mode)
    assert result["attempts"] == 0
    assert result["notes"] == ai.fallback(context)
    assert context["observation"]["report_state"]["summary"] == summary


def response(notes, **extra):
    return {
        "status": "completed",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(notes)}]}
        ],
        **extra,
    }


def test_live_request_is_bounded_and_uses_only_context(context):
    tree = ast.parse(Path(ai.__file__).read_text("utf-8"))
    for item in ast.walk(tree):
        if isinstance(item, ast.Import):
            assert {a.name for a in item.names} <= {
                "asyncio",
                "hashlib",
                "json",
                "re",
                "time",
                "httpx",
            }
        elif isinstance(item, ast.ImportFrom):
            assert (item.module, tuple(a.name for a in item.names)) in {
                ("pydantic", ("Field",)),
                ("workbench", ("assistant",)),
            }
    notes = ai.fallback(context)
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["store"] is False and "tools" not in body
        assert body["text"]["format"]["strict"] is True
        assert json.loads(body["input"]) == context
        assert "secret-key" not in request.content.decode()
        return httpx.Response(200, json=response(notes, usage={"input_tokens": 200}))

    result = ai.explain(
        context, provider="openai", key="secret-key", transport=httpx.MockTransport(handler)
    )
    assert len(calls) == result["attempts"] == 1
    assert result["status"] == "ok"
    assert result["notes"] == notes
    assert result["estimated_cost_ceiling_usd"] <= 0.05


@pytest.mark.parametrize(
    "fault",
    [
        "citation",
        "number",
        "action",
        "cause",
        "tools",
        "mixed",
        "refusal",
        "incomplete",
        "timeout",
        "http",
        "huge",
        "usage",
    ],
)
def test_bad_live_output_falls_back_without_retry(context, fault):
    notes = ai.fallback(context)
    if fault == "citation":
        notes["missing_evidence"][0]["evidence_ids"] = ["https://attacker.example"]
    elif fault in {"number", "action"}:
        notes["missing_evidence"][0]["text"] = (
            "There are 5 rows" if fault == "number" else "I repaired the source"
        )
    elif fault == "cause":
        notes["possible_causes"] = [
            {
                "text": "The source owner caused the issue",
                "evidence_ids": context["citation_ids"][:1],
            }
        ]
    body = response(notes)
    if fault == "usage":
        body["usage"] = "malformed"
    if fault in {"tools", "mixed"}:
        tool = {"type": "function_call", "name": "run_activity", "arguments": "{}"}
        body["output"] = [tool] if fault == "tools" else [*body["output"], tool]
    elif fault == "refusal":
        body["output"][0]["content"] = [{"type": "refusal"}]
    elif fault == "incomplete":
        body["status"] = "incomplete"
    calls = []

    def handler(request):
        calls.append(request)
        if fault == "timeout":
            raise httpx.ReadTimeout("secret provider diagnostic")
        if fault == "huge":
            return httpx.Response(200, content=b"x" * 32769)
        return httpx.Response(503 if fault == "http" else 200, json=body)

    result = ai.explain(
        context, provider="openai", key="secret-key", transport=httpx.MockTransport(handler)
    )
    assert result["status"] == "unavailable" and len(calls) == 1
    assert result["notes"] == ai.fallback(context)
    assert "secret" not in json.dumps(result)


def test_bounds_prevent_provider_calls_and_overlapping_generation(context, services):
    context["padding"] = "x" * ai.MAX_CONTEXT
    with pytest.raises(ValueError, match="context_too_large"):
        ai.explain(context, provider="openai", key="secret")
    svc = InvestigationService(None)
    with svc.lock, pytest.raises(LoadError, match="in progress"):
        svc.create(*services[:2], LOAD, None, "stub", "demo-analyst")


def test_catalog_is_versioned_copied_and_selects_conflict_and_freshness():
    books = select({"ACTIVITY_CONFLICT", "FEED_STALE"})
    assert {b["id"].split(":")[1] for b in books} == {
        "reconcile",
        "duplicates",
        "freshness",
        "review",
    }
    books[0]["check"] = "tamper"
    assert select(set())[0]["check"] != "tamper"


@pytest.fixture
def client(services, monkeypatch):
    app = api.create_app(
        None, analyst_token="a" * 40, operator_token="o" * 40, ai_key="never-expose"
    )
    app.state.evidence, app.state.operations = services[:2]
    svc = app.state.investigations
    records = {}

    def save(identifier, load_id, exception_id, actor, context, result):
        records[identifier] = {
            "investigation_id": identifier,
            "created_by": actor,
            "context": context,
            "result": result,
        }

    monkeypatch.setattr(svc, "save", save)
    monkeypatch.setattr(svc, "get", lambda identifier: records[identifier])
    monkeypatch.setattr(svc, "list", lambda *args: {"items": list(records.values())})
    with TestClient(app, base_url=ORIGIN) as client:
        yield client


def login(client, role="analyst"):
    result = client.post(
        "/api/session",
        headers={"Origin": ORIGIN},
        json={"token": ("a" if role == "analyst" else "o") * 40},
    )
    return {"Origin": ORIGIN, "X-CSRF-Token": result.json()["csrf_token"]}


@pytest.mark.parametrize("role", ["analyst", "operator"])
def test_both_roles_save_attributed_artifacts_with_frozen_citations(client, role):
    headers = login(client, role)
    result = client.post("/api/investigations", headers=headers, json={"load_id": LOAD})
    assert result.status_code == 200
    record = result.json()
    assert record["created_by"] == "demo-" + role
    url = f"/api/investigations/{record['investigation_id']}"
    assert client.get(url).json() == record
    assert client.get(url + "/evidence/runbook:review:1.0.0").status_code == 200
    assert client.get(url + "/evidence/foreign").status_code == 404
    assert client.get("/api/investigations/capabilities").json()["live_enabled"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "anonymous",
        "csrf",
        "origin",
        "actor",
        "packet",
        "model",
        "provider",
        "load",
        "expired",
        "logout",
    ],
)
def test_creation_requires_server_identity_and_closed_request(client, fault, monkeypatch):
    headers = {"Origin": ORIGIN} if fault == "anonymous" else login(client)
    body = {"load_id": LOAD}
    if fault == "csrf":
        headers.pop("X-CSRF-Token")
    elif fault == "origin":
        headers["Origin"] = "http://attacker.example"
    elif fault in {"actor", "packet", "model", "provider"}:
        body[fault] = "untrusted"
    elif fault == "load":
        body["load_id"] = "../source"
    elif fault == "expired":
        now = api.time.monotonic()
        monkeypatch.setattr(api.time, "monotonic", lambda: now + api.SESSION_SECONDS + 1)
    elif fault == "logout":
        client.post("/api/session/logout", headers=headers, json={})
    assert client.post("/api/investigations", headers=headers, json=body).status_code in {
        401,
        403,
        422,
    }
    assert client.app.state.investigations.list(LOAD)["items"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/api/investigations/capabilities",
        f"/api/investigations?load_id={LOAD}",
        f"/api/investigations/{LOAD}",
        f"/api/investigations/{LOAD}/evidence/foreign",
    ],
)
def test_investigation_reads_require_session(client, path):
    assert client.get(path).status_code == 401
