# Data dictionary and field ownership

Catalog verified against the P12 fresh SQL database: **12 tables, 3 views, 9 migrations**.
The [retained catalog](evidence/p12/schema.json) contains types, nullability, identity,
foreign keys, and index definitions. [Schema diagram](database-schema.md) describes
relationships; [versioned field ownership](../config/field-ownership.json) and
[source contracts](source-contracts.md) define normalization and authority.

## Ownership and accounting

| Authority | Owned business fields | Relationship rule |
|---|---|---|
| SQL department source | department_id, department_name, is_active | Registry cannot overwrite department identity/name/state |
| Project registry API | project_id, project_name, department_id, project_status, updated_at | department_id is the project's assignment |
| Activity CSV | activity_id, project_id, activity_date, activity_status, completed_units, source_updated_at | project_id is the activity's assignment |
| Workbench | capture IDs/hashes, attempts, provenance, dispositions, findings, reconciliation, lifecycle, audit, investigations | Derived evidence does not repair the authoritative source |

There is no last-writer-wins merging. IDs normalize to uppercase ASCII (16-character
maximum), names retain Unicode, and source timestamps must be UTC. Operational
timestamps use UTC; business dates are calendar dates. `completed_units` means
synthetic integer work units, not money or elapsed time. NULL source units mean
unknown, never zero. Multiple findings on one row count as one primary exclusion:
`raw_rows = accepted_rows + excluded_duplicate_rows + excluded_invalid_rows`.
Source completed counts include excluded rows; curated counts include accepted rows.

SQL reports view expressions conservatively nullable in some cases; the tables
below preserve catalog nullability rather than inferring stricter API guarantees.
`nvarchar(n)` lengths are UTF-16 code units; `varchar/varbinary` lengths are bytes.

## Object and field definitions

### `core.Activity`

One current activity per `(activity_date, activity_id)`. Source owns business values; ingestion supplies provenance.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `activity_date` | `date` | No | Activity business date; date replacement partition. |
| `activity_id` | `nvarchar(16)` | No | Activity business identifier; unique within its business date. |
| `project_id` | `nvarchar(16)` | No | Project identity in registry; activity source owns its project assignment. |
| `activity_status` | `varchar(16)` | No | Normalized planned, completed, or cancelled state. |
| `completed_units` | `int` | No | Source-declared integer work units; positive for completed, zero otherwise. View sums accepted units. |
| `source_updated_at` | `datetime2(0)` | No | Source-supplied UTC timestamp; not the ingestion time. |
| `origin_load_id` | `uniqueidentifier` | No | Accepted originating load; part of the composite staged-row provenance FK. |
| `origin_row_ordinal` | `int` | No | One-based captured row position; part of staged-row provenance FK. |
| `source_id` | `varchar(32)` | No | Versioned source identifier (department-reference, project-registry, daily-activity). |

### `core.Department`

One accepted department per `department_id`; SQL department source owns business values.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `department_id` | `nvarchar(16)` | No | Department identity in SQL source; registry owns each project assignment. |
| `department_name` | `nvarchar(100)` | No | Authoritative Unicode department display name from the SQL source. |
| `is_active` | `bit` | No | Authoritative department active flag from the SQL source. |
| `origin_load_id` | `uniqueidentifier` | No | Accepted originating load; part of the composite staged-row provenance FK. |
| `origin_row_ordinal` | `int` | No | One-based captured row position; part of staged-row provenance FK. |
| `source_id` | `varchar(32)` | No | Versioned source identifier (department-reference, project-registry, daily-activity). |

### `core.Project`

One accepted project per `project_id`; project registry owns business values.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `project_id` | `nvarchar(16)` | No | Project identity in registry; activity source owns its project assignment. |
| `project_name` | `nvarchar(100)` | No | Authoritative Unicode project display name from the registry. |
| `department_id` | `nvarchar(16)` | No | Department identity in SQL source; registry owns each project assignment. |
| `project_status` | `varchar(16)` | No | Registry-owned normalized project state (active, paused, closed). |
| `updated_at` | `datetime2(0)` | No | Registry-supplied UTC update time. |
| `origin_load_id` | `uniqueidentifier` | No | Accepted originating load; part of the composite staged-row provenance FK. |
| `origin_row_ordinal` | `int` | No | One-based captured row position; part of staged-row provenance FK. |
| `source_id` | `varchar(32)` | No | Versioned source identifier (department-reference, project-registry, daily-activity). |

### `meta.SchemaMigration`

