from sqlalchemy import BigInteger, String, ForeignKey, Integer, Text, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import TimestampMixin
from app.core.db import Base
from uuid import UUID
from app.core.audit_context import current_correlation_id, current_trace_id


_SENSITIVE_KEYS = {
    "authorization", "content", "credential", "credentials", "message", "password",
    "prompt", "secret", "token", "api_key", "access_token", "refresh_token",
}


def redact_audit_details(value):
    """Remove prompt, credential, and message bodies before an audit row is persisted."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if str(key).lower() in _SENSITIVE_KEYS else redact_audit_details(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_audit_details(item) for item in value]
    return value


def audit_category(action: str) -> str:
    action = (action or "").lower()
    for prefix, category in (
        (("login", "logout", "account_", "auth_"), "identity"),
        (("mcp_", "profile_mcp"), "connector"),
        (("task_", "schedule_"), "task"),
        (("approval_",), "approval"),
        (("add_profile", "update_profile", "delete_profile", "assign_profile", "sync_profile"), "policy"),
        (("add_skill", "update_skill", "delete_skill"), "skill"),
        (("chat_", "agent_", "hermes_"), "agent"),
        (("delete_", "export_", "retention_"), "data_governance"),
    ):
        if action.startswith(prefix):
            return category
    return "platform"


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    event_version: Mapped[int] = mapped_column(default=1, nullable=False)
    event_category: Mapped[str] = mapped_column(String(50), default="platform", nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(30), default="user", nullable=False)
    subject_type: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    subject_id: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), default=current_correlation_id, nullable=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), default=current_trace_id, nullable=True, index=True)
    run_id: Mapped[UUID] = mapped_column(nullable=True, index=True)
    task_id: Mapped[UUID] = mapped_column(nullable=True, index=True)
    session_id: Mapped[UUID] = mapped_column(nullable=True, index=True)
    policy_id: Mapped[str] = mapped_column(String(150), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="0" * 64)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


@event.listens_for(AuditLog, "before_insert")
def _normalize_audit_event(_mapper, _connection, target: AuditLog) -> None:
    target.details = redact_audit_details(target.details or {})
    if not target.event_category:
        target.event_category = audit_category(target.action)


class AuditExportCheckpoint(Base, TimestampMixin):
    __tablename__ = "audit_export_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    destination: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    last_audit_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
