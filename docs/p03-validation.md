# P03 validation record

Status: complete. The correction passed [run 36575474984](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36575474984), commit `02216b934fbf7a6e2937052917d10a818e90f516`, together with P04: 143 passed, including all 33 SQL cases. See [P04 verification](p04-validation.md).

## CI findings and correction

[Foundation checks run 36572081104](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36572081104) verified commit `2ec55374342d314a41785ee142ec078b8b65a5df`. The Python job passed. SQL readiness, database creation/migration reruns, runtime login provisioning, and runtime driver probes passed. The test artifact (`sql-checks`, ID `11034179449`, created 2026-09-29 13:02 UTC) reports **62 passed, 8 failed**.

All eight failures arose while inserting the valid department ID `DEPT-01`: `CK_Department_Id` rejected it before the tests could reach their intended assertions. Migration [004_identifier_checks.sql](../sql/migrations/004_identifier_checks.sql) replaces the identifier checks across all three curated tables with explicit ASCII character checks after removing literal hyphens/underscores. Applied scripts 001-003 remain unchanged. A regression test covers valid separators, lowercase, whitespace, punctuation, and non-ASCII input. This correction subsequently passed the SQL regression in run 36575474984.

The correction shipped with P04 and its SQL regression passed in the successful run above. The initial failure remains documented here as historical evidence.

## Implemented

- Eight-table foundation across source, migration metadata, captured input, loads, staging, and curated entities; reserved report schema.
- Three numbered migrations with a version ledger, per-script transactions, rollback diagnostics, and deployment locking.
- Source-matched provenance FKs, business keys, typed fields, unit/status checks, and unique publication/evaluation indexes.
- Explicit database creation and setup commands; separate administrator/runtime credentials and a restricted application role.
- Compose setup service and CI setup/rerun checks; 13 additional real-SQL integration cases.
- [Schema guide](database-schema.md), updated setup instructions, and P02's verified CI record.

## Original P03 local observations (before P04)

| Check | Result |
|---|---|
| Ruff lint and formatting | Passed |
| Default pytest run | 53 passed, 17 SQL tests skipped; one upstream Starlette warning |
| Deterministic fixture reproduction | All 29 generated files matched |
| Compose configuration, including tools/test/sources profiles | Passed with the standalone Compose CLI; this does not run containers |
| Dedicated demo configuration upgrade | Existing admin credential preserved; separate runtime credential generated; second run left file unchanged |

No Docker engine or SQL Server is available on the local Windows host. P02's [successful CI run](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36508588521) validates the previous revision only.

## Original acceptance checklist (now verified)

After this revision is pushed, the updated GitHub Actions workflow must:

1. Build the images, start SQL Server, create/migrate `workbench`, and rerun setup successfully.
2. Execute runtime `config-check`, `health`, and `db-smoke` as `workbench_app`.
3. Pass the full test suite with `--run-sql`, including empty-database migration, no-op reapplication, rollback of failed DDL plus its ledger entry, recovery, source-seed preservation, relational/lineage constraints, publication uniqueness, and role permissions.
4. Verify the mock registry container and clean up disposable infrastructure.

The successful run and artifact are recorded above and in the P04 validation record. The current suite and required P04 evidence are in [P04 validation](p04-validation.md). Reassess integration rework after the corrected run; retain the plan's 120-160-hour budget until that evidence exists.