One applied migration per `version`; deployment runner owns all fields.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `version` | `int` | No | Applied numbered migration version. |
| `name` | `nvarchar(128)` | No | Applied migration filename; runner validates the contiguous sequence. |
| `applied_at` | `datetime2(3)` | No | UTC deployment timestamp. |
| `applied_by` | `sysname` | No | SQL original login that applied the migration. |

### `ops.AuditEvent`

One event per `event_id`; application writes append-only history.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `event_id` | `uniqueidentifier` | No | Unique append-only audit event identifier. |
| `load_id` | `uniqueidentifier` | No | Associated attempt/publication identifier; view semantics are specified below. |
| `actor` | `nvarchar(128)` | No | Recorded application/CLI actor responsible for the event. |
| `action` | `varchar(32)` | No | Machine-readable event type, such as publication or recovery. |
| `detail_json` | `nvarchar(max)` | No | Structured event details, including applicable reasons and outcomes. |
| `occurred_at` | `datetime2(3)` | No | UTC audit event timestamp. |

### `ops.Exception`

One finding per `exception_id`. Validation owns immutable evidence; operator acknowledgement and verified successor resolution own lifecycle fields.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `exception_id` | `uniqueidentifier` | No | Unique finding identifier; investigation NULL means publication-wide scope. |
| `load_id` | `uniqueidentifier` | No | Associated attempt/publication identifier; view semantics are specified below. |
| `row_ordinal` | `int` | Yes | One-based staged-row ordinal; NULL for a whole-load finding. |
| `rule_id` | `varchar(64)` | No | Deterministic rule that produced the finding. |
| `rule_set_version` | `varchar(16)` | No | Version of rules used for the recorded evaluation. |
| `field_name` | `varchar(64)` | Yes | Affected field, or NULL for row/load-level findings. |
| `evidence_json` | `nvarchar(max)` | No | Frozen structured evidence. Finding evidence and reconciliation packets have distinct versioned shapes. |
| `created_at` | `datetime2(3)` | No | UTC artifact/finding creation timestamp. |
| `acknowledged_at` | `datetime2(3)` | Yes | UTC review timestamp; NULL means not acknowledged. |
| `acknowledged_by` | `nvarchar(128)` | Yes | Reviewer identity; populated with acknowledgement time and reason. |
| `acknowledgement_reason` | `nvarchar(500)` | Yes | Operator-supplied review reason; does not mean correction. |
| `resolved_at` | `datetime2(3)` | Yes | UTC verified resolution timestamp; NULL means unresolved. |
| `resolved_by_load_id` | `uniqueidentifier` | Yes | Successful successor load proving resolution; never the original load. |
| `resolution_reason` | `varchar(32)` | Yes | Verified key_valid, key_removed, or load_recovered outcome. |

### `ops.InputArtifact`

One capture per `artifact_id`; capture service owns bytes and metadata. Repeated captures may have the same content hash.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `artifact_id` | `uniqueidentifier` | No | Unique captured artifact ID; NULL on a load that failed before capture. |
| `source_id` | `varchar(32)` | No | Versioned source identifier (department-reference, project-registry, daily-activity). |
| `content_sha256` | `char(64)` | No | SHA-256 of captured raw bytes; distinct from the evaluation identity. |
| `content` | `varbinary(max)` | No | Exact captured input bytes; immutable through the runtime role. |
| `metadata_json` | `nvarchar(max)` | No | Capture provenance, manifest, fixture identity, and source metadata. |
| `captured_at` | `datetime2(3)` | No | UTC input capture timestamp. |

### `ops.Investigation`

One saved explanation per `investigation_id`; investigation service owns immutable context and result.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `investigation_id` | `uniqueidentifier` | No | Unique immutable investigation artifact identifier. |
| `requested_load_id` | `uniqueidentifier` | No | Attempt selected by the user, including a possible no-op. |
| `publication_load_id` | `uniqueidentifier` | No | Saved publication supplying facts; may differ from requested no-op attempt. |
| `exception_id` | `uniqueidentifier` | Yes | Unique finding identifier; investigation NULL means publication-wide scope. |
| `created_by` | `nvarchar(128)` | No | Authenticated actor who saved the investigation. |
| `created_at` | `datetime2(3)` | No | UTC artifact/finding creation timestamp. |
| `context_sha256` | `char(64)` | No | SHA-256 of the canonical frozen investigation context. |
| `context_json` | `nvarchar(max)` | No | Frozen packet, observations, finding, related records, and selected versioned runbooks. |
| `result_json` | `nvarchar(max)` | No | Saved deterministic facts, explanation mode, checked notes/citations, and provider outcome. |

