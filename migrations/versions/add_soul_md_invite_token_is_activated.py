"""Add soul_md to profiles, invite_token and is_activated to users

Revision ID: 002_add_soul_md_invite
Revises: 64336bb416f8
Create Date: 2026-06-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '002_add_soul_md_invite'
down_revision: Union[str, None] = '64336bb416f8'
branch_labels: Union[tuple[str, ...], None] = None
depends_on: Union[tuple[str, ...], None] = None


def upgrade() -> None:
    # 1. Rename 'description' to 'soul_md' in profiles, change type to Text
    op.alter_column('profiles', 'description', new_column_name='soul_md',
                     existing_type=sa.String(500),
                     type_=sa.Text(),
                     nullable=True)

    # 2. Add invite_token to users
    op.add_column('users', sa.Column('invite_token', sa.String(64), nullable=True))
    op.create_index(op.f('ix_users_invite_token'), 'users', ['invite_token'], unique=False)

    # 3. Add is_activated to users (default True for backward compatibility)
    op.add_column('users', sa.Column('is_activated', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.create_index(op.f('ix_users_is_activated'), 'users', ['is_activated'], unique=False)


def downgrade() -> None:
    # Reverse: remove new columns, rename soul_md back to description
    op.drop_index(op.f('ix_users_is_activated'), table_name='users')
    op.drop_column('users', 'is_activated')

    op.drop_index(op.f('ix_users_invite_token'), table_name='users')
    op.drop_column('users', 'invite_token')

    op.alter_column('profiles', 'soul_md', new_column_name='description',
                     existing_type=sa.Text(),
                     type_=sa.String(500),
                     nullable=True)
