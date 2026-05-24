from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class User(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: str


class Organization(BaseModel):
    id: UUID
    name: str
    created_at: str
    owner_id: UUID


class OrganizationMember(BaseModel):
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: str  # owner, admin, member


class Agent(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str
    system_prompt: str
    model: str
    temperature: float = 0.7
    enabled_tools: list = []
    active: bool = True


class Conversation(BaseModel):
    id: UUID
    organization_id: UUID
    agent_id: UUID
    title: str
    created_at: str


class Message(BaseModel):
    id: Optional[UUID] = None
    conversation_id: UUID
    organization_id: UUID
    role: str  # user, assistant, system
    content: str
    created_at: Optional[str] = None


class TokenUsage(BaseModel):
    organization_id: UUID
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
