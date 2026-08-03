from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


def _normalized_tools(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item or len(item) > 200:
            raise ValueError("MCP tool names must be between 1 and 200 characters")
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


class McpServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str = Field("", max_length=2000)
    url: str = Field(..., min_length=8, max_length=2048)
    auth_type: str = Field("none", pattern=r"^(none|bearer|api_key|oauth)$")
    credential_mode: str = Field("user", pattern=r"^(platform|user)$")
    api_key_header: str = Field("Authorization", min_length=1, max_length=100)
    credential: Optional[str] = Field(None, max_length=10000)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_platform_credential(self):
        if self.auth_type == "oauth":
            raise ValueError("OAuth MCP connections are not enabled yet")
        if self.credential_mode == "platform" and self.auth_type != "none" and not self.credential:
            raise ValueError("A platform credential is required for this MCP server")
        return self


class McpServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    url: Optional[str] = Field(None, min_length=8, max_length=2048)
    auth_type: Optional[str] = Field(None, pattern=r"^(none|bearer|api_key|oauth)$")
    credential_mode: Optional[str] = Field(None, pattern=r"^(platform|user)$")
    api_key_header: Optional[str] = Field(None, min_length=1, max_length=100)
    credential: Optional[str] = Field(None, max_length=10000)
    is_active: Optional[bool] = None


class McpDiscoveryRequest(BaseModel):
    credential: Optional[str] = Field(None, max_length=10000)


class McpUserConnectRequest(BaseModel):
    credential: Optional[str] = Field(None, max_length=10000)


class ProfileMcpBindingUpsert(BaseModel):
    server_id: UUID
    allowed_tools: list[str] = Field(default_factory=list, max_length=200)
    approval_required_tools: list[str] = Field(default_factory=list, max_length=200)
    is_active: bool = True

    @field_validator("allowed_tools", "approval_required_tools")
    @classmethod
    def normalize_tools(cls, value: list[str]) -> list[str]:
        return _normalized_tools(value)

    @model_validator(mode="after")
    def validate_approval_subset(self):
        if self.is_active and not self.allowed_tools:
            raise ValueError("An active MCP profile binding must allow at least one tool")
        invalid = set(self.approval_required_tools) - set(self.allowed_tools)
        if invalid:
            raise ValueError("Approval-required MCP tools must also be allowed")
        return self
