# Operator workbench (P07)

Open **http://127.0.0.1:8000/** after starting the Compose API. This is a local, synthetic-data demonstration with separate analyst and operator access tokens. The single page works without an AI provider.

## Start the screen

From the repository root, with Docker's Linux engine running:

```powershell
.\scripts\initialize-demo.ps1
docker compose --env-file .env.workbench up -d --wait --wait-timeout 240 sqlserver
docker compose --env-file .env.workbench --profile tools run --build --rm migrate
docker compose --env-file .env.workbench --profile sources up -d --build --wait mock-registry
docker compose --env-file .env.workbench build workbench
docker compose --env-file .env.workbench --profile tools run --rm migrate seed-departments
$referenceHash = (Get-Content fixtures/generated/index.json -Raw | ConvertFrom-Json).reference_sets.default
docker compose --env-file .env.workbench run --rm workbench load-departments --reference-hash $referenceHash
docker compose --env-file .env.workbench run --rm workbench load-projects
docker compose --env-file .env.workbench --profile web up -d --build --wait api
```

Open the ignored `.env.workbench` locally and paste the value of `WB_DEMO_OPERATOR_TOKEN` into the sign-in field. Use `WB_DEMO_ANALYST_TOKEN` for inspection and saving investigations, without ingestion or acknowledgement rights. Never include either value in a screenshot or commit. Tokens select predefined server identities; no role is supplied by the browser. Sessions expire after an hour and on server restart. The browser does not save the token in local storage.

## Walk through a correction

1. Choose **2026-09-25**. On a fresh activity database, select **Golden source**, provide a run reason, and choose **Run snapshot**. The screen shows 100 source rows, 94 accepted rows, and the six explained exclusions.
2. Inspect a finding. Expand its captured source, finding/reference evidence, rule, and audit history. Optional acknowledgement records review and a reason; it leaves the finding unresolved.
3. Select **Corrected source**, describe the correction, and run it. The supplied corrected CSV is a full-date replacement: source and curated results now agree at 98 completed activities and 197 units. There is no inline editing of captured evidence.
4. Choose **All loads for date** and **Resolved** to inspect the original six findings. Their source evidence stays intact; each points to the successful correcting load. Select the older recorded load to view its historical 100/94 report.
5. Repeat the corrected snapshot. The attempt is a **no-op**, referencing the same publication without duplicating activities. Repeating a superseded golden input also records a no-op and does not restore it as current.

If this database already contains the completed P05 demo, golden/corrected inputs will be no-ops. Inspect the existing history; use an explicitly separate demo database for a fresh recording rather than deleting the existing one. Older databases upgraded after correction may contain unresolved historical findings because migration 007 does not backfill resolution; unchanged reruns do not resolve them.

Date availability is evaluated against that date's next-day 09:00 America/New_York deadline using the server clock. It does not assert that an old date is today's feed. A failed replacement is labeled **Failed refresh** even when an earlier publication is available. Failed/interrupted attempts may have no saved reconciliation; their findings remain selectable. Read errors clear displayed report data and produce an error message. If a run response is lost, refresh load history before retrying.

## Browser verification and captures

P08 adds **Who ran this load?** below the summary. Expand it to inspect the selected attempt's initiating actor and paginated audit events, including run reasons and terminal results. A no-op's audit belongs to that attempt, while its reconciliation still refers to the reused publication. The panel also works when a failed load has no report. See the [role and audit guide](permissions-audit.md).

For local browser checks without Docker, using an explicit in-memory service:

```powershell
.\scripts\uv.ps1 sync --locked --python 3.12
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.tools\playwright'
.\scripts\uv.ps1 run --locked python -m playwright install chromium
.\scripts\uv.ps1 run --locked python scripts/check-ui.py --fixture --origin http://127.0.0.1:8017 --output runs/ui-fixture
```

The fixture exists only in the test tooling; it is not a production fallback and does not prove SQL behavior. It uses accepted P05 report facts with simulated later lifecycle states. Screenshots are real browser captures; the GIF is a paced replay of five captures. No login token is captured, and no credential-bearing browser trace is retained. See [Playwright screenshots](https://playwright.dev/python/docs/screenshots).

CI runs the same journey against the real SQL API in a dedicated `workbench_ui` database and uploads `ui-demo`. Live mode requires `WB_DEMO_ANALYST_TOKEN` and `WB_DEMO_OPERATOR_TOKEN` in the script's environment and a database with no activity attempts. `WB_SQL_DATABASE` now selects the Compose setup/runtime/API database, defaulting to `workbench`; use the same value when seeding, migrating, and starting the API. CI's disposal happens only inside its disposable volume. See [P07 validation](p07-validation.md) for its user-confirmed acceptance and pending artifact retention; [P08 validation](p08-validation.md) covers the new gate.

P09 adds **Explain this evidence**, with load/finding scope, offline guidance, AI-off mode, explicitly enabled live AI, and saved history for each attempt. Both roles can save an investigation; the original facts, observed state, and runbook versions remain frozen after correction. See the [investigation walkthrough](investigations.md) and [P09 validation](p09-validation.md). The screen provides no arbitrary file uploads, direct SQL, manual exception resolution, or AI repair action.
