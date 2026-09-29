# P04 validation record

Status: implemented locally; P03 correction and live SQL acceptance are pending.

## Implemented

- SQL department, paginated REST registry, and CSV/manifest adapters with retained captures.
- Fixed v1 validation, normalized duplicate/conflict rules, primary exclusions and additional findings.
- Migration 004 corrects P03's identifier check; migration 005 adds findings, audit events, and deterministic attempt ordering. Existing migration files remain unchanged.
- Restricted-login ingestion commands, sequential no-op reruns, fixed reference dependencies, atomic date replacement, and failed-attempt recording.
- Read-only freshness with an injected clock, New York daylight-saving handling, and failed-refresh status.
- CLI/Compose instructions and CI commands for real source loading and SQL tests.

## Observed locally

| Check | Result |
|---|---|
| Ruff lint and format | Passed |
| pytest | 110 passed, 33 live SQL tests skipped |
| Golden row validation | 100 raw, 94 accepted, six expected exclusions; 189 accepted units |
| Corrected/clean/conflict/invalid/empty fixtures | Local adapter and validation checks passed |
| REST pagination | TestClient checks plus a real local HTTP smoke run: default 25 accepted; unknown-department 24 accepted; incomplete 20-of-25 capture rejected |
| Freshness | Before/at/after deadline and winter UTC offset checks passed |
| Existing generated fixtures | All 29 files reproduced byte for byte |
| Compose profiles | Configuration validates with tools, sources, and test profiles |

The suite has one pre-existing upstream Starlette TestClient HTTPX deprecation warning. No local Docker engine or SQL Server is available; there is no claim of local publication or rollback execution.

## P03 prerequisite defect

[Run 36572081104](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36572081104), commit `2ec55374342d314a41785ee142ec078b8b65a5df`, passed setup/migration reruns and runtime driver checks but had **62 tests pass and 8 fail**. All eight failures occurred when the original department identifier check rejected `DEPT-01`. The appended correction uses explicit ASCII alphabet checks after removing literal separators and adds a SQL regression case. Its effectiveness still requires the next live run; see [P03 validation](p03-validation.md).

## Required next CI evidence

The workflow must build the updated images, apply all five migrations, verify the identifier regression, seed the SQL source, load all three sources with runtime credentials, and execute an identical CLI rerun. Its SQL suite must pass all 33 integration cases with no skips, including:

- Golden publication, corrected replacement, empty day, and preservation of other dates.
- No-op history/audit and the successful-evaluation uniqueness constraint.
- Rollback after deletion and just before commit, with retained staging and successful retry.
- Structural faults, unknown references, failed dependencies, and rejection of changed reference data.
- Actual REST pagination, actual SQL source reads, runtime grants, and freshness derived from SQL state.

Record the new run/commit and test artifact before accepting P03/P04 or starting P05. P05 still owns persisted reconciliation, the guided CLI demonstration, screenshots/recording, and the evidence packet for the AI slice.
