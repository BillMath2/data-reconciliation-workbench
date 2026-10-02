# P08 validation record

Status: implemented and verified locally; live SQL/browser acceptance pending. P07 was accepted on the user's green-CI confirmation for `9c98633`. No P07 artifact download or independent run-log inspection is claimed.

## Changes

- Read-only `GET /api/loads/{load_id}/audit` returns the selected attempt, its initiating actor, and paginated audit events with actors, timestamps, actions, and details. Both demo roles can inspect it. A no-op shows its own attempt history rather than substituting the reused publication's audit trail; failed loads remain inspectable.
- The screen's **Who ran this load?** panel shows that history and run reasons. Acknowledgement refreshes it. Source, rule, finding, operator reason, and audit values use text nodes; logout clears the displayed audit evidence.
- The HTTP boundary now checks the **actual received bytes** before parsing JSON. Previously only `Content-Length` was bounded. Writes reject oversized bodies, false lengths, duplicate/ambiguous boundary headers, and transfer encoding; the supported JSON write limit remains 8 KiB. Boundary errors receive the same cache, content-type, frame, referrer, and content-security headers as ordinary responses.
- Existing server sessions, operator dependencies, exact Origin checks, CSRF validation, runtime SQL permissions, and atomic mutation/audit transactions remain the authority. No schema migration, new business mutation, database role expansion, or AI tool capability was introduced.

## Coverage

| Acceptance requirement | Verification |
|---|---|
| Analyst mutation requests denied | Both operator endpoints checked with analyst sessions, even with valid CSRF; SQL test verifies loads, artifacts, findings, audit counts, original evidence, and curated totals stay unchanged |
| Operator actions attributable | Audit API checks run reason/actor/timestamp, review idempotency, successor resolution, separate no-op and failed attempt history, and pagination |
| Cross-site mutation checks | Both endpoints reject missing/wrong/session-mismatched CSRF, missing/null/other origins, and forged/expired/revoked cookies; a real browser cross-origin form is rejected |
| Audit records cannot be silently omitted or edited | SQL runtime UPDATE/DELETE on audit records denied; injected load-start audit failure prevents an admitted load, publication-audit failure rolls publication/resolution back, and no-op audit failure prevents a successful no-op; existing P06 acknowledgement-audit rollback remains required |
| Source content escaped | Chromium verifies markup stays text in source, finding, rule, resolution, exception audit, and load-audit fields; no injected element or event handler executes |
| Assistant has no write path | Explicit dependency-boundary check, no tool definitions in provider requests, a function-call-only response returns unavailable, and database/mutation hooks are forbidden in the test; route inventory permits only the reviewed session/run/acknowledgement POST routes |

## Local verification

- **245 tests passed; 48 SQL tests skipped.** The existing Starlette TestClient deprecation warning remains.
- Expanded Chromium walkthrough passes against the explicit in-memory service, including load-audit display/pagination, analyst acknowledgement denial, actual cross-origin form submission, and escaping checks. This verifies browser/API integration, not SQL persistence. The same script runs against SQL in CI and saves `ui-demo`.
- Ruff lint/format, JavaScript syntax, locked dependency consistency, fixture consistency, Compose configuration, and wheel asset checks pass.
- Docker's engine is unavailable locally. No new SQL execution is claimed.

## CI gate

Commit/push and require both Foundation checks jobs green. Expected full suite at this revision: **293 passed**, including **48 SQL tests without skips**. Three new SQL cases in `tests/integration/test_permissions_audit.py` check denied-request state preservation, attributable/append-only history, and required-audit rollback. Existing SQL, API, and browser checks remain mandatory.

Retain `sql-checks` and the `ui-demo` verification manifest/captures with the run URL. P08 remains pending until this new live gate passes. Then the planned next package is P09 (AI investigation in the screen); P11 recovery/performance can also proceed after P08.

## Scope limits

Analyst/operator are predefined local demo identities, not individual enterprise accounts. CLI actor labels are caller-provided and are not authenticated identities. Both HTTP roles use the restricted runtime SQL login behind server-side authorization; the database does not identify individual browser roles. Direct SQL compromise of that login is outside the HTTP role boundary.

The append-only audit is a load/exception history, not a production authentication or intrusion log. Rejected requests, login, and logout do not create load audit records. Server restart revokes in-memory sessions. SSO, production TLS, distributed sessions, rate limiting, and a broader security assessment remain outside this demo's acceptance claim.
