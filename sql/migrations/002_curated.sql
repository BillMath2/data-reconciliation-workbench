CREATE TABLE core.Department (
    department_id NVARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL,
    department_name NVARCHAR(100) NOT NULL,
    is_active BIT NOT NULL,
    origin_load_id UNIQUEIDENTIFIER NOT NULL,
    origin_row_ordinal INT NOT NULL,
    source_id VARCHAR(32) NOT NULL DEFAULT 'department-reference',
    CONSTRAINT PK_Department PRIMARY KEY (department_id),
    CONSTRAINT CK_Department_Id CHECK
        (LEN(department_id) > 0 AND DATALENGTH(department_id) = 2 * LEN(department_id)
         AND department_id NOT LIKE N'%[^A-Z0-9_-]%'),
    CONSTRAINT CK_Department_Name CHECK (LEN(LTRIM(RTRIM(department_name))) > 0),
    CONSTRAINT CK_Department_Source CHECK (source_id = 'department-reference'),
    CONSTRAINT FK_Department_Row FOREIGN KEY (origin_load_id, origin_row_ordinal, source_id)
        REFERENCES stg.SourceRow (load_id, row_ordinal, source_id)
);

CREATE TABLE core.Project (
    project_id NVARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL,
    project_name NVARCHAR(100) NOT NULL,
    department_id NVARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL,
    project_status VARCHAR(16) NOT NULL,
    updated_at DATETIME2(0) NOT NULL,
    origin_load_id UNIQUEIDENTIFIER NOT NULL,
    origin_row_ordinal INT NOT NULL,
    source_id VARCHAR(32) NOT NULL DEFAULT 'project-registry',
    CONSTRAINT PK_Project PRIMARY KEY (project_id),
    CONSTRAINT CK_Project_Id CHECK
        (LEN(project_id) > 0 AND DATALENGTH(project_id) = 2 * LEN(project_id)
         AND project_id NOT LIKE N'%[^A-Z0-9_-]%'),
    CONSTRAINT CK_Project_Name CHECK (LEN(LTRIM(RTRIM(project_name))) > 0),
    CONSTRAINT CK_Project_Status CHECK (project_status IN ('active', 'paused', 'closed')),
    CONSTRAINT CK_Project_Source CHECK (source_id = 'project-registry'),
    CONSTRAINT FK_Project_Department FOREIGN KEY (department_id)
        REFERENCES core.Department (department_id),
    CONSTRAINT FK_Project_Row FOREIGN KEY (origin_load_id, origin_row_ordinal, source_id)
        REFERENCES stg.SourceRow (load_id, row_ordinal, source_id)
);
CREATE INDEX IX_Project_Department ON core.Project (department_id);

CREATE TABLE core.Activity (
    activity_date DATE NOT NULL,
    activity_id NVARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL,
    project_id NVARCHAR(16) COLLATE Latin1_General_100_BIN2 NOT NULL,
    activity_status VARCHAR(16) NOT NULL,
    completed_units INT NOT NULL,
    source_updated_at DATETIME2(0) NOT NULL,
    origin_load_id UNIQUEIDENTIFIER NOT NULL,
    origin_row_ordinal INT NOT NULL,
    source_id VARCHAR(32) NOT NULL DEFAULT 'daily-activity',
    CONSTRAINT PK_Activity PRIMARY KEY (activity_date, activity_id),
    CONSTRAINT CK_Activity_Id CHECK
        (LEN(activity_id) > 0 AND DATALENGTH(activity_id) = 2 * LEN(activity_id)
         AND activity_id NOT LIKE N'%[^A-Z0-9_-]%'),
    CONSTRAINT CK_Activity_Status CHECK (activity_status IN ('planned', 'completed', 'cancelled')),
    CONSTRAINT CK_Activity_Units CHECK
        ((activity_status = 'completed' AND completed_units > 0) OR
         (activity_status IN ('planned', 'cancelled') AND completed_units = 0)),
    CONSTRAINT CK_Activity_Source CHECK (source_id = 'daily-activity'),
    CONSTRAINT FK_Activity_Project FOREIGN KEY (project_id) REFERENCES core.Project (project_id),
    CONSTRAINT FK_Activity_Row FOREIGN KEY (origin_load_id, origin_row_ordinal, source_id)
        REFERENCES stg.SourceRow (load_id, row_ordinal, source_id)
);
CREATE INDEX IX_Activity_ProjectDate ON core.Activity (project_id, activity_date);
