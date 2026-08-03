"""
Celery application for async tasks and scheduled jobs.
"""
import sys
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "fq_saas",
    broker=settings.celery_broker_url,
    backend=settings.redis_url,
)

# Windows compatibility: use solo pool (single-process)
# On Linux/macOS, prefork (default) works fine with multiprocessing
if sys.platform == "win32":
    celery_app.conf.update(task_always_eager=False, worker_pool="solo")

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Riyadh",
    enable_utc=True,
    beat_schedule={
        # Reset daily API key token counters at midnight
        "reset-daily-token-counters": {
            "task": "app.tasks.reset_daily_counters",
            "schedule": crontab(hour=0, minute=0),
        },
        # Cleanup old sessions (older than 90 days) daily
        "cleanup-old-sessions": {
            "task": "app.tasks.cleanup_old_sessions",
            "schedule": crontab(hour=2, minute=0),
        },
        "evaluate-platform-alerts": {
            "task": "app.tasks.evaluate_platform_alerts",
            "schedule": crontab(minute="*/10"),
        },
        "fail-stale-agent-runs": {
            "task": "app.tasks.fail_stale_agent_runs",
            "schedule": crontab(minute="*/10"),
        },
        "enqueue-due-agent-tasks": {
            "task": "app.tasks.enqueue_due_agent_tasks",
            "schedule": crontab(minute="*"),
        },
        "recover-stale-durable-tasks": {
            "task": "app.tasks.recover_stale_durable_tasks",
            "schedule": crontab(minute="*/2"),
        },
        "export-audit-events": {
            "task": "app.tasks.export_audit_events",
            "schedule": crontab(minute="*/2"),
        },
        "sync-knowledge-sources": {
            "task": "app.tasks.sync_all_knowledge_sources",
            "schedule": crontab(minute="*/15"),
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])
