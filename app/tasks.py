"""
Celery tasks for async and scheduled jobs.
"""
import datetime
import sys
from uuid import UUID

# Windows psycopg3 compatibility
if sys.platform == "win32":
    import asyncio
    policy_cls = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if policy_cls is not None:
        asyncio.set_event_loop_policy(policy_cls())

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.core.config import settings
from app.models.user_api_key import UserApiKey
from app.models.session import Session
from app.models.message import Message
from app.models.agent_run import AgentRun
from app.services.alert_service import alert_service


def _run_worker_async(awaitable):
    """Run async task code on a fresh loop and release pooled connections before it closes."""
    import asyncio
    from app.core.db import engine

    async def runner():
        try:
            return await awaitable
        finally:
            await engine.dispose()

    return asyncio.run(runner())


@celery_app.task(bind=True, acks_late=True, reject_on_worker_lost=True, name="app.tasks.run_durable_agent_task")
def run_durable_agent_task(self, task_id: str):
    """Execute one durable task under a database-backed worker lease."""
    from app.services.durable_task_service import execute_durable_task

    return _run_worker_async(execute_durable_task(UUID(task_id), str(self.request.id)))


@celery_app.task(name="app.tasks.enqueue_due_agent_tasks")
def enqueue_due_agent_tasks():
    """Materialize due schedules exactly once and enqueue their durable tasks."""
    from app.services.durable_task_service import enqueue_due_schedules

    task_ids = _run_worker_async(enqueue_due_schedules())
    for task_id in task_ids:
        run_durable_agent_task.delay(task_id)
    return {"enqueued": len(task_ids), "task_ids": task_ids}


@celery_app.task(name="app.tasks.recover_stale_durable_tasks")
def recover_stale_durable_tasks():
    """Recover tasks abandoned after a worker crash without replaying unsafe effects."""
    from app.services.durable_task_service import recover_stale_tasks

    result = _run_worker_async(recover_stale_tasks())
    for task_id in result.pop("task_ids", []):
        run_durable_agent_task.delay(task_id)
    return result


@celery_app.task(bind=True, max_retries=8, name="app.tasks.export_audit_events")
def export_audit_events(self):
    """Export immutable audit events with an exponential retry and durable checkpoint."""
    from app.services.audit_service import export_audit_batch

    try:
        return _run_worker_async(_export_audit_with_session(export_audit_batch))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(900, 15 * (2 ** self.request.retries)))


async def _export_audit_with_session(exporter):
    from app.core.db import async_session

    async with async_session() as session:
        return await exporter(session)


@celery_app.task(bind=True, max_retries=5, name="app.tasks.sync_knowledge_source")
def sync_knowledge_source(self, source_id: str):
    """Incrementally synchronize one administrator-approved local knowledge source."""
    try:
        return _run_worker_async(_sync_knowledge_source(UUID(source_id)))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(900, 30 * (2 ** self.request.retries)))


async def _sync_knowledge_source(source_id: UUID):
    from app.core.db import async_session
    from app.models.knowledge import KnowledgeSource
    from app.services.knowledge_service import sync_local_source

    async with async_session.begin() as db:
        source = await db.get(KnowledgeSource, source_id)
        if not source or not source.is_active:
            return {"status": "not_available"}
        source.sync_status = "syncing"
    try:
        async with async_session.begin() as db:
            source = await db.get(KnowledgeSource, source_id)
            return await sync_local_source(db, source)
    except Exception as exc:
        async with async_session.begin() as db:
            source = await db.get(KnowledgeSource, source_id)
            if source:
                source.sync_status = "failed"
                source.sync_error = str(exc)[:1000]
        raise


@celery_app.task(name="app.tasks.sync_all_knowledge_sources")
def sync_all_knowledge_sources():
    """Queue all active local sources; individual jobs remain independently retryable."""
    source_ids = _run_worker_async(_active_local_knowledge_source_ids())
    for source_id in source_ids:
        sync_knowledge_source.delay(source_id)
    return {"queued": len(source_ids)}


async def _active_local_knowledge_source_ids():
    from app.core.db import async_session
    from app.models.knowledge import KnowledgeSource

    async with async_session() as db:
        result = await db.execute(select(KnowledgeSource.id).where(
            KnowledgeSource.is_active.is_(True), KnowledgeSource.source_type == "local_folder",
        ))
        return [str(item) for item in result.scalars().all()]

