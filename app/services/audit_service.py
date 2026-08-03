"""Structured audit events and reliable checkpointed SIEM export."""
from datetime import datetime
from uuid import UUID

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_log import AuditExportCheckpoint, AuditLog, redact_audit_details


async def log_audit_event(
    db: AsyncSession,
    user_id: str | UUID | None,
    action: str,
    details: dict | None = None,
    ip_address: str | None = None,
    *,
    event_category: str | None = None,
    actor_type: str = "user",
    subject_type: str | None = None,
    subject_id: str | None = None,
    run_id: UUID | None = None,
    task_id: UUID | None = None,
    session_id: UUID | None = None,
    policy_id: str | None = None,
    reason: str | None = None,
) -> AuditLog:
    audit = AuditLog(
        user_id=user_id,
        action=action,
        details=redact_audit_details(details or {}),
        ip_address=ip_address,
        event_category=event_category,
        actor_type=actor_type,
        subject_type=subject_type,
        subject_id=subject_id,
        run_id=run_id,
        task_id=task_id,
        session_id=session_id,
        policy_id=policy_id,
        reason=reason,
    )
    db.add(audit)
    return audit


def _json_value(value):
    if isinstance(value, (datetime, UUID)):
        return str(value)
    return value


def serialize_audit_event(event: AuditLog) -> dict:
    return {
        column.name: _json_value(getattr(event, column.name))
        for column in AuditLog.__table__.columns
    }


async def verify_audit_chain(db: AsyncSession) -> bool:
    return bool((await db.execute(text("SELECT verify_audit_log_chain()"))).scalar_one())


async def export_audit_batch(db: AsyncSession) -> dict:
    """Send the next immutable audit batch and advance the checkpoint only on success."""
    if not settings.audit_export_url:
        return {"status": "disabled", "exported": 0}

    result = await db.execute(
        select(AuditExportCheckpoint)
        .where(AuditExportCheckpoint.destination == settings.audit_export_url)
        .with_for_update()
    )
    checkpoint = result.scalar_one_or_none()
    if checkpoint is None:
        checkpoint = AuditExportCheckpoint(destination=settings.audit_export_url)
        db.add(checkpoint)
        await db.flush()

    events_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.id > checkpoint.last_audit_id)
        .order_by(AuditLog.id)
        .limit(settings.audit_export_batch_size)
    )
    events = list(events_result.scalars())
    if not events:
        return {"status": "current", "exported": 0, "checkpoint": checkpoint.last_audit_id}

    headers = {"Content-Type": "application/json"}
    if settings.audit_export_token:
        headers["Authorization"] = f"Bearer {settings.audit_export_token}"
    try:
        async with httpx.AsyncClient(timeout=settings.audit_export_timeout_seconds) as client:
            response = await client.post(
                settings.audit_export_url,
                json={"schema": "fqsaas.audit.v1", "events": [serialize_audit_event(event) for event in events]},
                headers=headers,
            )
            response.raise_for_status()
    except Exception as exc:
        checkpoint.failure_count += 1
        checkpoint.last_error = str(exc)[:1000]
        await db.commit()
        raise

    checkpoint.last_audit_id = events[-1].id
    checkpoint.failure_count = 0
    checkpoint.last_error = None
    await db.commit()
    return {"status": "exported", "exported": len(events), "checkpoint": checkpoint.last_audit_id}
