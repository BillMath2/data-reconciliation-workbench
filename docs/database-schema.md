# Database schema and migrations

P03 introduces eight tables through three numbered migrations. The tables support captured evidence, load attempts, and current curated data. Ingestion, findings, reconciliation, audit events, investigations, and reporting views arrive in later packages. Live SQL verification of this revision is pending; see [P03 validation](p03-validation.md).

## Initial tables

| Table | Key and important fields | Responsibility |
|---|---|---|
| `meta.SchemaMigration` | Version PK, unique filename, UTC applied time, original login | Applied-version ledger, created by the runner before migration 001 |
| `source.Department` | Department ID PK; name and active flag | Authoritative synthetic SQL input; compatible with P02's seed |
| `ops.InputArtifact` | UUID PK; source ID, SHA-256, raw bytes, JSON metadata, UTC captured time | Preserve exact captured input; runtime can insert/read but cannot update/delete |
| `ops.Load` | UUID PK; source/date, artifact FK, contract/rule versions, reference hash, evaluation key, status/times, actor, previous/reused load links | One row per attempt; retain failed, superseded, and no-op attempts |
| `stg.SourceRow` | `(load_id, row_ordinal)` PK; source, raw JSON, SHA-256, disposition, primary rule | Captured row envelope and one accounting disposition per row |
| `core.Department` | Department ID PK; name/active, originating load/ordinal | Current curated department |
| `core.Project` | Project ID PK; department FK, name/status, UTC updated time, originating load/ordinal | Current curated project |
| `core.Activity` | `(activity_date, activity_id)` PK; project FK, status/units, UTC source update, originating load/ordinal | Current activity partition per business date |

The full typed column definitions live in [001_capture.sql](../sql/migrations/001_capture.sql) and [002_curated.sql](../sql/migrations/002_curated.sql). Field ownership and normalization are specified in the [source contracts](source-contracts.md). Curated IDs are uppercase ASCII, at most 16 characters; names are Unicode and at most 100 characters. Curated source timestamps use `DATETIME2(0)` and must be supplied in UTC. Operational timestamps use UTC `DATETIME2(3)`.

```mermaid
erDiagram
    InputArtifact ||--o{ Load : captured_input
    Load ||--o{ SourceRow : contains
    SourceRow ||--o{ Department : provenance
    SourceRow ||--o{ Project : provenance
    SourceRow ||--o{ Activity : provenance
    Department ||--o{ Project : owns
    Project ||--o{ Activity : references
```

The diagram shows the six pipeline tables. `source.Department` is the simulated input, not the curated department table; `meta.SchemaMigration` is independent deployment metadata. A load may exist without an artifact when capture fails.

## Constraints and publication boundary

Composite foreign keys carry the source ID through artifact, load, staged row, and curated provenance. An activity cannot point at a department source row. Project/department and activity/project FKs reject missing curated parents. Activity checks enforce positive units for completed work and zero for planned/cancelled work. The SQL tests exercise these constraints directly.

Two filtered unique indexes on `ops.Load` protect publication identity:

- `(source_id, business_date)` is unique where `is_current = 1`. Reference loads use a NULL business date, giving each reference source one current snapshot.
- `evaluation_key` is unique for rows with a non-NULL `published_at`. Superseding a load retains that timestamp and its successful evaluation identity; failed/no-op attempts do not reserve the key.

A published load must have its artifact, evaluation key, reference hash, contract/rule versions, and completion timestamps; activity loads also require a business date. No-op attempts link to the reused load. Published input and source-row history cannot be deleted by the runtime role.

These constraints are the database foundation, not a working publication engine. P04 must implement normalization, hash verification, legal state transitions, immutable staged evidence after validation, matching row/date/key values, and atomic replacement of a date's curated rows together with publication state. FKs alone do not establish that a staged row passed validation. P04 must also require NULL business dates for reference snapshots and prevent changing the fixed reference set.

Store the fixture-set ID, manifest, and source capture details in artifact metadata. The evaluation key must incorporate source/date, captured payload **and manifest semantics**, contract/rule versions, and the reference hash; otherwise a corrected manifest could incorrectly reuse a previous evaluation. Keep duplicate raw captures if necessary; identical content does not erase an attempted load. Multi-worker ingestion remains deferred.

## Setup and reruns

From the repository root after generating `.env.workbench` and starting SQL Server:

```powershell
docker compose --env-file .env.workbench --profile tools run --build --rm migrate
docker compose --env-file .env.workbench --profile tools run --rm migrate
docker compose --env-file .env.workbench run --build --rm workbench health
```

The first setup reports `applied: [1, 2, 3]` for an empty database. An unchanged rerun reports `applied: []` and `current_version: 3`. These are expected outputs; CI must verify them against SQL Server. Setup does not seed reference data or load curated records.

The underlying CLI commands are:

| Command | Action | Access |
|---|---|---|
| `db-create` | Create configured user database if absent; never replace it | Administrator |
| `migrate` | Apply pending scripts to an existing database | Schema deployment |
| `db-setup` | Create database, migrate, provision/verify runtime login | Administrator; requires both passwords |
| `health` / `db-smoke` | Read-only connectivity / session-local transaction probe | Runtime |

For direct Python use, supply `--env-file` explicitly and point it at an accessible SQL endpoint. Compose keeps SQL private and pins its application database to `workbench`. `--migration-dir` defaults to `sql/migrations` relative to the working directory. System databases are rejected; database names must start with an ASCII letter and contain only letters, digits, and underscores (maximum 63 characters).

## Migration behavior and recovery

The runner validates a contiguous sequence of `001_description.sql` files before connecting. It checks that recorded versions and filenames form an exact prefix of that sequence. Unknown/newer versions and renamed applied files fail clearly. Checksums and changed-content detection are intentionally deferred: never edit an applied migration; add the next numbered script.

Each file is one T-SQL batch with no `GO`, `USE`, or transaction-control statements. The runner owns the transaction: execute the script, insert its ledger row, then commit. On failure it rolls back both. Earlier successful migrations remain applied, and an unchanged rerun starts at the first unapplied version. Ledger bootstrap is committed separately, so an initial failure can leave an empty ledger. No automatic down-migration or database deletion is provided.

A session-scoped application lock serializes deployment sessions across these commits. This does not implement concurrent ingestion. See Microsoft's [application-lock reference](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-getapplock-transact-sql?view=sql-server-ver17).

On failure, inspect the safe CLI diagnostic and failed migration filename, resolve the cause, and rerun setup. A failed unpublished migration may be corrected before its first successful application. Driver messages are withheld from CLI output to avoid credential disclosure. Setup phases commit independently: a runtime-login provisioning failure can leave a successfully migrated database ready for retry.

## Runtime access

[003_runtime_role.sql](../sql/migrations/003_runtime_role.sql) grants `workbench_runtime` only the initial application permissions: read source and migration history; read/insert artifacts; read/insert/update loads and staging; read/write/delete curated rows; read the reserved report schema. It grants no DDL, source writes, ledger writes, or artifact/history deletion. Later migrations extend permissions as operational tables are introduced.

Compose setup uses `sa`; the application uses the separate `workbench_app` SQL login/user. Setup rejects unexpected principal types, mismatched login/user identities, server-role membership, and unrelated database-role membership. This is a fresh development-instance provisioning path, not a general audit/remediation tool for existing SQL permissions. Successful setup also verifies the runtime password with a real connection. Existing passwords are not silently reset. Keep both credentials for the persistent volume; changing an env-file value does not rotate a stored SQL password.
