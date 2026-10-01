# P05 validation record

Status: complete. SQL execution, saved evidence, and the three-stage recording were accepted on October 1, 2026. P05A is next.

## Verified CI revision and provenance

- Run: [36637726571](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36637726571). The user confirmed both `python` and `sql-server` jobs green and supplied the downloaded `sql-demo` and `sql-checks` artifacts.
- Source commit: `3bf61d91fa19e19eb5f6d1955c37e8c2dd243b37` (`adding P05`), embedded in the recording manifest.
- Recording timestamp: September 29, 2026, 22:08:56 UTC; SQL Server version: `16.0.4295.3`.
- Supplied artifact links: [11065247717](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36637726571/artifacts/11065247717) and [11065112970](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36637726571/artifacts/11065112970). The supplied links do not identify which ID belongs to each artifact name, so no mapping is assumed.
- Retained [test output](evidence/p05/sql-checks.txt): **164 passed, 1 warning in 123.84s**, with no skips (126 non-SQL and 38 SQL cases).
- [Provenance manifest](evidence/p05/provenance.json) records the supplied run/artifact links and SHA-256 hashes of the archive, retained evidence, and rendered media. Review used downloaded artifacts and the user's job-status confirmation; it did not independently retrieve the GitHub run.

## Acceptance evidence

The supplied setup log showed an empty database migrated through 006, a second migration run applying nothing, and successful runtime configuration, health, and driver checks. The three-stage demo ran with the runtime login.

| Stage | Observed result |
|---|---|
| Golden discrepancy | 100 source rows = 94 accepted + 2 duplicate extras + 4 invalid; completed units 202 source / 189 report |
| Primary reasons | 2 duplicates (5 units), 3 unknown projects (6 units), 1 missing project ID (2 units) |
| Corrected snapshot | 98 source / 98 accepted; 197 source / 197 report units; no exclusions |
| Identical rerun | `no_op`, reusing the corrected publication ID and identical saved evidence |
| Historical evidence | The verified demo manifest records the immutable historical-evidence check; the SQL suite includes historical/no-op evidence coverage |

Downloaded reports were checked against the independently specified [fixture expectations](../fixtures/expected/golden.json), including all six excluded row ordinals and rule IDs. Each exported evidence packet matches its report, and every citation ID resolves inside that packet. The corrected and repeated reports share publication `27f2d269-8b09-4610-9ce5-6f1cefffae68`; the original publication is `c4efb766-80fb-4b03-8fa6-9238da90fa5a`.

The five new SQL cases cover historical/no-op evidence, unknown-versus-zero totals, atomic reconciliation rollback, corrupted SQL total detection, and the guided demo's assertions/history guard. All 38 SQL cases passed. One existing upstream Starlette TestClient deprecation warning remains.

## Demonstration materials

The README now leads with the [P05 replay](images/p05/walkthrough.gif) and links all three [terminal captures](images/p05/README.md). Each 1440-by-720 capture was visually inspected. The GIF contains three 11-second frames (33 seconds total). The captures render actual CLI output; they are not desktop screenshots. The original real-time `.cast`, transcript, reports, and bounded packets are retained in the [evidence bundle](evidence/p05/README.md), ready for P05A.

The prior [P04 baseline](p04-validation.md) remains available. These P05 results supersede the earlier local-only result of 126 passed / 38 SQL tests skipped. No new local SQL execution is claimed.

## Next checkpoint

P05A adds a labeled offline explanation stub and one real provider call against this saved golden evidence, with citation/count checks, timeout/output caps, and unavailable-provider handling. Provider/model selection, credentials, and a small call budget remain to be established. The workbench screen and exception lifecycle remain later packages; this demo does not claim findings have been automatically resolved.

At the P05 checkpoint, the remaining package estimates total **56-76 focused hours** (P05A and P06-P12). Retain the original **120-160-hour** whole-project planning budget; elapsed effort was not logged, so this is remaining scope estimated from the backlog, not an actual-versus-budget calculation. Reassess after the first real provider call. The final 5-7 minute narrated screen/AI video remains P12 work.
