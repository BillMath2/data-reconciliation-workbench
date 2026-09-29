# Source contracts and synthetic fixtures (P02)

Contract and rule-set version: **1.0.0**. All names, IDs, and events are fictional. Dates are deliberately fixed; tests must inject their clock rather than rewrite fixtures to today's date.

## What is implemented

The three source contracts, field ownership, rule metadata, deterministic source generator, read-only mock registry API, SQL department bootstrap, and independent expected outcomes are checked in. P04 now implements their adapters, validation, quarantine, and publication path; see the [ingestion guide](ingestion.md) and its pending SQL acceptance gate.

| Source | Contract | Authoritative fields | Transport |
|---|---|---|---|
| Department reference | [departments.json](../config/contracts/v1/departments.json) | Department identity, name, active flag | `source.Department`, five rows |
| Project registry | [projects.json](../config/contracts/v1/projects.json) | Project identity, name, department assignment, status, update time | Mock REST snapshot, 25 rows in pages of 10/10/5 |
| Daily activities | [activities.json](../config/contracts/v1/activities.json) | Activity identity/date, project assignment, status, completed units, update time | UTF-8 CSV and sidecar manifest |

Each contract lists the field's target curated column. [Field ownership](../config/field-ownership.json) separates an activity's project assignment from the registry's ownership of project descriptions. A referencing feed never overwrites the referenced entity's fields. These JSON files are explicit metadata contracts, not JSON Schema documents or an executable rules framework.

## Identity, types, and normalization

- Keys: `department_id`, `project_id`, and `(activity_date, activity_id)` respectively.
- IDs: trim surrounding whitespace, uppercase ASCII letters, allow only `A-Z`, digits, `_`, and `-`; maximum 16 characters. Raw values are preserved in staged evidence.
- Names: trimmed, nonempty strings up to 100 characters. Statuses: trimmed lowercase strings from the allowed set in the contract.
- Department activity flag: SQL `BIT`, represented as a JSON boolean. An inactive department or paused/closed project is still a known reference; v1 does not reject activities solely for that state.
- Business dates: calendar-valid `YYYY-MM-DD` in `America/New_York`. A parseable row date differing from the manifest fails the entire load. Missing or unparseable row dates are individual required/format findings and have no valid business key.
- Row timestamps: calendar-valid `YYYY-MM-DDTHH:MM:SSZ`, second precision, UTC. Manifest/API export timestamps follow the same format; invalid envelope metadata fails the load.
- CSV units: trim whitespace, parse only decimal digits, and require an integer from 0 through 2,147,483,647. Completed rows require at least one unit; planned/cancelled rows require zero. No floats, negative values, scientific notation, or silent numeric coercion.
- Missing values: absent/null/blank after trimming. A missing required CSV **column** is a load error; a blank required **cell** is a row finding.

Fixed rule IDs and parameters are in [rules.json](../config/rules.json). A load fails for unknown schema versions, missing/extra columns or record fields, malformed CSV/JSON structure, invalid manifest metadata/counts, mixed valid business dates, incomplete pagination, or duplicate reference keys. Other row findings preserve evidence and quarantine the affected row. Local tests cover these checks; SQL integration tests cover their durable publication behavior and await CI.

## Snapshot and reconciliation semantics

Every activity CSV is a full replacement snapshot for one business date. Its manifest declares `schema_version`, `source_id`, `business_date`, `exported_at`, `row_count`, `reference_set_id`, and `reference_set_sha256`. Row count excludes the header and includes duplicate/invalid records. A header-only file with count zero is a valid empty day; a missing file is a missing feed.

The feed is due at 09:00 New York time on the day after its business date. S08 specifies UTC times immediately before and after that deadline. An absent current-day artifact is stale after the deadline even when an older publication is visible.

After normalization, compare all six activity fields for duplicate detection. Different payloads sharing a complete business key form a conflicting group: exclude the whole group. Identical copies retain the lowest one-based captured row ordinal; exclude later copies. A retained copy must still pass the other rules. Rows with missing/unparseable keys remain separate invalid rows.

A row can have multiple findings but one accounting disposition. Select its primary exclusion using the ordered rule list in the activity contract, so totals never count it twice. Unknown unit values make the source-unit total incomplete, not zero. The future reporting layer must distinguish source totals, accepted totals, duplicate exclusions, and invalid-row exclusions.

Reference fixtures are fixed per demo database. Their SHA-256 is computed from UTF-8 canonical JSON containing the departments sorted by ID and projects sorted by ID, with sorted object keys and compact separators. `fixtures/generated/index.json` also records raw-byte hashes for every generated artifact except the index itself. JSON/CSV/SQL fixtures use LF line endings enforced by `.gitattributes`.

