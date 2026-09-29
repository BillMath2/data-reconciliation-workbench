CREATE TABLE ops.ReconciliationResult (
    load_id UNIQUEIDENTIFIER NOT NULL,
    calculation_version VARCHAR(16) NOT NULL,
    raw_rows BIGINT NOT NULL,
    accepted_rows BIGINT NOT NULL,
    excluded_duplicate_rows BIGINT NOT NULL,
    excluded_invalid_rows BIGINT NOT NULL,
    source_completed_count BIGINT NOT NULL,
    curated_completed_count BIGINT NOT NULL,
    source_completed_units BIGINT NULL,
    curated_completed_units BIGINT NOT NULL,
    summary_json NVARCHAR(MAX) NOT NULL,
    evidence_json NVARCHAR(MAX) NOT NULL,
    recorded_at DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_ReconciliationResult PRIMARY KEY (load_id),
    CONSTRAINT FK_ReconciliationResult_Load FOREIGN KEY (load_id) REFERENCES ops.Load (load_id),
    CONSTRAINT CK_ReconciliationResult_Accounting CHECK
        (raw_rows = accepted_rows + excluded_duplicate_rows + excluded_invalid_rows
         AND accepted_rows >= 0 AND excluded_duplicate_rows >= 0 AND excluded_invalid_rows >= 0
         AND source_completed_count >= curated_completed_count AND curated_completed_count >= 0
         AND curated_completed_units >= 0
         AND (source_completed_units IS NULL OR source_completed_units >= curated_completed_units)),
    CONSTRAINT CK_ReconciliationResult_Json CHECK
        (ISJSON(summary_json)=1 AND ISJSON(evidence_json)=1)
);
GRANT SELECT, INSERT ON ops.ReconciliationResult TO workbench_runtime;
-- Dynamic batches allow CREATE VIEW while the migration runner owns the transaction.
EXEC(N'CREATE VIEW report.vw_LoadReconciliation AS
    SELECT l.load_id, l.business_date, l.status, l.is_current, l.reference_set_sha256,
           r.calculation_version, r.raw_rows, r.accepted_rows,
           r.excluded_duplicate_rows, r.excluded_invalid_rows,
           r.source_completed_count, r.curated_completed_count,
           r.source_completed_units, r.curated_completed_units,
           r.source_completed_count - r.curated_completed_count AS completed_count_difference,
           r.source_completed_units - r.curated_completed_units AS completed_unit_difference
    FROM ops.Load l JOIN ops.ReconciliationResult r ON r.load_id=l.load_id
    WHERE l.published_at IS NOT NULL;');
EXEC(N'CREATE VIEW report.vw_ProjectActivity AS
    SELECT a.activity_date, a.project_id, p.project_name, p.department_id,
           a.origin_load_id AS load_id, COUNT_BIG(*) AS activity_count,
           SUM(CASE WHEN a.activity_status=''completed'' THEN CAST(1 AS BIGINT) ELSE 0 END)
               AS completed_count,
           SUM(CAST(a.completed_units AS BIGINT)) AS completed_units
    FROM core.Activity a
    JOIN core.Project p ON p.project_id=a.project_id
    JOIN ops.Load l ON l.load_id=a.origin_load_id AND l.is_current=1
    GROUP BY a.activity_date, a.project_id, p.project_name, p.department_id, a.origin_load_id;');
