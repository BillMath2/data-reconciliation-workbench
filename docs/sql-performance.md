# P11 exception-query measurement

The selected query is the evidence API's first unresolved-finding page for a
business date: join `ops.Exception` to `ops.Load`, filter `resolved_at IS NULL`
and the selected date, order by attempt/ordinal/rule/ID, and return fifty rows.

The disposable relational fixture contains **100,000 synthetic activities and
100,000 historical findings**, with 100 findings still unresolved. It is loaded
setwise for query measurement and is **not** output from the ingestion pipeline:
the demo adapter still caps each input at 10,000 rows. The benchmark does not
measure capture/validation throughput or construct reconciled publications.

The final full-suite measurement on SQL Server 16.0.4295.3 (8 SQL-visible CPUs,
12,934,144 KiB reported physical memory) produced:

| Metric | Before | After migration 009 |
|---|---:|---:|
| Median operator logical reads | 2,718 | 6 |
| Median elapsed time, including XML plan transfer | 20.833 ms | 3.506 ms |
| Returned rows | 50 | 50 |

This is a **99.78% reduction in logical reads**. The before plan reads the
clustered exception index; the after plan uses `IX_Exception_UnresolvedPage`.
Every sampled result was identical. The actual evidence service also returned
the expected fifty ordinals through the restricted login.

## Reproduce and inspect

```powershell
docker compose --env-file .env.workbench --profile test run --build --rm --volume "${PWD}/runs/p11:/app/p11-evidence" -e WB_P11_EVIDENCE_DIR=/app/p11-evidence tests -v --run-sql tests/integration/test_performance.py
```

The test removes the candidate index only inside its owned, randomly named test
database, updates statistics, warms the query, and records three actual XML
plans/runs. It then applies the checked-in index DDL, warms again, and repeats.
There are no index hints or server-wide cache flushes. Logical reads are summed
from actual-plan `RunTimeCountersPerThread.ActualLogicalReads`; elapsed time
includes execution and plan transfer. The retained `.sqlplan` files open in SSMS.

The index covers the default unresolved page and omits resolved history. Its
keys preserve load/row/rule/ID ordering; included columns cover lifecycle fields,
including the filtered `resolved_at` column. See Microsoft's
[IS NULL filtered-index guidance](https://learn.microsoft.com/en-us/troubleshoot/sql/database-engine/performance/filtered-index-with-column-is-null).
Costs include index storage and maintenance on finding insert, acknowledgement,
and resolution. Existing history access remains available through the original
indexes; this is not a universal improvement for every filter or data distribution.

CI asserts unchanged results, use of the candidate index, and fewer logical
reads. It records timing without a brittle wall-clock pass threshold. These
warm-cache measurements cover one selected date and first page; they do not
prove the proposed two-second whole-screen target, concurrent throughput, or
performance at deep pagination offsets.

See [retained plans and observations](evidence/p11/README.md) for all samples.
The earlier focused run had the same logical reads with slightly different timing.
