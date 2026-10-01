-- Original finding evidence stays immutable; only lifecycle columns are writable.
ALTER TABLE ops.Exception ADD
    acknowledged_at DATETIME2(3) NULL,
    acknowledged_by NVARCHAR(128) NULL,
    acknowledgement_reason NVARCHAR(500) NULL,
    resolved_at DATETIME2(3) NULL,
    resolved_by_load_id UNIQUEIDENTIFIER NULL,
    resolution_reason VARCHAR(32) NULL;
ALTER TABLE ops.Exception ADD
    CONSTRAINT FK_Exception_ResolutionLoad FOREIGN KEY (resolved_by_load_id)
        REFERENCES ops.Load (load_id),
    CONSTRAINT CK_Exception_Acknowledgement CHECK (
        (acknowledged_at IS NULL AND acknowledged_by IS NULL AND acknowledgement_reason IS NULL)
        OR (acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL
            AND acknowledgement_reason IS NOT NULL
            AND LEN(LTRIM(RTRIM(acknowledged_by))) > 0
            AND LEN(LTRIM(RTRIM(acknowledgement_reason))) > 0)),
    CONSTRAINT CK_Exception_Resolution CHECK (
        (resolved_at IS NULL AND resolved_by_load_id IS NULL AND resolution_reason IS NULL)
        OR (resolved_at IS NOT NULL AND resolved_by_load_id IS NOT NULL
            AND resolved_by_load_id <> load_id AND resolution_reason IS NOT NULL
            AND resolution_reason IN ('key_valid', 'key_removed', 'load_recovered')));
GRANT UPDATE (acknowledged_at, acknowledged_by, acknowledgement_reason,
    resolved_at, resolved_by_load_id, resolution_reason)
    ON OBJECT::ops.Exception TO workbench_runtime;
EXEC(N'CREATE VIEW report.vw_OpenExceptions AS
    SELECT e.exception_id, e.load_id, l.source_id, l.business_date, e.row_ordinal,
           e.rule_id, e.rule_set_version, e.field_name, e.created_at,
           e.acknowledged_at, e.acknowledged_by, e.acknowledgement_reason,
           CASE WHEN e.acknowledged_at IS NULL THEN ''open'' ELSE ''acknowledged'' END AS status
    FROM ops.Exception e JOIN ops.Load l ON l.load_id=e.load_id
    WHERE e.resolved_at IS NULL;');
