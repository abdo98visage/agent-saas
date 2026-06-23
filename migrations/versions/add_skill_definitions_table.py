"""add skill definitions table

Revision ID: add_skill_definitions_table
Revises: add_user_token_version
Create Date: 2026-06-23 11:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_skill_definitions_table"
down_revision = "add_user_token_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_definitions",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("instructions_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_skill_definitions_is_active"), "skill_definitions", ["is_active"], unique=False)
    op.create_index(op.f("ix_skill_definitions_name"), "skill_definitions", ["name"], unique=True)
    op.create_index(op.f("ix_skill_definitions_slug"), "skill_definitions", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_skill_definitions_slug"), table_name="skill_definitions")
    op.drop_index(op.f("ix_skill_definitions_name"), table_name="skill_definitions")
    op.drop_index(op.f("ix_skill_definitions_is_active"), table_name="skill_definitions")
    op.drop_table("skill_definitions")
