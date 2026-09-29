-- Synthetic source bootstrap only; operational migrations belong to P03.
-- Execute in a disposable user database. No GO separators; one DB-API batch.
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF DB_NAME() IN ('master', 'model', 'msdb', 'tempdb')
    THROW 51000, 'Use a disposable user database for source fixtures.', 1;
BEGIN TRY
    BEGIN TRANSACTION;
    IF SCHEMA_ID(N'source') IS NULL EXEC(N'CREATE SCHEMA source');
    IF OBJECT_ID(N'source.Department', N'U') IS NULL
        CREATE TABLE source.Department (
            department_id NVARCHAR(16) NOT NULL PRIMARY KEY,
            department_name NVARCHAR(100) NOT NULL,
            is_active BIT NOT NULL
        );
    DECLARE @seed TABLE (
        department_id NVARCHAR(16), department_name NVARCHAR(100), is_active BIT
    );
    INSERT INTO @seed VALUES
    (N'DEPT-01', N'Synthetic Department 1', 1),
    (N'DEPT-02', N'Synthetic Department 2', 1),
    (N'DEPT-03', N'Synthetic Department 3', 1),
    (N'DEPT-04', N'Synthetic Department 4', 1),
    (N'DEPT-05', N'Synthetic Department 5', 1);
    IF EXISTS (
        SELECT department_id, department_name, is_active FROM source.Department
        EXCEPT SELECT department_id, department_name, is_active FROM @seed
    ) THROW 51001, 'Reference data differs; use a fresh demo database.', 1;
    INSERT INTO source.Department (department_id, department_name, is_active)
    SELECT s.department_id, s.department_name, s.is_active FROM @seed AS s
    WHERE NOT EXISTS (
        SELECT 1 FROM source.Department AS d WHERE d.department_id = s.department_id
    );
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
