# Interrupted loads and backup/restore

P11 supports an explicit operator recovery command and repeatable rehearsals.
Stop the worker you are investigating before applying recovery. The command
also takes the same database/session application lock as ingestion; a live
supported worker causes `WORKER_BUSY`, not a forced unlock or process kill.

## Recover an abandoned attempt

Preview using the restricted runtime login:

```powershell
docker compose --env-file .env.workbench run --rm workbench recover-loads
```

Review the listed load IDs, prior statuses, and whether captured artifacts exist.
Only noncurrent, unpublished attempts in `started`, `captured`, or `validated`
are eligible. Then record an operator reason:

```powershell
docker compose --env-file .env.workbench run --rm workbench recover-loads --apply --actor Bill --reason "Worker stopped; reviewed abandoned attempts"
```

This changes eligible attempts to `failed` with `LOAD_INTERRUPTED`, appends a
finding, and records a `load_recovered` audit event in one transaction. The event
means **attempt recovery**, not successful publication. Captured/staged rows and
previous publications remain intact. Preview does not write anything; repeated
apply is a no-op. A failed audit insert rolls back the recovery operation.

Retry the same source through the usual operator screen or CLI. If the original
transaction did not commit, the retry publishes normally. If it committed before
the client lost the acknowledgement, the recorded evaluation key causes a no-op.
Recovery never relabels a committed publication as failed. Do not edit load states
or remove source/history records manually to force a retry.

An attempt stopped before capture may have no date or artifact; retry from the
original source. Its load-level interruption finding may remain open because
there is insufficient date/reference evidence to attribute a successor. Later
captured attempts can be resolved by the normal verified-successor lifecycle.

## Repeat the crash and restore proof

```powershell
docker compose --env-file .env.workbench --profile test run --build --rm tests -v --run-sql tests/integration/test_recovery.py tests/integration/test_backup_restore.py
```

The worker exits without Python cleanup at six boundaries: started, captured,
validated, after deleting the old partition, before commit, and after commit.
These are test-only hooks, not API or CLI fault switches. The tests verify
transaction rollback, preserved reconciliation packets, audited recovery,
exactly-once publication on retry, and no-op behavior after a committed attempt.
They simulate a lost acknowledgement by process exit after commit; they do not
inject a network failure inside SQL Server's commit protocol.

## Backup and restore rehearsal

The test uses an administrator connection to make a `COPY_ONLY` backup with
`CHECKSUM`, run `RESTORE VERIFYONLY`, and **actually restore** into a generated
`workbench_restore_<uuid>` database with unique `MOVE` destinations. Existing
destinations are refused; `WITH REPLACE` is never used. It runs `DBCC CHECKDB`,
compares counts and content hashes of all twelve application tables, opens a
saved investigation with the restored runtime login, then retries a correction
and verifies a no-op repeat. The source database is checked unchanged.

Only the generated restored database is removed afterward. The unique `.bak`
file is retained under `/var/opt/mssql/data/wb_rehearsal_<uuid>.bak` in the SQL
volume; the evidence JSON records its exact path. CI discards its disposable
volume at job completion. Local test backups remain until explicitly removed.
The successful local backup/restore times describe this small synthetic dataset,
not a production recovery-time objective.

Backup, restore, SHOWPLAN, and schema changes stay on administrator/test connections;
no new server privileges or web recovery route are granted to the application.
This same-instance proof does not establish offsite durability, point-in-time
recovery, login portability to another SQL instance, or a disaster-recovery SLA.

SQL Server releases session application locks when the session ends; see
[application-lock semantics](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-getapplock-transact-sql).
The rehearsal follows Microsoft's [backup/restore copy guidance](https://learn.microsoft.com/en-us/sql/relational-databases/databases/copy-databases-with-backup-and-restore)
and supplements [VERIFYONLY](https://learn.microsoft.com/en-us/sql/t-sql/statements/restore-statements-verifyonly-transact-sql)
with an actual restore and data checks.
