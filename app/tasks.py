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
