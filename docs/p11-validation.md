# P11 validation: recovery, restore, and SQL performance

Status: implemented and locally verified on October 2, 2026; the user subsequently confirmed P11 GitHub CI green for `901db40`. The exact CI run/artifacts were not independently inspected in this session. P10's rerun was
confirmed green by the user for commit `47a79fb`; live-model evaluation and human
semantic review remain open. P11 depends on accepted P08 and can proceed independently.

Implemented:

- Preview-first `workbench recover-loads`, with explicit apply/reason, ingestion
  lock coordination, atomic failure/finding/audit updates, preserved artifacts,
  and safe explicit retry.
- Six real worker-exit rehearsals, including interruption mid-publication and
  after commit, plus active-worker exclusion and audit-failure rollback checks.
- Copy-only/checksummed backup, actual isolated restore, CHECKDB, all-table hash
  comparison, restored investigation/lifecycle verification, and correction retry.
- A 100,000-activity/100,000-finding query fixture, actual before/after SQL plans,
  logical-read and timing measurements, and migration 009's covering filtered index.
- Existing SQL CI now retains `p11-evidence` alongside the prior artifacts.
  Verbose test names and slow-test timings make stalls easier to locate; the SQL
  test step is bounded to 15 minutes within the existing 30-minute job budget.

The full Docker suite passed **386 tests, including all 64 SQL cases, with no
skips**, in **301.80 seconds**. The existing Starlette/httpx deprecation warning
remains. Lint, formatting, fixture regeneration checks, and `git diff --check`
passed. The recovery and restore checks run with real SQL and real abrupt process
exit; these are not mocked transaction results.

The final performance run measured **2,718 to 6 logical reads (99.78% fewer)**
with identical output. Median query time including XML plan transfer was
**20.833 ms before and 3.506 ms after**. The small test backup took 179 ms and
actual restore took 811 ms; these times are not recovery SLA claims. The restored
database contained all nine migrations and the twelve table snapshots matched.

Migration 009 was applied to the existing local `workbench` database; repeating
setup applied nothing. Recovery preview found no abandoned attempts. The API was
rebuilt and left healthy; its historical 94-row report, corrected 98-row report,
and six resolved findings still passed the authenticated inspection check.

No dependencies, identity privileges, schema tables, or live-model calls were added.
See the [recovery runbook](recovery-runbook.md), [performance method](sql-performance.md),
and [evidence](evidence/p11/README.md). P11 CI acceptance is still required after
commit/push; P12 full release additionally requires P10's live/human-review gates.
