ALTER TABLE ops.Load ADD attempt_number BIGINT IDENTITY(1,1) NOT NULL;
CREATE INDEX IX_Load_SourceAttempt ON ops.Load (source_id, attempt_number DESC);
ALTER TABLE ops.Load ADD CONSTRAINT CK_Load_ReferenceDate CHECK
    (source_id = 'daily-activity' OR business_date IS NULL);

CREATE TABLE ops.Exception (
    exception_id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWSEQUENTIALID(),
    load_id UNIQUEIDENTIFIER NOT NULL,
    row_ordinal INT NULL,
    rule_id VARCHAR(64) NOT NULL,
    rule_set_version VARCHAR(16) NOT NULL,
    field_name VARCHAR(64) NULL,
    evidence_json NVARCHAR(MAX) NOT NULL,
    created_at DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_Exception PRIMARY KEY (exception_id),
    CONSTRAINT FK_Exception_Load FOREIGN KEY (load_id) REFERENCES ops.Load (load_id),
    CONSTRAINT FK_Exception_Row FOREIGN KEY (load_id, row_ordinal)
        REFERENCES stg.SourceRow (load_id, row_ordinal),
    CONSTRAINT CK_Exception_Evidence CHECK (ISJSON(evidence_json) = 1)
);
CREATE INDEX IX_Exception_Load ON ops.Exception (load_id, row_ordinal);

CREATE TABLE ops.AuditEvent (
    event_id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWSEQUENTIALID(),
    load_id UNIQUEIDENTIFIER NOT NULL,
    actor NVARCHAR(128) NOT NULL,
    action VARCHAR(32) NOT NULL,
    detail_json NVARCHAR(MAX) NOT NULL,
    occurred_at DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_AuditEvent PRIMARY KEY (event_id),
    CONSTRAINT FK_AuditEvent_Load FOREIGN KEY (load_id) REFERENCES ops.Load (load_id),
    CONSTRAINT CK_AuditEvent_Detail CHECK (ISJSON(detail_json) = 1)
);
CREATE INDEX IX_AuditEvent_Load ON ops.AuditEvent (load_id, occurred_at);
GRANT SELECT, INSERT ON ops.Exception TO workbench_runtime;
GRANT SELECT, INSERT ON ops.AuditEvent TO workbench_runtime;