@celery_app.task(name="app.tasks.fail_stale_agent_runs")
def fail_stale_agent_runs():
    """Finalize runs abandoned by process crashes or lost clients."""
    import asyncio
    from sqlalchemy import update
    task_engine = create_async_engine(settings.database_url)
    task_session = sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)

    async def _finalize():
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=settings.agent_run_stale_minutes)
        async with task_session() as session:
            result = await session.execute(
                update(AgentRun)
                .where(AgentRun.status == "running", AgentRun.started_at < cutoff)
                .values(
                    status="failed",
                    ended_at=datetime.datetime.utcnow(),
                    error_code="RunTimeout",
                    error_message="Run exceeded the maximum active lifetime",
                )
                .returning(AgentRun.id)
            )
            run_ids = list(result.scalars().all())
            await session.commit()
            return len(run_ids)

    async def _run():
        try:
            return await _finalize()
        finally:
            await task_engine.dispose()

    return asyncio.run(_run())


@celery_app.task(name="app.tasks.reset_daily_counters")
def reset_daily_counters():
    """Reset spent_today for all API keys at midnight."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    
    task_engine = create_async_engine(settings.database_url)
    task_session = sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)
    
    async def _reset():
        async with task_session() as session:
            stmt = text("UPDATE user_api_keys SET spent_today = 0")
            await session.execute(stmt)
            await session.commit()
    
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_reset())
    finally:
        loop.run_until_complete(task_engine.dispose())
        loop.close()
    return "Daily counters reset"


@celery_app.task(name="app.tasks.cleanup_old_sessions")
def cleanup_old_sessions():
    """Delete sessions older than 90 days."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    
    # Create a fresh engine for this task to avoid shared connection issues
    task_engine = create_async_engine(settings.database_url)
    task_session = sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)
    
    async def _cleanup():
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)
        async with task_session() as session:
            from sqlalchemy import bindparam
            result = await session.execute(
                select(Session.id).where(Session.created_at < bindparam("cutoff")),
                {"cutoff": cutoff}
            )
            old_session_ids = [row[0] for row in result.all()]
            deleted = 0
            for session_id in old_session_ids:
                await session.execute(
                    delete(Message).where(Message.session_id == session_id)
                )
                await session.execute(
                    delete(Session).where(Session.id == session_id)
                )
                deleted += 1
            await session.commit()
            return f"Cleaned up {deleted} old sessions"
    
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_cleanup())
    finally:
        loop.run_until_complete(task_engine.dispose())
        loop.close()
    return result


@celery_app.task(bind=True, max_retries=5, name="app.tasks.send_email_notification")
def send_email_notification(self, to_email: str, subject: str, body: str, alert_id: str | None = None):
    """Send an email notification via SMTP."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from app.core.config import settings

    if not settings.smtp_host:
        raise RuntimeError("SMTP is not configured")

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.smtp_from_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        port = settings.smtp_port
        use_tls = port != 465

        if use_tls:
            server = smtplib.SMTP(settings.smtp_host, port)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(settings.smtp_host, port)

        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)
        server.quit()
        if alert_id:
            async def _mark_delivered():
                from app.models.alert_event import AlertEvent
                delivery_engine = create_async_engine(settings.database_url)
                delivery_session = sessionmaker(delivery_engine, class_=AsyncSession, expire_on_commit=False)
                try:
                    async with delivery_session() as session:
                        alert = await session.get(AlertEvent, UUID(alert_id))
                        if alert:
                            alert.last_notified_at = datetime.datetime.utcnow()
                            await session.commit()
                finally:
                    await delivery_engine.dispose()
            import asyncio
            asyncio.run(_mark_delivered())
        return f"Email sent to {to_email}"
    except Exception as e:
        countdown = min(300, 10 * (2 ** self.request.retries))
        raise self.retry(exc=e, countdown=countdown)


@celery_app.task(name="app.tasks.evaluate_platform_alerts")
def evaluate_platform_alerts():
    """Evaluate operational alerts and persist them for the admin dashboard."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings

    task_engine = create_async_engine(settings.database_url)
    task_session = sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)

    async def _evaluate():
        async with task_session() as session:
            candidates = await alert_service.collect_candidates(session)
            result = await alert_service.sync_candidates(session, candidates)
            if settings.smtp_host and settings.alert_notification_recipients:
                pending_alerts = await alert_service.pending_notifications(session)
                for alert in pending_alerts:
                    subject = alert_service.notification_subject(alert)
                    body = alert_service.notification_body(alert)
                    for recipient in settings.alert_notification_recipients:
                        send_email_notification.delay(recipient, subject, body, str(alert.id))
            await session.commit()
            return result

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_evaluate())
    finally:
        loop.run_until_complete(task_engine.dispose())
        loop.close()
    return result