### `ops.Load`

One attempt per `load_id`; ingestion owns state/provenance, including distinct failed and no-op attempts.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `load_id` | `uniqueidentifier` | No | Associated attempt/publication identifier; view semantics are specified below. |
| `source_id` | `varchar(32)` | No | Versioned source identifier (department-reference, project-registry, daily-activity). |
| `business_date` | `date` | Yes | Activity partition date; reference loads and some capture failures have NULL. |
| `artifact_id` | `uniqueidentifier` | Yes | Unique captured artifact ID; NULL on a load that failed before capture. |
| `reference_set_sha256` | `char(64)` | Yes | Fixed reference fixture-set identity used for validation. |
| `contract_version` | `varchar(16)` | Yes | Source contract version used for this attempt. |
| `rule_set_version` | `varchar(16)` | Yes | Version of rules used for the recorded evaluation. |
| `evaluation_key` | `char(64)` | Yes | Hash of input/manifest semantics, source/date, references, and contract/rule versions. |
| `status` | `varchar(32)` | No | Attempt processing state; the open-findings view instead derives open or acknowledged. |
| `is_current` | `bit` | No | Whether this load is the current publication for its source/date. |
| `started_at` | `datetime2(3)` | No | UTC attempt start time. |
| `finished_at` | `datetime2(3)` | Yes | UTC terminal attempt time; NULL while unfinished. |
| `published_at` | `datetime2(3)` | Yes | UTC successful publication time; retained after supersession; NULL for failed/no-op attempts. |
| `started_by` | `nvarchar(128)` | No | Recorded initiating actor. |
| `failure_code` | `varchar(64)` | Yes | Safe machine-readable failure reason; NULL when absent. |
| `previous_load_id` | `uniqueidentifier` | Yes | Prior publication displaced by this successful replacement, when any. |
| `reused_load_id` | `uniqueidentifier` | Yes | Existing successful publication reused by a no-op attempt. |
| `attempt_number` | `bigint IDENTITY` | No | Identity sequence providing stable attempt order without timestamp ties. |

### `ops.ReconciliationResult`

One frozen result per successful activity `load_id`; reconciliation code owns all measures. Historical results are not recomputed from current facts.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `load_id` | `uniqueidentifier` | No | Associated attempt/publication identifier; view semantics are specified below. |
| `calculation_version` | `varchar(16)` | No | Version of deterministic reconciliation accounting. |
| `raw_rows` | `bigint` | No | All captured data rows, excluding header. |
| `accepted_rows` | `bigint` | No | Rows accepted for this publication, counted once. |
| `excluded_duplicate_rows` | `bigint` | No | Rows excluded under the primary duplicate disposition. |
| `excluded_invalid_rows` | `bigint` | No | Rows excluded under the primary invalid disposition. |
| `source_completed_count` | `bigint` | No | Captured rows declaring completed, including excluded records. |
| `curated_completed_count` | `bigint` | No | Accepted completed rows at this publication. |
| `source_completed_units` | `bigint` | Yes | Sum declared by completed source rows; NULL when any required value is uncomputable. |
| `curated_completed_units` | `bigint` | No | Sum of accepted completed units at publication. |
| `summary_json` | `nvarchar(max)` | No | Frozen accounting summary with primary exclusion reasons and completeness. |
| `evidence_json` | `nvarchar(max)` | No | Frozen structured evidence. Finding evidence and reconciliation packets have distinct versioned shapes. |
| `recorded_at` | `datetime2(3)` | No | UTC time reconciliation was persisted. |

### `report.vw_LoadReconciliation`

One saved successful activity publication per `load_id`, current or superseded; joins Load and ReconciliationResult.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `load_id` | `uniqueidentifier` | No | Associated attempt/publication identifier; view semantics are specified below. |
| `business_date` | `date` | Yes | Activity partition date; reference loads and some capture failures have NULL. |
| `status` | `varchar(32)` | No | Attempt processing state; the open-findings view instead derives open or acknowledged. |
| `is_current` | `bit` | No | Whether this load is the current publication for its source/date. |
| `reference_set_sha256` | `char(64)` | Yes | Fixed reference fixture-set identity used for validation. |
| `calculation_version` | `varchar(16)` | No | Version of deterministic reconciliation accounting. |
| `raw_rows` | `bigint` | No | All captured data rows, excluding header. |
| `accepted_rows` | `bigint` | No | Rows accepted for this publication, counted once. |
| `excluded_duplicate_rows` | `bigint` | No | Rows excluded under the primary duplicate disposition. |
| `excluded_invalid_rows` | `bigint` | No | Rows excluded under the primary invalid disposition. |
| `source_completed_count` | `bigint` | No | Captured rows declaring completed, including excluded records. |
| `curated_completed_count` | `bigint` | No | Accepted completed rows at this publication. |
| `source_completed_units` | `bigint` | Yes | Sum declared by completed source rows; NULL when any required value is uncomputable. |
| `curated_completed_units` | `bigint` | No | Sum of accepted completed units at publication. |
| `completed_count_difference` | `bigint` | Yes | Source completed count minus curated completed count. |
| `completed_unit_difference` | `bigint` | Yes | Source minus curated units; NULL propagates unknown source totals. |

