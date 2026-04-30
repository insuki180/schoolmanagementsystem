"""Audit logging helpers."""

from app.models.audit_log import AuditLog


async def create_log(
    db,
    action,
    performed_by,
    target_user=None,
    school_id=None,
    class_id=None,
    role=None,
):
    """Create an audit log entry inside the current request transaction."""
    log = AuditLog(
        action=action,
        performed_by=performed_by,
        target_user=target_user,
        school_id=school_id,
        class_id=class_id,
        role=role,
    )
    db.add(log)
    await db.flush()
    return log
