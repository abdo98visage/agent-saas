from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatRequest(BaseModel):
    agent_slug: str
    message: str
    conversation_id: Optional[str] = None


class RunAgentRequest(BaseModel):
    agent_slug: str
    prompt: str
    model: Optional[str] = None
    temperature: Optional[float] = None


class DocumentUploadRequest(BaseModel):
    organization_id: str
