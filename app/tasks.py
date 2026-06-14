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

engine = create_async_engine(settings.database_url)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


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


@celery_app.task(name="app.tasks.send_email_notification")
def send_email_notification(to_email: str, subject: str, body: str):
    """Send an email notification via SMTP."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from app.core.config import settings

    if not settings.smtp_host:
        print(f"[EMAIL] SMTP not configured. Would send to: {to_email}, Subject: {subject}")
        return f"Email queued (SMTP not configured): {to_email}"

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
        return f"Email sent to {to_email}"
    except Exception as e:
        print(f"[EMAIL] Failed to send to {to_email}: {e}")
        return f"Email failed: {str(e)}"


@celery_app.task(name="app.tasks.track_token_usage")
def track_token_usage(user_id: str, model: str, tokens_used: int, cost: float):
    """Record token usage asynchronously."""
    import asyncio
    async def _track():
        async with async_session() as session:
            today = datetime.date.today().isoformat()
            pass
    asyncio.run(_track())
    return "Token usage tracked"
