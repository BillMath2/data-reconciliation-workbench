"""Explicit recovery of abandoned attempts, serialized with ingestion."""

from contextlib import closing, suppress

from workbench.db import connect
from workbench.migrations import execute_batch, validate_database_name
from workbench.pipeline import audit, finding
from workbench.validation import LoadError


def recover(settings, *, apply=False, actor="cli", reason=None):
    """Preview by default. The ingestion lock proves no supported worker is active."""
    validate_database_name(settings.database)
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 128:
        raise LoadError(
            "INVALID_REQUEST", "A nonempty actor of at most 128 characters is required."
        )
    if apply and (
        not isinstance(reason, str) or not reason.strip() or len(reason.encode("utf-16-le")) > 1000
    ):
        raise LoadError(
            "INVALID_REQUEST", "Recovery requires a reason of at most 500 UTF-16 units."
        )
    with closing(connect(settings)) as connection, closing(connection.cursor()) as cursor:
        cursor.execute(
            "DECLARE @r INT; EXEC @r=sys.sp_getapplock "
            "@Resource=N'workbench:ingestion', @LockMode='Exclusive', "
            "@LockOwner='Session', @LockTimeout=0; SELECT @r;"
        )
        lock = cursor.fetchone()[0]
        while cursor.nextset():
            pass
        if lock < 0:
            raise LoadError(
                "WORKER_BUSY", "An ingestion or recovery session is active; retry later."
            )
        try:
            cursor.execute(
                "SELECT load_id, source_id, status, artifact_id FROM ops.Load "
                "WHERE status IN ('started','captured','validated') "
                "AND published_at IS NULL AND is_current=0 ORDER BY attempt_number"
            )
            items = [
                {
                    "load_id": str(r[0]).lower(),
                    "source_id": r[1],
                    "previous_status": r[2],
                    "artifact_retained": r[3] is not None,
                }
                for r in cursor.fetchall()
            ]
            if apply:
                for item in items:
                    cursor.execute(
                        "UPDATE ops.Load SET status='failed', failure_code='LOAD_INTERRUPTED', "
                        "finished_at=SYSUTCDATETIME() WHERE load_id=?",
                        (item["load_id"],),
                    )
                    finding(
                        cursor,
                        item["load_id"],
                        "LOAD_INTERRUPTED",
                        {"message": "Worker ended before a durable publication was recorded."},
                    )
                    audit(
                        cursor,
                        item["load_id"],
                        actor,
                        "load_recovered",
                        {
                            "previous_status": item["previous_status"],
                            "reason": reason.strip(),
                            "code": "LOAD_INTERRUPTED",
                            "action": "marked_failed_for_explicit_retry",
                        },
                    )
                connection.commit()
            else:
                connection.rollback()
            return {
                "status": "ok",
                "check": "recover-loads",
                "applied": apply,
                "count": len(items),
                "items": items,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            with suppress(Exception):
                execute_batch(
                    cursor,
                    "EXEC sys.sp_releaseapplock "
                    "@Resource=N'workbench:ingestion', @LockOwner='Session';",
                )
                connection.commit()
