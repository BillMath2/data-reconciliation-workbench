-- Query-only, set-based synthetic fixture. This is not an ingestion throughput test.
-- The caller supplies two fresh load IDs: a historical attempt and its successor.
DECLARE @old UNIQUEIDENTIFIER=?, @current UNIQUEIDENTIFIER=?;
DECLARE @artifact UNIQUEIDENTIFIER=NEWID();
INSERT ops.InputArtifact(artifact_id,source_id,content_sha256,content,metadata_json)
VALUES(@artifact,'daily-activity',LOWER(CONVERT(VARCHAR(64),HASHBYTES('SHA2_256','P11 relational fixture'),2)),
       CONVERT(VARBINARY(MAX),'P11 relational fixture'),N'{"synthetic_query_benchmark_only":true}');
INSERT ops.Load(load_id,source_id,business_date,artifact_id,status,started_by)
VALUES(@old,'daily-activity','2026-09-25',@artifact,'failed','performance-fixture'),
      (@current,'daily-activity','2026-09-25',@artifact,'validated','performance-fixture');
WITH digit(n) AS (SELECT n FROM (VALUES(0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) v(n))
SELECT 1+a.n+10*b.n+100*c.n+1000*d.n+10000*e.n AS n
INTO #numbers FROM digit a CROSS JOIN digit b CROSS JOIN digit c CROSS JOIN digit d CROSS JOIN digit e;
SELECT n, (
    SELECT CONCAT('PERF-',RIGHT(CONCAT('000000',n),6)) AS activity_id,
           'PRJ-001' AS project_id,'2026-09-25' AS activity_date,
           'completed' AS activity_status,'1' AS completed_units,
           '2026-09-25T23:00:00Z' AS source_updated_at
    FOR JSON PATH, WITHOUT_ARRAY_WRAPPER
) AS raw INTO #raw FROM #numbers;
INSERT stg.SourceRow(load_id,row_ordinal,source_id,raw_record_json,row_sha256,disposition,primary_rule_id)
SELECT l.load_id,r.n,'daily-activity',r.raw,
       LOWER(CONVERT(VARCHAR(64),HASHBYTES('SHA2_256',CONVERT(VARCHAR(MAX),r.raw)),2)),
       CASE WHEN l.load_id=@current THEN 'accepted' ELSE 'excluded_invalid' END,
       CASE WHEN l.load_id=@current THEN NULL ELSE 'ROW_REQUIRED' END
FROM #raw r CROSS JOIN (VALUES(@old),(@current)) l(load_id);
INSERT core.Activity(activity_date,activity_id,project_id,activity_status,completed_units,
                     source_updated_at,origin_load_id,origin_row_ordinal)
SELECT '2026-09-25',CONCAT('PERF-',RIGHT(CONCAT('000000',n),6)),'PRJ-001','completed',1,
       '2026-09-25T23:00:00',@current,n FROM #numbers;
INSERT ops.Exception(load_id,row_ordinal,rule_id,rule_set_version,field_name,evidence_json,
                     resolved_at,resolved_by_load_id,resolution_reason)
SELECT @old,n,'ROW_REQUIRED','1.0.0','project_id',N'{"synthetic_query_fixture":true}',
       CASE WHEN n<=99900 THEN SYSUTCDATETIME() ELSE NULL END,
       CASE WHEN n<=99900 THEN @current ELSE NULL END,
       CASE WHEN n<=99900 THEN 'key_valid' ELSE NULL END FROM #numbers;
DROP TABLE #raw;
DROP TABLE #numbers;
