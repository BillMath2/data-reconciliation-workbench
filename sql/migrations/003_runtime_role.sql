CREATE ROLE workbench_runtime AUTHORIZATION dbo;
GRANT SELECT ON SCHEMA::source TO workbench_runtime;
GRANT SELECT ON meta.SchemaMigration TO workbench_runtime;
GRANT SELECT, INSERT ON ops.InputArtifact TO workbench_runtime;
GRANT SELECT, INSERT, UPDATE ON ops.Load TO workbench_runtime;
GRANT SELECT, INSERT, UPDATE ON stg.SourceRow TO workbench_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::core TO workbench_runtime;
GRANT SELECT ON SCHEMA::report TO workbench_runtime;
-- No schema changes, migration-ledger writes, source writes, or history deletion.
-- P04/P06/P08 extend grants only when their operational tables are introduced.
