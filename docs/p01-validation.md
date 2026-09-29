# P01 validation record

Status: complete for the container-based foundation.

## Verified revision and environment

- Repository commit: `5552a3bf66a98454829acd1567b0b76bb8adbcb4` (`adding P0`). This record uses the plan's work-package name **P01** for that foundation work.
- Workflow: [Foundation checks, run 36504051164](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36504051164).
- Both jobs, `python` and `sql-server`, completed successfully on `ubuntu-24.04`.
- Artifact: `sql-checks`, ID `11007260604`, created September 29, 2026 at 00:38 UTC (September 28 in New York).
- The artifact's test summary is `15 passed in 0.15s`. That duration covers pytest execution, not image builds or database startup.

## Acceptance evidence

| Gate | Observed result |
|---|---|
| Locked Python dependencies | `uv sync --locked --python 3.12` succeeded |
| Lint and formatting | Both Ruff checks passed |
| Unit tests | Python job passed; SQL cases are intentionally opt-in in that job |
| Compose configuration | Validation succeeded |
| Real SQL Server readiness | Compose started the pinned SQL Server image and passed its query-based health check |
| Runtime image | Build succeeded; `config-check`, `health`, and `db-smoke` succeeded |
| Driver behavior | Parameter binding, Unicode round trip, commit, and rollback checks passed against SQL Server |
| Test image and integration suite | Build succeeded; all 13 unit tests and both SQL integration tests passed, with no skips |
| Disposable CI cleanup | Containers and the CI database volume were removed successfully |

The primary driver, `mssql-python`, passed. Switching to the optional `pyodbc` fallback was unnecessary, and fallback execution is not claimed.

## Scope of this result

This proves the Python/SQL Server container foundation. The probe uses session-local temporary tables in `master`; it does not validate the future application schema, ingestion rules, reconciliation totals, permissions, or AI behavior. Those remain later work packages.

Local Windows unit/configuration checks passed separately. Docker Desktop was not installed, and this record does not claim a local Windows Compose run. The successful Linux CI run satisfies P01's live database acceptance gate.

The next work package is **P02: specify the three source contracts and seed synthetic fixtures**, including independently specified golden expected results. P03 will add application migrations, relational constraints, and additional SQL integration tests.
