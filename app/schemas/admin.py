"""Admin API Pydantic schemas — input validation for all admin endpoints."""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from uuid import UUID


# Disable Pydantic protected_namespaces warning for model_* fields
class _BaseSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


# --- Employees ---

class EmployeeCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=50)
    role: str = Field("employee", pattern="^(employee|admin)$")
    max_tokens_per_day: int = Field(50000, ge=1000, le=10000000)
    max_requests_per_day: int = Field(200, ge=10, le=100000)


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, pattern="^(employee|admin)$")
    is_active: Optional[bool] = None
    max_tokens_per_day: Optional[int] = Field(None, ge=1000, le=10000000)
    max_requests_per_day: Optional[int] = Field(None, ge=10, le=100000)


class EmployeeQuotas(BaseModel):
    max_tokens_per_day: int = Field(..., ge=1000, le=10000000)
    max_requests_per_day: int = Field(..., ge=10, le=100000)


# --- Profiles ---

class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50, pattern="^[a-z0-9-]+$")
    agents_md: str = Field("", max_length=50000)
    soul_md: str = Field("", max_length=50000)
    skills: list[str] = Field(default_factory=list)
    system_prompt: str = Field("", max_length=20000)


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    soul_md: Optional[str] = Field(None, max_length=50000)
    agents_md: Optional[str] = Field(None, max_length=50000)
    skills: Optional[list[str]] = None
    system_prompt: Optional[str] = Field(None, max_length=20000)
    is_active: Optional[bool] = None


# --- Assignments ---

class AssignmentCreate(BaseModel):
    user_id: UUID
    profile_id: UUID
    priority: int = Field(0, ge=0, le=99)


# --- Agent Templates ---

class AgentTemplateCreate(_BaseSchema):
    name: str = Field(..., min_length=1, max_length=50, pattern="^[a-z0-9-]+$")
    department: Optional[str] = Field(None, max_length=50)
    system_prompt: str = Field("", max_length=20000)
    tools: list[str] = Field(default_factory=list)
    model_name: str = Field("qwen3-14b", max_length=100)
    max_tokens_per_request: int = Field(4000, ge=100, le=32000)
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class AgentTemplateUpdate(_BaseSchema):
    department: Optional[str] = Field(None, max_length=50)
    system_prompt: Optional[str] = Field(None, max_length=20000)
    tools: Optional[list[str]] = None
    model_name: Optional[str] = Field(None, max_length=100)
    max_tokens_per_request: Optional[int] = Field(None, ge=100, le=32000)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)


# --- API Keys ---

class ApiKeyCreate(BaseModel):
    user_id: UUID
    provider: str = Field(..., pattern="^(minimax|openai|ollama)$")
    api_key: str = Field(..., min_length=10, max_length=500)
    daily_budget: int = Field(50000, ge=1000, le=10000000)


class ApiKeyUpdate(BaseModel):
    is_active: Optional[bool] = None
    daily_budget: Optional[int] = Field(None, ge=1000, le=10000000)
    api_key: Optional[str] = Field(None, min_length=10, max_length=500)
