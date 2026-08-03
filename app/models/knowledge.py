from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_sources"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    root_path: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(32), default="internal", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sync_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    sync_error: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    document_count: Mapped[int] = mapped_column(Integer, default=0)


class KnowledgeSourceUser(Base, TimestampMixin):
    __tablename__ = "knowledge_source_users"

    source_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)


class KnowledgeDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_documents"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_knowledge_document_source_external"),)

    source_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime)
    document_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)


class KnowledgeChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("document_id", "ordinal", name="uq_knowledge_chunk_document_ordinal"),)

    source_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
