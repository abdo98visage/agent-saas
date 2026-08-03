from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class KnowledgeSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    slug: str = Field(min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    source_type: Literal["managed_upload", "local_folder"]
    root_path: str | None = Field(default=None, max_length=2000)
    classification: Literal["internal", "confidential_local_only"] = "internal"
    allowed_user_ids: list[UUID] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def validate_root(self):
        if self.source_type == "local_folder" and not self.root_path:
            raise ValueError("root_path is required for local_folder")
        if self.source_type == "managed_upload" and self.root_path:
            raise ValueError("root_path is not used for managed_upload")
        return self


class KnowledgeAssignments(BaseModel):
    user_ids: list[UUID] = Field(max_length=1000)


class KnowledgeSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    root_path: str | None = Field(default=None, max_length=2000)
    classification: Literal["internal", "confidential_local_only"] | None = None
    is_active: bool | None = None


class ManagedDocument(BaseModel):
    external_id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=200000)
    metadata: dict = Field(default_factory=dict)


class ManagedDocumentImport(BaseModel):
    documents: list[ManagedDocument] = Field(max_length=100)
    replace_all: bool = True
