import copy
import json

import httpx
import pytest

from workbench import evaluation as ev
from workbench import investigation_assistant as ai

SPEC = ev.load_spec()
CASES = SPEC["cases"]


def context(case):
    return json.loads((ev.SPEC.parent / "contexts" / f"{case['id']}.json").read_text("utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_versioned_corpus_integrity_and_offline_answer(case):
    packet = context(case)
    assert ai.digest(packet) == case["context_sha256"]
    assert ev.check_context(case, packet) == []
    assert ev.check_result(case, packet, ai.explain(packet), "stub") == []


def test_checker_catches_wrong_totals_citations_missing_chain_and_mutated_response():
    case = next(c for c in CASES if c["id"] == "S02")
    packet = context(case)
    packet["observation"]["report_state"]["summary"]["accepted_rows"] += 1
    packet["citation_ids"].append("invented")
    packet["observation"]["selected_finding"]["related_records"] = []
    errors = ev.check_context(case, packet)
    assert "fact_mismatch:accepted_rows" in errors
    assert "report_packet_disagreement" in errors
    assert "unresolvable_context_citations" in errors
    assert "missing_related_source_records" in errors
    packet = context(case)
    answer = ai.explain(packet)
    answer["context_sha256"] = "tampered"
    answer["notes"]["missing_evidence"][0]["text"] = "PWNED_CANARY"
    errors = ev.check_result(case, packet, answer, "stub")
    assert "context_hash_mismatch" in errors and "injection_followed" in errors


@pytest.mark.parametrize(
    "fault", ["repair", "number", "citation", "tool", "timeout", "unavailable"]
)
def test_failure_matrix_retains_facts_and_rejected_response_without_retry(fault):
    case = next(c for c in CASES if c["id"] == "injection-repair")
    packet = context(case)
    original = copy.deepcopy(packet)
    notes = ai.fallback(packet)
    if fault == "repair":
        notes["missing_evidence"][0]["text"] = "I repaired the source."
    if fault == "number":
        notes["missing_evidence"][0]["text"] = "There are 999 accepted rows."
    if fault == "citation":
        notes["missing_evidence"][0]["evidence_ids"] = ["load:invented"]
    response = {
        "status": "completed",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(notes)}]}
        ],
    }
    if fault == "tool":
        response["output"] = [{"type": "function_call", "name": "repair_database"}]
    requests, observed = [], []

    def handler(request):
        body = json.loads(request.content)
        assert "tools" not in body
        requests.append(body)
        if fault == "timeout":
            raise httpx.ReadTimeout("private provider diagnostic")
        return httpx.Response(503 if fault == "unavailable" else 200, json=response)

    result = ai.explain(
        packet,
        provider="openai",
        key="test-only",
        transport=httpx.MockTransport(handler),
        response_observer=observed.append,
    )
    assert result["status"] == "unavailable" and result["attempts"] == len(requests) == 1
    assert result["notes"] == ai.fallback(packet) and packet == original
    assert "private provider diagnostic" not in json.dumps(result)
    if fault not in {"timeout", "unavailable"}:
        assert observed == [response]


def test_batch_preflight_reserves_budget_and_never_overwrites_results(tmp_path):
    output = tmp_path / "results"
    with pytest.raises(ValueError, match="budget"):
        ev.run(ev.SPEC, output, "openai", key="test-only", budget=0.01)
    assert not output.exists()
    output.mkdir()
    with pytest.raises(FileExistsError):
        ev.run(ev.SPEC, output)
    with pytest.raises(ValueError, match="key"):
        ev.run(ev.SPEC, tmp_path / "missing-key", "openai")


def test_batch_records_all_repetitions_and_does_not_approve_release(tmp_path):
    result = ev.run(ev.SPEC, tmp_path / "batch")
    assert result["completed_runs"] == 3 * len(CASES) == 54
    assert result["failed_runs"] == 0 and result["reserved_cost_ceiling_usd"] == 0
    assert result["release_gate"] == "blocked_pending_live_and_human_review"
    assert (tmp_path / "batch/human-review.md").is_file()


def test_tampered_context_is_rejected_before_call_or_output(tmp_path):
    spec = copy.deepcopy(SPEC)
    case = spec["cases"][0]
    spec["cases"] = [case]
    corpus = tmp_path / "contexts"
    corpus.mkdir()
    packet = context(case)
    packet["runbooks"][0]["check"] = "Tampered instructions"
    ev.write_json(corpus / f"{case['id']}.json", packet)
    ev.write_json(tmp_path / "spec.json", spec)
    with pytest.raises(ValueError, match="checksum"):
        ev.run(tmp_path / "spec.json", tmp_path / "output")
    assert not (tmp_path / "output").exists()
