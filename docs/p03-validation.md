# P03 validation record

Status: implemented locally; live SQL Server acceptance is pending.

## Implemented

- Eight-table foundation across source, migration metadata, captured input, loads, staging, and curated entities; reserved report schema.
- Three numbered migrations with a version ledger, per-script transactions, rollback diagnostics, and deployment locking.
- Source-matched provenance FKs, business keys, typed fields, unit/status checks, and unique publication/evaluation indexes.
- Explicit database creation and setup commands; separate administrator/runtime credentials and a restricted application role.
- Compose setup service and CI setup/rerun checks; 13 additional real-SQL integration cases.
- [Schema guide](database-schema.md), updated setup instructions, and P02's verified CI record.

## Observed locally

| Check | Result |
|---|---|
| Ruff lint and formatting | Passed |
| Default pytest run | 53 passed, 17 SQL tests skipped; one upstream Starlette warning |
| Deterministic fixture reproduction | All 29 generated files matched |
| Compose configuration, including tools/test/sources profiles | Passed with the standalone Compose CLI; this does not run containers |
| Dedicated demo configuration upgrade | Existing admin credential preserved; separate runtime credential generated; second run left file unchanged |

No Docker engine or SQL Server is available on the local Windows host. P02's [successful CI run](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36508588521) validates the previous revision only.

## Remaining acceptance gate

After this revision is pushed, the updated GitHub Actions workflow must:

1. Build the images, start SQL Server, create/migrate `workbench`, and rerun setup successfully.
2. Execute runtime `config-check`, `health`, and `db-smoke` as `workbench_app`.
3. Pass the full test suite with `--run-sql`, including empty-database migration, no-op reapplication, rollback of failed DDL plus its ledger entry, recovery, source-seed preservation, relational/lineage constraints, publication uniqueness, and role permissions.
4. Verify the mock registry container and clean up disposable infrastructure.

Record that run/commit and its artifact here before marking P03 complete or starting P04. Reassess the P03/P04 estimates after observing any SQL integration rework; retain the plan's 120-160-hour budget until that evidence exists.
