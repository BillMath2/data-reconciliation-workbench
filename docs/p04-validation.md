# P04 validation record

Status: complete for P04 and the P03 corrective migration.

## Verified CI revision

- Run: [36575474984](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36575474984), commit `02216b934fbf7a6e2937052917d10a818e90f516` (`adding P04`).
- Both Python and SQL jobs passed. SQL artifact `11038275046`, created 2026-09-29 13:32 UTC, reports **143 passed, 1 warning in 108.85s**: 110 non-SQL tests and all 33 SQL tests, with no skips.
- Setup/migration reruns, the identifier regression, actual REST/SQL/CSV ingestion with the runtime login, CLI no-op, correction, transaction rollback, and the mock container all passed.
- [Baseline CLI captures and replay](images/p04-baseline/README.md) use actual output from this run. They do not claim to show P05's later reconciliation workflow.

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

[Run 36572081104](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36572081104), commit `2ec55374342d314a41785ee142ec078b8b65a5df`, passed setup/migration reruns and runtime driver checks but had **62 tests pass and 8 fail**. All eight failures occurred when the original department identifier check rejected `DEPT-01`. The appended correction uses explicit ASCII alphabet checks after removing literal separators and adds a SQL regression case. Its effectiveness was verified by run 36575474984; see [P03 validation](p03-validation.md).

## Acceptance gates verified by this run

The workflow built the images, applied all five P04 migrations, verified the identifier regression, seeded the SQL source, loaded all three sources with runtime credentials, and executed an identical CLI rerun. Its SQL suite passed all 33 integration cases with no skips, including:

- Golden publication, corrected replacement, empty day, and preservation of other dates.
- No-op history/audit and the successful-evaluation uniqueness constraint.
- Rollback after deletion and just before commit, with retained staging and successful retry.
- Structural faults, unknown references, failed dependencies, and rejection of changed reference data.
- Actual REST pagination, actual SQL source reads, runtime grants, and freshness derived from SQL state.

The successful run above satisfies these gates. P05 adds persisted reconciliation, the guided CLI demonstration, and the saved evidence packet; its new SQL checks require a separate run.