### `report.vw_OpenExceptions`

One unresolved finding per `exception_id`, including acknowledged findings. Derived `status` is open or acknowledged.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `exception_id` | `uniqueidentifier` | No | Unique finding identifier; investigation NULL means publication-wide scope. |
| `load_id` | `uniqueidentifier` | No | Associated attempt/publication identifier; view semantics are specified below. |
| `source_id` | `varchar(32)` | No | Versioned source identifier (department-reference, project-registry, daily-activity). |
| `business_date` | `date` | Yes | Activity partition date; reference loads and some capture failures have NULL. |
| `row_ordinal` | `int` | Yes | One-based staged-row ordinal; NULL for a whole-load finding. |
| `rule_id` | `varchar(64)` | No | Deterministic rule that produced the finding. |
| `rule_set_version` | `varchar(16)` | No | Version of rules used for the recorded evaluation. |
| `field_name` | `varchar(64)` | Yes | Affected field, or NULL for row/load-level findings. |
| `created_at` | `datetime2(3)` | No | UTC artifact/finding creation timestamp. |
| `acknowledged_at` | `datetime2(3)` | Yes | UTC review timestamp; NULL means not acknowledged. |
| `acknowledged_by` | `nvarchar(128)` | Yes | Reviewer identity; populated with acknowledgement time and reason. |
| `acknowledgement_reason` | `nvarchar(500)` | Yes | Operator-supplied review reason; does not mean correction. |
| `status` | `varchar(12)` | No | Attempt processing state; the open-findings view instead derives open or acknowledged. |

### `report.vw_ProjectActivity`

Current accepted facts grouped by activity date, project, project name, department, and publication load. Computed by SQL; not historical accounting.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `activity_date` | `date` | No | Activity business date; date replacement partition. |
| `project_id` | `nvarchar(16)` | No | Project identity in registry; activity source owns its project assignment. |
| `project_name` | `nvarchar(100)` | No | Authoritative Unicode project display name from the registry. |
| `department_id` | `nvarchar(16)` | No | Department identity in SQL source; registry owns each project assignment. |
| `load_id` | `uniqueidentifier` | No | Associated attempt/publication identifier; view semantics are specified below. |
| `activity_count` | `bigint` | Yes | All current accepted activities in the project/date/publication group. |
| `completed_count` | `bigint` | Yes | Current accepted completed activities in the project/date/publication group. |
| `completed_units` | `bigint` | Yes | Source-declared integer work units; positive for completed, zero otherwise. View sums accepted units. |

### `source.Department`

One authoritative synthetic SQL record per `department_id`; seed/input owner, read-only to runtime.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `department_id` | `nvarchar(16)` | No | Department identity in SQL source; registry owns each project assignment. |
| `department_name` | `nvarchar(100)` | No | Authoritative Unicode department display name from the SQL source. |
| `is_active` | `bit` | No | Authoritative department active flag from the SQL source. |

### `stg.SourceRow`

One captured row per `(load_id, row_ordinal)`; capture owns raw evidence, validation owns disposition.

| Field | SQL type | Nullable | Meaning |
|---|---|---|---|
| `load_id` | `uniqueidentifier` | No | Associated attempt/publication identifier; view semantics are specified below. |
| `row_ordinal` | `int` | No | One-based staged-row ordinal; NULL for a whole-load finding. |
| `source_id` | `varchar(32)` | No | Versioned source identifier (department-reference, project-registry, daily-activity). |
| `raw_record_json` | `nvarchar(max)` | No | Captured row envelope before normalization; retained for evidence. |
| `row_sha256` | `char(64)` | No | Hash identifying the captured row representation. |
| `disposition` | `varchar(24)` | No | Pending before validation; then one primary accounting result: accepted, excluded_duplicate, or excluded_invalid. |
| `primary_rule_id` | `varchar(64)` | Yes | Rule assigned the primary exclusion disposition, NULL when accepted. |
