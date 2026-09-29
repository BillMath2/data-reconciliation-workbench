# Reconciliation, evidence, and the CLI demonstration

P05 saves one reconciliation result and one bounded evidence packet per successfully published activity load. The result is inserted in the same transaction as curated replacement and publication state. No-op attempts reuse a prior result; failed publications cannot leave a successful result behind.

P03/P04 are verified in [CI run 36575474984](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36575474984). P05's migration, publication extension, and complete recording await their own SQL run. See [P05 validation](p05-validation.md).

## Read a report or export evidence

After setup, seeding, and loading an activity date with migration 006 applied:

```powershell
docker compose --env-file .env.workbench run --rm workbench reconcile --business-date 2026-09-25 --format text
docker compose --env-file .env.workbench run --rm workbench reconcile --business-date 2026-09-25
docker compose --env-file .env.workbench run --rm workbench evidence --business-date 2026-09-25
```

`reconcile` defaults to JSON with the report and packet. `--format text` displays counts, unit totals, primary exclusion groups, and publication state. Select a specific historical publication or no-op attempt using `--load-id <uuid>` instead of the business date. A date selects its current publication; a no-op ID follows its `reused_load_id`, which may now be historical. Failed attempts return `REPORT_UNAVAILABLE`, not an unrelated successful report.

`evidence` returns only the saved packet. `--output <new-file>` writes it to an existing directory without overwriting files. Inside Docker, export paths are container paths unless mounted; the guided demo below writes all artifacts to a host directory.

Migration 006 does not invent historical reconciliation records for P04 publications. Those remain inspectable through their load/staging evidence, but the new report is unavailable for them. An identical rerun retains its original no-op semantics and does not backfill a report. Use a fresh demo database for the complete guided workflow.

## What the counts mean

| Metric | Definition |
|---|---|
| Raw/accepted/excluded rows | Full activity snapshot for one business date; each raw row has exactly one disposition |
| Completed activity counts | Rows declaring normalized `completed` status, compared with actual curated completed rows |
| Completed units | Units on declared completed rows; `null` if any such source row has unreadable/out-of-range units |
| Primary reasons | Each excluded row contributes once, even when it has additional findings |
| Unknown statuses | Reported separately; they are not silently treated as completed or as a known valid status |

The engine checks actual SQL row/count/unit totals against the accepted staged rows. Row accounting and completed-count differences must match their exclusion groups. Unit differences are checked when source units are complete. Unknown units remain unknown; an empty snapshot has known zero totals. All sums use Python integers and SQL `BIGINT`, avoiding 32-bit aggregate overflow.

The golden fixture reconciles `100 = 94 + 2 + 4` rows and `202 - 189 = 5 + 6 + 2` completed units: duplicate extras, unknown projects, and a missing project ID. After correction, source and report both contain 98 completed activities and 197 units. Independent expectations remain in `fixtures/expected/golden.json`; ingestion and reconciliation never read that file. Tests and the guided demo use it to verify their observed results.

`report.vw_LoadReconciliation` includes saved successful and superseded publications with an `is_current` flag. `report.vw_ProjectActivity` groups only current curated activities by date/project/load. An empty date has a saved zero reconciliation even though it has no project rows.

## Evidence boundary

The saved packet contains the business date, reference hash, contract/rule/calculation versions, captured artifact hash, summary, relevant fixed rule definitions, and stable evidence IDs. These include `load:<uuid>`, `artifact:<uuid>`, `reconciliation:<load-uuid>`, `exception:<uuid>`, and `row:<load-uuid>:<ordinal>`.

At most 40 findings and 20 excluded source-row samples are included. Source strings are capped at 240 characters, nested collections at 20 entries, and the full packet at 64 KiB. If multibyte source text exceeds that budget, samples are removed until it fits; accounting remains intact. Counts record how many findings/rows are included versus available. Full raw captures and all findings remain in SQL. Source snippets are explicitly untrusted data. A future explanation must cite only `citation_ids`; packet bounds alone do not implement the P05A provider/citation validation layer.

Historical packets are read from saved JSON, not recomputed against today's references or rules. The surrounding report separately supplies current/superseded status and no-op request context. Packets do not claim that an assistant repaired data or that historical exceptions are resolved. Freshness remains a separate read-only observation with an injected clock; it must not be mistaken for a historical publication fact.

## Record the SQL walkthrough

Use a fresh, migrated demo database with the department source seeded and mock registry running. The command refuses any database with previous activity attempts; it never deletes history to reset a demo. For repeated experiments, use a distinct Compose project/volume, or a separately configured disposable database. Only one mock registry should occupy host port 8001 at a time.

From PowerShell after the README setup, before manually loading any activities:

```powershell
docker compose --env-file .env.workbench --profile tools run --rm migrate seed-departments
docker compose --env-file .env.workbench --profile sources up -d --build --wait mock-registry
New-Item -ItemType Directory -Force runs | Out-Null
docker compose --env-file .env.workbench run --rm --volume "${PWD}/runs:/app/runs" workbench demo --output-dir /app/runs/demo
```

On Linux, add `--user "$(id -u):$(id -g)"` to the `docker compose run` command so the non-root container process can write the host directory. CI uses that form. Choose a new output directory for each run; existing output is preserved.

The demo loads references, publishes golden input, records its report, publishes corrected input, repeats it, and verifies unchanged totals and immutable historical evidence. It writes:

- `golden.json`, `corrected.json`, `repeat.json`: observed SQL reports.
- Matching `*-evidence.json`: bounded saved packets for the upcoming AI slice.
- `transcript.txt` and `demo.cast`: captured output, including real elapsed output timings in asciinema v2 format.
- `recording.json`: verified stages, UTC time, SQL Server version, and source revision when `WB_BUILD_REVISION` is supplied.

The successful manifest and recording are written only after all demo assertions pass. A failed run can leave partial reports for diagnosis but does not get a verified recording manifest.

Render recorded output with development dependencies:

```powershell
.\scripts\uv.ps1 sync --locked --python 3.12
.\scripts\uv.ps1 run --locked python scripts/render-demo.py runs/demo/recording.json runs/demo/media
```

The renderer produces three PNG terminal captures and a 33-second paced GIF. They render the actual recorded text; they are not desktop screenshots or a narrated video. The `.cast` preserves real timing. CI uploads the raw recording, reports, packets, and rendered media as the `sql-demo` artifact. After a successful P05 run, review and promote those assets to the README. The initial checked-in [baseline replay](images/p04-baseline/walkthrough.gif) is accurately labeled P04 footage, not a substitute for P05's pending SQL acceptance.
