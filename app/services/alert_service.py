from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_run import AgentRun
from app.models.alert_event import AlertEvent
from app.models.profile import Profile
from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.services.hermes_orchestrator import hermes_orchestrator


@dataclass
class AlertCandidate:
    alert_type: str
    severity: str
    title: str
    message: str
    fingerprint: str
    context: dict


class AlertService:
    async def collect_candidates(self, db: AsyncSession) -> list[AlertCandidate]:
        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        candidates: list[AlertCandidate] = []

        try:
            hermes = await hermes_orchestrator.status()
            if hermes.get("run_health") == "unhealthy" or hermes.get("status") in {"error", "unhealthy"}:
                candidates.append(
                    AlertCandidate(
                        alert_type="hermes_runtime",
                        severity="critical",
                        title="Agent runtime is unhealthy",
                        message="The agent runtime is unreachable or unhealthy.",
                        fingerprint="hermes_runtime",
                        context=hermes,
                    )
                )
        except Exception as exc:
            candidates.append(
                AlertCandidate(
                    alert_type="hermes_runtime",
                    severity="critical",
                    title="Agent runtime check failed",
                    message="The agent runtime status check raised an exception.",
                    fingerprint="hermes_runtime",
                    context={"error": str(exc)},
                )
            )

        failed_profile_syncs = await db.execute(
            select(func.count(Profile.id)).where(Profile.hermes_sync_status.in_(["sync_failed", "not_configured"]))
        )
        failed_profile_syncs_count = int(failed_profile_syncs.scalar() or 0)
        if failed_profile_syncs_count:
            candidates.append(
                AlertCandidate(
                    alert_type="profile_sync",
                    severity="warning",
                    title="Profile sync issues detected",
                    message=f"{failed_profile_syncs_count} agent profiles need sync attention.",
                    fingerprint="profile_sync",
                    context={"count": failed_profile_syncs_count},
                )
            )

        failed_runs_today = await db.execute(
            select(func.count(AgentRun.id)).where(
                AgentRun.created_at >= today_start,
                AgentRun.status == "failed",
            )
        )
        failed_runs_today_count = int(failed_runs_today.scalar() or 0)
        if failed_runs_today_count:
            candidates.append(
                AlertCandidate(
                    alert_type="agent_runs",
                    severity="critical" if failed_runs_today_count >= 5 else "warning",
                    title="Failed agent runs detected",
                    message=f"{failed_runs_today_count} agent runs failed today.",
                    fingerprint="failed_runs_today",
                    context={"count": failed_runs_today_count},
                )
            )

        key_result = await db.execute(select(UserApiKey).where(UserApiKey.is_active == True))
        for key in key_result.scalars().all():
            percent_used = round((key.spent_today / key.daily_budget) * 100, 2) if key.daily_budget else 0.0
            if percent_used >= 70:
                owner_ref = str(key.user_id or key.profile_id or "platform")
                candidates.append(
                    AlertCandidate(
                        alert_type="api_key_budget",
                        severity="critical" if percent_used >= 90 else "warning",
                        title="API key budget pressure",
                        message=f"{key.provider} {key.owner_type} key reached {percent_used}% of its daily token budget.",
                        fingerprint=f"api_key_budget:{key.id}",
                        context={
                            "key_id": str(key.id),
                            "provider": key.provider,
                            "owner_type": key.owner_type,
                            "owner_ref": owner_ref,
                            "spent_today": key.spent_today,
                            "daily_budget": key.daily_budget,
                            "percent_used": percent_used,
                        },
                    )
                )

        user_kpi_result = await db.execute(
            select(User.email, User.full_name, User.id, func.coalesce(func.sum(AgentRun.total_cost), 0), func.coalesce(func.sum(AgentRun.output_tokens + AgentRun.input_tokens), 0))
            .join(AgentRun, AgentRun.user_id == User.id)
            .where(AgentRun.created_at >= today_start)
            .group_by(User.email, User.full_name, User.id)
        )
        for email, full_name, user_id, total_cost, total_tokens in user_kpi_result.all():
            total_cost = float(total_cost or 0.0)
            total_tokens = int(total_tokens or 0)
            if total_cost > settings.kpi_cost_alert_threshold or total_tokens > settings.kpi_token_alert_threshold:
                candidates.append(
                    AlertCandidate(
                        alert_type="user_usage",
                        severity="critical" if total_cost > settings.kpi_cost_alert_threshold else "warning",
                        title="User usage threshold exceeded",
                        message=f"{email} exceeded configured KPI alert thresholds.",
                        fingerprint=f"user_usage:{user_id}",
                        context={
                            "user_id": str(user_id),
                            "email": email,
                            "full_name": full_name,
                            "total_cost": total_cost,
                            "total_tokens": total_tokens,
                        },
                    )
                )

        return candidates

    async def sync_candidates(self, db: AsyncSession, candidates: list[AlertCandidate]) -> dict:
        now = datetime.utcnow()
        active_fingerprints = {candidate.fingerprint for candidate in candidates}
        existing_result = await db.execute(select(AlertEvent))
        existing_alerts = {alert.fingerprint: alert for alert in existing_result.scalars().all()}

        activated = 0
        resolved = 0
        active_ids: list[str] = []

        for candidate in candidates:
            alert = existing_alerts.get(candidate.fingerprint)
            if alert:
                alert.severity = candidate.severity
                alert.title = candidate.title
                alert.message = candidate.message
                alert.context = candidate.context
                alert.status = "active"
                alert.last_seen_at = now
            else:
                alert = AlertEvent(
                    alert_type=candidate.alert_type,
                    severity=candidate.severity,
                    status="active",
                    title=candidate.title,
                    message=candidate.message,
                    fingerprint=candidate.fingerprint,
                    context=candidate.context,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(alert)
                activated += 1
            active_ids.append(candidate.fingerprint)

        for fingerprint, alert in existing_alerts.items():
            if alert.status == "active" and fingerprint not in active_fingerprints:
                alert.status = "resolved"
                alert.last_seen_at = now
                resolved += 1

        return {"active": len(active_ids), "activated": activated, "resolved": resolved}

    async def list_alerts(
        self,
        db: AsyncSession,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[AlertEvent]:
        query = select(AlertEvent).order_by(desc(AlertEvent.last_seen_at), desc(AlertEvent.created_at)).limit(limit)
        if status:
            query = query.where(AlertEvent.status == status)
        if severity:
            query = query.where(AlertEvent.severity == severity)
        return list((await db.execute(query)).scalars().all())

    async def acknowledge(self, db: AsyncSession, alert_id: str) -> AlertEvent | None:
        alert = await db.get(AlertEvent, alert_id)
        if not alert:
            return None
        alert.is_acknowledged = True
        return alert

    async def pending_notifications(self, db: AsyncSession) -> list[AlertEvent]:
        cooldown_cutoff = datetime.utcnow() - timedelta(minutes=settings.alert_notification_cooldown_minutes)
        result = await db.execute(
            select(AlertEvent)
            .where(
                AlertEvent.status == "active",
                AlertEvent.severity == "critical",
                AlertEvent.is_acknowledged == False,
            )
            .order_by(desc(AlertEvent.last_seen_at))
        )
        alerts = []
        for alert in result.scalars().all():
            if alert.last_notified_at is None or alert.last_notified_at <= cooldown_cutoff:
                alerts.append(alert)
        return alerts

    def notification_subject(self, alert: AlertEvent) -> str:
        return f"[AgentSaaS][{alert.severity.upper()}] {alert.title}"

    def notification_body(self, alert: AlertEvent) -> str:
        context_lines = "".join(
            f"<li><strong>{key}</strong>: {value}</li>"
            for key, value in (alert.context or {}).items()
        )
        return (
            f"<h3>{alert.title}</h3>"
            f"<p>{alert.message}</p>"
            f"<p><strong>Type:</strong> {alert.alert_type}</p>"
            f"<p><strong>Severity:</strong> {alert.severity}</p>"
            f"<p><strong>First seen:</strong> {alert.first_seen_at}</p>"
            f"<p><strong>Last seen:</strong> {alert.last_seen_at}</p>"
            f"<ul>{context_lines}</ul>"
        )


alert_service = AlertService()
