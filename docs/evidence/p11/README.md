# P11 observed local evidence

Recorded October 2, 2026, from the working tree based on `47a79fb`.
P10 CI green was user-confirmed after a rerun; P11 CI is still pending.

| Artifact | Observed result |
|---|---|
| `sql-checks.txt` | 386 passed, including 64 SQL cases, no skips; 301.80 seconds |
| `crash-*.json` | Six abrupt worker exits; prior publication or committed successor retained; explicit retry/no-op verified |
| `backup-restore.json` | COPY_ONLY/CHECKSUM, actual isolated restore, CHECKDB, twelve table fingerprints, saved investigation, correction and no-op retry |
| `performance.json` | 100,000 activities / 100,000 findings / 100 unresolved; identical fifty-row results; logical reads 2,718 to 6 |
| `before.sqlplan`, `after.sqlplan` | Actual plans from the first measured warm run before/after the candidate index |
| `tested-source-sha256.json` | Final code, test, migration, and workflow fingerprints |
| `local-application.json` | Local migration/repeat, recovery preview, and API checks |

The successful restore copy and all test databases were removed by their owned
test scopes. The unique backup path recorded in `backup-restore.json` remains
inside the local SQL volume; CI discards its test volume. Raw input artifacts,
historical findings, acknowledgement, audit, reconciliation, and saved
investigation content matched after restore before the correction was retried.

The performance data is a set-based relational query fixture, not an ingestion
throughput test or a measured whole-browser response time. Logical reads are
the sum of actual-plan operator counters; SQL timings include XML transfer.
The after plan uses the new filtered index without an index hint. See the
[method and limits](../../sql-performance.md) and [recovery runbook](../../recovery-runbook.md).

All data is synthetic. No passwords, connection strings, or provider keys are
included. No paid model call was made for P11.
