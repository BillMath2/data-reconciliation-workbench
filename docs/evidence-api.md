# Evidence API and exception lifecycle (P06)

Status: P06 accepted on user-confirmed green CI; see [P06 validation](p06-validation.md). P07 adds the [operator screen](workbench-ui.md) and the endpoints below, pending its own live SQL/browser gate. This is a local demo API, not a production identity service.

## Start the API

The API uses migration 007 and the restricted `workbench_app` login. From PowerShell at the repository root:

```powershell
.\scripts\initialize-demo.ps1
.\.tools\docker-compose.exe --env-file .env.workbench up -d --wait --wait-timeout 240 sqlserver
.\.tools\docker-compose.exe --env-file .env.workbench --profile tools run --build --rm migrate
.\.tools\docker-compose.exe --env-file .env.workbench --profile web up -d --build --wait api
```

Use `docker compose` instead of the portable `.tools/docker-compose.exe` when Docker Desktop provides the CLI. Docker's engine must be running. Setup adds distinct analyst/operator tokens to `.env.workbench`, preserves nonempty credentials, and never prints them. The API publishes only `127.0.0.1:8000`; SQL remains on the Compose network. Visit `/health` to check the process. It explicitly does not claim to check database/schema readiness.

Load data using the existing [ingestion commands](ingestion.md) or the [fresh-database walkthrough](reconciliation.md#record-the-sql-walkthrough). After seeding/publishing the reference sources, P07 can run the supplied activity snapshots from the screen. A new empty database has no reports or exceptions until data is loaded.

For direct Python operation, `workbench-api --env-file PATH` binds to `127.0.0.1:8000`. Supply reachable SQL settings with `WB_SQL_USERNAME=workbench_app`, its runtime password, and both demo tokens. The server refuses an administrator login. `--container` binds inside the container; keep the published host port restricted to localhost. Run a single process: sessions are in memory and are invalidated on restart.

## Sign in and inspect

The token selects a predefined identity on the server; clients cannot supply a role or actor. This PowerShell example reads the operator token from the ignored configuration without displaying it:

```powershell
$base = 'http://127.0.0.1:8000'
$tokenLine = Get-Content .env.workbench | Where-Object { $_ -match '^WB_DEMO_OPERATOR_TOKEN=' }
$demoToken = ($tokenLine -split '=', 2)[1]
$sessionInfo = Invoke-RestMethod -Uri "$base/api/session" -Method Post -ContentType 'application/json' -Headers @{ Origin = $base } -Body (@{ token = $demoToken } | ConvertTo-Json) -SessionVariable demoSession
$loads = Invoke-RestMethod -Uri "$base/api/loads?business_date=2026-09-25" -WebSession $demoSession
$findings = Invoke-RestMethod -Uri "$base/api/exceptions?business_date=2026-09-25&status=all" -WebSession $demoSession
$findings.items | Select-Object exception_id, rule_id, status, resolved_by_load_id
```

Use `WB_DEMO_ANALYST_TOKEN` instead for read-only access. Both identities can inspect all synthetic demo data. They are not institutional accounts or tenant boundaries.

To acknowledge an unresolved finding, replace `EXCEPTION_UUID` with an ID from the response:

```powershell
Invoke-RestMethod -Uri "$base/api/exceptions/EXCEPTION_UUID/acknowledge" -Method Post -ContentType 'application/json' -WebSession $demoSession -Headers @{ Origin = $base; 'X-CSRF-Token' = $sessionInfo.csrf_token } -Body (@{ reason = 'Reviewed the captured source; awaiting correction.' } | ConvertTo-Json)
```

The complete P05 demo already publishes a corrected snapshot, so its findings will be resolved in a fresh P06 database. To observe acknowledgement first, stop after loading the golden input, acknowledge a finding, then publish the corrected input through the CLI. Acknowledgement is not a correction.

## Endpoints

All evidence endpoints require a session. Responses are JSON with `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.

| Method and path | Behavior |
|---|---|
| `GET /health` | Public process health, labeled local demo |
| `GET /` and `GET /static/*` | Public screen shell/assets; all evidence requires a session |
| `GET /api/snapshots` | Supplied snapshot names, labels, and manifest dates; no paths or source editing |
| `GET /api/freshness?business_date=YYYY-MM-DD` | Date-specific availability, deadline, failed-refresh state; server UTC clock |
| `POST /api/activity-runs` | Operator-only `snapshot` (`golden` or `corrected`), matching `business_date`, and required `reason`; session actor and reason recorded with the admitted attempt |
| `POST /api/session` | JSON token login; creates opaque HttpOnly, SameSite=Strict cookie and returns a session-bound CSRF token |
| `GET /api/session` | Current actor, role, and CSRF token |
| `POST /api/session/logout` | Invalidates the session; requires origin, JSON, and CSRF token |
| `GET /api/loads` | Activity attempts, newest first; optional `business_date`, `limit`, `offset` |
| `GET /api/loads/{load_id}/reconciliation` | Stored report with original/current publication metadata |
| `GET /api/loads/{load_id}/evidence` | Exact saved P05/P05A packet; no historical recomputation |
| `GET /api/loads/{load_id}/evidence/{evidence_id}` | Resolve a citation only within the selected packet |
| `GET /api/exceptions` | Filter by `load_id`, `business_date`, `status`, `limit`, `offset` |
| `GET /api/exceptions/{exception_id}` | Original finding, untrusted source/reference evidence, matching versioned rule definition, lifecycle, and audit events |
| `POST /api/exceptions/{exception_id}/acknowledge` | Operator-only acknowledgement with required reason; actor comes from the session |

List limits default to 50 and cap at 100; offsets are bounded to 100,000. Exception status defaults to `unresolved`, including acknowledged findings; other values are `open`, `acknowledged`, `resolved`, and `all`. Ordering is stable for an unchanged dataset, not a snapshot across simultaneous updates. A no-op load resolves to its reused publication for report/packet/finding inspection. Failed loads expose findings but return 404 for unavailable reconciliation. Unknown IDs return 404; malformed arguments return 422; unavailable SQL returns a redacted 503.

## Lifecycle semantics

Migration 007 adds lifecycle columns to `ops.Exception` and `report.vw_OpenExceptions`; it adds no new table. Original finding payloads, staged rows, and saved packets remain unchanged. The runtime role can update only the lifecycle columns, not finding evidence or finding identity.

| Transition | Evidence required |
|---|---|
| Open to acknowledged | Operator session and a nonblank reason; actor, timestamp, and reason are stored and audited in one transaction |
| Open/acknowledged to resolved (`key_valid`) | Later successful activity publication for the same date, reference set, and rule/contract versions; all successor rows for the normalized activity key are accepted without findings |
| Open/acknowledged to resolved (`key_removed`) | A complete replacement omits the old valid key, and the successor contains no ambiguous invalid keys; this records removal, not repair |
| Load-level failure to resolved (`load_recovered`) | A later successful publication in the same known scope demonstrates a successful refresh; row-level findings may still exist on the successor |

Matching uses normalized activity IDs within the business date, never row ordinals. Reordered rows cannot resolve an unrelated finding. A remaining error (even a different error) on the same key keeps the original finding unresolved. Missing/unparseable old keys stay unresolved because a replacement cannot reliably identify their correction. Another business date or a different reference/rule version cannot close a finding.

Resolution and its audit events commit with curated replacement and reconciliation. An injected failure rolls them all back. Failed attempts and no-op reruns do not resolve history. Each resolution links the successor load; acknowledgement stays available after resolution. Repeated acknowledgement preserves the first actor/reason and adds no duplicate audit event; acknowledging an already resolved finding returns 409. There is no manual resolve endpoint. A later recurrence creates a new finding, leaving the earlier resolution intact.

Only daily-activity findings have automatic successor resolution in this slice; fixed reference-data findings remain inspectable/acknowledgeable. Migration 007 does not backfill historical resolutions. Existing findings are evaluated on the next qualifying new successful publication, not by reinterpreting a saved packet. The saved packet's original exception-resolution boundary remains unchanged; the API exposes lifecycle separately.

## Write protection and limits

Every write requires the exact configured Origin and a bounded JSON body. Authenticated writes additionally require the session's CSRF token; acknowledgement also requires the operator role. Cookies expire after an hour, are rotated at login, and are revoked on logout. The session store is bounded. The localhost HTTP cookie is intentionally not marked Secure; production TLS/SSO is outside this demo. Host validation rejects DNS-rebinding hosts; CORS is not enabled. Use the exact `http://127.0.0.1:8000` origin for the Compose setup.

Validation errors omit request bodies, and SQL errors are redacted. Raw source values are returned only as untrusted JSON; the P07 screen renders them with text nodes and applies a restrictive Content Security Policy. Snapshot runs use the same operator/Origin/CSRF boundary as acknowledgement; no path, URL, SQL, actor, or role can be supplied. Worker contention returns 409. An admitted pipeline failure returns its recorded `status: failed` and load ID so the screen can inspect it; invalid selection returns 422. P08 completes broader permission/audit verification. The optional AI explanation still has no write path.

The implementation uses FastAPI's documented [dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) and [response cookies](https://fastapi.tiangolo.com/advanced/response-cookies/).
