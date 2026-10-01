# P05A validation record

Status: complete for the bounded first AI slice, accepted locally on October 1, 2026. The offline stub and a real provider answer use the verified P05 golden evidence. P06 is next. The updated CI workflow has not yet been run for this revision.

## Acceptance evidence

- [Source SQL packet](evidence/p05/golden-evidence.json): produced by accepted P05 [CI run 36637726571](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36637726571), not a newly fabricated packet.
- [Offline stub](evidence/p05a/stub.txt) is explicitly labeled and uses no SQL or provider connection.
- [Live answer](evidence/p05a/live.txt), [structured result](evidence/p05a/live.json), and [provenance](evidence/p05a/provenance.json): OpenAI `gpt-4.1-mini-2025-04-14`, prompt `p05a-2`, 3,370 input / 852 output tokens, 8,703 ms recorded latency.
- Manual review confirmed 100 source / 94 report, two duplicate extras, three unknown projects, one missing project ID, and 202 source / 189 report units. All citations resolve. The response makes no unsupported repair claim.
- The live answer's suggested reference checks should use the captured reference set. Its possible-causes section restates the observed exclusions; it does not establish upstream causes. These limits are documented beside the retained example.
- A blocked sandbox connection produced the recorded [unavailable result](evidence/p05a/unavailable.json), retaining evidence and guidance. A network-enabled invocation reached the provider.
- The first live answer under prompt `p05a-1` failed structured count validation and was withheld; its [fallback record](evidence/p05a/rejected-v1.json) is retained. The corrected prompt/schema explicitly enumerates required metrics. The first rejected call's token usage was not retained; the implementation now retains returned usage even when validation rejects an answer. No automatic provider retries were used.

## Local verification

**158 tests passed; 38 SQL tests skipped**, with one pre-existing Starlette TestClient warning. This includes 32 new assistant tests covering:

- No SQL/network in stub mode and explicit configuration loading.
- Provider request format, token limits, secret redaction, and a preflight budget rejection.
- Exact counts, primary reasons, missing/unknown citations, and basic fabricated-action rejection.
- Missing, oversized, partial, inconsistent, and unknown-total packets.
- HTTP failure, disconnect, refusal, incomplete output, malformed/oversized response, HTTP timeout, and total deadline cancellation.
- Preserved deterministic fallback, usage on rejected answers, exit status, and export protection before a billable request.

Ruff lint and format checks pass; the dependency lock synchronizes offline. The CI Python job now runs an explicit offline explanation command, and the test image includes the verified packet. No SQL or schema behavior changed. The last live SQL acceptance remains P05's 164 passing tests; a new CI run is needed to verify the updated image and expanded suite together.

## Scope

This is one manually reviewed live example, not the P10 evaluation or a production governance guarantee. Full free-text factual validation, broad injection testing, screen integration, and persisted investigations remain later work. The original 120-160-hour project budget remains a planning estimate. Remaining P06-P12 packages total 52-70 focused hours before unused contingency.
