-- P11: narrow, ordered covering access for the default unresolved-finding page.
-- Resolved history remains in the clustered index and IX_Exception_Load.
CREATE INDEX IX_Exception_UnresolvedPage
ON ops.Exception (load_id, row_ordinal, rule_id, exception_id)
INCLUDE (rule_set_version, field_name, created_at, acknowledged_at, acknowledged_by,
         acknowledgement_reason, resolved_at, resolved_by_load_id, resolution_reason)
WHERE resolved_at IS NULL;
