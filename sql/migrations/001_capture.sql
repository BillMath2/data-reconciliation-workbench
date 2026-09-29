-- The Python runner owns the transaction and migration ledger.
IF SCHEMA_ID(N'source') IS NULL EXEC(N'CREATE SCHEMA source');
IF SCHEMA_ID(N'ops') IS NULL EXEC(N'CREATE SCHEMA ops');
IF SCHEMA_ID(N'stg') IS NULL EXEC(N'CREATE SCHEMA stg');
IF SCHEMA_ID(N'core') IS NULL EXEC(N'CREATE SCHEMA core');
IF SCHEMA_ID(N'report') IS NULL EXEC(N'CREATE SCHEMA report');

-- Compatible with the P02 source-only bootstrap; never replace existing rows.
IF OBJECT_ID(N'source.Department', N'U') IS NULL
    CREATE TABLE source.Department (
        department_id NVARCHAR(16) NOT NULL PRIMARY KEY,
        department_name NVARCHAR(100) NOT NULL,
        is_active BIT NOT NULL
    );

CREATE TABLE ops.InputArtifact (
    artifact_id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWSEQUENTIALID(),
    source_id VARCHAR(32) NOT NULL,
    content_sha256 CHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
    content VARBINARY(MAX) NOT NULL,
    metadata_json NVARCHAR(MAX) NOT NULL DEFAULT N'{}',
    captured_at DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_InputArtifact PRIMARY KEY (artifact_id),
    CONSTRAINT UQ_InputArtifact_Source UNIQUE (artifact_id, source_id),
    CONSTRAINT CK_InputArtifact_Source CHECK
        (source_id IN ('department-reference', 'project-registry', 'daily-activity')),
    CONSTRAINT CK_InputArtifact_Hash CHECK
        (LEN(content_sha256) = 64 AND content_sha256 NOT LIKE '%[^0-9a-f]%'),
    CONSTRAINT CK_InputArtifact_Metadata CHECK (ISJSON(metadata_json) = 1)
);

CREATE TABLE ops.Load (
    load_id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWSEQUENTIALID(),
    source_id VARCHAR(32) NOT NULL,
    business_date DATE NULL,
    artifact_id UNIQUEIDENTIFIER NULL,
    reference_set_sha256 CHAR(64) COLLATE Latin1_General_100_BIN2 NULL,
    contract_version VARCHAR(16) NULL,
    rule_set_version VARCHAR(16) NULL,
    evaluation_key CHAR(64) COLLATE Latin1_General_100_BIN2 NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'started',
    is_current BIT NOT NULL DEFAULT 0,
    started_at DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    finished_at DATETIME2(3) NULL,
    published_at DATETIME2(3) NULL,
    started_by NVARCHAR(128) NOT NULL,
    failure_code VARCHAR(64) NULL,
    previous_load_id UNIQUEIDENTIFIER NULL,
    reused_load_id UNIQUEIDENTIFIER NULL,
    CONSTRAINT PK_Load PRIMARY KEY (load_id),
    CONSTRAINT UQ_Load_Source UNIQUE (load_id, source_id),
    CONSTRAINT FK_Load_Artifact FOREIGN KEY (artifact_id, source_id)
        REFERENCES ops.InputArtifact (artifact_id, source_id),
    CONSTRAINT FK_Load_Previous FOREIGN KEY (previous_load_id, source_id)
        REFERENCES ops.Load (load_id, source_id),
    CONSTRAINT FK_Load_Reused FOREIGN KEY (reused_load_id, source_id)
        REFERENCES ops.Load (load_id, source_id),
    CONSTRAINT CK_Load_Source CHECK
        (source_id IN ('department-reference', 'project-registry', 'daily-activity')),
    CONSTRAINT CK_Load_Status CHECK (status IN
        ('started', 'captured', 'validated', 'published', 'published_with_exceptions',
         'failed', 'no_op', 'superseded')),
    CONSTRAINT CK_Load_ReferenceHash CHECK (reference_set_sha256 IS NULL OR
        (LEN(reference_set_sha256) = 64 AND reference_set_sha256 NOT LIKE '%[^0-9a-f]%')),
    CONSTRAINT CK_Load_EvaluationKey CHECK (evaluation_key IS NULL OR
        (LEN(evaluation_key) = 64 AND evaluation_key NOT LIKE '%[^0-9a-f]%')),
    CONSTRAINT CK_Load_Current CHECK (is_current = 0 OR
        (status IN ('published', 'published_with_exceptions') AND published_at IS NOT NULL)),
    CONSTRAINT CK_Load_Publication CHECK (published_at IS NULL OR
        (status IN ('published', 'published_with_exceptions', 'superseded') AND
         artifact_id IS NOT NULL AND evaluation_key IS NOT NULL AND
         reference_set_sha256 IS NOT NULL AND contract_version IS NOT NULL AND
         rule_set_version IS NOT NULL AND finished_at IS NOT NULL AND
         (source_id <> 'daily-activity' OR business_date IS NOT NULL))),
    CONSTRAINT CK_Load_PublishedStatus CHECK
        (status NOT IN ('published', 'published_with_exceptions', 'superseded') OR
         published_at IS NOT NULL),
    CONSTRAINT CK_Load_NoOp CHECK (status <> 'no_op' OR reused_load_id IS NOT NULL),
    CONSTRAINT CK_Load_NoSelfReference CHECK
        ((previous_load_id IS NULL OR previous_load_id <> load_id) AND
         (reused_load_id IS NULL OR reused_load_id <> load_id))
);

-- SQL Server treats NULL as a key value: one current reference snapshot per source.
CREATE UNIQUE INDEX UX_Load_Current ON ops.Load (source_id, business_date)
    WHERE is_current = 1;
-- Failed/no-op attempts can repeat a key; a successful evaluation remains unique
-- even after its publication is superseded.
CREATE UNIQUE INDEX UX_Load_PublishedEvaluation ON ops.Load (evaluation_key)
    WHERE evaluation_key IS NOT NULL AND published_at IS NOT NULL;

CREATE TABLE stg.SourceRow (
    load_id UNIQUEIDENTIFIER NOT NULL,
    row_ordinal INT NOT NULL,
    source_id VARCHAR(32) NOT NULL,
    raw_record_json NVARCHAR(MAX) NOT NULL,
    row_sha256 CHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
    disposition VARCHAR(24) NOT NULL DEFAULT 'pending',
    primary_rule_id VARCHAR(64) NULL,
    CONSTRAINT PK_SourceRow PRIMARY KEY (load_id, row_ordinal),
    CONSTRAINT UQ_SourceRow_Source UNIQUE (load_id, row_ordinal, source_id),
    CONSTRAINT FK_SourceRow_Load FOREIGN KEY (load_id, source_id)
        REFERENCES ops.Load (load_id, source_id),
    CONSTRAINT CK_SourceRow_Ordinal CHECK (row_ordinal > 0),
    CONSTRAINT CK_SourceRow_Json CHECK (ISJSON(raw_record_json) = 1),
    CONSTRAINT CK_SourceRow_Hash CHECK
        (LEN(row_sha256) = 64 AND row_sha256 NOT LIKE '%[^0-9a-f]%'),
    CONSTRAINT CK_SourceRow_Disposition CHECK
        (disposition IN ('pending', 'accepted', 'excluded_duplicate', 'excluded_invalid')),
    CONSTRAINT CK_SourceRow_Reason CHECK
        ((disposition IN ('pending', 'accepted') AND primary_rule_id IS NULL) OR
         (disposition IN ('excluded_duplicate', 'excluded_invalid') AND primary_rule_id IS NOT NULL))
);
