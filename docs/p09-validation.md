# P09 validation: saved screen investigations

Status: implemented and verified against local SQL Server on October 2, 2026; GitHub CI acceptance pending. P01–P08, including P05A, remain accepted on the previously recorded evidence/user confirmations. No real provider call was made for P09; expanded live evaluation is P10.

## Implemented

- Screen investigation for a saved publication or a finding belonging to it, with confirmed facts, tentative causes, missing evidence, proposed checks, and rule-selected versioned runbooks/owners.
- Code supplies exact counts and unknown-value labels; the model produces only cited notes. Clean and incomplete reports work. Failed loads without saved reconciliation remain inspectable through existing finding/audit controls but cannot create a P09 investigation.
- Migration 008 adds append-only `ops.Investigation`; creation and attributed audit are atomic. Saved context/citations survive source correction, subsequent lifecycle changes, and API restart.
- Both demo roles can save investigation artifacts with Origin/CSRF checks. Ingestion and acknowledgement remain operator-only. The explanation adapter has no database/action tools.
- Explicit offline/off/live states, disabled-by-default live provider, one bounded call, no retries, and deterministic fallback for unavailable or invalid responses.

## Local evidence

Local verification on October 2, 2026, now including the full Docker/SQL run:

| Check | Observed result |
|---|---|
| `python -m pytest -q` | **286 passed, 52 SQL tests skipped**; existing Starlette/httpx deprecation warning |
| Compose test service with `--run-sql` | **338 passed, including all 52 SQL cases; no skips**, in 231.25 seconds |
| Compose database setup, then repeated setup | Database created; migrations 001–008 applied; repeat applied nothing |
| Restricted-login health and driver smoke | Passed |
| SQL demonstration and API check | Golden 100/94, corrected 98/98, no-op reuse, six resolved findings |
| `ruff check .` / `ruff format --check .` | Passed |
| `scripts/check-ui.py --fixture --origin http://127.0.0.1:8017 --output runs/p09-ui` | Passed expanded Chromium walkthrough |
| `scripts/check-ui.py --output runs/p09-local/ui-sql` | Passed complete browser workflow against real SQL Server in a separate database |
| `docker-compose --env-file .env.workbench config --quiet` | Passed configuration validation; no secrets printed |
| `git diff --check` | Passed |

The earlier unit-only run preceded Docker Desktop installation. Docker is now available, and all previously skipped SQL tests passed against SQL Server **16.0.4295.3**. [Retained local evidence](evidence/p09-local/README.md) includes full test output, browser verification, and tested-source fingerprints. No new dependency or lockfile change was needed.

The browser tool exercises actual HTML/JavaScript and API routes, substituting only simulated evidence/persistence. It covers operator finding investigation, AI-off clean report, citation inspection, frozen history after correction, analyst creation/reopening, malicious prose escaping, and mobile width. It also retains the P07/P08 correction, permission, audit, failure-state, and cross-origin checks. Generated captures and `verification.json` are in ignored `runs/p09-ui`; they are fixture previews, not SQL or live-model proof.

The subsequent live browser run used the real API and a separate SQL database, with captures in `runs/p09-local/ui-sql`. After the walkthrough, the API was restored to the main `workbench` database and its historical/corrected results rechecked. All three services remain running and healthy; the main screen is at `http://127.0.0.1:8000`.

## CI acceptance gate

Commit/push the P09 changes and require both existing GitHub Actions jobs to pass. CI already runs the full SQL suite and the expanded browser journey against an isolated real SQL database. The full suite is now observed locally as **338 passed, including 52 SQL cases with no skips**; it has not yet been observed in P09 CI. Retain the CI `sql-checks` and `ui-demo` artifacts and link the run URL before marking the CI gate accepted.

New SQL cases verify persisted/reloaded context after correction, unchanged publication evidence and totals, no-op attempt/publication separation, foreign-finding rejection, analyst attribution, append-only runtime permissions, and rollback when the required audit insert fails. Migration tests include the twelfth table and eight-script upgrade path.

P10 still owns repeated real-model scenario evaluation, broader injection/semantic review, and expanded assistant release acceptance. P11 owns recovery and performance evidence. See [investigation use and limits](investigations.md).
