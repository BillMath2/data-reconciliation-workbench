# P06 validation record

Status: complete on the user's confirmation that P06 CI is green, associated with P06 commit `5b99939` in the local history. The run URL and test artifacts have not been supplied or independently inspected in this session. This confirmation clears the P07 dependency; the expected counts below remain distinct from a reviewed CI log.

## Implemented

- Migration 007 adds acknowledgement/resolution columns and checks, a successor-load FK, column-scoped runtime UPDATE grants, and `report.vw_OpenExceptions`.
- Saved-report, packet, citation, load-list, and exception-detail/list services and API routes. Packet content stays identical to P05/P05A evidence. Exception detail adds original source/reference facts, matching versioned rule metadata, and separate lifecycle/audit information.
- Idempotent acknowledgement records its session-derived actor and reason atomically with audit. Original evidence cannot be updated through the runtime role.
- New successful activity publication resolves eligible historical findings in the same transaction. Matching uses normalized keys, known scope/version equality, and fully valid successor groups; missing keys and persistent faults stay unresolved. Full snapshot removal is labeled separately from correction.
- Local analyst/operator identities, bounded in-memory sessions, HttpOnly/SameSite cookies, strict Origin/Host checks, CSRF protection, role checks, JSON/body limits, and redacted errors.
- `workbench-api`, a localhost-only Compose `web` profile, and generated demo access tokens. No new load/repair/AI write endpoints or UI screen.

## Local verification

- **195 tests passed; 44 SQL tests skipped**, including 37 new offline API/lifecycle cases. One pre-existing Starlette TestClient warning remains.
- API tests exercise authenticated reads, saved-packet equality, unknown citations, operator acknowledgement, analyst rejection, role/actor spoofing, cross-origin/CSRF failures, token rotation/expiry/logout, filter bounds, JSON source safety, and redacted SQL errors.
- Lifecycle tests exercise reordered/normalized keys, persistent or changed faults, ambiguous identities, removal, and date boundaries.
- Ruff lint/format, dependency lock synchronization, and Compose configuration validation pass.
- Docker's engine is unavailable locally (`docker_engine` named pipe absent). No new SQL execution or successful live API/database test is claimed.

## CI acceptance

The user reported the P06 workflow green on October 1, 2026. The gate requires both Foundation checks jobs green. Expected suite for that revision: **239 passed**, including all **44 SQL tests without skips**. Retain the run URL/test log when available; no exact observed count is claimed here.

The six new SQL cases verify:

1. Real API acknowledgement, audit attribution, correction resolution, stable historical packets/citations, and no-op inspection.
2. Failed publication rolls back resolution/audit; no-op does not close findings; successful retry resolves eligible load failures.
3. Partial correction with reordered rows resolves only proven keys; later correction closes the remaining findings.
4. Different-date publication leaves findings unchanged; an empty replacement records key removal.
5. Audit failure rolls acknowledgement back; restricted credentials cannot change original finding evidence or delete findings.
6. Exception pagination, failed-load evidence, and missing selections.

CI also starts the real Compose API after the golden/corrected/no-op demo and runs `scripts/check-api.py`: anonymous reads denied, analyst login, historical 100/94 report, current 98/98 report, no-op packet reuse, and six findings linked to the correcting load. Migration setup/repeat and the full existing SQL suite remain mandatory.

P06 is accepted on that confirmation. P07 adds the workbench screen and its own live browser/SQL gate. Existing production, multi-worker, reference-history, and P10 AI evaluation deferrals remain unchanged.
