"""add ACL-aware local knowledge connectors and full-text index

Revision ID: knowledge_connectors
Revises: evaluation_gates
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "knowledge_connectors"
down_revision = "evaluation_gates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("root_path", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(32), nullable=False, server_default="internal"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sync_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("slug"),
    )
    for column in ("slug", "source_type", "classification", "is_active", "sync_status"):
        op.create_index(f"ix_knowledge_sources_{column}", "knowledge_sources", [column])
    op.create_table(
        "knowledge_source_users",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id", "user_id"),
    )
    op.create_index("ix_knowledge_source_users_user_id", "knowledge_source_users", ["user_id"])
    op.create_table(
        "knowledge_documents",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_modified_at", sa.DateTime(), nullable=True),
        sa.Column("document_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_knowledge_document_source_external"),
    )
    for column in ("source_id", "content_hash", "deleted_at"):
        op.create_index(f"ix_knowledge_documents_{column}", "knowledge_documents", [column])
    op.create_table(
        "knowledge_chunks",
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_knowledge_chunk_document_ordinal"),
    )
    op.create_index("ix_knowledge_chunks_source_id", "knowledge_chunks", ["source_id"])
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.execute("CREATE INDEX ix_knowledge_chunks_fts ON knowledge_chunks USING gin (to_tsvector('simple', content))")


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("knowledge_source_users")
    op.drop_table("knowledge_sources")
