# P02 validation record

Status: complete for contracts, fixtures, source seed, and mock registry.

- Verified commit: `833e955bb45e85eed269a4e11ca9eda5b240f281` (`adding p02`).
- Workflow: [Foundation checks, run 36508588521](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36508588521); both `python` and `sql-server` jobs succeeded.
- SQL artifact: `sql-checks`, ID `11007614940`, created September 29, 2026 at 01:35 UTC (September 28 in New York).
- Observed pytest summary: **33 passed, 1 warning in 4.40s**, with no SQL skips. This covers 29 non-SQL tests and four SQL tests.

The run verified locked dependency installation, Ruff lint/format, byte-for-byte fixture reproduction, runtime and test image builds, SQL readiness and driver checks, repeatable department seeding and its safety guards, and the mock registry container's health/HTTP response. CI cleanup succeeded. The warning is the upstream Starlette TestClient HTTPX deprecation.

Local P02 checks separately retrieved all 25 projects through real HTTP pagination. Golden expectations describe the future ingestion result; P02 does not prove publication, reconciliation, or AI behavior. P03's new migrations and permissions are outside this verified revision.
