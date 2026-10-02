CREATE TABLE ops.Investigation (
    investigation_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_Investigation PRIMARY KEY,
    requested_load_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT FK_Investigation_Requested REFERENCES ops.Load(load_id),
    publication_load_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT FK_Investigation_Publication REFERENCES ops.Load(load_id),
    exception_id UNIQUEIDENTIFIER NULL
        CONSTRAINT FK_Investigation_Exception REFERENCES ops.Exception(exception_id),
    created_by NVARCHAR(128) NOT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_Investigation_Created DEFAULT SYSUTCDATETIME(),
    context_sha256 CHAR(64) NOT NULL,
    context_json NVARCHAR(MAX) NOT NULL CONSTRAINT CK_Investigation_Context CHECK (ISJSON(context_json)=1),
    result_json NVARCHAR(MAX) NOT NULL CONSTRAINT CK_Investigation_Result CHECK (ISJSON(result_json)=1)
);
CREATE INDEX IX_Investigation_Load ON ops.Investigation(requested_load_id, created_at, investigation_id);
GRANT SELECT, INSERT ON ops.Investigation TO workbench_runtime;
