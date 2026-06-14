"""Admin response schemas — used by __init__.py."""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID


class AdminUserList(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str] = None
    department: Optional[str] = None
    role: str
    is_active: bool
    max_tokens_per_day: int
    max_requests_per_day: int
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class AdminKPIResponse(BaseModel):
    user_id: str
    date: str
    tasks_completed: int
    messages_sent: int
    avg_response_quality: Optional[float] = None
    active_minutes: int
    tools_used: list


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[str] = None
    action: str
    details: dict
    ip_address: Optional[str] = None
    created_at: str