The unknown-department scenario has a separate reference hash and requires a fresh demo database. It must never mutate the default reference set in place. Historical reference re-evaluation remains deferred.

## Golden expectations

[golden.json](../fixtures/expected/golden.json) is maintained independently from the generator. The generator never reads or writes it. Its exclusions and totals are the assertions used by P04's validation/publication tests and the future reconciliation tests.

| Dataset | Source rows | Expected accepted rows | Source completed units | Expected accepted units |
|---|---:|---:|---:|---:|
| Clean | 100 | 100 | 201 | 201 |
| Golden discrepancy | 100 | 94 | 202 | 189 |
| Corrected snapshot | 98 | 98 | 197 | 197 |

In the golden file, ordinals 95-97 reference `PRJ-UNKNOWN`, ordinal 98 has a blank project ID, and ordinals 99/100 are exact copies of ordinals 1/2. These exclude four invalid rows (8 units) and two duplicate extras (5 units): `202 - 189 = 8 + 5`.

The correction removes the duplicate extras and repairs the four project assignments while retaining activity IDs. Only the repaired records receive the correction timestamp. P04's integration tests use the independent expected file to verify publication and replay; those live checks are pending.

## Reproduce and inspect the sources

From the repository root in PowerShell:

```powershell
.\scripts\uv.ps1 sync --locked --python 3.12
.\scripts\uv.ps1 run --locked workbench-fixtures --check fixtures/generated
.\scripts\uv.ps1 run --locked workbench-fixtures --output runs/recreated-fixtures
.\scripts\uv.ps1 run --locked workbench-registry
```

`--check` compares every generated file byte for byte without writing. `--output` writes the deterministic artifacts to the explicit destination; use `runs/` for experiments. Only deliberately regenerate checked-in data after a contract/fixture review. Independently review any expected-result changes.

With the registry running, open `http://127.0.0.1:8001/projects` or `/docs`. Follow `next_cursor` with `?cursor=page-2`, then `?cursor=page-3`. The terminal value is JSON `null`. Each page carries the same snapshot ID, reference hash, export timestamp, and declared total. The consumer must verify completeness and reject a repeated cursor or changed snapshot metadata.

Fault endpoints are explicit: `?scenario=incomplete` ends after 20 records while still declaring 25; `?scenario=unknown-department` changes PRJ-001's department in its own reference set. Keep the scenario parameter on every paginated request. Invalid cursors/scenarios return HTTP 400, and writes return HTTP 405. The API loads immutable fixture data at startup; it does not accept file paths or connect to a database.

Container equivalent:

```powershell
.\scripts\initialize-demo.ps1
docker compose --env-file .env.workbench --profile sources up -d --build --wait mock-registry
Invoke-RestMethod http://127.0.0.1:8001/projects
docker compose --env-file .env.workbench --profile sources down
```

The mock's port is bound to localhost; SQL remains private. This source service is separate from the future workbench web screen.

## SQL reference seed

The reproducible [department SQL script](../fixtures/generated/reference/departments.sql) creates only the synthetic `source` schema/table, inserts the five department records, and leaves an identical rerun unchanged. It refuses system databases and rejects changed or extra existing department data instead of overwriting it. Missing seed rows can be inserted. Operational schema/migrations belong to P03.

Run the script in a **disposable user database**, not `master`. For example, on a SQL host with `sqlcmd` and appropriate credentials, supply `-d WorkbenchDemo -b -i fixtures/generated/reference/departments.sql` after creating that demo database. Use `SQLCMDPASSWORD` or the environment's supported authentication rather than putting passwords on the command line. P03 provides the [database/migration setup path](database-schema.md); seeding requires administrator/source-owner access because the runtime role can only read the source table.

The opt-in integration suite creates a uniquely named `workbench_fixture_test_<uuid>` database, seeds it twice, verifies five rows, checks that altered source data is preserved on rejection, and removes only that database afterward. It also checks the system-database guard. This requires database-creation privileges in the disposable test environment; ordinary local unit tests do not connect to SQL Server.

## Scenario coverage and validation limits

[scenarios.json](../fixtures/scenarios.json) maps S01-S12 to source files or procedural steps. P04 tests cover replay, replacement, and injected publication failure for S09/S10/S11. S12 has separate manifest-count, header, date, and pagination faults. An additional empty-day fixture distinguishes zero activity from a missing feed. P05 adds saved reconciliation results and the guided demonstration.

P02 local verification covers fixture reproducibility/hashes, reference relationships, field ownership/rule references, exact golden inputs and independently specified outcomes, correction changes, mock API behavior, and a real HTTP pagination smoke test. [GitHub Actions run 36508588521](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36508588521) subsequently passed all 33 tests, including four live SQL checks, and verified the rebuilt mock registry container. See [P02 validation](p02-validation.md). P03 schema verification is a separate pending gate.
