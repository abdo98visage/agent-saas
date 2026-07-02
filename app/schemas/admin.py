"""Admin API Pydantic schemas — input validation for all admin endpoints."""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from uuid import UUID
from app.core.config import settings


# Disable Pydantic protected_namespaces warning for model_* fields
class _BaseSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


# --- Employees ---

class EmployeeCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=50)
    role: str = Field("employee", pattern="^(employee|admin)$")
    max_tokens_per_day: int = Field(56666666, ge=1000, le=1700000000)
    max_requests_per_day: int = Field(2000, ge=10, le=100000)


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, pattern="^(employee|admin)$")
    is_active: Optional[bool] = None
    max_tokens_per_day: Optional[int] = Field(None, ge=1000, le=1700000000)
    max_requests_per_day: Optional[int] = Field(None, ge=10, le=100000)


class EmployeeQuotas(BaseModel):
    max_tokens_per_day: int = Field(..., ge=1000, le=1700000000)
    max_requests_per_day: int = Field(..., ge=10, le=100000)


# --- Profiles ---

class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50, pattern="^[a-z0-9-]+$")
    agents_md: str = Field("", max_length=50000)
    soul_md: str = Field("", max_length=50000)
    skills: list[str] = Field(default_factory=list)
    system_prompt: str = Field("", max_length=20000)
    runtime_type: str = Field("hermes", pattern="^(hermes|direct_llm)$")
    provider_key_id: Optional[UUID] = None
    max_tokens_per_day: Optional[int] = Field(None, ge=1000, le=1700000000)
    max_requests_per_day: Optional[int] = Field(None, ge=10, le=100000)
    daily_cost_budget: Optional[int] = Field(None, ge=0, le=10000000)
    allowed_providers: list[str] = Field(default_factory=list)
    allowed_mcp_servers: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    approval_required_tools: list[str] = Field(default_factory=list)
    memory_settings: dict = Field(default_factory=dict)


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    soul_md: Optional[str] = Field(None, max_length=50000)
    agents_md: Optional[str] = Field(None, max_length=50000)
    skills: Optional[list[str]] = None
    system_prompt: Optional[str] = Field(None, max_length=20000)
    is_active: Optional[bool] = None
    runtime_type: Optional[str] = Field(None, pattern="^(hermes|direct_llm)$")
    provider_key_id: Optional[UUID] = None
    max_tokens_per_day: Optional[int] = Field(None, ge=1000, le=1700000000)
    max_requests_per_day: Optional[int] = Field(None, ge=10, le=100000)
    daily_cost_budget: Optional[int] = Field(None, ge=0, le=10000000)
    allowed_providers: Optional[list[str]] = None
    allowed_mcp_servers: Optional[list[str]] = None
    allowed_tools: Optional[list[str]] = None
    approval_required_tools: Optional[list[str]] = None
    memory_settings: Optional[dict] = None


# --- Skills ---

class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    description: str = Field("", max_length=300)
    instructions_md: str = Field("", max_length=100000)
    is_active: bool = True


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    slug: Optional[str] = Field(None, min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    description: Optional[str] = Field(None, max_length=300)
    instructions_md: Optional[str] = Field(None, max_length=100000)
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
    model_name: str = Field(settings.default_model, max_length=100)
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
    owner_type: str = Field("user", pattern="^(user|profile|platform)$")
    user_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    profile_ids: list[UUID] = Field(default_factory=list)
    provider: str = Field(..., pattern="^(minimax|openai|ollama)$")
    api_key: str = Field(..., min_length=10, max_length=500)
    daily_budget: int = Field(50000, ge=1000, le=1700000000)


class ApiKeyUpdate(BaseModel):
    owner_type: Optional[str] = Field(None, pattern="^(user|profile|platform)$")
    user_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    profile_ids: Optional[list[UUID]] = None
    provider: Optional[str] = Field(None, pattern="^(minimax|openai|ollama)$")
    is_active: Optional[bool] = None
    daily_budget: Optional[int] = Field(None, ge=1000, le=1700000000)
    api_key: Optional[str] = Field(None, min_length=10, max_length=500)


class ProviderPricingUpsert(BaseModel):
    monthly_price_usd: float = Field(..., gt=0, le=1000000)
    monthly_token_allowance: int = Field(..., gt=0, le=1000000000000)
    currency: str = Field("USD", min_length=3, max_length=8)


class AdminAgentTestMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=20000)
    profile_name: str = Field(..., min_length=1, max_length=100)
    conversation_id: Optional[UUID] = None
    agent_template_name: str = Field("default", min_length=1, max_length=50)
    project_context: Optional[str] = Field(None, max_length=20000)
