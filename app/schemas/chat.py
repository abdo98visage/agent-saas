from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None
    agent_template_name: str = "default"
    project_context: Optional[str] = None
    profile_name: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    content: str
    tokens_used: int | None = None
    model: str | None = None
    profile_name: str | None = None


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    agent_template_name: str = "default"


class ConversationResponse(BaseModel):
    conversation_id: UUID
