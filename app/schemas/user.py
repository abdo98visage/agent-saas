from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional
from uuid import UUID


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    department: Optional[str] = None
    role: str = "employee"
    max_tokens_per_day: int = 50000
    max_requests_per_day: int = 200


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserQuotaUpdate(BaseModel):
    max_tokens_per_day: int
    max_requests_per_day: int


class UserResponse(BaseModel):
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
