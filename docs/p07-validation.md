# P07 validation record

Status: implemented and checked locally; live SQL browser acceptance pending. P06 was accepted on the user's green-CI confirmation for the P06 change in `5b99939`.

## Implemented

- A responsive single-page workbench: token login, date/load selection with pagination, publication/freshness state, source-versus-curated counts and units, exclusion accounting, filterable exception ledger, and source/rule/evidence/audit inspector.
- Distinct current, historical, no-op, unavailable-report, missing-date, failed-refresh, and incomplete-total states. Historical report totals never substitute for current date availability.
- Operator acknowledgement and full-date snapshot runs through the existing ingestion pipeline. Only the checked-in `golden` and `corrected` snapshots are accepted; dates must match their manifests. No caller-selected paths, SQL, URLs, roles, or actor strings.
- Run reasons and session-derived actors are recorded in the admitted load's `load_started` audit event. Existing application locking, atomic replacement, lifecycle resolution, rollback, and no-op behavior remain in that shared pipeline. An unchanged rerun is not an undo operation.
- Authenticated reads; operator, Origin, CSRF, JSON/body-size checks on new writes. Source content uses DOM text nodes, with a restrictive Content Security Policy. The analyst screen hides write controls and server checks reject forged writes.
- Real Chromium screenshots and a 25-second paced screenshot replay. Checked-in captures use the explicit browser fixture with P05 saved facts and **simulated lifecycle states**, not live SQL. See [capture provenance](evidence/p07/README.md).

## Local verification

- **212 tests passed; 45 SQL tests skipped.** The existing Starlette TestClient deprecation warning remains. New tests cover authenticated reads, snapshot restrictions, role/origin/CSRF/actor boundaries, server-clock freshness, invalid audit reasons, and static asset security headers.
- `scripts/check-ui.py --fixture` passes in Chromium: empty start, 100/94 inspection, acknowledgement remaining unresolved, correction to 98/98 and 197 units, retained source and linked resolution, unchanged rerun, historical replay leaving the current publication intact, analyst denial, missing date, source escaping, mobile layout, incomplete totals, failed refresh, unavailable report, exception pagination, service failure, and session expiry.
- Error/edge presentation checks intercept selected browser responses and do not claim to exercise SQL failures. The core journey uses the real page, JavaScript, HTTP API, sessions, and simulated service. Static assets are included in the runtime wheel.
- Ruff lint/format, JavaScript syntax, locked dependencies, generated-fixture consistency, and Compose configuration checks pass. Docker's engine is unavailable locally; no local live SQL execution is claimed.

## Remaining acceptance gate

Commit/push this package and require both Foundation checks jobs green. The SQL test suite is expected to report **257 passed**, including **45 SQL cases without skips**, for this revision. The added SQL case checks the snapshot endpoint through the real pipeline, rejected date selection, attributable run reasons, corrected totals, six successor resolutions, and no-op reuse.

The SQL job also creates a separate `workbench_ui` database, seeds only its reference sources, starts the real API against it, then runs the browser journey from an empty activity history. It preserves the earlier CLI demo in `workbench` and uploads a new **`ui-demo`** artifact alongside `sql-demo` and `sql-checks`. Browser failure fails CI; the script refuses to run over an existing activity history. The Python job separately runs the fixture browser check.

Review and retain the `ui-demo` screenshots, GIF, verification manifest, run URL, and `sql-checks` output. Replace the explicitly labeled preview captures with the accepted live SQL captures, recording their provenance. P07 remains pending until this live gate passes. P08 completes the broader role/audit coverage; P09 adds AI to the screen; the final narrated recording remains P12.
