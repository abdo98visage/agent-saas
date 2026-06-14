from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog


async def log_audit_event(
    db: AsyncSession,
    user_id: str,
    action: str,
    details: dict = None,
    ip_address: str = None,
):
    """Log an audit event."""
    audit = AuditLog(
        user_id=user_id,
        action=action,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(audit)
