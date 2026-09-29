import base64
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from workbench.mock_registry import create_app
from workbench.pipeline import evaluation_key
from workbench.sources import Capture, activity_capture, canonical, registry_capture, strict_json

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/generated"


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("manifest-mismatch", "SRC_MANIFEST_COUNT"),
        ("schema-mismatch", "SRC_SCHEMA"),
    ],
)
def test_invalid_activity_envelope_keeps_original_capture(name, code):
    csv = FIXTURES / f"activity/{name}.csv"
    manifest = FIXTURES / f"activity/{name}.manifest.json"
    result = activity_capture(csv, manifest)
    assert result.error.code == code
    assert result.content == csv.read_bytes()
    assert base64.b64decode(result.metadata["manifest_base64"]) == manifest.read_bytes()


@pytest.mark.parametrize("mutation", ["extra-cell", "missing-cell", "bad-quote", "blank-row"])
def test_malformed_csv_fails_load(tmp_path, mutation):
    content = (FIXTURES / "activity/clean.csv").read_bytes()
    header, row, _ = content.split(b"\n", 2)
    bad = {
        "extra-cell": row + b",extra",
        "missing-cell": row.rsplit(b",", 1)[0],
        "bad-quote": b'"unterminated',
        "blank-row": b"",
    }[mutation]
    path = tmp_path / "input.csv"
    path.write_bytes(header + b"\n" + bad + b"\n")
    result = activity_capture(path, FIXTURES / "activity/clean.manifest.json")
    assert result.error.code == "SRC_SCHEMA"


def test_missing_file_is_a_safe_failed_capture(tmp_path):
    result = activity_capture(tmp_path / "missing.csv", tmp_path / "missing.json")
    assert result.error.code == "SOURCE_UNAVAILABLE"
    assert str(tmp_path) not in str(result.error)


@pytest.mark.parametrize("content", [b'{"a":1,"a":2}', b'{"x":NaN}', b"\xff"])
def test_ambiguous_or_invalid_json_is_rejected(content):
    with pytest.raises(ValueError):
        strict_json(content)


def test_api_adapter_consumes_mock_pagination_and_retains_response_bytes():
    with TestClient(create_app(FIXTURES)) as client:
        captured = []

        def fetch(url):
            parts = urlsplit(url)
            response = client.get(parts.path + "?" + parts.query)
            response.raise_for_status()
            captured.append(response.content)
            return response.content

        result = registry_capture("http://registry/projects", fetch)
    assert result.error is None
    assert len(result.records) == 25
    assert len({r["project_id"] for r in result.records}) == 25
    assert [base64.b64decode(p) for p in json.loads(result.content)["pages_base64"]] == captured


@pytest.mark.parametrize(
    "fault", ["short", "cursor-loop", "metadata-change", "transport", "bad-json"]
)
def test_api_completeness_failures_keep_received_pages(fault):
    original = json.loads((FIXTURES / "reference/projects-default.json").read_text())
    calls = 0

    def fetch(_):
        nonlocal calls
        calls += 1
        if calls == 2 and fault == "transport":
            raise OSError("secret endpoint information")
        if calls == 2 and fault == "bad-json":
            return b"invalid JSON"
        page = {**original, "items": original["items"][:10], "next_cursor": "again"}
        if fault == "short":
            page["next_cursor"] = None
        if calls == 2 and fault == "metadata-change":
            page["snapshot_id"] = "different"
        return canonical(page)

    result = registry_capture("http://registry/projects", fetch)
    assert result.error is not None
    assert len(json.loads(result.content)["pages_base64"]) >= 1
    assert "secret" not in str(result.error)
    assert calls <= 2


def test_manifest_changes_cannot_reuse_same_evaluation():
    first = Capture("daily-activity", content=b"same csv", metadata={"row_count": 99})
    second = Capture("daily-activity", content=b"same csv", metadata={"row_count": 100})
    assert evaluation_key(first) != evaluation_key(second)
    assert evaluation_key(first) == evaluation_key(first)
