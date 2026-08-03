"""Prometheus-compatible operational metrics without prompt or secret content."""
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db


router = APIRouter()


def _metric(name: str, value, labels: dict[str, str] | None = None) -> str:
    suffix = ""
    if labels:
        escaped = [f'{key}="{str(value).replace(chr(34), chr(92) + chr(34))}"' for key, value in labels.items()]
        suffix = "{" + ",".join(escaped) + "}"
    return f"{name}{suffix} {value}"


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
    db: AsyncSession = Depends(get_db),
):
    if settings.metrics_token:
        if not x_metrics_token or not secrets.compare_digest(x_metrics_token, settings.metrics_token):
            raise HTTPException(status_code=403, detail="Invalid metrics token")
    elif settings.environment.lower() == "production":
        raise HTTPException(status_code=503, detail="Metrics endpoint is not configured")

    task_rows = (await db.execute(text("SELECT status, count(*) FROM durable_tasks GROUP BY status"))).all()
    schedule_rows = (await db.execute(text("""
        SELECT event_type, count(*) FROM durable_task_events
        WHERE event_type IN ('schedule_enqueued', 'schedule_skipped', 'succeeded', 'failed')
        GROUP BY event_type
    """))).all()
    run_stats = (await db.execute(text("""
        SELECT count(*),
               coalesce(avg(latency_ms), 0),
               coalesce(sum(input_tokens), 0),
               coalesce(sum(output_tokens), 0),
               coalesce(sum(total_cost), 0)
        FROM agent_runs WHERE created_at >= now() - interval '24 hours'
    """))).one()
    pending_approvals = (await db.execute(text(
        "SELECT count(*) FROM approval_requests WHERE status = 'pending'"
    ))).scalar_one()
    approval_wait = (await db.execute(text("""
        SELECT coalesce(avg(extract(epoch from (coalesce(decided_at, now()) - created_at))), 0)
        FROM approval_requests
    """))).scalar_one()
    audit_valid = (await db.execute(text("SELECT verify_audit_log_chain()"))).scalar_one()
    knowledge_rows = (await db.execute(text("SELECT sync_status, count(*), coalesce(sum(document_count), 0) FROM knowledge_sources GROUP BY sync_status"))).all()

    lines = [
        "# HELP fqsaas_durable_tasks Current durable tasks by state.",
        "# TYPE fqsaas_durable_tasks gauge",
        *[_metric("fqsaas_durable_tasks", count, {"status": status}) for status, count in task_rows],
        "# HELP fqsaas_pending_approvals Pending durable task approvals.",
        "# TYPE fqsaas_pending_approvals gauge",
        _metric("fqsaas_pending_approvals", pending_approvals),
        "# HELP fqsaas_approval_wait_seconds Average approval wait time.",
        "# TYPE fqsaas_approval_wait_seconds gauge",
        _metric("fqsaas_approval_wait_seconds", float(approval_wait)),
        "# HELP fqsaas_agent_runs_24h Agent runs in the last 24 hours.",
        "# TYPE fqsaas_agent_runs_24h gauge",
        _metric("fqsaas_agent_runs_24h", run_stats[0]),
        _metric("fqsaas_agent_latency_ms_24h", float(run_stats[1])),
        _metric("fqsaas_input_tokens_24h", run_stats[2]),
        _metric("fqsaas_output_tokens_24h", run_stats[3]),
        _metric("fqsaas_cost_24h", float(run_stats[4])),
        _metric("fqsaas_audit_chain_valid", 1 if audit_valid else 0),
        *[_metric("fqsaas_knowledge_sources", count, {"status": sync_status}) for sync_status, count, _documents in knowledge_rows],
        *[_metric("fqsaas_knowledge_documents", documents, {"status": sync_status}) for sync_status, _count, documents in knowledge_rows],
        *[_metric("fqsaas_task_events_total", count, {"event": event}) for event, count in schedule_rows],
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
