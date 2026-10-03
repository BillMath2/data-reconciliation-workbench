# Operator troubleshooting and verification

Use the [screen setup](workbench-ui.md) for initial seeding and sign-in. The
[schema guide](database-schema.md) covers deployment; the [recovery runbook](recovery-runbook.md)
covers interrupted workers and actual backup/restore. All examples use the local
synthetic demo. Keep credentials in ignored `.env.workbench`.

## Diagnose before retrying

1. Select the business date and recorded attempt. Inspect freshness, terminal
   state, source/report counts, and **Who ran this load?**. Record its load ID.
2. Inspect captured rows, manifest/reference evidence, and rules. A finding proves
   the recorded validation result; it does not prove an upstream root cause.
3. Correct the authoritative source. In this demo, choose the supplied corrected
   fixture and enter a run reason as the operator.
4. Verify the new publication, report totals, and each finding's successor link.
   Reopen old evidence to confirm history remains. Acknowledgement alone never
   clears an exception.

| Symptom | Check and response | Successful verification |
|---|---|---|
| SQL/API unavailable | Check Docker Linux engine, `docker compose --env-file .env.workbench ps`, then `docker compose --env-file .env.workbench run --rm workbench health`. Apply pending migrations and rebuild API after an upgrade. | SQL health succeeds; API `/health` responds; authenticated report loads |
| Missing or stale date | Confirm selected date, server clock, and next-day 09:00 America/New_York deadline. Check whether a capture/attempt exists. Old available data is not today's feed. | Correct date has a successful publication and explicit availability state |
| Failed refresh | Inspect failed attempt and safe failure code. Repair input/manifest/API completeness; preserve prior publication. | Retry publishes atomically; old successful packet remains inspectable |
| Duplicate or unknown project | Inspect primary disposition, original row, and captured valid references. Correct source; do not delete history or edit SQL to suppress findings. | Expected row/units accounting and recorded resolution to successor |
| Reference hash mismatch | References are frozen per demo database. Use a separately named fresh database with the intended fixture set; never rewrite old reference identity. | All reference loads and activities use one consistent fixture-set hash |
| Lost response or stuck attempt | Refresh history first. For an abandoned worker, follow recovery preview/apply in the recovery runbook; stop the worker before apply. | Committed input yields audited no-op; uncommitted input retries once |
| Analyst cannot run/acknowledge | This is expected. Sign in with the operator identity for those actions. Both roles can save investigations. | Server authorizes intended action and records actor/reason |
| Session expired or API restarted | Sign in again using the local token; session tokens are not persisted by the browser. | Fresh session with correct displayed identity |
| Provider unavailable/disabled | Use offline guidance or AI-off mode; inspect exact facts and missing evidence. Do not infer a correction from a model suggestion. | Deterministic report/evidence remains usable and explanation mode is labeled |
| Repeat demo seems unchanged | A successful evaluation identity is reused even after supersession. Inspect historical golden/corrected loads or run the isolated release rehearsal. | Distinct no-op attempt links to the existing publication; totals unchanged |

## Verify the installation

```powershell
docker compose --env-file .env.workbench --profile tools run --build --rm migrate
docker compose --env-file .env.workbench run --rm workbench db-smoke
docker compose --env-file .env.workbench --profile test run --build --rm tests --run-sql
```

The SQL suite creates uniquely named disposable test databases. Unit-only pytest
skips SQL cases and is not equivalent to this suite. Use the [isolated P12 replay](demo-guide.md)
to repeat the entire CLI/browser story without consuming existing activity history.

Ordinary `docker compose --env-file .env.workbench down` preserves the named SQL
volume. Do not add `--volumes` to routine shutdown. The P12 helper uses it only
for the unique project it creates and owns. Production deployment, offsite backup,
identity federation, retention, and monitoring remain [outside the demonstrated scope](release-scope.md).
