# P05 validation record

Status: implemented locally; SQL acceptance and full P05 recording are pending.

## Verified prerequisite

P03/P04 passed [run 36575474984](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36575474984) for commit `02216b934fbf7a6e2937052917d10a818e90f516`: **143 tests passed**, including 33 SQL cases. The test artifact is `11038275046`. This verifies ingestion, correction, no-op, permissions, and rollback, but not the new P05 code.

## Implemented and checked locally

- Migration 006 adds `ops.ReconciliationResult` and two reporting views; publication writes actual SQL-checked totals and immutable evidence within its transaction.
- `reconcile`, `evidence`, and `demo` commands implement report selection, safe file export, and a fresh-database golden/correction/no-op walkthrough.
- Unit tests verify independent golden/corrected expectations, primary-reason accounting, unknown units/statuses, distinct row/completed grains, empty dates, actual-total mismatches, packet bounds/citations, and non-overwriting exports.
- **126 tests passed; 38 SQL tests skipped.** Ruff lint/format and Compose configuration checks passed. One existing upstream Starlette TestClient deprecation warning remains.
- The first PNG captures and 33-second GIF replay were generated from actual P04 CI JSON output and test results. They are labeled with their source run/commit. The first and last frames were visually inspected. These are rendered terminal captures, not desktop screenshots or P05 execution evidence.

## Pending live acceptance

The updated CI workflow must migrate an empty database through 006, run the full demo with the runtime login, pass all 38 SQL tests without skips, render its output, and upload `sql-demo` alongside `sql-checks`. The five added SQL cases cover historical/no-op evidence, unknown-versus-zero totals, atomic reconciliation rollback, detection of corrupted SQL totals, and the guided recording's assertions/history guard.

After that run succeeds, record its commit/run/artifact IDs here and promote the three P05 captures and replay to the README. No local SQL Server or Docker engine was available for this turn. The evidence packets for P05A must come from this verified SQL run; no synthetic packet is presented as a database result.

The final 5-7 minute narrated screen/AI video remains P12 work. P05A's first provider call follows P05 acceptance. The project planning budget remains 120-160 hours; re-estimate remaining UI/AI/recovery work after the verified demo replay.
