-- P03 CI exposed rejection of legal hyphenated IDs by the original LIKE checks.
-- Keep applied migrations immutable. Remove literal separators before testing
-- an explicit ASCII alphabet, avoiding bracket/range ambiguity in Unicode LIKE.
ALTER TABLE core.Department DROP CONSTRAINT CK_Department_Id;
ALTER TABLE core.Department ADD CONSTRAINT CK_Department_Id CHECK
    (LEN(department_id) > 0 AND DATALENGTH(department_id) = 2 * LEN(department_id)
     AND REPLACE(REPLACE(department_id, N'-', N''), N'_', N'')
         NOT LIKE N'%[^ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789]%');
ALTER TABLE core.Project DROP CONSTRAINT CK_Project_Id;
ALTER TABLE core.Project ADD CONSTRAINT CK_Project_Id CHECK
    (LEN(project_id) > 0 AND DATALENGTH(project_id) = 2 * LEN(project_id)
     AND REPLACE(REPLACE(project_id, N'-', N''), N'_', N'')
         NOT LIKE N'%[^ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789]%');
ALTER TABLE core.Activity DROP CONSTRAINT CK_Activity_Id;
ALTER TABLE core.Activity ADD CONSTRAINT CK_Activity_Id CHECK
    (LEN(activity_id) > 0 AND DATALENGTH(activity_id) = 2 * LEN(activity_id)
     AND REPLACE(REPLACE(activity_id, N'-', N''), N'_', N'')
         NOT LIKE N'%[^ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789]%');
